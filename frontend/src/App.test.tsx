import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
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

const makeIPO = (overrides: Partial<typeof ipo>) => ({
  ...ipo,
  ...overrides,
  metrics: { ...ipo.metrics, ...(overrides.metrics ?? {}) },
})

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

  it('renders each IPO reason with its own recommendation tier', async () => {
    const qiyunshan = makeIPO({
      id: 2,
      name: '齐云山食品',
      code: '02797.HK',
      industry: '食品饮料',
      final_score: 3,
      recommendation: '回避',
      subscription_multiple: 6.48,
      company_quality: ['小型食品饮料企业，规模和成长性证据不足。'],
      risks: ['上市后流动性和估值承接不确定。'],
    })
    const luoshi = makeIPO({
      id: 3,
      name: '珞石机器人',
      code: '03752.HK',
      industry: '机器人',
      final_score: 4,
      recommendation: '观望',
      subscription_multiple: 7.75,
      company_quality: ['机器人赛道有关注度。'],
      risks: ['盈利和估值证据仍需观察。'],
    })
    const details = new Map([[qiyunshan.id, qiyunshan], [luoshi.id, luoshi]])

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/ipos?active=true')) {
        return Response.json({ items: [qiyunshan, luoshi], total: 2, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      const id = Number(url.match(/\/ipos\/(\d+)$/)?.[1])
      if (details.has(id)) return Response.json(details.get(id))
      if (url.endsWith('/reports')) return Response.json([{ id: 1, report_date: '2026-07-03', version: 1, created_at: '2026-07-03T14:39:47', item_count: 2, buy_count: 0, hold_count: 1, avoid_count: 1 }])
      return Response.json({}, { status: 404 })
    }))

    const { container } = render(<App />)

    await waitFor(() => expect(screen.getByText(/2 只真实 IPO/)).toBeInTheDocument())
    const qiyunshanReason = [...container.querySelectorAll('.reason-list article')].find(article => article.textContent?.includes('齐云山食品'))
    expect(qiyunshanReason).toBeTruthy()
    expect(within(qiyunshanReason as HTMLElement).getByText('回避')).toBeInTheDocument()
    expect(within(qiyunshanReason as HTMLElement).queryByText('观望')).not.toBeInTheDocument()
  })
})
