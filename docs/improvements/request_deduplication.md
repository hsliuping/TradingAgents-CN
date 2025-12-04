# 请求去重机制 (Request Deduplication)

## 问题背景

### 原始问题
前端在短时间内发起了大量重复的 `quote` 请求（例如：同一个股票代码的多个并发请求），导致：

1. **多个并发请求同时调用 AKShare API**
2. **触发 AKShare 的限速保护**（Too Many Requests）
3. **所有请求都失败**

### 问题原因
- 前端可能因为组件重复渲染、状态更新等原因，短时间内发起多个相同的请求
- 后端没有请求去重机制，每个请求都会独立调用数据源API
- 即使有缓存，但在第一个请求完成之前，其他并发请求也会绕过缓存（因为缓存还没有数据）

## 解决方案

### 核心思路
使用 **asyncio.Lock** 实现请求去重，确保：
1. 对于同一个股票代码，同一时间只有一个实际的 API 调用
2. 其他并发请求等待第一个请求完成，然后共享结果
3. 不同股票的请求不会互相阻塞

### 实现细节

#### 1. 添加锁管理器
```python
from collections import defaultdict
import asyncio

class ForeignStockService:
    def __init__(self, db=None):
        # 🔥 请求去重：为每个 (market, code, data_type) 创建独立的锁
        self._request_locks = defaultdict(asyncio.Lock)
```

#### 2. 修改数据获取方法
```python
async def _get_hk_quote(self, code: str, force_refresh: bool = False) -> Dict:
    # 1. 第一次检查缓存
    if not force_refresh:
        cached_data = self._check_cache(code)
        if cached_data:
            return cached_data
    
    # 2. 🔥 获取锁（每个股票代码有独立的锁）
    request_key = f"HK_quote_{code}"
    lock = self._request_locks[request_key]
    
    async with lock:
        # 3. 🔥 再次检查缓存（可能在等待锁的过程中，其他请求已经完成并缓存了数据）
        if not force_refresh:
            cached_data = self._check_cache(code)
            if cached_data:
                logger.info(f"⚡ [去重后] 从缓存获取: {code}")
                return cached_data
        
        # 4. 调用API获取数据
        data = await self._fetch_from_api(code)
        
        # 5. 保存到缓存
        self._save_to_cache(code, data)
        
        return data
```

### 工作流程

#### 场景1：10个并发请求同一个股票
```
时间线：
T0: 请求1-10 同时到达
T1: 请求1 获得锁，开始调用API
    请求2-10 等待锁
T2: 请求1 完成API调用，保存到缓存，释放锁
T3: 请求2 获得锁，检查缓存，命中！直接返回
    请求3-10 继续等待
T4: 请求3 获得锁，检查缓存，命中！直接返回
    ...
T5: 所有请求完成

结果：只有1次API调用，其他9个请求从缓存获取
```

#### 场景2：3个不同股票，每个5个并发请求
```
时间线：
T0: 15个请求同时到达（00700×5, 00941×5, 01810×5）
T1: 每个股票的第1个请求获得各自的锁，开始调用API
    其他请求等待各自股票的锁
T2: 3个API调用并行执行（不互相阻塞）
T3: 3个请求完成，保存到缓存，释放锁
T4: 其他12个请求从缓存获取数据

结果：只有3次API调用（每个股票1次），其他12个请求从缓存获取
```

## 优势

### 1. 防止API限速
- 避免短时间内对同一股票的重复API调用
- 降低触发限速保护的风险

### 2. 提高性能
- 减少不必要的API调用
- 降低服务器负载
- 减少网络延迟

### 3. 不影响并发性
- 不同股票的请求可以并行处理
- 只对相同股票的请求进行去重

### 4. 自动清理
- 使用 `defaultdict(asyncio.Lock)` 自动管理锁
- 不需要手动清理锁对象

## 测试

### 测试用例
```python
# 测试1：10个并发请求同一个港股
async def test_concurrent_hk_quote_requests():
    service = ForeignStockService()
    code = '00700'
    tasks = [service._get_hk_quote(code) for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    # 验证：只有1次API调用
    assert api_call_count == 1
    assert len(results) == 10

# 测试2：不同股票不互相阻塞
async def test_different_stocks_no_blocking():
    service = ForeignStockService()
    codes = ['00700', '00941', '01810']
    tasks = []
    for code in codes:
        tasks.extend([service._get_hk_quote(code) for _ in range(5)])
    
    results = await asyncio.gather(*tasks)
    
    # 验证：每个股票只调用1次API
    assert api_call_count['00700'] == 1
    assert api_call_count['00941'] == 1
    assert api_call_count['01810'] == 1
```

### 运行测试
```bash
# 运行请求去重测试
pytest tests/test_request_deduplication.py -v

# 运行所有测试
pytest tests/ -v
```

## 性能对比

### 改进前
```
场景：10个并发请求同一个股票
- API调用次数：10次
- 总耗时：~10秒（假设每次API调用1秒）
- 失败率：高（容易触发限速）
```

### 改进后
```
场景：10个并发请求同一个股票
- API调用次数：1次
- 总耗时：~1秒（只有第一个请求调用API）
- 失败率：低（避免触发限速）
```

## 适用范围

此机制已应用于以下方法：
- ✅ `_get_hk_quote()` - 港股实时行情
- ✅ `_get_us_quote()` - 美股实时行情
- 🔄 可扩展到其他数据获取方法（K线、基本面等）

## 注意事项

### 1. 锁的粒度
- 当前实现：每个 `(market, code, data_type)` 一个锁
- 优点：精确控制，不同股票不互相影响
- 缺点：如果股票数量非常多，会创建很多锁对象

### 2. 内存管理
- `defaultdict(asyncio.Lock)` 会自动创建锁
- 锁对象在不再使用时会被垃圾回收
- 如果需要，可以添加定期清理机制

### 3. 强制刷新
- `force_refresh=True` 时仍然会使用锁
- 确保即使强制刷新，也不会有多个并发API调用

## 未来改进

### 1. 请求合并（Request Coalescing）
- 当前：后续请求等待第一个请求完成，然后从缓存获取
- 改进：后续请求直接等待第一个请求的结果，无需访问缓存

### 2. 智能限速
- 添加全局限速器，控制所有API调用的频率
- 例如：每秒最多10次API调用

### 3. 监控和统计
- 记录去重命中率
- 统计节省的API调用次数
- 监控锁等待时间

## 相关文件

- `app/services/foreign_stock_service.py` - 主要实现
- `tests/test_request_deduplication.py` - 测试用例
- `docs/improvements/request_deduplication.md` - 本文档

