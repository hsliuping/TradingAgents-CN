<template>
  <el-dialog
    v-model="visible"
    title="欢迎使用 TradingAgents-CN"
    width="600px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="!isFirstTime"
  >
    <div class="guide-dialog-content">
      <div class="welcome-header">
        <el-icon class="welcome-icon"><Document /></el-icon>
        <h3>欢迎使用 TradingAgents-CN</h3>
        <p class="welcome-subtitle">按照以下步骤完成初始设置，开始使用AI辅助股票分析技术学习平台</p>
      </div>

      <div class="steps-summary">
        <el-steps direction="vertical" :active="5" finish-status="success" size="small">
          <el-step title="获取API Token" description="获取大模型和数据源的API密钥" />
          <el-step title="填写Token配置" description="在设置页面填写您的API密钥" />
          <el-step title="同步股票数据" description="同步基础股票数据到系统" />
          <el-step title="搜索并添加自选股" description="搜索感兴趣的股票并添加到股票关注列表" />
          <el-step title="完成第一次分析" description="对自己关注股票进行AI分析" />
        </el-steps>
      </div>

      <div class="quick-actions">
        <el-button type="primary" @click="goToGuide" style="width: 100%">
          <el-icon><Document /></el-icon>
          查看完整使用指南
        </el-button>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-checkbox v-model="dontShowAgain" v-if="isFirstTime">
          不再显示此提示
        </el-checkbox>
        <div class="footer-buttons">
          <el-button v-if="isFirstTime" @click="handleSkip">稍后再说</el-button>
          <el-button type="primary" @click="handleConfirm">
            {{ isFirstTime ? '开始使用' : '知道了' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Document } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  isFirstTime?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'confirm'): void
  (e: 'skip'): void
}>()

const router = useRouter()
const dontShowAgain = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const goToGuide = () => {
  router.push('/guide')
  handleConfirm()
}

const handleConfirm = () => {
  if (dontShowAgain.value && props.isFirstTime) {
    // 保存到localStorage，不再显示
    localStorage.setItem('guide_dialog_shown', 'true')
  }
  emit('confirm')
  visible.value = false
}

const handleSkip = () => {
  emit('skip')
  visible.value = false
}
</script>

<style lang="scss" scoped>
.guide-dialog-content {
  .welcome-header {
    text-align: center;
    margin-bottom: 32px;

    .welcome-icon {
      font-size: 48px;
      color: var(--el-color-primary);
      margin-bottom: 16px;
    }

    h3 {
      margin: 0 0 8px 0;
      font-size: 20px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .welcome-subtitle {
      margin: 0;
      color: var(--el-text-color-regular);
      font-size: 14px;
    }
  }

  .steps-summary {
    margin-bottom: 24px;
    padding: 20px;
    background: var(--el-bg-color-page);
    border-radius: 8px;

    :deep(.el-steps) {
      .el-step__title {
        font-size: 14px;
        font-weight: 500;
      }

      .el-step__description {
        font-size: 12px;
        color: var(--el-text-color-regular);
      }
    }
  }

  .quick-actions {
    margin-top: 24px;
  }
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .footer-buttons {
    display: flex;
    gap: 12px;
  }
}
</style>
