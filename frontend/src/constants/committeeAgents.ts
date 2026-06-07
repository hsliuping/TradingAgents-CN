export type CommitteeMode = 'standard' | 'enhanced'

export interface CommitteeAgent {
  id: string
  name: string
  description: string
  tag?: string
}

export const FIXED_WORKFLOW_AGENTS: CommitteeAgent[] = [
  {
    id: 'bull_researcher',
    name: '多头研究员',
    description: '基于分析师报告构建买入与上行情景论据',
    tag: '自动执行'
  },
  {
    id: 'bear_researcher',
    name: '空头研究员',
    description: '识别下行风险、反驳过度乐观假设',
    tag: '自动执行'
  },
  {
    id: 'research_manager',
    name: '研究经理',
    description: '主持多空辩论并形成研究团队共识',
    tag: '自动执行'
  },
  {
    id: 'trader',
    name: '交易员',
    description: '把研究结论转化为交易计划和执行参考',
    tag: '自动执行'
  },
  {
    id: 'risk_team',
    name: '风险管理团队',
    description: '激进、保守、中性风险分析师与风险经理共同评估',
    tag: '自动执行'
  }
]

export const ENHANCED_COMMITTEE_AGENTS: CommitteeAgent[] = [
  {
    id: 'data_steward',
    name: 'Data Steward',
    description: '检查数据新鲜度、缺失字段和证据等级'
  },
  {
    id: 'industry_macro',
    name: 'Industry & Macro',
    description: '补充行业周期、政策、宏观与同业背景'
  },
  {
    id: 'business_moat',
    name: 'Business & Moat',
    description: '补充商业模式、竞争壁垒和管理执行'
  },
  {
    id: 'valuation',
    name: 'Valuation',
    description: '补充历史估值、同业对比和情景空间'
  },
  {
    id: 'flow_positioning',
    name: 'Flow & Positioning',
    description: '补充资金流、流动性和持仓拥挤度'
  },
  {
    id: 'scorecard',
    name: 'Scorecard',
    description: '生成结构化评分卡和分歧调和摘要'
  }
]

export const DEFAULT_SELECTED_COMMITTEE_AGENTS = ENHANCED_COMMITTEE_AGENTS.map(agent => agent.id)
