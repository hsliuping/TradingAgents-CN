// 市场参数规范化：V3.0 聚焦 A 股，港美股已暂停
export const normalizeMarketForAnalysis = (market: any): string => {
  const raw = String(market ?? '').trim()
  const upper = raw.toUpperCase()
  const cn = raw
  const isETF = ['ETF', '场内基金'].includes(cn) || upper === 'ETF'
  const isA = [
    'A股', '主板', '创业板', '科创板', '中小板', '沪市', '深市', '上交所', '深交所', '北交所'
  ].includes(cn) || ['CN', 'SH', 'SZ', 'SSE', 'SZSE'].includes(upper)
  if (isETF) return 'ETF'
  if (isA) return 'A股'
  // 默认按A股处理
  return 'A股'
}

/**
 * 将交易所代码转换为市场类型
 * @param exchangeCode 交易所代码（如 "sz", "sh", "hk", "us"）
 * @returns 市场类型（"A股", "港股", "美股"）
 */
export const exchangeCodeToMarket = (exchangeCode: string): string => {
  const code = String(exchangeCode ?? '').toLowerCase().trim()

  // A股交易所代码
  if (['sz', 'sh', 'bj', 'sse', 'szse', 'bse'].includes(code)) {
    return 'A股'
  }

  // 默认返回A股
  return 'A股'
}

/**
 * 根据股票代码判断市场类型
 * @param stockCode 股票代码
 * @returns 市场类型（"A股", "港股", "美股", "ETF"）
 */
export const getMarketByStockCode = (stockCode: string): string => {
  const code = String(stockCode ?? '').trim().toUpperCase()

  // 6位数字：先判断 ETF，否则 A股
  if (/^\d{6}$/.test(code)) {
    const prefix = code.substring(0, 2)
    if (['50', '51', '52', '56', '58', '15', '16', '18'].includes(prefix)) {
      return 'ETF'
    }
    return 'A股'
  }

  // 默认返回A股
  return 'A股'
}

export default {
  normalizeMarketForAnalysis,
  exchangeCodeToMarket,
  getMarketByStockCode
}

