<template>
  <div class="jdyun-config">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>京东云配置</span>
          <el-tag type="success" size="small">京东云合作版</el-tag>
        </div>
      </template>

      <el-alert
        title="京东云合作版说明"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      >
        <template #default>
          京东云合作版通过环境变量注入大模型和数据源配置，用户无需手动配置。
          如需修改配置，请联系管理员更新环境变量后重启服务。
        </template>
      </el-alert>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="模型服务地址">
          <span v-if="status.api_base">{{ status.api_base }}</span>
          <el-tag v-else type="danger" size="small">未配置</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="API Key">
          <el-tag v-if="status.api_key_configured" type="success" size="small">已配置</el-tag>
          <el-tag v-else type="danger" size="small">未配置</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="当前默认模型">
          <el-tag type="primary">{{ status.current_model || '未设置' }}</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="可选模型列表">
          <div class="model-list">
            <el-tag
              v-for="model in status.available_models"
              :key="model"
              :type="model === status.current_model ? 'primary' : 'info'"
              size="small"
              style="margin-right: 8px; margin-bottom: 4px;"
            >
              {{ model }}
            </el-tag>
          </div>
        </el-descriptions-item>

        <el-descriptions-item label="Embedding 模型">
          <el-tag type="info">{{ status.embedding_model || '未设置' }}</el-tag>
          <span style="margin-left: 8px; color: #909399; font-size: 12px;">
            (维度: {{ status.embedding_dims || 0 }})
          </span>
        </el-descriptions-item>

        <el-descriptions-item label="Tushare 数据源">
          <el-tag v-if="status.tushare_token_configured" type="success" size="small">已配置</el-tag>
          <el-tag v-else type="danger" size="small">未配置</el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="AKShare 数据源">
          <el-tag v-if="status.akshare_available" type="success" size="small">可用（免费开源）</el-tag>
          <el-tag v-else type="danger" size="small">不可用</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="config-actions" style="margin-top: 20px;">
        <el-button @click="loadStatus" :loading="loading">刷新状态</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/config'

interface JdyunStatus {
  jdyun_mode: boolean
  api_base: string
  api_key_configured: boolean
  current_model: string
  available_models: string[]
  embedding_model: string
  embedding_dims: number
  tushare_token_configured: boolean
  akshare_available: boolean
}

const status = ref<JdyunStatus>({
  jdyun_mode: true,
  api_base: '',
  api_key_configured: false,
  current_model: '',
  available_models: [],
  embedding_model: '',
  embedding_dims: 0,
  tushare_token_configured: false,
  akshare_available: true,
})

const loading = ref(false)

const loadStatus = async () => {
  loading.value = true
  try {
    const data = await configApi.getJdyunStatus()
    // 兼容旧后端不返回 akshare_available 的情况
    status.value = {
      ...data,
      akshare_available: data.akshare_available ?? true,
    }
  } catch (error: any) {
    ElMessage.error('获取京东云配置状态失败: ' + (error?.message || error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped>
.jdyun-config {
  max-width: 800px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
