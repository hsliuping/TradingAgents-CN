# 交易复盘流程任务中心集成设计

## 📋 文档信息

- **版本**: v1.1
- **创建日期**: 2025-12-31
- **最后更新**: 2025-12-31
- **作者**: AI Assistant
- **状态**: 已实现

## 🔄 更新记录

### v1.1 (2025-12-31)
- ✅ 移除传统同步模式选项
- ✅ 统一使用任务中心模式
- ✅ 简化用户选择，提升用户体验

## 🎯 设计目标

将交易复盘流程（Trade Review）完全纳入任务中心（Task Center）管理，实现：

1. **统一任务管理**: 复盘任务与股票分析任务使用相同的任务模型和管理机制
2. **实时进度跟踪**: 前端可以实时查询复盘任务的执行进度（当前无法查询）
3. **任务历史记录**: 所有复盘任务都有完整的执行记录和状态追踪
4. **统一执行模式**: 所有复盘任务统一使用任务中心模式（已移除传统同步模式）
5. **统一错误处理**: 统一的异常处理和错误恢复机制

## 💡 设计决策：移除传统模式

**决策**: 交易复盘统一使用任务中心模式，移除传统同步模式选项

**理由**:
1. **简化用户体验**: 用户不需要在"传统分析"和"工作流分析"之间选择
2. **统一架构**: 所有分析任务（持仓分析、交易复盘）都使用相同的任务管理机制
3. **更好的可观测性**: 所有任务都可以通过统一的API查询进度和状态
4. **避免混淆**: 两种模式并存容易让用户困惑，不知道选择哪个
5. **维护成本**: 减少代码分支，降低维护复杂度

**影响**:
- ✅ 前端UI更简洁，移除"分析本"选择
- ✅ 所有复盘任务都支持进度查询
- ✅ 统一的任务管理和监控
- ⚠️ 所有复盘都是异步执行（但这是更好的用户体验）

## ⚠️ 当前问题

**核心问题：v2.0 复盘流程虽然使用了工作流引擎，但没有纳入任务中心管理，导致：**

1. ❌ **无法查询进度**：前端无法实时查询复盘任务的执行进度
2. ❌ **无任务记录**：复盘任务不在 `unified_analysis_tasks` 集合中
3. ❌ **无内存状态**：没有使用 `MemoryStateManager` 管理任务状态
4. ❌ **进度回调丢失**：工作流执行时的进度回调没有保存到数据库
5. ❌ **无法取消任务**：无法通过任务中心取消正在执行的复盘任务

## 📊 当前架构分析

### 当前复盘流程（v2.0 with use_workflow=true）

```
用户请求 (POST /api/review/trade)
  {use_workflow: true, trade_ids: [...]}
  ↓
ReviewRouter (app/routers/review.py)
  ↓
TradeReviewService.create_trade_review()
  ├─ 获取交易记录 (_get_trade_records)
  ├─ 构建交易信息 (_build_trade_info)
  ├─ 获取市场快照 (_get_market_snapshot)
  ├─ 获取交易计划 (_get_trading_system)
  ├─ 创建初始报告 (trade_reviews 集合)
  ↓
_call_ai_trade_review(use_workflow=True)
  ├─ 判断 should_use_workflow = True
  ↓
_call_workflow_trade_review()
  ├─ 加载工作流 (trade_review_v2)
  ├─ 准备输入数据
  ├─ 执行工作流 (WorkflowEngine.execute())
  │   ├─ 时机分析师 (20%)
  │   ├─ 仓位分析师 (40%)
  │   ├─ 情绪分析师 (60%)
  │   ├─ 归因分析师 (80%)
  │   └─ 复盘总结师 (95%)
  ├─ 解析结果
  └─ 返回 AITradeReview
  ↓
更新 trade_reviews 集合
  ├─ ai_review
  ├─ status = COMPLETED
  └─ execution_time
  ↓
返回 TradeReviewResponse
  {review_id, status, ai_review, ...}
  ❌ 没有 task_id
```

**关键问题：**
- ❌ 没有创建 `UnifiedAnalysisTask`
- ❌ 没有使用 `TaskAnalysisService`
- ❌ 没有使用 `MemoryStateManager`
- ❌ 工作流进度回调没有保存到数据库
- ❌ 前端无法通过 `/api/tasks/{task_id}/progress` 查询进度

### 任务中心架构（股票分析）

```
用户请求 (POST /api/analysis/stock)
  {code: "688111", analysis_type: "comprehensive"}
  ↓
AnalysisRouter (app/routers/analysis.py)
  ↓
TaskAnalysisService.create_and_execute_task()
  ├─ 创建任务 (unified_analysis_tasks 集合)
  │   └─ task_id, task_type, task_params, status=PENDING
  ├─ 创建内存状态 (MemoryStateManager)
  │   └─ 计算预估时长、初始化进度
  ↓
UnifiedAnalysisEngine.execute_task()
  ├─ 获取工作流配置 (AnalysisWorkflowRegistry)
  ├─ 选择执行引擎 (workflow/legacy/llm)
  ├─ 执行分析 (带进度回调)
  │   ├─ 每个步骤更新进度
  │   ├─ 保存到 MongoDB (unified_analysis_tasks)
  │   └─ 保存到内存 (MemoryStateManager)
  ↓
保存结果
  ├─ unified_analysis_tasks 集合 (result 字段)
  └─ analysis_reports 集合 (兼容旧版)
  ↓
返回 UnifiedAnalysisTask
  {task_id, status, progress, result, ...}
```

**前端可以实时查询进度：**
```
GET /api/tasks/{task_id}/progress
→ {progress: 65, current_step: "基本面分析师", message: "..."}
```

### 关键差异对比

| 维度 | 当前复盘流程 (v2.0) | 任务中心 (股票分析) |
|------|---------------------|---------------------|
| **任务模型** | TradeReviewReport | UnifiedAnalysisTask |
| **数据库集合** | trade_reviews | unified_analysis_tasks |
| **进度跟踪** | ❌ 无（工作流内部有，但不保存） | ✅ 实时进度 + 内存状态 |
| **任务查询** | ❌ 只能通过 review_id 查结果 | ✅ 通过 task_id 查进度和结果 |
| **引擎选择** | ✅ 硬编码判断 (use_workflow) | ✅ 配置化 (AnalysisWorkflowRegistry) |
| **状态管理** | ReviewStatus (PROCESSING/COMPLETED/FAILED) | AnalysisStatus + TaskStatus |
| **错误处理** | 简单 try-catch | 统一异常处理 + 状态回滚 |
| **工作流引擎** | ✅ WorkflowEngine (trade_review_v2) | ✅ WorkflowEngine (多种工作流) |
| **进度回调** | ❌ 有回调但不保存 | ✅ 回调保存到 DB + 内存 |
| **任务取消** | ❌ 不支持 | ✅ 支持 (DELETE /api/tasks/{task_id}) |

## 🏗️ 集成设计

### 设计方案：双层架构

采用**双层架构**，保持复盘业务逻辑独立，同时纳入任务中心管理：

```
┌─────────────────────────────────────────────────────────────┐
│                     API 层 (Review Router)                   │
│                  POST /api/review/trade                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  业务层 (TradeReviewService)                 │
│  - 交易记录获取                                               │
│  - 交易信息构建                                               │
│  - 市场快照获取                                               │
│  - 交易计划关联                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              任务层 (TaskAnalysisService)                    │
│  - 创建统一任务 (UnifiedAnalysisTask)                        │
│  - 注册内存状态 (MemoryStateManager)                         │
│  - 执行任务 (带进度回调)                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              引擎层 (UnifiedAnalysisEngine)                  │
│  - 工作流引擎 (WorkflowEngine)                               │
│  - 传统引擎 (Legacy)                                         │
│  - LLM 引擎 (Direct LLM)                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    存储层 (MongoDB)                          │
│  - unified_analysis_tasks (任务记录)                         │
│  - trade_reviews (复盘报告)                                  │
│  - memory_state (内存状态)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **最小侵入**: 保持现有 TradeReviewService 的业务逻辑不变
2. **渐进式迁移**: 支持新旧两种模式并存，通过参数控制
3. **向后兼容**: 保持现有 API 接口和数据结构不变
4. **统一管理**: 所有任务都通过 TaskAnalysisService 管理
5. **复用现有工作流**: 继续使用 `trade_review_v2` 工作流，只是改为通过任务中心调用

### 改造策略

**参考实现：持仓分析和单股分析的集成模式**

#### 标准集成模式（参考 `app/routers/portfolio.py` 和 `app/routers/analysis.py`）

```python
# 1. 路由层：创建任务 + 后台执行
@router.post("/api/review/trade")
async def create_trade_review(request, user):
    # 1.1 创建任务（立即返回）
    result = await unified_service.create_trade_review_task(
        user_id=user["id"],
        request=request
    )

    # 1.2 后台执行任务
    asyncio.create_task(
        unified_service.execute_trade_review(
            task_id=result["task_id"],
            user_id=user["id"],
            request=request
        )
    )

    # 1.3 立即返回任务ID
    return {"task_id": result["task_id"], "status": "pending"}

# 2. 服务层：创建任务
async def create_trade_review_task(user_id, request):
    # 2.1 创建 UnifiedAnalysisTask
    task = UnifiedAnalysisTask(
        task_id=uuid.uuid4(),
        user_id=user_id,
        task_type=AnalysisTaskType.TRADE_REVIEW,
        task_params={...},
        status=AnalysisStatus.PENDING
    )

    # 2.2 保存到 unified_analysis_tasks
    await db.unified_analysis_tasks.insert_one(task.model_dump())

    # 2.3 保存到内存状态管理器
    await memory_manager.create_task(task_id, user_id, ...)

    return {"task_id": task.task_id}

# 3. 服务层：执行任务
async def execute_trade_review(task_id, user_id, request):
    # 3.1 更新状态为 PROCESSING
    await self._update_task_status(task_id, AnalysisStatus.PROCESSING)

    # 3.2 调用现有的复盘逻辑
    report = await trade_review_service.create_trade_review(user_id, request)

    # 3.3 更新任务结果
    await self._update_task_status(
        task_id,
        AnalysisStatus.COMPLETED,
        result={"ai_review": report.ai_review.model_dump()}
    )
```

**关键改动：**
1. ✅ **路由层**：在 `app/routers/review.py` 中添加新的路由逻辑
2. ✅ **服务层**：在 `app/services/unified_analysis_service.py` 中添加 `create_trade_review_task()` 和 `execute_trade_review()` 方法
3. ✅ **保持兼容**：现有的 `TradeReviewService.create_trade_review()` 方法保持不变
4. ✅ **统一管理**：所有任务都通过 `unified_analysis_tasks` 集合管理

## 📝 详细设计

### 1. 任务类型注册

#### 1.1 扩展 AnalysisTaskType 枚举

```python
# app/models/analysis.py

class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    STOCK_ANALYSIS = "stock_analysis"
    POSITION_ANALYSIS = "position_analysis"
    TRADE_REVIEW = "trade_review"  # ✅ 新增
    PERIODIC_REVIEW = "periodic_review"  # ✅ 新增（阶段性复盘）
    BATCH_ANALYSIS = "batch_analysis"
```

#### 1.2 注册工作流配置

在 `AnalysisWorkflowRegistry` 中注册交易复盘任务类型：

```python
# app/services/workflow_registry.py

AnalysisWorkflowRegistry.register(AnalysisWorkflowConfig(
    task_type=AnalysisTaskType.TRADE_REVIEW,
    workflow_id="trade_review_v2",  # 使用现有的 v2.0 工作流
    required_params=["review_id", "code", "trade_info", "market_snapshot"],
    optional_params={
        "trading_system_id": None,
        "trading_system": None,
        "user_id": None,
        "benchmark_data": {}
    },
    timeout=600,  # 10分钟超时
    description="交易复盘分析，包含时机、仓位、情绪、归因四个维度"
))
```

**注意：** 这里复用现有的 `trade_review_v2` 工作流，不需要创建新的工作流
```

### 2. 数据模型扩展

#### 2.1 UnifiedAnalysisTask 扩展

```python
# app/models/analysis.py

class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    STOCK_ANALYSIS = "stock_analysis"
    POSITION_ANALYSIS = "position_analysis"
    TRADE_REVIEW = "trade_review"  # ✅ 新增
    PERIODIC_REVIEW = "periodic_review"  # ✅ 新增（阶段性复盘）
    BATCH_ANALYSIS = "batch_analysis"
```

#### 2.2 任务参数结构

```python
# 交易复盘任务参数
task_params = {
    "review_id": "uuid",
    "code": "688111",
    "name": "金山办公",
    "market": "cn",
    "trade_info": {
        "code": "688111",
        "name": "金山办公",
        "holding_days": 10,
        "realized_pnl": 1500.0,
        "realized_pnl_pct": 5.2,
        "avg_buy_price": 100.0,
        "avg_sell_price": 105.2,
        "trades": [...]
    },
    "market_snapshot": {
        "kline_data": [...],
        "period_high": 110.0,
        "period_low": 95.0
    },
    "trading_system_id": "694bc27bd639700ce1d9dbea",  # 可选
    "trading_system": {...},  # 可选
    "user_id": "user_123"
}
```

### 3. 服务层改造

#### 3.1 UnifiedAnalysisService 扩展（参考持仓分析实现）

**文件**：`app/services/unified_analysis_service.py`

```python
# app/services/unified_analysis_service.py

class UnifiedAnalysisService:

    # ==================== 交易复盘相关方法 ====================

    async def create_trade_review_task(
        self,
        user_id: str,
        request: CreateTradeReviewRequest
    ) -> Dict[str, Any]:
        """创建交易复盘任务

        参考：create_position_analysis_task() 的实现

        Args:
            user_id: 用户ID
            request: 复盘请求

        Returns:
            任务信息字典 {"task_id": "...", "status": "pending"}
        """
        from bson import ObjectId

        task_id = str(uuid.uuid4())
        logger.info(f"📝 [交易复盘服务] 生成任务ID: {task_id}")

        # 准备任务参数
        task_params = {
            "trade_ids": request.trade_ids,
            "code": request.code,
            "review_type": request.review_type,
            "source": request.source or "paper",
            "trading_system_id": request.trading_system_id,
            "use_workflow": request.use_workflow
        }

        # 创建统一分析任务
        task = UnifiedAnalysisTask(
            task_id=task_id,
            user_id=ObjectId(user_id),
            task_type=AnalysisTaskType.TRADE_REVIEW,
            task_params=task_params,
            engine_type="workflow" if request.use_workflow else "auto",
            status=AnalysisStatus.PENDING,
            created_at=now_tz()
        )

        # 保存到数据库
        await self.db.unified_analysis_tasks.insert_one(
            task.model_dump(by_alias=True, exclude={"id"})
        )
        logger.info(f"✅ [交易复盘服务] 任务已保存到数据库: {task_id}")

        # 保存到内存状态管理器
        from app.services.memory_state_manager import get_memory_state_manager
        memory_manager = get_memory_state_manager()
        await memory_manager.create_task(
            task_id=task_id,
            user_id=user_id,
            stock_code=request.code,
            stock_name=None,  # 可以后续补充
            parameters=task_params
        )
        logger.info(f"✅ [交易复盘服务] 任务已保存到内存: {task_id}")

        return {
            "task_id": task_id,
            "status": AnalysisStatus.PENDING.value,
            "created_at": task.created_at.isoformat()
        }

    async def execute_trade_review(
        self,
        task_id: str,
        user_id: str,
        request: CreateTradeReviewRequest,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """执行交易复盘任务

        参考：execute_position_analysis() 的实现

        Args:
            task_id: 任务ID
            user_id: 用户ID
            request: 复盘请求
            progress_callback: 进度回调函数

        Returns:
            分析结果字典
        """
        logger.info(f"🚀 [交易复盘服务] execute_trade_review 被调用: task_id={task_id}")

        try:
            # 更新任务状态为处理中
            await self._update_task_status(
                task_id=task_id,
                status=AnalysisStatus.PROCESSING,
                message="正在进行交易复盘..."
            )

            # 调用现有的复盘服务
            from app.services.trade_review_service import get_trade_review_service
            trade_review_service = get_trade_review_service()

            # 执行复盘（使用现有逻辑）
            report = await trade_review_service.create_trade_review(
                user_id=user_id,
                request=request
            )

            # 格式化结果
            result = {
                "success": True,
                "task_id": task_id,
                "review_id": report.review_id,
                "code": report.trade_info.code,
                "name": report.trade_info.name,
                "ai_review": report.ai_review.model_dump() if report.ai_review else None,
                "trade_info": report.trade_info.model_dump(),
                "market_snapshot": report.market_snapshot.model_dump() if report.market_snapshot else None,
                "status": report.status.value,
                "execution_time": report.execution_time
            }

            # 更新任务状态为完成
            await self._update_task_status(
                task_id=task_id,
                status=AnalysisStatus.COMPLETED,
                result=result,
                message="复盘完成"
            )

            logger.info(f"✅ [交易复盘服务] 任务执行成功: {task_id}")
            return result

        except Exception as e:
            logger.error(f"❌ [交易复盘服务] 任务执行失败: {task_id} - {e}", exc_info=True)

            # 更新任务状态为失败
            await self._update_task_status(
                task_id=task_id,
                status=AnalysisStatus.FAILED,
                error_message=str(e),
                message=f"复盘失败: {str(e)}"
            )

            raise

    async def _update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        message: Optional[str] = None,
        progress: Optional[int] = None
    ):
        """更新任务状态

        参考：_update_position_task_status() 的实现
        """
        update_data = {
            "status": status.value,
            "updated_at": now_tz()
        }

        if result is not None:
            update_data["result"] = result
            update_data["completed_at"] = now_tz()

        if error_message is not None:
            update_data["error_message"] = error_message

        if message is not None:
            update_data["message"] = message

        if progress is not None:
            update_data["progress"] = progress

        # 更新数据库
        await self.db.unified_analysis_tasks.update_one(
            {"task_id": task_id},
            {"$set": update_data}
        )

        # 更新内存状态
        from app.services.memory_state_manager import get_memory_state_manager
        memory_manager = get_memory_state_manager()

        if status == AnalysisStatus.PROCESSING:
            await memory_manager.update_progress(
                task_id=task_id,
                progress=progress or 0,
                message=message or "处理中..."
            )
        elif status == AnalysisStatus.COMPLETED:
            await memory_manager.complete_task(
                task_id=task_id,
                result=result
            )
        elif status == AnalysisStatus.FAILED:
            await memory_manager.fail_task(
                task_id=task_id,
                error=error_message or "未知错误"
            )
```

#### 3.2 TradeReviewService 保持不变

**关键点**：现有的 `TradeReviewService.create_trade_review()` 方法**完全不需要修改**，继续使用现有逻辑。

```python
# app/services/trade_review_service.py

class TradeReviewService:

    async def create_trade_review(
        self,
        user_id: str,
        request: CreateTradeReviewRequest
    ) -> TradeReviewResponse:
        """创建交易复盘

        ✅ 保持现有逻辑不变
        ✅ 继续使用 _call_ai_trade_review()
        ✅ 继续使用 _call_workflow_trade_review()
        """
        # ... 现有逻辑保持不变 ...
```

### 4. 引擎层适配

#### 4.1 UnifiedAnalysisEngine 扩展

```python
# app/services/unified_analysis_engine.py

class UnifiedAnalysisEngine:

    async def _execute_via_workflow(
        self,
        task: UnifiedAnalysisTask,
        config: AnalysisWorkflowConfig,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """通过工作流引擎执行任务"""

        # 对于交易复盘任务，使用特殊处理
        if task.task_type == AnalysisTaskType.TRADE_REVIEW:
            return await self._execute_trade_review_workflow(
                task, config, progress_callback
            )

        # 其他任务类型的处理...
        ...

    async def _execute_trade_review_workflow(
        self,
        task: UnifiedAnalysisTask,
        config: AnalysisWorkflowConfig,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """执行交易复盘工作流"""
        from core.workflow.engine import WorkflowEngine
        from core.workflow.default_workflow_provider import get_default_workflow_provider

        # 1. 加载工作流
        provider = get_default_workflow_provider()
        workflow = provider.load_workflow(config.workflow_id)

        # 2. 准备工作流输入
        trade_info = task.task_params.get("trade_info", {})
        market_snapshot = task.task_params.get("market_snapshot", {})
        trading_system = task.task_params.get("trading_system")

        inputs = {
            "user_id": task.task_params.get("user_id"),
            "trade_ids": [t["trade_id"] for t in trade_info.get("trades", [])],
            "trade_info": trade_info,
            "market_data": {
                "kline_data": market_snapshot.get("kline_data", []),
                "period_high": market_snapshot.get("period_high", 0.0),
                "period_low": market_snapshot.get("period_low", 0.0),
                "summary": f"持仓期间最高价: {market_snapshot.get('period_high', 'N/A')}"
            },
            "messages": []
        }

        # 添加交易计划信息（如果有）
        if trading_system:
            inputs["trading_system"] = trading_system

        # 3. 执行工作流
        engine = WorkflowEngine()
        engine.load(workflow)

        # 包装进度回调
        def wrapped_callback(progress: int, message: str, step_name: str = ""):
            if progress_callback:
                progress_callback(progress, message, step_name=step_name)

        result = engine.execute(inputs, progress_callback=wrapped_callback)

        # 4. 提取 AI 复盘结果
        review_summary = result.get("review_summary", "")

        # 解析 JSON 格式的复盘总结
        import json
        try:
            summary_data = json.loads(review_summary.strip("```json").strip("```").strip())
        except:
            summary_data = {}

        # 5. 构建 AI 复盘对象
        ai_review = {
            "overall_score": summary_data.get("overall_score", 0),
            "timing_score": summary_data.get("timing_score", 0),
            "position_score": summary_data.get("position_score", 0),
            "emotion_score": summary_data.get("emotion_score", 0),
            "attribution_score": summary_data.get("attribution_score", 0),
            "discipline_score": summary_data.get("discipline_score", 0),
            "summary": summary_data.get("summary", ""),
            "strengths": summary_data.get("strengths", []),
            "weaknesses": summary_data.get("weaknesses", []),
            "suggestions": summary_data.get("suggestions", []),
            "timing_analysis": summary_data.get("timing_analysis", ""),
            "position_analysis": summary_data.get("position_analysis", ""),
            "emotion_analysis": summary_data.get("emotion_analysis", ""),
            "attribution_analysis": summary_data.get("attribution_analysis", ""),
            "actual_pnl": summary_data.get("actual_pnl", 0.0),
            "optimal_pnl": summary_data.get("optimal_pnl", 0.0),
            "missed_profit": summary_data.get("missed_profit", 0.0),
            "avoided_loss": summary_data.get("avoided_loss", 0.0),
            "plan_adherence": summary_data.get("plan_adherence", ""),
            "plan_deviation": summary_data.get("plan_deviation", "")
        }

        return {
            "ai_review": ai_review,
            "workflow_result": result  # 保留完整工作流结果
        }
```

### 5. 数据库设计

#### 5.1 unified_analysis_tasks 集合

```javascript
{
  "_id": ObjectId("..."),
  "task_id": "uuid",
  "user_id": ObjectId("..."),
  "task_type": "trade_review",
  "task_params": {
    "review_id": "uuid",
    "code": "688111",
    "name": "金山办公",
    "trade_info": {...},
    "market_snapshot": {...},
    "trading_system_id": "...",
    "user_id": "..."
  },
  "engine_type": "workflow",
  "workflow_id": "trade_review_v2",
  "preference_type": "neutral",
  "status": "completed",
  "progress": 100,
  "current_step": "复盘总结师",
  "message": "分析完成",
  "result": {
    "ai_review": {...},
    "workflow_result": {...}
  },
  "created_at": ISODate("..."),
  "started_at": ISODate("..."),
  "completed_at": ISODate("..."),
  "execution_time": 45.2,
  "error_message": null
}
```

#### 5.2 trade_reviews 集合（扩展）

```javascript
{
  "_id": ObjectId("..."),
  "review_id": "uuid",
  "user_id": "...",
  "task_id": "uuid",  // 🔑 新增：关联任务ID
  "review_type": "complete_trade",
  "trade_info": {...},
  "market_snapshot": {...},
  "ai_review": {...},
  "status": "completed",
  "execution_time": 45.2,
  "trading_system_id": "...",
  "trading_system_name": "...",
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### 4. 路由层改造

#### 4.1 修改 ReviewRouter（参考 PortfolioRouter）

**文件**：`app/routers/review.py`

```python
# app/routers/review.py

@router.post("/trade", response_model=dict)
async def create_trade_review(
    data: CreateTradeReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """创建交易复盘任务（异步模式）

    立即返回任务ID，后台执行复盘。
    前端可通过 GET /api/tasks/{task_id}/progress 查询进度。

    参考：app/routers/portfolio.py 的 analyze_position_by_code 实现
    """
    import asyncio

    try:
        logger.info(f"📝 [交易复盘路由] 收到复盘请求: {data.code}")

        # 判断是否使用任务中心
        use_task_center = data.use_workflow or _use_workflow_review()

        if use_task_center:
            # 🆕 使用任务中心模式（支持进度查询）
            from app.services.unified_analysis_service import get_unified_analysis_service
            unified_service = get_unified_analysis_service()

            # 创建任务（立即返回）
            result = await unified_service.create_trade_review_task(
                user_id=current_user["id"],
                request=data
            )
            logger.info(f"✅ [交易复盘路由] 任务创建成功: task_id={result['task_id']}")

            # 为了兼容前端，同时返回 review_id 字段（等于 task_id）
            result["review_id"] = result["task_id"]

            # 后台执行复盘
            logger.info(f"🚀 [交易复盘路由] 启动后台任务执行...")
            asyncio.create_task(
                unified_service.execute_trade_review(
                    task_id=result["task_id"],
                    user_id=current_user["id"],
                    request=data
                )
            )

            return ok(data=result)

        else:
            # 传统模式（保持不变）
            from app.services.trade_review_service import get_trade_review_service
            trade_review_service = get_trade_review_service()

            report = await trade_review_service.create_trade_review(
                user_id=current_user["id"],
                request=data
            )

            return ok(data=report.model_dump())

    except Exception as e:
        logger.error(f"❌ [交易复盘路由] 创建复盘失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

### 5. API 接口设计

#### 5.1 创建复盘接口（改造后）

```typescript
POST /api/review/trade

Request:
{
  "trade_ids": ["id1", "id2"],
  "review_type": "complete_trade",
  "code": "688111",
  "source": "real",
  "trading_system_id": "...",
  "use_workflow": true  // 🔑 控制是否使用任务中心
}

Response (任务中心模式):
{
  "code": 200,
  "data": {
    "task_id": "uuid",  // 🔑 任务ID
    "review_id": "uuid",  // 🔑 兼容字段（等于 task_id）
    "status": "pending",  // 🔑 立即返回 pending 状态
    "created_at": "2025-12-31T10:00:00Z"
  }
}

Response (传统模式):
{
  "code": 200,
  "data": {
    "review_id": "uuid",
    "status": "completed",  // 🔑 等待完成后返回
    "trade_info": {...},
    "market_snapshot": {...},
    "ai_review": {...},
    "execution_time": 45.2
  }
}
```

#### 5.2 查询任务进度接口（复用现有接口）

```typescript
GET /api/tasks/{task_id}/progress

Response:
{
  "code": 200,
  "data": {
    "task_id": "uuid",
    "status": "processing",
    "progress": 65,
    "current_step": "情绪分析师",
    "message": "😊 情绪分析师正在分析交易情绪...",
    "estimated_remaining": 15.5  // 预估剩余时间（秒）
  }
}
```

**注意**：这个接口已经存在于 `app/routers/tasks.py`，不需要新增。

#### 5.3 查询任务详情接口（复用现有接口）

```typescript
GET /api/tasks/{task_id}

Response:
{
  "code": 200,
  "data": {
    "task_id": "uuid",
    "task_type": "trade_review",
    "status": "completed",
    "progress": 100,
    "result": {
      "review_id": "uuid",
      "ai_review": {...},
      "trade_info": {...},
      "market_snapshot": {...}
    },
    "execution_time": 45.2,
    "created_at": "...",
    "completed_at": "..."
  }
}
```

**注意**：这个接口已经存在于 `app/routers/tasks.py`，不需要新增。

## 🔄 数据流设计

### 完整数据流（任务中心模式）

```
1. 用户发起复盘请求
   POST /api/review/trade
   {use_workflow: true, trade_ids: [...]}
   ↓

2. ReviewRouter.create_trade_review()
   ├─ 判断 use_workflow=true
   ├─ 调用 UnifiedAnalysisService.create_trade_review_task()
   ↓

3. UnifiedAnalysisService.create_trade_review_task()
   ├─ 生成 task_id
   ├─ 创建 UnifiedAnalysisTask
   │   ├─ task_type = TRADE_REVIEW
   │   ├─ status = PENDING
   │   └─ task_params = {trade_ids, code, ...}
   ├─ 保存到 unified_analysis_tasks 集合
   ├─ 保存到 MemoryStateManager
   └─ 返回 {task_id, status: "pending"}
   ↓

4. ReviewRouter 立即返回响应
   {task_id, review_id, status: "pending"}
   ↓

5. 后台任务启动（asyncio.create_task）
   UnifiedAnalysisService.execute_trade_review()
   ↓

6. execute_trade_review()
   ├─ 更新任务状态为 PROCESSING
   ├─ 调用 TradeReviewService.create_trade_review()
   │   ├─ 获取交易记录
   │   ├─ 构建交易信息
   │   ├─ 获取市场快照
   │   ├─ 获取交易计划
   │   ├─ 创建初始复盘报告 (trade_reviews)
   │   ├─ 调用 _call_ai_trade_review()
   │   │   ├─ 判断 use_workflow=true
   │   │   └─ 调用 _call_workflow_trade_review()
   │   │       ├─ 加载工作流 (trade_review_v2)
   │   │       ├─ 准备输入数据
   │   │       ├─ 执行工作流
   │   │       │   ├─ 时机分析师 (20%)
   │   │       │   ├─ 仓位分析师 (40%)
   │   │       │   ├─ 情绪分析师 (60%)
   │   │       │   ├─ 归因分析师 (80%)
   │   │       │   └─ 复盘总结师 (95%)
   │   │       └─ 返回 AITradeReview
   │   ├─ 更新 trade_reviews 集合
   │   └─ 返回 TradeReviewResponse
   ├─ 提取结果
   ├─ 更新任务状态为 COMPLETED
   └─ 保存结果到 unified_analysis_tasks
   ↓

7. 前端轮询查询进度
   GET /api/tasks/{task_id}/progress (每2秒)
   ├─ 从 MemoryStateManager 获取进度
   └─ 返回 {progress: 65, current_step: "情绪分析师", ...}
   ↓

8. 任务完成后查询结果
   GET /api/tasks/{task_id}
   ├─ 从 unified_analysis_tasks 查询
   └─ 返回 {result: {ai_review, trade_info, ...}}
```

### 前端实时查询进度

```
前端轮询查询进度：
GET /api/tasks/{task_id}/progress (每2秒)
  ↓
MemoryStateManager.get_task_progress()
  ├─ 从内存中获取最新进度
  ├─ progress: 65
  ├─ current_step: "情绪分析师"
  └─ message: "😊 情绪分析师正在分析交易情绪..."
  ↓
前端更新进度条
  ├─ 显示进度百分比
  ├─ 显示当前步骤
  └─ 显示提示信息
```

## 📋 实施计划

### Phase 1: 基础设施准备（0.5天）

#### 1.1 扩展数据模型
- [ ] 在 `app/models/analysis.py` 中添加 `TRADE_REVIEW` 任务类型
  ```python
  class AnalysisTaskType(str, Enum):
      TRADE_REVIEW = "trade_review"  # 新增
  ```

#### 1.2 注册工作流配置（可选）
- [ ] 在 `app/services/workflow_registry.py` 中注册 `TRADE_REVIEW` 工作流配置
- [ ] 验证配置参数与现有 `trade_review_v2` 工作流兼容

**注意**：这一步是可选的，因为我们直接调用现有的 `TradeReviewService`，不需要通过 `UnifiedAnalysisEngine`。

### Phase 2: 服务层改造（1-2天）

#### 2.1 扩展 UnifiedAnalysisService
- [ ] 在 `app/services/unified_analysis_service.py` 中添加 `create_trade_review_task()` 方法
  - [ ] 参考 `create_position_analysis_task()` 的实现
  - [ ] 创建 `UnifiedAnalysisTask` 对象
  - [ ] 保存到 `unified_analysis_tasks` 集合
  - [ ] 保存到 `MemoryStateManager`

- [ ] 在 `app/services/unified_analysis_service.py` 中添加 `execute_trade_review()` 方法
  - [ ] 参考 `execute_position_analysis()` 的实现
  - [ ] 调用 `TradeReviewService.create_trade_review()`
  - [ ] 更新任务状态（PROCESSING → COMPLETED/FAILED）
  - [ ] 保存结果到 `unified_analysis_tasks`

- [ ] 在 `app/services/unified_analysis_service.py` 中添加 `_update_task_status()` 方法
  - [ ] 参考 `_update_position_task_status()` 的实现
  - [ ] 更新数据库状态
  - [ ] 更新内存状态

#### 2.2 测试服务层
- [ ] 单元测试：测试 `create_trade_review_task()` 方法
- [ ] 单元测试：测试 `execute_trade_review()` 方法
- [ ] 集成测试：测试完整流程

### Phase 3: 路由层改造（0.5天）

#### 3.1 修改 ReviewRouter
- [ ] 在 `app/routers/review.py` 中修改 `create_trade_review()` 路由
  - [ ] 参考 `app/routers/portfolio.py` 的 `analyze_position_by_code` 实现
  - [ ] 判断是否使用任务中心（`use_workflow` 参数）
  - [ ] 任务中心模式：调用 `UnifiedAnalysisService.create_trade_review_task()`
  - [ ] 任务中心模式：后台执行 `UnifiedAnalysisService.execute_trade_review()`
  - [ ] 传统模式：调用 `TradeReviewService.create_trade_review()`

#### 3.2 测试路由层
- [ ] 测试任务中心模式：`POST /api/review/trade` (use_workflow=true)
- [ ] 测试传统模式：`POST /api/review/trade` (use_workflow=false)
- [ ] 测试进度查询：`GET /api/tasks/{task_id}/progress`
- [ ] 测试结果查询：`GET /api/tasks/{task_id}`

### Phase 4: 前端集成（1-2天）

#### 4.1 前端进度查询
- [ ] 实现进度轮询逻辑（每2秒查询一次）
- [ ] 实现进度条组件
- [ ] 实现步骤提示组件
- [ ] 实现错误提示

#### 4.2 前端测试
- [ ] 测试进度实时更新
- [ ] 测试任务完成后的结果展示
- [ ] 测试错误处理
- [ ] 测试用户体验

### Phase 5: 测试和优化（1天）

#### 5.1 端到端测试
- [ ] 测试完整复盘流程（从创建到完成）
- [ ] 测试进度查询功能
- [ ] 测试错误场景（网络中断、超时等）
- [ ] 测试并发场景（多个复盘任务同时执行）

#### 5.2 性能优化
- [ ] 优化进度查询性能（使用内存状态管理器）
- [ ] 优化任务状态更新性能
- [ ] 监控工作流执行性能

#### 5.3 文档更新
- [ ] 更新 API 文档
- [ ] 更新用户手册
- [ ] 更新开发文档

### 总计：4-6天

## 🎯 预期收益

### 1. 用户体验提升
- ✅ **实时进度反馈**：用户可以看到复盘任务的实时进度
- ✅ **透明度提升**：用户知道当前执行到哪个步骤
- ✅ **焦虑感降低**：不再是"黑盒"等待，有明确的进度指示

### 2. 系统可维护性提升
- ✅ **统一任务管理**：所有分析任务使用相同的管理机制
- ✅ **统一错误处理**：统一的异常处理和状态回滚
- ✅ **任务历史记录**：完整的任务执行记录，便于问题排查

### 3. 功能扩展性提升
- ✅ **支持任务取消**：可以取消正在执行的复盘任务
- ✅ **支持任务重试**：可以重试失败的复盘任务
- ✅ **支持批量复盘**：可以基于任务中心实现批量复盘功能

## ⚠️ 风险和注意事项

### 1. 向后兼容性
- **风险**：改造可能影响现有功能
- **缓解措施**：
  - 保留 `_create_trade_review_legacy()` 方法
  - 通过 `use_workflow` 参数控制新旧模式
  - 充分测试兼容性

### 2. 数据一致性
- **风险**：`trade_reviews` 和 `unified_analysis_tasks` 两个集合的数据可能不一致
- **缓解措施**：
  - 使用事务保证数据一致性（如果 MongoDB 支持）
  - 添加数据校验逻辑
  - 定期检查数据一致性

### 3. 性能影响
- **风险**：进度查询可能增加数据库负载
- **缓解措施**：
  - 使用内存状态管理器减少数据库查询
  - 优化查询索引
  - 控制轮询频率

### 4. 工作流适配
- **风险**：现有 `trade_review_v2` 工作流可能需要调整
- **缓解措施**：
  - 复用现有工作流逻辑
  - 只调整输入输出格式
  - 充分测试工作流执行

## 📊 成功指标

### 1. 功能指标
- ✅ 100% 的复盘任务都有进度记录
- ✅ 进度查询响应时间 < 100ms
- ✅ 进度更新延迟 < 2秒

### 2. 质量指标
- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试覆盖率 > 70%
- ✅ 零数据一致性问题

### 3. 用户体验指标
- ✅ 用户满意度提升
- ✅ 用户投诉减少
- ✅ 用户留存率提升

## 📚 参考资料

### 相关文件
- `app/services/trade_review_service.py` - 交易复盘服务
- `app/services/task_analysis_service.py` - 任务分析服务
- `app/services/unified_analysis_engine.py` - 统一分析引擎
- `app/services/memory_state_manager.py` - 内存状态管理器
- `app/services/workflow_registry.py` - 工作流注册表
- `core/workflow/engine.py` - 工作流引擎
- `workflows/trade_review_v2.json` - 交易复盘工作流 v2.0

### 相关文档
- [任务中心设计文档](./task-center-design.md)
- [工作流引擎设计文档](./workflow-engine-design.md)
- [交易复盘 v2.0 设计文档](./trade-review-v2-design.md)

## 📝 总结

本设计文档详细描述了如何将交易复盘流程（Trade Review）完全纳入任务中心（Task Center）管理，实现实时进度跟踪和统一任务管理。

### 核心改动

**参考实现：持仓分析和单股分析的集成模式**

1. **扩展数据模型**
   - 在 `AnalysisTaskType` 枚举中添加 `TRADE_REVIEW` 任务类型

2. **扩展 UnifiedAnalysisService**（参考 `create_position_analysis_task` 和 `execute_position_analysis`）
   - 添加 `create_trade_review_task()` 方法：创建任务并保存到 `unified_analysis_tasks`
   - 添加 `execute_trade_review()` 方法：调用现有的 `TradeReviewService.create_trade_review()`
   - 添加 `_update_task_status()` 方法：更新任务状态（数据库 + 内存）

3. **修改 ReviewRouter**（参考 `app/routers/portfolio.py` 的 `analyze_position_by_code`）
   - 判断是否使用任务中心（`use_workflow` 参数）
   - 任务中心模式：创建任务 + 后台执行
   - 传统模式：直接调用 `TradeReviewService`

4. **保持现有逻辑不变**
   - `TradeReviewService.create_trade_review()` 方法**完全不需要修改**
   - 继续使用现有的 `_call_workflow_trade_review()` 逻辑
   - 继续使用现有的 `trade_review_v2` 工作流

### 关键优势

- ✅ **实时进度跟踪**：前端可以实时查询复盘任务的执行进度
- ✅ **统一任务管理**：复盘任务与股票分析、持仓分析使用相同的管理机制
- ✅ **向后兼容**：保持现有 API 接口和数据结构不变
- ✅ **渐进式迁移**：支持新旧两种模式并存（通过 `use_workflow` 参数控制）
- ✅ **最小侵入**：现有的 `TradeReviewService` 逻辑完全不需要修改
- ✅ **复用现有工作流**：继续使用 `trade_review_v2` 工作流，不需要创建新的工作流

### 实施周期

**预计 4-6 天**

- Phase 1: 基础设施准备（0.5天）
- Phase 2: 服务层改造（1-2天）
- Phase 3: 路由层改造（0.5天）
- Phase 4: 前端集成（1-2天）
- Phase 5: 测试和优化（1天）

### 风险等级

**低风险**

- ✅ 参考了成熟的持仓分析和单股分析实现
- ✅ 现有逻辑完全不需要修改
- ✅ 支持新旧两种模式并存
- ✅ 充分的测试覆盖

### 对比原方案的改进

| 维度 | 原方案 | 新方案（参考持仓分析） |
|------|--------|----------------------|
| **服务层改造** | 重构 `TradeReviewService` | 扩展 `UnifiedAnalysisService` |
| **现有逻辑** | 需要修改 | **完全不需要修改** ✅ |
| **引擎层改造** | 需要扩展 `UnifiedAnalysisEngine` | **不需要** ✅ |
| **工作流适配** | 需要适配输入输出格式 | **直接复用现有工作流** ✅ |
| **实施周期** | 11-17天 | **4-6天** ✅ |
| **风险等级** | 中等 | **低** ✅ |

---

**文档版本：** v2.0
**最后更新：** 2025-12-31
**作者：** AI Assistant
**审核状态：** 待审核
**参考实现：** `app/routers/portfolio.py` (analyze_position_by_code) 和 `app/services/unified_analysis_service.py` (create_position_analysis_task, execute_position_analysis)
