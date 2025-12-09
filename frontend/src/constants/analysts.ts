/**
 * 分析师配置常量
 */

export interface Analyst {
  id: string
  name: string
  description: string
  icon?: string
}

// 保留空列表占位，所有分析师均应由后端配置返回
export const ANALYSTS: Analyst[] = []
export const ANALYST_NAMES: string[] = []
export const DEFAULT_ANALYSTS: string[] = []
export const DEFAULT_ANALYSTS_NAMES: string[] = []

// 根据名称获取分析师信息（当前无静态列表，返回 undefined）
export const getAnalystByName = (_name: string): Analyst | undefined => undefined

// 根据ID获取分析师信息（当前无静态列表，返回 undefined）
export const getAnalystById = (_id: string): Analyst | undefined => undefined

// 验证分析师名称是否有效（静态列表为空，统一返回 false）
export const isValidAnalyst = (_name: string): boolean => false

// 规范化分析师标识符（确保返回英文ID或 slug 简化 ID）
export const normalizeAnalystId = (input: string): string => {
  if (typeof input !== 'string') return ''
  const trimmed = input.trim()
  // 如果是完整的 slug 格式（如 "market-analyst"），转换为简短 ID
  if (trimmed.endsWith('-analyst')) {
    return trimmed.replace('-analyst', '').replace(/-/g, '_')
  }
  return trimmed
}

// 规范化分析师列表（确保所有元素都是英文ID，并去重）
export const normalizeAnalystIds = (inputs: string[]): string[] => {
  const normalized = inputs.map(normalizeAnalystId).filter(Boolean)
  // 使用 Set 去重，保持原始顺序
  return [...new Set(normalized)]
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
