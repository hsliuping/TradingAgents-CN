# 工作流引擎与现有分析功能集成设计

## 一、现状分析

### 1.1 现有分析功能架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       前端页面                                   │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ SingleAnalysis  │ BatchAnalysis   │ AnalysisHistory             │
│ (单股分析)       │ (批量分析)       │ (历史记录)                   │
└────────┬────────┴────────┬────────┴─────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API 路由层                                    │
│              app/routers/analysis.py                            │
├─────────────────┬───────────────────────────────────────────────┤
│ POST /single    │ POST /batch                                   │
│ GET /tasks/{id} │ GET /batches/{id}                             │
└────────┬────────┴────────┬──────────────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    服务层                                        │
│         app/services/simple_analysis_service.py                 │
├─────────────────────────────────────────────────────────────────┤
│ - create_analysis_task()     创建任务                            │
│ - execute_analysis_background()  后台执行                        │
│ - _execute_analysis_sync()   同步执行核心逻辑                     │
│ - _run_analysis_sync()       调用 TradingAgentsGraph            │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 TradingAgentsGraph                              │
│          tradingagents/graph/trading_graph.py                   │
├─────────────────────────────────────────────────────────────────┤
│ - propagate(ticker, date)    执行完整分析流程                     │
│ - 固定的节点和边定义                                              │
│ - 固定的分析师组合                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 新工作流引擎架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       前端页面                                   │
├─────────────────┬───────────────────────────────────────────────┤
│ WorkflowEditor  │ WorkflowExecute                               │
│ (工作流编辑器)   │ (工作流执行)                                   │
└────────┬────────┴────────┬──────────────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API 路由层                                    │
│              app/routers/workflows.py                           │
├─────────────────────────────────────────────────────────────────┤
│ POST /{id}/execute   执行工作流                                  │
│ GET /templates       获取模板                                    │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  WorkflowAPI / WorkflowEngine                   │
│             core/api/workflow_api.py                            │
│             core/workflow/engine.py                             │
├─────────────────────────────────────────────────────────────────┤
│ - execute(workflow_id, inputs)  执行工作流                       │
│ - 动态构建 LangGraph                                            │
│ - 支持自定义节点和边                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 两套系统的差异

| 特性 | 旧系统 (simple_analysis_service) | 新系统 (WorkflowEngine) |
|------|----------------------------------|------------------------|
| 流程定义 | 硬编码在 TradingAgentsGraph | 可视化编辑，存储在 MongoDB |
| 执行方式 | 固定流程 | 动态构建 LangGraph |
| 任务管理 | 完善（进度、状态、历史） | 基础（仅同步执行） |
| 报告保存 | 完善（MongoDB + 文件） | 基础（仅 MongoDB） |
| 前端集成 | 完善（轮询状态、结果展示） | 基础（同步等待） |

## 二、集成目标

### 2.1 核心目标

1. **单股分析**：支持选择工作流模板或使用默认流程
2. **批量分析**：支持使用自定义工作流执行批量任务
3. **向后兼容**：保持现有 API 和前端不变
4. **统一报告**：两套系统产生的报告格式统一

### 2.2 用户场景

```
场景1: 用户使用默认分析流程
  用户 -> 单股分析页面 -> 选择"默认流程" -> 提交 -> 后台执行 -> 查看结果

场景2: 用户使用自定义工作流
  用户 -> 单股分析页面 -> 选择"我的自定义流程" -> 提交 -> 后台执行 -> 查看结果

场景3: 用户批量分析使用自定义工作流
  用户 -> 批量分析页面 -> 选择股票 + 选择工作流 -> 提交 -> 并发执行 -> 任务中心查看
```

## 三、集成方案设计

### 3.1 方案概述

采用**适配器模式**，在服务层增加工作流适配器，统一两套执行引擎的接口。

```
┌─────────────────────────────────────────────────────────────────┐
│                    API 路由层                                    │
│              app/routers/analysis.py                            │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│              分析执行适配器 (新增)                                 │
│         app/services/analysis_executor.py                       │
├─────────────────────────────────────────────────────────────────┤
│ + execute(task_id, request, workflow_id=None)                   │
│   - workflow_id=None -> 使用旧引擎                               │
│   - workflow_id="xxx" -> 使用新工作流引擎                         │
└────────┬────────────────┬───────────────────────────────────────┘
         │                │
         ▼                ▼
┌─────────────────┐ ┌─────────────────────────────────────────────┐
│ 旧引擎           │ │ 新工作流引擎                                 │
│ TradingAgents   │ │ WorkflowEngine                              │
│ Graph           │ │                                             │
└─────────────────┘ └─────────────────────────────────────────────┘

### 3.2 详细设计

#### 3.2.1 请求模型扩展

```python
# app/models/analysis.py - 扩展 SingleAnalysisRequest

class SingleAnalysisRequest(BaseModel):
    symbol: Optional[str] = None
    stock_code: Optional[str] = None  # 兼容字段
    parameters: Optional[AnalysisParameters] = None

    # 🆕 新增：工作流相关字段
    workflow_id: Optional[str] = None  # 指定工作流ID，None表示使用默认
    workflow_config: Optional[Dict[str, Any]] = None  # 工作流运行时配置覆盖
```

#### 3.2.2 分析执行适配器

```python
# app/services/analysis_executor.py (新文件)

class AnalysisExecutor:
    """
    分析执行适配器

    统一两套执行引擎的接口，根据请求参数选择合适的执行引擎
    """

    def __init__(self):
        self.simple_service = get_simple_analysis_service()
        self.workflow_api = WorkflowAPI()

    async def execute(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        progress_tracker: Optional[RedisProgressTracker] = None
    ) -> Dict[str, Any]:
        """
        执行分析任务

        Args:
            task_id: 任务ID
            user_id: 用户ID
            request: 分析请求
            progress_tracker: 进度跟踪器

        Returns:
            分析结果
        """
        workflow_id = request.workflow_id

        if workflow_id:
            # 使用新工作流引擎
            return await self._execute_with_workflow(
                task_id, user_id, request, workflow_id, progress_tracker
            )
        else:
            # 使用旧引擎（默认行为）
            return await self._execute_with_legacy(
                task_id, user_id, request, progress_tracker
            )

    async def _execute_with_workflow(self, ...):
        """使用新工作流引擎执行"""
        # 1. 构建工作流输入
        inputs = {
            "ticker": request.get_symbol(),
            "analysis_date": request.parameters.analysis_date if request.parameters else None,
            "research_depth": request.parameters.research_depth if request.parameters else "标准",
            # ... 其他参数
        }

        # 2. 构建 LLM 配置
        legacy_config = await self._build_llm_config(request)

        # 3. 执行工作流
        result = self.workflow_api.execute(workflow_id, inputs, legacy_config)

        # 4. 转换结果格式（与旧引擎输出格式一致）
        return self._convert_workflow_result(result)

    async def _execute_with_legacy(self, ...):
        """使用旧引擎执行（保持原有逻辑）"""
        return await self.simple_service._execute_analysis_sync(
            task_id, user_id, request, progress_tracker
        )
```

#### 3.2.3 前端扩展

```vue
<!-- SingleAnalysis.vue - 新增工作流选择 -->

<el-form-item label="分析流程">
  <el-select v-model="analysisForm.workflow_id" placeholder="选择分析流程">
    <el-option label="默认流程（推荐）" :value="null" />
    <el-option
      v-for="wf in availableWorkflows"
      :key="wf.id"
      :label="wf.name"
      :value="wf.id"
    />
  </el-select>
  <span class="form-tip">选择自定义工作流或使用默认分析流程</span>
</el-form-item>
```

### 3.3 数据流设计

#### 单股分析数据流

```
1. 用户提交分析请求（含 workflow_id）
   ↓
2. API 创建任务记录（analysis_tasks 集合）
   ↓
3. BackgroundTask 启动执行
   ↓
4. AnalysisExecutor.execute() 判断引擎
   ├─ workflow_id=None → 旧引擎 TradingAgentsGraph.propagate()
   └─ workflow_id="xxx" → 新引擎 WorkflowEngine.execute()
   ↓
5. 执行完成，保存结果（analysis_reports 集合）
   ↓
6. 更新任务状态为 completed
   ↓
7. 前端轮询获取结果并展示
```

#### 批量分析数据流

```
1. 用户提交批量分析请求（含 workflow_id）
   ↓
2. API 为每只股票创建独立任务
   ↓
3. 并发启动多个 BackgroundTask
   ↓
4. 每个任务独立执行（复用 AnalysisExecutor）
   ↓
5. 各任务独立完成并保存结果
   ↓
6. 任务中心展示批次进度
```

### 3.4 接口兼容性

#### 保持不变的接口

| 接口 | 说明 |
|-----|------|
| POST /api/analysis/single | 单股分析提交 |
| POST /api/analysis/batch | 批量分析提交 |
| GET /api/analysis/tasks/{id}/status | 任务状态查询 |
| GET /api/analysis/tasks/{id}/result | 任务结果获取 |
| GET /api/analysis/reports/{id} | 报告详情 |

#### 新增/扩展的字段

| 字段 | 位置 | 说明 |
|-----|------|------|
| workflow_id | 请求体 | 可选，指定工作流ID |
| workflow_config | 请求体 | 可选，运行时配置覆盖 |
| source | 报告记录 | "legacy" 或 "workflow" |

## 四、实施计划

### 阶段一：基础集成（2-3天）

1. 扩展 `SingleAnalysisRequest` 模型，添加 `workflow_id` 字段
2. 创建 `AnalysisExecutor` 适配器类
3. 修改 `simple_analysis_service` 调用适配器
4. 统一报告保存格式

### 阶段二：前端集成（2-3天）

1. 单股分析页面增加工作流选择下拉框
2. 批量分析页面增加工作流选择
3. 加载用户可用的工作流列表
4. 结果展示适配两种数据格式

### 阶段三：进度追踪增强（1-2天）

1. 工作流引擎增加进度回调机制
2. 与现有 RedisProgressTracker 集成
3. 前端进度条适配

### 阶段四：测试与优化（2-3天）

1. 单元测试覆盖
2. 集成测试
3. 性能测试（并发场景）
4. 文档更新

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 两套引擎结果格式不一致 | 前端展示异常 | 适配层统一转换格式 |
| 工作流执行超时 | 任务卡死 | 增加超时控制和重试机制 |
| 并发执行资源竞争 | 系统负载过高 | 复用现有并发限制机制 |
| 旧接口兼容性破坏 | 现有功能异常 | workflow_id 默认 None 保持原行为 |

## 六、后续扩展

1. **工作流版本管理**：支持工作流版本回滚
2. **工作流市场**：用户可分享和下载工作流模板
3. **A/B 测试**：对比不同工作流的分析效果
4. **智能推荐**：根据股票特性推荐合适的工作流

---

## 七、Agent 插件架构集成 ✅ 已实现

### 7.1 架构概述

为了支持动态扩展分析师，实现了 **Agent 插件架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                    core/ 扩展层                              │
├─────────────────────────────────────────────────────────────┤
│  AnalystRegistry          # 分析师注册表                     │
│  ReportAggregator         # 报告聚合器                       │
│  AnalystWorkflowExtension # 工作流扩展器                     │
├─────────────────────────────────────────────────────────────┤
│                 tradingagents/ 核心引擎                      │
│  setup.py                 # 动态加载扩展分析师               │
│  researchers/*.py         # 使用 ReportAggregator           │
│  managers/*.py            # 使用 ReportAggregator           │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 核心组件

#### AnalystRegistry (分析师注册表)

```python
# core/agents/analyst_registry.py
class AnalystRegistry:
    def register(self, analyst_id, agent_class=None, factory=None, metadata=None)
    def get_analyst_class(self, analyst_id) -> Optional[Type[BaseAgent]]
    def get_analysts_ordered(self, selected=None) -> List[AgentMetadata]
    def get_output_fields() -> Dict[str, str]
    def is_registered(self, analyst_id) -> bool
```

#### ReportAggregator (报告聚合器)

```python
# core/utils/report_aggregator.py
class ReportAggregator:
    def aggregate(self, state: Dict[str, Any]) -> AggregatedReports

def get_all_reports(state: Dict[str, Any]) -> AggregatedReports
```

### 7.3 工作流动态加载

`tradingagents/graph/setup.py` 中的关键方法：

```python
def _get_extension_registry(self):
    """获取扩展分析师注册表"""
    try:
        from core.agents.analyst_registry import get_analyst_registry
        return get_analyst_registry()
    except ImportError:
        return None

def _load_extension_analysts(self, analyst_nodes, selected_analysts):
    """从注册表动态加载扩展分析师"""
    registry = self._get_extension_registry()
    if not registry:
        return

    for analyst_id in selected_analysts:
        if registry.is_registered(analyst_id):
            agent_class = registry.get_analyst_class(analyst_id)
            metadata = registry.get_analyst_metadata(analyst_id)

            # 创建节点
            agent = agent_class(self.llm_client)
            analyst_nodes[analyst_id] = lambda state, a=agent: a.execute(state)

            # 标记无工具调用的分析师
            if not metadata.requires_tools:
                self._no_tool_analysts.add(analyst_id)
```

### 7.4 下游 Agent 报告获取

研究员和经理使用 `ReportAggregator` 动态获取所有报告：

```python
# tradingagents/agents/researchers/bull_researcher.py
def _get_extension_reports(state: dict) -> dict:
    try:
        from core.utils.report_aggregator import get_all_reports
        reports = get_all_reports(state)
        return reports.to_dict()
    except ImportError:
        # 降级：返回硬编码字段
        return {
            "sector_report": state.get("sector_report", ""),
            "index_report": state.get("index_report", ""),
        }
```

### 7.5 新增分析师的标准流程

1. **创建 Agent 类**：
```python
# core/agents/adapters/new_analyst.py
class NewAnalystAgent(BaseAgent):
    metadata = BUILTIN_AGENTS["new_analyst"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 实现分析逻辑
        return {**state, "new_report": report}
```

2. **注册到 AnalystRegistry**：
```python
# core/agents/adapters/__init__.py
registry.register("new_analyst", NewAnalystAgent, metadata)
```

3. **完成！** 无需修改：
   - `tradingagents/graph/setup.py`
   - `tradingagents/agents/researchers/*.py`
   - `tradingagents/agents/managers/*.py`

### 7.6 已实现的扩展分析师

| 分析师 | ID | requires_tools | output_field |
|--------|-----|---------------|--------------|
| 大盘分析师 | index_analyst | False | index_report |
| 板块分析师 | sector_analyst | False | sector_report |

