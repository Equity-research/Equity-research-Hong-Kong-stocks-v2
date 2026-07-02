export type Recommendation = '申购' | '观望' | '回避'
export interface DimensionScore { key: string; label: string; score: number; weight: number; reasons: string[]; missing: string[] }
export interface Adjustment { id: number; value: number; reason: string; operator: string; created_at: string; original_score: number; final_score: number }
export interface IPO {
  id: number; name: string; english_name: string; code: string; industry: string; price_low: number; price_high: number;
  deadline: string; is_sample: boolean; original_score: number; adjustment: number; final_score: number; recommendation: Recommendation
}
export interface IPODetail extends IPO { dimensions: DimensionScore[]; risks: string[]; metrics: Record<string, number | null>; adjustments: Adjustment[] }
export interface IPOList { items: IPO[]; total: number; page: number; page_size: number }
export interface Report { id: number; report_date: string; version: number; created_at: string; item_count: number; buy_count: number; hold_count: number; avoid_count: number; markdown?: string }

