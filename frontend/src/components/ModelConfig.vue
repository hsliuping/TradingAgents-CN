<template>
  <div class="model-config-component">
    <!-- AI模型配置 -->
    <div class="config-section">
      <h4 class="config-title">🤖 AI模型配置</h4>
      <div class="model-config">
        <div class="model-item">
          <div class="model-label">
            <span>快速分析模型</span>
            <el-tooltip content="用于市场分析、新闻分析、基本面分析等" placement="top">
              <el-icon class="help-icon"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-select v-model="localQuickModel" size="small" style="width: 100%" filterable @change="onQuickModelChange">
            <el-option
              v-for="model in availableModels"
              :key="`quick-${model.provider}/${model.model_name}`"
              :label="model.model_display_name || model.model_name"
              :value="model.model_name"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <span style="flex: 1;">{{ model.model_display_name || model.model_name }}</span>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <!-- 能力等级徽章 -->
                  <el-tag
                    v-if="model.capability_level"
                    :type="getCapabilityTagType(model.capability_level)"
                    size="small"
                    effect="plain"
                  >
                    {{ getCapabilityText(model.capability_level) }}
                  </el-tag>
                  <!-- 角色标签 -->
                  <el-tag
                    v-if="isQuickAnalysisRole(model.suitable_roles)"
                    type="success"
                    size="small"
                    effect="plain"
                  >
                    ⚡快速
                  </el-tag>
                  <span style="font-size: 12px; color: #909399;">{{ model.provider }}</span>
                </div>
              </div>
            </el-option>
          </el-select>
        </div>

        <div class="model-item">
          <div class="model-label">
            <span>深度决策模型</span>
            <el-tooltip content="用于研究管理者综合决策、风险管理者最终评估" placement="top">
              <el-icon class="help-icon"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-select v-model="localDeepModel" size="small" style="width: 100%" filterable @change="onDeepModelChange">
            <el-option
              v-for="model in availableModels"
              :key="`deep-${model.provider}/${model.model_name}`"
              :label="model.model_display_name || model.model_name"
              :value="model.model_name"
            >
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <span style="flex: 1;">{{ model.model_display_name || model.model_name }}</span>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <!-- 能力等级徽章 -->
                  <el-tag
                    v-if="model.capability_level"
                    :type="getCapabilityTagType(model.capability_level)"
                    size="small"
                    effect="plain"
                  >
                    {{ getCapabilityText(model.capability_level) }}
                  </el-tag>
                  <!-- 角色标签 -->
                  <el-tag
                    v-if="isDeepAnalysisRole(model.suitable_roles)"
                    type="warning"
                    size="small"
                    effect="plain"
                  >
                    🧠深度
                  </el-tag>
                  <span style="font-size: 12px; color: #909399;">{{ model.provider }}</span>
                </div>
              </div>
            </el-option>
          </el-select>
        </div>
      </div>

      <!-- 🆕 模型推荐提示 -->
      <el-alert
        v-if="modelRecommendation"
        :title="modelRecommendation.title"
        :type="modelRecommendation.type"
        :closable="false"
        style="margin-top: 12px;"
      >
        <template #default>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
            <div style="font-size: 13px; line-height: 1.8; flex: 1; white-space: pre-line;">
              {{ modelRecommendation.message }}
            </div>
            <el-button
              v-if="modelRecommendation.quickModel && modelRecommendation.deepModel"
              type="primary"
              size="small"
              @click="applyRecommendedModels"
              style="flex-shrink: 0;"
            >
              应用推荐
            </el-button>
          </div>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { recommendModels } from '@/api/modelCapabilities'

// Props
interface Props {
  quickAnalysisModel: string
  deepAnalysisModel: string
  availableModels: any[]
  analysisDepth: string | number  // 支持字符串（如"标准"）或数字（如3）
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'update:quickAnalysisModel': [value: string]
  'update:deepAnalysisModel': [value: string]
}>()

// Local state
const localQuickModel = ref(props.quickAnalysisModel)
const localDeepModel = ref(props.deepAnalysisModel)

// 模型推荐提示
const modelRecommendation = ref<{
  title: string
  message: string
  type: 'success' | 'warning' | 'info' | 'error'
  quickModel?: string
  deepModel?: string
} | null>(null)

// Watch props changes
watch(() => props.quickAnalysisModel, (newVal) => {
  localQuickModel.value = newVal
})

watch(() => props.deepAnalysisModel, (newVal) => {
  localDeepModel.value = newVal
})

// Emit changes
const onQuickModelChange = (value: string) => {
  emit('update:quickAnalysisModel', value)
}

const onDeepModelChange = (value: string) => {
  emit('update:deepAnalysisModel', value)
}

/**
 * 获取能力等级文本
 */
const getCapabilityText = (level: number): string => {
  const texts: Record<number, string> = {
    1: '⚡基础',
    2: '📊标准',
    3: '🎯高级',
    4: '🔥专业',
    5: '👑旗舰'
  }
  return texts[level] || '📊标准'
}

/**
 * 获取能力等级标签类型
 */
const getCapabilityTagType = (level: number): 'success' | 'info' | 'warning' | 'danger' => {
  if (level >= 4) return 'danger'
  if (level >= 3) return 'warning'
  if (level >= 2) return 'success'
  return 'info'
}

/**
 * 判断是否适合快速分析
 */
const isQuickAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('quick_analysis') || roles.includes('both')
}

/**
 * 判断是否适合深度分析
 */
const isDeepAnalysisRole = (roles: string[] | undefined): boolean => {
  if (!roles || !Array.isArray(roles)) return false
  return roles.includes('deep_analysis') || roles.includes('both')
}

/**
 * 检查模型适配性并提供推荐
 */
const checkModelSuitability = async () => {
  // 将分析深度转换为标准格式
  let depthName: string
  if (typeof props.analysisDepth === 'number') {
    const depthNames: Record<number, string> = {
      1: '快速',
      2: '基础',
      3: '标准',
      4: '深度',
      5: '全面'
    }
    depthName = depthNames[props.analysisDepth] || '标准'
  } else {
    depthName = props.analysisDepth
  }

  try {
    // 获取推荐模型
    const recommendRes = await recommendModels(depthName)
    const responseData = recommendRes?.data?.data

    if (responseData) {
      const quickModel = responseData.quick_model || '未知'
      const deepModel = responseData.deep_model || '未知'

      // 获取模型的显示名称
      const quickModelInfo = props.availableModels.find(m => m.model_name === quickModel)
      const deepModelInfo = props.availableModels.find(m => m.model_name === deepModel)

      const quickDisplayName = quickModelInfo?.model_display_name || quickModel
      const deepDisplayName = deepModelInfo?.model_display_name || deepModel

      // 获取推荐理由
      const reason = responseData.reason || ''

      // 构建推荐说明
      const depthDescriptions: Record<string, string> = {
        '快速': '快速浏览，获取基本信息',
        '基础': '基础分析，了解主要指标',
        '标准': '标准分析，全面评估股票',
        '深度': '深度研究，挖掘投资机会',
        '全面': '全面分析，专业投资决策'
      }

      const message = `${depthDescriptions[depthName] || '标准分析'}\n\n推荐模型配置：\n• 快速模型：${quickDisplayName}\n• 深度模型：${deepDisplayName}\n\n${reason}`

      modelRecommendation.value = {
        title: '💡 模型推荐',
        message,
        type: 'info',
        quickModel,
        deepModel
      }
    } else {
      // 如果没有推荐数据，显示通用说明
      const generalDescriptions: Record<string, string> = {
        '快速': '快速分析：使用基础模型即可，注重速度和成本',
        '基础': '基础分析：快速模型用基础级，深度模型用标准级',
        '标准': '标准分析：快速模型用基础级，深度模型用标准级以上',
        '深度': '深度分析：快速模型用标准级，深度模型用高级以上，需要推理能力',
        '全面': '全面分析：快速模型用标准级，深度模型用专业级以上，强推理能力'
      }

      modelRecommendation.value = {
        title: '💡 模型推荐',
        message: generalDescriptions[depthName] || generalDescriptions['标准'],
        type: 'info'
      }
    }
  } catch (error) {
    console.error('获取模型推荐失败:', error)
  }
}

/**
 * 应用推荐的模型配置
 */
const applyRecommendedModels = () => {
  if (modelRecommendation.value?.quickModel && modelRecommendation.value?.deepModel) {
    localQuickModel.value = modelRecommendation.value.quickModel
    localDeepModel.value = modelRecommendation.value.deepModel
    
    emit('update:quickAnalysisModel', modelRecommendation.value.quickModel)
    emit('update:deepAnalysisModel', modelRecommendation.value.deepModel)

    // 清除推荐提示
    modelRecommendation.value = null

    ElMessage.success('已应用推荐的模型配置')
  }
}

// 监听分析深度变化
watch(() => props.analysisDepth, () => {
  checkModelSuitability()
})

// 监听模型选择变化
watch([localQuickModel, localDeepModel], () => {
  checkModelSuitability()
})

// 初始化
onMounted(() => {
  checkModelSuitability()
})
</script>

<style lang="scss" scoped>
.model-config-component {
  .config-section {
    margin-bottom: 24px;

    &:last-child {
      margin-bottom: 0;
    }

    .config-title {
      font-size: 14px;
      font-weight: 600;
      color: #1a202c;
      margin: 0 0 12px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .model-config {
      .model-item {
        margin-bottom: 16px;

        &:last-child {
          margin-bottom: 0;
        }

        .model-label {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 13px;
          color: #374151;

          .help-icon {
            color: #9ca3af;
            cursor: help;
          }
        }
      }
    }
  }
}
</style>

