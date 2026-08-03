import { ApiClient } from './request'

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
  service_status: 'READY' | 'DEGRADED'
  error_code?: string | null
}

export interface NotificationUnreadResponse {
  count: number
  service_status: 'READY' | 'DEGRADED'
  error_code?: string | null
}

export const notificationsApi = {
  async getUnreadCount(): Promise<{ success: boolean; data: NotificationUnreadResponse; message?: string }> {
    return await ApiClient.get('/api/notifications/unread_count', undefined, { skipErrorHandler: true })
  },

  async getList(params?: { status?: 'unread' | 'all'; page?: number; page_size?: number; type?: string }): Promise<{ success: boolean; data: NotificationListResponse }> {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    if (params?.type) query.set('type', params.type)
    const url = query.toString() ? `/api/notifications?${query.toString()}` : '/api/notifications'
    return await ApiClient.get(url, undefined, { skipErrorHandler: true })
  },

  async markRead(id: string): Promise<{ success: boolean }> {
    return await ApiClient.post(`/api/notifications/${id}/read`, undefined, { skipErrorHandler: true })
  },

  async markAllRead(): Promise<{ success: boolean }> {
    return await ApiClient.post('/api/notifications/read_all', undefined, { skipErrorHandler: true })
  }
}
