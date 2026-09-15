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

export interface SellerSubscriptionSchedule {
  enabled: boolean
  cron: string
  item_limit: number
  collect_ratings: boolean
  account_state_file?: string | null
  account_strategy: 'auto' | 'fixed' | 'rotate'
  is_running?: boolean
  last_run_summary?: string | null
  last_run_saved?: number
  last_run_ok?: boolean
  last_run_at?: string | null
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
  return await http(`/api/seller-subscriptions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
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

export async function getSellerMetricItems(sellerId?: string) {
  return await http<{ items: SellerMetricItem[]; total: number }>(
    '/api/seller-subscriptions/items',
    { params: sellerId ? { seller_id: sellerId } : undefined },
  )
}
