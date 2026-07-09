# TaskAnalysisService 集成指南

## 📌 核心原则

**不创建新 API，在现有服务中集成统一任务引擎**

### 为什么不创建新 API？

1. ✅ **避免重复** - 现有 API 已经覆盖所有功能
2. ✅ **保持一致性** - 前端已经在使用现有 API
3. ✅ **向后兼容** - 不破坏现有功能
4. ✅ **降低复杂度** - 不需要前端改动

---

## 🎯 集成方案

### 现有 API 映射

| 现有 API | 功能 | 对应任务类型 | 现有服务 |
|---------|------|------------|---------|
| `/api/analysis/single` | 股票分析 | `STOCK_ANALYSIS` | `simple_analysis_service` |
| `/api/portfolio/positions/analyze-by-code` | 持仓分析 | `POSITION_ANALYSIS` | `portfolio_service` |
| `/api/review/trade` | 交易复盘 | `TRADE_REVIEW` | `trade_review_service` |

### 集成策略

**在现有服务中添加一个方法，使用 `TaskAnalysisService`**

---

## 📝 集成示例

### 示例 1: 在 `portfolio_service.py` 中集成

**场景**: 持仓分析

**现有代码**:
```python
# app/services/portfolio_service.py

async def analyze_position_by_code(self, user_id, code, market, params):
    """持仓分析（现有方法）"""
    # 现有的分析逻辑
    ...
```

**集成后**:
```python
# app/services/portfolio_service.py

from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType

async def analyze_position_by_code_v2(self, user_id, code, market, params):
    """持仓分析 v2.0 - 使用统一任务引擎
    
    优势:
    - 支持多引擎切换（workflow/legacy/llm）
    - 统一的任务管理
    - 自动选择最佳引擎
    """
    task_service = get_task_analysis_service()
    
    # 创建并执行任务
    task = await task_service.create_and_execute_task(
        user_id=user_id,
        task_type=AnalysisTaskType.POSITION_ANALYSIS,
        task_params={
            "position_id": position_id,  # 或其他必需参数
            "code": code,
            "market": market,
            **params
        },
        engine_type="auto",  # 自动选择引擎
        preference_type=params.get("preference_type", "neutral")
    )
    
    # 返回结果
    return task.result
```

**API 路由不变**:
```python
# app/routers/portfolio.py

@router.post("/positions/analyze-by-code")
async def analyze_position_by_code(
    request: AnalyzePositionRequest,
    user_id: PyObjectId = Depends(get_current_user_id)
):
    """持仓分析 API（保持不变）"""
    service = get_portfolio_service()
    
    # 可以选择使用新方法或旧方法
    use_v2 = request.use_unified_engine  # 可选参数
    
    if use_v2:
        result = await service.analyze_position_by_code_v2(...)
    else:
        result = await service.analyze_position_by_code(...)  # 旧方法
    
    return result
```

---

### 示例 2: 在 `analysis_service.py` 中集成

**场景**: 股票分析

**集成代码**:
```python
# app/services/analysis_service.py

from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType

async def analyze_stock_v2(self, user_id, symbol, market_type, params):
    """股票分析 v2.0 - 使用统一任务引擎"""
    task_service = get_task_analysis_service()
    
    task = await task_service.create_and_execute_task(
        user_id=user_id,
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={
            "symbol": symbol,
            "market_type": market_type,
            **params
        },
        engine_type=params.get("engine_type", "auto"),
        preference_type=params.get("preference_type", "neutral")
    )
    
    return task.result
```

---

### 示例 3: 在 `trade_review_service.py` 中集成

**场景**: 交易复盘

**集成代码**:
```python
# app/services/trade_review_service.py

from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType

async def create_trade_review_v2(self, user_id, review_data):
    """交易复盘 v2.0 - 使用统一任务引擎"""
    task_service = get_task_analysis_service()
    
    task = await task_service.create_and_execute_task(
        user_id=user_id,
        task_type=AnalysisTaskType.TRADE_REVIEW,
        task_params={
            "review_id": review_data.get("review_id"),
            "code": review_data.get("code"),
            "trades": review_data.get("trades"),
            **review_data
        },
        engine_type="auto",
        preference_type=review_data.get("preference_type", "neutral")
    )
    
    return task.result
```

---

## 🔄 渐进式迁移策略

### 阶段 1: 添加 v2 方法（不破坏现有功能）

```python
class PortfolioService:
    async def analyze_position_by_code(self, ...):
        """旧方法 - 保持不变"""
        ...
    
    async def analyze_position_by_code_v2(self, ...):
        """新方法 - 使用 TaskAnalysisService"""
        ...
```

### 阶段 2: API 支持选择引擎

```python
@router.post("/positions/analyze-by-code")
async def analyze_position_by_code(
    request: AnalyzePositionRequest,
    user_id: PyObjectId = Depends(get_current_user_id)
):
    service = get_portfolio_service()
    
    # 通过参数选择使用哪个方法
    if request.use_unified_engine:
        return await service.analyze_position_by_code_v2(...)
    else:
        return await service.analyze_position_by_code(...)
```

### 阶段 3: 逐步切换默认引擎

```python
# 默认使用新引擎，但保留旧引擎作为备选
if request.use_legacy_engine:
    return await service.analyze_position_by_code(...)  # 旧引擎
else:
    return await service.analyze_position_by_code_v2(...)  # 新引擎（默认）
```

### 阶段 4: 完全迁移（可选）

```python
# 完全使用新引擎，移除旧方法
async def analyze_position_by_code(self, ...):
    """使用统一任务引擎"""
    return await self.analyze_position_by_code_v2(...)
```

---

## ✅ 优势总结

### 1. 对前端透明
- ✅ API 端点不变
- ✅ 请求/响应格式不变
- ✅ 前端无需改动

### 2. 向后兼容
- ✅ 旧方法继续工作
- ✅ 可以逐步迁移
- ✅ 支持 A/B 测试

### 3. 统一管理
- ✅ 所有任务使用同一个模型
- ✅ 统一的任务查询接口
- ✅ 统一的进度跟踪

### 4. 灵活扩展
- ✅ 支持多引擎切换
- ✅ 配置化的工作流
- ✅ 易于添加新分析类型

---

## 📊 对比

### 旧方案（创建新 API）

```
❌ 新 API: /api/v2/tasks/execute
❌ 前端需要改动
❌ 两套 API 并存
❌ 维护成本高
```

### 新方案（集成到现有服务）

```
✅ 现有 API: /api/analysis/single
✅ 前端无需改动
✅ 统一的 API 入口
✅ 维护成本低
```

---

## 🎯 下一步

1. 在 `portfolio_service.py` 中添加 `analyze_position_by_code_v2()` 方法
2. 在 `analysis_service.py` 中添加 `analyze_stock_v2()` 方法
3. 在 `trade_review_service.py` 中添加 `create_trade_review_v2()` 方法
4. 在 API 路由中添加引擎选择参数
5. 测试新旧引擎的兼容性

