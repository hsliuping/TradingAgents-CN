<template>
  <div class="report-detail">
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="report" class="report-content">
      <el-card class="report-header" shadow="never">
        <div class="header-content">
          <div class="title-section">
            <h1 class="report-title">
              <el-icon><Document /></el-icon>
              {{ report.stock_name || report.stock_symbol }} 研究报告
            </h1>
            <div class="report-meta">
              <el-tag type="primary">{{ report.stock_symbol }}</el-tag>
              <el-tag v-if="report.stock_name && report.stock_name !== report.stock_symbol" type="info">{{ report.stock_name }}</el-tag>
              <el-tag type="success">{{ getStatusText(report.status) }}</el-tag>
              <span class="meta-item">
                <el-icon><Calendar /></el-icon>
                {{ formatTime(report.created_at) }}
              </span>
              <span class="meta-item">
                <el-icon><User /></el-icon>
                {{ formatAnalysts(report.analysts) }}
              </span>
              <span v-if="report.model_info && report.model_info !== 'Unknown'" class="meta-item">
                <el-icon><Cpu /></el-icon>
                <el-tooltip :content="getModelDescription(report.model_info)" placement="top">
                  <el-tag type="info" style="cursor: help;">{{ report.model_info }}</el-tag>
                </el-tooltip>
              </span>
              <span v-if="report.research_depth" class="meta-item">
                <el-icon><DataAnalysis /></el-icon>
                <el-tooltip :content="getResearchDepthDescription(report.research_depth)" placement="top">
                  <el-tag type="warning" style="cursor: help;">深度: {{ report.research_depth }}</el-tag>
                </el-tooltip>
              </span>
            </div>
          </div>

          <div class="action-section">
            <el-dropdown trigger="click" @command="downloadReport">
              <el-button type="primary">
                <el-icon><Download /></el-icon>
                下载报告
                <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="markdown">
                    <el-icon><document /></el-icon> Markdown
                  </el-dropdown-item>
                  <el-dropdown-item command="docx">
                    <el-icon><document /></el-icon> Word 文档
                  </el-dropdown-item>
                  <el-dropdown-item command="pdf">
                    <el-icon><document /></el-icon> PDF
                  </el-dropdown-item>
                  <el-dropdown-item command="json" divided>
                    <el-icon><document /></el-icon> JSON (原始数据)
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button @click="goBack">
              <el-icon><Back /></el-icon>
              返回
            </el-button>
          </div>
        </div>
      </el-card>

      <div class="risk-disclaimer">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>
            <div class="disclaimer-content">
              <el-icon class="disclaimer-icon"><WarningFilled /></el-icon>
              <div class="disclaimer-text">
                <p style="margin: 0 0 8px 0;"><strong>⚠️ 重要风险提示与免责声明</strong></p>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                  <li><strong>平台性质：</strong>本页面仅展示研究辅助结果与公开信息整理，不提供个股交易建议。</li>
                  <li><strong>分析目的：</strong>所有内容仅用于研究、复盘与风险识别，不作为买卖依据。</li>
                  <li><strong>数据局限性：</strong>分析基于历史数据与公开信息，可能存在延迟、不完整或不准确。</li>
                  <li><strong>独立决策：</strong>请结合自身风险承受能力与投资目标独立判断。</li>
                </ul>
              </div>
            </div>
          </template>
        </el-alert>
      </div>

      <el-card class="metrics-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><TrendCharts /></el-icon>
            <span>关键指标</span>
          </div>
        </template>
        <div class="metrics-content">
          <el-row :gutter="24">
            <el-col :span="8">
              <div class="metric-item">
                <div class="metric-label">
                  <el-icon><TrendCharts /></el-icon>
                  研究概览
                  <el-tooltip content="仅展示研究摘要与公开信息整理，不提供方向性交易结论" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value recommendation-value">
                  <div class="core-conclusion">
                    {{ getResearchOverview() }}
                  </div>
                </div>
                <el-tag type="info" size="small" style="margin-top: 8px;">研究辅助</el-tag>
              </div>
            </el-col>

            <el-col :span="8">
              <div class="metric-item">
                <div class="metric-label">
                  <el-icon><Warning /></el-icon>
                  风险关注
                  <el-tooltip content="仅展示研究过程识别到的风险关注点，不展示风险评级" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value recommendation-value">
                  <div class="core-conclusion">
                    {{ getRiskFocus() }}
                  </div>
                </div>
                <el-tag type="warning" size="small" style="margin-top: 8px;">需自行判断</el-tag>
              </div>
            </el-col>

            <el-col :span="8">
              <div class="metric-item">
                <div class="metric-label">
                  <el-icon><DataAnalysis /></el-icon>
                  报告覆盖
                  <el-tooltip content="展示本页已保留的研究模块与分析师信息，不展示模型打分" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value recommendation-value">
                  <div class="core-conclusion">
                    <strong>已展示模块：</strong>{{ orderedModuleNames.length }} 个
                    <br>
                    <strong>参与分析：</strong>{{ formatAnalysts(report.analysts || []) || '未提供' }}
                  </div>
                </div>
                <el-tag type="success" size="small" style="margin-top: 8px;">公开信息整理</el-tag>
              </div>
            </el-col>
          </el-row>

          <div v-if="report.key_points && report.key_points.length > 0" class="key-points">
            <h4>
              <el-icon><List /></el-icon>
              关键要点
            </h4>
            <ul>
              <li v-for="(point, index) in report.key_points" :key="index">
                <el-icon class="point-icon"><Check /></el-icon>
                {{ formatKeyPoint(point) }}
              </li>
            </ul>
          </div>
        </div>
      </el-card>

      <el-card v-if="report.summary" class="summary-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>研究摘要</span>
          </div>
        </template>
        <div class="summary-content markdown-content" v-html="renderMarkdown(report.summary)"></div>
      </el-card>

      <el-card class="modules-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Files /></el-icon>
            <span>研究模块</span>
          </div>
        </template>

        <el-tabs v-model="activeModule" type="border-card">
          <el-tab-pane
            v-for="moduleName in orderedModuleNames"
            :key="moduleName"
            :label="getModuleDisplayName(moduleName)"
            :name="moduleName"
          >
            <div class="module-content">
              <div v-if="getModuleContent(report.reports[moduleName])" class="markdown-content">
                <div v-html="renderMarkdown(getModuleContent(report.reports[moduleName]))"></div>
              </div>
              <div v-else class="json-content">
                <pre>{{ JSON.stringify(report.reports[moduleName], null, 2) }}</pre>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>

    <div v-else class="error-container">
      <el-result icon="error" title="报告加载失败" sub-title="请检查报告ID是否正确或稍后重试">
        <template #extra>
          <el-button type="primary" @click="goBack">返回列表</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElInput, ElForm, ElFormItem } from 'element-plus'
import { configApi, type LLMConfig } from '@/api/config'
import {
  Document,
  Calendar,
  User,
  Download,
  Back,
  InfoFilled,
  TrendCharts,
  Files,
  WarningFilled,
  DataAnalysis,
  Warning,
  List,
  Check,
  Cpu,
  QuestionFilled,
  ArrowDown
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { marked } from 'marked'

// 路由和认证
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 配置 marked 以获得更完整的 Markdown 支持
marked.setOptions({ breaks: true, gfm: true })

// 响应式数据
const loading = ref(true)
const report = ref(null)
const activeModule = ref('')
const llmConfigs = ref<LLMConfig[]>([]) // 存储所有模型配置

// 获取模型配置列表
const fetchLLMConfigs = async () => {
  try {
    const response = await configApi.getSystemConfig()
    if (response.success && response.data?.llm_configs) {
      llmConfigs.value = response.data.llm_configs
    }
  } catch (error) {
    console.error('获取模型配置失败:', error)
  }
}

// 获取报告详情
const fetchReportDetail = async () => {
  loading.value = true
  try {
    const reportId = route.params.id as string

    const response = await fetch(`/api/reports/${reportId}/detail`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const result = await response.json()

    if (result.success) {
      report.value = result.data

      // 设置默认激活的模块（使用有序列表的第一个）
      // 注意：这里不能直接使用 orderedModuleNames，因为它是计算属性
      // 需要手动计算第一个模块
      const reports = result.data.reports || {}
      const availableModules = Object.keys(reports)

      // 按照 moduleOrder 找到第一个存在的模块
      const firstModule = moduleOrder.find(name => availableModules.includes(name))
      if (firstModule) {
        activeModule.value = firstModule
      } else if (availableModules.length > 0) {
        // 如果没有匹配的，使用第一个可用的
        activeModule.value = availableModules[0]
      }
    } else {
      throw new Error(result.message || '获取报告详情失败')
    }
  } catch (error) {
    console.error('获取报告详情失败:', error)
    ElMessage.error('获取报告详情失败')
  } finally {
    loading.value = false
  }
}

// 下载报告
const downloadReport = async (format: string = 'markdown') => {
  try {
    // 显示加载提示
    const loadingMsg = ElMessage({
      message: `正在生成${getFormatName(format)}格式报告...`,
      type: 'info',
      duration: 0
    })

    const response = await fetch(`/api/reports/${report.value.id}/download?format=${format}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    loadingMsg.close()

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || `HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url

    // 根据格式设置文件扩展名
    const ext = getFileExtension(format)
    // 清理股票名称中的特殊字符（用于文件名）
    const cleanStockName = (report.value.stock_name || '')
      .replace(/[\/\\:*?"<>|]/g, '') // 移除文件名不允许的字符
      .replace(/\s+/g, '_') // 空格替换为下划线
      .trim()
    // 构建文件名：股票代码_股票名称_研究报告_日期
    const fileName = cleanStockName
      ? `${report.value.stock_symbol}_${cleanStockName}_研究报告_${report.value.analysis_date}.${ext}`
      : `${report.value.stock_symbol}_研究报告_${report.value.analysis_date}.${ext}`
    a.download = fileName

    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    ElMessage.success(`${getFormatName(format)}报告下载成功`)
  } catch (error: any) {
    console.error('下载报告失败:', error)

    // 显示详细错误信息
    if (error.message && error.message.includes('pandoc')) {
      ElMessage.error({
        message: 'Word 导出需要安装 pandoc 工具（PDF 导出不需要 pandoc）',
        duration: 5000
      })
    } else if (error.message && (error.message.includes('weasyprint') || error.message.includes('pdfkit'))) {
      ElMessage.error({
        message: 'PDF 导出需要安装 PDF 引擎：pip install weasyprint（推荐）',
        duration: 5000
      })
    } else {
      ElMessage.error(`下载报告失败: ${error.message || '未知错误'}`)
    }
  }
}

// 辅助函数：获取格式名称
const getFormatName = (format: string): string => {
  const names: Record<string, string> = {
    'markdown': 'Markdown',
    'docx': 'Word',
    'pdf': 'PDF',
    'json': 'JSON'
  }
  return names[format] || format
}

// 辅助函数：获取文件扩展名
const getFileExtension = (format: string): string => {
  const extensions: Record<string, string> = {
    'markdown': 'md',
    'docx': 'docx',
    'pdf': 'pdf',
    'json': 'json'
  }
  return extensions[format] || 'txt'
}

const goBack = () => {
  router.push('/reports')
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: '已完成',
    processing: '生成中',
    failed: '失败'
  }
  return statusMap[status] || status
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 将分析师英文名称转换为中文
const formatAnalysts = (analysts: string[]) => {
  const analystNameMap: Record<string, string> = {
    // 宏观分析师
    'index_analyst': '大盘环境分析师',
    'sector_analyst': '行业板块研究分析师',
    
    // 分析师团队
    'market_analyst': '市场技术分析师',
    'fundamentals_analyst': '基本面分析师',
    'news_analyst': '新闻研究分析师',
    'sentiment_analyst': '情绪研究分析师',
    
    // 研究团队
    'bull_researcher': '乐观情景研究员',
    'bear_researcher': '审慎情景研究员',
    
    // 风险管理团队
    'risky_analyst': '高弹性情景分析师',
    'safe_analyst': '防御情景分析师',
    'neutral_analyst': '基准情景分析师',
    
    // 兼容旧格式（不带_analyst后缀）
    'market': '市场分析师',
    'fundamentals': '基本面分析师',
    'news': '新闻研究分析师',
    'social': '社交媒体研究分析师',
    'sentiment': '情绪研究分析师',
    'technical': '技术分析师'
  }

  return analysts.map(analyst => analystNameMap[analyst] || analyst).join('、')
}

// 获取模型的详细描述（从后端配置中获取）
const getModelDescription = (modelInfo: string) => {
  if (!modelInfo || modelInfo === 'Unknown') {
    return '未知模型'
  }

  // 1. 优先从后端配置中查找精确匹配
  const config = llmConfigs.value.find(c => c.model_name === modelInfo)
  if (config?.description) {
    return config.description
  }

  // 2. 尝试模糊匹配（处理版本号等变化）
  const fuzzyConfig = llmConfigs.value.find(c =>
    modelInfo.toLowerCase().includes(c.model_name.toLowerCase()) ||
    c.model_name.toLowerCase().includes(modelInfo.toLowerCase())
  )
  if (fuzzyConfig?.description) {
    return fuzzyConfig.description
  }

  // 3. 根据模型名称前缀提供通用描述
  const modelLower = modelInfo.toLowerCase()
  if (modelLower.includes('gpt')) {
    return `OpenAI ${modelInfo} - 强大的语言模型`
  } else if (modelLower.includes('claude')) {
    return `Anthropic ${modelInfo} - 高性能推理模型`
  } else if (modelLower.includes('qwen')) {
    return `阿里通义千问 ${modelInfo} - 中文优化模型`
  } else if (modelLower.includes('glm')) {
    return `智谱 ${modelInfo} - 综合性能优秀`
  } else if (modelLower.includes('deepseek')) {
    return `DeepSeek ${modelInfo} - 高性价比模型`
  } else if (modelLower.includes('ernie')) {
    return `百度文心 ${modelInfo} - 中文能力强`
  } else if (modelLower.includes('spark')) {
    return `讯飞星火 ${modelInfo} - 专业模型`
  } else if (modelLower.includes('moonshot')) {
    return `Moonshot ${modelInfo} - 长上下文模型`
  } else if (modelLower.includes('yi')) {
    return `零一万物 ${modelInfo} - 高性能模型`
  }

  // 4. 默认返回
  return `${modelInfo} - AI 大语言模型`
}

// 定义报告模块的展示顺序（按照分析流程顺序）
const moduleOrder = [
  // 第一阶段：宏观分析（2个）
  'index_report',
  'sector_report',

  // 第二阶段：分析师团队（4个）
  'market_report',
  'fundamentals_report',
  'sentiment_report',
  'news_report',

  // 第三阶段：研究与辩论过程
  'bull_researcher',
  'bull_report',
  'bear_researcher',
  'bear_report',
  'research_team_decision',
  'investment_plan',
  'trader_investment_plan',

  // 第四阶段：风险过程
  'risky_analyst',
  'risky_opinion',
  'safe_analyst',
  'safe_opinion',
  'neutral_analyst',
  'neutral_opinion',
  'risk_management_decision',
  'risk_assessment',
  'final_trade_decision',
  'investment_debate_state',
  'risk_debate_state',
  'detailed_analysis'
]

// 计算属性：按顺序返回存在的报告模块
const orderedModuleNames = computed(() => {
  if (!report.value?.reports) return []

  const availableModules = Object.keys(report.value.reports)

  // 按照 moduleOrder 的顺序过滤出存在的模块
  const ordered = moduleOrder.filter(name => availableModules.includes(name))

  const remaining = availableModules.filter(name => !moduleOrder.includes(name))

  return [...ordered, ...remaining]
})

const getModuleDisplayName = (moduleName: string) => {
  // 历史报告详情页保留完整模块展示，便于核查旧数据
  const nameMap: Record<string, string> = {
    // 🆕 宏观分析师团队 (2个) - 优先显示
    index_report: '📊 大盘环境研究',
    sector_report: '🏭 行业板块研究',

    // 分析师团队 (4个)
    market_report: '📈 市场技术研究',
    sentiment_report: '💭 情绪研究',
    news_report: '📰 新闻研究',
    fundamentals_report: '💰 基本面研究',
    bull_researcher: '🌤️ 乐观情景研究员',
    bull_report: '🌤️ 乐观情景论证',
    bear_researcher: '🌧️ 审慎情景研究员',
    bear_report: '🌧️ 审慎情景论证',
    research_team_decision: '🔬 研究结论汇总',
    investment_plan: '📋 研究经理简报',
    trader_investment_plan: '🧩 用户版研究简报',
    risky_analyst: '⚡ 高弹性情景分析师',
    risky_opinion: '⚡ 高弹性情景审阅',
    safe_analyst: '🛡️ 防御情景分析师',
    safe_opinion: '🛡️ 防御情景审阅',
    neutral_analyst: '⚖️ 基准情景分析师',
    neutral_opinion: '⚖️ 基准情景审阅',
    risk_management_decision: '⚠️ 风险治理结论',
    risk_assessment: '⚠️ 风险评估摘要',
    final_trade_decision: '📝 综合研究结论',
    investment_debate_state: '🔬 研究辩论状态',
    risk_debate_state: '🛡️ 风险辩论状态',
    detailed_analysis: '📄 详细分析'
  }
  // 未匹配到时，做一个友好的回退：下划线转空格
  return nameMap[moduleName] || moduleName.replace(/_/g, ' ')
}

const normalizeDisplayedResearchText = (content: string) => {
  if (!content) return ''

  const replacements: Array<[RegExp, string]> = [
    [/交易分析计划/g, '研究整合意见'],
    [/交易员计划/g, '研究整合意见'],
    [/初步投资计划/g, '研究团队结论'],
    [/投资计划/g, '研究结论'],
    [/投资建议/g, '研究结论'],
    [/操作建议/g, '研究观点'],
    [/大盘指数分析/g, '大盘环境研究'],
    [/行业板块分析/g, '行业板块研究'],
    [/市场情绪分析/g, '情绪研究'],
    [/新闻事件分析/g, '新闻研究'],
    [/风险治理摘要/g, '风险治理结论'],
    [/综合研究简报/g, '综合研究结论'],
    [/风险管理决策/g, '风险治理结论'],
    [/最终分析结果/g, '最终研究结论']
  ]

  return replacements.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), content)
}

const extractStructuredText = (value: any): string | null => {
  if (!value) return null

  if (typeof value === 'object') {
    for (const key of ['content', 'markdown', 'text', 'message', 'report', 'judge_decision']) {
      const item = value[key]
      if (typeof item === 'string' && item.trim()) {
        return item
      }
    }
    return null
  }

  if (typeof value !== 'string') {
    return null
  }

  let candidate = value.trim()
  for (let i = 0; i < 3; i += 1) {
    if (!candidate) break

    try {
      const parsed = JSON.parse(candidate)
      if (typeof parsed === 'string') {
        candidate = parsed.trim()
        continue
      }

      const extracted = extractStructuredText(parsed)
      if (extracted) {
        candidate = extracted.trim()
        continue
      }
    } catch {
      // 不是 JSON，继续使用原文本
    }

    break
  }

  if (
    ((candidate.startsWith('"') && candidate.endsWith('"')) ||
      (candidate.startsWith("'") && candidate.endsWith("'"))) &&
    candidate.length >= 2
  ) {
    candidate = candidate.slice(1, -1).trim()
  }

  return candidate || null
}

const prepareMarkdownContent = (content: string) => {
  if (!content) return ''

  const rawContent = extractStructuredText(content) || content

  const normalizedText = normalizeDisplayedResearchText(rawContent)
    .replace(/\u001b\[[0-9;]*m/g, '')
    .replace(/\r\n/g, '\n')
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/^\uFEFF/, '')

  const lines = normalizedText.split('\n')
  const nonEmptyLines = lines.filter(line => line.trim())

  if (nonEmptyLines.length === 0) {
    return normalizedText.trim()
  }

  const commonIndent = Math.min(
    ...nonEmptyLines.map(line => {
      const match = line.match(/^[\t ]*/)
      return match ? match[0].length : 0
    })
  )

  const dedentedLines = commonIndent > 0
    ? lines.map(line => line.slice(Math.min(commonIndent, line.length)))
    : lines

  let preparedText = dedentedLines.join('\n').trim()

  if (!preparedText) {
    return ''
  }

  if (
    ((preparedText.startsWith('"') && preparedText.endsWith('"')) ||
      (preparedText.startsWith("'") && preparedText.endsWith("'"))) &&
    preparedText.length >= 2
  ) {
    preparedText = preparedText.slice(1, -1).trim()
  }

  const fencedMarkdownMatch = preparedText.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/i)
  if (fencedMarkdownMatch) {
    preparedText = fencedMarkdownMatch[1].trim()
  }

  return preparedText
}

const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(prepareMarkdownContent(content)) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${prepareMarkdownContent(content)}</pre>`
  }
}

// 🔥 提取模块内容（支持对象中的 content 字段）
const getModuleContent = (moduleData: any): string | null => {
  if (!moduleData) return null

  const extractedText = extractStructuredText(moduleData)
  if (extractedText) {
    return normalizeDisplayedResearchText(extractedText)
  }
  
  // 如果是字符串，直接返回
  if (typeof moduleData === 'string') {
    return normalizeDisplayedResearchText(moduleData)
  }
  
  // 如果是对象，优先提取 content 字段
  if (typeof moduleData === 'object') {
    if (moduleData.content && typeof moduleData.content === 'string') {
      return normalizeDisplayedResearchText(moduleData.content)
    }
    if (moduleData.markdown && typeof moduleData.markdown === 'string') {
      return normalizeDisplayedResearchText(moduleData.markdown)
    }
    if (moduleData.judge_decision && typeof moduleData.judge_decision === 'string') {
      return normalizeDisplayedResearchText(moduleData.judge_decision)
    }
  }
  
  return null
}

// 获取分析深度描述
const getResearchDepthDescription = (depth: number) => {
  const descMap: Record<number, string> = {
    1: '快速分析 - 基础技术面和基本面分析',
    2: '标准分析 - 包含技术面、基本面和情绪研究',
    3: '深度分析 - 全面的多维度分析，包含详细的行业和竞争分析',
    4: '专家级分析 - 最全面的分析，包含所有维度和深度研究',
    5: '顶级分析 - 最高级别的分析深度，包含所有可能的分析维度'
  }
  return descMap[depth] || `分析深度: ${depth}`
}

// 格式化关键要点（处理 JSON 字段名）
const formatKeyPoint = (point: string): string => {
  if (!point) return ''

  // 字段名映射（英文 -> 中文）
  const fieldNameMap: Record<string, string> = {
    'analysis_view': '研究判断',
    'action': '研究判断',
    'confidence': '置信度',
    'reasoning': '研究依据',
    'summary': '研究摘要',
    'risk_score': '风险评分',
    'risk_level': '风险等级',
    'core_evidence': '核心依据',
    'uncertainties': '关键不确定性',
    'invalidation_conditions': '判断调整条件',
    'watch_items': '后续观察事项',
    'risk_warning': '风险提示'
  }

  // 检查是否是 JSON 格式的字段（如 "analysis_view": "中性"）
  const jsonMatch = point.match(/^"?([a-z_]+)"?\s*:\s*(.+)$/i)
  if (jsonMatch) {
    const fieldName = jsonMatch[1]
    let value = jsonMatch[2].trim()

    // 移除引号
    value = value.replace(/^["']|["']$/g, '')

    // 移除末尾的逗号
    value = value.replace(/,\s*$/, '')

    // 获取中文字段名
    const chineseName = fieldNameMap[fieldName] || fieldName

    return `${chineseName}: ${value}`
  }

  // 如果不是 JSON 格式，直接返回
  return point
}

const getPlainText = (content: string) => {
  return content
    .replace(/[#*_`>-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const getResearchOverview = () => {
  if (!report.value) return '已生成研究摘要，请查看下方详细报告。'

  const sourceText = report.value.summary || report.value.recommendation || ''
  const normalized = getPlainText(String(sourceText))

  if (!normalized) {
    return '已生成研究摘要，请查看下方详细报告。'
  }

  return normalized.length > 90 ? `${normalized.slice(0, 90)}...` : normalized
}

const getRiskFocus = () => {
  if (!report.value) return '请结合详细报告关注风险因素、信息披露与市场环境变化。'

  const riskPoint = (report.value.key_points || []).find((point: string) => {
    const normalized = String(point)
    return /风险|波动|回撤|不确定|关注/.test(normalized)
  })

  const rawText = riskPoint || report.value.summary || ''
  const normalized = getPlainText(String(rawText))

  if (!normalized) {
    return '请结合详细报告关注风险因素、信息披露与市场环境变化。'
  }

  return normalized.length > 90 ? `${normalized.slice(0, 90)}...` : normalized
}

// 生命周期
onMounted(() => {
  fetchLLMConfigs() // 先加载模型配置
  fetchReportDetail() // 再加载报告详情
})
</script>

<style lang="scss" scoped>
.report-detail {
  .loading-container {
    padding: 24px;
  }

  .report-content {
    .report-header {
      margin-bottom: 24px;

      .header-content {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;

        .title-section {
          .report-title {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 24px;
            font-weight: 600;
            color: var(--el-text-color-primary);
            margin: 0 0 12px 0;
          }

          .report-meta {
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;

            .meta-item {
              display: flex;
              align-items: center;
              gap: 4px;
              color: var(--el-text-color-regular);
              font-size: 14px;
            }
          }
        }

        .action-section {
          display: flex;
          gap: 8px;
        }
      }
    }

    /* 风险提示样式 */
    .risk-disclaimer {
      margin-bottom: 24px;
      animation: fadeInDown 0.5s ease-out;
    }

    .risk-disclaimer :deep(.el-alert) {
      background: linear-gradient(135deg, #fff3cd 0%, #ffe69c 100%);
      border: 2px solid #ffc107;
      border-radius: 12px;
      padding: 16px 20px;
      box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
    }

    .risk-disclaimer :deep(.el-alert__icon) {
      font-size: 24px;
      color: #ff6b00;
    }

    .disclaimer-content {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 15px;
      line-height: 1.6;
    }

    .disclaimer-icon {
      font-size: 24px;
      color: #ff6b00;
      flex-shrink: 0;
      animation: pulse 2s ease-in-out infinite;
    }

    .disclaimer-text {
      color: #856404;
      flex: 1;
    }

    .disclaimer-text strong {
      color: #d63031;
      font-size: 16px;
      font-weight: 700;
    }

    @keyframes pulse {
      0%, 100% {
        transform: scale(1);
        opacity: 1;
      }
      50% {
        transform: scale(1.1);
        opacity: 0.8;
      }
    }

    @keyframes fadeInDown {
      from {
        opacity: 0;
        transform: translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .summary-card,
    .metrics-card,
    .modules-card {
      margin-bottom: 24px;

      .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
      }
    }

    .summary-content {
      line-height: 1.6;
      color: var(--el-text-color-primary);
    }

    .metrics-content {
      .metric-item {
        text-align: center;
        padding: 24px;
        border: 1px solid var(--el-border-color-light);
        border-radius: 12px;
        background: var(--el-fill-color-blank);
        transition: all 0.3s ease;

        &:hover {
          box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
          transform: translateY(-2px);
        }

        .metric-label {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          font-size: 15px;
          font-weight: 500;
          color: var(--el-text-color-regular);
          margin-bottom: 16px;

          .el-icon {
            font-size: 18px;
          }
        }

        .metric-value {
          font-size: 18px;
          font-weight: 600;
          color: var(--el-color-primary);
        }

        .recommendation-value {
          font-size: 16px;
          line-height: 1.6;
          color: var(--el-text-color-primary);
          
          .core-conclusion {
            text-align: left;
            padding: 12px;
            background: var(--el-fill-color-light);
            border-radius: 8px;
            border-left: 3px solid var(--el-color-primary);
            
            strong {
              color: var(--el-color-primary);
              font-weight: 600;
            }
          }
        }
      }

      // 置信度评分样式
      .confidence-item {
        .confidence-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;

          .confidence-value {
            display: flex;
            align-items: baseline;
            gap: 4px;
            margin-top: 8px;

            .confidence-number {
              font-size: 32px;
              font-weight: 700;
              color: var(--el-color-primary);
            }

            .confidence-unit {
              font-size: 16px;
              color: var(--el-text-color-regular);
            }
          }

          .confidence-label {
            font-size: 14px;
            font-weight: 500;
            color: var(--el-text-color-secondary);
          }
        }
      }

      // 风险等级样式
      .risk-item {
        .risk-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;

          .risk-stars {
            display: flex;
            gap: 8px;
            font-size: 28px;

            .star-icon {
              color: #DCDFE6;
              transition: all 0.3s ease;

              &.active {
                color: #F7BA2A;
                animation: starPulse 0.6s ease-in-out;
              }
            }
          }

          .risk-label {
            font-size: 18px;
            font-weight: 700;
            margin-top: 4px;
          }

          .risk-description {
            font-size: 13px;
            color: var(--el-text-color-secondary);
            text-align: center;
            line-height: 1.4;
            max-width: 200px;
          }
        }
      }

      .key-points {
        margin-top: 32px;
        padding-top: 24px;
        border-top: 1px solid var(--el-border-color-lighter);

        h4 {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 600;
          color: var(--el-text-color-primary);

          .el-icon {
            font-size: 18px;
            color: var(--el-color-primary);
          }
        }

        ul {
          margin: 0;
          padding: 0;
          list-style: none;

          li {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 12px;
            padding: 12px;
            background: var(--el-fill-color-light);
            border-radius: 8px;
            line-height: 1.6;
            transition: all 0.2s ease;

            &:hover {
              background: var(--el-fill-color);
            }

            .point-icon {
              flex-shrink: 0;
              margin-top: 2px;
              font-size: 16px;
              color: var(--el-color-success);
            }
          }
        }
      }
    }

    // 星星脉冲动画
    @keyframes starPulse {
      0%, 100% {
        transform: scale(1);
      }
      50% {
        transform: scale(1.2);
      }
    }

    .module-content {
      .markdown-content {
        line-height: 1.6;

        :deep(p), :deep(li) {
          color: var(--el-text-color-primary);
        }

        :deep(pre) {
          white-space: pre-wrap;
          word-break: break-word;
          background: var(--el-fill-color-light);
          color: var(--el-text-color-primary);
          padding: 16px;
          border-radius: 8px;
          font-family: inherit;
        }

        :deep(code) {
          color: inherit;
        }
        
        :deep(h1), :deep(h2), :deep(h3) {
          margin: 16px 0 8px 0;
          color: var(--el-text-color-primary);
        }

        :deep(h1) { font-size: 24px; }
        :deep(h2) { font-size: 20px; }
        :deep(h3) { font-size: 16px; }
      }

      .json-content {
        pre {
          background: var(--el-fill-color-light);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          font-size: 14px;
          line-height: 1.4;
        }
      }
    }
  }

  .error-container {
    padding: 48px 24px;
  }
}
</style>
