<template>
  <el-dialog
    v-model="visible"
    title="选择工具"
    width="600px"
    class="tool-select-dialog"
    :close-on-click-modal="false"
    destroy-on-close
    @closed="handleClosed"
  >
    <div class="tool-select-dialog-body">
      <!-- 筛选区 -->
      <div class="filter-section">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索工具名称或 ID"
          clearable
          size="default"
          class="search-input"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select
          v-model="filterCategory"
          placeholder="筛选类别"
          clearable
          size="default"
          class="category-select"
        >
          <el-option
            v-for="cat in categoryOptions"
            :key="cat.value"
            :label="cat.label"
            :value="cat.value"
          />
        </el-select>
      </div>

      <!-- 已选统计 -->
      <div v-if="selectedIds.length > 0" class="selected-summary">
        已选 {{ selectedIds.length }} 个工具
      </div>

      <!-- 工具列表 -->
      <div class="tools-list">
        <div
          v-for="tool in filteredTools"
          :key="tool.id"
          class="tool-item"
          :class="{ selected: selectedIds.includes(tool.id) }"
          @click="toggleTool(tool.id)"
        >
          <el-checkbox
            :model-value="selectedIds.includes(tool.id)"
            @click.stop
            @change="(val: boolean | string | number) => toggleTool(tool.id, val as boolean)"
          />
          <div class="tool-info">
            <div class="tool-header">
              <span class="tool-icon">{{ tool.icon }}</span>
              <span class="tool-name">{{ tool.name }}</span>
              <el-tag size="small" :type="tool.is_online ? 'success' : 'info'">
                {{ tool.is_online ? '在线' : '离线' }}
              </el-tag>
            </div>
            <div class="tool-meta">
              <span class="tool-id">{{ tool.id }}</span>
              <el-tag size="small" effect="plain">{{ getCategoryLabel(tool.category) }}</el-tag>
            </div>
            <div v-if="tool.description" class="tool-desc">{{ tool.description }}</div>
          </div>
        </div>
        <el-empty v-if="filteredTools.length === 0" description="未找到匹配的工具" :image-size="60" />
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleConfirm">
          确定 ({{ selectedIds.length }})
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { ToolMetadata } from '@/api/tools'

// 类别显示名称映射
const CATEGORY_LABELS: Record<string, string> = {
  market: '市场数据',
  fundamentals: '基本面数据',
  news: '新闻数据',
  social: '社交媒体',
  technical: '技术分析',
  china: '中国市场',
  trade_review: '交易复盘',
  utility: '通用工具',
  knowledge: '知识型',
  mcp: 'MCP',
}

const props = defineProps<{
  modelValue: boolean
  tools: ToolMetadata[]
  selected: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'confirm', selected: string[]): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const searchKeyword = ref('')
const filterCategory = ref('')

// 选中的工具 ID（内部状态，可编辑）
const selectedIds = ref<string[]>([])

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      selectedIds.value = [...props.selected]
      searchKeyword.value = ''
      filterCategory.value = ''
    }
  }
)

watch(
  () => props.selected,
  (val) => {
    if (props.modelValue) {
      selectedIds.value = [...val]
    }
  },
  { immediate: true }
)

// 从 tools 中提取唯一类别
const categoryOptions = computed(() => {
  const cats = new Set<string>()
  props.tools.forEach((t) => cats.add(t.category))
  return Array.from(cats)
    .sort()
    .map((c) => ({ value: c, label: getCategoryLabel(c) }))
})

const getCategoryLabel = (cat: string) => CATEGORY_LABELS[cat] || cat

// 筛选后的工具列表
const filteredTools = computed(() => {
  let list = props.tools
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter(
      (t) =>
        t.name.toLowerCase().includes(kw) ||
        t.id.toLowerCase().includes(kw) ||
        (t.description || '').toLowerCase().includes(kw)
    )
  }
  if (filterCategory.value) {
    list = list.filter((t) => t.category === filterCategory.value)
  }
  return list
})

const toggleTool = (id: string, checked?: boolean) => {
  const idx = selectedIds.value.indexOf(id)
  const isChecked = checked !== undefined ? checked : idx === -1
  if (isChecked && idx === -1) {
    selectedIds.value = [...selectedIds.value, id]
  } else if (!isChecked && idx >= 0) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
}

const handleConfirm = () => {
  emit('confirm', [...selectedIds.value])
  visible.value = false
}

const handleCancel = () => {
  visible.value = false
}

const handleClosed = () => {
  searchKeyword.value = ''
  filterCategory.value = ''
}
</script>

<style scoped lang="scss">
.tool-select-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 480px;
}

.filter-section {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
  .search-input {
    flex: 1;
  }
  .category-select {
    width: 140px;
  }
}

.selected-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.tools-list {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 8px;
  min-height: 200px;
  max-height: 340px;

  .tool-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: var(--el-fill-color-light);
    }
    &.selected {
      background: var(--el-color-primary-light-9);
    }

    .tool-info {
      flex: 1;
      min-width: 0;
    }
    .tool-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
      .tool-icon {
        font-size: 18px;
      }
      .tool-name {
        font-weight: 500;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
    .tool-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
      .tool-id {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        font-family: monospace;
      }
    }
    .tool-desc {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
