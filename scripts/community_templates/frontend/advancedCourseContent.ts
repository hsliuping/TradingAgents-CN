/**
 * 高级课程内容静态导入映射（社区版）
 *
 * 本文件由发布管道（scripts/publish_community.py）生成：
 * 仅承载免费课程正文 loader（phase-01，前 5 节），无付费正文。
 */

// 免费课程文件导入映射（前 5 节，社区版保留）
const communityCourseContentMap: Record<string, () => Promise<{ default: string }>> = {
  // 阶段1：发现
  'phase-01-discover/lesson-01-stock-screening.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-01-stock-screening.md?raw'),
  'phase-01-discover/lesson-02-batch-analysis.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-02-batch-analysis.md?raw'),
  'phase-01-discover/lesson-03-single-analysis-basic.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-03-single-analysis-basic.md?raw'),
  'phase-01-discover/lesson-04-single-analysis-multi-scenario.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-04-single-analysis-multi-scenario.md?raw'),
  'phase-01-discover/lesson-05-discover-pitfalls.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-05-discover-pitfalls.md?raw'),
}

// 课程文件导入映射（社区版：仅免费部分）
const courseContentMap: Record<string, () => Promise<{ default: string }>> = {
  ...communityCourseContentMap
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
