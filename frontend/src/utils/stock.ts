/**
 * 股票代码字段兼容性工具函数
 * 
 * 用于处理前后端字段标准化过程中的兼容性问题
 */

/**
 * 从对象中获取股票代码（兼容新旧字段）
 * @param obj 包含股票代码的对象
 * @returns 股票代码（6位）
 */
export function getStockSymbol(obj: any): string {
  return obj?.symbol || obj?.stock_code || obj?.code || ''
}

/**
 * 从对象中获取完整股票代码（如 000001.SZ）
 * @param obj 包含股票代码的对象
 * @returns 完整股票代码
 */
export function getFullSymbol(obj: any): string {
  return obj?.full_symbol || obj?.symbol || obj?.stock_code || obj?.code || ''
}

/**
 * 创建包含兼容字段的股票代码对象
 * @param symbol 6位股票代码
 * @param fullSymbol 完整代码（可选）
 * @returns 包含新旧字段的对象
 */
export function createSymbolObject(symbol: string, fullSymbol?: string) {
  return {
    symbol,
    stock_code: symbol,  // 兼容字段
    code: symbol,        // 兼容字段
    ...(fullSymbol && { full_symbol: fullSymbol })
  }
}

/**
 * 标准化股票代码列表（去重、兼容新旧字段）
 * @param symbols 股票代码列表（可能包含新旧字段）
 * @returns 标准化后的代码列表
 */
export function normalizeSymbols(symbols: (string | { symbol?: string; stock_code?: string; code?: string })[]): string[] {
  const result = new Set<string>()
  
  for (const item of symbols) {
    if (typeof item === 'string') {
      if (item) result.add(item)
    } else if (item && typeof item === 'object') {
      const symbol = getStockSymbol(item)
      if (symbol) result.add(symbol)
    }
  }
  
  return Array.from(result)
}

/**
 * 验证股票代码格式
 * @param symbol 股票代码
 * @param market 市场类型（可选）
 * @returns 是否有效
 */
export function validateSymbol(symbol: string, market?: string): boolean {
  if (!symbol) return false
  
  const trimmed = symbol.trim()
  
  if (market === 'A股' || market === 'CN') {
    // A股：6位数字
    return /^\d{6}$/.test(trimmed)
  } else if (market === '美股' || market === 'US') {
    // 美股：1-5个字母
    return /^[A-Z]{1,5}$/.test(trimmed.toUpperCase())
  } else if (market === '港股' || market === 'HK') {
    // 港股：4-5位数字.HK
    return /^\d{4,5}(\.HK)?$/.test(trimmed.toUpperCase())
  }
  
  // 未指定市场时，尝试通用验证
  return /^\d{6}$/.test(trimmed) || // A股
         /^[A-Z]{1,5}$/.test(trimmed.toUpperCase()) || // 美股
         /^\d{4,5}(\.HK)?$/.test(trimmed.toUpperCase()) // 港股
}

/**
 * 格式化股票代码显示
 * @param symbol 股票代码
 * @param market 市场类型（可选）
 * @returns 格式化后的代码
 */
export function formatSymbol(symbol: string, market?: string): string {
  if (!symbol) return ''
  
  const trimmed = symbol.trim()
  
  if (market === '美股' || market === 'US') {
    return trimmed.toUpperCase()
  } else if (market === '港股' || market === 'HK') {
    // 确保港股代码包含 .HK 后缀
    if (/^\d{4,5}$/.test(trimmed)) {
      return `${trimmed}.HK`
    }
    return trimmed.toUpperCase()
  }
  
  return trimmed
}

/**
 * 从完整代码中提取6位代码
 * @param fullSymbol 完整代码（如 000001.SZ）
 * @returns 6位代码
 */
export function extractSymbol(fullSymbol: string): string {
  if (!fullSymbol) return ''
  
  // 移除市场后缀（.SZ, .SH, .BJ, .HK等）
  return fullSymbol.split('.')[0]
}

/**
 * 从6位代码推断市场代码
 * @param symbol 6位股票代码
 * @returns 市场代码（SZ/SH/BJ）或 null
 */
export function inferMarketCode(symbol: string): string | null {
  if (!symbol || !/^\d{6}$/.test(symbol)) return null
  
  const code = symbol.substring(0, 3)
  
  // 深圳市场
  if (['000', '001', '002', '003', '300', '301'].includes(code)) {
    return 'SZ'
  }
  
  // 上海市场
  if (['600', '601', '603', '605', '688', '689'].includes(code)) {
    return 'SH'
  }
  
  // 北京市场
  if (['430', '830', '870'].includes(code)) {
    return 'BJ'
  }
  
  return null
}

/**
 * 构建完整股票代码
 * @param symbol 6位股票代码
 * @param marketCode 市场代码（可选，如果不提供则自动推断）
 * @returns 完整代码（如 000001.SZ）
 */
export function buildFullSymbol(symbol: string, marketCode?: string): string {
  if (!symbol) return ''
  
  const market = marketCode || inferMarketCode(symbol)
  
  if (market) {
    return `${symbol}.${market}`
  }
  
  return symbol
}

/**
 * 批量转换对象中的股票代码字段
 * @param obj 包含股票代码的对象
 * @returns 转换后的对象（包含新旧字段）
 */
export function normalizeStockObject<T extends Record<string, any>>(obj: T): T {
  if (!obj) return obj
  
  const symbol = getStockSymbol(obj)
  
  if (symbol) {
    return {
      ...obj,
      symbol,
      stock_code: symbol,  // 兼容字段
      code: symbol         // 兼容字段
    }
  }
  
  return obj
}

/**
 * 批量转换对象数组中的股票代码字段
 * @param arr 对象数组
 * @returns 转换后的数组
 */
export function normalizeStockArray<T extends Record<string, any>>(arr: T[]): T[] {
  if (!Array.isArray(arr)) return arr
  
  return arr.map(item => normalizeStockObject(item))
}

