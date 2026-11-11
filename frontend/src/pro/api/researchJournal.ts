/**
 * 研究日志 API（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版不提供研究日志后端，接口一律返回空数据，共享页面自动降级为空态。
 */
export type JournalJudgment = 'bullish' | 'bearish' | 'neutral' | string
export type HypothesisStatus = 'open' | 'confirmed' | 'falsified' | 'expired' | 'none' | string

export interface JournalJudgmentOption {
  value: string
  label: string
  tagType: 'success' | 'danger' | 'info'
}

export const JOURNAL_JUDGMENT_OPTIONS: JournalJudgmentOption[] = []

export const HYPOTHESIS_STATUS_LABELS: Record<string, string> = {}

export const DEFAULT_OVERDUE_DAYS = 90

/** 研究日志条目（社区版仅作类型占位，字段由调用方按需读取） */
export type ResearchJournalEntry = Record<string, any>
export type JournalReviewEntry = Record<string, any>
export type HypothesisScanItem = Record<string, any>

export interface JournalListData {
  items: ResearchJournalEntry[]
  total?: number
}

export interface HypothesisScanData {
  items: HypothesisScanItem[]
  count?: number
}

export function journalJudgmentLabel(value?: string | null): string {
  const map: Record<string, string> = {
    bullish: '看好',
    bearish: '看空',
    neutral: '中性',
  }
  return value ? map[value] ?? value : '—'
}

export function journalJudgmentTagType(
  value?: string | null,
): 'success' | 'danger' | 'info' {
  if (value === 'bullish') return 'success'
  if (value === 'bearish') return 'danger'
  return 'info'
}

export const researchJournalApi = {
  list: async (_stockCode?: string): Promise<JournalListData> => ({ items: [] }),
  add: async (_payload?: any): Promise<any> => null,
  update: async (_id?: string, _payload?: any): Promise<any> => null,
  remove: async (_id?: string): Promise<any> => null,
  review: async (_payload?: any): Promise<any> => ({ items: [] }),
  hypothesisScan: async (_payload?: any): Promise<HypothesisScanData> => ({ items: [] }),
}

export default researchJournalApi
