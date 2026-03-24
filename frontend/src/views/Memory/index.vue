<template>
  <div class="memory-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Coin /></el-icon>
          AI 记忆管理
        </h1>
        <span class="subtitle">查看和管理 AI 系统从对话、分析中积累的记忆</span>
      </div>
      <div class="header-right">
        <el-button @click="fetchAll" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-popconfirm
          title="确定要清除全部记忆？此操作不可恢复。"
          confirm-button-text="确认清除"
          cancel-button-text="取消"
          @confirm="handleDeleteAll"
        >
          <template #reference>
            <el-button type="danger" plain :disabled="stats.total === 0">
              <el-icon><Delete /></el-icon>
              清除全部
            </el-button>
          </template>
        </el-popconfirm>
      </div>
    </div>

    <!-- 健康状态 + 统计概览 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :xs="24" :sm="8" :md="6">
        <el-card shadow="hover" class="stat-card total-card">
          <div class="stat-content">
            <div class="stat-number">{{ stats.total }}</div>
            <div class="stat-label">总记忆数</div>
          </div>
          <el-icon class="stat-icon"><Coin /></el-icon>
        </el-card>
      </el-col>
      <el-col v-for="(count, scope) in stats.scopes" :key="scope" :xs="12" :sm="8" :md="6">
        <el-card shadow="hover" class="stat-card" @click="filterByScope(scope as string)">
          <div class="stat-content">
            <div class="stat-number">{{ count }}</div>
            <div class="stat-label">{{ getScopeLabel(scope as string) }}</div>
          </div>
          <el-tag :type="getScopeColor(scope as string)" size="small" effect="plain">
            {{ scope }}
          </el-tag>
        </el-card>
      </el-col>
    </el-row>

    <!-- 不可用提示 -->
    <el-alert
      v-if="!stats.enabled"
      title="记忆功能未启用"
      description="请在 .env 中设置 MEM0_ENABLED=true 并配置 LLM API Key 以启用记忆功能。"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    />
    <el-alert
      v-else-if="stats.enabled && stats.available === false"
      title="记忆服务不可用"
      :description="stats.message || 'mem0 初始化失败，请检查配置。'"
      type="error"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    />

    <!-- 搜索 + 过滤 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="10">
          <el-input
            v-model="searchQuery"
            placeholder="语义搜索记忆内容..."
            clearable
            @keyup.enter="handleSearch"
            @clear="handleClearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button @click="handleSearch" :loading="searching">搜索</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :span="5">
          <el-select
            v-model="currentScope"
            placeholder="全部类别"
            clearable
            @change="handleScopeChange"
            style="width: 100%"
          >
            <el-option
              v-for="s in scopeOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-col>
        <el-col :span="5">
          <span class="result-hint" v-if="isSearchMode">
            语义搜索结果：{{ memories.length }} 条
          </span>
          <span class="result-hint" v-else>
            共 {{ totalMemories }} 条记忆
          </span>
        </el-col>
        <el-col :span="4" style="text-align: right;">
          <el-button
            type="danger"
            plain
            size="small"
            :disabled="selectedIds.length === 0"
            @click="handleBatchDelete"
          >
            <el-icon><Delete /></el-icon>
            删除选中 ({{ selectedIds.length }})
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 记忆列表 -->
    <el-card shadow="never" class="list-card">
      <el-table
        ref="tableRef"
        :data="memories"
        v-loading="loading || searching"
        @selection-change="handleSelectionChange"
        row-key="id"
        style="width: 100%"
      >
        <el-table-column type="selection" width="45" />

        <el-table-column label="记忆内容" min-width="400">
          <template #default="{ row }">
            <div class="memory-content">{{ row.memory }}</div>
          </template>
        </el-table-column>

        <el-table-column label="类别" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getScopeColor(row.scope)" size="small">
              {{ getScopeLabel(row.scope) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="来源" width="120" align="center">
          <template #default="{ row }">
            <span class="agent-label">{{ row.agent_id || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="相关度" width="90" align="center" v-if="isSearchMode">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.score || 0) * 100)"
              :stroke-width="6"
              :text-inside="false"
              :show-text="false"
              :color="getScoreColor(row.score)"
              style="width: 60px; display: inline-block;"
            />
            <span class="score-text">{{ ((row.score || 0) * 100).toFixed(0) }}%</span>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.created_at || row.updated_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定删除这条记忆？"
              @confirm="handleDeleteOne(row.id)"
            >
              <template #reference>
                <el-button type="danger" text size="small">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty v-if="!loading && !searching" :image-size="120">
            <template #description>
              <p v-if="isSearchMode">未找到相关记忆，换个关键词试试</p>
              <p v-else-if="currentScope">该类别暂无记忆</p>
              <p v-else>AI 尚未积累任何记忆，开始使用智能助手或分析功能后会自动记录</p>
            </template>
          </el-empty>
        </template>
      </el-table>

      <!-- 分页（非搜索模式） -->
      <div class="pagination-wrapper" v-if="!isSearchMode && totalMemories > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalMemories"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Coin, Refresh, Delete, Search } from '@element-plus/icons-vue'
import { memoryApi, SCOPE_LABELS, SCOPE_COLORS } from '@/api/memory'
import type { MemoryItem } from '@/api/memory'

const loading = ref(false)
const searching = ref(false)
const searchQuery = ref('')
const currentScope = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const memories = ref<MemoryItem[]>([])
const totalMemories = ref(0)
const selectedIds = ref<string[]>([])
const isSearchMode = ref(false)

const stats = reactive<{
  enabled: boolean
  available?: boolean
  total: number
  scopes: Record<string, number>
  message?: string
}>({
  enabled: true,
  available: true,
  total: 0,
  scopes: {},
})

const scopeOptions = computed(() =>
  Object.entries(SCOPE_LABELS).map(([value, label]) => ({ value, label }))
)

function getScopeLabel(scope: string) {
  return SCOPE_LABELS[scope] || scope
}

function getScopeColor(scope: string): any {
  return SCOPE_COLORS[scope] || 'info'
}

function getScoreColor(score: number) {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.5) return '#e6a23c'
  return '#909399'
}

function formatTime(t: string) {
  if (!t) return '-'
  try {
    const d = new Date(t)
    if (isNaN(d.getTime())) return t
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return t
  }
}

async function fetchStats() {
  try {
    const data = await memoryApi.getStats()
    stats.enabled = data.enabled
    stats.available = data.available
    stats.total = data.total ?? 0
    stats.scopes = data.scopes ?? {}
    stats.message = data.message
  } catch {
    // ignore
  }
}

async function fetchList() {
  loading.value = true
  isSearchMode.value = false
  try {
    const data = await memoryApi.getList({
      scope: currentScope.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    memories.value = data.items
    totalMemories.value = data.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载记忆列表失败')
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) {
    handleClearSearch()
    return
  }
  searching.value = true
  isSearchMode.value = true
  try {
    const data = await memoryApi.recall(q, currentScope.value || undefined, 20)
    memories.value = data.items
    totalMemories.value = data.count
  } catch (e: any) {
    ElMessage.error(e?.message || '搜索失败')
  } finally {
    searching.value = false
  }
}

function handleClearSearch() {
  searchQuery.value = ''
  isSearchMode.value = false
  currentPage.value = 1
  fetchList()
}

function handleScopeChange() {
  currentPage.value = 1
  if (isSearchMode.value && searchQuery.value.trim()) {
    handleSearch()
  } else {
    fetchList()
  }
}

function filterByScope(scope: string) {
  currentScope.value = scope
  handleScopeChange()
}

function handleSelectionChange(rows: MemoryItem[]) {
  selectedIds.value = rows.map(r => r.id)
}

async function handleDeleteOne(id: string) {
  const ok = await memoryApi.deleteMemory(id)
  if (ok) {
    ElMessage.success('记忆已删除')
    fetchAll()
  } else {
    ElMessage.error('删除失败')
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 条记忆？`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  const result = await memoryApi.batchDelete(selectedIds.value)
  ElMessage.success(`已删除 ${result.deleted} 条记忆`)
  selectedIds.value = []
  fetchAll()
}

async function handleDeleteAll() {
  loading.value = true
  try {
    const result = await memoryApi.deleteAll()
    ElMessage.success(`已清除 ${result.deleted} 条记忆`)
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.message || '清除失败')
  } finally {
    loading.value = false
  }
}

async function fetchAll() {
  await Promise.all([fetchStats(), fetchList()])
}

onMounted(() => {
  fetchAll()
})
</script>

<style lang="scss" scoped>
.memory-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;

  .header-left {
    h1 {
      margin: 0 0 4px 0;
      font-size: 22px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .header-icon {
      color: var(--el-color-primary);
    }

    .subtitle {
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
  }
}

.stats-row {
  margin-bottom: 16px;

  .stat-card {
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    overflow: hidden;

    &:hover {
      transform: translateY(-2px);
      box-shadow: var(--el-box-shadow-light);
    }

    &.total-card {
      background: linear-gradient(135deg, var(--el-color-primary-light-9), var(--el-color-primary-light-7));
    }

    :deep(.el-card__body) {
      padding: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .stat-content {
      .stat-number {
        font-size: 28px;
        font-weight: 700;
        color: var(--el-text-color-primary);
        line-height: 1.2;
      }

      .stat-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-top: 4px;
      }
    }

    .stat-icon {
      font-size: 32px;
      color: var(--el-color-primary-light-3);
      opacity: 0.5;
    }
  }
}

.filter-card {
  margin-bottom: 16px;

  .result-hint {
    color: var(--el-text-color-secondary);
    font-size: 13px;
    line-height: 32px;
  }
}

.list-card {
  .memory-content {
    font-size: 13px;
    line-height: 1.6;
    color: var(--el-text-color-primary);
    word-break: break-word;
  }

  .agent-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .score-text {
    font-size: 11px;
    color: var(--el-text-color-secondary);
    margin-left: 4px;
  }

  .time-text {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    padding: 16px 0 4px;
  }
}
</style>
