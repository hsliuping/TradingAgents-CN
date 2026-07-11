# 工作流类型化改造技术设计

| 字段 | 内容 |
|------|------|
| 版本 | v3.0.0 |
| 状态 | 待实现 |
| 创建日期 | 2026-07-11 |
| 关联需求 | [工作流类型化改造需求文档](./workflow-typing-requirements.md) |

## 一、现状分析

### 1.1 后端已完成类型化（70%）

| 文件 | 已实现能力 |
|------|-----------|
| [default_workflow_provider.py](file:///c:/TradingAgentsCN/core/workflow/default_workflow_provider.py) | `WORKFLOW_TYPE_DEFAULTS`、`infer_workflow_type()`、`get_active_workflow_id(type)`、`set_active_workflow_id(id, name, type)` |
| [unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py) | `_workflow_type_for_task()` 将任务类型映射为 workflow_type，`_resolve_workflow_id()` 按类型解析 |
| [workflow_api.py](file:///c:/TradingAgentsCN/core/api/workflow_api.py) | 创建/更新时写入 `workflow_type` 顶层字段，已创建索引 |
| [workflows.py](file:///c:/TradingAgentsCN/app/routers/workflows.py) | `WorkflowCreate`/`WorkflowUpdate` 已支持 `workflow_type` 字段，`set_as_default` 已按类型设置 |
| [workflow_registry.py](file:///c:/TradingAgentsCN/app/services/workflow_registry.py) | 已按任务类型注册 5 种工作流 |

### 1.2 前端是主要短板（30%）

| 文件 | 问题 |
|------|------|
| [SingleAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue) | `selectedWorkflowId` 定义了但 `submitAnalysis()` 不传递给后端（Bug） |
| [Workflow/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/index.vue) | 使用硬编码 `isStockAnalysisWorkflow()` 判断类型，无类型分组展示 |
| [WorkflowGeneration.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/WorkflowGeneration.vue) | AI 创建时不设置 `workflow_type` |
| [Editor.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Editor.vue) | 部分支持，但无类型显示/编辑 UI |
| [workflow.ts](file:///c:/TradingAgentsCN/frontend/src/api/workflow.ts) | `WorkflowDefinition` 接口缺少 `workflow_type` 字段 |

### 1.3 AI 生成工作流条件分支缺陷

| 文件 | 问题 |
|------|------|
| [workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) | `PlannedEdge` 缺少 `type` 和 `condition` 字段 |
| [workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py) | `_blueprint_to_workflow_dict()` 将所有边硬编码为 `"normal"` |

## 二、技术方案

### 2.1 P0 改动

#### 2.1.1 修复 SingleAnalysis.vue 的 workflow_id 传递

**文件**：[SingleAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue)

**改动位置**：`submitAnalysis()` 方法（约第 1303-1452 行），构造 `SingleAnalysisRequest` 处（约第 1382-1397 行）

**改动内容**：
```typescript
// 修改前
const request: SingleAnalysisRequest = {
  symbol: analysisForm.symbol,
  stock_code: analysisForm.symbol,
  parameters: {
    market_type: analysisForm.market,
    analysis_date: ...,
    research_depth: ...,
    selected_analysts: ...,
    engine: 'v2'
  }
}

// 修改后
const request: SingleAnalysisRequest = {
  symbol: analysisForm.symbol,
  stock_code: analysisForm.symbol,
  workflow_id: selectedWorkflowId.value,  // 新增：传递用户选择的工作流
  parameters: {
    market_type: analysisForm.market,
    analysis_date: ...,
    research_depth: ...,
    selected_analysts: ...,
    engine: 'v2'
  }
}
```

**代码量**：约 5 行

#### 2.1.2 WorkflowDefinition 模型增加 workflow_type 字段

**文件**：[core/workflow/models.py](file:///c:/TradingAgentsCN/core/workflow/models.py) 的 `WorkflowDefinition` 类（约第 108 行）

**改动内容**：
```python
class WorkflowDefinition(BaseModel):
    # ... 现有字段 ...
    workflow_type: Optional[str] = None  # 新增：流程类型
```

**代码量**：约 2 行

#### 2.1.3 模板补充 workflow_type

**文件 1**：[v2_stock_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_stock_analysis_workflow.py)

在 config 字典中补充：
```python
config = {
    # ... 现有配置 ...
    "workflow_type": "stock_analysis",  # 新增
}
```

**文件 2**：[v2_etf_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_etf_analysis_workflow.py)

在 config 字典中补充：
```python
config = {
    # ... 现有配置 ...
    "workflow_type": "etf_analysis",  # 新增
}
```

**代码量**：每个文件 1 行，共 2 行

#### 2.1.4 前端 API 接口补字段

**文件**：[workflow.ts](file:///c:/TradingAgentsCN/frontend/src/api/workflow.ts) 的 `WorkflowDefinition` 接口（约第 34 行）

**改动内容**：
```typescript
export interface WorkflowDefinition {
  // ... 现有字段 ...
  workflow_type?: string  // 新增
}
```

**代码量**：1 行

#### 2.1.5 AI 生成服务设置 workflow_type

**文件**：[workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py)

**改动 1**：`confirm_and_create()` 方法接收 `workflow_type` 参数

```python
async def confirm_and_create(
    self,
    session_id: str,
    workflow_type: Optional[str] = None  # 新增参数
) -> Dict[str, Any]:
    # ... 现有逻辑 ...
```

**改动 2**：`_blueprint_to_workflow_dict()` 设置 `workflow_type`

```python
def _blueprint_to_workflow_dict(self, blueprint, workflow_type: Optional[str] = None):
    # ... 现有逻辑 ...
    workflow_dict = {
        # ... 现有字段 ...
        "workflow_type": workflow_type or self._infer_type_from_blueprint(blueprint),  # 新增
    }
    return workflow_dict
```

**改动 3**：新增 `_infer_type_from_blueprint()` 辅助方法（当用户未显式选择时，从蓝图推断）

**代码量**：约 15 行

#### 2.1.6 AI 生成工作流支持条件分支

**文件 1**：[workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) 的 `PlannedEdge` 类（约第 57-63 行）

**改动内容**：
```python
class PlannedEdge(BaseModel):
    """规划的边"""
    id: str
    source: str
    target: str
    label: Optional[str] = None
    animated: bool = False
    type: Optional[str] = "normal"  # 新增：edge 类型（normal/conditional）
    condition: Optional[str] = None  # 新增：条件表达（"true"/"false"）
```

**文件 2**：[workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py) 的 `_blueprint_to_workflow_dict()`（约第 736-745 行）

**改动内容**：
```python
# 修改前
edges.append({
    "id": e.id,
    "source": e.source,
    "target": e.target,
    "type": "normal",  # 硬编码
    "label": e.label,
    "animated": e.animated,
})

# 修改后
edges.append({
    "id": e.id,
    "source": e.source,
    "target": e.target,
    "type": e.type or "normal",  # 从蓝图读取
    "condition": e.condition,  # 新增：传递条件
    "label": e.label,
    "animated": e.animated,
})
```

**文件 3**：[workflow_planner.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_planner.py) 的 System Prompt

在 System Prompt 中增加条件分支的使用说明，让 AI 知道如何生成条件边。

**代码量**：约 20 行

### 2.2 P1 改动

#### 2.2.1 流程列表页按类型分组展示

**文件**：[Workflow/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/index.vue)

**改动 1**：新增类型配置常量

```typescript
const WORKFLOW_TYPE_CONFIG = {
  stock_analysis: { label: '单股研究流程', icon: 'Document' },
  etf_analysis: { label: 'ETF 分析流程', icon: 'DataAnalysis' },
  position_analysis: { label: '持仓分析流程', icon: 'Wallet' },
  trade_review: { label: '操作复盘流程', icon: 'Refresh' },
  portfolio_health: { label: '组合健康度流程', icon: 'Monitor' },
  general: { label: '通用研究流程', icon: 'Search' },
}
```

**改动 2**：替换 `isStockAnalysisWorkflow()` 硬编码判断

```typescript
// 修改前：通过 ID/名称字符串匹配判断
function isStockAnalysisWorkflow(wf) {
  return wf.id?.includes('stock') || wf.name?.includes('股票')
}

// 修改后：通过 workflow_type 字段判断
function getWorkflowType(wf) {
  return wf.workflow_type || wf.config?.workflow_type || 'general'
}
```

**改动 3**：`sortedTemplates` 计算属性按类型分组

```typescript
const groupedTemplates = computed(() => {
  const groups = {}
  for (const wf of workflows.value) {
    const type = getWorkflowType(wf)
    if (!groups[type]) groups[type] = []
    groups[type].push(wf)
  }
  return groups
})
```

**改动 4**：创建工作流对话框增加类型选择器

```vue
<el-form-item label="流程类型" required>
  <el-select v-model="newWorkflow.workflow_type" placeholder="选择流程类型">
    <el-option
      v-for="(config, type) in WORKFLOW_TYPE_CONFIG"
      :key="type"
      :label="config.label"
      :value="type"
    />
  </el-select>
</el-form-item>
```

**改动 5**：`createWorkflow()` 传递 `workflow_type`

```typescript
async function createWorkflow() {
  const result = await workflowApi.create({
    name: newWorkflow.name,
    description: newWorkflow.description,
    workflow_type: newWorkflow.workflow_type,  // 新增
  })
  // ...
}
```

**代码量**：约 80 行

#### 2.2.2 AI 创建流程增加类型选择

**文件**：[WorkflowGeneration.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/WorkflowGeneration.vue)

**改动 1**：在需求描述之前增加类型选择步骤

```vue
<el-step title="选择类型" />
<el-step title="描述需求" />
<el-step title="确认方案" />
<el-step title="自动补全" />
<el-step title="完成" />
```

**改动 2**：类型选择步骤的 UI

```vue
<div class="type-selector">
  <h3>你要创建什么类型的分析流程？</h3>
  <el-radio-group v-model="selectedWorkflowType">
    <el-radio label="stock_analysis">单股研究流程</el-radio>
    <el-radio label="etf_analysis">ETF 分析流程</el-radio>
    <el-radio label="position_analysis">持仓分析流程</el-radio>
    <el-radio label="trade_review">操作复盘流程</el-radio>
    <el-radio label="general">通用研究流程</el-radio>
  </el-radio-group>
  <p class="type-description">{{ getTypeDescription(selectedWorkflowType) }}</p>
</div>
```

**改动 3**：`confirmAndCreate()` 传递 `workflow_type`

```typescript
async function confirmAndCreate() {
  const result = await workflowGenerationApi.confirm(sessionId, {
    workflow_type: selectedWorkflowType.value,  // 新增
  })
  // ...
}
```

**代码量**：约 50 行

#### 2.2.3 流程编辑器显示类型

**文件**：[Editor.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Editor.vue)

**改动 1**：编辑器顶部显示类型

```vue
<div class="workflow-type-display">
  <span class="label">流程类型：</span>
  <el-tag>{{ getWorkflowTypeLabel(workflow.workflow_type) }}</el-tag>
  <el-button text @click="showTypeEditor = true">修改</el-button>
</div>
```

**改动 2**：类型修改对话框

```vue
<el-dialog v-model="showTypeEditor" title="修改流程类型">
  <el-select v-model="editingType">
    <el-option
      v-for="(config, type) in WORKFLOW_TYPE_CONFIG"
      :key="type"
      :label="config.label"
      :value="type"
    />
  </el-select>
</el-dialog>
```

**改动 3**：`saveWorkflow()` 时传递 `workflow_type`

```typescript
async function saveWorkflow() {
  await workflowApi.update(workflow.value.id, {
    workflow_type: workflow.value.workflow_type,  // 新增
    // ... 其他字段
  })
}
```

**代码量**：约 30 行

## 三、数据流设计

### 3.1 创建工作流的数据流

```
用户选择类型 + 描述需求
        ↓
前端 WorkflowGeneration.vue
  - selectedWorkflowType
  - 调用 API 传递 workflow_type
        ↓
后端 workflow_generation_service.py
  - confirm_and_create(workflow_type)
  - _blueprint_to_workflow_dict(workflow_type)
        ↓
后端 workflow_api.py
  - create(workflow_type)
  - 写入 MongoDB workflows 集合
  - workflow_type 作为顶层字段
        ↓
MongoDB workflows 集合
  - { _id, name, workflow_type, nodes, edges, ... }
```

### 3.2 使用工作流的数据流（单股研究）

```
用户在单股研究页面提交分析
  - selectedWorkflowId（用户选择的或默认的）
        ↓
前端 SingleAnalysis.vue
  - submitAnalysis()
  - request.workflow_id = selectedWorkflowId
        ↓
后端 analysis.py 路由
  - submit_single_analysis()
  - 创建任务时携带 workflow_id
        ↓
后端 unified_analysis_engine.py
  - _resolve_workflow_id()
  - 优先级 1：用户显式指定的 workflow_id
  - 优先级 2：按 workflow_type 获取活动工作流
  - 优先级 3：注册表默认
  - 优先级 4：系统默认
        ↓
后端 workflow_engine.py
  - 加载并执行工作流
```

### 3.3 条件分支的数据流（AI 生成）

```
用户描述需求（含条件逻辑）
  "如果现金流有风险，走辩论路径，否则直接决策"
        ↓
AI 规划器（workflow_planner.py）
  - 生成蓝图（含条件边）
  - PlannedEdge.type = "conditional"
  - PlannedEdge.condition = "true" / "false"
        ↓
蓝图转工作流（_blueprint_to_workflow_dict）
  - 读取 e.type 和 e.condition
  - 写入 edges 数组
        ↓
工作流引擎（builder.py）
  - _create_condition_node()
  - _add_conditional_edge()
  - 按 condition 路由
```

## 四、影响范围

### 4.1 需要修改的文件

| 文件 | 改动类型 | 代码量 | 优先级 |
|------|---------|--------|--------|
| [SingleAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue) | Bug 修复 | ~5 行 | P0 |
| [core/workflow/models.py](file:///c:/TradingAgentsCN/core/workflow/models.py) | 字段新增 | ~2 行 | P0 |
| [v2_stock_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_stock_analysis_workflow.py) | 配置补全 | ~1 行 | P0 |
| [v2_etf_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_etf_analysis_workflow.py) | 配置补全 | ~1 行 | P0 |
| [workflow.ts](file:///c:/TradingAgentsCN/frontend/src/api/workflow.ts) | 接口补字段 | ~1 行 | P0 |
| [workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py) | 类型设置 + 条件分支 | ~30 行 | P0 |
| [workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) | 模型字段新增 | ~4 行 | P0 |
| [workflow_planner.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_planner.py) | Prompt 调整 | ~10 行 | P0 |
| [Workflow/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/index.vue) | 类型化改造 | ~80 行 | P1 |
| [WorkflowGeneration.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/WorkflowGeneration.vue) | 类型选择 UI | ~50 行 | P1 |
| [Editor.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Editor.vue) | 类型显示/编辑 | ~30 行 | P1 |

**总计：约 215 行代码**

### 4.2 不需要修改的文件

| 文件 | 原因 |
|------|------|
| [default_workflow_provider.py](file:///c:/TradingAgentsCN/core/workflow/default_workflow_provider.py) | 已完整实现类型化 |
| [unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py) | 已完整实现类型化解析 |
| [workflow_api.py](file:///c:/TradingAgentsCN/core/api/workflow_api.py) | 已支持 workflow_type |
| [workflows.py](file:///c:/TradingAgentsCN/app/routers/workflows.py) | 已支持 workflow_type |
| [engine.py](file:///c:/TradingAgentsCN/core/workflow/engine.py) | 类型无关 |
| [builder.py](file:///c:/TradingAgentsCN/core/workflow/builder.py) | 条件分支已实现（手动创建路径） |

### 4.3 数据迁移

**不需要数据迁移脚本**。

- 历史无 `workflow_type` 的工作流，通过 `infer_workflow_type()` 自动推断
- `infer_workflow_type()` 的回退逻辑：config -> ID 映射 -> 文本启发式
- 新创建的工作流显式设置 `workflow_type`

## 五、测试要点

### 5.1 P0 测试

1. **单股研究 workflow_id 传递**
   - 在单股研究页面选择一个自定义工作流
   - 提交分析
   - 验证后端使用的是用户选择的工作流（而非全局默认）

2. **AI 创建工作流设置类型**
   - 通过 AI 创建选择"单股研究流程"类型
   - 创建完成后检查数据库，`workflow_type` 为 `stock_analysis`

3. **AI 生成工作流条件分支**
   - 通过 AI 描述一个含条件分支的需求
   - 验证生成的 edges 中有 `type: "conditional"` 的边
   - 执行工作流，验证条件分支按预期二选一执行

4. **模板 workflow_type 补全**
   - 检查 `v2_stock_analysis_workflow` 的 config 包含 `workflow_type: "stock_analysis"`
   - 检查 `v2_etf_analysis_workflow` 的 config 包含 `workflow_type: "etf_analysis"`

### 5.2 P1 测试

1. **流程列表分组**
   - 创建不同类型的工作流
   - 验证流程管理页面按类型分组展示

2. **创建流程类型选择**
   - AI 创建路径：第一步选择类型
   - 手动创建路径：创建对话框选择类型

3. **编辑器类型显示**
   - 打开编辑器，验证显示当前工作流的类型
   - 修改类型，保存，验证数据库更新

## 六、实施顺序

```
步骤 1：P0 后端改动（约 50 行）
  - models.py 增加 workflow_type 字段
  - 模板补充 workflow_type
  - workflow_spec.py PlannedEdge 增加字段
  - workflow_generation_service.py 设置类型 + 条件分支
  - workflow_planner.py Prompt 调整
        ↓
步骤 2：P0 前端改动（约 10 行）
  - workflow.ts 接口补字段
  - SingleAnalysis.vue 修复 workflow_id 传递
        ↓
步骤 3：P0 测试验证
  - 单股研究 workflow_id 传递
  - AI 创建工作流类型设置
  - AI 条件分支生成
        ↓
步骤 4：P1 前端改动（约 160 行）
  - Workflow/index.vue 类型化改造
  - WorkflowGeneration.vue 类型选择
  - Editor.vue 类型显示
        ↓
步骤 5：P1 测试验证
  - 流程列表分组
  - 创建流程类型选择
  - 编辑器类型显示
```

## 七、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 历史工作流无 workflow_type | 类型分组时归类到"通用" | `infer_workflow_type()` 自动推断，文本启发式兜底 |
| AI 规划器不理解条件分支 | 生成的蓝图仍用普通边 | Prompt 中明确说明条件边的用法和示例 |
| 条件表达式安全风险 | `eval()` 执行用户表达式 | 已有设计：条件节点使用受限的 `eval()` 上下文（仅暴露 state） |
| 前端类型选择增加操作步骤 | 用户嫌麻烦 | 默认选择"单股研究流程"，用户不主动切换则无感 |

## 八、关联文档

- [工作流类型化改造需求文档](./workflow-typing-requirements.md)
- [v4.0 功能取舍](file:///c:/TradingAgentsCN/docs/05-design/v4.0/v3-to-v4-feature-triage.md)
- [AI 工作流生成设计](file:///c:/TradingAgentsCN/docs/05-design/v3.0/ai-workflow-generation.md)
