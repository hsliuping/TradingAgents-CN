<template>
  <div class="about">
    <!-- Hero Section -->
    <div class="hero-section">
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="hero-title">
            TradingAgents-CN
            <span class="version-badge">v2.0</span>
          </h1>
          <p class="hero-subtitle">
            AI辅助股票分析技术学习平台
          </p>
          <p class="hero-description">
            专注于AI辅助分析技术的学习与验证平台。通过优化的工作流引擎和全流程分析辅助，
            帮助您系统学习股票分析方法，提升分析能力。所有分析结论用于学习和验证AI股票分析技术，
            不作为真实炒股操盘指导。
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

    <!-- 学习平台定位说明 -->
    <div class="learning-platform-section">
      <div class="platform-card">
        <div class="platform-header">
          <div class="platform-icon">
            <el-icon><Document /></el-icon>
          </div>
          <div class="platform-content">
            <h3>AI辅助分析技术学习平台</h3>
            <p>
              TradingAgents-CN 是一个专注于<strong>AI辅助股票分析技术学习与验证</strong>的平台。
              我们致力于帮助用户通过实践学习专业的股票分析方法，理解AI如何辅助分析决策，
              提升股票分析的学习能力和思维水平。
            </p>
            <div class="platform-features">
              <div class="platform-feature-item">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>所有分析结论用于学习和验证AI股票分析技术</span>
              </div>
              <div class="platform-feature-item">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>不作为真实炒股操盘指导</span>
              </div>
              <div class="platform-feature-item">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>通过实践学习专业的分析方法论</span>
              </div>
              <div class="platform-feature-item">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>理解AI辅助分析的原理和过程</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 学习中心 -->
    <div class="learning-center-section">
      <div class="section-header">
        <h2 class="section-title">学习中心</h2>
        <p class="section-subtitle">系统化的学习课程，从入门到提高，助您掌握AI辅助股票分析技术</p>
      </div>

      <div class="learning-courses">
        <div class="course-card featured">
          <div class="course-badge">重点推荐</div>
          <div class="course-header">
            <div class="course-icon">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="course-info">
              <h3>全流程AI辅助学习课程</h3>
              <div class="course-meta">
                <el-tag type="primary" size="small">24学时</el-tag>
                <el-tag type="success" size="small">系统化</el-tag>
                <el-tag type="warning" size="small">实战导向</el-tag>
              </div>
            </div>
          </div>
          <div class="course-content">
            <p class="course-description">
              本课程是学习中心的<strong>核心课程</strong>，通过24学时的系统化学习，
              帮助您全面掌握AI辅助股票分析的全流程方法，最终形成全流程使用AI辅助的
              <strong>计划→执行→复盘→提升</strong>的炒股方法提升思路。
            </p>
            <div class="course-features">
              <div class="course-feature">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>从基础概念到高级应用，循序渐进</span>
              </div>
              <div class="course-feature">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>全流程模拟演练，理论与实践结合</span>
              </div>
              <div class="course-feature">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>AI辅助分析工具的实际应用</span>
              </div>
              <div class="course-feature">
                <el-icon class="feature-icon"><CircleCheck /></el-icon>
                <span>形成计划→执行→复盘→提升的循环提升方法</span>
              </div>
            </div>
            <div class="course-outcomes">
              <h4>学习成果</h4>
              <ul>
                <li>掌握AI辅助股票分析的核心方法论</li>
                <li>熟练使用平台的分析工具和功能</li>
                <li>理解工作流引擎和配置化架构的应用</li>
                <li>能够形成全流程使用AI辅助的分析方法，建立持续提升的学习循环</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="course-grid">
          <div class="course-card">
            <div class="course-header">
              <div class="course-icon beginner">
                <el-icon><Document /></el-icon>
              </div>
              <div class="course-info">
                <h3>入门课程</h3>
                <p class="course-level">适合零基础学员</p>
              </div>
            </div>
            <div class="course-content">
              <p>从股票分析基础概念开始，了解AI辅助分析的基本原理，学习平台的基本使用方法。</p>
              <div class="course-topics">
                <span class="topic-tag">基础概念</span>
                <span class="topic-tag">平台入门</span>
                <span class="topic-tag">工具使用</span>
              </div>
            </div>
          </div>

          <div class="course-card">
            <div class="course-header">
              <div class="course-icon intermediate">
                <el-icon><Search /></el-icon>
              </div>
              <div class="course-info">
                <h3>提高课程</h3>
                <p class="course-level">适合有一定基础的学员</p>
              </div>
            </div>
            <div class="course-content">
              <p>深入学习高级分析技巧，掌握多维度分析方法，提升分析能力和决策水平。</p>
              <div class="course-topics">
                <span class="topic-tag">高级技巧</span>
                <span class="topic-tag">多维分析</span>
                <span class="topic-tag">策略优化</span>
              </div>
            </div>
          </div>

          <div class="course-card">
            <div class="course-header">
              <div class="course-icon advanced">
                <el-icon><Setting /></el-icon>
              </div>
              <div class="course-info">
                <h3>全流程方法构建</h3>
                <p class="course-level">高级实战课程</p>
              </div>
            </div>
            <div class="course-content">
              <p>学习如何构建全流程使用AI辅助的分析方法，整合计划、执行、复盘、提升四个环节，形成持续改进的学习循环。</p>
              <div class="course-topics">
                <span class="topic-tag">计划制定</span>
                <span class="topic-tag">执行复盘</span>
                <span class="topic-tag">持续提升</span>
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
        <p class="section-subtitle">优化分析引擎，全流程分析辅助，提升股票分析学习能力</p>
      </div>

      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon primary">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <h3>优化分析引擎</h3>
          </div>
          <p>v2.0 全新工作流引擎，支持可视化流程定义，配置化架构让分析流程更灵活、更强大。多智能体协作，从基本面、技术面、新闻、社媒等多维度提供全方位分析视角</p>
          <div class="feature-tags">
            <el-tag size="small">工作流引擎</el-tag>
            <el-tag size="small">可视化配置</el-tag>
            <el-tag size="small">多智能体</el-tag>
            <el-tag size="small">配置化架构</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon success">
              <el-icon><Search /></el-icon>
            </div>
            <h3>全流程分析辅助</h3>
          </div>
          <p>从数据收集、指标计算、智能体分析到报告生成的完整流程辅助。支持单股分析、批量分析、持仓分析、交易复盘等多种分析场景，帮助您系统学习完整的分析流程</p>
          <div class="feature-tags">
            <el-tag size="small" type="success">全流程辅助</el-tag>
            <el-tag size="small" type="success">多场景分析</el-tag>
            <el-tag size="small" type="success">流程学习</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon warning">
              <el-icon><Files /></el-icon>
            </div>
            <h3>提升学习能力</h3>
          </div>
          <p>通过AI辅助分析，学习专业的股票分析方法论。查看详细的分析过程、推理逻辑和决策依据，理解不同分析维度的作用，逐步提升您的股票分析技能</p>
          <div class="feature-tags">
            <el-tag size="small" type="warning">方法论学习</el-tag>
            <el-tag size="small" type="warning">过程透明</el-tag>
            <el-tag size="small" type="warning">技能提升</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon info">
              <el-icon><Document /></el-icon>
            </div>
            <h3>学习平台定位</h3>
          </div>
          <p>专注于AI辅助分析技术的学习与验证。所有分析结论用于学习和验证AI股票分析技术，不作为真实炒股操盘指导。通过实践学习，理解AI如何辅助分析，提升分析思维</p>
          <div class="feature-tags">
            <el-tag size="small" type="info">学习平台</el-tag>
            <el-tag size="small" type="info">技术验证</el-tag>
            <el-tag size="small" type="info">思维提升</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon danger">
              <el-icon><Monitor /></el-icon>
            </div>
            <h3>批量分析处理</h3>
          </div>
          <p>支持批量股票分析，并行处理提高效率。适合学习不同股票的分析方法对比，理解市场差异和个股特性</p>
          <div class="feature-tags">
            <el-tag size="small" type="danger">批量处理</el-tag>
            <el-tag size="small" type="danger">并行计算</el-tag>
            <el-tag size="small" type="danger">对比学习</el-tag>
          </div>
        </div>

        <div class="feature-card">
          <div class="feature-header">
            <div class="feature-icon primary">
              <el-icon><Setting /></el-icon>
            </div>
            <h3>配置化架构</h3>
          </div>
          <p>v2.0 全新配置化架构，工作流、智能体、工具、提示词均可动态配置。支持可视化工作流编辑器，无需修改代码即可调整分析流程，灵活适应不同学习需求</p>
          <div class="feature-tags">
            <el-tag size="small">动态配置</el-tag>
            <el-tag size="small">可视化编辑</el-tag>
            <el-tag size="small">灵活调整</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 技术架构 -->
    <div class="tech-section">
      <div class="section-header">
        <h2 class="section-title">技术架构</h2>
        <p class="section-subtitle">v2.0 全新架构，配置化设计，为学习平台提供强大支撑</p>
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
            <h3>v2.0 核心引擎</h3>
          </div>
          <div class="tech-list">
            <div class="tech-item">
              <span class="tech-name">工作流引擎</span>
              <span class="tech-desc">可视化流程定义</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">配置化架构</span>
              <span class="tech-desc">动态配置管理</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">多智能体系统</span>
              <span class="tech-desc">协作式AI分析</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">统一LLM客户端</span>
              <span class="tech-desc">多模型支持</span>
            </div>
            <div class="tech-item">
              <span class="tech-name">全流程辅助</span>
              <span class="tech-desc">端到端分析支持</span>
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
                <span><strong>v2.0 工作流引擎：</strong>全新配置化架构，支持可视化流程定义，灵活调整分析流程</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>全流程分析辅助：</strong>从数据收集到报告生成的完整流程支持，帮助系统学习分析方法</span>
              </li>
              <li>
                <el-icon class="check-icon"><CircleCheck /></el-icon>
                <span><strong>学习平台定位：</strong>专注于AI辅助分析技术的学习与验证，提升股票分析学习能力</span>
              </li>
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
                <span><strong>批量分析功能：</strong>支持批量股票分析和任务管理，适合对比学习</span>
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

      <div class="version-info" v-loading="systemInfoLoading">
        <div class="version-card">
          <div class="version-main">
            <div class="version-number">{{ systemInfo.version || 'v2.0' }}</div>
            <div class="version-status">正式版</div>
          </div>
          <div class="version-details">
            <div class="version-item" v-if="systemInfo.full_version">
              <span class="label">完整版本</span>
              <span class="value">{{ systemInfo.full_version }}</span>
            </div>
            <div class="version-item" v-if="systemInfo.build_date">
              <span class="label">构建时间</span>
              <span class="value">{{ formatBuildDate(systemInfo.build_date) }}</span>
            </div>
            <div class="version-item" v-if="systemInfo.build_type">
              <span class="label">构建类型</span>
              <span class="value">{{ formatBuildType(systemInfo.build_type) }}</span>
            </div>
            <div class="version-item" v-if="systemInfo.git_commit">
              <span class="label">Git提交</span>
              <span class="value code">{{ systemInfo.git_commit }}</span>
            </div>
            <div class="version-item" v-if="!systemInfo.build_date">
              <span class="label">构建时间</span>
              <span class="value">{{ buildTime }}</span>
            </div>
            <div class="version-item">
              <span class="label">API版本</span>
              <span class="value">v2.0</span>
            </div>
          </div>
          <div class="version-actions" v-if="systemInfo.full_version">
            <el-button type="primary" size="small" @click="copyVersionInfo" plain>
              <el-icon><DocumentCopy /></el-icon>
              复制版本信息
            </el-button>
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
          <p>1079484482</p>
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
        <p>&copy; 2025-2026 TradingAgents-CN. All rights reserved.</p>
        <p>许可证说明：tradingagents 目录内的代码采用了部分原 TradingAgents 项目的代码，遵循 Apache 2.0 开源许可证；其他部分因 1.0 版开源后被盗用代码，因此不再开源。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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
  CircleCheck,
  DocumentCopy
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'

const router = useRouter()
const buildTime = ref(new Date().toLocaleString('zh-CN'))
const systemInfoLoading = ref(false)
const systemInfo = ref<{
  version?: string
  full_version?: string
  build_timestamp?: string
  build_date?: string
  build_unix?: number
  git_commit?: string
  build_type?: string
}>({})

// 加载系统信息
const loadSystemInfo = async () => {
  systemInfoLoading.value = true
  try {
    const response = await ApiClient.get('/api/system/info')
    if (response.success && response.data) {
      systemInfo.value = response.data
    }
  } catch (error) {
    console.error('加载系统信息失败:', error)
  } finally {
    systemInfoLoading.value = false
  }
}

// 格式化构建日期
const formatBuildDate = (dateStr: string) => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'Asia/Shanghai'
    })
  } catch {
    return dateStr
  }
}

// 格式化构建类型
const formatBuildType = (type: string) => {
  const typeMap: Record<string, string> = {
    docker: 'Docker镜像',
    installer: 'Windows安装版',
    portable: '便携版'
  }
  return typeMap[type] || type
}

// 复制版本信息
const copyVersionInfo = async () => {
  const info = [
    `版本号: ${systemInfo.value.version || 'v2.0'}`,
    systemInfo.value.full_version ? `完整版本: ${systemInfo.value.full_version}` : '',
    systemInfo.value.build_date ? `构建时间: ${formatBuildDate(systemInfo.value.build_date)}` : '',
    systemInfo.value.build_type ? `构建类型: ${formatBuildType(systemInfo.value.build_type)}` : '',
    systemInfo.value.git_commit ? `Git提交: ${systemInfo.value.git_commit}` : ''
  ].filter(Boolean).join('\n')

  try {
    await navigator.clipboard.writeText(info)
    ElMessage.success('版本信息已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败，请手动复制')
  }
}

const goToAnalysis = () => {
  router.push('/analysis/single')
}

const viewDocumentation = () => {
  window.open('https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw', '_blank')
}

// 页面加载时获取系统信息
onMounted(() => {
  loadSystemInfo()
})
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

  // Learning Platform Section
  .learning-platform-section {
    margin-bottom: 80px;

    .platform-card {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05));
      border-radius: 16px;
      padding: 40px;
      border: 2px solid rgba(102, 126, 234, 0.2);
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

      .platform-header {
        display: flex;
        gap: 24px;
        align-items: flex-start;

        .platform-icon {
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

        .platform-content {
          flex: 1;

          h3 {
            margin: 0 0 16px 0;
            font-size: 24px;
            font-weight: 700;
            color: var(--el-text-color-primary);
          }

          p {
            color: var(--el-text-color-regular);
            line-height: 1.8;
            margin: 0 0 24px 0;
            font-size: 16px;

            strong {
              color: var(--el-color-primary);
              font-weight: 600;
            }
          }

          .platform-features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;

            .platform-feature-item {
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 12px;
              background: var(--el-bg-color);
              border-radius: 8px;
              border: 1px solid var(--el-border-color-lighter);

              .feature-icon {
                color: var(--el-color-success);
                font-size: 18px;
                flex-shrink: 0;
              }

              span {
                color: var(--el-text-color-regular);
                font-size: 14px;
                line-height: 1.5;
              }
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

  // Learning Center Section
  .learning-center-section {
    margin-bottom: 80px;

    .learning-courses {
      .course-card {
        background: var(--el-bg-color);
        border-radius: 16px;
        padding: 32px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid var(--el-border-color-lighter);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;

        &.featured {
          background: linear-gradient(135deg, rgba(102, 126, 234, 0.03), rgba(118, 75, 162, 0.03));
          border: 2px solid rgba(102, 126, 234, 0.3);
          margin-bottom: 32px;

          &::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
          }
        }

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }

        .course-badge {
          position: absolute;
          top: 20px;
          right: 20px;
          background: linear-gradient(135deg, #667eea, #764ba2);
          color: white;
          padding: 6px 16px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }

        .course-header {
          display: flex;
          align-items: flex-start;
          gap: 20px;
          margin-bottom: 24px;

          .course-icon {
            width: 64px;
            height: 64px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
            flex-shrink: 0;
            background: linear-gradient(135deg, #667eea, #764ba2);

            &.beginner {
              background: linear-gradient(135deg, var(--el-color-success), #52c41a);
            }

            &.intermediate {
              background: linear-gradient(135deg, var(--el-color-warning), #faad14);
            }

            &.advanced {
              background: linear-gradient(135deg, var(--el-color-danger), #ff4d4f);
            }
          }

          .course-info {
            flex: 1;

            h3 {
              margin: 0 0 8px 0;
              font-size: 24px;
              font-weight: 700;
              color: var(--el-text-color-primary);
            }

            .course-level {
              margin: 0;
              font-size: 14px;
              color: var(--el-text-color-regular);
            }

            .course-meta {
              display: flex;
              gap: 8px;
              margin-top: 8px;
            }
          }
        }

        .course-content {
          .course-description {
            color: var(--el-text-color-regular);
            line-height: 1.8;
            margin: 0 0 24px 0;
            font-size: 16px;

            strong {
              color: var(--el-color-primary);
              font-weight: 600;
            }
          }

          .course-features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-bottom: 24px;

            .course-feature {
              display: flex;
              align-items: center;
              gap: 12px;
              padding: 12px;
              background: var(--el-bg-color-page);
              border-radius: 8px;
              border: 1px solid var(--el-border-color-lighter);

              .feature-icon {
                color: var(--el-color-success);
                font-size: 18px;
                flex-shrink: 0;
              }

              span {
                color: var(--el-text-color-regular);
                font-size: 14px;
                line-height: 1.5;
              }
            }
          }

          .course-outcomes {
            background: var(--el-bg-color-page);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid var(--el-color-primary);

            h4 {
              margin: 0 0 16px 0;
              font-size: 18px;
              font-weight: 600;
              color: var(--el-text-color-primary);
            }

            ul {
              margin: 0;
              padding-left: 20px;
              list-style: none;

              li {
                position: relative;
                padding-left: 24px;
                margin-bottom: 12px;
                color: var(--el-text-color-regular);
                line-height: 1.6;

                &::before {
                  content: '✓';
                  position: absolute;
                  left: 0;
                  color: var(--el-color-success);
                  font-weight: 600;
                }

                &:last-child {
                  margin-bottom: 0;
                }
              }
            }
          }

          .course-topics {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 16px;

            .topic-tag {
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

      .course-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 24px;
      }
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

              &.code {
                font-family: 'Courier New', monospace;
                font-size: 13px;
                background: rgba(255, 255, 255, 0.1);
                padding: 2px 8px;
                border-radius: 4px;
              }
            }
          }
        }

        .version-actions {
          margin-top: 24px;
          text-align: center;
          position: relative;
          z-index: 1;
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

    .learning-platform-section {
      .platform-card {
        padding: 24px;

        .platform-header {
          flex-direction: column;
          gap: 20px;

          .platform-icon {
            margin: 0 auto;
          }

          .platform-content {
            h3 {
              text-align: center;
              font-size: 20px;
            }

            .platform-features {
              grid-template-columns: 1fr;
            }
          }
        }
      }
    }

    .learning-center-section {
      .learning-courses {
        .course-card {
          padding: 24px;

          &.featured {
            margin-bottom: 24px;

            .course-badge {
              top: 16px;
              right: 16px;
              font-size: 11px;
              padding: 4px 12px;
            }
          }

          .course-header {
            flex-direction: column;
            gap: 16px;
            text-align: center;

            .course-icon {
              margin: 0 auto;
            }

            .course-info {
              h3 {
                font-size: 20px;
              }
            }
          }

          .course-content {
            .course-features {
              grid-template-columns: 1fr;
            }
          }
        }

        .course-grid {
          grid-template-columns: 1fr;
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
