<template>
  <div class="agent-card">
    <div class="card-header">
      <div class="header-main">
        <div class="agent-icon" :class="agent.type">
          {{ agent.name.charAt(0).toUpperCase() }}
        </div>
        <div class="agent-info">
          <div class="agent-name">{{ agent.name }}</div>
          <div class="agent-id">{{ agent.id }}</div>
        </div>
      </div>
      <div class="header-status">
        <el-tag :type="agent.enabled ? 'success' : 'info'" size="small" effect="plain">
          {{ agent.enabled ? '启用' : '禁用' }}
        </el-tag>
      </div>
    </div>
    
    <div class="card-body">
      <p class="description">{{ agent.description || '暂无描述' }}</p>
      <div class="tags">
        <el-tag size="small" type="info" effect="light">{{ agent.type }}</el-tag>
        <el-tag v-if="!agent.is_system" size="small" type="warning" effect="light">自定义</el-tag>
      </div>
    </div>
    
    <div class="card-footer">
      <el-button link type="primary" @click="$emit('edit', agent)">配置</el-button>
      <el-button link :type="agent.is_system ? 'warning' : 'danger'" @click="$emit('delete', agent)">
        {{ agent.is_system ? '重置' : '删除' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentConfig } from '@/api/agents'

defineProps<{
  agent: AgentConfig
}>()

defineEmits<{
  (e: 'edit', agent: AgentConfig): void
  (e: 'delete', agent: AgentConfig): void
}>()
</script>

<style scoped>
.agent-card {
  background-color: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  transition: all 0.2s;
  height: 100%;
}

.agent-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--el-box-shadow-light);
  border-color: var(--el-color-primary-light-5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.header-main {
  display: flex;
  gap: 12px;
}

.agent-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 18px;
  flex-shrink: 0;
}

/* Different colors for types */
.agent-icon.market { background-color: #e0f2fe; color: #0284c7; }
.agent-icon.social { background-color: #fce7f3; color: #db2777; }
.agent-icon.risk_manager { background-color: #fef3c7; color: #d97706; }
.agent-icon.trader { background-color: #dcfce7; color: #16a34a; }

.agent-info {
  overflow: hidden;
}

.agent-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-id {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.card-body {
  flex: 1;
  margin-bottom: 16px;
}

.description {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  margin: 0 0 12px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tags {
  display: flex;
  gap: 8px;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 12px;
  gap: 12px;
}
</style>
