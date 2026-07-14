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

    <el-menu-item index="/analysis/batch">
      <el-icon><DataAnalysis /></el-icon>
      <template #title>
        批量分析
        <el-tag v-if="isAdvancedMenuItem('/analysis/batch')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
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

    <el-menu-item index="/reports">
      <el-icon><Document /></el-icon>
      <template #title>研究报告</template>
    </el-menu-item>

    <el-sub-menu index="/workflow">
      <template #title>
        <el-icon><SetUp /></el-icon>
        <span>分析流</span>
        <el-tag v-if="isAdvancedMenuItem('/workflow')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </template>
      <el-menu-item index="/workflow">
        流程管理
        <el-tag v-if="isAdvancedMenuItem('/workflow')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </el-menu-item>
      <el-menu-item index="/workflow/tools">
        工具配置
        <el-tag v-if="isAdvancedMenuItem('/workflow/tools')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </el-menu-item>
      <el-menu-item index="/workflow/agent-workshop">
        Agent 工坊
        <el-tag type="primary" size="small" style="margin-left: 4px; transform: scale(0.85);">迭代</el-tag>
      </el-menu-item>
      <el-menu-item index="/workflow/skills">
        Skill 中心
        <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
      </el-menu-item>
      <el-menu-item index="/workflow/mcp-servers">
        MCP 服务器
        <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
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

    <el-menu-item index="/trading-system">
      <el-icon><Tickets /></el-icon>
      <template #title>交易计划</template>
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

        <el-menu-item index="/settings/email">
          邮件通知
          <el-tag v-if="isAdvancedMenuItem('/settings/email')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/channel-configs">
          渠道推送
          <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/watchlist-groups">
          定时分析分组
          <el-tag v-if="isAdvancedMenuItem('/settings/watchlist-groups')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/scheduled-analysis">
          定时分析配置
          <el-tag v-if="isAdvancedMenuItem('/settings/scheduled-analysis')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
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

      <!-- 分析配置 -->
      <el-sub-menu index="/settings-analysis">
        <template #title>分析配置</template>
        <el-menu-item index="/settings/templates">
          提示词模板
          <el-tag v-if="isAdvancedMenuItem('/settings/templates')" type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/prompt-policies">
          注入策略管理
          <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
        </el-menu-item>
        <el-menu-item index="/settings/prompt-design">
          Prompt 设计助手
          <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
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
        <el-menu-item index="/settings/social-media">社媒消息管理</el-menu-item>
        <el-menu-item index="/settings/data-import">
          数据导入管理
          <el-tag type="success" size="small" style="margin-left: 4px; transform: scale(0.85);">高级</el-tag>
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
} from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()

const advancedMenuItems = new Set([
  '/analysis/batch',
  '/workflow',
  '/workflow/tools',
  '/workflow/agents',
  '/settings/templates',
  '/settings/email',
  '/settings/watchlist-groups',
  '/settings/scheduled-analysis',
  '/settings/data-import'
])

const isAdvancedMenuItem = (index: string) => advancedMenuItems.has(index)

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
