/**
 * 高级课程配置
 * 
 * 定义所有高级课程的分类和课程信息
 */

export interface Lesson {
  id: string
  title: string
  file: string  // Markdown文件路径（相对于 docs/courses/advanced/expanded/）
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

export const advancedCourseCategories: CourseCategory[] = [
  {
    id: 'basics',
    name: '基础篇',
    icon: '📚',
    description: '从散户到系统交易者的基础概念',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-1', 
        title: '第1课：从散户到系统交易者', 
        file: 'lesson-01-basics-retail-to-system-trader.md', 
        order: 1 
      },
      { 
        id: 'lesson-2', 
        title: '第2课：可进化投资系统的核心循环', 
        file: 'lesson-02-basics-evolvable-investment-cycle.md', 
        order: 2 
      }
    ]
  },
  {
    id: 'stock-selection',
    name: '选股篇',
    icon: '🔍',
    description: 'AI辅助的选股策略和方法',
    lessonCount: 3,
    lessons: [
      { 
        id: 'lesson-3', 
        title: '第3课：单股分析深度应用', 
        file: 'lesson-03-stock-selection-single-analysis.md', 
        order: 3 
      },
      { 
        id: 'lesson-4', 
        title: '第4课：批量分析选股', 
        file: 'lesson-04-stock-selection-batch-analysis.md', 
        order: 4 
      },
      { 
        id: 'lesson-5', 
        title: '第5课：短线与中长线选股策略', 
        file: 'lesson-05-stock-selection-short-long-term.md', 
        order: 5 
      }
    ]
  },
  {
    id: 'timing',
    name: '择时篇',
    icon: '⏰',
    description: 'AI多智能体辩论辅助择时决策',
    lessonCount: 3,
    lessons: [
      { 
        id: 'lesson-6', 
        title: '第6课：多空辩论的应用', 
        file: 'lesson-06-timing-bull-bear-debate.md', 
        order: 6 
      },
      { 
        id: 'lesson-7', 
        title: '第7课：风险辩论的应用', 
        file: 'lesson-07-timing-risk-debate.md', 
        order: 7 
      },
      { 
        id: 'lesson-8', 
        title: '第8课：多智能体辩论的综合应用', 
        file: 'lesson-08-timing-multi-agent-debate.md', 
        order: 8 
      }
    ]
  },
  {
    id: 'execution',
    name: '执行篇',
    icon: '⚡',
    description: '仓位管理和执行策略',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-9', 
        title: '第9课：仓位管理原则', 
        file: 'lesson-09-execution-position-management.md', 
        order: 9 
      },
      { 
        id: 'lesson-10', 
        title: '第10课：执行策略', 
        file: 'lesson-10-execution-strategy.md', 
        order: 10 
      }
    ]
  },
  {
    id: 'position-management',
    name: '持仓管理篇',
    icon: '📊',
    description: 'AI辅助的持仓分析和决策',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-11', 
        title: '第11课：AI持仓分析的应用', 
        file: 'lesson-11-position-ai-analysis.md', 
        order: 11 
      },
      { 
        id: 'lesson-12', 
        title: '第12课：持仓决策', 
        file: 'lesson-12-position-decision.md', 
        order: 12 
      }
    ]
  },
  {
    id: 'risk-management',
    name: '风险管理篇',
    icon: '🛡️',
    description: '风险识别和控制策略',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-13', 
        title: '第13课：风险辩论的应用', 
        file: 'lesson-13-risk-debate-application.md', 
        order: 13 
      },
      { 
        id: 'lesson-14', 
        title: '第14课：止盈止损策略', 
        file: 'lesson-14-risk-profit-loss-strategy.md', 
        order: 14 
      }
    ]
  },
  {
    id: 'review-improvement',
    name: '复盘改进篇',
    icon: '🔄',
    description: 'AI辅助的交易复盘和持续改进',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-15', 
        title: '第15课：AI交易复盘的应用', 
        file: 'lesson-15-review-ai-trade-review.md', 
        order: 15 
      },
      { 
        id: 'lesson-16', 
        title: '第16课：持续改进方法', 
        file: 'lesson-16-review-continuous-improvement.md', 
        order: 16 
      }
    ]
  },
  {
    id: 'short-term-practice',
    name: '短线实战篇',
    icon: '⚡',
    description: '短线交易的完整实战案例',
    lessonCount: 3,
    lessons: [
      { 
        id: 'lesson-17', 
        title: '第17课：短线交易计划设计', 
        file: 'lesson-17-short-term-plan-design.md', 
        order: 17 
      },
      { 
        id: 'lesson-18', 
        title: '第18课：短线实战案例（上）', 
        file: 'lesson-18-short-term-case-study-1.md', 
        order: 18 
      },
      { 
        id: 'lesson-19', 
        title: '第19课：短线实战案例（下）', 
        file: 'lesson-19-short-term-case-study-2.md', 
        order: 19 
      }
    ]
  },
  {
    id: 'long-term-practice',
    name: '中长线实战篇',
    icon: '📈',
    description: '中长线投资的完整实战案例',
    lessonCount: 3,
    lessons: [
      { 
        id: 'lesson-20', 
        title: '第20课：中长线投资系统设计', 
        file: 'lesson-20-long-term-system-design.md', 
        order: 20 
      },
      { 
        id: 'lesson-21', 
        title: '第21课：中长线实战案例（上）', 
        file: 'lesson-21-long-term-case-study-1.md', 
        order: 21 
      },
      { 
        id: 'lesson-22', 
        title: '第22课：中长线实战案例（下）', 
        file: 'lesson-22-long-term-case-study-2.md', 
        order: 22 
      }
    ]
  },
  {
    id: 'trading-plan',
    name: '交易计划建立',
    icon: '📋',
    description: '建立和完善个人交易计划',
    lessonCount: 2,
    lessons: [
      { 
        id: 'lesson-23', 
        title: '第23课：个人交易计划模板', 
        file: 'lesson-23-trading-plan-template.md', 
        order: 23 
      },
      { 
        id: 'lesson-24', 
        title: '第24课：持续优化与成长', 
        file: 'lesson-24-continuous-optimization.md', 
        order: 24 
      }
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

  // 上一课：同一分类的前一课，或上一个分类的最后一课
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

  // 下一课：同一分类的下一课，或下一个分类的第一课
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

