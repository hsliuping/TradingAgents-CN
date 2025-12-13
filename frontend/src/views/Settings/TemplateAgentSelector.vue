<template>
  <div class="ta-selector">
    <el-card class="ta-hero">
      <div class="ta-title">选择要管理的 Agent 类型</div>
      <div class="ta-sub">先按类型进入，再管理该类型下的提示词模板，保持清晰与高效。</div>
    </el-card>
    <el-row :gutter="16" class="ta-grid">
      <el-col v-for="item in cards" :key="item.type" :xs="24" :sm="12" :md="8">
        <el-card class="ta-card">
          <div class="ta-card-title">{{ item.cn }} <span class="ta-en">{{ item.type }}</span></div>
          <div class="ta-desc">{{ item.desc }}</div>
          <div class="ta-examples">典型Agent：{{ item.examples.join('、') }}</div>
          <div class="ta-stats">
            <el-tag type="info">系统模板：{{ stats[item.type]?.system ?? '—' }}</el-tag>
            <el-tag type="success" style="margin-left:8px">我的模板：{{ stats[item.type]?.user ?? '—' }}</el-tag>
          </div>
          <div class="ta-actions">
            <el-button type="primary" @click="goManage(item.type)">管理该类型模板</el-button>
            <el-button @click="goManage(item.type, true)">仅系统</el-button>
            <el-button @click="goManage(item.type, false)">仅我的</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { TemplatesApi } from '@/api/templates'
import { ElMessage } from 'element-plus'

const router = useRouter()

const cards = [
  { type: 'analysts', cn: '分析师', desc: '市场、基本面、新闻、社媒等分析任务的提示词模板', examples: ['市场分析师','基本面分析师','新闻分析师','社媒分析师'] },
  { type: 'researchers', cn: '研究员', desc: '研究观点与报告撰写的提示词模板', examples: ['看涨研究员','看跌研究员'] },
  { type: 'debators', cn: '辩手', desc: '多观点对辩与决策支持的提示词模板', examples: ['激进辩手','保守辩手','中性辩手'] },
  { type: 'managers', cn: '管理者', desc: '研究/风险管理流程的提示词模板', examples: ['研究管理者','风险管理者'] },
  { type: 'trader', cn: '交易员', desc: '交易执行与复盘的提示词模板', examples: ['交易员'] },
  { type: 'reviewers', cn: '复盘分析师', desc: '交易复盘与多维度分析的提示词模板', examples: ['时机分析师','仓位分析师','情绪分析师','归因分析师','复盘总结师'] }
]

const stats: Record<string, { system: number; user: number } | undefined> = reactive({})

const fetchCounts = async () => {
  try {
    for (const c of cards) {
      const [sys, user] = await Promise.all([
        TemplatesApi.list({ agent_type: c.type, is_system: true, limit: 1, skip: 0 }),
        TemplatesApi.list({ agent_type: c.type, is_system: false, limit: 1, skip: 0 })
      ])

      const sysTotal = (sys.data && typeof (sys.data as any).total === 'number')
        ? (sys.data as any).total
        : Array.isArray((sys.data as any).items)
          ? (sys.data as any).items.length
          : (Array.isArray(sys.data) ? (sys.data as any).length : 0)

      const userTotal = (user.data && typeof (user.data as any).total === 'number')
        ? (user.data as any).total
        : Array.isArray((user.data as any).items)
          ? (user.data as any).items.length
          : (Array.isArray(user.data) ? (user.data as any).length : 0)

      stats[c.type] = { system: sysTotal, user: userTotal }
    }
  } catch (e: any) {
    ElMessage.warning(e?.message || '统计加载失败')
  }
}

const goManage = (type: string, isSystem?: boolean) => {
  const query: any = { agent_type: type }
  if (typeof isSystem === 'boolean') query.is_system = isSystem
  router.push({ path: '/settings/templates/manage', query })
}

onMounted(fetchCounts)
</script>

<style scoped>
.ta-selector { padding: 16px }
.ta-hero { margin-bottom: 12px }
.ta-title { font-size: 20px; font-weight: 600 }
.ta-sub { color: #666; margin-top: 6px }
.ta-card { margin-bottom: 16px }
.ta-card-title { font-size: 16px; font-weight: 600 }
.ta-en { color: #999; margin-left: 6px }
.ta-desc { margin-top: 6px; color: #666 }
.ta-examples { margin-top: 6px; color: #666 }
.ta-stats { margin-top: 8px }
.ta-actions { margin-top: 12px }
</style>
