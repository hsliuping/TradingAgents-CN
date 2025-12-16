<template>
  <div class="ta-debug">
    <div class="ta-toolbar">
      <el-button link @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>
    <el-card>
      <el-form :model="form" label-width="120px">
        <el-form-item label="分析师类型">
          <el-select v-model="form.analyst_type" style="width: 300px" placeholder="选择分析师类型">
            <el-option-group v-for="group in groupedAgents" :key="group.version" :label="group.version">
              <el-option
                v-for="agent in group.agents"
                :key="agent.id"
                :label="agent.name"
                :value="agent.id"
              >
                <span>{{ agent.name }}</span>
                <span style="float: right; color: #8492a6; font-size: 12px">{{ agent.version }}</span>
              </el-option>
            </el-option-group>
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
        <el-form-item label="股票代码" v-if="needsStockSymbol">
          <el-input v-model="form.stock.symbol" placeholder="如 600519" style="width: 200px" />
          <el-date-picker
            v-model="form.stock.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="分析日期"
            style="width: 180px; margin-left:12px"
          />
        </el-form-item>
        <el-form-item label="分析日期" v-if="!needsStockSymbol">
          <el-date-picker
            v-model="form.stock.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="分析日期"
            style="width: 200px"
          />
          <span style="font-size:12px;color:#909399;margin-left:10px;">大盘分析不需要指定具体股票</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runDebug" :loading="loading">运行调试</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card class="ta-result" v-if="result">
      <template #header>
        <div class="card-header">
          <span>📊 分析结果</span>
          <span class="meta-info">{{ result.analyst_type }} · {{ result.symbol }} · {{ result.report_length }} 字符</span>
        </div>
      </template>
      <el-scrollbar height="600px">
        <div class="markdown-body" v-html="renderMarkdown(result.report)"></div>
      </el-scrollbar>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TemplatesDebugApi } from '@/api/templates_debug'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configApi } from '@/api/config'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import { marked } from 'marked'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useLicenseStore } from '@/stores/license'

// 配置 marked 选项
marked.setOptions({ breaks: true, gfm: true })

// Markdown 渲染函数
const renderMarkdown = (content: string): string => {
  if (!content) return '<p>暂无内容</p>'
  try {
    return marked.parse(content) as string
  } catch (e) {
    console.error('Markdown 渲染失败:', e)
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

const form = ref({
  analyst_type: 'fundamentals',
  template_id: '',
  use_current: true,
  llm: { provider: 'custom_openai', model: '', temperature: 0.7, max_tokens: 4000, backend_url: '' },
  stock: { symbol: '', analysis_date: '' }
})

const loading = ref(false)
const result = ref<any>(null)
const researchDepth = ref('标准')
const availableModels = ref<any[]>([])
const availableAgents = ref<any[]>([])

const licenseStore = useLicenseStore()
const router = useRouter()

// 按版本分组的agents
const groupedAgents = computed(() => {
  const groups = [
    { version: 'v1.0 (旧版)', agents: [] as any[] },
    { version: 'v2.0 (新版)', agents: [] as any[] }
  ]

  availableAgents.value.forEach(agent => {
    // 规范化版本号检查
    const v = agent.version || ''
    if (v === 'v1.0' || v === '1.0' || v === '1.0.0') {
      groups[0].agents.push(agent)
    } else if (v === 'v2.0' || v === '2.0' || v.startsWith('2.')) {
      groups[1].agents.push(agent)
    }
  })

  // 只返回有agents的分组
  return groups.filter(group => group.agents.length > 0)
})

// 加载可用的agents
const loadAvailableAgents = async (targetAgentType?: string) => {
  try {
    const res = await TemplatesDebugApi.listDebugAgents()
    if (res.success && res.data) {
      availableAgents.value = res.data

      // 如果指定了目标agent类型，尝试设置它
      if (targetAgentType) {
        const targetAgent = availableAgents.value.find(a => a.id === targetAgentType)
        if (targetAgent) {
          form.value.analyst_type = targetAgentType
          return
        }
      }

      // 如果当前选择的agent不在列表中，选择第一个
      if (!availableAgents.value.find(a => a.id === form.value.analyst_type)) {
        if (availableAgents.value.length > 0) {
          form.value.analyst_type = availableAgents.value[0].id
        }
      }
    }
  } catch (error) {
    console.error('加载agents失败:', error)
    ElMessage.error('加载分析师列表失败')
  }
}

// 判断是否需要股票代码输入
const needsStockSymbol = computed(() => {
  // 只有大盘分析师不需要具体的股票代码
  // 板块分析师需要股票代码来分析该股票所属的行业/板块
  return form.value.analyst_type !== 'index_analyst'
})

const runDebug = async () => {
  loading.value = true
  try {
    const symbol = String(form.value.stock.symbol || '').trim()

    // 只有需要股票代码的分析师才验证股票代码
    if (needsStockSymbol.value && !symbol) {
      ElMessage.error('请填写股票代码')
      loading.value = false
      return
    }
    // 获取选中的agent版本
    const selectedAgent = availableAgents.value.find(a => a.id === form.value.analyst_type)
    const agentVersion = selectedAgent?.version

    const res = await TemplatesDebugApi.debugAnalyst({
      analyst_type: form.value.analyst_type as any,
      agent_version: agentVersion, // 传递版本号
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
    // 处理权限错误
    if (e?.response?.status === 403) {
      const detail = e?.response?.data?.detail
      if (detail?.code === 'ADVANCED_REQUIRED') {
        ElMessageBox.confirm(
          '提示词调试功能为高级学员专属，请升级学员等级后使用。',
          '权限不足',
          {
            confirmButtonText: '查看学员状态',
            cancelButtonText: '返回',
            type: 'warning'
          }
        ).then(() => {
          router.push('/settings/license')
        }).catch(() => {
          // 用户点击取消，返回上一页
          router.back()
        })
        return
      }
    }
    ElMessage.error(e?.response?.data?.detail || e?.message || '调试失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    // 先解析URL参数
    const route = useRoute()
    const q = route.query || {}

    console.log('🔍 [模板调试] URL参数:', q)

    // 加载可用的agents，并传递目标agent类型
    const targetAgentType = typeof q.analyst_type === 'string' ? q.analyst_type : undefined
    await loadAvailableAgents(targetAgentType)

    // 应用其他URL参数
    if (typeof q.template_id === 'string' && q.template_id) {
      form.value.use_current = false
      form.value.template_id = q.template_id as string
    }
    if (typeof q.symbol === 'string') form.value.stock.symbol = q.symbol as string

    // 🔥 处理agent_type参数，用于区分v1.0和v2.0
    if (typeof q.agent_type === 'string' && q.agent_type) {
      const agentType = q.agent_type as string
      console.log('🔍 [模板调试] 检测到agent_type参数:', agentType)

      // 判断是否为v2.0版本
      const isV2 = agentType.endsWith('_v2')
      const targetVersion = isV2 ? 'v2.0' : 'v1.0'

      console.log('🔍 [模板调试] 目标版本:', targetVersion, '目标分析师类型:', targetAgentType)

      if (targetAgentType) {
        // 查找对应版本的分析师
        const targetAgent = availableAgents.value.find(agent => {
          const v = agent.version || ''
          const isAgentV2 = v === 'v2.0' || v === '2.0' || v.startsWith('2.')
          const isAgentV1 = v === 'v1.0' || v === '1.0' || v === '1.0.0'
          
          if (isV2 && !isAgentV2) return false
          if (!isV2 && !isAgentV1) return false

          if (isV2) {
            // v2.0版本：检查agent.id是否包含targetAgentType
            return agent.id.includes(targetAgentType)
          } else {
            // v1.0版本：直接匹配agent.id
            return agent.id === targetAgentType
          }
        })

        if (targetAgent) {
          form.value.analyst_type = targetAgent.id
          console.log('🔍 [模板调试] 自动选择分析师:', targetAgent.id, '版本:', targetVersion)
        } else {
          console.warn('🔍 [模板调试] 未找到匹配的分析师:', { agentType, targetAgentType, targetVersion })
        }
      }
    }

    if (!form.value.stock.analysis_date) {
      // 默认使用今天的日期，后端会自动查找最近的有效交易日
      const d = new Date()
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      form.value.stock.analysis_date = `${yyyy}-${mm}-${dd}`
    }

    try {
      const defaults = await configApi.getDefaultModels()
      console.log('🔍 [模板调试] 获取到的默认模型配置:', defaults)
      // 模板调试使用快速分析模型，因为是单个agent的快速测试
      form.value.llm.model = defaults.quick_analysis_model || form.value.llm.model
      console.log('🔍 [模板调试] 设置的模型名称:', form.value.llm.model)
    } catch (e) {
      console.error('❌ [模板调试] 获取默认模型失败:', e)
      // ignore, 保持默认值
    }

    try {
      const llmConfigs = await configApi.getLLMConfigs()
      availableModels.value = (llmConfigs as any[]).filter((c: any) => c.enabled)
      console.log('🔍 [模板调试] 可用模型列表:', availableModels.value.map(m => m.model_name))

      // 如果模型名称为空，使用第一个可用模型
      if (!form.value.llm.model && availableModels.value.length > 0) {
        form.value.llm.model = availableModels.value[0].model_name
        console.log('🔍 [模板调试] 模型名称为空，使用第一个可用模型:', form.value.llm.model)
      }

      const info = availableModels.value.find((m: any) => m.model_name === form.value.llm.model)
      if (info) {
        form.value.llm.provider = info.provider
        console.log('🔍 [模板调试] 找到模型信息:', { model: form.value.llm.model, provider: info.provider })
      } else {
        console.warn('⚠️ [模板调试] 未找到模型信息:', form.value.llm.model)
      }
    } catch (e) {
      console.error('❌ [模板调试] 获取LLM配置失败:', e)
      availableModels.value = []
    }
  } catch {}
})

watch(() => form.value.llm.model, (newModel) => {
  const info = availableModels.value.find((m: any) => m.model_name === newModel)
  form.value.llm.provider = info?.provider || 'custom_openai'
})

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.ta-debug { padding: 16px }
.ta-toolbar { margin: 4px 0 8px 0 }
.ta-result { margin-top: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px }
.ta-meta { color: var(--el-text-color-secondary); margin-bottom: 6px }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.meta-info {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 12px;
}

/* Markdown 样式 */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

:deep(.markdown-body h1) {
  font-size: 28px;
  font-weight: 600;
  margin: 24px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}

:deep(.markdown-body h2) {
  font-size: 24px;
  font-weight: 600;
  margin: 20px 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

:deep(.markdown-body h3) {
  font-size: 20px;
  font-weight: 600;
  margin: 16px 0 8px 0;
}

:deep(.markdown-body h4) {
  font-size: 16px;
  font-weight: 600;
  margin: 12px 0 6px 0;
}

:deep(.markdown-body p) {
  margin: 8px 0;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin: 8px 0;
  padding-left: 24px;
}

:deep(.markdown-body li) {
  margin: 4px 0;
}

:deep(.markdown-body table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

:deep(.markdown-body table th),
:deep(.markdown-body table td) {
  border: 1px solid var(--el-border-color-light);
  padding: 8px 12px;
  text-align: left;
}

:deep(.markdown-body table th) {
  background-color: var(--el-fill-color);
  font-weight: 600;
}

:deep(.markdown-body code) {
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

:deep(.markdown-body pre) {
  background-color: var(--el-fill-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 12px 0;
}

:deep(.markdown-body pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
}

:deep(.markdown-body blockquote) {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--el-text-color-secondary);
}

:deep(.markdown-body strong) {
  font-weight: 600;
}

:deep(.markdown-body em) {
  font-style: italic;
}

:deep(.markdown-body a) {
  color: var(--el-color-primary);
  text-decoration: none;
}

:deep(.markdown-body a:hover) {
  text-decoration: underline;
}

:deep(.markdown-body hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-light);
  margin: 16px 0;
}
</style>