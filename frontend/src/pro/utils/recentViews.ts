/**
 * 最近浏览记录（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版无最近浏览后端，仅本地占位，不产生任何请求。
 */
export interface RecentView {
  code: string
  name: string
  ts: number
}

export function recordStockView(_code: string, _name?: string): void {
  // 社区版：不做记录
}

export async function fetchRemoteViews(_limit?: number): Promise<RecentView[]> {
  return []
}

export function getRecentViews(): RecentView[] {
  return []
}
