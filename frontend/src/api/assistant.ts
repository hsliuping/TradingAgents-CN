/**
 * 智能助手 API
 */

import { request } from './request'

export interface ChatRequest {
  message: string
  conversation_id?: string
  quick_model?: string
  deep_model?: string
}

export interface ChatResponse {
  reply: string
  tools_used: string[]
  data_refs?: unknown[]
  conversation_id?: string
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
  conversation_id?: string
}

export interface AssistantThreadSummary {
  abstract: string
  confirmed_facts: string[]
  open_questions: string[]
  next_actions: string[]
  focus_score: number
}

export interface AssistantThreadReportRef {
  ref_type: string
  report_key: string
  source_collection: string
  title: string
  symbol?: string | null
  summary: string
  status?: string | null
  task_id?: string | null
  analysis_id?: string | null
  created_at?: string | null
  linked_at?: string | null
}

export interface AssistantThreadReportDetail {
  ref_type: string
  report_key: string
  title: string
  symbol?: string | null
  status?: string | null
  task_id?: string | null
  analysis_id?: string | null
  created_at?: string | null
  linked_at?: string | null
  content: string
  content_format: string
}

export interface AssistantThreadReportDetailResponse {
  detail: AssistantThreadReportDetail
}

export interface AssistantThreadReportSearchResponse {
  items: AssistantThreadReportRef[]
  total: number
}

export interface AssistantThreadAttachReportResponse {
  success: boolean
  attached_ref: AssistantThreadReportRef
}

export interface AssistantThreadItem {
  thread_id: string
  title: string
  parent_thread_id?: string | null
  topic_type: string
  pinned: boolean
  archived: boolean
  message_count: number
  last_user_message: string
  updated_at?: string
  report_refs: AssistantThreadReportRef[]
  current_summary?: AssistantThreadSummary
}

export interface AssistantThreadListResponse {
  items: AssistantThreadItem[]
  total: number
}

export interface AssistantThreadMessagesResponse extends ConversationResponse {
  thread?: AssistantThreadItem
}

export interface ThreadSummarizeResponse {
  conversation_id: string
  summary: AssistantThreadSummary
}

export interface ThreadDeleteResponse {
  success: boolean
  deleted_thread_ids: string[]
}

export interface StreamCallbacks {
  onToken?: (content: string) => void
  onToolEvent?: (event: Record<string, any>) => void
  onDone?: (data: { tools_used: string[]; conversation_id?: string }) => void
  onError?: (message: string) => void
}

export const assistantApi = {
  /** 获取主题列表 */
  async getThreads(): Promise<AssistantThreadListResponse> {
    const res = await request.get<AssistantThreadListResponse>('/api/assistant/threads')
    return res as unknown as AssistantThreadListResponse
  },

  /** 创建新主题 */
  async createThread(title?: string, parentThreadId?: string): Promise<AssistantThreadItem> {
    const res = await request.post<AssistantThreadItem>('/api/assistant/threads', {
      title,
      parent_thread_id: parentThreadId
    })
    return res as unknown as AssistantThreadItem
  },

  /** 删除主题及其子主题 */
  async deleteThread(threadId: string): Promise<ThreadDeleteResponse> {
    const res = await request.delete<ThreadDeleteResponse>(`/api/assistant/threads/${threadId}`)
    return res as unknown as ThreadDeleteResponse
  },

  /** 获取指定主题消息 */
  async getThreadMessages(threadId: string): Promise<AssistantThreadMessagesResponse> {
    const res = await request.get<AssistantThreadMessagesResponse>(`/api/assistant/threads/${threadId}/messages`)
    return res as unknown as AssistantThreadMessagesResponse
  },

  /** 获取主题关联报告详情 */
  async getThreadReportDetail(threadId: string, refType: string, reportKey: string): Promise<AssistantThreadReportDetailResponse> {
    const encodedRefType = encodeURIComponent(refType)
    const encodedReportKey = encodeURIComponent(reportKey)
    const res = await request.get<AssistantThreadReportDetailResponse>(
      `/api/assistant/threads/${threadId}/reports/${encodedRefType}/${encodedReportKey}`
    )
    return res as unknown as AssistantThreadReportDetailResponse
  },

  /** 搜索可关联旧报告 */
  async getThreadReportCandidates(threadId: string, refType: string, keyword?: string, limit = 8): Promise<AssistantThreadReportSearchResponse> {
    const res = await request.get<AssistantThreadReportSearchResponse>(`/api/assistant/threads/${threadId}/report-candidates`, {
      params: {
        ref_type: refType,
        keyword,
        limit,
      }
    })
    return res as unknown as AssistantThreadReportSearchResponse
  },

  /** 手动关联旧报告 */
  async attachThreadReport(threadId: string, refType: string, reportKey: string): Promise<AssistantThreadAttachReportResponse> {
    const res = await request.post<AssistantThreadAttachReportResponse>(`/api/assistant/threads/${threadId}/report-links`, {
      ref_type: refType,
      report_key: reportKey,
    })
    return res as unknown as AssistantThreadAttachReportResponse
  },

  /** 清空指定主题 */
  async clearThreadMessages(threadId: string): Promise<void> {
    await request.delete(`/api/assistant/threads/${threadId}/messages`)
  },

  /** 手动总结指定主题 */
  async summarizeThread(threadId: string): Promise<ThreadSummarizeResponse> {
    const res = await request.post<ThreadSummarizeResponse>(`/api/assistant/threads/${threadId}/summarize`)
    return res as unknown as ThreadSummarizeResponse
  },

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
  async chat(message: string, conversationId?: string, quickModel?: string, deepModel?: string): Promise<ChatResponse> {
    const res = await request.post<ChatResponse>('/api/assistant/chat', {
      message,
      conversation_id: conversationId,
      quick_model: quickModel,
      deep_model: deepModel,
    })
    return res as unknown as ChatResponse
  },

  /** 规划分析（Plan-then-Execute 模式） */
  async plannedAnalysis(message: string, conversationId?: string, quickModel?: string, deepModel?: string): Promise<PlannedAnalysisResponse> {
    const res = await request.post<PlannedAnalysisResponse>('/api/assistant/planned-analysis', {
      message,
      conversation_id: conversationId,
      quick_model: quickModel,
      deep_model: deepModel,
    })
    return res as unknown as PlannedAnalysisResponse
  },

  /** 流式对话（SSE）— 快速对话模式使用 */
  chatStream(
    message: string,
    conversationId?: string,
    quickModel?: string,
    deepModel?: string,
    callbacks?: StreamCallbacks,
  ): AbortController {
    const controller = new AbortController()
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    const token = localStorage.getItem('auth-token') || ''
    const appToken = localStorage.getItem('app-token') || ''

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    if (appToken) headers['X-App-Token'] = appToken

    fetch(`${baseUrl}/api/assistant/chat/stream`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        quick_model: quickModel,
        deep_model: deepModel,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          callbacks?.onError?.(`HTTP ${response.status}: ${response.statusText}`)
          return
        }

        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''

          for (const part of parts) {
            if (!part.trim() || part.startsWith(': ')) continue

            let eventType = ''
            let eventData = ''

            for (const line of part.split('\n')) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7)
              } else if (line.startsWith('data: ')) {
                eventData = line.slice(6)
              }
            }

            if (!eventData) continue

            try {
              const data = JSON.parse(eventData)
              switch (eventType) {
                case 'token':
                  callbacks?.onToken?.(data.content || '')
                  break
                case 'done':
                  callbacks?.onDone?.(data)
                  break
                case 'error':
                  callbacks?.onError?.(data.message || '未知错误')
                  break
                default:
                  callbacks?.onToolEvent?.({ ...data, event: eventType || data.event })
              }
            } catch {
              // Ignore malformed JSON
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          callbacks?.onError?.(err.message || '网络请求失败')
        }
      })

    return controller
  },
}
