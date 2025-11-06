/**
 * 超短行情分析API
 */

import { request, type ApiResponse } from './request'

// 超短行情分析请求
export interface ShortTermAnalysisRequest {
  ticker: string
  analysis_date: string
  llm_provider?: string
  llm_model?: string
}

// 超短行情分析响应
export interface ShortTermAnalysisResponse {
  success: boolean
  ticker: string
  analysis_date: string
  report?: string
  probabilities?: {
    limit_up?: number | null  // 涨停概率
    up?: number | null        // 上涨概率
    down?: number | null      // 下跌概率
  }
  error?: string
  timestamp: string
}

// 批量超短行情分析请求
export interface BatchShortTermAnalysisRequest {
  title: string
  description?: string
  symbols: string[]
  analysis_date: string
  llm_provider?: string
  llm_model?: string
}

// 批量超短行情分析响应
export interface BatchShortTermAnalysisResponse {
  success: boolean
  data: {
    batch_id: string
    total_tasks: number
    task_ids: string[]
  }
  message?: string
}

// 超短行情分析API
export const shortTermAnalysisApi = {
  // 单股超短行情分析
  analyzeShortTerm(req: ShortTermAnalysisRequest): Promise<ApiResponse<ShortTermAnalysisResponse>> {
    return request.post('/api/short-term/analyze', req)
  },

  // 批量超短行情分析
  startBatchAnalysis(req: BatchShortTermAnalysisRequest): Promise<ApiResponse<BatchShortTermAnalysisResponse['data']>> {
    return request.post('/api/short-term/batch', req)
  },

  // 获取批量分析状态
  getBatchStatus(batchId: string): Promise<ApiResponse<any>> {
    return request.get(`/api/short-term/batches/${batchId}/status`)
  },

  // 获取批量分析结果
  getBatchResults(batchId: string): Promise<ApiResponse<any>> {
    return request.get(`/api/short-term/batches/${batchId}/results`)
  }
}

