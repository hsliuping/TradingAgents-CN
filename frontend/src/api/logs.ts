/**
 * 日志管理 API
 */

import { ApiClient, type ApiResponse } from './request'

const unwrapResponse = <T>(promise: Promise<ApiResponse<T>>): Promise<T> =>
  promise.then((res) => res.data)

export interface LogFileInfo {
  name: string
  path: string
  size: number
  size_mb: number
  modified_at: string
  type: 'error' | 'webapi' | 'worker' | 'access' | 'other'
}

export interface LogContentResponse {
  filename: string
  lines: string[]
  stats: {
    total_lines: number
    filtered_lines: number
    error_count: number
    warning_count: number
    info_count: number
    debug_count: number
  }
}

export interface LogStatistics {
  total_files: number
  total_size_mb: number
  error_files: number
  recent_errors: string[]
  log_types: Record<string, number>
}

export interface LogReadRequest {
  filename: string
  lines?: number
  level?: 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG'
  keyword?: string
  start_time?: string
  end_time?: string
}

export interface LogExportRequest {
  filenames?: string[]
  level?: 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG'
  start_time?: string
  end_time?: string
  format?: 'zip' | 'txt'
}

export const LogsApi = {
  /**
   * 获取日志文件列表
   */
  listLogFiles(): Promise<LogFileInfo[]> {
    return unwrapResponse(ApiClient.get<LogFileInfo[]>('/api/system/system-logs/files'))
  },

  /**
   * 读取日志文件内容
   */
  readLogFile(request: LogReadRequest): Promise<LogContentResponse> {
    return unwrapResponse(ApiClient.post<LogContentResponse>('/api/system/system-logs/read', request))
  },

  /**
   * 导出日志文件
   */
  async exportLogs(request: LogExportRequest): Promise<Blob> {
    const response = await fetch('/api/system/system-logs/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    })
    if (!response.ok) {
      throw new Error(`导出日志失败: HTTP ${response.status}`)
    }
    return await response.blob()
  },

  /**
   * 获取日志统计信息
   */
  getStatistics(days: number = 7): Promise<LogStatistics> {
    return unwrapResponse(ApiClient.get<LogStatistics>('/api/system/system-logs/statistics', { days }))
  },

  /**
   * 删除日志文件
   */
  deleteLogFile(filename: string): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.delete<{ success: boolean; message: string }>(`/api/system/system-logs/files/${filename}`))
  }
}

