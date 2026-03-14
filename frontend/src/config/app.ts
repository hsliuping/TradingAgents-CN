const fallbackVersion = '3.0.0'

const appVersion = (import.meta.env.VITE_APP_VERSION || '').trim() || fallbackVersion

export const APP_CONFIG = {
  version: appVersion,
  fullVersion: appVersion,
} as const