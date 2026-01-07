/**
 * 定时分析配置 API
 */

import request from './request'

export interface ScheduledAnalysisTimeSlot {
  name: string
  cron_expression: string
  enabled: boolean
  group_ids: string[]
  analysis_depth?: number
  quick_analysis_model?: string
  deep_analysis_model?: string
  prompt_template_id?: string
}

export interface ScheduledAnalysisConfig {
  id: string
  user_id: string
  name: string
  description?: string
  enabled: boolean
  time_slots: ScheduledAnalysisTimeSlot[]
  default_group_ids?: string[]
  default_analysis_depth: number
  default_quick_analysis_model: string
  default_deep_analysis_model: string
  default_prompt_template_id?: string
  notify_on_complete: boolean
  notify_on_error: boolean
  send_email: boolean
  created_at: string
  updated_at: string
  last_run_at?: string
}

export interface ScheduledAnalysisConfigCreate {
  name: string
  description?: string
  enabled?: boolean
  time_slots?: ScheduledAnalysisTimeSlot[]
  default_group_ids?: string[]
  default_analysis_depth?: number
  default_quick_analysis_model?: string
  default_deep_analysis_model?: string
  default_prompt_template_id?: string
  notify_on_complete?: boolean
  notify_on_error?: boolean
  send_email?: boolean
}

export interface ScheduledAnalysisConfigUpdate {
  name?: string
  description?: string
  enabled?: boolean
  time_slots?: ScheduledAnalysisTimeSlot[]
  default_group_ids?: string[]
  default_analysis_depth?: number
  default_quick_analysis_model?: string
  default_deep_analysis_model?: string
  default_prompt_template_id?: string
  notify_on_complete?: boolean
  notify_on_error?: boolean
  send_email?: boolean
}

export interface ScheduledAnalysisHistory {
  id: string
  config_id: string
  config_name: string
  time_slot_name: string
  created_at: string
  status: string
  total_count: number
  success_count: number
  failed_count: number
  task_ids: string[]
  result_summary?: Record<string, number>
}

/**
 * 预览 CRON 表达式
 */
export function previewCron(cron_expression: string) {
  return request({
    url: '/api/scheduled-analysis/preview-cron',
    method: 'post',
    data: { cron_expression }
  })
}

/**
 * 获取所有配置
 */
export function getScheduledAnalysisConfigs() {
  return request({
    url: '/api/scheduled-analysis/configs',
    method: 'get'
  })
}

/**
 * 创建配置
 */
export function createScheduledAnalysisConfig(data: ScheduledAnalysisConfigCreate) {
  return request({
    url: '/api/scheduled-analysis/configs',
    method: 'post',
    data
  })
}

/**
 * 获取配置详情
 */
export function getScheduledAnalysisConfig(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}`,
    method: 'get'
  })
}

/**
 * 获取配置执行历史
 */
export function getScheduledAnalysisHistory(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}/history`,
    method: 'get'
  })
}

/**
 * 更新配置
 */
export function updateScheduledAnalysisConfig(configId: string, data: ScheduledAnalysisConfigUpdate) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}`,
    method: 'put',
    data
  })
}

/**
 * 删除配置
 */
export function deleteScheduledAnalysisConfig(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}`,
    method: 'delete'
  })
}

/**
 * 启用配置
 */
export function enableScheduledAnalysisConfig(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}/enable`,
    method: 'post'
  })
}

/**
 * 禁用配置
 */
export function disableScheduledAnalysisConfig(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}/disable`,
    method: 'post'
  })
}

/**
 * 测试执行配置
 */
export function testScheduledAnalysisConfig(configId: string) {
  return request({
    url: `/api/scheduled-analysis/configs/${configId}/test`,
    method: 'post'
  })
}

