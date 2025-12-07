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

    <el-menu-item index="/learning">
      <el-icon><Reading /></el-icon>
      <template #title>学习中心</template>
    </el-menu-item>

    <el-sub-menu index="/analysis">
      <template #title>
        <el-icon><TrendCharts /></el-icon>
        <span>股票分析</span>
      </template>
      <el-menu-item index="/analysis/single">单股分析</el-menu-item>
      <el-menu-item index="/analysis/batch">批量分析</el-menu-item>
      <!-- 新增：将分析报告作为股票分析的子菜单 -->
      <el-menu-item index="/reports">分析报告</el-menu-item>
    </el-sub-menu>

    <el-menu-item index="/tasks">
      <el-icon><List /></el-icon>
      <template #title>任务中心</template>
    </el-menu-item>

    <el-menu-item index="/screening">
      <el-icon><Search /></el-icon>
      <template #title>股票筛选</template>
    </el-menu-item>

    <el-menu-item index="/favorites">
      <el-icon><Star /></el-icon>
      <template #title>我的自选股</template>
    </el-menu-item>

    <el-menu-item index="/paper">
      <el-icon><CreditCard /></el-icon>
      <template #title>模拟交易</template>
    </el-menu-item>

    <el-menu-item index="/portfolio">
      <el-icon><PieChart /></el-icon>
      <template #title>
        持仓分析
        <el-tag type="warning" size="small" style="margin-left: 4px; transform: scale(0.85);">PRO</el-tag>
      </template>
    </el-menu-item>

    <el-menu-item index="/review">
      <el-icon><DocumentChecked /></el-icon>
      <template #title>
        操作复盘
        <el-tag type="warning" size="small" style="margin-left: 4px; transform: scale(0.85);">PRO</el-tag>
      </template>
    </el-menu-item>

    <!-- 分析报告已移至“股票分析”子菜单，保留注释便于追踪 -->
    <!--
    <el-menu-item index="/reports">
      <el-icon><Document /></el-icon>
      <template #title>分析报告</template>
    </el-menu-item>
    -->

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
        <el-menu-item index="/settings/email">
          邮件通知
          <el-tag type="warning" size="small" style="margin-left: 4px; transform: scale(0.85);">PRO</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/watchlist-groups">
          自选股分组
          <el-tag type="warning" size="small" style="margin-left: 4px; transform: scale(0.85);">PRO</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/scheduled-analysis">
          定时分析配置
          <el-tag type="warning" size="small" style="margin-left: 4px; transform: scale(0.85);">PRO</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/license">
          授权管理
          <el-icon style="margin-left: 4px;"><Key /></el-icon>
        </el-menu-item>
      </el-sub-menu>

      <!-- 系统配置 -->
      <el-sub-menu index="/settings-config">
        <template #title>系统配置</template>
        <el-menu-item index="/settings/config">配置管理</el-menu-item>
        <el-menu-item index="/settings/cache">缓存管理</el-menu-item>
      </el-sub-menu>

      <!-- 系统管理 -->
      <el-sub-menu index="/settings-admin">
        <template #title>系统管理</template>
        <el-menu-item index="/settings/database">数据库管理</el-menu-item>
        <el-menu-item index="/settings/logs">操作日志</el-menu-item>
        <el-menu-item index="/settings/system-logs">系统日志</el-menu-item>
        <el-menu-item index="/settings/sync">多数据源同步</el-menu-item>
        <el-menu-item index="/settings/scheduler">定时任务</el-menu-item>
        <el-menu-item index="/settings/usage">使用统计</el-menu-item>
        <el-menu-item index="/settings/templates">模板管理</el-menu-item>
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
import {
  Odometer,
  Reading,
  TrendCharts,
  Search,
  Star,
  List,
  /* Document 移除：不再使用顶级分析报告菜单图标 */
  Setting,
  InfoFilled,
  CreditCard,
  PieChart,
  DocumentChecked,
  Key
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()

const activeMenu = computed(() => route.path)
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
