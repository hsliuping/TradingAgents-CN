/**
 * 对话驱动回测 API
 */
import { request } from './request'

export interface StrategyDSL {
  name: string
  description?: string
  universe: { type: string; symbols?: string[]; params?: Record<string, unknown> }
  entry_rules: Array<Record<string, unknown>>
  exit_rules: Array<Record<string, unknown>>
  config: Record<string, unknown>
}

export interface BacktestSummary {
  final_value?: number
  total_return?: number
  win_rate?: number
  max_drawdown_pct?: number
  sharpe_ratio?: number
  trade_count?: number
}

export const backtestApi = {
  /** 分析策略可行性 */
  async analyze(description: string): Promise<{ analysis: string }> {
    return request.post('/api/backtest/analyze', { description }) as unknown as Promise<{ analysis: string }>
  },

  /** 生成策略 DSL */
  async generate(description: string): Promise<{ strategy: StrategyDSL }> {
    return request.post('/api/backtest/generate', { description }) as unknown as Promise<{ strategy: StrategyDSL }>
  },

  /** 执行回测 */
  async run(strategy: StrategyDSL, sessionId?: string): Promise<{
    session_id: string
    result_id?: string
    success: boolean
    summary?: BacktestSummary
    error?: string
  }> {
    return request.post('/api/backtest/run', {
      strategy,
      session_id: sessionId
    }) as unknown as Promise<any>
  },

  /** 获取回测结果 */
  async getResult(resultId: string): Promise<Record<string, unknown>> {
    return request.get(`/api/backtest/results/${resultId}`) as unknown as Promise<Record<string, unknown>>
  },

  /** 列出回测会话 */
  async listSessions(limit = 50): Promise<Array<Record<string, unknown>>> {
    const raw = (await request.get('/api/backtest/sessions', { params: { limit } })) as unknown
    return (Array.isArray(raw) ? raw : []) as Array<Record<string, unknown>>
  },

  /** 删除回测会话 */
  async deleteSession(sessionId: string): Promise<void> {
    await request.delete(`/api/backtest/sessions/${sessionId}`)
  }
}
