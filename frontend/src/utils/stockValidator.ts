/**
 * 股票代码格式验证工具
 * 支持 A股、美股、港股的代码格式验证
 */

export interface StockValidationResult {
  valid: boolean
  market?: 'A股' | '美股' | '港股' | 'A股指数'
  message?: string
  normalizedCode?: string
}

/**
 * A股指数代码验证
 * 格式：
 * - 6位数字 + .SH/.SZ 后缀 (e.g. 000001.SH, 399001.SZ)
 * - 或者特定的指数代码范围
 */
export function validateIndexStock(code: string): StockValidationResult {
  // 移除空格
  const cleanCode = code.trim().toUpperCase();

  // 格式一：6位数字.SH/.SZ
  if (/^\d{6}\.(SH|SZ)$/.test(cleanCode)) {
    return { valid: true, market: 'A股指数', normalizedCode: cleanCode };
  }
  
  // 格式二：纯6位数字，尝试自动补全 (需要更多的上下文，这里只做基本校验)
  if (/^\d{6}$/.test(cleanCode)) {
    // 简单的指数代码范围判断 (仅作参考)
    // 上证指数 000xxx
    if (cleanCode.startsWith('000')) {
        return { valid: true, market: 'A股指数', normalizedCode: cleanCode + '.SH' }; // 默认为上证
    }
    // 深证指数 399xxx
    if (cleanCode.startsWith('399')) {
        return { valid: true, market: 'A股指数', normalizedCode: cleanCode + '.SZ' };
    }
    
    // 其他指数代码 (如 98xxxx 国证指数等)
    // 允许通过，不强制补全后缀，交给后端处理或用户自行补充
    return { valid: true, market: 'A股指数', normalizedCode: cleanCode };
  }

  // 格式三：H开头的行业指数 (e.g. H30184)
  if (/^H\d{5}$/.test(cleanCode) || /^H\d{5}\.(CSI|SH|SZ)$/.test(cleanCode)) {
      return { valid: true, market: 'A股指数', normalizedCode: cleanCode.includes('.') ? cleanCode : cleanCode + '.CSI' };
  }

  return { valid: false, message: '指数代码格式应为 6位数字.SH/.SZ 或 H开头行业指数' };
}


/**
 * A股代码格式验证
 * 格式：6位数字
 * - 60xxxx: 上海主板
 * - 68xxxx: 科创板
 * - 00xxxx: 深圳主板
 * - 30xxxx: 创业板
 * - 43xxxx/83xxxx/87xxxx: 北交所
 */
export function validateAStock(code: string): StockValidationResult {
  // 移除空格和特殊字符
  const cleanCode = code.trim().replace(/[^0-9]/g, '')
  
  // 必须是6位数字
  if (!/^\d{6}$/.test(cleanCode)) {
    return {
      valid: false,
      message: 'A股代码必须是6位数字'
    }
  }
  
  // 验证前缀
  const prefix = cleanCode.substring(0, 2)
  const validPrefixes = ['60', '68', '00', '30', '43', '83', '87']
  
  if (!validPrefixes.includes(prefix)) {
    return {
      valid: false,
      message: 'A股代码前缀不正确（支持：60/68/00/30/43/83/87开头）'
    }
  }
  
  return {
    valid: true,
    market: 'A股',
    normalizedCode: cleanCode
  }
}

/**
 * 美股代码格式验证
 * 格式：1-5个大写字母
 * 示例：AAPL, MSFT, GOOGL, TSLA, BRK.B
 */
export function validateUSStock(code: string): StockValidationResult {
  // 移除空格，保留字母和点号
  const cleanCode = code.trim().toUpperCase().replace(/[^A-Z.]/g, '')
  
  // 基本格式：1-5个字母，可能包含一个点号
  if (!/^[A-Z]{1,5}(\.[A-Z])?$/.test(cleanCode)) {
    return {
      valid: false,
      message: '美股代码格式不正确（1-5个字母，如：AAPL、BRK.B）'
    }
  }
  
  // 不能全是点号
  if (cleanCode.replace(/\./g, '').length === 0) {
    return {
      valid: false,
      message: '美股代码不能为空'
    }
  }
  
  return {
    valid: true,
    market: '美股',
    normalizedCode: cleanCode
  }
}

/**
 * 港股代码格式验证
 * 格式：5位数字（前面可能有0）
 * 示例：00700（腾讯）、09988（阿里巴巴）、01810（小米）
 * 也支持不带前导0的格式：700、9988、1810
 */
export function validateHKStock(code: string): StockValidationResult {
  // 移除空格和特殊字符
  const cleanCode = code.trim().replace(/[^0-9]/g, '')
  
  // 必须是1-5位数字
  if (!/^\d{1,5}$/.test(cleanCode)) {
    return {
      valid: false,
      message: '港股代码必须是1-5位数字'
    }
  }
  
  // 转换为5位格式（补齐前导0）
  const normalizedCode = cleanCode.padStart(5, '0')
  
  return {
    valid: true,
    market: '港股',
    normalizedCode: normalizedCode
  }
}

/**
 * 自动识别股票代码格式并验证
 * @param code 股票代码
 * @param marketHint 市场提示（可选），如果提供则优先验证该市场
 */
export function validateStockCode(
  code: string,
  marketHint?: 'A股' | '美股' | '港股' | 'A股指数'
): StockValidationResult {
  if (!code || !code.trim()) {
    return {
      valid: false,
      message: '请输入股票代码'
    }
  }
  
  const trimmedCode = code.trim()
  
  // 如果提供了市场提示，优先验证该市场
  if (marketHint) {
    switch (marketHint) {
      case 'A股':
        return validateAStock(trimmedCode)
      case '美股':
        return validateUSStock(trimmedCode)
      case '港股':
        return validateHKStock(trimmedCode)
      case 'A股指数':
        return validateIndexStock(trimmedCode)
    }
  }
  
  // 自动识别：先判断是否全是数字
  const isNumeric = /^\d+$/.test(trimmedCode.replace(/[^0-9]/g, ''))
  
  if (isNumeric) {
    const cleanCode = trimmedCode.replace(/[^0-9]/g, '')
    
    // 6位数字 -> A股 (包括指数可能的纯数字输入)
    if (cleanCode.length === 6) {
      // 优先尝试指数验证 (如果是 000xxx 或 399xxx)
      if (cleanCode.startsWith('000') || cleanCode.startsWith('399')) {
          const indexRes = validateIndexStock(cleanCode);
          if (indexRes.valid) return indexRes;
      }
      
      // 尝试 A股股票验证
      const aStockRes = validateAStock(cleanCode)
      if (aStockRes.valid) {
        return aStockRes
      }

      // 如果不是有效的 A股股票代码，尝试作为通用指数代码验证
      // (支持如 98xxxx 等其他指数)
      const indexRes = validateIndexStock(cleanCode);
      if (indexRes.valid) {
        return indexRes;
      }

      return aStockRes; // 返回 A股验证的错误信息
    }
    
    // 1-5位数字 -> 港股
    if (cleanCode.length >= 1 && cleanCode.length <= 5) {
      return validateHKStock(cleanCode)
    }
    
    return {
      valid: false,
      message: '数字代码长度不正确（A股6位，港股1-5位）'
    }
  }
  
  // 包含字母 -> 美股 或 指数(带后缀)
  if (/[A-Za-z]/.test(trimmedCode)) {
    // 优先检查是否为 A股指数 (带后缀 或 H开头)
    if (trimmedCode.includes('.SH') || trimmedCode.includes('.SZ') || trimmedCode.startsWith('H')) {
        return validateIndexStock(trimmedCode);
    }
    return validateUSStock(trimmedCode)
  }
  
  return {
    valid: false,
    message: '无法识别的股票代码格式'
  }
}

/**
 * 获取股票代码格式说明
 */
export function getStockCodeFormatHelp(market: 'A股' | '美股' | '港股' | 'A股指数'): string {
  switch (market) {
    case 'A股':
      return '6位数字，如：000001（平安银行）、600519（贵州茅台）'
    case '美股':
      return '1-5个字母，如：AAPL（苹果）、TSLA（特斯拉）'
    case '港股':
      return '1-5位数字，如：700（腾讯）、9988（阿里巴巴）'
    case 'A股指数':
      return '6位数字，可带后缀，如：000001.SH（上证指数）、399001.SZ（深证成指）'
    default:
      return ''
  }
}

/**
 * 获取股票代码示例
 */
export function getStockCodeExamples(market: 'A股' | '美股' | '港股' | 'A股指数'): string[] {
  switch (market) {
    case 'A股':
      return ['000001', '600519', '000858', '300750']
    case '美股':
      return ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    case '港股':
      return ['00700', '09988', '01810', '03690']
    case 'A股指数':
      return ['000001.SH', '399001.SZ', '000300.SH', '399006.SZ']
    default:
      return []
  }
}

/**
 * 格式化股票代码显示
 * @param code 原始代码
 * @param market 市场类型
 */
export function formatStockCode(code: string, market: 'A股' | '美股' | '港股' | 'A股指数'): string {
  const validation = validateStockCode(code, market)
  return validation.normalizedCode || code
}

