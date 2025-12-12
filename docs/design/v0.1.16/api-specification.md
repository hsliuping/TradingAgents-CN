# TradingAgents-CN v0.1.16 API 接口规范

## 概述

本规范定义前后端分离后的REST API与SSE接口，涵盖认证、选股、分析、队列与进度流。

## 认证 Authentication

### 登录
- Method: POST
- URL: /api/auth/login
- Body:
```
{
  "username": "string",
  "password": "string"
}
```
- Response:
```
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {"id": "u_123", "name": "Alice"}
}
```

### 登出
- Method: POST
- URL: /api/auth/logout
- Headers: Authorization: Bearer <token>
- Response: 204 No Content

### 当前用户
- Method: GET
- URL: /api/auth/me
- Headers: Authorization: Bearer <token>
- Response:
```
{
  "id": "u_123",
  "name": "Alice",
  "roles": ["user"],
  "preferences": {...}
}
```

## 选股 Screening

### 条件筛选
- Method: POST
- URL: /api/screening/filter
- Body:
```
{
  "market": "CN|HK|US",
  "sectors": ["Tech", "Finance"],
  "market_cap": {"min": 10e8, "max": 10e12},
  "indicators": {"pe": {"max": 30}, "pb": {"max": 3}},
  "limit": 100,
  "sort": {"field": "market_cap", "order": "desc"}
}
```
- Response:
```
{
  "results": [{"code": "600519.SH", "name": "贵州茅台", "market_cap": 2.5e12, ...}],
  "total": 3584,
  "took_ms": 124
}
```

## 分析 Analysis

### 提交单股分析
- Method: POST
- URL: /api/analysis/submit
- Body:
```
{
  "stock_code": "600519.SH",
  "market_type": "CN|HK|US",
  "analysis_date": "2025-01-17",
  "research_depth": "basic|medium|deep",
  "analysts": ["researcher", "analyst"],
  "options": {"risk": true, "news": true}
}
```
- Response:
```
{ "task_id": "task_abc", "status": "queued" }
```

### 提交批量分析
- Method: POST
- URL: /api/analysis/batch
- Body:
```
{
  "title": "本周重点标的",
  "stocks": ["600519.SH", "000001.SZ", "00700.HK"],
  "params": {"market_type": "CN", "analysis_date": "2025-01-17", ...}
}
```
- Response:
```
{ "batch_id": "batch_xyz", "total": 3, "queued": 3 }
```

### 查询任务/批次状态
- Method: GET
- URL: /api/analysis/task/{task_id}
- Response:
```
{ "task_id": "task_abc", "status": "processing", "progress": 42, "message": "Fetching data" }
```

- Method: GET
- URL: /api/analysis/batch/{batch_id}
- Response:
```
{ "batch_id": "batch_xyz", "status": "processing", "progress": 33, "completed": 1, "failed": 0, "total": 3 }
```

### 取消/重试
- Method: POST
- URL: /api/analysis/task/{task_id}/cancel
- Response: 202 Accepted

- Method: POST
- URL: /api/analysis/task/{task_id}/retry
- Response: 202 Accepted

## 队列 Queue

### 队列统计
- Method: GET
- URL: /api/queue/stats
- Response:
```
{ "total_pending": 12, "total_processing": 3, "workers": 2 }
```

## 进度流 Progress (SSE)

### 订阅批次进度
- Method: GET
- URL: /api/stream/batch/{batch_id}
- Response (text/event-stream):
```
event: progress
data: {"batch_id":"batch_xyz","progress":40,"completed":2,"failed":0}
```

### 订阅任务进度
- Method: GET
- URL: /api/stream/task/{task_id}
- Response (text/event-stream):
```
event: progress
data:{"task_id":"task_abc","progress":72,"message":"LLM reasoning"}
```

## 错误处理

- 统一错误响应：
```
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Task not found",
    "request_id": "req_12345"
  }
}
```

## 安全与限流
- 所有受保护接口需Bearer Token
- 速率限制建议：每用户 60 req/min；提交分析 10 req/min
- CORS严格白名单

## 附录
- 状态枚举：queued|processing|completed|failed|cancelled
- 进度范围：0-100，整数
- 时间格式：ISO8601，UTC