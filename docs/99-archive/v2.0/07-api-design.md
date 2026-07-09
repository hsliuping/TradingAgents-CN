# API 接口设计

## 📋 概述

本文档定义 v2.0 新增的 API 接口，主要包括：
1. 工作流管理 API
2. 智能体管理 API
3. 提示词管理 API
4. 授权管理 API

---

## 🔗 工作流 API

### 基础路径: `/api/v1/workflows`

#### 获取工作流列表

```http
GET /api/v1/workflows
```

**Query 参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| is_template | bool | 否 | 是否只返回模板 |
| category | string | 否 | 分类筛选 |

**响应**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "wf_001",
        "name": "默认分析流程",
        "description": "标准多智能体分析",
        "version": "1.0.0",
        "is_template": true,
        "node_count": 10,
        "created_at": "2025-12-07T10:00:00Z",
        "updated_at": "2025-12-07T10:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

#### 创建工作流

```http
POST /api/v1/workflows
```

**请求体**:
```json
{
  "name": "我的分析流程",
  "description": "自定义分析流程",
  "nodes": [
    {
      "id": "node_1",
      "type": "analyst",
      "agent_id": "market_analyst",
      "name": "市场分析师",
      "position": {"x": 100, "y": 100},
      "config": {}
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "START",
      "target": "node_1"
    }
  ],
  "variables": [],
  "settings": {}
}
```

#### 执行工作流

```http
POST /api/v1/workflows/{workflow_id}/execute
```

**请求体**:
```json
{
  "ticker": "AAPL",
  "date": "2025-12-07",
  "variables": {
    "analysis_depth": "deep"
  }
}
```

**响应** (SSE 流式):
```
event: node_start
data: {"node_id": "market", "node_name": "市场分析师"}

event: node_progress
data: {"node_id": "market", "progress": 50, "message": "正在分析..."}

event: node_complete
data: {"node_id": "market", "output": "市场分析报告..."}

event: workflow_complete
data: {"result": {...}, "duration": 120}
```

---

## 🤖 智能体 API

### 基础路径: `/api/v1/agents`

#### 获取智能体列表

```http
GET /api/v1/agents
```

**Query 参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| category | string | 否 | 分类: analyst, researcher, trader, risk, manager |

**响应**:
```json
{
  "code": 0,
  "data": [
    {
      "id": "market_analyst",
      "name": "市场分析师",
      "description": "分析市场趋势和技术指标",
      "category": "analyst",
      "version": "1.0.0",
      "inputs": ["company_of_interest", "trade_date"],
      "outputs": ["market_report"],
      "tools": ["get_stock_price", "get_technical_indicators"],
      "icon": "TrendCharts",
      "color": "#1890ff",
      "license_tier": "free"
    }
  ]
}
```

#### 获取智能体详情

```http
GET /api/v1/agents/{agent_id}
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "market_analyst",
    "name": "市场分析师",
    "description": "分析市场趋势和技术指标",
    "category": "analyst",
    "version": "1.0.0",
    "inputs": ["company_of_interest", "trade_date"],
    "outputs": ["market_report"],
    "tools": [
      {
        "name": "get_stock_price",
        "description": "获取股票价格",
        "parameters": {...}
      }
    ],
    "prompt_template": {
      "id": "market_analyst_prompt",
      "name": "市场分析师提示词",
      "content": "你是一个专业的市场分析师..."
    },
    "config_schema": {
      "type": "object",
      "properties": {
        "analysis_period": {"type": "string", "default": "1M"}
      }
    }
  }
}
```

---

## 📝 提示词 API

### 基础路径: `/api/v1/prompts`

#### 获取提示词列表

```http
GET /api/v1/prompts
```

#### 更新提示词

```http
PUT /api/v1/prompts/{prompt_id}
```

**请求体**:
```json
{
  "content": "你是一个专业的市场分析师...",
  "variables": ["company", "date", "market_type"],
  "version_note": "优化了分析深度"
}
```

#### 获取提示词版本历史

```http
GET /api/v1/prompts/{prompt_id}/versions
```

---

## 🔐 授权 API

### 基础路径: `/api/v1/license`

#### 获取当前许可证信息

```http
GET /api/v1/license
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "tier": "pro",
    "expires_at": "2026-12-07T00:00:00Z",
    "features": {
      "max_workflows": -1,
      "max_agents": 10,
      "max_concurrent": 10,
      "custom_prompts": true,
      "api_calls_per_day": 5000
    },
    "usage": {
      "workflows_count": 5,
      "api_calls_today": 120
    }
  }
}
```

#### 激活许可证

```http
POST /api/v1/license/activate
```

**请求体**:
```json
{
  "license_key": "XXXX-XXXX-XXXX-XXXX"
}
```

---

## 📊 错误码定义

| 错误码 | 描述 |
|--------|------|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | 资源不存在 |
| 2001 | 许可证无效 |
| 2002 | 许可证过期 |
| 2003 | 功能未授权 |
| 2004 | 超出配额限制 |
| 3001 | 工作流验证失败 |
| 3002 | 工作流执行失败 |
| 4001 | 智能体不存在 |
| 5001 | 内部错误 |

