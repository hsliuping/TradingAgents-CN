<template>
  <div class="onboarding">
    <!-- 已完成：配置摘要 -->
    <el-result
      v-if="done"
      icon="success"
      :title="result?.message || '接入完成'"
      sub-title="大模型已就绪，可以直接在分析页面选择使用"
    >
      <template #extra>
        <div class="summary" v-if="result">
          <div class="summary-grid">
            <div class="summary-item">
              <span class="k">接入厂家</span>
              <span class="v">{{ result.provider?.display_name || result.provider?.name }}</span>
            </div>
            <div class="summary-item">
              <span class="k">导入模型</span>
              <span class="v">{{ result.imported }} 个<em v-if="result.skipped">，{{ result.skipped }} 个已存在</em></span>
            </div>
            <div class="summary-item">
              <span class="k">默认可用</span>
              <span class="v">{{ result.model_count }} 个</span>
            </div>
          </div>
        </div>
        <div class="btns">
          <el-button type="primary" @click="goAnalysis">去分析页面使用</el-button>
          <el-button @click="reset">继续接入其他厂家</el-button>
        </div>
      </template>
    </el-result>

    <!-- 接入表单 -->
    <el-card v-else class="onboard-card" shadow="never">
      <template #header>
        <div class="card-head">
          <el-icon class="head-icon"><Guide /></el-icon>
          <div>
            <div class="head-title">接入大模型服务</div>
            <div class="head-sub">填入 API Key 即可自动拉取模型并配置默认模型，无需在多个页面间跳转</div>
          </div>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="onboard-form"
      >
        <div class="form-section">
          <div class="section-title">
            <span class="dot">1</span> 填写 API 信息
          </div>

          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="服务名称" prop="name">
                <el-input
                  v-model="form.name"
                  placeholder="如 sensenova、custom"
                  maxlength="64"
                  show-word-limit
                  clearable
                />
                <div class="hint">唯一标识，仅小写字母、数字、下划线、连字符</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="显示名称" prop="display_name">
                <el-input v-model="form.display_name" placeholder="如 SenseNova" clearable />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="API 基础地址" prop="base_url">
                <el-input v-model="form.base_url" placeholder="https://token.sensenova.cn/v1" clearable>
                  <template #append><el-icon><Link /></el-icon></template>
                </el-input>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="API Key" prop="api_key">
            <el-input
              v-model="form.api_key"
              type="password"
              show-password
              :placeholder="hasExistingKey ? '留空 = 沿用该厂家已保存的密钥' : 'sk-...'"
              clearable
              class="key-input"
            >
              <template #prefix><el-icon><Key /></el-icon></template>
            </el-input>
            <div class="hint" v-if="hasExistingKey">
              已检测到该名称的厂家保存过密钥，留空即可复用，无需重复填写
            </div>
          </el-form-item>
        </div>

        <div class="form-section">
          <div class="section-title">
            <span class="dot">2</span> 选择默认模型（可选）
            <el-button link type="primary" class="autofill-btn" @click="autoFillDefaults">
              智能推荐
            </el-button>
          </div>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="快速分析模型">
                <el-select
                  v-model="form.quick_analysis_model"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="下拉选择或输入模型名"
                  style="width: 100%"
                >
                  <el-option
                    v-for="m in fetchedModels"
                    :key="m"
                    :value="m"
                    :label="m"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="深度分析模型">
                <el-select
                  v-model="form.deep_analysis_model"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="下拉选择或输入模型名"
                  style="width: 100%"
                >
                  <el-option
                    v-for="m in fetchedModels"
                    :key="m"
                    :value="m"
                    :label="m"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-alert
            v-if="fetchedModels.length > 0"
            type="success"
            :closable="false"
            class="fetch-alert"
          >
            <div class="alert-body">
              <el-icon><CircleCheck /></el-icon>
              <span>已连通，拉取到 <b>{{ fetchedModels.length }}</b> 个可用模型，已全部纳入默认导入</span>
            </div>
          </el-alert>

          <el-alert
            v-else-if="fetchState === 'error'"
            type="warning"
            :closable="false"
            class="fetch-alert"
          >
            <div class="alert-body">
              <el-icon><Warning /></el-icon>
              <span>{{ fetchError }}。仍可继续提交，将在保存后重试拉取。</span>
            </div>
          </el-alert>
        </div>
      </el-form>

      <div class="form-actions">
        <el-button :loading="fetchLoading" @click="handleTestConnection">
          <el-icon v-if="!fetchLoading"><Connection /></el-icon>
          {{ fetchLoading ? '拉取中...' : (fetchedModels.length > 0 ? '重新测试连接' : '测试连接并拉取模型') }}
        </el-button>
        <div class="spacer"></div>
        <el-button @click="reset" :disabled="submitting">重置</el-button>
        <el-button type="primary" :loading="submitting" @click="handleOnboard">
          <el-icon v-if="!submitting"><Guide /></el-icon>
          {{ submitting ? '正在接入...' : '开始接入' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  Guide, Key, Link, Connection, CircleCheck, Warning
} from '@element-plus/icons-vue'
import { configApi } from '@/api/config'

const router = useRouter()
const formRef = ref<FormInstance>()
const done = ref(false)
const submitting = ref(false)
const fetchLoading = ref(false)
const fetchState = ref<'idle' | 'loading' | 'ok' | 'error'>('idle')
const fetchError = ref('')
const fetchedModels = ref<string[]>([])
const result = ref<any>(null)

const NAME_RE = /^[a-z0-9_-]+$/

const form = reactive({
  name: '',
  display_name: '',
  base_url: '',
  api_key: '',
  quick_analysis_model: '',
  deep_analysis_model: '',
})

// 同名厂家是否已保存过 API Key。
// 注意：后端 GET /llm/providers 返回的 api_key 永远脱敏（如 "sk-EjZ...MTTgIR"），
// 因此不能回读预填到表单——否则用户不改动直接点「开始接入」，
// 就会把脱敏字符串当成新 Key 发给后端并覆盖掉真实密钥。
const hasExistingKey = ref(false)
const existingProviderName = ref('')

const rules: FormRules = {
  name: [
    { required: true, message: '请输入服务名称', trigger: 'blur' },
    { pattern: NAME_RE, message: '仅允许小写字母、数字、下划线、连字符', trigger: 'blur' },
  ],
  base_url: [
    { required: true, message: '请输入 API 基础地址', trigger: 'blur' },
  ],
  api_key: [
    // 留空合法：同名厂家已保存过密钥时，后端会复用已保存的真实值
    { min: 8, message: 'API Key 长度不足', trigger: 'blur' },
  ],
}

const defaultBaseUrl = computed(() => form.base_url.replace(/\/+$/, ''))

onMounted(async () => {
  // 仅预填「服务名称 / 显示名称 / API 基础地址」这三类非敏感信息，
  // 让用户从已有的配置改起（改名即新建）。
  // API Key 绝不回读：后端返回的 api_key 永远是脱敏值（如 "sk-EjZ...MTTgIR"），
  // 回读进表单会被当成新 Key 提交，覆盖掉真实密钥。
  try {
    const providers = await configApi.getLLMProviders()
    const list = (providers || []) as Array<any>
    const withKey = list.find(p => p.api_key && String(p.api_key).trim())
    if (withKey && !form.name) {
      form.name = withKey.name
      form.display_name = withKey.display_name || withKey.name
      form.base_url = withKey.default_base_url || ''
      hasExistingKey.value = true
      existingProviderName.value = withKey.name
    }
  } catch {
    // 忽略：预填失败不影响手动填写
  }
})

/**
 * 测试连接并拉取模型列表（不保存厂家）。
 * 通过 fetch-models 的 override 参数直连用户刚填的 Key 与地址，
 * 这样「开始接入」前的任何失败都不会留下半成品配置。
 */
async function handleTestConnection() {
  if (!form.base_url) {
    ElMessage.warning('请填写 API 基础地址')
    return
  }
  // 复用路径的前提：所选名称的厂家已保存过密钥
  if (!form.api_key && !existingProviderName.value) {
    ElMessage.warning('请填写 API Key（或改用已保存过密钥的厂家名称）')
    return
  }

  fetchLoading.value = true
  fetchState.value = 'loading'
  fetchError.value = ''
  fetchedModels.value = []

  try {
    // 两条路径：
    //  - 填了新 Key：用 override 参数直连，无需厂家先落库
    //  - 留空：走已保存的厂家记录，复用其密钥（此时不应带上脱敏值）
    const useOverride = !!form.api_key
    const res = await configApi.fetchProviderModels(
      useOverride ? (form.name || '__test__') : existingProviderName.value,
      useOverride
        ? { api_key: form.api_key, base_url: defaultBaseUrl.value }
        : undefined
    )
    if (res.success) {
      fetchedModels.value = (res.models || []).map(m => m.name || m.id).filter(Boolean)
      fetchState.value = 'ok'
      if (fetchedModels.value.length === 0) {
        fetchError.value = 'API 未返回任何模型'
      } else {
        ElMessage.success(`连通成功，拉取到 ${fetchedModels.value.length} 个模型`)
      }
    } else {
      throw new Error(res.message || '连接失败')
    }
  } catch (e: any) {
    fetchState.value = 'error'
    fetchError.value = e?.message || '连接失败'
    ElMessage.warning(`测试失败：${fetchError.value}`)
  } finally {
    fetchLoading.value = false
  }
}

/** 智能推荐：优先选名称最短（通常是最稳定的通用款）作为快速分析，
 *  选含 pro/large/max/plus 等字样（通常是更强款）作为深度分析。 */
function autoFillDefaults() {
  if (fetchedModels.value.length === 0) {
    ElMessage.info('请先测试连接以拉取模型列表')
    return
  }
  const list = [...fetchedModels.value]
  // 快速分析：最短名（一般是最轻量的通用款）
  list.sort((a, b) => a.length - b.length)
  form.quick_analysis_model = list[0] || ''
  // 深度分析：带强项关键词的优先，否则最长名
  const strong = list.filter(m => /pro|max|large|plus|ultra|high|ultra/i.test(m))
  const byLen = [...list].sort((a, b) => b.length - a.length)
  form.deep_analysis_model = (strong[0] || byLen[0] || '')
  if (!form.quick_analysis_model && !form.deep_analysis_model) {
    ElMessage.warning('未识别到可推荐的模型')
    return
  }
  ElMessage.success('已根据模型命名自动推荐默认模型')
}

/** 开始接入：一次性完成 保存厂家 → 拉模型 → 导入配置 → 设默认 */
async function handleOnboard() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const res: any = await configApi.onboardLLMProvider({
        name: form.name,
        display_name: form.display_name || form.name,
        // 留空 = 沿用同名厂家已保存的密钥；填了则更新
        api_key: form.api_key || undefined,
        base_url: defaultBaseUrl.value,
        quick_analysis_model: form.quick_analysis_model || undefined,
        deep_analysis_model: form.deep_analysis_model || undefined,
        // 不传 models 字段：后端默认导入拉取到的全部模型
      })
      if (!res.success) {
        throw new Error(res.message || '接入失败')
      }
      result.value = res
      done.value = true
      ElMessage.success(res.message || '接入完成')
    } catch (e: any) {
      ElMessage.error(`接入失败：${e?.message || e}`)
    } finally {
      submitting.value = false
    }
  })
}

function goAnalysis() {
  router.push('/analysis/single')
}

function reset() {
  done.value = false
  result.value = null
  fetchedModels.value = []
  fetchState.value = 'idle'
  fetchError.value = ''
  form.quick_analysis_model = ''
  form.deep_analysis_model = ''
  form.api_key = ''
}
</script>

<style scoped>
.onboarding {
  max-width: 960px;
  margin: 0 auto;
}

.onboard-card {
  border: none;
  border-radius: 12px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.head-icon {
  font-size: 34px;
  color: var(--el-color-primary);
}

.head-title {
  font-size: 18px;
  font-weight: 600;
}

.head-sub {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.onboard-form {
  padding-top: 4px;
}

.form-section {
  padding: 16px 16px 8px;
  margin-bottom: 8px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 14px;
}

.dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
}

.autofill-btn {
  margin-left: auto;
}

.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  margin-top: 2px;
}

.key-input :deep(.el-input__wrapper) {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
}

.fetch-alert {
  margin-bottom: 8px;
}

.alert-body {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.form-actions .spacer {
  flex: 1;
}

.summary-grid {
  display: flex;
  gap: 40px;
  justify-content: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.summary-item .k {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.summary-item .v {
  font-size: 22px;
  font-weight: 600;
}

.summary-item .v em {
  font-style: normal;
  font-size: 13px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
  margin-left: 6px;
}

.btns {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
