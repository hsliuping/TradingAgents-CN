const fallbackVersion = '4.0.0-beta.1'

const appVersion = (import.meta.env.VITE_APP_VERSION || '').trim() || fallbackVersion

export const APP_CONFIG = {
  version: appVersion,
  fullVersion: appVersion,
} as const