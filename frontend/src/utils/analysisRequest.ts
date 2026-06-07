import type { SingleAnalysisRequest } from '@/api/analysis'
import type { CommitteeMode } from '@/constants/committeeAgents'

interface BuildSingleAnalysisRequestInput {
  symbol: string
  market: string
  analysisDate: Date
  researchDepth: string
  selectedAnalysts: string[]
  includeSentiment: boolean
  includeRisk: boolean
  language: string
  agentEngine: 'tradingagents' | 'codex'
  quickAnalysisModel: string
  deepAnalysisModel: string
  committeeMode: CommitteeMode
  selectedCommitteeAgents: string[]
}

export const buildSingleAnalysisRequest = (
  input: BuildSingleAnalysisRequestInput
): SingleAnalysisRequest => {
  const selectedCommitteeAgents =
    input.committeeMode === 'enhanced' ? input.selectedCommitteeAgents : []

  return {
    symbol: input.symbol,
    stock_code: input.symbol,
    parameters: {
      market_type: input.market,
      analysis_date: input.analysisDate.toISOString().split('T')[0],
      research_depth: input.researchDepth,
      selected_analysts: input.selectedAnalysts,
      include_sentiment: input.includeSentiment,
      include_risk: input.includeRisk,
      language: input.language,
      agent_engine: input.agentEngine,
      committee_mode: input.committeeMode,
      selected_committee_agents: selectedCommitteeAgents,
      quick_analysis_model: input.quickAnalysisModel,
      deep_analysis_model: input.deepAnalysisModel
    }
  }
}
