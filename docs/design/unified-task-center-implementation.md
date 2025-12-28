# 统一任务中心实施文档

## 📋 概述

本文档记录了统一任务中心的实施过程，包括后端 API、前端页面和路由配置。

## 🎯 实施目标

创建一个统一的任务中心，支持查看和管理所有类型的分析任务：
- ✅ 股票分析（stock_analysis）
- ✅ 持仓分析（position_analysis）
- ✅ 交易复盘（trade_review）
- ✅ 组合健康度（portfolio_health）
- ✅ 风险评估（risk_assessment）
- ✅ 市场概览（market_overview）
- ✅ 板块分析（sector_analysis）

## 🆚 与旧版任务中心的区别

### 旧版任务中心 (`/tasks`)

**文件**: `frontend/src/views/Tasks/TaskCenter.vue`

**特点**:
- ❌ 只显示股票分析任务
- ❌ 使用旧版 API (`/api/analysis/tasks`)
- ❌ 数据模型不统一
- ❌ 无法查看持仓分析、交易复盘等任务

**API**:
- `GET /api/analysis/tasks` - 获取任务列表
- `GET /api/analysis/tasks/{task_id}/status` - 获取任务状态
- `GET /api/analysis/tasks/{task_id}/result` - 获取任务结果

---

### 新版统一任务中心 (`/tasks/unified`)

**文件**: `frontend/src/views/Tasks/UnifiedTaskCenter.vue`

**特点**:
- ✅ 显示所有类型的分析任务
- ✅ 使用新版 API (`/api/v2/tasks`)
- ✅ 使用 `UnifiedAnalysisTask` 模型
- ✅ 支持按任务类型和状态筛选
- ✅ 实时统计信息
- ✅ 自动刷新（每 10 秒）

**API**:
- `GET /api/v2/tasks/list` - 获取任务列表
- `GET /api/v2/tasks/statistics` - 获取任务统计
- `GET /api/v2/tasks/{task_id}` - 获取任务详情
- `DELETE /api/v2/tasks/{task_id}` - 取消任务

---

## 📁 创建的文件

### 1. 后端 API

**文件**: `app/routers/unified_tasks.py`

**功能**:
- 提供统一的任务查询接口
- 支持按任务类型和状态筛选
- 支持分页查询
- 提供任务统计信息
- 支持取消任务

**端点**:
```python
GET  /api/v2/tasks/list          # 获取任务列表
GET  /api/v2/tasks/statistics    # 获取任务统计
GET  /api/v2/tasks/{task_id}     # 获取任务详情
DELETE /api/v2/tasks/{task_id}   # 取消任务
```

**响应模型**:
- `TaskListItem` - 任务列表项
- `TaskStatistics` - 任务统计

---

### 2. 前端 API 接口

**文件**: `frontend/src/api/unifiedTasks.ts`

**功能**:
- 定义任务类型枚举 `TaskType`
- 定义任务状态枚举 `TaskStatus`
- 定义数据模型（`TaskListItem`, `TaskDetail`, `TaskStatistics`）
- 提供 API 调用方法
- 提供中文名称映射和颜色映射

**导出**:
```typescript
// 枚举
export enum TaskType { ... }
export enum TaskStatus { ... }

// 类型
export interface TaskListItem { ... }
export interface TaskDetail { ... }
export interface TaskStatistics { ... }

// API 方法
export function getTaskList(params?: TaskListParams)
export function getTaskStatistics()
export function getTaskDetail(taskId: string)
export function cancelTask(taskId: string)

// 映射
export const TaskTypeNames: Record<TaskType, string>
export const TaskStatusNames: Record<TaskStatus, string>
export const TaskStatusColors: Record<TaskStatus, string>
```

---

### 3. 前端任务中心页面

**文件**: `frontend/src/views/Tasks/UnifiedTaskCenter.vue`

**功能**:
- 显示任务统计卡片（6 个维度）
- 支持按任务类型和状态筛选
- 显示任务列表（表格形式）
- 支持查看任务详情
- 支持取消任务
- 支持查看错误信息
- 自动刷新（每 10 秒）
- 分页支持

**UI 组件**:
- 统计卡片（总任务、等待中、进行中、已完成、失败、已取消）
- 筛选表单（任务类型、状态）
- 任务列表表格
- 分页组件

---

## 🔧 修改的文件

### 1. 后端主应用

**文件**: `app/main.py`

**修改**:
```python
# v2.0 统一任务中心路由
from app.routers import unified_tasks as unified_tasks_router
app.include_router(unified_tasks_router.router, tags=["unified-task-center"])
```

---

### 2. 前端路由配置

**文件**: `frontend/src/router/index.ts`

**修改**:
```typescript
{
  path: '/tasks',
  name: 'TaskCenter',
  component: () => import('@/layouts/BasicLayout.vue'),
  meta: {
    title: '任务中心',
    icon: 'List',
    requiresAuth: true,
    transition: 'slide-up'
  },
  children: [
    {
      path: '',
      name: 'TaskCenterHome',
      component: () => import('@/views/Tasks/TaskCenter.vue'),
      meta: { title: '任务中心（旧版）', requiresAuth: true }
    },
    {
      path: 'unified',
      name: 'UnifiedTaskCenter',
      component: () => import('@/views/Tasks/UnifiedTaskCenter.vue'),
      meta: { title: '统一任务中心', requiresAuth: true }
    }
  ]
}
```

---

### 3. 前端侧边栏菜单

**文件**: `frontend/src/components/Layout/SidebarMenu.vue`

**修改**:
```vue
<el-sub-menu index="/tasks">
  <template #title>
    <el-icon><List /></el-icon>
    <span>任务中心</span>
  </template>
  <el-menu-item index="/tasks">任务中心（旧版）</el-menu-item>
  <el-menu-item index="/tasks/unified">
    统一任务中心
    <el-tag type="primary" size="small" style="margin-left: 4px; transform: scale(0.85);">新版</el-tag>
  </el-menu-item>
</el-sub-menu>
```

**说明**: 将原来的单个菜单项改为子菜单，包含旧版和新版两个入口

---

## 🎨 页面截图说明

### 统计卡片
- 总任务数
- 等待中任务数
- 进行中任务数
- 已完成任务数
- 失败任务数
- 已取消任务数

### 筛选表单
- 任务类型下拉框（7 种类型）
- 状态下拉框（5 种状态）
- 查询按钮
- 重置按钮
- 刷新按钮

### 任务列表
- 任务 ID
- 任务类型（中文显示）
- 股票/代码
- 市场
- 状态（带颜色标签）
- 进度条
- 创建时间
- 执行时间
- 操作按钮（详情、取消、查看错误）

---

## 🚀 使用方法

### 访问统一任务中心

1. **通过菜单**: 点击左侧菜单 "任务中心" → "统一任务中心"
2. **通过 URL**: 直接访问 `/tasks/unified`

### 筛选任务

1. 选择任务类型（可选）
2. 选择状态（可选）
3. 点击"查询"按钮

### 查看任务详情

1. 点击任务行的"详情"按钮
2. 弹窗显示完整的任务信息（JSON 格式）

### 取消任务

1. 对于"等待中"或"进行中"的任务，点击"取消"按钮
2. 确认后任务状态变为"已取消"

### 查看错误信息

1. 对于"失败"的任务，点击"查看错误"按钮
2. 弹窗显示错误详情

---

## 📊 数据流

```
前端页面 (UnifiedTaskCenter.vue)
    ↓
前端 API (unifiedTasks.ts)
    ↓
后端 API (/api/v2/tasks/*)
    ↓
TaskAnalysisService
    ↓
MongoDB (unified_analysis_tasks 集合)
```

---

## 🔄 自动刷新机制

- 页面加载时立即获取数据
- 每 10 秒自动刷新任务列表和统计信息
- 页面卸载时清除定时器

---

## ✅ 测试建议

1. **创建不同类型的任务**:
   - 股票分析
   - 持仓分析
   - 交易复盘

2. **验证筛选功能**:
   - 按任务类型筛选
   - 按状态筛选
   - 组合筛选

3. **验证操作功能**:
   - 查看任务详情
   - 取消任务
   - 查看错误信息

4. **验证自动刷新**:
   - 创建新任务后，等待 10 秒查看是否自动刷新
   - 任务状态变化后，查看是否自动更新

---

## 🎉 总结

我们成功实现了统一任务中心，核心成果：

1. ✅ **后端 API** - 提供统一的任务查询接口
2. ✅ **前端 API** - 完整的类型定义和 API 调用
3. ✅ **前端页面** - 美观的任务中心界面
4. ✅ **路由配置** - 与旧版任务中心并存
5. ✅ **向后兼容** - 旧版任务中心继续工作

**访问地址**: `/tasks/unified`

**优势**:
- 支持所有类型的分析任务
- 实时统计信息
- 自动刷新
- 美观的 UI
- 完整的操作功能

