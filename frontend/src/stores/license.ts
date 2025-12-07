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
  plan: 'free' | 'pro' | 'enterprise'
  features: string[]
  device_registered: boolean
  is_valid: boolean
  error_message?: string
  verified_at?: string
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
           ['pro', 'enterprise'].includes(licenseInfo.value.plan)
  })

  const isEnterprise = computed(() => {
    if (!licenseInfo.value) return false
    return licenseInfo.value.is_valid && 
           licenseInfo.value.plan === 'enterprise'
  })

  const plan = computed(() => licenseInfo.value?.plan || 'free')

  const hasFeature = (feature: ProFeature) => {
    if (!licenseInfo.value?.is_valid) return false
    // enterprise 拥有所有功能
    if (licenseInfo.value.plan === 'enterprise') return true
    // pro 用户检查功能列表
    if (licenseInfo.value.plan === 'pro') {
      return licenseInfo.value.features.includes(feature)
    }
    return false
  }

  // Actions
  const setAppToken = async (token: string) => {
    appToken.value = token
    localStorage.setItem('app-token', token)
    // 立即验证
    await verifyLicense()
  }

  const clearAppToken = () => {
    appToken.value = null
    licenseInfo.value = null
    localStorage.removeItem('app-token')
  }

  const verifyLicense = async (force = false): Promise<boolean> => {
    // 如果没有 token，返回 free 状态
    if (!appToken.value) {
      licenseInfo.value = {
        email: '',
        plan: 'free',
        features: [],
        device_registered: false,
        is_valid: true,
      }
      return true
    }

    // 检查缓存（5分钟内不重复验证）
    if (!force && lastVerifiedAt.value) {
      const elapsed = Date.now() - lastVerifiedAt.value.getTime()
      if (elapsed < 5 * 60 * 1000 && licenseInfo.value) {
        return licenseInfo.value.is_valid
      }
    }

    loading.value = true
    error.value = null

    try {
      const response = await request.post('/api/license/verify', {
        token: appToken.value
      })

      if (response.success && response.data) {
        licenseInfo.value = response.data
        lastVerifiedAt.value = new Date()
        return response.data.is_valid
      } else {
        error.value = response.message || '验证失败'
        licenseInfo.value = {
          email: '',
          plan: 'free',
          features: [],
          device_registered: false,
          is_valid: false,
          error_message: error.value
        }
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
    plan,
    hasFeature,
    // Actions
    setAppToken,
    clearAppToken,
    verifyLicense
  }
})

