import { describe, expect, it } from 'vitest'
import { formatMoney, getCurrencyAmount, toFiniteNumber } from '../number'

describe('number utilities', () => {
  describe('toFiniteNumber', () => {
    it('accepts finite numbers and numeric strings', () => {
      expect(toFiniteNumber(12.34)).toBe(12.34)
      expect(toFiniteNumber('12.34')).toBe(12.34)
      expect(toFiniteNumber(' 1000 ')).toBe(1000)
    })

    it('falls back for missing or non-finite values', () => {
      expect(toFiniteNumber(null)).toBe(0)
      expect(toFiniteNumber(undefined)).toBe(0)
      expect(toFiniteNumber('')).toBe(0)
      expect(toFiniteNumber({})).toBe(0)
      expect(toFiniteNumber([])).toBe(0)
      expect(toFiniteNumber(true, 9)).toBe(9)
      expect(toFiniteNumber(Number.NaN, 9)).toBe(9)
      expect(toFiniteNumber(Number.POSITIVE_INFINITY, 9)).toBe(9)
    })
  })

  describe('formatMoney', () => {
    it('formats numbers and numeric strings with thousands separators', () => {
      expect(formatMoney(1000000)).toBe('1,000,000.00')
      expect(formatMoney('1000000')).toBe('1,000,000.00')
    })

    it('uses zero for invalid money values', () => {
      expect(formatMoney(null)).toBe('0.00')
      expect(formatMoney(undefined)).toBe('0.00')
      expect(formatMoney({})).toBe('0.00')
      expect(formatMoney('')).toBe('0.00')
    })
  })

  describe('getCurrencyAmount', () => {
    it('reads and normalizes values from currency objects', () => {
      expect(getCurrencyAmount({ CNY: '1000' }, 'CNY')).toBe(1000)
      expect(getCurrencyAmount({ HKD: null }, 'HKD')).toBe(0)
    })

    it('supports legacy scalar amounts', () => {
      expect(getCurrencyAmount(123, 'CNY')).toBe(123)
      expect(getCurrencyAmount('456', 'USD')).toBe(456)
    })

    it('uses fallback for missing currencies or malformed values', () => {
      expect(getCurrencyAmount({ CNY: 100 }, 'USD', 7)).toBe(7)
      expect(getCurrencyAmount({ USD: {} }, 'USD', 7)).toBe(7)
      expect(getCurrencyAmount(undefined, 'CNY', 7)).toBe(7)
    })
  })
})
