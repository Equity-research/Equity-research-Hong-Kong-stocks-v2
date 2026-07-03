import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const ipo = {
  id: 1,
  name: '普源精电',
  english_name: 'RIGOL Technologies Co., Ltd.',
  code: '00537.HK',
  industry: '电子测量仪器',
  price_low: 45.98,
  price_high: 45.98,
  minimum_subscription_amount: 4644.37,
  subscription_multiple: 21.02,
  deadline: '2026-07-06',
  is_sample: false,
  original_score: 8,
  adjustment: 0,
  final_score: 8,
  recommendation: '申购',
  dimensions: [
    { key: 'cornerstone_presence', label: '基石投资者', score: 1, weight: 1, reasons: [], missing: [] },
    { key: 'cornerstone_quality', label: '基石质量', score: 1, weight: 1, reasons: [], missing: [] },
    { key: 'greenshoe', label: '绿鞋机制', score: 1, weight: 1, reasons: [], missing: [] },
    { key: 'subscription', label: '公开申购倍数', score: 1, weight: 3, reasons: [], missing: [] },
    { key: 'valuation', label: '估值吸引力', score: 3, weight: 3, reasons: [], missing: [] },
    { key: 'sponsor', label: '保荐人', score: 1, weight: 1, reasons: [], missing: [] },
  ],
  risks: ['认购热度处于中下游。'],
  metrics: { is_ah: true, ah_premium: 70.4, a_ticker: '688337.SS', a_close_cny: 67.73, cny_hkd: 1.1565 },
  adjustments: [],
  issuance_shares: 24802200,
  lot_size: 100,
  greenshoe: true,
  cornerstone_investors: ['HHLR'],
  cornerstone_ratio: 42.11,
  sponsors: ['中信证券'],
  company_quality: ['2025年收入约9.00亿元。'],
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('App', () => {
  it('loads the latest IPO data from the API', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/ipos?active=true')) {
        return Response.json({ items: [{ ...ipo, dimensions: undefined, risks: undefined, metrics: undefined, adjustments: undefined }], total: 1, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      if (url.endsWith('/ipos/1')) return Response.json(ipo)
      if (url.endsWith('/reports')) return Response.json([{ id: 1, report_date: '2026-07-03', version: 1, created_at: '2026-07-03T14:39:47', item_count: 1, buy_count: 1, hold_count: 0, avoid_count: 0 }])
      return Response.json({}, { status: 404 })
    }))

    render(<App />)

    expect(screen.getByText('正在加载最新数据...')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/1 只真实 IPO/)).toBeInTheDocument())
    expect(screen.getAllByText('普源精电').length).toBeGreaterThan(0)
    expect(screen.getByText(/数据截至 2026-07-03 14:39/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /生成今日日报/ })).toBeInTheDocument()
  })
})
