# Augment 项目规则说明

## 📋 概述

本目录包含 TradingAgents-CN Pro 项目的 Augment AI 规则文件。这些规则帮助 Augment 理解项目结构、开发规范和最佳实践。

---

## 📁 规则文件列表

### 1. `project_overview.md` - 项目概览

**用途**: 提供项目的整体信息和架构说明

**包含内容**:
- 📋 项目基本信息（名称、版本、技术栈）
- 🏗️ 架构版本说明（v1.x vs v2.0）
- 📁 核心目录结构
- 🗄️ MongoDB 数据库集合列表
- 🔧 配置管理原则
- 💻 开发规范

**何时参考**:
- 开始新功能开发
- 需要了解项目整体架构
- 不确定代码应该放在哪个目录

---

### 2. `database_export.md` - 数据库导出规则

**用途**: 定义数据库导出和导入的规范

**包含内容**:
- 📊 导出集合分类（配置类 vs 数据类）
- 🎯 导出场景（演示系统 vs 迁移）
- 🔐 脱敏规则
- 📝 文件命名规范
- 🚀 导入配置

**何时参考**:
- 需要导出数据库配置
- 准备便携版发布包
- 数据迁移或备份

---

### 3. `directory_structure.md` - 目录结构规则

**用途**: 定义项目的目录组织规范

**包含内容**:
- 📁 项目根目录结构
- 📦 核心代码包结构
- 🌐 Web 界面结构
- 📚 文档结构
- 🧪 测试结构
- 🔧 脚本结构

**何时参考**:
- 创建新文件或目录
- 组织代码结构
- 不确定文件应该放在哪里

---

### 3. `directory_structure.md` - 目录结构规则

**用途**: 定义项目的目录组织规范

**包含内容**:
- 📁 项目根目录结构
- 📦 核心代码包结构
- 🌐 Web 界面结构
- 📚 文档结构
- 🧪 测试结构
- 🔧 脚本结构

**何时参考**:
- 创建新文件或目录
- 组织代码结构
- 不确定文件应该放在哪里

---

### 4. `deployment_packaging.md` - 部署和打包规则

**用途**: 定义三种打包方式的规范和流程

**包含内容**:
- 🐳 Docker 部署打包（跨平台）
- 📦 绿色便携版（Windows 免安装）
- 💿 Windows 安装包（NSIS 安装程序）
- 🔧 构建脚本和参数
- 📝 构建顺序建议

**何时参考**:
- 准备发布新版本
- 构建部署包
- 修改打包脚本
- 了解部署方式

---

## 🎯 使用场景

### 场景 1: 开始新功能开发

1. 查看 `project_overview.md` 了解架构
2. 确定功能应该在 `core/` 还是 `app/` 实现
3. 参考 `directory_structure.md` 确定文件位置
4. 遵循配置管理原则（数据库 > .env > 代码）

### 场景 2: 数据库配置导出

1. 查看 `database_export.md` 了解导出规则
2. 确定导出场景（演示系统 vs 迁移）
3. 选择正确的集合列表
4. 决定是否启用脱敏

### 场景 3: 代码重构

1. 参考 `project_overview.md` 了解 v2.0 架构
2. 使用配置管理器而不是硬编码
3. 遵循目录结构规范
4. 保持向后兼容

### 场景 4: 准备发布新版本

1. 查看 `deployment_packaging.md` 了解三种打包方式
2. 更新 `VERSION` 文件
3. 按顺序构建：便携版 → 安装包 → Docker 镜像
4. 验证每个打包产物

---

## 🔧 配置管理核心原则

### 优先级

```
数据库配置 > .env 配置 > 代码默认值
```

### 存储位置

| 配置类型 | 存储位置 | 示例 |
|---------|---------|------|
| 业务配置 | MongoDB | 工作流、Agent、工具配置 |
| 基础设施 | .env | MongoDB 连接、服务器端口 |
| 默认值 | 代码 | 内置配置、备选参数 |

### 正确示例

```python
# ✅ 正确：使用配置管理器
from core.config import BindingManager

bm = BindingManager()
bm.set_database(db)
tools = bm.get_tools_for_agent(agent_id)

# ❌ 错误：直接从环境变量读取业务配置
api_key = os.getenv("MY_API_KEY")  # 应该存数据库
```

---

## 📊 MongoDB 集合速查

### v2.0 核心集合（必须导出）

```python
# 工作流和智能体
workflow_definitions, agent_configs, tool_configs

# 绑定关系
tool_agent_bindings, agent_workflow_bindings, agent_io_definitions

# 系统配置
system_configs, llm_providers, model_catalog

# 用户和交易
users, user_configs, trading_systems

# 提示词
prompt_templates, user_template_configs
```

### 数据类集合（不建议导出）

```python
# 大量数据
stock_basic_info, market_quotes, stock_financial_data
stock_news, operation_logs
```

---

## 🚀 快速参考

### 新功能开发

1. **位置**: `core/` (v2.0) 或 `app/` (API)
2. **配置**: 优先使用数据库配置
3. **管理器**: 使用 `core/config/` 中的配置管理器

### API 开发

1. **路由**: `app/routers/`
2. **服务**: `app/services/`
3. **模型**: `app/models/` 和 `app/schemas/`

### 前端开发

1. **页面**: `frontend/src/views/`
2. **组件**: `frontend/src/components/`
3. **API**: `frontend/src/api/`

### 数据库操作

1. **连接**: `from app.core.database import get_mongo_db`
2. **异步**: `await init_database()` + `get_mongo_db()`
3. **同步**: `get_mongo_db_sync()`

---

## 📝 更新规则

### 何时更新规则文件

- ✅ 新增重要的 MongoDB 集合
- ✅ 架构发生重大变更
- ✅ 新增核心开发规范
- ✅ 目录结构调整

### 如何更新

1. 编辑对应的规则文件
2. 更新 `最后更新` 日期
3. 提交到版本控制

---

## ❓ 常见问题

### Q: 为什么需要这些规则文件？

**A**: 帮助 Augment AI 理解项目结构和开发规范，提供更准确的代码建议。

### Q: 规则文件会自动应用吗？

**A**: 是的，Augment 会自动读取 `.augment/rules/` 目录下的所有规则文件。

### Q: 可以自定义规则吗？

**A**: 可以！在 `.augment/rules/` 目录下创建新的 `.md` 文件即可。

### Q: 规则文件支持什么格式？

**A**: Markdown (`.md`) 格式，支持代码块、表格等。

---

## 🔗 相关文档

- 📖 项目文档: `docs/`
- 🔧 Cursor 规则: `.cursor/rules/tradingagents.mdc`
- 📝 发布说明: `RELEASE_NOTES_v1.0.0.md`
- 🗄️ 数据库方案: `DATABASE_INIT_SOLUTION.md`

---

**最后更新**: 2026-01-05  
**维护者**: TradingAgents-CN Pro Team

