import { http } from '@/lib/http'

export interface SellerSubscription {
  id: number
  seller_user_id: string
  seller_url?: string | null
  nickname?: string | null
  profile_nickname?: string | null
  enabled: boolean
  note?: string | null
  shop_level?: string | null
  followers?: number | null
  item_count?: number | null
  last_captured_at?: string | null
  profile_captured_at?: string | null
  created_at?: string
}

export interface SellerSubscriptionStats {
  task_name: string
  item_count: number
  seller_count: number
  enabled_seller_count?: number
  console_log_enabled?: boolean
  next_run_at?: string | null
  schedule: SellerSubscriptionSchedule
}

export interface SellerSubscriptionSchedule {
  enabled: boolean
  cron: string
  item_limit: number
  collect_ratings: boolean
  account_state_file?: string | null
  account_strategy: 'auto' | 'fixed' | 'rotate'
  run_headless?: boolean | null
  run_headless_effective?: boolean
  is_running?: boolean
  last_run_summary?: string | null
  last_run_saved?: number
  last_run_ok?: boolean
  last_run_at?: string | null
  next_run_at?: string | null
}

export interface SellerMetricItem {
  item_id: string
  seller_user_id: string
  title?: string | null
  price?: number | null
  item_status?: string | null
  want_count?: number | null
  view_count?: number | null
  snapshot_time?: string | null
}

export type SellerItemsSortBy = 'snapshot_time' | 'price' | 'want_count' | 'view_count'
export type SellerItemsSortOrder = 'asc' | 'desc'

export interface SellerItemsQuery {
  sellerId?: string
  page?: number
  pageSize?: number
  search?: string
  sortBy?: SellerItemsSortBy
  sortOrder?: SellerItemsSortOrder
}

export interface SellerMetricItemPage {
  items: SellerMetricItem[]
  total: number
  page: number
  page_size: number
}

export interface SellerProfile {
  task_name?: string | null
  seller_user_id?: string
  nickname?: string | null
  shop_level?: string | null
  praise_ratio?: number | null
  followers?: number | null
  item_count?: number | null
  rating_count?: number | null
  profile_json?: Record<string, unknown> | null
  captured_at?: string | null
}

export interface SellerDetail {
  subscription: SellerSubscription
  profile: SellerProfile | null
}

export interface SellerMetricHistoryPoint {
  item_id: string
  seller_user_id?: string
  title?: string | null
  price?: number | null
  item_status?: string | null
  want_count?: number | null
  view_count?: number | null
  snapshot_time?: string | null
}

export async function listSellerSubscriptions() {
  return await http<{ items: SellerSubscription[]; schedule: SellerSubscriptionSchedule }>(
    '/api/seller-subscriptions',
  )
}

export async function addSellerSubscription(payload: { seller_url: string; note?: string }) {
  return await http('/api/seller-subscriptions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function updateSellerSubscription(
  id: number,
  payload: Partial<Pick<SellerSubscription, 'enabled' | 'note'>>,
) {
  return await http<{ message: string; item: SellerSubscription }>(
    `/api/seller-subscriptions/${id}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

export async function deleteSellerSubscription(id: number) {
  return await http(`/api/seller-subscriptions/${id}`, { method: 'DELETE' })
}

export async function updateSellerSubscriptionSchedule(
  payload: Partial<SellerSubscriptionSchedule>,
) {
  return await http('/api/seller-subscriptions/schedule', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function runSellerSubscriptions() {
  return await http('/api/seller-subscriptions/run', { method: 'POST' })
}

export async function getSellerSubscriptionStats() {
  return await http<SellerSubscriptionStats>('/api/seller-subscriptions/stats')
}

export async function getSellerMetricItems(query: SellerItemsQuery = {}) {
  const params: Record<string, string | number> = {}
  if (query.sellerId) params.seller_id = query.sellerId
  if (query.page) params.page = query.page
  if (query.pageSize) params.page_size = query.pageSize
  if (query.search) params.search = query.search
  if (query.sortBy) params.sort_by = query.sortBy
  if (query.sortOrder) params.sort_order = query.sortOrder
  return await http<SellerMetricItemPage>('/api/seller-subscriptions/items', { params })
}

export async function getSellerDetail(sellerUserId: string) {
  return await http<SellerDetail>(`/api/seller-subscriptions/detail/${encodeURIComponent(sellerUserId)}`)
}

export async function getItemMetricHistory(itemId: string, limit = 200) {
  return await http<{ items: SellerMetricHistoryPoint[] }>('/api/seller-subscriptions/metrics', {
    params: { item_id: itemId, limit },
  })
}

export interface SellerItemDataSummary {
  has_record: boolean
  crawl_time?: string | null
  task_type?: string | null
  task_name?: string | null
  top_level_keys: string[]
  product_fields: string[]
  seller_fields: string[]
  image_count: number
  description_length: number
  has_sku_data: boolean
}

export interface SellerItemDetailApiSummary {
  has_detail_api: boolean
  api?: string
  sku_count: number
  top_level_keys: string[]
  data_keys: string[]
  item_do_keys: string[]
  min_price?: string | null
  max_price?: string | null
  sold_price?: string | null
}

export interface SellerItemDetailApiRow {
  id: number
  item_id: string
  seller_user_id?: string | null
  task_name: string
  source: string
  api_name: string
  raw_json: Record<string, unknown>
  captured_at?: string | null
}

export interface SellerItemDetailResponse {
  item_id: string
  result_filename: string
  result_item_id: number | null
  crawl_time: string | null
  metrics: SellerMetricHistoryPoint[]
  record: Record<string, unknown> | null
  detail_api: SellerItemDetailApiRow | null
  detail_api_summary: SellerItemDetailApiSummary
  data_summary: SellerItemDataSummary
}

export async function getSellerItemDetail(itemId: string) {
  return await http<SellerItemDetailResponse>(
    `/api/seller-subscriptions/items/${encodeURIComponent(itemId)}/detail`,
  )
}
