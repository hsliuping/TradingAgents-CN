/**
 * 数据库管理API
 */

import { ApiClient } from './request'
import { useAuthStore } from '@/stores/auth'

// 数据库状态接口
export interface DatabaseStatus {
  mongodb: {
    connected: boolean
    host: string
    port: number
    database: string
    version?: string
    uptime?: number
    connections?: any
    memory?: any
    connected_at?: string
    error?: string
  }
  redis: {
    connected: boolean
    host: string
    port: number
    database: number
    version?: string
    uptime?: number
    memory_used?: number
    memory_peak?: number
    connected_clients?: number
    total_commands?: number
    error?: string
  }
}

// 数据库统计接口
export interface DatabaseStats {
  total_collections: number
  total_documents: number
  total_size: number
  collections: Array<{
    name: string
    documents: number
    size: number
    storage_size: number
    indexes: number
    index_size: number
  }>
}

// 备份信息接口
export interface BackupInfo {
  id: string
  name: string
  filename: string
  size: number
  collections: string[]
  created_at: string
  created_by?: string
}

// 连接测试结果接口
export interface ConnectionTestResult {
  mongodb: {
    success: boolean
    response_time_ms?: number
    message: string
    error?: string
  }
  redis: {
    success: boolean
    response_time_ms?: number
    message: string
    error?: string
  }
  overall: boolean
}

// 数据库管理API
export const databaseApi = {
  // 获取数据库状态
  async getStatus(): Promise<DatabaseStatus> {
    const response = await ApiClient.get<DatabaseStatus>('/api/system/database/status')
    return response.data
  },

  // 获取数据库统计
  async getStats(): Promise<DatabaseStats> {
    const response = await ApiClient.get<DatabaseStats>('/api/system/database/stats')
    return response.data
  },

  // 测试数据库连接
  testConnections(): Promise<{ success: boolean; message: string; data: ConnectionTestResult }> {
    return ApiClient.post('/api/system/database/test')
  },

  // 创建备份
  createBackup(data: {
    name: string
    collections?: string[]
  }): Promise<{ success: boolean; message: string; data: BackupInfo }> {
    return ApiClient.post('/api/system/database/backup', data)
  },

  // 获取备份列表
  getBackups(): Promise<{ success: boolean; data: BackupInfo[] }> {
    return ApiClient.get('/api/system/database/backups')
  },

  // 删除备份
  deleteBackup(backupId: string): Promise<{ success: boolean; message: string }> {
    return ApiClient.delete(`/api/system/database/backups/${backupId}`)
  },

  // 导入数据
  importData(
    file: File,
    options: {
      collection: string
      format?: string
      overwrite?: boolean
    }
  ): Promise<{ success: boolean; message: string; data: any }> {
    const formData = new FormData()
    formData.append('file', file)

    // 🔥 使用 URL 参数传递 collection, format, overwrite
    // FastAPI 的 File 参数和其他参数混用时，其他参数需要通过 Query 传递
    const params = new URLSearchParams({
      collection: options.collection,
      format: options.format || 'json',
      overwrite: String(options.overwrite || false)
    })

    console.log('📤 导入数据请求:', {
      filename: file.name,
      size: file.size,
      collection: options.collection,
      format: options.format,
      overwrite: options.overwrite
    })

    return ApiClient.post(`/api/system/database/import?${params.toString()}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 导出数据
  exportData(options: {
    collections?: string[]
    format?: string
    sanitize?: boolean  // 是否脱敏（清空敏感字段，用于演示系统）
  }): Promise<Blob> {
    const token = useAuthStore().token
    return fetch('/api/system/database/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(options)
    }).then(async (response) => {
      if (!response.ok) {
        throw new Error(`导出数据失败: HTTP ${response.status}`)
      }
      return response.blob()
    })
  },

  // 清理旧数据
  cleanupOldData(days: number = 30): Promise<{
    success: boolean
    message: string
    data: {
      deleted_count: number
      cleaned_collections: string[]
      cutoff_date: string
    }
  }> {
    return ApiClient.post(`/api/system/database/cleanup?days=${days}`)
  },

  // 清理过期分析结果
  cleanupAnalysisResults(days: number = 30): Promise<{
    success: boolean
    message: string
    data: {
      deleted_count: number
      cleaned_collections: string[]
      cutoff_date: string
    }
  }> {
    return ApiClient.post(`/api/system/database/cleanup/analysis?days=${days}`)
  },

  // 清理操作日志
  cleanupOperationLogs(days: number = 90): Promise<{
    success: boolean
    message: string
    data: {
      deleted_count: number
      cleaned_collections: string[]
      cutoff_date: string
    }
  }> {
    return ApiClient.post(`/api/system/database/cleanup/logs?days=${days}`)
  }
}

// 工具函数
export const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export const formatDateTime = (dateTime: string): string => {
  return new Date(dateTime).toLocaleString('zh-CN')
}

export const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) {
    return `${days}天 ${hours}小时 ${minutes}分钟`
  } else if (hours > 0) {
    return `${hours}小时 ${minutes}分钟`
  } else {
    return `${minutes}分钟`
  }
}
