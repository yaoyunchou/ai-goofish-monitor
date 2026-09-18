const SHANGHAI_TZ = 'Asia/Shanghai'

function hasTimezone(value: string): boolean {
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value.trim())
}

/** 解析后端时间：无时区后缀时按北京时间理解。 */
export function parseAppDateTime(value: string): Date {
  const trimmed = value.trim()
  if (!trimmed) return new Date(NaN)
  if (trimmed.includes('T') && !hasTimezone(trimmed)) {
    return new Date(`${trimmed}+08:00`)
  }
  return new Date(trimmed)
}

/** 统一按 Asia/Shanghai 展示业务时间。 */
export function formatShanghaiTime(value?: string | null): string {
  if (!value) return '-'
  const date = parseAppDateTime(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    timeZone: SHANGHAI_TZ,
    hour12: false,
  })
}
