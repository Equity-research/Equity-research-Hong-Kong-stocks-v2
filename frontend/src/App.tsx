import { useCallback, useEffect, useMemo, useState } from 'react'
import { BarChart3, BookOpen, CalendarDays, ChevronDown, Download, FileText, Menu, RefreshCw, Save, SlidersHorizontal, X } from 'lucide-react'
import { api } from './api'
import type { IPODetail, IPO, Report, ReportInsights } from './types'

type Page = 'today' | 'ipos' | 'reports' | 'rules'

function RecommendationBadge({ value }: { value: IPO['recommendation'] }) {
  return <span className={`recommendation ${value === '申购' ? 'buy' : value === '观望' ? 'hold' : 'avoid'}`}>{value}</span>
}

function Header({ page, onPage }: { page: Page; onPage: (p: Page) => void }) {
  const [open, setOpen] = useState(false)
  const items: [Page, string][] = [['today', '今日分析'], ['ipos', 'IPO项目'], ['reports', '历史日报'], ['rules', '评分规则']]
  return <header className="topbar">
    <button className="brand" onClick={() => onPage('today')}>港股IPO分析</button>
    <button className="menu-button" aria-label="打开导航" onClick={() => setOpen(v => !v)}><Menu size={21} /></button>
    <nav className={open ? 'nav open' : 'nav'}>{items.map(([key, label]) =>
      <button key={key} className={page === key ? 'active' : ''} onClick={() => { onPage(key); setOpen(false) }}>{label}</button>)}</nav>
    <div className="source"><span className="status-dot" />数据源：本地文件 · 2026-07-02</div>
  </header>
}

function ReportInsightsPanel({ insights }: { insights: ReportInsights }) {
  const hasRanking = insights.fundamental_valuation_ranking.length > 0
  const hasDifficulty = insights.allotment_difficulty.length > 0
  return <div className="mobile-report-insights">
    <section><h3>1）按“基本面和估值”来看</h3>{hasRanking
      ? <p className="valuation-ranking">{insights.fundamental_valuation_ranking.map(group => group.join(' = ')).join(' > ')}</p>
      : <p className="insights-empty">待补充</p>}</section>
    <section><h3>2）中签难度初判</h3>{hasDifficulty
      ? <dl>{insights.allotment_difficulty.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.companies.join(' + ')}{item.note ? <small>{item.note}</small> : null}</dd></div>)}</dl>
      : <p className="insights-empty">待补充</p>}</section>
  </div>
}

function Summary({ items, insights }: { items: IPO[]; insights: ReportInsights }) {
  const avg = items.length ? items.reduce((sum, item) => sum + item.final_score, 0) / items.length : 0
  const values = [['今日项目数', items.length, ''], ['建议申购', items.filter(i => i.recommendation === '申购').length, 'green'],
    ['建议观望', items.filter(i => i.recommendation === '观望').length, 'amber'], ['建议回避', items.filter(i => i.recommendation === '回避').length, 'red'],
    ['平均最终分', avg.toFixed(1), '']]
  return <section className="summary" aria-label="今日汇总">{values.map(([label, value, color]) =>
    <div className={`summary-item ${label === '平均最终分' ? 'average-score' : ''}`} key={label}><span>{label}</span><strong className={String(color)}>{value}</strong></div>)}
    <ReportInsightsPanel insights={insights}/>
  </section>
}

function FilterBar({ industry, recommendation, onIndustry, onRecommendation, onReset, industries }:
  { industry: string; recommendation: string; onIndustry: (v:string)=>void; onRecommendation:(v:string)=>void; onReset:()=>void; industries:string[] }) {
  return <div className="filters">
    <label>行业<select value={industry} onChange={e => onIndustry(e.target.value)}><option value="">全部</option>{industries.map(v => <option key={v}>{v}</option>)}</select></label>
    <label>推荐<select value={recommendation} onChange={e => onRecommendation(e.target.value)}><option value="">全部</option><option>申购</option><option>观望</option><option>回避</option></select></label>
    <button className="secondary" onClick={onReset}><RefreshCw size={16}/>重置</button>
  </div>
}

function IPOTable({ items, selected, onSelect }: { items: IPO[]; selected?: number; onSelect:(id:number)=>void }) {
  if (!items.length) return <div className="empty"><BarChart3 size={38}/><h3>没有符合条件的 IPO</h3><p>请调整筛选条件后重试。</p></div>
  return <div className="table-wrap"><table><thead><tr><th>公司</th><th>代码</th><th>行业</th><th>招股价</th><th>最小申购金额</th><th>市场申购倍数</th><th>截止日期</th><th>原始分</th><th>调整</th><th>最终分</th><th>建议</th></tr></thead>
    <tbody>{items.map(item => <tr key={item.id} className={selected === item.id ? 'selected' : ''} onClick={() => onSelect(item.id)}>
      <td><span className="radio"/><strong>{item.name}</strong><small>{item.english_name}</small><div className="mobile-ipo-metrics">
        <span><b>招股价</b>{item.price_low.toFixed(2)}–{item.price_high.toFixed(2)} HKD</span>
        <span><b>最小申购金额</b>{item.minimum_subscription_amount == null ? '待补充' : `${item.minimum_subscription_amount.toLocaleString('zh-HK')} HKD`}</span>
        <span><b>市场申购倍数</b>{item.subscription_multiple == null ? '待补充' : `${item.subscription_multiple.toFixed(2)} 倍`}</span>
      </div></td><td>{item.code}</td><td>{item.industry}</td>
      <td>{item.price_low.toFixed(2)}–{item.price_high.toFixed(2)}<small>HKD</small></td>
      <td>{item.minimum_subscription_amount == null ? '待补充' : `${item.minimum_subscription_amount.toLocaleString('zh-HK')} HKD`}</td>
      <td>{item.subscription_multiple == null ? '待补充' : `${item.subscription_multiple.toFixed(2)} 倍`}</td>
      <td>{item.deadline}</td><td>{item.original_score.toFixed(1)}</td>
      <td className={item.adjustment > 0 ? 'green' : item.adjustment < 0 ? 'red' : ''}>{item.adjustment > 0 ? '+' : ''}{item.adjustment}</td>
      <td><strong>{item.final_score.toFixed(1)}</strong></td><td><RecommendationBadge value={item.recommendation}/></td>
    </tr>)}</tbody></table></div>
}

function IssuanceProfile({ detail }: { detail: IPODetail }) {
  const issuanceShares = detail.issuance_shares == null ? '待补充' : `${detail.issuance_shares.toLocaleString('zh-HK')} 股`
  const lotSize = detail.lot_size == null ? '待补充' : `${detail.lot_size.toLocaleString('zh-HK')} 股`
  const greenshoe = detail.greenshoe == null ? '待补充' : detail.greenshoe ? '有' : '无'
  const cornerstoneInvestors = detail.cornerstone_investors?.length ? detail.cornerstone_investors.join('、') : '待补充'
  const cornerstoneRatio = detail.cornerstone_ratio == null ? '待补充' : `${detail.cornerstone_ratio.toFixed(2)}%`
  const sponsors = detail.sponsors?.length ? detail.sponsors.join('、') : '待补充'
  const fields = [['发行数量', issuanceShares], ['每手股数', lotSize], ['绿鞋', greenshoe],
    ['基石投资者', cornerstoneInvestors], ['基石占比', cornerstoneRatio], ['保荐人', sponsors]]
  return <>
    <section className="issuance-profile"><h3>发行资料</h3><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
    <section className="company-quality"><h3>公司质地</h3>{detail.company_quality?.length
      ? <ol>{detail.company_quality.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ol>
      : <p>待补充</p>}</section>
  </>
}

function DetailPanel({ detail, onClose, onSaved }: { detail: IPODetail | null; onClose:()=>void; onSaved:()=>void }) {
  const [value, setValue] = useState(0); const [reason, setReason] = useState(''); const [message, setMessage] = useState(''); const [saving, setSaving] = useState(false)
  useEffect(() => { if (detail) { setValue(detail.adjustment); setReason(''); setMessage('') } }, [detail?.id])
  if (!detail) return null
  const save = async () => {
    if (reason.trim().length < 10) { setMessage('调整原因至少需要 10 个字符'); return }
    setSaving(true); setMessage('')
    try { await api.adjust(detail.id, value, reason); setMessage('调整已保存'); onSaved() } catch (e) { setMessage(e instanceof Error ? e.message : '保存失败') } finally { setSaving(false) }
  }
  return <aside className="detail-panel" aria-label="IPO详情">
    <div className="detail-head"><div><h2>{detail.name}</h2><span>{detail.code}</span><RecommendationBadge value={detail.recommendation}/></div><button aria-label="关闭详情" onClick={onClose}><X/></button></div>
    <p className="meta">招股价　{detail.price_low.toFixed(2)}–{detail.price_high.toFixed(2)} HKD　　截止 {detail.deadline}</p>
    <IssuanceProfile detail={detail}/>
    <section><h3>风险提示</h3><ul className="risks">{detail.risks.map(r => <li key={r}>{r}</li>)}</ul></section>
    <section className="adjust"><h3>手动调整 <small>（−1 至 +1）</small></h3><div className="range-row"><span>−1</span><input aria-label="手动调整" type="range" min="-1" max="1" step="1" value={value} onChange={e => setValue(Number(e.target.value))}/><span>+1</span><output>{value > 0 ? '+' : ''}{value}</output></div>
      <label>调整原因（必填）<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={200} placeholder="请填写调整原因，至少 10 个字符"/><small>{reason.length} / 200</small></label>
      <div className="save-row"><button className="primary" disabled={saving} onClick={save}><Save size={17}/>{saving ? '保存中…' : '保存调整'}</button><span className={message.includes('已保存') ? 'success' : 'error'}>{message}</span></div>
    </section>
  </aside>
}

function TodayPage({ onReports }: { onReports:()=>void }) {
  const [items, setItems] = useState<IPO[]>([]); const [detail, setDetail] = useState<IPODetail | null>(null); const [selected, setSelected] = useState<number>();
  const [insights, setInsights] = useState<ReportInsights>({ fundamental_valuation_ranking: [], allotment_difficulty: [] })
  const [industry, setIndustry] = useState(''); const [recommendation, setRecommendation] = useState(''); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [generating, setGenerating] = useState(false)
  const load = useCallback(async () => { setLoading(true); setError(''); try { const data = await api.listIPOs(); setItems(data.items); setInsights(data.insights ?? { fundamental_valuation_ranking: [], allotment_difficulty: [] }); if (!selected && data.items.length && window.matchMedia('(min-width: 1101px)').matches) { setSelected(data.items[0].id); setDetail(await api.getIPO(data.items[0].id)) } } catch (e) { setError(e instanceof Error ? e.message : '加载失败') } finally { setLoading(false) } }, [selected])
  useEffect(() => { void load() }, [])
  const openDetail = async (id:number) => { setSelected(id); try { setDetail(await api.getIPO(id)) } catch { setError('无法加载 IPO 详情') } }
  const visible = useMemo(() => items.filter(i => (!industry || i.industry === industry) && (!recommendation || i.recommendation === recommendation)), [items, industry, recommendation])
  const createReport = async () => { setGenerating(true); try { const report = await api.createReport(); window.open(api.downloadUrl(report.id, 'pdf'), '_blank'); onReports() } catch (e) { setError(e instanceof Error ? e.message : '日报生成失败') } finally { setGenerating(false) } }
  return <main className="dashboard"><div className="workspace"><div className="content">
    <div className="page-title"><div><h1>今日 IPO 分析</h1><p>16 只真实 IPO · 透明评分 · 数据截至 2026-07-02 10:34 CST</p></div><button className="primary" onClick={createReport} disabled={generating}><FileText size={18}/>{generating ? '生成中…' : '生成今日日报'}</button></div>
    {error && <div className="alert">{error}<button onClick={() => load()}>重试</button></div>}
    {loading ? <div className="loading">正在加载 IPO 数据…</div> : <><Summary items={items} insights={insights}/><FilterBar industry={industry} recommendation={recommendation} onIndustry={setIndustry} onRecommendation={setRecommendation} onReset={() => {setIndustry('');setRecommendation('')}} industries={[...new Set(items.map(i=>i.industry))]}/><IPOTable items={visible} selected={selected} onSelect={openDetail}/><p className="count">共 {visible.length} 条 · 缺失字段统一显示“待补充”</p></>}
  </div><DetailPanel detail={detail} onClose={() => setDetail(null)} onSaved={async () => { await load(); if (selected) setDetail(await api.getIPO(selected)) }}/></div></main>
}

function IPOPage() {
  const [items, setItems] = useState<IPO[]>([]); const [detail, setDetail] = useState<IPODetail|null>(null)
  useEffect(() => { api.listIPOs('?page_size=100').then(r => setItems(r.items)) }, [])
  return <main className="simple-page"><div className="section-title"><SlidersHorizontal/><div><h1>IPO 项目</h1><p>查看当日全部项目及其评分结果</p></div></div><IPOTable items={items} selected={detail?.id} onSelect={id => api.getIPO(id).then(setDetail)}/><DetailPanel detail={detail} onClose={()=>setDetail(null)} onSaved={()=> detail && api.getIPO(detail.id).then(setDetail)}/></main>
}

function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]); const [loading, setLoading] = useState(true)
  const load = () => api.reports().then(setReports).finally(()=>setLoading(false)); useEffect(() => { void load() }, [])
  const create = async () => { await api.createReport(); await load() }
  return <main className="simple-page"><div className="page-title"><div className="section-title"><CalendarDays/><div><h1>历史日报</h1><p>同一日期重复生成会保留新版本</p></div></div><button className="primary" onClick={create}><FileText size={17}/>生成今日日报</button></div>
    {loading ? <div className="loading">正在读取日报…</div> : reports.length ? <div className="report-list">{reports.map(r => <article key={r.id}><div><strong>{r.report_date}</strong><span>版本 {r.version}</span><small>{r.item_count} 个项目 · 申购 {r.buy_count} · 观望 {r.hold_count} · 回避 {r.avoid_count}</small></div><div><a href={api.downloadUrl(r.id,'md')}><Download size={16}/>Markdown</a><a href={api.downloadUrl(r.id,'pdf')}><Download size={16}/>PDF</a></div></article>)}</div> : <div className="empty"><FileText/><h3>还没有历史日报</h3><p>生成第一份日报后会显示在这里。</p></div>}
  </main>
}

function RulesPage() {
  const dimensions = [['基石投资者',1,'有基石投资者得 1 分'],['基石质量',1,'主权基金、头部长线基金或产业龙头等优质基石得 1 分'],['绿鞋机制',1,'设有绿鞋机制得 1 分'],['公开申购倍数',3,'＜10 倍 0 分；10–＜50 倍 1 分；50–＜100 倍 2 分；≥100 倍 3 分'],['估值吸引力',3,'A+H 按 A/H 溢价评分；其他公司按相对同业估值折价评分'],['保荐人表现',1,'头部保荐人且近期项目表现稳定得 1 分']]
  return <main className="simple-page"><div className="section-title"><BookOpen/><div><h1>评分规则</h1><p>10 分制 · 所有权重与阈值均来自 scoring_rules.yaml</p></div></div><div className="rules-grid">{dimensions.map(([name,weight,desc]) => <article key={String(name)}><strong>{name}</strong><b>{weight} 分</b><p>{desc}</p></article>)}</div><section className="method"><h2>计算与推荐</h2><p>A+H 溢价≤30%计 0 分，＞30%至50%计 1 分，＞50%至70%计 2 分，＞70%计 3 分。非 A+H 公司相对同业溢价计 0 分、接近同业计 1 分、折价10%至30%计 2 分、折价超过30%计 3 分。缺失数据计 0 分。</p><div className="thresholds"><span className="buy">8–10　申购</span><span className="hold">4–7.99　观望</span><span className="avoid">0–3.99　回避</span></div><p>人工调整限制为 −1 至 +1，必须填写至少 10 个字符的原因；原始规则分始终保留。</p></section></main>
}

export default function App() {
  const [page, setPage] = useState<Page>('today')
  return <><Header page={page} onPage={setPage}/>{page === 'today' && <TodayPage onReports={()=>setPage('reports')}/>} {page === 'ipos' && <IPOPage/>}{page === 'reports' && <ReportsPage/>}{page === 'rules' && <RulesPage/>}<footer>免责声明：数据来自本地招股书及结构化资料，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。</footer></>
}
