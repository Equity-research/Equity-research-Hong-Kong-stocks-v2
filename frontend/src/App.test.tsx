import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the latest report page as the only entry', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: '今日 IPO 分析' })).toBeInTheDocument()
    expect(screen.getByText(/9 只真实 IPO/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /生成今日日报/ })).toBeInTheDocument()
    expect(screen.getAllByText('普源精电').length).toBeGreaterThan(0)
    expect(screen.queryByText('历史日报')).not.toBeInTheDocument()
    expect(screen.queryByText('评分规则')).not.toBeInTheDocument()
  })
})
