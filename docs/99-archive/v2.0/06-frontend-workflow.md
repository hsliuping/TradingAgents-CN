# 前端工作流编辑器设计

## 📋 概述

使用 Vue Flow 实现可视化工作流编辑器，用户可以通过拖拽方式定义分析流程。

---

## 🛠️ 技术选型

| 组件 | 选择 | 原因 |
|------|------|------|
| 流程图库 | Vue Flow | Vue3 生态最成熟，API 友好 |
| 状态管理 | Pinia | 已有基础设施 |
| UI 组件 | Element Plus | 已有基础设施 |

**安装依赖**:
```bash
npm install @vue-flow/core @vue-flow/background @vue-flow/controls @vue-flow/minimap
```

---

## 📁 目录结构

```
frontend/src/views/WorkflowDesigner/
├── index.vue                    # 主页面
├── components/
│   ├── FlowCanvas.vue           # 画布组件
│   ├── NodePalette.vue          # 节点面板 (左侧)
│   ├── PropertyPanel.vue        # 属性面板 (右侧)
│   ├── Toolbar.vue              # 工具栏
│   └── WorkflowList.vue         # 工作流列表
├── nodes/                       # 自定义节点
│   ├── AnalystNode.vue          # 分析师节点
│   ├── ResearcherNode.vue       # 研究员节点
│   ├── TraderNode.vue           # 交易员节点
│   ├── RiskNode.vue             # 风险评估节点
│   ├── ManagerNode.vue          # 管理者节点
│   ├── ConditionNode.vue        # 条件判断节点
│   ├── ParallelNode.vue         # 并行节点
│   └── MergeNode.vue            # 合并节点
├── edges/                       # 自定义边
│   └── ConditionalEdge.vue      # 条件边
├── composables/
│   ├── useWorkflow.ts           # 工作流逻辑
│   ├── useNodeDrag.ts           # 拖拽逻辑
│   └── useValidation.ts         # 验证逻辑
└── types/
    └── workflow.ts              # 类型定义
```

---

## 🎨 UI 布局设计

```
┌─────────────────────────────────────────────────────────────────────┐
│  Toolbar: [新建] [保存] [另存] [导入] [导出] [运行] [撤销] [重做]    │
├───────────┬─────────────────────────────────────────┬───────────────┤
│           │                                         │               │
│  节点面板  │              画布区域                   │   属性面板    │
│           │                                         │               │
│ ┌───────┐ │    ┌─────┐      ┌─────┐      ┌─────┐   │ 节点属性      │
│ │分析师 │ │    │市场 │─────▶│新闻 │─────▶│基本 │   │ ─────────    │
│ ├───────┤ │    │分析 │      │分析 │      │面   │   │ ID: xxx      │
│ │研究员 │ │    └─────┘      └─────┘      └─────┘   │ 名称: xxx    │
│ ├───────┤ │                      │                  │ 智能体: xxx  │
│ │交易员 │ │                      ▼                  │              │
│ ├───────┤ │               ┌─────────┐               │ 工具配置     │
│ │风险   │ │               │研究辩论 │               │ ─────────    │
│ ├───────┤ │               └─────────┘               │ [配置...]    │
│ │条件   │ │                      │                  │              │
│ ├───────┤ │                      ▼                  │ 提示词       │
│ │并行   │ │               ┌─────────┐               │ ─────────    │
│ └───────┘ │               │ 交易员  │               │ [编辑...]    │
│           │               └─────────┘               │              │
│           │                                         │              │
├───────────┴─────────────────────────────────────────┴───────────────┤
│  状态栏: 节点: 8 | 边: 10 | 已保存 | 上次修改: 2025-12-07 15:30     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📝 核心组件设计

### FlowCanvas.vue (画布组件)

```vue
<template>
  <div class="flow-canvas">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :default-viewport="{ zoom: 1 }"
      fit-view-on-init
      @node-drag-stop="onNodeDragStop"
      @connect="onConnect"
      @edge-update="onEdgeUpdate"
    >
      <Background />
      <Controls />
      <MiniMap />
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import AnalystNode from '../nodes/AnalystNode.vue'
import ResearcherNode from '../nodes/ResearcherNode.vue'
// ... 其他节点

const nodeTypes = {
  analyst: AnalystNode,
  researcher: ResearcherNode,
  trader: TraderNode,
  risk: RiskNode,
  manager: ManagerNode,
  condition: ConditionNode,
  parallel: ParallelNode,
  merge: MergeNode,
}
</script>
```

### AnalystNode.vue (分析师节点)

```vue
<template>
  <div 
    class="analyst-node"
    :class="{ selected: selected }"
    :style="{ borderColor: data.color }"
  >
    <div class="node-header" :style="{ backgroundColor: data.color }">
      <el-icon><DataAnalysis /></el-icon>
      <span>{{ data.label }}</span>
    </div>
    <div class="node-body">
      <div class="agent-info">
        <span class="agent-name">{{ data.agentName }}</span>
      </div>
      <div class="tool-badges" v-if="data.tools?.length">
        <el-tag size="small" v-for="tool in data.tools.slice(0, 2)" :key="tool">
          {{ tool }}
        </el-tag>
        <el-tag size="small" v-if="data.tools.length > 2">
          +{{ data.tools.length - 2 }}
        </el-tag>
      </div>
    </div>
    <!-- 连接点 -->
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
```

---

## 🔌 API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/workflows` | GET | 获取工作流列表 |
| `/api/workflows` | POST | 创建工作流 |
| `/api/workflows/{id}` | GET | 获取工作流详情 |
| `/api/workflows/{id}` | PUT | 更新工作流 |
| `/api/workflows/{id}` | DELETE | 删除工作流 |
| `/api/workflows/{id}/execute` | POST | 执行工作流 |
| `/api/workflows/{id}/validate` | POST | 验证工作流 |
| `/api/workflows/templates` | GET | 获取模板列表 |
| `/api/agents` | GET | 获取可用智能体列表 |

---

## 📊 路由配置

```typescript
// frontend/src/router/index.ts
{
  path: '/workflow',
  name: 'WorkflowDesigner',
  component: () => import('@/views/WorkflowDesigner/index.vue'),
  meta: {
    title: '工作流设计器',
    icon: 'Flow',
    requiresAuth: true,
    requiredLicense: 'basic'  // 需要基础版以上许可证
  }
}
```

