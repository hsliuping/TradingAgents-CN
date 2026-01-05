# Augment AI 规则配置指南

## 📋 概述

本文档说明如何为 Augment AI 配置项目规则，使其更好地理解 TradingAgents-CN Pro 项目。

---

## 🎯 为什么需要规则文件？

### 问题

每次使用 Augment AI 时，都需要重新解释项目结构、配置原则和开发规范，效率低下。

### 解决方案

在 `.augment/rules/` 目录下创建规则文件，Augment 会自动读取并应用这些规则。

---

## 📁 规则文件结构

```
.augment/rules/
├── README.md                  # 规则说明文档
├── project_overview.md        # 项目概览
├── database_export.md         # 数据库导出规则
└── directory_structure.md     # 目录结构规则
```

---

## 📝 已创建的规则文件

### 1. `project_overview.md`

**内容**:
- 项目基本信息（名称、版本、技术栈）
- 架构版本说明（v1.x vs v2.0）
- 核心目录结构
- MongoDB 数据库集合列表
- 配置管理原则
- 开发规范

**用途**: 让 Augment 了解项目整体架构和开发规范

---

### 2. `database_export.md`

**内容**:
- 导出集合分类（配置类 vs 数据类）
- 导出场景（演示系统 vs 迁移）
- 脱敏规则
- 文件命名规范
- 导入配置

**用途**: 让 Augment 知道如何正确导出和导入数据库配置

---

### 3. `directory_structure.md`

**内容**:
- 项目根目录结构
- 核心代码包结构
- Web 界面结构
- 文档结构
- 测试结构
- 脚本结构

**用途**: 让 Augment 知道文件应该放在哪个目录

---

### 4. `README.md`

**内容**:
- 规则文件列表和说明
- 使用场景
- 配置管理核心原则
- MongoDB 集合速查
- 快速参考

**用途**: 规则文件的使用指南

---

## 🔧 与 Cursor 规则的对比

### Cursor 规则

**位置**: `.cursor/rules/tradingagents.mdc`  
**格式**: Markdown with frontmatter  
**特性**: 
- 支持 `alwaysApply: true` 自动应用
- 单文件包含所有规则

### Augment 规则

**位置**: `.augment/rules/*.md`  
**格式**: Markdown  
**特性**:
- 多文件组织，按主题分类
- 自动读取目录下所有 `.md` 文件
- 更灵活的组织方式

---

## 🚀 使用示例

### 场景 1: 询问项目架构

**用户**: "这个项目的架构是什么样的？"

**Augment**: 
- 自动读取 `project_overview.md`
- 回答包含 v1.x vs v2.0 架构说明
- 说明核心目录结构
- 解释配置管理原则

### 场景 2: 导出数据库配置

**用户**: "我需要导出数据库配置用于便携版"

**Augment**:
- 自动读取 `database_export.md`
- 知道应该导出哪些集合
- 知道应该启用脱敏
- 提供正确的导出命令

### 场景 3: 创建新功能

**用户**: "我要创建一个新的 API 路由"

**Augment**:
- 自动读取 `project_overview.md` 和 `directory_structure.md`
- 知道应该在 `app/routers/` 创建路由
- 知道应该在 `app/services/` 创建服务
- 知道应该使用 `core/config/` 中的配置管理器

---

## ✅ 验证规则是否生效

### 方法 1: 直接询问

```
用户: "这个项目的配置管理原则是什么？"

Augment: 应该回答 "数据库配置 > .env 配置 > 代码默认值"
```

### 方法 2: 测试场景

```
用户: "我要添加一个新的 LLM 模型配置"

Augment: 应该建议将配置存储在 MongoDB 的 model_catalog 集合中
```

### 方法 3: 检查文件位置建议

```
用户: "我要创建一个新的工具"

Augment: 应该建议在 core/tools/ 目录下创建
```

---

## 📝 维护规则文件

### 何时更新

- ✅ 新增重要的 MongoDB 集合
- ✅ 架构发生重大变更
- ✅ 新增核心开发规范
- ✅ 目录结构调整
- ✅ 配置管理原则变化

### 如何更新

1. 编辑对应的规则文件（`.augment/rules/*.md`）
2. 更新 `最后更新` 日期
3. 提交到版本控制
4. Augment 会自动读取最新版本

---

## 🎓 最佳实践

### 1. 保持规则简洁

- ✅ 只包含核心信息
- ✅ 使用清晰的标题和分类
- ❌ 避免过多细节

### 2. 使用示例代码

```python
# ✅ 好的示例：清晰明了
from core.config import BindingManager
bm = BindingManager()
tools = bm.get_tools_for_agent(agent_id)

# ❌ 错误示例：说明为什么错误
api_key = os.getenv("MY_API_KEY")  # 业务配置应存数据库
```

### 3. 定期审查

- 每月检查规则是否过时
- 根据项目变化更新规则
- 删除不再适用的规则

---

## 🔗 相关资源

- **Augment 规则目录**: `.augment/rules/`
- **Cursor 规则文件**: `.cursor/rules/tradingagents.mdc`
- **项目文档**: `docs/`
- **发布说明**: `RELEASE_NOTES_v1.0.0.md`

---

## ❓ 常见问题

### Q: Augment 会自动读取规则吗？

**A**: 是的，Augment 会自动读取 `.augment/rules/` 目录下的所有 `.md` 文件。

### Q: 规则文件支持什么格式？

**A**: Markdown (`.md`) 格式，支持代码块、表格、列表等。

### Q: 可以有多个规则文件吗？

**A**: 可以！建议按主题分类创建多个文件，便于维护。

### Q: 规则文件会影响性能吗？

**A**: 不会，Augment 只在需要时读取规则文件。

---

**最后更新**: 2026-01-05  
**维护者**: TradingAgents-CN Pro Team

