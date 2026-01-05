# TradingAgents-CN Pro - 项目概览

## 📋 项目基本信息

**项目名称**: TradingAgents-CN Pro  
**版本**: v1.0.0 (基于 v2.0 架构)  
**类型**: 多智能体股票分析系统  
**许可证**: 专有许可证（商业版）  
**技术栈**: Python 3.10 + FastAPI + Vue 3 + MongoDB + Redis

---

## 🏗️ 架构版本说明

### v1.x (旧版 - 逐步淘汰)
- 位于 `tradingagents/` 目录
- 基于 LangGraph 的简单工作流
- 硬编码的智能体和工具
- 许可证: Apache 2.0 (开源)

### v2.0 (当前版本 - 主要开发方向)
- 位于 `core/` 目录
- 完全配置化的工作流引擎
- 插件化的智能体和工具系统
- 数据库驱动的配置管理
- 许可证: 专有许可证 (商业版)

---

## 📁 核心目录结构

```
TradingAgentsCN/
├── core/                      # v2.0 核心功能（商业版）
│   ├── workflow/              # 工作流引擎
│   ├── agents/                # 智能体系统
│   ├── llm/                   # 统一 LLM 客户端
│   ├── config/                # 配置管理器
│   ├── state/                 # 状态管理
│   ├── tools/                 # 工具系统
│   ├── prompts/               # 提示词管理
│   ├── compat/                # 兼容层
│   └── licensing/             # 许可证模块（Cython编译）
│
├── app/                       # 后端 API（商业版）
│   ├── routers/               # FastAPI 路由
│   ├── services/              # 业务逻辑层
│   ├── models/                # 数据模型
│   ├── schemas/               # API 模式
│   ├── middleware/            # 中间件
│   └── core/                  # 数据库连接等
│
├── frontend/                  # 前端界面（商业版）
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── components/        # 通用组件
│   │   ├── api/               # API 客户端
│   │   └── stores/            # 状态管理
│   └── public/
│
├── tradingagents/             # v1.x 旧版代码（开源）
│   ├── agents/                # 旧版智能体
│   ├── dataflows/             # 数据流处理
│   ├── models/                # 旧版模型
│   └── tools/                 # 旧版工具
│
├── web/                       # 旧版 Web 界面（逐步淘汰）
├── docs/                      # 项目文档
│   └── deployment/            # 部署文档
│       └── docker/            # Docker 部署文档
├── tests/                     # 测试文件
├── scripts/                   # 工具脚本
│   ├── deployment/            # 便携版打包脚本
│   └── windows-installer/     # Windows 安装包脚本
├── examples/                  # 示例代码
├── install/                   # 安装配置文件
├── data/                      # 数据目录
├── config/                    # 配置文件
├── prompts/                   # 提示词模板
├── release/                   # 发布产物
│   ├── TradingAgentsCN-portable/  # 便携版目录
│   └── packages/              # 打包文件
├── vendors/                   # 嵌入式运行时（便携版）
│   ├── python/                # Python 3.10.11 嵌入式版本
│   ├── mongodb/               # MongoDB 便携版
│   ├── redis/                 # Redis 便携版
│   └── nginx/                 # Nginx 便携版
├── Dockerfile.backend         # 后端 Docker 镜像
├── Dockerfile.frontend        # 前端 Docker 镜像
├── docker-compose.yml         # Docker Compose 配置
└── VERSION                    # 版本号文件
```

---

## 🗄️ MongoDB 数据库集合

### v2.0 核心集合（必须导出）

**工作流和智能体**:
- `workflow_definitions` - 工作流定义
- `workflows` - 工作流实例
- `agent_configs` - Agent 配置
- `tool_configs` - 工具配置

**绑定关系**:
- `tool_agent_bindings` - 工具-Agent 绑定
- `agent_workflow_bindings` - Agent-工作流 绑定
- `agent_io_definitions` - Agent IO 定义

**系统配置**:
- `system_configs` - 系统配置（包括 LLM 配置）
- `llm_providers` - LLM 提供商
- `model_catalog` - 模型目录
- `platform_configs` - 平台配置

**数据源和市场**:
- `datasource_groupings` - 数据源分组
- `market_categories` - 市场分类

**用户相关**:
- `users` - 用户数据
- `user_configs` - 用户配置
- `user_tags` - 用户标签
- `user_favorites` - 用户收藏

**交易系统**:
- `trading_systems` - 个人交易计划
- `trading_system_versions` - 交易计划版本历史

**提示词**:
- `prompt_templates` - 提示词模板
- `user_template_configs` - 用户模板配置

**任务和分析**:
- `unified_analysis_tasks` - 统一分析任务（v2.0）
- `analysis_tasks` - 分析任务（v1.x）
- `analysis_reports` - 分析报告

### 数据类集合（不建议导出，数据量大）
- `stock_basic_info` - 股票基础信息
- `market_quotes` - 市场行情
- `stock_financial_data` - 财务数据
- `stock_news` - 股票新闻
- `operation_logs` - 操作日志

---

## 🔧 配置管理原则

### 配置存储优先级

**数据库配置 > .env 配置 > 代码默认值**

### 配置存储位置

1. **MongoDB 数据库**（主要存储位置）:
   - 工作流配置
   - Agent 配置
   - 工具配置
   - 提示词配置
   - 绑定关系
   - 系统配置
   - 用户配置

2. **.env 文件**（仅用于基础设施）:
   - MongoDB 连接参数
   - Redis 连接参数
   - 服务器地址和端口
   - 调试模式
   - API 密钥（环境变量注入）

3. **代码默认值**（最后的备选）:
   - 内置配置
   - 默认参数

### 配置管理器

位于 `core/config/` 目录：
- `binding_manager.py` - 统一绑定管理
- `tool_config_manager.py` - 工具配置管理
- `agent_config_manager.py` - Agent 配置管理
- `workflow_config_manager.py` - 工作流配置管理

所有配置管理器特性：
- **单例模式** - 全局唯一实例
- **缓存机制** - 5分钟 TTL 缓存
- **优先级原则** - 数据库 > 代码默认值

---

## 💻 开发规范

### 代码组织原则

1. **新功能优先在 `core/` 目录实现**
   - 使用 v2.0 配置化架构
   - 遵循配置优先原则

2. **API 实现放在 `app/` 目录**
   - 路由: `app/routers/`
   - 业务逻辑: `app/services/`
   - 优先使用 `core/` 配置管理器

3. **前端实现放在 `frontend/` 目录**
   - Vue 3 + TypeScript
   - Element Plus UI 组件库

4. **兼容旧代码**
   - `tradingagents/` 逐步迁移
   - 保持向后兼容
   - 使用 `core/compat/` 兼容层

### 安全规范

1. **许可证验证服务器地址必须硬编码**
   - ✅ 在 `core/licensing/validator.py` 中硬编码
   - ✅ 在 `app/services/license_service.py` 中硬编码
   - ❌ 不能从环境变量读取（防止用户搭建假服务器绕过验证）
   - 🔐 当前域名: `https://www.tradingagentscn.com/api/v1`

2. **敏感配置保护**
   - 许可证验证密钥在 Cython 编译后的代码中
   - 用户无法查看或修改验证逻辑

### 配置读取实现

```python
# ✅ 正确方式
from core.config import BindingManager

bm = BindingManager()
bm.set_database(db)
tools = bm.get_tools_for_agent(agent_id)  # 自动从数据库读取

# ❌ 错误方式
api_key = os.getenv("MY_API_KEY")  # 业务配置应存数据库
```

### 数据库连接

```python
from app.core.database import get_mongo_db, init_database

# 异步操作
await init_database()
db = get_mongo_db()

# 同步操作
from app.core.database import get_mongo_db_sync
db = get_mongo_db_sync()
```

---

**最后更新**: 2026-01-05  
**版本**: v1.0.0 (基于 v2.0 架构)

