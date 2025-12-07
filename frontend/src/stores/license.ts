/**
 * 授权信息 Store
 * 
 * 管理用户的 PRO 授权状态和功能权限
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/api/request'

// 授权信息接口
export interface LicenseInfo {
  email: string
  plan: 'free' | 'trial' | 'pro' | 'enterprise'
  features: string[]
  device_registered: boolean
  is_valid: boolean
  error_message?: string
  verified_at?: string
  trial_end_at?: string  // 试用到期时间
  pro_expire_at?: string  // PRO到期时间
}

// PRO 功能列表
export const PRO_FEATURES = [
  'email_notification',      // 邮件通知
  'watchlist_groups',        // 自选股分组
  'scheduled_analysis',      // 定时分析
  'portfolio_analysis',      // 持仓分析
  'trade_review',            // 操作复盘
  'advanced_screening',      // 高级选股
  'batch_analysis',          // 批量分析
  'export_reports',          // 导出报告
] as const

export type ProFeature = typeof PRO_FEATURES[number]

export const useLicenseStore = defineStore('license', () => {
  // 状态
  const appToken = ref<string | null>(localStorage.getItem('app-token'))
  const licenseInfo = ref<LicenseInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastVerifiedAt = ref<Date | null>(null)

  // 计算属性
  const isPro = computed(() => {
    if (!licenseInfo.value) return false
    return licenseInfo.value.is_valid &&
           ['trial', 'pro', 'enterprise'].includes(licenseInfo.value.plan)
  })

  const isEnterprise = computed(() => {
    if (!licenseInfo.value) return false
    return licenseInfo.value.is_valid &&
           licenseInfo.value.plan === 'enterprise'
  })

  const isTrial = computed(() => {
    if (!licenseInfo.value) return false
    return licenseInfo.value.is_valid &&
           licenseInfo.value.plan === 'trial'
  })

  const plan = computed(() => licenseInfo.value?.plan || 'free')

  const hasFeature = (feature: ProFeature) => {
    if (!licenseInfo.value?.is_valid) return false
    // trial、pro、enterprise 用户拥有所有 PRO 功能
    if (['trial', 'pro', 'enterprise'].includes(licenseInfo.value.plan)) {
      return true
    }
    return false
  }

  // Actions
  const setAppToken = async (token: string) => {
    appToken.value = token
    localStorage.setItem('app-token', token)
    // 立即刷新状态（强制跳过缓存）
    await verifyLicense(true)
  }

  const clearAppToken = () => {
    appToken.value = null
    licenseInfo.value = null
    localStorage.removeItem('app-token')
  }

  const verifyLicense = async (force = false): Promise<boolean> => {
    loading.value = true
    error.value = null

    try {
      // 调用 /status 接口获取授权状态，force=true 时强制刷新（跳过后端缓存）
      const response = await request.get('/api/license/status', {
        params: { force_refresh: force }
      })

      if (response.success && response.data) {
        // 如果用户没有配置 token
        if (!response.data.has_token) {
          licenseInfo.value = {
            email: '',
            plan: 'free',
            features: [],
            device_registered: false,
            is_valid: true,
          }
          // 清除本地存储的 token
          appToken.value = null
          localStorage.removeItem('app-token')
        } else {
          licenseInfo.value = {
            email: response.data.email || '',
            plan: response.data.plan || 'free',
            features: response.data.features || [],
            device_registered: response.data.device_registered || false,
            is_valid: response.data.is_valid !== false,
            error_message: response.data.error_message,
            trial_end_at: response.data.trial_end_at,
            pro_expire_at: response.data.pro_expire_at
          }
        }
        lastVerifiedAt.value = new Date()
        return licenseInfo.value.is_valid
      } else {
        error.value = response.message || '获取授权状态失败'
        return false
      }
    } catch (e: any) {
      error.value = e.message || '网络错误'
      // 网络错误时保持之前的状态
      return licenseInfo.value?.is_valid || false
    } finally {
      loading.value = false
    }
  }

  // 初始化时验证
  if (appToken.value) {
    verifyLicense()
  }

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
    hasFeature,
    // Actions
    setAppToken,
    clearAppToken,
    verifyLicense
  }
})

