# 自定义工作流产出物配置设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 设计中 |
| 日期 | 2026-03-24 |
| 目标 | 解决自定义空白工作流无法正确收集和呈现 Agent 产出物的问题，实现产出物动态推导与可配置化 |
| 前置文档 | [v2.0 统一分析引擎](../v2.0/unified-analysis-engine-design.md)、[v2.0 Agent 迁移](../v2.0/agents/) |

---

## 1. 背景与问题

### 1.1 现状

当前系统中工作流的产出物处理逻辑**完全硬编码**，耦合在三个位置：

```
┌─────────────────────────────────────────────────────────────┐
│  WorkflowEngine.execute()                                    │
│  硬编码 fields = ["market_report", "sentiment_report", ...]  │
│  只认识 11 个预设字段名                                        │
├─────────────────────────────────────────────────────────────┤
│  report_formatter.extract_reports_from_state()               │
│  硬编码 STANDARD_REPORT_FIELDS = [10 个固定字段名]             │
│  对 final_trade_decision 等做特殊 JSON→Markdown 转换          │
├─────────────────────────────────────────────────────────────┤
│  _generate_final_trade_decision()                            │
│  只拼接 investment_plan + trader_investment_plan              │
│          + risk_assessment 三个字段                           │
├─────────────────────────────────────────────────────────────┤
│  前端 SingleAnalysis.vue / ReportDetail.vue                  │
│  硬编码 moduleOrder、moduleNames 映射                         │
│  只渲染预设字段的 Tab                                         │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 问题矩阵

| # | 问题 | 影响 |
|---|------|------|
| 1 | WorkflowEngine 硬编码 11 个 report field | 自定义工作流中的 Agent（如 `timing_analyst`, `emotion_analyst`）的 `output_field` 被丢弃 |
| 2 | `_generate_final_trade_decision` 只拼 3 个特定字段 | 自定义工作流没有 `investment_plan` 等字段时，不产生最终决策 |
| 3 | `report_formatter` 只认 `STANDARD_REPORT_FIELDS` | 自定义 Agent 的产出物无法被格式化和呈现 |
| 4 | 前端 `moduleOrder` 硬编码 | 自定义 Agent 的报告没有 Tab 显示，用户看不到结果 |
| 5 | `_get_node_progress_info` 硬编码节点名→进度映射 | 自定义 Agent 节点进度不友好（fallback 到默认 50%） |
| 6 | WorkflowDefinition 没有 output 相关声明 | 没有地方让用户/系统指定"这个工作流最终该产出什么" |

### 1.3 已有基础

Agent 层已经做好了声明式配置：

```python
# core/agents/config.py - AgentMetadata
class AgentMetadata(BaseModel):
    output_field: str = ""         # 输出到 state 的字段名
    report_label: str = ""         # 报告标签，如 "【市场分析】"
    node_name: str = ""            # 工作流节点名称
    execution_order: int = 100     # 执行顺序
    reads_from: List[str] = []     # 读取其他 Agent 的输出字段
```

问题在于 **WorkflowEngine 和下游消费方没有利用这些声明**。

---

## 2. 设计目标

### 2.1 核心目标

1. 自定义空白工作流的所有 Agent 产出物都能被正确收集、格式化和展示
2. 内置工作流模板保持完全兼容，零改动即可工作
3. 支持用户在可视化编辑器中配置"最终产出什么"

### 2.2 非目标（不在本期范围）

- 不改变 Agent 内部的执行逻辑
- 不改变 LangGraph 的 state 传递机制
- 不引入新的前端编辑器组件（复用现有属性面板）

---

## 3. 架构设计

### 3.1 四层联动架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: WorkflowDefinition (模型层)                        │
│  新增 output_config 字段，声明产出物策略                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: WorkflowEngine (执行引擎层)                        │
│  执行完后根据 output_config 动态收集 structured_reports       │
│  替代硬编码 fields 列表                                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: report_formatter (格式化层)                        │
│  接受动态字段列表，兼容旧逻辑                                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: 前端展示层                                         │
│  从结果中动态读取 report_manifest 渲染 Tab                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
WorkflowDefinition.output_config
        │
        ▼
WorkflowEngine.execute()
        │
        ├── 遍历 definition.nodes → 收集每个 Agent 的 output_field
        ├── 应用 output_config.strategy 决定哪些字段是最终产出
        ├── 动态构建 structured_reports
        ├── 动态构建 report_manifest（字段名→显示名→顺序→分类）
        │
        ▼
report_formatter.extract_reports_from_state(state, report_fields=动态列表)
        │
        ▼
API 返回结果 { reports: {...}, report_manifest: [...], ... }
        │
        ▼
前端读取 report_manifest 动态渲染 Tab
```

---

## 4. 详细设计

### 4.1 Layer 1: WorkflowDefinition 模型扩展

#### 4.1.1 新增 OutputConfig 模型

```python
# core/workflow/models.py

class OutputStrategy(str, Enum):
    """产出物组装策略"""
    AUTO = "auto"                  # 自动推导：从拓扑末端 Agent 收集
    COLLECT_ALL = "collect_all"    # 收集所有 Agent 的 output_field
    SPECIFIED = "specified"        # 用户手动指定字段列表
    LAST_NODE = "last_node"        # 只取 END 节点的直接前驱的输出
    LLM_SUMMARIZE = "llm_summarize"  # 收集后用 LLM 综合（P2）

class OutputFieldConfig(BaseModel):
    """单个输出字段的配置"""
    field_name: str                    # state 中的字段名
    display_name: str = ""             # 显示名称（空=从 AgentMetadata 推导）
    category: str = ""                 # 分类（如 "分析师团队", "决策层"）
    order: int = 0                     # 显示排序（越小越前）
    is_primary: bool = False           # 是否为主要输出（用于摘要提取）
    format_hint: str = "markdown"      # 格式提示：markdown | json_to_markdown | plain

class WorkflowOutputConfig(BaseModel):
    """工作流产出物配置"""
    strategy: OutputStrategy = OutputStrategy.AUTO
    fields: List[OutputFieldConfig] = Field(default_factory=list)
    primary_field: str = ""            # 主要输出字段名（用于 recommendation 等提取）
    summary_prompt: str = ""           # strategy=llm_summarize 时的 prompt（P2）
```

#### 4.1.2 WorkflowDefinition 扩展

```python
class WorkflowDefinition(BaseModel):
    # ... 现有字段 ...

    # 🆕 产出物配置
    output_config: WorkflowOutputConfig = Field(
        default_factory=WorkflowOutputConfig
    )
```

#### 4.1.3 向后兼容

`output_config` 有默认值 `WorkflowOutputConfig(strategy="auto")`，现有工作流定义不含此字段时自动使用 `auto` 策略。

---

### 4.2 Layer 2: WorkflowEngine 动态产出物收集

#### 4.2.1 核心方法：`_collect_output_manifest`

在 `execute` / `execute_async` 执行完成后、返回结果前调用：

```python
def _collect_output_manifest(
    self,
    state: Dict[str, Any],
    definition: WorkflowDefinition,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    根据 output_config 从 state 中收集产出物。

    Returns:
        (structured_reports, report_manifest)
        - structured_reports: {field_name: {"content": str, "success": bool, ...}}
        - report_manifest: [{"field": str, "display_name": str, "category": str, "order": int}, ...]
    """
```

#### 4.2.2 策略实现

**AUTO 策略（默认）：**

```
1. 如果 definition 中有内置工作流标识（id 在 BUILTIN_WORKFLOW_IDS 中），
   回退到现有硬编码逻辑（完全兼容）
2. 否则：
   a. 遍历 definition.nodes，收集每个 Agent 节点的 agent_id
   b. 查询 AgentMetadata（优先从 DB，其次从 registry），获取 output_field、report_label、execution_order
   c. 按 execution_order 排序
   d. 从 state 中提取对应字段值
   e. 自动识别"主要输出"：拓扑上最后执行的 Agent 的 output_field
```

**COLLECT_ALL 策略：**

```
1. 遍历 definition.nodes 中所有 agent 类型节点
2. 收集全部 output_field
3. 从 state 中提取
4. 按 execution_order 排序
```

**SPECIFIED 策略：**

```
1. 直接使用 output_config.fields 列表
2. 从 state 中提取对应字段
3. 按 OutputFieldConfig.order 排序
```

**LAST_NODE 策略：**

```
1. 找到 END 节点
2. 反向遍历边，找到 END 的直接前驱 Agent 节点
3. 只收集这些 Agent 的 output_field
```

#### 4.2.3 report_manifest 结构

每个产出物字段生成一条 manifest 记录：

```json
{
  "field": "timing_analysis",
  "display_name": "时机分析",
  "category": "分析师团队",
  "order": 10,
  "is_primary": false,
  "format_hint": "markdown",
  "agent_id": "timing_analyst",
  "has_content": true
}
```

#### 4.2.4 替换现有硬编码逻辑

当前 `execute` 方法中的 302-346 行（硬编码 fields 列表 + structured_reports 构建）和 348-366 行（`_generate_final_trade_decision` 逻辑）将被重构：

```python
# 执行完成后
result = final_state

# 🆕 动态收集产出物
structured_reports, report_manifest = self._collect_output_manifest(
    result, self._definition
)
result["structured_reports"] = structured_reports
result["report_manifest"] = report_manifest

# 🆕 动态生成 final summary（替代硬编码的 _generate_final_trade_decision）
primary_field = self._resolve_primary_field(result, self._definition)
if primary_field and primary_field in result:
    existing_ftd = result.get("final_trade_decision")
    if not existing_ftd or (isinstance(existing_ftd, dict) and not existing_ftd.get("action")):
        result["final_trade_decision"] = self._generate_dynamic_summary(
            result, report_manifest
        )
```

#### 4.2.5 动态进度推导

`_get_node_progress_info` 在硬编码映射未命中时，利用 AgentMetadata 动态生成：

```python
if node_name in node_mapping:
    return node_mapping[node_name]

# 🆕 动态推导：从 definition 的节点列表中查找
if self._definition:
    for i, node in enumerate(self._definition.nodes):
        agent_id = node.agent_id or ""
        if agent_id == node_name or node.label == node_name:
            total = len([n for n in self._definition.nodes
                        if n.type not in (NodeType.START, NodeType.END)])
            progress = int(10 + (80 * (i / max(total, 1))))
            label = node.label or agent_id.replace("_", " ").title()
            return (progress, f"正在执行: {label}", label)
```

---

### 4.3 Layer 3: report_formatter 适配

#### 4.3.1 `extract_reports_from_state` 接受动态字段

```python
def extract_reports_from_state(
    state: Any,
    report_fields: Optional[List[str]] = None,  # 🆕 动态字段列表
    report_manifest: Optional[List[Dict]] = None,  # 🆕 manifest 提供格式提示
) -> Dict[str, str]:
    """
    从 state 中提取报告内容。

    当 report_fields 不为空时，使用它替代 STANDARD_REPORT_FIELDS。
    当 report_manifest 提供 format_hint 时，据此决定是否做 JSON→Markdown 转换。
    """
    fields = report_fields or STANDARD_REPORT_FIELDS
    # ... 现有逻辑改为遍历 fields ...
```

#### 4.3.2 格式化策略

| format_hint | 处理方式 |
|---|---|
| `markdown` | 直接使用，清理署名 |
| `json_to_markdown` | 调用 `_convert_json_to_markdown` |
| `plain` | 原样返回，不做处理 |

通过 `report_manifest` 中的 `format_hint` 决定，不再对 `final_trade_decision` 等字段做 if-else 硬编码判断。

---

### 4.4 Layer 4: 前端动态渲染

#### 4.4.1 API 响应结构

在现有结果基础上新增 `report_manifest` 字段：

```json
{
  "success": true,
  "reports": {
    "timing_analysis": "...(markdown)...",
    "emotion_analysis": "...(markdown)...",
    "review_summary": "...(markdown)..."
  },
  "report_manifest": [
    {"field": "timing_analysis", "display_name": "时机分析", "category": "分析师团队", "order": 10},
    {"field": "emotion_analysis", "display_name": "情绪分析", "category": "分析师团队", "order": 30},
    {"field": "review_summary", "display_name": "复盘总结", "category": "决策层", "order": 100, "is_primary": true}
  ],
  "recommendation": "...",
  "confidence_score": 0.75,
  ...
}
```

#### 4.4.2 前端渲染逻辑变更

**SingleAnalysis.vue / ReportDetail.vue：**

```
1. 如果响应包含 report_manifest（新格式）：
   - 按 manifest 的 order 排序生成 Tab
   - display_name 作为 Tab 标题
   - category 用于 Tab 分组（可选）
   - is_primary=true 的字段自动激活

2. 如果响应不包含 report_manifest（旧格式）：
   - 回退到现有的 moduleOrder + moduleNames 硬编码逻辑
   - 完全兼容旧结果
```

```typescript
// 前端伪代码
const tabs = computed(() => {
  if (result.report_manifest?.length) {
    return result.report_manifest
      .filter(m => result.reports[m.field])
      .sort((a, b) => a.order - b.order)
      .map(m => ({
        key: m.field,
        title: m.display_name,
        category: m.category,
      }))
  }
  // fallback: 旧逻辑
  return moduleOrder.filter(...)
})
```

---

## 5. 兼容性策略

### 5.1 内置工作流完全兼容

```
判断条件：definition.id 存在于 BUILTIN_WORKFLOW_IDS 集合中
          或 output_config.strategy == "auto" 且 definition 不含自定义节点

行为：
  - WorkflowEngine 走现有硬编码 fields 列表 + _generate_final_trade_decision
  - report_formatter 走 STANDARD_REPORT_FIELDS
  - 前端走 moduleOrder fallback
  - 零变更，零风险
```

### 5.2 已保存的旧工作流定义

旧定义不含 `output_config` 字段：

```python
class WorkflowOutputConfig(BaseModel):
    strategy: OutputStrategy = OutputStrategy.AUTO  # 默认 auto
    fields: List[OutputFieldConfig] = Field(default_factory=list)
    # ...
```

`output_config` 缺失时 Pydantic 使用默认值，`strategy=auto` 触发自动推导。

### 5.3 旧 API 响应兼容

旧格式不含 `report_manifest` 字段，前端 fallback 到 `moduleOrder` 硬编码逻辑。

---

## 6. AUTO 策略详细算法

AUTO 是默认策略，也是最关键的策略。核心思想是**从工作流拓扑和 Agent 声明中自动推导产出物**。

### 6.1 算法流程

```
输入: workflow_definition, final_state
输出: structured_reports, report_manifest

Step 1: 判断是否为内置工作流
  if definition.id in BUILTIN_WORKFLOW_IDS:
      return 现有硬编码逻辑的结果

Step 2: 收集所有 Agent 节点的元数据
  agent_nodes = [n for n in definition.nodes if n.agent_id]
  for node in agent_nodes:
      metadata = lookup_agent_metadata(node.agent_id)
      # 优先从 DB agent_configs 读取，其次从代码 AGENT_METADATA_REGISTRY

Step 3: 推导 output_field 列表
  output_fields = []
  for node, metadata in agent_nodes_with_metadata:
      field = metadata.output_field or f"{node.agent_id}_report"
      output_fields.append({
          "field": field,
          "display_name": metadata.report_label or metadata.node_name or node.label,
          "order": metadata.execution_order,
          "agent_id": node.agent_id,
          "category": _infer_category(metadata),  # 从 agent 类型推导
      })

Step 4: 推导主要输出
  # 找到拓扑上最后执行（execution_order 最大）的 Agent
  # 或者有 is_primary 标记的 Agent
  primary = max(output_fields, key=lambda f: f["order"])
  primary["is_primary"] = True

Step 5: 从 state 中提取内容
  for field_info in output_fields:
      content = extract_text(final_state.get(field_info["field"]))
      structured_reports[field_info["field"]] = {
          "content": content,
          "success": bool(content.strip()),
      }

Step 6: 生成 report_manifest
  report_manifest = sorted(output_fields, key=lambda f: f["order"])

return structured_reports, report_manifest
```

### 6.2 分类推导规则

```python
def _infer_category(metadata: AgentMetadata) -> str:
    """从 Agent 元数据推导产出物分类"""
    category_map = {
        "analyst": "分析师团队",
        "researcher": "研究团队",
        "trader": "交易团队",
        "risk": "风险管理团队",
        "manager": "决策层",
        "post_processor": "后处理",
    }
    return category_map.get(metadata.category, "其他")
```

---

## 7. 数据库存储

### 7.1 workflow_definitions 集合扩展

`output_config` 作为 `WorkflowDefinition` 的子文档存储：

```json
{
  "_id": "wf_custom_review_001",
  "name": "自定义复盘工作流",
  "nodes": [...],
  "edges": [...],
  "output_config": {
    "strategy": "collect_all",
    "fields": [
      {
        "field_name": "timing_analysis",
        "display_name": "时机分析报告",
        "category": "分析师团队",
        "order": 10
      },
      {
        "field_name": "review_summary",
        "display_name": "复盘总结",
        "category": "决策层",
        "order": 100,
        "is_primary": true
      }
    ],
    "primary_field": "review_summary"
  }
}
```

### 7.2 现有文档无 output_config

读取时 Pydantic 默认值生效，`strategy=auto`，不影响现有数据。

---

## 8. 实施计划

### Phase 1: 模型与引擎层（P0）

| 任务 | 文件 | 预估 |
|------|------|------|
| 新增 `OutputStrategy`, `OutputFieldConfig`, `WorkflowOutputConfig` 模型 | `core/workflow/models.py` | 0.5h |
| `WorkflowDefinition` 添加 `output_config` 字段 | `core/workflow/models.py` | 0.5h |
| 实现 `_collect_output_manifest` 方法 | `core/workflow/engine.py` | 2h |
| 实现 AUTO 策略的 Agent 元数据查询 | `core/workflow/engine.py` | 1h |
| 重构 `execute` / `execute_async` 结果构建部分 | `core/workflow/engine.py` | 1.5h |
| 动态进度推导 fallback | `core/workflow/engine.py` | 0.5h |
| 内置工作流兼容逻辑 | `core/workflow/engine.py` | 0.5h |

### Phase 2: 格式化层（P1）

| 任务 | 文件 | 预估 |
|------|------|------|
| `extract_reports_from_state` 支持 `report_fields` 参数 | `app/utils/report_formatter.py` | 1h |
| `format_analysis_result` 传递动态字段 | `app/utils/report_formatter.py` | 0.5h |
| `unified_analysis_service._format_result` 适配 | `app/services/unified_analysis_service.py` | 0.5h |

### Phase 3: 前端适配（P1）

| 任务 | 文件 | 预估 |
|------|------|------|
| `SingleAnalysis.vue` 动态 Tab 渲染 | `frontend/src/views/Analysis/SingleAnalysis.vue` | 1.5h |
| `ReportDetail.vue` 动态 Tab 渲染 | `frontend/src/views/Reports/ReportDetail.vue` | 1h |
| 工作流执行结果页动态渲染 | `frontend/src/views/Workflow/Execute.vue` | 1h |

### Phase 4: LLM 综合策略（P2，可选）

| 任务 | 文件 | 预估 |
|------|------|------|
| 实现 `llm_summarize` 策略 | `core/workflow/engine.py` | 2h |
| `_generate_dynamic_summary` 方法 | `core/workflow/engine.py` | 1.5h |

### Phase 5: 可视化编辑器集成（P2，可选）

| 任务 | 文件 | 预估 |
|------|------|------|
| 工作流属性面板增加 output_config 配置 UI | `frontend/src/views/Workflow/` | 2h |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 内置工作流结果格式变化导致前端渲染异常 | 高 | AUTO 策略对内置工作流 ID 走硬编码 fallback；前端对缺少 `report_manifest` 的响应走旧逻辑 |
| Agent 元数据在 DB 中缺失 | 中 | fallback 到代码中的 `AGENT_METADATA_REGISTRY`，再 fallback 到 `f"{agent_id}_report"` |
| `output_field` 命名冲突（两个 Agent 写同名字段） | 低 | 编译期 `validate()` 检测冲突并警告；运行时后执行的 Agent 覆盖前者 |
| 旧版本工作流定义导入后无 `output_config` | 低 | Pydantic 默认值 `strategy=auto` 确保自动推导 |

---

## 10. 验证标准

### 10.1 Phase 1 完成标准

- [ ] 使用内置股票分析工作流，结果与改动前完全一致
- [ ] 创建含 `timing_analyst` + `emotion_analyst` + `review_manager` 的自定义工作流，执行后能看到 3 个报告 Tab
- [ ] 创建只含 `market_analyst_v2` 的单 Agent 工作流，能正常展示 1 个报告
- [ ] 旧格式 `workflow_definitions` 文档能正常加载和执行

### 10.2 Phase 3 完成标准

- [ ] 前端 `report_manifest` 有值时，按 manifest 动态渲染 Tab
- [ ] 前端 `report_manifest` 缺失时，走旧 `moduleOrder` 逻辑
- [ ] Tab 标题显示 `display_name`，按 `order` 排序

---

## 附录

### A. 涉及文件清单

```
核心模型:
  core/workflow/models.py           # OutputConfig 模型定义

执行引擎:
  core/workflow/engine.py           # 动态产出物收集、进度推导

格式化:
  app/utils/report_formatter.py     # 动态字段支持

服务层:
  app/services/unified_analysis_service.py  # 传递动态字段

前端:
  frontend/src/views/Analysis/SingleAnalysis.vue
  frontend/src/views/Reports/ReportDetail.vue
  frontend/src/views/Workflow/Execute.vue
```

### B. 与现有机制的关系

```
AgentMetadata.output_field ──┐
AgentMetadata.report_label   ├── WorkflowEngine._collect_output_manifest() 读取
AgentMetadata.execution_order┘
                                         │
                                         ▼
                               report_manifest[]
                                         │
                              ┌──────────┼──────────┐
                              ▼          ▼          ▼
                        report_formatter  API    Frontend
                        (动态字段)     (透传)   (动态Tab)
```

---

**最后更新**: 2026-03-24
**版本**: v1.0
