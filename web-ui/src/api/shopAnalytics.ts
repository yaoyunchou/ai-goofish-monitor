import { http } from '@/lib/http'

export interface ShopMetric {
  value?: number | null
  prev?: number | null
  ratio?: number | null
  display?: string | number | null
  [key: string]: unknown
}

export interface ShopOverview {
  cycle: string
  has_data: boolean
  empty_message?: string
  shop_name?: string | null
  snapshot_date?: string | null
  captured_at?: string | null
  metrics?: Record<string, ShopMetric>
  distribution?: Record<string, unknown>
  raw?: unknown[]
}

export interface ShopDistribution {
  cycle: string
  type: string
  has_data: boolean
  empty_message?: string
  items: { label?: string; count?: number; ratio_format?: string; [key: string]: unknown }[]
}

export interface ShopTrendPoint {
  date: string
  api_name?: string
  value?: number | null
  prev?: number | null
  ratio?: number | null
  [key: string]: unknown
}

export interface ShopTrend {
  metric: string
  cycle: string
  has_data: boolean
  empty_message?: string
  points: ShopTrendPoint[]
}

export async function getShopOverview(cycle = '1d'): Promise<ShopOverview> {
  return await http<ShopOverview>('/api/shop-analytics/overview', { params: { cycle } })
}

export async function getShopDistribution(
  cycle = '1d',
  type = 'source',
): Promise<ShopDistribution> {
  return await http<ShopDistribution>('/api/shop-analytics/distribution', {
    params: { cycle, type },
  })
}

export async function getShopTrend(
  metric = 'showPv',
  days = 30,
  cycle = '1d',
): Promise<ShopTrend> {
  return await http<ShopTrend>('/api/shop-analytics/trend', {
    params: { metric, days, cycle },
  })
}

export async function collectShopAnalytics(): Promise<{ message?: string; task_id?: number }> {
  return await http<{ message?: string; task_id?: number }>('/api/shop-analytics/collect', {
    method: 'POST',
  })
}

export type ShopAnalyticsPeriod = 'today' | '7d'

export interface ShopAnalyticsFreshness {
  last_captured_at?: string | null
  last_run_at?: string | null
}

export interface ShopAnalyticsCards {
  enabled_shop_count: number
  shops_with_data: number
  item_count: number
  want_sum: number | null
  view_sum: number | null
  item_count_scope: 'anchor_day' | 'range'
  want_view_scope: 'anchor_day' | 'latest_day_in_range'
}

export interface ShopAnalyticsTrendPoint {
  date: string
  want: number | null
  view: number | null
}

export interface ShopAnalyticsShopRow {
  seller_user_id: string
  shop_name: string
  item_count: number
  want_sum: number
  view_sum: number
  enabled: boolean
}

export interface ShopAnalyticsHotItem {
  item_id: string
  title?: string | null
  seller_user_id: string
  shop_name: string
  want_count: number | null
  view_count: number | null
}

export interface ShopAnalyticsDashboard {
  period: ShopAnalyticsPeriod
  timezone: string
  today: string
  range_start: string
  range_end: string
  anchor_day: string | null
  has_data: boolean
  freshness: ShopAnalyticsFreshness
  cards: ShopAnalyticsCards
  trend: ShopAnalyticsTrendPoint[]
  shops: ShopAnalyticsShopRow[]
  hot_items: ShopAnalyticsHotItem[]
}

export async function getShopAnalyticsDashboard(
  period: ShopAnalyticsPeriod = 'today',
): Promise<ShopAnalyticsDashboard> {
  return await http<ShopAnalyticsDashboard>('/api/shop-analytics/dashboard', { params: { period } })
}

