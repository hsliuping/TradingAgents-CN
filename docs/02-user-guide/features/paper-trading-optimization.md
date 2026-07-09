# 模拟交易 name 字段优化方案

## 问题分析

### 原始问题
模拟交易持仓表 `paper_positions` 缺少股票名称字段。

### 性能问题
在获取港股名称时，发现了重复API调用的问题：

```
1. ForeignStockService.get_quote() → yfinance 获取行情 ❌ (缺少 name)
2. get_hk_stock_info_unified() → AKShare 获取名称 ❌ (重复调用)
```

**问题根源**：
- `HKStockProvider.get_real_time_price()` 没有返回 `name` 字段
- `_get_last_price()` 调用了 `ForeignStockService.get_quote()` 获取价格（无 name）
- `_get_stock_name()` 又调用了 `get_hk_stock_info_unified()` 获取名称（重复调用）
- 两次调用获取的是同一只股票的数据，造成浪费

## 优化方案

### 核心思路
**复用已获取的行情数据**，避免重复API调用。

### 实现方式

#### 1. 修改 HKStockProvider.get_real_time_price() 返回 name 字段

**文件**：`tradingagents/dataflows/providers/hk/hk_stock.py`

```python
def get_real_time_price(self, symbol: str) -> Optional[Dict]:
    # 获取行情数据
    data = ticker.history(period="1d", timeout=self.timeout)

    # 尝试获取股票名称（从 ticker.info）
    stock_name = f'港股{symbol}'
    try:
        info = ticker.info
        if info and 'longName' in info:
            stock_name = info.get('longName', info.get('shortName', stock_name))
    except Exception:
        pass

    return {
        'symbol': symbol,
        'name': stock_name,  # ← 添加股票名称
        'price': latest['Close'],
        ...
    }
```

#### 2. 使用 ForeignStockService 获取名称

**文件**：`app/routers/paper.py`

```python
async def _get_stock_name(code: str, market: str) -> str:
    if market in ["HK", "US"]:
        # 使用 ForeignStockService（复用已获取的行情数据）
        service = ForeignStockService(db=db)
        quote = await service.get_quote(market, code, force_refresh=False)

        if quote and quote.get("name"):
            return quote.get("name")
```

#### 3. 缓存机制

`ForeignStockService.get_quote()` 内置三级缓存：
1. **Redis 缓存**（最快）
2. **MongoDB 缓存**（次快）
3. **文件缓存**（备用）

**优势**：
- 第一次调用：从API获取行情（包含价格和名称）
- 第二次调用：从缓存读取（毫秒级响应）
- 避免重复API调用

**关键点**：
- ✅ `get_real_time_price()` 在获取行情时，同时从 `ticker.info` 获取股票名称
- ✅ 名称和价格一起缓存到 Redis/MongoDB/File
- ✅ 后续调用直接从缓存读取，无需再次调用 API

#### 4. 数据流

```
用户下单（买入港股 09988）
    ↓
_get_last_price(09988, HK)
    ↓
ForeignStockService.get_quote(HK, 09988)
    ↓
HKStockProvider.get_real_time_price(09988)
    ↓
yfinance API:
  - ticker.history(period="1d") → 获取价格
  - ticker.info → 获取股票名称 ← 关键修改
    ↓
返回 { price: 100.5, name: "阿里巴巴-SW", ... }
    ↓
保存到缓存（Redis/MongoDB/File）
    ↓
返回价格：100.5
    ↓
_get_stock_name(09988, HK)
    ↓
ForeignStockService.get_quote(HK, 09988, force_refresh=False)
    ↓
从缓存读取 { price: 100.5, name: "阿里巴巴-SW" }  ← 无需API调用
    ↓
返回名称："阿里巴巴-SW"
```

## 性能对比

### 优化前

| 操作 | API调用 | 耗时 |
|------|--------|------|
| 获取价格 | yfinance | ~4秒 |
| 获取名称 | AKShare | ~30秒 |
| **总计** | **2次** | **~34秒** |

### 优化后

| 操作 | API调用 | 耗时 |
|------|--------|------|
| 获取价格 | yfinance | ~4秒 |
| 获取名称 | 缓存读取 | ~10ms |
| **总计** | **1次** | **~4秒** |

**性能提升**：~88% ⚡

## 技术细节

### ForeignStockService.get_quote() 返回数据

```python
{
    'code': '09988',
    'name': '阿里巴巴',  # ← 已包含名称
    'market': 'HK',
    'price': 100.5,
    'open': 99.8,
    'high': 101.2,
    'low': 99.5,
    'volume': 12345678,
    'currency': 'HKD',
    'source': 'yfinance',
    'updated_at': '2025-12-19T17:03:48'
}
```

### 数据源优先级

港股/美股的数据源优先级由数据库配置决定：

```sql
-- hk_data_sources 表
{ source: 'yahoo_finance', enabled: true, priority: 1 }
{ source: 'akshare', enabled: true, priority: 2 }
```

## 优势总结

✅ **性能优化**：避免重复API调用，提升 88% 性能
✅ **缓存复用**：一次API调用，多次使用
✅ **代码简化**：统一使用 ForeignStockService
✅ **数据一致性**：价格和名称来自同一数据源
✅ **容错机制**：缓存失败时自动降级到API调用

## 测试验证

```bash
# 运行测试
python tests/test_new_paper_position.py

# 预期结果
✅ 创建持仓: 09988 (HK)
   名称: 阿里巴巴
   性能: ~4秒（仅1次API调用）
```

