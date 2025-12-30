# 完整修复总结

## 📋 修复的问题

用户报告了单股分析页面的多个问题：

1. ❌ **步骤名称显示英文**：`neutral_analyst_v2` 等节点显示英文而不是中文
2. ❌ **步骤名称和消息相同**：`current_step_name` 和 `message` 应该不同
3. ❌ **时间计算不正确**：`elapsed_time` 为负数，`remaining_time` 和 `estimated_total_time` 为0
4. ❌ **结果API不支持v2引擎**：`/api/analysis/tasks/{task_id}/result` 返回404

## ✅ 修复方案

### 1. 节点映射修复

**问题**：
- `neutral_analyst_v2` 等 v2 风险分析师节点没有映射
- `current_step_name` 和 `message` 返回相同的值

**修复**：
- **文件**：`core/workflow/engine.py`
- **内容**：
  1. 添加所有 v2 风险分析师节点映射：
     - `risky_analyst_v2` → ("激进分析师", "⚡ 激进分析师正在评估高风险机会...")
     - `safe_analyst_v2` → ("保守分析师", "🛡️ 保守分析师正在评估风险因素...")
     - `neutral_analyst_v2` → ("中性分析师", "⚖️ 中性分析师正在平衡风险收益...")
     - `risk_manager_v2` → ("风险管理者", "👔 风险管理者正在做最终决策...")
  2. 修改映射格式：`(progress, message, step_name)`
     - `step_name`：简短的中文名称（如 "市场分析师"）
     - `message`：详细的描述（如 "📈 市场分析师正在分析技术指标和市场趋势..."）
  3. 更新所有 v1 和 v2 节点的映射

**效果**：
```json
{
    "current_step_name": "中性分析师",  // ✅ 简短的中文名称
    "message": "⚖️ 中性分析师正在平衡风险收益..."  // ✅ 详细的描述
}
```

### 2. 时间计算修复

**问题**：
- `elapsed_time` 显示为负数（-28782秒）
- `remaining_time` 和 `estimated_total_time` 始终为0
- 时区处理错误导致时间计算错误

**修复**：
- **文件**：`app/routers/analysis.py`
- **内容**：
  1. 修复时区处理：使用 `datetime.now(timezone.utc)` 而不是 `datetime.utcnow()`
  2. 遵循旧版本逻辑：
     - **预估总时长**：任务创建时预估的固定值（不随进度变化）
     - **已用时间**：从任务开始到现在的实际时间
     - **剩余时间**：`预估总时长 - 已用时间`
  3. 使用 `RedisProgressTracker._get_base_total_time()` 计算预估总时长

**效果**：
```json
{
    "elapsed_time": 10.0,            // ✅ 正确的已用时间
    "remaining_time": 290.0,         // ✅ 正确的预计剩余
    "estimated_total_time": 300.0    // ✅ 固定的预估总时长
}
```

**数学验证**：`10.0 + 290.0 = 300.0` ✅

### 3. 结果API修复

**问题**：
- `/api/analysis/tasks/{task_id}/result` 接口只从 `analysis_reports` 和 `analysis_tasks` 集合查询
- v2 引擎的任务结果保存在 `unified_analysis_tasks` 集合中
- 导致 v2 引擎任务返回404

**修复**：
- **文件**：`app/routers/analysis.py`
- **内容**：
  1. 优先从 `unified_analysis_tasks` 集合查询（v2 引擎任务）
  2. 如果没找到，再从 `analysis_reports` 集合查询（v1 引擎任务）
  3. 最后从 `analysis_tasks` 集合查询（兜底）
  4. 正确处理 `execution_time` 的计算（支持 datetime 对象和字符串）

**效果**：
```
请求: GET /api/analysis/tasks/{task_id}/result
响应: 200 OK
数据: {
    "analysis_id": "...",
    "stock_symbol": "000001",
    "summary": "...",
    "decision": {...},
    "source": "unified_tasks"  // ✅ 标记数据来源
}
```

## 📝 修改的文件

1. **`core/workflow/engine.py`**
   - 添加 v2 风险分析师节点映射
   - 修改映射格式，区分 `step_name` 和 `message`
   - 更新所有节点的映射

2. **`app/routers/analysis.py`**
   - 修复 `/tasks/{task_id}/status` 接口的时间计算
   - 修复 `/tasks/{task_id}/result` 接口的数据源查询
   - 区分 `current_step_name` 和 `message` 字段

3. **`app/services/unified_analysis_service.py`**
   - 修改进度回调，正确设置 `current_step_name` 和 `current_step_description`
   - 从 `kwargs` 中提取 `step_name` 参数

4. **`app/services/unified_analysis_engine.py`**
   - 修改 `wrapped_progress_callback`，正确设置 `task.current_step` 和 `task.message`
   - 从 `kwargs` 中提取 `step_name` 参数

5. **`app/services/progress/tracker.py`**
   - 修改 `update_progress()` 方法，优先使用手动提供的 `current_step_name` 和 `current_step_description`
   - 避免自动检测的步骤名称覆盖工作流引擎提供的值

6. **`app/models/analysis.py`**
   - 在 `UnifiedAnalysisTask` 模型中添加 `message` 字段

7. **测试文件**
   - `tests/test_node_mapping_fix.py` - 测试 v2 风险分析师节点映射
   - `tests/test_status_api_time_fix.py` - 测试固定预估总时长的时间计算逻辑
   - `tests/test_step_name_message_separation.py` - 测试步骤名称和消息的分离

8. **文档**
   - `docs/fixes/api/status_api_time_calculation_fix.md`
   - `docs/fixes/api/result_api_unified_tasks_support.md`
   - `docs/fixes/summary/complete_fix_summary.md`

## 🧪 测试验证

所有测试都通过了：

```
✅ test_v2_risk_analysts_mapping - v2 风险分析师节点映射
✅ test_all_v2_nodes_mapping - 所有 v2 节点映射
✅ test_step_name_vs_message_difference - 步骤名称和消息的区别
✅ test_v1_nodes_also_updated - v1 节点也更新了
✅ test_time_calculation_with_fixed_total - 固定预估总时长的时间计算
✅ test_base_total_time_calculation - 基准时间计算
✅ test_time_consistency_over_time - 时间一致性
```

## 🚀 下一步

请**重启后端服务**，然后测试：

1. 发起一个新的单股分析任务（使用 `engine: "v2"`）
2. 查看进度显示：
   - ✅ 步骤名称应该显示简短的中文（如 "中性分析师"）
   - ✅ 消息应该显示详细的描述（如 "⚖️ 中性分析师正在平衡风险收益..."）
   - ✅ 时间数据应该一致且为正数
   - ✅ `elapsed_time + remaining_time ≈ estimated_total_time`
3. 等待任务完成后，查看结果：
   - ✅ `/api/analysis/tasks/{task_id}/result` 应该能正常返回结果

## 📊 修复效果对比

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| 步骤名称 | `🔍 正在执行: neutral_analyst_v2` | `中性分析师` ✅ |
| 消息 | `🔍 正在执行: neutral_analyst_v2` | `⚖️ 中性分析师正在平衡风险收益...` ✅ |
| 已用时间 | `-28782.549036` 秒 | `10.0` 秒 ✅ |
| 剩余时间 | `0` 秒 | `290.0` 秒 ✅ |
| 预计总时长 | `0` 秒 | `300.0` 秒 ✅ |
| 结果API | 404 Not Found | 200 OK ✅ |

所有问题都已修复！🎉

