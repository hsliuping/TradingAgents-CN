import { ApiClient } from './request'

export enum GrowthMemoryStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  EXPIRED = 'expired'
}

export enum GrowthSuggestionStatus {
  PENDING = 'pending',
  ACCEPTED = 'accepted',
  DISMISSED = 'dismissed',
  EXPIRED = 'expired'
}

export enum GrowthMemoryScope {
  TASK_TEMP = 'task_temp',
  OBJECT_TRACKING = 'object_tracking',
  USER_PREFERENCE = 'user_preference',
  RESEARCH_ASSET = 'research_asset',
  PATTERN = 'pattern'
}

export interface GrowthEvidenceRef {
  type: string
  id: string
  label?: string
}

export interface GrowthMemoryItem {
  memory_id: string
  user_id: string
  scope: GrowthMemoryScope | string
  status: GrowthMemoryStatus | string
  review_level: string
  source_type: string
  source_id: string
  task_type?: string
  workflow_id?: string
  object_type?: string
  object_key?: string
  title: string
  summary: string
  content: string
  structured_payload?: Record<string, any>
  confidence: number
  evidence_refs: GrowthEvidenceRef[]
  created_at: string
  updated_at: string
}

export interface GrowthSuggestion {
  suggestion_id: string
  user_id: string
  suggestion_type: string
  status: GrowthSuggestionStatus | string
  source_type: string
  source_id: string
  task_type?: string
  workflow_id?: string
  object_type?: string
  object_key?: string
  title: string
  summary: string
  suggested_action?: Record<string, any>
  confidence: number
  source_refs: GrowthEvidenceRef[]
  activation_result?: {
    status?: string
    target?: string
    mode?: string
    session_id?: string
    ai_message?: string
    error?: string
  }
  created_at: string
  updated_at: string
}

export interface TaskGrowthContextPayload {
  task_id: string
  memory_items: GrowthMemoryItem[]
  suggestions: GrowthSuggestion[]
  summary: {
    memory_items_count: number
    suggestions_count: number
  }
}

export function getTaskGrowthContext(taskId: string) {
  return ApiClient.get<TaskGrowthContextPayload>(`/api/workflow-growth/tasks/${taskId}`)
}

export function approveGrowthMemory(memoryId: string) {
  return ApiClient.post<{ success: boolean; message: string }>(`/api/workflow-growth/memories/${memoryId}/approve`)
}

export function rejectGrowthMemory(memoryId: string) {
  return ApiClient.post<{ success: boolean; message: string }>(`/api/workflow-growth/memories/${memoryId}/reject`)
}

export function acceptGrowthSuggestion(suggestionId: string) {
  return ApiClient.post<GrowthSuggestion>(`/api/workflow-growth/suggestions/${suggestionId}/accept`)
}

export function dismissGrowthSuggestion(suggestionId: string) {
  return ApiClient.post<{ success: boolean; message: string }>(`/api/workflow-growth/suggestions/${suggestionId}/dismiss`)
}

export const GrowthMemoryStatusNames: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  rejected: '已拒绝',
  expired: '已过期'
}

export const GrowthSuggestionStatusNames: Record<string, string> = {
  pending: '待处理',
  accepted: '已接受',
  dismissed: '已忽略',
  expired: '已过期'
}

export const GrowthMemoryScopeNames: Record<string, string> = {
  task_temp: '任务临时记忆',
  object_tracking: '对象跟踪记忆',
  user_preference: '用户偏好',
  research_asset: '研究资产',
  pattern: '经验模式'
}