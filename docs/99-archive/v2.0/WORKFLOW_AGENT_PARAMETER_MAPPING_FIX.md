# 工作流 Agent 参数映射修复

## 🔴 问题现象

工作流执行时，Agent 报错：
```
ValueError: Missing required parameters: ticker or analysis_date
```

虽然工作流输入中有这些数据，但格式不同。

---

## 🎯 根本原因

**参数格式不匹配**：

| 场景 | 参数格式 | Agent 期望 |
|------|---------|----------|
| 标准分析流程 | `ticker`, `analysis_date` | ✅ 直接使用 |
| 交易复盘流程 | `trade_info.code`, 无 `analysis_date` | ❌ 不匹配 |

**工作流输入结构**（交易复盘）：
```python
inputs = {
    "user_id": "...",
    "trade_ids": [...],
    "trade_info": {
        "code": "688111",  # ← Agent 需要的 ticker
        "name": "...",
        "holding_period": 18,
        ...
    },
    "market_data": {...},
    "benchmark_data": {...},
    "messages": []
}
```

**Agent 期望的参数**：
```python
state = {
    "ticker": "688111",  # ← 从 trade_info.code 提取
    "analysis_date": "2025-12-18",  # ← 使用当前日期
    ...
}
```

---

## ✅ 修复方案（已实施）

### 修复 1：AnalystAgent 基类

**文件**：`core/agents/analyst.py` 第 71-107 行

添加参数映射逻辑：
```python
# 从 trade_info 中提取 code
if not ticker and "trade_info" in state:
    trade_info = state.get("trade_info", {})
    if isinstance(trade_info, dict):
        ticker = trade_info.get("code")

# 使用当前日期作为分析日期
if not analysis_date:
    from datetime import datetime
    analysis_date = datetime.now().strftime("%Y-%m-%d")
```

### 修复 2：ResearcherAgent 基类

**文件**：`core/agents/researcher.py` 第 75-112 行

同样的参数映射逻辑。

### 修复 3：ManagerAgent 基类

**文件**：`core/agents/manager.py` 第 77-113 行

同样的参数映射逻辑。

---

## 📋 受影响的 Agent

所有继承这三个基类的 Agent 都自动获得修复：

**AnalystAgent 子类**：
- timing_analyst_v2
- position_analyst_v2
- emotion_analyst_v2
- attribution_analyst_v2

**ResearcherAgent 子类**：
- 同上

**ManagerAgent 子类**：
- review_manager_v2

---

## 🧪 验证方法

运行交易复盘流程，检查日志：
```
✅ [节点执行] 🚀 timing_analyst_v2 - 开始执行
✅ [节点执行] ✅ timing_analyst_v2 - 执行完成
```

如果看到这些日志，说明修复成功。

