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
              v-for="model in quickModels"
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
              v-for="model in deepModels"
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'

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

const quickModels = computed(() => props.availableModels.filter(
  model => !model.role || model.role === 'RESEARCH_AGENT'
))
const deepModels = computed(() => props.availableModels.filter(
  model => !model.role || model.role === 'TOP_RISK_REVIEWER'
))

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
