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
          {{ cat.name }} ({{ cat.count }})
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
              <el-tag size="small" :type="getLicenseType(agent.license_tier)">{{ agent.license_tier }}</el-tag>
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

    <!-- Agent详情弹窗 -->
    <el-dialog
      v-model="detailsVisible"
      :title="selectedAgent?.name"
      width="700px"
    >
      <div v-if="selectedAgent" class="agent-details">
        <div class="header-info">
          <div class="icon-wrapper" :style="{ color: selectedAgent.color, backgroundColor: selectedAgent.color + '15' }">
            {{ selectedAgent.icon }}
          </div>
          <div class="basic-info">
            <div class="id-row">ID: {{ selectedAgent.id }}</div>
            <div class="desc">{{ selectedAgent.description }}</div>
          </div>
        </div>

        <el-divider />

        <div class="detail-grid">
          <div class="grid-item">
            <span class="label">分类</span>
            <span class="value">{{ getCategoryName(selectedAgent.category) }}</span>
          </div>
          <div class="grid-item">
            <span class="label">权限等级</span>
            <el-tag size="small">{{ selectedAgent.license_tier }}</el-tag>
          </div>
        </div>

        <div class="detail-section">
          <h3>输入/输出</h3>
          <div class="io-container">
            <div class="io-box">
              <span class="io-label">输入</span>
              <div class="io-tags">
                <el-tag v-for="in_item in selectedAgent.inputs" :key="in_item" type="info" size="small">
                  {{ in_item }}
                </el-tag>
                <span v-if="!selectedAgent.inputs.length" class="empty-text">无特定输入</span>
              </div>
            </div>
            <div class="io-arrow">→</div>
            <div class="io-box">
              <span class="io-label">输出</span>
              <div class="io-tags">
                <el-tag v-for="out_item in selectedAgent.outputs" :key="out_item" type="success" size="small">
                  {{ out_item }}
                </el-tag>
                <span v-if="!selectedAgent.outputs.length" class="empty-text">无特定输出</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 这里可以预留工具配置的展示，虽然目前API没有直接返回该Agent配置了哪些工具 -->
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi, type AgentMetadata, type AgentCategory } from '@/api/agents'

const loading = ref(false)
const agents = ref<AgentMetadata[]>([])
const categories = ref<AgentCategory[]>([])
const currentCategory = ref('')
const detailsVisible = ref(false)
const selectedAgent = ref<AgentMetadata | null>(null)

const getCategoryName = (categoryId: string) => {
  const category = categories.value.find(c => c.id === categoryId)
  return category ? category.name : categoryId
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

const filteredAgents = computed(() => {
  if (!currentCategory.value) {
    return agents.value
  }
  return agents.value.filter(a => a.category === currentCategory.value)
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
  selectedAgent.value = agent
  detailsVisible.value = true
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

.agent-details {
  .header-info {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;
    
    .icon-wrapper {
      width: 64px;
      height: 64px;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      margin-right: 20px;
    }
    
    .basic-info {
      .id-row {
        color: var(--el-text-color-secondary);
        font-size: 13px;
        margin-bottom: 8px;
      }
      
      .desc {
        font-size: 15px;
        line-height: 1.6;
      }
    }
  }
  
  .detail-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    margin: 20px 0;
    
    .grid-item {
      display: flex;
      align-items: center;
      
      .label {
        color: var(--el-text-color-secondary);
        width: 80px;
      }
      
      .value {
        font-weight: 500;
      }
    }
  }
  
  .io-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--el-fill-color-light);
    padding: 20px;
    border-radius: 8px;
    
    .io-box {
      flex: 1;
      display: flex;
      flex-direction: column;
      
      .io-label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-bottom: 8px;
        text-transform: uppercase;
      }
      
      .io-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        
        .empty-text {
          font-size: 12px;
          color: var(--el-text-color-placeholder);
          font-style: italic;
        }
      }
    }
    
    .io-arrow {
      margin: 0 20px;
      color: var(--el-text-color-placeholder);
      font-size: 20px;
    }
  }
}
</style>
