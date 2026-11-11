/**
 * 行业世界模型注册表（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版无行业工作台，注册表全部为空、命中判定恒为 null，共享页面自动降级为「无行业覆盖」。
 * 注意：本文件必须自包含，不得再引用任何 @/pro/* 模块（社区版这些模块已被剔除）。
 */
import { defineComponent } from 'vue'
import type { Component } from 'vue'

export type IndustryKey = 'pig' | 'insurance' | 'battery' | 'auto' | 'bank'

export interface RelatedStock {
  code: string
  name: string
  role: string
  segment?: string
}

export interface IndustrySummaryHit {
  key: IndustryKey
  label: string
  name: string
  path: string
  stock: RelatedStock
}

export interface IndustryRegistryEntry {
  key: IndustryKey
  code: string
  name: string
  label: string
  workbenchPath: string
  relatedStocks: RelatedStock[]
  allCodes: string[]
  summaryComponent: Component
  fetchState: () => Promise<any>
  fetchCompanyState?: (code: string) => Promise<any>
}

export interface IndustryCrossRef {
  label: string
  path: string
  note?: string
}

const EmptySummary = defineComponent({
  name: 'EmptyIndustrySummary',
  render: () => null,
})

const EMPTY_STOCKS: RelatedStock[] = []
const EMPTY_CODES: string[] = []

export const PIG_RELATED_STOCKS: RelatedStock[] = EMPTY_STOCKS
export const INSURANCE_RELATED_STOCKS: RelatedStock[] = EMPTY_STOCKS
export const BATTERY_RELATED_STOCKS: RelatedStock[] = EMPTY_STOCKS
export const AUTO_RELATED_STOCKS: RelatedStock[] = EMPTY_STOCKS
export const BANK_RELATED_STOCKS: RelatedStock[] = EMPTY_STOCKS

export const PIG_INDUSTRY_CODES: string[] = EMPTY_CODES
export const BANK_INDUSTRY_CODES: string[] = EMPTY_CODES

export function matchIndustryStock(
  _list: RelatedStock[],
  _stockName: string,
): RelatedStock | null {
  return null
}

export function findIndustryHits(_stockName: string): IndustrySummaryHit[] {
  return []
}

export function firstIndustryHit(_stockName: string): IndustrySummaryHit | null {
  return null
}

export function classifyIndustryByCode(_code: string): IndustryKey | null {
  return null
}

function emptyEntry(key: IndustryKey, label: string): IndustryRegistryEntry {
  return {
    key,
    code: '',
    name: '',
    label,
    workbenchPath: '',
    relatedStocks: EMPTY_STOCKS,
    allCodes: EMPTY_CODES,
    summaryComponent: EmptySummary,
    fetchState: async () => null,
  }
}

export const INDUSTRY_ORDER: IndustryKey[] = ['pig', 'insurance', 'battery', 'auto', 'bank']

export const INDUSTRY_REGISTRY: Record<IndustryKey, IndustryRegistryEntry> = {
  pig: emptyEntry('pig', '猪周期'),
  insurance: emptyEntry('insurance', '保险'),
  battery: emptyEntry('battery', '电池'),
  auto: emptyEntry('auto', '汽车'),
  bank: emptyEntry('bank', '银行'),
}

export const INDUSTRY_CROSS_REFS: Partial<Record<IndustryKey, IndustryCrossRef>> = {}
