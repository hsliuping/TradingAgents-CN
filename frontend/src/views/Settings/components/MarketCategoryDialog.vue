<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑市场分类' : '添加市场分类'"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="100px"
      label-position="left"
    >
      <el-form-item label="分类ID" prop="id">
        <el-input
          v-model="formData.id"
          placeholder="请输入分类ID（英文）"
          :disabled="isEdit"
        />
        <div class="form-help">用于系统内部标识，建议使用英文</div>
      </el-form-item>

      <el-form-item label="分类名称" prop="name">
        <el-input
          v-model="formData.name"
          placeholder="请输入分类名称"
          :disabled="isEdit"
        />
        <div class="form-help">系统内部名称，通常与ID相同</div>
      </el-form-item>

      <el-form-item label="显示名称" prop="display_name">
        <el-input
          v-model="formData.display_name"
          placeholder="请输入显示名称"
        />
        <div class="form-help">用户界面显示的名称</div>
      </el-form-item>

      <el-form-item label="排序顺序" prop="sort_order">
        <el-input-number
          v-model="formData.sort_order"
          :min="1"
          :max="100"
          controls-position="right"
          style="width: 200px"
        />
        <div class="form-help">数值越小排序越靠前</div>
      </el-form-item>

      <el-form-item label="启用状态">
        <el-switch v-model="formData.enabled" />
      </el-form-item>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="formData.description"
          type="textarea"
          :rows="3"
          placeholder="请输入分类描述"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { configApi, type MarketCategory } from '@/api/config'

// Props
interface Props {
  visible: boolean
  category?: MarketCategory | null
}

const props = withDefaults(defineProps<Props>(), {
  category: null
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'success': []
}>()

// Refs
const formRef = ref<FormInstance>()
const loading = ref(false)

// Computed
const isEdit = computed(() => !!props.category)

// 表单数据
const defaultFormData = {
  id: '',
  name: '',
  display_name: '',
  description: '',
  enabled: true,
  sort_order: 1
}

const formData = ref({ ...defaultFormData })

// 表单验证规则
const rules: FormRules = {
  id: [
    { required: true, message: '请输入分类ID', trigger: 'blur' },
    { pattern: /^[a-z_]+$/, message: '分类ID只能包含小写字母和下划线', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  sort_order: [{ required: true, message: '请输入排序顺序', trigger: 'blur' }]
}

// 监听分类变化
watch(
  () => props.category,
  (category) => {
    if (category) {
      formData.value = { ...category }
    } else {
      formData.value = { ...defaultFormData }
    }
  },
  { immediate: true }
)

// 监听visible变化
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      if (props.category) {
        formData.value = { ...props.category }
      } else {
        formData.value = { ...defaultFormData }
      }
    }
  }
)

// 处理关闭
const handleClose = () => {
  emit('update:visible', false)
}

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true

    if (isEdit.value) {
      // 更新分类
      await configApi.updateMarketCategory(formData.value.id, formData.value)
      ElMessage.success('市场分类更新成功')
    } else {
      // 创建分类
      await configApi.addMarketCategory(formData.value)
      ElMessage.success('市场分类创建成功')
    }

    emit('success')
    handleClose()
  } catch (error) {
    console.error('保存市场分类失败:', error)
    ElMessage.error('保存市场分类失败')
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.form-help {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

.dialog-footer {
  text-align: right;
}
</style>
