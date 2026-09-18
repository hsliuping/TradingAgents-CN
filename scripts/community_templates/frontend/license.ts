/**
 * 授权信息 Store（社区版）
 *
 * 本文件由发布管道（scripts/publish_community.py）生成：
 * 社区版无授权体系，本 stub 保持与 Pro 版 stores/license.ts 完全一致的公开接口，
 * 消费方（Dashboard/UserProfile/featureAccess/Learning/DataImport/TradeReview）零改动。
 *
 * 行为语义：
 * - 不发起任何网络请求（无 /api/license/status 探活，社区版无该路由）
 * - isPro 恒为 false，plan 恒为 'free'
 * - hasFeature 仅放行免费功能（与后端 community_stub FREE_ACCESS_FEATURES 对齐）
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 授权信息接口（与 Pro 版保持一致）
export interface LicenseInfo {
  email: string
  plan: 'free' | 'trial' | 'pro' | 'enterprise'
  features: string[]
  auth_server?: string
  auth_server_options?: Array<{ value: string; label: string }>
  device_registered: boolean
  is_valid: boolean
  error_message?: string
  verified_at?: string
  trial_end_at?: string
  pro_expire_at?: string
  offline_mode?: boolean
}

// 高级学员功能列表（与 Pro 版保持一致，仅作为类型与枚举来源）
export const PRO_FEATURES = [
  'advanced_courses',
  'email_notification',
  'watchlist_groups',
  'scheduled_analysis',
  'portfolio_analysis',
  'trade_review',
  'batch_analysis',
  'export_reports',
  'trading_plan_check',
  'workflow',
  'workflow_tools',
  'workflow_agents',
  'prompt_templates',
] as const

export type ProFeature = typeof PRO_FEATURES[number]

// 社区版免费放行的功能（与 core/licensing/community_stub.py FREE_ACCESS_FEATURES 对齐）
const FREE_ACCESS_FEATURES = new Set<ProFeature>([
  'portfolio_analysis',
  'trade_review'
])

// 社区版固定授权信息（Free 档）
const COMMUNITY_LICENSE_INFO: LicenseInfo = {
  email: '',
  plan: 'free',
  features: ['portfolio_analysis', 'trade_review'],
  device_registered: false,
  is_valid: true,
  offline_mode: false
}

export const useLicenseStore = defineStore('license', () => {
  // 状态（保留接口兼容；licenseInfo 固定为 Free 档，不来自网络）
  const appToken = ref<string | null>(localStorage.getItem('app-token'))
  const licenseInfo = ref<LicenseInfo | null>({ ...COMMUNITY_LICENSE_INFO })
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastVerifiedAt = ref<Date | null>(null)

  // 计算属性：社区版恒定值
  const isPro = computed(() => false)
  const isEnterprise = computed(() => false)
  const isTrial = computed(() => false)
  // 类型保持与 Pro 版一致（完整联合类型），运行时值恒为 'free'，
  // 消费方的 plan === 'pro' 等分支类型合法（运行时永不命中，走 free 兜底）
  const plan = computed((): LicenseInfo['plan'] => 'free')

  const expireAt = computed(() => null)
  const daysRemaining = computed(() => null)
  const isExpiringSoon = computed(() => false)
  const isExpired = computed(() => false)
  const isOffline = computed(() => false)
  const hasLegacyCourseAccess = computed(() => false)

  const hasFeature = (_feature: ProFeature) => {
    return FREE_ACCESS_FEATURES.has(_feature)
  }

  // Actions：本地空操作，不发网络请求
  const setAppToken = async (token: string) => {
    appToken.value = token
    localStorage.setItem('app-token', token)
  }

  const clearAppToken = () => {
    appToken.value = null
    licenseInfo.value = { ...COMMUNITY_LICENSE_INFO }
    localStorage.removeItem('app-token')
  }

  const verifyLicense = async (_force = false, _authServer?: string): Promise<boolean> => {
    // 社区版无授权体系：直接返回 Free 档有效状态，不发起请求
    lastVerifiedAt.value = new Date()
    return true
  }

  // 社区版无需初始化验证（不发请求）

  return {
    // State
    appToken,
    licenseInfo,
    loading,
    error,
    // Getters
    isPro,
    isEnterprise,
    isTrial,
    plan,
    expireAt,
    daysRemaining,
    isExpiringSoon,
    isExpired,
    isOffline,
    hasLegacyCourseAccess,
    hasFeature,
    // Actions
    setAppToken,
    clearAppToken,
    verifyLicense
  }
})
