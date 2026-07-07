export type Recommendation = '申购' | '观望' | '回避'
export interface DimensionScore { key: string; label: string; score: number; weight: number; reasons: string[]; missing: string[] }
export interface Adjustment { id: number; value: number; reason: string; operator: string; created_at: string; original_score: number; final_score: number }
export interface IPO {
  id: number; name: string; english_name: string; code: string; industry: string; price_low: number; price_high: number;
  minimum_subscription_amount: number | null; subscription_multiple: number | null;
  deadline: string; is_sample: boolean; original_score: number; adjustment: number; final_score: number; recommendation: Recommendation
}
export interface IPODetail extends IPO {
  dimensions: DimensionScore[]; risks: string[]; metrics: Record<string, string | number | boolean | null>; adjustments: Adjustment[];
  issuance_shares: number | null; lot_size: number | null; greenshoe: boolean | null;
  cornerstone_investors: string[]; cornerstone_ratio: number | null; sponsors: string[]; company_quality: string[]
}
export interface GreyMarketQuote {
  ipo_id: number
  code: string
  price: number
  change_pct: number | null
  reference_price: number | null
  reference_label: string | null
  fetched_at: string
  source: string
}
export interface AllotmentDifficulty { label: string; companies: string[]; note: string | null }
export interface ReportInsights { fundamental_valuation_ranking: string[][]; allotment_difficulty: AllotmentDifficulty[] }
export interface IPOList { items: IPO[]; total: number; page: number; page_size: number; insights: ReportInsights }
export interface Report { id: number; report_date: string; version: number; created_at: string; item_count: number; buy_count: number; hold_count: number; avoid_count: number; markdown?: string }
export interface DataRefreshStart { job_id: string; status: string }
export interface DataRefreshStatus {
  job_id: string
  status: 'running' | 'succeeded' | 'failed'
  started_at: string
  finished_at: string | null
  report_date: string
  detail: string | null
  progress_current: number
  progress_total: number
  progress_percent: number
  progress_label: string | null
}
export interface AShareHotWord { word: string; count: number; sentiment: 'positive' | 'neutral' | 'negative'; weight: number }
export interface AShareMarketSample { code: string; name: string; price: number; change_pct: number; change: number; volume: number; amount: number }
export interface AShareHotSector {
  code: string
  name: string
  price: number
  change_pct: number
  turnover_rate: number
  amount: number
  main_inflow: number
  leading_stock: string
  leading_stock_code: string
  leading_stock_change_pct: number
}
export interface AShareSentiment {
  record_date: string
  generated_at: string
  average_price: number
  average_change_pct: number
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
  sentiment_score: number
  sentiment_label: string
  market_source: string
  hot_word_sources: string[]
  sector_source: string
  market_file: string
  hot_words_file: string
  hot_sectors_file: string
  hot_words: AShareHotWord[]
  hot_sectors: AShareHotSector[]
  market_sample: AShareMarketSample[]
}
export interface AShareSentimentHistoryPoint {
  record_date: string
  generated_at: string
  sentiment_score: number
  sentiment_label: string
  average_price: number
  average_change_pct: number
  stock_count: number
  up_count: number
  down_count: number
  flat_count: number
}
export interface USMarketNewsItem {
  title: string
  source: string
  url: string
  published_at: string | null
  title_zh?: string | null
  source_zh?: string | null
  article_title_zh?: string | null
  article_summary_zh?: string | null
  article_body_zh?: string | null
  article_key_points_zh?: string[] | null
  original_url?: string | null
  original_title?: string | null
  original_body?: string | null
  original_saved_at?: string | null
}
export interface USMarketModule {
  key: string
  name: string
  focus: string
  sentiment_score: number
  trend: string
  analysis: string
  news: USMarketNewsItem[]
}
export interface QQQHistoryPoint {
  date: string | null
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  change_pct: number | null
}
export interface USMarketQQQ {
  symbol: string
  price: number | null
  change: number | null
  change_pct: number | null
  quote_time: string | null
  trend: string
  analysis: string
  history: QQQHistoryPoint[]
  news: USMarketNewsItem[]
}
export interface USMarketDashboard {
  record_date: string
  generated_at: string
  source: string
  cache_file: string
  modules: USMarketModule[]
  qqq: USMarketQQQ
  highlights: string[]
}
