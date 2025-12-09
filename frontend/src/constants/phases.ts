
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
    title: '第二阶段 - 双向辩论',
    description: '看涨分析师与看跌分析师进行对抗性辩论，挖掘投资机会和风险',
    agents: ['看涨分析师', '看跌分析师'],
    defaultRounds: 2,
    minRounds: 1,
    maxRounds: 5,
    estimatedTimePerRound: 3
  },
  {
    id: 3,
    name: 'phase3',
    title: '第三阶段 - 投资组合策略',
    description: '保守/中性/激进三类策略师与投资组合经理协同制定组合方案',
    agents: ['保守策略师', '中性策略师', '激进策略师', '投资组合经理'],
    defaultRounds: 1,
    minRounds: 0,
    maxRounds: 3,
    estimatedTimePerRound: 3
  },
  {
    id: 4,
    name: 'phase4',
    title: '第四阶段 - 最终决策',
    description: '专业交易员综合所有信息进行最终投资决策',
    agents: ['专业交易员'],
    defaultRounds: 1,
    minRounds: 0,
    maxRounds: 1,
    estimatedTimePerRound: 2
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
