<template>
  <div class="guide-page">
    <!-- 欢迎标题 -->
    <div class="guide-header">
      <h1 class="guide-title">
        <el-icon><Document /></el-icon>
        欢迎使用 TradingAgents-CN
      </h1>
      <p class="guide-subtitle">按照以下步骤完成初始设置，开始您的AI股票分析之旅</p>
    </div>

    <!-- 步骤列表 -->
    <div class="steps-container">
      <el-steps :active="currentStep" direction="vertical" finish-status="success">
        <!-- 步骤1：获取Token -->
        <el-step title="获取API Token" description="获取大模型和数据源的API密钥">
          <template #description>
            <div class="step-content">
              <p>在使用系统之前，您需要准备以下API密钥：</p>
              <ul class="step-list">
                <li>
                  <strong>大模型API密钥：</strong>
                  支持 OpenAI、Claude、智谱AI、DeepSeek 等主流大语言模型
                </li>
                <li>
                  <strong>数据源API密钥：</strong>
                  支持 Tushare、AKShare、Baostock 等数据源
                </li>
              </ul>
              <el-button type="primary" @click="goToSettings">
                <el-icon><Setting /></el-icon>
                前往配置页面
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤2：填写Token -->
        <el-step title="填写Token配置" description="在设置页面填写您的API密钥">
          <template #description>
            <div class="step-content">
              <p>在设置页面完成以下配置：</p>
              <ul class="step-list">
                <li>配置大模型提供商和API密钥</li>
                <li>配置数据源提供商和API密钥</li>
                <li>保存配置并验证连接</li>
              </ul>
              <el-button type="primary" @click="goToSettings">
                <el-icon><Setting /></el-icon>
                前往设置页面
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤3：同步数据 -->
        <el-step title="同步股票数据" description="同步基础股票数据到系统">
          <template #description>
            <div class="step-content">
              <p>完成数据同步，获取最新的股票基础信息：</p>
              <ul class="step-list">
                <li>在设置页面找到"多数据源同步"功能</li>
                <li>选择需要同步的市场（A股、港股、美股等）</li>
                <li>执行同步操作，等待数据同步完成</li>
              </ul>
              <el-button type="primary" @click="goToSync">
                <el-icon><Refresh /></el-icon>
                前往数据同步
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤4：搜索股票 -->
        <el-step title="搜索并添加自选股" description="搜索感兴趣的股票并添加到自选列表">
          <template #description>
            <div class="step-content">
              <p>开始使用股票筛选功能：</p>
              <ul class="step-list">
                <li>在"股票筛选"页面搜索股票代码或名称</li>
                <li>查看股票详情信息</li>
                <li>将感兴趣的股票添加到"股票关注列表"</li>
              </ul>
              <el-button type="primary" @click="goToScreening">
                <el-icon><Search /></el-icon>
                前往股票筛选
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤5：完成第一次分析 -->
        <el-step title="完成第一次分析" description="对自选股进行AI分析">
          <template #description>
            <div class="step-content">
              <p>开始您的第一次AI股票分析：</p>
              <ul class="step-list">
                <li>在"单股分析"页面选择要分析的股票</li>
                <li>选择分析偏好（激进、保守、中性）</li>
                <li>点击"开始分析"，等待AI完成分析</li>
                <li>查看详细的分析报告和操作建议</li>
              </ul>
              <el-button type="primary" @click="goToAnalysis">
                <el-icon><TrendCharts /></el-icon>
                开始分析
              </el-button>
            </div>
          </template>
        </el-step>
      </el-steps>
    </div>

    <!-- 快速操作 -->
    <div class="quick-actions">
      <h3>快速操作</h3>
      <div class="action-buttons">
        <el-button type="primary" @click="goToSettings">
          <el-icon><Setting /></el-icon>
          配置管理
        </el-button>
        <el-button @click="goToScreening">
          <el-icon><Search /></el-icon>
          股票筛选
        </el-button>
        <el-button @click="goToAnalysis">
          <el-icon><TrendCharts /></el-icon>
          单股分析
        </el-button>
        <el-button @click="goToDashboard">
          <el-icon><HomeFilled /></el-icon>
          返回首页
        </el-button>
      </div>
    </div>

    <!-- 提示信息 -->
    <el-alert
      title="提示"
      type="info"
      :closable="false"
      show-icon
      class="info-alert"
    >
      <template #default>
        <p>如果您在设置过程中遇到问题，可以：</p>
        <ul>
          <li>查看 <a href="/about" target="_blank">关于页面</a> 了解更多信息</li>
          <li>访问 <a href="/learning" target="_blank">学习中心</a> 查看使用教程</li>
          <li>联系技术支持获取帮助</li>
        </ul>
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Document,
  Setting,
  Refresh,
  Search,
  TrendCharts,
  HomeFilled
} from '@element-plus/icons-vue'

const router = useRouter()
const currentStep = ref(0) // 当前步骤，可以根据用户完成情况动态设置

const goToSettings = () => {
  router.push('/settings/config')
}

const goToSync = () => {
  router.push('/settings/sync')
}

const goToScreening = () => {
  router.push('/screening')
}

const goToAnalysis = () => {
  router.push('/analysis/single')
}

const goToDashboard = () => {
  router.push('/dashboard')
}
</script>

<style lang="scss" scoped>
.guide-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 24px;

  .guide-header {
    text-align: center;
    margin-bottom: 48px;

    .guide-title {
      font-size: 36px;
      font-weight: 700;
      color: var(--el-text-color-primary);
      margin: 0 0 16px 0;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;

      .el-icon {
        font-size: 40px;
        color: var(--el-color-primary);
      }
    }

    .guide-subtitle {
      font-size: 18px;
      color: var(--el-text-color-regular);
      margin: 0;
    }
  }

  .steps-container {
    margin-bottom: 48px;

    :deep(.el-steps) {
      .el-step__head {
        .el-step__icon {
          width: 40px;
          height: 40px;
          font-size: 20px;
        }
      }

      .el-step__title {
        font-size: 18px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .el-step__description {
        margin-top: 16px;
        padding-left: 0;
      }
    }

    .step-content {
      padding: 20px;
      background: var(--el-bg-color-page);
      border-radius: 8px;
      border-left: 4px solid var(--el-color-primary);

      p {
        margin: 0 0 16px 0;
        color: var(--el-text-color-regular);
        font-size: 15px;
        line-height: 1.6;
      }

      .step-list {
        margin: 0 0 20px 0;
        padding-left: 24px;
        color: var(--el-text-color-regular);

        li {
          margin-bottom: 12px;
          line-height: 1.6;

          strong {
            color: var(--el-text-color-primary);
            font-weight: 600;
          }

          &:last-child {
            margin-bottom: 0;
          }
        }
      }

      .el-button {
        margin-top: 8px;
      }
    }
  }

  .quick-actions {
    background: var(--el-bg-color);
    border-radius: 12px;
    padding: 32px;
    margin-bottom: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    border: 1px solid var(--el-border-color-lighter);

    h3 {
      margin: 0 0 24px 0;
      font-size: 20px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .action-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;

      .el-button {
        flex: 1;
        min-width: 150px;
      }
    }
  }

  .info-alert {
    margin-top: 32px;

    :deep(.el-alert__content) {
      p {
        margin: 0 0 12px 0;
        color: var(--el-text-color-regular);
      }

      ul {
        margin: 0;
        padding-left: 24px;
        color: var(--el-text-color-regular);

        li {
          margin-bottom: 8px;
          line-height: 1.6;

          a {
            color: var(--el-color-primary);
            text-decoration: none;

            &:hover {
              text-decoration: underline;
            }
          }
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .guide-page {
    padding: 24px 16px;

    .guide-header {
      .guide-title {
        font-size: 28px;
        flex-direction: column;
        gap: 8px;

        .el-icon {
          font-size: 32px;
        }
      }

      .guide-subtitle {
        font-size: 16px;
      }
    }

    .steps-container {
      :deep(.el-steps) {
        .el-step__head {
          .el-step__icon {
            width: 32px;
            height: 32px;
            font-size: 16px;
          }
        }

        .el-step__title {
          font-size: 16px;
        }
      }

      .step-content {
        padding: 16px;

        .step-list {
          padding-left: 20px;
        }
      }
    }

    .quick-actions {
      padding: 24px;

      .action-buttons {
        .el-button {
          min-width: 100%;
        }
      }
    }
  }
}
</style>
