<template>
  <div class="skill-gaps-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total ?? 0 }}</div>
          <div class="stat-label">全部缺口</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card pending">
          <div class="stat-value">{{ stats.by_status?.pending ?? 0 }}</div>
          <div class="stat-label">待处理</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card resolved">
          <div class="stat-value">{{ stats.by_status?.resolved ?? 0 }}</div>
          <div class="stat-label">已解决</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card dismissed">
          <div class="stat-value">{{ stats.by_status?.dismissed ?? 0 }}</div>
          <div class="stat-label">已忽略</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 过滤栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :span="6">
          <el-select v-model="filterStatus" placeholder="全部状态" clearable @change="loadList(1)">
            <el-option label="待处理" value="pending" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="dismissed" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button @click="loadList(1)">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never" class="list-card">
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="gap.tool_name" label="工具名" min-width="160" />
        <el-table-column label="缺口类型" width="140">
          <template #default="{ row }">
            <el-tag :type="row.gap.type === 'tool_not_found' ? 'danger' : 'warning'" size="small">
              {{ row.gap.type === 'tool_not_found' ? '工具未找到' : '执行失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source.agent_id" label="Agent" width="140" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发现时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="warning"
              @click="handleDismiss(row)"
            >忽略</el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="success"
              @click="handleCreateSkill(row)"
            >创建 Skill</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pagination"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadList"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="缺口报告详情" width="600px">
      <template v-if="current">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="工具名">{{ current.gap?.tool_name }}</el-descriptions-item>
          <el-descriptions-item label="缺口类型">{{ current.gap?.type }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ current.source?.agent_id }}</el-descriptions-item>
          <el-descriptions-item label="工作流">{{ current.source?.workflow_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ current.gap?.error_message || '—' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(current.status) }}</el-descriptions-item>
          <el-descriptions-item label="发现时间">{{ formatDate(current.created_at) }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="current?.status === 'pending'" type="warning" @click="handleDismiss(current)">忽略</el-button>
        <el-button v-if="current?.status === 'pending'" type="success" @click="handleCreateSkill(current)">创建 Skill</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listGaps,
  getGapStats,
  dismissGap,
  getCreateSkillParams,
  type SkillGapReport,
  type GapStats,
} from '@/api/skill_gaps'

type ElTagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const router = useRouter()

// 列表状态
const loading = ref(false)
const items = ref<SkillGapReport[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')

// 统计
const stats = ref<Partial<GapStats>>({})

// 详情对话框
const detailVisible = ref(false)
const current = ref<SkillGapReport | null>(null)

async function loadList(p = page.value) {
  loading.value = true
  page.value = p
  try {
    const res = await listGaps({ status: filterStatus.value || undefined, page: p, page_size: pageSize.value })
    items.value = res.items
    total.value = res.total
  } catch {
    ElMessage.error('加载缺口列表失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getGapStats()
  } catch {
    // ignore
  }
}

function openDetail(row: SkillGapReport) {
  current.value = row
  detailVisible.value = true
}

async function handleDismiss(row: SkillGapReport | null) {
  if (!row) return
  await ElMessageBox.confirm(`确定忽略工具 "${row.gap?.tool_name}" 的缺口报告吗？30天内不再重复提醒。`, '忽略确认', { type: 'warning' })
  try {
    await dismissGap(row.report_id)
    ElMessage.success('已忽略')
    detailVisible.value = false
    loadList()
    loadStats()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleCreateSkill(row: SkillGapReport | null) {
  if (!row) return
  try {
    const res = await getCreateSkillParams(row.report_id)
    router.push({
      path: '/workflow/skill-generation/create',
      query: {
        name: res.prefill.name,
        description: res.prefill.description,
        tags: res.prefill.tags.join(','),
        from_gap: row.report_id,
      },
    })
  } catch {
    ElMessage.error('获取预填参数失败')
  }
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '待处理', reviewed: '已查看', creating: '创建中', resolved: '已解决', dismissed: '已忽略', expired: '已过期' }
  return map[status] ?? status
}

function statusTagType(status: string): ElTagType {
  const map: Record<string, ElTagType> = { pending: 'danger', reviewed: 'info', creating: 'primary', resolved: 'success', dismissed: 'info', expired: 'info' }
  return map[status] ?? 'info'
}

function formatDate(dt: string) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('zh-CN')
}

onMounted(() => {
  loadList()
  loadStats()
})
</script>

<style scoped>
.skill-gaps-page { padding: 20px; }
.stats-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: bold; color: var(--el-color-primary); }
.stat-card.pending .stat-value { color: var(--el-color-danger); }
.stat-card.resolved .stat-value { color: var(--el-color-success); }
.stat-card.dismissed .stat-value { color: var(--el-color-info); }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.filter-card { margin-bottom: 16px; }
.list-card { }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>

