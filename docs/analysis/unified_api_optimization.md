# 统一接口优化方案

## 📊 涉及的接口

### 1. `/api/analysis/tasks/{task_id}/result`
- **用途**：获取任务分析结果
- **返回字段**：`reports`, `state`, `detailed_analysis`, `decision`, 元数据
- **问题**：包含大量重复数据

### 2. `/api/reports/{report_id}/detail`
- **用途**：获取报告详情
- **返回字段**：`reports`, `decision`, 元数据（**没有** `state` 和 `detailed_analysis`）
- **问题**：数据库中存储的 `reports` 可能包含重复数据

## 🔍 数据流分析

### 数据保存流程

```
分析执行完成
  ↓
result_data (包含 reports, state, detailed_analysis)
  ↓
_save_to_analysis_reports() / save_analysis_report()
  ↓
提取 reports 字段
  ↓
保存到 analysis_reports 集合
  ↓
/api/reports/{report_id}/detail 读取
```

### 当前问题

1. **`/api/analysis/tasks/{task_id}/result`**：
   - 返回完整的 `result_data`，包含 `state` 和 `detailed_analysis`
   - `detailed_analysis.structured_reports` 与 `reports` 完全重复
   - `state` 中的内容已提取到 `reports`

2. **`/api/reports/{report_id}/detail`**：
   - 从数据库读取，只返回 `reports`（没有 `state` 和 `detailed_analysis`）
   - 但数据库中存储的 `reports` 如果是从 `result_data.reports` 保存的，可能包含重复数据
   - 如果是从 `result_data.detailed_analysis.structured_reports` 保存的，则与 API 返回的 `reports` 重复

## 🎯 统一优化方案

### 方案一：统一返回结构（推荐）

**原则**：所有接口返回相同的数据结构，只包含必要字段

**统一返回结构**：
```json
{
  "success": true,
  "data": {
    // 元数据（必须）
    "id": "...",
    "analysis_id": "...",
    "stock_symbol": "...",
    "stock_name": "...",
    "analysis_date": "...",
    "model_info": "...",
    "research_depth": "...",
    "analysts": [...],
    "confidence_score": 0.73,
    "risk_level": "中等",
    "key_points": [...],
    
    // 核心数据（必须）
    "summary": "...",
    "recommendation": "...",
    "decision": {
      "action": "看涨",
      "confidence": 0.7,
      "risk_score": 0.5,
      "price_analysis_range": [8.58, 12.86],
      "reasoning": "..."
    },
    
    // 报告内容（必须）
    "reports": {
      "market_report": "...",
      "fundamentals_report": "...",
      "bull_researcher": "...",
      "bear_researcher": "...",
      "research_team_decision": "...",
      "trader_investment_plan": "...",
      "risky_analyst": "...",
      "safe_analyst": "...",
      "neutral_analyst": "...",
      "risk_management_decision": "...",
      "final_trade_decision": "..."
    }
    
    // ❌ 移除以下字段（默认不返回）
    // - state
    // - detailed_analysis
  }
}
```

### 方案二：添加查询参数控制

**所有接口统一支持**：
```python
GET /api/analysis/tasks/{task_id}/result?include_state=false&include_detailed=false
GET /api/reports/{report_id}/detail?include_state=false&include_detailed=false
```

**默认值**：
- `include_state=false` - 默认不返回 state
- `include_detailed=false` - 默认不返回 detailed_analysis

## 🔧 具体修改点

### 1. `/api/analysis/tasks/{task_id}/result` 接口

**文件**：`app/routers/analysis.py`

**修改**：
```python
@router.get("/tasks/{task_id}/result", response_model=Dict[str, Any])
async def get_task_result(
    task_id: str,
    include_state: bool = False,  # 🆕 默认 False
    include_detailed: bool = False,  # 🆕 默认 False
    user: dict = Depends(get_current_user)
):
    # 获取结果数据
    result_data = service.get_result_data(task_id)
    
    # 构建基础返回数据（只包含必要字段）
    response_data = {
        # 元数据
        "stock_symbol": result_data.get("stock_symbol"),
        "analysis_date": result_data.get("analysis_date"),
        "model_info": result_data.get("model_info"),
        # ... 其他元数据
        
        # 核心数据
        "summary": result_data.get("summary"),
        "recommendation": result_data.get("recommendation"),
        "decision": result_data.get("decision"),
        "reports": result_data.get("reports"),
    }
    
    # 可选字段（根据参数决定）
    if include_state:
        response_data["state"] = result_data.get("state")
    if include_detailed:
        response_data["detailed_analysis"] = result_data.get("detailed_analysis")
    
    return {"success": True, "data": response_data}
```

### 2. `/api/reports/{report_id}/detail` 接口

**文件**：`app/routers/reports.py`

**当前状态**：
- ✅ 已经只返回 `reports`（没有 `state` 和 `detailed_analysis`）
- ⚠️ 但数据库中存储的 `reports` 可能包含重复数据

**修改**：
```python
@router.get("/{report_id}/detail")
async def get_report_detail(
    report_id: str,
    include_state: bool = False,  # 🆕 默认 False
    include_detailed: bool = False,  # 🆕 默认 False
    user: dict = Depends(get_current_user)
):
    # ... 查询逻辑 ...
    
    report = {
        # ... 元数据 ...
        "reports": doc.get("reports", {}),
        "decision": doc.get("decision", {}),
        # ... 其他字段 ...
    }
    
    # 🔥 清理 reports 中的重复数据（如果存在）
    reports = report.get("reports", {})
    if isinstance(reports, dict):
        # 移除可能的重复字段
        cleaned_reports = {}
        for key, value in reports.items():
            # 跳过 structured_reports（如果存在）
            if key != "structured_reports":
                cleaned_reports[key] = value
        report["reports"] = cleaned_reports
    
    # 可选字段（根据参数决定）
    if include_state:
        # 从 analysis_tasks.result.state 获取（如果存在）
        if tasks_doc and tasks_doc.get("result", {}).get("state"):
            report["state"] = tasks_doc["result"]["state"]
    
    if include_detailed:
        # 从 analysis_tasks.result.detailed_analysis 获取（如果存在）
        if tasks_doc and tasks_doc.get("result", {}).get("detailed_analysis"):
            report["detailed_analysis"] = tasks_doc["result"]["detailed_analysis"]
    
    return {"success": True, "data": report}
```

### 3. 数据保存优化

**文件**：`app/services/task_analysis_service.py`

**修改 `_build_result_data` 方法**：
```python
def _build_result_data(self, raw_result: Dict[str, Any], ...) -> Dict[str, Any]:
    # 提取 reports（移除重复数据）
    reports = self._extract_reports(raw_result)
    
    # 构建结果数据（不包含 state 和 detailed_analysis）
    result_data = {
        # 元数据
        "stock_symbol": ...,
        "decision": formatted_decision,
        "reports": reports,  # ✅ 主要数据源
        
        # ❌ 移除以下字段（默认不返回）
        # "state": state,  # 改为可选
        # "detailed_analysis": raw_result,  # 改为可选
    }
    
    return result_data
```

**修改 `_extract_reports` 方法**：
```python
def _extract_reports(self, raw_result: Dict[str, Any]) -> Dict[str, str]:
    reports = {}
    
    # 1. 优先从顶层提取（已格式化的 reports）
    if "reports" in raw_result and isinstance(raw_result["reports"], dict):
        reports.update(raw_result["reports"])
    
    # 2. 从 detailed_analysis.structured_reports 提取（如果顶层没有）
    # ❌ 移除：不再从 structured_reports 提取（避免重复）
    
    # 3. 从 state 提取（如果顶层没有）
    # ⚠️ 保留：但仅作为回退，且提取后不再保存到 state
    
    return reports
```

### 4. 数据库存储优化

**文件**：`app/utils/report_saver.py`

**确保保存时只保存必要的 reports**：
```python
async def save_analysis_report(
    db,
    reports: Dict[str, str],  # 只接收清理后的 reports
    ...
):
    # 🔥 清理 reports（移除可能的重复字段）
    cleaned_reports = {}
    for key, value in reports.items():
        # 跳过 structured_reports（如果存在）
        if key != "structured_reports":
            cleaned_reports[key] = value
    
    document = {
        # ...
        "reports": cleaned_reports,  # 使用清理后的 reports
        # ...
    }
    
    await db.analysis_reports.insert_one(document)
```

## 📋 实施步骤

### 阶段一：接口统一（本周）

1. ✅ 修改 `/api/analysis/tasks/{task_id}/result`
   - 添加 `include_state` 和 `include_detailed` 参数
   - 默认不返回 `state` 和 `detailed_analysis`

2. ✅ 修改 `/api/reports/{report_id}/detail`
   - 添加 `include_state` 和 `include_detailed` 参数
   - 清理 `reports` 中的重复数据

3. ✅ 修改 `_build_result_data` 方法
   - 移除 `state` 和 `detailed_analysis` 的默认返回
   - 确保 `reports` 不包含重复数据

### 阶段二：数据清理（下周）

1. ✅ 修改 `_extract_reports` 方法
   - 不再从 `detailed_analysis.structured_reports` 提取
   - 优先从顶层 `reports` 提取

2. ✅ 修改 `save_analysis_report` 函数
   - 清理保存的 `reports`，移除重复字段

3. ✅ 前端代码更新
   - 移除 `state` 回退逻辑
   - 统一从 `reports` 取值

### 阶段三：数据迁移（可选）

1. ✅ 清理现有数据库中的重复数据
   - 脚本：移除 `reports.structured_reports`（如果存在）

## ✅ 预期效果

### 数据大小对比

| 接口 | 当前大小 | 优化后大小 | 节省 |
|------|---------|-----------|------|
| `/api/analysis/tasks/{task_id}/result` | ~1200 KB | ~300 KB | 75% |
| `/api/reports/{report_id}/detail` | ~300 KB | ~300 KB | 0%* |

*如果数据库中没有重复数据，则无变化；如果有，则也会减少

### 统一性提升

1. **数据结构统一**
   - 所有接口返回相同的基础结构
   - 可选字段通过参数控制

2. **前端代码简化**
   - 统一从 `reports` 取值
   - 不再需要判断多个路径

3. **维护成本降低**
   - 减少数据同步逻辑
   - 降低不一致风险

## 🔍 检查清单

- [ ] 修改 `/api/analysis/tasks/{task_id}/result` 接口
- [ ] 修改 `/api/reports/{report_id}/detail` 接口
- [ ] 修改 `_build_result_data` 方法
- [ ] 修改 `_extract_reports` 方法
- [ ] 修改 `save_analysis_report` 函数
- [ ] 更新前端代码（移除 state 回退）
- [ ] 测试所有接口
- [ ] 更新 API 文档

## 📝 注意事项

1. **向后兼容**
   - 保留 `include_state` 和 `include_detailed` 参数
   - 默认不返回，但可以通过参数获取

2. **数据库兼容**
   - 现有数据可能包含重复字段
   - 读取时清理，保存时不再保存重复数据

3. **前端兼容**
   - 逐步迁移前端代码
   - 确保所有页面正常显示
