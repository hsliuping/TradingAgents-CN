/**
 * Skill 缺口感知 API 客户端
 */
import request from '@/api/request'

export interface GapSource {
  agent_id: string
  agent_name: string
  workflow_id: string
  workflow_name: string
  task_id: string
  node_id: string
}

export interface GapInfo {
  type: string
  tool_name: string
  error_message: string
  tool_call_args: Record<string, unknown>
  context_summary: string
}

export interface SkillGapReport {
  report_id: string
  user_id: string
  status: 'pending' | 'reviewed' | 'creating' | 'resolved' | 'dismissed' | 'expired'
  source: GapSource
  gap: GapInfo
  analysis: Record<string, unknown> | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  expires_at: string
}

export interface GapListResponse {
  items: SkillGapReport[]
  total: number
  page: number
  page_size: number
}

export interface GapStats {
  by_status: Record<string, number>
  by_type: Record<string, number>
  total: number
}

export interface CreateSkillParams {
  prefill: {
    name: string
    description: string
    tags: string[]
  }
  report_id: string
}

/** 获取缺口报告列表 */
export function listGaps(params: {
  status?: string
  page?: number
  page_size?: number
}): Promise<GapListResponse> {
  return request.get('/api/skill-gaps', { params })
}

/** 获取缺口统计 */
export function getGapStats(): Promise<GapStats> {
  return request.get('/api/skill-gaps/stats')
}

/** 获取单个缺口报告 */
export function getGap(reportId: string): Promise<SkillGapReport> {
  return request.get(`/api/skill-gaps/${reportId}`)
}

/** 忽略缺口 */
export function dismissGap(reportId: string): Promise<{ success: boolean; message: string }> {
  return request.post(`/api/skill-gaps/${reportId}/dismiss`)
}

/** 标记已解决 */
export function resolveGap(
  reportId: string,
  skillId: string = ''
): Promise<{ success: boolean; message: string }> {
  return request.post(`/api/skill-gaps/${reportId}/resolve`, { skill_id: skillId })
}

/** 获取创建 Skill 预填参数 */
export function getCreateSkillParams(reportId: string): Promise<CreateSkillParams> {
  return request.get(`/api/skill-gaps/${reportId}/create-skill-params`)
}

