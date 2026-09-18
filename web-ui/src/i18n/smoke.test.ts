import { describe, expect, it } from 'vitest'
import zhCN from '@/i18n/messages/zh-CN'
import enUS from '@/i18n/messages/en-US'
import { formatRelativeTimeFromNow, i18n, t } from '@/i18n'

const ROUTE_TITLE_KEYS = [
  'routes.dashboard',
  'routes.sellerSubscriptions',
  'routes.sellerItems',
  'routes.sellerItemDetail',
  'routes.shopAnalytics',
]

describe('i18n smoke', () => {
  it('provides zh-CN route titles used by router meta', () => {
    for (const key of ROUTE_TITLE_KEYS) {
      expect(zhCN.routes[key.split('.')[1] as keyof typeof zhCN.routes]).toBeTruthy()
    }
  })

  it('provides en-US route titles used by router meta', () => {
    for (const key of ROUTE_TITLE_KEYS) {
      expect(enUS.routes[key.split('.')[1] as keyof typeof enUS.routes]).toBeTruthy()
    }
  })

  it('formats relative time in active locale', () => {
    i18n.global.locale.value = 'zh-CN'
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    expect(formatRelativeTimeFromNow(fiveMinutesAgo)).toContain('分钟')
    expect(t('routes.shopAnalytics')).toBe('店铺数据')
  })

  it('shop analytics item tooltip states口径 without a hardcoded sample count', () => {
    expect(zhCN.shopAnalytics.tooltipItems).toContain('不是全库跨日去重商品数')
    expect(zhCN.shopAnalytics.tooltipItems).not.toMatch(/185/)
    expect(enUS.shopAnalytics.tooltipItems).not.toMatch(/\b185\b/)
    expect(enUS.shopAnalytics.tooltipItems.toLowerCase()).toMatch(/distinct/)
  })

  it('seller collection schedule card exposes next-run copy', () => {
    expect(zhCN.sellerCollection.scheduleCard.nextRun).toBe('下次执行')
    expect(zhCN.sellerCollection.scheduleCard.jobMissingHint).toContain('未挂上')
    expect(enUS.sellerCollection.scheduleCard.nextRun).toBe('Next run')
    expect(enUS.sellerCollection.scheduleCard.jobMissingHint.toLowerCase()).toContain('not mounted')
  })
})
