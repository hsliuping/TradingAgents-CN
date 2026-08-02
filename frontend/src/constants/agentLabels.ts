/**
 * Agent 类型与名称的中文显示映射
 * 用于下拉选择、表格展示等场景
 */

/** v1.0 及以下版本，不展示 */
export const v1AgentTypes = [
  'analysts',
  'researchers',
  'debators',
  'managers',
  'trader',
  'reviewers',
  'position_analysis',
]

export const agentTypeMap: Record<string, string> = {
  analysts_v2: '独立分析师 v2.0',
  researchers_v2: '积极/谨慎证据研究员 v2.0',
  debators_v2: '风险多情景研究 v2.0',
  managers_v2: '研究/风险评估师 v2.0',
  trader_v2: '研究整合员 v2.0',
  reviewers_v2: '复盘分析 v2.0',
  position_analysis_v2: '仓位分析 v2.0',
  post_processors_v2: '后处理器 v2.0',
  // 数据库中存在无 _v2 后缀的别名，统一显示中文
  post_processors: '后处理器 v2.0',
  // Agent工坊
  universal: '自定义Agent',
}

export const agentNameMap: Record<string, string> = {
  fundamentals_analyst_v2: '基本面分析师 v2.0',
  market_analyst_v2: '市场分析师 v2.0',
  news_analyst_v2: '新闻分析师 v2.0',
  social_analyst_v2: '社交媒体分析师 v2.0',
  sector_analyst_v2: '板块分析师 v2.0',
  index_analyst_v2: '大盘分析师 v2.0',
  bull_researcher_v2: '积极证据研究员 v2.0',
  bear_researcher_v2: '谨慎证据研究员 v2.0',
  research_manager_v2: '研究整合员 v2.0',
  risk_manager_v2: '风险评估师 v2.0',
  trader_v2: '研究整合员 v2.0',
  risky_analyst_v2: '高弹性情景分析师 v2.0',
  safe_analyst_v2: '防御情景分析师 v2.0',
  neutral_analyst_v2: '基准情景分析师 v2.0',
  timing_analyst_v2: '时机评估师 v2.0',
  position_analyst_v2: '持仓评估师 v2.0',
  emotion_analyst_v2: '情绪研究师 v2.0',
  attribution_analyst_v2: '归因研究师 v2.0',
  review_manager_v2: '复盘总结师 v2.0',
  pa_technical_v2: '技术面研究师 v2.0',
  pa_fundamental_v2: '基本面研究师 v2.0',
  pa_risk_v2: '风险评估师 v2.0',
  pa_advisor_v2: '持仓研究师 v2.0',
  chip_distribution_analyst_v2: '筹码分布分析师 v2.0',
  etf_analyst_v2: 'ETF 分析师 v2.0',
  data_preparer_v2: '数据准备器 v2.0',
  report_generator_v2: '报告生成器 v2.0',
}

export const labelAgentType = (v?: string) => (v && agentTypeMap[v]) || v || '-'
export const labelAgentName = (v?: string) => (v && agentNameMap[v]) || v || '-'

/** agent_id → agent_type，用于 Prompt 设计助手的 chat API */
export const agentIdToTypeMap: Record<string, string> = {
  // v2
  market_analyst_v2: 'analysts_v2',
  fundamentals_analyst_v2: 'analysts_v2',
  news_analyst_v2: 'analysts_v2',
  social_analyst_v2: 'analysts_v2',
  sector_analyst_v2: 'analysts_v2',
  index_analyst_v2: 'analysts_v2',
  etf_analyst_v2: 'analysts_v2',
  chip_distribution_analyst_v2: 'analysts_v2',
  data_preparer_v2: 'analysts_v2',
  bull_researcher_v2: 'researchers_v2',
  bear_researcher_v2: 'researchers_v2',
  research_manager_v2: 'managers_v2',
  risk_manager_v2: 'managers_v2',
  trader_v2: 'trader_v2',
  risky_analyst_v2: 'debators_v2',
  safe_analyst_v2: 'debators_v2',
  neutral_analyst_v2: 'debators_v2',
  timing_analyst_v2: 'reviewers_v2',
  position_analyst_v2: 'reviewers_v2',
  emotion_analyst_v2: 'reviewers_v2',
  attribution_analyst_v2: 'reviewers_v2',
  review_manager_v2: 'reviewers_v2',
  pa_technical_v2: 'position_analysis_v2',
  pa_fundamental_v2: 'position_analysis_v2',
  pa_risk_v2: 'position_analysis_v2',
  pa_advisor_v2: 'position_analysis_v2',
  report_generator_v2: 'post_processors_v2',
  // v1（兼容旧工作流）
  market_analyst: 'analysts_v2',
  fundamentals_analyst: 'analysts_v2',
  news_analyst: 'analysts_v2',
  social_analyst: 'analysts_v2',
  sector_analyst: 'analysts_v2',
  index_analyst: 'analysts_v2',
  bull_researcher: 'researchers_v2',
  bear_researcher: 'researchers_v2',
  research_manager: 'managers_v2',
  risk_manager: 'managers_v2',
  trader: 'trader_v2',
  risky_analyst: 'debators_v2',
  safe_analyst: 'debators_v2',
  neutral_analyst: 'debators_v2',
  timing_analyst: 'reviewers_v2',
  position_analyst: 'reviewers_v2',
  emotion_analyst: 'reviewers_v2',
  attribution_analyst: 'reviewers_v2',
  review_manager: 'reviewers_v2',
  pa_technical: 'position_analysis_v2',
  pa_fundamental: 'position_analysis_v2',
  pa_risk: 'position_analysis_v2',
  pa_advisor: 'position_analysis_v2',
}

export const resolveAgentType = (agentId?: string) =>
  (agentId && agentIdToTypeMap[agentId]) || 'analysts_v2'

/** 仅保留 v2.0 及以上类型 */
export const filterV2AgentTypes = (types: string[]) =>
  types.filter((t) => !v1AgentTypes.includes(t))
