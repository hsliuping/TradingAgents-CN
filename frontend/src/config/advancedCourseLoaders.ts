/**
 * 高级课程旧版加载器兼容层
 *
 * 历史上这里会把高级课程正文直接打包进前端。为避免再次暴露高级内容，
 * 旧同步加载方式保留空实现，不再提供正文内容。
 */

/**
 * 课程文件映射表
 *
 * 旧版同步正文映射已下线，保留空对象仅用于兼容历史导入。
 */
export const courseFileMap: Record<string, string> = {}

/**
 * 根据文件名获取课程内容
 */
export function getCourseContent(fileName: string): string | null {
  void fileName
  return null
}

