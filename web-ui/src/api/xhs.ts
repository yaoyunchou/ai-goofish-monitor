import { http } from '@/lib/http'

export interface XhsProduct {
  id: string
  source_url?: string | null
  title?: string | null
  shop_name?: string | null
  cover_url?: string | null
  price?: number | null
  last_error?: string | null
  last_status?: string | null
  updated_at?: string | null
  sold_total?: number | null
  today?: number | null
  today_incomplete?: boolean
  today_fuzzy?: number | null
  yesterday?: number | null
  yesterday_incomplete?: boolean
  last_hour?: number | null
  last_hour_incomplete?: boolean
  shop_id?: number | null
  assigned_shop_name?: string | null
  category?: string | null
  tags?: string[]
}

export interface XhsSchedule {
  cron: string
  enabled: boolean
  next_run_at?: string | null
}

export interface XhsSeriesPoint {
  label: string
  delta: number | null
  incomplete: boolean
  fuzzy_amount?: number | null
}

export async function listXhsProducts(): Promise<XhsProduct[]> {
  const data = await http<{ items: XhsProduct[] }>('/api/xhs/products')
  return data.items
}

export async function listXhsFailures(): Promise<XhsProduct[]> {
  const data = await http<{ items: XhsProduct[] }>('/api/xhs/failures')
  return data.items
}

export async function ignoreXhsFailures(productIds: string[]): Promise<void> {
  await http('/api/xhs/failures/ignore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_ids: productIds }),
  })
}

export async function listXhsDelisted(): Promise<XhsProduct[]> {
  const data = await http<{ items: XhsProduct[] }>('/api/xhs/delisted')
  return data.items
}

export async function addXhsProduct(payload: {
  url: string
  shop_name?: string | null
  category?: string | null
  tags?: string[]
}): Promise<XhsProduct> {
  return await http<XhsProduct>('/api/xhs/products', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function updateXhsLabels(
  productId: string,
  payload: { shop_name?: string | null; category?: string | null; tags: string[] },
): Promise<XhsProduct> {
  return await http<XhsProduct>(`/api/xhs/products/${productId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export interface XhsShopSummary {
  id: number
  name: string
  product_count: number
  sold_total?: number | null
  today?: number | null
  today_incomplete?: boolean
  yesterday?: number | null
  yesterday_incomplete?: boolean
  last_hour?: number | null
  last_hour_incomplete?: boolean
}

export interface XhsShopList {
  items: XhsShopSummary[]
  unassigned: XhsShopSummary & { items: XhsProduct[] }
}

export async function listXhsShops(): Promise<XhsShopList> {
  return await http<XhsShopList>('/api/xhs/shops')
}

export async function createXhsShop(name: string): Promise<{ id: number; name: string }> {
  return await http('/api/xhs/shops', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export async function getXhsShop(shopId: string): Promise<XhsShopSummary & { items: XhsProduct[] }> {
  return await http(`/api/xhs/shops/${shopId}`)
}

export async function downloadXhsTemplate(): Promise<void> {
  const response = await fetch('/api/xhs/products/import-template')
  if (!response.ok) throw new Error('模板下载失败')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = '小红书商品导入模板.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

export async function importXhsProducts(file: File): Promise<{ added: number; updated: number; failed: { row: number; reason: string }[] }> {
  const body = new FormData()
  body.append('file', file)
  return await http('/api/xhs/products/import', { method: 'POST', body })
}

export async function removeXhsProduct(productId: string): Promise<void> {
  await http(`/api/xhs/products/${productId}`, { method: 'DELETE' })
}

export async function collectXhsProduct(productId: string): Promise<{ saved: number; failed: number; stopped: boolean }> {
  return await http(`/api/xhs/products/${productId}/collect`, { method: 'POST' })
}

export async function collectAllXhs(): Promise<{ saved: number; failed: number; stopped: boolean }> {
  return await http('/api/xhs/collect', { method: 'POST' })
}

export async function getXhsProduct(productId: string): Promise<XhsProduct> {
  return await http<XhsProduct>(`/api/xhs/products/${productId}`)
}

export async function getXhsSeries(productId: string, kind: 'hourly' | 'daily'): Promise<XhsSeriesPoint[]> {
  const data = await http<{ points: XhsSeriesPoint[] }>(`/api/xhs/products/${productId}/series`, {
    params: { kind },
  })
  return data.points
}

export async function getXhsSchedule(): Promise<XhsSchedule> {
  return await http<XhsSchedule>('/api/xhs/schedule')
}

export async function saveXhsSchedule(cron: string, enabled: boolean): Promise<XhsSchedule> {
  return await http<XhsSchedule>('/api/xhs/schedule', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cron, enabled }),
  })
}

export function xhsCoverSrc(url: string | null | undefined): string {
  if (!url) return ''
  return `/api/xhs/cover?url=${encodeURIComponent(url)}`
}
