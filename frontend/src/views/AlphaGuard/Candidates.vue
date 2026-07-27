<template>
  <div v-loading="loading" class="page-grid">
    <el-card shadow="never">
      <template #header><div class="header-row"><strong>我的候选池</strong><div><el-button @click="reconcile">安全核对</el-button><el-button type="primary" @click="dialogVisible = true">添加 A 股/ETF</el-button></div></div></template>
      <el-alert type="info" :closable="false" show-icon title="移除 USER_SELECTED 来源不会删除仍有持仓、有效订单或其他来源的候选；保护原因会明确显示。" />
      <el-table :data="candidates" size="small">
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="status" label="状态" width="140" />
        <el-table-column label="来源" min-width="220">
          <template #default="{ row }"><el-tag v-for="source in row.sources" :key="source" class="source-tag">{{ source }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column prop="updated_at" label="更新时间" min-width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button link type="danger" @click="remove(row)">移除来源</el-button></template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !candidates.length" description="候选池为空；系统不会自动推荐全市场股票" />
    </el-card>

    <el-dialog v-model="dialogVisible" title="添加用户选择候选" width="480px">
      <el-form label-width="90px">
        <el-form-item label="市场"><el-input model-value="CN" disabled /></el-form-item>
        <el-form-item label="股票代码"><el-input v-model.trim="form.symbol" placeholder="例如 600519 或 510300" /></el-form-item>
        <el-form-item label="名称"><el-input v-model.trim="form.name" placeholder="可选" /></el-form-item>
        <el-form-item label="优先级"><el-slider v-model="form.priority" :min="0" :max="100" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!form.symbol" @click="add">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { alphaguardApi, type CandidateEntry } from '@/api/alphaguard'

const loading = ref(false)
const dialogVisible = ref(false)
const candidates = ref<CandidateEntry[]>([])
const form = reactive({ symbol: '', name: '', priority: 50 })

async function load() {
  loading.value = true
  try {
    candidates.value = (await alphaguardApi.candidates({ market: 'CN', limit: 500 })).data.items
  } finally {
    loading.value = false
  }
}
async function add() {
  await alphaguardApi.addCandidate({ symbol: form.symbol, name: form.name || undefined, priority: form.priority, market: 'CN' })
  dialogVisible.value = false
  form.symbol = ''
  form.name = ''
  ElMessage.success('候选来源已合并')
  await load()
}
async function remove(row: Record<string, unknown>) {
  const candidate = row as unknown as CandidateEntry
  await ElMessageBox.confirm(`移除 ${candidate.symbol} 的 USER_SELECTED 来源？保护依赖仍会保留。`, '安全移除', { type: 'warning' })
  const result = (await alphaguardApi.removeCandidate(candidate.candidate_id)).data
  if (result.monitoring_retained) {
    ElMessage.warning(`候选继续保留：${result.retention_reasons.join('；')}`)
  } else {
    ElMessage.success('用户选择来源已移除')
  }
  await load()
}
async function reconcile() {
  const result = await alphaguardApi.reconcileCandidates()
  ElMessage.success(`核对完成：${JSON.stringify(result.data)}`)
  await load()
}
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.source-tag { margin-right: 4px; margin-bottom: 3px; }
</style>
