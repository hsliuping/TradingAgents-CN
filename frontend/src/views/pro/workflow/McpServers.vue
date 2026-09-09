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

      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.category === 'datasource' ? 'success' : 'primary'" size="small">
            {{ row.category === 'datasource' ? '数据源' : '功能' }}
          </el-tag>
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
            @change="(val) => handleToggle(row, Boolean(val))"
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

    <!-- 凭证保险箱 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <span style="font-weight: 600; font-size: 16px;">凭证保险箱</span>
            <span style="color: var(--el-text-color-secondary); font-size: 13px; margin-left: 8px;">加密存储 MCP Server 所需的 API Key</span>
          </div>
          <el-button type="primary" size="small" @click="showCredentialDialog">
            <el-icon><Plus /></el-icon>
            添加凭证
          </el-button>
        </div>
      </template>

      <el-table v-if="credentials.length" :data="credentials" size="small" border stripe>
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column prop="key_name" label="变量名 / Header" width="180" />
        <el-table-column prop="key_value_masked" label="密钥" width="180" />
        <el-table-column prop="server_id" label="关联 Server" width="180">
          <template #default="{ row }">
            <span v-if="row.server_id">{{ row.server_id }}</span>
            <el-text v-else type="info" size="small">未关联</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="applyCredential(row)" :disabled="!row.server_id">
              应用到 Server
            </el-button>
            <el-button type="danger" link size="small" @click="deleteCredential(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无凭证，点击「添加凭证」存储 API Key" :image-size="60" />
    </el-card>

    <!-- 工具列表对话框 -->
    <el-dialog
      v-model="toolsVisible"
      :title="`工具列表 — ${toolsServer?.name}`"
      width="960px"
      destroy-on-close
    >
      <div v-if="toolsServer?.discovered_tools?.length" class="tools-table-wrap">
        <el-table
          :data="toolsServer.discovered_tools"
          size="small"
          border
          max-height="70vh"
        >
          <el-table-column prop="name" label="工具名称" min-width="140" align="top" />
          <el-table-column prop="description" label="描述" min-width="280" align="top">
            <template #default="{ row }">
              <div class="cell-wrap">{{ row.description }}</div>
            </template>
          </el-table-column>
          <el-table-column label="Tool ID" min-width="260" align="top">
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
      :width="form.category === 'datasource' ? '85%' : '75%'"
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

        <!-- 服务器类型 -->
        <el-form-item label="类型">
          <el-radio-group v-model="form.category">
            <el-radio-button value="function">功能类（Agent 直接调用）</el-radio-button>
            <el-radio-button value="datasource">数据源类（持久化到 MongoDB）</el-radio-button>
          </el-radio-group>
          <div class="field-hint" v-if="form.category === 'datasource'">
            工具调用结果将通过字段映射写入指定 MongoDB 集合，并记录审计日志。
          </div>
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

        <!-- 数据源映射配置（仅数据源类显示） -->
        <template v-if="form.category === 'datasource'">
          <el-divider content-position="left">
            <span class="divider-label">数据映射配置</span>
          </el-divider>
          <div v-for="(dm, dmIdx) in form.data_mappings" :key="dmIdx" class="dm-card">
            <div class="dm-card-header">
              <span class="dm-card-title">工具映射 {{ dmIdx + 1 }}</span>
              <el-button type="danger" link size="small" @click="removeDataMapping(dmIdx)">
                <el-icon><Delete /></el-icon> 移除
              </el-button>
            </div>
            <el-form-item label="工具名称">
              <div style="display:flex;gap:8px;width:100%">
                <el-select
                  v-if="serverTools.length > 0"
                  v-model="dm.tool_name"
                  placeholder="请选择工具"
                  style="flex:1"
                  clearable
                >
                  <el-option
                    v-for="tool in serverTools"
                    :key="tool.name"
                    :label="tool.name"
                    :value="tool.name"
                  >
                    <span style="font-weight:500">{{ tool.name }}</span>
                    <span style="font-size:12px;color:var(--el-text-color-secondary);margin-left:8px">{{ tool.description }}</span>
                  </el-option>
                </el-select>
                <el-input v-else v-model="dm.tool_name" placeholder="先点「发现工具」，再重新编辑此服务器" style="flex:1" />
                <el-button type="primary" plain size="small" @click="showProbeDialog(dmIdx)" :disabled="!dm.tool_name">
                  探测字段
                </el-button>
              </div>
              <div v-if="dm.tool_name && serverTools.length > 0" class="field-hint" style="margin-top:4px">
                {{ serverTools.find(t => t.name === dm.tool_name)?.description }}
              </div>
            </el-form-item>
            <el-form-item label="目标集合">
              <el-autocomplete
                v-model="dm.target_collection"
                :fetch-suggestions="getCollectionSuggestions"
                placeholder="选择 stock_* / mcp_* 集合或输入自定义集合名"
                style="width:100%"
                clearable
              >
                <template #suffix>
                  <el-icon v-if="mongoCollections.length === 0" style="color:var(--el-text-color-placeholder)"><Loading /></el-icon>
                </template>
              </el-autocomplete>
              <div class="field-hint" style="margin-top:4px">
                可选择已有集合，或输入新名称（系统将自动创建）
              </div>
            </el-form-item>
            <el-form-item>
              <el-button
                type="success"
                @click="showAIMappingDialog(dmIdx)"
                :disabled="!dm.tool_name || !dm.target_collection"
                style="width:100%"
              >
                🤖 AI 智能对接（自动生成字段映射）
              </el-button>
            </el-form-item>
            <el-form-item label="字段映射">
              <div class="kv-list" style="width:100%">
                <div class="kv-header">
                  <span style="width:180px;font-size:12px;color:var(--el-text-color-secondary)">源字段（MCP 返回）</span>
                  <span style="flex:1;margin-left:8px;font-size:12px;color:var(--el-text-color-secondary)">目标字段（MongoDB）</span>
                </div>
                <div v-for="(fld, fldIdx) in dm.field_mapping_list" :key="fldIdx" class="kv-row">
                  <el-input v-model="fld.key" placeholder="源字段名" style="width:180px" />
                  <el-input v-model="fld.value" placeholder="目标字段名" style="flex:1;margin:0 8px" />
                  <el-button type="danger" link @click="removeFieldMapping(dmIdx, fldIdx)"><el-icon><Delete /></el-icon></el-button>
                </div>
                <el-button link type="primary" @click="addFieldMapping(dmIdx)">
                  <el-icon><Plus /></el-icon> 添加字段映射
                </el-button>
              </div>
            </el-form-item>
          </div>
          <div style="margin-bottom:16px">
            <el-button link type="primary" @click="addDataMapping">
              <el-icon><Plus /></el-icon> 添加工具映射
            </el-button>
            <span class="field-hint" style="margin-left:12px">每个 MCP 工具配置一条映射规则</span>
          </div>
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

    <!-- 探测工具字段对话框 -->
    <el-dialog v-model="probeDialog.visible" :title="`探测工具字段：${probeDialog.tool_name}`" width="620px" destroy-on-close>
      <div>
        <!-- 参数表单 -->
        <div v-if="probeDialog.input_params.length > 0">
          <div style="font-size:13px;font-weight:500;margin-bottom:10px;color:var(--el-text-color-primary)">
            工具输入参数（选填，填写后探测结果更准确）
          </div>
          <el-form label-width="120px" size="small">
            <el-form-item
              v-for="p in probeDialog.input_params"
              :key="p.name"
              :label="p.name"
            >
              <el-input v-model="p.value" :placeholder="p.description || (p.required ? '必填' : '选填')" />
              <span v-if="p.required" style="color:var(--el-color-danger);margin-left:4px;font-size:11px">必填</span>
            </el-form-item>
          </el-form>
        </div>
        <div v-else style="font-size:13px;color:var(--el-text-color-secondary);margin-bottom:10px">
          该工具无输入参数，直接探测即可
        </div>

        <el-button type="primary" :loading="probeDialog.loading" @click="executeProbeTool" style="margin-bottom:16px">
          执行探测
        </el-button>

        <!-- 探测结果 -->
        <template v-if="probeDialog.result">
          <el-divider content-position="left">检测到的输出字段</el-divider>
          <el-table :data="probeDialog.result.detected_fields" size="small" border max-height="240">
            <el-table-column prop="name" label="字段名" min-width="160" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="sample" label="样本值" min-width="180" show-overflow-tooltip />
          </el-table>

          <el-divider content-position="left">原始返回（前 500 字符）</el-divider>
          <el-input
            type="textarea"
            :model-value="probeDialog.result.raw_result.slice(0, 500)"
            :rows="4"
            readonly
            style="font-family:monospace;font-size:12px"
          />
        </template>
      </div>
      <template #footer>
        <el-button @click="probeDialog.visible = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!probeDialog.result || probeDialog.result.detected_fields.length === 0"
          @click="applyDetectedFields"
        >
          导入字段到映射列表
        </el-button>
      </template>
    </el-dialog>

    <!-- AI 智能对接对话框 -->
    <el-dialog v-model="aiMappingDialog.visible" title="🤖 AI 智能字段映射" width="90%" destroy-on-close :body-style="{ 'max-height': 'calc(80vh - 120px)', 'overflow-y': 'auto' }">
      <div v-if="aiMappingDialog.loading" style="text-align:center;padding:40px">
        <el-icon class="is-loading" style="font-size:32px;color:var(--el-color-primary);margin-bottom:16px"><Loading /></el-icon>
        <div style="font-size:14px;color:var(--el-text-color-secondary)">AI 正在分析工具字段和集合结构，生成映射建议...</div>
      </div>
      <template v-else>
        <div v-if="aiMappingDialog.explanation" style="margin-bottom:16px;padding:12px;background:var(--el-fill-color-light);border-radius:4px;border-left:3px solid var(--el-color-primary)">
          <div style="font-size:13px;font-weight:500;margin-bottom:4px">📋 AI 分析说明</div>
          <div style="font-size:12px;color:var(--el-text-color-secondary);line-height:1.6">{{ aiMappingDialog.explanation }}</div>
        </div>

        <div style="margin-bottom:16px">
          <div style="font-size:13px;font-weight:500;margin-bottom:8px">建议的字段映射（共 {{ aiMappingDialog.mappings.length }} 个字段）</div>
          <el-table :data="aiMappingDialog.mappings" size="small" border>
            <el-table-column type="selection" width="40" />
            <el-table-column label="源字段（MCP）" min-width="180">
              <template #default="{ row }">
                <div style="display:flex;align-items:center;gap:8px">
                  <el-input v-model="row.source" size="small" style="width:100px" placeholder="字段名" />
                  <el-tag v-if="row.reason === '未被 AI 映射，请手动配置'" type="info" size="small">待配置</el-tag>
                  <el-tag v-else type="success" size="small">AI 建议</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="" width="30" align="center">
              <template #default>
                <span style="color:var(--el-text-color-secondary)">→</span>
              </template>
            </el-table-column>
            <el-table-column label="目标字段（MongoDB）" min-width="240">
              <template #default="{ row }">
                <div style="display:flex;flex-direction:column;gap:4px">
                  <el-autocomplete
                    v-model="row.target"
                    :fetch-suggestions="(queryString, cb) => {
                      const results = queryString
                        ? aiMappingDialog.collectionFields.filter(f => f.includes(queryString))
                        : aiMappingDialog.collectionFields
                      cb(results.map(f => ({ value: f })))
                    }"
                    size="small"
                    placeholder="选择或输入字段名"
                    style="width:100%"
                  />
                  <div v-if="aiMappingDialog.collectionFieldDescriptions[row.target]" style="font-size:12px;color:var(--el-text-color-secondary);padding:0 4px;line-height:1.4">
                    📝 {{ aiMappingDialog.collectionFieldDescriptions[row.target] }}
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="映射理由" min-width="160" show-overflow-tooltip />
            <el-table-column label="操作" width="60" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="aiMappingDialog.mappings.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="aiMappingDialog.collectionFields.length > 0" style="margin-bottom:16px;padding:12px;background:var(--el-fill-color-light);border-radius:4px">
          <div style="font-size:12px;color:var(--el-text-color-secondary)">
            <span style="font-weight:500">📊 集合现有字段：</span>
            {{ aiMappingDialog.collectionFields.join('、') }}
          </div>
        </div>
      </template>

      <template #footer>
        <el-button @click="aiMappingDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="aiMappingDialog.loading" :disabled="aiMappingDialog.loading || aiMappingDialog.mappings.length === 0" @click="applyAIMappings">
          应用选中的映射
        </el-button>
      </template>
    </el-dialog>

    <!-- 凭证添加对话框 -->
    <el-dialog v-model="credDialogVisible" title="添加凭证" width="500px" destroy-on-close>
      <el-form :model="credForm" label-width="120px">
        <el-form-item label="凭证名称" required>
          <el-input v-model="credForm.name" placeholder="如 Tushare API Key" />
        </el-form-item>
        <el-form-item label="变量名 / Header" required>
          <el-input v-model="credForm.key_name" placeholder="如 TUSHARE_TOKEN 或 Authorization" />
        </el-form-item>
        <el-form-item label="密钥值" required>
          <el-input v-model="credForm.key_value" type="password" show-password placeholder="输入 API Key" />
        </el-form-item>
        <el-form-item label="关联 MCP Server">
          <el-select v-model="credForm.server_id" clearable placeholder="选择关联的 MCP Server" style="width: 100%;">
            <el-option v-for="s in servers" :key="s.server_id" :label="s.name" :value="s.server_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="credForm.description" placeholder="凭证用途说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="credDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="credSaving" @click="saveCredential">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Plus, Refresh, Delete, Loading } from '@element-plus/icons-vue'
import { mcpApi, type MCPServer, type MCPDiscoveredTool, type MCPProbeResult, type CredentialItem } from '@/api/mcp'

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

// 服务器已发现工具列表（打开编辑对话框时加载）
const serverTools = ref<MCPDiscoveredTool[]>([])
// MongoDB 集合名称列表（用于目标集合自动补全）
const mongoCollections = ref<string[]>([])

// AI 智能对接对话框状态
const aiMappingDialog = reactive({
  visible: false,
  dmIdx: -1,
  loading: false,
  explanation: '',
  mappings: [] as Array<{ source: string; target: string; reason: string; selected: boolean }>,
  collectionFields: [] as string[],
  collectionFieldDescriptions: {} as Record<string, string>,
})

// 探测对话框状态
const probeDialog = reactive({
  visible: false,
  dmIdx: -1,
  tool_name: '',
  input_params: [] as Array<{ name: string; description: string; required: boolean; value: string }>,
  loading: false,
  result: null as null | MCPProbeResult,
})

interface KvItem { key: string; value: string }
interface ConnState { url: string; command: string; argsStr: string; headersList: KvItem[]; envList: KvItem[] }
interface DataMappingItem { tool_name: string; target_collection: string; field_mapping_list: KvItem[] }
interface FormState {
  server_id: string; name: string; description: string
  transport_type: 'sse' | 'streamable_http' | 'stdio'
  is_enabled: boolean; connection: ConnState
  category: 'datasource' | 'function'
  data_mappings: DataMappingItem[]
}
const form = reactive<FormState>({
  server_id: '', name: '', description: '', transport_type: 'sse', is_enabled: false,
  connection: { url: '', command: '', argsStr: '', headersList: [], envList: [] },
  category: 'function',
  data_mappings: [],
})

const loadData = async () => {
  loading.value = true
  try { servers.value = (await mcpApi.listServers()).servers || [] }
  catch { ElMessage.error('加载 MCP 服务器失败') }
  finally { loading.value = false }
  loadCredentials()
}

// 凭证保险箱
const credentials = ref<CredentialItem[]>([])
const credDialogVisible = ref(false)
const credSaving = ref(false)
const credForm = ref({ name: '', key_name: '', key_value: '', server_id: '', description: '' })

const loadCredentials = async () => {
  try { credentials.value = await mcpApi.listCredentials() }
  catch { /* ignore */ }
}

const showCredentialDialog = () => {
  credForm.value = { name: '', key_name: '', key_value: '', server_id: '', description: '' }
  credDialogVisible.value = true
}

const saveCredential = async () => {
  if (!credForm.value.name || !credForm.value.key_name || !credForm.value.key_value) {
    ElMessage.warning('请填写凭证名称、变量名和密钥值')
    return
  }
  credSaving.value = true
  try {
    await mcpApi.createCredential({
      name: credForm.value.name,
      key_name: credForm.value.key_name,
      key_value: credForm.value.key_value,
      server_id: credForm.value.server_id || undefined,
      description: credForm.value.description || undefined,
    })
    ElMessage.success('凭证已保存')
    credDialogVisible.value = false
    loadCredentials()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存凭证失败')
  } finally {
    credSaving.value = false
  }
}

const applyCredential = async (cred: CredentialItem) => {
  if (!cred.server_id) return
  try {
    await mcpApi.applyCredentialToServer(cred.id, cred.server_id)
    ElMessage.success(`已将凭证 ${cred.name} 应用到 MCP Server`)
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '应用凭证失败')
  }
}

const deleteCredential = async (cred: CredentialItem) => {
  try {
    await ElMessageBox.confirm(`确定删除凭证「${cred.name}」？`, '确认删除', { type: 'warning' })
    await mcpApi.deleteCredential(cred.id)
    ElMessage.success('已删除')
    loadCredentials()
  } catch { /* cancelled */ }
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
    const count = res.tool_count ?? res.tools?.length ?? 0
    ElMessage.success(`发现 ${count} 个工具${res.registered ? '，已注册到工具库' : ''}`)
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
  Object.assign(form, { server_id: '', name: '', description: '', transport_type: 'sse', is_enabled: false, category: 'function', data_mappings: [] })
  Object.assign(form.connection, { url: '', command: '', argsStr: '', headersList: [], envList: [] })
}
const showCreateDialog = () => {
  formMode.value = 'create'; resetForm(); serverTools.value = []; formVisible.value = true
  loadCollections()
}
const showEditDialog = (server: MCPServer) => {
  formMode.value = 'edit'; editingId.value = server.server_id
  form.data_mappings = (server.data_mappings || []).map(dm => {
    // 优先使用 field_mapping_list（支持一源多目标），否则从 field_mapping 对象转换
    const list = dm.field_mapping_list?.length
      ? dm.field_mapping_list.map((f: any) => ({ key: f.source ?? f.key, value: f.target ?? f.value }))
      : Object.entries(dm.field_mapping || {}).map(([k, v]) => ({ key: k, value: v as string }))
    return {
      tool_name: dm.tool_name,
      target_collection: dm.target_collection || '',
      field_mapping_list: list,
    }
  })
  Object.assign(form, {
    name: server.name, description: server.description,
    transport_type: server.transport_type,
    category: (server.category || 'function') as 'datasource' | 'function',
  })
  Object.assign(form.connection, {
    url: server.connection.url || '', command: server.connection.command || '',
    argsStr: (server.connection.args || []).join('\n'),
    headersList: Object.entries(server.connection.headers || {}).map(([k, v]) => ({ key: k, value: v })),
    envList: Object.entries(server.connection.env || {}).map(([k, v]) => ({ key: k, value: v })),
  })
  formVisible.value = true
  // 异步加载已发现工具列表（工具下拉）+ MongoDB 集合列表（目标集合自动补全）
  loadServerTools(server.server_id)
  loadCollections()
}

// 加载 MongoDB 集合列表
const loadCollections = async () => {
  try {
    const res = await mcpApi.listCollections()
    mongoCollections.value = res.collections || []
  } catch {
    mongoCollections.value = []
  }
}

const getCollectionSuggestions = (
  queryString: string,
  callback: (items: Array<{ value: string }>) => void,
) => {
  const items = mongoCollections.value
    .filter((collection) => {
      const isSupportedCollection =
        collection.startsWith('stock') ||
        collection.startsWith('mcp') ||
        collection === 'market_quotes'

      return isSupportedCollection && (!queryString || collection.toLowerCase().includes(queryString.toLowerCase()))
    })
    .map((collection) => ({ value: collection }))

  callback(items)
}

// 加载服务器工具列表（从数据库缓存，不重连 MCP 服务器）
const loadServerTools = async (serverId: string) => {
  try {
    const res = await mcpApi.listServerTools(serverId)
    serverTools.value = res.tools || []
  } catch {
    serverTools.value = []
  }
}

// 显示探测对话框（基于已选工具的 input_schema 生成参数表单）
const showProbeDialog = (dmIdx: number) => {
  const dm = form.data_mappings[dmIdx]
  if (!dm.tool_name) { ElMessage.warning('请先选择工具'); return }
  const toolMeta = serverTools.value.find(t => t.name === dm.tool_name)
  const schema = toolMeta?.input_schema || {}
  const props = (schema as any).properties || {}
  const required: string[] = (schema as any).required || []
  probeDialog.dmIdx = dmIdx
  probeDialog.tool_name = dm.tool_name
  probeDialog.input_params = Object.entries(props).map(([name, def]: [string, any]) => ({
    name,
    description: def.description || '',
    required: required.includes(name),
    value: '',
  }))
  probeDialog.result = null
  probeDialog.visible = true
}

// 执行探测调用
const executeProbeTool = async () => {
  probeDialog.loading = true
  try {
    const args: Record<string, any> = {}
    for (const p of probeDialog.input_params) {
      if (p.value.trim()) args[p.name] = p.value.trim()
    }
    probeDialog.result = await mcpApi.probeTool(editingId.value, probeDialog.tool_name, args)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '探测失败')
  } finally {
    probeDialog.loading = false
  }
}

// 将探测到的字段导入到字段映射列表（追加不重复的字段）
const applyDetectedFields = () => {
  if (!probeDialog.result || probeDialog.dmIdx < 0) return
  const dm = form.data_mappings[probeDialog.dmIdx]
  const existingKeys = new Set(dm.field_mapping_list.map(f => f.key))
  let added = 0
  for (const f of probeDialog.result.detected_fields) {
    if (!existingKeys.has(f.name)) {
      dm.field_mapping_list.push({ key: f.name, value: '' })
      existingKeys.add(f.name)
      added++
    }
  }
  probeDialog.visible = false
  ElMessage.success(`已导入 ${added} 个字段到映射列表`)
}

// 显示 AI 智能对接对话框
const showAIMappingDialog = (dmIdx: number) => {
  const dm = form.data_mappings[dmIdx]
  if (!dm.tool_name || !dm.target_collection) {
    ElMessage.warning('请先选择工具名称和目标集合')
    return
  }
  aiMappingDialog.dmIdx = dmIdx
  aiMappingDialog.loading = true
  aiMappingDialog.visible = true
  aiMappingDialog.mappings = []
  aiMappingDialog.explanation = ''
  aiMappingDialog.collectionFields = []
  executeAIMappingSuggestion(dmIdx)
}

// 执行 AI 字段映射建议
const executeAIMappingSuggestion = async (dmIdx: number) => {
  const dm = form.data_mappings[dmIdx]
  aiMappingDialog.loading = true
  try {
    const result = await mcpApi.aiSuggestMapping(
      editingId.value,
      dm.tool_name,
      dm.target_collection
    )
    if (result.success) {
      aiMappingDialog.mappings = (result.mappings || []).map(m => ({
        ...m,
        selected: true,
      }))
      aiMappingDialog.explanation = result.explanation || ''
      aiMappingDialog.collectionFields = result.collection_fields || []
      aiMappingDialog.collectionFieldDescriptions = result.collection_field_descriptions || {}
    } else {
      ElMessage.error('AI 推断失败')
      aiMappingDialog.visible = false
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || 'AI 推断失败')
    aiMappingDialog.visible = false
  } finally {
    aiMappingDialog.loading = false
  }
}

// 应用 AI 建议的字段映射（支持一个源字段映射到多个目标字段）
const applyAIMappings = () => {
  if (aiMappingDialog.dmIdx < 0) return
  const dm = form.data_mappings[aiMappingDialog.dmIdx]
  const existingPairs = new Set(dm.field_mapping_list.map(f => `${f.key}->${f.value}`))
  let applied = 0
  for (const m of aiMappingDialog.mappings) {
    // 只应用：选中的 + 有目标字段的 + 不重复的 (源,目标) 对（支持一源多目标）
    if (m.selected && m.target && !existingPairs.has(`${m.source}->${m.target}`)) {
      dm.field_mapping_list.push({ key: m.source, value: m.target })
      existingPairs.add(`${m.source}->${m.target}`)
      applied++
    }
  }
  aiMappingDialog.visible = false
  ElMessage.success(`已应用 ${applied} 个字段映射`)
}

// data_mappings 操作辅助函数
const addDataMapping = () => form.data_mappings.push({ tool_name: '', target_collection: '', field_mapping_list: [] })
const removeDataMapping = (idx: number) => form.data_mappings.splice(idx, 1)
const addFieldMapping = (dmIdx: number) => form.data_mappings[dmIdx].field_mapping_list.push({ key: '', value: '' })
const removeFieldMapping = (dmIdx: number, fldIdx: number) => form.data_mappings[dmIdx].field_mapping_list.splice(fldIdx, 1)

const buildDataMappings = () => {
  if (form.category !== 'datasource') return []
  return form.data_mappings
    .filter(dm => dm.tool_name.trim() && dm.target_collection.trim())
    .map(dm => ({
      tool_name: dm.tool_name.trim(),
      target_collection: dm.target_collection.trim(),
      // 使用 field_mapping_list 数组格式，支持一个源字段映射到多个目标字段（Object 会覆盖同 key）
      field_mapping_list: dm.field_mapping_list
        .filter(f => f.key.trim() && f.value.trim())
        .map(f => ({ source: f.key.trim(), target: f.value.trim() })),
    }))
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
        category: form.category,
        data_mappings: buildDataMappings(),
      })
      ElMessage.success('创建成功')
    } else {
      await mcpApi.updateServer(editingId.value, {
        name: form.name, description: form.description,
        transport_type: form.transport_type, connection: buildConnection(),
        category: form.category,
        data_mappings: buildDataMappings(),
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

/* 工具列表对话框 */
.tools-table-wrap { min-height: 200px; }
.cell-wrap { white-space: normal; word-break: break-word; line-height: 1.4; }

/* 数据映射配置 */
.divider-label { font-size: 13px; font-weight: 500; color: var(--el-text-color-primary); }
.dm-card {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  padding: 12px 16px 4px;
  margin-bottom: 12px;
  background: var(--el-fill-color-blank);
}
.dm-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.dm-card-title { font-weight: 500; font-size: 13px; color: var(--el-text-color-regular); }
.kv-header { display: flex; margin-bottom: 4px; padding-right: 28px; }
.field-hint { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; line-height: 1.4; }
</style>
