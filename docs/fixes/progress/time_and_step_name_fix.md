# 进度跟踪时间计算和步骤名称修复

## 📋 问题描述

用户报告了两个问题：

### 1. 时间计算不正确
- **问题**：已用时间、预计剩余时间、预计总时长的数值不一致
- **表现**：前端显示的三个时间字段无法满足数学关系：`已用时间 + 预计剩余 ≈ 预计总时长`

### 2. 步骤名称显示英文
- **问题**：v2 版本的 Agent 节点名称（如 `market_analyst_v2`）没有映射到中文友好名称
- **表现**：前端显示 `market_analyst_v2` 而不是 "📈 市场分析师正在分析技术指标和市场趋势..."

## 🔍 根本原因分析

### 问题1：时间计算不一致

**原因**：`RedisProgressTracker.to_dict()` 方法直接从 `progress_data` 字典中获取时间字段，而没有实时重新计算。

**代码位置**：`app/services/progress/tracker.py` 第 453-471 行

**问题代码**：
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        'elapsed_time': self.progress_data.get('elapsed_time', 0),  # ❌ 使用缓存值
        'remaining_time': self.progress_data.get('remaining_time', 0),  # ❌ 使用缓存值
        'estimated_total_time': self.progress_data.get('estimated_total_time', 0),  # ❌ 使用缓存值
    }
```

**影响**：
- 当调用 `to_dict()` 时，返回的是上次 `update_progress()` 时计算的时间
- 如果两次调用之间有时间间隔，`elapsed_time` 就会过时
- 导致 `elapsed_time + remaining_time ≠ estimated_total_time`

### 问题2：v2 节点名称未映射

**原因**：`core/workflow/engine.py` 中的 `_get_node_progress_info()` 方法只有 v1 版本的节点映射，缺少 v2 版本。

**代码位置**：`core/workflow/engine.py` 第 334-382 行

**问题代码**：
```python
node_mapping = {
    "market_analyst": (15, "📈 市场分析师...", "market_analyst"),  # ✅ v1 有映射
    # ❌ 缺少 v2 映射
}
```

**影响**：
- v2 版本的节点（如 `market_analyst_v2`）找不到映射
- 返回默认消息：`f"🔍 正在执行: {node_name}"`
- 前端显示英文节点ID而不是中文友好名称

## ✅ 修复方案

### 修复1：实时计算时间

**文件**：`app/services/progress/tracker.py`

**修改内容**：
```python
def to_dict(self) -> Dict[str, Any]:
    try:
        # 🔧 实时计算时间估算，确保返回最新的时间信息
        elapsed, remaining, est_total = self._calculate_time_estimates()
        
        return {
            'task_id': self.task_id,
            'analysts': self.analysts,
            'research_depth': self.research_depth,
            'llm_provider': self.llm_provider,
            'steps': [asdict(step) for step in self.analysis_steps],
            'start_time': self.progress_data.get('start_time'),
            'elapsed_time': elapsed,  # ✅ 使用实时计算的值
            'remaining_time': remaining,  # ✅ 使用实时计算的值
            'estimated_total_time': est_total,  # ✅ 使用实时计算的值
            'progress_percentage': self.progress_data.get('progress_percentage', 0),
            'status': self.progress_data.get('status', 'pending'),
            'current_step': self.progress_data.get('current_step'),
            'current_step_name': self.progress_data.get('current_step_name', ''),
            'current_step_description': self.progress_data.get('current_step_description', ''),
            'last_message': self.progress_data.get('last_message', ''),
            'last_update': self.progress_data.get('last_update', time.time()),
        }
    except Exception as e:
        logger.error(f"[RedisProgress] to_dict failed: {self.task_id} - {e}")
        return self.progress_data
```

**效果**：
- 每次调用 `to_dict()` 都会重新计算时间
- 确保 `elapsed_time + remaining_time ≈ estimated_total_time`
- 时间数据始终是最新的

### 修复2：添加 v2 节点映射

**文件**：`core/workflow/engine.py`

**修改内容**：
```python
node_mapping = {
    # === v2.0 分析师节点 ===
    "market_analyst_v2": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "market_analyst_v2"),
    "fundamentals_analyst_v2": (25, "💰 基本面分析师正在分析财务数据...", "fundamentals_analyst_v2"),
    "news_analyst_v2": (35, "📰 新闻分析师正在分析相关新闻和事件...", "news_analyst_v2"),
    "social_analyst_v2": (40, "💬 社媒分析师正在分析社交媒体情绪...", "social_analyst_v2"),
    "sector_analyst_v2": (20, "📊 板块分析师正在分析行业趋势...", "sector_analyst_v2"),
    "index_analyst_v2": (10, "📈 大盘分析师正在分析市场环境...", "index_analyst_v2"),
    
    # === v2.0 研究团队 ===
    "bull_researcher_v2": (50, "🐂 看多研究员正在构建看多观点...", "bull_researcher_v2"),
    "bear_researcher_v2": (55, "🐻 看空研究员正在构建看空观点...", "bear_researcher_v2"),
    "research_manager_v2": (60, "🔬 研究经理正在综合研究观点...", "research_manager_v2"),
    
    # === v2.0 交易团队 ===
    "trader_v2": (70, "💼 交易员正在制定交易计划...", "trader_v2"),
    
    # === v2.0 风险管理团队 ===
    "risk_manager_v2": (90, "👔 风险管理者正在做最终决策...", "risk_manager_v2"),
    
    # === v1.0 节点（向后兼容）===
    # ... 保留原有的 v1 映射 ...
}
```

**效果**：
- v2 版本的节点现在有了中文友好名称
- 前端显示正确的中文描述
- 保持向后兼容（v1 节点仍然工作）

## 🧪 测试验证

创建了完整的测试文件：`tests/test_progress_time_fix.py`

### 测试1：时间计算一致性
```python
def test_time_calculation_consistency():
    """验证 elapsed_time + remaining_time ≈ estimated_total_time"""
    # 测试结果：✅ 通过
    # 已用时间: 1.02秒
    # 预计剩余: 658.98秒
    # 预计总时长: 660.00秒
    # 差值: 0.00秒
```

### 测试2：v2 节点名称映射
```python
def test_v2_node_name_mapping():
    """验证 v2 节点有正确的中文映射"""
    # 测试结果：✅ 通过
    # market_analyst_v2 → "📈 市场分析师正在分析技术指标和市场趋势..."
```

### 测试3：时间重新计算
```python
def test_progress_update_time_recalculation():
    """验证每次调用 to_dict() 都会重新计算时间"""
    # 测试结果：✅ 通过
    # 第一次已用时间: 0.52秒
    # 第二次已用时间: 1.53秒（增加了1秒）
```

## 📊 修复效果

### 修复前
- ❌ 时间数据不一致：`80 + 280 ≠ 780`
- ❌ 步骤名称显示英文：`market_analyst_v2`

### 修复后
- ✅ 时间数据一致：`1.02 + 658.98 = 660.00`
- ✅ 步骤名称显示中文：`📈 市场分析师正在分析技术指标和市场趋势...`

## 🎯 总结

本次修复解决了两个关键问题：

1. **时间计算准确性**：通过实时计算确保时间数据的数学一致性
2. **用户体验**：通过添加 v2 节点映射提供友好的中文提示

所有修改都经过了完整的测试验证，确保不会影响现有功能。

