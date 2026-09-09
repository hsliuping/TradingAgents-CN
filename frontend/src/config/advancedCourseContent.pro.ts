/**
 * 高级课程内容加载映射 · Pro 专属部分（v3.6.0 社区版开源分离 M1 §7.4）
 *
 * 承载付费课程正文的动态加载映射（第 6-30 节，对应 docs/07-courses/v3.0/ 付费部分）。
 * 社区版发布时本文件整文件删除，advancedCourseContent.ts 中
 * proCourseContentMap 替换为空对象 —— 付费正文不进入社区版前端构建产物。
 *
 * 注意：新增付费课程正文 loader 只登记在本文件；误登记到 advancedCourseContent.ts = 发布即泄露。
 */

/** Pro 付费课程文件加载映射（第 6-30 节） */
export const proCourseContentMap: Record<string, () => Promise<{ default: string }>> = {
  // 阶段2：跟踪
  'phase-02-track/lesson-06-ai-assistant-overview.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-06-ai-assistant-overview.md?raw'),
  'phase-02-track/lesson-07-ai-assistant-industry-research.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-07-ai-assistant-industry-research.md?raw'),
  'phase-02-track/lesson-08-ai-assistant-daily-research.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-08-ai-assistant-daily-research.md?raw'),
  'phase-02-track/lesson-09-scheduled-track-rhythm.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-09-scheduled-track-rhythm.md?raw'),

  // 阶段3：持仓
  'phase-03-position/lesson-10-paper-trading.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-10-paper-trading.md?raw'),
  'phase-03-position/lesson-11-position-research.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-11-position-research.md?raw'),
  'phase-03-position/lesson-12-add-reduce-decision.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-12-add-reduce-decision.md?raw'),
  'phase-03-position/lesson-13-risk-tracking.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-13-risk-tracking.md?raw'),
  'phase-03-position/lesson-14-position-pitfalls.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-14-position-pitfalls.md?raw'),
  'phase-03-position/lesson-15-ai-assistant-position.md': () => import('../../../docs/07-courses/v3.0/phase-03-position/lesson-15-ai-assistant-position.md?raw'),

  // 阶段4：复盘
  'phase-04-review/lesson-16-trade-review.md': () => import('../../../docs/07-courses/v3.0/phase-04-review/lesson-16-trade-review.md?raw'),
  'phase-04-review/lesson-17-case-library.md': () => import('../../../docs/07-courses/v3.0/phase-04-review/lesson-17-case-library.md?raw'),
  'phase-04-review/lesson-18-review-to-action.md': () => import('../../../docs/07-courses/v3.0/phase-04-review/lesson-18-review-to-action.md?raw'),
  'phase-04-review/lesson-19-continuous-improvement.md': () => import('../../../docs/07-courses/v3.0/phase-04-review/lesson-19-continuous-improvement.md?raw'),

  // 阶段5：短线
  'phase-05-short-term/lesson-20-short-system-design.md': () => import('../../../docs/07-courses/v3.0/phase-05-short-term/lesson-20-short-system-design.md?raw'),
  'phase-05-short-term/lesson-21-short-case-1.md': () => import('../../../docs/07-courses/v3.0/phase-05-short-term/lesson-21-short-case-1.md?raw'),
  'phase-05-short-term/lesson-22-short-case-2.md': () => import('../../../docs/07-courses/v3.0/phase-05-short-term/lesson-22-short-case-2.md?raw'),

  // 阶段6：中长线
  'phase-06-long-term/lesson-23-long-system-design.md': () => import('../../../docs/07-courses/v3.0/phase-06-long-term/lesson-23-long-system-design.md?raw'),
  'phase-06-long-term/lesson-24-long-case-1.md': () => import('../../../docs/07-courses/v3.0/phase-06-long-term/lesson-24-long-case-1.md?raw'),
  'phase-06-long-term/lesson-25-long-case-2.md': () => import('../../../docs/07-courses/v3.0/phase-06-long-term/lesson-25-long-case-2.md?raw'),

  // 阶段7：平台扩展
  'phase-07-extension/lesson-26-ai-workflow-architect.md': () => import('../../../docs/07-courses/v3.0/phase-07-extension/lesson-26-ai-workflow-architect.md?raw'),
  'phase-07-extension/lesson-27-agent-skill-workshop.md': () => import('../../../docs/07-courses/v3.0/phase-07-extension/lesson-27-agent-skill-workshop.md?raw'),
  'phase-07-extension/lesson-28-buffett-workflow-case.md': () => import('../../../docs/07-courses/v3.0/phase-07-extension/lesson-28-buffett-workflow-case.md?raw'),

  // 阶段8：个人计划
  'phase-08-personal-plan/lesson-29-personal-trading-plan.md': () => import('../../../docs/07-courses/v3.0/phase-08-personal-plan/lesson-29-personal-trading-plan.md?raw'),
  'phase-08-personal-plan/lesson-30-continuous-growth.md': () => import('../../../docs/07-courses/v3.0/phase-08-personal-plan/lesson-30-continuous-growth.md?raw'),
}
