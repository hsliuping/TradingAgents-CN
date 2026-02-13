/**
 * 智能助手 API
 */

import { request } from './request'

export interface ChatRequest {
  message: string
  conversation_id?: string
}

export interface ChatResponse {
  reply: string
  tools_used: string[]
  data_refs?: unknown[]
}

export const assistantApi = {
  /** 发送对话消息 */
  async chat(message: string, conversationId?: string): Promise<ChatResponse> {
    const res = await request.post<ChatResponse>('/api/assistant/chat', {
      message,
      conversation_id: conversationId
    })
    return res as unknown as ChatResponse
  }
}
