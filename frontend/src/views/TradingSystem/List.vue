<template>
  <div class="trading-system-list">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Tickets /></el-icon>
          个人交易系统
        </h1>
        <span class="subtitle">管理您的交易规则和纪律</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          创建交易系统
        </el-button>
      </div>
    </div>

    <!-- 激活系统提示 -->
    <el-alert
      v-if="!store.hasActiveSystem && !store.listLoading && systems.length > 0"
      title="您还没有激活任何交易系统"
      type="warning"
      description="请选择一个交易系统并激活，以便在复盘和分析时进行合规检查。"
      show-icon
      :closable="false"
      class="mb-4"
    />

    <!-- 空状态 -->
    <el-empty
      v-if="!store.listLoading && systems.length === 0"
      description="还没有创建交易系统"
    >
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        创建第一个交易系统
      </el-button>
    </el-empty>

    <!-- 交易系统列表 -->
    <el-row v-else :gutter="20" v-loading="store.listLoading">
      <el-col v-for="system in systems" :key="system.id" :xs="24" :sm="12" :lg="8">
        <el-card class="system-card" :class="{ 'is-active': system.is_active }" shadow="hover">
          <!-- 卡片头部 -->
          <template #header>
            <div class="card-header">
              <div class="system-title">
                <span class="name">{{ system.name }}</span>
                <el-tag v-if="system.is_active" type="success" size="small">激活</el-tag>
              </div>
              <el-dropdown @command="handleCommand($event, system)">
                <el-button type="text" size="small">
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="view">
                      <el-icon><View /></el-icon> 查看详情
                    </el-dropdown-item>
                    <el-dropdown-item command="edit">
                      <el-icon><Edit /></el-icon> 编辑
                    </el-dropdown-item>
                    <el-dropdown-item v-if="!system.is_active" command="activate">
                      <el-icon><Check /></el-icon> 激活
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <el-icon><Delete /></el-icon> 删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>

          <!-- 卡片内容 -->
          <div class="card-content">
            <p class="description">{{ system.description || '暂无描述' }}</p>
            
            <div class="system-meta">
              <div class="meta-item">
                <span class="label">交易风格</span>
                <el-tag size="small" :type="getStyleType(system.style)">
                  {{ getStyleLabel(system.style) }}
                </el-tag>
              </div>
              <div class="meta-item">
                <span class="label">风险偏好</span>
                <el-tag size="small" :type="getRiskType(system.risk_profile)">
                  {{ getRiskLabel(system.risk_profile) }}
                </el-tag>
              </div>
            </div>

            <div class="system-stats">
              <div class="stat-item">
                <el-icon><Calendar /></el-icon>
                <span>创建于 {{ formatDate(system.created_at) }}</span>
              </div>
              <div class="stat-item">
                <el-icon><RefreshRight /></el-icon>
                <span>更新于 {{ formatDate(system.updated_at) }}</span>
              </div>
            </div>
          </div>

          <!-- 卡片底部 -->
          <div class="card-footer">
            <el-button type="primary" text @click="handleView(system)">
              <el-icon><View /></el-icon> 查看规则
            </el-button>
            <el-button
              v-if="!system.is_active"
              type="success"
              text
              @click="handleActivate(system)"
            >
              <el-icon><Check /></el-icon> 激活此系统
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  Tickets,
  Plus,
  MoreFilled,
  View,
  Edit,
  Check,
  Delete,
  Calendar,
  RefreshRight
} from '@element-plus/icons-vue'
import { useTradingSystemStore } from '@/stores/tradingSystem'
import type { TradingSystem } from '@/api/tradingSystem'

const router = useRouter()
const store = useTradingSystemStore()

const systems = computed(() => store.systems)

// 生命周期
onMounted(() => {
  store.fetchSystems()
})

// 方法
function handleCreate() {
  router.push('/trading-system/create')
}

function handleView(system: TradingSystem) {
  router.push(`/trading-system/${system.id}`)
}

function handleEdit(system: TradingSystem) {
  router.push(`/trading-system/${system.id}/edit`)
}

async function handleActivate(system: TradingSystem) {
  await store.activateSystem(system.id!)
}

async function handleDelete(system: TradingSystem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除交易系统 "${system.name}" 吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning' }
    )
    await store.deleteSystem(system.id!)
  } catch {
    // 用户取消
  }
}

function handleCommand(command: string, system: TradingSystem) {
  switch (command) {
    case 'view':
      handleView(system)
      break
    case 'edit':
      handleEdit(system)
      break
    case 'activate':
      handleActivate(system)
      break
    case 'delete':
      handleDelete(system)
      break
  }
}

// 工具函数
function getStyleLabel(style: string) {
  const map: Record<string, string> = {
    short_term: '短线',
    medium_term: '中线',
    long_term: '长线'
  }
  return map[style] || style
}

function getStyleType(style: string) {
  const map: Record<string, string> = {
    short_term: 'danger',
    medium_term: 'warning',
    long_term: 'success'
  }
  return map[style] || 'info'
}

function getRiskLabel(risk: string) {
  const map: Record<string, string> = {
    conservative: '保守',
    balanced: '中性',
    aggressive: '激进'
  }
  return map[risk] || risk
}

function getRiskType(risk: string) {
  const map: Record<string, string> = {
    conservative: 'success',
    balanced: 'warning',
    aggressive: 'danger'
  }
  return map[risk] || 'info'
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped lang="scss">
.trading-system-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      font-size: 24px;
      font-weight: 600;

      .header-icon {
        color: var(--el-color-primary);
      }
    }

    .subtitle {
      color: var(--el-text-color-secondary);
      font-size: 14px;
      margin-top: 4px;
      display: block;
    }
  }
}

.mb-4 {
  margin-bottom: 16px;
}

.system-card {
  margin-bottom: 20px;
  transition: all 0.3s;

  &.is-active {
    border-color: var(--el-color-success);

    :deep(.el-card__header) {
      background: var(--el-color-success-light-9);
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .system-title {
      display: flex;
      align-items: center;
      gap: 8px;

      .name {
        font-weight: 600;
        font-size: 16px;
      }
    }
  }

  .card-content {
    .description {
      color: var(--el-text-color-secondary);
      font-size: 14px;
      margin-bottom: 16px;
      line-height: 1.5;
    }

    .system-meta {
      display: flex;
      gap: 16px;
      margin-bottom: 12px;

      .meta-item {
        display: flex;
        align-items: center;
        gap: 8px;

        .label {
          color: var(--el-text-color-secondary);
          font-size: 13px;
        }
      }
    }

    .system-stats {
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--el-text-color-secondary);
      font-size: 12px;

      .stat-item {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }

  .card-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--el-border-color-lighter);
  }
}
</style>

