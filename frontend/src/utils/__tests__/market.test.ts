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

  describe('港股识别', () => {
    it('应该识别带.HK后缀的代码为港股', () => {
      expect(getMarketByStockCode('0700.HK')).toBe('港股')
      expect(getMarketByStockCode('9988.HK')).toBe('港股')
      expect(getMarketByStockCode('1810.HK')).toBe('港股')
    })

    it('应该识别1位数字为港股', () => {
      expect(getMarketByStockCode('1')).toBe('港股')
      expect(getMarketByStockCode('2')).toBe('港股')
    })

    it('应该识别2位数字为港股', () => {
      expect(getMarketByStockCode('01')).toBe('港股')
      expect(getMarketByStockCode('88')).toBe('港股')
    })

    it('应该识别3位数字为港股', () => {
      expect(getMarketByStockCode('700')).toBe('港股')
      expect(getMarketByStockCode('388')).toBe('港股')
    })

    it('应该识别4位数字为港股', () => {
      expect(getMarketByStockCode('1810')).toBe('港股')
      expect(getMarketByStockCode('9988')).toBe('港股')
      expect(getMarketByStockCode('3690')).toBe('港股')
    })

    it('应该识别5位数字为港股', () => {
      expect(getMarketByStockCode('00700')).toBe('港股')
      expect(getMarketByStockCode('09988')).toBe('港股')
      expect(getMarketByStockCode('01810')).toBe('港股')
    })
  })

  describe('美股识别', () => {
    it('应该识别纯字母代码为美股', () => {
      expect(getMarketByStockCode('AAPL')).toBe('美股')
      expect(getMarketByStockCode('TSLA')).toBe('美股')
      expect(getMarketByStockCode('GOOGL')).toBe('美股')
      expect(getMarketByStockCode('MSFT')).toBe('美股')
    })

    it('应该识别小写字母代码为美股', () => {
      expect(getMarketByStockCode('aapl')).toBe('美股')
      expect(getMarketByStockCode('tsla')).toBe('美股')
    })
  })

  describe('边界情况', () => {
    it('应该处理空字符串', () => {
      expect(getMarketByStockCode('')).toBe('A股') // 默认返回A股
    })

    it('应该处理带空格的代码', () => {
      expect(getMarketByStockCode(' 700 ')).toBe('港股')
      expect(getMarketByStockCode(' AAPL ')).toBe('美股')
    })
  })
})

