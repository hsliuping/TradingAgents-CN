/**
 * 统一任务中心 API
 *
 * 对接后端 /api/v2/tasks/* 端点
 * 支持所有类型的分析任务（股票分析、持仓分析、交易复盘等）
 */

import { ApiClient } from './request'

// ==================== 类型定义 ====================

/**
 * 任务类型枚举
 */
export enum TaskType {
  STOCK_ANALYSIS = 'stock_analysis',
  POSITION_ANALYSIS = 'position_analysis',
  TRADE_REVIEW = 'trade_review',
  PORTFOLIO_HEALTH = 'portfolio_health',
  RISK_ASSESSMENT = 'risk_assessment',
  MARKET_OVERVIEW = 'market_overview',
  SECTOR_ANALYSIS = 'sector_analysis'
}

/**
 * 任务状态枚举
 */
export enum TaskStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  SUSPENDED = 'suspended'  // 挂起状态（服务重启后未完成的任务）
}

/**
 * 任务列表项
 */
export interface TaskListItem {
  task_id: string
  task_type: TaskType
  status: TaskStatus
  progress: number
  created_at: string
  started_at?: string
  completed_at?: string
  execution_time: number
  error_message?: string
  
  // 任务参数（用于显示）
  symbol?: string
  code?: string
  market?: string
}

/**
 * 任务详情
 */
export interface TaskDetail {
  task_id: string
  user_id: string
  task_type: TaskType
  task_params: Record<string, any>
  workflow_id?: string
  engine_type: string
  preference_type: string
  status: TaskStatus
  progress: number
  current_step?: string
  result?: Record<string, any>
  created_at: string
  started_at?: string
  completed_at?: string
  execution_time: number
  error_message?: string
  retry_count: number
  max_retries: number
  tokens_used: number
  cost: number
}

/**
 * 任务统计
 */
export interface TaskStatistics {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
  cancelled: number
}

/**
 * 任务列表查询参数
 */
export interface TaskListParams {
  task_type?: TaskType
  status?: TaskStatus
  limit?: number
  skip?: number
}

// ==================== API 方法 ====================

/**
 * 获取任务列表
 */
export function getTaskList(params?: TaskListParams) {
  return ApiClient.get<{
    tasks: TaskListItem[]
    total: number
    limit: number
    skip: number
  }>('/api/v2/tasks/list', params)
}

/**
 * 获取任务统计
 */
export function getTaskStatistics() {
  return ApiClient.get<TaskStatistics>('/api/v2/tasks/statistics')
}

/**
 * 获取任务详情
 */
export function getTaskDetail(taskId: string) {
  return ApiClient.get<TaskDetail>(`/api/v2/tasks/${taskId}`)
}

/**
 * 取消任务
 */
export function cancelTask(taskId: string) {
  return ApiClient.delete<{ success: boolean; message: string }>(`/api/v2/tasks/${taskId}`)
}

/**
 * 恢复挂起的任务
 */
export function resumeTask(taskId: string) {
  return ApiClient.post<{ success: boolean; message: string }>(`/api/v2/tasks/${taskId}/resume`)
}

/**
 * 任务类型中文名称映射
 */
export const TaskTypeNames: Record<TaskType, string> = {
  [TaskType.STOCK_ANALYSIS]: '股票分析',
  [TaskType.POSITION_ANALYSIS]: '持仓分析',
  [TaskType.TRADE_REVIEW]: '交易复盘',
  [TaskType.PORTFOLIO_HEALTH]: '组合健康度',
  [TaskType.RISK_ASSESSMENT]: '风险评估',
  [TaskType.MARKET_OVERVIEW]: '市场概览',
  [TaskType.SECTOR_ANALYSIS]: '板块分析'
}

/**
 * 任务状态中文名称映射
 */
export const TaskStatusNames: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '等待中',
  [TaskStatus.PROCESSING]: '进行中',
  [TaskStatus.COMPLETED]: '已完成',
  [TaskStatus.FAILED]: '失败',
  [TaskStatus.CANCELLED]: '已取消',
  [TaskStatus.SUSPENDED]: '已挂起'
}

/**
 * 任务状态颜色映射
 */
export const TaskStatusColors: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: 'info',
  [TaskStatus.PROCESSING]: 'warning',
  [TaskStatus.COMPLETED]: 'success',
  [TaskStatus.FAILED]: 'danger',
  [TaskStatus.CANCELLED]: 'info',
  [TaskStatus.SUSPENDED]: 'warning'
}

