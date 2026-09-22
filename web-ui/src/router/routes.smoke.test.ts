import { describe, expect, it } from 'vitest'
import router from './index'

const REQUIRED_PATHS = [
  '/login',
  '/dashboard',
  '/tasks',
  '/accounts',
  '/results',
  '/seller-subscriptions/sellers',
  '/seller-subscriptions/items',
  '/seller-subscriptions/items/:itemId',
  '/seller-subscriptions/sellers/:sellerUserId',
  '/seller-subscriptions/collection',
  '/shop-analytics',
  '/xhs',
  '/xhs/add',
  '/xhs/failed',
  '/xhs/delisted',
  '/xhs/settings',
  '/xhs/shops',
  '/xhs/shops/:shopId',
  '/xhs/:productId',
  '/logs',
  '/settings',
]

describe('router smoke', () => {
  it('registers core application routes', () => {
    const paths = router.getRoutes().map((route) => route.path)
    for (const path of REQUIRED_PATHS) {
      expect(paths).toContain(path)
    }
  })

  it('assigns title keys for authenticated pages', () => {
    const titled = router
      .getRoutes()
      .filter((route) => route.meta?.requiresAuth)
      .map((route) => route.meta?.titleKey)
    expect(titled).toContain('routes.sellerSubscriptions')
    expect(titled).toContain('routes.shopAnalytics')
    expect(titled).toContain('routes.xhs')
    expect(titled).toContain('routes.xhsAdd')
    expect(titled).toContain('routes.xhsFailed')
    expect(titled).toContain('routes.xhsDelisted')
    expect(titled).toContain('routes.xhsSettings')
    expect(titled).toContain('routes.xhsShops')
    expect(titled).toContain('routes.xhsShop')
    expect(titled).toContain('routes.xhsProduct')
    expect(titled).toContain('routes.sellerItemDetail')
  })
})
