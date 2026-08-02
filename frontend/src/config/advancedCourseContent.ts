/**
 * 高级课程内容静态导入映射 v3.0
 * 
 * 所有课程文件位于 docs/07-courses/v3.0/
 */

// 课程文件导入映射
const courseContentMap: Record<string, () => Promise<{ default: string }>> = {
  // 阶段1：发现
  'phase-01-discover/lesson-01-stock-screening.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-01-stock-screening.md?raw'),
  'phase-01-discover/lesson-02-batch-analysis.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-02-batch-analysis.md?raw'),
  'phase-01-discover/lesson-03-single-analysis-basic.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-03-single-analysis-basic.md?raw'),
  'phase-01-discover/lesson-04-single-analysis-multi-scenario.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-04-single-analysis-multi-scenario.md?raw'),
  'phase-01-discover/lesson-05-discover-pitfalls.md': () => import('../../../docs/07-courses/v3.0/phase-01-discover/lesson-05-discover-pitfalls.md?raw'),

  // 阶段2：跟踪
  'phase-02-track/lesson-06-general-research.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-06-general-research.md?raw'),
  'phase-02-track/lesson-07-scheduled-push.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-07-scheduled-push.md?raw'),
  'phase-02-track/lesson-08-ai-assistant-memory.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-08-ai-assistant-memory.md?raw'),
  'phase-02-track/lesson-09-track-rhythm.md': () => import('../../../docs/07-courses/v3.0/phase-02-track/lesson-09-track-rhythm.md?raw'),

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
