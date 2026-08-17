/**
 * 高级课程配置 v3.0
 * 
 * 30节系统课程，按"炒股全生命周期"组织
 * 前 FREE_LESSON_COUNT 节免费预览，其余引导至知识星球付费
 */

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

export const advancedCourseCategories: CourseCategory[] = [
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
  },
  {
    id: 'phase-02-track',
    name: '跟踪阶段',
    icon: '👁️',
    description: '选出来后怎么持续跟进？',
    lessonCount: 4,
    lessons: [
      { id: 'lesson-06', title: '第6课：AI助手功能全景', file: 'phase-02-track/lesson-06-ai-assistant-overview.md', order: 6 },
      { id: 'lesson-07', title: '第7课：用AI助手做行业研究', file: 'phase-02-track/lesson-07-ai-assistant-industry-research.md', order: 7 },
      { id: 'lesson-08', title: '第8课：AI助手驱动日常研究闭环', file: 'phase-02-track/lesson-08-ai-assistant-daily-research.md', order: 8 },
      { id: 'lesson-09', title: '第9课：定时分析与跟踪节奏', file: 'phase-02-track/lesson-09-scheduled-track-rhythm.md', order: 9 },
    ]
  },
  {
    id: 'phase-03-position',
    name: '持仓阶段',
    icon: '📊',
    description: '买入后怎么管理仓位？',
    lessonCount: 6,
    lessons: [
      { id: 'lesson-10', title: '第10课：模拟交易·先练手再实战', file: 'phase-03-position/lesson-10-paper-trading.md', order: 10 },
      { id: 'lesson-11', title: '第11课：持仓研究·AI监控持仓', file: 'phase-03-position/lesson-11-position-research.md', order: 11 },
      { id: 'lesson-12', title: '第12课：加减仓决策·看AI输出做判断', file: 'phase-03-position/lesson-12-add-reduce-decision.md', order: 12 },
      { id: 'lesson-13', title: '第13课：风险跟踪·边界怎么设', file: 'phase-03-position/lesson-13-risk-tracking.md', order: 13 },
      { id: 'lesson-14', title: '第14课：持仓阶段的常见错误', file: 'phase-03-position/lesson-14-position-pitfalls.md', order: 14 },
      { id: 'lesson-15', title: '第15课：智能助手在持仓阶段的应用', file: 'phase-03-position/lesson-15-ai-assistant-position.md', order: 15 },
    ]
  },
  {
    id: 'phase-04-review',
    name: '复盘阶段',
    icon: '🔄',
    description: '卖完了怎么回顾总结？',
    lessonCount: 4,
    lessons: [
      { id: 'lesson-16', title: '第16课：操作复盘·这笔交易做对了吗', file: 'phase-04-review/lesson-16-trade-review.md', order: 16 },
      { id: 'lesson-17', title: '第17课：案例库沉淀·经验变资产', file: 'phase-04-review/lesson-17-case-library.md', order: 17 },
      { id: 'lesson-18', title: '第18课：复盘结果怎么指导下次交易', file: 'phase-04-review/lesson-18-review-to-action.md', order: 18 },
      { id: 'lesson-19', title: '第19课：持续优化·迭代交易系统', file: 'phase-04-review/lesson-19-continuous-improvement.md', order: 19 },
    ]
  },
  {
    id: 'phase-05-short-term',
    name: '短线风格专章',
    icon: '⚡',
    description: '短线交易者的专属实战课',
    lessonCount: 3,
    lessons: [
      { id: 'lesson-20', title: '第20课：短线研究的平台工具链', file: 'phase-05-short-term/lesson-20-short-system-design.md', order: 20 },
      { id: 'lesson-21', title: '第21课：短线研究实战（上）·发现与跟踪', file: 'phase-05-short-term/lesson-21-short-case-1.md', order: 21 },
      { id: 'lesson-22', title: '第22课：短线研究实战（下）·跟踪与复盘', file: 'phase-05-short-term/lesson-22-short-case-2.md', order: 22 },
    ]
  },
  {
    id: 'phase-06-long-term',
    name: '中长线风格专章',
    icon: '📈',
    description: '中长线投资者的专属实战课',
    lessonCount: 3,
    lessons: [
      { id: 'lesson-23', title: '第23课：中长线研究的平台工具链', file: 'phase-06-long-term/lesson-23-long-system-design.md', order: 23 },
      { id: 'lesson-24', title: '第24课：中长线实战（上）·价值股估值修复', file: 'phase-06-long-term/lesson-24-long-case-1.md', order: 24 },
      { id: 'lesson-25', title: '第25课：中长线实战（下）·成长股业绩跟踪', file: 'phase-06-long-term/lesson-25-long-case-2.md', order: 25 },
    ]
  },
  {
    id: 'phase-07-extension',
    name: '平台扩展',
    icon: '🔧',
    description: '功能不够用？自己造！',
    lessonCount: 3,
    lessons: [
      { id: 'lesson-26', title: '第26课：AI工作流架构师·用自然语言生成工作流', file: 'phase-07-extension/lesson-26-ai-workflow-architect.md', order: 26 },
      { id: 'lesson-27', title: '第27课：Agent工坊+Skill中心·自定义分析师', file: 'phase-07-extension/lesson-27-agent-skill-workshop.md', order: 27 },
      { id: 'lesson-28', title: '第28课：实战·以巴菲特工作流为例', file: 'phase-07-extension/lesson-28-buffett-workflow-case.md', order: 28 },
    ]
  },
  {
    id: 'phase-08-personal-plan',
    name: '个人交易计划',
    icon: '📋',
    description: '把方法论变成你自己的',
    lessonCount: 2,
    lessons: [
      { id: 'lesson-29', title: '第29课：个人交易计划模板', file: 'phase-08-personal-plan/lesson-29-personal-trading-plan.md', order: 29 },
      { id: 'lesson-30', title: '第30课：持续优化与成长', file: 'phase-08-personal-plan/lesson-30-continuous-growth.md', order: 30 },
    ]
  }
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
