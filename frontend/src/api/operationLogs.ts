/**
 * 操作日志API接口
 */

import { ApiClient } from './request'

// 操作日志数据类型
export interface OperationLog {
  id: string
  user_id: string
  username: string
  action_type: string
  action: string
  details?: Record<string, any>
  success: boolean
  error_message?: string
  duration_ms?: number
  ip_address?: string
  user_agent?: string
  session_id?: string
  timestamp: string
  created_at: string
}

// 操作日志查询参数
export interface OperationLogQuery {
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
  action_type?: string
  success?: boolean
  keyword?: string
}

// 操作日志列表响应
export interface OperationLogListResponse {
  success: boolean
  data: {
    logs: OperationLog[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }
  message: string
}

// 操作日志统计
export interface OperationLogStats {
  total_logs: number
  success_logs: number
  failed_logs: number
  success_rate: number
  action_type_distribution: Record<string, number>
  hourly_distribution: Array<{
    hour: string
    count: number
  }>
}

// 操作日志统计响应
export interface OperationLogStatsResponse {
  success: boolean
  data: OperationLogStats
  message: string
}

// 创建操作日志请求
export interface CreateOperationLogRequest {
  action_type: string
  action: string
  details?: Record<string, any>
  success?: boolean
  error_message?: string
  duration_ms?: number
  session_id?: string
}

// 清空日志请求
export interface ClearLogsRequest {
  days?: number
  action_type?: string
}

// 清空日志响应
export interface ClearLogsResponse {
  success: boolean
  data: {
    deleted_count: number
    filter: Record<string, any>
  }
  message: string
}

// 操作日志API类
export class OperationLogsApi {
  /**
   * 获取操作日志列表
   */
  static getOperationLogs(params: OperationLogQuery = {}): Promise<OperationLogListResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.action_type) queryParams.append('action_type', params.action_type)
    if (params.success !== undefined) queryParams.append('success', params.success.toString())
    if (params.keyword) queryParams.append('keyword', params.keyword)
    
    const url = `/api/system/logs/list${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return ApiClient.get(url)
  }

  /**
   * 获取操作日志统计
   */
  static getOperationLogStats(days: number = 30): Promise<OperationLogStatsResponse> {
    return ApiClient.get(`/api/system/logs/stats?days=${days}`)
  }

  /**
   * 获取操作日志详情
   */
  static getOperationLogDetail(logId: string): Promise<{
    success: boolean
    data: OperationLog
    message: string
  }> {
    return ApiClient.get(`/api/system/logs/${logId}`)
  }

  /**
   * 创建操作日志
   */
  static createOperationLog(data: CreateOperationLogRequest): Promise<{
    success: boolean
    data: { log_id: string }
    message: string
  }> {
    return ApiClient.post('/api/system/logs/create', data)
  }

  /**
   * 清空操作日志
   */
  static clearOperationLogs(data: ClearLogsRequest = {}): Promise<ClearLogsResponse> {
    return ApiClient.post('/api/system/logs/clear', data)
  }

  /**
   * 导出操作日志为CSV
   */
  static exportOperationLogsCSV(params: {
    start_date?: string
    end_date?: string
    action_type?: string
  } = {}): Promise<Blob> {
    const queryParams = new URLSearchParams()
    
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.action_type) queryParams.append('action_type', params.action_type)
    
    const url = `/api/system/logs/export/csv${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return ApiClient.get(url, { responseType: 'blob' })
  }
}

// 操作类型常量
export const ActionTypes = {
  STOCK_ANALYSIS: 'stock_analysis',
  CONFIG_MANAGEMENT: 'config_management',
  CACHE_OPERATION: 'cache_operation',
  DATA_IMPORT: 'data_import',
  DATA_EXPORT: 'data_export',
  SYSTEM_SETTINGS: 'system_settings',
  USER_LOGIN: 'user_login',
  USER_LOGOUT: 'user_logout',
  USER_MANAGEMENT: 'user_management',  // 🔧 添加用户管理操作类型
  DATABASE_OPERATION: 'database_operation',
  SCREENING: 'screening',
  REPORT_GENERATION: 'report_generation'
} as const

// 操作类型名称映射
export const ActionTypeNames = {
  [ActionTypes.STOCK_ANALYSIS]: '股票分析',
  [ActionTypes.CONFIG_MANAGEMENT]: '配置管理',
  [ActionTypes.CACHE_OPERATION]: '缓存操作',
  [ActionTypes.DATA_IMPORT]: '数据导入',
  [ActionTypes.DATA_EXPORT]: '数据导出',
  [ActionTypes.SYSTEM_SETTINGS]: '系统设置',
  [ActionTypes.USER_LOGIN]: '用户登录',
  [ActionTypes.USER_LOGOUT]: '用户登出',
  [ActionTypes.USER_MANAGEMENT]: '用户管理',  // 🔧 添加用户管理操作类型名称
  [ActionTypes.DATABASE_OPERATION]: '数据库操作',
  [ActionTypes.SCREENING]: '股票筛选',
  [ActionTypes.REPORT_GENERATION]: '报告生成'
} as const

// 操作类型标签颜色映射
export const ActionTypeTagColors = {
  [ActionTypes.STOCK_ANALYSIS]: 'primary',
  [ActionTypes.CONFIG_MANAGEMENT]: 'success',
  [ActionTypes.CACHE_OPERATION]: 'warning',
  [ActionTypes.DATA_IMPORT]: 'info',
  [ActionTypes.DATA_EXPORT]: 'info',
  [ActionTypes.SYSTEM_SETTINGS]: 'danger',
  [ActionTypes.USER_LOGIN]: 'success',
  [ActionTypes.USER_LOGOUT]: 'warning',
  [ActionTypes.USER_MANAGEMENT]: 'warning',  // 🔧 添加用户管理操作类型颜色
  [ActionTypes.DATABASE_OPERATION]: 'primary',
  [ActionTypes.SCREENING]: 'info',
  [ActionTypes.REPORT_GENERATION]: 'primary'
} as const

// 便捷函数
export const getActionTypeName = (actionType: string): string => {
  return ActionTypeNames[actionType as keyof typeof ActionTypeNames] || actionType
}

export const getActionTypeTagColor = (actionType: string): string => {
  return ActionTypeTagColors[actionType as keyof typeof ActionTypeTagColors] || 'info'
}

// 格式化时间（导入统一的时间格式化工具）
import { formatDateTime as formatDateTimeUtil } from '@/utils/datetime'

export const formatDateTime = (timestamp: string | number): string => {
  return formatDateTimeUtil(timestamp)
}

// 默认导出
export default OperationLogsApi
