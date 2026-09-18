/** 统一解析后端 enabled（避免字符串/数字导致 UI 与保存不一致）。 */
export function normalizeSubscriptionEnabled(value: unknown): boolean {
  if (value === true || value === 1) return true
  if (value === false || value === 0 || value === null || value === undefined) return false
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (text === 'true' || text === 't' || text === '1' || text === 'yes') return true
    if (text === 'false' || text === 'f' || text === '0' || text === 'no' || text === '') return false
  }
  return Boolean(value)
}

export function normalizeSellerSubscription<T extends { enabled?: unknown }>(item: T): T {
  return { ...item, enabled: normalizeSubscriptionEnabled(item.enabled) }
}
