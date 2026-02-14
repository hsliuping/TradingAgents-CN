<template>
  <div class="backtest-page">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon class="title-icon"><TrendCharts /></el-icon>
        策略回测
      </h1>
      <el-tag type="warning" size="small" effect="plain" class="risk-tag">
        仅供学习研究，不构成投资建议
      </el-tag>
    </div>

    <div class="backtest-layout">
      <!-- 主区域 -->
      <div class="main-area">
        <el-card shadow="never" class="step-card">
          <el-steps :active="currentStep" finish-status="success" align-center>
            <el-step title="描述策略" />
            <el-step title="确认参数" />
            <el-step title="查看结果" />
          </el-steps>

          <!-- Step 1: 描述策略 -->
          <div v-show="currentStep === 0" class="step-content">
            <el-input
              v-model="description"
              type="textarea"
              :rows="4"
              placeholder="用自然语言描述您的策略想法，例如：每月初买入茅台、平安、招行，持有一季度后卖出..."
              :disabled="loading"
            />
            <div class="step-actions">
              <el-button type="primary" :loading="loading" @click="onAnalyze">
                分析可行性
              </el-button>
            </div>
          </div>

          <!-- Step 2: 确认参数 -->
          <div v-show="currentStep === 1" class="step-content">
            <div v-if="analysis" class="analysis-block">
              <h4>AI 分析</h4>
              <div class="analysis-text">{{ analysis }}</div>
            </div>
            <!-- 补充/改进：用户可根据分析结果迭代修改 -->
            <div v-if="analysis && !strategy" class="refinement-block">
              <h4>如需调整</h4>
              <el-input
                v-model="refinement"
                type="textarea"
                :rows="2"
                placeholder="在此补充或修改策略要求，例如：加入五粮液、时间改为2018-2023年、减少持仓数量..."
                :disabled="loading"
              />
              <div class="refinement-actions">
                <el-button :loading="loading" @click="onBackToEdit">
                  返回修改原始描述
                </el-button>
                <el-button
                  v-if="refinement.trim()"
                  type="primary"
                  :loading="loading"
                  @click="onReanalyze"
                >
                  根据补充重新分析
                </el-button>
              </div>
            </div>
            <div v-if="generateError" class="error-block">
              <el-alert type="error" :title="generateError" show-icon />
              <div class="step-actions" style="margin-top: 8px;">
                <el-button type="primary" :loading="loading" @click="onRetryGenerate">
                  重试生成
                </el-button>
              </div>
            </div>
            <div v-else-if="!strategy" class="step-actions">
              <el-button type="primary" :loading="loading" @click="onGenerate">
                生成策略参数
              </el-button>
            </div>
            <div v-else class="strategy-block">
              <h4>策略参数</h4>
              <pre class="strategy-json">{{ JSON.stringify(strategy, null, 2) }}</pre>
              <div class="step-actions">
                <el-button type="primary" :loading="loading" @click="onRun">
                  执行回测
                </el-button>
                <el-button @click="strategy = null">重新生成</el-button>
              </div>
            </div>
          </div>

          <!-- Step 3: 查看结果 -->
          <div v-show="currentStep === 2" class="step-content">
            <div v-if="runError" class="error-block">
              <el-alert type="error" :title="runError" show-icon />
            </div>
            <div v-else-if="summary" class="result-summary">
              <h4>回测结果</h4>
              <div class="metrics-grid">
                <div class="metric-item">
                  <span class="label">总收益</span>
                  <span :class="['value', (summary.total_return ?? 0) >= 0 ? 'positive' : 'negative']">
                    {{ (summary.total_return ?? 0).toFixed(2) }}%
                  </span>
                </div>
                <div class="metric-item">
                  <span class="label">最大回撤</span>
                  <span class="value negative">{{ (summary.max_drawdown_pct ?? 0).toFixed(2) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="label">夏普比率</span>
                  <span class="value">{{ (summary.sharpe_ratio ?? 0).toFixed(2) }}</span>
                </div>
                <div class="metric-item">
                  <span class="label">胜率</span>
                  <span class="value">{{ (summary.win_rate ?? 0).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="label">交易笔数</span>
                  <span class="value">{{ summary.trade_count ?? 0 }}</span>
                </div>
                <div class="metric-item">
                  <span class="label">最终资产</span>
                  <span class="value">{{ formatNumber(summary.final_value ?? 0) }}</span>
                </div>
              </div>
            </div>
            <div class="step-actions">
              <el-button @click="startOver">新建回测</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 侧边栏：历史会话 -->
      <div class="sidebar">
        <el-card shadow="never" class="sessions-card">
          <template #header>
            <span>历史会话</span>
            <el-button type="primary" link size="small" @click="loadSessions">刷新</el-button>
          </template>
          <el-scrollbar v-if="sessions.length" max-height="400">
            <div
              v-for="s in sessions"
              :key="s.id"
              class="session-item"
              @click="selectSession(s)"
            >
              <div class="session-name">{{ (s.strategy as any)?.name || s.id?.slice(0, 8) }}</div>
              <div class="session-meta">{{ s.status }} · {{ formatDate(s.created_at) }}</div>
              <el-button type="danger" link size="small" @click.stop="deleteSession(s.id)">
                删除
              </el-button>
            </div>
          </el-scrollbar>
          <el-empty v-else description="暂无回测记录" :image-size="60" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts } from '@element-plus/icons-vue'
import { backtestApi, type StrategyDSL, type BacktestSummary } from '@/api/backtest'

const currentStep = ref(0)
const description = ref('')
const refinement = ref('')  // 用户补充/修改（在 AI 分析后）
const analysis = ref('')
const strategy = ref<StrategyDSL | null>(null)
const summary = ref<BacktestSummary | null>(null)
const runError = ref('')
const generateError = ref('')
const loading = ref(false)
const sessions = ref<Array<Record<string, unknown>>>([])

/** 当前有效描述：含补充时拼接，供 generate 使用 */
const effectiveDescription = () => {
  const base = description.value.trim()
  const extra = refinement.value.trim()
  if (!extra) return base
  return base + '\n\n【用户补充】\n' + extra
}

const onAnalyze = async () => {
  if (!description.value.trim()) {
    ElMessage.warning('请输入策略描述')
    return
  }
  loading.value = true
  analysis.value = ''
  try {
    const res = await backtestApi.analyze(description.value)
    analysis.value = res.analysis || ''
    currentStep.value = 1
  } catch (e: any) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    loading.value = false
  }
}

const onReanalyze = async () => {
  if (!refinement.value.trim()) return
  loading.value = true
  try {
    const res = await backtestApi.analyze(effectiveDescription())
    analysis.value = res.analysis || ''
    refinement.value = ''
    ElMessage.success('已根据您的补充重新分析')
  } catch (e: any) {
    ElMessage.error(e?.message || '重新分析失败')
  } finally {
    loading.value = false
  }
}

const onBackToEdit = () => {
  currentStep.value = 0
  refinement.value = ''
}

const onGenerate = async () => {
  loading.value = true
  strategy.value = null
  generateError.value = ''
  try {
    const res = await backtestApi.generate(effectiveDescription())
    strategy.value = res.strategy
    generateError.value = ''
  } catch (e: any) {
    const d = e?.response?.data?.detail
    const msg = Array.isArray(d) ? d.map((x: any) => x?.msg || String(x)).join('; ') : (d || e?.message || '生成失败')
    generateError.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const onRetryGenerate = () => {
  generateError.value = ''
  onGenerate()
}

const onRun = async () => {
  if (!strategy.value) return
  loading.value = true
  runError.value = ''
  summary.value = null
  try {
    const res = await backtestApi.run(strategy.value)
    if (res.success && res.summary) {
      summary.value = res.summary
      currentStep.value = 2
      loadSessions()
    } else {
      runError.value = res.error || '回测失败'
    }
  } catch (e: any) {
    runError.value = e?.message || '回测失败'
  } finally {
    loading.value = false
  }
}

const startOver = () => {
  currentStep.value = 0
  description.value = ''
  refinement.value = ''
  analysis.value = ''
  strategy.value = null
  summary.value = null
  runError.value = ''
  generateError.value = ''
}

const loadSessions = async () => {
  try {
    sessions.value = await backtestApi.listSessions()
  } catch {
    sessions.value = []
  }
}

const selectSession = (s: Record<string, unknown>) => {
  const str = s.strategy as StrategyDSL
  if (str?.name) {
    strategy.value = str
    description.value = str.description || str.name
    analysis.value = ''
    currentStep.value = 1
  }
}

const deleteSession = async (id: string) => {
  try {
    await backtestApi.deleteSession(id)
    loadSessions()
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const formatNumber = (n: number) => {
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

const formatDate = (d: unknown) => {
  if (!d) return ''
  try {
    const dt = typeof d === 'string' ? new Date(d) : d instanceof Date ? d : new Date(String(d))
    return dt.toLocaleDateString('zh-CN')
  } catch {
    return String(d).slice(0, 10)
  }
}

onMounted(loadSessions)
</script>

<style scoped>
.backtest-page {
  padding: 16px;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 1.25rem;
}
.title-icon { font-size: 1.25em; }
.risk-tag { flex-shrink: 0; }

.backtest-layout {
  display: flex;
  gap: 20px;
}
.main-area { flex: 1; min-width: 0; }
.sidebar { width: 280px; flex-shrink: 0; }

.step-card {
  margin-bottom: 0;
}
.step-content {
  margin-top: 24px;
  min-height: 120px;
}
.step-actions {
  margin-top: 16px;
}
.analysis-block, .strategy-block, .refinement-block {
  margin-bottom: 16px;
}
.refinement-block h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}
.refinement-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.analysis-block h4, .strategy-block h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}
.analysis-text {
  white-space: pre-wrap;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 13px;
}
.strategy-json {
  padding: 12px;
  background: var(--el-fill-color-darker);
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
  max-height: 240px;
}
.error-block { margin-bottom: 16px; }
.result-summary h4 { margin: 0 0 12px 0; font-size: 14px; }
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.metric-item {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  text-align: center;
}
.metric-item .label { display: block; font-size: 12px; color: var(--el-text-color-secondary); }
.metric-item .value { font-size: 18px; font-weight: 600; }
.metric-item .value.positive { color: var(--el-color-success); }
.metric-item .value.negative { color: var(--el-color-danger); }

.sessions-card :deep(.el-card__header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.session-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
}
.session-item:hover { background: var(--el-fill-color-light); }
.session-name { font-weight: 500; }
.session-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
</style>
