import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

vi.stubGlobal('fetch', vi.fn(async (input: string) => {
  if (input.includes('/reports')) return new Response(JSON.stringify([]), { status: 200 })
  if (input.match(/\/ipos\/\d/)) return new Response(JSON.stringify({ id:1,name:'示例科技有限公司',english_name:'SampleTech',code:'06999.HK',industry:'资讯科技',price_low:15,price_high:18,minimum_subscription_amount:null,subscription_multiple:82,deadline:'2026-07-08',is_sample:true,original_score:80,adjustment:0,final_score:80,recommendation:'申购',dimensions:[],risks:[],metrics:{},adjustments:[] }), { status: 200 })
  return new Response(JSON.stringify({ items:[],total:0,page:1,page_size:20,insights:{fundamental_valuation_ranking:[],allotment_difficulty:[]} }), { status: 200 })
}))

describe('App', () => {
  it('renders the analysis navigation and local-data disclosure', async () => {
    render(<App />)
    expect(screen.getByText('港股IPO分析')).toBeInTheDocument()
    expect(screen.getByText('今日分析')).toBeInTheDocument()
    expect(await screen.findByText('没有符合条件的 IPO')).toBeInTheDocument()
    expect(screen.getByText(/数据源：本地文件/)).toBeInTheDocument()
    expect(screen.getByText(/16 只真实 IPO/)).toBeInTheDocument()
  })
})
