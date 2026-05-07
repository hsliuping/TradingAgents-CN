const MODEL_SELECTION_DELIMITER = '::'

type ModelLike = {
  provider?: string
  model_name?: string
  model_display_name?: string
}

export interface ParsedModelSelection {
  provider: string
  modelName: string
}

export const normalizeModelProvider = (provider?: string | null): string => {
  return String(provider || '').trim().toLowerCase()
}

export const encodeModelSelection = (model: ModelLike): string => {
  const provider = normalizeModelProvider(model.provider)
  const modelName = String(model.model_name || '').trim()

  if (!provider || !modelName) {
    return modelName
  }

  return `${provider}${MODEL_SELECTION_DELIMITER}${modelName}`
}

export const parseModelSelection = (value?: string | null): ParsedModelSelection => {
  const raw = String(value || '').trim()
  if (!raw) {
    return { provider: '', modelName: '' }
  }

  const delimiterIndex = raw.indexOf(MODEL_SELECTION_DELIMITER)
  if (delimiterIndex <= 0) {
    return { provider: '', modelName: raw }
  }

  return {
    provider: normalizeModelProvider(raw.slice(0, delimiterIndex)),
    modelName: raw.slice(delimiterIndex + MODEL_SELECTION_DELIMITER.length).trim(),
  }
}

export const matchesModelSelection = (model: ModelLike, selection?: string | null): boolean => {
  const { provider, modelName } = parseModelSelection(selection)
  const currentModelName = String(model.model_name || '').trim()

  if (!modelName || currentModelName !== modelName) {
    return false
  }

  if (!provider) {
    return true
  }

  return normalizeModelProvider(model.provider) === provider
}

export const findModelBySelection = <T extends ModelLike>(models: T[], selection?: string | null): T | undefined => {
  return models.find(model => matchesModelSelection(model, selection))
}

export const resolveModelSelection = <T extends ModelLike>(
  selection: string | undefined | null,
  models: T[],
  preferredProvider?: string | null
): string => {
  const raw = String(selection || '').trim()
  if (!raw) {
    return ''
  }

  const parsed = parseModelSelection(raw)
  if (parsed.provider) {
    const exactMatch = findModelBySelection(models, raw)
    return exactMatch ? encodeModelSelection(exactMatch) : raw
  }

  const matches = models.filter(model => String(model.model_name || '').trim() === parsed.modelName)
  if (matches.length === 0) {
    return raw
  }

  const normalizedPreferredProvider = normalizeModelProvider(preferredProvider)
  if (normalizedPreferredProvider) {
    const preferredMatch = matches.find(model => normalizeModelProvider(model.provider) === normalizedPreferredProvider)
    if (preferredMatch) {
      return encodeModelSelection(preferredMatch)
    }
  }

  if (matches.length === 1) {
    return encodeModelSelection(matches[0])
  }

  return raw
}

export const getModelOptionLabel = (model: ModelLike): string => {
  const baseName = String(model.model_display_name || model.model_name || '').trim()
  const provider = String(model.provider || '').trim()

  if (!provider) {
    return baseName
  }

  return `${baseName} (${provider})`
}