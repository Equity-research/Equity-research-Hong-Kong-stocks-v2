import { useEffect, useMemo, useState } from 'react'
import { FileText, RefreshCw, X } from 'lucide-react'
import { api } from './api'
import type { AShareSentiment, IPODetail, Report } from './types'

type Tier = '申购' | '观望' | '回避'
type Market = 'hk' | 'us' | 'cn'

interface LatestIPO {
  id: number
  code: string
  name: string
  industry: string
  price: string
  end: string
  minimum: number | null
  sub: number | null
  issuanceShares: number | null
  lotSize: number | null
  greenshoe: boolean | null
  cornerstoneInvestors: string[]
  cornerstoneRatio: number | null
  sponsors: string[]
  scores: number[]
  total: number
  tier: Tier
  summary: string
  isAh: boolean
  ahPremium: number | null
  aTicker: string | null
  aClose: number | null
  cnyHkd: number | null
  quality: string[]
  risks: string[]
}

const SCORE_LABELS = ['基石投资者', '基石质量', '绿鞋机制', '公开申购倍数', '估值吸引力', '保荐人']
const SCORE_WEIGHTS = [1, 1, 1, 3, 3, 1]
const MARKET_TABS: Array<{ key: Market; label: string }> = [
  { key: 'hk', label: '港股' },
  { key: 'us', label: '美股' },
  { key: 'cn', label: 'A股' },
]

const money = (value: number | null) => value == null ? '待补充' : `HK$${Math.round(value).toLocaleString('zh-HK')}`
const numberText = (value: number | null, suffix = '') => value == null ? '待补充' : `${value.toLocaleString('zh-HK')}${suffix}`
const tierClass = (tier: Tier) => tier === '申购' ? 'buy' : tier === '观望' ? 'hold' : 'avoid'
const shortDate = (value: string) => value.slice(5)
const priceText = (low: number, high: number) => low === high ? low.toFixed(2) : `${low.toFixed(2)}–${high.toFixed(2)}`
const cnyAmount = (value: number) => {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(1)}亿`
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(1)}万`
  return `${value.toFixed(0)}`
}

function summaryText(item: IPODetail) {
  const multiple = item.subscription_multiple
  const prefix = `规则${item.final_score.toFixed(0)}分`
  if (item.recommendation === '申购') return `${prefix}；评分达到申购区间，但仍需控制单票仓位。`
  if (item.recommendation === '观望') {
    return `${prefix}；仍可申购，认购热度${multiple == null ? '待补充' : `${multiple.toFixed(2)}倍`}，建议结合估值和中签率谨慎观察。`
  }
  return `${prefix}；当前规则分偏低，暂不纳入优先申购。`
}

function toLatestIPO(item: IPODetail): LatestIPO {
  const dimensions = Object.fromEntries(item.dimensions.map(dimension => [dimension.key, dimension]))
  const metrics = item.metrics
  return {
    id: item.id,
    code: item.code.replace('.HK', ''),
    name: item.name,
    industry: item.industry,
    price: priceText(item.price_low, item.price_high),
    end: item.deadline,
    minimum: item.minimum_subscription_amount,
    sub: item.subscription_multiple,
    issuanceShares: item.issuance_shares,
    lotSize: item.lot_size,
    greenshoe: item.greenshoe,
    cornerstoneInvestors: item.cornerstone_investors,
    cornerstoneRatio: item.cornerstone_ratio,
    sponsors: item.sponsors,
    scores: SCORE_LABELS.map((_, index) => {
      const keys = ['cornerstone_presence', 'cornerstone_quality', 'greenshoe', 'subscription', 'valuation', 'sponsor']
      return dimensions[keys[index]]?.score ?? 0
    }),
    total: item.final_score,
    tier: item.recommendation,
    summary: summaryText(item),
    isAh: Boolean(metrics.is_ah),
    ahPremium: typeof metrics.ah_premium === 'number' ? metrics.ah_premium : null,
    aTicker: typeof metrics.a_ticker === 'string' ? metrics.a_ticker : null,
    aClose: typeof metrics.a_close_cny === 'number' ? metrics.a_close_cny : null,
    cnyHkd: typeof metrics.cny_hkd === 'number' ? metrics.cny_hkd : null,
    quality: item.company_quality,
    risks: item.risks,
  }
}

function formatTimestamp(report: Report | null) {
  if (!report) return '实时 API'
  const createdAt = report.created_at.replace('T', ' ').slice(0, 16)
  return `${report.report_date} ${createdAt.slice(11)}`
}

function formatDateTime(value?: string) {
  if (!value) return '待获取'
  return value.replace('T', ' ').replace(/\+.*/, '').slice(0, 19)
}

const tierOrder: Record<Tier, number> = { '申购': 0, '观望': 1, '回避': 2 }

function reasonPoints(item: LatestIPO) {
  return [
    item.summary,
    ...item.quality,
    ...item.risks,
  ].filter(Boolean)
}

function Insights({ data, onOpen }: { data: LatestIPO[]; onOpen: (item: LatestIPO) => void }) {
  const investable = data.filter(item => item.tier !== '回避')
  const ranking = [...investable].sort((a, b) => (b.total - a.total) || ((b.sub ?? 0) - (a.sub ?? 0)))
  const bands = [
    { label: '极难', min: 100, max: Infinity, note: '百倍以上认购，预计中签率最低' },
    { label: '较难', min: 50, max: 100, note: '50至100倍认购' },
    { label: '中等', min: 10, max: 50, note: '10至50倍认购' },
    { label: '较易', min: 0, max: 10, note: '低于10倍认购；仍不代表一定获配' },
  ].map(band => ({
    ...band,
    companies: data.filter(item => item.sub != null && item.sub >= band.min && item.sub < band.max).map(item => item.name),
  })).filter(group => group.companies.length)
  const reasons = [...data].sort((a, b) => (tierOrder[a.tier] - tierOrder[b.tier]) || (b.total - a.total) || ((b.sub ?? 0) - (a.sub ?? 0)))

  return <section className="summary-card">
    <div className="stats">
      <div><span>今日项目数</span><strong>{data.length}</strong></div>
      <div><span>建议申购</span><strong className="green">{data.filter(x => x.tier === '申购').length}</strong></div>
      <div><span>建议观望</span><strong className="amber">{data.filter(x => x.tier === '观望').length}</strong></div>
      <div><span>建议回避</span><strong className="red">{data.filter(x => x.tier === '回避').length}</strong></div>
    </div>
    <div className="insights">
      <section className="decision-reasons"><h3>1）申购/不申购原因</h3><div className="reason-list">
        {reasons.map(item => <article key={item.code}>
          <b><button className="reason-link" type="button" onClick={() => onOpen(item)}>{item.name}</button><span className={tierClass(item.tier)}>{item.tier}</span></b>
          <ul>{reasonPoints(item).map(point => <li key={point}>{point}</li>)}</ul>
        </article>)}
      </div></section>
      <section><h3>2）按优先级排序</h3><p>{ranking.map(item => item.name).join(' > ') || '暂无项目'}</p></section>
      <section><h3>3）中签难度初判</h3><dl>{bands.map(group => <div key={group.label}><dt>{group.label}</dt><dd>{group.companies.join(' + ')}<small>{group.note}</small></dd></div>)}</dl></section>
    </div>
  </section>
}

function FundingConflict({ data }: { data: LatestIPO[] }) {
  const investable = data.filter(item => item.tier !== '回避')
  const byDate = new Map<string, LatestIPO[]>()
  investable.forEach(item => byDate.set(item.end, [...(byDate.get(item.end) ?? []), item]))
  const pressure = [...byDate.entries()].map(([date, items]) => ({
    date,
    items,
    total: items.reduce((sum, item) => sum + (item.minimum ?? 0), 0),
  })).sort((a, b) => b.total - a.total)
  const highest = pressure[0]
  if (!highest) return null
  return <section className="funding-card">
    <div>
      <h3>4）资金冲突情况</h3>
      <p>压力最高 <strong>{shortDate(highest.date)}</strong></p>
      <p>{highest.items.length} 只，最低一手约 {money(highest.total)}</p>
      <p>申购/观望票最低一手合计约 {money(highest.total)}，同日截止需预留现金。</p>
    </div>
    <div className="funding-days">{pressure.map(group => <article key={group.date}>
      <b>{shortDate(group.date)}</b>
      <strong>{[...group.items].sort((a, b) => b.total - a.total).map(item => item.name).join(' + ')}</strong>
      <span>最低一手合计 {money(group.total)}</span>
    </article>)}</div>
  </section>
}

function IPOCard({ item, onOpen }: { item: LatestIPO; onOpen: (item: LatestIPO) => void }) {
  return <button className="ipo-card" type="button" onClick={() => onOpen(item)}>
    <div className="ipo-top">
      <div><div className="ipo-title"><strong>{item.name}</strong>{item.isAh && <span>A+H</span>}</div><small>{item.code}.HK · {item.industry}</small></div>
      <b className={tierClass(item.tier)}>{item.tier}</b>
    </div>
    <div className="metrics">
      <span><b>招股价</b>{item.price} HKD</span>
      <span><b>最小申购金额</b>{item.minimum == null ? '待补充' : `${item.minimum.toLocaleString('zh-HK')} HKD`}</span>
      <span><b>市场申购倍数</b>{item.sub == null ? '待补充' : `${item.sub.toFixed(2)} 倍`}</span>
    </div>
  </button>
}

function DetailDrawer({ item, onClose }: { item: LatestIPO | null; onClose: () => void }) {
  return <>
    <div className={item ? 'backdrop open' : 'backdrop'} onClick={onClose} />
    <aside className={item ? 'drawer open' : 'drawer'} aria-hidden={!item}>
      {item && <>
        <button className="close" aria-label="关闭详情" onClick={onClose}><X size={22} /></button>
        <div className="drawer-head">
          <h2>{item.name}{item.isAh && <span>A+H</span>}</h2>
          <p>{item.code}.HK · {item.industry}</p>
          <b className={tierClass(item.tier)}>{item.tier}</b>
        </div>
        <p className="drawer-meta">港股招股价区间 {item.price} HKD　截止 {item.end}　最小申购 {money(item.minimum)}　认购倍数 {item.sub == null ? '待补充' : `${item.sub.toFixed(2)} 倍`}</p>
        <section><h3>发行资料</h3><dl className="issue-grid">
          <div><dt>港股招股价区间</dt><dd>{item.price} HKD</dd></div>
          <div><dt>绿鞋</dt><dd>{item.greenshoe == null ? '待补充' : item.greenshoe ? '有' : '无'}</dd></div>
          <div><dt>基石投资者</dt><dd>{item.cornerstoneInvestors.length ? item.cornerstoneInvestors.join('、') : '待补充'}</dd></div>
          <div><dt>基石占比</dt><dd>{item.cornerstoneRatio == null ? '待补充' : `${item.cornerstoneRatio.toFixed(2)}%`}</dd></div>
          <div><dt>发行数量</dt><dd>{numberText(item.issuanceShares, ' 股')}</dd></div>
          <div><dt>每手股数</dt><dd>{numberText(item.lotSize, ' 股')}</dd></div>
          <div><dt>保荐人</dt><dd>{item.sponsors.length ? item.sponsors.join('、') : '待补充'}</dd></div>
        </dl></section>
        <section><h3>A/H 估值</h3><div className="ah-valuation">
          <p className="ah-offer-price"><span>港股招股价区间</span><strong>{item.price} HKD</strong></p>
          <p>{item.ahPremium == null ? '非 A+H 或数据待补充' : `A股 ${item.aTicker} 最新收盘 ${item.aClose?.toFixed(2)} CNY，CNY/HKD ${item.cnyHkd?.toFixed(4)}，A/H 溢价 ${item.ahPremium.toFixed(1)}%`}</p>
        </div></section>
        <section><h3>公司质地</h3><ul>{item.quality.map(text => <li key={text}>{text}</li>)}</ul></section>
        <section><h3>风险提示</h3><ul>{item.risks.map(text => <li key={text}>{text}</li>)}</ul></section>
        <section className="conclusion"><h3>研究结论</h3><p>{item.summary}</p></section>
        <section><h3>评分维度</h3>{item.scores.map((score, index) => <div className="dim" key={SCORE_LABELS[index]}><span>{SCORE_LABELS[index]}</span><i><em style={{ width: `${Math.min(100, score / SCORE_WEIGHTS[index] * 100)}%` }} /></i><b>{score}</b></div>)}</section>
      </>}
    </aside>
  </>
}

function AShareEmotion({ data, loading, error, onRefresh }: { data: AShareSentiment | null; loading: boolean; error: string; onRefresh: () => void }) {
  const maxWordCount = Math.max(1, ...(data?.hot_words.map(word => word.count) ?? [1]))
  return <section className="cn-market">
    <div className="page-title"><div><h1>A股市场情绪图</h1></div><div className="refresh-panel"><button className="secondary" onClick={onRefresh} disabled={loading}><RefreshCw size={16}/>{loading ? '刷新中...' : '刷新数据'}</button><small>数据抓取时间：{formatDateTime(data?.generated_at)}</small></div></div>
    {error && <div className="alert">{error}</div>}
    {loading && <div className="empty">正在读取 A股行情、热词和板块数据...</div>}
    {!loading && data && <>
      <div className="emotion-hero">
        <div className="emotion-gauge" style={{ ['--score' as string]: `${data.sentiment_score}%` }}>
          <span>市场情绪</span>
          <strong>{data.sentiment_score}</strong>
          <b>{data.sentiment_label}</b>
        </div>
        <div className="cn-stats">
          <div><span>当日平均股价</span><strong>{data.average_price.toFixed(2)}</strong></div>
          <div><span>平均涨跌幅</span><strong className={data.average_change_pct >= 0 ? 'green' : 'red'}>{data.average_change_pct.toFixed(2)}%</strong></div>
          <div><span>上涨/下跌</span><strong><i className="green">{data.up_count}</i><small>/</small><i className="red">{data.down_count}</i></strong></div>
          <div><span>样本股票数</span><strong>{data.stock_count}</strong></div>
        </div>
      </div>
      <div className="emotion-grid">
        <section className="hot-words">
          <h3>评论热词</h3>
          <div>{data.hot_words.map(word => <article key={word.word} className={word.sentiment}>
            <b>{word.word}</b>
            <i><em style={{ width: `${Math.max(12, word.count / maxWordCount * 100)}%` }} /></i>
            <span>{word.count}</span>
          </article>)}</div>
        </section>
        <section className="market-sample">
          <h3>行情样本</h3>
          <div>{data.market_sample.slice(0, 10).map(item => <article key={item.code}>
            <b>{item.name}</b>
            <span>{item.price.toFixed(2)}</span>
            <strong className={item.change_pct >= 0 ? 'green' : 'red'}>{item.change_pct.toFixed(2)}%</strong>
          </article>)}</div>
        </section>
      </div>
      <section className="hot-sectors">
        <h3>热点板块</h3>
        <div>{data.hot_sectors.slice(0, 12).map((sector, index) => <article key={sector.code}>
          <b>{index + 1}</b>
          <strong>{sector.name}<small>{sector.code}</small></strong>
          <span className={sector.change_pct >= 0 ? 'green' : 'red'}>{sector.change_pct.toFixed(2)}%</span>
          <span>成交 {cnyAmount(sector.amount)}</span>
          <span className={sector.main_inflow >= 0 ? 'green' : 'red'}>主力 {cnyAmount(sector.main_inflow)}</span>
          <em>领涨 {sector.leading_stock || '待补充'} {sector.leading_stock_change_pct ? `${sector.leading_stock_change_pct.toFixed(2)}%` : ''}</em>
        </article>)}</div>
      </section>
    </>}
  </section>
}

export default function App() {
  const [market, setMarket] = useState<Market>('hk')
  const [industry, setIndustry] = useState('')
  const [tier, setTier] = useState('')
  const [selected, setSelected] = useState<LatestIPO | null>(null)
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [data, setData] = useState<LatestIPO[]>([])
  const [aShareData, setAShareData] = useState<AShareSentiment | null>(null)
  const [aShareLoading, setAShareLoading] = useState(false)
  const [aShareError, setAShareError] = useState('')

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const reports = await api.reports()
      const reportDate = reports[0]?.report_date
      const activeParams = reportDate
        ? `?active=true&report_date=${encodeURIComponent(reportDate)}&page_size=100`
        : '?active=true&page_size=100'
      const listing = await api.listIPOs(activeParams)
      const details = await Promise.all(listing.items.map(item => api.getIPO(item.id)))
      setData(details.map(toLatestIPO).sort((a, b) => (b.total - a.total) || ((b.sub ?? 0) - (a.sub ?? 0))))
      setReport(reports[0] ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const loadAShareData = async (refresh = false) => {
    setAShareLoading(true)
    setAShareError('')
    try {
      setAShareData(await api.aShareSentiment(refresh))
    } catch (e) {
      setAShareError(e instanceof Error ? e.message : 'A股情绪数据加载失败')
    } finally {
      setAShareLoading(false)
    }
  }

  useEffect(() => {
    if (market === 'cn' && !aShareData && !aShareLoading) void loadAShareData(false)
  }, [market])

  const industries = useMemo(() => [...new Set(data.map(item => item.industry))].sort(), [data])
  const visible = data.filter(item => (!industry || item.industry === industry) && (!tier || item.tier === tier))
  const createReport = async () => {
    setGenerating(true)
    setError('')
    try {
      const nextReport = await api.createReport()
      setReport(nextReport)
      await loadData()
      window.open(api.downloadUrl(nextReport.id, 'pdf'), '_blank')
    } catch (e) {
      setError(e instanceof Error ? e.message : '日报生成失败')
    } finally {
      setGenerating(false)
    }
  }

  return <main className="page">
    <div className="market-tabs" role="tablist" aria-label="市场">
      {MARKET_TABS.map(tab => <button
        key={tab.key}
        type="button"
        role="tab"
        aria-selected={market === tab.key}
        className={market === tab.key ? 'active' : ''}
        onClick={() => {
          setMarket(tab.key)
          setSelected(null)
        }}
      >{tab.label}</button>)}
    </div>
    {market === 'hk' ? <>
      <div className="page-title"><div><h1>今日 IPO 分析</h1><p>{data.length || 0} 只真实 IPO · 透明评分 · 数据截至 {formatTimestamp(report)}</p></div><button className="primary" onClick={createReport} disabled={generating}><FileText size={18}/>{generating ? '生成中...' : '生成今日日报'}</button></div>
      {error && <div className="alert">{error}</div>}
      {loading && <div className="empty">正在加载最新数据...</div>}
      {!loading && !error && <>
        <Insights data={data} onOpen={setSelected} />
        <FundingConflict data={data} />
        <div className="filters"><label>行业<select value={industry} onChange={e => setIndustry(e.target.value)}><option value="">全部</option>{industries.map(value => <option key={value}>{value}</option>)}</select></label><label>推荐<select value={tier} onChange={e => setTier(e.target.value)}><option value="">全部</option><option>申购</option><option>观望</option><option>回避</option></select></label><button className="secondary" onClick={() => { setIndustry(''); setTier('') }}><RefreshCw size={16}/>重置</button></div>
        <section className="cards">{visible.map(item => <IPOCard item={item} key={item.code} onOpen={setSelected} />)}</section>
        {!visible.length && <div className="empty">没有符合条件的 IPO</div>}
      </>}
    </> : market === 'cn' ? <AShareEmotion data={aShareData} loading={aShareLoading} error={aShareError} onRefresh={() => loadAShareData(true)} /> : <section className="blank-market" aria-label={`${MARKET_TABS.find(tab => tab.key === market)?.label}页面`} />}
    <DetailDrawer item={selected} onClose={() => setSelected(null)} />
    <footer>免责声明：数据来自本地招股书及结构化资料，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。</footer>
  </main>
}
