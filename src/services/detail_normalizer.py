"""将 MTOP detail_data 拆分写入 goofish_ 规范化表。"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Optional
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text
from src.utils import log_time


def _now() -> str:
    return datetime.now().isoformat()

def _ss(v: Any) -> Optional[str]:
    if v is None: return None
    s = str(v)
    return s if s else None

def _si(v: Any) -> Optional[int]:
    if v is None: return None
    try: return int(v)
    except (TypeError, ValueError): return None

def _sb(v: Any) -> Optional[bool]:
    if isinstance(v, bool): return v
    return None

def _sf(v: Any) -> Optional[float]:
    if v is None: return None
    try: return float(v)
    except (TypeError, ValueError): return None


def normalize_and_save_detail(detail_data: dict, collected_item_id: int) -> None:
    """将完整 MTOP detail_data 拆分写入 goofish_ 规范化表。"""
    if not isinstance(detail_data, dict) or not detail_data:
        return
    item_do = detail_data.get("itemDO") or {}
    seller_do = detail_data.get("sellerDO") or {}
    track_params = detail_data.get("trackParams") or {}
    buyer_do = detail_data.get("buyerDO") or {}
    config_info = detail_data.get("configInfo") or {}
    server_time = detail_data.get("serverTime") or ""
    item_id = _ss(item_do.get("itemId"))
    seller_id = _ss(seller_do.get("sellerId")) or _ss(seller_do.get("pageUserId")) or _ss(seller_do.get("userId")) or _ss(track_params.get("sellerId"))
    if not item_id:
        log_time(f"[Normalizer] 跳过：缺少 item_id (collected={collected_item_id})")
        return
    now = _now()
    raw_full = json_text(detail_data)
    try:
        with db_connection() as conn:
            _upsert_seller(conn, seller_do, seller_id, now)
            _upsert_item(conn, item_do, item_id, seller_id, now)
            _upsert_item_skus(conn, item_do, item_id)
            _upsert_item_images(conn, item_do, item_id)
            _upsert_item_labels(conn, item_do, item_id)
            _upsert_item_tags(conn, item_do, item_id)
            _upsert_category(conn, item_do)
            _upsert_seller_tags(conn, seller_do, seller_id)
            _upsert_seller_other_items(conn, seller_do, seller_id, now)
            _upsert_track_params(conn, track_params, item_id, seller_id)
            _upsert_detail_snapshot(conn, collected_item_id, item_id, seller_id, server_time, buyer_do, config_info, track_params, raw_full, now)
            conn.commit()
        log_time(f"[Normalizer] 完成 item={item_id} seller={seller_id}")
    except Exception as exc:
        log_time(f"[Normalizer] 失败: {type(exc).__name__}: {exc}")


def _upsert_seller(conn, sd: dict, sid: Optional[str], now: str) -> None:
    if not sid or not sd:
        return
    rm = sd.get("remarkDO") or {}
    conn.execute(
        """INSERT INTO goofish_sellers (seller_id,unique_name,nick,portrait_url,city,publish_city,
        signature,user_reg_day,register_time,has_sold_num,item_count,reply_ratio_24h,
        reply_in24h_ratio_double,reply_interval,avg_reply_30d_long,last_visit_time,
        new_good_ratio_rate,zhima_auth,aoi_type,seller_type_string,yxp_pro,xianyu_summary,
        remark_good_cnt,remark_default_cnt,remark_bad_cnt,raw_json,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (seller_id) DO UPDATE SET unique_name=EXCLUDED.unique_name,nick=EXCLUDED.nick,
        portrait_url=EXCLUDED.portrait_url,city=EXCLUDED.city,publish_city=EXCLUDED.publish_city,
        signature=EXCLUDED.signature,user_reg_day=EXCLUDED.user_reg_day,register_time=EXCLUDED.register_time,
        has_sold_num=EXCLUDED.has_sold_num,item_count=EXCLUDED.item_count,
        reply_ratio_24h=EXCLUDED.reply_ratio_24h,reply_in24h_ratio_double=EXCLUDED.reply_in24h_ratio_double,
        reply_interval=EXCLUDED.reply_interval,avg_reply_30d_long=EXCLUDED.avg_reply_30d_long,
        last_visit_time=EXCLUDED.last_visit_time,new_good_ratio_rate=EXCLUDED.new_good_ratio_rate,
        zhima_auth=EXCLUDED.zhima_auth,aoi_type=EXCLUDED.aoi_type,
        seller_type_string=EXCLUDED.seller_type_string,yxp_pro=EXCLUDED.yxp_pro,
        xianyu_summary=EXCLUDED.xianyu_summary,remark_good_cnt=EXCLUDED.remark_good_cnt,
        remark_default_cnt=EXCLUDED.remark_default_cnt,remark_bad_cnt=EXCLUDED.remark_bad_cnt,
        raw_json=EXCLUDED.raw_json,updated_at=EXCLUDED.updated_at""",
        (sid, _ss(sd.get("uniqueName")), _ss(sd.get("nick")), _ss(sd.get("portraitUrl")),
         _ss(sd.get("city")), _ss(sd.get("publishCity")), _ss(sd.get("signature")),
         _si(sd.get("userRegDay")), _si(sd.get("registerTime")), _si(sd.get("hasSoldNumInteger")),
         _si(sd.get("itemCount")), _ss(sd.get("replyRatio24h")), _sf(sd.get("replyIn24hRatioDouble")),
         _ss(sd.get("replyInterval")), _si(sd.get("avgReply30dLong")), _ss(sd.get("lastVisitTime")),
         _ss(sd.get("newGoodRatioRate")), _sb(sd.get("zhimaAuth")), _ss(sd.get("aoiType")),
         _ss(sd.get("sellerTypeString")), _sb(sd.get("yxpPro")), _ss(sd.get("xianyuSummary")),
         _si(rm.get("sellerGoodRemarkCnt")), _si(rm.get("sellerDefaultRemarkCnt")),
         _si(rm.get("sellerBadRemarkCnt")), json_text(sd), now),
    )


def _upsert_item(conn, ido: dict, iid: str, sid: Optional[str], now: str) -> None:
    conn.execute(
        """INSERT INTO goofish_items (item_id,seller_id,title,description,desc_tag,desc_tag_color,
        sold_price,original_price,transport_fee,quantity,sold_cnt,want_cnt,want_cnt_unit,
        browse_cnt,collect_cnt,favor_cnt,interact_favor_cnt,item_status,item_status_str,
        item_type,simple_item,bargained,trade_access_type,gmt_create,gmt_create_date,
        category_id,title_is_user_input,raw_json,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (item_id) DO UPDATE SET seller_id=EXCLUDED.seller_id,title=EXCLUDED.title,
        description=EXCLUDED.description,desc_tag=EXCLUDED.desc_tag,desc_tag_color=EXCLUDED.desc_tag_color,
        sold_price=EXCLUDED.sold_price,original_price=EXCLUDED.original_price,
        transport_fee=EXCLUDED.transport_fee,quantity=EXCLUDED.quantity,sold_cnt=EXCLUDED.sold_cnt,
        want_cnt=EXCLUDED.want_cnt,want_cnt_unit=EXCLUDED.want_cnt_unit,browse_cnt=EXCLUDED.browse_cnt,
        collect_cnt=EXCLUDED.collect_cnt,favor_cnt=EXCLUDED.favor_cnt,
        interact_favor_cnt=EXCLUDED.interact_favor_cnt,item_status=EXCLUDED.item_status,
        item_status_str=EXCLUDED.item_status_str,item_type=EXCLUDED.item_type,
        simple_item=EXCLUDED.simple_item,bargained=EXCLUDED.bargained,
        trade_access_type=EXCLUDED.trade_access_type,gmt_create=EXCLUDED.gmt_create,
        gmt_create_date=EXCLUDED.gmt_create_date,category_id=EXCLUDED.category_id,
        title_is_user_input=EXCLUDED.title_is_user_input,raw_json=EXCLUDED.raw_json,
        updated_at=EXCLUDED.updated_at""",
        (iid, sid, _ss(ido.get("title")), _ss(ido.get("desc")), _ss(ido.get("descTag")),
         _ss(ido.get("descTagColor")), _ss(ido.get("soldPrice")), _ss(ido.get("originalPrice")),
         _ss(ido.get("transportFee")), _si(ido.get("quantity")), _si(ido.get("soldCnt")),
         _si(ido.get("wantCnt")), _ss(ido.get("wantCntUnit")), _si(ido.get("browseCnt")),
         _si(ido.get("collectCnt")), _si(ido.get("favorCnt")), _si(ido.get("interactFavorCnt")),
         _si(ido.get("itemStatus")), _ss(ido.get("itemStatusStr")), _ss(ido.get("itemType")),
         _sb(ido.get("simpleItem")), _sb(ido.get("bargained")), _si(ido.get("tradeAccessType")),
         _si(ido.get("gmtCreate")), _ss(ido.get("GMT_CREATE_DATE_KEY")), _si(ido.get("categoryId")),
         _sb(ido.get("titleIsUserInput")), json_text(ido), now),
    )


def _upsert_item_skus(conn, ido: dict, iid: str) -> None:
    lst = ido.get("skuList") or ido.get("idleItemSkusList") or []
    if not lst:
        return
    conn.execute("DELETE FROM goofish_item_skus WHERE item_id = %s", (iid,))
    for sku in lst:
        conn.execute(
            "INSERT INTO goofish_item_skus (item_id,sku_id,price,price_in_cent,quantity,inventory_id,properties,property_image_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (iid, _ss(sku.get("skuId")), _si(sku.get("price")), _si(sku.get("priceInCent")),
             _si(sku.get("quantity")), _si(sku.get("inventoryId")),
             json_text(sku.get("propertyList") or []),
             _ss((sku.get("propertyImage") or {}).get("url"))),
        )


def _upsert_item_images(conn, ido: dict, iid: str) -> None:
    imgs = ido.get("imageInfos") or []
    if not imgs:
        return
    conn.execute("DELETE FROM goofish_item_images WHERE item_id = %s", (iid,))
    for idx, img in enumerate(imgs):
        conn.execute(
            "INSERT INTO goofish_item_images (item_id,url,major,width,height,sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
            (iid, _ss(img.get("url")), bool(img.get("major")),
             _si(img.get("widthSize")), _si(img.get("heightSize")), idx),
        )


def _upsert_item_labels(conn, ido: dict, iid: str) -> None:
    ext = ido.get("itemLabelExtList") or []
    cpv = ido.get("cpvLabels") or []
    if not ext and not cpv:
        return
    conn.execute("DELETE FROM goofish_item_labels WHERE item_id = %s", (iid,))
    seen, idx = set(), 0
    for e in ext:
        l, v = e.get("propertyText") or "", e.get("valueText") or ""
        k = f"{l}:{v}"
        if k in seen or not l or not v:
            continue
        seen.add(k)
        conn.execute(
            "INSERT INTO goofish_item_labels (item_id,source,property_id,property_text,value_id,value_text,label_type,sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (iid, "ext", _si(e.get("propertyId")), l, _si(e.get("valueId")), v, _ss(e.get("labelType")), idx))
        idx += 1
    for e in cpv:
        l, v = e.get("propertyName") or "", e.get("valueName") or ""
        k = f"{l}:{v}"
        if k in seen or not l or not v:
            continue
        seen.add(k)
        conn.execute(
            "INSERT INTO goofish_item_labels (item_id,source,property_id,property_text,value_id,value_text,label_type,sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (iid, "cpv", _si(e.get("propertyId")), l, _si(e.get("valueId")), v, None, idx))
        idx += 1


def _upsert_item_tags(conn, ido: dict, iid: str) -> None:
    sources = [
        ("common", ido.get("commonTags") or []),
        ("price_relative", ido.get("priceRelativeTags") or []),
        ("recommend", ido.get("recommendTagList") or []),
        ("desc_relative", ido.get("descRelativeTags") or []),
    ]
    if not any(lst for _, lst in sources):
        return
    conn.execute("DELETE FROM goofish_item_tags WHERE item_id = %s", (iid,))
    for tt, tags in sources:
        for idx, tag in enumerate(tags):
            if not isinstance(tag, dict):
                continue
            text = tag.get("text") or ""
            if not text:
                continue
            conn.execute(
                "INSERT INTO goofish_item_tags (item_id,tag_type,text,text_color,bg_color,border_color,sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (iid, tt, text, _ss(tag.get("textColor")), _ss(tag.get("bgColor")),
                 _ss(tag.get("borderColor")), idx))


def _upsert_category(conn, ido: dict) -> None:
    cat = ido.get("itemCatDTO")
    if not isinstance(cat, dict) or not cat.get("catId"):
        return
    conn.execute(
        """INSERT INTO goofish_categories (cat_id,leaf_id,tb_cat_id,channel_cat_id,root_channel_cat_id,level2_channel_cat_id,level3_channel_cat_id,sug_show)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (cat_id) DO UPDATE SET
        leaf_id=EXCLUDED.leaf_id,tb_cat_id=EXCLUDED.tb_cat_id,channel_cat_id=EXCLUDED.channel_cat_id,
        root_channel_cat_id=EXCLUDED.root_channel_cat_id,level2_channel_cat_id=EXCLUDED.level2_channel_cat_id,
        level3_channel_cat_id=EXCLUDED.level3_channel_cat_id,sug_show=EXCLUDED.sug_show""",
        (_si(cat.get("catId")), _si(cat.get("leafId")), _si(cat.get("tbCatId")),
         _si(cat.get("channelCatId")), _si(cat.get("rootChannelCatId")),
         _si(cat.get("level2ChannelCatId")), _si(cat.get("level3ChannelCatId")),
         _sb(cat.get("sugShow"))))


def _upsert_seller_tags(conn, sd: dict, sid: str) -> None:
    sources = [
        ("identity", sd.get("identityTags") or []),
        ("seller_info", sd.get("sellerInfoTags") or []),
        ("level", sd.get("levelTags") or []),
    ]
    if not any(lst for _, lst in sources):
        return
    conn.execute("DELETE FROM goofish_seller_tags WHERE seller_id = %s", (sid,))
    for tt, tags in sources:
        for idx, tag in enumerate(tags):
            if not isinstance(tag, dict):
                continue
            conn.execute(
                "INSERT INTO goofish_seller_tags (seller_id,tag_type,text,icon_url,link,sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
                (sid, tt, _ss(tag.get("text")), _ss(tag.get("iconUrl")), _ss(tag.get("link")), idx))


def _upsert_seller_other_items(conn, sd: dict, sid: str, now: str) -> None:
    items = sd.get("sellerItems") or []
    if not items:
        return
    conn.execute("DELETE FROM goofish_seller_other_items WHERE seller_id = %s", (sid,))
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        conn.execute(
            "INSERT INTO goofish_seller_other_items (seller_id,item_id,title,text,icon_url,link,sort_order,fetched_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (sid, _ss(item.get("itemId")), _ss(item.get("title")), _ss(item.get("text")),
             _ss(item.get("iconUrl")), _ss(item.get("link")), idx, now))


def _upsert_track_params(conn, tp: dict, iid: str, sid: Optional[str]) -> None:
    if not tp:
        return
    conn.execute("DELETE FROM goofish_item_track_params WHERE item_id = %s", (iid,))
    conn.execute(
        "INSERT INTO goofish_item_track_params (item_id,seller_id,category_id,main_pic,channel_cat_id,root_channel_cat_id,buyer_id,medal_id,buyer_bucket_id,seller_bucket_id,raw_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (iid, sid, _ss(tp.get("categoryId")), _ss(tp.get("mainPic")),
         _ss(tp.get("channelCatId")), _ss(tp.get("rootChannelCatId")),
         _ss(tp.get("buyerId")), _ss(tp.get("medal_id")),
         _ss(tp.get("buyerBucketId")), _ss(tp.get("sellerBucketId")), json_text(tp)))


def _upsert_detail_snapshot(conn, cid: int, iid: str, sid: Optional[str], st: str,
                             bd: dict, ci: dict, tp: dict, raw: str, now: str) -> None:
    conn.execute(
        "INSERT INTO goofish_item_details (collected_item_id,item_id,seller_id,server_time,buyer_json,config_json,track_params_json,raw_json,fetched_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (cid, iid, sid, st, json_text(bd), json_text(ci), json_text(tp), raw, now))
