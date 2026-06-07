export type TradePlanAction = 'buy' | 'sell' | 'hold' | 'watch'

export interface TradePlanPriceBlock {
  price?: number | null
  reason?: string
  zone?: string
  strategy?: string
}

export interface TradePlanEntryZone {
  low?: number | null
  high?: number | null
  text?: string
}

export interface TradePlan {
  action: TradePlanAction | string
  entry_zone?: TradePlanEntryZone
  entry_trigger?: string
  stop_loss?: TradePlanPriceBlock
  take_profit?: TradePlanPriceBlock
  invalidations?: string[]
  time_horizon?: string
  position_hint?: string
  confidence?: number
  risk_level?: string
  evidence_grade?: string
}

export interface TradePlanOrderSeed {
  side: 'buy' | 'sell'
  price: number
}

export const normalizeTradePlanAction = (action: unknown): TradePlanAction => {
  const text = String(action || '').trim().toLowerCase()
  if (text === 'buy' || text === '买入' || text === '增持') return 'buy'
  if (text === 'sell' || text === '卖出' || text === '减持') return 'sell'
  if (text === 'hold' || text === '持有') return 'hold'
  if (text === 'watch' || text === '观望' || text === '等待') return 'watch'
  return 'watch'
}

export const getTradePlanFromAnalysisResult = (result: unknown): TradePlan | null => {
  if (!result || typeof result !== 'object') return null
  const tradePlan = (result as { trade_plan?: unknown }).trade_plan
  if (!tradePlan || typeof tradePlan !== 'object' || Array.isArray(tradePlan)) return null
  return tradePlan as TradePlan
}

export const toFiniteTradePlanNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export const buildTradePlanOrderSeed = (
  tradePlan: TradePlan | null,
  currentPrice: number
): TradePlanOrderSeed | null => {
  if (!tradePlan) return null
  const action = normalizeTradePlanAction(tradePlan.action)
  if (action !== 'buy' && action !== 'sell') return null

  const fallbackPrice = Number.isFinite(currentPrice) && currentPrice > 0 ? currentPrice : 0
  const entryLow = toFiniteTradePlanNumber(tradePlan.entry_zone?.low)
  const entryHigh = toFiniteTradePlanNumber(tradePlan.entry_zone?.high)
  const stopPrice = toFiniteTradePlanNumber(tradePlan.stop_loss?.price)

  const price =
    action === 'buy'
      ? entryHigh || entryLow || fallbackPrice
      : stopPrice || entryLow || fallbackPrice

  if (!Number.isFinite(price) || price <= 0) return null
  return { side: action, price }
}

export const formatTradePlanPrice = (price: unknown): string => {
  const value = toFiniteTradePlanNumber(price)
  return value === null ? '暂无' : value.toFixed(2)
}

export const formatTradePlanPercent = (value: unknown): string => {
  const number = toFiniteTradePlanNumber(value)
  return number === null ? '暂无' : `${(number * 100).toFixed(0)}%`
}
