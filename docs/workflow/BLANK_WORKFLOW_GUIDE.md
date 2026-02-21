# 📝 空白工作流模板使用指南

## 概述

空白工作流模板（`BLANK_WORKFLOW`）是 TradingAgents-CN v2.0 提供的最简单的工作流模板，只包含开始和结束节点。用户可以在此基础上自由添加自定义节点，构建个性化的分析流程。

---

## 🎯 适用场景

1. **自定义分析流程**
   - 根据个人投资风格定制分析流程
   - 组合不同的分析师创建独特的分析策略

2. **学习工作流构建**
   - 了解工作流的基本结构
   - 学习节点和边的连接方式

3. **快速原型开发**
   - 快速测试新的分析思路
   - 验证不同 Agent 组合的效果

4. **调试和测试** ✨ **新增**
   - 支持直接执行和调试
   - 可以添加任意 v2.0 Agent 进行测试
   - 实时查看工作流执行结果

---

## 📦 模板结构

### 默认节点

```python
nodes = [
    {
        "id": "start",
        "type": "start",
        "label": "开始",
        "position": {"x": 400, "y": 50}
    },
    {
        "id": "end",
        "type": "end",
        "label": "结束",
        "position": {"x": 400, "y": 500}
    }
]
```

### 默认边

```python
edges = [
    {
        "id": "e_start_end",
        "source": "start",
        "target": "end",
        "type": "normal",
        "style": "dashed"  # 虚线表示这是临时连接
    }
]
```

---

## 🚀 使用方法

### 方法 1: 通过前端界面（推荐）

1. **创建新工作流**
   ```
   工作流管理 → 创建工作流 → 选择"空白流程"模板
   ```

2. **添加节点**
   - 点击画布空白处
   - 选择节点类型（分析师、研究员、交易员等）
   - 配置节点参数

3. **连接节点**
   - 拖拽节点的输出端点到另一个节点的输入端点
   - 删除默认的 start → end 虚线连接

4. **保存工作流**
   - 点击"保存"按钮
   - 输入工作流名称和描述

5. **调试工作流** ✨ **新增**
   - 在模板卡片或工作流列表中点击"调试"按钮
   - 输入股票代码（如：600519）
   - 查看工作流执行结果
   - 根据结果调整节点配置

### 方法 2: 通过 Python 代码

```python
from core.workflow.templates import BLANK_WORKFLOW
from core.workflow.models import NodeDefinition, EdgeDefinition, NodeType, Position
from core.workflow.engine import WorkflowEngine

# 1. 复制空白模板
workflow = BLANK_WORKFLOW.model_copy(deep=True)
workflow.id = "my_custom_workflow"
workflow.name = "我的自定义流程"

# 2. 添加自定义节点
workflow.nodes.append(
    NodeDefinition(
        id="market_analyst",
        type=NodeType.ANALYST,
        agent_id="market_analyst_v2",
        label="市场分析师",
        position=Position(x=400, y=200),
    )
)

# 3. 修改边连接
# 删除默认的 start -> end 边
workflow.edges = [
    edge for edge in workflow.edges 
    if edge.id != "e_start_end"
]

# 添加新的边
workflow.edges.extend([
    EdgeDefinition(
        id="e1",
        source="start",
        target="market_analyst",
    ),
    EdgeDefinition(
        id="e2",
        source="market_analyst",
        target="end",
    ),
])

# 4. 执行工作流
engine = WorkflowEngine()
engine.load(workflow)
result = engine.execute({
    "ticker": "000001.SZ",
    "market_type": "A股",
})
```

---

## 📚 常见自定义示例

### 示例 1: 单分析师流程

```python
# 只使用一个分析师
workflow.nodes.append(
    NodeDefinition(
        id="fundamentals_analyst",
        type=NodeType.ANALYST,
        agent_id="fundamentals_analyst_v2",
        label="基本面分析师",
        position=Position(x=400, y=250),
    )
)
```

### 示例 2: 双分析师并行流程

```python
# 两个分析师并行分析
workflow.nodes.extend([
    NodeDefinition(
        id="market_analyst",
        type=NodeType.ANALYST,
        agent_id="market_analyst_v2",
        label="市场分析师",
        position=Position(x=200, y=200),
    ),
    NodeDefinition(
        id="news_analyst",
        type=NodeType.ANALYST,
        agent_id="news_analyst_v2",
        label="新闻分析师",
        position=Position(x=600, y=200),
    ),
    NodeDefinition(
        id="trader",
        type=NodeType.TRADER,
        agent_id="trader_v2",
        label="交易员",
        position=Position(x=400, y=350),
    ),
])

# 连接边
workflow.edges = [
    EdgeDefinition(id="e1", source="start", target="market_analyst"),
    EdgeDefinition(id="e2", source="start", target="news_analyst"),
    EdgeDefinition(id="e3", source="market_analyst", target="trader"),
    EdgeDefinition(id="e4", source="news_analyst", target="trader"),
    EdgeDefinition(id="e5", source="trader", target="end"),
]
```

---

## 💡 最佳实践

1. **合理布局节点**
   - 从上到下或从左到右排列
   - 保持节点间距一致（建议 150-200 像素）
   - 避免边交叉

2. **清晰的命名**
   - 使用描述性的节点 ID
   - 为节点添加有意义的 label
   - 在 config 中添加 description

3. **测试流程**
   - 先用简单数据测试
   - 逐步添加节点
   - 验证每个节点的输出

4. **保存版本**
   - 重大修改前保存副本
   - 使用版本号管理
   - 添加详细的描述

---

## ⚠️ 注意事项

1. **节点 ID 唯一性**
   - 每个节点的 ID 必须唯一
   - 建议使用有意义的命名（如 `market_analyst_1`）

2. **边的连接**
   - 确保每个节点都有输入和输出
   - 避免创建循环（除非使用 DEBATE 节点）
   - start 节点只能有输出，end 节点只能有输入

3. **Agent 可用性**
   - 确保引用的 agent_id 在系统中存在
   - 检查 Agent 的工具绑定是否正确

---

## 🐛 调试功能

### 功能说明

空白流程支持直接执行和调试，无需创建副本即可测试工作流。

### 使用步骤

1. **创建或打开工作流**
   ```
   方式1: 工作流管理 → 新建分析流程 → 选择"空白流程"模板 → 创建并进入编辑
   方式2: 工作流管理 → 我的分析流 → 选择基于空白流程创建的工作流 → 编辑
   ```

2. **添加节点并保存**
   - 从左侧节点面板拖拽节点到画布
   - 连接节点形成工作流
   - 点击"保存"按钮

3. **点击调试按钮**
   - 在编辑器顶部工具栏找到"执行"按钮（绿色按钮）
   - 点击进入执行页面

4. **输入参数**
   - 股票代码：如 `600519`（贵州茅台）
   - 分析日期：默认为当前日期
   - 其他参数：根据工作流节点配置

5. **查看结果**
   - 实时查看每个节点的执行状态
   - 查看 Agent 的分析输出
   - 检查工作流执行日志

### 调试技巧

1. **从简单开始**
   - 先添加 1-2 个节点测试
   - 确认基本流程正常后再添加更多节点

2. **使用单个 Agent 测试**
   - 添加一个分析师节点（如市场分析师 v2）
   - 连接 start → analyst → end
   - 点击编辑器顶部的"执行"按钮（绿色）
   - 输入股票代码并查看输出

3. **逐步增加复杂度**
   - 测试通过后添加更多分析师
   - 尝试并行分析（parallel → analysts → merge）
   - 添加辩论节点测试多轮对抗

4. **检查节点配置**
   - 确保每个节点的 agent_id 正确
   - 检查工具绑定是否完整
   - 验证提示词模板是否合适

5. **快速迭代**
   - 修改节点配置后保存
   - 立即点击"执行"按钮测试
   - 根据结果调整配置
   - 重复测试直到满意

---

## 📖 相关文档

- [工作流引擎文档](../design/v2.0/03-workflow-engine.md)
- [节点类型说明](../design/v2.0/agents/03-workflow-layer-design.md)
- [其他工作流模板](../../core/workflow/templates/)
- [工作流执行指南](./WORKFLOW_EXECUTION_GUIDE.md)

---

**最后更新**: 2026-02-19
**版本**: v3.0.0-alpha

