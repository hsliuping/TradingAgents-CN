<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2 class="title">主线观察</h2>
        <div class="subtitle">跟踪市场主线题材/行业热度与领涨标的（当前为前端占位数据）</div>
      </div>
      <div class="actions">
        <el-select v-model="market" style="width: 140px">
          <el-option label="A股" value="A股" />
          <el-option label="港股" value="港股" />
          <el-option label="美股" value="美股" />
        </el-select>
        <el-button type="primary" @click="refresh">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>主线 Top3</span>
              <el-tag type="info" size="small">{{ market }}</el-tag>
            </div>
          </template>
          <div class="top-list">
            <div v-for="t in top3" :key="t.name" class="top-item">
              <div class="name">
                <el-tag :type="heatTagType(t.heat)" size="small">{{ t.heat }}</el-tag>
                <span class="text">{{ t.name }}</span>
              </div>
              <div class="desc">{{ t.note }}</div>
              <div class="leaders">
                <el-tag v-for="s in t.leaders" :key="s" size="small" type="success" effect="plain">{{ s }}</el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>题材/行业列表</span>
              <el-input v-model="keyword" placeholder="搜索题材/行业" clearable style="width: 220px" />
            </div>
          </template>
          <el-table :data="filtered" style="width: 100%">
            <el-table-column prop="name" label="主线" min-width="180" />
            <el-table-column prop="heat" label="热度" width="120">
              <template #default="{ row }">
                <el-tag :type="heatTagType(row.heat)" size="small">{{ row.heat }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="trend" label="趋势" width="120">
              <template #default="{ row }">
                <el-tag :type="row.trend === '上行' ? 'danger' : row.trend === '震荡' ? 'warning' : 'info'" size="small">
                  {{ row.trend }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="signal" label="信号" min-width="220" />
            <el-table-column label="代表" min-width="220">
              <template #default="{ row }">
                <el-tag v-for="s in row.leaders" :key="s" size="small" type="success" effect="plain" style="margin-right: 6px">
                  {{ s }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

type Heat = '高' | '中' | '低'
type Trend = '上行' | '震荡' | '回落'

type ThemeRow = {
  name: string
  heat: Heat
  trend: Trend
  signal: string
  leaders: string[]
  note?: string
}

const market = ref<'A股' | '港股' | '美股'>('A股')
const keyword = ref('')
const lastUpdated = ref(new Date())

const rows = ref<ThemeRow[]>([
  { name: '人工智能应用', heat: '高', trend: '上行', signal: '资金集中度提升，留意回撤承接', leaders: ['000001', '300750', '688788'], note: '业绩线索+政策预期' },
  { name: '高股息价值', heat: '中', trend: '震荡', signal: '防御属性增强，关注利率预期变化', leaders: ['600000', '601988'] },
  { name: '周期资源', heat: '低', trend: '回落', signal: '价格波动加大，谨慎追涨', leaders: ['601857', '600028'] }
])

const filtered = computed(() => {
  const kw = keyword.value.trim()
  if (!kw) return rows.value
  return rows.value.filter((r) => r.name.includes(kw) || r.signal.includes(kw))
})

const top3 = computed(() => rows.value.slice().sort((a, b) => heatRank(b.heat) - heatRank(a.heat)).slice(0, 3))

function heatRank(h: Heat) {
  if (h === '高') return 3
  if (h === '中') return 2
  return 1
}

function heatTagType(h: Heat) {
  if (h === '高') return 'danger'
  if (h === '中') return 'warning'
  return 'info'
}

function refresh() {
  lastUpdated.value = new Date()
  ElMessage.success(`已刷新（${dayjs(lastUpdated.value).format('HH:mm:ss')}）`)
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
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .top-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .top-item {
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 10px;
    padding: 10px 12px;
    background: var(--el-fill-color-blank);
  }
  .name {
    display: flex;
    align-items: center;
    gap: 10px;
    .text {
      font-weight: 700;
      color: var(--el-text-color-primary);
    }
  }
  .desc {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-regular);
    line-height: 1.6;
  }
  .leaders {
    margin-top: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
}
</style>
