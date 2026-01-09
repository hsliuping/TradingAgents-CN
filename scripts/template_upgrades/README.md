# v2.0 Agent 模板升级脚本

## 📋 概述

本目录包含所有 v2.0 Agent 模板的升级脚本，用于批量更新数据库中的提示词模板。

## 📁 脚本列表

| 脚本文件 | Agent 类型 | 包含的 Agent |
|---------|-----------|-------------|
| `upgrade_researchers_v2.py` | 研究员 | bull_researcher_v2, bear_researcher_v2 |
| `upgrade_risk_analysts_v2.py` | 风险分析师 | risky_analyst_v2, safe_analyst_v2, neutral_analyst_v2 |
| `upgrade_managers_v2.py` | 管理员 | research_manager_v2, risk_manager_v2 |
| `upgrade_trader_v2.py` | 交易员 | trader_v2 |
| `upgrade_reviewers_v2.py` | 复盘分析师 | timing_analyst_v2, position_analyst_v2, emotion_analyst_v2, attribution_analyst_v2, review_manager_v2 |
| `upgrade_position_advisors_v2.py` | 持仓顾问 | pa_technical_v2, pa_fundamental_v2, pa_risk_v2, pa_advisor_v2 |
| `restore_cache_templates.py` | **缓存场景模板** | pa_technical_v2, pa_fundamental_v2 (with_cache/without_cache) |
| `upgrade_all_v2_templates.py` | **一键升级** | 所有上述 Agent |

## 🚀 使用方法

### 方法 1: 一键升级所有模板（推荐）

```powershell
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 运行一键升级脚本
python scripts\template_upgrades\upgrade_all_v2_templates.py
```

### 方法 2: 单独升级某类 Agent

```powershell
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 升级研究员
python scripts\template_upgrades\upgrade_researchers_v2.py

# 升级风险分析师
python scripts\template_upgrades\upgrade_risk_analysts_v2.py

# 升级管理员
python scripts\template_upgrades\upgrade_managers_v2.py

# 升级交易员
python scripts\template_upgrades\upgrade_trader_v2.py

# 升级复盘分析师
python scripts\template_upgrades\upgrade_reviewers_v2.py

# 升级持仓顾问
python scripts\template_upgrades\upgrade_position_advisors_v2.py

# 恢复缓存场景模板（如果被误删）
python scripts\template_upgrades\restore_cache_templates.py
```

## 📊 升级内容

每个脚本主要升级以下字段：

1. **`content.analysis_requirements`** - 分析要求（详细的分析指导）
2. **`content.output_format`** - 输出格式（部分 Agent）
3. **`updated_at`** - 更新时间

## 🔄 缓存场景模板说明

### 什么是缓存场景模板？

持仓分析 Agent（`pa_technical_v2` 和 `pa_fundamental_v2`）有两种工作模式：

1. **with_cache**: 有缓存的单股分析报告
   - 提示词会引导 Agent 结合缓存报告进行分析
   - 避免重复分析，提高效率
   - 示例：`with_cache_aggressive`, `with_cache_neutral`, `with_cache_conservative`

2. **without_cache**: 无缓存的单股分析报告
   - 提示词会引导 Agent 直接基于持仓信息分析
   - 独立完成分析，不依赖缓存
   - 示例：`without_cache_aggressive`, `without_cache_neutral`, `without_cache_conservative`

### 如何使用？

系统会自动根据是否有缓存报告选择对应的模板：

```python
# 在 core/agents/adapters/position/technical_analyst_v2.py 中
cache_scenario = "with_cache" if has_cache else "without_cache"
preference_id = f"{cache_scenario}_{user_preference}"
# 例如: with_cache_aggressive, without_cache_neutral
```

### 如何恢复？

如果这些模板被误删，运行恢复脚本：

```powershell
python scripts\template_upgrades\restore_cache_templates.py
```

### ⚠️ 重要提醒

**不要删除 `with_cache` 和 `without_cache` 模板！**

这些模板是持仓分析功能的核心，删除后会导致：
- 持仓分析无法正常工作
- Agent 无法获取正确的提示词
- 分析结果质量下降

## ✅ 升级后验证

升级完成后，可以通过以下方式验证：

### 1. 查看数据库

```powershell
# 查看所有 v2.0 模板
python scripts\check_all_v2_agents.py
```

### 2. 前端验证

1. 登录系统
2. 进入"系统设置" → "提示词管理"
3. 查看各个 Agent 的模板内容
4. 确认 `analysis_requirements` 字段已更新

### 3. 运行分析测试

1. 创建一个测试分析任务
2. 查看生成的报告
3. 确认报告结构和内容符合新的要求

## 🔧 脚本结构

每个升级脚本的结构：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
升级 XXX v2.0 模板
"""

# 1. 导入依赖
import os, sys
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient

# 2. 数据库连接
# ...

# 3. 模板定义
REQUIREMENTS = {
    "agent1": """详细的分析要求...""",
    "agent2": """详细的分析要求...""",
}

# 4. 更新函数
def update_agents():
    collection = db['prompt_templates']
    # 更新逻辑...
    return updated_count

# 5. 主函数
def main():
    updated = update_agents()
    print(f"✅ 完成！共更新 {updated} 个模板")

if __name__ == "__main__":
    main()
```

## 📝 注意事项

1. **备份数据库**: 升级前建议备份 `prompt_templates` 集合
2. **测试环境**: 建议先在测试环境运行，确认无误后再在生产环境运行
3. **版本控制**: 脚本会自动更新 `updated_at` 字段，可以通过该字段追踪更新历史
4. **幂等性**: 脚本可以重复运行，不会产生副作用
5. **缓存场景模板**: `with_cache` 和 `without_cache` 模板由单独的脚本管理，不要删除！

## 🔄 更新流程

当需要更新某个 Agent 的模板时：

1. 编辑对应的升级脚本（如 `upgrade_researchers_v2.py`）
2. 修改 `REQUIREMENTS` 字典中的内容
3. 运行脚本更新数据库
4. 验证更新结果
5. 提交代码到版本控制

## 📚 相关文档

- [v2.0 Agent 架构设计](../../docs/design/v2.0/)
- [提示词管理文档](../../docs/prompts/)
- [数据库设计文档](../../docs/database/)

## ❓ 常见问题

### Q: 升级脚本会覆盖用户自定义的模板吗？

A: 不会。脚本只更新 `is_system: True` 的系统模板，用户自定义模板不受影响。

### Q: 如何回滚到之前的版本？

A: 可以从数据库备份中恢复，或者修改脚本中的内容后重新运行。

### Q: 升级后需要重启服务吗？

A: 不需要。模板是从数据库动态加载的，更新后立即生效。

### Q: 如何查看某个模板的更新历史？

A: 可以通过 `updated_at` 字段查看最后更新时间，或者查看 Git 提交历史。

---

**最后更新**: 2026-01-09  
**维护者**: TradingAgents-CN Pro Team

