# 统一任务中心导入错误修复

## 🐛 问题描述

### 问题 1: 后端导入错误

启动后端时出现导入错误：

```
ImportError: cannot import name 'get_current_user_id' from 'app.routers.auth_db'
```

**错误位置**: `app/routers/unified_tasks.py` 第 15 行

### 问题 2: 前端导入错误

启动前端时出现导入错误：

```
Failed to resolve import "./client" from "src/api/unifiedTasks.ts". Does the file exist?
```

**错误位置**: `frontend/src/api/unifiedTasks.ts` 第 8 行

## 🔍 问题分析

### 问题 1: 后端导入错误

#### 根本原因

`app.routers.auth_db` 模块中只有 `get_current_user` 函数，没有 `get_current_user_id` 函数。

### 现有认证机制

**文件**: `app/routers/auth_db.py`

```python
async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """获取当前用户信息"""
    # ... 验证 token ...
    
    # 返回完整的用户信息
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "name": user.username,
        "is_admin": user.is_admin,
        "roles": ["admin"] if user.is_admin else ["user"],
        "preferences": user.preferences.model_dump() if user.preferences else {}
    }
```

**返回值**: 字典，包含 `id` 字段（字符串类型）

### 问题 2: 前端导入错误

#### 根本原因

`frontend/src/api/` 目录下没有 `client.ts` 文件。

#### 正确的导入方式

项目中所有 API 文件都从 `'./request'` 导入 `ApiClient`：

**参考示例**: `frontend/src/api/stocks.ts`
```typescript
import { ApiClient } from './request'

export const stocksApi = {
  async getQuote(symbol: string) {
    return ApiClient.get<QuoteResponse>(`/api/stocks/${symbol}/quote`)
  }
}
```

**参考示例**: `frontend/src/api/scheduler.ts`
```typescript
import { ApiClient } from './request'

export function getJobs() {
  return ApiClient.get<Job[]>('/api/scheduler/jobs')
}
```

## 🛠️ 修复方案

### 修复 1: 后端导入错误

### 修改内容

**文件**: `app/routers/unified_tasks.py`

#### 1. 修改导入语句

**修改前**:
```python
from app.routers.auth_db import get_current_user_id
```

**修改后**:
```python
from app.routers.auth_db import get_current_user
```

#### 2. 修改所有端点的依赖注入

**修改前**:
```python
@router.get("/list", summary="获取任务列表")
async def get_task_list(
    task_type: Optional[AnalysisTaskType] = Query(None, description="任务类型过滤"),
    status: Optional[AnalysisStatus] = Query(None, description="状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    user_id: PyObjectId = Depends(get_current_user_id)  # ❌ 错误
):
    try:
        service = get_task_analysis_service()
        
        tasks = await service.list_user_tasks(
            user_id=user_id,  # ❌ 直接使用
            ...
        )
```

**修改后**:
```python
@router.get("/list", summary="获取任务列表")
async def get_task_list(
    task_type: Optional[AnalysisTaskType] = Query(None, description="任务类型过滤"),
    status: Optional[AnalysisStatus] = Query(None, description="状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    user: dict = Depends(get_current_user)  # ✅ 正确
):
    try:
        user_id = PyObjectId(user["id"])  # ✅ 从字典中提取 ID 并转换
        service = get_task_analysis_service()
        
        tasks = await service.list_user_tasks(
            user_id=user_id,
            ...
        )
```

### 修改的端点

1. **GET /api/v2/tasks/list** - 获取任务列表
2. **GET /api/v2/tasks/statistics** - 获取任务统计
3. **GET /api/v2/tasks/{task_id}** - 获取任务详情
4. **DELETE /api/v2/tasks/{task_id}** - 取消任务

### 修改模式

所有端点都遵循相同的修改模式：

```python
# 1. 依赖注入改为 get_current_user
user: dict = Depends(get_current_user)

# 2. 在函数内部提取 user_id 并转换类型
user_id = PyObjectId(user["id"])

# 3. 使用 user_id 调用服务
service.method(user_id=user_id, ...)
```

### 修复 2: 前端导入错误

**文件**: `frontend/src/api/unifiedTasks.ts`

#### 修改导入语句

**修改前**:
```typescript
import ApiClient from './client'  // ❌ 错误：文件不存在
```

**修改后**:
```typescript
import { ApiClient } from './request'  // ✅ 正确：使用项目标准导入
```

## ✅ 修复结果

### 修复前

**后端错误**:
```
ImportError: cannot import name 'get_current_user_id' from 'app.routers.auth_db'
```

**前端错误**:
```
Failed to resolve import "./client" from "src/api/unifiedTasks.ts". Does the file exist?
```

### 修复后

- ✅ 后端导入错误已解决
- ✅ 前端导入错误已解决
- ✅ 所有端点使用正确的认证依赖
- ✅ 用户 ID 正确提取和转换
- ✅ 后端可以正常启动
- ✅ 前端可以正常编译

## 📊 影响范围

### 修改的文件

- `app/routers/unified_tasks.py` - 后端路由文件
- `frontend/src/api/unifiedTasks.ts` - 前端 API 文件

### 修改的行数

**后端**:
- 导入语句: 1 行
- 端点函数: 4 个端点，每个端点 2-3 行修改
- 总计: 约 10 行修改

**前端**:
- 导入语句: 1 行

### 影响的功能

- 统一任务中心 API (`/api/v2/tasks/*`)
- 统一任务中心前端页面 (`/tasks/unified`)
- 所有需要用户认证的任务查询功能

## 🔄 相关模式

### 其他路由的参考

项目中其他路由也使用相同的模式：

**示例 1**: `app/routers/license.py`
```python
@router.get("/status")
async def get_license_status(
    user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False)
):
    user_id = str(user["id"])
    # ...
```

**示例 2**: `app/routers/agents.py`
```python
async def get_user_license_tier(
    user: dict = Depends(get_current_user),
    x_app_token: Optional[str] = Header(None)
) -> str:
    logger.info(f"🔍 检查用户许可证: user_id={user.get('id')}")
    # ...
```

## 📝 经验教训

1. **统一认证模式**: 项目中应该统一使用 `get_current_user` 依赖
2. **类型转换**: 从 `user["id"]` (字符串) 转换为 `PyObjectId` 时要注意
3. **参考现有代码**: 新增路由时应参考现有路由的认证模式

## 🎯 验证步骤

1. **启动后端**: `python -m app`
2. **检查日志**: 确认没有导入错误
3. **测试 API**: 访问 `/api/v2/tasks/list` 等端点
4. **验证认证**: 确认需要有效的 token 才能访问

## 🔗 相关文档

- [统一任务中心实施文档](../design/unified-task-center-implementation.md)
- [认证系统文档](../archive/AUTHENTICATION_FIX_SUMMARY.md)

