# 数据模型设计

## 📋 概述

本文档定义 v2.0 的核心数据模型，包括数据库表结构和 Pydantic 模型。

---

## 🗄️ 数据库设计 (MongoDB)

### workflows 集合

```javascript
{
  "_id": ObjectId("..."),
  "id": "wf_001",                    // 业务ID
  "name": "默认分析流程",
  "description": "标准多智能体分析",
  "version": "1.0.0",
  
  // 图结构
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
      "target": "node_1",
      "condition": null
    }
  ],
  
  // 配置
  "variables": [
    {"name": "ticker", "type": "string", "default": ""}
  ],
  "settings": {
    "timeout": 300,
    "retry_count": 3
  },
  
  // 元数据
  "is_template": false,
  "is_active": true,
  "license_tier": "free",
  "created_by": "user_001",
  "created_at": ISODate("2025-12-07T10:00:00Z"),
  "updated_at": ISODate("2025-12-07T10:00:00Z")
}
```

### workflow_executions 集合

```javascript
{
  "_id": ObjectId("..."),
  "id": "exec_001",
  "workflow_id": "wf_001",
  "workflow_version": "1.0.0",
  
  // 输入
  "input": {
    "ticker": "AAPL",
    "date": "2025-12-07"
  },
  
  // 执行状态
  "status": "completed",  // pending, running, completed, failed, cancelled
  "started_at": ISODate("2025-12-07T10:00:00Z"),
  "completed_at": ISODate("2025-12-07T10:02:00Z"),
  "duration_seconds": 120,
  
  // 节点执行记录
  "node_executions": [
    {
      "node_id": "node_1",
      "agent_id": "market_analyst",
      "status": "completed",
      "started_at": ISODate("..."),
      "completed_at": ISODate("..."),
      "output": "市场分析报告...",
      "error": null,
      "llm_usage": {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "total_tokens": 1500
      }
    }
  ],
  
  // 最终结果
  "result": {
    "decision": "buy",
    "confidence": 0.85,
    "reports": {...}
  },
  
  // 元数据
  "user_id": "user_001",
  "created_at": ISODate("2025-12-07T10:00:00Z")
}
```

### prompts 集合

```javascript
{
  "_id": ObjectId("..."),
  "id": "prompt_001",
  "agent_id": "market_analyst",
  "name": "市场分析师提示词",
  "description": "用于市场分析的系统提示词",
  
  // 内容
  "content": "你是一个专业的市场分析师...",
  "variables": ["company", "date", "market_type"],
  
  // 版本控制
  "version": 3,
  "versions": [
    {
      "version": 1,
      "content": "...",
      "created_at": ISODate("..."),
      "note": "初始版本"
    }
  ],
  
  // 元数据
  "is_system": true,  // 系统内置 vs 用户自定义
  "created_by": "system",
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### licenses 集合

```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user_001",
  "license_key": "XXXX-XXXX-XXXX-XXXX",
  "tier": "pro",  // free, basic, pro, enterprise
  
  // 有效期
  "activated_at": ISODate("2025-01-01T00:00:00Z"),
  "expires_at": ISODate("2026-01-01T00:00:00Z"),
  
  // 功能配置
  "features": {
    "max_workflows": -1,
    "max_custom_workflows": -1,
    "max_agents": 10,
    "max_concurrent": 10,
    "custom_prompts": true,
    "api_calls_per_day": 5000,
    "history_retention_days": 365
  },
  
  // 使用统计
  "usage": {
    "workflows_count": 5,
    "api_calls_today": 120,
    "api_calls_date": "2025-12-07"
  },
  
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

---

## 📊 索引设计

```javascript
// workflows
db.workflows.createIndex({ "id": 1 }, { unique: true })
db.workflows.createIndex({ "created_by": 1 })
db.workflows.createIndex({ "is_template": 1 })
db.workflows.createIndex({ "license_tier": 1 })

// workflow_executions
db.workflow_executions.createIndex({ "id": 1 }, { unique: true })
db.workflow_executions.createIndex({ "workflow_id": 1 })
db.workflow_executions.createIndex({ "user_id": 1, "created_at": -1 })
db.workflow_executions.createIndex({ "status": 1 })

// prompts
db.prompts.createIndex({ "id": 1 }, { unique: true })
db.prompts.createIndex({ "agent_id": 1 })

// licenses
db.licenses.createIndex({ "user_id": 1 }, { unique: true })
db.licenses.createIndex({ "license_key": 1 }, { unique: true })
```

---

## 🔄 状态机

### 工作流执行状态

```
                    ┌──────────┐
                    │ pending  │
                    └────┬─────┘
                         │ start
                         ▼
                    ┌──────────┐
         ┌─────────│ running  │─────────┐
         │         └────┬─────┘         │
         │ cancel       │ complete      │ error
         ▼              ▼               ▼
    ┌──────────┐  ┌──────────┐   ┌──────────┐
    │cancelled │  │completed │   │  failed  │
    └──────────┘  └──────────┘   └──────────┘
```

---

## 📝 Pydantic 模型

详见各模块设计文档中的数据模型定义：
- [03-workflow-engine.md](./03-workflow-engine.md) - WorkflowDefinition
- [05-agent-system.md](./05-agent-system.md) - AgentMetadata, AgentConfig
- [04-unified-llm.md](./04-unified-llm.md) - LLMConfig, LLMResponse

