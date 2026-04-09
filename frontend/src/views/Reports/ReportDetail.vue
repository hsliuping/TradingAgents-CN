<template>
  <div class="report-detail">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 报告内容 -->
    <div v-else-if="report" class="report-content">
      <!-- 报告头部 -->
      <el-card class="report-header" shadow="never">
        <div class="header-content">
          <div class="title-section">
            <h1 class="report-title">
              <el-icon><Document /></el-icon>
              {{ report.stock_name || report.stock_symbol }} 分析报告
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
  StarFilled,
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
    // 构建文件名：股票代码_股票名称_分析报告_日期
    const fileName = cleanStockName
      ? `${report.value.stock_symbol}_${cleanStockName}_分析报告_${report.value.analysis_date}.${ext}`
      : `${report.value.stock_symbol}_分析报告_${report.value.analysis_date}.${ext}`
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
    'index_analyst': '大盘指数分析师',
    'sector_analyst': '行业板块分析师',
    
    // 分析师团队
    'market_analyst': '市场技术分析师',
    'fundamentals_analyst': '基本面分析师',
    'news_analyst': '新闻事件分析师',
    'sentiment_analyst': '市场情绪分析师',
    
    // 研究团队
    'bull_researcher': '多头研究员',
    'bear_researcher': '空头研究员',
    
    // 风险管理团队
    'risky_analyst': '激进分析师',
    'safe_analyst': '保守分析师',
    'neutral_analyst': '中性分析师',
    
    // 兼容旧格式（不带_analyst后缀）
    'market': '市场分析师',
    'fundamentals': '基本面分析师',
    'news': '新闻分析师',
    'social': '社媒分析师',
    'sentiment': '情绪分析师',
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
  'detailed_analysis'
]

// 计算属性：按顺序返回存在的报告模块
const orderedModuleNames = computed(() => {
  if (!report.value?.reports) return []

  const availableModules = Object.keys(report.value.reports)

  // 按照 moduleOrder 的顺序过滤出存在的模块
  const ordered = moduleOrder.filter(name => availableModules.includes(name))

  // 添加不在 moduleOrder 中但存在的模块（放在最后）
  const hiddenModules = [
    'investment_plan',
    'bull_researcher',
    'bull_report',
    'bear_researcher',
    'bear_report',
    'research_team_decision',
    'trader_investment_plan',
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
    'risk_debate_state'
  ]
  const remaining = availableModules.filter(name => !moduleOrder.includes(name) && !hiddenModules.includes(name))

  return [...ordered, ...remaining]
})

const getModuleDisplayName = (moduleName: string) => {
  // 统一与单股分析的中文标签映射（仅保留研究类报告）
  const nameMap: Record<string, string> = {
    // 🆕 宏观分析师团队 (2个) - 优先显示
    index_report: '📊 大盘指数分析',
    sector_report: '🏭 行业板块分析',

    // 分析师团队 (4个)
    market_report: '📈 市场技术分析',
    sentiment_report: '💭 市场情绪分析',
    news_report: '📰 新闻事件分析',
    fundamentals_report: '💰 基本面分析',
    detailed_analysis: '📄 详细分析'
  }
  // 未匹配到时，做一个友好的回退：下划线转空格
  return nameMap[moduleName] || moduleName.replace(/_/g, ' ')
}

const renderMarkdown = (content: string) => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

// 🔥 提取模块内容（支持对象中的 content 字段）
const getModuleContent = (moduleData: any): string | null => {
  if (!moduleData) return null
  
  // 如果是字符串，直接返回
  if (typeof moduleData === 'string') {
    return moduleData
  }
  
  // 如果是对象，优先提取 content 字段
  if (typeof moduleData === 'object') {
    if (moduleData.content && typeof moduleData.content === 'string') {
      return moduleData.content
    }
    if (moduleData.markdown && typeof moduleData.markdown === 'string') {
      return moduleData.markdown
    }
    if (moduleData.judge_decision && typeof moduleData.judge_decision === 'string') {
      return moduleData.judge_decision
    }
  }
  
  return null
}

// 置信度评分相关函数
// 将后端返回的 0-1 小数转换为 0-100 的百分制
const normalizeConfidenceScore = (score: number) => {
  // 如果已经是 0-100 的范围，直接返回
  if (score > 1) {
    return Math.round(score)
  }
  // 如果是 0-1 的小数，转换为百分制
  return Math.round(score * 100)
}

const getConfidenceColor = (score: number) => {
  if (score >= 80) return '#67C23A' // 较高 - 绿色
  if (score >= 60) return '#409EFF' // 中上 - 蓝色
  if (score >= 40) return '#E6A23C' // 中等 - 橙色
  return '#F56C6C' // 较低 - 红色
}

const getConfidenceLabel = (score: number) => {
  if (score >= 80) return '较高'
  if (score >= 60) return '中上'
  if (score >= 40) return '中等'
  return '较低'
}

// 风险等级相关函数
const getRiskStars = (riskLevel: string) => {
  const riskMap: Record<string, number> = {
    '低': 1,
    '中低': 2,
    '中等': 3,
    '中高': 4,
    '高': 5
  }
  return riskMap[riskLevel] || 3
}

const getRiskColor = (riskLevel: string) => {
  const colorMap: Record<string, string> = {
    '低': '#67C23A',      // 绿色
    '中低': '#95D475',    // 浅绿色
    '中等': '#E6A23C',    // 橙色
    '中高': '#F56C6C',    // 红色
    '高': '#F56C6C'       // 深红色
  }
  return colorMap[riskLevel] || '#E6A23C'
}

const getRiskDescription = (riskLevel: string) => {
  const descMap: Record<string, string> = {
    '低': '风险较小，适合稳健投资者',
    '中低': '风险可控，适合大多数投资者',
    '中等': '风险适中，需要谨慎评估',
    '中高': '风险较高，需要密切关注',
    '高': '风险很高，建议谨慎投资'
  }
  return descMap[riskLevel] || '请根据自身风险承受能力决策'
}

// 获取分析深度描述
const getResearchDepthDescription = (depth: number) => {
  const descMap: Record<number, string> = {
    1: '快速分析 - 基础技术面和基本面分析',
    2: '标准分析 - 包含技术面、基本面和市场情绪分析',
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
    'analysis_view': '分析观点',
    'action': '分析观点',
    'confidence': '置信度',
    'price_analysis_range': '价格分析区间',
    'target_price': '价格分析区间',
    'risk_reference_price': '风险控制参考价',
    'stop_loss': '风险控制参考价',
    'risk_exposure_ratio': '风险敞口比例',
    'position_ratio': '风险敞口比例',
    'reasoning': '分析推理',
    'summary': '分析摘要',
    'risk_score': '风险评分',
    'risk_level': '风险等级'
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

// 提取核心结论（简洁版）
const getCoreConclusion = () => {
  if (!report.value) return '暂无'

  // 优先从 decision 字段提取
  if (report.value.decision) {
    const action = report.value.decision.action || report.value.decision.analysis_view || '持有'

    // 🔥 合规修改：直接返回分析观点，不提取前提（避免从 JSON 格式的 reasoning 中提取错误信息）
    return action
  }

  // 如果没有 decision 字段，尝试从 recommendation 中提取
  if (report.value.recommendation) {
    const rec = report.value.recommendation

    // 尝试提取核心结论（匹配"核心结论：..."或"分析观点：..."）
    const coreMatch = rec.match(/核心结论[：:]\s*([^。\n]+)/) ||
                      rec.match(/分析观点[：:]\s*([^。\n]+)/) ||
                      rec.match(/投资建议[：:]\s*([^。\n]+)/) ||
                      rec.match(/建议[：:]\s*([^。\n]+)/)

    if (coreMatch && coreMatch[1]) {
      // 清理提取的内容，移除多余的空格和换行
      const cleaned = coreMatch[1].trim().replace(/\s+/g, ' ')
      return cleaned.length > 100 ? cleaned.substring(0, 100) + '...' : cleaned
    }

    // 如果没找到，返回前50个字符
    return rec.length > 50 ? rec.substring(0, 50) + '...' : rec
  }

  return '暂无'
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
