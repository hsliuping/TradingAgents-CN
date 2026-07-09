# 基于线程池的数据同步处理方案设计

## 1. 问题分析

### 1.1 当前实现的问题

1. **协程并发 vs 线程并发**
   - 当前使用 `asyncio.gather` 进行协程级别的并发
   - 协程并发在遇到 I/O 阻塞时可能卡住整个事件循环
   - 如果某个协程中的网络请求超时或数据库操作阻塞，会影响其他协程

2. **进度更新不及时**
   - 进度更新依赖于批次处理完成
   - 如果某个批次卡住，进度不会更新
   - 用户看到"40/5799"但进度显示0%，说明进度计算有问题

3. **任务卡住问题**
   - 单个股票处理时间过长会导致整个批次等待
   - 没有超时机制
   - 没有任务取消机制

4. **资源管理**
   - 没有线程池大小限制
   - 可能导致资源耗尽

## 2. 设计方案

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    ThreadPoolSyncService                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ThreadPoolExecutor (max_workers=10-20)            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ Worker 1 │  │ Worker 2 │  │ Worker N │  ...    │  │
│  │  └──────────┘  └──────────┘  └──────────┘         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Task Queue (Queue)                                   │  │
│  │  - 股票代码列表                                        │  │
│  │  - 任务参数                                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Result Queue (Queue)                                 │  │
│  │  - 成功结果                                            │  │
│  │  - 错误信息                                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Progress Tracker                                      │  │
│  │  - 实时进度更新                                        │  │
│  │  - 统计信息                                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 ThreadPoolSyncService

**职责**：
- 管理线程池生命周期
- 分发任务到工作线程
- 收集结果并更新进度
- 处理错误和重试

**关键参数**：
```python
class ThreadPoolSyncService:
    def __init__(
        self,
        max_workers: int = 10,           # 线程池大小
        timeout_per_task: int = 36000,   # 单个任务超时时间（秒，默认10小时，用于历史数据同步）
        progress_update_interval: int = 5,  # 进度更新间隔（秒）
        enable_retry: bool = True,       # 是否启用重试
        max_retries: int = 3             # 最大重试次数
    ):
```

#### 2.2.2 Worker Thread

**职责**：
- 从任务队列获取任务
- 执行同步操作（调用 provider API）
- 保存数据到数据库
- 将结果放入结果队列

**处理流程**：
```
1. 从任务队列获取股票代码
2. 检查任务是否已取消
3. 调用 provider.get_financial_data(symbol)
4. 保存数据到数据库
5. 将结果放入结果队列
6. 更新统计信息
```

#### 2.2.3 Progress Tracker

**职责**：
- 实时跟踪处理进度
- 定期更新到 MongoDB/Redis
- 计算剩余时间
- 统计成功/失败数量

**更新机制**：
- 每处理完一个股票，立即更新统计
- 每 N 秒（可配置）更新一次进度到数据库
- 使用线程安全的计数器

### 2.3 数据流设计

```
主线程 (Async)
    │
    ├─> 初始化 ThreadPoolExecutor
    ├─> 创建任务队列，填充股票列表
    ├─> 启动工作线程（Worker Threads）
    │   │
    │   ├─> Worker 1: 处理股票 A
    │   ├─> Worker 2: 处理股票 B
    │   ├─> Worker 3: 处理股票 C
    │   └─> ...
    │
    ├─> 启动进度跟踪线程
    │   │
    │   └─> 定期更新进度到数据库
    │
    └─> 等待所有任务完成
        │
        └─> 收集结果，返回统计信息
```

### 2.4 关键特性

#### 2.4.1 真正的并行处理

- 使用 `ThreadPoolExecutor` 实现真正的多线程
- 每个线程独立处理一个股票
- 线程之间互不干扰

#### 2.4.2 实时进度更新

```python
class ProgressTracker:
    def __init__(self, job_id: str, total_items: int):
        self.job_id = job_id
        self.total_items = total_items
        self.processed_items = 0  # 线程安全的计数器
        self.success_count = 0
        self.error_count = 0
        self.lock = threading.Lock()
    
    def update(self, success: bool):
        with self.lock:
            self.processed_items += 1
            if success:
                self.success_count += 1
            else:
                self.error_count += 1
            
            # 计算进度
            progress = int((self.processed_items / self.total_items) * 100)
            
            # 异步更新到数据库（不阻塞工作线程）
            asyncio.create_task(self._update_progress(progress))
```

#### 2.4.3 任务取消机制

```python
class CancellationToken:
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self):
        with self._lock:
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

# 在工作线程中检查
if cancellation_token.is_cancelled():
    logger.info(f"任务已取消，停止处理 {symbol}")
    return
```

#### 2.4.4 超时处理

```python
from concurrent.futures import TimeoutError

try:
    future = executor.submit(process_symbol, symbol, ...)
    result = future.result(timeout=timeout_per_task)
except TimeoutError:
    logger.error(f"{symbol} 处理超时（{timeout_per_task}秒）")
    # 标记为失败，继续处理下一个
```

#### 2.4.5 错误处理和重试

```python
def process_symbol_with_retry(symbol, max_retries=3):
    for attempt in range(max_retries):
        try:
            return process_symbol(symbol)
        except RetryableError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                time.sleep(wait_time)
                continue
            else:
                raise
        except NonRetryableError as e:
            # 不可重试的错误，直接失败
            raise
```

### 2.5 集成方案

#### 2.5.1 与现有代码集成

```python
# 在 FinancialDataSyncService 中使用线程池服务
class FinancialDataSyncService:
    async def sync_financial_data(
        self,
        symbols: List[str],
        data_sources: List[str],
        job_id: str = None
    ):
        # 创建线程池同步服务
        thread_pool_service = ThreadPoolSyncService(
            max_workers=10,
            timeout_per_task=300
        )
        
        # 为每个数据源创建同步任务
        for data_source in data_sources:
            await thread_pool_service.sync_in_thread_pool(
                items=symbols,
                process_func=self._sync_symbol_financial_data,
                job_id=f"{job_id}_{data_source}",
                context={"data_source": data_source}
            )
```

#### 2.5.2 进度更新集成

```python
# 在 ThreadPoolSyncService 中集成 update_job_progress
async def _update_progress(self, progress_tracker: ProgressTracker):
    from app.services.scheduler_service import update_job_progress
    
    await update_job_progress(
        job_id=self.job_id,
        progress=progress_tracker.get_progress(),
        message=f"正在同步财务数据 ({progress_tracker.processed_items}/{progress_tracker.total_items})",
        current_item=progress_tracker.current_item,
        total_items=progress_tracker.total_items,
        processed_items=progress_tracker.processed_items
    )
```

## 3. 实现细节

### 3.1 线程安全

- 使用 `threading.Lock` 保护共享数据
- 使用线程安全的队列（`queue.Queue`）
- 使用 `threading.local()` 存储线程本地数据

### 3.2 异步与同步的桥接

```python
# 在工作线程中调用异步函数
def sync_wrapper(async_func, *args, **kwargs):
    """将异步函数包装为同步函数，在工作线程中调用"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func(*args, **kwargs))
    finally:
        loop.close()
```

### 3.3 资源管理

- 使用 `with` 语句管理线程池
- 确保线程池正确关闭
- 清理资源，避免内存泄漏

## 4. 配置参数

### 4.1 线程池配置

```python
THREAD_POOL_CONFIG = {
    "max_workers": 10,              # 线程池大小（根据CPU核心数调整）
    "timeout_per_task": 36000,      # 单个任务超时时间（秒，10小时，用于历史数据同步）
    "progress_update_interval": 5,  # 进度更新间隔（秒）
    "enable_retry": True,           # 是否启用重试
    "max_retries": 3,               # 最大重试次数
    "retry_delay": 2,                # 重试延迟（秒）
}
```

### 4.2 数据源特定配置

```python
DATA_SOURCE_CONFIG = {
    "tushare": {
        "max_workers": 5,           # Tushare API限制较严格
        "timeout_per_task": 36000,  # 10小时（历史数据同步需要很长时间）
        "rate_limit": 200           # 每分钟请求数
    },
    "akshare": {
        "max_workers": 10,
        "timeout_per_task": 36000,  # 10小时
        "rate_limit": 100
    },
    "baostock": {
        "max_workers": 15,
        "timeout_per_task": 36000,  # 10小时
        "rate_limit": 50
    }
}
```

### 4.3 任务类型特定配置

```python
TASK_TYPE_CONFIG = {
    "financial": {
        "timeout_per_task": 36000,  # 10小时（财务数据同步也需要很长时间，特别是全量同步）
        "max_workers": 10
    },
    "historical": {
        "timeout_per_task": 36000,  # 10小时（历史数据同步需要很长时间）
        "max_workers": 10
    },
    "news": {
        "timeout_per_task": 1800,   # 30分钟（新闻数据同步相对较快）
        "max_workers": 15
    }
}
```

## 5. 优势

1. **真正的并行处理**：多个线程同时处理不同股票，互不干扰
2. **实时进度更新**：每处理完一个股票立即更新进度
3. **任务取消支持**：可以随时取消正在执行的任务
4. **超时保护**：单个任务超时不会影响其他任务
5. **错误隔离**：单个股票处理失败不影响其他股票
6. **资源可控**：通过线程池大小控制资源使用

## 6. 注意事项

1. **数据库连接**：每个线程需要独立的数据库连接
2. **异步函数调用**：在工作线程中调用异步函数需要特殊处理
3. **进度更新频率**：避免过于频繁的数据库更新
4. **线程安全**：确保所有共享数据都是线程安全的

## 7. 测试计划

1. **单元测试**：测试线程池服务的基本功能
2. **集成测试**：测试与现有服务的集成
3. **性能测试**：测试并发处理性能
4. **压力测试**：测试大量任务的处理能力
5. **错误测试**：测试错误处理和恢复机制

## 8. 迁移计划

1. **阶段1**：实现 ThreadPoolSyncService 基础功能
2. **阶段2**：集成到 FinancialDataSyncService
3. **阶段3**：扩展到其他同步服务（历史数据、新闻数据等）
4. **阶段4**：优化和性能调优
5. **阶段5**：完全替换旧实现
