# TradingAgents v4.0 · Prototype v2

面向真实落地的高保真原型。技术栈与实际前端一致（Vue 3 + Element Plus），
通过 CDN 引入避免 npm/构建步骤；后续可零成本迁移为正式 Vue SFC 工程。

## 目录结构

```
prototype-v2/
├── index.html            原型导航首页
├── workspace.html        今日工作台（L0 入口聚合层）
├── discover.html         候选发现（L0.5 研究前漏斗，做候选分流）
├── object.html           研究对象列表页（L1 对象层入口，按类型分组）
├── object-detail.html    研究对象档案页（L1 对象层核心，单个对象 6 Tab）
├── task.html             任务详情页（L2 动作层核心）
├── library.html          研究库（L3 资产层核心，可复用沉淀）
├── learning.html         学习中心（方法论知识入口）
├── studio.html           方法工坊（模板化研究入口）
├── control.html          系统控制台（运行与告警操作面）
├── serve.ps1             启动本地预览服务
├── assets/
│   ├── theme.css         全局主题（品牌色 + 间距 + 组件微调）
│   └── shared.js         AppShell + AssistantDrawer 共享 Vue 组件
└── README.md             本文
```

## 启动预览

```powershell
cd docs/design/v4.0/prototype-v2
./serve.ps1
# 浏览器访问 http://127.0.0.1:8766/
```

或直接：

```powershell
python -m http.server 8766
```

## 设计基线

| 维度 | 取值 | 备注 |
|---|---|---|
| 主色 | `#4F73E8`（覆盖 Element Plus `--el-color-primary`） | 蓝紫品牌色 |
| 渐变 | `linear-gradient(135deg, #6B48E3 → #4F73E8 → #409EFF)` | 仅用于 Hero / Logo / FAB |
| 涨色 | `#F56C6C` | A 股语义：红 = 涨 |
| 跌色 | `#909399` | A 股语义：灰 = 跌（**严禁绿色**） |
| 基础字号 | 14px | 紧凑但不局促 |
| 区块间距 | 24px gutter / 32px section gap | 克制密度 |
| 圆角 | 8px (md) / 12px (lg) | 卡片用 lg，按钮用 md |

## 已落地的关键设计

1. **6 层架构落地**：`AppShell` 左侧导航把 8 模块按 L0-L5 分组（研究 / 执行与沉淀 / 方法与系统）
2. **智能助手为全局抽屉**：右下角 FAB → 抽屉随当前页面带上下文 → 任何 AI 输出都是「草稿」必须确认
3. **事实/观点/规则分层**：对象档案页的 Tab 体系（事实层 / 概念关系 / 系统观点 / 我的研究）严格隔离
4. **A 股语义色**：所有涨跌相关数字用红/灰，绝不使用绿色
5. **沉淀对话框**：任务详情页右栏明确"草稿默认不入库"的产品契约
6. **来源标记**：每个数据卡片都有 `<el-icon>Link</el-icon>` 来源行

## 与 Prototype-v1 的差异

| 项 | v1 (../static-prototype) | v2 (本目录) |
|---|---|---|
| 技术栈 | 纯 HTML/CSS/JS | Vue 3 + Element Plus（CDN） |
| 组件 | 自写 div | el-card / el-tabs / el-timeline / el-tag / el-table |
| 一致性 | 与实际前端不同 | 直接基于实际前端组件库 |
| 范围 | 11 页全覆盖（演示性） | 8 个核心页已落地（持续扩展） |
| 密度 | 内容拥挤 | 24px gutter + 32px section gap |

## 下一步建议

- 在候选发现与研究对象之间补“升格为正式对象”的明确动作与状态同步
- 强化研究库里动态资产的专题归档持久化
- 让系统控制台接入更真实的日志流、运行指标和历史告警
- 把 `shared.js` 的 `AppShell / AssistantDrawer` 提取为正式 Vue SFC，迁入 `frontend/src/components/`
