<template>
  <div class="trading-system-detail" v-loading="store.loading">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <h1 v-if="system">
          {{ system.name }}
          <el-tag v-if="system.is_active" type="success" size="small">默认</el-tag>
        </h1>
      </div>
      <div class="header-right" v-if="system">
        <el-button @click="showEvaluationHistory">
          <el-icon><Clock /></el-icon>
          评估历史
        </el-button>
        <el-button type="primary" @click="handleEvaluate" :loading="evaluating">
          <el-icon><DocumentChecked /></el-icon>
          AI评估
        </el-button>
        <el-button @click="handleEdit">
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
        <el-button
          v-if="!system.is_active"
          type="success"
          @click="handleActivate"
        >
          <el-icon><Check /></el-icon>
          设为默认
        </el-button>
      </div>
    </div>

    <!-- 基本信息 -->
    <el-card v-if="system" class="info-card">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="系统名称">{{ system.name }}</el-descriptions-item>
        <el-descriptions-item label="交易风格">
          <el-tag :type="getStyleType(system.style)">{{ getStyleLabel(system.style) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="风险偏好">
          <el-tag :type="getRiskType(system.risk_profile)">{{ getRiskLabel(system.risk_profile) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="3">
          {{ system.description || '暂无描述' }}
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{ system.version }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(system.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(system.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 规则模块 -->
    <div v-if="system" class="rules-section">
      <!-- 选股规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Search /></el-icon>
            <span>选股规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.stock_selection" type="stock_selection" />
      </el-card>

      <!-- 择时规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Timer /></el-icon>
            <span>择时规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.timing" type="timing" />
      </el-card>

      <!-- 仓位规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><DataAnalysis /></el-icon>
            <span>仓位规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.position" type="position" />
      </el-card>

      <!-- 持仓规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Briefcase /></el-icon>
            <span>持仓规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.holding" type="holding" />
      </el-card>

      <!-- 风险管理规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Warning /></el-icon>
            <span>风险管理规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.risk_management" type="risk_management" />
      </el-card>

      <!-- 复盘规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Document /></el-icon>
            <span>复盘规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.review" type="review" />
      </el-card>

      <!-- 纪律规则 -->
      <el-card class="rule-card">
        <template #header>
          <div class="card-header">
            <el-icon><Flag /></el-icon>
            <span>纪律规则</span>
          </div>
        </template>
        <RuleDisplay :rule="system.discipline" type="discipline" />
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty v-if="!store.loading && !system" description="交易计划不存在">
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>

    <!-- AI评估结果对话框 -->
    <el-dialog
      v-model="evaluationDialogVisible"
      title="AI评估结果"
      width="800px"
      :close-on-click-modal="false"
    >
      <!-- 加载状态 -->
      <div v-if="evaluating && !evaluationResult" class="evaluation-loading">
        <div class="loading-animation">
          <div class="loading-spinner">
            <el-icon class="spinning"><Loading /></el-icon>
          </div>
          <div class="loading-text">
            <h3>AI正在分析您的交易计划...</h3>
            <p>请稍候，这可能需要几秒钟时间</p>
          </div>
          <div class="loading-steps">
            <div class="step-item" :class="{ active: true }">
              <el-icon><Document /></el-icon>
              <span>解析交易计划</span>
            </div>
            <div class="step-item" :class="{ active: true }">
              <el-icon><DataAnalysis /></el-icon>
              <span>多维度评估</span>
            </div>
            <div class="step-item" :class="{ active: true }">
              <el-icon><DocumentChecked /></el-icon>
              <span>生成评估报告</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 评估结果 -->
      <div v-else-if="evaluationResult" class="evaluation-content">
        <!-- 总体评分 -->
        <div class="score-section">
          <div class="score-circle">
            <div class="score-value">{{ evaluationResult.overall_score }}</div>
            <div class="score-label">综合评分</div>
          </div>
          <div class="score-level">
            <el-tag 
              :type="getScoreTagType(evaluationResult.overall_score)" 
              size="large"
            >
              {{ getScoreLevel(evaluationResult.overall_score) }}
            </el-tag>
          </div>
        </div>

        <!-- 优点 -->
        <el-card class="evaluation-card" shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><CircleCheck /></el-icon>
              <span>优点</span>
            </div>
          </template>
          <ul class="evaluation-list">
            <li v-for="(strength, index) in evaluationResult.strengths" :key="index">
              {{ strength }}
            </li>
            <li v-if="evaluationResult.strengths.length === 0" class="empty-item">暂无</li>
          </ul>
        </el-card>

        <!-- 缺点 -->
        <el-card class="evaluation-card" shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><WarningFilled /></el-icon>
              <span>需要改进</span>
            </div>
          </template>
          <ul class="evaluation-list">
            <li v-for="(weakness, index) in evaluationResult.weaknesses" :key="index">
              {{ weakness }}
            </li>
            <li v-if="evaluationResult.weaknesses.length === 0" class="empty-item">暂无</li>
          </ul>
        </el-card>

        <!-- 改进建议 -->
        <el-card class="evaluation-card" shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon><Pointer /></el-icon>
              <span>改进建议</span>
            </div>
          </template>
          <ul class="evaluation-list">
            <li v-for="(suggestion, index) in evaluationResult.suggestions" :key="index">
              {{ suggestion }}
            </li>
            <li v-if="evaluationResult.suggestions.length === 0" class="empty-item">暂无</li>
          </ul>
        </el-card>

        <!-- 详细分析 -->
        <el-card class="evaluation-card" shadow="never" v-if="evaluationResult.detailed_analysis">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>详细分析</span>
            </div>
          </template>
          <div class="detailed-analysis">
            <pre>{{ evaluationResult.detailed_analysis }}</pre>
          </div>
        </el-card>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="!evaluating && !evaluationResult" class="evaluation-error">
        <el-empty description="评估失败，请重试">
          <el-button type="primary" @click="handleEvaluate">重新评估</el-button>
        </el-empty>
      </div>
      
      <template #footer>
        <el-button v-if="!evaluating" @click="evaluationDialogVisible = false">关闭</el-button>
        <el-button v-if="evaluating" disabled>评估中...</el-button>
      </template>
    </el-dialog>

    <!-- 评估历史记录对话框 -->
    <el-dialog
      v-model="historyDialogVisible"
      title="AI评估历史记录"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-loading="loadingHistory" class="evaluation-history">
        <el-table :data="evaluationHistory" stripe>
          <el-table-column prop="created_at" label="评估时间" width="180">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="overall_score" label="评分" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getScoreTagType(row.overall_score)" size="large">
                {{ row.overall_score }}分
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="grade" label="等级" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getScoreTagType(row.overall_score)" size="small">
                {{ row.grade }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="summary" label="评估摘要" min-width="300">
            <template #default="{ row }">
              <div class="summary-text">{{ row.summary }}</div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewHistoryDetail(row.evaluation_id)">
                查看详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container" v-if="historyTotal > 0">
          <el-pagination
            v-model:current-page="historyPage"
            v-model:page-size="historyPageSize"
            :total="historyTotal"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadEvaluationHistory"
            @current-change="loadEvaluationHistory"
          />
        </div>

        <el-empty v-if="!loadingHistory && evaluationHistory.length === 0" description="暂无评估记录" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft, 
  Edit, 
  Check, 
  Search, 
  Timer, 
  DataAnalysis, 
  Briefcase, 
  Warning, 
  Document, 
  Flag, 
  DocumentChecked,
  CircleCheck,
  WarningFilled,
  Pointer,
  Loading,
  Clock
} from '@element-plus/icons-vue'
import { useTradingSystemStore } from '@/stores/tradingSystem'
import { 
  evaluateTradingSystem, 
  getEvaluationHistory,
  getEvaluationDetail,
  type TradingPlanEvaluation,
  type EvaluationHistoryItem
} from '@/api/tradingSystem'
import RuleDisplay from './components/RuleDisplay.vue'

const route = useRoute()
const router = useRouter()
const store = useTradingSystemStore()

const systemId = computed(() => route.params.id as string)
const system = computed(() => store.currentSystem)
const evaluating = ref(false)
const evaluationResult = ref<TradingPlanEvaluation | null>(null)
const evaluationDialogVisible = ref(false)

// 评估历史相关
const historyDialogVisible = ref(false)
const loadingHistory = ref(false)
const evaluationHistory = ref<EvaluationHistoryItem[]>([])
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)

// 生命周期
onMounted(() => {
  if (systemId.value) {
    store.fetchSystem(systemId.value)
  }
})

// 方法
function goBack() {
  router.push('/trading-system')
}

function handleEdit() {
  router.push(`/trading-system/${systemId.value}/edit`)
}

async function handleActivate() {
  if (systemId.value) {
    await store.activateSystem(systemId.value)
  }
}

async function handleEvaluate() {
  if (!systemId.value) return
  
  evaluating.value = true
  evaluationDialogVisible.value = true
  evaluationResult.value = null // 清空上次结果
  try {
    const res = await evaluateTradingSystem(systemId.value)
    console.log('评估响应:', res)
    if (res.success && res.data?.evaluation) {
      evaluationResult.value = res.data.evaluation
      ElMessage.success('交易计划AI评估成功！')
    } else {
      ElMessage.error(res.message || '评估失败')
    }
  } catch (error: any) {
    console.error('评估交易计划失败:', error)
    ElMessage.error(error.response?.data?.message || error.message || '评估失败，请稍后重试')
  } finally {
    evaluating.value = false
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

function formatDateTime(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

function getScoreTagType(score: number): string {
  if (score >= 90) return 'success'
  if (score >= 80) return 'primary'
  if (score >= 70) return 'warning'
  if (score >= 60) return 'info'
  return 'danger'
}

function getScoreLevel(score: number): string {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '中等'
  if (score >= 60) return '及格'
  return '不及格'
}

// 评估历史相关函数
async function showEvaluationHistory() {
  historyDialogVisible.value = true
  historyPage.value = 1
  await loadEvaluationHistory()
}

async function loadEvaluationHistory() {
  if (!systemId.value) return
  
  loadingHistory.value = true
  try {
    const res = await getEvaluationHistory(systemId.value, historyPage.value, historyPageSize.value)
    if (res.success && res.data) {
      evaluationHistory.value = res.data.items || []
      historyTotal.value = res.data.total || 0
    } else {
      ElMessage.error(res.message || '获取评估历史失败')
    }
  } catch (error: any) {
    console.error('获取评估历史失败:', error)
    ElMessage.error(error.message || '获取评估历史失败')
  } finally {
    loadingHistory.value = false
  }
}

async function viewHistoryDetail(evaluationId: string) {
  try {
    const res = await getEvaluationDetail(evaluationId)
    if (res.success && res.data?.evaluation) {
      const evalData = res.data.evaluation.evaluation_result
      evaluationResult.value = evalData
      evaluationDialogVisible.value = true
      historyDialogVisible.value = false
    } else {
      ElMessage.error(res.message || '获取评估详情失败')
    }
  } catch (error: any) {
    console.error('获取评估详情失败:', error)
    ElMessage.error(error.message || '获取评估详情失败')
  }
}
</script>

<style scoped lang="scss">
.trading-system-detail {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
  }
}

.info-card {
  margin-bottom: 24px;
}

.rules-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
}

.rule-card {
  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evaluation-loading {
  padding: 40px 20px;
  text-align: center;

  .loading-animation {
    .loading-spinner {
      margin-bottom: 24px;

      .spinning {
        font-size: 64px;
        color: var(--el-color-primary);
        animation: spin 1s linear infinite;
      }
    }

    .loading-text {
      margin-bottom: 32px;

      h3 {
        margin: 0 0 8px 0;
        font-size: 18px;
        color: var(--el-text-color-primary);
      }

      p {
        margin: 0;
        font-size: 14px;
        color: var(--el-text-color-secondary);
      }
    }

    .loading-steps {
      display: flex;
      justify-content: center;
      gap: 32px;
      margin-top: 32px;

      .step-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        opacity: 0.3;
        transition: opacity 0.3s;

        &.active {
          opacity: 1;
        }

        .el-icon {
          font-size: 24px;
          color: var(--el-color-primary);
        }

        span {
          font-size: 13px;
          color: var(--el-text-color-regular);
        }
      }
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.evaluation-error {
  padding: 40px 20px;
}

.evaluation-content {
  .score-section {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 24px;
    margin-bottom: 24px;
    padding: 24px;
    background: var(--el-fill-color-light);
    border-radius: 8px;

    .score-circle {
      text-align: center;

      .score-value {
        font-size: 48px;
        font-weight: bold;
        color: var(--el-color-primary);
        line-height: 1;
      }

      .score-label {
        margin-top: 8px;
        font-size: 14px;
        color: var(--el-text-color-secondary);
      }
    }
  }

  .evaluation-card {
    margin-bottom: 16px;

    .evaluation-list {
      margin: 0;
      padding-left: 20px;
      list-style-type: disc;

      li {
        margin-bottom: 8px;
        line-height: 1.6;
        color: var(--el-text-color-regular);

        &.empty-item {
          color: var(--el-text-color-placeholder);
          list-style-type: none;
          padding-left: 0;
        }
      }
    }

    .detailed-analysis {
      pre {
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: inherit;
        line-height: 1.6;
        color: var(--el-text-color-regular);
        margin: 0;
      }
    }
  }
}

.evaluation-history {
  .summary-text {
    max-height: 60px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.5;
    color: var(--el-text-color-regular);
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

