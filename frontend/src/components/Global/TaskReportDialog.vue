<template>
  <el-dialog v-model="visible" title="报告详情" width="70%">
    <template v-if="sections && sections.length > 0">
      <el-tabs v-model="active">
        <el-tab-pane v-for="(sec, idx) in sections" :key="sec.key || idx" :label="sec.title" :name="String(idx)">
          <div v-if="typeof sec.content === 'string'" class="markdown-content" v-html="renderMarkdown(sec.content)"></div>
          <div v-else class="json-content"><pre>{{ JSON.stringify(sec.content, null, 2) }}</pre></div>
        </el-tab-pane>
      </el-tabs>
    </template>
    <template v-else>
      <el-empty description="暂无内容" />
    </template>
    <template #footer>
      <el-button @click="emit('close')">关闭</el-button>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
const props = defineProps<{ modelValue: boolean; sections: Array<{ key?: string; title: string; content: any }> }>()
const emit = defineEmits(['update:modelValue','close'])
const visible = computed({ get: () => props.modelValue, set: (v: boolean) => emit('update:modelValue', v) })
const active = ref('0')
marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (s: string) => { try { return marked.parse(s||'') as string } catch { return s } }
</script>

