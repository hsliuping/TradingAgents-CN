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
}

export interface EmbeddedNanobotChatResponse {
  content: string
  session_key: string
  stop_reason?: string
  tools_used: string[]
  usage: Record<string, number>
  tool_events: Array<Record<string, any>>
}

export interface EmbeddedNanobotStreamCallbacks {
  onStarted?: (data: { message?: string; session_key?: string }) => void
  onProgress?: (data: { message?: string; session_key?: string }) => void
  onToken?: (content: string) => void
  onToolEvent?: (event: Record<string, any>) => void
  onDone?: (data: EmbeddedNanobotChatResponse) => void
  onError?: (message: string) => void
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
      if (err.name !== 'AbortError') {
        callbacks?.onError?.(err.message || '网络请求失败，请检查网络连接后重试')
      }
    })

  return controller
}

export const embeddedNanobotApi = {
  async getStatus(): Promise<EmbeddedNanobotStatusResponse> {
    return await request.get('/api/embedded-nanobot/status') as unknown as EmbeddedNanobotStatusResponse
  },

  async chat(payload: EmbeddedNanobotChatRequest): Promise<EmbeddedNanobotChatResponse> {
    return await request.post('/api/embedded-nanobot/chat', payload) as unknown as EmbeddedNanobotChatResponse
  },

  chatStream(payload: EmbeddedNanobotChatRequest, callbacks?: EmbeddedNanobotStreamCallbacks): AbortController {
    return createEmbeddedNanobotStream('/api/embedded-nanobot/chat/stream', payload, callbacks)
  },
}

export default embeddedNanobotApi