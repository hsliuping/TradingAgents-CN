import { ApiClient } from './request'

export interface RecentViewItem {
  code: string
  name: string
  viewed_at?: string
}

export const recentViewsApi = {
  /** 记录一次个股访问（未登录/离线时后端静默失败，前端 localStorage 兜底） */
  record: (code: string, name: string) =>
    ApiClient.post<{ recorded: boolean }>('/api/recent-views', { code, name }),
  /** 最近浏览的个股（按浏览时间倒序，跨浏览器跟随账号） */
  list: (limit = 6) =>
    ApiClient.get<RecentViewItem[]>(`/api/recent-views?limit=${limit}`),
}
