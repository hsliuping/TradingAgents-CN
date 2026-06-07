import { describe, expect, it } from 'vitest'
import {
  buildTradePlanOrderSeed,
  getTradePlanFromAnalysisResult,
  normalizeTradePlanAction
} from '../tradePlan'

const buyPlan = {
  action: 'buy',
  entry_zone: { low: 10, high: 10.8, text: '10.00-10.80' },
  entry_trigger: '放量突破10.80元',
  stop_loss: { price: 9.2, reason: '跌破支撑' },
  take_profit: { price: 12.5, zone: '12.00-12.50', strategy: '分批止盈' },
  invalidations: ['跌破9.20元'],
  time_horizon: '5-20个交易日',
  position_hint: '单笔不超过计划资金的20%',
  confidence: 0.72,
  risk_level: '中等',
  evidence_grade: 'B'
}

describe('trade plan utilities', () => {
  it('normalizes supported trade plan actions', () => {
    expect(normalizeTradePlanAction('buy')).toBe('buy')
    expect(normalizeTradePlanAction('sell')).toBe('sell')
    expect(normalizeTradePlanAction('hold')).toBe('hold')
    expect(normalizeTradePlanAction('watch')).toBe('watch')
    expect(normalizeTradePlanAction('买入')).toBe('buy')
    expect(normalizeTradePlanAction('unknown')).toBe('watch')
  })

  it('returns a structured trade plan only when present', () => {
    expect(getTradePlanFromAnalysisResult({ trade_plan: buyPlan })?.action).toBe('buy')
    expect(getTradePlanFromAnalysisResult({})).toBeNull()
    expect(getTradePlanFromAnalysisResult({ trade_plan: 'bad' })).toBeNull()
  })

  it('builds simulated order seed from buy and sell plans only', () => {
    expect(buildTradePlanOrderSeed(buyPlan, 10.2)).toEqual({
      side: 'buy',
      price: 10.8
    })

    expect(
      buildTradePlanOrderSeed(
        {
          ...buyPlan,
          action: 'sell',
          stop_loss: { price: 9.2, reason: '破位' }
        },
        10.2
      )
    ).toEqual({
      side: 'sell',
      price: 9.2
    })

    expect(buildTradePlanOrderSeed({ ...buyPlan, action: 'hold' }, 10.2)).toBeNull()
    expect(buildTradePlanOrderSeed({ ...buyPlan, action: 'watch' }, 10.2)).toBeNull()
  })
})
