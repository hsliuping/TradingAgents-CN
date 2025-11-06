<template>
  <div class="batch-analysis">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">
            <el-icon class="title-icon"><Files /></el-icon>
            批量分析
          </h1>
          <p class="page-description">
            AI驱动的批量股票分析，高效处理多只股票
          </p>
        </div>
      </div>

      <!-- 风险提示 -->
      <div class="risk-disclaimer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <span style="font-size: 14px;">
              <strong>⚠️ 重要提示：</strong>本工具为股票分析辅助工具，所有分析结果仅供参考，不构成投资建议。投资有风险，决策需谨慎。
            </span>
          </template>
        </el-alert>
      </div>
    </div>

    <!-- 股票列表输入区域 -->
    <div class="analysis-container">
      <el-row :gutter="24">
        <el-col :span="24">
          <el-card class="stock-list-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>📋 股票列表</h3>
                <el-tag :type="stockCodes.length > 0 ? 'success' : 'info'" size="small">
                  {{ stockCodes.length }} 只股票
                </el-tag>
              </div>
            </template>

            <div class="stock-input-section">
              <div class="input-area">
                <el-input
                  v-model="stockInput"
                  type="textarea"
                  :rows="8"
                  placeholder="请输入股票代码，每行一个&#10;支持格式：&#10;000001&#10;000002.SZ&#10;600036.SH&#10;AAPL&#10;TSLA"
                  @input="parseStockCodes"
                  class="stock-textarea"
                />
                <div class="input-actions">
                  <el-button type="primary" @click="parseStockCodes" size="small">
                    解析股票代码
                  </el-button>
                  <el-button @click="clearStocks" size="small">清空</el-button>
                </div>
              </div>

              <!-- 股票预览 -->
              <div v-if="stockCodes.length > 0" class="stock-preview">
                <h4>股票预览</h4>
                <div class="stock-tags">
                  <el-tag
                    v-for="(code, index) in stockCodes.slice(0, 20)"
                    :key="code"
                    closable
                    @close="removeStock(index)"
                    class="stock-tag"
                  >
                    {{ code }}
                  </el-tag>
                  <el-tag v-if="stockCodes.length > 20" type="info">
                    +{{ stockCodes.length - 20 }} 更多...
                  </el-tag>
                </div>
              </div>

              <!-- 无效代码提示 -->
              <div v-if="invalidCodes.length > 0" class="invalid-codes">
                <el-alert
                  title="以下股票代码格式可能有误，请检查："
                  type="warning"
                  :closable="false"
                >
                  <div class="invalid-list">
                    <el-tag v-for="code in invalidCodes" :key="code" type="danger" size="small">
                      {{ code }}
                    </el-tag>
                  </div>
                </el-alert>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 分析配置区域 -->
      <el-row :gutter="24" style="margin-top: 24px;">
        <!-- 左侧：分析配置 -->
        <el-col :span="18">
          <el-card class="config-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>⚙️ 分析配置</h3>
                <el-tag type="primary" size="small">批量设置</el-tag>
              </div>
            </template>

            <el-form :model="batchForm" label-width="100px" class="batch-form">
              <!-- 基础信息 -->
              <div class="form-section">
                <h4 class="section-title">📋 基础信息</h4>
                <el-form-item label="批次标题" required>
                  <el-input
                    v-model="batchForm.title"
                    placeholder="如：银行板块分析"
                    size="large"
                  />
                </el-form-item>

                <el-form-item label="批次描述">
                  <el-input
                    v-model="batchForm.description"
                    type="textarea"
                    :rows="2"
                    placeholder="描述本次批量分析的目的和背景（可选）"
                  />
                </el-form-item>
              </div>

              <!-- 分析参数 -->
              <div class="form-section">
                <h4 class="section-title">⚙️ 分析参数</h4>
                <el-form-item label="市场类型">
                  <el-select v-model="batchForm.market" placeholder="选择市场" size="large" style="width: 100%">
                    <el-option label="🇨🇳 A股市场" value="A股" />
                    <el-option label="🇺🇸 美股市场" value="美股" />
                    <el-option label="🇭🇰 港股市场" value="港股" />
                  </el-select>
                </el-form-item>

                <el-form-item label="分析深度">
                  <el-select v-model="batchForm.depth" placeholder="选择深度" size="large" style="width: 100%">
                    <el-option label="⚡ 1级 - 快速分析 (2-4分钟/只)" value="1" />
                    <el-option label="📈 2级 - 基础分析 (4-6分钟/只)" value="2" />
                    <el-option label="🎯 3级 - 标准分析 (6-10分钟/只，推荐)" value="3" />
                    <el-option label="🔍 4级 - 深度分析 (10-15分钟/只)" value="4" />
                    <el-option label="🏆 5级 - 全面分析 (15-25分钟/只)" value="5" />
                  </el-select>
                </el-form-item>
              </div>

              <!-- 分析师选择 -->
              <div class="form-section">
                <h4 class="section-title">👥 分析师团队</h4>
                <div class="analysts-selection">
                  <el-checkbox-group v-model="batchForm.analysts" class="analysts-group">
                    <div
                      v-for="analyst in ANALYSTS"
                      :key="analyst.id"
                      class="analyst-option"
                    >
                      <el-checkbox :label="analyst.name" class="analyst-checkbox">
                        <div class="analyst-info">
                          <span class="analyst-name">{{ analyst.name }}</span>
                          <span class="analyst-desc">{{ analyst.description }}</span>
                        </div>
                      </el-checkbox>
                    </div>
                  </el-checkbox-group>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="form-section">
                <div class="action-buttons" style="display: flex; justify-content: center; align-items: center; width: 100%; text-align: center;">
                  <el-button
                    type="primary"
                    size="large"
                    @click="submitBatchAnalysis"
                    :loading="submitting"
                    :disabled="stockCodes.length === 0"
                    class="submit-btn large-batch-btn"
                    style="width: 320px; height: 56px; font-size: 18px; font-weight: 700; border-radius: 16px;"
                  >
                    <el-icon><TrendCharts /></el-icon>
                    开始批量分析 ({{ stockCodes.length }}只)
                  </el-button>
                </div>
              </div>
            </el-form>
          </el-card>
        </el-col>

        <!-- 右侧：高级配置 -->
        <el-col :span="6">
          <el-card class="advanced-config-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <h3>🔧 高级配置</h3>
              </div>
            </template>

            <div class="config-content">
              <!-- AI模型配置组件 -->
              <ModelConfig
                v-model:quick-analysis-model="modelSettings.quickAnalysisModel"
                v-model:deep-analysis-model="modelSettings.deepAnalysisModel"
                :available-models="availableModels"
                :analysis-depth="batchForm.depth"
              />

              <!-- 分析选项 -->
              <div class="config-section">
                <h4 class="config-title">⚙️ 分析选项</h4>
                <div class="analysis-options">
                  <div class="option-item">
                    <el-switch v-model="batchForm.includeSentiment" />
                    <div class="option-content">
                      <div class="option-name">情绪分析</div>
                      <div class="option-desc">分析市场情绪和投资者心理</div>
                    </div>
                  </div>

                  <div class="option-item">
                    <el-switch v-model="batchForm.includeRisk" />
                    <div class="option-content">
                      <div class="option-name">风险评估</div>
                      <div class="option-desc">包含详细的风险因素分析</div>
                    </div>
                  </div>

                  <div class="option-item">
                    <el-select v-model="batchForm.language" size="small" style="width: 100%">
                      <el-option label="中文" value="zh-CN" />
                      <el-option label="English" value="en-US" />
                    </el-select>
                    <div class="option-content">
                      <div class="option-name">语言偏好</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 股票预览 -->
    <el-card v-if="stockCodes.length > 0" class="stock-preview-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h3>股票预览 ({{ stockCodes.length }}只)</h3>
          <el-button type="text" @click="validateStocks">
            <el-icon><Check /></el-icon>
            验证股票代码
          </el-button>
        </div>
      </template>

      <div class="stock-grid">
        <div
          v-for="(code, index) in stockCodes"
          :key="index"
          class="stock-item"
          :class="{ invalid: invalidCodes.includes(code) }"
        >
          <span class="stock-code">{{ code }}</span>
          <el-button
            type="text"
            size="small"
            @click="removeStock(index)"
            class="remove-btn"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <div v-if="invalidCodes.length > 0" class="invalid-notice">
        <el-alert
          title="发现无效股票代码"
          type="warning"
          :description="`以下股票代码可能无效：${invalidCodes.join(', ')}`"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Files, TrendCharts, Check, Close } from '@element-plus/icons-vue'
import { ANALYSTS, DEFAULT_ANALYSTS, convertAnalystNamesToIds } from '@/constants/analysts'
import { configApi } from '@/api/config'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ModelConfig from '@/components/ModelConfig.vue'

// 路由实例（必须在顶层调用）
const router = useRouter()
const route = useRoute()

const submitting = ref(false)
const stockInput = ref('')
const stockCodes = ref<string[]>([])  // 保留用于表单绑定
const symbols = ref<string[]>([])     // 标准化后的代码列表
const invalidCodes = ref<string[]>([])

// 模型设置
const modelSettings = ref({
  quickAnalysisModel: 'qwen-turbo',
  deepAnalysisModel: 'qwen-max'
})

// 可用的模型列表（从配置中获取）
const availableModels = ref<any[]>([])

const batchForm = reactive({
  title: '',
  description: '',
  market: 'A股',
  depth: '3',  // 默认3级标准分析，将在 onMounted 中从用户偏好加载
  analysts: [...DEFAULT_ANALYSTS],  // 将在 onMounted 中从用户偏好加载
  includeSentiment: true,
  includeRisk: true,
  language: 'zh-CN'
})

const parseStockCodes = () => {
  const codes = stockInput.value
    .split('\n')
    .map(code => code.trim())
    .filter(code => code.length > 0)
    .filter((code, index, arr) => arr.indexOf(code) === index) // 去重

  stockCodes.value = codes

  // 标准化股票代码（移除市场后缀，统一大写）
  symbols.value = codes.map(code => {
    // 移除 .SZ, .SH, .BJ, .HK 等后缀
    const cleanCode = code.split('.')[0].toUpperCase()
    return cleanCode
  })
}

const clearStocks = () => {
  stockInput.value = ''
  stockCodes.value = []
  symbols.value = []
  invalidCodes.value = []
}

// 初始化模型设置
const initializeModelSettings = async () => {
  try {
    // 获取默认模型
    const defaultModels = await configApi.getDefaultModels()
    modelSettings.value.quickAnalysisModel = defaultModels.quick_analysis_model
    modelSettings.value.deepAnalysisModel = defaultModels.deep_analysis_model

    // 获取所有可用的模型列表
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = llmConfigs.filter((config: any) => config.enabled)

    console.log('✅ 加载模型配置成功:', {
      quick: modelSettings.value.quickAnalysisModel,
      deep: modelSettings.value.deepAnalysisModel,
      available: availableModels.value.length
    })
  } catch (error) {
    console.error('加载默认模型配置失败:', error)
    // 使用硬编码的默认值
    modelSettings.value.quickAnalysisModel = 'qwen-turbo'
    modelSettings.value.deepAnalysisModel = 'qwen-max'
  }
}

// 页面初始化
onMounted(async () => {
  await initializeModelSettings()

  // 🆕 从用户偏好加载默认设置
  const authStore = useAuthStore()
  const userPrefs = authStore.user?.preferences

  if (userPrefs) {
    // 加载默认市场
    if (userPrefs.default_market) {
      batchForm.market = userPrefs.default_market
    }

    // 加载默认分析深度
    if (userPrefs.default_depth) {
      batchForm.depth = userPrefs.default_depth
    }

    // 加载默认分析师
    if (userPrefs.default_analysts && userPrefs.default_analysts.length > 0) {
      batchForm.analysts = [...userPrefs.default_analysts]
    }

    console.log('✅ 批量分析已加载用户偏好设置:', {
      market: batchForm.market,
      depth: batchForm.depth,
      analysts: batchForm.analysts
    })
  }

  // 读取路由查询参数以便从筛选页预填充（路由参数优先级最高）
  const q = route.query as any
  if (q?.stocks) {
    const parts = String(q.stocks).split(',').map((s) => s.trim()).filter(Boolean)
    stockCodes.value = parts
    stockInput.value = parts.join('\n')
    // 触发解析以更新 symbols
    parseStockCodes()
  }
  if (q?.market) {
    const m = String(q.market)
    if (m === 'A股' || m === '美股' || m === '港股') {
      batchForm.market = m
    }
  }
})

const removeStock = (index: number) => {
  const removedCode = stockCodes.value[index]
  stockCodes.value.splice(index, 1)
  
  // 更新输入框
  stockInput.value = stockCodes.value.join('\n')
  
  // 从无效列表中移除
  const invalidIndex = invalidCodes.value.indexOf(removedCode)
  if (invalidIndex > -1) {
    invalidCodes.value.splice(invalidIndex, 1)
  }
}

const validateStocks = async () => {
  // 模拟验证股票代码
  const invalid = stockCodes.value.filter(code => {
    // 简单的验证规则：A股代码应该是6位数字
    return !/^\d{6}$/.test(code)
  })
  
  invalidCodes.value = invalid
  
  if (invalid.length === 0) {
    ElMessage.success('所有股票代码验证通过')
  } else {
    ElMessage.warning(`发现 ${invalid.length} 个无效股票代码`)
  }
}

const submitBatchAnalysis = async () => {
  if (!batchForm.title) {
    ElMessage.warning('请输入批次标题')
    return
  }

  if (stockCodes.value.length === 0) {
    ElMessage.warning('请输入股票代码')
    return
  }

  if (stockCodes.value.length > 10) {
    ElMessage.warning('单次批量分析最多支持10只股票，请减少股票数量')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要提交批量分析任务吗？\n批次：${batchForm.title}\n股票数量：${stockCodes.value.length}只`,
      '确认提交',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    submitting.value = true

    // 准备批量分析请求参数（为将来的真实API调用做准备）
    const batchRequest = {
      title: batchForm.title,
      description: batchForm.description,
      symbols: symbols.value,
      stock_codes: symbols.value,  // 兼容字段
      parameters: {
        market_type: batchForm.market,
        research_depth: batchForm.depth,
        selected_analysts: convertAnalystNamesToIds(batchForm.analysts),
        include_sentiment: batchForm.includeSentiment,
        include_risk: batchForm.includeRisk,
        language: batchForm.language,
        quick_analysis_model: modelSettings.value.quickAnalysisModel,
        deep_analysis_model: modelSettings.value.deepAnalysisModel
      }
    }

    // 调用真实的批量分析API
    const { analysisApi } = await import('@/api/analysis')
    const response = await analysisApi.startBatchAnalysis(batchRequest)

    if (!response?.success) {
      throw new Error(response?.message || '批量分析提交失败')
    }

    const { batch_id, total_tasks } = response.data

    // 显示成功提示并引导用户去任务中心
    ElMessageBox.confirm(
      `✅ 批量分析任务已成功提交！\n\n📊 股票数量：${total_tasks}只\n📋 批次ID：${batch_id}\n\n任务正在后台执行中，最多同时执行3个任务，其他任务会自动排队等待。\n\n是否前往任务中心查看进度？`,
      '提交成功',
      {
        confirmButtonText: '前往任务中心',
        cancelButtonText: '留在当前页面',
        type: 'success',
        distinguishCancelAndClose: true,
        closeOnClickModal: false
      }
    ).then(() => {
      // 用户点击"前往任务中心"
      router.push({ path: '/tasks', query: { batch_id } })
    }).catch((action) => {
      // 用户点击"留在当前页面"或关闭对话框
      if (action === 'cancel') {
        ElMessage.info('任务正在后台执行，您可以随时前往任务中心查看进度')
      }
    })

  } catch (error: any) {
    // 处理错误
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量分析提交失败')
    }
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  // 从用户偏好加载默认值
  const authStore = useAuthStore()
  const userPrefs = authStore.user?.preferences

  Object.assign(batchForm, {
    title: '',
    description: '',
    market: userPrefs?.default_market || 'A股',
    depth: userPrefs?.default_depth || '3',
    analysts: userPrefs?.default_analysts ? [...userPrefs.default_analysts] : [...DEFAULT_ANALYSTS]
  })
  clearStocks()
}
</script>

<style lang="scss" scoped>
.batch-analysis {
  min-height: 100vh;
  background: var(--el-bg-color-page);
  padding: 24px;

  .page-header {
    margin-bottom: 32px;

    .header-content {
      background: var(--el-bg-color);
      padding: 32px;
      border-radius: 16px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    .title-section {
      .page-title {
        display: flex;
        align-items: center;
        font-size: 32px;
        font-weight: 700;
        color: #1a202c;
        margin: 0 0 8px 0;

        .title-icon {
          margin-right: 12px;
          color: #3b82f6;
        }
      }

      .page-description {
        font-size: 16px;
        color: #64748b;
        margin: 0;
      }
    }
  }

  .analysis-container {
    .stock-list-card, .config-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

      :deep(.el-card__header) {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 16px 16px 0 0;
        padding: 20px 24px;

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 24px;
      }
    }

    // 右侧高级配置卡片样式
    .advanced-config-card {
      border-radius: 16px;
      border: none;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

      :deep(.el-card__header) {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        border-radius: 16px 16px 0 0;
        padding: 20px 24px;

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
          }
        }
      }

      :deep(.el-card__body) {
        padding: 24px;
      }

      .config-content {
        .config-section {
          margin-bottom: 24px;

          &:last-child {
            margin-bottom: 0;
          }

          .analysis-options {
            .option-item {
              display: flex;
              align-items: flex-start;
              gap: 12px;
              padding: 12px 0;
              border-bottom: 1px solid #f3f4f6;

              &:last-child {
                border-bottom: none;
                padding-bottom: 0;
              }

              .option-content {
                flex: 1;

                .option-name {
                  font-size: 14px;
                  font-weight: 500;
                  color: #374151;
                  margin-bottom: 2px;
                }

                .option-desc {
                  font-size: 12px;
                  color: #6b7280;
                }
              }
            }
          }
        }
      }
    }

    .stock-input-section {
      .input-area {
        margin-bottom: 24px;

        .stock-textarea {
          :deep(.el-textarea__inner) {
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 14px;
            line-height: 1.6;

            &:focus {
              border-color: #3b82f6;
              box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
          }
        }

        .input-actions {
          margin-top: 12px;
          display: flex;
          gap: 12px;
        }
      }

      .stock-preview {
        h4 {
          font-size: 16px;
          font-weight: 600;
          color: #1a202c;
          margin: 0 0 12px 0;
        }

        .stock-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;

          .stock-tag {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-weight: 600;
          }
        }
      }

      .invalid-codes {
        margin-top: 16px;

        .invalid-list {
          margin-top: 8px;
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
      }
    }

    .batch-form {
      .form-section {
        margin-bottom: 32px;

        .section-title {
          font-size: 16px;
          font-weight: 600;
          color: #1a202c;
          margin: 0 0 16px 0;
          padding-bottom: 8px;
          border-bottom: 2px solid #e2e8f0;
        }
      }

      .analysts-selection {
        .analysts-group {
          display: flex;
          flex-direction: column;
          gap: 12px;

          .analyst-option {
            .analyst-checkbox {
              width: 100%;

              :deep(.el-checkbox__label) {
                width: 100%;
              }

              :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
                background-color: #3b82f6;
                border-color: #3b82f6;
              }

              :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
                color: #3b82f6;
              }

              .analyst-info {
                display: flex;
                flex-direction: column;
                gap: 4px;

                .analyst-name {
                  font-weight: 500;
                  color: #374151;
                }

                .analyst-desc {
                  font-size: 12px;
                  color: #6b7280;
                }
              }
            }
          }
        }
      }
    }

    .action-section {
      margin-top: 24px !important;
      display: flex !important;
      justify-content: center !important;
      align-items: center !important;
      width: 100% !important;
      text-align: center !important;

      .submit-btn.el-button {
        width: 320px !important;
        height: 56px !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
        min-width: 320px !important;
        max-width: 320px !important;

        &:hover {
          transform: translateY(-3px) !important;
          box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
          background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        }

        &:disabled {
          opacity: 0.6 !important;
          transform: none !important;
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
        }

        .el-icon {
          margin-right: 8px !important;
          font-size: 20px !important;
        }

        span {
          font-size: 18px !important;
          font-weight: 700 !important;
        }
      }
    }
  }
}
</style>

<style>
/* 全局样式确保按钮样式生效 */
.action-section {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
  text-align: center !important;
}

.large-batch-btn.el-button {
  width: 320px !important;
  height: 56px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  border-radius: 16px !important;
  transition: all 0.3s ease !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.2) !important;
  min-width: 320px !important;
  max-width: 320px !important;
}

.large-batch-btn.el-button:hover {
  transform: translateY(-3px) !important;
  box-shadow: 0 12px 30px rgba(59, 130, 246, 0.4) !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
}

.large-batch-btn.el-button:disabled {
  opacity: 0.6 !important;
  transform: none !important;
  box-shadow: 0 4px 15px rgba(59, 130, 246, 0.1) !important;
}

.large-batch-btn.el-button .el-icon {
  margin-right: 8px !important;
  font-size: 20px !important;
}

.large-batch-btn.el-button span {
  font-size: 18px !important;
  font-weight: 700 !important;
}
</style>
