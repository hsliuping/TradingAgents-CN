<template>
  <div class="about">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-inner">
        <div class="hero-main">
          <h1 class="hero-title">
            {{ isJdyun ? 'TradingAgents-CN 京东云合作版' : 'TradingAgents-CN' }}
            <span class="version-badge">{{ versionDisplay }}</span>
          </h1>
          <p class="hero-tagline">AI 辅助股票分析技术学习平台</p>

          <p class="hero-desc" v-if="!isJdyun">
            通过优化的工作流引擎与全流程分析辅助，配合行业研究工作台，
            帮助您系统学习股票分析方法，逐步建立自己的分析体系。
          </p>
          <template v-else>
            <p class="hero-desc">
              配 Key、选模型、搭环境费时费力，研究做到一半还可能被限流中断——
              京东云合作版帮您一键解决：开通即用，Key 和数据源全部预配置；
              内置 429 限流应对，深度分析稳稳跑完全流程。
            </p>
            <p class="hero-desc">
              14 个维度的结构化研究报告 + 乐观/审慎双情景研究员，帮您系统建立自己的分析方法论。
            </p>
          </template>

          <div class="hero-pills">
            <span v-for="pill in heroPills" :key="pill">
              <el-icon><CircleCheck /></el-icon>{{ pill }}
            </span>
          </div>

          <div class="hero-actions">
            <el-button size="large" class="btn-light" @click="goToAnalysis">
              <el-icon><TrendCharts /></el-icon>
              开始分析
            </el-button>
            <el-button size="large" class="btn-ghost" @click="goToLearning">
              <el-icon><Reading /></el-icon>
              查看课程
            </el-button>
          </div>

          <div class="hero-acknowledgment" v-if="!isJdyun">
            <el-icon><Star /></el-icon>
            <span>
              基于
              <a href="https://github.com/TauricResearch/TradingAgents" target="_blank" rel="noopener noreferrer">TradingAgents</a>
              项目开发，感谢原项目的贡献
            </span>
          </div>
        </div>

        <div class="hero-side">
          <div class="ver-preview" v-loading="systemInfoLoading">
            <div class="ver-label">当前版本</div>
            <div class="ver-num">{{ versionDisplay }}</div>
            <div class="ver-status" :class="versionStatusClass">{{ versionStatusText }}</div>
            <div class="ver-meta" v-if="systemInfo.build_type">
              {{ formatBuildType(systemInfo.build_type) }}
            </div>
            <div class="ver-meta" v-if="systemInfo.build_date">
              {{ formatShortDate(systemInfo.build_date) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 版本信息 -->
    <div class="section">
      <div class="section-head">
        <h2>版本信息</h2>
        <p>当前系统的版本号与构建信息，反馈问题时请一并提供</p>
      </div>
      <div class="version-card" v-loading="systemInfoLoading">
        <div class="version-main">
          <div class="version-num">{{ versionDisplay }}</div>
          <span class="status-chip" :class="versionStatusClass">{{ versionStatusText }}</span>
        </div>
        <div class="version-grid">
          <div class="version-item" v-if="systemInfo.full_version">
            <span class="label">完整版本</span>
            <span class="value code">{{ systemInfo.full_version }}</span>
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
            <span class="label">Git 提交</span>
            <span class="value code">{{ systemInfo.git_commit }}</span>
          </div>
          <div class="version-item" v-if="!systemInfo.build_date && !systemInfo.build_type">
            <span class="label">构建信息</span>
            <span class="value muted">开发环境运行</span>
          </div>
        </div>
        <div class="version-actions" v-if="systemInfo.version">
          <el-button size="small" plain @click="copyVersionInfo">
            <el-icon><DocumentCopy /></el-icon>
            复制版本信息
          </el-button>
        </div>
      </div>
    </div>

    <!-- 版本亮点 / 京东云版特色 -->
    <div class="section">
      <div class="section-head" v-if="!isJdyun">
        <h2>版本亮点</h2>
        <p>本版本的核心能力一览</p>
      </div>
      <div class="section-head" v-else>
        <h2>京东云版特色</h2>
        <p>开箱即用、零配置、限速友好、合规研究，专为京东云用户定制</p>
      </div>

      <div class="feature-grid" v-if="!isJdyun">
        <div class="feature-card">
          <div class="feature-icon primary"><el-icon><DataAnalysis /></el-icon></div>
          <h3>行业研究工作台</h3>
          <p>覆盖猪周期、保险、电池、汽车、银行等行业：行业数据跟踪、研究日志与资料库、决策辅助，行业分析不止于个股</p>
          <div class="feature-tags">
            <el-tag size="small">行业数据</el-tag>
            <el-tag size="small">研究日志</el-tag>
            <el-tag size="small">决策辅助</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon success"><el-icon><TrendCharts /></el-icon></div>
          <h3>优化分析引擎</h3>
          <p>多智能体协作，可视化工作流、Agent 工坊、Skill 中心与 MCP 扩展，工作流、智能体、工具、提示词均可动态配置</p>
          <div class="feature-tags">
            <el-tag size="small" type="success">多智能体</el-tag>
            <el-tag size="small" type="success">可视化工作流</el-tag>
            <el-tag size="small" type="success">Agent 工坊</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon warning"><el-icon><Search /></el-icon></div>
          <h3>全流程分析辅助</h3>
          <p>从数据收集、指标计算、智能体分析到报告生成的完整流程支持，单股、批量、持仓、复盘多场景，分析过程透明可追溯</p>
          <div class="feature-tags">
            <el-tag size="small" type="warning">多场景分析</el-tag>
            <el-tag size="small" type="warning">过程透明</el-tag>
            <el-tag size="small" type="warning">结构化报告</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon info"><el-icon><Reading /></el-icon></div>
          <h3>系统化学习课程</h3>
          <p>从入门到实战的课程体系 + AI 助手随行答疑，边学边用，逐步掌握 AI 辅助股票分析方法论</p>
          <div class="feature-tags">
            <el-tag size="small" type="info">课程体系</el-tag>
            <el-tag size="small" type="info">AI 助手</el-tag>
            <el-tag size="small" type="info">随学随用</el-tag>
          </div>
        </div>
      </div>

      <div class="feature-grid" v-else>
        <div class="feature-card">
          <div class="feature-icon primary"><el-icon><Box /></el-icon></div>
          <h3>开箱即用</h3>
          <p>登录就能用，不用装环境、不用配数据库、不用敲一行命令，京东云都帮你搞定了</p>
          <div class="feature-tags">
            <el-tag size="small">免安装</el-tag>
            <el-tag size="small">免部署</el-tag>
            <el-tag size="small">登录即用</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon success"><el-icon><Key /></el-icon></div>
          <h3>零配置</h3>
          <p>不用懂 API 是什么、不用去申请 Key、不用纠结选哪个模型。模型、数据源、向量库全部京东云预配好</p>
          <div class="feature-tags">
            <el-tag size="small" type="success">免Key</el-tag>
            <el-tag size="small" type="success">免选模型</el-tag>
            <el-tag size="small" type="success">零门槛</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon warning"><el-icon><DataAnalysis /></el-icon></div>
          <h3>覆盖全流程</h3>
          <p>想研究一只股票？想知道哪些股票值得看？想知道自己的操作对不对？单股分析、智能筛选、持仓复盘、交易计划，一个系统全搞定</p>
          <div class="feature-tags">
            <el-tag size="small" type="warning">单股研究</el-tag>
            <el-tag size="small" type="warning">智能选股</el-tag>
            <el-tag size="small" type="warning">持仓复盘</el-tag>
          </div>
        </div>
        <div class="feature-card">
          <div class="feature-icon info"><el-icon><ChatDotRound /></el-icon></div>
          <h3>不会用？问 AI 就行</h3>
          <p>右下角的智能助手就是你的随身顾问。"报告怎么导出？""筛选条件怎么设？"——直接问它，比翻文档快多了</p>
          <div class="feature-tags">
            <el-tag size="small" type="info">随时提问</el-tag>
            <el-tag size="small" type="info">看手册</el-tag>
            <el-tag size="small" type="info">配操作</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 技术栈（京东云版隐藏） -->
    <div class="section" v-if="!isJdyun">
      <div class="section-head">
        <h2>技术栈</h2>
        <p>现代化技术架构，为分析平台提供稳定支撑</p>
      </div>
      <div class="tech-card">
        <div class="tech-col">
          <div class="tech-col-head"><el-icon><Monitor /></el-icon>前端</div>
          <div class="tech-row"><span>Vue 3 + TypeScript</span><span>现代化前端框架</span></div>
          <div class="tech-row"><span>Element Plus</span><span>企业级 UI 组件库</span></div>
          <div class="tech-row"><span>Pinia + Vite</span><span>状态管理与构建</span></div>
        </div>
        <div class="tech-col">
          <div class="tech-col-head"><el-icon><Cpu /></el-icon>后端</div>
          <div class="tech-row"><span>FastAPI + Python 3.11</span><span>高性能 API 框架</span></div>
          <div class="tech-row"><span>MongoDB + Redis</span><span>数据存储与缓存</span></div>
          <div class="tech-row"><span>异步任务处理</span><span>高并发分析执行</span></div>
        </div>
        <div class="tech-col">
          <div class="tech-col-head"><el-icon><Setting /></el-icon>核心引擎</div>
          <div class="tech-row"><span>工作流引擎</span><span>可视化流程定义</span></div>
          <div class="tech-row"><span>Agent 工坊 / Skill 中心</span><span>自定义智能体与工具</span></div>
          <div class="tech-row"><span>MCP 服务器</span><span>外部能力扩展</span></div>
        </div>
      </div>
    </div>

    <!-- 开源与许可（京东云版隐藏） -->
    <div class="section" v-if="!isJdyun">
      <div class="section-head">
        <h2>开源与许可</h2>
        <p>致敬开源，感谢原项目的贡献</p>
      </div>
      <div class="origin-card">
        <div class="origin-header">
          <div class="origin-icon"><el-icon><Link /></el-icon></div>
          <div class="origin-info">
            <h3>TradingAgents</h3>
            <a href="https://github.com/TauricResearch/TradingAgents"
               target="_blank" rel="noopener noreferrer" class="origin-link">
              <el-icon><Link /></el-icon>
              github.com/TauricResearch/TradingAgents
            </a>
          </div>
        </div>
        <p class="origin-desc">
          TradingAgents-CN 是基于 Tauric Research 团队的开源项目 TradingAgents 开发的中文本地化版本，
          在原项目基础上进行了以下改进与扩展：
        </p>
        <ul class="origin-list">
          <li><el-icon><CircleCheck /></el-icon><span><strong>行业研究工作台：</strong>行业数据、研究日志与决策辅助，扩展分析视角</span></li>
          <li><el-icon><CircleCheck /></el-icon><span><strong>中文本地化：</strong>针对中国 A 股市场优化，集成 Tushare / AKShare 等中文数据源</span></li>
          <li><el-icon><CircleCheck /></el-icon><span><strong>多模型支持：</strong>支持国内外主流大语言模型，统一配置管理</span></li>
          <li><el-icon><CircleCheck /></el-icon><span><strong>现代化界面：</strong>基于 Vue 3 + Element Plus 的全新前端，支持暗色主题</span></li>
        </ul>
        <div class="license-note">
          <el-icon><Document /></el-icon>
          <span>
            许可说明：<strong>tradingagents</strong> 目录内的代码沿用了原 TradingAgents 项目部分代码，
            遵循 <a href="https://www.apache.org/licenses/LICENSE-2.0" target="_blank" rel="noopener noreferrer">Apache 2.0</a> 开源许可证；
            其余部分暂不开源。
          </span>
        </div>
      </div>
    </div>

    <!-- 赞助商（京东云版隐藏） -->
    <div class="section" v-if="!isJdyun">
      <div class="section-head">
        <h2>赞助商</h2>
        <p>感谢以下企业对本项目的赞助与支持</p>
      </div>
      <div class="sponsor-card">
        <div class="sponsor-header">
          <div class="sponsor-icon"><el-icon><Star /></el-icon></div>
          <div class="sponsor-info">
            <h3>字节火山引擎</h3>
            <p>字节自研豆包模型 + 满血版开源 SOTA 模型，覆盖文本、VLM、图像生成，全模态一站配齐</p>
          </div>
        </div>
        <div class="sponsor-actions">
          <el-button type="primary" size="small" plain @click="goToVolcengine">
            <el-icon><Link /></el-icon>
            注册即领 2500 万 Tokens，立即前往
          </el-button>
        </div>
      </div>
    </div>

    <!-- 联系我们 -->
    <div class="section">
      <div class="section-head" v-if="!isJdyun">
        <h2>联系我们</h2>
        <p>获取支持、反馈问题或加入社区讨论</p>
      </div>
      <div class="section-head" v-else>
        <h2>支持与反馈</h2>
        <p>京东云合作版专属支持渠道</p>
      </div>

      <div class="contact-grid" v-if="!isJdyun">
        <div class="contact-card">
          <div class="contact-icon email"><el-icon><Message /></el-icon></div>
          <h4>邮箱联系</h4>
          <p>hsliup@163.com</p>
          <span>技术支持和商务合作</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon qq"><el-icon><ChatDotRound /></el-icon></div>
          <h4>QQ 交流群</h4>
          <p>1079484482</p>
          <span>用户交流和问题讨论</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon wechat"><el-icon><ChatDotRound /></el-icon></div>
          <h4>微信公众号</h4>
          <p>TradingAgents-CN</p>
          <span>最新动态和使用教程</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon docs"><el-icon><Document /></el-icon></div>
          <h4>使用文档</h4>
          <p>
            <a href="https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw" target="_blank" rel="noopener noreferrer">查看详细文档</a>
          </p>
          <span>完整的使用指南和 API 文档</span>
        </div>
      </div>

      <div class="contact-grid" v-else>
        <div class="contact-card">
          <div class="contact-icon wechat"><el-icon><ChatDotRound /></el-icon></div>
          <h4>京东云技术支持</h4>
          <p>联系您的京东云客户经理</p>
          <span>开通账号、权限、限速等问题</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon docs"><el-icon><Document /></el-icon></div>
          <h4>系统 Bug 反馈</h4>
          <p>
            <a href="https://github.com/hsliuping/TradingAgents-CN-Pro/issues" target="_blank" rel="noopener noreferrer">GitHub Issues</a>
          </p>
          <span>提交系统缺陷与异常问题</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon email"><el-icon><Message /></el-icon></div>
          <h4>功能建议</h4>
          <p>系统内"反馈"按钮</p>
          <span>右上角反馈入口提交建议</span>
        </div>
        <div class="contact-card">
          <div class="contact-icon qq"><el-icon><Reading /></el-icon></div>
          <h4>使用文档</h4>
          <p>京东云版使用手册</p>
          <span>系统内"帮助"按钮查看完整手册</span>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer">
      <p v-if="!isJdyun">&copy; 2025-2026 TradingAgents-CN. All rights reserved.</p>
      <p v-else>&copy; 2025-2026 TradingAgents-CN 京东云合作版. All rights reserved.</p>
      <p v-if="isJdyun">本系统由京东云提供模型服务支持，仅供 A 股研究学习使用，所有输出不构成投资建议。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  TrendCharts,
  Search,
  Document,
  Monitor,
  Setting,
  Message,
  ChatDotRound,
  Cpu,
  Star,
  Link,
  CircleCheck,
  DocumentCopy,
  Box,
  Key,
  DataAnalysis,
  Reading
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'
import { isJdyunMode } from '@/utils/config'

const router = useRouter()
const isJdyun = computed(() => isJdyunMode())
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

// 版本号展示（全部来自后端 /api/system/info，不硬编码）
const versionDisplay = computed(() => systemInfo.value.version || '...')

// 版本状态（根据版本号自动判断）
const versionStatusText = computed(() => {
  const v = (systemInfo.value.version || '') + (systemInfo.value.full_version || '')
  if (v.includes('beta') || v.includes('alpha') || v.includes('rc')) return '测试版'
  if (v.includes('dev')) return '开发版'
  if (!v) return ''
  return '正式版'
})

const versionStatusClass = computed(() => {
  const text = versionStatusText.value
  if (text === '测试版') return 'status-beta'
  if (text === '开发版') return 'status-dev'
  return 'status-stable'
})

// Hero 定位标签
const heroPills = computed(() =>
  isJdyun.value
    ? ['0 配置，开通即用', '429 自动重试', '14 维度研究报告', '仅支持 A 股']
    : ['用于学习 AI 股票分析技术', '不作操盘指导', '实践学习方法论']
)

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

// 格式化构建日期（完整）
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
      timeZone: 'Asia/Shanghai'
    })
  } catch {
    return dateStr
  }
}

// 格式化日期（仅日期，用于 hero 侧卡）
const formatShortDate = (dateStr: string) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return `构建于 ${date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })}`
  } catch {
    return ''
  }
}

// 格式化构建类型
const formatBuildType = (type: string) => {
  const typeMap: Record<string, string> = {
    docker: 'Docker 镜像',
    installer: 'Windows 安装版',
    portable: '便携版'
  }
  return typeMap[type] || type
}

// 复制版本信息
const copyVersionInfo = async () => {
  const info = [
    `版本号: ${systemInfo.value.version || '-'}`,
    systemInfo.value.full_version ? `完整版本: ${systemInfo.value.full_version}` : '',
    systemInfo.value.build_date ? `构建时间: ${formatBuildDate(systemInfo.value.build_date)}` : '',
    systemInfo.value.build_type ? `构建类型: ${formatBuildType(systemInfo.value.build_type)}` : '',
    systemInfo.value.git_commit ? `Git 提交: ${systemInfo.value.git_commit}` : ''
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

const goToLearning = () => {
  router.push('/learning')
}

const goToVolcengine = () => {
  window.open('https://www.volcengine.com/product/ark?utm_campaign=hw&utm_content=TradingAgents-CN&utm_medium=devrel-1&utm_source=OWO&utm_term=TradingAgents-CN', '_blank')
}

onMounted(() => {
  loadSystemInfo()
})
</script>

<style lang="scss" scoped>
.about {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 24px 0;

  // ===== Hero =====
  .hero {
    background: linear-gradient(135deg, #1e5edb 0%, #409eff 60%, #53a8ff 100%);
    border-radius: 16px;
    padding: 44px 48px;
    margin-bottom: 36px;
    color: #fff;
    position: relative;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: -80px;
      right: -60px;
      width: 360px;
      height: 360px;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.14) 0%, transparent 70%);
      pointer-events: none;
    }

    .hero-inner {
      display: flex;
      align-items: center;
      gap: 48px;
      position: relative;
      z-index: 1;
    }

    .hero-main {
      flex: 1;
      min-width: 0;

      .hero-title {
        font-size: 32px;
        font-weight: 700;
        margin: 0 0 10px 0;
        line-height: 1.25;

        .version-badge {
          display: inline-block;
          background: rgba(255, 255, 255, 0.22);
          padding: 3px 12px;
          border-radius: 16px;
          font-size: 14px;
          font-weight: 500;
          margin-left: 12px;
          vertical-align: middle;
          font-family: Consolas, 'SF Mono', 'Courier New', monospace;
        }
      }

      .hero-tagline {
        font-size: 18px;
        font-weight: 600;
        margin: 0 0 12px 0;
        opacity: 0.95;
      }

      .hero-desc {
        font-size: 14.5px;
        line-height: 1.7;
        margin: 0 0 8px 0;
        opacity: 0.88;
        max-width: 640px;
      }

      .hero-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 16px 0 0 0;

        span {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          padding: 5px 12px;
          background: rgba(255, 255, 255, 0.14);
          border-radius: 14px;
          border: 1px solid rgba(255, 255, 255, 0.22);

          .el-icon {
            font-size: 14px;
            color: #6ee7a0;
          }
        }
      }

      .hero-actions {
        display: flex;
        gap: 12px;
        margin-top: 24px;

        .el-button {
          padding: 11px 22px;
          font-size: 15px;
          border-radius: 8px;

          &.btn-light {
            background: #fff;
            color: #1e5edb;
            border: none;

            &:hover {
              background: rgba(255, 255, 255, 0.92);
            }
          }

          &.btn-ghost {
            background: rgba(255, 255, 255, 0.12);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.35);

            &:hover {
              background: rgba(255, 255, 255, 0.22);
              color: #fff;
            }
          }
        }
      }

      .hero-acknowledgment {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        opacity: 0.85;
        margin-top: 20px;

        .el-icon {
          font-size: 15px;
          color: #ffd700;
        }

        a {
          color: #fff;
          text-decoration: none;
          font-weight: 500;
          border-bottom: 1px solid rgba(255, 255, 255, 0.4);

          &:hover {
            border-bottom-color: #fff;
          }
        }
      }
    }

    .hero-side {
      flex-shrink: 0;

      .ver-preview {
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 14px;
        padding: 24px 32px;
        text-align: center;
        min-width: 200px;

        .ver-label {
          font-size: 13px;
          opacity: 0.85;
          margin-bottom: 8px;
        }

        .ver-num {
          font-size: 30px;
          font-weight: 700;
          font-family: 'Courier New', monospace;
          margin-bottom: 10px;
        }

        .ver-status {
          display: inline-block;
          padding: 3px 14px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;

          &.status-stable { background: #67c23a; color: #fff; }
          &.status-beta { background: #e6a23c; color: #fff; }
          &.status-dev { background: #909399; color: #fff; }
        }

        .ver-meta {
          font-size: 12px;
          opacity: 0.8;
          margin-top: 8px;
        }
      }
    }
  }

  // ===== 通用 Section =====
  .section {
    margin-bottom: 40px;
  }

  .section-head {
    margin-bottom: 18px;

    h2 {
      font-size: 20px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin: 0 0 6px 0;
    }

    p {
      font-size: 14px;
      color: var(--el-text-color-secondary);
      margin: 0;
    }
  }

  // ===== 版本信息 =====
  .version-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 12px;
    padding: 24px 28px;
    display: flex;
    align-items: center;
    gap: 32px;
    flex-wrap: wrap;

    .version-main {
      display: flex;
      align-items: center;
      gap: 14px;

      .version-num {
        font-size: 34px;
        font-weight: 700;
        font-family: 'Courier New', monospace;
        color: var(--el-color-primary);
      }

      .status-chip {
        padding: 3px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;

        &.status-stable { background: var(--el-color-success); color: #fff; }
        &.status-beta { background: var(--el-color-warning); color: #fff; }
        &.status-dev { background: var(--el-color-info); color: #fff; }
      }
    }

    .version-grid {
      flex: 1;
      min-width: 280px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 4px 32px;

      .version-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 7px 0;
        border-bottom: 1px dashed var(--el-border-color-extra-light);

        .label {
          font-size: 13px;
          color: var(--el-text-color-secondary);
          flex-shrink: 0;
          margin-right: 16px;
        }

        .value {
          font-size: 13px;
          font-weight: 500;
          color: var(--el-text-color-primary);
          text-align: right;
          word-break: break-all;

          &.code {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background: var(--el-fill-color-light);
            padding: 2px 8px;
            border-radius: 4px;
          }

          &.muted {
            color: var(--el-text-color-secondary);
            font-weight: 400;
          }
        }
      }
    }

    .version-actions {
      flex-shrink: 0;
    }
  }

  // ===== 版本亮点 =====
  .feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;

    .feature-card {
      background: var(--el-bg-color);
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 12px;
      padding: 24px;
      transition: box-shadow 0.25s ease, border-color 0.25s ease;

      &:hover {
        border-color: var(--el-color-primary-light-5);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.07);
      }

      .feature-icon {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 21px;
        color: #fff;
        margin-bottom: 14px;

        &.primary { background: linear-gradient(135deg, #409eff, #1e5edb); }
        &.success { background: linear-gradient(135deg, #67c23a, #4a9f28); }
        &.warning { background: linear-gradient(135deg, #e6a23c, #cf8420); }
        &.info { background: linear-gradient(135deg, #909399, #6b6e76); }
      }

      h3 {
        margin: 0 0 8px 0;
        font-size: 17px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      p {
        color: var(--el-text-color-regular);
        line-height: 1.65;
        margin: 0 0 14px 0;
        font-size: 14px;
      }

      .feature-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;

        .el-tag {
          border-radius: 10px;
        }
      }
    }
  }

  // ===== 技术栈 =====
  .tech-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 12px;
    padding: 24px 28px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 28px;

    .tech-col {
      &-head {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        margin-bottom: 10px;

        .el-icon {
          color: var(--el-color-primary);
          font-size: 17px;
        }
      }

      .tech-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 16px;
        padding: 7px 0;
        border-bottom: 1px dashed var(--el-border-color-extra-light);
        font-size: 13.5px;

        &:last-child { border-bottom: none; }

        span:first-child {
          font-weight: 500;
          color: var(--el-text-color-primary);
          white-space: nowrap;
        }

        span:last-child {
          font-size: 12.5px;
          color: var(--el-text-color-secondary);
          text-align: right;
        }
      }
    }
  }

  // ===== 开源与许可 =====
  .origin-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 12px;
    padding: 28px 32px;

    .origin-header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--el-border-color-extra-light);

      .origin-icon {
        width: 52px;
        height: 52px;
        border-radius: 12px;
        background: linear-gradient(135deg, #409eff, #1e5edb);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        color: #fff;
        flex-shrink: 0;
      }

      .origin-info {
        h3 {
          margin: 0 0 6px 0;
          font-size: 19px;
          font-weight: 700;
          color: var(--el-text-color-primary);
        }

        .origin-link {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: var(--el-color-primary);
          text-decoration: none;
          font-size: 13.5px;
          font-weight: 500;

          .el-icon { font-size: 13px; }

          &:hover { text-decoration: underline; }
        }
      }
    }

    .origin-desc {
      color: var(--el-text-color-regular);
      line-height: 1.75;
      margin: 0 0 12px 0;
      font-size: 14px;
    }

    .origin-list {
      list-style: none;
      padding: 0;
      margin: 0 0 16px 0;

      li {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 6px 0;
        font-size: 14px;
        line-height: 1.6;
        color: var(--el-text-color-regular);

        .el-icon {
          color: var(--el-color-success);
          font-size: 16px;
          margin-top: 3px;
          flex-shrink: 0;
        }

        strong {
          color: var(--el-text-color-primary);
          font-weight: 600;
        }
      }
    }

    .license-note {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 14px 16px;
      background: var(--el-fill-color-light);
      border-radius: 8px;
      border-left: 3px solid var(--el-color-primary);
      font-size: 13.5px;
      line-height: 1.65;
      color: var(--el-text-color-regular);

      .el-icon {
        color: var(--el-color-primary);
        font-size: 16px;
        margin-top: 2px;
        flex-shrink: 0;
      }

      strong { color: var(--el-text-color-primary); }

      a {
        color: var(--el-color-primary);
        text-decoration: none;

        &:hover { text-decoration: underline; }
      }
    }
  }

  // ===== 赞助商 =====
  .sponsor-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-color-primary-light-7);
    border-radius: 12px;
    padding: 24px 28px;

    .sponsor-header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;

      .sponsor-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background: linear-gradient(135deg, #409eff, #ec4899);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        color: #fff;
        flex-shrink: 0;
      }

      .sponsor-info {
        h3 {
          margin: 0 0 4px 0;
          font-size: 17px;
          font-weight: 700;
          color: var(--el-text-color-primary);
        }

        p {
          margin: 0;
          font-size: 13.5px;
          color: var(--el-text-color-secondary);
          line-height: 1.6;
        }
      }
    }

    .sponsor-actions {
      .el-button {
        border-radius: 8px;
      }
    }
  }

  // ===== 联系我们 =====
  .contact-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;

    .contact-card {
      background: var(--el-bg-color);
      border: 1px solid var(--el-border-color-lighter);
      border-radius: 12px;
      padding: 24px 20px;
      text-align: center;
      transition: border-color 0.25s ease, box-shadow 0.25s ease;

      &:hover {
        border-color: var(--el-color-primary-light-5);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.07);
      }

      .contact-icon {
        width: 46px;
        height: 46px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 14px;
        font-size: 20px;
        color: #fff;

        &.email { background: linear-gradient(135deg, #f56c6c, #d94848); }
        &.qq { background: linear-gradient(135deg, #36a3f7, #1e5edb); }
        &.wechat { background: linear-gradient(135deg, #2bc47a, #1a9e5c); }
        &.docs { background: linear-gradient(135deg, #409eff, #1e5edb); }
      }

      h4 {
        margin: 0 0 8px 0;
        font-size: 15.5px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      p {
        margin: 0 0 6px 0;
        font-size: 14.5px;
        font-weight: 500;
        color: var(--el-text-color-primary);

        a {
          color: var(--el-color-primary);
          text-decoration: none;

          &:hover { text-decoration: underline; }
        }
      }

      span {
        font-size: 12.5px;
        color: var(--el-text-color-secondary);
      }
    }
  }

  // ===== Footer =====
  .footer {
    text-align: center;
    padding: 28px 0 36px;
    border-top: 1px solid var(--el-border-color-extra-light);

    p {
      margin: 6px 0;
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }
}

// ===== 响应式 =====
@media (max-width: 900px) {
  .about {
    .hero {
      padding: 32px 28px;

      .hero-inner {
        flex-direction: column;
        align-items: stretch;
        gap: 28px;
      }

      .hero-side {
        .ver-preview {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 16px;
          min-width: 0;

          .ver-label { margin-bottom: 0; }
          .ver-num { margin-bottom: 0; font-size: 24px; }
          .ver-meta { margin-top: 0; }
        }
      }
    }

    .version-card {
      flex-direction: column;
      align-items: stretch;
      gap: 16px;

      .version-actions {
        text-align: right;
      }
    }
  }
}

@media (max-width: 600px) {
  .about {
    padding: 16px 16px 0;

    .hero {
      .hero-title {
        font-size: 26px;
        .version-badge {
          display: inline-block;
          margin: 8px 0 0;
        }
      }

      .hero-actions {
        flex-wrap: wrap;
      }
    }

    .section-head h2 { font-size: 18px; }

    .feature-grid,
    .contact-grid {
      grid-template-columns: 1fr;
    }

    .tech-card {
      grid-template-columns: 1fr;
    }
  }
}
</style>
