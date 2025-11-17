import { ApiClient, type ApiResponse } from './request'

export interface ModelCapabilityItem {
  provider: string
  models: Array<{ name: string; type?: string; max_tokens?: number }>
}

export const ModelCapabilitiesApi = {
  async list(): Promise<ApiResponse<ModelCapabilityItem[]>> {
    return ApiClient.get('/api/v1/model-capabilities')
  }
}