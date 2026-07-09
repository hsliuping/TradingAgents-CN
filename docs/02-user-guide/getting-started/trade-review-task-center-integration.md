# 交易复盘接入统一任务管理中心

## 📋 概述

将交易复盘功能接入新的统一任务管理中心，实现：
- ✅ 统一的任务创建和执行流程
- ✅ 实时进度跟踪（内存状态管理器）
- ✅ 任务状态持久化（MongoDB）
- ✅ 支持多引擎切换（workflow/legacy/llm）
- ✅ 任务可查询、可取消

---

## 🔧 修改内容

### 1. 路由层修改 (`app/routers/review.py`)

**修改前**：
```python
@router.post("/trade", response_model=Dict[str, Any])
async def create_trade_review(
    request: CreateTradeReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    service = get_trade_review_service()
    result = await service.create_trade_review(  # ❌ 旧版方法
        user_id=current_user["id"],
        request=request
    )
```

**修改后**：
```python
@router.post("/trade", response_model=Dict[str, Any])
async def create_trade_review(
    request: CreateTradeReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    service = get_trade_review_service()
    result = await service.create_trade_review_v2(  # ✅ 新版方法
        user_id=current_user["id"],
        request=request
    )
```

### 2. 服务层修改 (`app/services/trade_review_service.py`)

#### 2.1 添加内存状态管理器支持

```python
from app.services.memory_state_manager import get_memory_state_manager, TaskStatus

async def create_trade_review_v2(
    self,
    user_id: str,
    request: CreateTradeReviewRequest
) -> TradeReviewResponse:
    # ... 前置处理 ...
    
    # 🔥 创建任务（先创建，后执行，以便获取 task_id）
    task = await task_service.create_task(
        user_id=PyObjectId(user_id),
        task_type=AnalysisTaskType.TRADE_REVIEW,
        task_params=task_params,
        engine_type=engine_type,
        preference_type=preference_type
    )
    
    # 🔥 在内存状态管理器中创建任务状态
    memory_manager = get_memory_state_manager()
    await memory_manager.create_task(
        task_id=task.task_id,
        user_id=user_id,
        stock_code=trade_info.code,
        stock_name=trade_info.name,
        parameters=task_params
    )
    
    # 🔥 执行任务（带进度回调）
    task = await task_service.execute_task(task)
```

#### 2.2 添加详细日志

```python
logger.info(f"📋 [交易复盘v2.0] 步骤1: 获取交易记录...")
logger.info(f"🔨 [交易复盘v2.0] 步骤2: 构建交易信息...")
logger.info(f"📝 [交易复盘v2.0] 步骤8: 创建分析任务...")
logger.info(f"✅ [交易复盘v2.0] 任务已创建: {task.task_id}")
logger.info(f"🚀 [交易复盘v2.0] 步骤9: 执行分析任务...")
logger.info(f"✅ [交易复盘v2.0] 复盘完成: {review_id}, 任务ID: {task.task_id}")
```

---

## 📊 数据流

```
用户请求
  ↓
路由层 (review.py)
  ↓
服务层 (trade_review_service.py)
  ├─ 获取交易记录
  ├─ 构建交易信息
  ├─ 获取市场快照
  ↓
统一任务引擎 (task_analysis_service.py)
  ├─ 创建任务 (MongoDB: unified_analysis_tasks)
  ├─ 创建内存状态 (memory_state_manager)
  ├─ 执行任务 (workflow/legacy/llm)
  │   ├─ 更新进度 (实时)
  │   └─ 更新状态 (MongoDB + 内存)
  ↓
保存结果
  ├─ 更新复盘报告 (MongoDB: trade_reviews)
  └─ 返回响应
```

---

## 🎯 优势

### 1. **统一管理**
- 所有分析任务（股票分析、持仓分析、交易复盘）都使用同一套任务管理系统
- 统一的任务查询接口 (`/api/v2/tasks/*`)

### 2. **实时进度**
- 内存状态管理器提供毫秒级的进度更新
- 前端可以通过 WebSocket 实时获取进度

### 3. **多引擎支持**
- `engine_type="auto"`: 自动选择最佳引擎
- `engine_type="workflow"`: 使用工作流引擎（v2.0）
- `engine_type="legacy"`: 使用传统分析方式
- `engine_type="llm"`: 直接调用 LLM

### 4. **任务可追溯**
- 每个任务都有唯一的 `task_id`
- 可以查询任务历史、执行时间、错误信息等

---

## 🔍 测试验证

### 1. 创建交易复盘

```bash
POST /api/review/trade
{
  "trade_ids": ["trade_id_1", "trade_id_2"],
  "review_type": "complete_trade",
  "code": "601668",
  "source": "paper",
  "use_workflow": true
}
```

### 2. 查询任务状态

```bash
GET /api/v2/tasks/{task_id}
```

### 3. 查询用户所有任务

```bash
GET /api/v2/tasks?task_type=trade_review
```

---

## 📝 注意事项

1. **兼容性**: 旧版 `create_trade_review` 方法仍然保留，但不再使用
2. **进度回调**: 任务执行过程中会自动更新内存状态管理器
3. **错误处理**: 任务失败时会自动更新状态为 `FAILED`，并记录错误信息

---

## 🚀 下一步

- [ ] 前端适配：显示任务进度条
- [ ] 添加任务取消功能
- [ ] 添加任务重试功能
- [ ] 优化进度更新频率

