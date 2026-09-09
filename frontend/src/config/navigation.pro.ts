/**
 * Pro 专属菜单项配置（v3.6.0 社区版开源分离 · M1 收敛改造）
 *
 * - SidebarMenu 中的 Pro 菜单项（分析流/批量分析/模板/Prompt/推送/授权）集中于此
 * - 社区版发布处理：本文件整文件替换为空配置（见 scripts/publish_community.py），
 *   SidebarMenu.vue 无需任何修改，Pro 菜单项自动不渲染
 * - 见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §7.2
 *
 * 注意：新增 Pro 菜单入口时必须登记到此文件——不登记 = 社区版泄露。
 */

export interface ProMenuBadge {
  text: string
  type: 'success' | 'primary' | 'info' | 'warning' | 'danger'
}

export interface ProMenuItem {
  /** 路由路径（el-menu-item index） */
  path: string
  /** 菜单显示名 */
  label: string
  /** 是否显示"高级"标签 */
  advanced?: boolean
  /** 其他角标（如 Agent 工坊的"迭代"） */
  badge?: ProMenuBadge
}

export interface ProMenuGroup extends ProMenuItem {
  /** 子菜单项 */
  children: ProMenuItem[]
}

/** 顶级菜单中的 Pro 项（批量分析） */
export const proTopLevelItems: ProMenuItem[] = [
  { path: '/analysis/batch', label: '批量分析', advanced: true }
]

/** 分析流子菜单（整组 Pro） */
export const proWorkflowMenu: ProMenuGroup = {
  path: '/workflow',
  label: '分析流',
  advanced: true,
  children: [
    { path: '/workflow', label: '流程管理', advanced: true },
    { path: '/workflow/tools', label: '工具配置', advanced: true },
    { path: '/workflow/agent-workshop', label: 'Agent 工坊', badge: { text: '迭代', type: 'primary' } },
    { path: '/workflow/skills', label: 'Skill 中心', advanced: true },
    { path: '/workflow/mcp-servers', label: 'MCP 服务器', advanced: true }
  ]
}

/** 个人设置组中的 Pro 项 */
export const proPersonalSettingsItems: ProMenuItem[] = [
  { path: '/settings/email', label: '邮件通知', advanced: true },
  { path: '/settings/channel-configs', label: '渠道推送', advanced: true },
  { path: '/settings/watchlist-groups', label: '定时分析分组', advanced: true },
  { path: '/settings/scheduled-analysis', label: '定时分析配置', advanced: true }
]

/** 授权管理菜单项（licensing 体系，社区版剔除；京东云模式下始终隐藏） */
export const proLicenseMenuItem: ProMenuItem = {
  path: '/settings/license',
  label: '授权管理'
}

/** 分析配置组中的 Pro 项 */
export const proAnalysisSettingsItems: ProMenuItem[] = [
  { path: '/settings/templates', label: '提示词模板', advanced: true },
  { path: '/settings/prompt-policies', label: '注入策略管理', advanced: true },
  { path: '/settings/prompt-design', label: 'Prompt 设计助手', advanced: true }
]
