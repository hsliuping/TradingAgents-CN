/**
 * MCP服务器管理API接口
 * 提供MCP配置管理和服务器状态控制功能
 *
 * Copyright (c) 2025 TradingAgents-CN. All rights reserved.
 */

import type { ApiResponse } from './request'
import { ApiClient } from './request'

// MCP配置接口定义
export interface McpConfiguration {
  mcpServers: Record<string, McpServerConfig>
}

export interface McpServerConfig {
  type?: 'stdio' | 'http' | 'streamable-http'
  command?: string
  args?: string[]
  url?: string
  headers?: Record<string, string>
  env?: Record<string, string>
  enabled?: boolean
  autoConnect?: boolean
  timeout?: number
}

export interface McpServerStatus {
  name: string
  status: 'online' | 'offline' | 'checking'
  lastCheck: string
  responseTime?: number
  errorMessage?: string
  framework?: string  // 添加框架字段
  tools_count?: number  // 添加工具数量字段
  connection_tested?: boolean  // 添加连接测试字段
  warning?: string  // 添加警告字段
}

export interface McpValidationResult {
  success: boolean
  valid: boolean
  errors: string[]
  warnings: string[]
}

export interface McpTestResult {
  serverName: string
  connectionSuccess: boolean
  responseTime?: number
  message?: string
  error?: string
}

/**
 * MCP API接口封装
 */
export const mcpApi = {
  /**
   * 获取MCP配置
   * @returns MCP配置数据
   */
  getConfig: (): Promise<ApiResponse<McpConfiguration>> =>
    ApiClient.get('/api/mcp/config'),

  /**
   * 保存MCP配置
   * @param config MCP配置数据
   * @returns 保存操作结果
   */
  saveConfig: (config: McpConfiguration): Promise<ApiResponse<void>> =>
    ApiClient.post('/api/mcp/config', config),

  /**
   * 验证MCP配置格式
   * @param config 待验证的配置数据
   * @returns 验证结果
   */
  validateConfig: (config: McpConfiguration | Record<string, any>): Promise<ApiResponse<McpValidationResult>> =>
    ApiClient.post('/api/mcp/config/validate', config),

  /**
   * 获取所有服务器状态
   * @returns 服务器状态列表
   */
  getServersStatus: (): Promise<ApiResponse<McpServerStatus[]>> =>
    ApiClient.get('/api/mcp/servers'),

  /**
   * 刷新所有服务器状态
   * @returns 刷新后的服务器状态列表
   */
  refreshAllStatus: (): Promise<ApiResponse<McpServerStatus[]>> =>
    ApiClient.post('/api/mcp/servers/refresh'),

  /**
   * 获取单个服务器状态
   * @param serverName 服务器名称
   * @returns 服务器状态信息
   */
  getServerStatus: (serverName: string): Promise<ApiResponse<McpServerStatus>> =>
    ApiClient.get(`/api/mcp/servers/${serverName}/status`),

  /**
   * 切换服务器启用状态
   * @param serverName 服务器名称
   * @param enabled 是否启用
   * @returns 操作结果
   */
  toggleServer: (serverName: string, enabled: boolean): Promise<ApiResponse<void>> =>
    ApiClient.post(`/api/mcp/servers/${serverName}/toggle`, { enabled }),

  /**
   * 测试服务器连接
   * @param serverName 服务器名称
   * @returns 连接测试结果
   */
  testServerConnection: (serverName: string): Promise<ApiResponse<McpTestResult>> =>
    ApiClient.post(`/api/mcp/servers/${serverName}/test`),

  /**
   * 获取服务器工具列表
   * @param serverName 服务器名称
   * @returns 工具列表
   */
  getServerTools: (serverName: string): Promise<ApiResponse<any[]>> =>
    ApiClient.get(`/api/mcp/servers/${serverName}/tools`),

  /**
   * 执行服务器工具
   * @param serverName 服务器名称
   * @param toolName 工具名称
   * @param toolArgs 工具参数
   * @returns 执行结果
   */
  executeServerTool: (serverName: string, toolName: string, toolArgs: Record<string, any>): Promise<ApiResponse<any>> =>
    ApiClient.post(`/api/mcp/servers/${serverName}/tools/${toolName}/execute`, { arguments: toolArgs })
}

/**
 * MCP配置工具类
 */
export class McpConfigHelper {
  /**
   * 解析服务器列表从配置
   * @param config MCP配置
   * @returns 服务器状态列表
   */
  static parseServersFromConfig(config: McpConfiguration): McpServerStatus[] {
    const mcpServers = config.mcpServers || {}

    return Object.entries(mcpServers).map(([name, serverConfig]) => ({
      name,
      status: serverConfig.enabled !== false ? 'checking' : 'offline',
      lastCheck: new Date().toISOString(),
      responseTime: undefined,
      errorMessage: serverConfig.enabled === false ? '服务器已禁用' : undefined
    }))
  }

  /**
   * 验证服务器配置格式
   * @param serverName 服务器名称
   * @param serverConfig 服务器配置
   * @returns 验证错误列表
   */
  static validateServerConfig(serverName: string, serverConfig: McpServerConfig): string[] {
    const errors: string[] = []

    if (!serverConfig.type) {
      errors.push(`服务器 ${serverName}: 缺少 type 字段`)
    }

    switch (serverConfig.type) {
      case 'stdio':
        if (!serverConfig.command) {
          errors.push(`STDIO服务器 ${serverName}: 缺少 command 字段`)
        }
        break
      case 'http':
      case 'streamable-http':
        if (!serverConfig.url) {
          errors.push(`HTTP服务器 ${serverName}: 缺少 url 字段`)
        } else if (!serverConfig.url.startsWith('http://') && !serverConfig.url.startsWith('https://')) {
          errors.push(`HTTP服务器 ${serverName}: url 格式无效`)
        }
        break
    }

    return errors
  }

  /**
   * 获取服务器类型标签颜色
   * @param type 服务器类型
   * @returns Element Plus 标签类型
   */
  static getServerTypeTagType(type?: string): 'success' | 'primary' | 'warning' | 'info' | 'danger' {
    switch (type) {
      case 'stdio':
        return 'success'
      case 'http':
        return 'primary'
      case 'streamable-http':
        return 'warning'
      default:
        return 'info'
    }
  }

  /**
   * 获取服务器状态文本
   * @param server 服务器状态
   * @returns 状态描述文本
   */
  static getServerStatusText(server: McpServerStatus): string {
    switch (server.status) {
      case 'checking':
        return '检测中'
      case 'online':
        return server.responseTime ? `在线 (${server.responseTime}ms)` : '在线'
      case 'offline':
        return server.errorMessage || '离线'
      default:
        return '未知'
    }
  }

  /**
   * 格式化JSON配置
   * @param jsonString JSON字符串
   * @returns 格式化后的JSON字符串
   * @throws JSON解析错误
   */
  static formatJson(jsonString: string): string {
    const parsed = JSON.parse(jsonString)
    return JSON.stringify(parsed, null, 2)
  }

  /**
   * 验证JSON格式
   * @param jsonString JSON字符串
   * @returns 验证结果
   */
  static validateJson(jsonString: string): { valid: boolean; error?: string } {
    try {
      JSON.parse(jsonString)
      return { valid: true }
    } catch (error: any) {
      return {
        valid: false,
        error: `JSON格式错误: ${error.message}`
      }
    }
  }
}

export default mcpApi