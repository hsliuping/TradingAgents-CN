# 工作流执行页面 v2.0 升级

## 📋 概述

将工作流执行页面从同步执行方式升级到 v2.0 异步执行方式，使用统一任务引擎。

**升级日期**: 2026-01-07  
**影响范围**: 工作流执行功能

---

## 🎯 升级目标

### 问题
- ❌ 使用同步执行方式，前端需要等待 5-30 分钟
- ❌ 执行过程中无法获取实时进度
- ❌ 用户体验差，界面长时间阻塞
- ❌ 没有使用现成的 v2.0 统一任务引擎

### 解决方案
- ✅ 改用 v2.0 统一任务引擎（异步执行）
- ✅ 返回 task_id，前端轮询进度
- ✅ 实时显示执行进度和步骤状态
- ✅ 统一的报告格式和任务管理
- ✅ 与单股分析保持一致的用户体验

---

## 🔧 技术实现

### 后端改造

#### 1. 修改工作流执行 API

**文件**: `app/routers/workflows.py`

**改动**:
```python
@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    data: WorkflowExecuteRequest,
    user: dict = Depends(get_current_user)  # 添加用户认证
):
    """执行工作流 - 使用 v2.0 统一任务引擎（异步执行）"""
    
    # 使用 TaskAnalysisService 创建任务
    task_service = get_task_analysis_service()
    
    task = await task_service.create_task(
        user_id=PyObjectId(user_id),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params=task_params,
        engine_type="workflow",  # 强制使用工作流引擎
        workflow_id=workflow_id  # 指定使用哪个工作流
    )
    
    # 异步执行任务（不等待完成）
    asyncio.create_task(task_service.execute_task(task))
    
    # 返回 task_id
    return ok({
        "task_id": task.task_id,
        "status": task.status,
        "message": "任务已提交，正在后台执行"
    })
```

**关键变化**:
- ❌ 旧版：同步执行，等待结果返回
- ✅ 新版：创建任务后立即返回 task_id
- ✅ 使用 `engine_type="workflow"` 强制使用工作流引擎
- ✅ 通过 `workflow_id` 参数指定使用哪个工作流

---

### 前端改造

#### 1. 修改执行逻辑

**文件**: `frontend/src/views/Workflow/Execute.vue`

**改动**:

1. **导入分析 API**:
```typescript
import { analysisApi } from '@/api/analysis'
```

2. **添加任务ID和轮询定时器**:
```typescript
const currentTaskId = ref<string | null>(null)
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
```

3. **修改执行函数**:
```typescript
const executeWorkflow = async () => {
  // ... 参数验证 ...
  
  // 调用 API（返回 task_id）
  const result = await workflowApi.execute(workflowId.value, inputs)
  
  // 获取任务ID
  currentTaskId.value = result.task_id || null
  
  // 开始轮询任务状态
  startPollingTaskStatus()
}
```

4. **添加轮询函数**:
```typescript
const startPollingTaskStatus = () => {
  pollingTimer.value = setInterval(async () => {
    // 获取任务状态
    const response = await analysisApi.getTaskStatus(currentTaskId.value)
    const status = response.data
    
    // 更新进度信息
    if (status.progress_info) {
      updateProgressInfo(status.progress_info)
    }
    
    // 任务完成
    if (status.status === 'completed') {
      clearInterval(pollingTimer.value)
      const resultResponse = await analysisApi.getTaskResult(currentTaskId.value)
      executionResult.value = resultResponse.data
      executing.value = false
      ElMessage.success('分析完成！')
    }
    
    // 任务失败
    if (status.status === 'failed') {
      clearInterval(pollingTimer.value)
      executionError.value = status.error
      executing.value = false
    }
  }, 2000) // 每2秒轮询一次
}
```

5. **添加进度更新函数**:
```typescript
const updateProgressInfo = (progressInfo: any) => {
  if (!progressInfo) return

  // 获取当前步骤名称
  const currentStepName = progressInfo.current_step_name || progressInfo.current_step
  if (!currentStepName) return

  // 重置所有步骤状态
  for (const step of executionSteps.value) {
    step.status = 'pending'
  }

  // 找到当前步骤并标记为 running
  let currentStepIndex = -1
  for (let i = 0; i < executionSteps.value.length; i++) {
    const step = executionSteps.value[i]

    // 尝试多种匹配方式
    if (step.name === currentStepName ||
        step.name.includes(currentStepName) ||
        currentStepName.includes(step.name)) {
      step.status = 'running'
      currentStepIndex = i
      break
    }
  }

  // 标记当前步骤之前的所有步骤为已完成
  for (let i = 0; i < currentStepIndex; i++) {
    executionSteps.value[i].status = 'completed'
  }
}
```

**关键逻辑**:
- ✅ 只需要 `current_step_name` 就能更新进度
- ✅ 当前步骤标记为 `running`
- ✅ 之前的步骤自动标记为 `completed`
- ✅ 之后的步骤保持 `pending`

6. **组件卸载时清理定时器**:
```typescript
onUnmounted(() => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }
})
```

---

#### 2. 修改 API 类型定义

**文件**: `frontend/src/api/workflow.ts`

**改动**:
```typescript
export interface ExecutionResult {
  success: boolean
  task_id?: string  // v2.0 异步执行返回的任务ID
  status?: string   // v2.0 任务状态
  message?: string  // v2.0 提示消息
  result?: Record<string, any>  // v1.x 同步执行的结果（兼容）
  execution?: {  // v1.x 执行信息（兼容）
    id: string
    workflow_id: string
    state: string
    started_at?: string
    completed_at?: string
    error?: string
  }
  error?: string
}
```

---

## 📊 对比

### 执行流程对比

**旧版 (v1.x)**:
```
用户点击执行
  ↓
前端调用 API
  ↓
后端同步执行工作流（5-30分钟）
  ↓
返回完整结果
  ↓
前端显示结果
```

**新版 (v2.0)**:
```
用户点击执行
  ↓
前端调用 API
  ↓
后端创建任务，返回 task_id（立即返回）
  ↓
前端开始轮询任务状态（每2秒）
  ├─ 更新进度信息
  ├─ 更新步骤状态
  └─ 任务完成后获取结果
```

---

## ✅ 优势

1. **用户体验提升**
   - ✅ 提交后立即返回，不阻塞界面
   - ✅ 实时显示执行进度
   - ✅ 可以看到当前执行到哪个步骤

2. **技术架构统一**
   - ✅ 使用 v2.0 统一任务引擎
   - ✅ 与单股分析保持一致
   - ✅ 统一的任务管理和进度跟踪

3. **可维护性提升**
   - ✅ 复用现有的成熟代码
   - ✅ 统一的错误处理
   - ✅ 统一的报告格式

---

## 🧪 测试步骤

1. **前往工作流执行页面**
   - 路径：分析流 → 流程管理 → 选择工作流 → 执行

2. **填写执行参数**
   - 股票代码：600519
   - 分析深度：标准
   - 选择模型

3. **点击"开始执行"**
   - ✅ 立即返回，显示"任务已提交"
   - ✅ 开始显示执行进度

4. **观察进度更新**
   - ✅ 步骤状态实时更新
   - ✅ 当前步骤高亮显示

5. **等待任务完成**
   - ✅ 显示"分析完成"
   - ✅ 显示完整的分析报告

---

## 📝 注意事项

1. **向后兼容**
   - ExecutionResult 类型保留了 v1.x 的字段
   - 支持新旧两种返回格式

2. **定时器清理**
   - 组件卸载时自动清理轮询定时器
   - 避免内存泄漏

3. **错误处理**
   - 任务失败时显示错误信息
   - 自动停止轮询

---

**最后更新**: 2026-01-07  
**相关文档**:
- `docs/features/scheduled_analysis_v2_engine_upgrade.md` - 定时分析 v2.0 升级
- `docs/design/v2.0/trade-review-task-center-integration.md` - 任务中心集成设计

