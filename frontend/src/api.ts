import type { AShareSentiment, AShareSentimentHistoryPoint, DataRefreshStart, DataRefreshStatus, GreyMarketQuote, IPODetail, IPOList, Report, USMarketDashboard } from './types'

const API = import.meta.env.VITE_API_URL ?? '/api'
const REQUEST_TIMEOUT_MS = 20_000
const GET_RETRY_COUNT = 2

interface RequestOptions extends RequestInit {
  timeoutMs?: number
  retryCount?: number
}

async function request<T>(path: string, options?: RequestOptions): Promise<T> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, retryCount, ...fetchOptions } = options ?? {}
  const headers = new Headers(options?.headers)
  const adminKey = window.sessionStorage.getItem('stock-admin-api-key')
  if (adminKey) {
    headers.set('X-Admin-Key', adminKey)
  }
  if (options?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const method = options?.method?.toUpperCase() ?? 'GET'
  const attempts = (retryCount ?? (method === 'GET' ? GET_RETRY_COUNT : 0)) + 1
  let lastError: unknown
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(`${API}${path}`, { ...fetchOptions, headers, signal: controller.signal })
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(typeof body.detail === 'string' ? body.detail : '请求失败')
      }
      return response.json() as Promise<T>
    } catch (error) {
      lastError = error instanceof DOMException && error.name === 'AbortError'
        ? new Error('请求超时，数据刷新仍可能在后台继续，请稍后重试')
        : error instanceof TypeError
          ? new Error('无法连接数据服务，请检查网络或确认服务已启动')
        : error
      if (attempt === attempts - 1) {
        break
      }
      await new Promise(resolve => window.setTimeout(resolve, 600 * (attempt + 1)))
    } finally {
      window.clearTimeout(timeout)
    }
  }
  throw lastError
}

export const api = {
  listIPOs: (params = '') => request<IPOList>(`/ipos${params}`),
  getIPO: (id: number) => request<IPODetail>(`/ipos/${id}`),
  adjust: (id: number, value: number, reason: string) => request(`/ipos/${id}/adjustments`, { method: 'POST', body: JSON.stringify({ value, reason, operator: '本地用户' }) }),
  greyMarketPrice: (id: number) => request<GreyMarketQuote>(`/ipos/${id}/grey-market-price`, { method: 'POST' }),
  saveGreyMarketPrice: (id: number, price: number) => request<GreyMarketQuote>(`/ipos/${id}/grey-market-price`, { method: 'PUT', body: JSON.stringify({ price }) }),
  finalizeGreyMarketPrice: (id: number) => request<IPODetail>(`/ipos/${id}/grey-market-price/finalize`, { method: 'POST' }),
  reports: () => request<Report[]>('/reports'),
  createReport: () => request<Report>('/reports', { method: 'POST' }),
  startDataRefresh: () => request<DataRefreshStart>('/data-refresh', { method: 'POST' }),
  dataRefreshStatus: (id: string) => request<DataRefreshStatus>(`/data-refresh/${id}`),
  aShareSentiment: (refresh = false) => request<AShareSentiment>(
    `/a-shares/sentiment${refresh ? '?refresh=true' : ''}`,
    refresh ? { timeoutMs: 120_000, retryCount: 0 } : undefined,
  ),
  aShareSentimentHistory: () => request<AShareSentimentHistoryPoint[]>('/a-shares/sentiment/history?limit=15'),
  usMarketDashboard: (refresh = false) => request<USMarketDashboard>(
    `/us-market/dashboard${refresh ? '?refresh=true' : ''}`,
    refresh ? { timeoutMs: 120_000, retryCount: 0 } : undefined,
  ),
  rules: () => request<Record<string, unknown>>('/scoring-rules'),
  downloadUrl: (id: number, format: 'md' | 'pdf') => `${API}/reports/${id}/download?format=${format}`,
}
