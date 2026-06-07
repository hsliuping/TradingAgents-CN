export type Currency = 'CNY' | 'HKD' | 'USD'
export type CurrencyAmountInput = number | string | Partial<Record<Currency, unknown>> | null | undefined

export const toFiniteNumber = (value: unknown, fallback = 0): number => {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string' && value.trim() === '') return fallback
  if (typeof value !== 'number' && typeof value !== 'string') return fallback

  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) ? numericValue : fallback
}

export const getCurrencyAmount = (
  amount: CurrencyAmountInput,
  currency: Currency,
  fallback = 0
): number => {
  if (typeof amount === 'number' || typeof amount === 'string') {
    return toFiniteNumber(amount, fallback)
  }

  if (amount && typeof amount === 'object' && !Array.isArray(amount)) {
    return toFiniteNumber(amount[currency], fallback)
  }

  return fallback
}

export const formatMoney = (value: unknown, fallback = 0): string => {
  return toFiniteNumber(value, fallback).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}
