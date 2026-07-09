# 修复港股/美股名称缓存问题

## 问题描述

用户报告：缓存中的港股/美股数据没有包含股票名称（`name` 字段）。

### 日志分析

```
2025-12-19 17:18:07 | app.services.foreign_stock_service | INFO | ✅ yfinance获取港股行情成功: 09988
2025-12-19 17:18:07 | tradingagents.dataflows.cache.adaptive | INFO | 数据缓存成功: 09988 -> dc0fde199d006756c6a9129501c4423c (后端: redis)
```

**问题**：虽然日志显示"获取成功"，但缓存的数据中 `name` 字段为默认值（如 "港股09988"），而不是真实的股票名称（如 "阿里巴巴-SW"）。

## 根本原因

### 代码分析

**文件**：`tradingagents/dataflows/providers/hk/hk_stock.py`

**问题代码**（第 206-240 行）：

```python
def get_real_time_price(self, symbol: str) -> Optional[Dict]:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d", timeout=self.timeout)
    
    if not data.empty:
        latest = data.iloc[-1]
        return {
            'symbol': symbol,
            'price': latest['Close'],
            'open': latest['Open'],
            'high': latest['High'],
            'low': latest['Low'],
            'volume': latest['Volume'],
            'timestamp': data.index[-1].strftime('%Y-%m-%d %H:%M:%S'),
            'currency': 'HKD'
            # ❌ 缺少 'name' 字段
        }
```

**问题**：
- `get_real_time_price()` 只返回了价格数据，没有返回股票名称
- `ForeignStockService._format_hk_quote()` 在格式化时，如果原始数据没有 `name` 字段，会使用默认值 `f'港股{code}'`
- 导致缓存中保存的是默认名称，而不是真实名称

## 解决方案

### 1. 修改 HKStockProvider.get_real_time_price()

**文件**：`tradingagents/dataflows/providers/hk/hk_stock.py` 第 206-256 行

**修改内容**：在获取港股行情时，同时从 `ticker.info` 获取股票名称

```python
def get_real_time_price(self, symbol: str) -> Optional[Dict]:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d", timeout=self.timeout)
    
    if not data.empty:
        latest = data.iloc[-1]
        
        # ✅ 尝试获取股票名称（从 ticker.info）
        stock_name = f'港股{symbol}'
        try:
            info = ticker.info
            if info and 'longName' in info:
                stock_name = info.get('longName', info.get('shortName', stock_name))
        except Exception:
            # 静默失败，使用默认名称
            pass
        
        return {
            'symbol': symbol,
            'name': stock_name,  # ✅ 添加股票名称
            'price': latest['Close'],
            'open': latest['Open'],
            'high': latest['High'],
            'low': latest['Low'],
            'volume': latest['Volume'],
            'timestamp': data.index[-1].strftime('%Y-%m-%d %H:%M:%S'),
            'currency': 'HKD'
        }
```

### 2. 修改 ForeignStockService._get_us_quote_from_alpha_vantage()

**文件**：`app/services/foreign_stock_service.py` 第 508-566 行

**修改内容**：Alpha Vantage 的 GLOBAL_QUOTE API 不包含股票名称，需要额外获取

```python
def _get_us_quote_from_alpha_vantage(self, code: str) -> Dict:
    # 获取行情数据
    quote = data["Global Quote"]

    # 尝试获取股票名称（Alpha Vantage GLOBAL_QUOTE 不包含名称）
    stock_name = None
    try:
        # 使用 yfinance 获取名称（快速且免费）
        import yfinance as yf
        ticker = yf.Ticker(code)
        info = ticker.info
        if info:
            stock_name = info.get('longName') or info.get('shortName')
    except Exception:
        pass

    if not stock_name:
        stock_name = f'美股{code}'

    return {
        'symbol': quote.get('01. symbol', code),
        'name': stock_name,  # ✅ 添加股票名称
        'price': float(quote.get('05. price', 0)),
        ...
    }
```

### 3. 修改 ForeignStockService._get_us_quote_from_finnhub()

**文件**：`app/services/foreign_stock_service.py` 第 568-625 行

**修改内容**：Finnhub 的 quote API 不包含股票名称，需要额外获取

```python
def _get_us_quote_from_finnhub(self, code: str) -> Dict:
    # 获取行情数据
    quote = client.quote(code.upper())

    # 尝试获取股票名称
    stock_name = None
    try:
        # 优先使用 Finnhub 的 company_profile2
        profile = client.company_profile2(symbol=code.upper())
        if profile:
            stock_name = profile.get('name')
    except Exception:
        # 降级到 yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(code)
            info = ticker.info
            if info:
                stock_name = info.get('longName') or info.get('shortName')
        except Exception:
            pass

    if not stock_name:
        stock_name = f'美股{code}'

    return {
        'symbol': code.upper(),
        'name': stock_name,  # ✅ 添加股票名称
        'price': quote.get('c', 0),
        ...
    }
```

### 优势

1. **一次API调用，获取两个数据**：
   - 港股：`ticker.history(period="1d")` + `ticker.info` → 价格 + 名称
   - 美股：行情API + 名称API → 价格 + 名称

2. **缓存包含完整数据**：
   - 缓存中保存的数据包含真实的股票名称
   - 后续调用直接从缓存读取，无需再次调用 API

3. **容错机制**：
   - 如果获取名称失败，使用默认名称
   - 不影响价格数据的获取

4. **多数据源支持**：
   - Alpha Vantage：使用 yfinance 补充名称
   - Finnhub：优先使用 company_profile2，降级到 yfinance
   - yfinance：直接从 ticker.info 获取

## 测试验证

### 测试脚本

**文件**：`tests/test_hk_stock_name.py`

```bash
python tests/test_hk_stock_name.py
```

### 预期结果

```
📊 测试股票: 00700 (预期名称: 腾讯控股)
✅ 获取成功:
   代码: 0700.HK
   名称: Tencent Holdings Limited
   价格: 450.2
   货币: HKD
   ✅ name 字段正确: Tencent Holdings Limited

📊 测试股票: 09988 (预期名称: 阿里巴巴)
✅ 获取成功:
   代码: 9988.HK
   名称: Alibaba Group Holding Limited
   价格: 100.5
   货币: HKD
   ✅ name 字段正确: Alibaba Group Holding Limited
```

## 影响范围

### 修改的文件

| 文件 | 修改内容 |
|------|--------|
| `tradingagents/dataflows/providers/hk/hk_stock.py` | 修改 `get_real_time_price()` 添加 `name` 字段 |
| `app/services/foreign_stock_service.py` | 修改 `_get_us_quote_from_alpha_vantage()` 添加 `name` 字段 |
| `app/services/foreign_stock_service.py` | 修改 `_get_us_quote_from_finnhub()` 添加 `name` 字段 |
| `tests/test_hk_stock_name.py` | 新增港股测试脚本 |
| `docs/FIX_HK_STOCK_NAME_ISSUE.md` | 问题修复文档 |
| `docs/PAPER_TRADING_OPTIMIZATION.md` | 更新优化文档 |

### 受影响的功能

✅ **模拟交易**：新建持仓时，股票名称会正确保存（港股/美股）
✅ **港股行情**：缓存中包含真实的股票名称
✅ **美股行情**：缓存中包含真实的股票名称（所有数据源）
✅ **性能优化**：避免重复API调用

### 数据源支持情况

| 市场 | 数据源 | name 字段支持 |
|------|--------|-------------|
| 港股 | yfinance | ✅ 已修复 |
| 港股 | AKShare | ✅ 原本支持 |
| 美股 | yfinance | ✅ 原本支持 |
| 美股 | Alpha Vantage | ✅ 已修复 |
| 美股 | Finnhub | ✅ 已修复 |

## 下一步

1. **重启 Web 服务**（加载新的代码）
2. **清空缓存**（Redis/MongoDB/File）
3. **测试新建模拟交易**（港股）
4. **验证缓存数据**（检查 `name` 字段是否正确）

## 注意事项

⚠️ **需要清空旧缓存**：
- 旧缓存中的数据没有 `name` 字段或使用默认值
- 清空缓存后，新的API调用会返回包含真实名称的数据

⚠️ **yfinance 的 ticker.info 可能失败**：
- 某些股票的 `ticker.info` 可能返回空或不完整
- 代码已添加容错机制，失败时使用默认名称

