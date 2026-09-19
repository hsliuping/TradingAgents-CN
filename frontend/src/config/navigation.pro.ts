/**
 * Pro 专属菜单配置（社区版）
 *
 * 本文件由发布管道（scripts/publish_community.py）生成：
 * 社区版无 Pro 菜单项，全部导出为空配置，SidebarMenu 零改动。
 */

export interface ProMenuItem {
  path: string
  label: string
  advanced?: boolean
  badge?: { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'info' }
}

export interface ProMenuGroup {
  path: string
  label: string
  advanced?: boolean
  children: ProMenuItem[]
}

/** 顶级菜单中的 Pro 项（社区版：空） */
export const proTopLevelItems: ProMenuItem[] = []

/** 顶级菜单中的 Pro 项·交易计划（社区版：空） */
export const proTradingSystemMenuItems: ProMenuItem[] = []

/** 分析流子菜单（社区版：空） */
export const proWorkflowMenu: ProMenuGroup = {
  path: '/workflow',
  label: '分析流',
  children: []
}

/** 个人设置中的 Pro 项（社区版：空） */
export const proPersonalSettingsItems: ProMenuItem[] = []

/** 授权管理菜单项（社区版：空） */
export const proLicenseMenuItem: ProMenuItem | null = null

/** 分析配置中的 Pro 项（社区版：空） */
export const proAnalysisSettingsItems: ProMenuItem[] = []

/** 系统管理中的 Pro 项（社区版：空） */
export const proAdminSettingsItems: ProMenuItem[] = []
