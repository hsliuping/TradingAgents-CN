# 定时任务管理前端实施文档

## 📋 概述

本文档记录了定时任务管理前端界面的实施过程，包括创建的文件、修改的文件以及使用说明。

## 🎯 实施目标

在前端系统配置中添加定时任务管理界面，支持以下功能：
- ✅ 查看所有定时任务列表
- ✅ 查看任务详情（触发器、参数、下次执行时间等）
- ✅ 暂停/恢复任务
- ✅ 手动触发任务
- ✅ 查看任务执行历史
- ✅ 查看调度器统计信息
- ✅ 实时显示任务状态

## 📁 创建的文件

### 1. API 接口层
**文件**: `frontend/src/api/scheduler.ts`

定义了与后端定时任务管理 API 交互的接口：

```typescript
// 主要接口
- getJobs(): 获取所有定时任务列表
- getJobDetail(jobId): 获取任务详情
- pauseJob(jobId): 暂停任务
- resumeJob(jobId): 恢复任务
- triggerJob(jobId): 手动触发任务
- getJobHistory(jobId, params): 获取任务执行历史
- getAllHistory(params): 获取所有任务执行历史
- getSchedulerStats(): 获取调度器统计信息
- getSchedulerHealth(): 调度器健康检查
```

**类型定义**:
```typescript
interface Job {
  id: string
  name: string
  next_run_time: string | null
  paused: boolean
  trigger: string
  func?: string
  args?: any[]
  kwargs?: Record<string, any>
}

interface JobHistory {
  job_id: string
  action: string
  status: string
  error_message?: string
  timestamp: string
}

interface SchedulerStats {
  total_jobs: number
  running_jobs: number
  paused_jobs: number
  scheduler_running: boolean
}
```

### 2. 页面组件
**文件**: `frontend/src/views/System/SchedulerManagement.vue`

定时任务管理主页面，包含以下功能模块：

#### 页面结构
```
┌─────────────────────────────────────────────────┐
│ 📊 统计信息卡片                                  │
│ - 总任务数 / 运行中 / 已暂停                     │
│ - 刷新按钮 / 执行历史按钮                        │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│ 📋 任务列表表格                                  │
│ - 任务名称 + 状态标签                            │
│ - 触发器类型                                     │
│ - 下次执行时间 + 相对时间                        │
│ - 操作按钮（暂停/恢复/立即执行/详情）            │
└─────────────────────────────────────────────────┘
```

#### 对话框
1. **任务详情对话框**
   - 显示任务的完整信息
   - 包括 ID、名称、状态、触发器、执行函数、参数等
   - 可以跳转到执行历史

2. **执行历史对话框**
   - 显示任务的执行历史记录
   - 支持分页查询
   - 显示操作类型、状态、时间、错误信息

#### 主要功能
```typescript
// 数据加载
- loadJobs(): 加载任务列表和统计信息
- showJobDetail(job): 显示任务详情
- loadHistory(): 加载执行历史

// 任务操作
- handlePause(job): 暂停任务（需要确认）
- handleResume(job): 恢复任务
- handleTrigger(job): 手动触发任务（需要确认）

// 历史查询
- showJobHistory(job): 显示单个任务的执行历史
- showHistoryDialog(): 显示所有任务的执行历史
- handleHistoryPageChange(page): 分页切换

// 格式化
- formatTrigger(trigger): 格式化触发器显示
- formatAction(action): 格式化操作类型
- formatDateTime(dateStr): 格式化日期时间
- formatRelativeTime(dateStr): 格式化相对时间
```

### 3. 测试脚本
**文件**: `scripts/test_scheduler_frontend.py`

用于测试后端 API 是否正常工作的 Python 脚本。

**测试内容**:
- ✅ 登录认证
- ✅ 健康检查
- ✅ 获取统计信息
- ✅ 获取任务列表
- ✅ 获取任务详情
- ✅ 暂停任务
- ✅ 恢复任务
- ✅ 获取执行历史

**使用方法**:
```bash
python scripts/test_scheduler_frontend.py
```

## 🔧 修改的文件

### 1. 路由配置
**文件**: `frontend/src/router/index.ts`

在 `/settings` 路由下添加了 `scheduler` 子路由：

```typescript
{
  path: 'scheduler',
  name: 'SchedulerManagement',
  component: () => import('@/views/System/SchedulerManagement.vue'),
  meta: {
    title: '定时任务',
    requiresAuth: true
  }
}
```

**位置**: 第 295-302 行

### 2. 侧边栏菜单
**文件**: `frontend/src/components/Layout/SidebarMenu.vue`

在"系统管理"子菜单中添加了"定时任务"菜单项：

```vue
<el-sub-menu index="/settings-admin">
  <template #title>系统管理</template>
  <el-menu-item index="/settings/database">数据库管理</el-menu-item>
  <el-menu-item index="/settings/logs">操作日志</el-menu-item>
  <el-menu-item index="/settings/sync">多数据源同步</el-menu-item>
  <el-menu-item index="/settings/scheduler">定时任务</el-menu-item>  <!-- 新增 -->
  <el-menu-item index="/settings/usage">使用统计</el-menu-item>
</el-sub-menu>
```

**位置**: 第 77-86 行

### 3. 日期时间工具
**文件**: `frontend/src/utils/datetime.ts`

添加了 `formatRelativeTime` 函数，用于格式化相对时间：

```typescript
/**
 * 格式化相对时间（距离现在多久）
 * @param dateStr - 时间字符串或时间戳
 * @returns 相对时间描述
 */
export function formatRelativeTime(dateStr: string | number | null | undefined): string
```

**功能**:
- 自动判断过去还是将来
- 支持多种时间单位（天、小时、分钟、秒）
- 返回友好的中文描述（例如："3小时后"、"5分钟前"）

**位置**: 第 167-230 行

## 🎨 UI 设计

### 颜色方案
- **运行中**: 绿色标签 (`type="success"`)
- **已暂停**: 橙色标签 (`type="warning"`)
- **成功**: 绿色图标
- **失败**: 红色文本

### 图标使用
- 📊 统计信息: `<Timer />`, `<List />`, `<VideoPlay />`, `<VideoPause />`
- 🔄 操作按钮: `<Refresh />`, `<Document />`, `<Promotion />`, `<View />`

### 响应式设计
- 表格自动适应屏幕宽度
- 操作按钮固定在右侧
- 对话框宽度适配内容

## 🔐 权限控制

### 查看权限
- 所有登录用户都可以查看任务列表和详情
- 所有登录用户都可以查看执行历史

### 操作权限
- **暂停任务**: 仅管理员（`is_admin=True`）
- **恢复任务**: 仅管理员
- **手动触发任务**: 仅管理员

### 权限检查
权限检查在后端 API 层面实现（`app/routers/scheduler.py`），前端不做额外限制。

## 📊 数据流

```
┌─────────────┐
│  Vue 组件   │
└──────┬──────┘
       │
       │ 调用 API
       ↓
┌─────────────┐
│ scheduler.ts│ (API 接口层)
└──────┬──────┘
       │
       │ HTTP 请求
       ↓
┌─────────────┐
│  request.ts │ (Axios 实例)
└──────┬──────┘
       │
       │ 添加认证头
       ↓
┌─────────────┐
│  后端 API   │ (/api/scheduler/*)
└──────┬──────┘
       │
       │ 调用服务
       ↓
┌─────────────┐
│SchedulerSvc │ (app/services/scheduler_service.py)
└──────┬──────┘
       │
       │ 操作调度器
       ↓
┌─────────────┐
│ APScheduler │
└─────────────┘
```

## 🧪 测试步骤

### 1. 启动后端服务
```bash
# 确保后端服务正在运行
python -m uvicorn app.main:app --reload
```

### 2. 启动前端服务
```bash
cd frontend
npm run dev
```

### 3. 访问页面
1. 打开浏览器访问 `http://localhost:5173`
2. 登录系统（用户名: `admin`, 密码: `admin123`）
3. 点击左侧菜单 "设置" → "系统管理" → "定时任务"

### 4. 测试功能
- ✅ 查看任务列表是否正常显示
- ✅ 统计信息是否正确
- ✅ 点击"详情"按钮查看任务详情
- ✅ 点击"暂停"按钮暂停任务
- ✅ 点击"恢复"按钮恢复任务
- ✅ 点击"立即执行"按钮触发任务
- ✅ 点击"执行历史"按钮查看历史记录
- ✅ 测试分页功能

### 5. 运行自动化测试
```bash
python scripts/test_scheduler_frontend.py
```

## 📝 使用说明

### 查看任务列表
1. 进入"定时任务"页面
2. 页面会自动加载所有任务
3. 可以看到每个任务的名称、触发器、下次执行时间和状态

### 暂停任务
1. 找到要暂停的任务
2. 点击"暂停"按钮
3. 确认操作
4. 任务状态会变为"已暂停"

### 恢复任务
1. 找到已暂停的任务
2. 点击"恢复"按钮
3. 任务状态会变为"运行中"

### 手动触发任务
1. 找到要执行的任务
2. 点击"立即执行"按钮
3. 确认操作
4. 任务会在后台立即执行

### 查看任务详情
1. 点击任务行的"详情"按钮
2. 查看任务的完整信息
3. 可以从详情对话框跳转到执行历史

### 查看执行历史
1. 点击页面顶部的"执行历史"按钮查看所有历史
2. 或者在任务详情对话框中点击"查看执行历史"查看单个任务的历史
3. 支持分页查询

## 🔍 故障排查

### 问题 1: 页面无法加载任务列表
**可能原因**:
- 后端服务未启动
- 认证 Token 过期
- 调度器未初始化

**解决方法**:
1. 检查后端服务是否正常运行
2. 重新登录获取新的 Token
3. 检查后端日志，确认调度器已启动

### 问题 2: 暂停/恢复操作失败
**可能原因**:
- 用户权限不足（非管理员）
- 任务 ID 不存在
- 调度器状态异常

**解决方法**:
1. 确认当前用户是管理员
2. 刷新任务列表，确认任务 ID 正确
3. 检查后端日志，查看错误信息

### 问题 3: 执行历史为空
**可能原因**:
- 任务从未执行过
- MongoDB 连接失败
- 历史记录未正确保存

**解决方法**:
1. 手动触发任务，生成历史记录
2. 检查 MongoDB 连接状态
3. 检查 `scheduler_history` 集合是否存在

## 📚 相关文档

- [定时任务管理后端实施文档](./scheduler_management.md)
- [定时任务管理实施总结](./scheduler_management_summary.md)
- [API 文档](../api/scheduler.md)

## 🎉 总结

定时任务管理前端界面已经完成，提供了完整的任务管理功能：
- ✅ 直观的任务列表展示
- ✅ 实时的状态更新
- ✅ 友好的操作交互
- ✅ 完整的历史记录
- ✅ 响应式的 UI 设计

用户可以通过这个界面方便地管理系统中的所有定时任务，无需手动操作数据库或编写脚本。

