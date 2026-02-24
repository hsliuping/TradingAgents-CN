<template>
  <div class="mcp-servers-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><Connection /></el-icon>
          MCP 服务器
        </h1>
        <span class="subtitle">配置外部 MCP 服务器，工具可被 Agent 和 Skill 直接调用</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          添加 MCP 服务器
        </el-button>
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 服务器列表 -->
    <el-table v-loading="loading" :data="servers" style="width: 100%" border stripe>
      <el-table-column prop="name" label="服务器名称" min-width="180">
        <template #default="{ row }">
          <div class="server-name">
            <span :class="['status-dot', row.status]"></span>
            <span class="name-text">{{ row.name }}</span>
          </div>
          <div v-if="row.last_error" class="error-hint">{{ row.last_error }}</div>
        </template>
      </el-table-column>

      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />

      <el-table-column prop="transport_type" label="传输方式" width="140">
        <template #default="{ row }">
          <el-tag :type="getTransportTag(row.transport_type)">{{ getTransportLabel(row.transport_type) }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusTag(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="工具数" width="80" align="center">
        <template #default="{ row }">
          <el-badge :value="row.discovered_tools?.length || 0" type="primary" />
        </template>
      </el-table-column>

      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.is_enabled"
            :loading="togglingId === row.server_id"
            @change="(val: boolean) => handleToggle(row, val)"
            size="small"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleTest(row)" :loading="testingId === row.server_id">测试</el-button>
          <el-button type="success" link @click="handleDiscover(row)" :loading="discoveringId === row.server_id">发现工具</el-button>
          <el-button type="primary" link @click="showTools(row)">工具列表</el-button>
          <el-button type="primary" link @click="showEditDialog(row)">编辑</el-button>
          <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态 -->
    <el-empty v-if="!loading && servers.length === 0" description="暂无 MCP 服务器，点击「添加 MCP 服务器」开始配置">
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        添加 MCP 服务器
      </el-button>
    </el-empty>

    <!-- 工具列表对话框 -->
    <el-dialog v-model="toolsVisible" :title="`工具列表 — ${toolsServer?.name}`" width="700px" destroy-on-close>
      <div v-if="toolsServer?.discovered_tools?.length">
        <el-table :data="toolsServer.discovered_tools" size="small" border>
          <el-table-column prop="name" label="工具名称" width="200" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column label="Tool ID" width="240">
            <template #default="{ row }">
              <el-tag size="small" type="info">mcp_{{ toolsServer!.server_id }}_{{ row.name }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="尚未发现工具，请先点击「发现工具」" />
      <template #footer>
        <el-button @click="toolsVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formMode === 'create' ? '添加 MCP 服务器' : '编辑 MCP 服务器'"
      width="640px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" ref="formRef">
        <el-form-item label="服务器 ID" v-if="formMode === 'create'">
          <el-input v-model="form.server_id" placeholder="留空自动生成" clearable />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：AkShare MCP" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="服务器功能说明" />
        </el-form-item>
        <el-form-item label="传输方式">
          <el-radio-group v-model="form.transport_type">
            <el-radio-button value="sse">SSE</el-radio-button>
            <el-radio-button value="streamable_http">Streamable HTTP</el-radio-button>
            <el-radio-button value="stdio">stdio（本地）</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- SSE / Streamable HTTP 配置 -->
        <template v-if="form.transport_type === 'sse' || form.transport_type === 'streamable_http'">
          <el-form-item label="服务器 URL" required>
            <el-input v-model="form.connection.url" placeholder="https://your-mcp-server.com/sse" />
          </el-form-item>
          <el-form-item label="请求头">
            <div class="kv-list">
              <div v-for="(item, idx) in form.connection.headersList" :key="idx" class="kv-row">
                <el-input v-model="item.key" placeholder="Header-Key" style="width: 180px" />
                <el-input v-model="item.value" placeholder="value" style="flex: 1; margin: 0 8px" />
                <el-button type="danger" link @click="removeHeader(idx)"><el-icon><Delete /></el-icon></el-button>
              </div>
              <el-button link type="primary" @click="addHeader"><el-icon><Plus /></el-icon> 添加请求头</el-button>
            </div>
          </el-form-item>
        </template>

        <!-- stdio 配置 -->
        <template v-else>
          <el-form-item label="命令" required>
            <el-input v-model="form.connection.command" placeholder="如：python 或 uvx" />
          </el-form-item>
          <el-form-item label="参数">
            <el-input v-model="form.connection.argsStr" type="textarea" :rows="2" placeholder="每行一个参数，如：&#10;-m&#10;akshare_mcp" />
          </el-form-item>
          <el-form-item label="环境变量">
            <div class="kv-list">
              <div v-for="(item, idx) in form.connection.envList" :key="idx" class="kv-row">
                <el-input v-model="item.key" placeholder="ENV_KEY" style="width: 180px" />
                <el-input v-model="item.value" placeholder="value" style="flex: 1; margin: 0 8px" />
                <el-button type="danger" link @click="removeEnv(idx)"><el-icon><Delete /></el-icon></el-button>
              </div>
              <el-button link type="primary" @click="addEnv"><el-icon><Plus /></el-icon> 添加环境变量</el-button>
            </div>
          </el-form-item>
        </template>

        <el-form-item label="创建后启用" v-if="formMode === 'create'">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Plus, Refresh, Delete } from '@element-plus/icons-vue'
import { mcpApi, type MCPServer } from '@/api/mcp'

const loading = ref(false)
const servers = ref<MCPServer[]>([])
const testingId = ref('')
const discoveringId = ref('')
const togglingId = ref('')

const toolsVisible = ref(false)
const toolsServer = ref<MCPServer | null>(null)

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formLoading = ref(false)
const editingId = ref('')

interface KvItem { key: string; value: string }
interface ConnState { url: string; command: string; argsStr: string; headersList: KvItem[]; envList: KvItem[] }
interface FormState {
  server_id: string; name: string; description: string
  transport_type: 'sse' | 'streamable_http' | 'stdio'
  is_enabled: boolean; connection: ConnState
}
const form = reactive<FormState>({
  server_id: '', name: '', description: '', transport_type: 'sse', is_enabled: false,
  connection: { url: '', command: '', argsStr: '', headersList: [], envList: [] },
})

const loadData = async () => {
  loading.value = true
  try { servers.value = (await mcpApi.listServers()).servers || [] }
  catch { ElMessage.error('加载 MCP 服务器失败') }
  finally { loading.value = false }
}
onMounted(loadData)

const getTransportTag = (t: string) => ({ sse: '', streamable_http: 'success', stdio: 'warning' }[t] || 'info') as any
const getTransportLabel = (t: string) => ({ sse: 'SSE', streamable_http: 'Streamable HTTP', stdio: 'stdio（本地）' }[t] || t)
const getStatusTag = (s: string) => ({ active: 'success', inactive: 'info', error: 'danger', unknown: 'warning' }[s] || 'info') as any
const getStatusLabel = (s: string) => ({ active: '正常', inactive: '未激活', error: '错误', unknown: '未知' }[s] || s)

const handleTest = async (server: MCPServer) => {
  testingId.value = server.server_id
  try {
    const res = await mcpApi.testConnection(server.server_id)
    if (res.success) ElMessage.success(`连接成功，发现 ${res.tool_count} 个工具`)
    else ElMessage.error(`连接失败：${res.error}`)
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '测试失败') }
  finally { testingId.value = ''; loadData() }
}

const handleDiscover = async (server: MCPServer) => {
  discoveringId.value = server.server_id
  try {
    const res = await mcpApi.discoverTools(server.server_id)
    ElMessage.success(`发现 ${res.tool_count} 个工具${res.registered ? '，已注册到工具库' : ''}`)
    loadData()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '发现工具失败') }
  finally { discoveringId.value = '' }
}

const handleToggle = async (server: MCPServer, val: boolean) => {
  togglingId.value = server.server_id
  try {
    await mcpApi.toggleServer(server.server_id, val)
    ElMessage.success(`已${val ? '启用' : '禁用'} ${server.name}`)
    loadData()
  } catch { server.is_enabled = !val; ElMessage.error('操作失败') }
  finally { togglingId.value = '' }
}

const handleDelete = async (server: MCPServer) => {
  try {
    await ElMessageBox.confirm(`确定删除 MCP 服务器「${server.name}」？相关工具将从工具库注销。`, '删除确认',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' })
    await mcpApi.deleteServer(server.server_id)
    ElMessage.success('已删除')
    loadData()
  } catch (e: any) { if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败') }
}

const showTools = (server: MCPServer) => { toolsServer.value = server; toolsVisible.value = true }

const resetForm = () => {
  Object.assign(form, { server_id: '', name: '', description: '', transport_type: 'sse', is_enabled: false })
  Object.assign(form.connection, { url: '', command: '', argsStr: '', headersList: [], envList: [] })
}
const showCreateDialog = () => { formMode.value = 'create'; resetForm(); formVisible.value = true }
const showEditDialog = (server: MCPServer) => {
  formMode.value = 'edit'; editingId.value = server.server_id
  Object.assign(form, { name: server.name, description: server.description, transport_type: server.transport_type })
  Object.assign(form.connection, {
    url: server.connection.url || '', command: server.connection.command || '',
    argsStr: (server.connection.args || []).join('\n'),
    headersList: Object.entries(server.connection.headers || {}).map(([k, v]) => ({ key: k, value: v })),
    envList: Object.entries(server.connection.env || {}).map(([k, v]) => ({ key: k, value: v })),
  })
  formVisible.value = true
}

const addHeader = () => form.connection.headersList.push({ key: '', value: '' })
const removeHeader = (idx: number) => form.connection.headersList.splice(idx, 1)
const addEnv = () => form.connection.envList.push({ key: '', value: '' })
const removeEnv = (idx: number) => form.connection.envList.splice(idx, 1)

const buildConnection = () => {
  if (form.transport_type === 'stdio') {
    const args = form.connection.argsStr.split('\n').map(s => s.trim()).filter(Boolean)
    const env = Object.fromEntries(form.connection.envList.filter(i => i.key).map(i => [i.key, i.value]))
    return { command: form.connection.command, args, ...(Object.keys(env).length ? { env } : {}) }
  }
  const headers = Object.fromEntries(form.connection.headersList.filter(i => i.key).map(i => [i.key, i.value]))
  return { url: form.connection.url, ...(Object.keys(headers).length ? { headers } : {}) }
}

const handleSave = async () => {
  if (!form.name.trim()) { ElMessage.warning('请填写服务器名称'); return }
  if (form.transport_type === 'stdio' && !form.connection.command.trim()) { ElMessage.warning('请填写命令'); return }
  if (form.transport_type !== 'stdio' && !form.connection.url.trim()) { ElMessage.warning('请填写服务器 URL'); return }
  formLoading.value = true
  try {
    if (formMode.value === 'create') {
      await mcpApi.createServer({
        server_id: form.server_id || undefined,
        name: form.name, description: form.description,
        transport_type: form.transport_type,
        connection: buildConnection(), is_enabled: form.is_enabled,
      })
      ElMessage.success('创建成功')
    } else {
      await mcpApi.updateServer(editingId.value, {
        name: form.name, description: form.description,
        transport_type: form.transport_type, connection: buildConnection(),
      })
      ElMessage.success('更新成功')
    }
    formVisible.value = false
    loadData()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
  finally { formLoading.value = false }
}
</script>

<style scoped>
.mcp-servers-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-left h1 { display: flex; align-items: center; gap: 8px; margin: 0 0 4px 0; font-size: 22px; font-weight: 600; }
.header-icon { color: var(--el-color-primary); }
.subtitle { color: var(--el-text-color-secondary); font-size: 14px; }
.header-right { display: flex; gap: 8px; }
.server-name { display: flex; align-items: center; gap: 8px; }
.name-text { font-weight: 500; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.active { background: var(--el-color-success); }
.status-dot.inactive { background: var(--el-color-info); }
.status-dot.error { background: var(--el-color-danger); }
.status-dot.unknown { background: var(--el-color-warning); }
.error-hint { font-size: 12px; color: var(--el-color-danger); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
.kv-list { width: 100%; }
.kv-row { display: flex; align-items: center; margin-bottom: 8px; }
</style>
