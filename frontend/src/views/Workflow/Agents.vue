<template>
  <div class="agents-config-page">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><UserFilled /></el-icon>
          Agent配置
        </h1>
        <span class="subtitle">查看和管理智能体配置</span>
      </div>
      <div class="header-right">
        <el-button @click="refreshAgents">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="filter-section">
      <el-radio-group v-model="currentCategory" @change="handleCategoryChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat.id" :label="cat.id">
          {{ cat.name }} ({{ getCategoryCount(cat.id) }})
        </el-radio-button>
      </el-radio-group>
    </div>

    <el-row :gutter="20">
      <el-col v-for="agent in filteredAgents" :key="agent.id" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="agent-card" shadow="hover" :body-style="{ padding: '0px' }">
          <div class="agent-header" :style="{ backgroundColor: agent.color + '15' }">
            <div class="agent-icon" :style="{ color: agent.color }">
              {{ agent.icon || '🤖' }}
            </div>
            <div class="agent-title">
              <h3>{{ agent.name }}</h3>
<el-tag size="small" :type="getLicenseType(agent.license_tier) || undefined">{{ agent.license_tier }}</el-tag>
            </div>
          </div>
          
          <div class="agent-body">
            <p class="description">{{ agent.description }}</p>
            
            <div class="tags">
              <el-tag v-for="tag in agent.tags" :key="tag" size="small" effect="plain" class="tag-item">
                {{ tag }}
              </el-tag>
            </div>

            <div class="status-bar">
              <span v-if="agent.is_available" class="status available">
                <el-icon><CircleCheckFilled /></el-icon> 可用
              </span>
              <span v-else class="status locked">
                <el-icon><Lock /></el-icon> {{ agent.locked_reason || '不可用' }}
              </span>
            </div>
          </div>
          
          <div class="agent-footer">
            <el-button text class="action-btn" @click="showAgentDetails(agent)">
              查看详情
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { agentApi, type AgentMetadata, type AgentCategory, type AgentToolsConfig, type AgentToolsUpdate } from '@/api/agents'
import { toolsApi, type ToolMetadata } from '@/api/tools'

const router = useRouter()

const loading = ref(false)
const agents = ref<AgentMetadata[]>([])
const categories = ref<AgentCategory[]>([])
const currentCategory = ref('')

const getCategoryName = (categoryId: string) => {
  const category = categories.value.find(c => c.id === categoryId)
  return category ? category.name : categoryId
}

// 获取分类的 v2.0 agent 数量
const getCategoryCount = (categoryId: string) => {
  const v2Agents = agents.value.filter(isV2Agent)
  if (!categoryId) {
    return v2Agents.length
  }
  return v2Agents.filter(a => a.category === categoryId).length
}

const getLicenseType = (tier: string) => {
  switch (tier) {
    case 'free': return 'info'
    case 'basic': return 'success'
    case 'pro': return 'warning'
    case 'enterprise': return 'danger'
    default: return ''
  }
}

// 判断是否为 v2.0 agent
const isV2Agent = (agent: AgentMetadata): boolean => {
  const id = (agent.id || '').toLowerCase()
  const name = (agent.name || '').toLowerCase()
  const tags = Array.isArray(agent.tags) ? agent.tags : []
  
  // 1. ID 明确包含 _v2 或 v2_（最可靠的判断方式）
  if (id.includes('_v2') || id.startsWith('v2_')) {
    return true
  }
  
  // 2. 名称包含 v2.0 或 v2
  if (name.includes('v2.0') || name.includes(' v2')) {
    return true
  }
  
  // 3. tags 包含 v2 相关标签
  if (tags.some(tag => String(tag).toLowerCase().includes('v2'))) {
    return true
  }
  
  // 默认：过滤掉非v2.0的agent
  return false
}

const filteredAgents = computed(() => {
  // 🔥 只显示v2.0的agent，屏蔽非v2.0的agent
  const v2Agents = agents.value.filter(isV2Agent)
  
  // 再根据分类过滤
  if (!currentCategory.value) {
    return v2Agents
  }
  return v2Agents.filter(a => a.category === currentCategory.value)
})

const loadData = async () => {
  loading.value = true
  try {
    const [agentsData, categoriesData] = await Promise.all([
      agentApi.listAvailable(), // 使用 listAvailable 以获取 availability info
      agentApi.getCategories()
    ])
    agents.value = agentsData
    categories.value = categoriesData
  } catch (error) {
    console.error('加载Agent失败:', error)
    ElMessage.error('加载Agent列表失败')
  } finally {
    loading.value = false
  }
}

const refreshAgents = () => {
  loadData()
}

const handleCategoryChange = () => {
  // logic if needed
}

const showAgentDetails = (agent: AgentMetadata) => {
  // 跳转到详情页面
  router.push({
    name: 'AgentDetail',
    params: { id: agent.id }
  })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.agents-config-page {
  padding: 20px;
  background-color: var(--el-bg-color);
  min-height: calc(100vh - 60px);

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      h1 {
        display: flex;
        align-items: center;
        font-size: 24px;
        margin: 0 0 8px 0;
        
        .header-icon {
          margin-right: 12px;
          color: var(--el-color-primary);
        }
      }

      .subtitle {
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }
  }

  .filter-section {
    margin-bottom: 24px;
  }
}

.agent-card {
  margin-bottom: 20px;
  transition: all 0.3s;
  border: 1px solid var(--el-border-color-lighter);
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.1);
  }
  
  .agent-header {
    padding: 20px;
    display: flex;
    align-items: flex-start;
    
    .agent-icon {
      font-size: 32px;
      margin-right: 16px;
      background: #fff;
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    .agent-title {
      flex: 1;
      
      h3 {
        margin: 0 0 8px 0;
        font-size: 16px;
        line-height: 1.4;
      }
    }
  }
  
  .agent-body {
    padding: 20px;
    
    .description {
      color: var(--el-text-color-secondary);
      font-size: 13px;
      line-height: 1.6;
      height: 42px;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      margin-bottom: 16px;
    }
    
    .tags {
      margin-bottom: 16px;
      height: 24px;
      overflow: hidden;
      
      .tag-item {
        margin-right: 6px;
      }
    }
    
    .status-bar {
      font-size: 12px;
      
      .status {
        display: flex;
        align-items: center;
        gap: 4px;
        
        &.available {
          color: var(--el-color-success);
        }
        &.locked {
          color: var(--el-text-color-placeholder);
        }
      }
    }
  }
  
  .agent-footer {
    padding: 10px 20px;
    border-top: 1px solid var(--el-border-color-lighter);
    text-align: right;
    
    .action-btn {
      padding: 0;
    }
  }
}
</style>
