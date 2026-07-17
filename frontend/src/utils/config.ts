/**
 * 前端配置工具
 */

/**
 * 检测是否为京东云合作版模式
 * 通过构建时注入的环境变量 VITE_JDYUN_MODE 控制
 */
export const isJdyunMode = (): boolean => {
  return import.meta.env.VITE_JDYUN_MODE === 'true'
}

/**
 * 京东云预置的对话模型列表
 */
export const JDYUN_CHAT_MODELS = [
  'GLM-5',
  'GLM-5.1',
  'GLM-5.2',
  'DeepSeek-V4-Flash',
] as const

/**
 * 获取可用的模型列表
 * 京东云模式下返回 4 个预置模型，非京东云模式下返回 null（表示使用数据库配置的模型）
 */
export const getAvailableModels = (): string[] | null => {
  if (isJdyunMode()) {
    return [...JDYUN_CHAT_MODELS]
  }
  return null
}
