<template>
  <div class="data-import-container">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Upload /></el-icon>
        数据导入管理
      </h1>
      <p class="page-description">
        通过 API 接口批量导入股票数据、社媒消息等数据到系统中
      </p>
    </div>

    <el-row :gutter="20">
      <!-- 股票数据批量导入 -->
      <el-col :span="12">
        <el-card class="import-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><TrendCharts /></el-icon>
                股票数据批量导入
              </span>
              <el-tag v-if="!isPro" type="warning" size="small">PRO</el-tag>
            </div>
          </template>

          <div class="card-content">
            <p class="description">
              通过 API 接口批量导入股票基本信息、实时行情、财务数据和新闻数据
            </p>

            <div class="features">
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>股票基本信息批量导入</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>实时行情数据批量导入</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>财务数据批量导入</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>新闻数据批量导入</span>
              </div>
            </div>

            <div class="actions">
              <el-button type="primary" @click="goToStockDataApiGuide">
                <el-icon><Document /></el-icon>
                查看 API 文档
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 社媒消息批量导入 -->
      <el-col :span="12">
        <el-card class="import-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><ChatDotRound /></el-icon>
                社媒消息批量导入
              </span>
              <el-tag v-if="!isPro" type="warning" size="small">PRO</el-tag>
            </div>
          </template>

          <div class="card-content">
            <p class="description">
              通过 API 接口批量导入社交媒体消息数据，支持多平台数据源
            </p>

            <div class="features">
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>支持多平台消息导入</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>自动情绪分析</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>关键词提取</span>
              </div>
              <div class="feature-item">
                <el-icon color="#409EFF"><Check /></el-icon>
                <span>重要性评估</span>
              </div>
            </div>

            <div class="actions">
              <el-button type="primary" @click="goToSocialMediaApiGuide">
                <el-icon><Document /></el-icon>
                查看 API 文档
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- PRO 权限提示 -->
    <el-alert
      v-if="!isPro"
      type="warning"
      :closable="false"
      show-icon
      style="margin-top: 20px;"
    >
      <template #title>
        <strong>批量导入功能为高级学员专属</strong>
      </template>
      <p>
        您当前是免费用户，无法使用批量导入功能。
        <router-link to="/settings/license">点击这里</router-link> 升级到 PRO 版本。
      </p>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Upload, TrendCharts, ChatDotRound, Document, Check } from '@element-plus/icons-vue'
import { useLicenseStore } from '@/stores/license'

const router = useRouter()
const licenseStore = useLicenseStore()

// 检查是否为 PRO 用户
const isPro = computed(() => licenseStore.isPro)

// 跳转到股票数据 API 指南
const goToStockDataApiGuide = () => {
  router.push('/settings/stock-data/api-guide')
}

// 跳转到社媒消息 API 指南
const goToSocialMediaApiGuide = () => {
  router.push('/settings/social-media/api-guide')
}
</script>

<style scoped lang="scss">
.data-import-container {
  padding: 20px;

  .page-header {
    margin-bottom: 24px;

    .page-title {
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 8px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .page-description {
      font-size: 14px;
      color: var(--el-text-color-secondary);
      margin: 0;
    }
  }

  .import-card {
    height: 100%;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
      font-size: 16px;

      span {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }

    .card-content {
      .description {
        color: var(--el-text-color-regular);
        margin-bottom: 20px;
        line-height: 1.6;
      }

      .features {
        margin-bottom: 24px;

        .feature-item {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          color: var(--el-text-color-regular);

          .el-icon {
            font-size: 16px;
          }
        }
      }

      .actions {
        display: flex;
        gap: 12px;
      }
    }
  }
}
</style>

