import { describe, it, expect } from 'vitest'
import { getMarketByStockCode } from '../market'

describe('getMarketByStockCode', () => {
  describe('A股识别', () => {
    it('应该识别6位数字为A股', () => {
      expect(getMarketByStockCode('000001')).toBe('A股')
      expect(getMarketByStockCode('600519')).toBe('A股')
      expect(getMarketByStockCode('300750')).toBe('A股')
      expect(getMarketByStockCode('688981')).toBe('A股')
    })
  })

  describe('边界情况', () => {
    it('应该处理空字符串', () => {
      expect(getMarketByStockCode('')).toBe('A股') // 默认返回A股
    })
  })
})

