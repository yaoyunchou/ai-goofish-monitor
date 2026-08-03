import type { CollectionItem } from '@/types/collection.d.ts'
import { http } from '@/lib/http'

export async function collectResultItem(payload: {
  result_item_id?: number
  result_filename?: string
  item_id?: string
}): Promise<{ message: string; collection: CollectionItem }> {
  return await http('/api/collections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function getCollection(id: number): Promise<CollectionItem> {
  return await http(`/api/collections/${id}`)
}

export async function listCollections(): Promise<{ items: CollectionItem[] }> {
  return await http('/api/collections')
}

export async function refreshCollectionSkus(id: number): Promise<{ message: string; collection: CollectionItem }> {
  return await http(`/api/collections/${id}/refresh-skus`, { method: 'POST' })
}

export async function deleteCollection(id: number): Promise<{ message: string }> {
  return await http(`/api/collections/${id}`, { method: 'DELETE' })
}
