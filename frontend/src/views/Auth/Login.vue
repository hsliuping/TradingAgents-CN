<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <img src="/favicon.ico" alt="TradingAgents-CN" class="logo" />
        <h1 class="title">TradingAgents-CN 2.0</h1>
        <p class="subtitle">多智能体股票分析学习平台</p>
      </div>

      <el-card class="login-card" shadow="always">
        <el-form
          :model="loginForm"
          :rules="loginRules"
          ref="loginFormRef"
          label-position="top"
          size="large"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              prefix-icon="User"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <div class="form-options">
              <el-checkbox v-model="loginForm.rememberMe">
                记住我
              </el-checkbox>
            </div>
          </el-form-item>

          <el-form-item>
            <div class="agreement-check">
              <el-checkbox v-model="agreedToTerms">
                我已阅读并同意
              </el-checkbox>
              <el-link type="primary" :underline="false" @click.prevent="showAgreementDialog">《用户协议》</el-link>
              <span class="agreement-and">和</span>
              <el-link type="primary" :underline="false" @click.prevent="showPrivacyDialog">《隐私政策》</el-link>
            </div>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="loginLoading"
              :disabled="!agreedToTerms"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>

          <el-form-item>
            <div class="login-tip">
              <el-text type="info" size="small">
                默认账号：admin / admin123（请登录后修改密码）
              </el-text>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <div class="login-footer">
        <p>&copy; 2025-2026 TradingAgents-CN. All rights reserved.</p>
        <p class="disclaimer">
          TradingAgents-CN 是一个 AI 多 Agents 的股票分析学习平台。平台中的分析结论、观点和“投资建议”均由 AI 自动生成，仅用于学习、研究与交流，不构成任何形式的投资建议或承诺。用户据此进行的任何投资行为及其产生的风险与后果，均由用户自行承担。市场有风险，入市需谨慎。
        </p>
      </div>
    </div>

    <!-- 用户协议弹窗 -->
    <el-dialog
      v-model="agreementDialogVisible"
      title="用户协议"
      width="680px"
      top="5vh"
      :close-on-click-modal="false"
      class="legal-dialog"
    >
      <div class="legal-content" v-html="agreementHtml"></div>
      <template #footer>
        <el-button @click="agreementDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 隐私政策弹窗 -->
    <el-dialog
      v-model="privacyDialogVisible"
      title="隐私政策"
      width="680px"
      top="5vh"
      :close-on-click-modal="false"
      class="legal-dialog"
    >
      <div class="legal-content" v-html="privacyHtml"></div>
      <template #footer>
        <el-button @click="privacyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { marked } from 'marked'

const router = useRouter()
const authStore = useAuthStore()

const loginFormRef = ref()
const loginLoading = ref(false)

// 协议相关状态
const agreedToTerms = ref(false)
const agreementDialogVisible = ref(false)
const privacyDialogVisible = ref(false)
const agreementHtml = ref('')
const privacyHtml = ref('')

const loginForm = reactive({
  username: '',
  password: '',
  rememberMe: false
})

// 初始化：检查是否已经同意过协议
onMounted(() => {
  const accepted = localStorage.getItem('terms-accepted')
  if (accepted === 'true') {
    agreedToTerms.value = true
  }
})

// 加载并显示用户协议
const showAgreementDialog = async () => {
  if (!agreementHtml.value) {
    try {
      const response = await fetch('/legal/USER_AGREEMENT.md')
      if (response.ok) {
        const mdText = await response.text()
        agreementHtml.value = await marked(mdText)
      } else {
        agreementHtml.value = '<p>用户协议加载失败，请稍后重试。</p>'
      }
    } catch {
      agreementHtml.value = '<p>用户协议加载失败，请稍后重试。</p>'
    }
  }
  agreementDialogVisible.value = true
}

// 加载并显示隐私政策
const showPrivacyDialog = async () => {
  if (!privacyHtml.value) {
    try {
      const response = await fetch('/legal/PRIVACY_POLICY.md')
      if (response.ok) {
        const mdText = await response.text()
        privacyHtml.value = await marked(mdText)
      } else {
        privacyHtml.value = '<p>隐私政策加载失败，请稍后重试。</p>'
      }
    } catch {
      privacyHtml.value = '<p>隐私政策加载失败，请稍后重试。</p>'
    }
  }
  privacyDialogVisible.value = true
}

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  // 防止重复提交
  if (loginLoading.value) {
    console.log('⏭️ 登录请求进行中，跳过重复点击')
    return
  }

  // 检查是否同意协议
  if (!agreedToTerms.value) {
    ElMessage.warning('请先阅读并同意用户协议和隐私政策')
    return
  }

  try {
    await loginFormRef.value.validate()

    loginLoading.value = true
    console.log('🔐 开始登录流程...')

    // 调用真实的登录API
    const success = await authStore.login({
      username: loginForm.username,
      password: loginForm.password
    })

    if (success) {
      console.log('✅ 登录成功')
      // 记住用户已同意协议
      localStorage.setItem('terms-accepted', 'true')
      ElMessage.success('登录成功')

      // 跳转到重定向路径或仪表板
      const redirectPath = authStore.getAndClearRedirectPath()
      console.log('🔄 重定向到:', redirectPath)
      router.push(redirectPath)
    } else {
      ElMessage.error('用户名或密码错误')
    }

  } catch (error) {
    console.error('登录失败:', error)
    // 只有在不是表单验证错误时才显示错误消息
    const errorMessage = error instanceof Error ? error.message : String(error)
    if (errorMessage && !errorMessage.includes('validate')) {
      ElMessage.error('登录失败，请重试')
    }
  } finally {
    loginLoading.value = false
  }
}


</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-container {
  width: 100%;
  max-width: 400px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
  color: white;

  .logo {
    width: 64px;
    height: 64px;
    margin-bottom: 16px;
  }

  .title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 8px 0;
  }

  .subtitle {
    font-size: 16px;
    opacity: 0.9;
    margin: 0;
  }
}

.login-card {
  .form-options {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }

  .agreement-check {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    font-size: 13px;
    line-height: 1.6;

    .el-checkbox {
      margin-right: 0;
    }

    .el-link {
      font-size: 13px;
      vertical-align: baseline;
    }

    .agreement-and {
      margin: 0 2px;
      color: var(--el-text-color-regular);
    }
  }

  .login-tip {
    text-align: center;
    width: 100%;
    color: var(--el-text-color-regular);
  }
}

.login-footer {
  text-align: center;
  margin-top: 32px;
  color: white;
  opacity: 0.9;

  p {
    margin: 0;
    font-size: 14px;
  }

  .disclaimer {
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.6;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
    color: white;
    opacity: 0.85;
  }
}
</style>


<style lang="scss">
/* 法律文档弹窗样式（不使用 scoped，因为 el-dialog 渲染在 body 下） */
.legal-dialog {
  .el-dialog__body {
    max-height: 65vh;
    overflow-y: auto;
    padding: 16px 24px;
  }

  .legal-content {
    font-size: 14px;
    line-height: 1.8;
    color: var(--el-text-color-primary);

    h1 {
      font-size: 20px;
      margin: 16px 0 8px;
    }

    h2 {
      font-size: 17px;
      margin: 20px 0 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--el-border-color-lighter);
    }

    h3 {
      font-size: 15px;
      margin: 14px 0 6px;
    }

    p {
      margin: 8px 0;
    }

    ul, ol {
      padding-left: 20px;
      margin: 8px 0;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0;
      font-size: 13px;

      th, td {
        border: 1px solid var(--el-border-color);
        padding: 6px 10px;
        text-align: left;
      }

      th {
        background: var(--el-fill-color-light);
        font-weight: 600;
      }
    }

    blockquote {
      margin: 10px 0;
      padding: 8px 16px;
      border-left: 4px solid var(--el-color-warning);
      background: var(--el-fill-color-lighter);
      border-radius: 4px;
    }

    strong {
      color: var(--el-color-danger);
    }

    hr {
      margin: 16px 0;
      border: none;
      border-top: 1px solid var(--el-border-color-lighter);
    }
  }
}
</style>