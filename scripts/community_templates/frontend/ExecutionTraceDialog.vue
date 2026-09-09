<template>
  <!-- 社区版：执行轨迹为 Pro 能力，此弹窗由发布管道替换为空壳 -->
  <el-dialog
    :model-value="modelValue"
    title="执行轨迹"
    width="720px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-empty description="当前版本不提供执行轨迹查看" />
  </el-dialog>
</template>

<script setup lang="ts">
// 社区版空壳组件：由发布管道生成，保持 UnifiedTaskCenter 引用兼容
defineProps<{ modelValue: boolean; taskId: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: boolean): void }>()
</script>
