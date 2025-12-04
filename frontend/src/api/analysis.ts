
/**
 * 股票分析API
 */

import { request, type ApiResponse } from './request'

// 分析相关类型定义
export interface AnalysisRequest {
  market_type: string
  stock_symbol: string
  analysis_date: string
  analysis_type: string
  data_sources: string[]
  analysis_depth: number
  include_news: boolean
  include_financials: boolean
  llm_provider?: string
  llm_model?: string
}

// 后端期望的请求格式
export interface SingleAnalysisRequest {
  symbol?: string  // 主字段：6位股票代码
  stock_code?: string  // 兼容字段（已废弃）
  parameters?: {
    market_type?: string
    analysis_date?: string
    research_depth?: string
    selected_analysts?: string[]
    custom_prompt?: string
    include_sentiment?: boolean
    include_risk?: boolean
    language?: string
    quick_analysis_model?: string
    deep_analysis_model?: string
  }
}

export interface AnalysisProgress {
  analysis_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_step: string
  step_detail: string
  steps: AnalysisStep[]
  started_at: string
  updated_at: string
  estimated_completion?: string
}

export interface AnalysisStep {
  name: string
  title: string
  description: string
  status: 'pending' | 'active' | 'success' | 'error'
  started_at?: string
  completed_at?: string
  duration?: number
  error_message?: string
}

export interface AnalysisResult {
  analysis_id: string
  symbol?: string  // 主字段：6位股票代码
  stock_symbol: string  // 兼容字段
  stock_code?: string  // 兼容字段（已废弃）
  stock_name: string
  market_type: string
  analysis_date: string
  analysis_type: string

  // 基础数据
  current_price: number
  price_change: number
  price_change_percent: number
  volume: number
  market_cap?: number

  // 分析结果
  summary: string
  technical_analysis: string
  fundamental_analysis: string
  sentiment_analysis: string
  news_analysis?: string
  recommendation: string
  risk_assessment: string

  // 评分
  technical_score: number
  fundamental_score: number
  sentiment_score: number
  overall_score: number

  // 元数据
  data_sources: string[]
  llm_provider: string
  llm_model: string
  analysis_duration: number
  token_usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    cost: number
  }

  created_at: string
  updated_at: string
}

export interface AnalysisHistory {
  total: number
  page: number
  page_size: number
  analyses: AnalysisResult[]
}

// 股票分析API
export const analysisApi = {
  // 开始分析
  startAnalysis(analysisRequest: AnalysisRequest): Promise<{ analysis_id: string; message: string }> {
    return request.post('/api/analysis/single', analysisRequest)
  },

  // 开始单股分析（使用后端期望的格式）
  startSingleAnalysis(analysisRequest: SingleAnalysisRequest): Promise<ApiResponse<any>> {
    return request.post('/api/analysis/single', analysisRequest)
  },

  // 获取任务状态
  getTaskStatus(taskId: string): Promise<ApiResponse<any>> {
    return request.get(`/api/analysis/tasks/${taskId}/status`)
  },

  // 获取分析进度
  getProgress(analysisId: string): Promise<AnalysisProgress> {
    return request.get(`/api/analysis/${analysisId}/progress`)
  },

  // 获取分析结果
  getResult(analysisId: string): Promise<AnalysisResult> {
    return request.get(`/api/analysis/${analysisId}/result`)
  },

  // 停止分析
  stopAnalysis(analysisId: string): Promise<{ message: string }> {
    return request.post(`/api/analysis/${analysisId}/stop`, {})
  },

  // 获取分析历史（用户维度）
  getHistory(params?: {
    page?: number
    page_size?: number
    market_type?: string
    symbol?: string  // 主字段：股票代码
    stock_code?: string  // 兼容字段（已废弃）
    start_date?: string
    end_date?: string
    status?: string
  }): Promise<any> {
    return request.get('/api/analysis/user/history', { params })
  },

  // 删除分析结果
  deleteAnalysis(analysisId: string): Promise<{ message: string }> {
    return request.delete(`/api/analysis/${analysisId}`)
  },

  // 导出分析结果
  exportAnalysis(analysisId: string, format: 'pdf' | 'excel' | 'json' = 'pdf'): Promise<Blob> {
    return request.get(`/api/analysis/${analysisId}/export`, {
      params: { format },
      responseType: 'blob'
    })
  },

  // 批量分析（方案A：与单股一致的进程内执行）
  startBatchAnalysis(batchRequest: {
    title: string
    description?: string
    symbols?: string[]  // 主字段：股票代码列表
    stock_codes?: string[]  // 兼容字段（已废弃）
    parameters?: SingleAnalysisRequest['parameters']
  }): Promise<ApiResponse<{ batch_id: string; total_tasks: number; task_ids: string[]; mapping?: any[]; status: string }>>{
    return request.post('/api/analysis/batch', batchRequest)
  },

  // 获取批次详情（兼容原有队列接口，若后续需要）
  getBatch(batchId: string): Promise<any> {
    return request.get(`/api/analysis/batches/${batchId}`)
  },

  // 获取任务详情（兼容原有队列接口，若后续需要）
  getTaskDetails(taskId: string): Promise<any> {
    return request.get(`/api/analysis/tasks/${taskId}/details`)
  },

  // 获取任务列表（新版 simple service）
  getTaskList(params?: { status?: string; limit?: number; offset?: number }): Promise<any>{
    return request.get('/api/analysis/tasks', { params })
  },

  // 获取任务结果（新版 simple service）
  getTaskResult(taskId: string): Promise<any>{
    return request.get(`/api/analysis/tasks/${taskId}/result`)
  },

  // 标记任务为失败
  markTaskAsFailed(taskId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/api/analysis/tasks/${taskId}/mark-failed`, {})
  },

  // 删除任务
  deleteTask(taskId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api/analysis/tasks/${taskId}`)
  },

  // 分享分析结果
  shareAnalysis(analysisId: string, options: {
    expires_in?: number // 过期时间（秒）
    password?: string   // 访问密码
    public?: boolean    // 是否公开
  }): Promise<{ share_url: string; share_code: string }> {
    return request.post(`/api/analysis/${analysisId}/share`, options)
  },

  // 获取股票基础信息
  getStockInfo(symbol: string, market: string): Promise<{
    symbol: string
    name: string
    market: string
    current_price: number
    change: number
    change_percent: number
    volume: number
    market_cap?: number
    pe_ratio?: number
    pb_ratio?: number
    dividend_yield?: number
  }> {
    return request.get('/api/analysis/stock-info', {
      params: { symbol, market }
    })
  },

  // 搜索股票
  searchStocks(query: string, market?: string): Promise<Array<{
    symbol: string
    name: string
    market: string
    type: string
  }>> {
    return request.get('/api/analysis/search', {
      params: { query, market }
    })
  },

  // 获取热门股票
  getPopularStocks(market?: string, limit: number = 10): Promise<Array<{
    symbol: string
    name: string
    market: string
    current_price: number
    change_percent: number
    volume: number
    analysis_count: number
  }>> {
    return request.get('/api/analysis/popular', {
      params: { market, limit }
    })
  },

  // 获取分析统计
  getAnalysisStats(params?: {
    start_date?: string
    end_date?: string
    market_type?: string
  }): Promise<{
    total_analyses: number
    successful_analyses: number
    failed_analyses: number
    avg_duration: number
    total_tokens: number
    total_cost: number
    popular_stocks: Array<{
      symbol: string
      name: string
      count: number
    }>
    analysis_by_date: Array<{
      date: string
      count: number
    }>
    analysis_by_market: Array<{
      market: string
      count: number
    }>
  }> {
    return request.get('/api/analysis/stats', { params })
  }
}

// 分析相关的常量
export const MARKET_TYPES = {
  US: '美股',
  CN: 'A股',
  HK: '港股'
} as const

export const ANALYSIS_TYPES = {
  BASIC: 'basic',
  DEEP: 'deep',
  TECHNICAL: 'technical',
  NEWS: 'news',
  COMPREHENSIVE: 'comprehensive'
} as const

/**
 * 数据源常量
 *
 * 注意：这些常量与后端 DataSourceType 枚举保持同步
 * 添加新数据源时，请先在后端 tradingagents/constants/data_sources.py 中注册
 */
export const DATA_SOURCES = {
  // 缓存数据源
  MONGODB: 'mongodb',

  // 中国市场数据源
  TUSHARE: 'tushare',
  AKSHARE: 'akshare',
  BAOSTOCK: 'baostock',

  // 美股数据源
  FINNHUB: 'finnhub',
  YAHOO_FINANCE: 'yahoo_finance',
  ALPHA_VANTAGE: 'alpha_vantage',
  IEX_CLOUD: 'iex_cloud',

  // 专业数据源
  WIND: 'wind',
  CHOICE: 'choice',

  // 其他数据源
  QUANDL: 'quandl',
  LOCAL_FILE: 'local_file',
  CUSTOM: 'custom'
} as const

// 分析状态常量
export const ANALYSIS_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed'
} as const

// 步骤状态常量
export const STEP_STATUS = {
  PENDING: 'pending',
  ACTIVE: 'active',
  SUCCESS: 'success',
  ERROR: 'error'
} as const

// 验证函数
export const validateAnalysisRequest = (request: Partial<AnalysisRequest>): string[] => {
  const errors: string[] = []

  if (!request.market_type) errors.push('请选择市场类型')
  if (!request.stock_symbol) errors.push('请输入股票代码')
  if (!request.analysis_date) errors.push('请选择分析日期')
  if (!request.analysis_type) errors.push('请选择分析类型')
  if (!request.data_sources || request.data_sources.length === 0) {
    errors.push('请至少选择一个数据源')
  }

  // 验证股票代码格式
  if (request.stock_symbol) {
    const symbol = request.stock_symbol.trim().toUpperCase()
    if (request.market_type === '美股') {
      if (!/^[A-Z]{1,5}$/.test(symbol)) {
        errors.push('美股代码格式不正确，应为1-5个字母')
      }
    } else if (request.market_type === 'A股') {
      if (!/^\d{6}$/.test(symbol)) {
        errors.push('A股代码格式不正确，应为6位数字')
      }
    } else if (request.market_type === '港股') {
      if (!/^\d{4,5}\.HK$/.test(symbol)) {
        errors.push('港股代码格式不正确，应为4-5位数字.HK')
      }
    }
  }

  return errors
}

// 格式化函数
export const formatAnalysisType = (type: string): string => {
  const typeMap: Record<string, string> = {
    basic: '基础分析',
    deep: '深度分析',
    technical: '技术分析',
    news: '新闻分析',
    comprehensive: '综合分析'
  }
  return typeMap[type] ?? type
}

export const formatMarketType = (market: string): string => {
  const marketMap: Record<string, string> = {
    '美股': '🇺🇸 美股',
    'A股': '🇨🇳 A股',
    '港股': '🇭🇰 港股'
  }
  return marketMap[market] ?? market
}

export const formatDataSource = (source: string): string => {
  const sourceMap: Record<string, string> = {
    finnhub: 'FinnHub',
    tushare: 'Tushare',
    akshare: 'AKShare',
    yahoo: 'Yahoo Finance'
  }
  return sourceMap[source] ?? source
}

/**
 * 获取分析历史记录（当前用户）
 */
export const getAnalysisHistory = async (params: {
  page?: number
  page_size?: number
  status?: string
}) => {
  const response = await request.get('/api/analysis/user/history', { params })
  return response.data
}

/**
 * 获取所有任务列表（不限用户）
 */
export const getAllTasks = async (params: {
  limit?: number
  offset?: number
  status?: string
}) => {
  return request<{
    tasks: any[]
    total: number
    limit: number
    offset: number
  }>({
    url: '/api/analysis/tasks/all',
    method: 'GET',
    params
  })
}

// 工具函数
export const getStockExamples = (market: string): string[] => {
  const examples: Record<string, string[]> = {
    '美股': ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'NFLX'],
    'A股': ['000001', '600519', '000002', '600036', '000858', '002415', '300059', '688981'],
    '港股': ['0700.HK', '9988.HK', '3690.HK', '0941.HK', '1810.HK', '2318.HK', '1299.HK']
  }
  return examples[market] ?? []
}

export const getStockPlaceholder = (market: string): string => {
  const placeholders: Record<string, string> = {
    '美股': '输入美股代码，如 AAPL, TSLA, MSFT',
    'A股': '输入A股代码，如 000001, 600519',
    '港股': '输入港股代码，如 0700.HK, 9988.HK'
  }
  return placeholders[market] ?? '输入股票代码'
}




