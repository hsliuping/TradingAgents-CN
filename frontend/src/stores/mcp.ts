import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { mcpApi, type MCPConnector, type MCPUpdatePayload } from '@/api/mcp'

export const useMCPStore = defineStore('mcp', () => {
  const connectors = ref<MCPConnector[]>([])
  const loading = ref(false)
  const saving = ref(false)

  const enabledCount = computed(() => connectors.value.filter((c) => c.enabled).length)

  const fetchConnectors = async () => {
    loading.value = true
    try {
      const res = await mcpApi.list()
      connectors.value = res.data || []
    } catch (error) {
      console.error('加载 MCP 连接器失败', error)
      ElMessage.error('加载 MCP 连接器失败')
    } finally {
      loading.value = false
    }
  }

  const batchUpdate = async (payload: MCPUpdatePayload) => {
    saving.value = true
    try {
      await mcpApi.batchUpdate(payload)
      ElMessage.success('配置已更新')
      await fetchConnectors()
    } catch (error) {
      console.error('更新 MCP 配置失败', error)
      ElMessage.error('更新配置失败')
      throw error
    } finally {
      saving.value = false
    }
  }

  const toggleConnector = async (name: string, enabled: boolean) => {
    // 乐观更新
    const original = connectors.value.find(c => c.name === name)?.enabled
    connectors.value = connectors.value.map(c => 
      c.name === name ? { ...c, enabled } : c
    )
    
    try {
      await mcpApi.toggle(name, enabled)
      ElMessage.success(enabled ? '已启用连接器' : '已停用连接器')
    } catch (error) {
      console.error('切换连接器状态失败', error)
      ElMessage.error('切换状态失败')
      // 回滚
      if (original !== undefined) {
          connectors.value = connectors.value.map(c => 
            c.name === name ? { ...c, enabled: original } : c
          )
      }
      throw error
    }
  }

  const deleteConnector = async (name: string) => {
    try {
      await mcpApi.delete(name)
      connectors.value = connectors.value.filter((item) => item.name !== name)
      ElMessage.success('已删除连接器')
    } catch (error) {
      console.error('删除 MCP 连接器失败', error)
      ElMessage.error('删除连接器失败')
      throw error
    }
  }

  return {
    connectors,
    loading,
    saving,
    enabledCount,
    fetchConnectors,
    batchUpdate,
    toggleConnector,
    deleteConnector
  }
})
