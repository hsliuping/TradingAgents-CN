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

export interface PlannedAnalysisResponse extends ChatResponse {
  plan?: {
    question: string
    template_id?: string
    source: string
    steps: Array<{
      id: number
      tool: string
      args: Record<string, any>
      intent: string
      depends_on: number[]
    }>
  }
  step_results?: Array<{
    step_id: number
    tool: string
    intent: string
    success: boolean
    result?: any
    error?: string
    duration_ms: number
  }>
  source: 'seed_flow' | 'llm_plan' | 'react'
  supplemented: boolean
}

export interface MessageItem {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
}

export interface ConversationResponse {
  messages: MessageItem[]
}

export const assistantApi = {
  /** 获取会话历史 */
  async getConversation(): Promise<ConversationResponse> {
    const res = await request.get<ConversationResponse>('/api/assistant/conversation')
    return res as unknown as ConversationResponse
  },

  /** 清空会话 */
  async clearConversation(): Promise<void> {
    await request.delete('/api/assistant/conversation')
  },

  /** 发送对话消息 */
  async chat(message: string, conversationId?: string): Promise<ChatResponse> {
    const res = await request.post<ChatResponse>('/api/assistant/chat', {
      message,
      conversation_id: conversationId
    })
    return res as unknown as ChatResponse
  },

  /** 规划分析（Plan-then-Execute 模式） */
  async plannedAnalysis(message: string, conversationId?: string): Promise<PlannedAnalysisResponse> {
    const res = await request.post<PlannedAnalysisResponse>('/api/assistant/planned-analysis', {
      message,
      conversation_id: conversationId
    })
    return res as unknown as PlannedAnalysisResponse
  }
}
