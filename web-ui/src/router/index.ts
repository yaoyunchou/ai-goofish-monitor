import { watch } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAuth } from '@/composables/useAuth'
import { i18n, t } from '@/i18n'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { titleKey: 'routes.login' },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { titleKey: 'routes.dashboard', requiresAuth: true },
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/TasksView.vue'),
        meta: { titleKey: 'routes.tasks', requiresAuth: true },
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/AccountsView.vue'),
        meta: { titleKey: 'routes.accounts', requiresAuth: true },
      },
      {
        path: 'results',
        name: 'Results',
        component: () => import('@/views/ResultsView.vue'),
        meta: { titleKey: 'routes.results', requiresAuth: true },
      },
      {
        path: 'seller-subscriptions',
        redirect: '/seller-subscriptions/sellers',
      },
      {
        path: 'seller-subscriptions/collection',
        name: 'SellerCollection',
        component: () => import('@/views/SellerCollectionView.vue'),
        meta: { titleKey: 'routes.sellerCollection', requiresAuth: true },
      },
      {
        path: 'seller-subscriptions/sellers',
        name: 'SellerSubscriptions',
        component: () => import('@/views/SellerSubscriptionView.vue'),
        meta: { titleKey: 'routes.sellerSubscriptions', requiresAuth: true },
      },
      {
        path: 'seller-subscriptions/sellers/:sellerUserId',
        name: 'SellerDetail',
        component: () => import('@/views/SellerDetailView.vue'),
        meta: { titleKey: 'routes.sellerDetail', requiresAuth: true },
      },
      {
        path: 'seller-subscriptions/items',
        name: 'SellerItems',
        component: () => import('@/views/SellerItemsView.vue'),
        meta: { titleKey: 'routes.sellerItems', requiresAuth: true },
      },
      {
        path: 'seller-subscriptions/items/:itemId',
        name: 'SellerItemDetail',
        component: () => import('@/views/SellerItemDetailView.vue'),
        meta: { titleKey: 'routes.sellerItemDetail', requiresAuth: true },
      },
      {
        path: 'shop-analytics',
        name: 'ShopAnalytics',
        component: () => import('@/views/ShopAnalyticsView.vue'),
        meta: { titleKey: 'routes.shopAnalytics', requiresAuth: true },
      },
      {
        path: 'xhs',
        name: 'XhsBoard',
        component: () => import('@/views/xhs/XhsBoardView.vue'),
        meta: { titleKey: 'routes.xhs', requiresAuth: true },
      },
      {
        path: 'xhs/shops',
        name: 'XhsShops',
        component: () => import('@/views/xhs/XhsShopsView.vue'),
        meta: { titleKey: 'routes.xhsShops', requiresAuth: true },
      },
      {
        path: 'xhs/shops/:shopId',
        name: 'XhsShop',
        component: () => import('@/views/xhs/XhsShopView.vue'),
        meta: { titleKey: 'routes.xhsShop', requiresAuth: true },
      },
      {
        path: 'xhs/add',
        name: 'XhsAdd',
        component: () => import('@/views/xhs/XhsAddView.vue'),
        meta: { titleKey: 'routes.xhsAdd', requiresAuth: true },
      },
      {
        path: 'xhs/failed',
        name: 'XhsFailed',
        component: () => import('@/views/xhs/XhsFailedView.vue'),
        meta: { titleKey: 'routes.xhsFailed', requiresAuth: true },
      },
      {
        path: 'xhs/delisted',
        name: 'XhsDelisted',
        component: () => import('@/views/xhs/XhsDelistedView.vue'),
        meta: { titleKey: 'routes.xhsDelisted', requiresAuth: true },
      },
      {
        path: 'xhs/settings',
        name: 'XhsSettings',
        component: () => import('@/views/xhs/XhsSettingsView.vue'),
        meta: { titleKey: 'routes.xhsSettings', requiresAuth: true },
      },
      {
        path: 'xhs/:productId',
        name: 'XhsProduct',
        component: () => import('@/views/xhs/XhsProductView.vue'),
        meta: { titleKey: 'routes.xhsProduct', requiresAuth: true },
      },
      {
        path: 'results/collected/:id',
        name: 'CollectionDetail',
        component: () => import('@/views/CollectionDetailView.vue'),
        meta: { titleKey: 'routes.collectionDetail', requiresAuth: true },
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogsView.vue'),
        meta: { titleKey: 'routes.logs', requiresAuth: true },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { titleKey: 'routes.settings', requiresAuth: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function updateDocumentTitle() {
  const currentRoute = router.currentRoute.value
  const titleKey = typeof currentRoute.meta.titleKey === 'string'
    ? currentRoute.meta.titleKey
    : null
  const appName = t('app.name')
  document.title = titleKey ? `${t(titleKey)} - ${appName}` : appName
}

router.beforeEach((to, _from, next) => {
  const { isAuthenticated } = useAuth()

  if (to.meta.requiresAuth && !isAuthenticated.value) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && isAuthenticated.value) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

router.afterEach(() => {
  updateDocumentTitle()
})

watch(
  () => i18n.global.locale.value,
  () => {
    updateDocumentTitle()
  },
)

export default router
