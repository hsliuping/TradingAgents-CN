# 前端调试接口集成指南

## 接口概述

调试接口用于快速测试单个 Agent 模板，前端可以实时查看分析报告。

### 接口地址

```
POST http://127.0.0.1:3000/api/templates/debug/analyst
```

## 请求格式

```json
{
  "analyst_type": "fundamentals",
  "template_id": "6919a866fa8b760161a9167c",
  "use_current": false,
  "llm": {
    "provider": "dashscope",
    "model": "qwen-plus",
    "temperature": 0.7,
    "max_tokens": 4000,
    "backend_url": "",
    "api_key": ""
  },
  "stock": {
    "symbol": "000001",
    "analysis_date": "2025-11-17"
  }
}
```

## 响应格式

### 成功响应

```json
{
  "success": true,
  "data": {
    "analyst_type": "fundamentals",
    "symbol": "000001",
    "analysis_date": "2025-11-17",
    "report": "# 平安银行（000001）基本面分析报告\n\n## 📊 公司基本信息\n...",
    "report_length": 1878,
    "template": {
      "source": "user",
      "template_id": "6919a866fa8b760161a9167c",
      "version": 3,
      "agent_type": "analysts",
      "agent_name": "fundamentals_analyst",
      "preference_type": "neutral",
      "status": "active"
    },
    "debug_mode": true,
    "debug_template_id": "6919a866fa8b760161a9167c"
  },
  "message": "调试分析完成"
}
```

## 前端集成示例

### Vue 3 + TypeScript

```typescript
// api/debug.ts
import axios from 'axios'

interface DebugRequest {
  analyst_type: 'fundamentals' | 'market' | 'news' | 'social'
  template_id?: string
  use_current?: boolean
  llm: {
    provider: string
    model: string
    temperature: number
    max_tokens: number
    backend_url?: string
    api_key?: string
  }
  stock: {
    symbol: string
    analysis_date?: string
  }
}

interface DebugResponse {
  success: boolean
  data: {
    analyst_type: string
    symbol: string
    analysis_date: string
    report: string
    report_length: number
    template: {
      source: string
      template_id: string
      version: number
      agent_type: string
      agent_name: string
      preference_type: string
      status: string
    }
    debug_mode: boolean
    debug_template_id?: string
  }
  message: string
}

export async function debugAnalyst(req: DebugRequest): Promise<DebugResponse> {
  const response = await axios.post('/api/templates/debug/analyst', req)
  return response.data
}
```

### 组件使用

```vue
<template>
  <div class="debug-container">
    <!-- 表单 -->
    <form @submit.prevent="handleDebug">
      <div class="form-group">
        <label>分析师类型</label>
        <select v-model="form.analyst_type">
          <option value="fundamentals">基本面分析</option>
          <option value="market">市场分析</option>
          <option value="news">新闻分析</option>
          <option value="social">社交媒体分析</option>
        </select>
      </div>

      <div class="form-group">
        <label>模板ID</label>
        <input v-model="form.template_id" placeholder="可选，用于调试特定模板" />
      </div>

      <div class="form-group">
        <label>股票代码</label>
        <input v-model="form.stock.symbol" required />
      </div>

      <div class="form-group">
        <label>LLM提供商</label>
        <select v-model="form.llm.provider">
          <option value="dashscope">DashScope</option>
          <option value="openai">OpenAI</option>
          <option value="deepseek">DeepSeek</option>
        </select>
      </div>

      <button type="submit" :disabled="loading">
        {{ loading ? '分析中...' : '开始调试' }}
      </button>
    </form>

    <!-- 结果展示 -->
    <div v-if="result" class="result-container">
      <div class="result-header">
        <h2>{{ result.data.analyst_type }} - {{ result.data.symbol }}</h2>
        <div class="meta-info">
          <span>报告长度: {{ result.data.report_length }} 字符</span>
          <span v-if="result.data.debug_mode" class="debug-badge">调试模式</span>
          <span>模板版本: {{ result.data.template.version }}</span>
        </div>
      </div>

      <!-- 报告内容 -->
      <div class="report-content">
        <div v-html="markdownToHtml(result.data.report)"></div>
      </div>

      <!-- 模板信息 -->
      <div class="template-info">
        <h3>模板信息</h3>
        <ul>
          <li>来源: {{ result.data.template.source }}</li>
          <li>Agent: {{ result.data.template.agent_type }}/{{ result.data.template.agent_name }}</li>
          <li>偏好: {{ result.data.template.preference_type }}</li>
          <li>状态: {{ result.data.template.status }}</li>
        </ul>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { debugAnalyst } from '@/api/debug'
import { markdownToHtml } from '@/utils/markdown'

const loading = ref(false)
const result = ref(null)
const error = ref('')

const form = ref({
  analyst_type: 'fundamentals',
  template_id: '',
  use_current: false,
  llm: {
    provider: 'dashscope',
    model: 'qwen-plus',
    temperature: 0.7,
    max_tokens: 4000,
    backend_url: '',
    api_key: ''
  },
  stock: {
    symbol: '000001',
    analysis_date: new Date().toISOString().split('T')[0]
  }
})

async function handleDebug() {
  loading.value = true
  error.value = ''
  result.value = null

  try {
    const response = await debugAnalyst(form.value)
    result.value = response
  } catch (err: any) {
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.debug-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.result-container {
  margin-top: 30px;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 20px;
}

.result-header {
  border-bottom: 2px solid #007bff;
  padding-bottom: 15px;
  margin-bottom: 20px;
}

.meta-info {
  display: flex;
  gap: 20px;
  margin-top: 10px;
  font-size: 14px;
  color: #666;
}

.debug-badge {
  background-color: #ffc107;
  color: #000;
  padding: 2px 8px;
  border-radius: 3px;
  font-weight: bold;
}

.report-content {
  background-color: #f9f9f9;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
  max-height: 600px;
  overflow-y: auto;
}

.template-info {
  background-color: #f0f0f0;
  padding: 15px;
  border-radius: 4px;
}

.template-info ul {
  list-style: none;
  padding: 0;
}

.template-info li {
  padding: 5px 0;
}

.error-message {
  color: #d32f2f;
  background-color: #ffebee;
  padding: 15px;
  border-radius: 4px;
  margin-top: 20px;
}
</style>
```

## 使用流程

1. **选择分析师类型** - 选择要调试的 Agent
2. **输入股票代码** - 输入要分析的股票
3. **选择模板** - 可选，指定要调试的模板ID
4. **配置LLM** - 选择LLM提供商和模型
5. **点击调试** - 提交请求
6. **查看报告** - 实时显示分析报告和模板信息

## 注意事项

- 调试接口只测试单个 Agent 节点，不执行完整流程
- 报告内容使用 Markdown 格式，需要前端进行渲染
- 模板ID为空时，使用默认模板
- 调试模式不会修改任何配置或数据库

