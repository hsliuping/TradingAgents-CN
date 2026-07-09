# 结果API支持unified_analysis_tasks集合

## 📋 问题描述

用户报告 `/api/analysis/tasks/{task_id}/result` 接口返回404错误：

```
2025-12-28 21:26:22 | webapi | WARNING | ❌ [RESULT] 所有数据源都未找到结果: fb7d6632-ec86-4930-8222-66b9aeed1be0
2025-12-28 21:26:22 | webapi | INFO | ❌ GET /api/analysis/tasks/fb7d6632-ec86-4930-8222-66b9aeed1be0/result - 状态: 404
```

**问题表现**：
- 使用 v2 引擎（`engine: "v2"`）创建的任务，结果保存在 `unified_analysis_tasks` 集合中
- `/result` 接口只从 `analysis_reports` 和 `analysis_tasks` 集合中查找
- 导致 v2 引擎的任务结果无法获取

## 🔍 根本原因分析

### 问题代码位置

**文件**：`app/routers/analysis.py` 第 459-467 行

### 原因：缺少对 unified_analysis_tasks 集合的查询

```python
if not result_data:
    # 内存中没有找到，尝试从MongoDB中查找
    logger.info(f"📊 [RESULT] 内存中未找到，尝试从MongoDB查找: {task_id}")

    from app.core.database import get_mongo_db
    db = get_mongo_db()

    # ❌ 直接从 analysis_reports 集合中查找，跳过了 unified_analysis_tasks
    mongo_result = await db.analysis_reports.find_one({"task_id": task_id})
```

**数据流程**：

1. **v2 引擎任务**：
   - 任务创建 → `unified_analysis_tasks` 集合
   - 结果保存 → `unified_analysis_tasks.result` 字段
   - `/result` 接口 → ❌ 没有查询 `unified_analysis_tasks`

2. **v1 引擎任务**：
   - 任务创建 → `analysis_tasks` 集合
   - 结果保存 → `analysis_reports` 集合
   - `/result` 接口 → ✅ 能正常查询

## ✅ 修复方案

### 修复内容

**文件**：`app/routers/analysis.py` 第 459-506 行

### 添加对 unified_analysis_tasks 集合的查询

```python
if not result_data:
    # 内存中没有找到，尝试从MongoDB中查找
    logger.info(f"📊 [RESULT] 内存中未找到，尝试从MongoDB查找: {task_id}")

    from app.core.database import get_mongo_db
    db = get_mongo_db()

    # ✅ 首先从 unified_analysis_tasks 集合中查找（v2 引擎任务）
    unified_task = await db.unified_analysis_tasks.find_one({"task_id": task_id})
    if unified_task and unified_task.get("result"):
        logger.info(f"✅ [RESULT] 从unified_analysis_tasks找到结果: {task_id}")
        
        result = unified_task["result"]
        task_params = unified_task.get("task_params", {})
        
        # 计算执行时间
        execution_time = 0
        completed_at = unified_task.get("completed_at")
        started_at = unified_task.get("started_at")
        if completed_at and started_at:
            try:
                # 如果是 datetime 对象，直接相减
                if hasattr(completed_at, 'timestamp') and hasattr(started_at, 'timestamp'):
                    execution_time = (completed_at - started_at).total_seconds()
                # 如果是字符串，先解析
                elif isinstance(completed_at, str) and isinstance(started_at, str):
                    from dateutil import parser
                    completed_dt = parser.parse(completed_at)
                    started_dt = parser.parse(started_at)
                    execution_time = (completed_dt - started_dt).total_seconds()
            except Exception as e:
                logger.warning(f"⚠️ 计算执行时间失败: {e}")
                execution_time = 0
        
        # 构造结果数据（兼容前端期望的格式）
        result_data = {
            "analysis_id": unified_task.get("task_id"),  # 使用 task_id 作为 analysis_id
            "stock_symbol": task_params.get("symbol") or task_params.get("stock_code"),
            "stock_code": task_params.get("stock_code") or task_params.get("symbol"),
            "analysis_date": task_params.get("analysis_date"),
            "summary": result.get("summary", ""),
            "recommendation": result.get("recommendation", ""),
            "confidence_score": result.get("confidence_score", 0.0),
            "risk_level": result.get("risk_level", "中等"),
            "key_points": result.get("key_points", []),
            "execution_time": execution_time,
            "tokens_used": result.get("tokens_used", 0),
            "analysts": task_params.get("selected_analysts", []),
            "research_depth": task_params.get("research_depth", "快速"),
            "reports": result.get("reports", {}),
            "state": result.get("state", {}),
            "detailed_analysis": result.get("detailed_analysis", {}),
            "created_at": unified_task.get("created_at"),
            "updated_at": unified_task.get("completed_at"),
            "status": "completed",
            "decision": result.get("decision", {}),
            "source": "unified_tasks"  # 标记数据来源
        }
        
        logger.info(f"📊 [RESULT] unified_tasks数据结构: {list(result_data.keys())}")
        logger.info(f"📊 [RESULT] summary长度: {len(result_data['summary'])}")
        logger.info(f"📊 [RESULT] recommendation长度: {len(result_data['recommendation'])}")
        logger.info(f"📊 [RESULT] decision字段: {bool(result_data.get('decision'))}")
    
    # ✅ 如果 unified_analysis_tasks 中没有找到，再从 analysis_reports 集合中查找
    if not result_data:
        mongo_result = await db.analysis_reports.find_one({"task_id": task_id})
        # ... 后续逻辑保持不变
```

## 📊 修复效果

### 修复前

```
请求: GET /api/analysis/tasks/fb7d6632-ec86-4930-8222-66b9aeed1be0/result
响应: 404 Not Found
错误: "分析结果不存在"
```

**查询顺序**：
1. ❌ 内存（`simple_analysis_service`）
2. ❌ `analysis_reports` 集合
3. ❌ `analysis_tasks` 集合
4. ❌ 返回404

### 修复后

```
请求: GET /api/analysis/tasks/fb7d6632-ec86-4930-8222-66b9aeed1be0/result
响应: 200 OK
数据: {
    "analysis_id": "fb7d6632-ec86-4930-8222-66b9aeed1be0",
    "stock_symbol": "000001",
    "summary": "...",
    "recommendation": "...",
    "decision": {...},
    "source": "unified_tasks"
}
```

**查询顺序**：
1. ❌ 内存（`simple_analysis_service`）
2. ✅ `unified_analysis_tasks` 集合（v2 引擎任务）
3. ⏭️ `analysis_reports` 集合（如果步骤2没找到）
4. ⏭️ `analysis_tasks` 集合（如果步骤3没找到）

## 🎯 总结

本次修复解决了 v2 引擎任务结果无法获取的问题：

1. **添加 unified_analysis_tasks 查询**：优先从 v2 引擎的集合中查找结果
2. **兼容性处理**：保持对 v1 引擎（`analysis_reports` 和 `analysis_tasks`）的支持
3. **数据格式统一**：确保返回的数据格式与前端期望一致
4. **执行时间计算**：正确处理 datetime 对象和字符串的时间计算

现在 v2 引擎的任务结果可以正常获取了！

