<template>
  <div class="agent-availability">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Agent 可用性检查</span>
          <el-button type="primary" @click="refresh">刷新</el-button>
        </div>
      </template>

      <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
        <p><strong>许可证状态：</strong></p>
        <p>isPro: {{ licenseStore.isPro }}</p>
        <p>plan: {{ licenseStore.plan }}</p>
        <p>is_valid: {{ licenseStore.licenseInfo?.is_valid }}</p>
      </el-alert>

      <el-table :data="agentList" border>
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="id" label="ID" width="200" />
        <el-table-column prop="license_tier" label="许可证等级" width="120">
          <template #default="{ row }">
            <el-tag :type="getTierType(row.license_tier)">
              {{ row.license_tier }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="是否可用" width="120">
          <template #default="{ row }">
            <el-tag :type="isAvailable(row) ? 'success' : 'danger'">
              {{ isAvailable(row) ? '可用' : '锁定' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检查逻辑" min-width="300">
          <template #default="{ row }">
            <pre>{{ getCheckLogic(row) }}</pre>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useLicenseStore } from '@/stores/license'
import { agentApi } from '@/api/agents'
import { ElMessage } from 'element-plus'

const licenseStore = useLicenseStore()
const agentList = ref<any[]>([])

const isAvailable = (agent: any) => {
  if (!agent.license_tier) return true
  const tier = agent.license_tier.toLowerCase()
  if (tier === 'free') return true
  if (tier === 'basic') return true
  if (['pro', 'enterprise'].includes(tier)) {
    return licenseStore.isPro
  }
  return true
}

const getCheckLogic = (agent: any) => {
  if (!agent.license_tier) {
    return '无 license_tier → 默认可用'
  }
  const tier = agent.license_tier.toLowerCase()
  if (tier === 'free') {
    return 'tier=free → 可用'
  }
  if (tier === 'basic') {
    return 'tier=basic → 可用'
  }
  if (['pro', 'enterprise'].includes(tier)) {
    return `tier=${tier} → isPro=${licenseStore.isPro} → ${licenseStore.isPro ? '可用' : '锁定'}`
  }
  return '未知逻辑'
}

const getTierType = (tier: string) => {
  const types: Record<string, any> = {
    free: 'info',
    basic: 'success',
    pro: 'warning',
    enterprise: 'danger'
  }
  return types[tier?.toLowerCase()] || 'info'
}

const loadAgents = async () => {
  try {
    agentList.value = await agentApi.listAll()
    console.log('📋 加载 Agent 列表:', agentList.value.length)
  } catch (error) {
    console.error('加载失败:', error)
    ElMessage.error('加载失败')
  }
}

const refresh = async () => {
  await licenseStore.verifyLicense(true)
  await loadAgents()
  ElMessage.success('刷新成功')
}

onMounted(async () => {
  if (licenseStore.appToken) {
    await licenseStore.verifyLicense()
  }
  await loadAgents()
})
</script>

<style scoped lang="scss">
.agent-availability {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  pre {
    font-size: 12px;
    margin: 0;
  }
}
</style>

