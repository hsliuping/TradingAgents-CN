/**
 * 配置管理API
 */

import { ApiClient } from './request'

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
  embedding_model?: string  // 🔥 新增：Embedding 模型名称
  test_model?: string  // 🔥 新增：测试模型名称（用于测试API连接，如果未填写则使用系统默认值）
  api_key?: string  // 🔥 新增：API Key（可选，用于测试连接或覆盖环境变量）
  api_secret?: string  // 🔥 新增：API Secret（某些厂家需要，如百度千帆）
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
  config_id?: string
  provider: string
  provider_name?: string
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
}

export interface FetchProviderModelsFilters {
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


// Gateway 平台配置
export interface GatewayConfig {
  platform: string
  app_id: string
  app_secret: string
  bot_secret: string
  connection_mode: string   // 'webhook' | 'websocket'
  enabled: boolean
  configured: boolean
  // 飞书专属
  verification_token?: string
  encrypt_key?: string
  // 钉钉专属
  app_key?: string
  robot_code?: string
}

export interface GatewayConfigRequest {
  app_id?: string
  app_secret?: string
  bot_secret?: string
  connection_mode?: string   // 'webhook' | 'websocket'
  enabled: boolean
  // 飞书专属
  verification_token?: string
  encrypt_key?: string
  // 钉钉专属
  app_key?: string
  robot_code?: string
}

// 系统设置元数据
export interface SettingMeta {
  key: string
  sensitive: boolean
  editable: boolean
  source: 'environment' | 'database' | 'default'
  has_value: boolean
}

// 配置管理API
export const configApi = {
  // 获取系统配置
  getSystemConfig(): Promise<SystemConfig> {
    return ApiClient.get('/api/config/system').then((response: any) => response.data ?? response)
  },

  // ========== 大模型厂家管理 ==========

  // 获取所有大模型厂家
  getLLMProviders(): Promise<LLMProvider[]> {
    return ApiClient.get('/api/config/llm/providers').then((response: any) => response.data ?? response)
  },

  // 添加大模型厂家
  addLLMProvider(provider: Partial<LLMProvider>): Promise<{ message: string; id: string }> {
    return ApiClient.post('/api/config/llm/providers', provider) as any
  },

  // 更新大模型厂家
  updateLLMProvider(id: string, provider: Partial<LLMProvider>): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/llm/providers/${id}`, provider)
  },

  // 删除大模型厂家
  deleteLLMProvider(id: string): Promise<{ message: string }> {
    return ApiClient.delete(`/api/config/llm/providers/${id}`)
  },

  // 启用/禁用大模型厂家
  toggleLLMProvider(id: string, isActive: boolean): Promise<{ message: string }> {
    return ApiClient.patch(`/api/config/llm/providers/${id}/toggle`, { is_active: isActive })
  },

  // 迁移环境变量到厂家管理
  migrateEnvToProviders(): Promise<{ message: string; data: any }> {
    return ApiClient.post('/api/config/llm/providers/migrate-env')
  },

  // 🆕 初始化聚合渠道厂家配置
  initAggregatorProviders(): Promise<{ success: boolean; message: string; data: { added_count: number; skipped_count: number } }> {
    return ApiClient.post('/api/config/llm/providers/init-aggregators')
  },

  // 测试厂家API
  testProviderAPI(providerId: string): Promise<{ success: boolean; message: string; data?: any }> {
    return ApiClient.post(`/api/config/llm/providers/${providerId}/test`)
  },

  // 🔥 新增：获取所有支持 embedding 的厂家和模型列表
  getEmbeddingProviders(): Promise<Array<{
    name: string
    display_name: string
    models: string[]
  }>> {
    return ApiClient.get('/api/config/llm/providers/embedding').then((response: any) => response.data ?? response)
  },

  // 获取可用的模型列表（按厂家分组）
  getAvailableModels(): Promise<Array<{
    provider: string
    provider_name: string
    models: Array<{ name: string; display_name: string }>
  }>> {
    return ApiClient.get('/api/config/models').then((response: any) => response.data ?? response)
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
    return ApiClient.get('/api/config/model-catalog').then((response: any) => response.data ?? response)
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
    return ApiClient.get(`/api/config/model-catalog/${provider}`).then((response: any) => response.data ?? response)
  },

  // 保存模型目录
  saveModelCatalog(catalog: {
    provider: string
    provider_name: string
    models: Array<{ name: string; display_name: string; description?: string }>
  }): Promise<{ success: boolean; message: string }> {
    return ApiClient.post('/api/config/model-catalog', catalog)
  },

  // 删除模型目录
  deleteModelCatalog(provider: string): Promise<{ success: boolean; message: string }> {
    return ApiClient.delete(`/api/config/model-catalog/${provider}`)
  },

  // 初始化默认模型目录
  initModelCatalog(): Promise<{ success: boolean; message: string }> {
    return ApiClient.post('/api/config/model-catalog/init')
  },

  // 🔥 新增：导出模型目录（供下载）
  exportModelCatalog(provider?: string): Promise<{
    success: boolean
    message: string
    data: {
      catalogs: Array<{
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
      }>
      exported_at: string
      version: string
    }
  }> {
    const url = provider
      ? `/api/config/model-catalog/export?provider=${encodeURIComponent(provider)}`
      : '/api/config/model-catalog/export'
    return ApiClient.get(url)
  },

  // 🔥 新增：获取预设模型目录模板
  getModelCatalogTemplate(): Promise<{
    success: boolean
    message: string
    data: {
      catalogs: Array<{
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
      }>
      exported_at: string
      version: string
      description: string
    }
  }> {
    return ApiClient.get('/api/config/model-catalog/template')
  },

  // 🔥 新增：导入模型目录（从JSON文件）
  importModelCatalog(data: {
    catalogs: Array<{
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
    }>
    merge_mode?: 'update' | 'replace' | 'append'
  }): Promise<{
    success: boolean
    message: string
    data: {
      success_count: number
      failed_count: number
      total_count: number
      errors: string[]
    }
  }> {
    return ApiClient.post('/api/config/model-catalog/import', {
      catalogs: data.catalogs,
      merge_mode: data.merge_mode || 'update'
    })
  },

  // 从厂家 API 获取模型列表
  fetchProviderModels(provider: string, filters?: FetchProviderModelsFilters): Promise<{
    success: boolean
    message?: string
    models?: Array<{
      id: string
      name: string
      context_length?: number
    }>
  }> {
    return ApiClient.post(`/api/config/llm/providers/${provider}/fetch-models`, filters || {})
  },

  // ========== 大模型配置管理 ==========

  // 获取所有大模型配置
  getLLMConfigs(): Promise<LLMConfig[]> {
    return ApiClient.get('/api/config/llm').then((response: any) => response.data ?? response)
  },

  // 添加或更新大模型配置
  updateLLMConfig(config: Partial<LLMConfig>): Promise<{ message: string; model_name: string }> {
    return ApiClient.post('/api/config/llm', config) as any
  },

  // 删除大模型配置
  deleteLLMConfig(provider: string, modelName: string): Promise<{ message: string }> {
    return ApiClient.delete(`/api/config/llm/${provider}/${modelName}`)
  },

  // 设置默认大模型
  setDefaultLLM(name: string): Promise<{ message: string; default_llm: string }> {
    return ApiClient.post('/api/config/llm/set-default', { name }) as any
  },

  // 一键导入大模型配置（按厂家）
  batchImportLLMConfigs(providers?: string[]): Promise<{ success: boolean; message: string; imported: number; skipped: number; errors: string[] }> {
    return ApiClient.post('/api/config/llm/batch-import', { providers: providers || [] }) as any
  },

  // 获取所有数据源配置
  getDataSourceConfigs(): Promise<DataSourceConfig[]> {
    return ApiClient.get('/api/config/datasource').then((response: any) => response.data ?? response)
  },

  // 添加数据源配置
  addDataSourceConfig(config: Partial<DataSourceConfig>): Promise<{ message: string; name: string }> {
    return ApiClient.post('/api/config/datasource', config) as any
  },

  // 设置默认数据源
  setDefaultDataSource(name: string): Promise<{ message: string; default_data_source: string }> {
    return ApiClient.post('/api/config/datasource/set-default', { name }) as any
  },

  // 更新数据源配置
  updateDataSourceConfig(name: string, config: Partial<DataSourceConfig>): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/datasource/${name}`, config)
  },

  // 删除数据源配置
  deleteDataSourceConfig(name: string): Promise<{ message: string }> {
    return ApiClient.delete(`/api/config/datasource/${name}`)
  },

  // 市场分类管理
  getMarketCategories(): Promise<MarketCategory[]> {
    return ApiClient.get('/api/config/market-categories').then((response: any) => response.data ?? response)
  },

  addMarketCategory(category: Partial<MarketCategory>): Promise<{ message: string; id: string }> {
    return ApiClient.post('/api/config/market-categories', category) as any
  },

  updateMarketCategory(id: string, category: Partial<MarketCategory>): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/market-categories/${id}`, category)
  },

  deleteMarketCategory(id: string): Promise<{ message: string }> {
    return ApiClient.delete(`/api/config/market-categories/${id}`)
  },

  // 数据源分组管理
  getDataSourceGroupings(): Promise<DataSourceGrouping[]> {
    return ApiClient.get('/api/config/datasource-groupings').then((response: any) => response.data ?? response)
  },

  addDataSourceToCategory(dataSourceName: string, categoryId: string, priority?: number): Promise<{ message: string }> {
    return ApiClient.post('/api/config/datasource-groupings', {
      data_source_name: dataSourceName,
      market_category_id: categoryId,
      priority: priority || 0,
      enabled: true
    })
  },

  removeDataSourceFromCategory(dataSourceName: string, categoryId: string): Promise<{ message: string }> {
    return ApiClient.delete(`/api/config/datasource-groupings/${dataSourceName}/${categoryId}`)
  },

  updateDataSourceGrouping(dataSourceName: string, categoryId: string, updates: Partial<DataSourceGrouping>): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/datasource-groupings/${dataSourceName}/${categoryId}`, updates)
  },

  // 批量更新分类内数据源排序
  updateCategoryDataSourceOrder(categoryId: string, orderedDataSources: Array<{name: string, priority: number}>): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/market-categories/${categoryId}/datasource-order`, {
      data_sources: orderedDataSources
    })
  },

  // 获取系统设置元数据
  getSystemSettingsMeta(): Promise<{ items: SettingMeta[] }> {
    return ApiClient.get('/api/config/settings/meta').then((r: any) => r.data)
  },


  // ========== 数据库配置管理 ==========

  // 获取所有数据库配置
  getDatabaseConfigs(): Promise<DatabaseConfig[]> {
    return ApiClient.get('/api/config/database').then((response: any) => response.data ?? response)
  },

  // 获取指定的数据库配置
  getDatabaseConfig(dbName: string): Promise<DatabaseConfig> {
    return ApiClient.get(`/api/config/database/${encodeURIComponent(dbName)}`).then((response: any) => response.data ?? response)
  },

  // 添加数据库配置
  addDatabaseConfig(config: Partial<DatabaseConfig>): Promise<{ success: boolean; message: string }> {
    return ApiClient.post('/api/config/database', config)
  },

  // 更新数据库配置
  updateDatabaseConfig(dbName: string, config: Partial<DatabaseConfig>): Promise<{ success: boolean; message: string }> {
    return ApiClient.put(`/api/config/database/${encodeURIComponent(dbName)}`, config)
  },

  // 删除数据库配置
  deleteDatabaseConfig(dbName: string): Promise<{ success: boolean; message: string }> {
    return ApiClient.delete(`/api/config/database/${encodeURIComponent(dbName)}`)
  },

  // 测试数据库配置连接
  testDatabaseConfig(dbName: string): Promise<ConfigTestResponse> {
    return ApiClient.post(`/api/config/database/${encodeURIComponent(dbName)}/test`)
  },

  // 获取系统设置
  getSystemSettings(): Promise<Record<string, any>> {
    return ApiClient.get('/api/config/settings')
  },

  // 获取默认模型配置
  getDefaultModels(): Promise<{
    default_provider?: string
    quick_analysis_model: string
    quick_analysis_model_config_id?: string
    deep_analysis_model: string
    deep_analysis_model_config_id?: string
    deep_reasoning_model?: string
    deep_reasoning_model_config_id?: string
    coding_model?: string
    coding_model_config_id?: string
  }> {
    return ApiClient.get('/api/config/settings').then((settings: any) => ({
      default_provider: settings.data?.default_provider || settings.default_provider || '',
      quick_analysis_model: settings.data?.quick_analysis_model || settings.quick_analysis_model || 'qwen-turbo',
      quick_analysis_model_config_id: settings.data?.quick_analysis_model_config_id || settings.quick_analysis_model_config_id || '',
      deep_analysis_model: settings.data?.deep_analysis_model || settings.deep_analysis_model || 'qwen-max',
      deep_analysis_model_config_id: settings.data?.deep_analysis_model_config_id || settings.deep_analysis_model_config_id || '',
      deep_reasoning_model: settings.data?.deep_reasoning_model || settings.deep_reasoning_model || '',
      deep_reasoning_model_config_id: settings.data?.deep_reasoning_model_config_id || settings.deep_reasoning_model_config_id || '',
      coding_model: settings.data?.coding_model || settings.coding_model || '',
      coding_model_config_id: settings.data?.coding_model_config_id || settings.coding_model_config_id || ''
    }))
  },

  // 更新系统设置
  updateSystemSettings(settings: Record<string, any>): Promise<{ success: boolean; data: any; message: string; timestamp: string }> {
    return ApiClient.put('/api/config/settings', settings) as any
  },

  // 测试配置连接
  testConfig(testRequest: ConfigTestRequest): Promise<ConfigTestResponse> {
    return ApiClient.post('/api/config/test', testRequest)
  },

  // 测试代理连接
  testProxyConnection(proxyConfig: { http_proxy?: string; https_proxy?: string }): Promise<{ success: boolean; data: { response_time: number }; message: string; timestamp: string }> {
    return ApiClient.post('/api/config/test-proxy', proxyConfig) as any
  },

  // 导出配置
  exportConfig(): Promise<{ message: string; data: any; exported_at: string }> {
    return ApiClient.post('/api/config/export') as any
  },

  // 导入配置
  importConfig(configData: Record<string, any>): Promise<{ message: string }> {
    return ApiClient.post('/api/config/import', configData)
  },

  // 迁移传统配置
  migrateLegacyConfig(): Promise<{ message: string }> {
    return ApiClient.post('/api/config/migrate-legacy')
  },

  // 配置重载
  reloadConfig(): Promise<{ success: boolean; message: string; data?: any }> {
    return ApiClient.post('/api/config/reload')
  },

  // ========== Gateway 平台配置管理 ==========

  // 获取 Gateway 平台配置
  getGatewayConfig(platform: string): Promise<GatewayConfig> {
    return ApiClient.get(`/api/config/gateway/${platform}`).then((r: any) => r.data)
  },

  // 更新 Gateway 平台配置
  updateGatewayConfig(platform: string, config: GatewayConfigRequest): Promise<{ message: string }> {
    return ApiClient.put(`/api/config/gateway/${platform}`, config)
  },

  // 测试 Gateway 平台连接
  testGatewayConnection(platform: string): Promise<{ success: boolean; data?: any; message: string }> {
    return ApiClient.post(`/api/config/gateway/${platform}/test`)
  },

  // ========== 向量迁移 ==========

  // 获取 Qdrant 中所有 collection 列表（主存储 + mem0），包含迁移状态
  getQdrantCollections(): Promise<{
    main: Array<{
      name: string
      point_count: number
      dimensions: number
      source: string
      migration_status: 'pending' | 'migrated' | 'outdated'
      current_model: string
      last_migration: string | null
    }>
    mem0: Array<{
      name: string
      point_count: number
      dimensions: number
      source: string
      migration_status: 'pending' | 'migrated' | 'outdated'
      current_model: string
      last_migration: string | null
    }>
  }> {
    return ApiClient.get('/api/config/qdrant/collections').then((response: any) => response.data ?? response)
  },

  // 获取 Qdrant 中所有 mem0 collection 列表（兼容旧接口）
  getMem0Collections(): Promise<Array<{
    name: string
    point_count: number
    dimensions: number
    is_current: boolean
  }>> {
    return ApiClient.get('/api/config/memory/collections').then((response: any) => response.data ?? response)
  },

  // 迁移 collection 向量数据（主存储原地重编码 / mem0 跨 collection 迁移）
  migrateCollection(collection_name: string, source: 'main' | 'mem0', dry_run?: boolean): Promise<{
    success: boolean
    collection_name?: string
    source_collection?: string
    target_collection?: string
    total_seen: number
    migrated: number
    skipped: number
    dry_run: boolean
    model_used?: string
  }> {
    return ApiClient.post('/api/config/qdrant/migrate', { collection_name, source, dry_run: !!dry_run }) as any
  },

  // 迁移旧 mem0 collection 到当前 collection（兼容旧接口）
  migrateMem0Collection(source_collection: string, dry_run?: boolean): Promise<{
    success: boolean
    source_collection: string
    target_collection: string
    total_seen: number
    migrated: number
    skipped: number
    dry_run: boolean
  }> {
    return ApiClient.post('/api/config/memory/migrate', { source_collection, dry_run: !!dry_run }) as any
  },

  // 删除空 collection
  deleteCollection(collection_name: string, source: 'main' | 'mem0'): Promise<{ success: boolean; message: string }> {
    return ApiClient.post('/api/config/qdrant/delete-collection', { collection_name, source }) as any
  },

  // ========== 京东云合作版 ==========

  // 获取京东云配置状态
  getJdyunStatus(): Promise<{
    jdyun_mode: boolean
    api_base: string
    api_key_configured: boolean
    current_model: string
    available_models: string[]
    embedding_model: string
    embedding_dims: number
    tushare_token_configured: boolean
    akshare_available: boolean
  }> {
    return ApiClient.get('/api/config/jdyun/status').then((response: any) => response.data ?? response)
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
  QMT: 'qmt',

  // 其他数据源
  QUANDL: 'quandl',
  LOCAL_FILE: 'local_file',
  LOCAL: 'local',  // 本地数据（用户通过API导入）
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
  temperature: 0.2,  // 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
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
