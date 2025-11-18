<template>
  <div class="about">
    <!-- Hero Section -->
    <div class="hero-section">
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="hero-title">
            TradingAgents-CN
            <span class="version-badge">v1.0.0-preview</span>
          </h1>
          <p class="hero-subtitle">
            现代化的多智能体股票分析学习平台
          </p>
          <p class="hero-description">
            基于先进的AI技术，为投资者提供专业、准确、及时的股票分析服务。
            采用多智能体协作模式，从不同角度对股票进行全方位分析，助您做出更明智的投资决策。
          </p>
          <div class="hero-acknowledgment">
            <el-icon><Star /></el-icon>
            <span>基于 <a href="https://github.com/TauricResearch/TradingAgents" target="_blank" rel="noopener noreferrer">TradingAgents</a> 项目开发，感谢原项目的贡献</span>
          </div>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="goToAnalysis">
              <el-icon><TrendCharts /></el-icon>
              开始分析
            </el-button>
            <el-button size="large" @click="viewDocumentation">
              <el-icon><Document /></el-icon>
              查看文档
            </el-button>
          </div>
        </div>
        <div class="hero-visual">
          <div class="hero-card">
            <div class="hero-stats">
              <div class="stat-item">
                <div class="stat-number">12</div>
                <div class="stat-label">智能体</div>
              </div>
              <div class="stat-item">
                <div class="stat-number">12+</div>
                <div class="stat-label">数据源</div>
              </div>
              <div class="stat-item">
                <div class="stat-number">24/7</div>
                <div class="stat-label">实时监控</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 核心功能 -->
    <div class="features-section">
      <div class="section-header">
        <h2 class="section-title">核心功能</h2>
        <p class="section-subtitle">强大的AI驱动分析能力，全方位投资决策支持</p>
      </div>

      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon primary">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <h3>多智能体分析</h3>
          </div>
          <p>基本面、技术面、新闻分析、社媒分析等12个智能体协作，提供全方位的股票分析视角</p>
          <div class="feature-tags">
            <el-tag size="small">基本面分析</el-tag>
            <el-tag size="small">技术分析</el-tag>
            <el-tag size="small">新闻分析</el-tag>
            <el-tag size="small">社媒分析</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon success">
              <el-icon><Search /></el-icon>
            </div>
            <h3>智能股票筛选</h3>
          </div>
          <p>多维度筛选条件，智能算法推荐，快速发现具有投资价值的优质股票</p>
          <div class="feature-tags">
            <el-tag size="small" type="success">多维筛选</el-tag>
            <el-tag size="small" type="success">智能推荐</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon warning">
              <el-icon><Files /></el-icon>
            </div>
            <h3>批量分析处理</h3>
          </div>
          <p>支持批量股票分析，并行处理提高效率，适合大规模投资组合分析</p>
          <div class="feature-tags">
            <el-tag size="small" type="warning">批量处理</el-tag>
            <el-tag size="small" type="warning">并行计算</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon info">
              <el-icon><Document /></el-icon>
            </div>
            <h3>专业分析报告</h3>
          </div>
          <p>生成详细的分析报告，支持PDF、Excel等多种格式导出，便于分享和存档</p>
          <div class="feature-tags">
            <el-tag size="small" type="info">PDF导出</el-tag>
            <el-tag size="small" type="info">Excel报表</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon danger">
              <el-icon><Monitor /></el-icon>
            </div>
            <h3>实时监控</h3>
          </div>
          <p>实时监控分析进度和系统状态，提供详细的任务执行日志和性能指标</p>
          <div class="feature-tags">
            <el-tag size="small" type="danger">实时监控</el-tag>
            <el-tag size="small" type="danger">性能分析</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon primary">
              <el-icon><Setting /></el-icon>
            </div>
            <h3>个性化配置</h3>
          </div>
          <p>灵活的参数配置和个人偏好设置，支持自定义分析策略和风险偏好</p>
          <div class="feature-tags">
            <el-tag size="small">自定义策略</el-tag>
            <el-tag size="small">风险配置</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 技术架构 -->
    <div class="tech-section">
      <div class="section-header">
        <h2 class="section-title">技术架构</h2>
        <p class="section-subtitle">现代化的技术栈，确保系统的稳定性和可扩展性</p>
      </div>

      <div class="tech-stack">
        <div class="tech-category">
          <div class="tech-header">
            <div class="tech-icon frontend">
              <el-icon><Monitor /></el-icon>
            </div>
            <h3>前端技术</h3>
          </div>
          <div class="tech-list">
            <div class="tech-item">
              <span class="tech-name">Vue 3</span>
              <span class="tech-desc">现代化前端框架</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">TypeScript</span>
              <span class="tech-desc">类型安全开发</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">Element Plus</span>
              <span class="tech-desc">企业级UI组件库</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">Pinia</span>
              <span class="tech-desc">状态管理</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">Vite</span>
              <span class="tech-desc">快速构建工具</span>
            </div>
          </div>
        </div>

        <div class="tech-category">
          <div class="tech-header">
            <div class="tech-icon backend">
              <el-icon><Monitor /></el-icon>
            </div>
            <h3>后端技术</h3>
          </div>
          <div class="tech-list">
            <div class="tech-item">
              <span class="tech-name">FastAPI</span>
              <span class="tech-desc">高性能API框架</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">Python 3.10+</span>
              <span class="tech-desc">现代Python开发</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">Redis</span>
              <span class="tech-desc">高性能缓存和队列</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">MongoDB</span>
              <span class="tech-desc">文档数据库</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">异步处理</span>
              <span class="tech-desc">高并发任务处理</span>
            </div>
          </div>
        </div>

        <div class="tech-category">
          <div class="tech-header">
            <div class="tech-icon ai">
              <el-icon><Cpu /></el-icon>
            </div>
            <h3>AI技术</h3>
          </div>
          <div class="tech-list">
            <div class="tech-item">
              <span class="tech-name">多智能体系统</span>
              <span class="tech-desc">协作式AI分析</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">大语言模型</span>
              <span class="tech-desc">GPT/Claude/Qwen等</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">机器学习</span>
              <span class="tech-desc">智能预测算法</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">数据挖掘</span>
              <span class="tech-desc">深度数据分析</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 项目来源 -->
    <div class="origin-section">
      <div class="section-header">
        <h2 class="section-title">项目来源</h2>
        <p class="section-subtitle">致敬开源，感谢原项目的贡献</p>
      </div>

      <div class="origin-content">
        <div class="origin-card">
          <div class="origin-header">
            <div class="origin-icon">
              <el-icon><Link /></el-icon>
            </div>
            <div class="origin-info">
              <h3>TradingAgents</h3>
              <a href="https://github.com/TauricResearch/TradingAgents"
                 target="_blank"
                 rel="noopener noreferrer"
                 class="origin-link">
                <el-icon><Link /></el-icon>
                github.com/TauricResearch/TradingAgents
              </a>
            </div>
          </div>

          <div class="origin-description">
            <p>
              <strong>TradingAgents-CN</strong> 是基于 <strong>TradingAgents</strong> 项目开发的中文本地化版本。
              原项目由 Tauric Research 团队开发，是一个创新的多智能体股票分析框架。
            </p>
            <p>
              我们在原项目的基础上进行了以下改进和扩展：
            </p>
            <ul class="origin-improvements">
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>完整的中文支持：</strong>针对中国A股市场优化，支持中文数据源和分析</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>现代化Web界面：</strong>基于 Vue 3 + Element Plus 开发的全新前端界面</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>增强的数据源：</strong>集成 Tushare、AKShare 等中国市场数据源</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>多LLM支持：</strong>支持国内外主流大语言模型（OpenAI、Claude、智谱AI、DeepSeek等）</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>批量分析功能：</strong>支持批量股票分析和任务管理</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>用户系统：</strong>完整的用户认证和个性化配置</span>
              </li>
            </ul>
            <p class="origin-thanks">
              <el-icon><Star /></el-icon>
              <strong>特别感谢</strong> Tauric Research 团队的开源贡献，为我们提供了优秀的技术基础和设计理念。
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 版本信息 -->
    <div class="version-section">
      <div class="section-header">
        <h2 class="section-title">版本信息</h2>
      </div>

      <div class="version-info">
        <div class="version-card">
          <div class="version-main">
            <div class="version-number">v1.0.0-preview</div>
            <div class="version-status">预览版</div>
          </div>
          <div class="version-details">
            <div class="version-item">
              <span class="label">发布日期</span>
              <span class="value">2025-10-16</span>
            </div>
            <div class="version-item">
              <span class="label">构建时间</span>
              <span class="value">{{ buildTime }}</span>
            </div>
            <div class="version-item">
              <span class="label">API版本</span>
              <span class="value">v1.0.0-preview</span>
            </div>
          </div>
        </div>

        <div class="framework-info">
          <h4>技术版本</h4>
          <div class="framework-list">
            <div class="framework-item">
              <span class="name">Vue</span>
              <span class="version">3.4.0</span>
            </div>
            <div class="framework-item">
              <span class="name">Element Plus</span>
              <span class="version">2.4.4</span>
            </div>
            <div class="framework-item">
              <span class="name">FastAPI</span>
              <span class="version">0.104.0</span>
            </div>
            <div class="framework-item">
              <span class="name">Python</span>
              <span class="version">3.10+</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 联系我们 -->
    <div class="contact-section">
      <div class="section-header">
        <h2 class="section-title">联系我们</h2>
        <p class="section-subtitle">获取支持、反馈问题或加入社区讨论</p>
      </div>

      <div class="contact-grid">
        <div class="contact-card">
          <div class="contact-icon email">
            <el-icon><Message /></el-icon>
          </div>
          <h4>邮箱联系</h4>
          <p>hsliup@163.com</p>
          <span class="contact-desc">技术支持和商务合作</span>
        </div>

        <div class="contact-card">
          <div class="contact-icon qq">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h4>QQ交流群</h4>
          <p>187537480</p>
          <span class="contact-desc">用户交流和问题讨论</span>
        </div>

        <div class="contact-card">
          <div class="contact-icon wechat">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h4>微信公众号</h4>
          <p>TradingAgents-CN</p>
          <span class="contact-desc">最新动态和使用教程</span>
        </div>

        <div class="contact-card">
          <div class="contact-icon docs">
            <el-icon><Document /></el-icon>
          </div>
          <h4>使用文档</h4>
          <p>
            <a href="https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw"
               target="_blank"
               rel="noopener noreferrer"
               class="doc-link">
              查看详细文档
            </a>
          </p>
          <span class="contact-desc">完整的使用指南和API文档</span>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer-section">
      <div class="footer-content">
        <p>&copy; 2025 TradingAgents-CN. All rights reserved.</p>
        <p>许可证说明：开源组件遵循 Apache 2.0；前端与后端采用专有许可证（个人学习/研究免费，商业使用需授权）。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  TrendCharts,
  Search,
  Files,
  Document,
  Monitor,
  Setting,
  Message,
  ChatDotRound,
  Cpu,
  Star,
  Link,
  CircleCheck
} from '@element-plus/icons-vue'

const router = useRouter()
const buildTime = ref(new Date().toLocaleString('zh-CN'))

const goToAnalysis = () => {
  router.push('/analysis/single')
}

const viewDocumentation = () => {
  window.open('https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw', '_blank')
}
</script>

<style lang="scss" scoped>
.about {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;

  // Hero Section
  .hero-section {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 60px 40px;
    margin-bottom: 48px;
    color: white;
    position: relative;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
      pointer-events: none;
    }

    .hero-content {
      display: flex;
      align-items: center;
      gap: 60px;
      position: relative;
      z-index: 1;
    }

    .hero-text {
      flex: 1;

      .hero-title {
        font-size: 48px;
        font-weight: 700;
        margin: 0 0 16px 0;
        line-height: 1.2;

        .version-badge {
          display: inline-block;
          background: rgba(255, 255, 255, 0.2);
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 14px;
          font-weight: 500;
          margin-left: 16px;
          backdrop-filter: blur(10px);
        }
      }

      .hero-subtitle {
        font-size: 24px;
        font-weight: 500;
        margin: 0 0 16px 0;
        opacity: 0.9;
      }

      .hero-description {
        font-size: 16px;
        line-height: 1.6;
        margin: 0 0 20px 0;
        opacity: 0.8;
        max-width: 600px;
      }

      .hero-acknowledgment {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        opacity: 0.9;
        margin-bottom: 32px;
        padding: 12px 16px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        max-width: 600px;

        .el-icon {
          font-size: 16px;
          color: #ffd700;
        }

        a {
          color: white;
          text-decoration: none;
          font-weight: 500;
          border-bottom: 1px solid rgba(255, 255, 255, 0.3);
          transition: all 0.3s ease;

          &:hover {
            border-bottom-color: white;
          }
        }
      }

      .hero-actions {
        display: flex;
        gap: 16px;

        .el-button {
          padding: 12px 24px;
          font-size: 16px;
          border-radius: 8px;

          &.el-button--primary {
            background: white;
            color: #667eea;
            border: none;

            &:hover {
              background: rgba(255, 255, 255, 0.9);
              transform: translateY(-2px);
            }
          }

          &:not(.el-button--primary) {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(10px);

            &:hover {
              background: rgba(255, 255, 255, 0.2);
              transform: translateY(-2px);
            }
          }
        }
      }
    }

    .hero-visual {
      .hero-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 32px;
        border: 1px solid rgba(255, 255, 255, 0.2);

        .hero-stats {
          display: flex;
          gap: 24px;

          .stat-item {
            text-align: center;

            .stat-number {
              font-size: 32px;
              font-weight: 700;
              margin-bottom: 8px;
            }

            .stat-label {
              font-size: 14px;
              opacity: 0.8;
            }
          }
        }
      }
    }
  }

  // Section Headers
  .section-header {
    text-align: center;
    margin-bottom: 48px;

    .section-title {
      font-size: 36px;
      font-weight: 700;
      color: var(--el-text-color-primary);
      margin: 0 0 16px 0;
    }

    .section-subtitle {
      font-size: 18px;
      color: var(--el-text-color-regular);
      margin: 0;
      max-width: 600px;
      margin-left: auto;
      margin-right: auto;
    }
  }

  // Features Section
  .features-section {
    margin-bottom: 80px;

    .features-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
      gap: 24px;

      .feature-card {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;

        &::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 4px;
          background: linear-gradient(90deg, var(--el-color-primary), var(--el-color-success));
        }

        &:hover {
          transform: translateY(-8px);
          box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        }

        .feature-header {
          display: flex;
          align-items: center;
          gap: 16px;
          margin-bottom: 16px;

          .feature-icon {
            width: 56px;
            height: 56px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;

            &.primary {
              background: linear-gradient(135deg, var(--el-color-primary), #667eea);
            }

            &.success {
              background: linear-gradient(135deg, var(--el-color-success), #52c41a);
            }

            &.warning {
              background: linear-gradient(135deg, var(--el-color-warning), #faad14);
            }

            &.info {
              background: linear-gradient(135deg, var(--el-color-info), #1890ff);
            }

            &.danger {
              background: linear-gradient(135deg, var(--el-color-danger), #ff4d4f);
            }
          }

          h3 {
            margin: 0;
            font-size: 20px;
            font-weight: 600;
            color: #1a202c;
          }
        }

        p {
          color: var(--el-text-color-regular);
          line-height: 1.6;
          margin: 0 0 20px 0;
        }

        .feature-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;

          .el-tag {
            border-radius: 12px;
            border: none;
            font-size: 12px;
          }
        }
      }
    }
  }

  // Origin Section
  .origin-section {
    margin-bottom: 80px;

    .origin-content {
      max-width: 900px;
      margin: 0 auto;

      .origin-card {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 40px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);
        position: relative;
        overflow: hidden;

        &::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 4px;
          background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .origin-header {
          display: flex;
          align-items: center;
          gap: 20px;
          margin-bottom: 32px;
          padding-bottom: 24px;
          border-bottom: 2px solid var(--el-border-color-lighter);

          .origin-icon {
            width: 64px;
            height: 64px;
            border-radius: 16px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
            flex-shrink: 0;
          }

          .origin-info {
            flex: 1;

            h3 {
              margin: 0 0 8px 0;
              font-size: 24px;
              font-weight: 700;
              color: var(--el-text-color-primary);
            }

            .origin-link {
              display: inline-flex;
              align-items: center;
              gap: 6px;
              color: var(--el-color-primary);
              text-decoration: none;
              font-size: 14px;
              font-weight: 500;
              transition: all 0.3s ease;

              .el-icon {
                font-size: 14px;
              }

              &:hover {
                color: #667eea;
                text-decoration: underline;
              }
            }
          }
        }

        .origin-description {
          p {
            color: var(--el-text-color-regular);
            line-height: 1.8;
            margin: 0 0 20px 0;
            font-size: 15px;

            strong {
              color: var(--el-text-color-primary);
              font-weight: 600;
            }
          }

          .origin-improvements {
            list-style: none;
            padding: 0;
            margin: 24px 0;

            li {
              display: flex;
              align-items: flex-start;
              gap: 12px;
              padding: 12px 0;
              color: var(--el-text-color-regular);
              line-height: 1.6;
              font-size: 15px;

              .check-icon {
                color: var(--el-color-success);
                font-size: 18px;
                margin-top: 2px;
                flex-shrink: 0;
              }

              strong {
                color: var(--el-text-color-primary);
                font-weight: 600;
              }
            }
          }

          .origin-thanks {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 32px;
            padding: 20px;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
            border-radius: 12px;
            border-left: 4px solid #667eea;
            font-size: 15px;
            color: var(--el-text-color-regular);

            .el-icon {
              color: #ffd700;
              font-size: 20px;
              flex-shrink: 0;
            }

            strong {
              color: var(--el-text-color-primary);
              font-weight: 600;
            }
          }
        }
      }
    }
  }

  // Tech Section
  .tech-section {
    margin-bottom: 80px;

    .tech-stack {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 32px;

      .tech-category {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }

        .tech-header {
          display: flex;
          align-items: center;
          gap: 16px;
          margin-bottom: 24px;

          .tech-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: white;

            &.frontend {
              background: linear-gradient(135deg, #42b883, #35495e);
            }

            &.backend {
              background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            }

            &.ai {
              background: linear-gradient(135deg, #a55eea, #26de81);
            }
          }

          h3 {
            margin: 0;
            font-size: 20px;
            font-weight: 600;
            color: #1a202c;
          }
        }

        .tech-list {
          .tech-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--el-border-color-extra-light);

            &:last-child {
              border-bottom: none;
            }

            .tech-name {
              font-weight: 500;
              color: #1a202c;
            }

            .tech-desc {
              font-size: 14px;
              color: var(--el-text-color-regular);
            }
          }
        }
      }
    }
  }

  // Version Section
  .version-section {
    margin-bottom: 80px;

    .version-info {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 32px;

      .version-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 32px;
        color: white;
        position: relative;
        overflow: hidden;

        &::before {
          content: '';
          position: absolute;
          top: -50%;
          right: -50%;
          width: 100%;
          height: 100%;
          background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
          pointer-events: none;
        }

        .version-main {
          text-align: center;
          margin-bottom: 24px;
          position: relative;
          z-index: 1;

          .version-number {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 8px;
          }

          .version-status {
            background: rgba(255, 255, 255, 0.2);
            padding: 4px 16px;
            border-radius: 20px;
            font-size: 14px;
            display: inline-block;
            backdrop-filter: blur(10px);
          }
        }

        .version-details {
          position: relative;
          z-index: 1;

          .version-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);

            &:last-child {
              border-bottom: none;
            }

            .label {
              opacity: 0.8;
            }

            .value {
              font-weight: 500;
            }
          }
        }
      }

      .framework-info {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);

        h4 {
          margin: 0 0 24px 0;
          font-size: 20px;
          font-weight: 600;
          color: #1a202c;
        }

        .framework-list {
          .framework-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--el-border-color-extra-light);

            &:last-child {
              border-bottom: none;
            }

            .name {
              font-weight: 500;
              color: #1a202c;
            }

            .version {
              background: var(--el-color-primary-light-9);
              color: var(--el-color-primary);
              padding: 4px 12px;
              border-radius: 12px;
              font-size: 12px;
              font-weight: 500;
            }
          }
        }
      }
    }
  }
  // Contact Section
  .contact-section {
    margin-bottom: 80px;

    .contact-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;

      .contact-card {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);
        transition: all 0.3s ease;

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }

        .contact-icon {
          width: 64px;
          height: 64px;
          border-radius: 16px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 20px;
          font-size: 24px;
          color: white;

          &.email {
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
          }

          &.qq {
            background: linear-gradient(135deg, #12c2e9, #c471ed);
          }

          &.wechat {
            background: linear-gradient(135deg, #07c160, #00d4aa);
          }

          &.docs {
            background: linear-gradient(135deg, #667eea, #764ba2);
          }
        }

        h4 {
          margin: 0 0 12px 0;
          font-size: 18px;
          font-weight: 600;
          color: #1a202c;
        }

        p {
          margin: 0 0 8px 0;
          font-size: 16px;
          font-weight: 500;
          color: #1a202c;

          .doc-link {
            color: var(--el-color-primary);
            text-decoration: none;
            font-weight: 500;

            &:hover {
              text-decoration: underline;
            }
          }
        }

        .contact-desc {
          font-size: 14px;
          color: var(--el-text-color-regular);
        }
      }
    }
  }

  // Footer Section
  .footer-section {
    text-align: center;
    padding: 40px 0;
    border-top: 1px solid var(--el-border-color-extra-light);
    color: var(--el-text-color-regular);

    .footer-content {
      p {
        margin: 8px 0;
        font-size: 14px;
      }
    }
  }
}

// 响应式设计
@media (max-width: 1024px) {
  .about {
    .version-section .version-info {
      grid-template-columns: 1fr;
    }
  }
}

@media (max-width: 768px) {
  .about {
    padding: 0 16px;

    .hero-section {
      padding: 40px 24px;

      .hero-content {
        flex-direction: column;
        gap: 32px;
        text-align: center;
      }

      .hero-text {
        .hero-title {
          font-size: 36px;

          .version-badge {
            display: block;
            margin: 16px auto 0;
            width: fit-content;
          }
        }

        .hero-subtitle {
          font-size: 20px;
        }

        .hero-actions {
          justify-content: center;
          flex-wrap: wrap;
        }
      }
    }

    .section-header {
      .section-title {
        font-size: 28px;
      }

      .section-subtitle {
        font-size: 16px;
      }
    }

    .features-section .features-grid {
      grid-template-columns: 1fr;
    }

    .tech-section .tech-stack {
      grid-template-columns: 1fr;
    }

    .contact-section .contact-grid {
      grid-template-columns: 1fr;
    }
  }
}

@media (max-width: 480px) {
  .about {
    .hero-section {
      padding: 32px 20px;

      .hero-text {
        .hero-title {
          font-size: 28px;
        }

        .hero-subtitle {
          font-size: 18px;
        }

        .hero-actions {
          .el-button {
            padding: 10px 20px;
            font-size: 14px;
          }
        }
      }
    }

    .features-section .features-grid .feature-card {
      padding: 24px;
    }

    .tech-section .tech-stack .tech-category {
      padding: 24px;
    }

    .contact-section .contact-grid .contact-card {
      padding: 24px;
    }
  }
}
</style>
