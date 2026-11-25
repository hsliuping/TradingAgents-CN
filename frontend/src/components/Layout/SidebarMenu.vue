<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="appStore.sidebarCollapsed"
    :unique-opened="true"
    router
    class="sidebar-menu"
  >
    <el-menu-item index="/dashboard">
      <el-icon><Odometer /></el-icon>
      <template #title>仪表板</template>
    </el-menu-item>

    <el-menu-item index="/guide">
      <el-icon><Document /></el-icon>
      <template #title>使用指南</template>
    </el-menu-item>

    <el-menu-item index="/learning">
      <el-icon><Reading /></el-icon>
      <template #title>学习中心</template>
    </el-menu-item>

    <el-menu-item index="/analysis/single">
      <el-icon><TrendCharts /></el-icon>
      <template #title>单股研究</template>
    </el-menu-item>

    <!-- Pro：批量分析（社区版发布时 navigation.pro.ts 整文件替换为空配置，菜单自动隐藏） -->
    <el-menu-item v-for="item in proTopLevelItems" :key="item.path" :index="item.path">
      <el-icon><DataAnalysis /></el-icon>
      <template #title>
        {{ item.label }}
        <el-tag v-if="item.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </template>
    </el-menu-item>

    <el-menu-item index="/analysis/general">
      <el-icon><Search /></el-icon>
      <template #title>通用研究</template>
    </el-menu-item>

    <el-menu-item index="/assistant">
      <el-icon><ChatDotRound /></el-icon>
      <template #title>智能助手</template>
    </el-menu-item>

    <el-menu-item index="/memory">
      <el-icon><Coin /></el-icon>
      <template #title>AI 记忆</template>
    </el-menu-item>

    <!-- Skill 中心（v3.6.0 起免费开放） -->
    <el-menu-item index="/skills">
      <el-icon><MagicStick /></el-icon>
      <template #title>Skill 中心</template>
    </el-menu-item>

    <el-menu-item index="/reports">
      <el-icon><Document /></el-icon>
      <template #title>研究报告</template>
    </el-menu-item>

    <!-- Pro：分析流子菜单（社区版发布时自动隐藏，见 navigation.pro.ts） -->
    <el-sub-menu :index="proWorkflowMenu.path">
      <template #title>
        <el-icon><SetUp /></el-icon>
        <span>{{ proWorkflowMenu.label }}</span>
        <el-tag v-if="proWorkflowMenu.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </template>
      <el-menu-item v-for="child in proWorkflowMenu.children" :key="child.path" :index="child.path">
        {{ child.label }}
        <el-tag v-if="child.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        <el-tag v-else-if="child.badge" :type="child.badge.type" size="small" style="margin-left: 4px; transform: scale(0.85);">{{ child.badge.text }}</el-tag>
      </el-menu-item>
    </el-sub-menu>

    <el-menu-item index="/tasks/unified">
      <el-icon><List /></el-icon>
      <template #title>任务中心</template>
    </el-menu-item>

    <el-menu-item index="/screening">
      <el-icon><Search /></el-icon>
      <template #title>股票筛选</template>
    </el-menu-item>

    <el-menu-item index="/favorites">
      <el-icon><Star /></el-icon>
      <template #title>股票关注列表</template>
    </el-menu-item>

    <el-menu-item index="/paper">
      <el-icon><CreditCard /></el-icon>
      <template #title>模拟交易</template>
    </el-menu-item>

    <el-menu-item index="/portfolio">
      <el-icon><PieChart /></el-icon>
      <template #title>持仓研究</template>
    </el-menu-item>

    <el-menu-item index="/review">
      <el-icon><DocumentChecked /></el-icon>
      <template #title>操作复盘</template>
    </el-menu-item>

    <!-- Pro：交易计划（社区版发布时自动隐藏，见 navigation.pro.ts） -->
    <el-menu-item v-for="item in proTradingSystemMenuItems" :key="item.path" :index="item.path">
      <el-icon><Tickets /></el-icon>
      <template #title>
        {{ item.label }}
        <el-tag v-if="item.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </template>
    </el-menu-item>

    <el-sub-menu index="/settings">
      <template #title>
        <el-icon><Setting /></el-icon>
        <span>设置</span>
      </template>

      <!-- 个人设置 -->
      <el-sub-menu index="/settings-personal">
        <template #title>个人设置</template>
        <el-menu-item index="/settings">通用设置</el-menu-item>
        <el-menu-item index="/settings?tab=appearance">外观设置</el-menu-item>
        <el-menu-item index="/settings?tab=analysis">分析偏好</el-menu-item>
        <el-menu-item index="/settings?tab=notifications">通知设置</el-menu-item>
        <el-menu-item index="/settings?tab=security">安全设置</el-menu-item>
        <el-menu-item index="/settings?tab=assistant">助理设置</el-menu-item>

        <!-- Pro：个人设置项（社区版发布时自动隐藏，见 navigation.pro.ts） -->
        <el-menu-item v-for="item in proPersonalSettingsItems" :key="item.path" :index="item.path">
          {{ item.label }}
          <el-tag v-if="item.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item v-if="!isJdyunMode() && proLicenseMenuItem" :index="proLicenseMenuItem.path">
          {{ proLicenseMenuItem.label }}
          <el-icon style="margin-left: 4px;"><Key /></el-icon>
        </el-menu-item>
      </el-sub-menu>

      <!-- 系统配置 -->
      <el-sub-menu index="/settings-config">
        <template #title>系统配置</template>
        <!-- 京东云模式：显示京东云配置状态页（只读），隐藏配置管理 -->
        <el-menu-item v-if="isJdyunMode()" index="/settings/jdyun-config">系统配置</el-menu-item>
        <!-- 非京东云模式：显示完整的配置管理 -->
        <el-menu-item v-else index="/settings/config">配置管理</el-menu-item>
        <el-menu-item index="/settings/cache">缓存管理</el-menu-item>
      </el-sub-menu>

      <!-- 分析配置 -->
      <el-sub-menu index="/settings-analysis">
        <template #title>分析配置</template>
        <!-- Pro：分析配置项（社区版发布时自动隐藏，见 navigation.pro.ts） -->
        <el-menu-item v-for="item in proAnalysisSettingsItems" :key="item.path" :index="item.path">
          {{ item.label }}
          <el-tag v-if="item.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/analysis-profiles">
          行业/个股配置
          <el-tag type="info" size="small" style="margin-left: 4px; transform: scale(0.85);">智能</el-tag>
        </el-menu-item>
      </el-sub-menu>

      <!-- 系统管理 -->
      <el-sub-menu index="/settings-admin">
        <template #title>系统管理</template>
        <el-menu-item index="/settings/database">数据库管理</el-menu-item>
        <el-menu-item index="/settings/logs">操作日志</el-menu-item>
        <el-menu-item index="/settings/system-logs">系统日志</el-menu-item>
        <el-menu-item index="/settings/sync">多数据源同步</el-menu-item>
        <el-menu-item index="/settings/capability-index">工具能力索引</el-menu-item>
        <el-menu-item index="/settings/scheduler">定时任务</el-menu-item>
        <!-- Pro：系统管理项（社区版发布时自动隐藏，见 navigation.pro.ts） -->
        <el-menu-item v-for="item in proAdminSettingsItems" :key="item.path" :index="item.path">
          {{ item.label }}
          <el-tag v-if="item.advanced" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/data-import">
          数据导入管理
          <el-tag v-if="isAdvancedMenuItem('/settings/data-import')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/usage">使用统计</el-menu-item>
        <el-menu-item index="/settings/update">系统更新</el-menu-item>
      </el-sub-menu>
    </el-sub-menu>

    <el-menu-item index="/about">
      <el-icon><InfoFilled /></el-icon>
      <template #title>关于</template>
    </el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { isJdyunMode } from '@/utils/config'
// Pro 专属菜单项（v3.6.0 社区版开源分离 M1）：集中配置于 navigation.pro.ts，
// 社区版发布时整文件替换为空配置，Pro 菜单项自动不渲染
import {
  proTopLevelItems,
  proTradingSystemMenuItems,
  proWorkflowMenu,
  proPersonalSettingsItems,
  proLicenseMenuItem,
  proAnalysisSettingsItems,
  proAdminSettingsItems
} from '@/config/navigation.pro'
import {
  Odometer,
  Reading,
  TrendCharts,
  DataAnalysis,
  Document,
  Search,
  Star,
  List,
  SetUp,
  Setting,
  InfoFilled,
  CreditCard,
  PieChart,
  DocumentChecked,
  Key,
  Tickets,
  ChatDotRound,
  Coin,
  MagicStick,
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()

const advancedMenuItems = new Set([
  '/settings/data-import'
])

const isAdvancedMenuItem = (index: string) => {
  // 所有模式统一显示"高级"标签，京东云模式下功能同样可用（不收费、不认证）
  return advancedMenuItems.has(index)
}

const activeMenu = computed(() => {
  if (route.path.startsWith('/workflow/agent-studio')) return '/workflow/agent-workshop'
  if (route.path.startsWith('/workflow/agent-workshop/')) return '/workflow/agent-workshop'
  return route.path
})
</script>

<style lang="scss" scoped>
.sidebar-menu {
  border: none;
  height: 100%;

  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    height: 48px;
    line-height: 48px;
  }

  :deep(.el-menu-item.is-active) {
    background-color: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }
}
</style>
