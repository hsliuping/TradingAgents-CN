# Tushare数据源集成指南

本指南介绍如何在TradingAgents中集成和使用Tushare数据源，获取高质量的中国A股市场数据。

## 📊 Tushare简介

Tushare是一个免费、开源的Python财经数据接口包，主要实现对股票等金融数据从数据采集、清洗加工到数据存储的过程，能够为金融分析人员提供快速、整洁、和多样的便于分析的数据。

### 主要特点

- **数据全面**: 覆盖股票、基金、期货、债券等多种金融产品
- **数据质量高**: 数据来源权威，经过清洗和验证
- **更新及时**: 提供实时和历史数据
- **接口简单**: Python原生接口，易于使用
- **免费使用**: 基础功能免费，高级功能需要积分

## 🚀 快速开始

### 1. 注册Tushare账号

1. 访问 [Tushare官网](https://tushare.pro/register)
2. 注册账号并完成邮箱验证
3. 登录后在个人中心获取API Token

### 2. 安装依赖

```bash
# Tushare已包含在项目依赖中
pip install tushare>=1.4.21
```

### 3. 配置环境变量

在项目根目录创建或编辑 `.env` 文件：

```bash
# Tushare API Token
TUSHARE_TOKEN=your_tushare_token_here

# 设置默认A股数据源为Tushare
DEFAULT_CHINA_DATA_SOURCE=tushare

# 启用数据缓存
ENABLE_DATA_CACHE=true
```

### 4. 验证配置

运行测试脚本验证配置：

```bash
python tests/test_tushare_integration.py
```

## 📚 使用方法

### 命令行界面 (CLI)

```bash
# 启动CLI
python -m cli.main

# 选择分析中国股票
# 系统会自动使用Tushare数据源
```

### Web界面

```bash
# 启动Web界面
python -m streamlit run web/app.py

# 在配置页面选择Tushare作为A股数据源
```

### API接口

```python
from tradingagents.dataflows import (
    get_china_stock_data_tushare,
    search_china_stocks_tushare,
    get_china_stock_fundamentals_tushare,
    get_china_stock_info_tushare
)

# 获取股票历史数据
data = get_china_stock_data_tushare("000001", "2024-01-01", "2024-12-31")

# 搜索股票
results = search_china_stocks_tushare("平安银行")

# 获取基本面数据
fundamentals = get_china_stock_fundamentals_tushare("000001")

# 获取股票基本信息
info = get_china_stock_info_tushare("000001")
```

### 直接使用适配器

```python
from tradingagents.dataflows.tushare_adapter import get_tushare_adapter

# 获取适配器实例
adapter = get_tushare_adapter()

# 获取股票数据
data = adapter.get_stock_data("000001", "2024-01-01", "2024-12-31")

# 获取股票信息
info = adapter.get_stock_info("000001")

# 搜索股票
results = adapter.search_stocks("平安")

# 获取基本面数据
fundamentals = adapter.get_fundamentals("000001")
```

## 🔧 高级配置

### 缓存配置

Tushare集成支持多种缓存方式：

```bash
# 文件缓存 (默认)
CACHE_TYPE=file

# Redis缓存
CACHE_TYPE=redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MongoDB缓存
CACHE_TYPE=mongodb
MONGODB_HOST=localhost
MONGODB_PORT=27017
```

### API限制配置

```bash
# API调用频率限制 (每分钟)
TUSHARE_API_RATE_LIMIT=200

# API超时设置 (秒)
TUSHARE_API_TIMEOUT=30

# 并发请求数量
MAX_CONCURRENT_REQUESTS=5
```

### 数据源回退

```bash
# 备用数据源
FALLBACK_DATA_SOURCES=akshare,baostock

# 自动切换
AUTO_FALLBACK_ENABLED=true
```

## 📊 支持的数据类型

### 1. 股票基础数据

- **股票列表**: 获取所有A股股票基本信息
- **股票信息**: 股票名称、行业、地区等基本信息
- **历史行情**: 日线、周线、月线数据
- **实时行情**: 最新价格和交易数据

### 2. 财务数据

- **资产负债表**: 公司资产、负债、股东权益
- **利润表**: 营业收入、利润、费用等
- **现金流量表**: 经营、投资、筹资活动现金流
- **财务指标**: PE、PB、ROE等关键指标

### 3. 市场数据

- **交易日历**: 交易日、节假日信息
- **股票分类**: 行业分类、概念分类
- **指数数据**: 上证指数、深证成指等

## 🎯 最佳实践

### 1. API使用优化

```python
# 批量获取数据
symbols = ["000001", "000002", "600036"]
for symbol in symbols:
    data = adapter.get_stock_data(symbol, start_date, end_date)
    # 处理数据...
    time.sleep(0.1)  # 避免频率限制
```

### 2. 缓存策略

```python
# 启用缓存以提高性能
adapter = get_tushare_adapter()  # 默认启用缓存

# 对于频繁访问的数据，设置合适的缓存时间
# 日线数据: 24小时
# 基本信息: 7天
# 财务数据: 30天
```

### 3. 错误处理

```python
try:
    data = adapter.get_stock_data("000001", start_date, end_date)
    if data.empty:
        print("未获取到数据")
    else:
        # 处理数据
        pass
except Exception as e:
    print(f"数据获取失败: {e}")
    # 使用备用数据源或缓存数据
```

## 🔍 故障排除

### 常见问题

1. **Token无效**
   ```
   错误: 无效的token
   解决: 检查TUSHARE_TOKEN是否正确设置
   ```

2. **API调用超限**
   ```
   错误: 调用频率超限
   解决: 降低调用频率或升级账号权限
   ```

3. **网络连接问题**
   ```
   错误: 连接超时
   解决: 检查网络连接，增加超时时间
   ```

4. **数据为空**
   ```
   错误: 返回空数据
   解决: 检查股票代码和日期范围是否正确
   ```

### 调试模式

启用详细日志以便调试：

```bash
# 在.env文件中设置
LOG_LEVEL=DEBUG
ENABLE_VERBOSE_LOGGING=true
```

## 📈 性能优化

### 1. 缓存优化

- 启用Redis或MongoDB缓存以提高性能
- 设置合适的缓存过期时间
- 定期清理过期缓存

### 2. 并发优化

- 使用连接池减少连接开销
- 控制并发请求数量避免API限制
- 实现请求队列管理

### 3. 数据预取

- 预先获取常用股票数据
- 批量获取减少API调用次数
- 使用异步请求提高效率

## 🔄 版本更新

### v0.1.6 新特性

- ✅ 完整的Tushare API集成
- ✅ 智能缓存机制
- ✅ 多数据源回退
- ✅ 统一接口设计
- ✅ 性能优化

### 后续计划

- 🔄 实时数据推送
- 🔄 更多财务指标
- 🔄 技术指标计算
- 🔄 新闻情感分析

## 📞 技术支持

- **GitHub Issues**: 问题报告和功能请求
- **文档**: 详细的API文档和示例
- **社区**: 用户交流和经验分享

---

**注意**: Tushare的高级功能需要积分，建议根据使用需求选择合适的套餐。
