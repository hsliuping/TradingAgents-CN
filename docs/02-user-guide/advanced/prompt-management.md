# 提示词模板系统使用指南

## 概述

提示词模板系统v1.0.1是一个完整的提示词管理解决方案，支持：

- **系统模板**：只读的示例模板，由系统维护
- **用户模板**：用户基于系统模板创建的自定义版本
- **分析偏好**：激进/中性/保守三种分析风格
- **版本管理**：完整的历史记录和版本对比
- **草稿/启用**：支持草稿保存和正式启用

## 快速开始

### 1. 初始化系统模板

```bash
python scripts/init_system_templates.py
```

这将创建31个系统模板（13个Agent × 3种偏好类型）。

### 2. API端点

#### 模板管理

```bash
# 创建用户模板（基于系统模板）
POST /api/v1/templates
{
  "agent_type": "analysts",
  "agent_name": "market_analyst",
  "template_name": "My Market Analysis",
  "preference_type": "aggressive",
  "content": {
    "system_prompt": "...",
    "tool_guidance": "...",
    "analysis_requirements": "..."
  },
  "status": "draft"
}

# 获取模板
GET /api/v1/templates/{template_id}

# 更新模板
PUT /api/v1/templates/{template_id}

# 获取Agent的所有模板
GET /api/v1/templates/agent/{agent_type}/{agent_name}
```

#### 分析偏好

```bash
# 创建偏好
POST /api/v1/preferences?user_id=user123
{
  "preference_type": "aggressive",
  "risk_level": 0.8,
  "confidence_threshold": 0.6,
  "position_size_multiplier": 1.5,
  "decision_speed": "fast"
}

# 获取用户偏好
GET /api/v1/preferences/user/{user_id}

# 更新偏好
PUT /api/v1/preferences/{preference_id}
```

#### 用户配置

```bash
# 创建用户配置
POST /api/v1/user-template-configs?user_id=user123
{
  "agent_type": "analysts",
  "agent_name": "market_analyst",
  "template_id": "template_id",
  "preference_id": "preference_id",
  "is_active": true
}

# 获取活跃配置
GET /api/v1/user-template-configs/active?user_id=user123&agent_type=analysts&agent_name=market_analyst
```

#### 历史记录

```bash
# 获取模板历史
GET /api/v1/template-history/template/{template_id}

# 对比两个版本
GET /api/v1/template-history/template/{template_id}/compare?version1=1&version2=2
```

## 数据模型

### PromptTemplate

```python
{
  "_id": ObjectId,
  "agent_type": str,           # analysts, researchers, debators, managers, trader
  "agent_name": str,           # 具体Agent名称
  "template_name": str,        # 模板名称
  "preference_type": str,      # aggressive, neutral, conservative
  "content": {
    "system_prompt": str,
    "tool_guidance": str,
    "analysis_requirements": str,
    "output_format": str,
    "constraints": str
  },
  "is_system": bool,           # 是否为系统模板
  "created_by": ObjectId,      # 创建者（系统模板为null）
  "base_template_id": ObjectId, # 基础模板ID
  "base_version": int,         # 基础模板版本
  "status": str,               # draft, active
  "version": int,
  "created_at": datetime,
  "updated_at": datetime
}
```

### AnalysisPreference

```python
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "preference_type": str,      # aggressive, neutral, conservative
  "risk_level": float,         # 0.0-1.0
  "confidence_threshold": float,
  "position_size_multiplier": float,
  "decision_speed": str,       # fast, normal, slow
  "is_default": bool,
  "created_at": datetime,
  "updated_at": datetime
}
```

## 配额限制

- **Active模板**：每个(user, agent, preference)组合最多1个
- **Draft模板**：每个(user, agent, preference)组合最多5个
- **模板长度**：总长度不超过64KB

## 生效优先级

1. 用户有自定义模板 → 使用用户模板
2. 用户没有自定义模板 → 使用系统默认模板
3. 模板状态必须为 `active` 才能被使用

## 测试

```bash
pytest tests/test_prompt_template_system.py -v
```

## 更多信息

详见 `docs/design/v1.0.1/` 目录下的设计文档。

