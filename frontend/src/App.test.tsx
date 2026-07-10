import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

const makeIPO = (overrides: Partial<Omit<typeof ipo, 'metrics'>> & { metrics?: Record<string, unknown> }) => ({
  ...ipo,
  ...overrides,
  metrics: { ...ipo.metrics, ...(overrides.metrics ?? {}) },
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('loads the latest IPO data from the API', async () => {
    const expiredIPO = makeIPO({
      id: 2,
      name: '历史科技',
      code: '09999.HK',
      deadline: '2026-07-02',
      recommendation: '观望',
      final_score: 5,
      metrics: {
        grey_market_price: 4.5,
        grey_market_reference_price: 5,
        grey_market_reference_label: '最终招股价',
      },
    })
    const previousCloseIPO = makeIPO({
      id: 3,
      name: '昨日下跌科技',
      code: '08888.HK',
      deadline: '2026-07-01',
      metrics: {
        grey_market_price: 4.5,
        grey_market_reference_price: 5,
        grey_market_reference_label: '昨日收盘价',
      },
    })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/ipos?active=true')) {
        return Response.json({ items: [{ ...ipo, dimensions: undefined, risks: undefined, metrics: undefined, adjustments: undefined }], total: 1, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      if (url.includes('/ipos?page_size=100')) {
        return Response.json({ items: [ipo, expiredIPO, previousCloseIPO], total: 3, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      if (url.endsWith('/ipos/1')) return Response.json(ipo)
      if (url.endsWith('/ipos/2')) return Response.json(expiredIPO)
      if (url.endsWith('/ipos/3')) return Response.json(previousCloseIPO)
      if (url.endsWith('/reports')) return Response.json([{ id: 1, report_date: '2026-07-03', version: 1, created_at: '2026-07-03T14:39:47', item_count: 1, buy_count: 1, hold_count: 0, avoid_count: 0 }])
      return Response.json({}, { status: 404 })
    }))

    render(<App />)

    expect(screen.getByRole('tab', { name: '港股' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '美股' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tab', { name: 'A股' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByText('正在加载最新数据...')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/1 只真实 IPO/)).toBeInTheDocument())
    expect(screen.getAllByText('普源精电').length).toBeGreaterThan(0)
    expect(screen.getByText(/数据截至 2026-07-03 14:39/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /生成今日日报/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: /历史记录/ })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /历史记录/ }))
    await waitFor(() => expect(screen.getByText('07-02 截止')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /历史科技/ }))
    expect(screen.getByRole('heading', { name: /历史科技/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '关闭详情' }))
    expect(screen.getByRole('heading', { name: '历史记录' })).toBeInTheDocument()
    expect(screen.getByText('历史科技')).toBeInTheDocument()
    expect(screen.getAllByText('破发')).toHaveLength(1)
  })

  it('renders the US dashboard and the A-share sentiment page', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/ipos?active=true')) {
        return Response.json({ items: [{ ...ipo, dimensions: undefined, risks: undefined, metrics: undefined, adjustments: undefined }], total: 1, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      if (url.includes('/ipos?page_size=100')) {
        return Response.json({ items: [ipo], total: 1, page: 1, page_size: 100, insights: { fundamental_valuation_ranking: [], allotment_difficulty: [] } })
      }
      if (url.endsWith('/ipos/1')) return Response.json(ipo)
      if (url.endsWith('/reports')) return Response.json([{ id: 1, report_date: '2026-07-03', version: 1, created_at: '2026-07-03T14:39:47', item_count: 1, buy_count: 1, hold_count: 0, avoid_count: 0 }])
      if (url.endsWith('/us-market/dashboard')) return Response.json({
        record_date: '2026-07-06',
        generated_at: '2026-07-06T10:20:00+08:00',
        source: 'Google News RSS / Yahoo Finance QQQ',
        cache_file: '/tmp/us_market_news_2026-07-06.json',
        highlights: ['偏强模块：半导体、内存芯片，短线更适合关注顺势延续。', 'QQQ 当前判断：偏强。科技权重仍有上行动能。'],
        modules: [
          { key: 'semiconductors', name: '半导体', focus: '人工智能算力', sentiment_score: 4, trend: '偏强', analysis: '半导体新闻偏正面。', news: [{ title: 'Nvidia chip demand rises', title_zh: '英伟达芯片需求上升', source: 'Reuters', source_zh: '路透社', url: 'https://example.com/1', published_at: null, article_summary_zh: '文章总结：英伟达芯片需求改善。', article_body_zh: '中文编译：英伟达芯片需求改善。', article_key_points_zh: ['英伟达芯片需求改善'], original_url: 'https://example.com/original-1', original_title: 'Nvidia chip demand rises', original_body: 'Nvidia chip demand rises as data center customers keep ordering accelerators.', original_saved_at: '2026-07-06T10:21:00+08:00' }] },
          { key: 'memory_chips', name: '内存芯片', focus: '高带宽内存 和 DRAM', sentiment_score: 3, trend: '偏强', analysis: '内存芯片周期改善。', news: [{ title: 'Micron memory demand improves', title_zh: '美光内存需求改善', source: 'Bloomberg', source_zh: '彭博社', url: 'https://example.com/2', published_at: null, article_summary_zh: '文章总结：美光内存周期改善。', article_body_zh: '中文编译：美光内存周期改善。', article_key_points_zh: ['美光内存周期改善'] }] },
        ],
        qqq: {
          symbol: 'QQQ',
          price: 512.34,
          change: 3.21,
          change_pct: 0.63,
          quote_time: '2026-07-03 22:00',
          trend: '偏强',
          analysis: 'QQQ 最新日内变动约 0.63%，新闻与价格信号偏强。',
          history: [
            { date: '2026-07-02', open: 508.1, high: 510.2, low: 506.8, close: 509.1, change_pct: 0.2 },
            { date: '2026-07-03', open: 509.4, high: 513.2, low: 508.9, close: 512.34, change_pct: 0.63 },
          ],
          news: [{ title: 'Nasdaq 100 ETF gains', title_zh: '纳指100ETF上涨', source: 'MarketWatch', source_zh: '市场观察', url: 'https://example.com/3', published_at: null, article_summary_zh: '文章总结：纳指100ETF走强。', article_body_zh: '中文编译：纳指100ETF走强。', article_key_points_zh: ['纳指100ETF走强'] }],
        },
      })
      if (url.endsWith('/a-shares/sentiment')) return Response.json({
        record_date: '2026-07-06',
        generated_at: '2026-07-06T09:40:00+08:00',
        average_price: 18.32,
        average_change_pct: 0.76,
        stock_count: 5535,
        up_count: 3300,
        down_count: 1800,
        flat_count: 435,
        sentiment_score: 67,
        sentiment_label: '回暖',
        market_source: '东方财富行情快照',
        hot_word_sources: ['东方财富股吧-上证指数'],
        sector_source: '东方财富板块行情',
        market_file: '/tmp/a_share_market_2026-07-06.csv',
        hot_words_file: '/tmp/a_share_hot_words_2026-07-06.csv',
        hot_sectors_file: '/tmp/a_share_hot_sectors_2026-07-06.csv',
        hot_words: [{ word: '反弹', count: 8, sentiment: 'positive', weight: 2 }, { word: '震荡', count: 5, sentiment: 'neutral', weight: 0 }],
        hot_sectors: [{ code: 'BK1620', name: '钴', price: 1257.3, change_pct: 5.97, turnover_rate: 2.06, amount: 516686880, main_inflow: 55120228, leading_stock: '寒锐钴业', leading_stock_code: '300618', leading_stock_change_pct: 6.75 }],
        market_sample: [{ code: '000001', name: '平安银行', price: 11.2, change_pct: 1.23, change: 0.14, volume: 100, amount: 200 }],
      })
      return Response.json({}, { status: 404 })
    }))

    render(<App />)

    await waitFor(() => expect(screen.getByText(/1 只真实 IPO/)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('tab', { name: '美股' }))
    expect(screen.getByRole('tab', { name: '美股' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByText('今日 IPO 分析')).not.toBeInTheDocument()
    expect(screen.queryByText('普源精电')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('美股行业动态')).toBeInTheDocument())
    expect(screen.getByText('内存芯片')).toBeInTheDocument()
    expect(screen.getByText('纳指100ETF 新闻动态')).toBeInTheDocument()
    expect(screen.getByText('英伟达芯片需求上升')).toBeInTheDocument()
    expect(screen.getByText('文章总结：英伟达芯片需求改善。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /英伟达芯片需求上升/ }))
    expect(screen.getByRole('heading', { name: '已保存原文' })).toBeInTheDocument()
    expect(screen.getByText(/data center customers keep ordering accelerators/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'A股' }))
    expect(screen.getByRole('tab', { name: 'A股' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.queryByText('今日 IPO 分析')).not.toBeInTheDocument()
    expect(screen.queryByText('普源精电')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('A股市场情绪图')).toBeInTheDocument())
    expect(screen.getByText('67')).toBeInTheDocument()
    expect(screen.getByText('反弹')).toBeInTheDocument()
    expect(screen.getByText('热点板块')).toBeInTheDocument()
    expect(screen.getAllByText('钴').length).toBeGreaterThan(0)
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
      if (url.includes('/ipos?page_size=100')) {
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
