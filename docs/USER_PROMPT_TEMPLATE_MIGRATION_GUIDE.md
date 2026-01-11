# 用户级提示词配置迁移指南

## 📋 概述

本文档说明如何将所有 v2.0 Agent 迁移到支持用户级提示词配置的架构。

## 🎯 目标

实现用户级别的提示词配置功能，使得：
1. 系统优先使用用户配置的提示词（`user_template_configs` 集合）
2. 如果没有用户配置，则使用 `preference_id` 查找系统模板
3. 最后才使用代码中的默认提示词

## 🏗️ 架构设计

### 1. 基类方法

在所有 Agent 基类中添加 `_get_prompt_from_template()` 通用方法：
- `AnalystAgent` ✅ 已完成
- `ResearcherAgent` ✅ 已完成
- `ManagerAgent` ✅ 已完成
- `TraderAgent` ✅ 已完成

### 2. 工作流引擎

在 `app/services/unified_analysis_engine.py` 中：
- 创建 `AgentContext` 对象
- 将 `user_id` 和 `preference_id` 添加到 `AgentContext`
- 将 `AgentContext` 添加到 `workflow_inputs["context"]`

### 3. Agent 适配器

所有 Agent 适配器需要：
1. 删除直接导入的 `get_agent_prompt`
2. 在 `_build_system_prompt()` 或 `_build_user_prompt()` 中调用基类的 `_get_prompt_from_template()` 方法

## 📝 需要更新的文件列表

### AnalystAgent 子类（已完成 ✅）

- ✅ `core/agents/adapters/index_analyst_v2.py`
- ✅ `core/agents/adapters/market_analyst_v2.py`
- ✅ `core/agents/adapters/news_analyst_v2.py`
- ✅ `core/agents/adapters/sector_analyst_v2.py`
- ✅ `core/agents/adapters/social_analyst_v2.py`

### ResearcherAgent 子类（待更新 ⏳）

- ⏳ `core/agents/adapters/bull_researcher_v2.py`
- ⏳ `core/agents/adapters/bear_researcher_v2.py`
- ⏳ `core/agents/adapters/neutral_analyst_v2.py`
- ⏳ `core/agents/adapters/safe_analyst_v2.py`
- ⏳ `core/agents/adapters/risky_analyst_v2.py`

**复盘分析 ResearcherAgent**:
- ⏳ `core/agents/adapters/review/attribution_analyst_v2.py`
- ⏳ `core/agents/adapters/review/emotion_analyst_v2.py`
- ⏳ `core/agents/adapters/review/position_analyst_v2.py`
- ⏳ `core/agents/adapters/review/timing_analyst_v2.py`

**持仓分析 ResearcherAgent**:
- ⏳ `core/agents/adapters/position/fundamental_analyst_v2.py`
- ⏳ `core/agents/adapters/position/technical_analyst_v2.py`
- ⏳ `core/agents/adapters/position/risk_assessor_v2.py`

### ManagerAgent 子类（待更新 ⏳）

- ⏳ `core/agents/adapters/research_manager_v2.py`
- ⏳ `core/agents/adapters/risk_manager_v2.py`
- ⏳ `core/agents/adapters/review/review_manager_v2.py`
- ⏳ `core/agents/adapters/position/position_manager_v2.py`

### TraderAgent 子类（待更新 ⏳）

- ⏳ `core/agents/adapters/trader_v2.py`

## 🔧 更新步骤

### 步骤 1: 删除 get_agent_prompt 导入

**修改前**:
```python
# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None
```

**修改后**:
```python
# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法
```

### 步骤 2: 更新 _build_system_prompt 方法

**修改前**:
```python
def _build_system_prompt(self, market_type: str, context=None) -> str:
    # 从模板系统获取提示词
    if get_agent_prompt:
        try:
            template_variables = {
                "market_name": market_type,
                "ticker": "",
                "company_name": "",
            }
            prompt = get_agent_prompt(
                agent_type="analysts_v2",
                agent_name="market_analyst_v2",
                variables=template_variables,
                preference_id="neutral",
                fallback_prompt=None,
                context=context
            )
            if prompt:
                logger.info(f"✅ 从模板系统获取提示词")
                return prompt
        except Exception as e:
            logger.warning(f"从模板系统获取提示词失败: {e}")
    
    # 默认提示词
    return "你是一位专业的分析师..."
```

**修改后**:
```python
def _build_system_prompt(self, market_type: str, context=None) -> str:
    # 使用基类的通用方法从模板系统获取提示词
    template_variables = {
        "market_name": market_type,
        "ticker": "",
        "company_name": "",
    }
    
    prompt = self._get_prompt_from_template(
        agent_type="analysts_v2",
        agent_name="market_analyst_v2",
        variables=template_variables,
        context=context,
        fallback_prompt=None
    )
    
    if prompt:
        return prompt
    
    # 默认提示词
    return "你是一位专业的分析师..."
```

### 步骤 3: 更新 execute 方法中的调用（如果有）

某些 Agent（如 `market_analyst_v2.py`）在 `execute` 方法中也直接调用了 `get_agent_prompt`，需要同样更新。

**修改前**:
```python
system_prompt = system_override
if not system_prompt and get_agent_prompt:
    try:
        system_prompt = get_agent_prompt(...)
    except Exception as e:
        logger.warning(f"获取提示词失败: {e}")
        system_prompt = None
if not system_prompt:
    system_prompt = self._build_system_prompt(market_type)
```

**修改后**:
```python
system_prompt = system_override
if not system_prompt:
    system_prompt = self._get_prompt_from_template(
        agent_type="analysts_v2",
        agent_name="market_analyst_v2",
        variables=template_variables,
        context=context,
        fallback_prompt=None
    )
if not system_prompt:
    system_prompt = self._build_system_prompt(market_type, context=context)
```

## ✅ 验证方法

更新后，检查以下内容：

1. **导入检查**: 确保文件中不再有 `get_agent_prompt` 的导入
2. **方法调用**: 确保所有提示词获取都使用 `self._get_prompt_from_template()`
3. **日志输出**: 运行时应该看到类似的日志：
   ```
   ✅ 从模板系统获取 market_analyst_v2 提示词 (user_id=xxx, preference_id=neutral, 长度=1234)
   ```

## 🎯 预期效果

更新完成后：
1. 用户可以在 `user_template_configs` 集合中配置自己的提示词
2. 系统会自动优先使用用户配置
3. 如果没有用户配置，使用系统默认模板
4. 所有 Agent 的提示词获取逻辑统一，易于维护

## 🔍 常见问题

### Q1: 为什么要统一使用基类方法？

**A**:
1. **避免代码重复**: 每个 Agent 都需要相同的逻辑来获取提示词
2. **统一日志输出**: 便于调试和追踪
3. **自动支持用户配置**: 基类方法自动从 `context` 中提取 `user_id` 和 `preference_id`
4. **易于维护**: 如果需要修改逻辑，只需修改基类

### Q2: context 参数从哪里来？

**A**:
- 在工作流引擎 (`unified_analysis_engine.py`) 中创建
- 包含 `user_id` 和 `preference_id`
- 通过 `workflow_inputs["context"]` 传递给所有 Agent

### Q3: 如果 Agent 不需要用户配置怎么办？

**A**:
- 仍然使用 `_get_prompt_from_template()` 方法
- 如果没有用户配置，会自动降级到系统模板
- 最后降级到代码中的默认提示词

### Q4: 如何测试用户配置是否生效？

**A**:
1. 在 `user_template_configs` 集合中为特定用户添加配置
2. 使用该用户执行工作流
3. 查看日志，应该看到 `user_id=xxx` 的输出
4. 检查生成的报告是否使用了用户配置的提示词

## 📊 迁移进度追踪

| 基类 | 文件数 | 已完成 | 待更新 | 进度 |
|------|--------|--------|--------|------|
| AnalystAgent | 5 | 5 | 0 | 100% ✅ |
| ResearcherAgent | 10 | 0 | 10 | 0% ⏳ |
| ManagerAgent | 4 | 0 | 4 | 0% ⏳ |
| TraderAgent | 1 | 0 | 1 | 0% ⏳ |
| **总计** | **20** | **5** | **15** | **25%** |

## 📚 相关文件

- 基类实现: `core/agents/analyst.py`, `core/agents/researcher.py`, `core/agents/manager.py`, `core/agents/trader.py`
- 工作流引擎: `app/services/unified_analysis_engine.py`
- 模板系统: `tradingagents/utils/template_client.py`
- 数据库集合: `user_template_configs`, `prompt_templates`

## 🚀 批量更新建议

由于需要更新的文件较多，建议：

1. **分批更新**: 按基类分批更新，每次更新一个基类的所有子类
2. **测试验证**: 每批更新后运行测试，确保功能正常
3. **优先级**:
   - 高优先级: ResearcherAgent 子类（bull/bear researcher）
   - 中优先级: ManagerAgent 子类（research/risk manager）
   - 低优先级: 复盘分析和持仓分析相关的 Agent

---

**最后更新**: 2026-01-11
**状态**: 进行中（AnalystAgent 子类已完成，其他待更新）
**维护者**: TradingAgents-CN Pro Team

