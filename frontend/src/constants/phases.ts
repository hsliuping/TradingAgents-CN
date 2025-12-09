
export interface PhaseConfig {
  id: number
  name: string
  title: string
  description: string
  agents: string[]
  defaultRounds: number
  minRounds: number
  maxRounds: number
  estimatedTimePerRound: number  // 分钟
}

export const PHASES: PhaseConfig[] = [
  {
    id: 2,
    name: 'phase2',
    title: '第二阶段 - 双向辩论与交易计划',
    description: '看涨分析师与看跌分析师进行对抗性辩论，并由专业交易员制定具体交易计划',
    agents: ['看涨分析师', '看跌分析师', '专业交易员'],
    defaultRounds: 2,
    minRounds: 1,
    maxRounds: 5,
    estimatedTimePerRound: 3
  },
  {
    id: 3,
    name: 'phase3',
    title: '第三阶段 - 风控与组合策略',
    description: '保守/中性/激进三类策略师与投资组合经理协同评估风险并制定最终方案',
    agents: ['保守策略师', '中性策略师', '激进策略师', '投资组合经理'],
    defaultRounds: 1,
    minRounds: 0,
    maxRounds: 3,
    estimatedTimePerRound: 3
  },
  {
    id: 4,
    name: 'summary',
    title: '第四阶段 - 最终决策与总结',
    description: '综合所有分析生成关键指标、置信度评估及最终投资建议',
    agents: ['总结智能体'],
    defaultRounds: 1,
    minRounds: 0,
    maxRounds: 1,
    estimatedTimePerRound: 1
  }
]

// 估算总耗时（分钟）
export function estimateTotalTime(phases: Record<string, { enabled: boolean, debateRounds: number }>): number {
  let total = 5  // 第一阶段基础时间
  
  PHASES.forEach(phase => {
    const phaseKey = phase.name as keyof typeof phases
    if (phases[phaseKey]?.enabled) {
      total += phase.estimatedTimePerRound * phases[phaseKey].debateRounds
    }
  })
  
  return total
}
