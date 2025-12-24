# v2.0 复盘分析 - 交易计划规则集成完整方案

## 📋 概述

本文档说明了如何在 v2.0 复盘分析工作流中完整集成交易计划规则检查功能。

## 🎯 目标

- ✅ 在 v2.0 工作流的所有分析节点中集成交易计划规则
- ✅ 使用数据库提示词模板系统（而不是硬编码）
- ✅ 兼容有交易计划和无交易计划两种情况
- ✅ 保持模板的通用性和可维护性

## 🏗️ 架构设计

### 1. 数据库模板结构

**旧模板问题**：
- ❌ 包含股票分析相关的占位符（`{company_name}`, `{market_name}`, `{currency_symbol}`等）
- ❌ 分析要求太通用（"提供保守的分析视角"）
- ❌ 缺少交易计划规则占位符
- ❌ 有3种偏好（conservative/neutral/aggressive），但复盘应该是客观的

**新模板设计**：
- ✅ 只包含复盘相关的内容
- ✅ 具体的分析要点（买入时机、卖出时机、最优点差距等）
- ✅ 包含 `{trading_plan_section}` 占位符
- ✅ 只有 neutral 偏好（复盘应该是客观中立的）

### 2. 模板变量注入机制

```
工作流输入 (state)
  ↓
  包含 trading_plan 字段
  ↓
Agent.execute(state)
  ↓
  保存 state 到 self._current_state
  ↓
Agent._build_system_prompt()
  ↓
  从 self._current_state 获取 trading_plan
  ↓
  构建 trading_plan_section 文本
  ↓
  调用 get_agent_prompt(variables={'trading_plan_section': ...})
  ↓
  模板系统替换 {trading_plan_section} 占位符
  ↓
  返回完整的系统提示词
```

### 3. Agent 代码结构

每个 Agent 都需要：

1. **重写 `__init__()` 方法**：
   ```python
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       self._current_state = None
   ```

2. **重写 `execute()` 方法**：
   ```python
   def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
       self._current_state = state
       try:
           return super().execute(state)
       finally:
           self._current_state = None
   ```

3. **修改 `_build_system_prompt()` 方法**：
   ```python
   def _build_system_prompt(self, stance: str) -> str:
       # 从 state 获取交易计划
       trading_plan = None
       if self._current_state:
           trading_plan = self._current_state.get('trading_plan')
       
       # 构建交易计划规则文本
       trading_plan_section = ''
       if trading_plan:
           # ... 构建规则文本 ...
       
       # 调用模板系统
       if get_agent_prompt:
           variables = {'trading_plan_section': trading_plan_section}
           prompt = get_agent_prompt(..., variables=variables, ...)
           return prompt
       
       # 降级提示词也要包含交易计划规则
       return fallback_prompt + trading_plan_section
   ```

4. **简化 `_build_user_prompt()` 方法**：
   - 移除交易计划规则的硬编码
   - 只包含交易数据
   - 交易计划规则已经在系统提示词中

## 📊 涉及的 Agent

### 1. 时机分析师 v2.0 (timing_analyst_v2)

**交易计划规则**：
- 入场信号
- 出场信号

**检查要点**：
1. 买入时机是否符合入场信号要求
2. 卖出时机是否符合出场信号要求
3. 如有违反规则的地方，请明确指出

### 2. 仓位分析师 v2.0 (position_analyst_v2)

**交易计划规则**：
- 单只股票上限
- 最大持股数

**检查要点**：
1. 仓位是否超过单只股票上限
2. 加减仓操作是否合理
3. 如有违反规则的地方，请明确指出

### 3. 复盘总结师 v2.0 (review_manager_v2)

**交易计划规则**：
- 综合各维度的规则违反情况

**检查要点**：
1. 各维度分析中发现的规则违反情况
2. 合规性总体评价
3. 针对规则违反的改进建议

## 🔧 实施步骤

### 步骤 1：删除旧模板并创建新模板

运行脚本：
```bash
python scripts/create_review_templates.py
```

结果：
- 删除 15 个旧模板（5个Agent × 3种偏好）
- 创建 5 个新模板（5个Agent × 1种偏好neutral）

### 步骤 2：修改 Agent 代码

修改以下文件：
- `core/agents/adapters/review/timing_analyst_v2.py`
- `core/agents/adapters/review/position_analyst_v2.py`
- `core/agents/adapters/review/review_manager_v2.py`

### 步骤 3：测试

1. 创建一个交易计划
2. 进行一笔模拟交易
3. 进入操作复盘页面
4. 选择 v2.0 分析版本
5. 选择交易计划
6. 开始复盘
7. 查看分析结果中是否包含交易计划规则检查

## ✅ 验证清单

- [ ] 数据库中有 5 个新的复盘专用模板
- [ ] 所有模板都包含 `{trading_plan_section}` 占位符
- [ ] 所有模板都是 neutral 偏好
- [ ] 所有 Agent 都重写了 `execute()` 方法
- [ ] 所有 Agent 的 `_build_system_prompt()` 都支持交易计划规则注入
- [ ] 所有 Agent 的 `_build_user_prompt()` 都移除了重复的交易计划规则
- [ ] v2.0 复盘分析结果中包含交易计划规则检查

## 📝 注意事项

1. **模板优先级**：数据库模板 > 降级提示词
2. **变量注入**：通过 `get_agent_prompt()` 的 `variables` 参数传递
3. **占位符格式**：`{trading_plan_section}`（单层大括号）
4. **兼容性**：没有交易计划时，`trading_plan_section` 为空字符串
5. **日志输出**：系统提示词中会显示是否包含交易计划规则

## 🎉 完成

现在 v2.0 复盘分析完整支持交易计划规则检查！

