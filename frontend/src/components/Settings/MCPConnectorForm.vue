<template>
  <el-drawer
    :model-value="visible"
    :title="isEdit ? '编辑 MCP 连接器' : '新增 MCP 连接器'"
    size="520px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="110px"
      status-icon
      @keyup.enter.native="handleSubmit"
    >
      <el-form-item label="名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="如：内部 MCP 服务"
          maxlength="64"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="Endpoint" prop="endpoint">
        <el-input
          v-model="form.endpoint"
          placeholder="https://mcp.example.com"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="API Key">
        <el-input
          v-model="form.api_key"
          placeholder="可选，若需要认证"
          type="password"
          show-password
          maxlength="200"
        />
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="补充用途、环境等信息"
          maxlength="240"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="允许不安全证书">
        <el-switch v-model="form.insecure" />
        <span class="helper-text">仅在自签证书场景下启用</span>
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? '保存修改' : '创建' }}
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { MCPConnector, MCPConnectorPayload } from '@/types/mcp'

const props = defineProps<{
  visible: boolean
  connector?: MCPConnector | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: MCPConnectorPayload): void
}>()

const formRef = ref<FormInstance>()
const form = reactive<MCPConnectorPayload>({
  name: '',
  endpoint: '',
  api_key: '',
  description: '',
  insecure: false,
  enabled: true
})

const rules: FormRules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { min: 2, max: 64, message: '长度 2-64 字符', trigger: 'blur' }
  ],
  endpoint: [
    { required: true, message: '请输入 Endpoint', trigger: 'blur' },
    {
      type: 'url',
      message: '请输入有效的 URL（需含协议）',
      trigger: ['blur', 'change']
    }
  ]
}

const isEdit = computed(() => !!props.connector)

watch(
  () => props.connector,
  (val) => {
    if (val) {
      form.name = val.name
      form.endpoint = val.endpoint
      form.description = val.description || ''
      form.insecure = !!val.insecure
      form.api_key = ''
      form.enabled = val.enabled
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

const resetForm = () => {
  form.name = ''
  form.endpoint = ''
  form.api_key = ''
  form.description = ''
  form.insecure = false
  form.enabled = true
  formRef.value?.clearValidate()
}

const handleClose = () => {
  resetForm()
  emit('close')
}

const handleSubmit = () => {
  formRef.value?.validate((valid) => {
    if (!valid) return
    emit('submit', { ...form })
  })
}
</script>

<style scoped>
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.helper-text {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
