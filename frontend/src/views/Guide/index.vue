<template>
  <div class="guide-page">
    <!-- 欢迎标题 -->
    <div class="guide-header">
      <h1 class="guide-title">
        <el-icon><Document /></el-icon>
        欢迎使用 TradingAgents-CN
      </h1>
      <p class="guide-subtitle">
        {{ isJdyunModeRef ? '按照以下步骤完成初始设置，开始使用 AI 辅助股票分析' : '按照以下步骤完成初始设置，开始学习AI辅助股票分析技术' }}
      </p>
      <el-button v-if="!loading" text type="primary" @click="loadAllStatus" class="refresh-btn">
        <el-icon><Refresh /></el-icon>
        刷新进度
      </el-button>
    </div>

    <!-- 京东云版引导：4 步 -->
    <div v-if="isJdyunModeRef" class="steps-container" v-loading="loading" element-loading-text="正在检测配置进度...">
      <el-steps :active="jdyunCurrentStep" direction="vertical" finish-status="success">
        <!-- 京东云版步骤 1：欢迎（系统已就绪） -->
        <el-step title="欢迎使用" description="您的系统已由管理员配置完成">
          <template #description>
            <div class="step-content">
              <div class="jdyun-ready-list">
                <div class="ready-item">
                  <el-icon color="#67c23a"><CircleCheck /></el-icon>
                  <span>大模型：<strong>{{ jdyunStatus.current_model || 'GLM-5.1' }}</strong>（已就绪）</span>
                </div>
                <div class="ready-item">
                  <el-icon color="#67c23a"><CircleCheck /></el-icon>
                  <span>数据源：<strong>Tushare + AKShare</strong>（已就绪）</span>
                </div>
                <div class="ready-item">
                  <el-icon color="#67c23a"><CircleCheck /></el-icon>
                  <span>全功能开放（无需激活 License）</span>
                </div>
              </div>
              <p class="step-tip" style="margin-top: 12px;">
                接下来只需 3 步即可开始分析：同步数据 → 添加股票关注列表 → 完成首次研究
              </p>
            </div>
          </template>
        </el-step>

        <!-- 京东云版步骤 2：同步股票数据 -->
        <el-step title="同步股票数据" description="同步基础股票数据到系统">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.dataSynced" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                股票数据已同步完成
              </p>
              <template v-else>
                <p>同步基础股票数据，获取最新的股票信息：</p>
                <ul class="step-list">
                  <li><strong>第一步：</strong>同步基础数据（股票列表、基本信息）</li>
                  <li><strong>第二步：</strong>同步历史数据（K线、行情）</li>
                  <li><strong>第三步：</strong>同步财务数据（财报、指标）</li>
                  <li>
                    <strong style="color: var(--el-color-warning);">注意：</strong>
                    数据未同步完成时进行分析，可能因数据不全导致结果不准确
                  </li>
                </ul>
              </template>
              <el-button type="primary" @click="goToSync">
                <el-icon><Refresh /></el-icon>
                前往数据同步
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 京东云版步骤 3：搜索并添加股票关注列表 -->
        <el-step title="搜索并添加股票关注列表" description="搜索感兴趣的股票并添加到自选列表">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.hasFavorites" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                已添加股票关注列表
              </p>
              <template v-else>
                <p>开始使用股票筛选功能：</p>
                <ul class="step-list">
                  <li>在"股票筛选"页面搜索股票代码或名称</li>
                  <li>查看股票详情信息</li>
                  <li>将感兴趣的股票添加到"股票关注列表"</li>
                </ul>
              </template>
              <el-button type="primary" @click="goToScreening">
                <el-icon><Search /></el-icon>
                前往股票筛选
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 京东云版步骤 4：完成首次分析 -->
        <el-step title="完成第一次研究" description="对股票关注列表进行 AI 研究">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.hasAnalysis" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                已完成首次研究分析
              </p>
              <template v-else>
                <p>开始您的第一次 AI 股票研究：</p>
                <ul class="step-list">
                  <li>在"单股研究"页面输入股票代码（如：600519）</li>
                  <li>选择研究深度（1-5 级，从快速到全面）</li>
                  <li>点击"开始研究"，等待多智能体协作完成</li>
                  <li>低深度约 5-8 分钟，高深度可能 15-20 分钟</li>
                </ul>
              </template>
              <el-button type="primary" @click="goToAnalysis">
                <el-icon><TrendCharts /></el-icon>
                开始研究
              </el-button>
            </div>
          </template>
        </el-step>
      </el-steps>

      <!-- 完成引导按钮 -->
      <div v-if="jdyunAllCompleted" class="jdyun-complete-section">
        <el-alert
          title="引导已完成"
          type="success"
          description="您已完成所有初始设置步骤，可以开始使用系统的全部功能了。"
          :closable="false"
          show-icon
        />
        <div class="complete-actions">
          <el-button @click="goToLearning">
            <el-icon><Reading /></el-icon>
            查看学习中心
          </el-button>
          <el-button type="primary" size="large" @click="completeJdyunGuide">
            进入仪表板
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 跳过引导：未完成所有步骤时也允许进入仪表板，避免死循环 -->
      <div v-else class="jdyun-complete-section">
        <el-alert
          title="您可以随时跳过引导"
          type="info"
          description="未完成所有步骤也可进入仪表板开始使用，后续可从侧边栏「使用指南」回来查看。"
          :closable="false"
          show-icon
        />
        <div class="complete-actions">
          <el-button @click="goToLearning">
            <el-icon><Reading /></el-icon>
            查看学习中心
          </el-button>
          <el-button type="primary" size="large" @click="completeJdyunGuide">
            进入仪表板
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 标准版引导：7 步（原有逻辑保持不变） -->
    <div v-else class="steps-container" v-loading="loading" element-loading-text="正在检测配置进度...">
      <el-steps :active="currentStep" direction="vertical" finish-status="success">
        <!-- 步骤1：获取大模型API密钥 -->
        <el-step title="获取大模型API密钥" description="选择并获取大语言模型的API密钥">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.llmKey" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                大模型 API 密钥已配置
              </p>
              <template v-else>
              <p>系统支持多种主流大语言模型，推荐优先使用国内模型，您需要选择其中一个并获取API密钥：</p>
              <ul class="step-list">
                <li>
                  <strong>火山方舟：</strong>豆包大模型 Seed 系列（推荐国内用户）<br>
                  <span style="font-size: 13px; color: var(--el-text-color-secondary);">感谢字节火山引擎赞助本项目！注册即领2500万Tokens</span>
                  <div class="register-link-wrapper">
                    <el-link href="https://www.volcengine.com/product/ark?utm_campaign=hw&utm_content=TradingAgents-CN&utm_medium=devrel-1&utm_source=OWO&utm_term=TradingAgents-CN" target="_blank" type="primary" :underline="false" class="register-link">
                      <el-icon><Link /></el-icon>
                      注册即领2500万Tokens，立即前往
                    </el-link>
                  </div>
                </li>
                <li>
                  <strong>DeepSeek：</strong>DeepSeek-V4-Pro、V4-Flash模型（推荐国内用户）
                  <div class="register-link-wrapper">
                    <el-link href="https://platform.deepseek.com/" target="_blank" type="primary" :underline="false" class="register-link">
                      <el-icon><Link /></el-icon>
                      立即注册 DeepSeek 账号
                    </el-link>
                  </div>
                </li>
                <li><strong>智谱AI：</strong>GLM-5、GLM-5.2 等模型</li>
                <li><strong>OpenAI：</strong>GPT-5、GPT-5.4 等模型</li>
                <li><strong>Claude：</strong>Claude Opus 5、Opus 4.8 等模型</li>
                <li><strong>其他：</strong>Kimi、小米 MiMo、AIHubMix、硅基流动等</li>
                <li><strong>本地模型：</strong>Ollama（无需 API Key，本地部署）</li>
              </ul>
              <p class="step-tip">💡 提示：国内用户推荐优先使用火山方舟或 DeepSeek，访问速度更快，使用更稳定</p>
              </template>
            </div>
          </template>
        </el-step>

        <!-- 步骤2：获取数据源API密钥 -->
        <el-step title="获取数据源API密钥" description="注册Tushare账号并获取API Token">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.dataKey" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                数据源 Token 已配置
              </p>
              <template v-else>
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
              </template>
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
                    <li>找到对应的厂家（如火山方舟、DeepSeek等）</li>
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
                      如果积分不足，系统会自动使用免费的开源数据源（AKShare）作为替代。
                      <strong style="color: var(--el-color-warning);">请注意：</strong>开源数据源因稳定性问题，<strong>仅作为体验本平台使用</strong>，不建议用于正式学习或分析场景。
                    </p>
                    <ol style="margin-top: 8px; padding-left: 24px;">
                      <li>进入"配置管理" → "数据源配置"菜单</li>
                      <li>找到 Tushare 数据源并点击"编辑"</li>
                      <li>填入步骤2获取的Token（在 <a href="https://tushare.pro/user/index" target="_blank" rel="noopener noreferrer" class="tushare-link">Tushare个人中心</a> 获取）</li>
                      <li>保存配置</li>
                      <li>如果积分不足2000，系统会自动使用 AKShare 等免费数据源（仅用于体验，不建议正式使用）</li>
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

        <!-- 步骤4：激活License（社区版无此接口，运行时自动隐藏） -->
        <el-step v-if="licenseSupported" title="激活 License 授权" description="输入 License 密钥激活系统">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.licenseValid" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                License 已激活，无需重复操作
              </p>
              <template v-else>
                <p>v3.0 版本需要激活 License 才能使用完整功能：</p>
                <ul class="step-list">
                  <li>进入"设置" → "个人设置" → "授权管理"页面</li>
                  <li>输入收到的 License 密钥</li>
                  <li>点击"激活"按钮完成激活</li>
                  <li>激活后即可使用所有功能</li>
                </ul>
                <p class="step-tip">💡 提示：如果未收到 License 密钥，请联系管理员获取</p>
              </template>
              <el-button type="primary" @click="goToLicense">
                <el-icon><Key /></el-icon>
                前往授权管理
              </el-button>
            </div>
          </template>
        </el-step>

        <!-- 步骤5：同步数据 -->
        <el-step title="同步股票数据" description="同步基础股票数据到系统">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.dataSynced" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                股票数据已同步完成
              </p>
              <template v-else>
              <p>完成数据同步，获取最新的股票基础信息：</p>
              <ul class="step-list">
                <li>
                  <strong>重要说明：</strong>目前数据同步功能<strong style="color: var(--el-color-warning);">仅支持A股市场</strong>。
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
              </template>
            </div>
          </template>
        </el-step>

        <!-- 步骤6：搜索股票 -->
        <el-step title="搜索并添加股票关注列表" description="搜索感兴趣的股票并添加到自选列表">
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

        <!-- 步骤7：完成第一次研究 -->
        <el-step title="完成第一次研究" description="对股票关注列表进行 AI 研究">
          <template #description>
            <div class="step-content">
              <p v-if="stepStatus.hasAnalysis" class="step-completed-tip">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                已完成首次研究分析
              </p>
              <template v-else>
              <p>开始您的第一次 AI 股票研究：</p>
              <ul class="step-list">
                <li>
                  <strong>填写股票代码：</strong>
                  在"单股研究"页面输入股票代码（如：000001、600000等）
                </li>
                <li>
                  <strong>检测数据是否完整：</strong>
                  系统会自动检测该股票的基础数据、历史数据、财务数据是否完整
                </li>
                <li>
                  <strong>选择研究深度和研究团队：</strong>
                  <ol style="margin-top: 8px; padding-left: 24px;">
                    <li>选择研究深度等级（1-5级，从快速到全面）</li>
                    <li>选择研究团队（可选择多个研究模块，如市场、基本面、新闻等）</li>
                  </ol>
                </li>
                <li>
                  <strong>开始研究：</strong>
                  点击"开始研究"按钮，系统将启动多智能体协作研究流程
                </li>
                <li>
                  <strong>等待并查看结果：</strong>
                  等待研究完成（低深度约 5-8 分钟，高深度可能 15-20 分钟），研究完成后查看详细的研究报告和研究结论
                </li>
              </ul>
              <el-button type="primary" @click="goToAnalysis">
                <el-icon><TrendCharts /></el-icon>
                开始研究
              </el-button>
              </template>
            </div>
          </template>
        </el-step>
      </el-steps>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Document,
  Setting,
  Refresh,
  Search,
  TrendCharts,
  Link,
  Key,
  CircleCheck,
  Reading,
  ArrowRight
} from '@element-plus/icons-vue'
import { ApiClient } from '@/api/request'
import { isJdyunMode } from '@/utils/config'

const router = useRouter()
const isJdyunModeRef = isJdyunMode()
const currentStep = ref(0)
const loading = ref(true)
// License 步骤是否可用（社区版无 /api/license/status 接口，404 时自动隐藏该步骤）
const licenseSupported = ref(true)

// 京东云版状态
const jdyunStatus = ref({
  current_model: ''
})

// 各步骤完成状态
const stepStatus = ref({
  llmKey: false,        // 步骤1: LLM API密钥
  dataKey: false,       // 步骤2: 数据源Token
  configDone: false,    // 步骤3: 填写配置
  dataSynced: false,    // 步骤5: 数据同步
  hasFavorites: false,  // 步骤6: 添加股票关注列表
  hasAnalysis: false,   // 步骤7: 完成研究
  licenseValid: false   // License激活
})

// 检查股票关注列表状态
const checkFavorites = async () => {
  try {
    const resp = await ApiClient.get('/api/favorites')
    if (resp.success && resp.data) {
      const favorites = Array.isArray(resp.data) ? resp.data : (resp.data.items || resp.data.favorites || [])
      stepStatus.value.hasFavorites = favorites.length > 0
    }
  } catch (e) {
    console.error('检查股票关注列表失败:', e)
  }
}

// 检查京东云版配置（当前模型名）
const checkJdyunConfig = async () => {
  try {
    const resp = await ApiClient.get('/api/config/jdyun/status')
    if (resp.success && resp.data) {
      jdyunStatus.value.current_model = resp.data.current_model || resp.data.model || ''
    }
  } catch (e) {
    // 接口不存在时使用默认值
    jdyunStatus.value.current_model = 'GLM-5.1'
  }
}

// 京东云版当前步骤（基于 stepStatus）
const jdyunCurrentStep = computed(() => {
  // 4 步：欢迎 → 同步 → 股票关注列表 → 首次分析
  if (!stepStatus.value.dataSynced) return 1
  if (!stepStatus.value.hasFavorites) return 2
  if (!stepStatus.value.hasAnalysis) return 3
  return 4
})

// 京东云版是否全部完成
const jdyunAllCompleted = computed(() =>
  stepStatus.value.dataSynced &&
  stepStatus.value.hasFavorites &&
  stepStatus.value.hasAnalysis
)

// 完成京东云版引导
const completeJdyunGuide = () => {
  try {
    localStorage.setItem('jdyun_guide_completed', 'true')
  } catch (e) {
    console.warn('写入 localStorage 失败:', e)
  }
  router.push('/dashboard')
}

const goToLearning = () => {
  router.push('/learning')
}

// 检测 LLM API 密钥配置状态
const checkLLMKey = async () => {
  try {
    const resp = await ApiClient.get('/api/config/llm/providers')
    if (resp.success && resp.data) {
      const providers = Array.isArray(resp.data) ? resp.data : (resp.data.providers || [])
      stepStatus.value.llmKey = providers.some((p: any) => p.has_api_key || p.has_api_secret)
    }
  } catch (e) {
    console.error('检查LLM配置失败:', e)
  }
}

// 检测数据源同步状态（间接判断Token是否配置）
const checkDataSync = async () => {
  try {
    const resp = await ApiClient.get('/api/sync/stock_basics/status')
    if (resp.success && resp.data) {
      // 如果有同步记录或数据量 > 0，说明 Token 已配置并同步过
      const status = resp.data
      if (status.total_count > 0 || status.status === 'completed') {
        stepStatus.value.dataKey = true
        stepStatus.value.dataSynced = true
      }
    }
  } catch (e) {
    console.error('检查数据同步状态失败:', e)
  }
}

// 检测是否已完成过分析任务
const checkAnalysisHistory = async () => {
  try {
    const resp = await ApiClient.get('/api/v2/tasks/list', {
      params: { status: 'completed', limit: 1 }
    })
    if (resp.success && resp.data) {
      stepStatus.value.hasAnalysis = (resp.data.total || 0) > 0
    }
  } catch (e) {
    console.error('检查分析历史失败:', e)
  }
}

// 检测 License 状态
const checkLicense = async () => {
  try {
    // 注意：第三参数才是 RequestConfig；误传到第二参数会变成 URL query，
    // 导致 skipErrorHandler 失效、社区版 404 弹窗
    const resp = await ApiClient.get('/api/license/status', undefined, { skipErrorHandler: true })
    if (resp.success && resp.data) {
      stepStatus.value.licenseValid = resp.data.is_valid || resp.data.has_token || false
    }
  } catch (e: any) {
    // 404 = 社区版（无 License 激活功能），隐藏引导中的激活步骤
    if (e?.response?.status === 404) {
      licenseSupported.value = false
      console.debug('License 接口不可用（社区版），已隐藏激活步骤')
    } else {
      console.error('检查License状态失败:', e)
    }
  }
}

// 根据完成状态计算当前步骤
const updateCurrentStep = () => {
  // 社区版隐藏 License 步骤后，后续步骤索引前移一位
  const hasLicenseStep = licenseSupported.value
  let step = 0
  if (stepStatus.value.llmKey) step = 1
  if (stepStatus.value.dataKey) step = 2
  if (stepStatus.value.llmKey && stepStatus.value.dataKey) step = 3
  if (hasLicenseStep && stepStatus.value.licenseValid) step = 4
  if (stepStatus.value.dataSynced) step = hasLicenseStep ? 5 : 4
  if (stepStatus.value.hasAnalysis) step = hasLicenseStep ? 7 : 6
  currentStep.value = step
}

// 加载所有状态
const loadAllStatus = async () => {
  loading.value = true
  if (isJdyunModeRef) {
    // 京东云版：只检查同步、股票关注列表、分析历史
    await Promise.allSettled([
      checkDataSync(),
      checkFavorites(),
      checkAnalysisHistory(),
      checkJdyunConfig()
    ])
  } else {
    // 标准版：检查所有配置
    await Promise.allSettled([
      checkLLMKey(),
      checkDataSync(),
      checkAnalysisHistory(),
      checkLicense()
    ])
  }
  updateCurrentStep()
  loading.value = false
}

onMounted(() => {
  loadAllStatus()
})

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

const goToLicense = () => {
  router.push('/settings/license')
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

    .refresh-btn {
      margin-top: 12px;
    }

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

        &.step-completed-tip {
          display: flex;
          align-items: center;
          gap: 6px;
          color: var(--el-color-success);
          font-weight: 500;
        }

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

// 京东云版引导样式
.jdyun-ready-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin-top: 8px;

  .ready-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: var(--el-text-color-regular);

    strong {
      color: var(--el-text-color-primary);
    }
  }
}

.step-completed-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-color-success);
  font-weight: 500;
}

.jdyun-complete-section {
  margin-top: 32px;
  padding: 24px;
  background: linear-gradient(135deg, rgba(103, 194, 58, 0.05) 0%, rgba(64, 158, 255, 0.05) 100%);
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);

  .complete-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
  }
}
