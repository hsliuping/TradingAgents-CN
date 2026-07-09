# 废弃通知 (Deprecation Notice)

> **更新日期**: 2025-10-05
> 
> **相关文档**: `docs/configuration_optimization_plan.md`

---

## 📋 概述

本文档列出了系统中已废弃或计划废弃的功能、API和配置方式。请开发者和用户注意迁移到新的实现方式。

---

## 🚫 已废弃的配置系统

### 1. JSON 配置文件系统

#### 废弃时间
- **标记废弃**: 2025-10-05
- **计划移除**: 2025-12-31

#### 废弃原因
1. **配置分散**: 配置分散在多个 JSON 文件中，难以管理
2. **缺乏验证**: JSON 文件缺乏类型验证和格式检查
3. **不支持动态更新**: 修改配置需要重启服务
4. **缺乏审计**: 无法追踪配置变更历史
5. **多实例同步困难**: 多个服务实例之间配置同步复杂

#### 废弃的文件

| 文件 | 用途 | 替代方案 |
|------|------|----------|
| `config/models.json` | 大模型配置 | MongoDB `system_configs.llm_configs` |
| `config/settings.json` | 系统设置 | MongoDB `system_configs.system_settings` |
| `config/pricing.json` | 模型定价 | MongoDB `system_configs.llm_configs[].pricing` |
| `config/usage.json` | 使用统计 | MongoDB `llm_usage` 集合 |

#### 迁移步骤

**步骤1: 备份现有配置**
```bash
# 自动备份到 config/backup/
python scripts/migrate_config_to_db.py --backup
```

**步骤2: 执行迁移（Dry Run）**
```bash
# 先查看将要迁移的内容
python scripts/migrate_config_to_db.py --dry-run
```

**步骤3: 执行实际迁移**
```bash
# 执行迁移
python scripts/migrate_config_to_db.py
```

**步骤4: 验证迁移结果**
```bash
# 启动后端服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 访问 Web 界面，检查配置是否正确
# http://localhost:3000/settings/config
```

**步骤5: 删除旧配置文件（可选）**
```bash
# 确认迁移成功后，可以删除旧的 JSON 文件
# 注意：请先确保备份已完成
rm config/models.json
rm config/settings.json
rm config/pricing.json
rm config/usage.json
```

### 2. ConfigManager 类

#### 废弃时间
- **标记废弃**: 2025-10-05
- **计划移除**: 2025-12-31

#### 废弃原因
- 基于 JSON 文件的配置管理
- 不支持动态更新
- 缺乏类型验证

#### 废弃的类和方法

| 类/方法 | 位置 | 替代方案 |
|---------|------|----------|
| `ConfigManager` | `tradingagents/config/config_manager.py` | `app.services.config_service.ConfigService` |
| `ConfigManager.get_models()` | 同上 | `ConfigService.get_llm_configs()` |
| `ConfigManager.get_settings()` | 同上 | `ConfigService.get_system_settings()` |
| `ConfigManager.update_model()` | 同上 | `ConfigService.update_llm_config()` |
| `ConfigManager.update_settings()` | 同上 | `ConfigService.update_system_settings()` |

#### 迁移示例

**旧代码**:
```python
from tradingagents.config.config_manager import ConfigManager

# 获取配置
config_manager = ConfigManager()
models = config_manager.get_models()
settings = config_manager.get_settings()

# 更新配置
config_manager.update_model("dashscope", "qwen-turbo", {"enabled": True})
```

**新代码**:
```python
from app.services.config_service import config_service

# 获取配置
config = await config_service.get_system_config()
llm_configs = config.llm_configs
system_settings = config.system_settings

# 更新配置
await config_service.update_llm_config(
    provider="dashscope",
    model_name="qwen-turbo",
    updates={"enabled": True}
)
```

---

## ⚠️ 计划废弃的功能

### 1. 环境变量中的 API 密钥

#### 计划废弃时间
- **标记废弃**: 2025-10-05
- **计划移除**: 2026-03-31

#### 废弃原因
- API 密钥应该通过 Web 界面管理
- 环境变量仅用于系统级配置

#### 迁移建议
- 将 API 密钥从 `.env` 文件迁移到 Web 界面
- 保留环境变量作为备用方案（优先级低于数据库）

#### 保留的环境变量
以下环境变量将继续支持（用于最小化启动）：
- `MONGODB_*` - 数据库连接
- `REDIS_*` - Redis 连接
- `JWT_SECRET` - JWT 密钥
- `CSRF_SECRET` - CSRF 密钥

### 2. 旧的 API 端点

#### 计划废弃的端点

| 端点 | 废弃时间 | 替代端点 |
|------|----------|----------|
| `/api/config/models` | 2025-10-05 | `/api/config/llm` |
| `/api/config/providers` | 2025-10-05 | `/api/config/llm/providers` |

---

## 📊 废弃时间表

### 2025年第4季度（Q4）

| 日期 | 项目 | 状态 |
|------|------|------|
| 2025-10-05 | 标记 JSON 配置系统为废弃 | ✅ 完成 |
| 2025-10-05 | 标记 ConfigManager 为废弃 | ✅ 完成 |
| 2025-10-15 | 创建配置迁移脚本 | ✅ 完成 |
| 2025-11-01 | 更新所有代码使用新配置系统 | 🔄 进行中 |
| 2025-12-01 | 在文档中添加废弃警告 | 📅 计划中 |

### 2026年第1季度（Q1）

| 日期 | 项目 | 状态 |
|------|------|------|
| 2026-01-01 | 在启动时显示废弃警告 | 📅 计划中 |
| 2026-02-01 | 在 Web 界面显示迁移提示 | 📅 计划中 |
| 2026-03-31 | 移除旧的 JSON 配置系统 | 📅 计划中 |
| 2026-03-31 | 移除 ConfigManager 类 | 📅 计划中 |

---

## 🔔 废弃警告

### 启动时警告

从 2026-01-01 开始，如果检测到使用旧的配置系统，启动时会显示警告：

```
⚠️  警告: 检测到旧的 JSON 配置文件
   • config/models.json
   • config/settings.json

   这些文件将在 2026-03-31 后不再支持。
   请使用迁移脚本迁移到新的配置系统：
   
   python scripts/migrate_config_to_db.py
   
   详细信息: docs/DEPRECATION_NOTICE.md
```

### Web 界面提示

从 2026-02-01 开始，Web 界面会显示迁移提示：

```
💡 提示: 您正在使用旧的配置系统
   
   为了获得更好的体验，建议迁移到新的配置系统。
   新系统支持：
   • 动态更新配置，无需重启
   • 配置历史和回滚
   • 更好的验证和错误提示
   
   [立即迁移] [稍后提醒] [不再显示]
```

---

## 📚 相关文档

- **配置指南**: `docs/configuration_guide.md`
- **配置分析**: `docs/configuration_analysis.md`
- **优化计划**: `docs/configuration_optimization_plan.md`
- **迁移脚本**: `scripts/migrate_config_to_db.py`

---

## 💬 反馈和支持

如果您在迁移过程中遇到问题，请：

1. **查看文档**: `docs/configuration_guide.md`
2. **提交 Issue**: GitHub Issues
3. **联系支持**: [待补充]

---

## 📝 更新日志

### 2025-10-05
- ✅ 创建废弃通知文档
- ✅ 标记 JSON 配置系统为废弃
- ✅ 标记 ConfigManager 类为废弃
- ✅ 创建配置迁移脚本
- ✅ 制定废弃时间表

---

**感谢您的理解和配合！** 🙏

新的配置系统将为您带来更好的体验和更强大的功能。

