# 持仓分析提示词模板修复总结

## 📋 问题描述

在调试持仓分析流程时，发现了三个关键问题：

### 问题1：preference_id 未正确传递
- **现象**：代码中虽然生成了 `preference_id`（如 `with_cache_aggressive`），但模板系统查询时使用的是 `context` 中的 `preference_id`，而不是代码生成的。
- **影响**：无法正确查询到 `with_cache` 和 `without_cache` 对应的模板，总是使用默认的 `neutral` 模板。

### 问题2：没有缓存时缺少工具调用
- **现象**：当没有单股分析缓存时，技术面分析师应该调用工具获取市场数据，但 `default_tools` 为空列表。
- **影响**：没有缓存时无法获取市场数据，只能使用已有的 `market_data`。

### 问题3：数据库模板结构不完整
- **现象**：数据库中的 `with_cache` 和 `without_cache` 模板只有 2 个字段，而标准模板应该有 5 个字段（包含 `system_prompt` 和 `user_prompt`）。
- **影响**：模板系统无法正确加载和使用这些模板。

---

## ✅ 修复方案

### 修复1：传递 preference_id 到模板系统

**文件**：`core/agents/adapters/position/technical_analyst_v2.py` 和 `fundamental_analyst_v2.py`

**修改内容**：
```python
# 🔧 修复问题1：将生成的 preference_id 传递给 context
# 如果 context 是字典，更新 preference_id；如果是对象，创建新的 context 字典
if context:
    if isinstance(context, dict):
        context = {**context, "preference_id": preference_id}
    else:
        # 如果是对象，创建字典包装
        context_dict = {"user_id": getattr(context, "user_id", None)}
        if hasattr(context, "preference_id"):
            context_dict["preference_id"] = preference_id
        else:
            context_dict["preference_id"] = preference_id
        context = context_dict
else:
    # 如果没有 context，创建一个包含 preference_id 的字典
    context = {"preference_id": preference_id}

logger.info(f"🔧 [技术面分析师] 传递 preference_id 到模板系统: {preference_id}")
```

**效果**：
- ✅ 正确传递 `preference_id`（如 `with_cache_aggressive`）到模板系统
- ✅ 模板系统能够查询到对应的 `with_cache` 和 `without_cache` 模板

---

### 修复2：添加工具调用能力

**文件**：`core/agents/adapters/position/technical_analyst_v2.py`

**修改内容**：
```python
# Agent元数据
metadata = AgentMetadata(
    id="pa_technical_v2",
    name="技术面分析师 v2.0",
    description="分析持仓股票的技术面，包括K线形态、技术指标、支撑阻力位",
    category=AgentCategory.ANALYST,
    version="2.0.0",
    license_tier=LicenseTier.FREE,
    default_tools=["get_stock_market_data_unified"],  # 🔧 修复：当没有缓存时需要调用工具获取市场数据
)
```

**效果**：
- ✅ 当没有缓存时，技术面分析师可以调用 `get_stock_market_data_unified` 工具获取市场数据
- ✅ 工具调用逻辑由基类 `ResearcherAgent` 自动处理

---

### 修复3：修复数据库模板结构

**文件**：`scripts/fix_position_analysis_templates.py`（新建）

**功能**：
1. 查找所有 `with_cache` 和 `without_cache` 模板
2. 从对应的旧版模板（`aggressive`/`neutral`/`conservative`）中提取 `system_prompt` 和 `user_prompt`
3. 根据缓存场景调整 `user_prompt` 内容：
   - `with_cache`：添加引用缓存报告的说明
   - `without_cache`：添加调用工具的说明
4. 更新数据库中的模板结构

**使用方法**：
```bash
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 运行修复脚本
python scripts/fix_position_analysis_templates.py
```

**效果**：
- ✅ 所有 `with_cache` 和 `without_cache` 模板都包含完整的 5 个字段
- ✅ `system_prompt` 和 `user_prompt` 从旧版模板中正确提取
- ✅ `user_prompt` 根据缓存场景进行了适当调整

---

## 📊 修复后的流程

### 场景1：有缓存 + 使用缓存模板

```
用户请求（use_stock_analysis=True）
  ↓
检查缓存（24小时内）
  ↓
找到缓存报告 ✅
  ↓
生成 preference_id: "with_cache_aggressive"（假设用户偏好是 aggressive）
  ↓
传递 preference_id 到模板系统
  ↓
查询模板：agent_type="position_analysis_v2", agent_name="pa_technical_v2", preference_type="with_cache_aggressive"
  ↓
加载模板（包含 system_prompt 和 user_prompt）
  ↓
渲染 user_prompt（包含 {market_report} 变量，引用缓存报告）
  ↓
执行分析
```

### 场景2：无缓存 + 调用工具

```
用户请求（use_stock_analysis=True）
  ↓
检查缓存（24小时内）
  ↓
没有缓存报告 ❌
  ↓
生成 preference_id: "without_cache_neutral"（假设用户偏好是 neutral）
  ↓
传递 preference_id 到模板系统
  ↓
查询模板：agent_type="position_analysis_v2", agent_name="pa_technical_v2", preference_type="without_cache_neutral"
  ↓
加载模板（包含 system_prompt 和 user_prompt，user_prompt 包含工具调用说明）
  ↓
渲染 user_prompt（提示调用 get_stock_market_data_unified 工具）
  ↓
Agent 检测到需要工具 → 调用 get_stock_market_data_unified
  ↓
获取市场数据 → 执行分析
```

---

## 🧪 测试建议

### 1. 测试 preference_id 传递

```python
# 在 technical_analyst_v2.py 的 _build_user_prompt 方法中添加日志
logger.info(f"🔧 [技术面分析师] 传递 preference_id 到模板系统: {preference_id}")
logger.info(f"🔧 [技术面分析师] context 内容: {context}")

# 验证日志输出：
# ✅ 应该看到：preference_id="with_cache_aggressive" 或 "without_cache_neutral"
# ✅ context 中应该包含 preference_id 字段
```

### 2. 测试模板查询

```python
# 在 template_client.py 的 get_effective_template 方法中添加日志
logger.info(f"[diagnose] system_query={system_query}")

# 验证日志输出：
# ✅ with_cache 场景：preference_type="with_cache_aggressive"
# ✅ without_cache 场景：preference_type="without_cache_neutral"
```

### 3. 测试工具调用

```python
# 在没有缓存的情况下，验证工具是否被调用
# 检查日志：
# ✅ 应该看到：调用 get_stock_market_data_unified 工具
# ✅ 应该看到：工具返回的市场数据
```

### 4. 测试模板结构

```python
# 运行修复脚本后，检查数据库
from app.core.database import get_mongo_db_sync

db = get_mongo_db_sync()
template = db.prompt_templates.find_one({
    "agent_type": "position_analysis_v2",
    "agent_name": "pa_technical_v2",
    "preference_type": "with_cache_neutral"
})

# 验证：
# ✅ template["content"] 应该包含 5 个字段
# ✅ template["content"]["system_prompt"] 不应该为空
# ✅ template["content"]["user_prompt"] 不应该为空
```

---

## 📝 相关文件

### 修改的文件
1. `core/agents/adapters/position/technical_analyst_v2.py`
   - 添加工具：`default_tools=["get_stock_market_data_unified"]`
   - 修复 preference_id 传递逻辑

2. `core/agents/adapters/position/fundamental_analyst_v2.py`
   - 修复 preference_id 传递逻辑

### 新建的文件
1. `scripts/fix_position_analysis_templates.py`
   - 数据库模板结构修复脚本

### 文档
1. `docs/POSITION_ANALYSIS_TEMPLATE_FIX.md`（本文档）
   - 修复总结和使用说明

---

## 🎯 下一步建议

1. **运行修复脚本**：执行 `scripts/fix_position_analysis_templates.py` 修复数据库模板结构
2. **测试验证**：按照上述测试建议进行验证
3. **前端优化**：可以考虑在前端添加提示，告知用户是否有缓存报告可用
4. **监控日志**：在生产环境中监控日志，确保 preference_id 正确传递和模板正确加载

---

## ✅ 修复完成检查清单

- [x] 修复 preference_id 传递逻辑（technical_analyst_v2.py）
- [x] 修复 preference_id 传递逻辑（fundamental_analyst_v2.py）
- [x] 添加工具调用能力（technical_analyst_v2.py）
- [x] 创建数据库模板修复脚本
- [x] 编写修复总结文档

---

**最后更新**：2026-02-02  
**修复版本**：v2.0.1
