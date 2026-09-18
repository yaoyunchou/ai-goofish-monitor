import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import zhCN from '@/i18n/messages/zh-CN'
import enUS from '@/i18n/messages/en-US'

const here = dirname(fileURLToPath(import.meta.url))
const viewSource = readFileSync(resolve(here, './ShopAnalyticsView.vue'), 'utf8')
const chartSource = readFileSync(
  resolve(here, '../components/charts/WantViewTrendChart.vue'),
  'utf8',
)

describe('ShopAnalyticsView PRD 4.6 static acceptance', () => {
  it('only loads GET /dashboard, not compass overview/distribution/trend/collect', () => {
    expect(viewSource).toContain('getShopAnalyticsDashboard')
    expect(viewSource).not.toContain('getShopOverview')
    expect(viewSource).not.toContain('getShopDistribution')
    expect(viewSource).not.toContain('getShopTrend')
    expect(viewSource).not.toContain('collectShopAnalytics')
    expect(viewSource).not.toMatch(/\/api\/shop-analytics\/(overview|distribution|trend|collect)/)
    expect(viewSource).not.toContain("'/api/shop-analytics/collect'")
  })

  it('page title and empty copy drop compass / datacompass wording', () => {
    expect(zhCN.shopAnalytics.title).toBe('店铺分析')
    expect(zhCN.shopAnalytics.title).not.toBe('店铺数据罗盘')
    expect(enUS.shopAnalytics.title).toBe('Shop Analytics')
    expect(enUS.shopAnalytics.title).not.toMatch(/Compass/i)
    expect(zhCN.shopAnalytics.description).not.toMatch(/罗盘|datacompass|工作台/i)
    expect(zhCN.shopAnalytics.empty).toBe('还没有卖家订阅采集数据')
    expect(zhCN.shopAnalytics.empty).not.toMatch(/罗盘/)
    expect(zhCN.shopAnalytics.emptyHint).not.toMatch(/罗盘|datacompass|工作台/i)
    expect(zhCN.shopAnalytics.emptyHint).not.toContain('请先创建并运行')
  })

  it('does not bind showPv / uctr / pay cards on this page', () => {
    expect(viewSource).not.toContain('showPv')
    expect(viewSource).not.toContain('uctr')
    expect(viewSource).not.toContain('payOrdCnt')
    expect(viewSource).not.toContain('onlCnt')
    expect(viewSource).not.toContain('vstUv')
    expect(viewSource).toContain('cardWant')
    expect(viewSource).toContain('cardView')
    expect(viewSource).toContain('cardShops')
    expect(viewSource).toContain('cardItems')
  })

  it('renders WantViewTrendChart as SVG, not a showPv text list', () => {
    expect(viewSource).toContain('WantViewTrendChart')
    expect(viewSource).not.toMatch(/date · showPv|showPv/)
    expect(chartSource).toContain('<svg')
    expect(chartSource).toContain('role="img"')
  })

  it('empty-state primary CTA goes to seller-subscription collection', () => {
    expect(viewSource).toContain('to="/seller-subscriptions/collection"')
    expect(viewSource).toContain('to="/seller-subscriptions/sellers"')
    expect(zhCN.shopAnalytics.goCollection).toBe('去采集控制台')
  })
})
