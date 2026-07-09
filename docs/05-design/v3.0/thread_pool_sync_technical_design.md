# 线程池同步服务技术设计文档

## 1. 类设计

### 1.1 ThreadPoolSyncService（主服务类）

```python
class ThreadPoolSyncService:
    """
    基于线程池的数据同步服务
    
    特性：
    - 真正的多线程并行处理
    - 实时进度更新
    - 任务取消支持
    - 超时保护
    - 错误隔离和重试
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        timeout_per_task: int = 36000,  # 默认10小时（36000秒），用于历史数据同步
        progress_update_interval: int = 5,
        enable_retry: bool = True,
        max_retries: int = 3
    ):
        self.max_workers = max_workers
        self.timeout_per_task = timeout_per_task
        self.progress_update_interval = progress_update_interval
        self.enable_retry = enable_retry
        self.max_retries = max_retries
        
        # 线程池
        self.executor = None
        
        # 任务队列和结果队列
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 进度跟踪器
        self.progress_tracker = None
        
        # 取消令牌
        self.cancellation_token = CancellationToken()
        
        # 统计信息
        self.stats = SyncStats()
    
    async def sync_in_thread_pool(
        self,
        items: List[str],
        process_func: Callable,
        job_id: str,
        context: Dict[str, Any] = None
    ) -> SyncStats:
        """
        在线程池中执行同步任务
        
        Args:
            items: 要处理的项列表（如股票代码列表）
            process_func: 处理函数（同步或异步）
            job_id: 任务ID，用于进度跟踪
            context: 上下文信息（传递给处理函数）
        
        Returns:
            同步统计信息
        """
        # 1. 初始化进度跟踪器
        self.progress_tracker = ProgressTracker(
            job_id=job_id,
            total_items=len(items)
        )
        
        # 2. 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 3. 填充任务队列
        for item in items:
            self.task_queue.put((item, context))
        
        # 4. 启动工作线程
        futures = []
        for _ in range(self.max_workers):
            future = self.executor.submit(
                self._worker_loop,
                process_func,
                context
            )
            futures.append(future)
        
        # 5. 启动进度更新任务
        progress_task = asyncio.create_task(self._progress_update_loop())
        
        # 6. 等待所有任务完成
        try:
            # 等待所有工作线程完成
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"工作线程异常: {e}")
            
            # 等待进度更新任务完成
            await progress_task
            
        finally:
            # 关闭线程池
            self.executor.shutdown(wait=True)
        
        return self.stats
    
    def _worker_loop(self, process_func: Callable, context: Dict[str, Any]):
        """
        工作线程主循环
        
        从任务队列获取任务并处理
        """
        while True:
            # 检查是否已取消
            if self.cancellation_token.is_cancelled():
                logger.info("任务已取消，工作线程退出")
                break
            
            try:
                # 从队列获取任务（超时1秒，避免无限等待）
                try:
                    item, task_context = self.task_queue.get(timeout=1)
                except queue.Empty:
                    # 队列为空，检查是否所有任务都已完成
                    if self.progress_tracker.is_complete():
                        break
                    continue
                
                # 处理任务
                try:
                    result = self._process_item(
                        item,
                        process_func,
                        {**(context or {}), **(task_context or {})}
                    )
                    
                    # 更新统计
                    self.progress_tracker.record_success(item)
                    self.stats.success_count += 1
                    
                except Exception as e:
                    # 处理失败
                    self.progress_tracker.record_error(item, str(e))
                    self.stats.error_count += 1
                    self.stats.errors.append({
                        "item": item,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                finally:
                    self.task_queue.task_done()
                    
            except Exception as e:
                logger.error(f"工作线程异常: {e}", exc_info=True)
                break
    
    def _process_item(
        self,
        item: str,
        process_func: Callable,
        context: Dict[str, Any]
    ):
        """
        处理单个项目
        
        支持同步和异步函数
        """
        # 检查是否已取消
        if self.cancellation_token.is_cancelled():
            raise CancelledError("任务已取消")
        
        # 如果是异步函数，需要在线程中运行
        if asyncio.iscoroutinefunction(process_func):
            return self._run_async_in_thread(process_func, item, context)
        else:
            # 同步函数，直接调用
            return process_func(item, **context)
    
    def _run_async_in_thread(
        self,
        async_func: Callable,
        item: str,
        context: Dict[str, Any]
    ):
        """
        在线程中运行异步函数
        
        创建新的事件循环，避免与主事件循环冲突
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                async_func(item, **context)
            )
        finally:
            loop.close()
    
    async def _progress_update_loop(self):
        """
        进度更新循环
        
        定期更新进度到数据库
        """
        while not self.progress_tracker.is_complete():
            # 检查是否已取消
            if self.cancellation_token.is_cancelled():
                break
            
            # 更新进度
            await self._update_progress()
            
            # 等待更新间隔
            await asyncio.sleep(self.progress_update_interval)
        
        # 最后一次更新
        await self._update_progress()
    
    async def _update_progress(self):
        """
        更新进度到数据库
        """
        if not self.progress_tracker:
            return
        
        progress = self.progress_tracker.get_progress()
        current_item = self.progress_tracker.get_current_item()
        
        from app.services.scheduler_service import update_job_progress
        
        await update_job_progress(
            job_id=self.progress_tracker.job_id,
            progress=progress,
            message=f"正在同步数据 ({self.progress_tracker.processed_items}/{self.progress_tracker.total_items})",
            current_item=current_item,
            total_items=self.progress_tracker.total_items,
            processed_items=self.progress_tracker.processed_items
        )
    
    def cancel(self):
        """
        取消任务
        """
        self.cancellation_token.cancel()
        logger.info("任务取消请求已发送")
```

### 1.2 ProgressTracker（进度跟踪器）

```python
class ProgressTracker:
    """
    线程安全的进度跟踪器
    """
    
    def __init__(self, job_id: str, total_items: int):
        self.job_id = job_id
        self.total_items = total_items
        
        # 线程安全的计数器
        self._processed_items = 0
        self._success_count = 0
        self._error_count = 0
        self._current_item = None
        
        # 锁
        self._lock = threading.Lock()
        
        # 错误列表
        self._errors = []
    
    def record_success(self, item: str):
        """记录成功"""
        with self._lock:
            self._processed_items += 1
            self._success_count += 1
            self._current_item = item
    
    def record_error(self, item: str, error: str):
        """记录错误"""
        with self._lock:
            self._processed_items += 1
            self._error_count += 1
            self._current_item = item
            self._errors.append({
                "item": item,
                "error": error
            })
    
    def get_progress(self) -> int:
        """获取进度百分比"""
        with self._lock:
            if self.total_items == 0:
                return 0
            return int((self._processed_items / self.total_items) * 100)
    
    @property
    def processed_items(self) -> int:
        """已处理项数"""
        with self._lock:
            return self._processed_items
    
    @property
    def success_count(self) -> int:
        """成功数"""
        with self._lock:
            return self._success_count
    
    @property
    def error_count(self) -> int:
        """错误数"""
        with self._lock:
            return self._error_count
    
    @property
    def total_items(self) -> int:
        """总项数"""
        return self.total_items
    
    def get_current_item(self) -> str:
        """获取当前处理项"""
        with self._lock:
            return self._current_item
    
    def is_complete(self) -> bool:
        """是否完成"""
        with self._lock:
            return self._processed_items >= self.total_items
```

### 1.3 CancellationToken（取消令牌）

```python
class CancellationToken:
    """
    线程安全的取消令牌
    """
    
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self):
        """取消任务"""
        with self._lock:
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        with self._lock:
            return self._cancelled
    
    def reset(self):
        """重置（用于重新开始）"""
        with self._lock:
            self._cancelled = False
```

### 1.4 SyncStats（统计信息）

```python
@dataclass
class SyncStats:
    """同步统计信息"""
    total_items: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_items": self.total_items,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "success_rate": round(self.success_count / max(self.total_items, 1) * 100, 2),
            "errors": self.errors[:10]  # 只返回前10个错误
        }
```

## 2. 使用示例

### 2.1 财务数据同步

```python
# 在 FinancialDataSyncService 中使用
class FinancialDataSyncService:
    async def sync_financial_data(
        self,
        symbols: List[str],
        data_sources: List[str] = None,
        job_id: str = None
    ):
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        
        results = {}
        
        for data_source in data_sources:
            # 创建线程池服务
            # 注意：财务数据和历史数据同步都需要很长时间（特别是全量同步），超时时间设置为10小时
            thread_pool_service = ThreadPoolSyncService(
                max_workers=10,
                timeout_per_task=36000,  # 10小时（36000秒）
                progress_update_interval=5
            )
            
            # 执行同步
            stats = await thread_pool_service.sync_in_thread_pool(
                items=symbols,
                process_func=self._sync_symbol_financial_data_sync,
                job_id=f"{job_id}_{data_source}" if job_id else f"financial_{data_source}",
                context={
                    "data_source": data_source,
                    "provider": self.providers[data_source],
                    "report_types": ["quarterly", "annual"]
                }
            )
            
            results[data_source] = stats
        
        return results
    
    def _sync_symbol_financial_data_sync(
        self,
        symbol: str,
        data_source: str,
        provider: Any,
        report_types: List[str]
    ) -> bool:
        """
        同步单只股票的财务数据（同步版本，在线程中调用）
        """
        # 创建新的事件循环（在线程中）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._sync_symbol_financial_data_async(
                    symbol, data_source, provider, report_types
                )
            )
        finally:
            loop.close()
    
    async def _sync_symbol_financial_data_async(
        self,
        symbol: str,
        data_source: str,
        provider: Any,
        report_types: List[str]
    ) -> bool:
        """
        同步单只股票的财务数据（异步版本）
        """
        try:
            # 获取财务数据
            financial_data = await provider.get_financial_data(symbol)
            
            if not financial_data:
                return False
            
            # 保存数据
            saved_count = 0
            for report_type in report_types:
                count = await self.financial_service.save_financial_data(
                    symbol=symbol,
                    financial_data=financial_data,
                    data_source=data_source,
                    report_type=report_type
                )
                saved_count += count
            
            return saved_count > 0
            
        except Exception as e:
            logger.error(f"❌ {symbol} 财务数据同步失败 ({data_source}): {e}")
            raise
```

## 3. 集成点

### 3.1 与调度器集成

```python
# 在 scheduler_service.py 中
async def run_financial_data_sync_task(**kwargs):
    """运行财务数据同步任务"""
    job_id = kwargs.get("job_id", "financial_data_sync")
    
    # 获取同步服务
    sync_service = await get_financial_sync_service()
    
    # 执行同步（内部使用线程池）
    results = await sync_service.sync_financial_data(
        symbols=None,  # None表示同步所有股票
        data_sources=["tushare"],
        job_id=job_id
    )
    
    # 标记任务完成
    await mark_job_completed(job_id, stats=results["tushare"].to_dict())
    
    return results
```

### 3.2 任务取消集成

```python
# 在 scheduler_service.py 中
async def cancel_job_execution(execution_id: str) -> bool:
    """取消任务执行"""
    # ... 现有代码 ...
    
    # 如果任务正在使用线程池，取消线程池任务
    if hasattr(sync_service, 'thread_pool_service'):
        sync_service.thread_pool_service.cancel()
    
    return True
```

## 4. 性能优化

### 4.1 线程池大小调优

```python
# 根据CPU核心数和任务类型调整
import os

def get_optimal_worker_count(task_type: str) -> int:
    """获取最优工作线程数"""
    cpu_count = os.cpu_count() or 4
    
    # 不同任务类型的最优线程数
    config = {
        "financial": cpu_count * 2,      # I/O密集型
        "historical": cpu_count,          # 混合型
        "news": cpu_count * 3             # I/O密集型
    }
    
    return config.get(task_type, cpu_count)
```

### 4.2 批量更新优化

```python
# 批量更新进度，减少数据库写入
class BatchProgressUpdater:
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        self.pending_updates = []
        self.lock = threading.Lock()
    
    def add_update(self, progress_data: Dict):
        """添加更新"""
        with self.lock:
            self.pending_updates.append(progress_data)
            if len(self.pending_updates) >= self.batch_size:
                self._flush_updates()
    
    def _flush_updates(self):
        """刷新更新到数据库"""
        updates = self.pending_updates[:]
        self.pending_updates.clear()
        # 批量更新到数据库
```

## 5. 错误处理策略

### 5.1 错误分类

```python
class RetryableError(Exception):
    """可重试的错误"""
    pass

class NonRetryableError(Exception):
    """不可重试的错误"""
    pass

def classify_error(error: Exception) -> type:
    """分类错误"""
    # 网络错误、超时错误 -> 可重试
    if isinstance(error, (TimeoutError, ConnectionError)):
        return RetryableError
    
    # 数据不存在、权限错误 -> 不可重试
    if isinstance(error, (ValueError, PermissionError)):
        return NonRetryableError
    
    # 默认可重试
    return RetryableError
```

### 5.2 重试机制

```python
def process_with_retry(
    func: Callable,
    max_retries: int = 3,
    *args,
    **kwargs
):
    """带重试的处理函数"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RetryableError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                time.sleep(wait_time)
                continue
            else:
                raise
        except NonRetryableError:
            raise
```

## 6. 监控和日志

### 6.1 日志记录

```python
# 记录关键事件
logger.info(f"🚀 开始线程池同步: {job_id}, 总任务数: {total_items}")
logger.info(f"📊 进度更新: {processed_items}/{total_items} ({progress}%)")
logger.info(f"✅ 任务完成: 成功 {success_count}, 失败 {error_count}")
```

### 6.2 性能监控

```python
# 记录处理时间
start_time = time.time()
# ... 处理 ...
duration = time.time() - start_time
logger.info(f"⏱️ 处理耗时: {duration:.2f}秒, 平均: {duration/total_items:.2f}秒/项")
```

## 7. 测试用例

### 7.1 单元测试

```python
def test_thread_pool_service():
    """测试线程池服务"""
    service = ThreadPoolSyncService(max_workers=2)
    
    items = ["A", "B", "C"]
    results = await service.sync_in_thread_pool(
        items=items,
        process_func=mock_process_func,
        job_id="test_job"
    )
    
    assert results.success_count == 3
    assert results.error_count == 0
```

### 7.2 集成测试

```python
def test_financial_sync_integration():
    """测试财务数据同步集成"""
    service = FinancialDataSyncService()
    await service.initialize()
    
    results = await service.sync_financial_data(
        symbols=["000001", "000002"],
        data_sources=["tushare"]
    )
    
    assert "tushare" in results
    assert results["tushare"].success_count >= 0
```
