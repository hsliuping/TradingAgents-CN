import { ElMessageBox } from 'element-plus'
import type { Router } from 'vue-router'

import { useLicenseStore, type ProFeature } from '@/stores/license'

interface FeatureAccessOptions {
  title?: string
  message?: string
  redirectTo?: string
  confirmButtonText?: string
  cancelButtonText?: string
}

export async function ensureFeatureAccess(
  feature: ProFeature,
  router: Router,
  options: FeatureAccessOptions = {}
) {
  const licenseStore = useLicenseStore()

  if (!licenseStore.licenseInfo) {
    await licenseStore.verifyLicense()
  }

  if (licenseStore.hasFeature(feature)) {
    return true
  }

  try {
    await ElMessageBox.confirm(
      options.message || '此功能为高级学员专属，请前往授权管理完成认证。',
      options.title || '功能受限',
      {
        confirmButtonText: options.confirmButtonText || '前往授权管理',
        cancelButtonText: options.cancelButtonText || '稍后再说',
        type: 'warning'
      }
    )
    await router.push(options.redirectTo || '/settings/license')
  } catch {
    // 用户取消时不做额外处理
  }

  return false
}

export function ensureReportExportAccess(router: Router) {
  return ensureFeatureAccess('export_reports', router, {
    message: '报告下载与导出为高级学员专属，请前往授权管理完成认证。'
  })
}