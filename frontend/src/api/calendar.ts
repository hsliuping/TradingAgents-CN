import { request, type ApiResponse } from './request'

export type CalendarEvent = {
  event_id: string
  title: string
  summary?: string | null
  content?: string | null
  start_time: string
  end_time?: string | null
  date: string
  timezone: string
  region?: string | null
  category: string
  importance: number
  status: string
  tags: string[]
  source: string
  source_event_id: string
}

export type CalendarListResponse = {
  total: number
  items: CalendarEvent[]
}

export type CalendarAnalysisEnqueueResponse = {
  analysis_id: string
  task_id: string
  status: string
}

export type CalendarAnalysisDoc = {
  analysis_id: string
  task_id: string
  event_id: string
  status: string
  model_provider?: string | null
  model_name?: string | null
  prompt_version?: string
  result?: any
  error_message?: string | null
  created_at?: string
  updated_at?: string
}

export const calendarApi = {
  listEvents(params: { start: string; end: string; category?: string; min_importance?: number }) {
    return request.get<ApiResponse<{ total: number; items: CalendarEvent[] }>>('/api/market/calendar/events', { params })
  },
  sync(params: { start: string; end: string }) {
    return request.post<ApiResponse<any>>('/api/market/calendar/sync', null, { params })
  },
  analyze(eventId: string, body?: { model_name?: string; force_refresh?: boolean }) {
    return request.post<ApiResponse<CalendarAnalysisEnqueueResponse>>(`/api/market/calendar/events/${eventId}/analyze`, body || {})
  },
  getAnalysis(taskId: string) {
    return request.get<ApiResponse<CalendarAnalysisDoc>>(`/api/market/calendar/analyses/${taskId}`)
  },
  getLatestAnalysis(eventId: string) {
    return request.get<ApiResponse<CalendarAnalysisDoc>>(`/api/market/calendar/events/${eventId}/analysis`)
  }
}

