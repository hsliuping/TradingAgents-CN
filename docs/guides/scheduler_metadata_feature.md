# 定时任务元数据功能实现文档

## 📋 功能概述

为定时任务管理系统添加了"触发器名称"和"备注"字段，方便用户为每个定时任务添加自定义说明。

## ✨ 新增功能

### 1. 触发器名称 (display_name)
- 用户可以为每个定时任务设置一个友好的显示名称
- 最大长度：50 字符
- 可选字段

### 2. 备注 (description)
- 用户可以为每个定时任务添加详细的备注说明
- 最大长度：200 字符
- 支持多行文本
- 可选字段

### 3. 编辑功能
- 在任务列表中添加"编辑"按钮
- 弹出对话框编辑触发器名称和备注
- 实时保存到数据库

## 🔧 技术实现

### 后端实现

#### 1. 数据存储

使用 MongoDB 单独存储任务元数据：

**集合名称**: `scheduler_metadata`

**数据结构**:
```json
{
  "job_id": "tushare_basic_info_sync",
  "display_name": "Tushare基础信息同步",
  "description": "每天凌晨2点同步股票基础信息",
  "updated_at": "2025-10-08T10:00:00"
}
```

#### 2. 服务层修改

**文件**: `app/services/scheduler_service.py`

**新增方法**:

1. `_get_job_metadata(job_id)` - 获取任务元数据
   ```python
   async def _get_job_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
       """获取任务元数据（触发器名称和备注）"""
       db = self._get_db()
       metadata = await db.scheduler_metadata.find_one({"job_id": job_id})
       if metadata:
           metadata.pop("_id", None)
           return metadata
       return None
   ```

2. `update_job_metadata(job_id, display_name, description)` - 更新任务元数据
   ```python
   async def update_job_metadata(
       self,
       job_id: str,
       display_name: Optional[str] = None,
       description: Optional[str] = None
   ) -> bool:
       """更新任务元数据"""
       # 检查任务是否存在
       job = self.scheduler.get_job(job_id)
       if not job:
           return False
       
       # 使用 upsert 更新或插入
       db = self._get_db()
       await db.scheduler_metadata.update_one(
           {"job_id": job_id},
           {"$set": update_data},
           upsert=True
       )
       return True
   ```

**修改方法**:

1. `list_jobs()` - 在返回任务列表时附加元数据
2. `get_job()` - 在返回任务详情时附加元数据

#### 3. API 路由

**文件**: `app/routers/scheduler.py`

**新增接口**:

```python
@router.put("/jobs/{job_id}/metadata")
async def update_job_metadata(
    job_id: str,
    request: JobMetadataUpdateRequest,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """更新任务元数据（触发器名称和备注）"""
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以更新任务元数据")
    
    success = await service.update_job_metadata(
        job_id,
        display_name=request.display_name,
        description=request.description
    )
    if success:
        return ok(message=f"任务 {job_id} 元数据已更新")
    else:
        raise HTTPException(status_code=400, detail=f"更新任务 {job_id} 元数据失败")
```

**请求模型**:

```python
class JobMetadataUpdateRequest(BaseModel):
    """更新任务元数据请求"""
    display_name: Optional[str] = None
    description: Optional[str] = None
```

### 前端实现

#### 1. API 接口

**文件**: `frontend/src/api/scheduler.ts`

**接口定义更新**:

```typescript
export interface Job {
  id: string
  name: string
  next_run_time: string | null
  paused: boolean
  trigger: string
  display_name?: string  // 新增
  description?: string   // 新增
  func?: string
  args?: any[]
  kwargs?: Record<string, any>
}
```

**新增 API 函数**:

```typescript
/**
 * 更新任务元数据（触发器名称和备注）
 */
export function updateJobMetadata(
  jobId: string,
  data: { display_name?: string; description?: string }
) {
  return ApiClient.put<void>(`/api/scheduler/jobs/${jobId}/metadata`, data)
}
```

#### 2. Vue 组件

**文件**: `frontend/src/views/System/SchedulerManagement.vue`

**新增表格列**:

1. **触发器名称列**:
   ```vue
   <el-table-column prop="display_name" label="触发器名称" min-width="150">
     <template #default="{ row }">
       <el-text v-if="row.display_name" size="small">{{ row.display_name }}</el-text>
       <el-text v-else type="info" size="small">-</el-text>
     </template>
   </el-table-column>
   ```

2. **备注列**:
   ```vue
   <el-table-column prop="description" label="备注" min-width="200" show-overflow-tooltip>
     <template #default="{ row }">
       <el-text v-if="row.description" size="small">{{ row.description }}</el-text>
       <el-text v-else type="info" size="small">-</el-text>
     </template>
   </el-table-column>
   ```

**新增编辑按钮**:

```vue
<el-button
  size="small"
  :icon="Edit"
  @click="showEditDialog(row)"
>
  编辑
</el-button>
```

**新增编辑对话框**:

```vue
<el-dialog
  v-model="editDialogVisible"
  title="编辑任务信息"
  width="600px"
>
  <el-form :model="editForm" label-width="120px">
    <el-form-item label="触发器名称">
      <el-input
        v-model="editForm.display_name"
        placeholder="请输入触发器名称（可选）"
        maxlength="50"
        show-word-limit
      />
    </el-form-item>
    <el-form-item label="备注">
      <el-input
        v-model="editForm.description"
        type="textarea"
        :rows="4"
        placeholder="请输入备注信息（可选）"
        maxlength="200"
        show-word-limit
      />
    </el-form-item>
  </el-form>

  <template #footer>
    <el-button @click="editDialogVisible = false">取消</el-button>
    <el-button type="primary" @click="handleSaveMetadata" :loading="saveLoading">保存</el-button>
  </template>
</el-dialog>
```

**新增 Vue 逻辑**:

```typescript
// 编辑任务元数据
const editDialogVisible = ref(false)
const editingJob = ref<Job | null>(null)
const editForm = reactive({
  display_name: '',
  description: ''
})
const saveLoading = ref(false)

const showEditDialog = (job: Job) => {
  editingJob.value = job
  editForm.display_name = job.display_name || ''
  editForm.description = job.description || ''
  editDialogVisible.value = true
}

const handleSaveMetadata = async () => {
  if (!editingJob.value) return

  try {
    saveLoading.value = true
    await updateJobMetadata(editingJob.value.id, {
      display_name: editForm.display_name || undefined,
      description: editForm.description || undefined
    })
    ElMessage.success('任务信息已更新')
    editDialogVisible.value = false
    await loadJobs()
  } catch (error: any) {
    ElMessage.error(error.message || '更新任务信息失败')
  } finally {
    saveLoading.value = false
  }
}
```

## 📊 数据库索引

建议为 `scheduler_metadata` 集合创建索引：

```javascript
db.scheduler_metadata.createIndex({ "job_id": 1 }, { unique: true })
```

## 🔒 权限控制

- **查看元数据**: 所有登录用户
- **编辑元数据**: 仅管理员（`is_admin=True`）

## 📝 使用示例

### 1. 编辑任务信息

1. 登录系统（需要管理员权限）
2. 进入"系统管理" -> "定时任务"
3. 找到要编辑的任务，点击"编辑"按钮
4. 在弹出的对话框中填写：
   - **触发器名称**: 例如"Tushare基础信息同步"
   - **备注**: 例如"每天凌晨2点同步股票基础信息，包括股票代码、名称、行业等"
5. 点击"保存"按钮

### 2. 查看任务信息

在任务列表中可以直接看到：
- 任务名称（原始函数名）
- 触发器名称（自定义名称）
- 触发器（cron 表达式）
- 备注（详细说明）
- 下次执行时间

## 🎯 优势

1. **不修改 APScheduler**: 元数据存储在单独的集合中，不影响调度器的正常运行
2. **灵活扩展**: 可以随时添加新的元数据字段
3. **向后兼容**: 没有元数据的任务仍然可以正常显示和运行
4. **用户友好**: 提供直观的编辑界面，支持中文说明

## 📅 实施日期

**实施日期**: 2025-10-08  
**实施人员**: Augment Agent  
**状态**: ✅ 完成

