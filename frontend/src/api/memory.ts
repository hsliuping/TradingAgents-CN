/**
 * mem0 统一记忆层 API
 */

import { request } from './request'

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
      const res = await request.get<{ ok: boolean; mem0_version?: string; error?: string }>(
        '/api/memory/health',
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
}
