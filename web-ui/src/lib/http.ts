import { useAuth } from '@/composables/useAuth'

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

const BACKEND_HTML_HINT = '接口返回了 HTML 而非 JSON，请确认后端已启动（python -m src.app 或 VS Code F5 Backend）'

async function parseJsonBody(response: Response): Promise<unknown> {
  const text = await response.text()
  const trimmed = text.trim()
  if (!trimmed) {
    return null
  }
  if (trimmed.startsWith('<')) {
    throw new Error(BACKEND_HTML_HINT)
  }
  try {
    return JSON.parse(trimmed)
  } catch {
    throw new Error(`接口返回非 JSON：${trimmed.slice(0, 120)}`)
  }
}

function extractErrorDetail(data: unknown, status: number): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      return detail.map((item) => (typeof item === 'object' && item && 'msg' in item ? String(item.msg) : JSON.stringify(item))).join('; ')
    }
  }
  return `HTTP error! status: ${status}`
}

export async function http<T = unknown>(url: string, options: FetchOptions = {}): Promise<T> {
  const { logout } = useAuth()

  const headers = new Headers(options.headers)

  let fullUrl = url
  if (options.params) {
    const searchParams = new URLSearchParams()
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value))
      }
    })
    const queryString = searchParams.toString()
    if (queryString) {
      fullUrl += (url.includes('?') ? '&' : '?') + queryString
    }
  }

  const config: RequestInit = {
    ...options,
    headers,
  }

  const response = await fetch(fullUrl, config)

  if (response.status === 401) {
    logout()
    throw new Error('Unauthorized')
  }

  const data = await parseJsonBody(response)

  if (!response.ok) {
    throw new Error(extractErrorDetail(data, response.status))
  }

  if (response.status === 204) {
    return null as T
  }

  return data as T
}
