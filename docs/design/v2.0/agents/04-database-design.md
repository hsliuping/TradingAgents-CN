# 数据库设计 (Database Design)

## 概述

本文档描述插件化智能体架构的数据库设计，包括工具配置、Agent 配置、Workflow 配置以及各层之间的绑定关系。

## 数据库选择

- **MongoDB**：用于存储配置数据（灵活的 Schema）
- **现有集成**：复用项目已有的 MongoDB 连接

## 集合设计

### 1. tool_configs - 工具配置

存储工具的运行时配置和状态。

```javascript
// Collection: tool_configs
{
    "_id": ObjectId("..."),
    "tool_id": "get_stock_market_data_unified",  // 工具唯一标识
    "name": "统一股票市场数据",                    // 显示名称
    "description": "获取股票的历史K线、实时价格等市场数据",
    "category": "market",                         // 分类
    "version": "1.0.0",
    
    // 状态
    "enabled": true,                              // 是否启用
    "priority": 1,                                // 同类工具优先级
    
    // 运行时配置
    "config": {
        "timeout": 30,                            // 超时时间（秒）
        "retry_count": 3,                         // 重试次数
        "cache_ttl": 300                          // 缓存时间（秒）
    },
    
    // 参数定义 (JSON Schema)
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "股票代码"},
            "start_date": {"type": "string", "format": "date"},
            "end_date": {"type": "string", "format": "date"}
        },
        "required": ["ticker"]
    },
    
    // 元数据
    "tags": ["stock", "market", "price"],
    "author": "system",
    "is_builtin": true,                          // 是否内置
    
    // 时间戳
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 索引
db.tool_configs.createIndex({ "tool_id": 1 }, { unique: true })
db.tool_configs.createIndex({ "category": 1 })
db.tool_configs.createIndex({ "enabled": 1 })
db.tool_configs.createIndex({ "tags": 1 })
```

### 2. agent_configs - Agent 配置

存储 Agent 的运行时配置和状态。

```javascript
// Collection: agent_configs
{
    "_id": ObjectId("..."),
    "agent_id": "market_analyst",                // Agent 唯一标识
    "name": "市场分析师",                         // 显示名称
    "description": "分析股票市场数据、价格走势、技术指标",
    "category": "analysts",                      // 分类
    "version": "1.0.0",
    
    // 状态
    "enabled": true,
    
    // 提示词配置
    "prompt_template_type": "analysts",
    "prompt_template_name": "market_analyst",
    
    // 执行配置
    "config": {
        "max_iterations": 3,                     // 最大迭代次数
        "timeout": 120,                          // 超时时间（秒）
        "temperature": 0.7                       // LLM 温度
    },
    
    // 默认工具列表（可被绑定表覆盖）
    "default_tools": [
        "get_stock_market_data_unified"
    ],
    
    // 必需工具（缺失则报错）
    "required_tools": [
        "get_stock_market_data_unified"
    ],
    
    // 元数据
    "tags": ["market", "technical", "price"],
    "author": "system",
    "is_builtin": true,
    
    // 时间戳
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 索引
db.agent_configs.createIndex({ "agent_id": 1 }, { unique: true })
db.agent_configs.createIndex({ "category": 1 })
db.agent_configs.createIndex({ "enabled": 1 })
```

### 3. workflow_definitions - 工作流定义

存储工作流的完整定义。

```javascript
// Collection: workflow_definitions
{
    "_id": ObjectId("..."),
    "workflow_id": "position_analysis",          // 工作流唯一标识
    "name": "持仓分析工作流",
    "description": "对持仓股票进行多维度分析",
    "category": "position",
    "version": "1.0.0",
    
    // 状态
    "enabled": true,
    "is_builtin": true,
    
    // 执行模式
    "execution_mode": "parallel",                // sequential/parallel/conditional
    
    // 节点定义（用于可视化）
    "nodes": [
        {
            "id": "start",
            "type": "start",
            "position": {"x": 100, "y": 100}
        },
        {
            "id": "pa_technical_analyst",
            "type": "agent",
            "agent_id": "pa_technical_analyst",
            "position": {"x": 300, "y": 50}
        },
        {
            "id": "pa_fundamental_analyst",
            "type": "agent", 
            "agent_id": "pa_fundamental_analyst",
            "position": {"x": 300, "y": 150}
        },
        {
            "id": "pa_risk_assessor",
            "type": "agent",
            "agent_id": "pa_risk_assessor",
            "position": {"x": 300, "y": 250}
        },
        {
            "id": "pa_action_advisor",
            "type": "agent",
            "agent_id": "pa_action_advisor",
            "position": {"x": 500, "y": 150}
        },
        {
            "id": "end",
            "type": "end",
            "position": {"x": 700, "y": 150}
        }
    ],
    
    // 边定义
    "edges": [
        {"id": "e1", "source": "start", "target": "pa_technical_analyst"},
        {"id": "e2", "source": "start", "target": "pa_fundamental_analyst"},
        {"id": "e3", "source": "start", "target": "pa_risk_assessor"},
        {"id": "e4", "source": "pa_technical_analyst", "target": "pa_action_advisor"},
        {"id": "e5", "source": "pa_fundamental_analyst", "target": "pa_action_advisor"},
        {"id": "e6", "source": "pa_risk_assessor", "target": "pa_action_advisor"},
        {"id": "e7", "source": "pa_action_advisor", "target": "end"}
    ],
    
    // 并行组
    "parallel_groups": [
        ["pa_technical_analyst", "pa_fundamental_analyst", "pa_risk_assessor"]
    ],
    
    // 元数据
    "tags": ["position", "analysis"],
    "config": {},
    
    // 时间戳
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 索引
db.workflow_definitions.createIndex({ "workflow_id": 1 }, { unique: true })
db.workflow_definitions.createIndex({ "category": 1 })
db.workflow_definitions.createIndex({ "enabled": 1 })
```

### 4. tool_agent_bindings - 工具-Agent 绑定

存储工具与 Agent 的绑定关系。

```javascript
// Collection: tool_agent_bindings
{
    "_id": ObjectId("..."),
    "agent_id": "market_analyst",                // Agent 标识
    "tool_id": "get_stock_market_data_unified",  // 工具标识

    // 绑定配置
    "priority": 1,                               // 优先级（数字越小越优先）
    "enabled": true,                             // 是否启用

    // 工具特定配置（覆盖工具默认配置）
    "config": {
        "timeout": 60                            // 覆盖默认超时
    },

    // 时间戳
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 索引
db.tool_agent_bindings.createIndex({ "agent_id": 1, "tool_id": 1 }, { unique: true })
db.tool_agent_bindings.createIndex({ "agent_id": 1, "enabled": 1, "priority": 1 })
db.tool_agent_bindings.createIndex({ "tool_id": 1 })
```

### 5. agent_workflow_bindings - Agent-Workflow 绑定

存储 Agent 与 Workflow 的绑定关系。

```javascript
// Collection: agent_workflow_bindings
{
    "_id": ObjectId("..."),
    "workflow_id": "position_analysis",          // 工作流标识
    "agent_id": "pa_technical_analyst",          // Agent 标识

    // 执行配置
    "order": 1,                                  // 执行顺序
    "parallel_group": "analysis",                // 并行组名（null 表示串行）
    "enabled": true,

    // 工具覆盖（在此工作流中使用特定工具）
    "tool_overrides": [
        "get_stock_market_data_unified",
        "get_technical_indicators"
    ],

    // Agent 特定配置（覆盖 Agent 默认配置）
    "config": {
        "max_iterations": 2
    },

    // 时间戳
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 索引
db.agent_workflow_bindings.createIndex({ "workflow_id": 1, "agent_id": 1 }, { unique: true })
db.agent_workflow_bindings.createIndex({ "workflow_id": 1, "enabled": 1, "order": 1 })
db.agent_workflow_bindings.createIndex({ "agent_id": 1 })
```

## 关系图

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  tool_configs   │     │ tool_agent_bindings │     │   agent_configs     │
│                 │     │                     │     │                     │
│  tool_id (PK)   │◄────│  tool_id (FK)       │     │  agent_id (PK)      │
│  name           │     │  agent_id (FK)      │────►│  name               │
│  category       │     │  priority           │     │  category           │
│  enabled        │     │  enabled            │     │  enabled            │
│  config         │     │  config             │     │  default_tools      │
└─────────────────┘     └─────────────────────┘     └─────────────────────┘
                                                              │
                                                              │
                        ┌─────────────────────┐               │
                        │agent_workflow_      │               │
                        │    bindings         │               │
                        │                     │               │
                        │  workflow_id (FK)   │               │
                        │  agent_id (FK)      │───────────────┘
                        │  order              │
                        │  parallel_group     │
                        │  tool_overrides     │
                        └─────────────────────┘
                                  │
                                  │
                        ┌─────────────────────┐
                        │workflow_definitions │
                        │                     │
                        │  workflow_id (PK)   │
                        │  name               │
                        │  category           │
                        │  nodes              │
                        │  edges              │
                        └─────────────────────┘
```

## 配置优先级

工具配置的加载优先级（从高到低）：

1. **agent_workflow_bindings.tool_overrides** - 工作流级别的工具覆盖
2. **tool_agent_bindings** - Agent 级别的工具绑定
3. **agent_configs.default_tools** - Agent 默认工具
4. **tool_configs** - 工具默认配置

```python
def get_tools_for_agent(workflow_id: str, agent_id: str) -> List[str]:
    """获取 Agent 在特定工作流中的工具列表"""

    # 1. 检查工作流级别覆盖
    workflow_binding = db.agent_workflow_bindings.find_one({
        "workflow_id": workflow_id,
        "agent_id": agent_id,
        "enabled": True
    })
    if workflow_binding and workflow_binding.get("tool_overrides"):
        return workflow_binding["tool_overrides"]

    # 2. 检查 Agent 级别绑定
    agent_bindings = db.tool_agent_bindings.find({
        "agent_id": agent_id,
        "enabled": True
    }).sort("priority", 1)
    if agent_bindings.count() > 0:
        return [b["tool_id"] for b in agent_bindings]

    # 3. 使用 Agent 默认工具
    agent_config = db.agent_configs.find_one({"agent_id": agent_id})
    if agent_config:
        return agent_config.get("default_tools", [])

    return []
```

## 初始化脚本

```python
# scripts/init_plugin_architecture_db.py
"""
初始化插件化架构数据库集合和索引
"""

from pymongo import MongoClient, ASCENDING
from datetime import datetime

def init_collections(db):
    """初始化集合和索引"""

    # 1. tool_configs
    db.tool_configs.create_index([("tool_id", ASCENDING)], unique=True)
    db.tool_configs.create_index([("category", ASCENDING)])
    db.tool_configs.create_index([("enabled", ASCENDING)])
    db.tool_configs.create_index([("tags", ASCENDING)])

    # 2. agent_configs
    db.agent_configs.create_index([("agent_id", ASCENDING)], unique=True)
    db.agent_configs.create_index([("category", ASCENDING)])
    db.agent_configs.create_index([("enabled", ASCENDING)])

    # 3. workflow_definitions
    db.workflow_definitions.create_index([("workflow_id", ASCENDING)], unique=True)
    db.workflow_definitions.create_index([("category", ASCENDING)])
    db.workflow_definitions.create_index([("enabled", ASCENDING)])

    # 4. tool_agent_bindings
    db.tool_agent_bindings.create_index(
        [("agent_id", ASCENDING), ("tool_id", ASCENDING)],
        unique=True
    )
    db.tool_agent_bindings.create_index([
        ("agent_id", ASCENDING),
        ("enabled", ASCENDING),
        ("priority", ASCENDING)
    ])

    # 5. agent_workflow_bindings
    db.agent_workflow_bindings.create_index(
        [("workflow_id", ASCENDING), ("agent_id", ASCENDING)],
        unique=True
    )
    db.agent_workflow_bindings.create_index([
        ("workflow_id", ASCENDING),
        ("enabled", ASCENDING),
        ("order", ASCENDING)
    ])

    print("✅ 集合索引初始化完成")

def seed_builtin_tools(db):
    """导入内置工具配置"""
    builtin_tools = [
        {
            "tool_id": "get_stock_market_data_unified",
            "name": "统一股票市场数据",
            "description": "获取股票的历史K线、实时价格等市场数据",
            "category": "market",
            "enabled": True,
            "priority": 1,
            "is_builtin": True,
            "tags": ["stock", "market", "price", "kline"]
        },
        # ... 更多工具
    ]

    for tool in builtin_tools:
        tool["created_at"] = datetime.utcnow()
        tool["updated_at"] = datetime.utcnow()
        db.tool_configs.update_one(
            {"tool_id": tool["tool_id"]},
            {"$set": tool},
            upsert=True
        )

    print(f"✅ 导入 {len(builtin_tools)} 个内置工具")
```

## 总结

数据库设计的核心是：

1. **5个集合**：tool_configs, agent_configs, workflow_definitions, tool_agent_bindings, agent_workflow_bindings
2. **绑定分离**：工具-Agent 和 Agent-Workflow 绑定独立存储
3. **配置覆盖**：支持多级配置覆盖（工作流 > Agent > 默认）
4. **索引优化**：为常用查询建立复合索引
5. **向后兼容**：内置配置可被数据库配置覆盖

