# 功能权限控制设计

## 1. 现状分析

### 1.1 当前认证架构

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 (Vue + Pinia)                                              │
│  ├── auth.ts store - Token管理、用户信息                         │
│  ├── router守卫 - 路由级别认证检查                               │
│  └── localStorage - token、user-info持久化                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  后端 (FastAPI)                                                  │
│  ├── auth_db.py - 登录、Token生成/验证                          │
│  ├── auth_service.py - JWT Token处理                            │
│  └── user_service.py - 用户CRUD                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 当前用户模型

```python
class User(BaseModel):
    username: str
    email: str
    is_active: bool
    is_admin: bool         # 仅区分普通用户和管理员
    daily_quota: int       # 日配额
    concurrent_limit: int  # 并发限制
```

### 1.3 功能分层说明

| 功能 | 免费版 | 专业版增强 |
|------|--------|------------|
| 定时分析 | ✅ 基础定时（单一时间点） | 🔒 高级定时（分组/多时段/自定义深度） |
| 自定义提示词 | ✅ 模板管理（增删改查） | 🔒 模板调试、效果预览 |
| 持仓分析 | ❌ | 🔒 专业版独享 |
| 操作复盘 | ❌ | 🔒 专业版独享 |
| 邮件通知 | ❌ | 🔒 专业版独享 |
| 学习中心专业课程 | ❌ | 🔒 专业版独享 |

---

## 2. 权限模型设计

### 2.1 用户等级

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户等级体系                              │
├─────────────────────────────────────────────────────────────────┤
│  FREE     │ 免费用户，基础功能                                   │
│  TRIAL    │ 试用用户，7天体验全功能                              │
│  PRO      │ 专业版用户，全功能                                   │
│  LIFETIME │ 永久会员，全功能永不过期                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 功能权限矩阵

| 功能 | FREE | TRIAL | PRO | LIFETIME |
|------|------|-------|-----|----------|
| **基础分析** |
| 单股分析 | ✅ | ✅ | ✅ | ✅ |
| 批量分析 | ✅ | ✅ | ✅ | ✅ |
| 股票筛选 | ✅ | ✅ | ✅ | ✅ |
| 自选股管理 | ✅ | ✅ | ✅ | ✅ |
| 模拟交易 | ✅ | ✅ | ✅ | ✅ |
| 报告导出 | ✅ | ✅ | ✅ | ✅ |
| **定时分析** |
| 基础定时分析 | ✅ | ✅ | ✅ | ✅ |
| 高级定时（分组/多时段） | ❌ | ✅ | ✅ | ✅ |
| **自定义提示词** |
| 模板管理（增删改查） | ✅ | ✅ | ✅ | ✅ |
| 模板调试/效果预览 | ❌ | ✅ | ✅ | ✅ |
| **专业版独享** |
| 持仓分析 | ❌ | ✅ | ✅ | ✅ |
| 操作复盘 | ❌ | ✅ | ✅ | ✅ |
| 邮件通知 | ❌ | ✅ | ✅ | ✅ |
| **学习内容** |
| 基础文章 | ✅ | ✅ | ✅ | ✅ |
| 专业课程 | ❌ | ✅ | ✅ | ✅ |
| 视频教程 | ❌ | ✅ | ✅ | ✅ |

### 2.3 权限标识定义

```typescript
// types/permission.ts

export enum UserLevel {
  FREE = 'free',
  TRIAL = 'trial',
  PRO = 'pro',
  LIFETIME = 'lifetime'
}

export enum Feature {
  // 基础功能 (所有用户)
  SINGLE_ANALYSIS = 'single_analysis',
  BATCH_ANALYSIS = 'batch_analysis',
  BASIC_SCHEDULED_ANALYSIS = 'basic_scheduled_analysis',  // 基础定时分析
  PROMPT_TEMPLATE_MANAGEMENT = 'prompt_template_management',  // 基础模板管理
  STOCK_SCREENING = 'stock_screening',
  FAVORITES = 'favorites',
  PAPER_TRADING = 'paper_trading',
  REPORT_EXPORT = 'report_export',

  // 专业版增强功能 (基础功能免费，高级功能付费)
  ADVANCED_SCHEDULED_ANALYSIS = 'advanced_scheduled_analysis',  // 高级定时（分组/多时段）
  PROMPT_TEMPLATE_DEBUG = 'prompt_template_debug',  // 模板调试/效果预览

  // 专业版独享功能
  PORTFOLIO_ANALYSIS = 'portfolio_analysis',
  TRADE_REVIEW = 'trade_review',
  EMAIL_NOTIFICATION = 'email_notification',

  // 学习内容
  BASIC_LEARNING = 'basic_learning',
  PRO_COURSES = 'pro_courses',
  VIDEO_TUTORIALS = 'video_tutorials'
}

// 权限配置
export const FEATURE_PERMISSIONS: Record<Feature, UserLevel[]> = {
  // 基础功能 - 所有用户
  [Feature.SINGLE_ANALYSIS]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.BATCH_ANALYSIS]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.BASIC_SCHEDULED_ANALYSIS]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.PROMPT_TEMPLATE_MANAGEMENT]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.STOCK_SCREENING]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.FAVORITES]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.PAPER_TRADING]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.REPORT_EXPORT]: ['free', 'trial', 'pro', 'lifetime'],
  [Feature.BASIC_LEARNING]: ['free', 'trial', 'pro', 'lifetime'],

  // 专业版增强功能 - 仅付费用户
  [Feature.ADVANCED_SCHEDULED_ANALYSIS]: ['trial', 'pro', 'lifetime'],
  [Feature.PROMPT_TEMPLATE_DEBUG]: ['trial', 'pro', 'lifetime'],

  // 专业版独享功能 - 仅付费用户
  [Feature.PORTFOLIO_ANALYSIS]: ['trial', 'pro', 'lifetime'],
  [Feature.TRADE_REVIEW]: ['trial', 'pro', 'lifetime'],
  [Feature.EMAIL_NOTIFICATION]: ['trial', 'pro', 'lifetime'],
  [Feature.PRO_COURSES]: ['trial', 'pro', 'lifetime'],
  [Feature.VIDEO_TUTORIALS]: ['trial', 'pro', 'lifetime']
}
```

---

## 3. 用户模型扩展

### 3.1 后端用户模型

```python
# app/models/user.py

from enum import Enum
from datetime import datetime
from typing import Optional

class UserLevel(str, Enum):
    FREE = "free"
    TRIAL = "trial"
    PRO = "pro"
    LIFETIME = "lifetime"

class LicenseInfo(BaseModel):
    """License信息"""
    license_key: Optional[str] = None
    level: UserLevel = UserLevel.FREE
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    trial_started_at: Optional[datetime] = None
    trial_expires_at: Optional[datetime] = None
    devices: List[str] = Field(default_factory=list, max_items=3)
    
class User(BaseModel):
    """用户模型 - 扩展版"""
    # 原有字段
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    is_admin: bool = False
    
    # 新增：License信息
    license: LicenseInfo = Field(default_factory=LicenseInfo)
    
    @property
    def user_level(self) -> UserLevel:
        """计算当前用户等级"""
        if not self.license.license_key:
            return UserLevel.FREE
        
        now = datetime.utcnow()
        
        # 检查试用期
        if self.license.trial_expires_at:
            if now < self.license.trial_expires_at:
                return UserLevel.TRIAL
        
        # 检查订阅
        if self.license.level == UserLevel.LIFETIME:
            return UserLevel.LIFETIME
        
        if self.license.expires_at:
            if now < self.license.expires_at:
                return self.license.level
        
        return UserLevel.FREE
    
    def has_feature(self, feature: str) -> bool:
        """检查是否有某功能权限"""
        from app.config.feature_permissions import FEATURE_PERMISSIONS
        allowed_levels = FEATURE_PERMISSIONS.get(feature, [])
        return self.user_level.value in allowed_levels
```

---

## 4. 后端权限控制

### 4.1 权限装饰器

```python
# app/utils/permission.py

from functools import wraps
from fastapi import HTTPException, Depends
from app.routers.auth_db import get_current_user

def require_feature(feature: str):
    """功能权限装饰器"""
    async def dependency(current_user: dict = Depends(get_current_user)):
        user = await get_full_user(current_user['id'])

        if not user.has_feature(feature):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FEATURE_RESTRICTED",
                    "message": "此功能需要专业版",
                    "feature": feature,
                    "current_level": user.user_level.value,
                    "required_levels": FEATURE_PERMISSIONS.get(feature, [])
                }
            )
        return current_user

    return Depends(dependency)

def require_level(min_level: UserLevel):
    """用户等级装饰器"""
    async def dependency(current_user: dict = Depends(get_current_user)):
        user = await get_full_user(current_user['id'])

        level_order = [UserLevel.FREE, UserLevel.TRIAL, UserLevel.PRO, UserLevel.LIFETIME]
        user_level_index = level_order.index(user.user_level)
        required_level_index = level_order.index(min_level)

        if user_level_index < required_level_index:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "LEVEL_RESTRICTED",
                    "message": f"需要{min_level.value}等级才能使用此功能",
                    "current_level": user.user_level.value,
                    "required_level": min_level.value
                }
            )
        return current_user

    return Depends(dependency)
```

### 4.2 API路由保护示例

```python
# app/routers/scheduled_analysis.py

from app.utils.permission import require_feature
from app.models.permission import Feature

router = APIRouter(prefix="/api/v1/scheduled", tags=["scheduled-analysis"])

@router.post("/tasks")
async def create_scheduled_task(
    task_data: ScheduledTaskCreate,
    current_user: dict = require_feature(Feature.SCHEDULED_ANALYSIS)  # 需要专业版
):
    """创建定时分析任务 - 专业版功能"""
    ...

@router.get("/tasks")
async def list_scheduled_tasks(
    current_user: dict = require_feature(Feature.SCHEDULED_ANALYSIS)
):
    """获取定时分析任务列表 - 专业版功能"""
    ...

# app/routers/prompt_template.py

@router.post("/templates")
async def create_template(
    template_data: TemplateCreate,
    current_user: dict = require_feature(Feature.CUSTOM_PROMPT)  # 需要专业版
):
    """创建自定义提示词模板 - 专业版功能"""
    ...
```

### 4.3 权限检查API

```python
# app/routers/permission.py

router = APIRouter(prefix="/api/v1/permission", tags=["permission"])

@router.get("/check/{feature}")
async def check_feature_permission(
    feature: str,
    current_user: dict = Depends(get_current_user)
):
    """检查用户是否有某功能权限"""
    user = await get_full_user(current_user['id'])

    return {
        "feature": feature,
        "has_permission": user.has_feature(feature),
        "user_level": user.user_level.value,
        "required_levels": FEATURE_PERMISSIONS.get(feature, [])
    }

@router.get("/features")
async def get_user_features(
    current_user: dict = Depends(get_current_user)
):
    """获取用户所有功能权限"""
    user = await get_full_user(current_user['id'])

    features = {}
    for feature in Feature:
        features[feature.value] = user.has_feature(feature.value)

    return {
        "user_level": user.user_level.value,
        "is_trial": user.user_level == UserLevel.TRIAL,
        "trial_expires_at": user.license.trial_expires_at,
        "subscription_expires_at": user.license.expires_at,
        "features": features
    }

@router.get("/upgrade-info")
async def get_upgrade_info(
    current_user: dict = Depends(get_current_user)
):
    """获取升级信息"""
    user = await get_full_user(current_user['id'])

    return {
        "current_level": user.user_level.value,
        "can_trial": user.license.trial_started_at is None,
        "upgrade_url": "https://your-auth-site.com/pricing",
        "features_preview": [
            {"name": "定时分析", "description": "自动定期分析自选股"},
            {"name": "自定义提示词", "description": "个性化分析角度"},
            {"name": "持仓分析", "description": "基于成本的个性化建议"},
            {"name": "操作复盘", "description": "交易回顾与改进建议"},
        ]
    }
```

---

## 5. 前端权限控制

### 5.1 权限Store

```typescript
// stores/permission.ts

import { defineStore } from 'pinia'
import { permissionApi } from '@/api/permission'
import type { Feature, UserLevel } from '@/types/permission'

interface PermissionState {
  userLevel: UserLevel
  isTrial: boolean
  trialExpiresAt: string | null
  subscriptionExpiresAt: string | null
  features: Record<string, boolean>
  loading: boolean
}

export const usePermissionStore = defineStore('permission', {
  state: (): PermissionState => ({
    userLevel: 'free',
    isTrial: false,
    trialExpiresAt: null,
    subscriptionExpiresAt: null,
    features: {},
    loading: false
  }),

  getters: {
    // 是否是专业版用户
    isPro(): boolean {
      return ['pro', 'lifetime', 'trial'].includes(this.userLevel)
    },

    // 试用剩余天数
    trialDaysLeft(): number | null {
      if (!this.isTrial || !this.trialExpiresAt) return null
      const diff = new Date(this.trialExpiresAt).getTime() - Date.now()
      return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
    },

    // 检查功能权限
    hasFeature(): (feature: string) => boolean {
      return (feature: string) => this.features[feature] ?? false
    }
  },

  actions: {
    // 加载权限信息
    async loadPermissions() {
      this.loading = true
      try {
        const res = await permissionApi.getFeatures()
        this.userLevel = res.data.user_level
        this.isTrial = res.data.is_trial
        this.trialExpiresAt = res.data.trial_expires_at
        this.subscriptionExpiresAt = res.data.subscription_expires_at
        this.features = res.data.features
      } catch (e) {
        console.error('加载权限失败:', e)
      } finally {
        this.loading = false
      }
    },

    // 检查功能并显示升级提示
    checkFeatureWithPrompt(feature: string): boolean {
      if (this.hasFeature(feature)) {
        return true
      }

      // 显示升级提示
      this.showUpgradeDialog(feature)
      return false
    },

    // 显示升级对话框
    showUpgradeDialog(feature: string) {
      // 使用全局事件或直接调用dialog
      window.dispatchEvent(new CustomEvent('show-upgrade-dialog', {
        detail: { feature }
      }))
    }
  }
})
```

### 5.2 权限指令

```typescript
// directives/permission.ts

import type { Directive, DirectiveBinding } from 'vue'
import { usePermissionStore } from '@/stores/permission'

/**
 * v-feature 指令
 * 用法: v-feature="'scheduled_analysis'"
 * 如果没有权限，元素会被禁用并添加pro标记
 */
export const vFeature: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string>) {
    const permissionStore = usePermissionStore()
    const feature = binding.value

    if (!permissionStore.hasFeature(feature)) {
      // 禁用元素
      el.classList.add('feature-locked')
      el.setAttribute('disabled', 'true')

      // 添加Pro标记
      const badge = document.createElement('span')
      badge.className = 'pro-badge'
      badge.textContent = 'PRO'
      el.appendChild(badge)

      // 点击时显示升级提示
      el.addEventListener('click', (e) => {
        e.preventDefault()
        e.stopPropagation()
        permissionStore.showUpgradeDialog(feature)
      })
    }
  }
}

/**
 * v-if-feature 指令
 * 用法: v-if-feature="'scheduled_analysis'"
 * 如果没有权限，元素完全不显示
 */
export const vIfFeature: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string>) {
    const permissionStore = usePermissionStore()
    const feature = binding.value

    if (!permissionStore.hasFeature(feature)) {
      el.style.display = 'none'
    }
  }
}
```

### 5.3 权限组件

```vue
<!-- components/FeatureGate.vue -->
<template>
  <div class="feature-gate">
    <!-- 有权限：显示内容 -->
    <slot v-if="hasPermission" />

    <!-- 无权限：显示锁定状态 -->
    <div v-else class="feature-locked-overlay" @click="showUpgrade">
      <slot name="locked">
        <div class="locked-content">
          <el-icon :size="24"><Lock /></el-icon>
          <span class="locked-text">{{ lockedText }}</span>
          <el-tag type="warning" size="small">专业版</el-tag>
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { usePermissionStore } from '@/stores/permission'

const props = defineProps<{
  feature: string
  lockedText?: string
}>()

const permissionStore = usePermissionStore()

const hasPermission = computed(() =>
  permissionStore.hasFeature(props.feature)
)

const showUpgrade = () => {
  permissionStore.showUpgradeDialog(props.feature)
}
</script>

<style scoped>
.feature-locked-overlay {
  cursor: pointer;
  padding: 20px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  text-align: center;
}

.locked-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #909399;
}
</style>
```

### 5.4 升级提示对话框

```vue
<!-- components/UpgradeDialog.vue -->
<template>
  <el-dialog
    v-model="visible"
    title="升级到专业版"
    width="500px"
    :close-on-click-modal="true"
  >
    <div class="upgrade-content">
      <!-- 当前状态 -->
      <div class="current-status">
        <el-tag :type="statusType" size="large">{{ statusText }}</el-tag>
        <span v-if="trialDaysLeft !== null" class="trial-countdown">
          试用剩余 {{ trialDaysLeft }} 天
        </span>
      </div>

      <!-- 功能预览 -->
      <div class="features-preview">
        <h4>专业版功能</h4>
        <ul>
          <li v-for="feature in proFeatures" :key="feature.name">
            <el-icon><Check /></el-icon>
            <span>{{ feature.name }}</span>
            <span class="feature-desc">{{ feature.description }}</span>
          </li>
        </ul>
      </div>

      <!-- 价格方案 -->
      <div class="pricing-plans">
        <div class="plan" v-for="plan in plans" :key="plan.name">
          <div class="plan-name">{{ plan.name }}</div>
          <div class="plan-price">
            <span class="price">¥{{ plan.price }}</span>
            <span class="period">{{ plan.period }}</span>
          </div>
          <div v-if="plan.recommended" class="recommended">推荐</div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button v-if="canTrial" type="success" @click="startTrial">
          开始7天免费试用
        </el-button>
        <el-button type="primary" @click="goToUpgrade">
          前往升级
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { usePermissionStore } from '@/stores/permission'

const permissionStore = usePermissionStore()
const visible = ref(false)
const triggerFeature = ref('')

// 监听升级提示事件
onMounted(() => {
  window.addEventListener('show-upgrade-dialog', (e: CustomEvent) => {
    triggerFeature.value = e.detail.feature
    visible.value = true
  })
})

const trialDaysLeft = computed(() => permissionStore.trialDaysLeft)
const canTrial = computed(() => permissionStore.userLevel === 'free')

const statusType = computed(() => {
  switch (permissionStore.userLevel) {
    case 'free': return 'info'
    case 'trial': return 'warning'
    case 'pro': return 'success'
    case 'lifetime': return 'success'
    default: return 'info'
  }
})

const statusText = computed(() => {
  switch (permissionStore.userLevel) {
    case 'free': return '免费版'
    case 'trial': return '试用中'
    case 'pro': return '专业版'
    case 'lifetime': return '永久会员'
    default: return '未知'
  }
})

const proFeatures = [
  { name: '定时分析', description: '自动定期分析自选股' },
  { name: '自定义提示词', description: '个性化分析角度' },
  { name: '持仓分析', description: '基于成本的个性化建议' },
  { name: '操作复盘', description: '交易回顾与改进建议' },
  { name: '专业课程', description: '进阶学习内容' }
]

const plans = [
  { name: '月度', price: 29, period: '/月', recommended: false },
  { name: '年度', price: 199, period: '/年', recommended: true },
  { name: '永久', price: 399, period: '一次性', recommended: false }
]

const startTrial = async () => {
  // 调用试用API
  window.open('https://your-auth-site.com/trial', '_blank')
}

const goToUpgrade = () => {
  window.open('https://your-auth-site.com/pricing', '_blank')
}
</script>
```

---

## 6. 路由级权限控制

### 6.1 路由元信息扩展

```typescript
// router/index.ts

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    requiresFeature?: string    // 新增：需要的功能权限
    requiresLevel?: UserLevel   // 新增：需要的用户等级
  }
}

const routes: RouteRecordRaw[] = [
  // ... 基础路由

  // 专业版功能路由
  {
    path: '/favorites/scheduled',
    name: 'ScheduledAnalysis',
    component: () => import('@/views/Favorites/ScheduledAnalysis.vue'),
    meta: {
      title: '定时分析',
      requiresAuth: true,
      requiresFeature: 'scheduled_analysis'  // 需要专业版
    }
  },
  {
    path: '/settings/prompts',
    name: 'CustomPrompts',
    component: () => import('@/views/Settings/CustomPrompts.vue'),
    meta: {
      title: '自定义提示词',
      requiresAuth: true,
      requiresFeature: 'custom_prompt'  // 需要专业版
    }
  },
  {
    path: '/portfolio',
    name: 'PortfolioAnalysis',
    component: () => import('@/views/Portfolio/index.vue'),
    meta: {
      title: '持仓分析',
      requiresAuth: true,
      requiresFeature: 'portfolio_analysis'  // 需要专业版
    }
  }
]
```

### 6.2 路由守卫扩展

```typescript
// router/index.ts

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  // 认证检查
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    authStore.setRedirectPath(to.fullPath)
    next('/login')
    return
  }

  // 功能权限检查
  if (to.meta.requiresFeature) {
    // 确保权限已加载
    if (!permissionStore.features || Object.keys(permissionStore.features).length === 0) {
      await permissionStore.loadPermissions()
    }

    if (!permissionStore.hasFeature(to.meta.requiresFeature)) {
      // 显示升级提示
      permissionStore.showUpgradeDialog(to.meta.requiresFeature)
      // 阻止导航或跳转到升级页面
      next(from.fullPath || '/dashboard')
      return
    }
  }

  // 用户等级检查
  if (to.meta.requiresLevel) {
    // 类似逻辑
  }

  next()
})
```

---

## 7. 菜单动态控制

### 7.1 菜单配置

```typescript
// config/menu.ts

export interface MenuItem {
  path: string
  name: string
  title: string
  icon: string
  requiresFeature?: string
  children?: MenuItem[]
}

export const menuConfig: MenuItem[] = [
  // 基础功能 - 所有用户可见
  { path: '/dashboard', name: 'Dashboard', title: '仪表板', icon: 'Dashboard' },
  { path: '/analysis', name: 'Analysis', title: '股票分析', icon: 'TrendCharts' },
  { path: '/screening', name: 'Screening', title: '股票筛选', icon: 'Search' },
  { path: '/favorites', name: 'Favorites', title: '我的自选', icon: 'Star' },
  { path: '/paper-trading', name: 'PaperTrading', title: '模拟交易', icon: 'Wallet' },
  { path: '/learning', name: 'Learning', title: '学习中心', icon: 'Reading' },

  // 专业功能 - 带Pro标记
  {
    path: '/portfolio',
    name: 'Portfolio',
    title: '持仓分析',
    icon: 'PieChart',
    requiresFeature: 'portfolio_analysis'
  },
  {
    path: '/review',
    name: 'Review',
    title: '操作复盘',
    icon: 'DocumentChecked',
    requiresFeature: 'trade_review'
  },

  { path: '/settings', name: 'Settings', title: '系统设置', icon: 'Setting' }
]
```

### 7.2 菜单组件

```vue
<!-- components/Sidebar.vue -->
<template>
  <el-menu :default-active="activeMenu" router>
    <template v-for="item in menuItems" :key="item.path">
      <el-menu-item :index="item.path" :class="{ 'pro-item': isProFeature(item) }">
        <el-icon><component :is="item.icon" /></el-icon>
        <template #title>
          <span>{{ item.title }}</span>
          <el-tag
            v-if="isProFeature(item) && !hasFeature(item.requiresFeature)"
            type="warning"
            size="small"
            class="pro-tag"
          >
            PRO
          </el-tag>
        </template>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { usePermissionStore } from '@/stores/permission'
import { menuConfig } from '@/config/menu'

const route = useRoute()
const permissionStore = usePermissionStore()

const activeMenu = computed(() => route.path)
const menuItems = menuConfig

const isProFeature = (item: typeof menuConfig[0]) => !!item.requiresFeature
const hasFeature = (feature?: string) => feature ? permissionStore.hasFeature(feature) : true
</script>

<style scoped>
.pro-tag {
  margin-left: 8px;
  font-size: 10px;
}

.pro-item:not(.is-active) {
  opacity: 0.7;
}
</style>
```

---

## 8. 实现计划

### Phase 1: 基础架构 (Week 1)

- [ ] 扩展用户模型，添加License字段
- [ ] 实现权限配置常量
- [ ] 后端权限检查装饰器

### Phase 2: 后端API (Week 2)

- [ ] 权限检查API
- [ ] 保护已有专业功能API
- [ ] 统一403响应格式

### Phase 3: 前端权限Store (Week 3)

- [ ] 权限Store实现
- [ ] 权限加载与缓存
- [ ] 登录后自动加载权限

### Phase 4: 前端UI控制 (Week 4)

- [ ] 权限指令
- [ ] FeatureGate组件
- [ ] 升级对话框

### Phase 5: 路由与菜单 (Week 5)

- [ ] 路由元信息扩展
- [ ] 路由守卫权限检查
- [ ] 菜单Pro标记

### Phase 6: 测试优化 (Week 6)

- [ ] 各等级用户测试
- [ ] 边界情况处理
- [ ] 用户体验优化

---

## 9. 注意事项

### 9.1 安全原则

| 原则 | 说明 |
|------|------|
| **后端优先** | 前端控制仅为UX，后端必须做权限校验 |
| **防绕过** | API必须检查权限，不能只靠前端隐藏 |
| **审计日志** | 记录权限拒绝事件，便于分析 |

### 9.2 用户体验

| 场景 | 处理 |
|------|------|
| 试用到期 | 提前3天提醒，到期后降级为免费版 |
| 功能被锁 | 清晰展示"需要专业版"，引导升级 |
| 升级成功 | 即时生效，无需重新登录 |

### 9.3 兼容性

- 老用户默认为FREE等级
- 迁移脚本自动添加license字段
- 前端兼容无license字段的响应

