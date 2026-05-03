import { ApiClient, type ApiResponse } from './request'

export interface AdvancedLessonContentPayload {
  filename: string
  content: string
}

export interface AdvancedSampleContentPayload {
  sample_id: string
  filename: string
  content: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export function getAdvancedLessonContent(filename: string): Promise<ApiResponse<AdvancedLessonContentPayload>> {
  return ApiClient.get('/api/learning/advanced-courses/lessons/content', { filename })
}

export function downloadAdvancedLesson(filename: string) {
  return ApiClient.download(
    `/api/learning/advanced-courses/lessons/download?filename=${encodeURIComponent(filename)}`,
    filename
  )
}

export function getAdvancedSampleContent(sampleId: string): Promise<ApiResponse<AdvancedSampleContentPayload>> {
  return ApiClient.get(`/api/learning/advanced-courses/samples/${encodeURIComponent(sampleId)}`)
}

export function downloadAdvancedSample(sampleId: string, filename: string) {
  return ApiClient.download(
    `/api/learning/advanced-courses/samples/${encodeURIComponent(sampleId)}/download`,
    filename
  )
}

export function getAdvancedCourseImageUrl(imagePath: string) {
  const encodedPath = imagePath
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/')

  return `${API_BASE_URL}/api/learning/advanced-courses/images/${encodedPath}`
}