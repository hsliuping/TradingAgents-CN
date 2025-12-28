<template>
  <el-dialog v-model="visible" title="任务结果" width="60%">
    <div v-if="result">
      <!-- 推荐/建议 -->
      <div v-if="result.recommendation">
        <h4>建议</h4>
        <div class="markdown-content" v-html="renderMarkdown(result.recommendation)"></div>
      </div>
      
      <!-- 多空辩论结论 (如果无推荐) -->
      <div v-else-if="result.debate_summary">
        <h4>多空辩论结论</h4>
        <div class="markdown-content" v-html="renderMarkdown(result.debate_summary.conclusion || '无')"></div>
      </div>

      <!-- 如果两者都没有 -->
      <div v-if="!result.recommendation && !result.debate_summary">
        <h4>建议</h4>
        <div class="markdown-content">暂无建议</div>
      </div>

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
import { marked } from 'marked'

const props = defineProps<{ modelValue: boolean; result: any }>()
const emit = defineEmits(['update:modelValue','close','view-report'])

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v)
})

marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (s: string) => { try { return marked.parse(s||'') as string } catch { return s } }
</script>

