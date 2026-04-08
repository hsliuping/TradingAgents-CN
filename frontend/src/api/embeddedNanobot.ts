import { request } from './request'

export interface EmbeddedNanobotStatusResponse {
  enabled: boolean
  user_id: string
  workspace: string
}

export interface EmbeddedNanobotChatRequest {
  message: string
  session_key?: string
  model?: string
  channel?: string
  chat_id?: string
  media?: string[]
  skill_names?: string[]
  thread_context?: EmbeddedNanobotThreadContext
}

export interface EmbeddedNanobotThreadContext {
  spec_id?: string
  spec_name?: string
  workshop_session_id?: string
  version_id?: string
  version_status?: string
  workflow_id?: string
  node_id?: string
  preference_id?: string
  debug_template_id?: string
}

export interface EmbeddedNanobotChatResponse {
  content: string
  session_key: string
  thread_id?: string
  stop_reason?: string
  tools_used: string[]
  usage: Record<string, number>
  tool_events: Array<Record<string, any>>
}

export interface EmbeddedNanobotThreadItem {
  thread_id: string
  title: string
  session_key: string
  channel: string
  archived: boolean
  message_count: number
  last_user_message: string
  summary: string
  created_at?: string
  updated_at?: string
  thread_context?: EmbeddedNanobotThreadContext
}

export interface EmbeddedNanobotMessageItem {
  message_id: string
  role: string
  content: string
  tools_used: string[]
  stop_reason?: string
  usage: Record<string, number>
  tool_events: Array<Record<string, any>>
  created_at?: string
}

export interface EmbeddedNanobotStreamCallbacks {
  onStarted?: (data: { message?: string; session_key?: string }) => void
  onProgress?: (data: { message?: string; session_key?: string }) => void
  onToken?: (content: string) => void
  onToolEvent?: (event: Record<string, any>) => void
  onStepEvent?: (event: Record<string, any>) => void
  onDone?: (data: EmbeddedNanobotChatResponse) => void
  onError?: (message: string) => void
  onAbort?: () => void
}

function createEmbeddedNanobotStream(
  path: string,
  payload: EmbeddedNanobotChatRequest,
  callbacks?: EmbeddedNanobotStreamCallbacks,
): AbortController {
  const controller = new AbortController()
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const token = localStorage.getItem('auth-token') || ''
  const appToken = localStorage.getItem('app-token') || ''

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (appToken) headers['X-App-Token'] = appToken

  fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(payload),
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
            if (eventType === 'started') {
              callbacks?.onStarted?.(data)
            } else if (eventType === 'progress') {
              callbacks?.onProgress?.(data)
            } else if (eventType === 'token') {
              callbacks?.onToken?.(data.content || '')
            } else if (eventType === 'tool_event') {
              callbacks?.onToolEvent?.(data)
            } else if (eventType === 'step_event') {
              callbacks?.onStepEvent?.(data)
            } else if (eventType === 'done') {
              callbacks?.onDone?.(data)
            } else if (eventType === 'error') {
              callbacks?.onError?.(data.message || '未知错误')
            }
          } catch {
            // Ignore malformed JSON chunks.
          }
        }
      }
    })
    .catch((err) => {
      if (err.name === 'AbortError') {
        callbacks?.onAbort?.()
      } else {
        callbacks?.onError?.(err.message || '网络请求失败，请检查网络连接后重试')
      }
    })

  return controller
}

export const embeddedNanobotApi = {
  async getStatus(): Promise<EmbeddedNanobotStatusResponse> {
    return await request.get('/api/embedded-nanobot/status') as unknown as EmbeddedNanobotStatusResponse
  },

  async listThreads(limit = 50, archivedOnly = false): Promise<{ items: EmbeddedNanobotThreadItem[]; total: number }> {
    return await request.get(`/api/embedded-nanobot/threads?limit=${limit}&archived_only=${archivedOnly}`) as unknown as { items: EmbeddedNanobotThreadItem[]; total: number }
  },

  async getThreadMessages(threadId: string): Promise<{ thread: EmbeddedNanobotThreadItem | null; messages: EmbeddedNanobotMessageItem[] }> {
    return await request.get(`/api/embedded-nanobot/threads/${encodeURIComponent(threadId)}/messages`) as unknown as { thread: EmbeddedNanobotThreadItem | null; messages: EmbeddedNanobotMessageItem[] }
  },

  async deleteThread(threadId: string): Promise<{ archived: boolean; thread_id: string; deleted_messages: number }> {
    return await request.delete(`/api/embedded-nanobot/threads/${encodeURIComponent(threadId)}`) as unknown as { archived: boolean; thread_id: string; deleted_messages: number }
  },

  async restoreThread(threadId: string): Promise<{ restored: boolean; thread_id: string; archived: boolean }> {
    return await request.post(`/api/embedded-nanobot/threads/${encodeURIComponent(threadId)}/restore`) as unknown as { restored: boolean; thread_id: string; archived: boolean }
  },

  async updateThreadContext(
    threadId: string,
    payload: { session_key?: string; channel?: string; thread_context: EmbeddedNanobotThreadContext },
  ): Promise<{ thread: EmbeddedNanobotThreadItem | null; messages: EmbeddedNanobotMessageItem[] }> {
    return await request.put(
      `/api/embedded-nanobot/threads/${encodeURIComponent(threadId)}/context`,
      payload,
      {
        skipAuthError: true,
        skipErrorHandler: true,
      },
    ) as unknown as { thread: EmbeddedNanobotThreadItem | null; messages: EmbeddedNanobotMessageItem[] }
  },

  async chat(payload: EmbeddedNanobotChatRequest): Promise<EmbeddedNanobotChatResponse> {
    return await request.post('/api/embedded-nanobot/chat', payload) as unknown as EmbeddedNanobotChatResponse
  },

  chatStream(payload: EmbeddedNanobotChatRequest, callbacks?: EmbeddedNanobotStreamCallbacks): AbortController {
    return createEmbeddedNanobotStream('/api/embedded-nanobot/chat/stream', payload, callbacks)
  },
}

export default embeddedNanobotApi