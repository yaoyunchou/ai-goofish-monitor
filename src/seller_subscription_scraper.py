"""卖家用户页订阅采集：独立订阅表 + 详情补抓 + 分批模拟访问。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.seller_ids import (
    DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT,
    has_want_and_view,
    parse_metric_int,
    parse_seller_user_ids,
)
from src.domain.seller_subscription import SELLER_SUBSCRIPTION_TASK_NAME
from src.domain.seller_subscription_pacing import SubscriptionPacing
from src.scraper import (
    fetch_item_detail,
    launch_task_browser,
    scrape_user_profile,
)
from src.services.seller_item_daily_storage import (
    list_item_ids_with_daily_snapshot_sync,
    load_muted_item_ids_sync,
    upsert_seller_item_daily_snapshot,
)
from src.time_utils import shanghai_now_iso
from src.services.seller_subscription_storage import (
    get_subscription_by_user_sync,
    list_subscriptions_sync,
    record_subscription_run,
    save_seller_profile,
    touch_subscription_captured,
)
from src.utils import get_link_unique_key


@dataclass
class SellerScrapePlan:
    user_id: str
    profile: dict[str, Any]
    missing_items: list[dict] = field(default_factory=list)
    covered_items: list[dict] = field(default_factory=list)
    never_captured: bool = False

    @property
    def missing_count(self) -> int:
        return len(self.missing_items)

    @property
    def covered_count(self) -> int:
        return len(self.covered_items)


def _resolve_item_limit(task_config: dict) -> int:
    raw = task_config.get("item_limit", DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT)
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_SELLER_SUBSCRIPTION_ITEM_LIMIT
    return max(1, limit)


def _never_captured_seller_ids() -> set[str]:
    """从未成功采过商品（last_captured_at 为空）的订阅卖家。"""
    never: set[str] = set()
    try:
        rows = list_subscriptions_sync()
    except Exception:
        return never
    for row in rows:
        if row.get("last_captured_at"):
            continue
        user_id = str(row.get("seller_user_id") or "").strip()
        if user_id:
            never.add(user_id)
    return never


def _order_seller_ids_for_alignment(seller_ids: list[str], never_ids: set[str]) -> list[str]:
    """对齐列表时也把从未采过的店铺排前面。"""
    return sorted(seller_ids, key=lambda user_id: (0 if user_id in never_ids else 1, user_id))


async def scrape_seller_subscription(
    task_config: dict,
    debug_limit: int = 0,
    *,
    from_registry: bool = False,
) -> int:
    """采集一批卖家。

    from_registry=True 表示卖家列表取自订阅注册表（而非任务里写死的卖家），
    此时才会在采集每个卖家前复查订阅是否还在——防止「采集中途被删除」
    导致商品数据在清理后又写回来。历史任务里写死的卖家不受此校验影响。
    """
    task_name = task_config.get("task_name") or SELLER_SUBSCRIPTION_TASK_NAME
    seller_ids = parse_seller_user_ids(
        task_config.get("seller_user_ids"),
        task_config.get("seller_urls"),
    )
    if not seller_ids:
        print("订阅任务未配置卖家，跳过。")
        await record_subscription_run("未配置卖家", saved=0, ok=False)
        return 0

    scrape_config = dict(task_config)
    scrape_config["task_name"] = task_name
    scrape_config["keyword"] = task_config.get("keyword") or task_name
    scrape_config["seller_user_ids"] = seller_ids
    return await _scrape_seller_ids(
        task_config=scrape_config,
        debug_limit=debug_limit,
        touch_registry=task_name == SELLER_SUBSCRIPTION_TASK_NAME,
        skip_unsubscribed=from_registry,
    )


async def scrape_registered_seller_subscriptions(debug_limit: int = 0) -> int:
    from src.services.seller_subscription_service import build_scrape_task_config

    task_config = await build_scrape_task_config()
    if not task_config:
        print("没有启用的卖家订阅，跳过。")
        await record_subscription_run("没有启用的卖家订阅", saved=0, ok=False)
        return 0
    try:
        saved = await scrape_seller_subscription(
            task_config, debug_limit=debug_limit, from_registry=True
        )
    except Exception as exc:
        await record_subscription_run(f"采集异常: {exc}", saved=0, ok=False)
        raise
    if saved > 0:
        await record_subscription_run(f"本次入库 {saved} 条商品指标", saved=saved, ok=True)
    else:
        await record_subscription_run(
            "采集完成但未入库任何商品，请检查登录态或卖家主页是否有在售商品",
            saved=0,
            ok=False,
        )
    return saved


def _split_items_by_today_coverage(
    *,
    task_name: str,
    user_id: str,
    items: list[dict],
) -> tuple[list[dict], list[dict]]:
    covered_ids = list_item_ids_with_daily_snapshot_sync(
        task_name=task_name,
        seller_user_id=user_id,
        item_ids=[str(it.get("商品ID") or "") for it in items],
    )
    ordered = SubscriptionPacing.prioritize_missing_today(items, covered_ids)
    missing = [it for it in ordered if str(it.get("商品ID") or "") not in covered_ids]
    covered = [it for it in ordered if str(it.get("商品ID") or "") in covered_ids]
    return missing, covered


def _build_work_queue(
    plans: list[SellerScrapePlan],
) -> tuple[list[tuple[SellerScrapePlan, dict]], list[tuple[SellerScrapePlan, dict]]]:
    """全局两阶段：先所有卖家今日未采集，再所有卖家更新已有指标。"""
    ordered_plans = SubscriptionPacing.prioritize_sellers_by_missing(
        [
            {
                "user_id": plan.user_id,
                "missing_count": plan.missing_count,
                "never_captured": plan.never_captured,
            }
            for plan in plans
        ]
    )
    plan_by_id = {plan.user_id: plan for plan in plans}
    sorted_plans = [plan_by_id[str(row["user_id"])] for row in ordered_plans]

    phase_missing: list[tuple[SellerScrapePlan, dict]] = []
    phase_updates: list[tuple[SellerScrapePlan, dict]] = []
    for plan in sorted_plans:
        for item in plan.missing_items:
            phase_missing.append((plan, item))
        for item in plan.covered_items:
            phase_updates.append((plan, item))
    return phase_missing, phase_updates


def _still_subscribed(user_id: str) -> bool:
    """订阅是否仍然存在。

    DB 读不到时按「仍订阅」处理：这只是防写回的保护，不应中断整轮采集。
    """
    try:
        return get_subscription_by_user_sync(user_id) is not None
    except Exception as exc:
        print(f"   [警告] 校验卖家 {user_id} 的订阅是否存在失败，按仍订阅处理: {exc}")
        return True


async def _scrape_seller_ids(
    *,
    task_config: dict,
    debug_limit: int,
    touch_registry: bool,
    skip_unsubscribed: bool = False,
) -> int:
    task_name = task_config.get("task_name") or SELLER_SUBSCRIPTION_TASK_NAME
    keyword = task_config.get("keyword") or task_name
    item_limit = _resolve_item_limit(task_config)
    collect_ratings = bool(task_config.get("collect_ratings", False))
    seller_ids = parse_seller_user_ids(task_config.get("seller_user_ids"))
    never_ids = _never_captured_seller_ids()
    seller_ids = _order_seller_ids_for_alignment(seller_ids, never_ids)
    pacing = SubscriptionPacing.from_task_config(task_config)
    pacing.log_plan(len(seller_ids), item_limit)

    playwright, browser, context, state_file = await launch_task_browser(task_config)
    print(f"   使用登录态: {state_file}")
    scanned = 0
    detailed = 0
    saved = 0
    skipped = 0
    seller_saved: dict[str, int] = {}
    skipped_sellers: list[tuple[str, str]] = []  # (user_id, 原因)
    try:
        plans: list[SellerScrapePlan] = []
        print(
            f"\n[策略] 阶段零：对齐 {len(seller_ids)} 个订阅卖家的商品列表"
            f"（仅主页，不做详情；从未采集 {len(never_ids)} 家优先）"
        )
        if never_ids:
            print("   · 无历史商品、优先对齐：" + "、".join(sorted(never_ids & set(seller_ids))))

        for seller_index, user_id in enumerate(seller_ids):
            await pacing.before_list_alignment(seller_index)

            # seller_ids 是任务开始时快照的。若采集途中该订阅被删除，
            # 这里必须再确认一次，否则跑完会把刚清干净的商品数据又写回去。
            if skip_unsubscribed and not _still_subscribed(str(user_id)):
                print(f"   [跳过] 卖家 {user_id} 的订阅已不存在（已被删除），不再采集其商品。")
                skipped_sellers.append((str(user_id), "订阅已被删除"))
                continue

            print(f"\n=== 拉取卖家主页 {user_id}（监控前 {item_limit} 条在售商品）===")
            await pacing.before_profile()
            profile = await scrape_user_profile(
                context,
                user_id,
                collect_ratings=collect_ratings,
                max_items=item_limit,
            )
            profile["卖家ID"] = profile.get("卖家ID") or user_id
            await save_seller_profile(task_name, user_id, profile)

            items = [
                item
                for item in (profile.get("卖家发布的商品列表") or [])
                if item.get("商品状态") == "在售"
            ][:item_limit]
            if not items:
                raw_count = len(profile.get("卖家发布的商品列表") or [])
                print(
                    f"   卖家 {user_id} 未获取到在售商品（列表共 {raw_count} 条），跳过详情采集。"
                )
                skipped_sellers.append(
                    (str(user_id), f"主页无在售商品（解析 {raw_count} 条）")
                )
                continue

            # 剔除已停止监控的商品（健康度判定自动停用或人工停用）。
            # 必须在 _split_items_by_today_coverage 之前过滤，
            # 否则「今日已采集」的判定会把已停用商品重新拉回详情队列。
            # 读取失败时降级为空集合：停用过滤是优化手段，不应中断整轮采集。
            try:
                muted_ids = load_muted_item_ids_sync(user_id)
            except Exception as exc:
                print(f"   [警告] 读取已停用商品失败，本轮不过滤: {exc}")
                muted_ids = set()
            if muted_ids:
                before = len(items)
                items = [
                    item
                    for item in items
                    if str(item.get("商品ID") or item.get("item_id") or "") not in muted_ids
                ]
                skipped_muted = before - len(items)
                if skipped_muted:
                    print(f"   ⏭ 跳过 {skipped_muted} 个已停止监控的商品")
                if not items:
                    print(f"   卖家 {user_id} 在售商品均已停止监控，跳过详情采集。")
                    skipped_sellers.append(
                        (str(user_id), f"在售商品均已停止监控（过滤 {skipped_muted} 条）")
                    )
                    continue

            missing_items, covered_items = _split_items_by_today_coverage(
                task_name=task_name,
                user_id=user_id,
                items=items,
            )
            never_captured = user_id in never_ids
            print(
                f"   列表在售 {len(items)} 条；今日未采集 {len(missing_items)} 条，"
                f"已有今日指标 {len(covered_items)} 条"
                f"{'（该店尚无历史商品，详情阶段优先）' if never_captured else ''}。"
            )
            plans.append(
                SellerScrapePlan(
                    user_id=user_id,
                    profile=profile,
                    missing_items=missing_items,
                    covered_items=covered_items,
                    never_captured=never_captured,
                )
            )

        phase_missing, phase_updates = _build_work_queue(plans)
        total_missing = len(phase_missing)
        total_updates = len(phase_updates)
        print(
            f"\n[策略] 阶段一：今日未采集 {total_missing} 条"
            f"（无历史商品的店铺优先，全部补齐后再更新）"
        )
        for plan in SubscriptionPacing.prioritize_sellers_by_missing(
            [
                {
                    "user_id": p.user_id,
                    "missing_count": p.missing_count,
                    "never_captured": p.never_captured,
                }
                for p in plans
            ]
        ):
            if int(plan["missing_count"]) > 0:
                flag = " [无历史商品]" if plan.get("never_captured") else ""
                print(f"   · 卖家 {plan['user_id']}：今日未采集 {plan['missing_count']} 条{flag}")
        print(
            f"[策略] 阶段二：更新已有今日指标 {total_updates} 条"
            f"（全部卖家今日未采集完成后执行）"
        )

        last_user_id: str | None = None
        detail_index = 0
        for phase_name, work_queue in (
            ("今日未采集", phase_missing),
            ("更新已有", phase_updates),
        ):
            if not work_queue:
                continue
            print(f"\n--- 开始阶段：{phase_name}（{len(work_queue)} 条）---")
            for plan, item in work_queue:
                user_id = plan.user_id
                profile = plan.profile
                if last_user_id is not None and last_user_id != user_id:
                    print(f"   [策略] 切换卖家 {last_user_id} → {user_id}")
                    await pacing.before_seller(1)
                last_user_id = user_id

                scanned += 1
                if debug_limit > 0 and saved >= debug_limit:
                    print(f"已达到调试上限 {debug_limit}，停止采集。")
                    return saved

                item_id = item.get("商品ID")
                item_link = item.get("商品链接") or (
                    f"https://www.goofish.com/item?id={item_id}" if item_id else ""
                )
                if not item_link:
                    skipped += 1
                    continue

                print(
                    f"   [{phase_name}] 卖家 {user_id} 商品 {item_id} "
                    f"「{str(item.get('商品标题') or '')[:24]}」"
                )
                await pacing.before_detail(detail_index)
                detail_index += 1
                detailed += 1
                try:
                    detail = await fetch_item_detail(context, item_link)
                except Exception as exc:
                    print(f"   详情采集失败 {item_id}: {exc}")
                    skipped += 1
                    continue
                if not detail.get("ok"):
                    skipped += 1
                    continue

                item_data = {
                    "商品ID": item_id,
                    "商品标题": item.get("商品标题"),
                    "当前售价": item.get("商品价格"),
                    "商品主图链接": item.get("商品主图"),
                    "商品链接": item_link,
                    "商品状态": item.get("商品状态"),
                    "“想要”人数": detail.get("“想要”人数"),
                    "浏览量": detail.get("浏览量"),
                    "商品图片列表": detail.get("商品图片列表") or [],
                    "商品描述": detail.get("商品描述") or "",
                }
                if not has_want_and_view(item_data):
                    skipped += 1
                    print(f"   跳过 {item_id}：缺少有效的想要/浏览量")
                    continue

                want_count = parse_metric_int(item_data["“想要”人数"])
                view_count = parse_metric_int(item_data["浏览量"])
                record = {
                    "爬取时间": shanghai_now_iso(),
                    "搜索关键字": keyword,
                    "任务名称": task_name,
                    "任务类型": "seller_subscription",
                    "商品信息": item_data,
                    "卖家信息": {
                        "卖家ID": user_id,
                        "卖家昵称": profile.get("卖家昵称"),
                        "鱼小铺等级": profile.get("鱼小铺等级"),
                        "粉丝数": profile.get("粉丝数"),
                        "好评率": profile.get("好评率"),
                    },
                }
                item_data["_want_count"] = want_count
                item_data["_view_count"] = view_count
                detail_api_raw = detail.get("detail_api_raw")
                await upsert_seller_item_daily_snapshot(
                    task_name=task_name,
                    seller_user_id=user_id,
                    item=item_data,
                    crawl_record=record,
                    detail_api_raw=detail_api_raw if isinstance(detail_api_raw, dict) else None,
                )
                saved += 1
                seller_saved[user_id] = seller_saved.get(user_id, 0) + 1
                print(
                    f"   入库 {item_id} 想要={want_count} 浏览={view_count} "
                    f"key={get_link_unique_key(item_link)}"
                )
                await pacing.after_detail(detail_index - 1)

        for user_id, count in seller_saved.items():
            if touch_registry and count > 0:
                nickname = next(
                    (p.profile.get("卖家昵称") for p in plans if p.user_id == user_id),
                    None,
                )
                await touch_subscription_captured(user_id, nickname)

        print(
            f"订阅任务完成：扫描 {scanned} → 详情 {detailed} → 入库 {saved} → 跳过 {skipped}"
        )
        if skipped_sellers:
            print(
                f"[店铺汇总] 订阅 {len(seller_ids)} 家 → 有商品入库 "
                f"{len(seller_saved)} 家 → 整店跳过 {len(skipped_sellers)} 家"
            )
            for seller_id, reason in skipped_sellers:
                print(f"   · 跳过店铺 {seller_id}：{reason}")
        return saved
    finally:
        await browser.close()
        await playwright.stop()
