# 工作流 API 接口文档

## 📋 概述

工作流 API 提供了一套完整的接口，允许外部服务调用 TradingAgents-CN Pro 的自定义工作流。

**基础路径**: `/api/v1/workflow`

**认证方式**:
- JWT Token: `Authorization: Bearer <token>`
- Session Cookie: 自动从浏览器会话获取

---

## 🔌 API 端点

### 1. 执行工作流

**端点**: `POST /api/v1/workflow/execute`

**描述**: 执行指定的工作流，支持同步和异步两种模式

#### 请求参数

```json
{
  "workflow_id": "stock_analysis_workflow",  // 必填：工作流ID
  "ticker": "000001",                        // 必填：股票代码
  "analysis_date": "2026-02-19",             // 可选：分析日期（默认今天）
  "market_type": "cn",                       // 可选：市场类型（cn/us/hk）
  "research_depth": "标准",                   // 可选：研究深度（快速/标准/深度）
  "preference_type": "neutral",              // 可选：风险偏好（aggressive/neutral/conservative）
  "quick_analysis_model": "gpt-4o-mini",     // 可选：快速分析模型
  "deep_analysis_model": "gpt-4o",           // 可选：深度分析模型
  "lookback_days": 30,                       // 可选：回溯天数
  "max_debate_rounds": 2,                    // 可选：最大辩论轮数
  "custom_params": {},                       // 可选：自定义参数
  "async_mode": true,                        // 可选：是否异步执行（默认true）
  "timeout": 1800,                           // 可选：同步模式超时时间（秒）
  "callback_url": "https://..."              // 可选：异步模式回调URL
}
```

#### 响应示例

**异步模式**（默认）:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "任务已提交，正在后台执行"
}
```

**同步模式**:
```json
{
  "success": true,
  "result": {
    "summary": "分析完成",
    "reports": {...},
    "recommendation": "建议关注"
  },
  "execution_time": 125.5,
  "message": "任务执行完成"
}
```

---

### 2. 查询任务状态

**端点**: `GET /api/v1/workflow/task/{task_id}/status`

**描述**: 查询异步任务的执行状态和进度

#### 响应示例

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "message": "任务执行完成",
  "created_at": "2026-02-19T10:00:00Z",
  "started_at": "2026-02-19T10:00:05Z",
  "completed_at": "2026-02-19T10:02:10Z",
  "execution_time": 125.5,
  "result": {
    "summary": "分析完成",
    "recommendation": "建议关注"
  }
}
```

**状态值**:
- `pending`: 等待执行
- `running`: 正在执行
- `completed`: 执行完成
- `failed`: 执行失败
- `cancelled`: 已取消

---

### 3. 获取任务结果

**端点**: `GET /api/v1/workflow/task/{task_id}/result`

**描述**: 获取已完成任务的详细结果

#### 响应示例

```json
{
  "success": true,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "result": {
      "summary": "分析完成",
      "reports": {
        "market_report": "...",
        "fundamentals_report": "...",
        "综合报告": "..."
      },
      "recommendation": "建议关注"
    },
    "execution_time": 125.5,
    "completed_at": "2026-02-19T10:02:10Z"
  }
}
```

---

### 4. 取消任务

**端点**: `POST /api/v1/workflow/task/{task_id}/cancel`

**描述**: 取消正在执行或等待中的任务

#### 响应示例

```json
{
  "success": true,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "cancelled",
    "message": "任务已取消"
  }
}
```

---

## 📝 使用示例

### Python 示例

```python
import requests

# API 配置
BASE_URL = "http://127.0.0.1:8000"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. 异步执行工作流
response = requests.post(
    f"{BASE_URL}/api/v1/workflow/execute",
    headers=headers,
    json={
        "workflow_id": "stock_analysis_workflow",
        "ticker": "000001",
        "analysis_date": "2026-02-19",
        "research_depth": "标准",
        "async_mode": True
    }
)

task_id = response.json()["task_id"]
print(f"任务已提交: {task_id}")

# 2. 轮询任务状态
import time

while True:
    status_response = requests.get(
        f"{BASE_URL}/api/v1/workflow/task/{task_id}/status",
        headers=headers
    )
    
    status_data = status_response.json()
    print(f"任务状态: {status_data['status']} - 进度: {status_data['progress']}%")
    
    if status_data["status"] in ["completed", "failed", "cancelled"]:
        break
    
    time.sleep(5)  # 每5秒查询一次

# 3. 获取结果
if status_data["status"] == "completed":
    result_response = requests.get(
        f"{BASE_URL}/api/v1/workflow/task/{task_id}/result",
        headers=headers
    )
    
    result = result_response.json()["data"]["result"]
    print(f"分析结果: {result}")
```

### JavaScript/Node.js 示例

```javascript
const axios = require('axios');

const BASE_URL = 'http://127.0.0.1:8000';
const TOKEN = 'your_jwt_token_here';

const headers = {
  'Authorization': `Bearer ${TOKEN}`,
  'Content-Type': 'application/json'
};

// 1. 异步执行工作流
async function executeWorkflow() {
  const response = await axios.post(
    `${BASE_URL}/api/v1/workflow/execute`,
    {
      workflow_id: 'stock_analysis_workflow',
      ticker: '000001',
      analysis_date: '2026-02-19',
      research_depth: '标准',
      async_mode: true
    },
    { headers }
  );

  const taskId = response.data.task_id;
  console.log(`任务已提交: ${taskId}`);

  return taskId;
}

// 2. 轮询任务状态
async function pollTaskStatus(taskId) {
  while (true) {
    const response = await axios.get(
      `${BASE_URL}/api/v1/workflow/task/${taskId}/status`,
      { headers }
    );

    const statusData = response.data;
    console.log(`任务状态: ${statusData.status} - 进度: ${statusData.progress}%`);

    if (['completed', 'failed', 'cancelled'].includes(statusData.status)) {
      return statusData;
    }

    await new Promise(resolve => setTimeout(resolve, 5000)); // 每5秒查询一次
  }
}

// 3. 获取结果
async function getTaskResult(taskId) {
  const response = await axios.get(
    `${BASE_URL}/api/v1/workflow/task/${taskId}/result`,
    { headers }
  );

  return response.data.data.result;
}

// 主流程
(async () => {
  try {
    const taskId = await executeWorkflow();
    const status = await pollTaskStatus(taskId);

    if (status.status === 'completed') {
      const result = await getTaskResult(taskId);
      console.log('分析结果:', result);
    }
  } catch (error) {
    console.error('错误:', error.message);
  }
})();
```

### cURL 示例

```bash
# 1. 异步执行工作流
curl -X POST "http://127.0.0.1:8000/api/v1/workflow/execute" \
  -H "Authorization: Bearer your_jwt_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "stock_analysis_workflow",
    "ticker": "000001",
    "analysis_date": "2026-02-19",
    "research_depth": "标准",
    "async_mode": true
  }'

# 2. 查询任务状态
curl -X GET "http://127.0.0.1:8000/api/v1/workflow/task/{task_id}/status" \
  -H "Authorization: Bearer your_jwt_token_here"

# 3. 获取任务结果
curl -X GET "http://127.0.0.1:8000/api/v1/workflow/task/{task_id}/result" \
  -H "Authorization: Bearer your_jwt_token_here"

# 4. 取消任务
curl -X POST "http://127.0.0.1:8000/api/v1/workflow/task/{task_id}/cancel" \
  -H "Authorization: Bearer your_jwt_token_here"
```

---

## 🔧 高级用法

### 同步模式执行

适合执行时间较短的工作流（< 30分钟）：

```python
response = requests.post(
    f"{BASE_URL}/api/v1/workflow/execute",
    headers=headers,
    json={
        "workflow_id": "quick_analysis_workflow",
        "ticker": "000001",
        "async_mode": False,  # 同步模式
        "timeout": 300  # 5分钟超时
    }
)

if response.json()["success"]:
    result = response.json()["result"]
    print(f"分析结果: {result}")
else:
    print(f"执行失败或超时: {response.json()['message']}")
```

### 自定义参数传递

```python
response = requests.post(
    f"{BASE_URL}/api/v1/workflow/execute",
    headers=headers,
    json={
        "workflow_id": "custom_workflow",
        "ticker": "000001",
        "custom_params": {
            "report_style": "详细版",
            "include_charts": True,
            "export_format": "pdf",
            "custom_field_1": "value1",
            "custom_field_2": 123
        }
    }
)
```

### 回调 URL（异步通知）

```python
response = requests.post(
    f"{BASE_URL}/api/v1/workflow/execute",
    headers=headers,
    json={
        "workflow_id": "stock_analysis_workflow",
        "ticker": "000001",
        "async_mode": True,
        "callback_url": "https://your-service.com/api/workflow/callback"
    }
)

# 当任务完成时，系统会 POST 结果到 callback_url
# POST https://your-service.com/api/workflow/callback
# {
#   "task_id": "...",
#   "status": "completed",
#   "result": {...}
# }
```

---

## ⚠️ 注意事项

1. **认证要求**: 所有 API 都需要有效的 JWT Token 或 Session Cookie
2. **任务超时**: 同步模式默认超时 30 分钟，可通过 `timeout` 参数调整
3. **轮询频率**: 建议每 5-10 秒查询一次任务状态，避免过于频繁
4. **任务保留**: 已完成的任务结果会保留 7 天
5. **并发限制**: 每个用户最多同时执行 5 个工作流任务

---

## 🐛 错误处理

### 常见错误码

| 状态码 | 说明 | 解决方案 |
|--------|------|----------|
| 400 | 请求参数错误 | 检查必填参数是否提供 |
| 401 | 未认证 | 提供有效的 JWT Token |
| 403 | 无权访问 | 检查任务所有权 |
| 404 | 任务不存在 | 确认 task_id 正确 |
| 500 | 服务器错误 | 查看服务器日志 |

### 错误响应示例

```json
{
  "detail": "必须提供 ticker 或 stock_code 参数"
}
```

---

**最后更新**: 2026-02-19
**版本**: v1.0.0


