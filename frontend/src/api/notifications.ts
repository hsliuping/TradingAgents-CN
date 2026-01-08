import { request } from './request'

export interface NotificationItem {
  id: string
  title: string
  content?: string
  type: 'analysis' | 'alert' | 'system'
  status: 'unread' | 'read'
  created_at: string
  link?: string
  source?: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total?: number
  page?: number
  page_size?: number
}

export const notificationsApi = {
  async getUnreadCount(): Promise<{ success: boolean; data: { count: number } }> {
    // 后端尚未提供时兜底为0
    try {
      return await request.get('/api/notifications/unread_count')
    } catch {
      return { success: true, data: { count: 0 } }
    }
  },

  async getList(params?: { status?: 'unread' | 'all'; page?: number; page_size?: number; type?: string }): Promise<{ success: boolean; data: NotificationListResponse }> {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    if (params?.type) query.set('type', params.type)
    const url = query.toString() ? `/api/notifications?${query.toString()}` : '/api/notifications'
    try {
      return await request.get(url)
    } catch {
      return { success: true, data: { items: [], total: 0, page: params?.page ?? 1, page_size: params?.page_size ?? 20 } }
    }
  },

  async markRead(id: string): Promise<{ success: boolean }> {
    try {
      return await request.post(`/api/notifications/${id}/read`)
    } catch {
      return { success: true }
    }
  },

  async markAllRead(): Promise<{ success: boolean }> {
    try {
      return await request.post('/api/notifications/read_all')
    } catch {
      return { success: true }
    }
  }
}

