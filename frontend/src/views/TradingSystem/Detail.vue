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
          <el-tag v-if="system.is_active" type="success" size="small">激活</el-tag>
        </h1>
      </div>
      <div class="header-right" v-if="system">
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
          激活此系统
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
    <el-empty v-if="!store.loading && !system" description="交易系统不存在">
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  Flag
} from '@element-plus/icons-vue'
import { useTradingSystemStore } from '@/stores/tradingSystem'
import RuleDisplay from './components/RuleDisplay.vue'

const route = useRoute()
const router = useRouter()
const store = useTradingSystemStore()

const systemId = computed(() => route.params.id as string)
const system = computed(() => store.currentSystem)

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
</style>

