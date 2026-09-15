# 闲鱼卖家工作台（数据总览）探索文档

> 探索目标：[卖家工作台 - 数据总览](https://seller.goofish.com/?site=COMMONPRO#/seller-data/data)  
> 探索时间：2026-09-15  
> 探索方式：Playwright + 网络响应拦截  
> 原始快照：`docs/exploration/snapshots/exploration_snapshot.json`、`seller_workbench.png`

---

## 1. 页面概览

| 项 | 值 |
|---|---|
| 入口 URL | `https://seller.goofish.com/?site=COMMONPRO` |
| 数据总览路由 | `#/seller-data/data` |
| 完整 URL | `https://seller.goofish.com/?site=COMMONPRO#/seller-data/data` |
| 页面标题 | `数据总览 - 闲鱼卖家工作台` |
| 站点名称 | `鱼小铺专业卖家工作台`（API 返回） |
| 渲染方式 | Hash 路由 SPA + 微前端（`idle-seller-data` 子应用） |
| 登录要求 | **必须**为已开通鱼小铺/专业卖家的账号 Cookie |
| 与 C 端用户页关系 | C 端 `www.goofish.com/personal` 展示公开画像；本页展示**经营者视角**的后台指标 |

### 1.1 页面结构（UI）

```
┌──────────┬────────────────────────────────────────────────────────┐
│ 左侧菜单  │ 顶栏：通知 | 消息 | 下载 | 店铺名 | 账号                 │
│          ├────────────────────────────────────────────────────────┤
│ 数据 ▼   │ 数据总览                    [近1天] [近7天] [近30天]     │
│  数据总览 │ ─────────────────────────────────────────────────────  │
│  商品数据 │ 流量指标卡片：访问次数/人数、曝光、浏览、支付、退款        │
│  粉丝数据 │ 商品数据：在线商品数、被浏览商品数、动销商品数             │
│  客服数据 │ 交易数据：询单响应率、转化率漏斗                           │
│ 小铺 ▼   │ 复购情况：复购率、复购订单数、复购人数                     │
│ 商品 ▼   │ 浏览分布：来源/品类/时段/地域                               │
│ 交易 ▼   │ 售后数据：退款/维权/完结率                                  │
│ 推广 ▼   │                                                        │
│ 财务 ▼   │                                                        │
└──────────┴────────────────────────────────────────────────────────┘
```

### 1.2 弹窗与干扰项

探索时页面存在两类 overlay，自动化需先关闭：

| 弹窗 | 内容 | 处理建议 |
|---|---|---|
| 闲鱼卖家客服 | 推广 Windows/Mac 客户端下载 | 点击关闭 `×` |
| PC 端工作台使用反馈收集 | 满意度问卷 | 点击「取消」或勾选「近30天不再显示」 |

---

## 2. 技术架构

| 层级 | 说明 |
|---|---|
| 主站 | `seller.goofish.com/?site=COMMONPRO` 加载工作台壳 |
| 子应用 | `g.alicdn.com/idle-pc/idle-seller-data/{version}/index.html` |
| 路由 | Hash：`#/seller-data/data`（数据总览） |
| API 网关 | `https://h5api.m.goofish.com/h5/mtop.alibaba.idle.seller.*` |
| AppKey | `34839810`（与 C 端 PC 站一致） |
| 鉴权 | MTOP 签名 + `sessionOption=AutoLoginOnly` + 卖家身份 Cookie |

### 2.1 左侧菜单（来自 DOM 文本）

**数据**

- 数据总览（当前页）
- 商品数据
- 粉丝数据
- 客服数据

**小铺**

- 子账号管理、客服分流、安全中心

**商品**

- 商品发布、商品管理、运费模版

**交易**

- 订单管理、退款管理、评价管理、投诉管理、退货地址

**推广**

- 超强擦亮

**财务**

- 收入账单、支出账单、申请发票、开票信息

菜单权威来源 API：`mtop.alibaba.idle.seller.platform.sys.menu.query`

---

## 3. 核心 API 清单

| API | 用途 |
|---|---|
| `mtop.alibaba.idle.seller.platform.user.business.identity.get` | 校验卖家业务身份 |
| `mtop.alibaba.idle.seller.platform.query.login.merchant.info` | 登录商户/店铺信息 |
| `mtop.alibaba.idle.seller.platform.sys.menu.query` | 左侧菜单与站点配置 |
| `mtop.alibaba.idle.seller.platform.sys.usergroup.member.list` | 子账号/用户组成员 |
| `mtop.alibaba.idle.seller.platform.usergroup.member.list` | 成员列表 |
| `mtop.alibaba.idle.seller.datacompass.get.begin.time` | 数据罗盘起始时间 |
| `mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary` | **卖家总览指标**（流量/交易卡片） |
| `mtop.alibaba.idle.seller.pc.datacompass.singleuser.item.summary` | **商品维度指标** |
| `mtop.alibaba.idle.seller.pc.datacompass.singleuser.browse.summary` | **浏览分布**（来源/品类/时段/地域） |
| `mtop.alibaba.idle.seller.pc.datacompass.singleuser.repurchase.summary` | **复购指标** |
| `mtop.alibaba.idle.seller.pc.datacompass.flow.detail` | **流量转化明细**（漏斗字段） |
| `mtop.alibaba.idle.seller.pc.datacompass.refund.summary` | **售后/退款汇总** |

---

## 4. 数据总览指标（近 1 天样本）

以下为 2026-09-15 探索账号「蓝小飞鱼 / 大鱼二手书」的实际页面数据：

### 4.1 流量与交易（seller.summary + flow.detail）

| 指标 | 当前值 | 前1日 | 环比 |
|---|---|---|---|
| 商品访问次数 | 12 | 12 | 0.00% |
| 商品访问人数 | 5 | 4 | +25.00% |
| 商品曝光次数 | 76 | 72 | +5.56% |
| 商品曝光人数 | 44 | 36 | +22.22% |
| 商品浏览次数 | 11 | 9 | +22.22% |
| 商品浏览人数 | 5 | 3 | +66.67% |
| 支付笔数 | 0 | 0 | - |
| 支付金额 | ¥0.00 | ¥0.00 | - |
| 曝光点击率 | 11.36% | 36.37% | - |
| 浏览支付转化率 | 0.00% | - | - |

**flow.detail 关键字段**（`data.itemFlowTransferData`）：

| 字段 | 含义 |
|---|---|
| `showPv` / `showUv` | 曝光次数 / 人数 |
| `ipv` / `ipvUv` | 浏览次数 / 人数 |
| `payAmt` / `payUv` | 支付金额 / 支付人数 |
| `chatUv` / `chatCnt` | 询单人数 / 次数 |
| `rep3minUvRate` | 3 分钟询单响应率 |
| `uctr` | 曝光点击率 |
| `uctcvr` | 浏览支付转化率 |
| `timeCycle` | 统计周期（如 `1d`） |
| `scene` | 场景（如 `all`） |

每个指标通常为 `{ value, ratio, ... }` 结构，`ratio` 为环比。

### 4.2 商品数据（item.summary）

| 指标 | 当前值 | 前1日 | 环比 |
|---|---|---|---|
| 在线商品数 | 285 | 285 | 0.00% |
| 被浏览商品数 | 4 | 3 | +33.33% |
| 动销商品数 | 0 | 0 | - |

API 字段示例：`onlCnt`（在线数）、`dftCnt`（动销）、`favCnt`（收藏）。

### 4.3 复购情况（repurchase.summary）

| 指标 | 值 |
|---|---|
| 复购率 | 0.00% |
| 复购订单数 | 0 |
| 复购人数 | 0 |

### 4.4 浏览分布（browse.summary）

**来源分布**：首页 28.57% | 猜你喜欢 28.57% | 其他 28.57% | 搜索 14.29% | 闲鱼号 0.00%

**商品分布**：图书 54.55% | 早教机/故事机 27.27% | 手机数据线 18.18%

**时段分布**：14点-16点 45.45% | 10点-12点 18.18%

**地域分布**：无锡市 45.45% | 平顶山市 18.18% | 福州市 18.18% | 南昌市 9.09% | 长春市 9.09%

### 4.5 售后数据（refund.summary）

| 指标 | 值 |
|---|---|
| 发起退款笔数 | 0 |
| 退款发起率 | 0.00% |
| 维权笔数 | 0 |
| 成功退款笔数 | 0 |
| 处理中的退款笔数 | 0 |

---

## 5. API 响应结构

### 5.1 通用包装

```json
{
  "api": "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary",
  "v": "1.0",
  "ret": ["SUCCESS::调用成功"],
  "traceId": "...",
  "data": {
    "code": "success",
    "msg": "成功",
    "data": {
      "graphBannerBenchData": {
        "bannerDataList": [],
        "graphDataList": []
      }
    },
    "extendInfo": {
      "realDateRange": ["20260914", "20260914"]
    }
  }
}
```

### 5.2 菜单 API（`sys.menu.query`）

```json
{
  "title": "鱼小铺专业卖家工作台",
  "siteName": "idleFishSellerSite",
  "bizCode": "professionalSeller",
  "menu": [ "... nested menu tree ..." ]
}
```

---

## 6. 与用户主页的对比

| 维度 | C 端用户主页 (`www.goofish.com/personal`) | 卖家工作台 (`seller.goofish.com`) |
|---|---|---|
| 访问者 | 任意用户/买家 | 仅店铺经营者 |
| 数据类型 | 公开画像、在售商品、历史评价 | 经营指标、转化漏斗、售后、财务 |
| 核心 API 前缀 | `mtop.idle.web.user.*` | `mtop.alibaba.idle.seller.*` |
| 分页方式 | 滚动加载 cardList | 时间维度切换（1/7/30 天） |
| 项目现状 | 已集成 `scrape_user_profile` | **尚未集成**，需新模块 |

---

## 7. 爬虫实现建议

1. **登录态**：必须使用**卖家账号** Cookie；普通买家 Cookie 无法加载 datacompass API。
2. **入口**：先打开 `seller.goofish.com/?site=COMMONPRO`，等待 `#/seller-data/data` 子应用挂载。
3. **API 拦截**：监听 `mtop.alibaba.idle.seller.pc.datacompass.*`，按 `timeCycle` 参数区分 1d/7d/30d。
4. **签名**：MTOP 请求带 `sign=`，依赖 `_m_h5_tk`；可复用项目 Playwright 上下文自动签名。
5. **弹窗处理**：探索脚本应增加关闭反馈弹窗/客服推广的逻辑。
6. **合规**：该页面属于经营者后台数据，采集前需确保账号授权与平台规则合规。

### 7.1 建议采集模块结构

```
src/services/seller_datacompass_service.py   # 解析 datacompass API
src/scraper_seller.py                        # 独立 CLI 或定时任务
scripts/explore_goofish_pages.py             # 已有探索脚本
```

---

## 8. 与开放平台 API 的关系

卖家工作台使用的是 **MTOP 内部接口**（`h5api.m.goofish.com`），与 [闲鱼开放平台](https://open.goofish.pro) / [TOP API](https://open.alitrip.com/docs/api.htm?apiId=68593) 不同：

| 来源 | 接口示例 | 适用场景 |
|---|---|---|
| 工作台 MTOP | `mtop.alibaba.idle.seller.pc.datacompass.*` | 登录卖家 PC 工作台，实时罗盘 |
| TOP 开放平台 | `alibaba.idle.cycleshop.seller.reportinfo` | 需 AppKey + 授权，店内报告 |
| 非官方聚合 | `/api/seller/v2/statistic` | 第三方，非官方 |

若要做**对外产品化**数据服务，优先考虑开放平台授权；若做**个人店铺监控**，可沿用 Playwright + MTOP 拦截方案。

---

## 9. 探索结论

- 卖家工作台是**专业卖家（鱼小铺）**的经营数据中心，与 C 端用户主页互补。
- 「数据总览」页一次性拉取 6+ 个 datacompass API，覆盖流量、商品、复购、分布、售后全链路。
- 页面为 Hash SPA，**API 比 DOM 更适合稳定采集**。
- 本项目当前仅采集 C 端卖家画像；若要扩展「店铺经营监控」，建议以 `datacompass.*` 为切入点。

---

## 10. 复现命令

```bash
# 1. 导出卖家账号登录态到 docs/exploration/temp_login_state.json
# 2. 运行探索脚本
python scripts/explore_goofish_pages.py

# 输出：
# - docs/exploration/snapshots/exploration_snapshot.json
# - docs/exploration/snapshots/seller_workbench.png
```
