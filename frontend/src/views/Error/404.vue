<template>
  <div class="error-404">
    <div class="error-container">
      <div class="error-content">
        <div class="error-image">
          <img src="/404-illustration.svg" alt="404" />
        </div>
        
        <div class="error-info">
          <h1 class="error-code">404</h1>
          <h2 class="error-title">页面不存在</h2>
          <p class="error-description">
            抱歉，您访问的页面不存在或已被移除。
            请检查URL是否正确，或返回首页继续浏览。
          </p>
          
          <div class="error-actions">
            <el-button type="primary" size="large" @click="goHome">
              <el-icon><HomeFilled /></el-icon>
              返回首页
            </el-button>
            <el-button size="large" @click="goBack">
              <el-icon><ArrowLeft /></el-icon>
              返回上页
            </el-button>
          </div>
        </div>
      </div>
      
      <!-- 推荐链接 -->
      <div class="suggestions">
        <h3>您可能想要访问：</h3>
        <div class="suggestion-links">
          <el-link type="primary" @click="$router.push('/dashboard')">
            <el-icon><House /></el-icon>
            仪表板
          </el-link>
          <el-link type="primary" @click="$router.push('/analysis/single')">
            <el-icon><TrendCharts /></el-icon>
            单股分析
          </el-link>
          <el-link type="primary" @click="$router.push('/screening')">
            <el-icon><Search /></el-icon>
            股票筛选
          </el-link>
          <el-link type="primary" @click="$router.push('/queue')">
            <el-icon><Document /></el-icon>
            队列管理
          </el-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  HomeFilled,
  ArrowLeft,
  House,
  TrendCharts,
  Search,
  Document
} from '@element-plus/icons-vue'

const router = useRouter()

const goHome = () => {
  router.push('/')
}

const goBack = () => {
  if (window.history.length > 1) {
    router.go(-1)
  } else {
    router.push('/')
  }
}
</script>

<style lang="scss" scoped>
.error-404 {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 20px;
}

.error-container {
  max-width: 800px;
  width: 100%;
  text-align: center;
}

.error-content {
  display: flex;
  align-items: center;
  gap: 48px;
  margin-bottom: 48px;

  .error-image {
    flex: 1;
    max-width: 400px;

    img {
      width: 100%;
      height: auto;
    }
  }

  .error-info {
    flex: 1;
    text-align: left;

    .error-code {
      font-size: 120px;
      font-weight: 700;
      color: var(--el-color-primary);
      margin: 0;
      line-height: 1;
    }

    .error-title {
      font-size: 32px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 16px 0;
    }

    .error-description {
      font-size: 16px;
      color: var(--el-text-color-regular);
      line-height: 1.6;
      margin-bottom: 32px;
    }

    .error-actions {
      display: flex;
      gap: 16px;
    }
  }
}

.suggestions {
  background: white;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 24px 0;
  }

  .suggestion-links {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;

    .el-link {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      background: var(--el-fill-color-lighter);
      border-radius: 8px;
      text-decoration: none;
      transition: all 0.3s ease;

      &:hover {
        background: var(--el-color-primary-light-9);
        transform: translateY(-2px);
      }

      .el-icon {
        font-size: 20px;
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .error-404 {
    .error-content {
      flex-direction: column;
      text-align: center;

      .error-info {
        text-align: center;

        .error-actions {
          justify-content: center;
          flex-wrap: wrap;
        }
      }
    }

    .suggestions {
      padding: 24px 16px;

      .suggestion-links {
        grid-template-columns: 1fr;
      }
    }
  }
}
</style>
