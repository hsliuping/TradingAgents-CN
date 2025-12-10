<template>
  <div class="mcp-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">MCP</h1>
        <el-tooltip content="Model Context Protocol" placement="top">
          <el-icon class="help-icon"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <div class="header-right">
        <el-button class="icon-btn" @click="refresh" :loading="mcpStore.loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-dropdown trigger="click" @command="handleCommand">
          <el-button class="add-btn">
            <el-icon><Plus /></el-icon> 添加
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="manual">手动添加</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div class="server-list" v-loading="mcpStore.loading">
      <div 
        v-for="server in mcpStore.connectors" 
        :key="server.name" 
        class="server-item"
        :class="{ expanded: expandedItems.includes(server.name) }"
      >
        <div class="server-header" @click="toggleExpand(server.name)">
          <div class="item-left">
            <el-icon class="expand-arrow"><ArrowRight /></el-icon>
            <div class="server-icon" :style="{ backgroundColor: getIconColor(server.name) }">
              {{ server.name.charAt(0).toUpperCase() }}
            </div>
            <span class="server-name">{{ server.name }}</span>
            <el-tag size="small" :type="getTypeTagType(server.type)" class="type-tag">
              {{ server.type || 'stdio' }}
            </el-tag>
            <el-icon class="status-check" :class="getStatusClass(server.status)">
              <component :is="getStatusIcon(server.status)" />
            </el-icon>
            <span class="status-text" :class="getStatusClass(server.status)">{{ getStatusText(server.status) }}</span>
          </div>
          <div class="item-right">
            <el-switch 
              :model-value="server.enabled" 
              @change="(val) => handleToggle(server.name, val as boolean)"
              @click.stop
              style="--el-switch-on-color: #10b981;"
            />
          </div>
        </div>
        
        <div v-show="expandedItems.includes(server.name)" class="server-details">
          <div class="details-content">
            <!-- 健康信息 -->
            <div v-if="server.healthInfo" class="health-info">
              <div class="health-item">
                <span class="health-label">状态:</span>
                <span :class="getStatusClass(server.healthInfo.status)">{{ server.healthInfo.status }}</span>
              </div>
              <div v-if="server.healthInfo.latencyMs" class="health-item">
                <span class="health-label">延迟:</span>
                <span>{{ server.healthInfo.latencyMs.toFixed(0) }}ms</span>
              </div>
              <div v-if="server.healthInfo.lastCheck" class="health-item">
                <span class="health-label">最后检查:</span>
                <span>{{ formatTime(server.healthInfo.lastCheck) }}</span>
              </div>
              <div v-if="server.healthInfo.error" class="health-item error">
                <span class="health-label">错误:</span>
                <span>{{ server.healthInfo.error }}</span>
              </div>
            </div>
            <div class="code-block">
              <pre>{{ JSON.stringify(server.config, null, 2) }}</pre>
            </div>
            <div class="actions-row">
              <el-button type="danger" size="small" text bg @click="handleDelete(server.name)">删除配置</el-button>
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="mcpStore.connectors.length === 0 && !mcpStore.loading" class="empty-state-card">
        <el-icon class="empty-icon"><Tools /></el-icon>
        <p class="empty-text">暂无 MCP Servers</p>
        <div class="empty-actions">
          <el-button type="primary" bg text class="action-btn" @click="handleCommand('manual')">手动添加</el-button>
        </div>
      </div>
    </div>

    <!-- 手动配置 Dialog -->
    <el-dialog
      v-model="dialogVisible"
      title="手动配置"
      width="600px"
      class="mcp-config-dialog"
      :close-on-click-modal="false"
      align-center
    >
      <div class="dialog-body">
        <p class="dialog-desc">
          请从 MCP Servers 的介绍页面复制配置 JSON (优先使用 NPX 或 UVX 配置)，并粘贴到输入框中。
        </p>
        
        <div class="editor-container">
          <el-input
            v-model="jsonConfig"
            type="textarea"
            :rows="15"
            placeholder="// 示例:
{
  &quot;mcpServers&quot;: {
    &quot;example-server&quot;: {
      &quot;command&quot;: &quot;npx&quot;,
      &quot;args&quot;: [
        &quot;-y&quot;,
        &quot;mcp-server-example&quot;
      ]
    }
  }
}"
            class="json-editor"
          />
        </div>
        
        <div class="dialog-warning">
          <el-icon><Warning /></el-icon> 配置前请确认来源，甄别风险
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmAdd" :loading="mcpStore.saving">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { 
  QuestionFilled, 
  Refresh, 
  Plus, 
  ArrowDown, 
  ArrowRight, 
  Check, 
  Warning,
  Tools,
  Close,
  Loading,
  QuestionFilled as Unknown
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useMCPStore } from '@/stores/mcp'

const mcpStore = useMCPStore()
const expandedItems = ref<string[]>([])
const dialogVisible = ref(false)
const jsonConfig = ref('')

const refresh = () => {
  mcpStore.fetchConnectors()
}

const handleCommand = (command: string) => {
  if (command === 'manual') {
    jsonConfig.value = ''
    dialogVisible.value = true
  }
}

const toggleExpand = (name: string) => {
  const index = expandedItems.value.indexOf(name)
  if (index > -1) {
    expandedItems.value.splice(index, 1)
  } else {
    expandedItems.value.push(name)
  }
}

const getIconColor = (name: string) => {
  const colors = ['#3b82f6', '#eab308', '#a855f7', '#06b6d4', '#ec4899', '#f97316']
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

const getStatusClass = (status: string) => {
  switch (status) {
    case 'healthy': return 'success'
    case 'degraded': return 'warning'
    case 'unreachable': return 'danger'
    case 'stopped': return 'info'
    default: return 'unknown'
  }
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'healthy': return Check
    case 'degraded': return Warning
    case 'unreachable': return Close
    case 'stopped': return Close
    default: return Unknown
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'healthy': return '健康'
    case 'degraded': return '降级'
    case 'unreachable': return '不可达'
    case 'stopped': return '已停止'
    case 'unknown': return '未知'
    default: return status
  }
}

const getTypeTagType = (type: string) => {
  switch (type) {
    case 'streamable-http': return 'success'
    case 'http': return 'warning'
    case 'stdio': return 'info'
    default: return 'info'
  }
}

const formatTime = (isoString: string) => {
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString()
  } catch {
    return isoString
  }
}

const handleToggle = (name: string, val: boolean) => {
  mcpStore.toggleConnector(name, val)
}

const confirmAdd = async () => {
  if (!jsonConfig.value.trim()) return
  
  let config
  try {
    config = JSON.parse(jsonConfig.value)
  } catch (e) {
    ElMessage.error('JSON 解析失败，请检查格式是否正确')
    return
  }
  
  if (!config.mcpServers || typeof config.mcpServers !== 'object') {
    ElMessage.error('无效的配置格式，必须包含 "mcpServers" 对象')
    return
  }
  
  try {
    await mcpStore.batchUpdate(config)
    dialogVisible.value = false
    ElMessage.success('添加成功')
  } catch (e: any) {
    const errorMsg = e?.response?.data?.detail || e?.message || '更新配置失败'
    ElMessage.error(`配置更新失败: ${errorMsg}`)
  }
}

const handleDelete = (name: string) => {
  ElMessageBox.confirm(`确定要删除 ${name} 吗？`, '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await mcpStore.deleteConnector(name)
  })
}

onMounted(() => {
  mcpStore.fetchConnectors()
})
</script>

<style scoped>
.mcp-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}

.help-icon {
  color: var(--el-text-color-secondary);
  font-size: 16px;
  cursor: pointer;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-btn {
  background: transparent;
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-regular);
}

.add-btn {
  background-color: #f3f4f6;
  border: none;
  color: #1f2937;
}

/* Dark mode adjustments for buttons if needed */
:deep(.dark) .add-btn {
  background-color: #374151;
  color: #e5e7eb;
}

.server-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.server-item {
  background-color: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-darker);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.server-item:hover {
  border-color: var(--el-border-color-light);
}

.server-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  cursor: pointer;
  user-select: none;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.expand-arrow {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transition: transform 0.2s;
}

.server-item.expanded .expand-arrow {
  transform: rotate(90deg);
}

.server-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: white;
  font-size: 16px;
}

.server-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.status-check {
  font-size: 12px;
  margin-left: 4px;
}

.status-check.success {
  color: #10b981;
}

.status-check.warning {
  color: #eab308;
}

.status-check.danger {
  color: #ef4444;
}

.status-check.info {
  color: #6b7280;
}

.status-check.unknown {
  color: #9ca3af;
}

.status-text {
  font-size: 12px;
  margin-left: 4px;
}

.status-text.success {
  color: #10b981;
}

.status-text.warning {
  color: #eab308;
}

.status-text.danger {
  color: #ef4444;
}

.status-text.info {
  color: #6b7280;
}

.type-tag {
  margin-left: 8px;
}

.health-info {
  background-color: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.health-label {
  color: var(--el-text-color-secondary);
}

.health-item.error {
  color: #ef4444;
  width: 100%;
}

.server-details {
  border-top: 1px solid var(--el-border-color-darker);
  background-color: var(--el-fill-color-darker);
  padding: 16px;
}

.code-block {
  background-color: #1e1e1e;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  max-height: 300px;
  overflow: auto;
}

.code-block pre {
  margin: 0;
  color: #d4d4d4;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.actions-row {
  display: flex;
  justify-content: flex-end;
}

.empty-state-card {
  background-color: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-darker);
  border-radius: 8px;
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: #3b82f6;
  margin-bottom: 16px;
}

.empty-text {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin: 0 0 24px 0;
}

.empty-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  background-color: var(--el-fill-color-dark);
  border-color: var(--el-border-color-darker);
  color: var(--el-text-color-primary);
}

.action-btn:hover {
  background-color: var(--el-fill-color-light);
}

/* Dialog Styles */
.dialog-desc {
  margin-bottom: 16px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.5;
}

.editor-container {
  margin-bottom: 16px;
}

:deep(.json-editor .el-textarea__inner) {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  background-color: var(--el-fill-color-darker);
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.dialog-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #eab308;
  font-size: 12px;
}
</style>
