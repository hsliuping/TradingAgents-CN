<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">推荐股票</h2>
        <div class="subtitle">基于策略与主线给出观察名单（当前为前端占位数据）</div>
      </div>
      <div class="actions">
        <el-select v-model="market" style="width: 140px">
          <el-option label="A股" value="A股" />
          <el-option label="港股" value="港股" />
          <el-option label="美股" value="美股" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索代码/名称/理由" clearable style="width: 240px" />
      </div>
    </div>

    <el-card shadow="hover">
      <el-table :data="filtered" style="width: 100%" row-key="code">
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="theme" label="主线/标签" width="160">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.theme }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="推荐理由" min-width="260" />
        <el-table-column prop="confidence" label="置信度" width="120">
          <template #default="{ row }">
            <el-tag :type="confidenceType(row.confidence)" size="small">{{ row.confidence }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goAnalyze(row.code)">去分析</el-button>
            <el-button size="small" @click="copy(row.code)">复制代码</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-alert
        class="hint"
        type="info"
        :closable="false"
        show-icon
        title="说明：此页面目前仅展示前端占位数据；后续接入后端后将支持策略参数、实时打分与一键加入自选。"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

type Confidence = '高' | '中' | '低'
type Market = 'A股' | '港股' | '美股'

type StockRow = {
  market: Market
  code: string
  name: string
  theme: string
  reason: string
  confidence: Confidence
}

const router = useRouter()
const market = ref<Market>('A股')
const keyword = ref('')

const rows = ref<StockRow[]>([
  { market: 'A股', code: '300750', name: '示例公司A', theme: '主线：成长', reason: '趋势上行 + 资金流入', confidence: '高' },
  { market: 'A股', code: '688788', name: '示例公司B', theme: '主线：AI应用', reason: '题材强度高 + 回撤承接', confidence: '中' },
  { market: '港股', code: '00700', name: '示例公司HK', theme: '主线：互联网', reason: '估值修复预期 + 流动性改善', confidence: '中' },
  { market: '美股', code: 'AAPL', name: '示例公司US', theme: '主线：消费科技', reason: '强势龙头 + 财报预期', confidence: '低' }
])

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return rows.value
    .filter((r) => r.market === market.value)
    .filter((r) => {
      if (!kw) return true
      return (
        r.code.toLowerCase().includes(kw) ||
        r.name.toLowerCase().includes(kw) ||
        r.reason.toLowerCase().includes(kw) ||
        r.theme.toLowerCase().includes(kw)
      )
    })
})

function confidenceType(c: Confidence) {
  if (c === '高') return 'danger'
  if (c === '中') return 'warning'
  return 'info'
}

function goAnalyze(code: string) {
  router.push(`/analysis/single?stock_code=${encodeURIComponent(code)}`)
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.info('复制失败，请手动复制')
  }
}
</script>

<style lang="scss" scoped>
.page {
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }
  .title {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: var(--el-text-color-primary);
  }
  .subtitle {
    margin-top: 6px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .hint {
    margin-top: 14px;
  }
}
</style>
