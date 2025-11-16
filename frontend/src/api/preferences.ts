import { ApiClient, type ApiResponse } from './request'

export interface PreferenceItem {
  preference_id: string
  name: string
  description: string
  risk_level: number
  decision_speed: string
  is_system: boolean
}

export const PreferencesApi = {
  async listSystem(): Promise<ApiResponse<PreferenceItem[]>> {
    return ApiClient.get('/api/v1/preferences')
  }
}