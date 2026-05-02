/**
 * 高级课程内容加载器
 *
 * 高级课程正文改为由后端受权接口提供，避免继续打包到前端静态资源中。
 */

import { getAdvancedLessonContent } from '@/api/advancedCourses'

/**
 * 获取课程内容
 * @param filename 课程文件名（例如：'lesson-01-basics-retail-to-system-trader.md'）
 * @returns Promise<string> 课程Markdown内容
 */
export async function getCourseContent(filename: string): Promise<string> {
  const response = await getAdvancedLessonContent(filename)
  return response.data?.content || ''
}

/**
 * 同步获取课程内容（已废弃）
 *
 * 高级课程改为后端受权接口后，不再支持前端同步读取正文。
 */
export function getCourseContentSync(filename: string): string | null {
  void filename
  return null
}
