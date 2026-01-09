# v2.1 需求：工作流上下文配置系统

## 📋 需求概述

**版本**: v2.1  
**优先级**: 高  
**类型**: 功能增强  
**创建日期**: 2026-01-09

---

## 🎯 需求背景

### 当前问题

1. **Agent 配置是全局的**：
   - 同一个 Agent 在所有工作流中使用相同的工具和提示词
   - 无法根据工作流上下文调整 Agent 行为

2. **提示词模板使用 `agent_name` 而非 `agent_id`**：
   - `prompt_templates` 集合使用 `agent_type` + `agent_name` 查询
   - 与代码中的 `agent_id` 不一致（如 `market_analyst` vs `market_analyst_v2`）
   - 需要手动映射，容易出错

3. **缺乏工作流级别的配置能力**：
   - 无法为同一 Agent 在不同工作流中配置不同的工具
   - 无法为同一 Agent 在不同工作流中使用不同的提示词
   - 无法为同一 Agent 在不同工作流中设置不同的执行参数

### 典型场景

**场景 1：市场分析师在不同工作流中的角色**

```
工作流 A：股票分析工作流
- market_analyst_v2 需要工具：[get_stock_data, get_technical_indicators]
- 使用激进提示词（temperature: 0.9）
- 关注短线交易机会

工作流 B：交易复盘工作流
- market_analyst_v2 需要工具：[get_trade_records, get_market_snapshot]
- 使用保守提示词（temperature: 0.3）
- 关注风险控制
```

**场景 2：同一工作流中多次使用同一 Agent**

```
工作流 C：多维度分析工作流
- 节点 1：market_analyst_v2（技术分析）
  - 工具：[get_technical_indicators]
  - 提示词：专注技术指标
  
- 节点 2：market_analyst_v2（基本面分析）
  - 工具：[get_fundamentals]
  - 提示词：专注基本面
```

---

## 🎯 需求目标

1. **统一使用 `agent_id`**：
   - 所有集合统一使用 `agent_id` 作为主键
   - 消除 `agent_name` 和 `agent_id` 的不一致

2. **支持工作流级别配置**：
   - 同一 Agent 在不同工作流中可以使用不同的工具
   - 同一 Agent 在不同工作流中可以使用不同的提示词
   - 同一 Agent 在不同工作流中可以使用不同的执行参数

3. **支持节点级别配置**：
   - 同一工作流中多次使用同一 Agent 时，每个节点可以有独立配置

4. **保持向后兼容**：
   - 现有全局配置继续有效
   - 逐步迁移到新配置系统

---

## 📊 数据库设计

### 1. `tool_agent_bindings` 集合改进

**添加字段**：

```javascript
{
    "_id": ObjectId("..."),
    "workflow_id": "stock_analysis_workflow",  // 🆕 工作流 ID（null 表示全局）
    "node_id": "market_node",                  // 🆕 节点 ID（null 表示工作流级别）
    "agent_id": "market_analyst_v2",           // Agent ID
    "tool_id": "get_stock_data",               // 工具 ID
    "is_active": true,                         // 是否激活
    "priority": 1,                             // 优先级
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z"
}
```

**索引**：

```javascript
db.tool_agent_bindings.createIndex({
    "workflow_id": 1,
    "node_id": 1,
    "agent_id": 1,
    "is_active": 1
})
```

**查询优先级**：

```
1. workflow_id + node_id + agent_id（节点级别）
2. workflow_id + agent_id（工作流级别）
3. agent_id（全局级别，workflow_id = null）
```

---

### 2. `prompt_templates` 集合改进

**字段变更**：

```javascript
{
    "_id": ObjectId("..."),
    "agent_id": "market_analyst_v2",           // 🆕 使用 agent_id（主键）
    "agent_type": "analysts",                  // 保留（用于分类和向后兼容）
    "agent_name": "market_analyst",            // 保留（用于向后兼容）
    "template_name": "aggressive",             // 模板名称
    "preference_type": "aggressive",           // 偏好类型
    "content": {
        "system_prompt": "...",
        "user_prompt": "...",
        "tool_guidance": "...",
        "analysis_requirements": "...",
        "output_format": "...",
        "constraints": "..."
    },
    "is_system": true,                         // 是否为系统模板
    "created_by": null,                        // 创建者（系统模板为 null）
    "status": "active",                        // 状态
    "version": 1,                              // 版本号
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z"
}
```

**索引**：

```javascript
db.prompt_templates.createIndex({
    "agent_id": 1,
    "template_name": 1,
    "status": 1
})

// 保留旧索引用于向后兼容
db.prompt_templates.createIndex({
    "agent_type": 1,
    "agent_name": 1,
    "status": 1
})
```

---

### 3. `workflow_agent_bindings` 集合（新增）

**用途**：存储工作流级别的 Agent 配置覆盖

**字段**：

```javascript
{
    "_id": ObjectId("..."),
    "workflow_id": "stock_analysis_workflow",  // 工作流 ID
    "agent_id": "market_analyst_v2",           // Agent ID
    "node_id": "market_node",                  // 节点 ID（用于区分同一工作流中多次使用）
    "order": 10,                               // 执行顺序
    "is_active": true,                         // 是否激活
    
    // 配置覆盖
    "config_override": {
        "temperature": 0.9,                    // LLM 温度
        "max_iterations": 5,                   // 最大迭代次数
        "timeout": 180                         // 超时时间
    },
    
    // 提示词模板覆盖
    "prompt_template_id": ObjectId("..."),     // 指向 prompt_templates._id
    
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z"
}
```

**索引**：

```javascript
db.workflow_agent_bindings.createIndex({
    "workflow_id": 1,
    "agent_id": 1,
    "node_id": 1,
    "is_active": 1
})
```

---

### 4. `user_template_configs` 集合改进

**添加字段**：

```javascript
{
    "_id": ObjectId("..."),
    "user_id": ObjectId("..."),                // 用户 ID
    "workflow_id": "stock_analysis_workflow",  // 🆕 工作流 ID（null 表示全局）
    "node_id": "market_node",                  // 🆕 节点 ID（null 表示工作流级别）
    "agent_id": "market_analyst_v2",           // 🆕 使用 agent_id
    "agent_type": "analysts",                  // 保留（向后兼容）
    "agent_name": "market_analyst",            // 保留（向后兼容）
    "template_id": ObjectId("..."),            // 模板 ID
    "preference_id": "aggressive",             // 偏好 ID
    "is_active": true,                         // 是否激活
    "created_at": "2026-01-09T12:00:00Z",
    "updated_at": "2026-01-09T12:00:00Z"
}
```

**索引**：

```javascript
db.user_template_configs.createIndex({
    "user_id": 1,
    "workflow_id": 1,
    "node_id": 1,
    "agent_id": 1,
    "is_active": 1
})
```

**查询优先级**：

```
1. user_id + workflow_id + node_id + agent_id（用户节点级别）
2. user_id + workflow_id + agent_id（用户工作流级别）
3. user_id + agent_id（用户全局级别）
4. workflow_id + agent_id（工作流级别）
5. agent_id（全局级别）
```

---

## 🔧 代码改动

### 1. `BindingManager` 改进

**文件**: `core/config/binding_manager.py`

**新增方法**：

```python
def get_tools_for_agent(
    self,
    agent_id: str,
    workflow_id: Optional[str] = None,
    node_id: Optional[str] = None
) -> List[str]:
    """
    获取 Agent 绑定的工具列表

    Args:
        agent_id: Agent ID
        workflow_id: 工作流 ID（可选）
        node_id: 节点 ID（可选）

    Returns:
        工具ID列表

    查询优先级：
        1. workflow_id + node_id + agent_id（节点级别）
        2. workflow_id + agent_id（工作流级别）
        3. agent_id（全局级别）
    """
    # 构建查询条件（优先级从高到低）
    queries = []

    # 1. 节点级别
    if workflow_id and node_id:
        queries.append({
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": node_id,
            "is_active": {"$ne": False}
        })

    # 2. 工作流级别
    if workflow_id:
        queries.append({
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": None,
            "is_active": {"$ne": False}
        })

    # 3. 全局级别
    queries.append({
        "workflow_id": None,
        "agent_id": agent_id,
        "is_active": {"$ne": False}
    })

    # 按优先级查询
    for query in queries:
        bindings = list(self._db.tool_agent_bindings.find(
            query,
            sort=[("priority", -1)]
        ))
        if bindings:
            tool_ids = [b["tool_id"] for b in bindings]
            logger.info(f"✅ 找到工具绑定: {query} -> {tool_ids}")
            return tool_ids

    logger.warning(f"⚠️ 未找到工具绑定: {agent_id}")
    return []

def get_workflow_agent_config(
    self,
    workflow_id: str,
    agent_id: str,
    node_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    获取工作流级别的 Agent 配置

    Args:
        workflow_id: 工作流 ID
        agent_id: Agent ID
        node_id: 节点 ID（可选）

    Returns:
        配置字典，包含 config_override 和 prompt_template_id
    """
    query = {
        "workflow_id": workflow_id,
        "agent_id": agent_id,
        "is_active": True
    }

    if node_id:
        query["node_id"] = node_id

    binding = self._db.workflow_agent_bindings.find_one(query)

    if binding:
        return {
            "config_override": binding.get("config_override", {}),
            "prompt_template_id": binding.get("prompt_template_id")
        }

    return None
```

---

### 2. `GraphBuilder` 改进

**文件**: `core/workflow/builder.py`

**改动方法**: `_create_agent_node()`

```python
def _create_agent_node(self, node: NodeDefinition) -> Callable:
    """创建智能体节点"""
    agent_id = node.agent_id
    node_id = node.id
    workflow_id = self.workflow_id  # 从工作流定义获取

    # 🔥 从数据库加载工作流级别的工具绑定
    tool_ids = self.binding_manager.get_tools_for_agent(
        agent_id=agent_id,
        workflow_id=workflow_id,
        node_id=node_id
    )

    # 🔥 从数据库加载工作流级别的配置
    workflow_config = self.binding_manager.get_workflow_agent_config(
        workflow_id=workflow_id,
        agent_id=agent_id,
        node_id=node_id
    )

    config_override = {}
    prompt_template_id = None

    if workflow_config:
        config_override = workflow_config.get("config_override", {})
        prompt_template_id = workflow_config.get("prompt_template_id")

    # 合并配置（优先级：节点配置 > 工作流配置 > 全局配置）
    config = AgentConfig(**{
        **self.default_config.model_dump(),
        **config_override,
        **node.config
    })

    # 创建 Agent
    agent = self.factory.create(
        agent_id=agent_id,
        llm=llm,
        tool_ids=tool_ids,
        config_overrides=config.model_dump(),
        prompt_template_id=prompt_template_id
    )

    return agent
```

---

### 3. 提示词查询改进

**文件**: `tradingagents/utils/template_client.py`

**新增函数**：

```python
def get_agent_prompt_v2(
    agent_id: str,
    variables: Dict[str, str],
    workflow_id: Optional[str] = None,
    node_id: Optional[str] = None,
    user_id: Optional[str] = None,
    preference_id: Optional[str] = None,
    fallback_prompt: Optional[str] = None
) -> str:
    """
    获取 Agent 提示词（v2.1 版本，支持工作流上下文）

    Args:
        agent_id: Agent ID
        variables: 模板变量字典
        workflow_id: 工作流 ID（可选）
        node_id: 节点 ID（可选）
        user_id: 用户 ID（可选）
        preference_id: 偏好 ID（可选）
        fallback_prompt: 降级提示词

    Returns:
        完整的提示词字符串

    查询优先级：
        1. 用户节点级别配置
        2. 用户工作流级别配置
        3. 用户全局配置
        4. 工作流节点级别配置
        5. 工作流级别配置
        6. Agent 全局配置
        7. 代码默认值
    """
    client = get_template_client()
    db = client.db

    template_id = None

    # 1. 用户节点级别配置
    if user_id and workflow_id and node_id:
        config = db.user_template_configs.find_one({
            "user_id": ObjectId(user_id),
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": node_id,
            "is_active": True
        })
        if config:
            template_id = config["template_id"]

    # 2. 用户工作流级别配置
    if not template_id and user_id and workflow_id:
        config = db.user_template_configs.find_one({
            "user_id": ObjectId(user_id),
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": None,
            "is_active": True
        })
        if config:
            template_id = config["template_id"]

    # 3. 用户全局配置
    if not template_id and user_id:
        config = db.user_template_configs.find_one({
            "user_id": ObjectId(user_id),
            "workflow_id": None,
            "agent_id": agent_id,
            "is_active": True
        })
        if config:
            template_id = config["template_id"]

    # 4. 工作流节点级别配置
    if not template_id and workflow_id and node_id:
        binding = db.workflow_agent_bindings.find_one({
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": node_id,
            "is_active": True
        })
        if binding and binding.get("prompt_template_id"):
            template_id = binding["prompt_template_id"]

    # 5. 工作流级别配置
    if not template_id and workflow_id:
        binding = db.workflow_agent_bindings.find_one({
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "node_id": None,
            "is_active": True
        })
        if binding and binding.get("prompt_template_id"):
            template_id = binding["prompt_template_id"]

    # 6. Agent 全局配置
    if not template_id:
        template = db.prompt_templates.find_one({
            "agent_id": agent_id,
            "is_system": True,
            "status": "active"
        })
        if template:
            template_id = template["_id"]

    # 7. 获取模板并渲染
    if template_id:
        template = db.prompt_templates.find_one({"_id": template_id})
        if template:
            formatted = client.format_template(template["content"], variables)
            return formatted.get("system_prompt", "") + "\n\n" + formatted.get("user_prompt", "")

    # 8. 降级：使用代码默认值
    return fallback_prompt or "请进行分析。"
```

---

## 📝 迁移方案

### 阶段 1：数据库迁移（向后兼容）

**目标**：为现有数据添加新字段，保持向后兼容

**脚本**: `scripts/migration/migrate_to_v2.1.py`

```python
"""
迁移到 v2.1：添加工作流上下文字段
"""
import asyncio
from app.core.database import init_database, get_mongo_db

async def migrate():
    await init_database()
    db = get_mongo_db()

    print("=" * 80)
    print("迁移到 v2.1：添加工作流上下文字段")
    print("=" * 80)

    # 1. tool_agent_bindings：添加 workflow_id 和 node_id
    print("\n1. 迁移 tool_agent_bindings 集合...")
    result = await db.tool_agent_bindings.update_many(
        {"workflow_id": {"$exists": False}},
        {"$set": {"workflow_id": None, "node_id": None}}
    )
    print(f"   ✅ 更新 {result.modified_count} 条记录")

    # 2. prompt_templates：添加 agent_id
    print("\n2. 迁移 prompt_templates 集合...")
    templates = await db.prompt_templates.find(
        {"agent_id": {"$exists": False}}
    ).to_list(length=None)

    for template in templates:
        # 从 agent_name 推断 agent_id
        agent_name = template.get("agent_name", "")
        agent_type = template.get("agent_type", "")

        # 简单映射规则（可根据实际情况调整）
        if agent_type == "analysts":
            agent_id = f"{agent_name}_v2"
        else:
            agent_id = agent_name

        await db.prompt_templates.update_one(
            {"_id": template["_id"]},
            {"$set": {"agent_id": agent_id}}
        )

    print(f"   ✅ 更新 {len(templates)} 条记录")

    # 3. user_template_configs：添加 workflow_id、node_id 和 agent_id
    print("\n3. 迁移 user_template_configs 集合...")
    result = await db.user_template_configs.update_many(
        {"workflow_id": {"$exists": False}},
        {"$set": {"workflow_id": None, "node_id": None}}
    )
    print(f"   ✅ 更新 {result.modified_count} 条记录")

    # 4. 创建新索引
    print("\n4. 创建新索引...")

    await db.tool_agent_bindings.create_index([
        ("workflow_id", 1),
        ("node_id", 1),
        ("agent_id", 1),
        ("is_active", 1)
    ])
    print("   ✅ tool_agent_bindings 索引已创建")

    await db.prompt_templates.create_index([
        ("agent_id", 1),
        ("template_name", 1),
        ("status", 1)
    ])
    print("   ✅ prompt_templates 索引已创建")

    await db.user_template_configs.create_index([
        ("user_id", 1),
        ("workflow_id", 1),
        ("node_id", 1),
        ("agent_id", 1),
        ("is_active", 1)
    ])
    print("   ✅ user_template_configs 索引已创建")

    print("\n✅ 迁移完成！")

if __name__ == "__main__":
    asyncio.run(migrate())
```

---

### 阶段 2：代码更新

**步骤**：

1. ✅ 更新 `BindingManager.get_tools_for_agent()` 方法
2. ✅ 新增 `BindingManager.get_workflow_agent_config()` 方法
3. ✅ 更新 `GraphBuilder._create_agent_node()` 方法
4. ✅ 新增 `get_agent_prompt_v2()` 函数
5. ✅ 更新所有 Agent 的 `_build_system_prompt()` 方法

---

### 阶段 3：前端支持

**新增功能**：

1. **工作流编辑器**：
   - 为每个节点配置工具绑定
   - 为每个节点选择提示词模板
   - 为每个节点设置执行参数

2. **Agent 配置页面**：
   - 显示全局配置
   - 显示工作流级别配置
   - 显示节点级别配置

---

## ✅ 验收标准

### 功能验收

- [ ] 同一 Agent 在不同工作流中可以使用不同的工具
- [ ] 同一 Agent 在不同工作流中可以使用不同的提示词
- [ ] 同一 Agent 在不同工作流中可以使用不同的执行参数
- [ ] 同一工作流中多次使用同一 Agent 时，每个节点可以有独立配置
- [ ] 配置查询遵循正确的优先级
- [ ] 向后兼容：现有全局配置继续有效

### 性能验收

- [ ] 配置查询性能不低于当前版本
- [ ] 缓存机制正常工作
- [ ] 数据库索引优化完成

### 文档验收

- [ ] API 文档更新
- [ ] 数据库设计文档更新
- [ ] 迁移指南完成
- [ ] 用户手册更新

---

## 📅 开发计划

### 里程碑 1：数据库设计和迁移（1 周）

- [ ] 完成数据库设计
- [ ] 编写迁移脚本
- [ ] 测试迁移脚本

### 里程碑 2：后端实现（2 周）

- [ ] 更新 `BindingManager`
- [ ] 更新 `GraphBuilder`
- [ ] 更新提示词查询逻辑
- [ ] 编写单元测试

### 里程碑 3：前端实现（2 周）

- [ ] 工作流编辑器支持节点配置
- [ ] Agent 配置页面支持多级配置
- [ ] 用户界面优化

### 里程碑 4：测试和文档（1 周）

- [ ] 集成测试
- [ ] 性能测试
- [ ] 文档编写
- [ ] 用户验收测试

---

## 🔗 相关文档

- [v2.0 架构设计](../v2.0/05-agent-system.md)
- [数据库设计](../v2.0/agents/04-database-design.md)
- [工作流系统](../v2.0/03-workflow-system.md)

---

**创建日期**: 2026-01-09
**最后更新**: 2026-01-09
**负责人**: TradingAgents-CN Pro Team

