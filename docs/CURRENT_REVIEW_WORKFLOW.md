# 当前持仓分析和交易复盘流程说明

## 📋 目录

1. [交易复盘流程](#交易复盘流程) - 使用 v2.0 工作流
2. [单股持仓分析流程](#单股持仓分析流程) - 先调用单股分析，再使用 v2.0 工作流

---

## 1️⃣ 交易复盘流程

### ✅ 是的，使用的是 v2.0 版本的流程

### 环境变量配置

**文件**：`.env` 第 459-463 行

```env
USE_TEMPLATE_PROMPTS=true
USE_STOCK_ENGINE=true
```

- `USE_TEMPLATE_PROMPTS=true`：启用模板系统生成提示词
- `USE_STOCK_ENGINE=true`：启用工作流引擎进行多维度分析

### 代码逻辑

**文件**：`app/services/trade_review_service.py`

#### 1. 特性开关（第 29-40 行）

```python
def _use_workflow_review() -> bool:
    """动态读取 USE_STOCK_ENGINE 环境变量（复用持仓分析的引擎开关）
    
    当 USE_STOCK_ENGINE=true 时，交易复盘也会使用工作流引擎进行多维度分析
    """
    value = os.getenv("USE_STOCK_ENGINE", "false").lower() == "true"
    return value
```

#### 2. AI 复盘调用（第 597-617 行）

```python
async def _call_ai_trade_review(
    self,
    trade_info: TradeInfo,
    market_snapshot: MarketSnapshot,
    user_id: Optional[str] = None
) -> AITradeReview:
    """调用AI进行交易复盘分析
    
    如果启用工作流引擎（USE_WORKFLOW_REVIEW=true），使用多Agent工作流分析
    否则使用单次LLM调用分析
    """
    # 如果启用工作流引擎，使用多Agent工作流
    if _use_workflow_review():
        try:
            logger.info(f"🔄 [交易复盘] 使用工作流引擎进行多维度分析")
            return await self._call_workflow_trade_review(trade_info, market_snapshot, user_id)
        except Exception as e:
            logger.warning(f"⚠️ [交易复盘] 工作流引擎执行失败，降级到单次LLM调用: {e}")
            # 降级到单次 LLM 调用
```

#### 3. 工作流引擎调用（第 1889-2044 行）

```python
async def _call_workflow_trade_review(
    self,
    trade_info: TradeInfo,
    market_snapshot: MarketSnapshot,
    user_id: Optional[str] = None
) -> AITradeReview:
    """使用工作流引擎进行多维度交易复盘分析
    
    工作流包含:
    1. 时机分析师 - 分析买卖时机
    2. 仓位分析师 - 分析仓位管理
    3. 情绪分析师 - 分析情绪控制
    4. 归因分析师 - 分析收益来源
    5. 复盘总结师 - 综合总结报告
    """
    from core.workflow.engine import WorkflowEngine
    from core.workflow.default_workflow_provider import get_default_workflow_provider
    
    # 1. 加载复盘工作流 (v2.0)
    provider = get_default_workflow_provider()
    workflow = provider.load_workflow("trade_review_v2")  # 🔧 改为 v2.0 工作流
    logger.info(f"✅ [工作流复盘] 加载工作流: {workflow.name}")
```

### 工作流定义

**文件**：`core/workflow/templates/trade_review_workflow_v2.py`

```python
TRADE_REVIEW_WORKFLOW_V2 = WorkflowDefinition(
    id="trade_review_v2",
    name="交易复盘分析流程 v2.0",
    description="基于 v2.0 Agent 架构的交易复盘流程。包含时机分析、仓位分析、情绪分析、归因分析四个专业分析师并行分析，最后由复盘总结师综合生成报告。",
    version="2.0.0",
    is_template=True,
    tags=["v2.0", "复盘", "交易分析", "多维度", "并行分析"],
    nodes=[
        # 开始节点
        NodeDefinition(id="start", type=NodeType.START),
        
        # 并行开始节点
        NodeDefinition(id="parallel_start", type=NodeType.PARALLEL),
        
        # 时机分析师 v2.0
        NodeDefinition(
            id="timing_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="timing_analyst_v2",
            config={"output_field": "timing_analysis"},
        ),
        
        # 仓位分析师 v2.0
        NodeDefinition(
            id="position_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="position_analyst_v2",
            config={"output_field": "position_analysis"},
        ),
        
        # 情绪分析师 v2.0
        NodeDefinition(
            id="emotion_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="emotion_analyst_v2",
            config={"output_field": "emotion_analysis"},
        ),
        
        # 归因分析师 v2.0
        NodeDefinition(
            id="attribution_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="attribution_analyst_v2",
            config={"output_field": "attribution_analysis"},
        ),
        
        # 合并节点
        NodeDefinition(id="merge", type=NodeType.MERGE),
        
        # 复盘总结师 v2.0
        NodeDefinition(
            id="review_manager_v2",
            type=NodeType.MANAGER,
            agent_id="review_manager_v2",
            config={"output_field": "review_summary"},
        ),
        
        # 结束节点
        NodeDefinition(id="end", type=NodeType.END),
    ],
)
```

## 工作流执行流程

```
开始
  ↓
并行分析开始
  ├─→ 时机分析师 v2.0 → timing_analysis
  ├─→ 仓位分析师 v2.0 → position_analysis
  ├─→ 情绪分析师 v2.0 → emotion_analysis
  └─→ 归因分析师 v2.0 → attribution_analysis
  ↓
合并分析结果
  ↓
复盘总结师 v2.0 → review_summary
  ↓
结束
```

### 交易复盘总结

✅ **是的，当前交易复盘使用的是 v2.0 版本的流程**

- **工作流 ID**：`trade_review_v2`
- **工作流名称**：交易复盘分析流程 v2.0
- **版本**：2.0.0
- **分析师数量**：5 个（4 个并行分析师 + 1 个总结师）
- **执行模式**：并行分析 + 综合总结
- **启用条件**：`USE_STOCK_ENGINE=true`

---

## 2️⃣ 单股持仓分析流程

### ✅ 是的，也使用 v2.0 工作流，但有两个阶段

**文件**：`app/services/portfolio_service.py`

### 分析流程（第 2081-2175 行）

```python
async def analyze_position(
    self,
    user_id: str,
    position_id: str,
    params: PositionAnalysisRequest
) -> PositionAnalysisReport:
    """单股持仓分析 - 方案2实现

    流程：
    1. 调用现有单股分析服务获取完整的技术面、基本面、新闻面分析
    2. 将分析报告 + 持仓信息发给持仓分析专用LLM
    3. 生成个性化的持仓操作建议
    """

    # 第一阶段：调用现有单股分析获取详细报告
    logger.info(f"📊 [持仓分析] 第一阶段：调用单股分析服务 - {position.code}")
    stock_analysis_report = await self._get_stock_analysis_report(
        user_id=user_id,
        stock_code=position.code,
        market=market_name
    )

    # 第二阶段：结合持仓信息进行持仓分析
    logger.info(f"📊 [持仓分析] 第二阶段：持仓专用分析 - {position.code}")

    # 根据配置选择分析引擎（USE_STOCK_ENGINE=true 时使用工作流引擎v2.0）
    if _use_stock_engine():
        logger.info(f"🚀 [持仓分析] 使用工作流引擎v2.0进行分析")
        ai_result = await self._call_position_ai_analysis_workflow(
            snapshot=snapshot,
            params=params,
            stock_analysis_report=stock_analysis_report,  # ← 传入单股分析结果
            user_id=user_id
        )
    else:
        logger.info(f"🤖 [持仓分析] 使用传统LLM分析")
        ai_result = await self._call_position_ai_analysis_v2(
            snapshot=snapshot,
            params=params,
            stock_analysis_report=stock_analysis_report,  # ← 传入单股分析结果
            user_id=user_id
        )
```

### 第一阶段：获取单股分析报告（第 2532-2714 行）

```python
async def _get_stock_analysis_report(
    self,
    user_id: str,
    stock_code: str,
    market: str = "A股"
) -> Dict[str, Any]:
    """获取股票的完整分析报告

    复用现有的单股分析服务，获取技术面、基本面、新闻面等完整分析
    优化：
    1. 如果启用新引擎(USE_STOCK_ENGINE=true)，优先使用StockAnalysisEngine
    2. 先检查3小时内是否有已完成的分析报告（任意用户），直接复用
    3. 检查是否有正在运行的任务，避免重复创建
    4. 如果都没有，才创建新的分析任务
    """
    # 如果启用新引擎，优先尝试使用 StockAnalysisEngine
    if _use_stock_engine():
        engine_result = await self._get_stock_analysis_via_engine(stock_code, market)
        if engine_result:
            return engine_result
        logger.warning(f"⚠️ [持仓分析] StockAnalysisEngine 调用失败，降级到旧版服务")

    # 降级到旧版 simple_analysis_service
    return await self._get_stock_analysis_via_legacy(user_id, stock_code, market)
```

**StockAnalysisEngine** 调用（第 2556-2631 行）：
```python
async def _get_stock_analysis_via_engine(
    self,
    stock_code: str,
    market: str = "A股"
) -> Optional[Dict[str, Any]]:
    """通过 StockAnalysisEngine 获取分析报告"""
    try:
        from tradingagents.core.engine.stock_analysis_engine import StockAnalysisEngine

        engine = StockAnalysisEngine(llm=llm, use_stub=False)
        result = engine.analyze(
            ticker=stock_code,
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            market_type=market_type
        )

        # 返回包含技术面、基本面、新闻面等完整分析的报告
        return {
            "task_id": "engine",
            "source": "stock_analysis_engine",
            "reports": reports,
            "decision": result.final_decision,
            "summary": result.summary,
            "recommendation": result.recommendation
        }
```

### 第二阶段：持仓分析工作流（第 3450-3526 行）

```python
async def _call_position_ai_analysis_workflow(
    self,
    snapshot: PositionSnapshot,
    params: PositionAnalysisRequest,
    stock_analysis_report: Dict[str, Any],  # ← 接收单股分析结果
    user_id: Optional[str] = None
) -> PositionAnalysisResult:
    """使用工作流引擎进行持仓分析

    使用持仓分析工作流，包含：
    1. 持仓技术面分析师 - 分析技术指标和走势
    2. 持仓基本面分析师 - 分析财务数据和估值
    3. 持仓风险评估师 - 评估风险和止损建议
    4. 持仓操作建议师 - 综合分析给出操作建议
    """
    from core.api.workflow_api import WorkflowAPI

    # 准备工作流输入（包含单股分析报告）
    workflow_inputs = {
        "position_snapshot": snapshot.model_dump(),
        "stock_analysis_report": stock_analysis_report,  # ← 传入单股分析结果
        "user_preferences": params.model_dump(),
        # ...
    }

    # 执行工作流
    workflow_api = WorkflowAPI()
    result = await workflow_api.execute(
        workflow_id="position_analysis",  # ← 使用持仓分析工作流
        inputs=workflow_inputs
    )
```

### 持仓分析工作流定义

**文件**：`core/workflow/templates/position_analysis_workflow_v2.py`

```python
POSITION_ANALYSIS_WORKFLOW_V2 = WorkflowDefinition(
    id="position_analysis_v2",
    name="持仓分析流程 v2.0",
    description="基于 v2.0 Agent 架构的持仓分析流程。包含技术面分析、基本面分析、风险评估三个专业分析师并行分析，最后由操作建议师综合生成操作建议。",
    version="2.0.0",
    is_template=True,
    tags=["v2.0", "持仓", "分析", "多维度", "操作建议"],
    nodes=[
        # 开始节点
        NodeDefinition(id="start", type=NodeType.START),

        # 并行开始节点
        NodeDefinition(id="parallel_start", type=NodeType.PARALLEL),

        # 持仓技术面分析师 v2.0
        NodeDefinition(
            id="pa_technical_v2",
            type=NodeType.ANALYST,
            agent_id="pa_technical_v2",
            config={"output_field": "technical_analysis"},
        ),

        # 持仓基本面分析师 v2.0
        NodeDefinition(
            id="pa_fundamental_v2",
            type=NodeType.ANALYST,
            agent_id="pa_fundamental_v2",
            config={"output_field": "fundamental_analysis"},
        ),

        # 持仓风险评估师 v2.0
        NodeDefinition(
            id="pa_risk_v2",
            type=NodeType.ANALYST,
            agent_id="pa_risk_v2",
            config={"output_field": "risk_analysis"},
        ),

        # 合并节点
        NodeDefinition(id="merge", type=NodeType.MERGE),

        # 持仓操作建议师 v2.0
        NodeDefinition(
            id="pa_advisor_v2",
            type=NodeType.MANAGER,
            agent_id="pa_advisor_v2",
            config={"output_field": "action_advice"},
        ),

        # 结束节点
        NodeDefinition(id="end", type=NodeType.END),
    ],
)
```

### 持仓分析执行流程

```
第一阶段：单股分析
  ↓
StockAnalysisEngine.analyze()
  ├─→ 技术面分析
  ├─→ 基本面分析
  ├─→ 新闻面分析
  └─→ 综合决策
  ↓
第二阶段：持仓分析工作流 v2.0
  ↓
并行分析开始
  ├─→ 持仓技术面分析师 v2.0 → technical_analysis
  ├─→ 持仓基本面分析师 v2.0 → fundamental_analysis
  └─→ 持仓风险评估师 v2.0 → risk_analysis
  ↓
合并分析结果
  ↓
持仓操作建议师 v2.0 → action_advice
  ↓
结束
```

### 持仓分析总结

✅ **是的，单股持仓分析也使用 v2.0 工作流，但分为两个阶段**

**第一阶段：单股分析**
- **引擎**：`StockAnalysisEngine`（如果启用）或旧版 `simple_analysis_service`
- **目的**：获取股票的技术面、基本面、新闻面等完整分析
- **优化**：复用 3 小时内的分析报告，避免重复调用

**第二阶段：持仓分析工作流 v2.0**
- **工作流 ID**：`position_analysis_v2`
- **工作流名称**：持仓分析流程 v2.0
- **版本**：2.0.0
- **分析师数量**：4 个（3 个并行分析师 + 1 个操作建议师）
- **输入**：单股分析报告 + 持仓信息（成本、持仓天数、仓位占比等）
- **输出**：个性化的操作建议（加仓/减仓/止损/持有）
- **执行模式**：并行分析 + 综合建议
- **启用条件**：`USE_STOCK_ENGINE=true`

**关键区别**：
- **交易复盘**：直接使用工作流分析交易记录
- **持仓分析**：先获取单股分析报告，再结合持仓信息使用工作流分析

---

## 📊 总结对比

| 功能 | 工作流版本 | 分析师数量 | 是否先调用单股分析 | 启用条件 |
|------|-----------|-----------|------------------|---------|
| **交易复盘** | v2.0 (`trade_review_v2`) | 5 个 | ❌ 否 | `USE_STOCK_ENGINE=true` |
| **单股持仓分析** | v2.0 (`position_analysis_v2`) | 4 个 | ✅ 是 | `USE_STOCK_ENGINE=true` |

**共同点**：
- 都使用 v2.0 工作流架构
- 都采用并行分析 + 综合总结的模式
- 都由 `USE_STOCK_ENGINE=true` 环境变量控制

**不同点**：
- 持仓分析需要先获取单股分析报告（技术面、基本面、新闻面）
- 持仓分析会结合用户的持仓信息（成本、天数、仓位占比）给出个性化建议

