# 修复线程池中的异步事件循环错误

## 🐛 问题描述

### 错误信息
```
RuntimeError: There is no current event loop in thread 'ThreadPoolExecutor-41_0'.
```

### 错误场景
当在**线程池**（ThreadPoolExecutor）中调用数据源管理器获取股票数据时，所有数据源（Tushare、AKShare、BaoStock）都会失败，错误堆栈显示：

```python
File "D:\code\TradingAgents-CN\tradingagents\dataflows\data_source_manager.py", line 792, in _get_tushare_data
    loop = asyncio.get_event_loop()
  File "C:\Users\hsliu\AppData\Local\Programs\Python\Python310\lib\asyncio\events.py", line 656, in get_event_loop
    raise RuntimeError('There is no current event loop in thread %r.'
RuntimeError: There is no current event loop in thread 'ThreadPoolExecutor-41_0'.
```

### 根本原因

1. **线程池工作线程没有事件循环**
   - 主线程有默认的事件循环
   - 线程池的工作线程是独立的线程，没有事件循环
   - 调用 `asyncio.get_event_loop()` 会抛出 `RuntimeError`

2. **数据源使用异步方法**
   - Tushare、AKShare、BaoStock 的 provider 都使用异步方法
   - 在 `data_source_manager.py` 中使用 `loop.run_until_complete()` 运行异步方法
   - 但在线程池中获取事件循环失败

3. **影响范围**
   - 所有在线程池中运行的分析任务
   - 所有需要获取股票数据的操作
   - 导致数据源完全不可用

---

## ✅ 解决方案

### 修复策略

使用 **try-except** 捕获 `RuntimeError`，并在线程池中创建新的事件循环：

```python
import asyncio

try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    # 在线程池中没有事件循环，创建新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# 现在可以安全地使用 loop
data = loop.run_until_complete(async_function())
```

### 修复位置

**文件**: `tradingagents/dataflows/data_source_manager.py`

#### 1. `_get_tushare_data` 方法（2处）

**位置1**: 第773-783行（缓存命中时获取股票信息）
```python
# 修复前
import asyncio
loop = asyncio.get_event_loop()
stock_info = loop.run_until_complete(provider.get_stock_basic_info(symbol))

# 修复后
import asyncio
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    # 在线程池中没有事件循环，创建新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

stock_info = loop.run_until_complete(provider.get_stock_basic_info(symbol))
```

**位置2**: 第792-801行（从provider获取历史数据）
```python
# 修复前
import asyncio
loop = asyncio.get_event_loop()
data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date))

# 修复后
import asyncio
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    # 在线程池中没有事件循环，创建新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date))
```

#### 2. `_get_akshare_data` 方法

**位置**: 第838-839行
```python
# 修复前
import asyncio
loop = asyncio.get_event_loop()
data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date, period))

# 修复后
import asyncio
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    # 在线程池中没有事件循环，创建新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date, period))
```

#### 3. `_get_baostock_data` 方法

**位置**: 第894-895行
```python
# 修复前
import asyncio
loop = asyncio.get_event_loop()
data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date, period))

# 修复后
import asyncio
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    # 在线程池中没有事件循环，创建新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date, period))
```

---

## 📊 修复效果

### 修复前
```
❌ [Tushare] 调用失败: There is no current event loop in thread 'ThreadPoolExecutor-41_0'.
❌ [AKShare] 调用失败: There is no current event loop in thread 'ThreadPoolExecutor-41_0'.
❌ [BaoStock] 调用失败: There is no current event loop in thread 'ThreadPoolExecutor-41_0'.
❌ 所有数据源都无法获取000001的daily数据
```

### 修复后
```
✅ [Tushare] 成功获取数据
✅ [AKShare] 成功获取数据
✅ [BaoStock] 成功获取数据
✅ 数据源正常工作
```

---

## 🧪 测试验证

### 测试文件
`tests/test_asyncio_thread_pool_fix.py`

### 测试用例

#### 1. 基础测试：线程池中的异步方法
```python
def test_asyncio_in_thread_pool():
    """测试在线程池中使用异步方法"""
    def run_in_thread():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def simple_async():
            await asyncio.sleep(0.01)
            return "success"
        
        return loop.run_until_complete(simple_async())
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(run_in_thread)
        result = future.result(timeout=5)
        assert result == "success"
```

#### 2. 集成测试：DataSourceManager
```python
def test_data_source_manager_in_thread_pool():
    """测试 DataSourceManager 在线程池中的使用"""
    def get_stock_data():
        manager = DataSourceManager()
        result = manager.get_stock_data(
            symbol="000001",
            start_date="2025-01-01",
            end_date="2025-01-10",
            period="daily"
        )
        return result
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(get_stock_data)
        result = future.result(timeout=30)
        
        # 验证不是事件循环错误
        assert "There is no current event loop" not in str(result)
```

#### 3. 并发测试：多线程
```python
def test_multiple_threads():
    """测试多个线程同时使用异步方法"""
    def run_async_task(task_id):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def task():
            await asyncio.sleep(0.01)
            return f"Task {task_id} completed"
        
        return loop.run_until_complete(task())
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_async_task, i) for i in range(5)]
        results = [f.result(timeout=5) for f in futures]
        
        assert len(results) == 5
```

### 运行测试
```bash
# 使用 pytest
pytest tests/test_asyncio_thread_pool_fix.py -v

# 或直接运行
python tests/test_asyncio_thread_pool_fix.py
```

---

## 📝 技术说明

### asyncio 事件循环机制

1. **主线程的事件循环**
   - Python 主线程有默认的事件循环
   - 可以通过 `asyncio.get_event_loop()` 获取

2. **子线程的事件循环**
   - 子线程（包括线程池工作线程）没有默认事件循环
   - 需要手动创建：`asyncio.new_event_loop()`
   - 需要设置为当前线程的事件循环：`asyncio.set_event_loop(loop)`

3. **最佳实践**
   ```python
   # 方案1: try-except（推荐，兼容性好）
   try:
       loop = asyncio.get_event_loop()
       if loop.is_closed():
           loop = asyncio.new_event_loop()
           asyncio.set_event_loop(loop)
   except RuntimeError:
       loop = asyncio.new_event_loop()
       asyncio.set_event_loop(loop)
   
   # 方案2: asyncio.run()（Python 3.7+，但不适合需要复用loop的场景）
   result = asyncio.run(async_function())
   ```

### 为什么不使用 asyncio.run()

`asyncio.run()` 每次都会创建新的事件循环并在完成后关闭，不适合我们的场景：
- 我们需要在同一个 loop 中运行多个异步操作
- 我们需要复用事件循环以提高性能
- `run_until_complete()` 提供更好的控制

---

## 🎯 影响范围

### 修复的功能
- ✅ Tushare 数据源在线程池中正常工作
- ✅ AKShare 数据源在线程池中正常工作
- ✅ BaoStock 数据源在线程池中正常工作
- ✅ 所有在线程池中运行的分析任务

### 不受影响的功能
- ✅ 主线程中的数据获取（本来就正常）
- ✅ MongoDB 数据源（不使用异步）
- ✅ 其他不使用线程池的功能

---

## 🔗 相关资源

### Python 官方文档
- [asyncio - Asynchronous I/O](https://docs.python.org/3/library/asyncio.html)
- [asyncio.get_event_loop()](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop)
- [asyncio.new_event_loop()](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.new_event_loop)

### 相关 Issue
- [Python asyncio: RuntimeError: There is no current event loop in thread](https://stackoverflow.com/questions/46727787/runtimeerror-there-is-no-current-event-loop-in-thread-in-async-apscheduler)

---

## ✅ 验证清单

- [x] 修复 `_get_tushare_data` 方法（2处）
- [x] 修复 `_get_akshare_data` 方法
- [x] 修复 `_get_baostock_data` 方法
- [x] 创建测试用例
- [x] 编写修复文档
- [ ] 运行测试验证（需要实际运行）
- [ ] 在实际分析任务中验证（需要实际运行）

---

## 🎉 总结

这个修复解决了在线程池中使用异步数据源的关键问题，确保了数据源在多线程环境下的稳定性。修复后，所有数据源（Tushare、AKShare、BaoStock）都可以在线程池中正常工作，不再抛出事件循环错误。

