export interface CollectionSku {
  sku_id: string
  label: string
  price: number | null
  price_display: string
  properties?: Array<Record<string, unknown>>
  in_stock?: boolean
  source?: string
}

export interface CollectionItem {
  id: number
  result_item_id: number
  collected_at: string
  sku_fetch_status: 'pending' | 'running' | 'done' | 'failed'
  sku_fetched_at?: string | null
  sku_error?: string | null
  skus: CollectionSku[]
  sku_meta?: Record<string, unknown>
  summary?: {
    title?: string
    price_display?: string
    link?: string
    item_id?: string
    result_filename?: string
  }
  record?: Record<string, unknown>
}
