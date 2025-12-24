/**
 * 个人交易计划状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type {
  TradingSystem,
  TradingSystemCreatePayload,
  TradingSystemUpdatePayload
} from '@/api/tradingSystem'
import * as tradingSystemApi from '@/api/tradingSystem'

export const useTradingSystemStore = defineStore('tradingSystem', () => {
  // ==================== 状态 ====================
  
  /** 交易计划列表 */
  const systems = ref<TradingSystem[]>([])
  
  /** 当前激活的交易计划 */
  const activeSystem = ref<TradingSystem | null>(null)
  
  /** 当前查看的交易计划 */
  const currentSystem = ref<TradingSystem | null>(null)
  
  /** 加载状态 */
  const loading = ref(false)
  
  /** 列表加载状态 */
  const listLoading = ref(false)

  // ==================== 计算属性 ====================
  
  /** 是否有激活的交易计划 */
  const hasActiveSystem = computed(() => activeSystem.value !== null)
  
  /** 交易计划总数 */
  const totalSystems = computed(() => systems.value.length)
  
  /** 激活系统的名称 */
  const activeSystemName = computed(() => activeSystem.value?.name || '未设置')

  // ==================== 方法 ====================
  
  /**
   * 获取交易计划列表
   */
  async function fetchSystems(isActive?: boolean) {
    listLoading.value = true
    try {
      const response = await tradingSystemApi.getTradingSystems(isActive)
      systems.value = response.data.systems || []
      return systems.value
    } catch (error: any) {
      console.error('获取交易计划列表失败:', error)
      ElMessage.error('获取交易计划列表失败')
      systems.value = []
      return []
    } finally {
      listLoading.value = false
    }
  }

  /**
   * 获取激活的交易计划
   */
  async function fetchActiveSystem() {
    loading.value = true
    try {
      const response = await tradingSystemApi.getActiveTradingSystem()
      activeSystem.value = response.data.system
      return activeSystem.value
    } catch (error: any) {
      console.error('获取激活交易计划失败:', error)
      ElMessage.error('获取激活交易计划失败')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取交易计划详情
   */
  async function fetchSystem(systemId: string) {
    loading.value = true
    try {
      const response = await tradingSystemApi.getTradingSystem(systemId)
      currentSystem.value = response.data.system
      return currentSystem.value
    } catch (error: any) {
      console.error('获取交易计划详情失败:', error)
      ElMessage.error('获取交易计划详情失败')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建交易计划
   */
  async function createSystem(payload: TradingSystemCreatePayload) {
    loading.value = true
    try {
      const response = await tradingSystemApi.createTradingSystem(payload)
      const newSystem = response.data.system
      systems.value.unshift(newSystem)
      // 如果是激活状态，更新激活系统
      if (newSystem.is_active) {
        activeSystem.value = newSystem
      }
      ElMessage.success('交易计划创建成功')
      return newSystem
    } catch (error: any) {
      console.error('创建交易计划失败:', error)
      ElMessage.error('创建交易计划失败')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新交易计划
   */
  async function updateSystem(systemId: string, payload: TradingSystemUpdatePayload) {
    loading.value = true
    try {
      const response = await tradingSystemApi.updateTradingSystem(systemId, payload)
      const updatedSystem = response.data.system
      // 更新列表中的系统
      const index = systems.value.findIndex(s => s.id === systemId)
      if (index !== -1) {
        systems.value[index] = updatedSystem
      }
      // 如果是激活状态，更新激活系统
      if (updatedSystem.is_active) {
        activeSystem.value = updatedSystem
      }
      // 如果是当前查看的系统，更新当前系统
      if (currentSystem.value?.id === systemId) {
        currentSystem.value = updatedSystem
      }
      ElMessage.success('交易计划更新成功')
      return updatedSystem
    } catch (error: any) {
      console.error('更新交易计划失败:', error)
      ElMessage.error('更新交易计划失败')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除交易计划
   */
  async function deleteSystem(systemId: string) {
    loading.value = true
    try {
      await tradingSystemApi.deleteTradingSystem(systemId)
      // 从列表中移除
      systems.value = systems.value.filter(s => s.id !== systemId)
      // 如果删除的是激活系统，清空激活系统
      if (activeSystem.value?.id === systemId) {
        activeSystem.value = null
      }
      // 如果删除的是当前查看的系统，清空当前系统
      if (currentSystem.value?.id === systemId) {
        currentSystem.value = null
      }
      ElMessage.success('交易计划删除成功')
      return true
    } catch (error: any) {
      console.error('删除交易计划失败:', error)
      ElMessage.error('删除交易计划失败')
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 激活交易计划
   */
  async function activateSystem(systemId: string) {
    loading.value = true
    try {
      const response = await tradingSystemApi.activateTradingSystem(systemId)
      const activatedSystem = response.data.system
      // 更新列表中所有系统的激活状态
      systems.value.forEach(s => {
        s.is_active = s.id === systemId
      })
      // 更新激活系统
      activeSystem.value = activatedSystem
      ElMessage.success('交易计划激活成功')
      return activatedSystem
    } catch (error: any) {
      console.error('激活交易计划失败:', error)
      ElMessage.error('激活交易计划失败')
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 重置状态
   */
  function reset() {
    systems.value = []
    activeSystem.value = null
    currentSystem.value = null
    loading.value = false
    listLoading.value = false
  }

  return {
    // 状态
    systems,
    activeSystem,
    currentSystem,
    loading,
    listLoading,

    // 计算属性
    hasActiveSystem,
    totalSystems,
    activeSystemName,

    // 方法
    fetchSystems,
    fetchActiveSystem,
    fetchSystem,
    createSystem,
    updateSystem,
    deleteSystem,
    activateSystem,
    reset
  }
})


