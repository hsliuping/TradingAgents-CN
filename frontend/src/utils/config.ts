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
 * 京东云对话模型列表（默认值）
 *
 * 🔥 运行时会被后端 `/api/config/jdyun/status` 返回的 available_models 覆盖，
 * 避免前端硬编码模型列表与后端 OPENAI_MODEL 环境变量不一致。
 */
export let JDYUN_CHAT_MODELS: string[] = [
  'GLM-5',
  'GLM-5.1',
  'GLM-5.2',
  'DeepSeek-V4-Flash',
]

let _jdyunModelsLoaded = false

/**
 * 从后端加载京东云可用模型列表（启动/初始化时调用一次）
 *
 * 京东云模式下，模型列表以后端 OPENAI_MODEL 环境变量（逗号分隔）为准，
 * 前端只需在页面初始化时调用本函数，即可与后端保持一致。
 * 非京东云模式或加载失败时返回默认列表。
 */
export const loadJdyunChatModels = async (): Promise<string[]> => {
  if (!isJdyunMode() || _jdyunModelsLoaded) return JDYUN_CHAT_MODELS
  try {
    // 动态 import 打破循环依赖：config -> request -> auth -> config
    const { ApiClient } = await import('@/api/request')
    const resp: any = await ApiClient.get('/api/config/jdyun/status', undefined, { skipErrorHandler: true })
    const data = resp?.data || resp
    const models = data?.available_models
    if (Array.isArray(models) && models.length > 0) {
      JDYUN_CHAT_MODELS = models
    }
  } catch (e) {
    console.warn('加载京东云模型列表失败，使用默认列表:', e)
  } finally {
    _jdyunModelsLoaded = true
  }
  return JDYUN_CHAT_MODELS
}

/**
 * 获取可用的模型列表
 * 京东云模式下返回预置模型，非京东云模式下返回 null（表示使用数据库配置的模型）
 */
export const getAvailableModels = (): string[] | null => {
  if (isJdyunMode()) {
    return [...JDYUN_CHAT_MODELS]
  }
  return null
}
