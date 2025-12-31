# 修复：交易复盘详情查询支持任务中心模式

## 📋 问题描述

**日期**: 2025-12-31  
**问题**: 前端访问 `/api/review/trade/{review_id}` 时返回 404 错误

### 错误现象

```
请求: GET /api/review/trade/d90ca7d2-c0d1-4cac-a1d7-c6381baceba2
响应: 404 Not Found
错误: "复盘报告不存在"
```

### 根本原因

1. **数据存储位置变化**
   - 传统模式：数据存储在 `trade_reviews` 集合
   - 任务中心模式：数据存储在 `unified_analysis_tasks` 集合

2. **查询逻辑未更新**
   - `get_review_detail` 方法只查询 `trade_reviews` 集合
   - 无法找到任务中心模式创建的数据

3. **字段名称差异**
   - `trade_reviews` 集合使用 `review_id` 字段
   - `unified_analysis_tasks` 集合使用 `task_id` 字段

## 🔧 解决方案

### 修改文件

`app/services/trade_review_service.py`

### 修改内容

#### 1. 更新 `get_review_detail` 方法

**变更前**：
```python
async def get_review_detail(
    self,
    user_id: str,
    review_id: str
) -> Optional[TradeReviewReport]:
    """获取复盘详情"""
    doc = await self.db[self.trade_reviews_collection].find_one({
        "user_id": user_id,
        "review_id": review_id
    })

    if not doc:
        return None

    return TradeReviewReport(**doc)
```

**变更后**：
```python
async def get_review_detail(
    self,
    user_id: str,
    review_id: str
) -> Optional[TradeReviewReport]:
    """
    获取复盘详情
    
    支持两种数据源：
    1. trade_reviews 集合（传统模式）
    2. unified_analysis_tasks 集合（任务中心模式）
    """
    # 1. 先从 trade_reviews 集合查询（传统模式）
    doc = await self.db[self.trade_reviews_collection].find_one({
        "user_id": user_id,
        "review_id": review_id
    })

    if doc:
        logger.info(f"📊 [获取复盘详情] 从 trade_reviews 集合找到数据: {review_id}")
        return TradeReviewReport(**doc)

    # 2. 如果没找到，从 unified_analysis_tasks 集合查询（任务中心模式）
    logger.info(f"🔍 [获取复盘详情] trade_reviews 中未找到，尝试从 unified_analysis_tasks 查询: {review_id}")
    
    task_doc = await self.db["unified_analysis_tasks"].find_one({
        "user_id": user_id,
        "task_id": review_id  # review_id 实际上是 task_id
    })

    if not task_doc:
        logger.warning(f"❌ [获取复盘详情] 两个集合都未找到数据: {review_id}")
        return None

    logger.info(f"✅ [获取复盘详情] 从 unified_analysis_tasks 找到数据: {review_id}")
    
    # 3. 将任务数据转换为 TradeReviewReport 格式
    return self._convert_task_to_review_report(task_doc)
```

#### 2. 新增 `_convert_task_to_review_report` 方法

```python
def _convert_task_to_review_report(self, task_doc: dict) -> TradeReviewReport:
    """
    将 unified_analysis_tasks 的任务数据转换为 TradeReviewReport 格式
    
    Args:
        task_doc: unified_analysis_tasks 集合中的文档
        
    Returns:
        TradeReviewReport 对象
    """
    from app.models.review import (
        TradeReviewReport, TradeInfo, MarketSnapshot, AITradeReview,
        ReviewType, ReviewStatus
    )
    from datetime import datetime
    
    # 从任务结果中提取数据
    result = task_doc.get("result", {})
    task_params = task_doc.get("task_params", {})
    
    # 构建各个子对象...
    # （详见代码）
    
    return TradeReviewReport(...)
```

## 📊 查询流程

### 修复前

```
GET /api/review/trade/{review_id}
    ↓
查询 trade_reviews 集合
    ↓
未找到 → 返回 404
```

### 修复后

```
GET /api/review/trade/{review_id}
    ↓
查询 trade_reviews 集合
    ↓
找到？ → 返回数据
    ↓ 否
查询 unified_analysis_tasks 集合
    ↓
找到？ → 转换格式 → 返回数据
    ↓ 否
返回 404
```

## ✅ 优势

1. **向后兼容**
   - 仍然支持传统模式的数据查询
   - 不影响现有功能

2. **统一接口**
   - 前端无需修改
   - 使用相同的API接口

3. **自动适配**
   - 自动识别数据来源
   - 透明的数据格式转换

4. **完整日志**
   - 详细的查询日志
   - 便于问题排查

## 🔄 数据格式映射

### unified_analysis_tasks → TradeReviewReport

| 任务字段 | 复盘字段 | 说明 |
|---------|---------|------|
| `task_id` | `review_id` | 任务ID映射为复盘ID |
| `user_id` | `user_id` | 用户ID保持一致 |
| `status` | `status` | 状态需要映射 |
| `result.trade_info` | `trade_info` | 交易信息 |
| `result.market_snapshot` | `market_snapshot` | 市场快照 |
| `result.ai_review` | `ai_review` | AI分析结果 |
| `task_params.source` | `source` | 数据源 |
| `task_params.trading_system_id` | `trading_system_id` | 交易计划ID |
| `execution_time` | `execution_time` | 执行时间 |
| `error_message` | `error_message` | 错误信息 |

### 状态映射

| 任务状态 | 复盘状态 |
|---------|---------|
| `pending` | `PENDING` |
| `processing` | `PROCESSING` |
| `completed` | `COMPLETED` |
| `failed` | `FAILED` |

## 🔄 前端轮询支持

### 问题

即使后端支持了双数据源查询，前端仍然会遇到问题：

1. **前端提交复盘** → 立即收到 `review_id`（实际上是 `task_id`）
2. **前端立即打开详情对话框** → 触发 `GET /api/review/trade/{review_id}`
3. **任务还在后台执行中** → 数据还没有写入数据库 → **返回 404**

### 解决方案

修改 `ReviewDetailDialog.vue`，添加轮询逻辑：

#### 1. 捕获 404 错误并启动轮询

```typescript
const loadReport = async () => {
  if (!props.reviewId) return

  try {
    loading.value = true
    const res = await reviewApi.getReviewDetail(props.reviewId)
    if (res.success) {
      report.value = res.data || null

      // 🔄 如果状态是 pending 或 processing，启动轮询
      if (report.value && (report.value.status === 'pending' || report.value.status === 'processing')) {
        console.log('🔄 [复盘详情] 任务进行中，启动轮询...')
        startPolling()
      }
    }
  } catch (e: any) {
    // 如果是 404 错误，可能是任务还在创建中，尝试轮询
    if (e.message?.includes('404') || e.message?.includes('不存在')) {
      console.log('🔄 [复盘详情] 数据未找到，可能任务还在创建中，启动轮询...')
      ElMessage.info('复盘任务正在执行中，请稍候...')
      startPolling()
    } else {
      ElMessage.error(e.message || '加载复盘详情失败')
    }
  } finally {
    loading.value = false
  }
}
```

#### 2. 实现轮询逻辑

```typescript
// 轮询相关
let pollingTimer: number | null = null
const maxPollingAttempts = 60 // 最多轮询60次（60秒）
let pollingAttempts = 0

const startPolling = () => {
  // 清除之前的定时器
  if (pollingTimer) {
    clearInterval(pollingTimer)
  }

  pollingAttempts = 0

  pollingTimer = window.setInterval(async () => {
    pollingAttempts++

    console.log(`🔄 [复盘详情] 轮询第 ${pollingAttempts} 次...`)

    try {
      const res = await reviewApi.getReviewDetail(props.reviewId)
      if (res.success && res.data) {
        report.value = res.data

        // 如果任务完成或失败，停止轮询
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          console.log(`✅ [复盘详情] 任务${res.data.status === 'completed' ? '完成' : '失败'}，停止轮询`)
          stopPolling()

          if (res.data.status === 'completed') {
            ElMessage.success('复盘完成')
          } else {
            ElMessage.error(res.data.error_message || '复盘失败')
          }
        }
      }
    } catch (e) {
      console.log('🔄 [复盘详情] 轮询失败，继续等待...')
    }

    // 超过最大轮询次数，停止轮询
    if (pollingAttempts >= maxPollingAttempts) {
      console.log('⏱️ [复盘详情] 轮询超时，停止轮询')
      stopPolling()
      ElMessage.warning('复盘任务执行时间较长，请稍后刷新查看')
    }
  }, 1000) // 每秒轮询一次
}

const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
  pollingAttempts = 0
}
```

#### 3. 对话框关闭时清理定时器

```typescript
watch(() => [props.modelValue, props.reviewId], ([show, id]) => {
  if (show && id) {
    loadReport()
  } else if (!show) {
    // 对话框关闭时，停止轮询
    stopPolling()
  }
})
```

### 轮询流程

```
前端提交复盘
    ↓
收到 task_id
    ↓
打开详情对话框
    ↓
尝试加载详情
    ↓
404 错误？
    ↓ 是
启动轮询（每秒一次）
    ↓
    ├─→ 任务完成 → 显示详情 → 停止轮询
    ├─→ 任务失败 → 显示错误 → 停止轮询
    └─→ 超时（60秒） → 提示稍后查看 → 停止轮询
```

## 🧪 测试验证

### 测试场景

1. **任务中心模式创建的复盘（立即查看）**
   ```bash
   # 创建复盘（返回 task_id）
   POST /api/review/trade

   # 立即查询详情（使用 task_id）
   GET /api/review/trade/{task_id}

   # 预期：
   # - 首次请求可能返回 404
   # - 前端自动启动轮询
   # - 任务完成后显示详情
   ```

2. **任务中心模式创建的复盘（稍后查看）**
   ```bash
   # 创建复盘（返回 task_id）
   POST /api/review/trade

   # 等待任务完成后查询详情
   GET /api/review/trade/{task_id}

   # 预期：
   # - 直接返回完整数据
   # - 不需要轮询
   ```

3. **传统模式创建的复盘**
   ```bash
   # 查询详情（使用 review_id）
   GET /api/review/trade/{review_id}

   # 预期：成功返回数据
   ```

4. **不存在的复盘**
   ```bash
   # 查询详情（使用不存在的ID）
   GET /api/review/trade/invalid-id

   # 预期：
   # - 启动轮询
   # - 60秒后超时
   # - 提示稍后查看
   ```

## 📝 相关文档

- [交易复盘任务中心集成设计](../design/v2.0/trade-review-task-center-integration.md)
- [移除分析版本选择器总结](../changes/SUMMARY-remove-analysis-version-selector.md)
- [分析结果API支持统一任务](./api/result_api_unified_tasks_support.md)

## 🎯 总结

通过**后端双数据源查询**和**前端轮询机制**，实现了：

### 后端改进
- ✅ 支持从 `trade_reviews` 集合查询（传统模式）
- ✅ 支持从 `unified_analysis_tasks` 集合查询（任务中心模式）
- ✅ 自动数据格式转换
- ✅ 向后兼容

### 前端改进
- ✅ 自动检测任务状态
- ✅ 智能轮询机制
- ✅ 实时进度反馈
- ✅ 超时保护

### 用户体验
- ✅ 提交复盘后立即查看详情
- ✅ 自动等待任务完成
- ✅ 实时显示任务状态
- ✅ 无需手动刷新

现在前端可以正常查询任务中心模式创建的复盘详情了！

