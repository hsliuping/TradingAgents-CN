/**
 * 分析师配置常量
 */

export interface Analyst {
  id: string
  name: string
  description: string
  icon?: string
}

// 系统支持的分析师列表
export const ANALYSTS: Analyst[] = [
  {
    id: 'market',
    name: '市场分析师',
    description: '分析市场趋势、行业动态和宏观经济环境',
    icon: 'TrendCharts'
  },
  {
    id: 'fundamentals',
    name: '基本面分析师',
    description: '分析公司财务状况、业务模式和竞争优势',
    icon: 'DataAnalysis'
  },
  {
    id: 'news',
    name: '新闻分析师',
    description: '分析相关新闻、公告和市场事件的影响',
    icon: 'Document'
  },
  {
    id: 'social',
    name: '社媒分析师',
    description: '分析社交媒体情绪、投资者心理和舆论导向',
    icon: 'ChatDotRound'
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
  '市场分析师': 'market',
  '基本面分析师': 'fundamentals',
  '新闻分析师': 'news',
  '社媒分析师': 'social'
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
