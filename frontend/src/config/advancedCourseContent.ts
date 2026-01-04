/**
 * 高级课程内容静态导入映射
 * 
 * 所有课程文件已重命名为英文名，避免Vite动态导入中文路径问题
 */

// 课程文件导入映射
const courseContentMap: Record<string, () => Promise<{ default: string }>> = {
  // 基础篇
  'lesson-01-basics-retail-to-system-trader.md': () => import('../../../docs/courses/advanced/expanded/lesson-01-basics-retail-to-system-trader.md?raw'),
  'lesson-02-basics-evolvable-investment-cycle.md': () => import('../../../docs/courses/advanced/expanded/lesson-02-basics-evolvable-investment-cycle.md?raw'),
  
  // 选股篇
  'lesson-03-stock-selection-single-analysis.md': () => import('../../../docs/courses/advanced/expanded/lesson-03-stock-selection-single-analysis.md?raw'),
  'lesson-04-stock-selection-batch-analysis.md': () => import('../../../docs/courses/advanced/expanded/lesson-04-stock-selection-batch-analysis.md?raw'),
  'lesson-05-stock-selection-short-long-term.md': () => import('../../../docs/courses/advanced/expanded/lesson-05-stock-selection-short-long-term.md?raw'),
  
  // 择时篇
  'lesson-06-timing-bull-bear-debate.md': () => import('../../../docs/courses/advanced/expanded/lesson-06-timing-bull-bear-debate.md?raw'),
  'lesson-07-timing-risk-debate.md': () => import('../../../docs/courses/advanced/expanded/lesson-07-timing-risk-debate.md?raw'),
  'lesson-08-timing-multi-agent-debate.md': () => import('../../../docs/courses/advanced/expanded/lesson-08-timing-multi-agent-debate.md?raw'),
  
  // 执行篇
  'lesson-09-execution-position-management.md': () => import('../../../docs/courses/advanced/expanded/lesson-09-execution-position-management.md?raw'),
  'lesson-10-execution-strategy.md': () => import('../../../docs/courses/advanced/expanded/lesson-10-execution-strategy.md?raw'),
  
  // 持仓管理篇
  'lesson-11-position-ai-analysis.md': () => import('../../../docs/courses/advanced/expanded/lesson-11-position-ai-analysis.md?raw'),
  'lesson-12-position-decision.md': () => import('../../../docs/courses/advanced/expanded/lesson-12-position-decision.md?raw'),
  
  // 风险管理篇
  'lesson-13-risk-debate-application.md': () => import('../../../docs/courses/advanced/expanded/lesson-13-risk-debate-application.md?raw'),
  'lesson-14-risk-profit-loss-strategy.md': () => import('../../../docs/courses/advanced/expanded/lesson-14-risk-profit-loss-strategy.md?raw'),
  
  // 复盘改进篇
  'lesson-15-review-ai-trade-review.md': () => import('../../../docs/courses/advanced/expanded/lesson-15-review-ai-trade-review.md?raw'),
  'lesson-16-review-continuous-improvement.md': () => import('../../../docs/courses/advanced/expanded/lesson-16-review-continuous-improvement.md?raw'),
  
  // 短线实战篇
  'lesson-17-short-term-plan-design.md': () => import('../../../docs/courses/advanced/expanded/lesson-17-short-term-plan-design.md?raw'),
  'lesson-18-short-term-case-study-1.md': () => import('../../../docs/courses/advanced/expanded/lesson-18-short-term-case-study-1.md?raw'),
  'lesson-19-short-term-case-study-2.md': () => import('../../../docs/courses/advanced/expanded/lesson-19-short-term-case-study-2.md?raw'),
  
  // 中长线实战篇
  'lesson-20-long-term-system-design.md': () => import('../../../docs/courses/advanced/expanded/lesson-20-long-term-system-design.md?raw'),
  'lesson-21-long-term-case-study-1.md': () => import('../../../docs/courses/advanced/expanded/lesson-21-long-term-case-study-1.md?raw'),
  'lesson-22-long-term-case-study-2.md': () => import('../../../docs/courses/advanced/expanded/lesson-22-long-term-case-study-2.md?raw'),
  
  // 交易计划建立
  'lesson-23-trading-plan-template.md': () => import('../../../docs/courses/advanced/expanded/lesson-23-trading-plan-template.md?raw'),
  'lesson-24-continuous-optimization.md': () => import('../../../docs/courses/advanced/expanded/lesson-24-continuous-optimization.md?raw'),
}

/**
 * 获取课程内容
 * @param filename 课程文件名（例如：'lesson-01-basics-retail-to-system-trader.md'）
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
export function getCourseContentSync(filename: string): string | null {
  // 这个方法需要预先导入所有文件，暂时不使用
  return null
}
