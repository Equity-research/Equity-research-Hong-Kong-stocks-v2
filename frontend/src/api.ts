import type { AShareSentiment, IPODetail, IPOList, Report } from './types'

const API = import.meta.env.VITE_API_URL ?? '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json', ...options?.headers }, ...options })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(typeof body.detail === 'string' ? body.detail : '请求失败')
  }
  return response.json() as Promise<T>
}

export const api = {
  listIPOs: (params = '') => request<IPOList>(`/ipos${params}`),
  getIPO: (id: number) => request<IPODetail>(`/ipos/${id}`),
  adjust: (id: number, value: number, reason: string) => request(`/ipos/${id}/adjustments`, { method: 'POST', body: JSON.stringify({ value, reason, operator: '本地用户' }) }),
  reports: () => request<Report[]>('/reports'),
  createReport: () => request<Report>('/reports', { method: 'POST' }),
  aShareSentiment: () => request<AShareSentiment>('/a-shares/sentiment'),
  rules: () => request<Record<string, unknown>>('/scoring-rules'),
  downloadUrl: (id: number, format: 'md' | 'pdf') => `${API}/reports/${id}/download?format=${format}`,
}
