<template>
  <div class="ta-debug">
    <el-card>
      <el-form :model="form" label-width="120px">
        <el-form-item label="分析师类型">
          <el-select v-model="form.analyst_type" style="width: 200px">
            <el-option label="基本面分析师" value="fundamentals" />
            <el-option label="市场分析师" value="market" />
            <el-option label="新闻分析师" value="news" />
            <el-option label="社媒分析师" value="social" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板来源">
          <el-radio-group v-model="form.use_current">
            <el-radio :label="true">当前激活</el-radio>
            <el-radio :label="false">指定模板ID</el-radio>
          </el-radio-group>
          <el-input v-model="form.template_id" placeholder="模板ID" style="width: 300px; margin-left: 12px" :disabled="form.use_current" />
        </el-form-item>
        <el-form-item label="模型厂家">
          <el-input v-model="form.llm.provider" placeholder="custom_openai" style="width: 200px" />
          <el-input v-model="form.llm.backend_url" placeholder="后端URL" style="width: 300px; margin-left:12px" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.llm.model" placeholder="ta-deep" style="width: 200px" />
          <el-input-number v-model="form.llm.temperature" :min="0" :max="1" :step="0.1" style="margin-left:12px" />
          <el-input-number v-model="form.llm.max_tokens" :min="256" :max="8192" :step="256" style="margin-left:12px" />
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="form.stock.symbol" placeholder="如 600519" style="width: 200px" />
          <el-input v-model="form.stock.analysis_date" placeholder="分析日期" style="width: 180px; margin-left:12px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runDebug" :loading="loading">运行调试</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card class="ta-result" v-if="result">
      <div class="ta-meta">{{ result.analyst_type }} · {{ result.symbol }}</div>
      <pre class="ta-pre">{{ result.report }}</pre>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { TemplatesDebugApi } from '@/api/templates_debug'
import { ElMessage } from 'element-plus'

const form = ref({
  analyst_type: 'fundamentals',
  template_id: '',
  use_current: true,
  llm: { provider: 'custom_openai', model: 'ta-deep', temperature: 0.7, max_tokens: 2000, backend_url: '' },
  stock: { symbol: '', analysis_date: '' }
})

const loading = ref(false)
const result = ref<any>(null)

const runDebug = async () => {
  loading.value = true
  try {
    const res = await TemplatesDebugApi.debugAnalyst({
      analyst_type: form.value.analyst_type as any,
      template_id: form.value.use_current ? undefined : form.value.template_id,
      use_current: form.value.use_current,
      llm: form.value.llm,
      stock: form.value.stock
    })
    if (res.success) {
      result.value = res.data
    } else {
      ElMessage.error(res.message || '调试失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '调试失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ta-debug { padding: 16px }
.ta-result { margin-top: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px }
.ta-meta { color: var(--el-text-color-secondary); margin-bottom: 6px }
</style>