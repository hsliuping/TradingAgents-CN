/**
 * 个股资料库 API（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版不提供「我的资料」后端，接口一律返回空数据，共享页面降级为空态。
 */
export type MaterialKind = 'link' | 'note' | 'file' | string
export type MaterialCategory = string
export type MaterialSourceTier = string
export type StockMaterial = Record<string, any>
export type IntelCard = Record<string, any>

export const MATERIAL_FILE_EXTENSIONS: string[] = []
export const MAX_MATERIAL_FILE_SIZE = 0

export const MATERIAL_CATEGORY_OPTIONS: Array<{ label: string; value: string }> = []
export const MATERIAL_SOURCE_TIER_OPTIONS: Array<{ label: string; value: string }> = []

export function materialCategoryLabel(value?: string | null): string {
  return value || '—'
}

export function materialSourceTierLabel(value?: string | null): string {
  return value || '—'
}

export function materialSourceTierTagType(
  _value?: string | null,
): 'success' | 'warning' | 'info' | 'danger' {
  return 'info'
}

export async function fetchStockMaterials(_stockCode?: string): Promise<StockMaterial[]> {
  return []
}

export async function addStockMaterial(_payload?: any): Promise<any> {
  return null
}

export async function updateStockMaterial(_id?: string, _payload?: any): Promise<any> {
  return null
}

export async function deleteStockMaterial(_id?: string): Promise<any> {
  return null
}

export interface MaterialUploadOptions {
  stockName?: string
  title?: string
  category?: MaterialCategory
  sourceTier?: MaterialSourceTier
  sourceNote?: string
  remark?: string
  onProgress?: (percent: number) => void
}

export async function uploadStockMaterial(
  _stockCode?: string,
  _file?: File,
  _options?: MaterialUploadOptions,
): Promise<any> {
  return null
}

export async function fetchMaterialText(_id?: string): Promise<any> {
  return null
}

export async function reextractMaterialText(_id?: string): Promise<any> {
  return null
}

export async function distillMaterialIntel(_id?: string): Promise<any> {
  return null
}

export async function fetchMaterialIntelCard(_id?: string): Promise<IntelCard | null> {
  return null
}

export function materialFileUrl(_id?: string): string {
  return ''
}
