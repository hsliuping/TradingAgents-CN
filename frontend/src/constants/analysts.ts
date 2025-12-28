/**
 * 分析师配置常量
 */

export interface Analyst {
  id: string
  name: string
  description: string
  icon?: string
  // 新增分类属性
  category: 'stock' | 'index' | 'common'
}

// 系统支持的分析师列表
export const ANALYSTS: Analyst[] = [
  // === 个股专用 Agent (Stock Only) ===
  {
    id: 'fundamentals',
    name: '基本面分析师',
    description: '分析公司财务状况、业务模式和竞争优势',
    icon: 'DataAnalysis',
    category: 'stock'
  },
  {
    id: 'news',
    name: '新闻分析师', // 这里的 News 指个股新闻
    description: '分析个股相关新闻、公告和市场事件',
    icon: 'Document',
    category: 'stock'
  },
  {
    id: 'social',
    name: '社媒分析师',
    description: '分析社交媒体情绪、投资者心理和舆论导向',
    icon: 'ChatDotRound',
    category: 'stock'
  },

  // === 指数专用 Agent (Index Only) ===
  {
    id: 'macro',
    name: '宏观分析师',
    description: '分析GDP、CPI、货币政策等宏观经济指标',
    icon: 'DataLine',
    category: 'index'
  },
  {
    id: 'policy',
    name: '政策分析师',
    description: '解读国家战略、产业政策及其对市场的影响',
    icon: 'Reading',
    category: 'index'
  },
  {
    id: 'sector',
    name: '行业分析师',
    description: '分析板块轮动规律与资金流向',
    icon: 'PieChart',
    category: 'index'
  },
  {
    id: 'technical_index',
    name: '技术分析师(指数)',
    description: '基于K线、均线、成交量等指标分析大盘走势',
    icon: 'TrendCharts',
    category: 'index'
  },
  {
    id: 'intl_news',
    name: '国际新闻分析师',
    description: '监控全球地缘政治与外盘动态',
    icon: 'Global',
    category: 'index'
  },
  {
    id: 'bull_bear',
    name: '多空博弈',
    description: '模拟多头与空头辩论，深度挖掘市场分歧',
    icon: 'Connection',
    category: 'index'
  },
  {
    id: 'risk',
    name: '风险裁判',
    description: '综合评估市场风险，给出仓位控制建议',
    icon: 'Warning',
    category: 'index'
  },

  // === 通用 Agent (Common) ===
  {
    id: 'market',
    name: '市场分析师', // 既可以分析个股的市场表现，也可以分析大盘
    description: '分析市场整体趋势与情绪',
    icon: 'TrendCharts',
    category: 'common'
  }
]

// 分析师名称列表（用于表单选项）
export const ANALYST_NAMES = ANALYSTS.map(analyst => analyst.name)

// 默认选中的分析师
export const DEFAULT_ANALYSTS = ['市场分析师', '基本面分析师']

// 根据名称获取分析师信息
export const getAnalystByName = (name: string): Analyst | undefined => {
  return ANALYSTS.find(analyst => analyst.name === name)
}

// 根据ID获取分析师信息
export const getAnalystById = (id: string): Analyst | undefined => {
  return ANALYSTS.find(analyst => analyst.id === id)
}

// 验证分析师名称是否有效
export const isValidAnalyst = (name: string): boolean => {
  return ANALYST_NAMES.includes(name)
}

// 中文名称到英文ID的映射
export const ANALYST_NAME_TO_ID_MAP: Record<string, string> = {
  // Common
  '市场分析师': 'market',
  // Stock
  '基本面分析师': 'fundamentals',
  '新闻分析师': 'news',
  '社媒分析师': 'social',
  // Index
  '宏观分析师': 'macro',
  '政策分析师': 'policy',
  '行业分析师': 'sector',
  '技术分析师(指数)': 'technical_index',
  '国际新闻分析师': 'intl_news',
  '多空博弈': 'bull_bear',
  '风险裁判': 'risk'
}

// 将中文分析师名称转换为英文ID
export const convertAnalystNamesToIds = (names: string[]): string[] => {
  return names.map(name => ANALYST_NAME_TO_ID_MAP[name] || name)
}

// 将英文ID转换为中文分析师名称
export const convertAnalystIdsToNames = (ids: string[]): string[] => {
  const idToNameMap = Object.fromEntries(
    Object.entries(ANALYST_NAME_TO_ID_MAP).map(([name, id]) => [id, name])
  )
  return ids.map(id => idToNameMap[id] || id)
}

// 模型名称到供应商的映射
export const MODEL_TO_PROVIDER_MAP: Record<string, string> = {
  // 阿里百炼 (DashScope)
  'qwen-turbo': 'dashscope',
  'qwen-plus': 'dashscope',
  'qwen-max': 'dashscope',
  'qwen-plus-latest': 'dashscope',
  'qwen-max-longcontext': 'dashscope',

  // OpenAI
  'gpt-3.5-turbo': 'openai',
  'gpt-4': 'openai',
  'gpt-4-turbo': 'openai',
  'gpt-4o': 'openai',
  'gpt-4o-mini': 'openai',

  // Google
  'gemini-pro': 'google',
  'gemini-2.0-flash': 'google',
  'gemini-2.0-flash-thinking-exp': 'google',

  // DeepSeek
  'deepseek-chat': 'deepseek',
  'deepseek-coder': 'deepseek',

  // 智谱AI
  'glm-4': 'zhipu',
  'glm-3-turbo': 'zhipu',
  'chatglm3-6b': 'zhipu'
}

// 根据模型名称获取供应商
export const getProviderByModel = (modelName: string): string => {
  return MODEL_TO_PROVIDER_MAP[modelName] || 'dashscope' // 默认使用阿里百炼
}
