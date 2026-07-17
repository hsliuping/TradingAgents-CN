import request from './request'

export interface CapabilityIndexState {
  sync_mode?: string
  total_documents?: number
  indexed_documents?: number
  skipped_documents?: number
  vector_backend?: string
  fingerprint?: string
  [key: string]: unknown
}

export interface RebuildResult {
  sync_mode: string
  total_documents: number
  indexed_documents: number
  skipped_documents: number
  vector_backend: string
}

/** 获取能力索引当前状态 */
export function getCapabilityIndexState() {
  return request.get('/api/capability-index/state')
}

/** 强制重建能力索引 */
export function rebuildCapabilityIndex() {
  return request.post('/api/capability-index/rebuild')
}
