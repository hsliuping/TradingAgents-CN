import { ApiClient } from './request'
import type { ApiResponse } from './request'

export interface TagItem {
  id: string
  name: string
  color: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface CreateTagDto {
  name: string
  color?: string
  sort_order?: number
}

export interface UpdateTagDto {
  name?: string
  color?: string
  sort_order?: number
}

export const tagsApi = {
  async list(): Promise<ApiResponse<TagItem[]>> {
    return await ApiClient.get<TagItem[]>('/api/tags/')
  },
  async create(payload: CreateTagDto): Promise<ApiResponse<TagItem>> {
    return await ApiClient.post<TagItem>('/api/tags/', payload)
  },
  async update(id: string, payload: UpdateTagDto): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.put<{ id: string }>(`/api/tags/${id}`, payload)
  },
  async remove(id: string): Promise<ApiResponse<{ id: string }>> {
    return await ApiClient.delete<{ id: string }>(`/api/tags/${id}`)
  }
}

