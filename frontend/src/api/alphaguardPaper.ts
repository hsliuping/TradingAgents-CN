import { ApiClient } from './request'

export type AutomaticAccountType =
  | 'PAPER_QUANT'
  | 'PAPER_NORMAL'
  | 'PAPER_TOP_CONFIRMED'
  | 'PAPER_CHALLENGER'

export interface AutomaticPaperAccount {
  account_id: string
  user_id: string
  account_type: AutomaticAccountType
  market: 'CN'
  currency: 'CNY'
  status: 'ACTIVE' | 'SUSPENDED' | 'CLOSED'
  initial_cash: string
  cash_available: string
  cash_reserved: string
  realized_pnl: string
  total_fees: string
  updated_at: string
  execution_environment: 'PAPER'
  live_execution_allowed: false
}

export interface AutomaticPaperPosition {
  position_id: string
  account_id: string
  symbol: string
  market: 'CN'
  currency: 'CNY'
  quantity: number
  available_quantity: number
  reserved_quantity: number
  average_cost: string
  total_cost: string
  realized_pnl: string
  total_fees: string
  updated_at: string
}

export interface AutomaticPositionLot {
  lot_id: string
  account_id: string
  symbol: string
  acquired_trade_date: string
  original_quantity: number
  remaining_quantity: number
  reserved_quantity: number
  unit_cost: string
  total_cost: string
  available_from_date: string
  status: 'OPEN' | 'PARTIALLY_CLOSED' | 'CLOSED'
}

export interface AutomaticPaperOrder {
  order_id: string
  intent_id: string
  account_id: string
  account_type: AutomaticAccountType
  candidate_id?: string | null
  source_type: string
  source_object_id: string
  risk_decision_id?: string | null
  symbol: string
  side: 'BUY' | 'SELL'
  order_type: 'LIMIT' | 'MARKET_ON_OPEN'
  requested_quantity: number
  filled_quantity: number
  remaining_quantity: number
  limit_price?: string | null
  average_fill_price?: string | null
  total_fees: string
  status: string
  reject_reason?: string | null
  created_at: string
}

export interface FeeBreakdown {
  commission: string
  stamp_duty: string
  transfer_fee: string
  regulatory_fee: string
  other_fees: string
  total_fee: string
  fee_policy_version: string
}

export interface AutomaticPaperFill {
  fill_id: string
  order_id: string
  account_id: string
  trade_date: string
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: string
  notional: string
  fee_breakdown: FeeBreakdown
  matching_engine_version: string
  fee_policy_version: string
  created_at: string
}

export interface AutomaticAccountSnapshot {
  account_snapshot_id: string
  account_id: string
  trade_date: string
  cash_available: string
  cash_reserved: string
  position_market_value: string
  total_equity: string
  valuation_complete: boolean
  missing_price_symbols: string[]
}

interface ItemsResponse<T> {
  items: T[]
}

export const alphaguardPaperApi = {
  getAccounts() {
    return ApiClient.get<ItemsResponse<AutomaticPaperAccount>>('/api/alphaguard/paper/accounts')
  },
  getPositions(accountId: string) {
    return ApiClient.get<ItemsResponse<AutomaticPaperPosition>>(
      '/api/alphaguard/paper/positions',
      { account_id: accountId }
    )
  },
  getPositionLots(accountId: string) {
    return ApiClient.get<ItemsResponse<AutomaticPositionLot>>(
      '/api/alphaguard/paper/position-lots',
      { account_id: accountId }
    )
  },
  getOrders(accountId: string) {
    return ApiClient.get<ItemsResponse<AutomaticPaperOrder>>(
      '/api/alphaguard/paper/orders',
      { account_id: accountId, limit: 200 }
    )
  },
  getFills(accountId: string) {
    return ApiClient.get<ItemsResponse<AutomaticPaperFill>>(
      '/api/alphaguard/paper/fills',
      { account_id: accountId, limit: 200 }
    )
  },
  getAccountSnapshots(accountId: string) {
    return ApiClient.get<ItemsResponse<AutomaticAccountSnapshot>>(
      '/api/alphaguard/paper/account-snapshots',
      { account_id: accountId, limit: 30 }
    )
  },
  cancelOrder(orderId: string) {
    return ApiClient.post<AutomaticPaperOrder>(
      `/api/alphaguard/paper/orders/${encodeURIComponent(orderId)}/cancel`
    )
  }
}
