<template>
  <el-dialog v-model="visible" title="任务结果" width="60%">
    <div v-if="result">
      <h4>建议</h4>
      <div class="markdown-content" v-html="renderMarkdown(result.recommendation || '无')"></div>
      <h4 style="margin-top: 16px;">摘要</h4>
      <div class="markdown-content" v-html="renderMarkdown(result.summary || '无')"></div>
    </div>
    <template #footer>
      <el-button @click="emit('close')">关闭</el-button>
      <el-button type="primary" @click="emit('view-report')">查看报告详情</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'

const props = defineProps<{ modelValue: boolean; result: any }>()
const emit = defineEmits(['update:modelValue','close','view-report'])

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v)
})

// marked 配置已由 @/utils/markdown 统一管理
const renderMarkdown = (s: string) => { try { return safeMarkdown(s||'') } catch { return s } }
</script>

