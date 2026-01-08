# 仪表板"最近分析"显示修复

## 需求

仪表板的"最近分析"部分应该显示：
- **当前用户**的任务
- 按**开始时间**倒序排列
- 显示**最近10条**

## 修改内容

### 1. 前端修改

**文件**：`frontend/src/views/Dashboard/index.vue`

**修改**：将 `page_size` 从 5 改为 10

```typescript
const loadRecentAnalyses = async () => {
  try {
    const response = await getAnalysisHistory({
      page: 1,
      page_size: 10,  // 获取最近10条（修改前是5）
      status: undefined
    })
    if (response.success && response.data) {
      // 后端已经按开始时间倒序排列，直接使用
      recentAnalyses.value = response.data.tasks || []
      
      // 更新统计数据
      userStats.value.totalAnalyses = response.data.total || 0
      userStats.value.successfulAnalyses = response.data.tasks?.filter(
        (item: any) => item.status === 'completed'
      ).length || 0
    }
  } catch (error) {
    console.error('加载最近分析失败:', error)
  }
}
```

### 2. 后端逻辑确认

**文件**：`app/services/simple_analysis_service.py`

**确认**：`list_user_tasks` 方法已经按开始时间倒序排列（第1277行）

```python
# 转换为列表并按时间排序
merged_tasks = list(task_dict.values())
merged_tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)  # ✅ 倒序排列

# 分页
results = merged_tasks[offset:offset + limit]
```

**API 端点**：`GET /api/analysis/user/history`

**查询参数**：
- `page`: 页码（默认1）
- `page_size`: 每页大小（默认20，最大100）
- `status`: 状态筛选（可选）
- `start_date`: 开始日期（可选）
- `end_date`: 结束日期（可选）
- `stock_code`: 股票代码（可选）
- `market_type`: 市场类型（可选）

**响应格式**：
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "task_id": "abc-123",
        "stock_code": "601398",
        "stock_name": "工商银行",
        "status": "completed",
        "progress": 100,
        "start_time": "2025-01-01T10:00:00Z",
        "created_at": "2025-01-01T09:59:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 10
  },
  "message": "历史查询成功"
}
```

## 数据来源

### 任务数据合并逻辑

后端从两个地方获取任务数据：

1. **内存**（`MemoryStateManager`）：
   - 存储正在运行的任务（`running`/`pending` 状态）
   - 实时进度数据
   - 快速访问

2. **MongoDB**（`analysis_tasks` 集合）：
   - 存储已完成/失败的任务（`completed`/`failed` 状态）
   - 持久化存储
   - 历史记录

**合并策略**：
- 先从 MongoDB 读取任务
- 再从内存读取任务
- 内存中的任务覆盖 MongoDB 中的同名任务（内存优先）
- 按 `start_time` 倒序排列
- 分页返回

## 排序字段说明

任务对象包含两个时间字段：

1. **`created_at`**：任务创建时间（提交到队列的时间）
2. **`start_time`**：任务开始执行时间（实际开始分析的时间）

**排序使用 `start_time`**，因为：
- 更准确反映任务的实际执行顺序
- 用户更关心"最近执行的任务"而不是"最近提交的任务"
- 如果任务在队列中等待，`start_time` 会晚于 `created_at`

## 显示效果

仪表板"最近分析"表格显示：

| 股票代码 | 股票名称 | 状态 | 创建时间 | 操作 |
|---------|---------|------|---------|------|
| 601398 | 工商银行 | 已完成 | 2025-01-01 10:00 | 查看 / 下载 |
| 000001 | 平安银行 | 已完成 | 2025-01-01 09:30 | 查看 / 下载 |
| 600519 | 贵州茅台 | 处理中 | 2025-01-01 09:00 | 查看 |
| ... | ... | ... | ... | ... |

**特点**：
- ✅ 显示当前用户的任务
- ✅ 按开始时间倒序（最新的在最上面）
- ✅ 显示最近10条
- ✅ 包含所有状态（pending/running/completed/failed）
- ✅ 实时更新（内存中的任务优先）

## 测试建议

1. **执行几次分析任务**：
   - 提交3-5个分析任务
   - 等待任务完成

2. **刷新仪表板页面**：
   - 访问 `http://localhost:5173/dashboard`
   - 查看"最近分析"部分

3. **验证显示**：
   - 确认显示的是当前用户的任务
   - 确认按开始时间倒序排列（最新的在最上面）
   - 确认最多显示10条
   - 确认包含正在运行的任务

4. **验证实时性**：
   - 提交一个新任务
   - 刷新仪表板
   - 确认新任务出现在列表顶部

## 相关文件

- `frontend/src/views/Dashboard/index.vue` - 仪表板页面
- `frontend/src/api/analysis.ts` - 分析 API
- `app/routers/analysis.py` - 后端分析路由
- `app/services/simple_analysis_service.py` - 分析服务
- `app/services/memory_state_manager.py` - 内存状态管理器

## 注意事项

1. **分页参数**：
   - 前端请求 `page=1, page_size=10`
   - 后端返回最近10条任务

2. **状态筛选**：
   - 前端传 `status=undefined`，表示获取所有状态的任务
   - 如果只想显示已完成的任务，可以传 `status='completed'`

3. **性能优化**：
   - 内存中的任务数量有限（通常 < 100）
   - MongoDB 查询使用索引（`start_time` 字段）
   - 合并操作在内存中进行，速度很快

4. **数据一致性**：
   - 内存中的任务优先（覆盖 MongoDB 中的同名任务）
   - 确保显示的是最新的任务状态和进度

