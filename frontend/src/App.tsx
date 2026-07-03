import { useMemo, useState } from 'react'
import { FileText, RefreshCw, X } from 'lucide-react'
import { api } from './api'

type Tier = '申购' | '观望' | '回避'

interface LatestIPO {
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

const DATA_TIMESTAMP = '2026-07-03 12:19 CST'
const SCORE_LABELS = ['基石投资者', '基石质量', '绿鞋机制', '公开申购倍数', '估值吸引力', '保荐人']
const SCORE_WEIGHTS = [1, 1, 1, 3, 3, 1]
const PRIORITY_CODES = ['06951', '00537', '01377', '06745', '02249', '03752', '02797', '02475', '02523']

const DATA: LatestIPO[] = [
  { code: '00537', name: '普源精电', industry: '电子测量仪器', price: '45.98', end: '2026-07-06', minimum: 4644.37, sub: 20.25, issuanceShares: 24802200, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['HHLR', 'CPE Hemlock', '苏州高新区', '华圆', '阳光电源香港', '中信保诚基金', '彭年集团'], cornerstoneRatio: 42.11, sponsors: ['中信证券'], scores: [1, 1, 1, 1, 3, 1], total: 8, tier: '申购', summary: '规则8分；评分达到申购区间，但仍需控制单票仓位。', isAh: true, ahPremium: 75.8, aTicker: '688337.SS', aClose: 69.91, cnyHkd: 1.156, quality: ['2025年收入约9.00亿元。', '2025年净利润约0.86亿元。', '2025年毛利率约52.84%。', '基石配售占全球发售约42.11%。'], risks: ['认购热度处于中下游。', 'A/H 溢价较高，上市后需留意溢价回归压力。'] },
  { code: '06951', name: '三环集团', industry: '电子陶瓷', price: '100.30', end: '2026-07-06', minimum: 10131.15, sub: 37.36, issuanceShares: 71364300, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['淡马锡', '摩根大通', '阿里巴巴关联主体', '腾讯关联主体', '高盛资产', '宏利', '泰康人寿'], cornerstoneRatio: 49.81, sponsors: ['中国银河国际'], scores: [1, 1, 1, 1, 3, 1], total: 8, tier: '申购', summary: '规则8分；评分达到申购区间，但仍需控制单票仓位。', isAh: true, ahPremium: 75, aTicker: '300408.SZ', aClose: 151.83, cnyHkd: 1.156, quality: ['电子陶瓷细分行业龙头。', '引入17家基石投资者。', '基石阵容包含主权、长线及产业资本。'], risks: ['发行后市值和融资规模较大。', 'A/H 溢价较高，上市后需留意溢价回归压力。'] },
  { code: '01377', name: '鼎泰高科', industry: '刀具及功能性材料', price: '380.00', end: '2026-07-06', minimum: 38383.24, sub: 32.77, issuanceShares: 12632000, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['泰康人寿', 'ATHOS CAPITAL', 'HELVED MASTER FUND', 'Millennium', 'IFUND SPC', '霸菱资产', 'Martis Fund', '定颖投资'], cornerstoneRatio: 41.45, sponsors: ['中信证券', '汇丰'], scores: [1, 1, 1, 1, 2, 1], total: 7, tier: '观望', summary: '规则7分；仍可申购，认购热度32.77倍，建议结合估值和中签率谨慎观察。', isAh: true, ahPremium: 62, aTicker: '301377.SZ', aClose: 532.56, cnyHkd: 1.156, quality: ['2025年收入约20.84亿元，同比增长34.2%。', '2025年净利润约4.32亿元。', '2025年PCB钻针全球市场份额约29.2%。', '基石配售占全球发售约41.45%。'], risks: ['最高发行价较高。', '受 PCB 周期影响，A/H 溢价需持续跟踪。'] },
  { code: '02249', name: '晶合集成', industry: '晶圆代工', price: '30.00–32.30', end: '2026-07-07', minimum: 3262.57, sub: 2.09, issuanceShares: 216167000, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['合肥建投', '国资及产业资本', '长线基金'], cornerstoneRatio: 49.92, sponsors: ['中金公司', '中信证券'], scores: [1, 1, 1, 0, 3, 1], total: 7, tier: '观望', summary: '规则7分；仍可申购，认购热度2.09倍，建议结合估值和中签率谨慎观察。', isAh: true, ahPremium: 129.1, aTicker: '688249.SS', aClose: 64, cnyHkd: 1.156, quality: ['晶圆代工具备产业战略价值。', '重资产模式应结合PB和PS观察。', '发行后市值约667.13至718.27亿港元。', '基石配售占全球发售约49.92%。'], risks: ['认购倍数较低。', '晶圆代工周期性强，A/H 溢价需结合 PB/PS 继续跟踪。'] },
  { code: '06745', name: '滨化股份', industry: '基础化工', price: '3.59', end: '2026-07-07', minimum: 3626.21, sub: 3.39, issuanceShares: 352126000, lotSize: 1000, greenshoe: true, cornerstoneInvestors: ['北京益安', '鲁花道生', 'Aurora SF', '中国宏桥', 'Hyperion Venture', '天图', '盛威'], cornerstoneRatio: 30.91, sponsors: ['华泰国际', '建银国际'], scores: [1, 1, 1, 0, 3, 1], total: 7, tier: '观望', summary: '规则7分；仍可申购，认购热度3.39倍，建议结合估值和中签率谨慎观察。', isAh: true, ahPremium: 124.1, aTicker: '601678.SS', aClose: 6.96, cnyHkd: 1.156, quality: ['2025年收入约148.36亿元。', '2025年净利润约2.35亿元。', '发行价格较低、业务规模成熟。', '基石配售占全球发售约30.91%。'], risks: ['基础化工周期性明显。', '毛利率约9.81%、认购热度较低，A/H 溢价需持续跟踪。'] },
  { code: '03752', name: '珞石机器人', industry: '工业及协作机器人', price: '38.00', end: '2026-07-06', minimum: 3838.32, sub: 23.19, issuanceShares: 23031900, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['广发基金', '华泰资本', '金融街资本', 'Yishao Capital', 'All View Fund'], cornerstoneRatio: 31.4, sponsors: ['中金公司', '国泰海通'], scores: [1, 1, 1, 1, 0, 1], total: 5, tier: '观望', summary: '规则5分；仍可申购，认购热度23.19倍，建议结合估值和中签率谨慎观察。', isAh: false, ahPremium: null, aTicker: null, aClose: null, cnyHkd: null, quality: ['2025年收入约5.22亿元。', '2025年毛利率约21.89%。', '海外收入占比约8.9%。'], risks: ['2025年净亏损约1.79亿元。', '发行PS约17.5倍，高于多数可比口径。'] },
  { code: '02797', name: '齐云山食品', industry: '食品饮料', price: '5.00–8.00', end: '2026-07-06', minimum: 4040.34, sub: 44.08, issuanceShares: 25000000, lotSize: 500, greenshoe: true, cornerstoneInvestors: [], cornerstoneRatio: null, sponsors: ['中泰国际'], scores: [0, 0, 1, 1, 2, 0], total: 4, tier: '观望', summary: '规则4分；仍可申购，认购热度44.08倍，建议结合估值和中签率谨慎观察。', isAh: false, ahPremium: null, aTicker: null, aClose: null, cnyHkd: null, quality: ['2025年收入约3.14亿元。', '2025年净利润约0.49亿元。', '2025年毛利率约51.32%。'], risks: ['公司规模较小。', '同业估值证据有限且上市后流动性可能不足。'] },
  { code: '02475', name: '立讯精密', industry: '消费电子制造', price: '63.28', end: '2026-07-06', minimum: 6391.82, sub: 1.39, issuanceShares: 383472800, lotSize: 100, greenshoe: true, cornerstoneInvestors: ['淡马锡', 'HHLRA', 'GIC', 'CPE Neem', '景林资产', '睿远基金', 'ADIA', 'UBS', 'Oaktree', '腾讯', '富达', '泰康人寿', '嘉实国际'], cornerstoneRatio: 48.44, sponsors: ['中信证券', '高盛', '中金公司', '汇丰'], scores: [1, 1, 1, 0, 0, 1], total: 4, tier: '观望', summary: '规则4分；仍可申购，认购热度1.39倍，建议结合估值和中签率谨慎观察。', isAh: true, ahPremium: 19.2, aTicker: '002475.SZ', aClose: 65.23, cnyHkd: 1.156, quality: ['2025年收入约3323.44亿元。', '2025年净利润约181.70亿元。', '同批公司中业务规模和成熟度领先。', '基石配售约15亿美元，占全球发售约48.44%。'], risks: ['公开认购尚未足额。', '大体量融资承接、客户集中和全球供应链风险。'] },
  { code: '02523', name: '永康控股', industry: '货运物流', price: '2.20–2.68', end: '2026-07-08', minimum: 5414.05, sub: 10.99, issuanceShares: 51600000, lotSize: 2000, greenshoe: true, cornerstoneInvestors: [], cornerstoneRatio: null, sponsors: ['富强企业融资', '华富建业企业融资'], scores: [0, 0, 1, 1, 0, 0], total: 2, tier: '回避', summary: '规则2分；当前规则分偏低，暂不纳入优先申购。', isAh: false, ahPremium: null, aTicker: null, aClose: null, cnyHkd: null, quality: ['新加坡集装箱堆场运营商。', '2025年收入约1.49亿新加坡元。', '2025年净利润约0.13亿新加坡元。'], risks: ['成长性与业务稀缺性有限。', '小市值发行存在流动性风险。'] },
]

const money = (value: number | null) => value == null ? '待补充' : `HK$${Math.round(value).toLocaleString('zh-HK')}`
const numberText = (value: number | null, suffix = '') => value == null ? '待补充' : `${value.toLocaleString('zh-HK')}${suffix}`
const tierClass = (tier: Tier) => tier === '申购' ? 'buy' : tier === '观望' ? 'hold' : 'avoid'
const shortDate = (date: string) => date.slice(5)
const priorityIndex = (item: LatestIPO) => {
  const index = PRIORITY_CODES.indexOf(item.code)
  return index === -1 ? Number.MAX_SAFE_INTEGER : index
}
const priorityData = [...DATA].sort((a, b) => priorityIndex(a) - priorityIndex(b))
const names = (items: LatestIPO[]) => items.map(item => item.name).join(' > ')
const decisionReasons = [
  {
    name: '三环集团',
    codes: ['06951'],
    tier: '申购',
    points: ['电子陶瓷材料和元器件龙头，基本面扎实。', '2025年收入约89亿元、净利约26亿元，2026Q1继续高增。', '基石阵容很强：淡马锡、JPM、CPE、腾讯、阿里、GSAM、泰康、工银、TCL。', '保荐人中国银河上一单赛力斯表现一般，是扣分项。', '当前A/H溢价约75.0%，估值不便宜但结合稀缺性仍可接受，需控制仓位。'],
  },
  {
    name: '普源精电',
    codes: ['00537'],
    tier: '申购',
    points: ['电子测量仪器赛道稀缺，毛利率较高，2025年收入和利润仍有增长。', '基石占比约42%，HHLR、CPE、阳光电源等组合质量不错。', '当前A/H溢价约75.8%，估值不便宜但结合稀缺性仍可接受，适合申购但不宜重仓。'],
  },
  {
    name: '鼎泰高科',
    codes: ['01377'],
    tier: '观望',
    points: ['PCB钻针份额领先，收入增速和盈利质量不错。', '价格绝对值和最低一手金额都高，资金占用最大。', 'A/H溢价约62.0%，仍需结合PCB周期和上市初期承接观察。'],
  },
  {
    name: '滨化股份 / 晶合集成',
    codes: ['06745', '02249'],
    tier: '观望',
    points: ['两只都有基石支撑，但公开认购偏冷，滨化A/H溢价约124.1%、晶合集成约129.1%。', '滨化受化工周期影响，晶合集成重资产属性强，估值要结合周期位置看。', '更适合作为低热度博弈票，而不是优先申购票。'],
  },
  {
    name: '珞石机器人 / 齐云山食品 / 立讯精密',
    codes: ['03752', '02797', '02475'],
    tier: '观望',
    points: ['珞石和齐云山认购热度不低，但盈利、规模或估值证据不够扎实。', '立讯基本面强，但融资体量大且公开认购偏冷，中签容易不等于上市表现好。', '这组更适合等暗盘和资金热度确认。'],
  },
  {
    name: '永康控股',
    codes: ['02523'],
    tier: '回避',
    points: ['规则分最低，业务稀缺性和成长性证据不足。', '小市值物流资产上市后流动性不确定，暂不纳入优先申购。'],
  },
]

function Insights({ onOpen }: { onOpen: (item: LatestIPO) => void }) {
  return <section className="summary-card">
    <div className="stats">
      <div><span>今日项目数</span><strong>{DATA.length}</strong></div>
      <div><span>建议申购</span><strong className="green">{DATA.filter(x => x.tier === '申购').length}</strong></div>
      <div><span>建议观望</span><strong className="amber">{DATA.filter(x => x.tier === '观望').length}</strong></div>
      <div><span>建议回避</span><strong className="red">{DATA.filter(x => x.tier === '回避').length}</strong></div>
    </div>
    <div className="insights">
      <section className="decision-reasons"><h3>1）申购/不申购原因</h3><div className="reason-list">
        {decisionReasons.map(item => <article key={item.name}>
          <b>{item.codes.map((code, index) => {
            const ipo = DATA.find(dataItem => dataItem.code === code)
            return ipo ? <span className="reason-name" key={code}>{index > 0 && <span className="reason-separator">/</span>}<button className="reason-link" type="button" onClick={() => onOpen(ipo)}>{ipo.name}</button></span> : null
          })}<span className={tierClass(item.tier as Tier)}>{item.tier}</span></b>
          <ul>{item.points.map(point => <li key={point}>{point}</li>)}</ul>
        </article>)}
      </div></section>
      <section><h3>2）按优先级排序</h3><p>{names(priorityData)}</p></section>
      <section><h3>3）中签难度初判</h3><dl><div><dt>中等</dt><dd>三环集团 + 普源精电 + 鼎泰高科 + 珞石机器人 + 齐云山食品<small>10至50倍认购</small></dd></div><div><dt>较易</dt><dd>滨化股份 + 晶合集成 + 立讯精密<small>低于10倍认购；仍不代表一定获配</small></dd></div></dl></section>
    </div>
  </section>
}

function FundingConflict() {
  const investable = DATA.filter(item => item.tier !== '回避')
  const groups = [...new Map(investable.map(item => [item.end, investable.filter(x => x.end === item.end)]))]
  const pressure = groups.map(([date, items]) => ({
      date,
      items,
      total: items.reduce((sum, item) => sum + (item.minimum ?? 0), 0),
  })).sort((a, b) => b.total - a.total)
  const highest = pressure[0]
  return <section className="funding-card">
    <div>
      <h3>4）资金冲突情况</h3>
      <p>压力最高 <strong>{shortDate(highest.date)}</strong></p>
      <p>{highest.items.length} 只，最低一手约 {money(highest.total)}</p>
      <p>申购/观望票最低一手合计约 {money(highest.total)}，同日截止需预留现金。</p>
    </div>
    <div className="funding-days">{pressure.map(group => <article key={group.date}>
      <b>{shortDate(group.date)}</b>
      <strong>{[...group.items].sort((a, b) => priorityIndex(a) - priorityIndex(b)).map(item => item.name).join(' + ')}</strong>
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

export default function App() {
  const [industry, setIndustry] = useState('')
  const [tier, setTier] = useState('')
  const [selected, setSelected] = useState<LatestIPO | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const industries = useMemo(() => [...new Set(DATA.map(item => item.industry))].sort(), [])
  const visible = priorityData.filter(item => (!industry || item.industry === industry) && (!tier || item.tier === tier))
  const createReport = async () => {
    setGenerating(true)
    setError('')
    try {
      const report = await api.createReport()
      window.open(api.downloadUrl(report.id, 'pdf'), '_blank')
    } catch (e) {
      setError(e instanceof Error ? e.message : '日报生成失败')
    } finally {
      setGenerating(false)
    }
  }
  return <main className="page">
    <div className="page-title"><div><h1>今日 IPO 分析</h1><p>9 只真实 IPO · 透明评分 · 数据截至 {DATA_TIMESTAMP}</p></div><button className="primary" onClick={createReport} disabled={generating}><FileText size={18}/>{generating ? '生成中...' : '生成今日日报'}</button></div>
    {error && <div className="alert">{error}</div>}
    <Insights onOpen={setSelected} />
    <FundingConflict />
    <div className="filters"><label>行业<select value={industry} onChange={e => setIndustry(e.target.value)}><option value="">全部</option>{industries.map(value => <option key={value}>{value}</option>)}</select></label><label>推荐<select value={tier} onChange={e => setTier(e.target.value)}><option value="">全部</option><option>申购</option><option>观望</option><option>回避</option></select></label><button className="secondary" onClick={() => { setIndustry(''); setTier('') }}><RefreshCw size={16}/>重置</button></div>
    <section className="cards">{visible.map(item => <IPOCard item={item} key={item.code} onOpen={setSelected} />)}</section>
    {!visible.length && <div className="empty">没有符合条件的 IPO</div>}
    <DetailDrawer item={selected} onClose={() => setSelected(null)} />
    <footer>免责声明：数据来自本地招股书及结构化资料，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。</footer>
  </main>
}
