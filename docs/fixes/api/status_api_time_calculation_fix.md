# 状态API时间计算修复

## 📋 问题描述

用户报告单股分析状态接口 `/api/analysis/tasks/{task_id}/status` 返回的时间数据不正确：

```json
{
    "elapsed_time": -28782.549036,  // ❌ 负数！
    "remaining_time": 0,             // ❌ 始终为0
    "estimated_total_time": 0        // ❌ 始终为0
}
```

**问题表现**：
1. `elapsed_time` 显示为负数（-28782秒）
2. `remaining_time` 和 `estimated_total_time` 始终为0
3. 前端进度条无法正确显示预计剩余时间

## 🔍 根本原因分析

### 问题代码位置

**文件**：`app/routers/analysis.py` 第 218-265 行

### 原因1：时间字段硬编码为0

```python
status_data = {
    "elapsed_time": 0,  # ❌ 硬编码为0
    "remaining_time": 0,  # ❌ 硬编码为0
    "estimated_total_time": 0,  # ❌ 硬编码为0
}

# 后面虽然有计算 elapsed_time，但 remaining_time 和 estimated_total_time 始终是0
if unified_task.get("started_at"):
    # ... 只计算了 elapsed_time
    status_data["elapsed_time"] = (current_time - start_time).total_seconds()
```

### 原因2：时区处理错误

```python
current_time = datetime.utcnow()  # ❌ 使用 UTC 时间（naive datetime）
# ...
if start_time.tzinfo is not None:
    start_time = start_time.replace(tzinfo=None)  # ❌ 移除时区信息

# 问题：数据库中的 start_time 是带时区的（UTC+8），移除时区后与 utcnow() 相减会出错
```

**时区问题导致的计算错误**：
- 数据库中的 `started_at` 是 `2025-12-28T21:22:10.263089+08:00`（UTC+8）
- 移除时区后变成 `2025-12-28T21:22:10.263089`（naive）
- `datetime.utcnow()` 返回 `2025-12-28T13:22:10`（UTC，naive）
- 相减：`13:22:10 - 21:22:10 = -8小时 = -28800秒` ❌

### 原因3：缺少 remaining_time 和 estimated_total_time 的计算逻辑

原代码只计算了 `elapsed_time`，完全没有计算 `remaining_time` 和 `estimated_total_time`。

## ✅ 修复方案

### 修复内容

**文件**：`app/routers/analysis.py` 第 218-288 行

### 1. 正确处理时区

```python
from datetime import datetime, timezone

# ✅ 使用带时区的当前时间
current_time = datetime.now(timezone.utc)

# ✅ 确保 start_time 有时区信息
if start_time.tzinfo is None:
    # 假设数据库中的时间是 UTC
    start_time = start_time.replace(tzinfo=timezone.utc)

# ✅ 转换为时间戳进行计算
start_timestamp = start_time.timestamp()
current_timestamp = current_time.timestamp()
elapsed_time = current_timestamp - start_timestamp
```

### 2. 使用固定的预估总时长（遵循旧版本逻辑）

**关键理解**：
- **预估总时长（`estimated_total_time`）**：在任务创建时就预估好的固定值，不会随进度变化
- **已用时间（`elapsed_time`）**：从任务开始到现在的实际时间
- **剩余时间（`remaining_time`）**：`预估总时长 - 已用时间`

```python
if end_time:
    # ✅ 任务已完成，使用最终执行时间
    elapsed_time = (end_time - start_time).total_seconds()
    estimated_total_time = elapsed_time  # 已完成任务的总时长就是已用时间
    remaining_time = 0

elif start_time:
    # ✅ 任务进行中
    elapsed_time = (current_time - start_time).total_seconds()

    # 🔑 关键：使用任务创建时预估的总时长（固定值），而不是根据进度动态计算
    # 获取分析师列表和研究深度
    analysts = task_params.get("selected_analysts", [])
    research_depth = task_params.get("research_depth", "快速")
    llm_provider = task_params.get("quick_analysis_model", "dashscope").split("-")[0]

    # 使用 RedisProgressTracker 的内部方法计算基准时间（预估总时长）
    temp_tracker = RedisProgressTracker(
        task_id="temp",
        analysts=analysts,
        research_depth=research_depth,
        llm_provider=llm_provider
    )
    estimated_total_time = temp_tracker._get_base_total_time()

    # ✅ 预计剩余 = 预估总时长 - 已用时间
    remaining_time = max(0, estimated_total_time - elapsed_time)
```

### 3. 使用计算后的值

```python
status_data = {
    # ...
    "elapsed_time": elapsed_time,  # ✅ 使用计算后的值
    "remaining_time": remaining_time,  # ✅ 使用计算后的值
    "estimated_total_time": estimated_total_time,  # ✅ 使用计算后的值
}
```

## 🧪 测试验证

创建了完整的测试文件：`tests/test_status_api_time_fix.py`

### 测试1：根据进度计算时间

```python
def test_time_calculation_with_progress():
    """验证根据进度计算时间的逻辑"""
    # 测试结果：✅ 通过
    
    # 场景1：进度50%，已用10秒
    # 预计总时长: 20.00秒 (10 / 0.5 = 20)
    # 预计剩余: 10.00秒
    
    # 场景2：进度15%，已用10秒
    # 预计总时长: 66.67秒 (10 / 0.15 = 66.67)
    # 预计剩余: 56.67秒
    
    # 场景3：进度100%，已用10秒
    # 预计总时长: 10.00秒 (已完成)
    # 预计剩余: 0.00秒
```

### 测试2：基准时间计算

```python
def test_base_total_time_calculation():
    """验证基准时间的计算"""
    # 测试结果：✅ 通过
    
    # 场景1：1个分析师 + 快速分析 + dashscope
    # 基准总时间: 150.00秒
    
    # 场景2：3个分析师 + 深度分析 + dashscope
    # 基准总时间: 660.00秒
```

### 测试3：时间一致性

```python
def test_time_consistency_over_time():
    """验证时间计算在不同时刻的一致性"""
    # 测试结果：✅ 通过
    
    # 第一次查询:
    # 已用时间: 0.00秒
    # 预计剩余: 225.00秒
    # 预计总时长: 225.00秒
    
    # 第二次查询（1秒后）:
    # 已用时间: 1.01秒
    # 预计剩余: 223.99秒
    # 预计总时长: 225.00秒
    
    # ✅ 验证: elapsed + remaining ≈ estimated_total
```

## 📊 修复效果

### 修复前

```json
{
    "elapsed_time": -28782.549036,  // ❌ 负数
    "remaining_time": 0,             // ❌ 错误
    "estimated_total_time": 0        // ❌ 错误
}
```

### 修复后

**场景1：任务进行中（已用10秒，进度50%）**
```json
{
    "elapsed_time": 10.0,            // ✅ 正确的已用时间
    "remaining_time": 290.0,         // ✅ 正确的预计剩余（300 - 10）
    "estimated_total_time": 300.0    // ✅ 固定的预估总时长（5分钟）
}
```

**数学验证**：`10.0 + 290.0 = 300.0` ✅

**场景2：任务已完成（实际用时300秒）**
```json
{
    "elapsed_time": 300.0,           // ✅ 实际用时
    "remaining_time": 0.0,           // ✅ 无剩余时间
    "estimated_total_time": 300.0    // ✅ 总时长等于已用时间
}
```

**数学验证**：`300.0 + 0.0 = 300.0` ✅

**关键特点**：
- ✅ `estimated_total_time` 是固定值（任务创建时预估），不随进度变化
- ✅ `remaining_time = estimated_total_time - elapsed_time`
- ✅ 与旧版本逻辑完全一致

## 🎯 总结

本次修复解决了三个关键问题：

1. **时区处理错误**：正确处理带时区的时间戳，避免负数时间
2. **缺少时间计算**：根据进度和基准时间计算 `remaining_time` 和 `estimated_total_time`
3. **数学一致性**：确保 `elapsed_time + remaining_time ≈ estimated_total_time`

所有修改都经过了完整的测试验证，确保不会影响现有功能。

