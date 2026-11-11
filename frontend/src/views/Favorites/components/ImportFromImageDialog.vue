<template>
  <!-- 社区版：图片导入自选股为 Pro 能力，此弹窗由发布管道替换为空壳 -->
  <el-dialog
    :model-value="modelValue"
    title="从图片导入自选股"
    width="720px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-empty description="当前版本不提供图片导入自选股功能" />
  </el-dialog>
</template>

<script setup lang="ts">
// 社区版空壳组件：由发布管道生成，保持 Favorites 页面引用兼容
defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'imported', result: { added: number; skipped: number; failed: number }): void
}>()
</script>
