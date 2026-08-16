/**
 * mem0 统一记忆层 API
 */

import { ApiClient, request } from './request'

export interface MemoryItem {
  id: string
  memory: string
  user_id: string
  agent_id: string
  scope: string
  score: number
  metadata: Record<string, any>
  created_at: string
  updated_at: string
  object_type?: string
  object_key?: string
  symbol?: string
  market?: string
  memory_kind?: string
}

export interface MemoryQueryParams {
  scope?: string
  page?: number
  page_size?: number
  object_type?: string
  symbol?: string
  market?: string
  memory_kind?: string
}

export interface MemoryStatsData {
  enabled: boolean
  available?: boolean
  user_id?: string
  total?: number
  scopes?: Record<string, number>
  message?: string
}

export interface MemoryListData {
  items: MemoryItem[]
  total: number
  page: number
  page_size: number
}

export interface MemoryRecallData {
  count: number
  items: MemoryItem[]
}

/** 智能助手事实记忆（assistant_memory_facts） */
export interface AssistantFactItem {
  id: string
  topic: string
  content: string
  symbol?: string
  related_terms?: string[]
  tool_id?: string
  fetched_at?: string
  category?: string
  valid_until?: string
  thread_id?: string
}

export interface AssistantFactListData {
  items: AssistantFactItem[]
  total: number
  page: number
  page_size: number
}

export const FACT_CATEGORY_LABELS: Record<string, string> = {
  realtime_quote: '实时行情',
  industry_metric: '行业指标',
  company_financial: '公司财务',
  company_static: '公司资料',
  default: '通用',
}

export const SCOPE_LABELS: Record<string, string> = {
  conversation: '对话记忆',
  user_preference: '用户偏好',
  analysis_insight: '分析洞察',
  skill_lesson: '技能经验',
  agent_experience: 'Agent 经验',
  trade_pattern: '交易模式',
}

export const SCOPE_COLORS: Record<string, string> = {
  conversation: '',
  user_preference: 'success',
  analysis_insight: 'warning',
  skill_lesson: 'danger',
  agent_experience: 'info',
  trade_pattern: 'success',
}

export const memoryApi = {
  async getHealth() {
    try {
      const res = await ApiClient.get<{ ok: boolean; mem0_version?: string; error?: string }>(
        '/api/memory/health',
        undefined,
        { skipErrorHandler: true },
      )
      return (res as any)?.data ?? res
    } catch (error: any) {
      const responseData = error?.response?.data
      return responseData?.data ?? {
        ok: false,
        error: responseData?.message || error?.message || '记忆层不可用',
      }
    }
  },

  async getStats(): Promise<MemoryStatsData> {
    const res: any = await request.get('/api/memory/stats')
    return res?.data ?? res
  },

  async getList(params: MemoryQueryParams = {}): Promise<MemoryListData> {
    const res: any = await request.get('/api/memory/list', { params })
    return res?.data ?? res
  },

  async recall(query: string, params: MemoryQueryParams = {}, limit = 10): Promise<MemoryRecallData> {
    const res: any = await request.get('/api/memory/recall', {
      params: { query, limit, ...params },
    })
    return res?.data ?? res
  },

  async deleteMemory(memoryId: string): Promise<boolean> {
    const res: any = await request.delete(`/api/memory/${encodeURIComponent(memoryId)}`)
    return res?.success ?? false
  },

  async batchDelete(memoryIds: string[]): Promise<{ deleted: number; requested: number }> {
    const res: any = await request.post('/api/memory/batch-delete', { memory_ids: memoryIds })
    return res?.data ?? { deleted: 0, requested: memoryIds.length }
  },

  async deleteAll(): Promise<{ deleted: number }> {
    const res: any = await request.delete('/api/memory/clear-all')
    return res?.data ?? { deleted: 0 }
  },

  // ── 智能助手事实记忆（assistant_memory_facts）───────────────────────────
  async getAssistantFacts(
    params: { q?: string; symbol?: string; category?: string; page?: number; page_size?: number } = {},
  ): Promise<AssistantFactListData> {
    const res: any = await request.get('/api/memory/assistant-facts', { params })
    return res?.data ?? res
  },

  async deleteAssistantFact(factId: string): Promise<boolean> {
    const res: any = await request.delete(`/api/memory/assistant-facts/${encodeURIComponent(factId)}`)
    return res?.success ?? false
  },

  async batchDeleteAssistantFacts(factIds: string[]): Promise<{ deleted: number; requested: number }> {
    const res: any = await request.post('/api/memory/assistant-facts/batch-delete', { fact_ids: factIds })
    return res?.data ?? { deleted: 0, requested: factIds.length }
  },
}
