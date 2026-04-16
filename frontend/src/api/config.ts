/**
 * 配置管理API
 */

import { ApiClient } from './request'
import type { ApiResponse } from './request'

// 配置相关类型定义

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
  extra_config?: {
    has_api_key?: boolean
    source?: 'environment' | 'database'
    [key: string]: any
  }
  // 🆕 聚合渠道支持
  is_aggregator?: boolean
  aggregator_type?: string
  model_name_format?: string
  created_at?: string
  updated_at?: string
}

export interface LLMConfig {
  provider: string
  model_name: string
  model_display_name?: string  // 新增：模型显示名称
  api_key?: string  // 可选，优先从厂家配置获取
  api_base?: string
  max_tokens: number
  temperature: number
  timeout: number
  retry_times: number
  enabled: boolean
  description?: string
  // 定价配置
  input_price_per_1k?: number
  output_price_per_1k?: number
  currency?: string
  // 高级配置
  enable_memory?: boolean
  enable_debug?: boolean
  priority?: number
  model_category?: string
  // 🆕 模型能力分级系统
  capability_level?: number  // 模型能力等级(1-5): 1=基础, 2=标准, 3=高级, 4=专业, 5=旗舰
  suitable_roles?: string[]  // 适用角色: quick_analysis(快速分析), deep_analysis(深度分析), both(两者都适合)
  features?: string[]  // 模型特性: tool_calling, long_context, reasoning, vision, fast_response, cost_effective
  recommended_depths?: string[]  // 推荐的分析深度级别: 快速, 基础, 标准, 深度, 全面
  performance_metrics?: {  // 性能指标
    speed?: number  // 速度(1-5)
    cost?: number  // 成本(1-5)
    quality?: number  // 质量(1-5)
  }
  created_at?: string
  updated_at?: string
}

export interface FetchProviderModelsRequest {
  type?: string
  modalities?: string
  features?: string[]
  provider_names?: string[]
  model_keyword?: string
  sort_by?: string
  sort_order?: string
  limit?: number
  recommended_only?: boolean
  tools_only?: boolean
  exclude_preview?: boolean
}

export interface DataSourceConfig {
  name: string
  type: string
  api_key?: string
  api_secret?: string
  endpoint?: string
  timeout: number
  rate_limit: number
  enabled: boolean
  priority: number
  config_params: Record<string, any>
  description?: string
  // 新增字段：支持市场分类
  market_categories?: string[]  // 所属市场分类列表
  display_name?: string         // 显示名称
  provider?: string            // 数据提供商
  created_at?: string
  updated_at?: string
}

// 市场分类配置
export interface MarketCategory {
  id: string
  name: string
  display_name: string
  description?: string
  enabled: boolean
  sort_order: number
  created_at?: string
  updated_at?: string
}

// 数据源分组关系
export interface DataSourceGrouping {
  data_source_name: string
  market_category_id: string
  priority: number              // 在该分类中的优先级
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface DatabaseConfig {
  name: string
  type: string
  host: string
  port: number
  username?: string
  password?: string
  database?: string
  connection_params: Record<string, any>
  pool_size: number
  max_overflow: number
  enabled: boolean
  description?: string
}

export interface SystemConfig {
  config_name: string
  config_type: string
  llm_configs: LLMConfig[]
  default_llm?: string
  data_source_configs: DataSourceConfig[]
  default_data_source?: string
  database_configs: DatabaseConfig[]
  system_settings: Record<string, any>
  created_at: string
  updated_at: string
  version: number
  is_active: boolean
}

export interface ConfigTestRequest {
  config_type: 'llm' | 'datasource' | 'database'
  config_data: Record<string, any>
}

export interface ConfigTestResponse {
  success: boolean
  message: string
  details?: Record<string, any>
}


// 系统设置元数据
export interface SettingMeta {
  key: string
  sensitive: boolean
  editable: boolean
  source: 'environment' | 'database' | 'default'
  has_value: boolean
}

const unwrapResponse = <T>(promise: Promise<ApiResponse<T>>): Promise<T> =>
  promise.then((res) => res.data)

// 配置管理API
export const configApi = {
  // 获取系统配置
  getSystemConfig(): Promise<SystemConfig> {
    return unwrapResponse(ApiClient.get<SystemConfig>('/api/config/system'))
  },

  // ========== 大模型厂家管理 ==========

  // 获取所有大模型厂家
  getLLMProviders(): Promise<LLMProvider[]> {
    return unwrapResponse(ApiClient.get<LLMProvider[]>('/api/config/llm/providers'))
  },

  // 添加大模型厂家
  addLLMProvider(provider: Partial<LLMProvider>): Promise<{ message: string; id: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; id: string }>('/api/config/llm/providers', provider))
  },

  // 更新大模型厂家
  updateLLMProvider(id: string, provider: Partial<LLMProvider>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>(`/api/config/llm/providers/${id}`, provider))
  },

  // 删除大模型厂家
  deleteLLMProvider(id: string): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.delete<{ message: string }>(`/api/config/llm/providers/${id}`))
  },

  // 启用/禁用大模型厂家
  toggleLLMProvider(id: string, isActive: boolean): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.patch<{ message: string }>(`/api/config/llm/providers/${id}/toggle`, { is_active: isActive }))
  },

  // 迁移环境变量到厂家管理
  migrateEnvToProviders(): Promise<{ message: string; data: any }> {
    return unwrapResponse(ApiClient.post<{ message: string; data: any }>('/api/config/llm/providers/migrate-env'))
  },

  // 🆕 初始化聚合渠道厂家配置
  initAggregatorProviders(): Promise<{ success: boolean; message: string; data: { added_count: number; skipped_count: number } }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string; data: { added_count: number; skipped_count: number } }>('/api/config/llm/providers/init-aggregators'))
  },

  // 测试厂家API
  testProviderAPI(providerId: string): Promise<{ success: boolean; message: string; data?: any }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string; data?: any }>(`/api/config/llm/providers/${providerId}/test`))
  },

  // 获取可用的模型列表（按厂家分组）
  getAvailableModels(): Promise<Array<{
    provider: string
    provider_name: string
    models: Array<{ name: string; display_name: string }>
  }>> {
    return unwrapResponse(ApiClient.get<Array<{
      provider: string
      provider_name: string
      models: Array<{ name: string; display_name: string }>
    }>>('/api/config/models'))
  },

  // ========== 模型目录管理 ==========

  // 获取所有模型目录
  getModelCatalog(): Promise<Array<{
    provider: string
    provider_name: string
    models: Array<{
      name: string
      display_name: string
      description?: string
      context_length?: number
      max_tokens?: number
      input_price_per_1k?: number
      output_price_per_1k?: number
      currency?: string
      is_deprecated?: boolean
      release_date?: string
      capabilities?: string[]
    }>
  }>> {
    return unwrapResponse(ApiClient.get<Array<{
      provider: string
      provider_name: string
      models: Array<{
        name: string
        display_name: string
        description?: string
        context_length?: number
        max_tokens?: number
        input_price_per_1k?: number
        output_price_per_1k?: number
        currency?: string
        is_deprecated?: boolean
        release_date?: string
        capabilities?: string[]
      }>
    }>>('/api/config/model-catalog'))
  },

  // 获取指定厂家的模型目录
  getProviderModelCatalog(provider: string): Promise<{
    provider: string
    provider_name: string
    models: Array<{
      name: string
      display_name: string
      description?: string
      context_length?: number
      max_tokens?: number
      input_price_per_1k?: number
      output_price_per_1k?: number
      currency?: string
      is_deprecated?: boolean
      release_date?: string
      capabilities?: string[]
    }>
  }> {
    return unwrapResponse(ApiClient.get<{
      provider: string
      provider_name: string
      models: Array<{
        name: string
        display_name: string
        description?: string
        context_length?: number
        max_tokens?: number
        input_price_per_1k?: number
        output_price_per_1k?: number
        currency?: string
        is_deprecated?: boolean
        release_date?: string
        capabilities?: string[]
      }>
    }>(`/api/config/model-catalog/${provider}`))
  },

  // 保存模型目录
  saveModelCatalog(catalog: {
    provider: string
    provider_name: string
    models: Array<{ name: string; display_name: string; description?: string }>
  }): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string }>('/api/config/model-catalog', catalog))
  },

  // 删除模型目录
  deleteModelCatalog(provider: string): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.delete<{ success: boolean; message: string }>(`/api/config/model-catalog/${provider}`))
  },

  // 初始化默认模型目录
  initModelCatalog(): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string }>('/api/config/model-catalog/init'))
  },

  // 从厂家 API 获取模型列表
  fetchProviderModels(provider: string, filters?: FetchProviderModelsRequest): Promise<{
    success: boolean
    message?: string
    models?: Array<{
      id: string
      name: string
      context_length?: number
      max_tokens?: number
      description?: string
      capabilities?: string[]
      input_price_per_1k?: number
      output_price_per_1k?: number
      currency?: string
    }>
  }> {
    return unwrapResponse(ApiClient.post<{
      success: boolean
      message?: string
      models?: Array<{
        id: string
        name: string
        context_length?: number
        max_tokens?: number
        description?: string
        capabilities?: string[]
        input_price_per_1k?: number
        output_price_per_1k?: number
        currency?: string
      }>
    }>(`/api/config/llm/providers/${provider}/fetch-models`, filters || {}))
  },

  // ========== 大模型配置管理 ==========

  // 获取所有大模型配置
  getLLMConfigs(): Promise<LLMConfig[]> {
    return unwrapResponse(ApiClient.get<LLMConfig[]>('/api/config/llm'))
  },

  // 添加或更新大模型配置
  updateLLMConfig(config: Partial<LLMConfig>): Promise<{ message: string; model_name: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; model_name: string }>('/api/config/llm', config))
  },

  // 删除大模型配置
  deleteLLMConfig(provider: string, modelName: string): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.delete<{ message: string }>(`/api/config/llm/${provider}/${modelName}`))
  },

  // 设置默认大模型
  setDefaultLLM(name: string): Promise<{ message: string; default_llm: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; default_llm: string }>('/api/config/llm/set-default', { name }))
  },

  // 获取所有数据源配置
  getDataSourceConfigs(): Promise<DataSourceConfig[]> {
    return unwrapResponse(ApiClient.get<DataSourceConfig[]>('/api/config/datasource'))
  },

  // 添加数据源配置
  addDataSourceConfig(config: Partial<DataSourceConfig>): Promise<{ message: string; name: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; name: string }>('/api/config/datasource', config))
  },

  // 设置默认数据源
  setDefaultDataSource(name: string): Promise<{ message: string; default_data_source: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; default_data_source: string }>('/api/config/datasource/set-default', { name }))
  },

  // 更新数据源配置
  updateDataSourceConfig(name: string, config: Partial<DataSourceConfig>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>(`/api/config/datasource/${name}`, config))
  },

  // 删除数据源配置
  deleteDataSourceConfig(name: string): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.delete<{ message: string }>(`/api/config/datasource/${name}`))
  },

  // 市场分类管理
  getMarketCategories(): Promise<MarketCategory[]> {
    return unwrapResponse(ApiClient.get<MarketCategory[]>('/api/config/market-categories'))
  },

  addMarketCategory(category: Partial<MarketCategory>): Promise<{ message: string; id: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; id: string }>('/api/config/market-categories', category))
  },

  updateMarketCategory(id: string, category: Partial<MarketCategory>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>(`/api/config/market-categories/${id}`, category))
  },

  deleteMarketCategory(id: string): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.delete<{ message: string }>(`/api/config/market-categories/${id}`))
  },

  // 数据源分组管理
  getDataSourceGroupings(): Promise<DataSourceGrouping[]> {
    return unwrapResponse(ApiClient.get<DataSourceGrouping[]>('/api/config/datasource-groupings'))
  },

  addDataSourceToCategory(dataSourceName: string, categoryId: string, priority?: number): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.post<{ message: string }>('/api/config/datasource-groupings', {
      data_source_name: dataSourceName,
      market_category_id: categoryId,
      priority: priority || 0,
      enabled: true
    }))
  },

  removeDataSourceFromCategory(dataSourceName: string, categoryId: string): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.delete<{ message: string }>(`/api/config/datasource-groupings/${dataSourceName}/${categoryId}`))
  },

  updateDataSourceGrouping(dataSourceName: string, categoryId: string, updates: Partial<DataSourceGrouping>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>(`/api/config/datasource-groupings/${dataSourceName}/${categoryId}`, updates))
  },

  // 批量更新分类内数据源排序
  updateCategoryDataSourceOrder(categoryId: string, orderedDataSources: Array<{name: string, priority: number}>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>(`/api/config/market-categories/${categoryId}/datasource-order`, {
      data_sources: orderedDataSources
    }))
  },

  // 获取系统设置元数据
  getSystemSettingsMeta(): Promise<{ items: SettingMeta[] }> {
    return unwrapResponse(ApiClient.get<{ items: SettingMeta[] }>('/api/config/settings/meta'))
  },


  // ========== 数据库配置管理 ==========

  // 获取所有数据库配置
  getDatabaseConfigs(): Promise<DatabaseConfig[]> {
    return unwrapResponse(ApiClient.get<DatabaseConfig[]>('/api/config/database'))
  },

  // 获取指定的数据库配置
  getDatabaseConfig(dbName: string): Promise<DatabaseConfig> {
    return unwrapResponse(ApiClient.get<DatabaseConfig>(`/api/config/database/${encodeURIComponent(dbName)}`))
  },

  // 添加数据库配置
  addDatabaseConfig(config: Partial<DatabaseConfig>): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string }>('/api/config/database', config))
  },

  // 更新数据库配置
  updateDatabaseConfig(dbName: string, config: Partial<DatabaseConfig>): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.put<{ success: boolean; message: string }>(`/api/config/database/${encodeURIComponent(dbName)}`, config))
  },

  // 删除数据库配置
  deleteDatabaseConfig(dbName: string): Promise<{ success: boolean; message: string }> {
    return unwrapResponse(ApiClient.delete<{ success: boolean; message: string }>(`/api/config/database/${encodeURIComponent(dbName)}`))
  },

  // 测试数据库配置连接
  testDatabaseConfig(dbName: string): Promise<ConfigTestResponse> {
    return unwrapResponse(ApiClient.post<ConfigTestResponse>(`/api/config/database/${encodeURIComponent(dbName)}/test`))
  },

  // 获取系统设置
  getSystemSettings(): Promise<Record<string, any>> {
    return unwrapResponse(ApiClient.get<Record<string, any>>('/api/config/settings'))
  },

  // 获取默认模型配置
  getDefaultModels(): Promise<{ quick_analysis_model: string; deep_analysis_model: string }> {
    return unwrapResponse(ApiClient.get<Record<string, any>>('/api/config/settings')).then(settings => ({
      quick_analysis_model: settings.quick_analysis_model || 'qwen-turbo',
      deep_analysis_model: settings.deep_analysis_model || 'qwen-max'
    }))
  },

  // 更新系统设置
  updateSystemSettings(settings: Record<string, any>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.put<{ message: string }>('/api/config/settings', settings))
  },

  // 测试配置连接
  testConfig(testRequest: ConfigTestRequest): Promise<ConfigTestResponse> {
    return unwrapResponse(ApiClient.post<ConfigTestResponse>('/api/config/test', testRequest))
  },

  // 导出配置
  exportConfig(): Promise<{ message: string; data: any; exported_at: string }> {
    return unwrapResponse(ApiClient.post<{ message: string; data: any; exported_at: string }>('/api/config/export'))
  },

  // 导入配置
  importConfig(configData: Record<string, any>): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.post<{ message: string }>('/api/config/import', configData))
  },

  // 迁移传统配置
  migrateLegacyConfig(): Promise<{ message: string }> {
    return unwrapResponse(ApiClient.post<{ message: string }>('/api/config/migrate-legacy'))
  },

  // 配置重载
  reloadConfig(): Promise<{ success: boolean; message: string; data?: any }> {
    return unwrapResponse(ApiClient.post<{ success: boolean; message: string; data?: any }>('/api/config/reload'))
  }
}

// 配置相关的常量
export const CONFIG_PROVIDERS = {
  OPENAI: 'openai',
  QWEN: 'qwen',
  GLM: 'glm',
  GEMINI: 'gemini',
  CLAUDE: 'claude'
} as const

/**
 * 数据源类型常量
 *
 * 注意：这些常量与后端 DataSourceType 枚举保持同步
 * 添加新数据源时，请先在后端 tradingagents/constants/data_sources.py 中注册
 */
export const DATA_SOURCE_TYPES = {
  // 缓存数据源
  MONGODB: 'mongodb',

  // 中国市场数据源
  TUSHARE: 'tushare',
  AKSHARE: 'akshare',
  BAOSTOCK: 'baostock',

  // 美股数据源
  FINNHUB: 'finnhub',
  YAHOO_FINANCE: 'yahoo_finance',
  ALPHA_VANTAGE: 'alpha_vantage',
  IEX_CLOUD: 'iex_cloud',

  // 专业数据源
  WIND: 'wind',
  CHOICE: 'choice',

  // 其他数据源
  QUANDL: 'quandl',
  LOCAL_FILE: 'local_file',
  CUSTOM: 'custom'
} as const

export const DATABASE_TYPES = {
  MONGODB: 'mongodb',
  REDIS: 'redis',
  MYSQL: 'mysql',
  POSTGRESQL: 'postgresql'
} as const

// 默认配置模板
export const DEFAULT_LLM_CONFIG: Partial<LLMConfig> = {
  max_tokens: 4000,
  temperature: 0.7,
  timeout: 60,
  retry_times: 3,
  enabled: true
}

export const DEFAULT_DATA_SOURCE_CONFIG: Partial<DataSourceConfig> = {
  timeout: 30,
  rate_limit: 100,
  enabled: true,
  priority: 0,
  config_params: {},
  market_categories: []
}

// 默认市场分类
export const DEFAULT_MARKET_CATEGORIES: Partial<MarketCategory>[] = [
  {
    id: 'a_shares',
    name: 'a_shares',
    display_name: 'A股',
    description: '中国A股市场数据源',
    enabled: true,
    sort_order: 1
  },
  {
    id: 'us_stocks',
    name: 'us_stocks',
    display_name: '美股',
    description: '美国股票市场数据源',
    enabled: true,
    sort_order: 2
  },
  {
    id: 'hk_stocks',
    name: 'hk_stocks',
    display_name: '港股',
    description: '香港股票市场数据源',
    enabled: true,
    sort_order: 3
  },
  {
    id: 'crypto',
    name: 'crypto',
    display_name: '数字货币',
    description: '数字货币市场数据源',
    enabled: true,
    sort_order: 4
  },
  {
    id: 'futures',
    name: 'futures',
    display_name: '期货',
    description: '期货市场数据源',
    enabled: true,
    sort_order: 5
  }
]

export const DEFAULT_DATABASE_CONFIG: Partial<DatabaseConfig> = {
  pool_size: 10,
  max_overflow: 20,
  enabled: true,
  connection_params: {}
}

// 配置验证函数
export const validateLLMConfig = (config: Partial<LLMConfig>): string[] => {
  const errors: string[] = []

  if (!config.provider) errors.push('供应商不能为空')
  if (!config.model_name) errors.push('模型名称不能为空')
  // 注意：API密钥不在这里验证，因为它是在厂家配置中管理的
  if (config.max_tokens && config.max_tokens <= 0) errors.push('最大Token数必须大于0')
  if (config.temperature && (config.temperature < 0 || config.temperature > 2)) {
    errors.push('温度参数必须在0-2之间')
  }

  return errors
}

export const validateDataSourceConfig = (config: Partial<DataSourceConfig>): string[] => {
  const errors: string[] = []

  if (!config.name) errors.push('数据源名称不能为空')
  if (!config.type) errors.push('数据源类型不能为空')
  if (config.timeout && config.timeout <= 0) errors.push('超时时间必须大于0')
  if (config.rate_limit && config.rate_limit <= 0) errors.push('速率限制必须大于0')

  return errors
}

export const validateDatabaseConfig = (config: Partial<DatabaseConfig>): string[] => {
  const errors: string[] = []

  if (!config.name) errors.push('数据库名称不能为空')
  if (!config.type) errors.push('数据库类型不能为空')
  if (!config.host) errors.push('主机地址不能为空')
  if (!config.port || config.port <= 0) errors.push('端口号必须大于0')
  if (config.pool_size && config.pool_size <= 0) errors.push('连接池大小必须大于0')

  return errors
}
