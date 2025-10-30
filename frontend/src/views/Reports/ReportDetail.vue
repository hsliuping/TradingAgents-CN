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
                  <el-tag type="info" style="cursor: help;">{{ report.model_info }}</el-tag>
                </el-tooltip>
              </span>
            </div>
          </div>
          
          <div class="action-section">
            <el-button
              v-if="canApplyToTrading"
              type="success"
              @click="applyToTrading"
            >
              <el-icon><ShoppingCart /></el-icon>
              应用到交易
            </el-button>
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

      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <div class="disclaimer-content">
              <el-icon class="disclaimer-icon"><WarningFilled /></el-icon>
              <div class="disclaimer-text">
                <p style="margin: 0 0 8px 0;"><strong>⚠️ 重要风险提示与免责声明</strong></p>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                  <li><strong>工具性质：</strong>本系统为股票分析辅助工具，使用AI技术对公开市场数据进行分析，不具备证券投资咨询资质。</li>
                  <li><strong>非投资建议：</strong>所有分析结果、评分、建议仅为技术分析参考，不构成任何买卖建议或投资决策依据。</li>
                  <li><strong>数据局限性：</strong>分析基于历史数据和公开信息，可能存在延迟、不完整或不准确的情况，无法预测未来市场走势。</li>
                  <li><strong>投资风险：</strong>股票投资存在市场风险、流动性风险、政策风险等多种风险，可能导致本金损失。</li>
                  <li><strong>独立决策：</strong>投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。</li>
                  <li><strong>专业咨询：</strong>重大投资决策建议咨询具有合法资质的专业投资顾问或金融机构。</li>
                  <li><strong>责任声明：</strong>使用本工具产生的任何投资决策及其后果由投资者自行承担，本系统不承担任何责任。</li>
                </ul>
              </div>
            </div>
          </template>
        </el-alert>
      </div>

      <!-- 关键指标 -->
      <el-card class="metrics-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><TrendCharts /></el-icon>
            <span>关键指标</span>
          </div>
        </template>
        <div class="metrics-content">
          <el-row :gutter="24">
            <!-- 分析参考 -->
            <el-col :span="8">
              <div class="metric-item">
                <div class="metric-label">
                  <el-icon><TrendCharts /></el-icon>
                  分析参考
                  <el-tooltip content="基于AI模型的分析倾向，仅供参考，不构成投资建议" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="metric-value recommendation-value markdown-content" v-html="renderMarkdown(report.recommendation || '暂无')"></div>
                <el-tag type="info" size="small" style="margin-top: 8px;">仅供参考</el-tag>
              </div>
            </el-col>

            <!-- 风险评估 -->
            <el-col :span="8">
              <div class="metric-item risk-item">
                <div class="metric-label">
                  <el-icon><Warning /></el-icon>
                  风险评估
                  <el-tooltip content="基于历史数据的风险评估，实际风险可能更高" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="risk-display">
                  <div class="risk-stars">
                    <el-icon
                      v-for="star in 5"
                      :key="star"
                      class="star-icon"
                      :class="{ active: star <= getRiskStars(report.risk_level || '中等') }"
                    >
                      <StarFilled />
                    </el-icon>
                  </div>
                  <div class="risk-label" :style="{ color: getRiskColor(report.risk_level || '中等') }">
                    {{ report.risk_level || '中等' }}风险
                  </div>
                </div>
              </div>
            </el-col>

            <!-- 模型置信度 -->
            <el-col :span="8">
              <div class="metric-item confidence-item">
                <div class="metric-label">
                  <el-icon><DataAnalysis /></el-icon>
                  模型置信度
                  <el-tooltip content="基于AI模型计算的置信度，不代表实际投资成功率" placement="top">
                    <el-icon style="margin-left: 4px; cursor: help; font-size: 14px;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="confidence-display">
                  <el-progress
                    type="circle"
                    :percentage="normalizeConfidenceScore(report.confidence_score || 0)"
                    :width="120"
                    :stroke-width="10"
                    :color="getConfidenceColor(normalizeConfidenceScore(report.confidence_score || 0))"
                  >
                    <template #default="{ percentage }">
                      <span class="confidence-text">
                        <span class="confidence-number">{{ percentage }}</span>
                        <span class="confidence-unit">分</span>
                      </span>
                    </template>
                  </el-progress>
                  <div class="confidence-label">{{ getConfidenceLabel(normalizeConfidenceScore(report.confidence_score || 0)) }}</div>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- 关键要点 -->
          <div v-if="report.key_points && report.key_points.length > 0" class="key-points">
            <h4>
              <el-icon><List /></el-icon>
              关键要点
            </h4>
            <ul>
              <li v-for="(point, index) in report.key_points" :key="index">
                <el-icon class="point-icon"><Check /></el-icon>
                {{ point }}
              </li>
            </ul>
          </div>
        </div>
      </el-card>

      <!-- 报告摘要 -->
      <el-card v-if="report.summary" class="summary-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>执行摘要</span>
          </div>
        </template>
        <div class="summary-content markdown-content" v-html="renderMarkdown(report.summary)"></div>
      </el-card>

      <!-- 报告模块 -->
      <el-card class="modules-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Files /></el-icon>
            <span>分析报告</span>
          </div>
        </template>
        
        <el-tabs v-model="activeModule" type="border-card">
          <el-tab-pane
            v-for="(content, moduleName) in report.reports"
            :key="moduleName"
            :label="getModuleDisplayName(moduleName)"
            :name="moduleName"
          >
            <div class="module-content">
              <div v-if="typeof content === 'string'" class="markdown-content">
                <div v-html="renderMarkdown(content)"></div>
              </div>
              <div v-else class="json-content">
                <pre>{{ JSON.stringify(content, null, 2) }}</pre>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>

    <!-- 错误状态 -->
    <div v-else class="error-container">
      <el-result
        icon="error"
        title="报告加载失败"
        sub-title="请检查报告ID是否正确或稍后重试"
      >
        <template #extra>
          <el-button type="primary" @click="goBack">返回列表</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElInput, ElInputNumber, ElForm, ElFormItem } from 'element-plus'
import { paperApi } from '@/api/paper'
import { stocksApi } from '@/api/stocks'
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
  ShoppingCart,
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

      // 设置默认激活的模块
      const reports = result.data.reports || {}
      const moduleNames = Object.keys(reports)
      if (moduleNames.length > 0) {
        activeModule.value = moduleNames[0]
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
    a.download = `${report.value.stock_symbol}_分析报告_${report.value.analysis_date}.${ext}`

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
        message: 'PDF/Word 导出需要安装 pandoc 工具',
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

// 判断是否可以应用到交易
const canApplyToTrading = computed(() => {
  if (!report.value) return false
  const rec = report.value.recommendation || ''
  // 检查是否包含买入或卖出建议
  return rec.includes('买入') || rec.includes('卖出') || rec.toLowerCase().includes('buy') || rec.toLowerCase().includes('sell')
})

// 解析投资建议
const parseRecommendation = () => {
  if (!report.value) return null

  const rec = report.value.recommendation || ''
  const traderPlan = report.value.reports?.trader_investment_plan || ''

  // 解析操作类型
  let action: 'buy' | 'sell' | null = null
  if (rec.includes('买入') || rec.toLowerCase().includes('buy')) {
    action = 'buy'
  } else if (rec.includes('卖出') || rec.toLowerCase().includes('sell')) {
    action = 'sell'
  }

  if (!action) return null

  // 解析目标价格（从recommendation或trader_investment_plan中提取）
  let targetPrice: number | null = null
  const priceMatch = rec.match(/目标价[格]?[：:]\s*([0-9.]+)/) ||
                     traderPlan.match(/目标价[格]?[：:]\s*([0-9.]+)/)
  if (priceMatch) {
    targetPrice = parseFloat(priceMatch[1])
  }

  return {
    action,
    targetPrice,
    confidence: report.value.confidence_score || 0,
    riskLevel: report.value.risk_level || '中等'
  }
}

// 应用到模拟交易
const applyToTrading = async () => {
  const recommendation = parseRecommendation()
  if (!recommendation) {
    ElMessage.warning('无法解析投资建议，请检查报告内容')
    return
  }

  try {
    // 获取账户信息
    const accountRes = await paperApi.getAccount()
    if (!accountRes.success || !accountRes.data) {
      ElMessage.error('获取账户信息失败')
      return
    }

    const account = accountRes.data.account
    const positions = accountRes.data.positions

    // 查找当前持仓
    const currentPosition = positions.find(p => p.code === report.value.stock_symbol)

    // 获取当前实时价格
    let currentPrice = 10 // 默认价格
    try {
      const quoteRes = await stocksApi.getQuote(report.value.stock_symbol)
      if (quoteRes.success && quoteRes.data && quoteRes.data.price) {
        currentPrice = quoteRes.data.price
      }
    } catch (error) {
      console.warn('获取实时价格失败，使用默认价格')
    }

    // 计算建议交易数量
    let suggestedQuantity = 0
    let maxQuantity = 0

    if (recommendation.action === 'buy') {
      // 买入：根据可用资金和当前价格计算
      const availableCash = account.cash
      maxQuantity = Math.floor(availableCash / currentPrice / 100) * 100 // 100股为单位
      const suggested = Math.floor(maxQuantity * 0.2) // 建议使用20%资金
      suggestedQuantity = Math.floor(suggested / 100) * 100 // 向下取整到100的倍数
      suggestedQuantity = Math.max(100, suggestedQuantity) // 至少100股
    } else {
      // 卖出：根据当前持仓计算
      if (!currentPosition || currentPosition.quantity === 0) {
        ElMessage.warning('当前没有持仓，无法卖出')
        return
      }
      maxQuantity = currentPosition.quantity
      suggestedQuantity = Math.floor(maxQuantity / 100) * 100 // 向下取整到100的倍数
      suggestedQuantity = Math.max(100, suggestedQuantity) // 至少100股
    }

    // 用户可修改的价格和数量（使用reactive）
    const tradeForm = reactive({
      price: currentPrice,
      quantity: suggestedQuantity
    })

    // 显示可编辑的确认对话框
    const actionText = recommendation.action === 'buy' ? '买入' : '卖出'
    const actionColor = recommendation.action === 'buy' ? '#67C23A' : '#F56C6C'

    // 创建一个响应式的消息组件
    const MessageComponent = {
      setup() {
        // 计算预计金额
        const estimatedAmount = computed(() => {
          return (tradeForm.price * tradeForm.quantity).toFixed(2)
        })

        return () => h('div', { style: 'line-height: 2;' }, [
          // 风险提示横幅
          h('div', {
            style: 'background-color: #FEF0F0; border: 1px solid #F56C6C; border-radius: 4px; padding: 12px; margin-bottom: 16px;'
          }, [
            h('div', { style: 'color: #F56C6C; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center;' }, [
              h('span', { style: 'font-size: 16px; margin-right: 6px;' }, '⚠️'),
              h('span', '风险提示')
            ]),
            h('div', { style: 'color: #606266; font-size: 12px; line-height: 1.6;' }, [
              h('p', { style: 'margin: 4px 0;' }, '• 本交易基于AI分析结果，仅供参考，不构成投资建议'),
              h('p', { style: 'margin: 4px 0;' }, '• 模拟交易使用虚拟资金，与实盘存在显著差异'),
              h('p', { style: 'margin: 4px 0;' }, '• 股票投资存在市场风险，可能导致本金损失'),
              h('p', { style: 'margin: 4px 0;' }, '• 请勿将模拟结果作为实盘投资决策依据')
            ])
          ]),
          h('p', [
            h('strong', '股票代码：'),
            h('span', report.value.stock_symbol)
          ]),
          h('p', [
            h('strong', '操作类型：'),
            h('span', { style: `color: ${actionColor}; font-weight: bold;` }, actionText)
          ]),
          recommendation.targetPrice ? h('p', [
            h('strong', '目标价格：'),
            h('span', { style: 'color: #E6A23C;' }, `${recommendation.targetPrice.toFixed(2)}元`),
            h('span', { style: 'color: #909399; font-size: 12px; margin-left: 8px;' }, '(仅供参考)')
          ]) : null,
          h('p', [
            h('strong', '当前价格：'),
            h('span', `${currentPrice.toFixed(2)}元`)
          ]),
          h('div', { style: 'margin: 16px 0;' }, [
            h('p', { style: 'margin-bottom: 8px;' }, [
              h('strong', '交易价格：'),
              h('span', { style: 'color: #909399; font-size: 12px; margin-left: 8px;' }, '(可修改)')
            ]),
            h(ElInputNumber, {
              modelValue: tradeForm.price,
              'onUpdate:modelValue': (val: number) => { tradeForm.price = val },
              min: 0.01,
              max: 9999,
              precision: 2,
              step: 0.01,
              style: 'width: 200px;',
              controls: true
            })
          ]),
          h('div', { style: 'margin: 16px 0;' }, [
            h('p', { style: 'margin-bottom: 8px;' }, [
              h('strong', '交易数量：'),
              h('span', { style: 'color: #909399; font-size: 12px; margin-left: 8px;' }, '(可修改，100股为单位)')
            ]),
            h(ElInputNumber, {
              modelValue: tradeForm.quantity,
              'onUpdate:modelValue': (val: number) => { tradeForm.quantity = val },
              min: 100,
              max: maxQuantity,
              step: 100,
              style: 'width: 200px;',
              controls: true
            })
          ]),
          h('p', [
            h('strong', '预计金额：'),
            h('span', { style: 'color: #409EFF; font-weight: bold;' }, `${estimatedAmount.value}元`)
          ]),
          h('p', [
            h('strong', '模型置信度：'),
            h('span', `${(recommendation.confidence * 100).toFixed(1)}%`),
            h('span', { style: 'color: #909399; font-size: 12px; margin-left: 8px;' }, '(不代表实际成功率)')
          ]),
          h('p', [
            h('strong', '风险评估：'),
            h('span', recommendation.riskLevel),
            h('span', { style: 'color: #909399; font-size: 12px; margin-left: 8px;' }, '(实际风险可能更高)')
          ]),
          recommendation.action === 'buy' ? h('p', { style: 'color: #909399; font-size: 12px; margin-top: 12px;' },
            `可用资金：${account.cash.toFixed(2)}元，最大可买：${maxQuantity}股`
          ) : null,
          recommendation.action === 'sell' ? h('p', { style: 'color: #909399; font-size: 12px; margin-top: 12px;' },
            `当前持仓：${maxQuantity}股`
          ) : null
        ])
      }
    }

    await ElMessageBox({
      title: '确认交易',
      message: h(MessageComponent),
      confirmButtonText: '确认下单',
      cancelButtonText: '取消',
      type: 'warning',
      beforeClose: (action, instance, done) => {
        if (action === 'confirm') {
          // 验证输入
          if (tradeForm.quantity < 100 || tradeForm.quantity % 100 !== 0) {
            ElMessage.error('交易数量必须是100的整数倍')
            return
          }
          if (tradeForm.quantity > maxQuantity) {
            ElMessage.error(`交易数量不能超过${maxQuantity}股`)
            return
          }
          if (tradeForm.price <= 0) {
            ElMessage.error('交易价格必须大于0')
            return
          }

          // 检查资金是否充足
          if (recommendation.action === 'buy') {
            const totalAmount = tradeForm.price * tradeForm.quantity
            if (totalAmount > account.cash) {
              ElMessage.error('可用资金不足')
              return
            }
          }
        }
        done()
      }
    })

    // 执行交易
    const orderRes = await paperApi.placeOrder({
      code: report.value.stock_symbol,
      side: recommendation.action,
      quantity: tradeForm.quantity,
      analysis_id: report.value.analysis_id || report.value.id
    })

    if (orderRes.success) {
      ElMessage.success(`${actionText}订单已提交成功！`)
      // 可选：跳转到模拟交易页面
      setTimeout(() => {
        router.push({ name: 'PaperTradingHome' })
      }, 1500)
    } else {
      ElMessage.error(orderRes.message || '下单失败')
    }

  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('应用到交易失败:', error)
      ElMessage.error(error.message || '操作失败')
    }
  }
}

// 返回列表
const goBack = () => {
  router.push('/reports')
}

// 工具函数
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

const getModuleDisplayName = (moduleName: string) => {
  // 统一与单股分析的中文标签映射（完整的13个报告）
  const nameMap: Record<string, string> = {
    // 分析师团队 (4个)
    market_report: '📈 市场技术分析',
    sentiment_report: '💭 市场情绪分析',
    news_report: '📰 新闻事件分析',
    fundamentals_report: '💰 基本面分析',

    // 研究团队 (3个)
    bull_researcher: '🐂 多头研究员',
    bear_researcher: '🐻 空头研究员',
    research_team_decision: '🔬 研究经理决策',

    // 交易团队 (1个)
    trader_investment_plan: '💼 交易员计划',

    // 风险管理团队 (4个)
    risky_analyst: '⚡ 激进分析师',
    safe_analyst: '🛡️ 保守分析师',
    neutral_analyst: '⚖️ 中性分析师',
    risk_management_decision: '👔 投资组合经理',

    // 最终决策 (1个)
    final_trade_decision: '🎯 最终交易决策',

    // 兼容旧字段
    investment_plan: '📋 投资建议',
    investment_debate_state: '🔬 研究团队决策（旧）',
    risk_debate_state: '⚖️ 风险管理团队（旧）',
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
        }
      }

      // 置信度评分样式
      .confidence-item {
        .confidence-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;

          .el-progress {
            margin-bottom: 8px;
          }

          .confidence-text {
            display: flex;
            flex-direction: column;
            align-items: center;
            line-height: 1;

            .confidence-number {
              font-size: 32px;
              font-weight: 700;
            }

            .confidence-unit {
              font-size: 14px;
              margin-top: 4px;
              opacity: 0.8;
            }
          }

          .confidence-label {
            font-size: 16px;
            font-weight: 600;
            color: var(--el-text-color-primary);
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
