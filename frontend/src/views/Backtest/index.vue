<template>
  <div class="backtest-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <el-icon class="title-icon"><TrendCharts /></el-icon>
          策略回测
        </h1>
        <el-tag type="warning" size="small" effect="plain" class="risk-tag">
          仅供学习研究，不构成投资建议
        </el-tag>
      </div>
      <el-radio-group v-model="activeTab" class="header-tabs" size="default">
        <el-radio-button value="create">新建回测</el-radio-button>
        <el-radio-button value="library">策略库</el-radio-button>
      </el-radio-group>
    </div>

    <div class="backtest-layout">
      <!-- 主区域 -->
      <div class="main-area">
        <!-- 策略库列表 -->
        <el-card v-show="activeTab === 'library'" shadow="never" class="library-card">
          <template #header>
            <span>已保存策略</span>
            <el-button type="primary" link size="small" @click="loadSessions">刷新</el-button>
          </template>
          <el-table v-if="sessions.length" :data="sessions" stripe style="width: 100%" @row-click="(row) => selectSession(row)">
            <el-table-column prop="name" label="策略名称" min-width="180">
              <template #default="{ row }">{{ sessionDisplayName(row) }}</template>
            </el-table-column>
            <el-table-column label="收益" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.summary" :class="((row.summary as any)?.total_return ?? 0) >= 0 ? 'profit' : 'loss'">
                  {{ ((row.summary as any)?.total_return ?? 0).toFixed(1) }}%
                </span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ row.status }}</template>
            </el-table-column>
            <el-table-column label="日期" width="110">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="right" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click.stop="selectSession(row)">查看</el-button>
                <el-button type="danger" link size="small" @click.stop="deleteSession(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无已保存策略，执行回测后可保存" :image-size="80" />
        </el-card>

        <el-card v-show="activeTab === 'create'" shadow="never" class="step-card">
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
              <h4>策略名称 <span class="optional">（可选，便于查找）</span></h4>
              <el-input
                v-model="strategyName"
                placeholder="例如：茅台季度轮动策略"
                maxlength="80"
                show-word-limit
                class="name-input"
                clearable
              />
              <h4>策略代码</h4>
              <el-input
                v-model="strategy.code"
                type="textarea"
                :rows="12"
                placeholder="Python 策略代码"
                class="code-textarea"
                spellcheck="false"
              />
              <h4>回测配置</h4>
              <el-input
                v-model="configJson"
                type="textarea"
                :rows="6"
                placeholder="config JSON"
                class="config-textarea"
                spellcheck="false"
              />
              <div v-if="configJsonError" class="config-error">{{ configJsonError }}</div>
              <div class="step-actions">
                <el-button type="primary" :loading="loading" :disabled="!!configJsonError" @click="onRun">
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
                  <span :class="['value', (summary.total_return ?? 0) >= 0 ? 'profit' : 'loss']">
                    {{ (summary.total_return ?? 0).toFixed(2) }}%
                  </span>
                </div>
                <div class="metric-item">
                  <span class="label">最大回撤</span>
                  <span class="value loss">{{ (summary.max_drawdown_pct ?? 0).toFixed(2) }}%</span>
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
              <!-- 成交明细 -->
              <div v-if="(summary.transactions?.length ?? 0) > 0" class="trades-section">
                <h4>成交明细</h4>
                <el-table :data="summary.transactions" size="small" stripe max-height="320" class="trades-table">
                  <el-table-column prop="date" label="日期" width="100" />
                  <el-table-column prop="symbol" label="标的" width="90" />
                  <el-table-column prop="side" label="方向" width="70">
                    <template #default="{ row }">
                      <el-tag :type="row.side === 'buy' ? 'success' : 'danger'" size="small">
                        {{ row.side === 'buy' ? '买入' : '卖出' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="size" label="数量" width="80" align="right" />
                  <el-table-column prop="price" label="价格" width="90" align="right">
                    <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="cost_basis" label="持仓成本" width="95" align="right">
                    <template #default="{ row }">
                      <span v-if="row.cost_basis != null">{{ formatNumber(row.cost_basis) }}</span>
                      <span v-else class="muted">—</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="execution_amount" label="成交金额" width="95" align="right">
                    <template #default="{ row }">{{ formatNumber(row.execution_amount ?? 0) }}</template>
                  </el-table-column>
                  <el-table-column prop="pnl_net" label="盈亏" width="90" align="right">
                    <template #default="{ row }">
                      <span v-if="row.side === 'sell' && row.pnl_net != null" :class="(row.pnl_net ?? 0) >= 0 ? 'profit' : 'loss'">
                        {{ (row.pnl_net ?? 0).toFixed(2) }}
                      </span>
                      <span v-else class="muted">—</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <!-- 当前持仓（有持仓但无成交明细时） -->
              <div v-else-if="(summary.positions?.length ?? 0) > 0" class="trades-section">
                <h4>当前持仓（未平仓）</h4>
                <el-table :data="summary.positions" size="small" stripe max-height="200" class="trades-table">
                  <el-table-column prop="name" label="标的" width="90" />
                  <el-table-column prop="size" label="数量" width="80" align="right" />
                  <el-table-column prop="price" label="成本价" width="90" align="right">
                    <template #default="{ row }">{{ (row.price ?? 0).toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="value" label="市值" width="90" align="right">
                    <template #default="{ row }">{{ formatNumber(row.value ?? 0) }}</template>
                  </el-table-column>
                </el-table>
                <p class="positions-hint">策略有买入但未卖出，持仓市值变动计入总收益</p>
              </div>
              <!-- 交易盈亏（已平仓） -->
              <div v-else-if="(summary.trades?.length ?? 0) > 0" class="trades-section">
                <h4>交易盈亏</h4>
                <el-table :data="summary.trades" size="small" stripe max-height="280" class="trades-table">
                  <el-table-column prop="symbol" label="标的" width="90" />
                  <el-table-column prop="open_date" label="开仓日" width="100" />
                  <el-table-column prop="close_date" label="平仓日" width="100" />
                  <el-table-column prop="size" label="数量" width="70" align="right" />
                  <el-table-column prop="pnl_net" label="盈亏" width="90" align="right">
                    <template #default="{ row }">
                      <span :class="(row.pnl_net ?? 0) >= 0 ? 'profit' : 'loss'">
                        {{ (row.pnl_net ?? 0).toFixed(2) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="commission" label="手续费" width="80" align="right">
                    <template #default="{ row }">{{ (row.commission ?? 0).toFixed(2) }}</template>
                  </el-table-column>
                </el-table>
              </div>
              <div v-else-if="(summary.trade_count ?? 0) === 0" class="trades-empty">
                <el-empty description="本次回测无成交记录" :image-size="48" />
              </div>
            </div>
            <div class="step-actions">
              <el-button
                v-if="summary && !runError"
                type="warning"
                :loading="optimizing"
                @click="onOptimize"
              >
                {{ optimizing ? '优化中...' : '迭代优化' }}
              </el-button>
              <el-button v-if="currentSessionId" type="success" @click="openSaveDialog">保存策略</el-button>
              <el-button @click="startOver">新建回测</el-button>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 迭代优化结果弹窗 -->
      <el-dialog v-model="showOptimizationDialog" title="迭代优化结果" width="800px">
        <div v-if="optimizationResult" class="optimization-result">
          <!-- 优化总结 -->
          <div class="opt-section">
            <h4>优化总结</h4>
            <p class="opt-summary">{{ optimizationResult.optimization_summary || '优化完成' }}</p>
          </div>

          <!-- 最终评估 -->
          <div v-if="optimizationResult.final_evaluation" class="opt-section">
            <h4>最终评估</h4>
            <div class="eval-metrics">
              <div class="eval-item">
                <span class="label">评分</span>
                <el-tag :type="getScoreType(optimizationResult.final_evaluation.overall_score)" size="large">
                  {{ optimizationResult.final_evaluation.overall_score }}/100
                </el-tag>
              </div>
              <div class="eval-item">
                <span class="label">状态</span>
                <el-tag :type="optimizationResult.final_evaluation.is_satisfactory ? 'success' : 'warning'">
                  {{ optimizationResult.final_evaluation.is_satisfactory ? '满意' : '待改进' }}
                </el-tag>
              </div>
              <div class="eval-item">
                <span class="label">优先级</span>
                <el-tag :type="optimizationResult.final_evaluation.optimization_priority === 'high' ? 'danger' : 'info'">
                  {{ optimizationResult.final_evaluation.optimization_priority }}
                </el-tag>
              </div>
            </div>
            <!-- 问题列表 -->
            <div v-if="optimizationResult.final_evaluation.issues?.length" class="issues-list">
              <h5>发现的问题</h5>
              <div v-for="(issue, i) in optimizationResult.final_evaluation.issues" :key="i" class="issue-item">
                <el-tag :type="getSeverityType(issue.severity)" size="small">{{ issue.severity }}</el-tag>
                <span class="issue-desc">{{ issue.description }}</span>
                <div class="issue-suggestion">建议: {{ issue.suggestion }}</div>
              </div>
            </div>
          </div>

          <!-- 迭代历史 -->
          <div v-if="optimizationResult.iterations?.length" class="opt-section">
            <h4>迭代历史</h4>
            <el-table :data="optimizationResult.iterations" size="small" stripe>
              <el-table-column prop="iteration" label="迭代" width="70" align="center" />
              <el-table-column prop="score" label="评分" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="getScoreType(row.score)" size="small">{{ row.score }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="是否满意" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_satisfactory ? 'success' : 'warning'" size="small">
                    {{ row.is_satisfactory ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="已优化" width="80" align="center">
                <template #default="{ row }">{{ row.optimization_applied ? '✓' : '—' }}</template>
              </el-table-column>
              <el-table-column label="收益" width="100" align="right">
                <template #default="{ row }">
                  <span v-if="row.summary?.total_return != null" :class="row.summary.total_return >= 0 ? 'profit' : 'loss'">
                    {{ row.summary.total_return.toFixed(1) }}%
                  </span>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 系统日志和警告 -->
          <div v-if="optimizationResult.final_result?.warnings?.length" class="opt-section">
            <h4>⚠️ 系统警告</h4>
            <el-alert
              v-for="(warn, i) in optimizationResult.final_result.warnings"
              :key="i"
              type="warning"
              :title="warn"
              :closable="false"
              style="margin-bottom: 8px"
            />
          </div>
          <div v-if="optimizationResult.final_result?.logs?.length" class="opt-section">
            <h4>运行日志</h4>
            <ul class="logs-list">
              <li v-for="(log, i) in optimizationResult.final_result.logs" :key="i">{{ log }}</li>
            </ul>
          </div>
        </div>
        <template #footer>
          <el-button type="primary" @click="showOptimizationDialog = false">确定</el-button>
        </template>
      </el-dialog>

      <!-- 保存策略弹窗 -->
      <el-dialog v-model="saveNameDialogVisible" title="保存策略" width="400px" @close="saveNameInput = ''">
        <el-input
          v-model="saveNameInput"
          placeholder="输入策略名称，便于查找"
          maxlength="80"
          show-word-limit
          clearable
          @keyup.enter="confirmSave"
        />
        <template #footer>
          <el-button @click="saveNameDialogVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!saveNameInput.trim()" @click="confirmSave">保存</el-button>
        </template>
      </el-dialog>

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
              <div class="session-name">{{ sessionDisplayName(s) }}</div>
              <div class="session-meta">
                <span v-if="s.summary" class="session-return" :class="((s.summary as any)?.total_return ?? 0) >= 0 ? 'profit' : 'loss'">
                  收益 {{ ((s.summary as any)?.total_return ?? 0).toFixed(1) }}%
                </span>
                <span>{{ s.status }} · {{ formatDate(s.created_at) }}</span>
              </div>
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
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts } from '@element-plus/icons-vue'
import { backtestApi, type StrategyPython, type BacktestSummary, type OptimizationResult, type EvaluationResult } from '@/api/backtest'

const currentStep = ref(0)
const description = ref('')
const refinement = ref('')  // 用户补充/修改（在 AI 分析后）
const analysis = ref('')
const strategy = ref<StrategyPython | null>(null)
const configJson = ref('')
const configJsonError = computed(() => {
  if (!configJson.value.trim()) return ''
  try {
    JSON.parse(configJson.value)
    return ''
  } catch (e: any) {
    return '配置 JSON 格式错误: ' + (e?.message || String(e))
  }
})
const summary = ref<BacktestSummary | null>(null)
const runError = ref('')
const generateError = ref('')
const loading = ref(false)
const sessions = ref<Array<Record<string, unknown>>>([])
const activeTab = ref<'create' | 'library'>('create')
const currentSessionId = ref<string | null>(null)
const saveNameDialogVisible = ref(false)
const saveNameInput = ref('')
const strategyName = ref('')

// 迭代优化相关状态
const optimizing = ref(false)
const optimizationResult = ref<OptimizationResult | null>(null)
const showOptimizationDialog = ref(false)

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

watch(strategy, (s) => {
  if (s?.config) {
    configJson.value = JSON.stringify(s.config, null, 2)
  } else {
    configJson.value = ''
  }
}, { immediate: true })

const onGenerate = async () => {
  loading.value = true
  strategy.value = null
  configJson.value = ''
  generateError.value = ''
  try {
    const res = await backtestApi.generate(effectiveDescription())
    strategy.value = res.strategy
    if (res.strategy?.config) {
      configJson.value = JSON.stringify(res.strategy.config, null, 2)
    }
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
  if (configJsonError.value) return
  try {
    const parsed = JSON.parse(configJson.value || '{}')
    strategy.value = { ...strategy.value!, config: parsed }
  } catch {
    return
  }
  loading.value = true
  runError.value = ''
  summary.value = null
  try {
    const res = await backtestApi.run(strategy.value, {
      description: description.value,
      analysis: analysis.value,
      refinement: refinement.value,
      name: strategyName.value.trim() || undefined
    })
    if (res.success && res.summary) {
      summary.value = res.summary
      currentSessionId.value = res.session_id || null
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
  configJson.value = ''
  strategyName.value = ''
  summary.value = null
  runError.value = ''
  generateError.value = ''
  currentSessionId.value = null
}

const openSaveDialog = () => {
  saveNameInput.value = strategyName.value || (sessions.value.find(s => s.id === currentSessionId.value) as any)?.name || description.value.slice(0, 40) || ''
  saveNameDialogVisible.value = true
}

const confirmSave = async () => {
  const name = saveNameInput.value.trim()
  if (!name || !currentSessionId.value) return
  try {
    await backtestApi.updateSession(currentSessionId.value, name)
    saveNameDialogVisible.value = false
    loadSessions()
    ElMessage.success('策略已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

const loadSessions = async () => {
  try {
    sessions.value = await backtestApi.listSessions()
  } catch {
    sessions.value = []
  }
}

const selectSession = async (s: Record<string, unknown>) => {
  const sid = s.id as string
  if (!sid) return
  activeTab.value = 'create'
  currentSessionId.value = sid
  try {
    const full = await backtestApi.getSession(sid)
    const str = full.strategy as StrategyPython
    if (str && (str.code || str.config)) {
      strategy.value = str
      if (str.config) {
        configJson.value = JSON.stringify(str.config, null, 2)
      }
      description.value = (full.description as string) || (str as any).description || (str as any).name || ''
      strategyName.value = (full.name as string) || ''
      analysis.value = (full.analysis as string) || ''
      refinement.value = (full.refinement as string) || ''
      summary.value = (full.summary as BacktestSummary) || null
      summary.value ? (currentStep.value = 2) : (currentStep.value = 1)
    }
  } catch {
    // 降级：仅用 session 中的 strategy
    const str = s.strategy as StrategyPython
    if (str && (str.code || str.config)) {
      strategy.value = str
      if (str.config) configJson.value = JSON.stringify(str.config, null, 2)
      description.value = (s.description as string) || (str as any).description || (str as any).name || ''
      strategyName.value = (s.name as string) || ''
      analysis.value = (s.analysis as string) || ''
      refinement.value = ''
      summary.value = (s.summary as BacktestSummary) || null
      summary.value ? (currentStep.value = 2) : (currentStep.value = 1)
    }
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

const sessionDisplayName = (s: Record<string, unknown>) => {
  const name = (s.name as string) || ''
  if (name.trim()) return name.length > 50 ? name.slice(0, 50) + '…' : name
  const desc = (s.description as string) || ''
  if (desc.trim()) return desc.length > 50 ? desc.slice(0, 50) + '…' : desc
  const str = s.strategy as any
  return str?.name || (str?.code ? 'Python 策略' : '策略') || String(s.id || '').slice(0, 8)
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

/** 迭代优化策略 */
const onOptimize = async () => {
  if (!strategy.value || !description.value.trim()) {
    ElMessage.warning('缺少策略或描述信息')
    return
  }
  optimizing.value = true
  optimizationResult.value = null
  try {
    const result = await backtestApi.optimize(
      description.value,
      strategy.value,
      { maxIterations: 3, name: strategyName.value.trim() || undefined }
    )
    optimizationResult.value = result
    if (result.success) {
      // 更新当前策略和结果
      if (result.final_strategy) {
        strategy.value = result.final_strategy
        configJson.value = JSON.stringify(result.final_strategy.config || {}, null, 2)
      }
      if (result.final_result?.summary) {
        summary.value = result.final_result.summary
      }
      if (result.session_id) {
        currentSessionId.value = result.session_id
      }
      showOptimizationDialog.value = true
      loadSessions()
      ElMessage.success('迭代优化完成')
    } else {
      ElMessage.error(result.error || '优化失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '优化请求失败')
  } finally {
    optimizing.value = false
  }
}

/** 获取评分颜色 */
const getScoreType = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

/** 获取严重程度颜色 */
const getSeverityType = (severity: string) => {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}

onMounted(loadSessions)
watch(activeTab, (tab) => {
  if (tab === 'library') loadSessions()
})
</script>

<style scoped>
.backtest-page {
  padding: 16px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.library-card {
  margin-bottom: 0;
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
.code-textarea, .config-textarea {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}
.code-textarea { margin-bottom: 12px; }
.name-input { margin-bottom: 12px; }
.optional { font-weight: normal; color: var(--el-text-color-secondary); font-size: 12px; }
.config-textarea { margin-bottom: 8px; }
.config-error {
  color: var(--el-color-danger);
  font-size: 12px;
  margin-bottom: 8px;
}
.error-block { margin-bottom: 16px; }
.result-summary h4 { margin: 0 0 12px 0; font-size: 14px; }
.trades-section { margin-top: 16px; }
.trades-section h4 { margin: 0 0 8px 0; font-size: 13px; }
.trades-table { font-size: 12px; }
.trades-empty { margin-top: 16px; }
.positions-hint { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 8px; }
/* 中国习惯：正数（盈利）红色，负数（亏损）绿色 */
.profit { color: var(--el-color-danger); }
.loss { color: var(--el-color-success); }
.muted { color: var(--el-text-color-placeholder); }
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
.session-meta .session-return { margin-right: 6px; font-weight: 500; }

/* 迭代优化结果样式 */
.optimization-result {
  max-height: 60vh;
  overflow-y: auto;
}
.opt-section {
  margin-bottom: 20px;
}
.opt-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.opt-section h5 {
  margin: 8px 0;
  font-size: 13px;
  font-weight: 500;
}
.opt-summary {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 13px;
  white-space: pre-wrap;
}
.eval-metrics {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}
.eval-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.eval-item .label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.issues-list {
  margin-top: 12px;
}
.issue-item {
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
.issue-desc {
  margin-left: 8px;
  font-size: 13px;
}
.issue-suggestion {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  padding-left: 50px;
}
.logs-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.logs-list li {
  margin-bottom: 4px;
}
</style>
