<template>
  <el-card class="upgrade-card" shadow="hover">
    <div class="upgrade-content">
      <div class="upgrade-icon">
        <el-icon size="64"><Trophy /></el-icon>
      </div>
      <h3>🎓 解锁高级课程</h3>
      <p class="course-title">从散户到系统交易者：AI赋能的可进化投资法</p>
      <p class="description">
        一套完整的投资系统构建课程，包含24节精心设计的课程，涵盖从基础概念到实战应用的完整投资闭环。
      </p>
      <div class="features">
        <div class="feature-item">
          <el-icon><Check /></el-icon>
          <span>24节系统化课程</span>
        </div>
        <div class="feature-item">
          <el-icon><Check /></el-icon>
          <span>从基础到实战的完整体系</span>
        </div>
        <div class="feature-item">
          <el-icon><Check /></el-icon>
          <span>AI赋能的投资方法</span>
        </div>
        <div class="feature-item">
          <el-icon><Check /></el-icon>
          <span>可进化投资系统构建</span>
        </div>
      </div>
      <el-button 
        type="primary" 
        size="large" 
        @click="goToLicense"
        style="margin-top: 24px"
      >
        <el-icon><Key /></el-icon>
        前往认证成为高级学员
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Trophy, Check, Key } from '@element-plus/icons-vue'

const router = useRouter()

const goToLicense = () => {
  router.push('/settings/license')
}
</script>

<style scoped lang="scss">
.upgrade-card {
  margin-top: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;

  :deep(.el-card__body) {
    padding: 40px;
  }
}

.upgrade-content {
  text-align: center;
  color: white;

  .upgrade-icon {
    margin-bottom: 20px;
    
    .el-icon {
      color: #ffd700;
    }
  }

      h3 {
        font-size: 24px;
        margin-bottom: 12px;
        color: white;
      }

      .course-title {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 16px;
        color: #ffd700;
      }

      .description {
    font-size: 16px;
    line-height: 1.8;
    margin-bottom: 24px;
    opacity: 0.95;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
  }

  .features {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 24px;
    margin-bottom: 24px;

    .feature-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;

      .el-icon {
        color: #ffd700;
      }
    }
  }
}

// 暗黑模式适配
:global(html.dark) {
  .upgrade-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  }
}
</style>

