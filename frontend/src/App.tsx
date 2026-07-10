import { type CSSProperties, useEffect, useMemo, useState } from 'react'
import { Archive, FileText, RefreshCw, X } from 'lucide-react'
import { api } from './api'
import type { AShareSentiment, AShareSentimentHistoryPoint, IPODetail, Report, USMarketDashboard, USMarketNewsItem } from './types'

type Tier = '申购' | '观望' | '回避'
type Market = 'hk' | 'us' | 'cn'
type HKStage = 'subscribing' | 'filed'

interface LatestIPO {
  id: number
  code: string
  name: string
  industry: string
  price: string
  offerPriceLabel: string
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
  expectedListingDate: string | null
  greyMarketPrice: number | null
  greyMarketChangePct: number | null
  greyMarketReferencePrice: number | null
  greyMarketReferenceLabel: string | null
  greyMarketFetchedAt: string | null
  greyMarketSource: string | null
  greyMarketFinalized: boolean
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
const HK_STAGE_TABS: Array<{ key: HKStage; label: string }> = [
  { key: 'subscribing', label: '申购中' },
  { key: 'filed', label: '已递表' },
]

const money = (value: number | null) => value == null ? '待补充' : `HK$${Math.round(value).toLocaleString('zh-HK')}`
const numberText = (value: number | null, suffix = '') => value == null ? '待补充' : `${value.toLocaleString('zh-HK')}${suffix}`
const tierClass = (tier: Tier) => tier === '申购' ? 'buy' : tier === '观望' ? 'hold' : 'avoid'
const ipoLabel = (item: LatestIPO) => `${item.name}（${item.code}.HK）`
const shortDate = (value: string) => value.slice(5)
const priceText = (low: number, high: number) => low === high ? low.toFixed(2) : `${low.toFixed(2)}–${high.toFixed(2)}`
const offerPriceLabel = (low: number, high: number) => low === high ? '港股最终招股价' : '港股招股价区间'
const signedPct = (value: number | null) => value == null ? '' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
const isBelowOfferPrice = (item: LatestIPO) => (
  item.greyMarketPrice != null
  && item.greyMarketReferencePrice != null
  && (item.greyMarketReferenceLabel === '最终招股价' || item.greyMarketReferenceLabel === '最新招股价')
  && item.greyMarketPrice < item.greyMarketReferencePrice
)
const localISODate = () => {
  const now = new Date()
  const offsetMs = now.getTimezoneOffset() * 60 * 1000
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 10)
}
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
    offerPriceLabel: offerPriceLabel(item.price_low, item.price_high),
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
    expectedListingDate: typeof metrics.expected_listing_date === 'string' ? metrics.expected_listing_date : null,
    greyMarketPrice: typeof metrics.grey_market_price === 'number' ? metrics.grey_market_price : null,
    greyMarketChangePct: typeof metrics.grey_market_change_pct === 'number' ? metrics.grey_market_change_pct : null,
    greyMarketReferencePrice: typeof metrics.grey_market_reference_price === 'number' ? metrics.grey_market_reference_price : null,
    greyMarketReferenceLabel: typeof metrics.grey_market_reference_label === 'string' ? metrics.grey_market_reference_label : null,
    greyMarketFetchedAt: typeof metrics.grey_market_fetched_at === 'string' ? metrics.grey_market_fetched_at : null,
    greyMarketSource: typeof metrics.grey_market_source === 'string' ? metrics.grey_market_source : null,
    greyMarketFinalized: metrics.grey_market_finalized === true,
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
    companies: data.filter(item => item.sub != null && item.sub >= band.min && item.sub < band.max).map(ipoLabel),
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
          <b><button className="reason-link" type="button" onClick={() => onOpen(item)}>{ipoLabel(item)}</button><span className={tierClass(item.tier)}>{item.tier}</span></b>
          <ul>{reasonPoints(item).map(point => <li key={point}>{point}</li>)}</ul>
        </article>)}
      </div></section>
      <section><h3>2）按优先级排序</h3><p>{ranking.map(ipoLabel).join(' > ') || '暂无项目'}</p></section>
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
      <strong>{[...group.items].sort((a, b) => b.total - a.total).map(ipoLabel).join(' + ')}</strong>
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

function GreyMarketInput({ item, onSave, onFinalize, saving }: { item: LatestIPO; onSave: (item: LatestIPO, price: number) => void; onFinalize: (item: LatestIPO) => void; saving: boolean }) {
  const [editing, setEditing] = useState(item.greyMarketPrice == null)
  const [value, setValue] = useState(item.greyMarketPrice == null ? '' : item.greyMarketPrice.toFixed(2))
  const price = Number(value)
  const canSave = Number.isFinite(price) && price > 0
  const canEdit = !item.greyMarketFinalized
  useEffect(() => {
    if (!editing) setValue(item.greyMarketPrice == null ? '' : item.greyMarketPrice.toFixed(2))
  }, [editing, item.greyMarketPrice])
  return <div className="grey-market history-grey-market">
    <span><b>暗盘价格</b>{item.greyMarketPrice == null ? '待输入' : `${item.greyMarketPrice.toFixed(2)} HKD`}</span>
    {canEdit && editing ? <form className="grey-market-form" onSubmit={event => {
      event.preventDefault()
      if (canSave) {
        onSave(item, price)
        setEditing(false)
      }
    }}>
      <input aria-label={`${item.name} 暗盘价格`} inputMode="decimal" placeholder="输入价格" value={value} onChange={event => setValue(event.target.value)} />
      <button className="secondary grey-market-fetch" type="submit" disabled={!canSave || saving}>{saving ? '保存中...' : '保存'}</button>
    </form> : <div className="grey-market-actions">
      {item.greyMarketChangePct != null && <em className={item.greyMarketChangePct < 0 ? 'green' : 'red'} title={`${item.greyMarketReferenceLabel ?? '参考价'} ${item.greyMarketReferencePrice?.toFixed(2) ?? '待获取'} HKD`}>{signedPct(item.greyMarketChangePct)}</em>}
      {canEdit && item.greyMarketPrice != null && <>
        <button type="button" className="secondary grey-market-fetch" onClick={() => setEditing(true)} disabled={saving}>更新</button>
        <button type="button" className="secondary grey-market-fetch" onClick={() => onFinalize(item)} disabled={saving}>完成录入</button>
      </>}
    </div>}
  </div>
}

function IPOHistoryModal({ items, referenceDate, onOpen, onClose, onSaveGreyMarket, onFinalizeGreyMarket, greyMarketLoadingIds }: { items: LatestIPO[]; referenceDate: string; onOpen: (item: LatestIPO) => void; onClose: () => void; onSaveGreyMarket: (item: LatestIPO, price: number) => void; onFinalizeGreyMarket: (item: LatestIPO) => void; greyMarketLoadingIds: number[] }) {
  const grouped = [...items]
    .sort((a, b) => b.end.localeCompare(a.end) || (b.total - a.total))
    .reduce<Array<{ date: string; items: LatestIPO[] }>>((groups, item) => {
      const group = groups.find(entry => entry.date === item.end)
      if (group) group.items.push(item)
      else groups.push({ date: item.end, items: [item] })
      return groups
    }, [])

  return <>
    <div className="history-backdrop open" onClick={onClose} />
    <section className="history-modal ipo-history-modal" aria-label="IPO 历史记录">
      <button className="close" aria-label="关闭历史记录" onClick={onClose}><X size={22} /></button>
      <h2>历史记录</h2>
      <p>已收起截止日期早于 {referenceDate} 的分析记录，共 {items.length} 只。</p>
      {items.length ? <div className="ipo-history-list">
        {grouped.map(group => <details className="ipo-history-group" key={group.date}>
          <summary><span>{shortDate(group.date)} 截止</span><b>{group.items.length} 只</b></summary>
          <div>{group.items.map(item => <article className="ipo-history-item" key={item.code}>
            <button className="ipo-history-main" type="button" onClick={() => onOpen(item)}>
              <span className="ipo-history-title"><strong>{item.name}</strong><small>{item.code}.HK · {item.industry}</small></span>
              <span className="ipo-history-badges">
                <b className={tierClass(item.tier)}>{item.tier}</b>
                {isBelowOfferPrice(item) && <b className="break-badge">破发</b>}
              </span>
              <em>{item.total.toFixed(0)}分</em>
            </button>
            <GreyMarketInput item={item} onSave={onSaveGreyMarket} onFinalize={onFinalizeGreyMarket} saving={greyMarketLoadingIds.includes(item.id)} />
          </article>)}</div>
        </details>)}
      </div> : <div className="empty">暂无过期 IPO 记录</div>}
    </section>
  </>
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
        <p className="drawer-meta">{item.offerPriceLabel} {item.price} HKD　截止 {item.end}　最小申购 {money(item.minimum)}　认购倍数 {item.sub == null ? '待补充' : `${item.sub.toFixed(2)} 倍`}</p>
        <section><h3>暗盘价格</h3><div className="grey-market-detail">
          <strong>{item.greyMarketPrice == null ? '待获取' : `${item.greyMarketPrice.toFixed(2)} HKD`}</strong>
          {item.greyMarketChangePct != null && <b className={item.greyMarketChangePct < 0 ? 'green' : 'red'}>{signedPct(item.greyMarketChangePct)}</b>}
          <span>{item.greyMarketFetchedAt ? `记录时间 ${formatDateTime(item.greyMarketFetchedAt)} · ${item.greyMarketSource ?? '行情源'} · 按${item.greyMarketReferenceLabel ?? '参考价'} ${item.greyMarketReferencePrice?.toFixed(2) ?? '待获取'} HKD 计算` : '可在历史记录里手动输入暗盘价格；暗盘开始后会尝试获取最新招股价并计算暗盘涨跌幅。'}</span>
        </div></section>
        <section><h3>发行资料</h3><dl className="issue-grid">
          <div><dt>{item.offerPriceLabel}</dt><dd>{item.price} HKD</dd></div>
          <div><dt>绿鞋</dt><dd>{item.greenshoe == null ? '待补充' : item.greenshoe ? '有' : '无'}</dd></div>
          <div><dt>基石投资者</dt><dd>{item.cornerstoneInvestors.length ? item.cornerstoneInvestors.join('、') : '待补充'}</dd></div>
          <div><dt>基石占比</dt><dd>{item.cornerstoneRatio == null ? '待补充' : `${item.cornerstoneRatio.toFixed(2)}%`}</dd></div>
          <div><dt>发行数量</dt><dd>{numberText(item.issuanceShares, ' 股')}</dd></div>
          <div><dt>每手股数</dt><dd>{numberText(item.lotSize, ' 股')}</dd></div>
          <div><dt>保荐人</dt><dd>{item.sponsors.length ? item.sponsors.join('、') : '待补充'}</dd></div>
        </dl></section>
        <section><h3>A/H 估值</h3><div className="ah-valuation">
          <p className="ah-offer-price"><span>{item.offerPriceLabel}</span><strong>{item.price} HKD</strong></p>
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

function SentimentHistoryModal({ points, loading, error, onClose }: { points: AShareSentimentHistoryPoint[]; loading: boolean; error: string; onClose: () => void }) {
  const width = 620
  const height = 260
  const padding = 36
  const plotWidth = width - padding * 2
  const plotHeight = height - padding * 2
  const x = (index: number) => padding + (points.length <= 1 ? plotWidth / 2 : index / (points.length - 1) * plotWidth)
  const y = (score: number) => padding + (100 - score) / 100 * plotHeight

  return <>
    <div className="history-backdrop open" onClick={onClose} />
    <section className="history-modal" aria-label="近15日市场情绪">
      <button className="close" aria-label="关闭历史情绪" onClick={onClose}><X size={22} /></button>
      <h2>近15日市场情绪</h2>
      {loading && <div className="empty">正在读取历史情绪...</div>}
      {error && <div className="alert">{error}</div>}
      {!loading && !error && <>
        <p>{points.length >= 15 ? '显示最近15个交易记录' : `数据库中仅有 ${points.length} 条记录`}</p>
        {points.length ? <svg className="sentiment-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="市场情绪点状图">
          {[0, 25, 50, 75, 100].map(score => <g key={score}>
            <line x1={padding} x2={width - padding} y1={y(score)} y2={y(score)} />
            <text x={8} y={y(score) + 4}>{score}</text>
          </g>)}
          {points.map((point, index) => <g key={point.record_date}>
            <circle cx={x(index)} cy={y(point.sentiment_score)} r={7} />
            <text className="score-label" x={x(index)} y={y(point.sentiment_score) - 12}>{point.sentiment_score}</text>
            <text className="date-label" x={x(index)} y={height - 10}>{point.record_date.slice(5)}</text>
          </g>)}
        </svg> : <div className="empty">暂无收盘后市场情绪记录</div>}
      </>}
    </section>
  </>
}

function NewsDetailModal({ item, onClose }: { item: USMarketNewsItem; onClose: () => void }) {
  const summary = (item.article_summary_zh || '暂未提取到可用中文摘要。').replace(/^链接页摘要：/, '').replace(/^文章总结：/, '')
  const body = (item.article_body_zh || '链接页正文暂未提取到可用中文译文。').replace(/^中文编译：/, '')
  const originalBody = item.original_body?.trim()
  return <>
    <div className="history-backdrop open" onClick={onClose} />
    <section className="history-modal news-detail-modal" aria-label="美股新闻详情">
      <button className="close" aria-label="关闭新闻详情" onClick={onClose}><X size={22} /></button>
      <h2>{item.article_title_zh || item.title_zh || item.title || '美股新闻动态'}</h2>
      <p>{item.source_zh || '海外媒体'}{item.published_at ? ` · ${item.published_at}` : ''}</p>
      <article>
        <strong>{item.title_zh || item.article_title_zh || item.title || '美股新闻动态'}</strong>
        <section>
          <h3>文章总结</h3>
          <p>{summary}</p>
        </section>
        <section>
          <h3>译文正文</h3>
          <p>{body}</p>
        </section>
        <section>
          <h3>已保存原文</h3>
          {originalBody ? <>
            {item.original_title && <b className="original-title">{item.original_title}</b>}
            <p className="original-body">{originalBody}</p>
            {item.original_saved_at && <small>保存时间：{formatDateTime(item.original_saved_at)}</small>}
          </> : <p>暂未抓取到原文正文，请刷新数据后重试。</p>}
        </section>
      </article>
    </section>
  </>
}

function NewsLink({ item, onOpen }: { item: USMarketNewsItem; onOpen: (item: USMarketNewsItem) => void }) {
  return <button className="news-button" type="button" onClick={() => onOpen(item)}>
    <span>{item.title_zh || item.article_title_zh || item.title || '美股新闻动态'}</span>
    <small>{item.source_zh || '海外媒体'}</small>
    {item.article_summary_zh && <em>{item.article_summary_zh}</em>}
  </button>
}

function QQQDailyKLine({ history }: { history: NonNullable<USMarketDashboard['qqq']>['history'] }) {
  const width = 320
  const height = 128
  const padding = 12
  const values = history.flatMap(item => [item.high, item.low, item.open, item.close].filter((value): value is number => value != null))
  const maxValue = Math.max(...values, 1)
  const minValue = Math.min(...values, maxValue)
  const range = Math.max(maxValue - minValue, 1)
  const step = history.length ? (width - padding * 2) / history.length : 0
  const y = (value: number | null) => value == null ? height - padding : padding + (maxValue - value) / range * (height - padding * 2)
  return <div className="qqq-kline" aria-label="纳指100ETF日K线">
    <svg viewBox={`0 0 ${width} ${height}`} role="img">
      {history.map((item, index) => {
        const open = item.open ?? item.close
        const close = item.close ?? item.open
        const high = item.high ?? Math.max(open ?? 0, close ?? 0)
        const low = item.low ?? Math.min(open ?? 0, close ?? 0)
        const x = padding + step * index + step / 2
        const candleWidth = Math.max(6, Math.min(12, step * 0.48))
        const top = Math.min(y(open), y(close))
        const bodyHeight = Math.max(Math.abs(y(open) - y(close)), 2)
        const up = close != null && open != null && close >= open
        return <g key={item.date ?? index} className={up ? 'up' : 'down'}>
          <title>{`${item.date ?? ''} 开 ${open ?? '-'} 高 ${high ?? '-'} 低 ${low ?? '-'} 收 ${close ?? '-'}`}</title>
          <line x1={x} x2={x} y1={y(high)} y2={y(low)} />
          <rect x={x - candleWidth / 2} y={top} width={candleWidth} height={bodyHeight} rx={1.5} />
        </g>
      })}
    </svg>
    <span>日 K 线</span>
  </div>
}

function USMarketDashboardView({ data, loading, error, onRefresh }: { data: USMarketDashboard | null; loading: boolean; error: string; onRefresh: () => void }) {
  const trendClass = (trend: string) => trend === '偏强' ? 'positive' : trend === '承压' ? 'negative' : 'neutral'
  const changeClass = (value: number | null) => value == null ? 'neutral' : value >= 0 ? 'positive' : 'negative'
  const history = data?.qqq.history ?? []
  const [selectedNews, setSelectedNews] = useState<USMarketNewsItem | null>(null)
  return <section className="us-market">
    <div className="page-title"><div><h1>美股行业动态</h1><p>半导体 / 光模块 / 内存芯片 / 航天 / 机器人 / 美元 / 黄金 · 纳指100ETF 动态跟踪</p></div><div className="refresh-panel"><button className="secondary" onClick={onRefresh} disabled={loading}><RefreshCw size={16}/>{loading ? '抓取中...' : '刷新数据'}</button><small>数据抓取时间：{formatDateTime(data?.generated_at)}</small></div></div>
    {error && <div className="alert">{error}</div>}
    {loading && !data && <div className="empty">正在抓取美股新闻、链接页摘要与纳指100ETF行情...</div>}
    {data && <>
      <section className="us-highlights">
        {data.highlights.map(text => <strong key={text}>{text}</strong>)}
      </section>
      <div className="us-layout">
        <section className="us-modules">
          {data.modules.map(module => <article className="us-module" key={module.key}>
            <div className="us-module-head"><div><h3>{module.name}</h3><span>{module.focus}</span></div><b className={trendClass(module.trend)}>{module.trend}</b></div>
            <p className="analysis-highlight">{module.analysis}</p>
            <ul>{module.news.length ? module.news.map(item => <li key={item.url || item.title}><NewsLink item={item} onOpen={setSelectedNews} /></li>) : <li><span>暂无可用新闻，等待下一次刷新。</span></li>}</ul>
          </article>)}
        </section>
        <aside className="qqq-panel">
          <div className="qqq-head"><div><span>纳指100ETF（QQQ）</span><strong>{data.qqq.price == null ? '待获取' : data.qqq.price.toFixed(2)}</strong></div><b className={changeClass(data.qqq.change_pct)}>{data.qqq.change_pct == null ? '待获取' : `${data.qqq.change_pct.toFixed(2)}%`}</b></div>
          <p className="analysis-highlight">{data.qqq.analysis}</p>
          <QQQDailyKLine history={history} />
          <div className="qqq-news">
            <h3>纳指100ETF 新闻动态</h3>
            {data.qqq.news.map(item => <NewsLink key={item.url || item.title} item={item} onOpen={setSelectedNews} />)}
            {!data.qqq.news.length && <p>暂无可用新闻，等待下一次刷新。</p>}
          </div>
        </aside>
      </div>
    </>}
    {selectedNews && <NewsDetailModal item={selectedNews} onClose={() => setSelectedNews(null)} />}
  </section>
}

function AShareEmotion({ data, loading, error, onRefresh, onOpenHistory }: { data: AShareSentiment | null; loading: boolean; error: string; onRefresh: () => void; onOpenHistory: () => void }) {
  const maxWordCount = Math.max(1, ...(data?.hot_words.map(word => word.count) ?? [1]))
  const marketMoveClass = (value: number) => value >= 0 ? 'red' : 'green'
  return <section className="cn-market">
    <div className="page-title"><div><h1>A股市场情绪图</h1></div><div className="refresh-panel"><button className="secondary" onClick={onRefresh} disabled={loading}><RefreshCw size={16}/>{loading ? '刷新中...' : '刷新数据'}</button><small>数据抓取时间：{formatDateTime(data?.generated_at)}</small></div></div>
    {error && <div className="alert">{error}</div>}
    {loading && <div className="empty">正在读取 A股行情、热词和板块数据...</div>}
    {!loading && data && <>
      <div className="emotion-hero">
        <button className="emotion-gauge" type="button" onClick={onOpenHistory} style={{ ['--score' as string]: `${data.sentiment_score}%` }}>
          <span>市场情绪</span>
          <strong>{data.sentiment_score}</strong>
          <b>{data.sentiment_label}</b>
        </button>
        <div className="cn-stats">
          <div><span>当日平均股价</span><strong>{data.average_price.toFixed(2)}</strong></div>
          <div><span>平均涨跌幅</span><strong className={marketMoveClass(data.average_change_pct)}>{data.average_change_pct.toFixed(2)}%</strong></div>
          <div><span>上涨/下跌</span><strong><i className="red">{data.up_count}</i><small>/</small><i className="green">{data.down_count}</i></strong></div>
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
          <h3>涨幅前10板块</h3>
          <div>{data.hot_sectors.slice(0, 10).map(item => <article key={item.code}>
            <b>{item.name}</b>
            <span>{item.leading_stock || item.code}</span>
            <strong className={marketMoveClass(item.change_pct)}>{item.change_pct.toFixed(2)}%</strong>
          </article>)}</div>
        </section>
      </div>
      <section className="hot-sectors">
        <h3>热点板块</h3>
        <div>{data.hot_sectors.slice(0, 12).map((sector, index) => <article key={sector.code}>
          <b>{index + 1}</b>
          <strong>{sector.name}<small>{sector.code}</small></strong>
          <span className={marketMoveClass(sector.change_pct)}>{sector.change_pct.toFixed(2)}%</span>
          <span>成交 {cnyAmount(sector.amount)}</span>
          <span className={marketMoveClass(sector.main_inflow)}>主力 {cnyAmount(sector.main_inflow)}</span>
          <em>领涨 {sector.leading_stock || '待补充'} {sector.leading_stock_change_pct ? `${sector.leading_stock_change_pct.toFixed(2)}%` : ''}</em>
        </article>)}</div>
      </section>
    </>}
  </section>
}

export default function App() {
  const [market, setMarket] = useState<Market>('hk')
  const [hkStage, setHKStage] = useState<HKStage>('subscribing')
  const [industry, setIndustry] = useState('')
  const [tier, setTier] = useState('')
  const [selected, setSelected] = useState<LatestIPO | null>(null)
  const [generating, setGenerating] = useState(false)
  const [refreshingData, setRefreshingData] = useState(false)
  const [refreshProgress, setRefreshProgress] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [data, setData] = useState<LatestIPO[]>([])
  const [expiredData, setExpiredData] = useState<LatestIPO[]>([])
  const [ipoHistoryOpen, setIPOHistoryOpen] = useState(false)
  const [historyReferenceDate, setHistoryReferenceDate] = useState(localISODate())
  const [aShareData, setAShareData] = useState<AShareSentiment | null>(null)
  const [aShareLoading, setAShareLoading] = useState(false)
  const [aShareError, setAShareError] = useState('')
  const [usMarketData, setUSMarketData] = useState<USMarketDashboard | null>(null)
  const [usMarketLoading, setUSMarketLoading] = useState(false)
  const [usMarketError, setUSMarketError] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [historyPoints, setHistoryPoints] = useState<AShareSentimentHistoryPoint[]>([])
  const [greyMarketLoadingIds, setGreyMarketLoadingIds] = useState<number[]>([])
  const [autoGreyMarketDate, setAutoGreyMarketDate] = useState('')
  const [toastMessage, setToastMessage] = useState('')

  const patchIPO = (patch: (current: LatestIPO) => LatestIPO) => {
    setData(items => items.map(patch))
    setExpiredData(items => items.map(patch))
    setSelected(current => current ? patch(current) : current)
  }

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const reports = await api.reports()
      const reportDate = reports[0]?.report_date
      const activeParams = reportDate
        ? `?active=true&report_date=${encodeURIComponent(reportDate)}&page_size=100`
        : '?active=true&page_size=100'
      const referenceDate = reportDate ?? localISODate()
      const [listing, allListing] = await Promise.all([
        api.listIPOs(activeParams),
        api.listIPOs('?page_size=100&sort=deadline&order=desc'),
      ])
      const activeIds = new Set(listing.items.map(item => item.id))
      const expiredSummaries = allListing.items.filter(item => item.deadline < referenceDate && !activeIds.has(item.id))
      const detailIds = [...new Set([...listing.items.map(item => item.id), ...expiredSummaries.map(item => item.id)])]
      const details = await Promise.all(detailIds.map(id => api.getIPO(id)))
      const detailById = new Map(details.map(item => [item.id, toLatestIPO(item)]))
      setData(listing.items.map(item => detailById.get(item.id)).filter((item): item is LatestIPO => Boolean(item)).sort((a, b) => (b.total - a.total) || ((b.sub ?? 0) - (a.sub ?? 0))))
      setExpiredData(expiredSummaries.map(item => detailById.get(item.id)).filter((item): item is LatestIPO => Boolean(item)).sort((a, b) => b.end.localeCompare(a.end) || (b.total - a.total)))
      setHistoryReferenceDate(referenceDate)
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

  const updateGreyMarketQuote = async (item: LatestIPO, silent = false) => {
    if (greyMarketLoadingIds.includes(item.id) || item.greyMarketPrice != null) return
    setGreyMarketLoadingIds(ids => [...new Set([...ids, item.id])])
    if (!silent) setToastMessage('')
    try {
      const quote = await api.greyMarketPrice(item.id)
      const patch = (current: LatestIPO) => current.id === item.id ? {
        ...current,
        greyMarketPrice: quote.price,
        greyMarketChangePct: quote.change_pct,
        greyMarketReferencePrice: quote.reference_price,
        greyMarketReferenceLabel: quote.reference_label,
        greyMarketFetchedAt: quote.fetched_at,
        greyMarketSource: quote.source,
        greyMarketFinalized: false,
      } : current
      patchIPO(patch)
    } catch {
      if (!silent) setToastMessage('暗盘价格获取失败，请稍后再试')
    } finally {
      setGreyMarketLoadingIds(ids => ids.filter(id => id !== item.id))
    }
  }

  const saveGreyMarketQuote = async (item: LatestIPO, price: number) => {
    if (greyMarketLoadingIds.includes(item.id) || item.greyMarketFinalized) return
    setGreyMarketLoadingIds(ids => [...new Set([...ids, item.id])])
    setToastMessage('')
    try {
      const quote = await api.saveGreyMarketPrice(item.id, price)
      const patch = (current: LatestIPO) => current.id === item.id ? {
        ...current,
        greyMarketPrice: quote.price,
        greyMarketChangePct: quote.change_pct,
        greyMarketReferencePrice: quote.reference_price,
        greyMarketReferenceLabel: quote.reference_label,
        greyMarketFetchedAt: quote.fetched_at,
        greyMarketSource: quote.source,
        greyMarketFinalized: false,
      } : current
      patchIPO(patch)
    } catch (error) {
      setToastMessage(error instanceof Error ? error.message : '暗盘价格保存失败，请稍后再试')
    } finally {
      setGreyMarketLoadingIds(ids => ids.filter(id => id !== item.id))
    }
  }

  const finalizeGreyMarketQuote = async (item: LatestIPO) => {
    if (greyMarketLoadingIds.includes(item.id) || item.greyMarketPrice == null || item.greyMarketFinalized) return
    setGreyMarketLoadingIds(ids => [...new Set([...ids, item.id])])
    setToastMessage('')
    try {
      const detail = await api.finalizeGreyMarketPrice(item.id)
      const next = toLatestIPO(detail)
      patchIPO(current => current.id === item.id ? next : current)
    } catch (error) {
      setToastMessage(error instanceof Error ? error.message : '暗盘价格完成录入失败，请稍后再试')
    } finally {
      setGreyMarketLoadingIds(ids => ids.filter(id => id !== item.id))
    }
  }

  useEffect(() => {
    if (!toastMessage) return
    const timer = window.setTimeout(() => setToastMessage(''), 2600)
    return () => window.clearTimeout(timer)
  }, [toastMessage])

  useEffect(() => {
    if (market !== 'hk' || loading || !data.length) return
    const runDate = localISODate()
    const now = new Date()
    const target = new Date(now)
    target.setHours(18, 31, 0, 0)
    const fetchMissing = () => {
      if (autoGreyMarketDate === runDate) return
      setAutoGreyMarketDate(runDate)
      data.filter(item => item.greyMarketPrice == null).forEach(item => void updateGreyMarketQuote(item, true))
    }
    if (now >= target) {
      fetchMissing()
      return
    }
    const timer = window.setTimeout(fetchMissing, target.getTime() - now.getTime())
    return () => window.clearTimeout(timer)
  }, [market, loading, data, autoGreyMarketDate])

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

  const loadUSMarketData = async (refresh = false) => {
    setUSMarketLoading(true)
    setUSMarketError('')
    try {
      setUSMarketData(await api.usMarketDashboard(refresh))
    } catch (e) {
      setUSMarketError(e instanceof Error ? e.message : '美股数据加载失败')
    } finally {
      setUSMarketLoading(false)
    }
  }

  useEffect(() => {
    if (market === 'cn' && !aShareData && !aShareLoading) void loadAShareData(false)
    if (market === 'us' && !usMarketData && !usMarketLoading) void loadUSMarketData(false)
  }, [market])

  const openHistory = async () => {
    setHistoryOpen(true)
    setHistoryLoading(true)
    setHistoryError('')
    try {
      setHistoryPoints(await api.aShareSentimentHistory())
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : '历史情绪数据加载失败')
    } finally {
      setHistoryLoading(false)
    }
  }

  const openIPOHistory = async () => {
    await loadData()
    setIPOHistoryOpen(true)
  }

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

  const refreshData = async () => {
    setRefreshingData(true)
    setRefreshProgress(0)
    setError('')
    try {
      const job = await api.startDataRefresh()
      for (;;) {
        await new Promise(resolve => setTimeout(resolve, 2000))
        const status = await api.dataRefreshStatus(job.job_id)
        setRefreshProgress(status.progress_percent ?? 0)
        if (status.status === 'succeeded') {
          setRefreshProgress(100)
          window.location.reload()
          return
        }
        if (status.status === 'failed') {
          throw new Error(status.detail || '刷新数据失败')
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '刷新数据失败')
      setRefreshingData(false)
      setRefreshProgress(0)
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
      {hkStage === 'subscribing' ? <>
        <div className="hk-stage-tabs" role="tablist" aria-label="港股 IPO 阶段">
          {HK_STAGE_TABS.map(tab => <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={hkStage === tab.key}
            className={hkStage === tab.key ? 'active' : ''}
            onClick={() => setHKStage(tab.key)}
          >{tab.label}</button>)}
        </div>
        <div className="page-title"><div><h1>今日 IPO 分析</h1><p>{data.length || 0} 只真实 IPO · 透明评分 · 数据截至 {formatTimestamp(report)}</p></div><div className="title-actions"><button className={refreshingData ? 'secondary progress-button running' : 'secondary progress-button'} style={{ '--progress': `${refreshProgress}%` } as CSSProperties} onClick={refreshData} disabled={refreshingData}><RefreshCw size={16}/>{refreshingData ? `刷新中 ${refreshProgress}%` : '刷新数据'}</button><button className="primary" onClick={createReport} disabled={generating}><FileText size={18}/>{generating ? '生成中...' : '生成今日日报'}</button></div></div>
        {error && <div className="alert">{error}</div>}
        {loading && <div className="empty">正在加载最新数据...</div>}
        {!loading && !error && <>
          <Insights data={data} onOpen={setSelected} />
          <FundingConflict data={data} />
          <div className="filters"><label>行业<select value={industry} onChange={e => setIndustry(e.target.value)}><option value="">全部</option>{industries.map(value => <option key={value}>{value}</option>)}</select></label><label>推荐<select value={tier} onChange={e => setTier(e.target.value)}><option value="">全部</option><option>申购</option><option>观望</option><option>回避</option></select></label><button className="secondary" onClick={() => window.location.reload()}><RefreshCw size={16}/>重置</button><button className="secondary history-button" onClick={openIPOHistory}><Archive size={16}/>历史记录<span>{expiredData.length}</span></button></div>
          <section className="cards">{visible.map(item => <IPOCard item={item} key={item.code} onOpen={setSelected} />)}</section>
          {!visible.length && <div className="empty">没有符合条件的 IPO</div>}
        </>}
      </> : <>
        <div className="hk-stage-tabs" role="tablist" aria-label="港股 IPO 阶段">
          {HK_STAGE_TABS.map(tab => <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={hkStage === tab.key}
            className={hkStage === tab.key ? 'active' : ''}
            onClick={() => setHKStage(tab.key)}
          >{tab.label}</button>)}
        </div>
        <section className="empty filed-empty">
          <h2>已递表</h2>
          <p>暂无已递表项目数据。</p>
        </section>
      </>}
    </> : market === 'cn' ? <AShareEmotion data={aShareData} loading={aShareLoading} error={aShareError} onRefresh={() => loadAShareData(true)} onOpenHistory={openHistory} /> : <USMarketDashboardView data={usMarketData} loading={usMarketLoading} error={usMarketError} onRefresh={() => loadUSMarketData(true)} />}
    <DetailDrawer item={selected} onClose={() => setSelected(null)} />
    {ipoHistoryOpen && <IPOHistoryModal items={expiredData} referenceDate={historyReferenceDate} onOpen={(item) => {
      setSelected(item)
    }} onClose={() => setIPOHistoryOpen(false)} onSaveGreyMarket={saveGreyMarketQuote} onFinalizeGreyMarket={finalizeGreyMarketQuote} greyMarketLoadingIds={greyMarketLoadingIds} />}
    {historyOpen && <SentimentHistoryModal points={historyPoints} loading={historyLoading} error={historyError} onClose={() => setHistoryOpen(false)} />}
    {toastMessage && <div className="toast" role="status" aria-live="polite">{toastMessage}</div>}
    <footer>免责声明：数据来自本地招股书及结构化资料，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。</footer>
  </main>
}
