// 配置管理相关类型定义

// 大模型厂家
export interface LLMProvider {
  id: string
  name: string
  display_name: string
  description?: string
  website?: string
  api_doc_url?: string
  logo_url?: string
  is_active: boolean
  supported_features: string[]
  default_base_url?: string
  api_key?: string
  api_secret?: string
  extra_config?: Record<string, any>

  // 🆕 聚合渠道支持
  is_aggregator?: boolean
  aggregator_type?: string
  model_name_format?: string

  created_at?: string
  updated_at?: string
}

// 大模型配置
export interface LLMConfig {
  name: string
  provider: string
  model_name: string
  api_key?: string  // 可选，优先从厂家配置获取
  base_url?: string
  max_tokens?: number
  temperature?: number
  timeout?: number
  is_default?: boolean
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

// 数据源配置
export interface DataSourceConfig {
  name: string
  type: string
  config: Record<string, any>
  is_default?: boolean
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

// 数据库配置
export interface DatabaseConfig {
  name: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

// 系统配置
export interface SystemConfig {
  app_name: string
  version: string
  debug: boolean
  log_level: string
  max_concurrent_analyses: number
  default_timeout: number
  cache_enabled: boolean
  cache_ttl: number
}

// 配置测试请求
export interface ConfigTestRequest {
  type: 'llm' | 'datasource' | 'database'
  config: Record<string, any>
}

// 配置测试响应
export interface ConfigTestResponse {
  success: boolean
  message: string
  details?: Record<string, any>
  latency?: number
}
