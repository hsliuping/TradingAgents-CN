/**
 * 渠道推送配置 API
 * 支持飞书/钉钉/企业微信 Webhook + 邮件渠道
 */
import request from '@/utils/request'

export type ChannelType = 'feishu' | 'dingtalk' | 'wechatwork' | 'email'

export interface ChannelConfig {
  channel_id: string
  type: ChannelType
  name: string
  enabled: boolean
  webhook_url?: string
  email_address?: string
  events: string[]
  created_at?: string
  updated_at?: string
}

export interface ChannelConfigCreate {
  type: ChannelType
  name: string
  enabled?: boolean
  webhook_url?: string
  email_address?: string
  events?: string[]
}

export interface ChannelConfigUpdate {
  name?: string
  enabled?: boolean
  webhook_url?: string
  email_address?: string
  events?: string[]
}

export interface TestSendRequest {
  title?: string
  content?: string
}

// 获取渠道列表
export const getChannels = () =>
  request.get<{ channels: ChannelConfig[] }>('/api/channel-configs')

// 添加渠道
export const createChannel = (data: ChannelConfigCreate) =>
  request.post<{ channel: ChannelConfig }>('/api/channel-configs', data)

// 更新渠道
export const updateChannel = (channelId: string, data: ChannelConfigUpdate) =>
  request.put<{ channel: ChannelConfig }>(`/api/channel-configs/${channelId}`, data)

// 删除渠道
export const deleteChannel = (channelId: string) =>
  request.delete<{ success: boolean }>(`/api/channel-configs/${channelId}`)

// 测试推送
export const testChannel = (channelId: string, data?: TestSendRequest) =>
  request.post<{ success: boolean; message: string }>(
    `/api/channel-configs/${channelId}/test`,
    data || {}
  )

// 获取支持的事件类型
export const getEventTypes = () =>
  request.get<{ event_types: string[] }>('/api/channel-configs/event-types')

