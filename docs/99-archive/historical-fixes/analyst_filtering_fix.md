# 分析师动态裁剪功能修复

## 📋 问题描述

**问题**: v2.0 工作流引擎在执行股票分析时，即使前端只选择了部分分析师（如"市场分析师"和"基本面分析师"），后端仍然会运行所有分析师（包括"新闻分析师"和"社媒分析师"）。

**影响**:
- 用户无法自定义分析师组合
- 浪费 LLM Token 和执行时间
- 前端选择器失效

**根本原因**: `selected_analysts` 参数没有正确传递到 `WorkflowBuilder`。

---

## 🔍 问题定位

### 数据流追踪

```
前端 (SingleAnalysis.vue)
  ↓ selected_analysts: ["market", "fundamentals"]
API 路由 (/api/analysis/single)
  ↓ task_params.selected_analysts
UnifiedAnalysisEngine._execute_via_workflow()
  ↓ workflow_inputs.selected_analysts
  ❌ legacy_config (缺少 selected_analysts)
  ↓
WorkflowAPI.execute()
  ↓ legacy_config
WorkflowBuilder.__init__()
  ↓ self._selected_analysts = None  ❌ 未接收到参数
  ↓
_filter_analyst_nodes()
  ↓ 因为 self._selected_analysts 为空，跳过过滤
  ↓
✅ 所有分析师节点都被保留
```

### 关键代码位置

**问题代码** (`app/services/unified_analysis_engine.py:385-394`):
```python
# 准备遗留配置（LLM配置等）
legacy_config = {
    "preference_type": task.preference_type,
}

# 从任务参数中提取 LLM 配置
if "quick_analysis_model" in workflow_inputs:
    legacy_config["quick_think_llm"] = workflow_inputs["quick_analysis_model"]
if "deep_analysis_model" in workflow_inputs:
    legacy_config["deep_think_llm"] = workflow_inputs["deep_analysis_model"]
```

**问题**: `legacy_config` 中缺少 `selected_analysts` 字段。

---

## ✅ 修复方案

### 修改文件

**文件**: `app/services/unified_analysis_engine.py`

**修改位置**: `_execute_via_workflow` 方法（第 381-400 行）

**修改内容**:

```python
self.logger.info(f"📦 工作流输入参数: ticker={workflow_inputs.get('ticker')}, "
                f"analysis_date={workflow_inputs.get('analysis_date')}, "
                f"research_depth={workflow_inputs.get('research_depth')}, "
                f"selected_analysts={workflow_inputs.get('selected_analysts')}")  # 🆕 添加日志

# 准备遗留配置（LLM配置等）
legacy_config = {
    "preference_type": task.preference_type,
}

# 🔑 关键：从任务参数中提取 selected_analysts（用于动态裁剪工作流）
if "selected_analysts" in workflow_inputs:
    legacy_config["selected_analysts"] = workflow_inputs["selected_analysts"]
    self.logger.info(f"🎯 选中的分析师: {workflow_inputs['selected_analysts']}")  # 🆕 添加日志

# 从任务参数中提取 LLM 配置
if "quick_analysis_model" in workflow_inputs:
    legacy_config["quick_think_llm"] = workflow_inputs["quick_analysis_model"]
if "deep_analysis_model" in workflow_inputs:
    legacy_config["deep_think_llm"] = workflow_inputs["deep_analysis_model"]
```

**关键改动**:
1. ✅ 添加 `selected_analysts` 到 `legacy_config`
2. ✅ 添加日志输出，便于调试

---

## 🧪 测试验证

### 测试脚本

**文件**: `scripts/test_analyst_filtering.py`

**使用方法**:
```bash
python scripts/test_analyst_filtering.py
```

**测试场景**:
- 只选择"市场分析师"和"基本面分析师"
- 验证"新闻分析师"和"社媒分析师"是否被正确跳过

**预期结果**:
```
✅ 市场分析师报告已生成
✅ 基本面分析师报告已生成
✅ 新闻分析师报告正确跳过
✅ 社媒分析师报告正确跳过
```

### 手动测试

1. 打开前端单股分析页面
2. 选择股票代码（如 `000858`）
3. 只勾选"市场分析师"和"基本面分析师"
4. 点击"开始分析"
5. 观察后端日志：
   ```
   📦 工作流输入参数: ticker=000858, analysis_date=2026-01-07, research_depth=快速, selected_analysts=['market', 'fundamentals']
   🎯 选中的分析师: ['market', 'fundamentals']
   [WorkflowBuilder] 将过滤以下分析师节点: {'news_analyst', 'social_analyst'}
   ```

---

## 📊 影响范围

### 修改的文件

#### 后端
1. ✅ `app/services/unified_analysis_engine.py` (第 381-400 行)
   - 添加 `selected_analysts` 到 `legacy_config`
   - 添加日志输出

2. ✅ `app/routers/workflows.py` (第 85-102 行)
   - 在 `WorkflowExecuteRequest` 中添加 `selected_analysts` 字段
   - 在 `_build_legacy_config` 函数中添加 `selected_analysts` 支持

#### 前端
3. ✅ `frontend/src/views/Workflow/Execute.vue` (第 221-230, 339-349 行)
   - 在 `inputs` 中添加 `selected_analysts` 字段
   - 在 API 调用中传递 `selected_analysts` 参数

### 不需要修改的文件
- ✅ `core/workflow/builder.py` - 过滤逻辑已正确实现
- ✅ `frontend/src/views/Analysis/SingleAnalysis.vue` - 前端传参正确
- ✅ `app/routers/analysis.py` - 路由层传参正确

---

## 🔗 相关代码

### WorkflowBuilder 过滤逻辑

**文件**: `core/workflow/builder.py:742-800`

```python
def _filter_analyst_nodes(self, definition: WorkflowDefinition) -> WorkflowDefinition:
    """根据 selected_analysts 过滤工作流定义中的分析师节点"""
    
    # 如果没有 selected_analysts 配置，返回原始定义
    if not self._selected_analysts:
        return definition
    
    # 收集要移除的分析师节点 ID
    nodes_to_remove: Set[str] = set()
    for node in definition.nodes:
        if not self._is_analyst_selected(node):
            nodes_to_remove.add(node.id)
    
    logger.info(f"[WorkflowBuilder] 将过滤以下分析师节点: {nodes_to_remove}")
    
    # 创建新的节点列表（排除被过滤的节点）
    new_nodes = [n for n in definition.nodes if n.id not in nodes_to_remove]
    
    # 重新构建边（移除与被过滤节点相关的边）
    new_edges = [e for e in definition.edges 
                 if e.source not in nodes_to_remove and e.target not in nodes_to_remove]
    
    return WorkflowDefinition(...)
```

---

## 📝 总结

**问题**: `selected_analysts` 参数未传递到 `WorkflowBuilder`
**原因**: `legacy_config` 中缺少该字段
**修复**:
1. 在 `unified_analysis_engine.py` 中添加 `selected_analysts` 到 `legacy_config`
2. 在 `workflows.py` 中添加 `selected_analysts` 字段到 `WorkflowExecuteRequest`
3. 在前端工作流执行页面添加 `selected_analysts` 参数

**验证**: 通过测试脚本和手动测试确认修复生效

---

## 🔄 完整数据流（修复后）

```
前端 (SingleAnalysis.vue)
  ↓ selected_analysts: ["market", "fundamentals"]
API 路由 (/api/analysis/single)
  ↓ task_params.selected_analysts
UnifiedAnalysisEngine._execute_via_workflow()
  ↓ workflow_inputs.selected_analysts
  ✅ legacy_config.selected_analysts  ← 修复点 1
  ↓
WorkflowAPI.execute()
  ↓ legacy_config
WorkflowBuilder.__init__()
  ✅ self._selected_analysts = ["market", "fundamentals"]  ← 正确接收
  ↓
_filter_analyst_nodes()
  ✅ 过滤未选中的分析师节点
  ↓
✅ 只保留选中的分析师节点
```

---

**修复日期**: 2026-01-07
**修复人员**: Augment AI
**相关 Issue**: 分析师动态裁剪功能失效

