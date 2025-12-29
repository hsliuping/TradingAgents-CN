# TradingAgentsCN 项目开发规则

> 本文档定义了项目的架构原则、配置规范和开发约定，供开发者和 Cursor AI 参考使用。
> 
> **注意**: 同时参考根目录下的 `.cursorrules` 文件，该文件包含 Cursor AI 的快速参考规则。

## 📁 目录结构说明

### 核心目录职责

1. **`core/`** - v2.0 核心功能实现目录
   - 工作流引擎 (`workflow/`)
   - 智能体系统 (`agents/`)
   - 统一 LLM 客户端 (`llm/`)
   - 配置管理器 (`config/`)
   - 状态管理 (`state/`)
   - 工具系统 (`tools/`)
   - 提示词管理 (`prompts/`)
   - 兼容层 (`compat/`)
   - **许可证**: 专有许可证（商业版）

2. **`app/`** - 后端 API 实现目录
   - FastAPI 路由 (`routers/`)
   - API 服务层 (`services/`)
   - 数据模型和验证 (`models/`, `schemas/`)
   - 中间件 (`middleware/`)
   - 数据库连接 (`core/`)
   - **许可证**: 专有许可证（商业版）

3. **`frontend/`** - 前端实现目录
   - Vue.js 应用
   - 工作流可视化编辑器
   - 用户界面组件
   - **许可证**: 专有许可证（商业版）

4. **`tradingagents/`** - 旧版分析引擎实现目录
   - v1.x 代码
   - 基础智能体实现
   - 数据流处理
   - 基础工具定义
   - **许可证**: Apache 2.0（开源版）

## 🔧 配置存储原则

### 配置存储位置

**优先顺序**: 数据库配置 > .env配置 > 代码默认值

#### 1. 数据库配置（MongoDB）- **主要存储位置**

以下配置**必须**存储在 MongoDB 数据库中：

- **工作流配置** (`workflows`, `workflow_definitions` 集合)
- **Agent 配置** (`agent_configs` 集合)
- **工具配置** (`tool_configs` 集合)
- **提示词配置** (`prompt_templates` 集合)
- **绑定关系**:
  - `tool_agent_bindings` - 工具与Agent的绑定关系
  - `agent_workflow_bindings` - Agent与工作流的绑定关系
  - `agent_io_definitions` - Agent的输入输出定义
- **系统配置** (`system_configs` 集合)
- **用户配置** (用户相关的个性化设置)

#### 2. .env 文件配置 - **仅用于基础设施**

`.env` 文件**仅**用于存储以下基础配置：

- **MongoDB 连接参数**:
  - `MONGODB_HOST`, `MONGODB_PORT`
  - `MONGODB_USERNAME`, `MONGODB_PASSWORD`
  - `MONGODB_DATABASE`, `MONGODB_AUTH_SOURCE`
  - `MONGODB_CONNECTION_STRING` (完整连接字符串)
- **系统级基础配置**:
  - 服务器地址和端口 (`HOST`, `PORT`)
  - 调试模式 (`DEBUG`)
  - API 密钥（如果需要环境变量注入）
- **其他基础设施配置**:
  - Redis 连接参数
  - 日志配置路径
  - Docker 相关配置

### 配置读取优先级

在实现配置读取逻辑时，必须遵循以下优先级：

```
1. 首先从 MongoDB 数据库读取配置
2. 如果数据库中没有，再从 .env 文件读取
3. 最后使用代码中的默认值
```

### 配置管理器

v2.0 架构中的配置管理器位于 `core/config/` 目录：

- **`binding_manager.py`** - 统一绑定管理（工具↔Agent↔工作流）
- **`tool_config_manager.py`** - 工具配置管理
- **`agent_config_manager.py`** - Agent配置管理
- **`workflow_config_manager.py`** - 工作流配置管理

所有配置管理器都遵循：
- **单例模式** - 确保全局唯一实例
- **缓存机制** - 5分钟TTL缓存，提升性能
- **优先级原则** - 数据库配置 > 代码默认配置

## 🏗️ v2.0 架构核心要点

### 配置化设计目标

v2.0 的一个**核心目标**是将以下内容完全配置化，为插件化架构打下基础：

1. **工作流（Workflows）** - 可通过可视化编辑器定义
2. **智能体（Agents）** - 动态注册和配置
3. **工具（Tools）** - 独立定义，动态绑定
4. **提示词（Prompts）** - 存储在数据库中，支持版本管理

### 插件化基础

当前配置化架构为后续插件化提供基础：

- ✅ 动态加载工具、Agent和工作流
- ✅ 无需修改代码即可调整配置
- ✅ 支持运行时配置更新
- ✅ 配置集中管理（主要在数据库中）
- ✅ 灵活的配置覆盖机制

### MongoDB 数据库集合

v2.0 架构使用的主要 MongoDB 集合：

```
配置相关:
- tool_configs              # 工具配置
- agent_configs             # Agent配置
- workflow_definitions      # 工作流定义
- workflows                 # 工作流实例

绑定关系:
- tool_agent_bindings       # 工具-Agent绑定
- agent_workflow_bindings   # Agent-工作流绑定
- agent_io_definitions      # Agent IO定义

其他:
- prompt_templates          # 提示词模板
- system_configs            # 系统配置
- user_template_configs     # 用户模板配置
```

## 💻 开发规范

### 代码组织原则

1. **新功能优先在 `core/` 目录实现**
   - 使用 v2.0 的配置化架构
   - 遵循配置优先原则

2. **API 实现放在 `app/` 目录**
   - 路由定义在 `app/routers/`
   - 业务逻辑在 `app/services/`
   - API 应优先使用 `core/` 中的配置管理器

3. **前端实现放在 `frontend/` 目录**
   - Vue 3 + TypeScript
   - 遵循现有的组件结构

4. **兼容旧代码**
   - `tradingagents/` 目录的代码逐步迁移
   - 保持向后兼容性
   - 使用兼容层 (`core/compat/`) 进行适配

### 配置读取实现规范

在实现配置读取时，必须：

```python
# ✅ 正确的实现方式
from core.config import BindingManager, ToolConfigManager

# 1. 使用配置管理器（内部会优先读取数据库）
bm = BindingManager()
bm.set_database(db)  # 设置数据库连接
tools = bm.get_tools_for_agent(agent_id)  # 自动从数据库读取

# 2. 配置管理器内部实现优先级：
#    - 首先查询数据库
#    - 如果数据库没有，使用代码默认值
#    - 缓存结果（5分钟TTL）

# ❌ 错误的实现方式
# 直接从 .env 读取业务配置
api_key = os.getenv("MY_API_KEY")  # 业务配置应该存数据库
```

### 数据库连接

- 使用 `app.core.database` 模块获取数据库连接
- 异步操作使用 `get_mongo_db()`
- 同步操作使用 `get_mongo_db_sync()`
- 连接配置从 `.env` 读取（这是基础设施配置）

## 📝 注意事项

1. **配置存储原则**:
   - 业务配置 → 存储在 MongoDB
   - 基础设施配置 → 存储在 .env

2. **配置读取顺序**:
   - 数据库 > .env > 代码默认值

3. **目录职责**:
   - `core/` - v2.0 核心功能
   - `app/` - 后端 API
   - `frontend/` - 前端界面
   - `tradingagents/` - 旧版代码（逐步迁移）

4. **插件化方向**:
   - 所有配置都应该是可配置的
   - 为未来插件化做好准备
   - 避免硬编码业务逻辑

## 🔗 相关文档

- [v2.0 架构设计文档](../design/v2.0/01-architecture-overview.md)
- [配置矩阵文档](../configuration/CONFIG_MATRIX.md)
- [插件化智能体架构文档](../design/v2.0/agents/README.md)

---

**最后更新**: 2025-12-15  
**版本**: v2.0  
**维护者**: TradingAgentsCN Team

