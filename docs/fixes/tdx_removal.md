# TDX（通达信）数据源移除说明

## 📋 移除原因

TDX（通达信）数据源已从 TradingAgents-CN 项目中完全移除，原因如下：

1. **稳定性问题**：TDX 数据源依赖第三方服务器，连接不稳定
2. **维护成本高**：需要维护服务器列表和连接逻辑
3. **数据质量**：相比 Tushare 和 AKShare，数据质量和完整性较差
4. **功能重复**：已有 Tushare、AKShare、BaoStock 三个稳定的数据源
5. **使用率低**：实际使用中很少使用 TDX 数据源

## 🎯 推荐替代方案

### 数据源优先级（移除 TDX 后）

```
MongoDB（缓存） → Tushare → AKShare → BaoStock
```

### 推荐配置

#### 1. 使用 Tushare（推荐）
```bash
# .env 文件
TUSHARE_TOKEN=your_token_here
DEFAULT_CHINA_DATA_SOURCE=tushare
TUSHARE_ENABLED=true
```

**优势**：
- ✅ 数据质量最高
- ✅ 接口稳定
- ✅ 支持实时行情
- ✅ 支持财务数据
- ✅ 官方支持

**获取 Token**：
- 访问 https://tushare.pro/register?reg=tacn
- 注册并获取免费 Token
- 免费版每分钟 200 次调用

#### 2. 使用 AKShare（备选）
```bash
# .env 文件
DEFAULT_CHINA_DATA_SOURCE=akshare
```

**优势**：
- ✅ 完全免费
- ✅ 无需注册
- ✅ 数据源丰富
- ✅ 社区活跃

**限制**：
- ⚠️ 无官方 API 限流保护
- ⚠️ 部分数据可能不稳定

#### 3. 使用 BaoStock（备选）
```bash
# .env 文件
DEFAULT_CHINA_DATA_SOURCE=baostock
```

**优势**：
- ✅ 完全免费
- ✅ 历史数据完整
- ✅ 接口稳定

**限制**：
- ⚠️ 不支持实时行情
- ⚠️ 数据更新有延迟

## 🔧 代码变更

### 1. 数据源枚举
```python
# tradingagents/dataflows/data_source_manager.py

class ChinaDataSource(Enum):
    """中国股票数据源枚举"""
    MONGODB = "mongodb"
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    # TDX = "tdx"  # 已移除
```

### 2. 数据源检测
```python
# 移除前
def _check_available_sources(self):
    available = []
    # ... 其他数据源检测 ...
    
    # 检查TDX (通达信)
    try:
        import pytdx
        available.append(ChinaDataSource.TDX)
        logger.warning(f"⚠️ TDX数据源可用 (将被淘汰)")
    except ImportError:
        logger.info(f"ℹ️ TDX数据源不可用: 库未安装")
    
    return available

# 移除后
def _check_available_sources(self):
    available = []
    # ... 其他数据源检测 ...
    
    # TDX (通达信) 已移除
    # 不再检查和支持 TDX 数据源
    
    return available
```

### 3. 适配器获取
```python
# 移除前
def _get_adapter(self):
    if self.current_source == ChinaDataSource.TUSHARE:
        return self._get_tushare_adapter()
    # ... 其他数据源 ...
    elif self.current_source == ChinaDataSource.TDX:
        return self._get_tdx_adapter()
    else:
        raise ValueError(f"不支持的数据源: {self.current_source}")

# 移除后
def _get_adapter(self):
    if self.current_source == ChinaDataSource.TUSHARE:
        return self._get_tushare_adapter()
    # ... 其他数据源 ...
    # TDX 已移除
    else:
        raise ValueError(f"不支持的数据源: {self.current_source}")
```

### 4. 备用数据源
```python
# 移除前
fallback_order = [
    ChinaDataSource.AKSHARE,
    ChinaDataSource.TUSHARE,
    ChinaDataSource.BAOSTOCK,
    ChinaDataSource.TDX  # ❌ 已移除
]

# 移除后
fallback_order = [
    ChinaDataSource.AKSHARE,
    ChinaDataSource.TUSHARE,
    ChinaDataSource.BAOSTOCK,
]
```

### 5. 配置文件
```python
# tradingagents/config/providers_config.py

# 移除前
self._configs["tdx"] = {
    "enabled": self._get_bool_env("TDX_ENABLED", False),
    "timeout": self._get_int_env("TDX_TIMEOUT", 30),
    # ...
}

# 移除后
# 通达信配置 - 已移除
# TDX 数据源已不再支持
```

## 📝 迁移指南

### 如果您之前使用 TDX

#### 1. 检查环境变量
```bash
# 检查是否设置了 TDX 相关配置
grep -i "tdx" .env

# 如果有，请删除或注释掉
# TDX_ENABLED=true  # ❌ 删除此行
```

#### 2. 更新默认数据源
```bash
# .env 文件
# 旧配置
# DEFAULT_CHINA_DATA_SOURCE=tdx  # ❌ 不再支持

# 新配置（推荐）
DEFAULT_CHINA_DATA_SOURCE=tushare  # ✅ 推荐
TUSHARE_TOKEN=your_token_here

# 或使用免费的 AKShare
# DEFAULT_CHINA_DATA_SOURCE=akshare  # ✅ 免费
```

#### 3. 卸载 pytdx 依赖（可选）
```bash
pip uninstall pytdx
```

#### 4. 测试新数据源
```python
from tradingagents.dataflows import get_china_stock_data_unified

# 测试获取数据
data = get_china_stock_data_unified("000001", "2024-01-01", "2024-12-31")
print(data)
```

## 🔍 影响范围

### 受影响的文件
1. ✅ `tradingagents/dataflows/data_source_manager.py` - 移除 TDX 枚举和相关方法
2. ✅ `tradingagents/config/providers_config.py` - 移除 TDX 配置
3. ⚠️ `tradingagents/dataflows/providers/china/tdx.py` - 保留但标记为已弃用

### 不受影响的功能
- ✅ 所有使用统一接口的代码（`get_china_stock_data_unified`）
- ✅ Tushare、AKShare、BaoStock 数据源
- ✅ MongoDB 缓存功能
- ✅ 数据源自动降级功能

## ⚠️ 注意事项

### 1. TDX 文件保留
`tradingagents/dataflows/providers/china/tdx.py` 文件暂时保留，但已标记为已弃用：
- 不会被主动调用
- 仅用于向后兼容
- 将在未来版本中完全删除

### 2. 环境变量清理
如果您的 `.env` 文件中有以下配置，请删除或注释：
```bash
# ❌ 以下配置已无效
TDX_ENABLED=true
TDX_TIMEOUT=30
TDX_RATE_LIMIT=0.1
TDX_MAX_RETRIES=3
TDX_CACHE_ENABLED=true
TDX_CACHE_TTL=300
```

### 3. 代码中的直接引用
如果您的代码中直接引用了 TDX：
```python
# ❌ 不再支持
from tradingagents.dataflows.providers.china.tdx import get_tdx_provider
provider = get_tdx_provider()

# ✅ 使用统一接口
from tradingagents.dataflows import get_china_stock_data_unified
data = get_china_stock_data_unified(symbol, start_date, end_date)
```

## 📊 数据源对比

| 特性 | Tushare | AKShare | BaoStock | ~~TDX~~ |
|------|---------|---------|----------|---------|
| **稳定性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~~⭐⭐~~ |
| **数据质量** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~~⭐⭐⭐~~ |
| **实时行情** | ✅ | ✅ | ❌ | ~~✅~~ |
| **历史数据** | ✅ | ✅ | ✅ | ~~✅~~ |
| **财务数据** | ✅ | ✅ | ✅ | ~~❌~~ |
| **免费使用** | 部分 | ✅ | ✅ | ~~✅~~ |
| **需要注册** | ✅ | ❌ | ❌ | ~~❌~~ |
| **API限流** | ✅ | ❌ | ✅ | ~~❌~~ |
| **官方支持** | ✅ | ✅ | ✅ | ~~❌~~ |
| **状态** | ✅ 推荐 | ✅ 可用 | ✅ 可用 | ~~❌ 已移除~~ |

## 🎯 总结

### 移除的内容
- ❌ `ChinaDataSource.TDX` 枚举值
- ❌ `_get_tdx_adapter()` 方法
- ❌ `_get_tdx_data()` 方法
- ❌ TDX 数据源检测逻辑
- ❌ TDX 配置项
- ❌ 备用数据源列表中的 TDX

### 保留的内容
- ✅ `tradingagents/dataflows/providers/china/tdx.py` 文件（标记为已弃用）
- ✅ 所有其他数据源（Tushare、AKShare、BaoStock）
- ✅ 统一数据接口
- ✅ 数据源自动降级功能

### 推荐操作
1. ✅ 使用 Tushare 作为主数据源（需注册）
2. ✅ 使用 AKShare 作为免费备选
3. ✅ 启用 MongoDB 缓存提高性能
4. ✅ 清理 .env 文件中的 TDX 配置

## 📅 更新日期

2025-01-XX

## 👥 相关人员

- 开发者：AI Assistant
- 审核者：待定

