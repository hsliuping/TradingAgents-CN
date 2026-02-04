# Job ID 一致性修复报告

## 问题根源分析

### 问题描述
任务函数内部使用的 `job_id` 与 APScheduler 注册的 `id` 不一致，导致：
1. 前端查询任务进度时找不到对应的执行记录
2. 任务完成时无法正确更新状态
3. Redis 缓存和 MongoDB 记录使用不同的 job_id

### 根本原因
代码中存在两种不同的 job_id 传递方式：

1. **Tushare 方式**（正确）：
   - 任务函数硬编码 job_id
   - 调用 sync_* 方法时通过参数传递 job_id
   - 例如：`service.sync_stock_basic_info(force_update, job_id=job_id)`

2. **AKShare/BaoStock 方式**（有问题）：
   - sync_* 方法内部使用 `getattr(self, '_current_job_id', None) or "默认值"`
   - 任务函数没有设置 `service._current_job_id`
   - 导致使用默认值，可能与 APScheduler 注册的 id 不一致

## 修复清单

### ✅ 已修复的任务

#### 1. **news_sync** (AKShare 新闻同步)
- **APScheduler ID**: `news_sync`
- **问题**: `sync_news_data` 默认使用 `akshare_news_sync`
- **修复**: 在 `run_news_sync` 中设置 `service._current_job_id = "news_sync"`
- **文件**: `app/main.py:655`

#### 2. **akshare_basic_info_sync** (AKShare 基础信息同步)
- **APScheduler ID**: `akshare_basic_info_sync`
- **问题**: `sync_stock_basic_info` 默认使用 `akshare_basic_info_sync`（一致，但需要显式设置）
- **修复**: 在 `run_akshare_basic_info_sync` 中设置 `service._current_job_id = job_id`
- **文件**: `app/worker/akshare_sync_service.py:1654`

#### 3. **akshare_quotes_sync** (AKShare 实时行情同步)
- **APScheduler ID**: `akshare_quotes_sync`
- **问题**: `sync_realtime_quotes` 默认使用 `akshare_quotes_sync`（一致，但需要显式设置）
- **修复**: 在 `run_akshare_quotes_sync` 中添加 job_id 检查和设置
- **文件**: `app/worker/akshare_sync_service.py:1670-1673`

#### 4. **akshare_historical_sync** (AKShare 历史数据同步)
- **APScheduler ID**: `akshare_historical_sync`
- **问题**: `sync_historical_data` 默认使用 `akshare_historical_sync`（一致，但需要显式设置）
- **修复**: 在 `run_akshare_historical_sync` 中设置 `service._current_job_id = job_id`
- **文件**: `app/worker/akshare_sync_service.py:1698`

#### 5. **akshare_financial_sync** (AKShare 财务数据同步)
- **APScheduler ID**: `akshare_financial_sync`
- **问题**: `sync_financial_data` 默认使用 `akshare_financial_sync`（一致，但需要显式设置）
- **修复**: 在 `run_akshare_financial_sync` 中添加 job_id 检查和设置
- **文件**: `app/worker/akshare_sync_service.py:1709-1712`

#### 6. **baostock_basic_info_sync** (BaoStock 基础信息同步)
- **APScheduler ID**: `baostock_basic_info_sync`
- **问题**: `sync_stock_basic_info` 默认使用 `baostock_basic_info_sync`（一致，但需要显式设置）
- **修复**: 在 `run_baostock_basic_info_sync` 中设置 `service._current_job_id = job_id`
- **文件**: `app/worker/baostock_sync_service.py:712`

#### 7. **baostock_daily_quotes_sync** (BaoStock 日K线同步)
- **APScheduler ID**: `baostock_daily_quotes_sync`
- **问题**: `sync_daily_quotes` 默认使用 `baostock_daily_quotes_sync`（一致，但需要显式设置）
- **修复**: 在 `run_baostock_daily_quotes_sync` 中添加 job_id 检查和设置
- **文件**: `app/worker/baostock_sync_service.py:721-724`

#### 8. **baostock_historical_sync** (BaoStock 历史数据同步)
- **APScheduler ID**: `baostock_historical_sync`
- **问题**: `sync_historical_data` 默认使用 `baostock_historical_sync`（一致，但需要显式设置）
- **修复**: 在 `run_baostock_historical_sync` 中设置 `service._current_job_id = job_id`
- **文件**: `app/worker/baostock_sync_service.py:747`

### ✅ 已确认一致的任务（无需修复）

#### Tushare 任务（全部正确）
- ✅ `tushare_basic_info_sync` - 硬编码 job_id 并传递给 sync 方法
- ✅ `tushare_realtime_quotes_hourly` - 硬编码 job_id
- ✅ `tushare_historical_sync` - 硬编码 job_id 并传递给 sync 方法
- ✅ `tushare_financial_sync` - 硬编码 job_id 并传递给 sync 方法
- ✅ `tushare_status_check` - 不更新进度，不需要 job_id

#### 其他任务
- ✅ `favorites_data_sync` - 硬编码 job_id，直接调用 `update_job_progress`
- ✅ `watchlist_analysis` - 使用统一任务中心，不依赖 scheduler_executions
- ✅ `basics_sync_service` - 多数据源服务，不依赖 scheduler_executions
- ✅ `quotes_ingestion_service` - 实时行情入库服务，不依赖 scheduler_executions

## 修复模式

### 标准修复模式

对于所有使用 `_current_job_id` 的任务函数，统一添加：

```python
async def run_xxx_sync(...):
    """APScheduler任务：..."""
    job_id = "xxx_sync"  # 与 APScheduler 注册的 id 一致
    
    # 🔥 检查是否已有实例在运行
    is_running, instance_id = await _check_task_running(job_id)
    if is_running:
        logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
        return {
            "skipped": True,
            "reason": "已有实例在运行",
            "running_instance_id": instance_id
        }
    
    try:
        service = await get_xxx_sync_service()
        # 🔥 设置正确的 job_id，确保进度更新和状态标记使用正确的任务ID
        service._current_job_id = job_id
        result = await service.sync_xxx(...)
        ...
```

## 验证方法

1. **检查 APScheduler 注册的 ID**：
   ```python
   # app/main.py 中查找 scheduler.add_job(id="...")
   ```

2. **检查任务函数使用的 job_id**：
   ```python
   # 查找 job_id = "..." 或 service._current_job_id = "..."
   ```

3. **检查 sync_* 方法使用的 job_id**：
   ```python
   # 查找 getattr(self, '_current_job_id', None) or "默认值"
   ```

4. **确保一致性**：
   - APScheduler 注册的 id == 任务函数中的 job_id == sync_* 方法使用的 job_id

## 预防措施

### 建议的代码规范

1. **统一使用参数传递**（推荐）：
   - 所有 sync_* 方法接受 `job_id` 参数
   - 任务函数硬编码 job_id 并通过参数传递
   - 避免使用 `_current_job_id` 属性

2. **如果必须使用 `_current_job_id`**：
   - 必须在任务函数开始处设置
   - 确保与 APScheduler 注册的 id 完全一致
   - 添加注释说明为什么使用这种方式

3. **添加验证**：
   - 在 sync_* 方法开始处验证 job_id 是否设置
   - 如果未设置，记录警告日志

## 总结

- **修复数量**: 8 个任务函数
- **修复文件**: 
  - `app/main.py` (1处)
  - `app/worker/akshare_sync_service.py` (5处)
  - `app/worker/baostock_sync_service.py` (3处)
- **验证状态**: ✅ 所有任务函数已修复并验证

所有任务现在都能正确使用与 APScheduler 注册的 id 一致的 job_id，确保前端查询和状态更新正常工作。
