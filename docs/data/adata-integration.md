# AData数据源集成指南

AData是一个新兴的中国股票数据源，提供了丰富的实时和历史数据。本指南介绍如何在TradingAgents中集成和使用AData数据源。

## 功能概述

- **实时数据**: 提供股票实时行情数据
- **历史数据**: 提供股票历史K线数据
- **股票信息**: 提供股票基本信息、行业分类等
- **多市场支持**: 支持上交所、深交所、北交所股票
- **数据标准化**: 统一的数据格式，与其他数据源兼容

## 安装

### 安装AData库

```bash
pip install adata
```

### 验证安装

```python
import adata
print("AData版本:", adata.__version__)
```

## 配置

### 1. 设置数据源

在配置文件中设置默认数据源为AData：

```python
config = {
    "china_data_source": "adata",
    # 其他配置...
}
```

### 2. 环境变量配置

也可以通过环境变量设置：

```bash
export DEFAULT_CHINA_DATA_SOURCE=adata
```

### 3. 运行时切换

```python
from tradingagents.dataflows.data_source_manager import (
    DataSourceManager, 
    ChinaDataSource,
    get_data_source_manager
)

# 获取管理器实例
manager = get_data_source_manager()

# 切换到AData数据源
manager.set_current_source(ChinaDataSource.ADATA)
```

## 使用方法

### 基本用法

#### 使用统一接口

```python
from tradingagents.dataflows.data_source_manager import get_china_stock_data_unified

# 获取股票数据
data_str = get_china_stock_data_unified(
    symbol="000001",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
print(data_str)
```

#### 使用AData专用接口

```python
from tradingagents.dataflows.adata_utils import get_china_stock_data_adata

# 获取股票数据
data_str = get_china_stock_data_adata(
    symbol="000001",
    start_date="2024-01-01",
    end_date="2024-12-31"
)
print(data_str)
```

### 获取股票信息

```python
from tradingagents.dataflows.adata_utils import get_china_stock_info_adata

# 获取股票基本信息
info_str = get_china_stock_info_adata("000001")
print(info_str)
```

### 高级用法

#### 使用AData提供者

```python
from tradingagents.dataflows.adata_utils import get_adata_provider

# 获取AData提供者实例
provider = get_adata_provider()

# 检查可用性
if provider.check_availability():
    # 获取股票数据
    df = provider.get_stock_data("000001", "2024-01-01", "2024-12-31")
    
    # 获取股票信息
    info = provider.get_stock_info("000001")
    
    # 获取实时数据
    realtime = provider.get_realtime_data("000001")
```

## 支持的交易所和股票代码

### 上海证券交易所
- 主板: 600, 601, 603, 605
- 科创板: 688

### 深圳证券交易所
- 主板: 000, 001
- 中小板: 002, 003
- 创业板: 300, 301

### 北京证券交易所
- 400, 430, 830, 831

## 数据格式

### 历史数据字段

| 字段名 | 说明 | 类型 |
|--------|------|------|
| date | 交易日期 | datetime |
| open | 开盘价 | float |
| high | 最高价 | float |
| low | 最低价 | float |
| close | 收盘价 | float |
| vol | 成交量 | int |
| amount | 成交额 | float |
| change_pct | 涨跌幅 | float |

### 股票信息字段

| 字段名 | 说明 |
|--------|------|
| symbol | 股票代码 |
| name | 股票名称 |
| industry | 所属行业 |
| area | 所属地区 |
| list_date | 上市日期 |
| market | 上市市场 |
| source | 数据来源 |

## 示例代码

### 完整的分析流程

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 配置AData数据源
config = DEFAULT_CONFIG.copy()
config["china_data_source"] = "adata"
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "qwen-plus"

# 创建分析器
ta = TradingAgentsGraph(debug=True, config=config)

# 分析股票
state, decision = ta.propagate("000001", "2024-12-31")
print(f"建议: {decision['action']}, 信心: {decision['confidence']}")
```

### 批量分析

```python
from tradingagents.dataflows.data_source_manager import get_data_source_manager

# 获取管理器
manager = get_data_source_manager()
manager.set_current_source("adata")

# 股票列表
stocks = ["000001", "600519", "601127", "002415", "300750"]

# 批量获取信息
for stock in stocks:
    info = manager.get_stock_info(stock)
    print(f"{stock}: {info['name']} - {info['industry']}")
```

## 故障排除

### 常见问题和解决方案

#### 1. AData库未安装

**问题**: `ImportError: No module named 'adata'`

**解决**:
```bash
pip install adata
```

#### 2. 数据获取失败

**问题**: 获取股票数据返回空值

**可能原因**:
- 股票代码格式不正确
- 日期范围过大
- 网络连接问题

**解决**:
- 确保股票代码为6位数字
- 缩小日期范围进行测试
- 检查网络连接

#### 3. 数据源切换失败

**问题**: 无法切换到AData数据源

**解决**:
```python
from tradingagents.dataflows.data_source_manager import get_data_source_manager

manager = get_data_source_manager()
print("可用数据源:", [s.value for s in manager.available_sources])

# 如果AData不在列表中，检查安装
import adata
```

### 调试工具

#### 快速测试脚本

```bash
# 运行快速测试
python tests/quick_adata_test.py

# 运行完整测试
python tests/test_adata_integration.py
```

#### 手动验证

```python
import adata

# 测试AData连接
try:
    # 获取平安银行数据
data = adata.stock.market.get_market_stock(
        stock_code="000001",
        market="sz",
        start_date="2024-01-01",
        end_date="2024-01-10"
    )
    print("AData连接成功，数据条数:", len(data))
except Exception as e:
    print("AData连接失败:", e)
```

## 性能优化

### 缓存配置

AData集成支持缓存机制，可以显著提高性能：

```python
# 在配置中启用缓存
config = {
    "china_data_source": "adata",
    "cache_enabled": True,
    "cache_ttl": 3600,  # 1小时缓存
}
```

### 并发处理

对于批量数据获取，建议使用并发处理：

```python
import concurrent.futures
from tradingagents.dataflows.adata_utils import get_adata_provider

def fetch_stock_data(symbol):
    provider = get_adata_provider()
    return provider.get_stock_data(symbol, "2024-01-01", "2024-12-31")

symbols = ["000001", "600519", "601127"]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(fetch_stock_data, symbols))
```

## 与其他数据源的比较

### AData vs Tushare

| 特性 | AData | Tushare |
|------|--------|---------|
| 实时性 | 高 | 中等 |
| 数据完整性 | 高 | 高 |
| 易用性 | 简单 | 中等 |
| 免费额度 | 有限 | 有限 |
| 安装复杂度 | 简单 | 中等 |

### 使用建议

- **新项目**: 推荐使用AData，API设计更现代化
- **现有项目**: 可以并行使用多个数据源作为备用
- **生产环境**: 建议配置多个数据源，提高可靠性

## 更新日志

- **v1.0.0**: 初始版本，支持基本数据获取
- **v1.1.0**: 添加实时数据支持
- **v1.2.0**: 优化错误处理和性能

## 相关资源

- [AData官方文档](https://github.com/adata-team/adata)
- [TradingAgents文档](../README.md)
- [数据源比较](../data/data-sources.md)