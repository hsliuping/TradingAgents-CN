/**
 * 高级课程内容静态导入映射 v3.0
 *
 * 所有课程文件位于 docs/07-courses/v3.0/
 *
 * v3.6.0 社区版开源分离 M1 §7.4：免费/付费 loader 物理分离——
 * 本文件仅承载免费课程正文 loader（phase-01，前 5 节）；
 * 付费部分（第 6-30 节）在 advancedCourseContent.pro.ts，
 * 社区版发布时该文件整文件删除、下方 proCourseContentMap 替换为空对象，
 * 付费正文不进入社区版前端构建产物。
 */

// Pro 付费课程正文 loader（社区版发布时整文件剔除，此行替换为空对象）
import { proCourseContentMap } from './advancedCourseContent.pro'

// 免费课程文件导入映射（前 5 节，社区版保留）
const communityCourseContentMap: Record<string, () => Promise<{ default: string }>> = {
  // 阶段1：发现
  'phase-01-discover/lesson-01-stock-screening.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-01-stock-screening.md?raw'),
  'phase-01-discover/lesson-02-batch-analysis.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-02-batch-analysis.md?raw'),
  'phase-01-discover/lesson-03-single-analysis-basic.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-03-single-analysis-basic.md?raw'),
  'phase-01-discover/lesson-04-single-analysis-multi-scenario.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-04-single-analysis-multi-scenario.md?raw'),
  'phase-01-discover/lesson-05-discover-pitfalls.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-05-discover-pitfalls.md?raw'),
}

// 课程文件导入映射 = 免费部分 + Pro 付费部分（社区版发布后仅剩免费部分）
const courseContentMap: Record<string, () => Promise<{ default: string }>> = {
  ...communityCourseContentMap,
  ...proCourseContentMap
}

/**
 * 获取课程内容
 * @param filename 课程文件名（例如：'phase-01-discover/lesson-01-stock-screening.md'）
 * @returns Promise<string> 课程Markdown内容
 */
export async function getCourseContent(filename: string): Promise<string> {
  const loader = courseContentMap[filename]
  if (!loader) {
    throw new Error(`课程文件未找到: ${filename}`)
  }
  
  try {
    const module = await loader()
    return module.default
  } catch (error: any) {
    console.error(`加载课程文件失败: ${filename}`, error)
    throw new Error(`加载课程文件失败: ${filename} - ${error.message}`)
  }
}

/**
 * 同步获取课程内容（用于预加载）
 * 注意：这需要预先导入所有文件
 */
export function getCourseContentSync(_filename: string): string | null {
  return null
}
