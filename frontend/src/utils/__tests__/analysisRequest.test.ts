import { describe, expect, it } from 'vitest'
import { buildSingleAnalysisRequest } from '../analysisRequest'

describe('buildSingleAnalysisRequest', () => {
  it('preserves standard committee defaults when enhanced mode is off', () => {
    const request = buildSingleAnalysisRequest({
      symbol: '000001',
      market: 'A股',
      analysisDate: new Date('2026-06-06T00:00:00+08:00'),
      researchDepth: '标准',
      selectedAnalysts: ['market', 'fundamentals'],
      includeSentiment: true,
      includeRisk: true,
      language: 'zh-CN',
      agentEngine: 'tradingagents',
      quickAnalysisModel: 'qwen-turbo',
      deepAnalysisModel: 'qwen-max',
      committeeMode: 'standard',
      selectedCommitteeAgents: ['data_steward']
    })

    expect(request.parameters?.committee_mode).toBe('standard')
    expect(request.parameters?.selected_committee_agents).toEqual([])
  })

  it('includes selected committee agents when enhanced mode is enabled', () => {
    const request = buildSingleAnalysisRequest({
      symbol: '000001',
      market: 'A股',
      analysisDate: new Date('2026-06-06T00:00:00+08:00'),
      researchDepth: '标准',
      selectedAnalysts: ['market', 'fundamentals'],
      includeSentiment: true,
      includeRisk: true,
      language: 'zh-CN',
      agentEngine: 'codex',
      quickAnalysisModel: 'qwen-turbo',
      deepAnalysisModel: 'qwen-max',
      committeeMode: 'enhanced',
      selectedCommitteeAgents: ['data_steward', 'valuation', 'scorecard']
    })

    expect(request.parameters?.committee_mode).toBe('enhanced')
    expect(request.parameters?.selected_committee_agents).toEqual([
      'data_steward',
      'valuation',
      'scorecard'
    ])
  })
})
