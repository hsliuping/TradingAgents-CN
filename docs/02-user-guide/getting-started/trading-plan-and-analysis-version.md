# 交易计划与分析版本选择功能

> 本文档说明交易计划（原"交易计划"）的重命名和操作复盘分析版本选择功能

---

## 📋 功能概述

### 1. 名称变更：交易计划 → 交易计划

**变更原因**：
- "交易计划"容易让用户误解为实盘交易计划
- "交易计划"更符合个人投资者的理解
- 参考基金公司内部系统，类似功能通常称为"投资指引"或"投资约束"

**变更范围**：
- ✅ 前端显示文本（用户可见部分）
- ✅ API 注释和文档
- ⏸️ 代码变量名（保持不变，避免大规模重构）
- ⏸️ API 路径（保持不变，避免破坏现有API）

### 2. 分析版本选择（v1.0 / v2.0）

**功能说明**：
- 用户可以在操作复盘时选择使用哪个版本的分析引擎
- v1.0：传统分析方式（快速，单次LLM调用）
- v2.0：工作流分析方式（深度，多Agent协作）

**适用场景**：
- v1.0：快速复盘，日常使用
- v2.0：深度分析，重要交易复盘

---

## 🎯 使用指南

### 持仓操作复盘对话框

1. **进入复盘页面**
   - 路径：操作复盘 → 持仓操作复盘

2. **选择分析版本**
   - v1.0：传统分析（快速）
   - v2.0：工作流分析（深度）

3. **关联交易计划**（可选）
   - 选择一个已创建的交易计划
   - AI 将根据计划规则进行合规性检查

4. **选择分析维度**
   - 买入时机
   - 卖出时机
   - 仓位管理
   - 止盈止损
   - 心理分析

5. **开始复盘**
   - 点击"开始复盘"按钮
   - 等待 AI 分析完成

---

## 🔧 技术实现

### 后端修改

#### 1. 数据模型 (`app/models/review.py`)

```python
class CreateTradeReviewRequest(BaseModel):
    """创建交易复盘请求"""
    trade_ids: List[str]
    review_type: ReviewType = ReviewType.COMPLETE_TRADE
    code: Optional[str] = None
    source: str = "paper"
    trading_system_id: Optional[str] = None  # 关联的交易计划ID
    use_workflow: Optional[bool] = None  # 是否使用工作流引擎（v2.0）
```

#### 2. 服务层 (`app/services/trade_review_service.py`)

```python
async def _call_ai_trade_review(
    self,
    trade_info: TradeInfo,
    market_snapshot: MarketSnapshot,
    user_id: Optional[str] = None,
    trading_system: Optional[Dict[str, Any]] = None,
    use_workflow: Optional[bool] = None  # 新增参数
) -> AITradeReview:
    # 请求参数优先于环境变量
    should_use_workflow = use_workflow if use_workflow is not None else _use_workflow_review()
    
    if should_use_workflow:
        # 使用 v2.0 工作流引擎
        return await self._call_workflow_trade_review(...)
    else:
        # 使用 v1.0 传统分析
        return await self._build_legacy_trade_review_prompt(...)
```

### 前端修改

#### 1. API 接口 (`frontend/src/api/review.ts`)

```typescript
export interface CreateTradeReviewRequest {
  trade_ids: string[]
  review_type?: ReviewType
  code?: string
  source?: 'real' | 'paper'
  trading_system_id?: string  // 关联的交易计划ID
  use_workflow?: boolean  // 是否使用工作流引擎（v2.0）
}
```

#### 2. 对话框组件 (`frontend/src/views/TradeReview/components/PositionReviewDialog.vue`)

```vue
<el-form-item label="分析版本">
  <el-radio-group v-model="form.analysis_version">
    <el-radio value="v1.0">
      <el-tag size="small" type="info">v1.0</el-tag>
      <span>传统分析（快速）</span>
    </el-radio>
    <el-radio value="v2.0">
      <el-tag size="small" type="success">v2.0</el-tag>
      <span>工作流分析（深度）</span>
    </el-radio>
  </el-radio-group>
</el-form-item>
```

---

## 📊 版本对比

| 特性 | v1.0 传统分析 | v2.0 工作流分析 |
|------|-------------|---------------|
| 分析方式 | 单次LLM调用 | 多Agent协作 |
| 分析深度 | 基础分析 | 深度分析 |
| 分析速度 | 快速（~10秒） | 较慢（~30秒） |
| 提示词来源 | 硬编码 | 数据库模板 |
| 适用场景 | 日常快速复盘 | 重要交易深度分析 |
| 交易计划集成 | ✅ 支持 | ✅ 支持 |

---

## 🔄 后续优化

### 1. v2.0 工作流集成交易计划规则 ✅

**当前状态**：
- ✅ v1.0 已集成交易计划规则（在提示词中直接添加）
- ✅ v2.0 已集成交易计划规则（通过工作流输入注入）

**实现方案**：
- ✅ 在工作流输入中添加 `trading_plan` 字段
- ✅ 包含结构化规则数据和格式化文本
- ✅ 各 Agent 在构建提示词时自动使用规则
- ✅ 不修改数据库中的提示词模板，保持模板通用性

**集成的 Agent**：
- ✅ 时机分析师 v2.0 - 检查择时规则
- ✅ 仓位分析师 v2.0 - 检查仓位规则
- ✅ 复盘总结师 v2.0 - 总结合规性

### 2. 完整重命名

**当前状态**：
- 仅重命名了用户可见的文本
- 代码变量名和API路径保持不变

**后续计划**：
- 逐步重命名代码变量名
- 创建新的API路径，保留旧路径兼容性
- 更新所有文档

---

## 🔍 v2.0 工作流中交易计划规则的集成细节

### 工作流节点结构

```
开始 (start)
  ↓
并行分析开始 (parallel_start)
  ↓
  ├─→ 时机分析师 v2.0 (timing_analyst_v2) ← 使用择时规则
  ├─→ 仓位分析师 v2.0 (position_analyst_v2) ← 使用仓位规则
  ├─→ 情绪分析师 v2.0 (emotion_analyst_v2)
  └─→ 归因分析师 v2.0 (attribution_analyst_v2)
  ↓
合并分析结果 (merge)
  ↓
复盘总结师 v2.0 (review_manager_v2) ← 总结合规性
  ↓
结束 (end)
```

### 规则注入位置

**在工作流输入中注入**（推荐方案）：

```python
# app/services/trade_review_service.py
inputs = {
    "user_id": user_id,
    "trade_ids": [...],
    "trade_info": {...},
    "market_data": {...},
    "benchmark_data": {...},
    "trading_plan": {  # 🆕 交易计划规则
        "plan_id": "...",
        "plan_name": "短线趋势追踪系统",
        "style": "短线",
        "rules": {
            "stock_selection": {...},
            "timing": {
                "entry_signals": ["突破前高", "量价齐升"],
                "exit_signals": ["跌破5日均线", "成交量萎缩"]
            },
            "position": {
                "single_stock_limit": 15,
                "max_stocks": 8
            },
            "risk": {...},
            "discipline": {...}
        },
        "rules_text": "格式化的规则文本"
    },
    "messages": [],
}
```

### Agent 如何使用规则

**时机分析师 v2.0**：
```python
def _build_user_prompt(self, ..., state: Dict[str, Any]) -> str:
    trading_plan = state.get("trading_plan")

    if trading_plan:
        timing_rules = trading_plan.get("rules", {}).get("timing", {})
        prompt += f"""
=== 关联的交易计划 ===
**择时规则**：
- 入场信号: {'; '.join(timing_rules.get('entry_signals', []))}
- 出场信号: {'; '.join(timing_rules.get('exit_signals', []))}

**请在分析中重点检查**：
1. 买入时机是否符合入场信号要求
2. 卖出时机是否符合出场信号要求
3. 如有违反规则的地方，请明确指出
"""
```

**仓位分析师 v2.0**：
```python
def _build_user_prompt(self, ..., state: Dict[str, Any]) -> str:
    trading_plan = state.get("trading_plan")

    if trading_plan:
        position_rules = trading_plan.get("rules", {}).get("position", {})
        prompt += f"""
=== 关联的交易计划 ===
**仓位规则**：
- 单只股票上限: {position_rules.get('single_stock_limit')}%
- 最大持股数: {position_rules.get('max_stocks')}只

**请在分析中重点检查**：
1. 仓位是否超过单只股票上限
2. 加减仓操作是否合理
3. 如有违反规则的地方，请明确指出
"""
```

**复盘总结师 v2.0**：
```python
def _build_user_prompt(self, ..., state: Dict[str, Any]) -> str:
    trading_plan = state.get("trading_plan")

    if trading_plan:
        prompt += f"""
=== 交易计划合规性 ===
本次交易关联了交易计划：**{plan_name}**

请在复盘报告中增加"交易计划合规性"部分，总结：
1. 各维度分析中发现的规则违反情况
2. 合规性总体评价
3. 针对规则违反的改进建议
"""
```

---

## 📝 修改的文件

### 后端
- `app/models/review.py` - 添加 `use_workflow` 字段
- `app/services/trade_review_service.py` - 支持请求级别的版本选择，添加交易计划规则格式化方法
- `core/agents/adapters/review/timing_analyst_v2.py` - 集成择时规则检查
- `core/agents/adapters/review/position_analyst_v2.py` - 集成仓位规则检查
- `core/agents/adapters/review/review_manager_v2.py` - 集成合规性总结

### 前端
- `frontend/src/api/review.ts` - 添加 `use_workflow` 字段
- `frontend/src/views/TradeReview/components/PositionReviewDialog.vue` - 添加版本选择器
- `frontend/src/views/TradingSystem/List.vue` - 更新显示文本

### 文档
- `docs/guides/trading-plan-and-analysis-version.md` - 本文档

