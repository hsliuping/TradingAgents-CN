<template>
  <div class="guide-page">
    <!-- 欢迎标题 -->
    <div class="guide-header">
      <h1 class="guide-title">
        <el-icon><Document /></el-icon>
        欢迎使用 TradingAgents-CN
      </h1>
      <p class="guide-subtitle">按照以下步骤完成初始设置，开始学习AI辅助股票分析技术</p>
    </div>

    <!-- 步骤列表 -->
    <div class="steps-container">
      <el-steps :active="currentStep" direction="vertical" finish-status="success">
        <!-- 步骤1：获取大模型API密钥 -->
        <el-step title="获取大模型API密钥" description="选择并获取大语言模型的API密钥">
          <template #description>
            <div class="step-content">
              <p>系统支持多种主流大语言模型，推荐优先使用国内模型，您需要选择其中一个并获取API密钥：</p>
              <ul class="step-list">
                <li>
                  <strong>阿里云百炼：</strong>通义千问系列模型（推荐国内用户）
                  <div class="register-link-wrapper">
                    <el-link href="https://dashscope.console.aliyun.com/" target="_blank" type="primary" :underline="false" class="register-link">
                      <el-icon><Link /></el-icon>
                      立即注册百炼账号
                    </el-link>
                  </div>
                </li>
                <li>
                  <strong>DeepSeek：</strong>DeepSeek Chat 等模型（推荐国内用户）
                  <div class="register-link-wrapper">
                    <el-link href="https://platform.deepseek.com/" target="_blank" type="primary" :underline="false" class="register-link">
                      <el-icon><Link /></el-icon>
                      立即注册 DeepSeek 账号
                    </el-link>
                  </div>
                </li>
                <li><strong>智谱AI：</strong>GLM-4 等国产大模型</li>
                <li><strong>OpenAI：</strong>GPT-3.5、GPT-4 等模型</li>
                <li><strong>Claude：</strong>Anthropic 的 Claude 系列模型</li>
                <li>其他支持的大语言模型提供商</li>
              </ul>
              <p class="step-tip">💡 提示：国内用户推荐优先使用阿里云百炼或DeepSeek，访问速度更快，使用更稳定</p>
            </div>
          </template>
        </el-step>

        <!-- 步骤2：获取数据源API密钥 -->
        <el-step title="获取数据源API密钥" description="注册Tushare账号并获取API Token">
          <template #description>
            <div class="step-content">
              <p>系统使用 <strong>Tushare</strong> 作为数据源，您需要注册账号并获取API Token：</p>
              <ul class="step-list">
                <li>访问 Tushare 官网注册账号</li>
                <li>登录后在个人中心获取API Token</li>
                <li>将Token保存好，后续配置时需要用到</li>
              </ul>
              <div class="register-link-wrapper">
                <el-link href="https://tushare.pro/weborder/#/login?reg=tacn" target="_blank" type="primary" :underline="false" class="register-link">
                  <el-icon><Link /></el-icon>
                  立即注册 Tushare 账号
                </el-link>
                <el-link href="https://tushare.pro/user/index" target="_blank" type="info" :underline="false" class="register-link" style="margin-left: 12px;">
                  <el-icon><Link /></el-icon>
                  前往个人中心获取Token
                </el-link>
              </div>
            </div>
          </template>
        </el-step>

        <!-- 步骤3：填写Token配置 -->
        <el-step title="填写Token配置" description="在设置页面填写您的API密钥">
          <template #description>
            <div class="step-content">
              <p>在设置页面完成以下配置：</p>
              <ul class="step-list">
                <li>
                  <strong>配置大模型API密钥：</strong>
                  <ol style="margin-top: 8px; padding-left: 24px;">
                    <li>进入"配置管理" → "厂家管理"菜单</li>
                    <li>找到对应的厂家（如阿里云百炼、DeepSeek等）</li>
                    <li>点击"编辑"按钮</li>
                    <li>在API密钥字段中填入步骤1获取的密钥</li>
                    <li>保存配置</li>
                  </ol>
                </li>
                <li>
                  <strong>配置数据源API密钥：</strong>
                  <div style="margin-top: 8px; padding-left: 0;">
                    <p style="margin-bottom: 8px; color: var(--el-text-color-regular); font-size: 14px;">
                      <strong>重要提示：</strong>Tushare 数据源需要账户积分达到 <strong style="color: var(--el-color-warning);">2000积分以上</strong>才能使用完整功能。
                      如果积分不足，系统会自动使用免费的开源数据源（AKShare、Baostock）作为替代。
                      <strong style="color: var(--el-color-warning);">请注意：</strong>开源数据源因稳定性问题，<strong>仅作为体验本平台使用</strong>，不建议用于正式学习或分析场景。
                    </p>
                    <ol style="margin-top: 8px; padding-left: 24px;">
                      <li>进入"配置管理" → "数据源配置"菜单</li>
                      <li>找到 Tushare 数据源并点击"编辑"</li>
                      <li>填入步骤2获取的Token（在 <a href="https://tushare.pro/user/index" target="_blank" rel="noopener noreferrer" class="tushare-link">Tushare个人中心</a> 获取）</li>
                      <li>保存配置</li>
                      <li>如果积分不足2000，系统会自动使用 AKShare 或 Baostock 等免费数据源（仅用于体验，不建议正式使用）</li>
                    </ol>
                  </div>
                </li>
                <li>保存配置后，可以点击"测试"按钮验证连接是否正常</li>
              </ul>
              <el-button type="primary" @click="goToSettings">
                <el-icon><Setting /></el-icon>
                前往设置页面
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤4：同步数据 -->
        <el-step title="同步股票数据" description="同步基础股票数据到系统">
          <template #description>
            <div class="step-content">
              <p>完成数据同步，获取最新的股票基础信息：</p>
              <ul class="step-list">
                <li>
                  <strong>重要说明：</strong>目前数据同步功能<strong style="color: var(--el-color-warning);">仅支持A股市场</strong>，港股和美股数据暂不支持同步。
                </li>
                <li>
                  <strong>多数据源同步步骤：</strong>
                  <ol style="margin-top: 8px; padding-left: 24px;">
                    <li>进入"设置" → "多数据源同步"功能</li>
                    <li><strong>第一步：</strong>同步基础数据（股票列表、基本信息等）</li>
                    <li><strong>第二步：</strong>同步历史数据（K线数据、历史行情等）</li>
                    <li><strong>第三步：</strong>同步财务数据（财报数据、财务指标等）</li>
                    <li>等待所有同步任务完成（可能需要较长时间）</li>
                  </ol>
                </li>
                <li>
                  <strong style="color: var(--el-color-danger);">⚠️ 重要提示：</strong>
                  如果数据同步未完成，进行股票分析时可能<strong>拿不到完整数据</strong>，导致分析结果<strong>不准确</strong>。
                  建议等待数据同步完成后再进行分析。
                </li>
              </ul>
              <el-button type="primary" @click="goToSync">
                <el-icon><Refresh /></el-icon>
                前往数据同步
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤5：搜索股票 -->
        <el-step title="搜索并添加自选股" description="搜索感兴趣的股票并添加到自选列表">
          <template #description>
            <div class="step-content">
              <p>开始使用股票筛选功能：</p>
              <ul class="step-list">
                <li>在"股票筛选"页面搜索股票代码或名称</li>
                <li>查看股票详情信息</li>
                <li>将感兴趣的股票添加到"股票关注列表"</li>
                <li>
                  <strong style="color: var(--el-color-warning);">💡 提示：</strong>
                  如果使用 AKShare（AK）数据源，由于数据同步的限制，<strong>无法使用分类筛选功能</strong>。
                  建议使用 Tushare 数据源以获得完整的筛选功能。
                </li>
              </ul>
              <el-button type="primary" @click="goToScreening">
                <el-icon><Search /></el-icon>
                前往股票筛选
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤6：完成第一次分析 -->
        <el-step title="完成第一次分析" description="对自选股进行AI分析">
          <template #description>
            <div class="step-content">
              <p>开始您的第一次AI股票分析：</p>
              <ul class="step-list">
                <li>
                  <strong>填写股票代码：</strong>
                  在"单股分析"页面输入股票代码（如：000001、600000等）
                </li>
                <li>
                  <strong>检测数据是否完整：</strong>
                  系统会自动检测该股票的基础数据、历史数据、财务数据是否完整
                </li>
                <li>
                  <strong>选择分析深度和分析师：</strong>
                  <ol style="margin-top: 8px; padding-left: 24px;">
                    <li>选择分析深度等级（1-5级，从快速到全面）</li>
                    <li>选择分析师团队（可选择多个分析师，如市场分析师、基本面分析师等）</li>
                  </ol>
                </li>
                <li>
                  <strong>开始分析：</strong>
                  点击"开始分析"按钮，系统将启动多智能体协作分析流程
                </li>
                <li>
                  <strong>等待并查看结果：</strong>
                  等待几分钟（通常5-8分钟），分析完成后查看详细的分析报告和操作建议
                </li>
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
  HomeFilled,
  Link
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
      .el-step {
        margin-bottom: 40px;
        padding-bottom: 0;
        
        &:last-child {
          margin-bottom: 0;
        }
      }

      .el-step__head {
        margin-right: 24px !important;
        flex-shrink: 0;
        min-width: 40px;
        
        .el-step__icon {
          width: 40px;
          height: 40px;
          font-size: 20px;
          margin-right: 0 !important;
        }
      }

      .el-step__main {
        padding-top: 8px !important;
        flex: 1;
        min-width: 0;
      }

      .el-step__title {
        font-size: 18px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        margin-bottom: 20px !important;
        margin-top: 0 !important;
        margin-left: 0 !important;
        line-height: 1.6;
        padding-left: 0 !important;
        padding-top: 0 !important;
      }

      .el-step__description {
        margin-top: 0 !important;
        padding-left: 0 !important;
        padding-top: 0 !important;
      }
    }

    .step-content {
      padding: 24px;
      margin-top: 12px !important;
      background: var(--el-bg-color-page);
      border-radius: 8px;
      border-left: 4px solid var(--el-color-primary);

      p {
        margin: 0 0 16px 0;
        color: var(--el-text-color-regular);
        font-size: 15px;
        line-height: 1.8;

        &.step-tip {
          background: var(--el-color-info-light-9);
          border-left: 3px solid var(--el-color-info);
          padding: 12px 16px;
          border-radius: 4px;
          margin-top: 16px;
          color: var(--el-text-color-primary);
          font-size: 14px;
        }
      }

      .step-list {
        margin: 0 0 20px 0;
        padding-left: 24px;
        color: var(--el-text-color-regular);

        li {
          margin-bottom: 16px;
          line-height: 1.8;

          strong {
            color: var(--el-text-color-primary);
            font-weight: 600;
          }

          ol {
            margin-top: 8px;
            margin-bottom: 0;
            padding-left: 24px;
            color: var(--el-text-color-regular);

            li {
              margin-bottom: 6px;
              line-height: 1.6;
              font-size: 14px;

              &:last-child {
                margin-bottom: 0;
              }
            }
          }

          .tushare-link {
            color: var(--el-color-primary);
            text-decoration: none;
            font-weight: 500;

            &:hover {
              text-decoration: underline;
            }
          }

          .register-link-wrapper {
            margin-top: 8px;
            margin-left: 0;
            margin-bottom: 4px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
          }

          .register-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-weight: 500;
            font-size: 14px;
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
