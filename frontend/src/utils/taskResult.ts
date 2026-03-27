import { analysisApi } from '@/api/analysis'

const META_KEYS = new Set([
  'analysis_id',
  'analysis_date',
  'created_at',
  'updated_at',
  'status',
  'source',
  'symbol',
  'stock_symbol',
  'stock_code',
  'stock_name',
  'market_type',
  'analysts',
  'research_depth',
  'execution_time',
  'tokens_used',
  'confidence_score',
  'risk_level',
  'task_id',
  'id'
])

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const isApiEnvelope = (value: any) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  return 'data' in value && ('success' in value || 'message' in value || 'code' in value || Object.keys(value).length === 1)
}

const hasNonEmptyValue = (value: any): boolean => {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.some(item => hasNonEmptyValue(item))
  if (typeof value === 'object') return Object.values(value).some(item => hasNonEmptyValue(item))
  return true
}

export const unwrapTaskResultResponse = (value: any) => {
  let current = value

  for (let depth = 0; depth < 3; depth += 1) {
    if (!isApiEnvelope(current)) {
      break
    }
    current = current.data
  }

  return current ?? null
}

export const hasTaskResultContent = (result: any) => {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return false

  const preferredKeys = [
    'summary',
    'recommendation',
    'reports',
    'decision',
    'state',
    'index_report',
    'sector_report',
    'market_report',
    'fundamentals_report',
    'final_trade_decision'
  ]

  if (preferredKeys.some(key => hasNonEmptyValue(result[key]))) {
    return true
  }

  return Object.entries(result).some(([key, value]) => !META_KEYS.has(key) && hasNonEmptyValue(value))
}

export const mergeTaskResult = (...sources: any[]) => {
  const merged: Record<string, any> = {}

  sources.forEach(source => {
    if (!source || typeof source !== 'object' || Array.isArray(source)) return

    Object.entries(source).forEach(([key, value]) => {
      if (value === undefined || value === null) return

      if (typeof value === 'string') {
        if (!merged[key] || String(merged[key]).trim().length === 0 || value.trim().length > String(merged[key]).trim().length) {
          merged[key] = value
        }
        return
      }

      if (Array.isArray(value)) {
        if (!Array.isArray(merged[key]) || merged[key].length === 0) {
          merged[key] = value
        }
        return
      }

      if (typeof value === 'object') {
        merged[key] = {
          ...(merged[key] || {}),
          ...value
        }
        return
      }

      merged[key] = value
    })
  })

  return merged
}

export const fetchTaskResultWithRetry = async (
  taskId: string,
  options?: {
    seedData?: any
    attempts?: number
    delayMs?: number
    isComplete?: (result: any) => boolean
  }
) => {
  const attempts = Math.max(1, options?.attempts ?? 4)
  const delayMs = Math.max(0, options?.delayMs ?? 800)
  const isComplete = options?.isComplete ?? hasTaskResultContent
  const seedData = unwrapTaskResultResponse(options?.seedData)

  let bestResult = mergeTaskResult(seedData)

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await analysisApi.getTaskResult(taskId)
      const apiResult = unwrapTaskResultResponse(response)
      bestResult = mergeTaskResult(bestResult, seedData, apiResult)

      if (isComplete(bestResult)) {
        return bestResult
      }
    } catch (error) {
      console.error(`获取任务结果失败（第 ${attempt + 1} 次）`, error)
    }

    if (attempt < attempts - 1) {
      await delay(delayMs)
    }
  }

  return isComplete(bestResult) ? bestResult : seedData || bestResult || null
}