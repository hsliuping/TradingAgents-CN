export const DASHSCOPE_ENDPOINT_MODE_COMPATIBLE = 'compatible'
export const DASHSCOPE_ENDPOINT_MODE_CODING_PLAN = 'coding_plan'

export type DashScopeEndpointMode =
  | typeof DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
  | typeof DASHSCOPE_ENDPOINT_MODE_CODING_PLAN

export const DASHSCOPE_BASE_URL_MAP: Record<DashScopeEndpointMode, string> = {
  [DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  [DASHSCOPE_ENDPOINT_MODE_CODING_PLAN]: 'https://coding.dashscope.aliyuncs.com/v1'
}

export const DASHSCOPE_MODE_LABELS: Record<DashScopeEndpointMode, string> = {
  [DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]: '阿里百炼（兼容模式）',
  [DASHSCOPE_ENDPOINT_MODE_CODING_PLAN]: '千问 Coding Plan'
}

export const DASHSCOPE_MODELS_BY_MODE: Record<DashScopeEndpointMode, string[]> = {
  [DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]: [
    'qwen-turbo',
    'qwen-plus',
    'qwen-plus-latest',
    'qwen-max',
    'qwen-max-latest',
    'qwen-max-longcontext'
  ],
  [DASHSCOPE_ENDPOINT_MODE_CODING_PLAN]: [
    'qwen3.5-plus',
    'qwen3-max-2026-01-23',
    'qwen3-coder-next',
    'qwen3-coder-plus'
  ]
}

export const DASHSCOPE_DEFAULT_MODELS: Record<
  DashScopeEndpointMode,
  { quick: string; deep: string }
> = {
  [DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]: {
    quick: 'qwen-turbo',
    deep: 'qwen-max'
  },
  [DASHSCOPE_ENDPOINT_MODE_CODING_PLAN]: {
    quick: 'qwen3.5-plus',
    deep: 'qwen3-max-2026-01-23'
  }
}

export const normalizeDashScopeBaseUrl = (baseUrl?: string | null) => {
  if (!baseUrl) {
    return DASHSCOPE_BASE_URL_MAP[DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]
  }

  const normalized = baseUrl.replace(/\/$/, '')
  if (normalized.includes('coding.dashscope.aliyuncs.com')) {
    return DASHSCOPE_BASE_URL_MAP[DASHSCOPE_ENDPOINT_MODE_CODING_PLAN]
  }
  if (normalized.includes('dashscope.aliyuncs.com')) {
    return DASHSCOPE_BASE_URL_MAP[DASHSCOPE_ENDPOINT_MODE_COMPATIBLE]
  }
  return normalized
}

export const getDashScopeModeFromBaseUrl = (baseUrl?: string | null): DashScopeEndpointMode => {
  const normalized = normalizeDashScopeBaseUrl(baseUrl)
  if (normalized.includes('coding.dashscope.aliyuncs.com')) {
    return DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
  }
  return DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
}

export const getDashScopeBaseUrlForMode = (mode?: string | null) => {
  const normalizedMode =
    mode === DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      ? DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      : DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
  return DASHSCOPE_BASE_URL_MAP[normalizedMode]
}

export const getDashScopeModeFromModel = (
  modelName?: string | null,
  baseUrl?: string | null
): DashScopeEndpointMode => {
  if (modelName) {
    for (const [mode, models] of Object.entries(DASHSCOPE_MODELS_BY_MODE)) {
      if (models.includes(modelName)) {
        return mode as DashScopeEndpointMode
      }
    }
  }
  return getDashScopeModeFromBaseUrl(baseUrl)
}

export const getDashScopeBaseUrlForModel = (modelName?: string | null, baseUrl?: string | null) => {
  return getDashScopeBaseUrlForMode(getDashScopeModeFromModel(modelName, baseUrl))
}

export const getDashScopeDefaultModel = (mode?: string | null) => {
  const normalizedMode =
    mode === DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      ? DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      : DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
  return DASHSCOPE_DEFAULT_MODELS[normalizedMode].quick
}

export const getDashScopeDefaultDeepModel = (mode?: string | null) => {
  const normalizedMode =
    mode === DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      ? DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
      : DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
  return DASHSCOPE_DEFAULT_MODELS[normalizedMode].deep
}

export const buildDashScopeExtraConfig = (
  endpointMode?: string | null,
  existing: Record<string, any> = {}
) => {
  const mode =
    endpointMode && endpointMode in DASHSCOPE_BASE_URL_MAP
      ? (endpointMode as DashScopeEndpointMode)
      : getDashScopeModeFromBaseUrl(existing.default_base_url)

  return {
    ...existing,
    endpoint_mode: mode,
    endpoint_modes: [
      DASHSCOPE_ENDPOINT_MODE_COMPATIBLE,
      DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    ],
    base_url_map: { ...DASHSCOPE_BASE_URL_MAP }
  }
}
