import type { StockInfo } from '@/types/analysis'
import type { FactorWarningPayload, WarningCategory } from '@/api/screening'

type FactorTagType = 'warning' | 'danger' | 'info' | 'success'

interface FactorWarningEntry {
  key: string
  label: string
  tagType: FactorTagType
  conditions: string[]
}

interface FactorDiagnosticEntry {
  key: string
  label: string
  state: string
  reason: string
  missingInputs: string[]
  tagType: 'danger'
}

const warningCategoryMeta: Record<WarningCategory, { label: string; tagType: FactorTagType }> = {
  fallback_used: { label: '回退计算', tagType: 'warning' },
  proxy_used: { label: '代理估算', tagType: 'danger' },
  low_sample_size: { label: '样本偏少', tagType: 'info' },
  precision_degraded: { label: '精度受限', tagType: 'warning' },
}

const diagnosticLabelMap: Record<string, string> = {
  piotroski_f_score: '财务质量评分缺口',
  altman_z_score: '财务安全评分缺口',
  beneish_m_score: '盈余操纵风险缺口',
}

const warningFieldLabelMap: Record<string, string> = {
  pe_ttm: '滚动市盈率回退',
  pb: '市净率回退',
  pb_mrq: '最新市净率估算',
  ps_ttm: '滚动市销率回退',
  dividend_yield: '股息率回退',
  industry_pe_median: '行业估值样本偏少',
  industry_pb_median: '行业估值样本偏少',
  net_profit_ttm: '滚动净利润回退',
  roic: '投入资本回报率精度受限',
  interest_coverage: '利息保障倍数回退',
  inventory_turnover: '存货周转率估算',
  net_cash_position: '净现金头寸估算',
  fcf: '自由现金流估算',
}

const warningConditionDescriptionMap: Record<string, string> = {
  'pe_ttm fallback_to pe': '滚动市盈率缺少直接值，已回退使用市盈率口径。',
  'pb fallback_to pb_mrq': '市净率缺少直接值，已回退使用最新市净率口径。',
  'pb_mrq estimated_from market_cap_and_total_equity': '最新市净率由总市值和净资产估算得出。',
  'ps_ttm fallback_to ps': '滚动市销率缺少直接值，已回退使用市销率口径。',
  'dividend_yield fallback_to financial_field': '股息率缺少行情侧字段，已回退使用财务字段。',
  'industry_peer_sample_count < 5': '行业可比样本数偏少，横向参考稳定性有限。',
  'net_profit_ttm fallback_to net_profit_or_net_income': '滚动净利润缺少直接值，已回退使用净利润口径。',
  'roic money_cap_missing_assumed_zero': '货币资金字段缺失，投入资本回报率采用保守假设估算。',
  'interest_coverage fallback_to raw_interest_expense': '利息费用字段不完整，利息保障倍数已回退使用原始利息费用。',
  'inventory_turnover cost_proxy_used': '营业成本字段缺失，存货周转率改用成本代理估算。',
  'net_cash_position proxy_total_ncl_used': '长期负债字段不完整，净现金头寸采用代理口径估算。',
  'fcf conservative_proxy_used': '自由现金流采用保守代理口径估算。',
}

const diagnosticStateLabelMap: Record<string, string> = {
  available: '可用',
  missing_comparison_period: '缺少对比期',
  missing_required_inputs: '缺少关键输入',
  invalid_denominator: '关键分母无效',
  calculation_blocked: '计算被保护性阻断',
  unknown: '状态未知',
}

export const getFactorWarningEntries = (row: StockInfo): FactorWarningEntry[] => {
  const warnings = row.factor_warnings || {}
  return Object.entries(warnings).map(([fieldName, payload]: [string, FactorWarningPayload]) => {
    const category = payload.warning_categories?.[0]
    const meta = category ? warningCategoryMeta[category] : null
    return {
      key: fieldName,
      label: warningFieldLabelMap[fieldName] || meta?.label || fieldName,
      tagType: meta?.tagType || 'info',
      conditions: (payload.warning_conditions || []).map(
        condition => warningConditionDescriptionMap[condition] || condition
      ),
    }
  })
}

export const getFactorDiagnosticEntries = (row: StockInfo): FactorDiagnosticEntry[] => {
  const diagnostics = row.factor_diagnostics || {}
  return Object.entries(diagnostics).map(([key, payload]: [string, any]) => ({
    key,
    label: diagnosticLabelMap[key] || key,
    state: diagnosticStateLabelMap[payload?.state] || payload?.state || '状态未知',
    reason: payload?.reason || '',
    missingInputs: payload?.missing_inputs || [],
    tagType: 'danger',
  }))
}