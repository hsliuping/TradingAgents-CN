/**
 * Pro 专属路由定义（v3.6.0 社区版开源分离 · M1 收敛改造）
 *
 * - 全部 requiresPro 页面路由与 Pro 功能页面路由集中于此
 * - 页面组件位于 views/pro/（社区版发布时整体剔除）
 * - 社区版发布处理：本文件整文件替换为空导出（见 scripts/publish_community.py），
 *   router/index.ts 的展开处无需任何修改
 * - 见 docs/05-design/v3.0/v3.6.0-community-edition-separation-plan.md §7.2
 *
 * 注意：新增 Pro 页面时必须登记到此文件——不登记 = 社区版泄露。
 */
import type { RouteRecordRaw } from 'vue-router'

/**
 * Pro 顶级路由：分析流模块（/workflow 整组）
 */
export const proWorkflowRoutes: RouteRecordRaw[] = [
  {
    path: '/workflow',
    name: 'Workflow',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '分析流',
      icon: 'SetUp',
      requiresAuth: true,
      requiresPro: true,  // 🔥 需要高级学员权限
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'WorkflowHome',
        component: () => import('@/views/pro/workflow/index.vue'),
        meta: {
          title: '分析流管理',
          requiresAuth: true,
          requiresPro: true  // 🔥 需要高级学员权限
        }
      },
      {
        path: 'tools',
        name: 'WorkflowTools',
        component: () => import('@/views/pro/workflow/Tools.vue'),
        meta: {
          title: '工具配置',
          requiresAuth: true,
          requiresPro: true  // 🔥 需要高级学员权限
        }
      },
      {
        path: 'agents',
        redirect: '/workflow/agent-workshop'
      },
      {
        path: 'mcp-servers',
        name: 'MCPServers',
        component: () => import('@/views/pro/workflow/McpServers.vue'),
        meta: {
          title: 'MCP 服务器',
          requiresAuth: true,
          requiresPro: true  // 🔥 需要高级学员权限
        }
      },
      {
        // Skill 中心已免费（v3.6.0）：旧路径重定向到社区路由 /skills
        path: 'skills',
        redirect: '/skills'
      },
      {
        path: 'skill-gaps',
        redirect: '/skills'
      },
      {
        path: 'skill-generation',
        redirect: '/skills'
      },
      {
        path: 'skill-generation/create',
        redirect: '/skills/generation/create'
      },
      {
        path: 'workflow-generation/create',
        name: 'WorkflowGenerationCreate',
        component: () => import('@/views/pro/workflow/WorkflowGeneration.vue'),
        meta: {
          title: 'AI 工作流架构师',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: 'agent-workshop',
        name: 'AgentWorkshop',
        component: () => import('@/views/pro/workflow/AgentWorkshopLanding.vue'),
        meta: {
          title: 'Agent 工坊',
          requiresAuth: true,
          requiresPro: true
        }
      },
      {
        path: 'agent-workshop/manage',
        name: 'AgentWorkshopManager',
        component: () => import('@/views/pro/workflow/AgentWorkshopManager.vue'),
        meta: {
          title: 'Agent 管理',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: 'agent-workshop/create',
        name: 'AgentWorkshopCreate',
        component: () => import('@/views/pro/workflow/AgentWorkshop.vue'),
        meta: {
          title: 'Agent 工坊工作页',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: 'agent-studio',
        name: 'AgentStudio',
        component: () => import('@/views/pro/workflow/AgentStudio.vue'),
        meta: {
          title: 'Agent 工坊助手',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: 'agents/:id',
        name: 'AgentDetail',
        component: () => import('@/views/pro/workflow/AgentDetail.vue'),
        meta: {
          title: 'Agent详情',
          requiresAuth: true,
          requiresPro: true,  // 🔥 需要高级学员权限
          hideInMenu: true
        }
      },
      {
        path: 'editor/:id',
        name: 'WorkflowEditor',
        component: () => import('@/views/pro/workflow/Editor.vue'),
        meta: {
          title: '工作流编辑器',
          requiresAuth: true,
          requiresPro: true,  // 🔥 需要高级学员权限
          hideInMenu: true
        }
      },
      {
        path: 'execute/:id',
        name: 'WorkflowExecute',
        component: () => import('@/views/pro/workflow/Execute.vue'),
        meta: {
          title: '执行工作流',
          requiresAuth: true,
          requiresPro: true,  // 🔥 需要高级学员权限
          hideInMenu: true
        }
      }
    ]
  }
]

/**
 * Pro 顶级路由：交易计划模块（/trading-system 整组，trading_plan_check 付费功能）
 */
export const proTradingSystemRoutes: RouteRecordRaw[] = [
  {
    path: '/trading-system',
    name: 'TradingSystem',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '交易计划',
      icon: 'Tickets',
      requiresAuth: true,
      requiresPro: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'TradingSystemList',
        component: () => import('@/views/pro/TradingSystem/List.vue'),
        meta: {
          title: '交易计划列表',
          requiresAuth: true,
          requiresPro: true
        }
      },
      {
        path: 'create',
        name: 'TradingSystemCreate',
        component: () => import('@/views/pro/TradingSystem/Create.vue'),
        meta: {
          title: '创建交易计划',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: ':id',
        name: 'TradingSystemDetail',
        component: () => import('@/views/pro/TradingSystem/Detail.vue'),
        meta: {
          title: '交易计划详情',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      },
      {
        path: ':id/edit',
        name: 'TradingSystemEdit',
        component: () => import('@/views/pro/TradingSystem/Create.vue'),
        meta: {
          title: '编辑交易计划',
          requiresAuth: true,
          requiresPro: true,
          hideInMenu: true
        }
      }
    ]
  }
]

/**
 * Pro 子路由：/analysis 下的批量分析（batch_analysis 付费功能）
 */
export const proAnalysisChildren: RouteRecordRaw[] = [
  {
    path: 'batch',
    name: 'BatchAnalysis',
    component: () => import('@/views/pro/analysis/BatchAnalysis.vue')
  }
]

/**
 * Pro 子路由：/settings 下的 Pro 页面
 * （模板三件套 + Prompt 三件套 + 推送/分组/定时分析 + 授权管理）
 */
export const proSettingsChildren: RouteRecordRaw[] = [
  {
    path: 'templates',
    name: 'TemplateAgentSelector',
    component: () => import('@/views/pro/settings/TemplateAgentSelector.vue'),
    meta: {
      title: '模板类型选择',
      requiresAuth: true,
      requiresPro: true  // 🔥 需要高级学员权限
    }
  },
  {
    path: 'templates/manage',
    name: 'TemplateManagement',
    component: () => import('@/views/pro/settings/TemplateManagement.vue'),
    meta: {
      title: '模板管理',
      requiresAuth: true,
      requiresPro: true  // 🔥 需要高级学员权限
    }
  },
  {
    path: 'templates/debug',
    name: 'TemplateDebug',
    component: () => import('@/views/pro/settings/TemplateDebug.vue'),
    meta: {
      title: '模板调试台',
      requiresAuth: true,
      requiresPro: true  // 🔥 需要高级学员权限
    }
  },
  {
    path: 'email',
    name: 'EmailNotification',
    component: () => import('@/views/pro/settings/EmailNotification.vue'),
    meta: { title: '邮件通知', requiresAuth: true }
  },
  {
    path: 'channel-configs',
    name: 'ChannelConfigs',
    component: () => import('@/views/pro/settings/ChannelConfigs.vue'),
    meta: { title: '渠道推送', requiresAuth: true, requiresPro: true }
  },
  {
    path: 'watchlist-groups',
    name: 'WatchlistGroups',
    component: () => import('@/views/pro/settings/WatchlistGroups.vue'),
    meta: { title: '定时分析分组', requiresAuth: true }
  },
  {
    path: 'scheduled-analysis',
    name: 'ScheduledAnalysis',
    component: () => import('@/views/pro/settings/ScheduledAnalysis.vue'),
    meta: { title: '定时分析配置', requiresAuth: true }
  },
  {
    path: 'license',
    name: 'LicenseSettings',
    component: () => import('@/views/pro/settings/LicenseSettings.vue'),
    meta: { title: '授权管理', requiresAuth: true }
  },
  {
    path: 'prompt-preview',
    name: 'PromptPreview',
    component: () => import('@/views/pro/settings/PromptPreview.vue'),
    meta: { title: 'Prompt 预览', requiresAuth: true, requiresPro: true }
  },
  {
    path: 'prompt-policies',
    name: 'PromptPolicyManager',
    component: () => import('@/views/pro/settings/PromptPolicyManager.vue'),
    meta: { title: '注入策略管理', requiresAuth: true, requiresPro: true }
  },
  {
    path: 'prompt-design',
    name: 'PromptDesignWorkspace',
    component: () => import('@/views/pro/settings/PromptDesignWorkspace.vue'),
    meta: { title: 'Prompt 设计助手', requiresAuth: true, requiresPro: true }
  },
  {
    // 社媒消息管理（数据保存类 Pro 功能，后端 social_media.py 在 PRO_ROUTERS）
    path: 'social-media',
    name: 'SocialMedia',
    component: () => import('@/views/pro/settings/SocialMedia/index.vue'),
    meta: { title: '社媒消息管理', requiresAuth: true }
  },
  {
    path: 'social-media/api-guide',
    name: 'SocialMediaApiGuide',
    component: () => import('@/views/pro/settings/SocialMedia/ApiGuide.vue'),
    meta: { title: 'API接入指南', requiresAuth: true }
  },
  {
    path: 'social-media/template/:type',
    name: 'SocialMediaTemplate',
    component: () => import('@/views/pro/settings/SocialMedia/TemplateViewer.vue'),
    meta: { title: '模板文件', requiresAuth: true }
  },
  {
    path: 'social-media/api-example',
    name: 'SocialMediaApiExample',
    component: () => import('@/views/pro/settings/SocialMedia/TemplateViewer.vue'),
    meta: { title: 'API示例代码', requiresAuth: true }
  },
  {
    // 股票数据批量导入 API 指南（数据保存类 Pro 功能，后端 stock_data.py 在 PRO_ROUTERS）
    path: 'stock-data/api-guide',
    name: 'StockDataApiGuide',
    component: () => import('@/views/pro/settings/StockDataApiGuide.vue'),
    meta: { title: '股票数据批量导入 API', requiresAuth: true }
  }
]

/**
 * Pro 子路由：/learning 下的高级课程示例报告（付费课程样本，内容位于 docs/07-courses/advanced）
 */
export const proLearningChildren: RouteRecordRaw[] = [
  {
    path: 'advanced/sample/:sampleId',
    name: 'AdvancedSampleReport',
    component: () => import('@/views/pro/Learning/AdvancedSampleReport.vue'),
    meta: {
      title: '高级课程示例报告',
      requiresAuth: false
    }
  }
]
