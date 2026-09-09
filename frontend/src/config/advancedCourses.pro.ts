/**
 * 高级课程配置 · Pro 专属部分（v3.6.0 社区版开源分离 M1 §7.4）
 *
 * 承载付费课程元数据（第 6-30 节，phase-02 ~ phase-08）。
 * 社区版发布时本文件整文件删除，advancedCourses.ts 中
 * proCourseCategories 替换为空数组 —— 前端仅剩前 5 节免费课程。
 *
 * 注意：新增付费课程只登记在本文件；误登记到 advancedCourses.ts = 发布即泄露。
 */

import type { CourseCategory } from './advancedCourses'

/** Pro 付费课程分类（第 6-30 节） */
export const proCourseCategories: CourseCategory[] = [
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
