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
        <el-form-item label="研究深度">
          <el-select v-model="researchDepth" style="width: 200px">
            <el-option label="快速" value="快速" />
            <el-option label="基础" value="基础" />
            <el-option label="标准" value="标准" />
            <el-option label="深度" value="深度" />
            <el-option label="全面" value="全面" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板来源">
          <el-radio-group v-model="form.use_current">
            <el-radio :label="true">当前激活</el-radio>
            <el-radio :label="false">指定模板ID</el-radio>
          </el-radio-group>
          <el-input v-model="form.template_id" placeholder="模板ID" style="width: 300px; margin-left: 12px" :disabled="form.use_current" />
        </el-form-item>
        <el-form-item label="模型名称">
          <DeepModelSelector v-model="form.llm.model" :available-models="availableModels" type="deep" width="320px" />
        </el-form-item>
        <el-form-item label="生成参数">
          <div style="display:flex;align-items:center;gap:16px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:64px;color:#606266;">温度</span>
              <el-input-number v-model="form.llm.temperature" :min="0" :max="1" :step="0.1" />
              <span style="font-size:12px;color:#909399;">控制输出随机性，0更稳定，1更发散</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:88px;color:#606266;">最大Token</span>
              <el-input-number v-model="form.llm.max_tokens" :min="256" :max="8192" :step="256" />
              <span style="font-size:12px;color:#909399;">限制每次输出的最大Token数量</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="股票代码">
          <el-input v-model="form.stock.symbol" placeholder="如 600519" style="width: 200px" />
          <el-date-picker
            v-model="form.stock.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="分析日期"
            style="width: 180px; margin-left:12px"
          />
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
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { TemplatesDebugApi } from '@/api/templates_debug'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api/config'
import DeepModelSelector from '@/components/DeepModelSelector.vue'

const form = ref({
  analyst_type: 'fundamentals',
  template_id: '',
  use_current: true,
  llm: { provider: 'custom_openai', model: 'ta-deep', temperature: 0.7, max_tokens: 4000, backend_url: '' },
  stock: { symbol: '', analysis_date: '' }
})

const loading = ref(false)
const result = ref<any>(null)
const researchDepth = ref('标准')
const availableModels = ref<any[]>([])

const runDebug = async () => {
  loading.value = true
  try {
    const symbol = String(form.value.stock.symbol || '').trim()
    if (!symbol) {
      ElMessage.error('请填写股票代码')
      loading.value = false
      return
    }
    const res = await TemplatesDebugApi.debugAnalyst({
      analyst_type: form.value.analyst_type as any,
      template_id: form.value.use_current ? undefined : form.value.template_id,
      use_current: form.value.use_current,
      llm: form.value.llm,
      stock: { ...form.value.stock, symbol }
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

onMounted(async () => {
  try {
    const route = useRoute()
    const q = route.query || {}
    if (typeof q.analyst_type === 'string') form.value.analyst_type = q.analyst_type as any
    if (typeof q.template_id === 'string' && q.template_id) {
      form.value.use_current = false
      form.value.template_id = q.template_id as string
    }
    if (typeof q.symbol === 'string') form.value.stock.symbol = q.symbol as string

    if (!form.value.stock.analysis_date) {
      const d = new Date()
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      form.value.stock.analysis_date = `${yyyy}-${mm}-${dd}`
    }

    try {
      const defaults = await configApi.getDefaultModels()
      form.value.llm.model = defaults.deep_analysis_model || form.value.llm.model
    } catch (e) {
      // ignore, 保持默认值
    }

    try {
      const llmConfigs = await configApi.getLLMConfigs()
      availableModels.value = (llmConfigs as any[]).filter((c: any) => c.enabled)
      const info = availableModels.value.find((m: any) => m.model_name === form.value.llm.model)
      if (info) form.value.llm.provider = info.provider
    } catch (e) {
      availableModels.value = []
    }
  } catch {}
})

watch(() => form.value.llm.model, (newModel) => {
  const info = availableModels.value.find((m: any) => m.model_name === newModel)
  form.value.llm.provider = info?.provider || 'custom_openai'
})
</script>

<style scoped>
.ta-debug { padding: 16px }
.ta-result { margin-top: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px }
.ta-meta { color: var(--el-text-color-secondary); margin-bottom: 6px }
</style>