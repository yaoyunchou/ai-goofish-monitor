import { http } from '@/lib/http'

export interface FollowedSeller {
  seller_id: string
  unique_name?: string
  portrait_url?: string
  city?: string
  signature?: string
  item_count?: number
  has_sold_num?: number
  new_good_ratio_rate?: string
  user_reg_day?: number
  xianyu_summary?: string
  remark_good_cnt?: number
  remark_default_cnt?: number
  remark_bad_cnt?: number
  cron: string
  follow_at: string
  last_fetch_at?: string
  last_fetch_status: string
  last_fetch_error?: string
  note?: string
}

export interface SellerItem {
  item_id: string
  title: string
  price: string
  pic_url: string
  status: string
  want_cnt?: number
  browse_cnt?: number
  collect_cnt?: number
  sold_cnt?: number
  fetched_at: string
}

export async function listSellers(): Promise<{ items: FollowedSeller[] }> {
  return await http('/api/sellers')
}

export async function followSeller(payload: {
  seller_id: string
  seller_name?: string
  avatar_url?: string
  city?: string
  cron?: string
  note?: string
}): Promise<{ seller_id: string; followed: boolean }> {
  return await http('/api/sellers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function unfollowSeller(sellerId: string): Promise<{ message: string }> {
  return await http(`/api/sellers/${sellerId}`, { method: 'DELETE' })
}

export async function getSeller(sellerId: string, sort = 'want_cnt'): Promise<{ seller: FollowedSeller; items: SellerItem[] }> {
  return await http(`/api/sellers/${sellerId}?sort=${sort}`)
}

export async function refreshSeller(sellerId: string): Promise<{ seller_id: string; status: string; items_count?: number; error?: string }> {
  return await http(`/api/sellers/${sellerId}/refresh`, { method: 'POST' })
}

export async function refreshAllSellers(): Promise<{ results: any[] }> {
  return await http('/api/sellers/refresh-all', { method: 'POST' })
}

export async function updateSellerCron(sellerId: string, cron: string): Promise<{ message: string; cron: string }> {
  return await http(`/api/sellers/${sellerId}/cron`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cron }),
  })
}
