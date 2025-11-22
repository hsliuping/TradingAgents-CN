<template>
  <div class="mcp-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <el-icon><Connection /></el-icon>
          MCP客户端管理
        </h1>
        <p class="page-description">
          管理Model Context Protocol (MCP) 客户端连接配置，连接到外部MCP服务器获取工具和能力
        </p>
      </div>
      <div class="header-right">
        <el-button @click="refreshStatus" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新状态
        </el-button>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <el-row :gutter="24">
      <!-- 左侧：mcp.json编辑器 -->
      <el-col :span="12">
        <el-card class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>mcp.json 客户端配置</h3>
              <div class="header-actions">
                <el-button size="small" @click="formatJson">
                  <el-icon><RefreshRight /></el-icon>
                  格式化
                </el-button>
                <el-button size="small" type="primary" @click="saveConfig" :loading="saving">
                  <el-icon><Check /></el-icon>
                  保存配置
                </el-button>
              </div>
            </div>
          </template>

          <div class="json-editor">
            <el-input
              v-model="jsonConfig"
              type="textarea"
              :rows="25"
              placeholder='请输入MCP配置文件内容，例如：

{
  "mcpServers": {
    "zai-mcp-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@z_ai/mcp-server"]
    },
    "web-search-prime": {
      "type": "streamable-http",
      "url": "https://api.example.com/mcp"
    }
  }
}'
              class="json-textarea"
            />

            <div class="editor-status">
              <div v-if="jsonError" class="json-error">
                <el-icon><WarningFilled /></el-icon>
                <span>{{ jsonError }}</span>
              </div>

              <div v-if="saveSuccess" class="save-success">
                <el-icon><CircleCheck /></el-icon>
                <span>配置保存成功</span>
              </div>

              <div class="editor-info">
                <span class="char-count">{{ jsonConfig.length }} 字符</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：服务器列表 -->
      <el-col :span="12">
        <el-card class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>MCP服务器列表</h3>
              <el-tag type="info" size="small">{{ servers.length }} 个服务器</el-tag>
            </div>
          </template>

          <div v-loading="loading" class="servers-list">
            <div v-if="!servers.length" class="empty-state">
              <el-empty description="暂无MCP服务器">
                <p class="empty-tip">请在左侧编辑器中添加MCP服务器配置</p>
              </el-empty>
            </div>

            <div v-for="server in servers" :key="server.name" class="server-item">
              <!-- 服务器基本信息 -->
              <div class="server-header">
                <div class="server-info">
                  <div class="server-name">{{ server.name }}</div>
                  <div class="server-type">
                    <el-tag :type="getTypeTagType(server.type)" size="small">
                      {{ server.type || 'stdio' }}
                    </el-tag>
                  </div>
                </div>
                <div class="server-control">
                  <el-switch
                    v-model="server.enabled"
                    @change="toggleServer(server)"
                    size="large"
                    :active-text="server.enabled ? '已启用' : '已禁用'"
                    inline-prompt
                  />
                </div>
              </div>

              <!-- 服务器详细信息 -->
              <div class="server-details">
                <div v-if="server.command" class="detail-row">
                  <span class="detail-label">启动命令:</span>
                  <code class="detail-value">{{ server.command }} {{ server.args?.join(' ') || '' }}</code>
                </div>

                <div v-if="server.url" class="detail-row">
                  <span class="detail-label">服务地址:</span>
                  <code class="detail-value">{{ server.url }}</code>
                </div>

                <div v-if="server.env && Object.keys(server.env).length" class="detail-row">
                  <span class="detail-label">环境变量:</span>
                  <div class="env-vars">
                    <el-tag v-for="(value, key) in server.env" :key="key" size="small" type="info" effect="light">
                      {{ key }}
                    </el-tag>
                  </div>
                </div>
              </div>

              <!-- 状态栏 -->
              <div class="server-status">
                <div class="status-info">
                  <div class="status-dot" :class="`status-${server.status}`"></div>
                  <span class="status-text" :class="{ 'disabled': !server.enabled }">
                    {{ getServerStatusText(server) }}
                  </span>
                </div>
                <div class="status-actions">
                  <el-button
                    v-if="server.enabled && server.status === 'offline'"
                    size="small"
                    text
                    type="primary"
                    @click="toggleServer(server)"
                  >
                    重新连接
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 使用说明 -->
        <el-card class="help-content" shadow="never" style="margin-top: 16px;">
          <template #header>
            <h4>使用说明</h4>
          </template>

          <div class="help-sections">
            <div class="help-section">
              <h5>📝 配置格式</h5>
              <ul>
                <li><strong>STDIO类型</strong>: command + args</li>
                <li><strong>HTTP类型</strong>: type: "http" + url</li>
                <li><strong>Streamable HTTP</strong>: type: "streamable-http" + url</li>
              </ul>
            </div>

            <div class="help-section">
              <h5>⚡ 操作方式</h5>
              <ul>
                <li><strong>添加服务器</strong>: 在左侧JSON编辑器中添加配置</li>
                <li><strong>删除服务器</strong>: 直接删除对应配置项</li>
                <li><strong>启用/禁用</strong>: 使用右侧开关控制</li>
                <li><strong>状态检查</strong>: 点击"刷新状态"按钮</li>
              </ul>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Document, RefreshRight, Check,
  WarningFilled, CircleCheck, CircleClose,
  Connection, Loading, InfoFilled,
  Cpu, List, Key, Link
} from '@element-plus/icons-vue'
import { mcpApi, McpConfigHelper } from '@/api/mcp'

// 类型定义
interface McpServer {
  name: string
  type?: string
  command?: string
  args?: string[]
  url?: string
  headers?: Record<string, string>
  env?: Record<string, string>
  enabled: boolean
  status: 'checking' | 'online' | 'offline'
}

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const jsonConfig = ref('{}')
const jsonError = ref('')
const saveSuccess = ref(false)
const servers = ref<McpServer[]>([])

// 模拟默认配置
const defaultConfig = {
  "mcpServers": {
    "example-server": {
      "command": "echo",
      "args": ["Hello from MCP"]
    }
  }
}

// 方法
const loadConfig = async () => {
  try {
    loading.value = true
    const response = await mcpApi.getConfig()

    // 确保返回的数据格式正确
    if (response.data && response.data.mcpServers) {
      jsonConfig.value = JSON.stringify(response.data, null, 2)
    } else {
      jsonConfig.value = JSON.stringify(defaultConfig, null, 2)
    }

    parseServers()
  } catch (error: any) {
    console.error('加载MCP配置失败:', error)
    ElMessage.error('加载配置失败，使用默认配置')
    jsonConfig.value = JSON.stringify(defaultConfig, null, 2)
    parseServers()
  } finally {
    loading.value = false
  }
}

const parseServers = () => {
  try {
    // 确保 jsonConfig 不为空
    const configStr = jsonConfig.value || '{}'
    const config = JSON.parse(configStr)

    // 使用McpConfigHelper解析服务器
    const parsedServers = McpConfigHelper.parseServersFromConfig({ mcpServers: config.mcpServers || {} })

    // 合并配置信息，但不获取状态（状态只在保存后刷新）
    const mcpServers = config.mcpServers || {}
    servers.value = parsedServers.map(serverStatus => {
      const serverConfig = mcpServers[serverStatus.name] || {}

      // 检查是否为禁用状态
      const enabled = serverConfig.enabled !== false // 默认启用
      return {
        name: serverStatus.name,
        type: serverConfig.type,
        command: serverConfig.command,
        args: serverConfig.args,
        url: serverConfig.url,
        headers: serverConfig.headers,
        env: serverConfig.env,
        enabled: enabled,
        status: enabled ? 'checking' : 'offline',  // 初始状态：启用为checking，禁用为offline
        lastCheck: undefined,
        responseTime: undefined,
        errorMessage: enabled ? undefined : '客户端已禁用'
      }
    })

    jsonError.value = ''
  } catch (error: any) {
    jsonError.value = `JSON格式错误: ${error.message}`
    servers.value = []
  }
}

const refreshServersStatus = async () => {
  try {
    const response = await mcpApi.getServersStatus()
    if (response.success && response.data) {
      // 更新服务器状态，保持原有UI数据结构
      servers.value = servers.value.map(server => {
        const statusData = response.data.find((s: any) => s.name === server.name)
        if (statusData) {
          return {
            ...server,
            status: statusData.status,
            lastCheck: statusData.lastCheck,
            responseTime: statusData.responseTime,
            errorMessage: statusData.errorMessage,
            framework: statusData.framework, // 添加框架字段
            tools_count: statusData.tools_count, // 添加工具数量字段
            connection_tested: statusData.connection_tested, // 添加连接测试字段
            warning: statusData.warning // 添加警告字段
          }
        }
        return server
      })
    }
  } catch (error: any) {
    console.error('刷新服务器状态失败:', error)
    // 如果API调用失败，将启用的服务器设为checking状态
    servers.value = servers.value.map(server => ({
      ...server,
      status: server.enabled ? 'checking' : 'offline',
      lastCheck: new Date().toISOString(),
      responseTime: undefined,
      errorMessage: server.enabled ? undefined : '服务器已禁用'
    }))
  }
}

const formatJson = () => {
  try {
    jsonConfig.value = McpConfigHelper.formatJson(jsonConfig.value)
    ElMessage.success('JSON格式化成功')
  } catch (error: any) {
    ElMessage.error(`JSON格式错误: ${error.message}`)
  }
}

const saveConfig = async () => {
  try {
    // 验证JSON格式
    const config = JSON.parse(jsonConfig.value || '{}')

    // 验证配置结构
    try {
      const validationResponse = await mcpApi.validateConfig(config)
      console.log('验证响应:', validationResponse)

      // 检查验证响应格式
      if (!validationResponse || !validationResponse.data) {
        ElMessage.error('配置验证失败: 无法获取验证结果')
        return
      }

      if (!validationResponse.data.valid) {
        const errors = validationResponse.data.errors || []
        ElMessage.error(`配置验证失败: ${errors.join(', ')}`)
        return
      }
    } catch (validationError: any) {
      console.error('配置验证错误:', validationError)
      ElMessage.error(`配置验证失败: ${validationError.message || '验证服务异常'}`)
      return
    }

    saving.value = true

    // 保存配置
    try {
      const response = await mcpApi.saveConfig({ mcpServers: config.mcpServers || {} })
      console.log('保存响应:', response)

      saveSuccess.value = true
      setTimeout(() => {
        saveSuccess.value = false
      }, 3000)

      ElMessage.success('配置保存成功，正在检查MCP客户端状态...')

      // 重新解析配置（不获取状态）
      parseServers()

      // 延迟刷新状态，确保后端配置已更新
      setTimeout(() => {
        refreshStatus()
      }, 1000)
    } catch (saveError: any) {
      console.error('保存配置错误:', saveError)
      ElMessage.error(`保存失败: ${saveError.message || '保存服务异常'}`)
    }

  } catch (error: any) {
    console.error('JSON解析错误:', error)
    ElMessage.error(`JSON格式错误: ${error.message || '格式解析失败'}`)
  } finally {
    saving.value = false
  }
}

const refreshStatus = async () => {
  loading.value = true

  // 先设置为检测中状态
  servers.value = servers.value.map(server => ({
    ...server,
    status: server.enabled ? 'checking' : 'disabled',
    lastCheck: new Date().toISOString(),
    responseTime: undefined,
    errorMessage: server.enabled ? undefined : '客户端已禁用'
  }))

  try {
    const response = await mcpApi.refreshAllStatus()

    // 更新服务器状态
    const updatedServers = response.data || []
    servers.value = servers.value.map(server => {
      const updatedStatus = updatedServers.find(s => s.name === server.name)
      if (updatedStatus) {
        return {
          ...server,
          status: updatedStatus.status,
          lastCheck: updatedStatus.lastCheck,
          responseTime: updatedStatus.responseTime,
          errorMessage: updatedStatus.errorMessage
        }
      }
      return server
    })

    ElMessage.success(response.message || 'MCP客户端状态已刷新')
  } catch (error: any) {
    console.error('刷新MCP客户端状态失败:', error)
    ElMessage.error(`刷新状态失败: ${error.message || '网络错误'}`)

    // 恢复为离线状态
    servers.value = servers.value.map(server => ({
      ...server,
      status: 'offline',
      errorMessage: '状态获取失败'
    }))
  } finally {
    loading.value = false
  }
}

const getTypeTagType = (type?: string) => {
  return McpConfigHelper.getServerTypeTagType(type)
}

const toggleServer = async (server: McpServer) => {
  const originalEnabled = server.enabled
  server.status = 'checking'

  try {
    const response = await mcpApi.toggleServer(server.name, server.enabled)

    // 根据API响应更新状态
    if (response.data) {
      server.status = response.data.status || (server.enabled ? 'checking' : 'offline')
      server.lastCheck = response.data.lastCheck
      server.responseTime = response.data.responseTime
      server.errorMessage = response.data.errorMessage
      server.framework = response.data.framework
    }

    ElMessage.success(response.message || `${server.name} 状态已更新`)

    // 无论启用还是禁用，都刷新状态以获取最新信息
    setTimeout(async () => {
      try {
        const statusResponse = await mcpApi.getServerStatus(server.name)
        if (statusResponse.data) {
          const statusData = statusResponse.data
          server.status = statusData.status
          server.lastCheck = statusData.lastCheck
          server.responseTime = statusData.responseTime
          server.errorMessage = statusData.errorMessage

          if (statusData.status === 'online') {
            ElMessage.success(`${server.name} 已启用并连接成功`)
          } else {
            server.enabled = false
            ElMessage.error(`${server.name} 连接失败: ${statusData.errorMessage || '未知错误'}`)
          }
        }
      } catch (error: any) {
        server.enabled = false
        server.status = 'offline'
        ElMessage.error(`获取服务器状态失败: ${error.message}`)
      }
    }, 1000)

  } catch (error: any) {
    server.enabled = originalEnabled // 回滚状态
    server.status = 'offline'
    ElMessage.error(`操作失败: ${error.message || '网络错误'}`)
  }
}

const getServerStatusText = (server: McpServer) => {
  return McpConfigHelper.getServerStatusText(server)
}

// 监听JSON配置变化
watch(jsonConfig, () => {
  if (jsonConfig.value) {
    parseServers()
  }
})

// 生命周期
onMounted(() => {
  console.log('MCP Servers component mounted, loading config...')
  loadConfig()
  
  // 延迟自动刷新状态，确保配置加载完成
  setTimeout(() => {
    refreshServersStatus()
  }, 1000) // 1秒后自动刷新状态
})
</script>

<style lang="scss" scoped>
.mcp-management {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      flex: 1;

      .page-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 24px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        margin: 0 0 8px 0;
      }

      .page-description {
        margin: 0;
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }

    .header-right {
      display: flex;
      gap: 12px;
    }
  }

  .config-content {
    min-height: 500px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      h4 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .json-editor {
      .json-textarea {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.5;

        :deep(.el-textarea__inner) {
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 13px;
          line-height: 1.5;
          background-color: var(--el-fill-color-extra-light);
          border: 1px solid var(--el-border-color-light);
          resize: vertical;
        }
      }

      .json-error {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
        padding: 8px 12px;
        background-color: var(--el-color-danger-light-9);
        border: 1px solid var(--el-color-danger-light-7);
        border-radius: 4px;
        color: var(--el-color-danger);
        font-size: 14px;

        .el-icon {
          color: var(--el-color-danger);
        }
      }

      .save-success {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
        padding: 8px 12px;
        background-color: var(--el-color-success-light-9);
        border: 1px solid var(--el-color-success-light-7);
        border-radius: 4px;
        color: var(--el-color-success);
        font-size: 14px;

        .el-icon {
          color: var(--el-color-success);
        }
      }

      .editor-info {
        margin-top: 8px;
        text-align: right;

        .char-count {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
        }
      }
    }

    .servers-list {
      min-height: 400px;

      .empty-state {
        text-align: center;
        padding: 60px 20px;

        .empty-tip {
          color: var(--el-text-color-secondary);
          font-size: 14px;
          margin-top: 12px;
        }
      }

      .server-item {
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        background: var(--el-bg-color);
        transition: all 0.3s ease;

        &:hover {
          border-color: var(--el-color-primary-light-7);
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
        }

        .server-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;

          .server-info {
            flex: 1;

            .server-name {
              font-size: 16px;
              font-weight: 600;
              color: var(--el-text-color-primary);
              margin-bottom: 4px;
            }

            .server-type {
              margin-top: 4px;
            }
          }

          .server-control {
            margin-left: 16px;
          }
        }

        .server-details {
          margin-bottom: 12px;

          .detail-row {
            display: flex;
            align-items: flex-start;
            margin-bottom: 8px;
            font-size: 13px;

            &:last-child {
              margin-bottom: 0;
            }

            .detail-label {
              width: 80px;
              color: var(--el-text-color-secondary);
              font-weight: 500;
              flex-shrink: 0;
            }

            .detail-value {
              flex: 1;
              color: var(--el-text-color-primary);
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              font-size: 12px;
              background-color: var(--el-fill-color-extra-light);
              padding: 4px 8px;
              border-radius: 4px;
              word-break: break-all;
            }

            .env-vars {
              display: flex;
              flex-wrap: wrap;
              gap: 6px;
            }
          }
        }

        .server-status {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 12px;
          border-top: 1px solid var(--el-border-color-lighter);

          .status-info {
            display: flex;
            align-items: center;
            gap: 8px;

            .status-dot {
              width: 8px;
              height: 8px;
              border-radius: 50%;

              &.status-checking {
                background-color: var(--el-color-warning);
                animation: pulse 2s ease-in-out infinite;
              }

              &.status-online {
                background-color: var(--el-color-success);
              }

              &.status-offline {
                background-color: var(--el-color-danger);
              }
            }

            .status-text {
              font-size: 13px;
              font-weight: 500;
              color: var(--el-text-color-regular);

              &.disabled {
                color: var(--el-text-color-placeholder);
              }
            }
          }

          .status-actions {
            display: flex;
            gap: 8px;
          }
        }
      }
    }
  }

  .help-content {
    h4 {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .help-sections {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;

      .help-section {
        h5 {
          margin: 0 0 8px 0;
          font-size: 13px;
          font-weight: 600;
          color: var(--el-text-color-primary);
        }

        ul {
          margin: 0;
          padding-left: 16px;

          li {
            margin-bottom: 4px;
            font-size: 13px;
            color: var(--el-text-color-regular);

            strong {
              color: var(--el-text-color-primary);
            }
          }
        }
      }
    }
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.1);
  }
}
</style>