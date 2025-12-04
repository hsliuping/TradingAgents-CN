/**
 * 模型能力管理 API
 */

import { request } from './request'

/**
 * 模型能力信息
 */
export interface ModelCapabilityInfo {
  model_name: string
  capability_level: number
  suitable_roles: string[]
  features: string[]
  recommended_depths: string[]
  performance_metrics?: {
    speed: number
    cost: number
    quality: number
  }
  description?: string
}

/**
 * 模型推荐响应
 */
export interface ModelRecommendationResponse {
  quick_model: string
  deep_model: string
  quick_model_info: ModelCapabilityInfo
  deep_model_info: ModelCapabilityInfo
  reason: string
}

/**
 * 模型验证响应
 */
export interface ModelValidationResponse {
  valid: boolean
  warnings: string[]
  recommendations: string[]
}

/**
 * 徽章样式
 */
export interface BadgeStyle {
  text: string
  color: string
  icon: string
}

/**
 * 所有徽章样式
 */
export interface AllBadges {
  capability_levels: Record<string, BadgeStyle>
  roles: Record<string, BadgeStyle>
  features: Record<string, BadgeStyle>
}

/**
 * 分析深度要求
 */
export interface DepthRequirement {
  min_capability: number
  quick_model_min: number
  deep_model_min: number
  required_features: string[]
  description: string
}

/**
 * 获取所有默认模型能力配置
 */
export function getDefaultModelConfigs() {
  return request({
    url: '/api/model-capabilities/default-configs',
    method: 'get'
  })
}

/**
 * 获取分析深度要求
 */
export function getDepthRequirements() {
  return request({
    url: '/api/model-capabilities/depth-requirements',
    method: 'get'
  })
}

/**
 * 获取能力等级描述
 */
export function getCapabilityDescriptions() {
  return request({
    url: '/api/model-capabilities/capability-descriptions',
    method: 'get'
  })
}

/**
 * 获取所有徽章样式
 */
export function getAllBadges() {
  return request({
    url: '/api/model-capabilities/badges',
    method: 'get'
  })
}

/**
 * 推荐模型
 * @param researchDepth 研究深度：快速/基础/标准/深度/全面
 */
export function recommendModels(researchDepth: string) {
  return request({
    url: '/api/model-capabilities/recommend',
    method: 'post',
    data: {
      research_depth: researchDepth
    }
  })
}

/**
 * 验证模型对
 * @param quickModel 快速模型
 * @param deepModel 深度模型
 * @param researchDepth 研究深度
 */
export function validateModels(quickModel: string, deepModel: string, researchDepth: string) {
  return request({
    url: '/api/model-capabilities/validate',
    method: 'post',
    data: {
      quick_model: quickModel,
      deep_model: deepModel,
      research_depth: researchDepth
    }
  })
}

/**
 * 批量初始化模型能力
 * @param overwrite 是否覆盖已有配置
 */
export function batchInitCapabilities(overwrite: boolean = false) {
  return request({
    url: '/api/model-capabilities/batch-init',
    method: 'post',
    data: {
      overwrite
    }
  })
}

/**
 * 获取指定模型的能力信息
 * @param modelName 模型名称
 */
export function getModelCapability(modelName: string) {
  return request({
    url: `/api/model-capabilities/model/${modelName}`,
    method: 'get'
  })
}

