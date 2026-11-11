/**
 * 猪周期数据 API（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版无猪周期 Pro 领域数据，接口一律返回空数据，共享页面自动降级。
 */
export type PigCycleState = Record<string, any>
export type PigCycleL0State = Record<string, any>
export type TermWarnings = Record<string, any>
export type PigCyclePlan = Record<string, any>

/** 每日结论（社区版类型占位：保留共享页面读取的字段形状） */
export interface DailyReviewItem {
  date?: string
  coverage?: string
  summary?: string
  facts?: { fuses?: Record<string, string> }
  [key: string]: any
}

export async function fetchPigCycleState(_params?: any): Promise<PigCycleState | null> {
  return null
}

export async function fetchPigCycleL0(_params?: any): Promise<PigCycleL0State | null> {
  return null
}

export async function fetchTermWarnings(_params?: any): Promise<TermWarnings | null> {
  return null
}

export async function fetchPigCyclePlanCurrent(_params?: any): Promise<PigCyclePlan | null> {
  return null
}

export async function fetchDailyReviews(_params?: any): Promise<{ items: DailyReviewItem[] }> {
  return { items: [] }
}
