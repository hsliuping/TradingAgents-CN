import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { isJdyunMode } from '@/utils/config'
// Pro 专属路由（v3.6.0 社区版开源分离 M1）：集中定义于 pro.routes.ts，
// 社区版发布时整文件替换为空导出，本文件无需修改
import { proWorkflowRoutes, proTradingSystemRoutes, proAnalysisChildren, proSettingsChildren, proLearningChildren } from './pro.routes'

// 配置NProgress
NProgress.configure({
  showSpinner: false,
  minimum: 0.2,
  easing: 'ease',
  speed: 500
})

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  // 兼容文档链接：将 /paper/<name>.md 重定向到学习中心文章路由
  {
    path: '/paper/:name.md',
    name: 'PaperMdRedirect',
    redirect: (to) => `/learning/article/${to.params.name as string}`,
    meta: { title: '文档跳转', hideInMenu: true, requiresAuth: false }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '仪表板',
      icon: 'Dashboard',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'DashboardHome',
        component: () => import('@/views/Dashboard/index.vue'),
        meta: {
          title: '仪表板',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/help',
    name: 'Help',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '使用手册',
      icon: 'QuestionFilled',
      requiresAuth: true,
      hideInMenu: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'HelpHome',
        component: () => import('@/views/Help/index.vue'),
        meta: {
          title: '使用手册',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/guide',
    name: 'Guide',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '使用指南',
      icon: 'Document',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'GuideHome',
        component: () => import('@/views/Guide/index.vue'),
        meta: {
          title: '使用指南',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/analysis',
    name: 'Analysis',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/analysis/single',
    children: [
      {
        path: 'single',
        name: 'SingleAnalysis',
        component: () => import('@/views/Analysis/SingleAnalysis.vue')
      },
      // 批量分析（Pro）→ pro.routes.ts
      ...proAnalysisChildren,
      {
        path: 'general',
        name: 'GeneralAnalysis',
        component: () => import('@/views/Analysis/GeneralAnalysis.vue')
      },

    ]
  },
  {
    path: '/screening',
    name: 'StockScreening',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '股票筛选',
      icon: 'Search',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'StockScreeningHome',
        component: () => import('@/views/Screening/index.vue'),
        meta: {
          title: '股票筛选',
          requiresAuth: true
        }
      }
    ]
  },

  {
    path: '/favorites',
    name: 'Favorites',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '股票关注列表',
      icon: 'Star',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'FavoritesHome',
        component: () => import('@/views/Favorites/index.vue'),
        meta: {
          title: '股票关注列表',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/learning',
    name: 'Learning',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '学习中心',
      icon: 'Reading',
      requiresAuth: false,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'LearningHome',
        component: () => import('@/views/Learning/index.vue'),
        meta: {
          title: '学习中心',
          requiresAuth: false
        }
      },
      {
        path: ':category',
        name: 'LearningCategory',
        component: () => import('@/views/Learning/Category.vue'),
        meta: {
          title: '学习分类',
          requiresAuth: false
        }
      },
      {
        path: 'article/:id',
        name: 'LearningArticle',
        component: () => import('@/views/Learning/Article.vue'),
        meta: {
          title: '文章详情',
          requiresAuth: false
        }
      },
      {
        path: 'advanced',
        name: 'AdvancedCourses',
        component: () => import('@/views/Learning/Advanced.vue'),
        meta: {
          title: '从散户到系统交易者：AI赋能的可进化投资法',
          requiresAuth: false
        }
      },
      // 高级课程示例报告（Pro，付费课程样本）→ pro.routes.ts
      ...proLearningChildren,
      {
        path: 'advanced/:category/:lesson',
        name: 'AdvancedLesson',
        component: () => import('@/views/Learning/AdvancedLesson.vue'),
        meta: {
          title: '从散户到系统交易者：AI赋能的可进化投资法',
          requiresAuth: false
        }
      }
    ]
  },
  {
    path: '/stocks',
    name: 'Stocks',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '股票详情',
      icon: 'TrendCharts',
      requiresAuth: true,
      hideInMenu: true,
      transition: 'fade'
    },
    children: [
      {
        path: ':code',
        name: 'StockDetail',
        component: () => import('@/views/Stocks/Detail.vue'),
        meta: {
          title: '股票详情',
          requiresAuth: true,
          hideInMenu: true,
          transition: 'fade'
        }
      }
    ]
  },


  {
    path: '/tasks',
    name: 'TaskCenter',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/tasks/unified',
    meta: {
      title: '任务中心',
      icon: 'List',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: 'unified',
        name: 'UnifiedTaskCenter',
        component: () => import('@/views/Tasks/UnifiedTaskCenter.vue'),
        meta: { title: '任务中心', requiresAuth: true }
      }
    ]
  },
  // 保留旧版路由但重定向（以防有直接访问的链接）
  {
    path: '/tasks/old',
    name: 'TaskCenterHome',
    redirect: '/tasks/unified',
    meta: { title: '任务中心（旧版）', requiresAuth: true }
  },
  { path: '/queue', redirect: '/tasks/unified' },
  { path: '/analysis/history', redirect: '/tasks/unified' },
  {
    path: '/assistant',
    name: 'Assistant',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '智能助手',
      icon: 'ChatDotRound',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'AssistantHome',
        component: () => import('@/views/Assistant/index.vue'),
        meta: {
          title: '智能助手',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/debug/embedded-nanobot',
    name: 'EmbeddedNanobotDebug',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '助手调试',
      hideInMenu: true,
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'EmbeddedNanobotDebugHome',
        component: () => import('@/views/Debug/EmbeddedNanobot.vue'),
        meta: {
          title: '助手调试',
          hideInMenu: true,
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '对象记忆',
      icon: 'Coin',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'MemoryHome',
        component: () => import('@/views/Memory/index.vue'),
        meta: {
          title: '股票对象记忆',
          requiresAuth: true
        }
      }
    ]
  },
  {
    // Skill 中心（v3.6.0 起免费开放，随社区版开源）
    path: '/skills',
    name: 'SkillCenter',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: 'Skill 中心',
      icon: 'MagicStick',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'SkillCenterHome',
        component: () => import('@/views/Skills/SkillCenter.vue'),
        meta: {
          title: 'Skill 中心',
          requiresAuth: true
        }
      },
      {
        path: 'generation/create',
        name: 'SkillGenerationCreate',
        component: () => import('@/views/Skills/SkillGenerationCreate.vue'),
        meta: {
          title: '创建 Skill',
          requiresAuth: true,
          hideInMenu: true
        }
      }
    ]
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '分析报告',
      icon: 'Document',
      requiresAuth: true,
      transition: 'fade'
    },
    children: [
      {
        path: '',
        name: 'ReportsHome',
        component: () => import('@/views/Reports/index.vue'),
        meta: {
          title: '分析报告',
          requiresAuth: true
        }
      },
      {
        path: 'view/:id',
        name: 'ReportDetail',
        component: () => import('@/views/Reports/ReportDetail.vue'),
        meta: {
          title: '报告详情',
          requiresAuth: true
        }
      },
      {
        path: 'token',
        name: 'TokenStatistics',
        component: () => import('@/views/Reports/TokenStatistics.vue'),
        meta: {
          title: 'Token统计',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '设置',
      icon: 'Setting',
      requiresAuth: true,
      transition: 'slide-left'
    },
    children: [
      {
        path: '',
        name: 'SettingsHome',
        component: () => import('@/views/Settings/index.vue'),
        meta: {
          title: '设置',
          requiresAuth: true
        }
      },
      {
        path: 'config',
        name: 'ConfigManagement',
        component: () => import('@/views/Settings/ConfigManagement.vue'),
        meta: {
          title: '配置管理',
          requiresAuth: true
        }
      },
      {
        path: 'database',
        name: 'DatabaseManagement',
        component: () => import('@/views/System/DatabaseManagement.vue'),
        meta: {
          title: '数据库管理',
          requiresAuth: true
        }
      },
      {
        path: 'logs',
        name: 'OperationLogs',
        component: () => import('@/views/System/OperationLogs.vue'),
        meta: {
          title: '操作日志',
          requiresAuth: true
        }
      },
      {
        path: 'system-logs',
        name: 'LogManagement',
        component: () => import('@/views/System/LogManagement.vue'),
        meta: {
          title: '系统日志',
          requiresAuth: true
        }
      },
      {
        path: 'sync',
        name: 'MultiSourceSync',
        component: () => import('@/views/System/MultiSourceSync.vue'),
        meta: {
          title: '多数据源同步',
          requiresAuth: true
        }
      },
      {
        path: 'capability-index',
        name: 'CapabilityIndex',
        component: () => import('@/views/Settings/index.vue'),
        meta: {
          title: '工具能力索引',
          requiresAuth: true
        }
      },
      {
        path: 'cache',
        name: 'CacheManagement',
        component: () => import('@/views/Settings/CacheManagement.vue'),
        meta: {
          title: '缓存管理',
          requiresAuth: true
        }
      },
      {
        path: 'usage',
        name: 'UsageStatistics',
        component: () => import('@/views/Settings/UsageStatistics.vue'),
        meta: {
          title: '使用统计',
          requiresAuth: true
        }
      },
        {
        path: 'scheduler',
        name: 'SchedulerManagement',
        component: () => import('@/views/System/SchedulerManagement.vue'),
        meta: {
            title: '定时任务',
            requiresAuth: true
        }
      },
        // 社媒消息管理（Pro 数据保存）→ pro.routes.ts
        {
          path: 'data-import',
          name: 'DataImport',
          component: () => import('@/views/System/DataImport.vue'),
          meta: {
            title: '数据导入管理',
            requiresAuth: true
          }
        },
        {
          path: 'update',
          name: 'UpdateManagement',
          component: () => import('@/views/System/UpdateManagement.vue'),
          meta: {
            title: '系统更新',
            requiresAuth: true
          }
        },
      // Pro 页面子路由（模板三件套/Prompt 三件套/推送/分组/定时分析/授权管理/社媒消息管理/数据API指南）→ pro.routes.ts
      ...proSettingsChildren,
      {
        path: 'analysis-profiles',
        name: 'AnalysisProfiles',
        component: () => import('@/views/Settings/AnalysisProfiles.vue'),
        meta: { title: '行业/个股配置', requiresAuth: true }
      },
      {
        path: 'jdyun-config',
        name: 'JdyunConfig',
        component: () => import('@/views/Settings/JdyunConfig.vue'),
        meta: { title: '系统配置', requiresAuth: true }
      }
    ]
  },

  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Auth/Login.vue'),
    meta: {
      title: '登录',
      hideInMenu: true,
      transition: 'fade'
    }
  },

  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/About/index.vue'),
    meta: {
      title: '关于',
      icon: 'InfoFilled',
      requiresAuth: false, // 关于页面不需要认证
      transition: 'fade'
    }
  },
  {
    path: '/paper',
    name: 'PaperTrading',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '模拟交易',
      icon: 'CreditCard',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'PaperTradingHome',
        component: () => import('@/views/PaperTrading/index.vue'),
        meta: {
          title: '模拟交易',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '持仓分析',
      icon: 'PieChart',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'PortfolioHome',
        component: () => import('@/views/Portfolio/index.vue'),
        meta: {
          title: '持仓分析',
          requiresAuth: true
        }
      }
    ]
  },
  {
    path: '/review',
    name: 'TradeReview',
    component: () => import('@/layouts/BasicLayout.vue'),
    meta: {
      title: '操作复盘',
      icon: 'TrendCharts',
      requiresAuth: true,
      transition: 'slide-up'
    },
    children: [
      {
        path: '',
        name: 'TradeReviewHome',
        component: () => import('@/views/TradeReview/index.vue'),
        meta: {
          title: '操作复盘',
          requiresAuth: true
        }
      }
    ]
  },
  // 分析流模块（Pro）→ pro.routes.ts
  ...proWorkflowRoutes,
  // 交易计划（Pro，trading_plan_check 付费功能）→ pro.routes.ts
  ...proTradingSystemRoutes,

  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/Error/404.vue'),
    meta: {
      title: '页面不存在',
      hideInMenu: true,
      requiresAuth: true
    }
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 全局前置守卫
router.beforeEach(async (to, _from, next) => {
  // 开始进度条
  NProgress.start()

  const authStore = useAuthStore()
  const appStore = useAppStore()

  // 等待认证初始化完成，避免初始化期间跳转出现竞态
  if (!authStore.authInitialized) {
    try {
      await authStore.checkAuthStatus()
    } catch {
      // 初始化失败时继续走原有判断逻辑
    }
  }

  // 设置页面标题
  const title = to.meta.title as string
  if (title) {
    document.title = `${title} - TradingAgents-CN`
  }

  console.log('🚦 路由守卫检查:', {
    path: to.fullPath,
    name: to.name,
    requiresAuth: to.meta.requiresAuth,
    requiresPro: to.meta.requiresPro,
    isAuthenticated: authStore.isAuthenticated,
    hasToken: !!authStore.token
  })

  // 检查是否需要高级学员权限
  if (to.meta.requiresPro) {
    try {
      const { useLicenseStore } = await import('@/stores/license')
      const licenseStore = useLicenseStore()
      
      // 如果License状态未加载，先验证
      if (!licenseStore.licenseInfo) {
        await licenseStore.verifyLicense()
      }
      
      if (!licenseStore.isPro) {
        ElMessage.warning('此功能需要高级学员权限，请先认证')
        NProgress.done()
        next('/settings/license')
        return
      }
    } catch (error) {
      console.error('检查License权限失败:', error)
      // 如果检查失败，允许访问（开发环境可能未配置）
    }
  }

  // 检查是否需要认证
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    console.log('🔒 需要认证但用户未登录:', {
      path: to.fullPath,
      requiresAuth: to.meta.requiresAuth,
      isAuthenticated: authStore.isAuthenticated,
      token: authStore.token ? '存在' : '不存在'
    })
    // 保存原始路径，登录后跳转
    authStore.setRedirectPath(to.fullPath)
    next('/login')
    return
  }



  // 如果已登录且访问登录页，重定向到仪表板
  if (authStore.isAuthenticated && to.name === 'Login') {
    next('/dashboard')
    return
  }

  // 京东云版首次登录引导：未完成引导且访问仪表板时跳转到 /guide
  if (authStore.isAuthenticated && isJdyunMode()) {
    const guideCompleted = (() => {
      try {
        return localStorage.getItem('jdyun_guide_completed') === 'true'
      } catch {
        return false
      }
    })()

    // 用户主动点击"查看引导"或已经在 /guide 页面，不拦截
    const goingToGuide = to.path === '/guide'

    if (!guideCompleted && to.path === '/dashboard' && !goingToGuide) {
      next('/guide?mode=jdyun')
      return
    }
  }

  // PRO 功能路由检查
  const proRoutes = [
    '/settings/email',
    '/settings/channel-configs',
    '/settings/watchlist-groups',
    '/settings/scheduled-analysis',
    '/settings/templates',  // 🔥 提示词模板需要高级学员权限
    '/workflow'  // 分析流功能需要高级学员权限
  ]

  // 检查是否是 PRO 路由
  const isProRoute = proRoutes.some(route => to.path.startsWith(route))
  if (isProRoute && authStore.isAuthenticated) {
    // 延迟导入 license store 避免循环依赖
    const { useLicenseStore } = await import('@/stores/license')
    const licenseStore = useLicenseStore()

    // 确保已验证授权状态
    if (!licenseStore.licenseInfo) {
      await licenseStore.verifyLicense()
    }

    // 如果不是高级学员，显示提示并重定向到授权管理页面
    if (!licenseStore.isPro) {
      ElMessage.warning('此功能为高级学员专属，请先升级学员等级')
      next('/settings/license')
      return
    }
  }

  // 更新当前路由信息
  appStore.setCurrentRoute(to)

  next()
})

// 全局后置守卫
router.afterEach((_to, _from) => {
  // 结束进度条
  NProgress.done()

  // 页面切换后的处理
  nextTick(() => {
    // 可以在这里添加页面分析、埋点等逻辑
  })
})

// 路由错误处理
router.onError((error) => {
  console.error('路由错误:', error)
  NProgress.done()
  ElMessage.error('页面加载失败，请重试')
})

export default router

// 导出路由配置供其他地方使用
export { routes }
