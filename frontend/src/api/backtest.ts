/**
 * 对话驱动回测 API
 */
import { request } from './request'

export interface StrategyDSL {
  name?: string
  description?: string
  universe?: { type: string; symbols?: string[]; index_code?: string; params?: Record<string, unknown> }
  entry_rules?: Array<Record<string, unknown>>
  exit_rules?: Array<Record<string, unknown>>
  config?: Record<string, unknown>
}

/** Python 策略：code + config */
export interface StrategyPython {
  code: string
  config: Record<string, unknown>
}

/** 策略类型：DSL 或 Python */
export type Strategy = StrategyDSL | StrategyPython

export function isPythonStrategy(s: Strategy): s is StrategyPython {
  return 'code' in s && 'config' in s
}

export interface BacktestSummary {
  final_value?: number
  total_return?: number
  win_rate?: number
  max_drawdown_pct?: number
  sharpe_ratio?: number
  trade_count?: number
  trades?: Array<{ symbol: string; open_date: string; close_date: string; size: number; pnl: number; pnl_net: number; commission: number }>
  transactions?: Array<{ date: string; symbol: string; side: string; size: number; price: number; value: number }>
  positions?: Array<{ name: string; size: number; price: number; value: number }>
}

/** 评估结果 */
export interface EvaluationResult {
  overall_score: number
  is_satisfactory: boolean
  issues: Array<{
    type: string
    severity: 'high' | 'medium' | 'low'
    description: string
    suggestion: string
  }>
  strengths?: string[]
  optimization_priority: 'high' | 'medium' | 'low' | 'none'
  next_steps?: string
}

/** 迭代记录 */
export interface IterationRecord {
  iteration: number
  score: number
  is_satisfactory: boolean
  optimization_applied: boolean
  summary?: BacktestSummary
}

/** 迭代优化结果 */
export interface OptimizationResult {
  session_id: string
  success: boolean
  error?: string
  final_strategy?: StrategyPython
  final_result?: { success: boolean; summary?: BacktestSummary; logs?: string[]; warnings?: string[] }
  final_evaluation?: EvaluationResult
  iterations?: IterationRecord[]
  optimization_summary?: string
  result_id?: string
}

export const backtestApi = {
  /** 分析策略可行性 */
  async analyze(description: string): Promise<{ analysis: string }> {
    return request.post('/api/backtest/analyze', { description }) as unknown as Promise<{ analysis: string }>
  },

  /** 生成策略（Python 代码 + config） */
  async generate(description: string): Promise<{ strategy: StrategyPython }> {
    return request.post('/api/backtest/generate', { description }) as unknown as Promise<{ strategy: StrategyPython }>
  },

  /** 执行回测（支持 DSL 或 {code, config}），保存原始需求、分析、策略、结果 */
  async run(
    strategy: Strategy,
    opts?: { sessionId?: string; description?: string; analysis?: string; refinement?: string; name?: string }
  ): Promise<{
    session_id: string
    result_id?: string
    success: boolean
    summary?: BacktestSummary
    error?: string
  }> {
    return request.post('/api/backtest/run', {
      strategy,
      session_id: opts?.sessionId,
      description: opts?.description,
      analysis: opts?.analysis,
      refinement: opts?.refinement,
      name: opts?.name
    }) as unknown as Promise<any>
  },

  /** 获取单个会话详情（含策略、原始需求、AI 分析、回测结果） */
  async getSession(sessionId: string): Promise<Record<string, unknown>> {
    return request.get(`/api/backtest/sessions/${sessionId}`) as unknown as Promise<Record<string, unknown>>
  },

  /** 更新会话（如策略名称） */
  async updateSession(sessionId: string, name: string): Promise<{ success: boolean }> {
    return request.patch(`/api/backtest/sessions/${sessionId}`, { name }) as unknown as Promise<{ success: boolean }>
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
  },

  /** 运行迭代优化 */
  async optimize(
    description: string,
    strategy: StrategyPython,
    opts?: { maxIterations?: number; sessionId?: string; name?: string }
  ): Promise<OptimizationResult> {
    return request.post('/api/backtest/optimize', {
      description,
      strategy,
      max_iterations: opts?.maxIterations || 3,
      session_id: opts?.sessionId,
      name: opts?.name
    }) as unknown as Promise<OptimizationResult>
  },

  /** 评估现有回测结果 */
  async evaluate(sessionId: string, description: string): Promise<EvaluationResult> {
    return request.post('/api/backtest/evaluate', {
      session_id: sessionId,
      description
    }) as unknown as Promise<EvaluationResult>
  }
}
