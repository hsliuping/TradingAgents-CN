/**
 * 用户使用手册内容加载器
 *
 * 通过 Vite 的 `?raw` 静态导入机制将 docs/02-user-guide/ 下的 Markdown 手册打包到前端产物中。
 * 根据当前是否为京东云合作版模式，自动选择对应的手册内容。
 *
 * 涉及文件：
 * - 标准版：docs/02-user-guide/user-manual-v3.0.md
 * - 京东云版：docs/02-user-guide/jdyun-user-manual-v3.0.md
 */

import { isJdyunMode } from '@/utils/config'

// 标准版使用手册（懒加载，避免首屏体积过大）
const standardManualLoader = (): Promise<{ default: string }> =>
  import('../../../docs/02-user-guide/user-manual-v3.0.md?raw')

// 京东云合作版使用手册（v3.0 合并后使用标准版手册，京东云专属手册已移除）
const jdyunManualLoader = (): Promise<{ default: string }> =>
  import('../../../docs/02-user-guide/user-manual-v3.0.md?raw')

/**
 * 获取当前模式下的用户手册内容
 *
 * @returns Markdown 格式的手册字符串
 */
export async function getUserManualContent(): Promise<string> {
  try {
    if (isJdyunMode()) {
      const mod = await jdyunManualLoader()
      return mod.default
    }
    const mod = await standardManualLoader()
    return mod.default
  } catch (err) {
    console.error('[userManual] 加载使用手册失败:', err)
    return '# 使用手册加载失败\n\n请稍后重试，或联系管理员获取最新版本的使用手册。'
  }
}

/**
 * 获取当前模式下的手册标题
 */
export function getUserManualTitle(): string {
  return isJdyunMode()
    ? 'TradingAgents-CN Pro 京东云合作版使用手册'
    : 'TradingAgents-CN Pro v3.0 完整使用手册'
}

/**
 * 获取当前模式下的手册简短描述
 */
export function getUserManualDescription(): string {
  return isJdyunMode()
    ? '面向京东云合作版用户的完整使用指南'
    : '面向新用户与进阶用户的完整使用指南'
}
