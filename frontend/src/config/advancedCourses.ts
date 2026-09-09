/**
 * 高级课程配置 v3.0
 *
 * 30节系统课程，按"炒股全生命周期"组织
 * 前 FREE_LESSON_COUNT 节免费预览，其余引导至知识星球付费
 *
 * v3.6.0 社区版开源分离 M1 §7.4：免费/付费数据物理分离——
 * 本文件仅承载免费课程元数据（phase-01，前 5 节）；
 * 付费部分（第 6-30 节）在 advancedCourses.pro.ts，
 * 社区版发布时该文件整文件删除、下方 proCourseCategories 替换为空数组。
 */

// Pro 付费课程分类（社区版发布时整文件剔除，此行替换为空数组）
import { proCourseCategories } from './advancedCourses.pro'

export interface Lesson {
  id: string
  title: string
  file: string  // Markdown文件路径（相对于 docs/07-courses/v3.0/）
  order: number
}

export interface CourseCategory {
  id: string
  name: string
  icon: string
  description: string
  lessonCount: number
  lessons: Lesson[]
}

/** 免费开放的课程数量 */
export const FREE_LESSON_COUNT = 5

/**
 * 判断课程是否免费
 */
export function isFreeLesson(order: number): boolean {
  return order <= FREE_LESSON_COUNT
}

/** 免费课程分类（前 5 节，社区版保留） */
const communityCourseCategories: CourseCategory[] = [
  {
    id: 'phase-01-discover',
    name: '发现阶段',
    icon: '🔍',
    description: '从6000只股票里找到值得研究的',
    lessonCount: 5,
    lessons: [
      { id: 'lesson-01', title: '第1课：股票筛选（自然语言+条件筛选）', file: 'phase-01-discover/lesson-01-stock-screening.md', order: 1 },
      { id: 'lesson-02', title: '第2课：批量分析（单次≤10只）', file: 'phase-01-discover/lesson-02-batch-analysis.md', order: 2 },
      { id: 'lesson-03', title: '第3课：单股研究入门（5级深度）', file: 'phase-01-discover/lesson-03-single-analysis-basic.md', order: 3 },
      { id: 'lesson-04', title: '第4课：单股研究进阶·多情景辩论', file: 'phase-01-discover/lesson-04-single-analysis-multi-scenario.md', order: 4 },
      { id: 'lesson-05', title: '第5课：发现阶段的常见错误', file: 'phase-01-discover/lesson-05-discover-pitfalls.md', order: 5 },
    ]
  }
]

/** 全量课程分类 = 免费部分 + Pro 付费部分（社区版发布后仅剩免费部分） */
export const advancedCourseCategories: CourseCategory[] = [
  ...communityCourseCategories,
  ...proCourseCategories
]

/**
 * 根据分类ID和课程ID获取课程信息
 */
export function getLesson(categoryId: string, lessonId: string): Lesson | null {
  const category = advancedCourseCategories.find(cat => cat.id === categoryId)
  if (!category) return null
  
  return category.lessons.find(lesson => lesson.id === lessonId) || null
}

/**
 * 根据课程文件路径获取课程信息
 */
export function getLessonByFile(file: string): { category: CourseCategory, lesson: Lesson } | null {
  for (const category of advancedCourseCategories) {
    const lesson = category.lessons.find(l => l.file === file)
    if (lesson) {
      return { category, lesson }
    }
  }
  return null
}

/**
 * 获取上一课和下一课
 */
export function getAdjacentLessons(categoryId: string, lessonId: string): {
  prev: { category: CourseCategory, lesson: Lesson } | null
  next: { category: CourseCategory, lesson: Lesson } | null
} {
  const category = advancedCourseCategories.find(cat => cat.id === categoryId)
  if (!category) {
    return { prev: null, next: null }
  }

  const lessonIndex = category.lessons.findIndex(l => l.id === lessonId)
  if (lessonIndex === -1) {
    return { prev: null, next: null }
  }

  // 上一课
  let prev: { category: CourseCategory, lesson: Lesson } | null = null
  if (lessonIndex > 0) {
    prev = { category, lesson: category.lessons[lessonIndex - 1] }
  } else {
    const categoryIndex = advancedCourseCategories.findIndex(cat => cat.id === categoryId)
    if (categoryIndex > 0) {
      const prevCategory = advancedCourseCategories[categoryIndex - 1]
      if (prevCategory.lessons.length > 0) {
        prev = { 
          category: prevCategory, 
          lesson: prevCategory.lessons[prevCategory.lessons.length - 1] 
        }
      }
    }
  }

  // 下一课
  let next: { category: CourseCategory, lesson: Lesson } | null = null
  if (lessonIndex < category.lessons.length - 1) {
    next = { category, lesson: category.lessons[lessonIndex + 1] }
  } else {
    const categoryIndex = advancedCourseCategories.findIndex(cat => cat.id === categoryId)
    if (categoryIndex < advancedCourseCategories.length - 1) {
      const nextCategory = advancedCourseCategories[categoryIndex + 1]
      if (nextCategory.lessons.length > 0) {
        next = { category: nextCategory, lesson: nextCategory.lessons[0] }
      }
    }
  }

  return { prev, next }
}
