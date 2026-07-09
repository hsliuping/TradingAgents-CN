# Tushare使用指南

## 🎉 恭喜！您的Tushare配置已完成

您的系统已经成功配置并使用Tushare作为默认的中国股票数据源。现在您可以享受高质量、稳定的A股数据服务！

## ✅ 当前配置状态

```
📊 数据源状态: ✅ 正常
🔑 TUSHARE_TOKEN: ✅ 已配置 (56字符)
🎯 默认数据源: tushare
📦 可用数据源: tushare, akshare, baostock, tdx(已弃用)
🔗 API连接: ✅ 成功
```

## 🚀 立即开始使用

### 1. 命令行界面 (推荐)

```bash
# 启动CLI
python -m cli.main

# 选择分析中国股票
# 系统会自动使用Tushare数据源获取数据
```

### 2. Web界面

```bash
# 启动Web界面
python -m streamlit run web/app.py

# 在浏览器中访问: http://localhost:8501
# 系统会自动使用Tushare数据源
```

### 3. API调用示例

```python
from tradingagents.dataflows import (
    get_china_stock_data_unified,
    get_china_stock_info_unified
)

# 获取平安银行历史数据
data = get_china_stock_data_unified("000001", "2024-01-01", "2024-12-31")
print(data)

# 获取股票基本信息
info = get_china_stock_info_unified("000001")
print(info)
```

## 📊 Tushare数据优势

### 与TDX对比
| 特性 | TDX (旧) | Tushare (新) |
|------|----------|--------------|
| 数据质量 | ⚠️ 个人接口 | ✅ 专业API |
| 连接稳定性 | ⚠️ 经常断线 | ✅ 高可用 |
| 数据完整性 | ⚠️ 部分缺失 | ✅ 完整准确 |
| 更新频率 | ⚠️ 延迟较大 | ✅ 及时更新 |
| 技术支持 | ❌ 无官方支持 | ✅ 专业支持 |

### 数据覆盖
- ✅ **股票基础数据**: 所有A股股票信息
- ✅ **历史行情**: 日线、周线、月线数据（支持多周期同步）
- ✅ **财务数据**: 三大财务报表
- ✅ **实时数据**: 最新价格和交易信息
- ✅ **技术指标**: 常用技术分析指标

### 多周期数据支持 🆕
- **日线数据** (daily): 每个交易日的OHLCV数据
- **周线数据** (weekly): 每周的OHLCV数据
- **月线数据** (monthly): 每月的OHLCV数据
- 所有周期数据统一存储在 `stock_daily_quotes` 集合

## 🎯 常用功能示例

### 1. 股票分析

```python
# 分析平安银行
from tradingagents.dataflows import get_china_stock_fundamentals_tushare

# 获取基本面分析
fundamentals = get_china_stock_fundamentals_tushare("000001")
print(fundamentals)
```

### 2. 股票搜索

```python
# 搜索银行股
from tradingagents.dataflows import search_china_stocks_tushare

results = search_china_stocks_tushare("银行")
print(results)
```

### 3. 多周期数据初始化 🆕

```bash
# 初始化多周期历史数据（日线、周线、月线）
python cli/tushare_init.py --full --multi-period

# 指定历史数据范围（例如1年）
python cli/tushare_init.py --full --multi-period --historical-days 365

# 强制重新初始化
python cli/tushare_init.py --full --multi-period --force
```

### 4. 查询多周期数据 🆕

```python
from tradingagents.config.database_manager import get_mongodb_client

client = get_mongodb_client()
db = client.get_database('tradingagents')
collection = db.stock_daily_quotes

# 查询日线数据
daily_data = list(collection.find({
    'symbol': '000001',
    'period': 'daily',
    'data_source': 'tushare'
}).sort('trade_date', 1))

# 查询周线数据
weekly_data = list(collection.find({
    'symbol': '000001',
    'period': 'weekly',
    'data_source': 'tushare'
}).sort('trade_date', 1))

# 查询月线数据
monthly_data = list(collection.find({
    'symbol': '000001',
    'period': 'monthly',
    'data_source': 'tushare'
}).sort('trade_date', 1))

print(f"日线: {len(daily_data)} 条")
print(f"周线: {len(weekly_data)} 条")
print(f"月线: {len(monthly_data)} 条")
```

### 5. 数据源切换

```python
# 查看当前数据源
from tradingagents.dataflows import get_current_china_data_source

current = get_current_china_data_source()
print(current)

# 切换数据源（如果需要）
from tradingagents.dataflows import switch_china_data_source

switch_china_data_source("tushare")  # 确保使用Tushare
```

## ⚡ 性能优化建议

### 1. 利用缓存
- 系统自动缓存数据，重复查询会更快
- 缓存有效期24小时，确保数据新鲜度

### 2. 批量查询
```python
# 批量获取多只股票信息
stocks = ["000001", "000002", "600036", "600519"]
for stock in stocks:
    info = get_china_stock_info_unified(stock)
    print(f"{stock}: {info.split('股票名称: ')[1].split('\\n')[0]}")
```

### 3. 合理使用API
- Tushare有调用频率限制
- 建议间隔0.1秒进行连续调用
- 充分利用缓存减少API调用

## 🔧 故障排除

### 常见问题

1. **Token无效**
   ```
   错误: 无效的token
   解决: 检查.env文件中的TUSHARE_TOKEN是否正确
   ```

2. **API调用超限**
   ```
   错误: 调用频率超限
   解决: 等待一分钟后重试，或升级Tushare账号
   ```

3. **网络连接问题**
   ```
   错误: 连接超时
   解决: 检查网络连接，重试操作
   ```

### 调试命令

```bash
# 检查配置
python -c "
import os
print('TUSHARE_TOKEN:', '已设置' if os.getenv('TUSHARE_TOKEN') else '未设置')
print('DEFAULT_CHINA_DATA_SOURCE:', os.getenv('DEFAULT_CHINA_DATA_SOURCE', 'tushare'))
"

# 测试连接
python -c "
import tushare as ts
import os
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()
print('Tushare连接测试成功')
"
```

## 📈 高级功能

### 1. 自定义数据源策略

```python
from tradingagents.dataflows.data_source_manager import get_data_source_manager

manager = get_data_source_manager()

# 查看所有可用数据源
print("可用数据源:", [s.value for s in manager.available_sources])

# 设置备用数据源策略
# 主: Tushare -> 备用1: AKShare -> 备用2: BaoStock
```

### 2. 数据质量监控

```python
# 获取数据时检查质量
data = get_china_stock_data_unified("000001", "2024-01-01", "2024-12-31")

if "❌" in data:
    print("数据获取失败，请检查网络或API配置")
else:
    print("数据获取成功，质量良好")
```

## 🎯 最佳实践

### 1. 环境配置
- 确保`.env`文件中正确设置`TUSHARE_TOKEN`
- 设置`DEFAULT_CHINA_DATA_SOURCE=tushare`
- 定期检查Token有效性

### 2. 代码使用
- 优先使用统一接口`get_china_stock_data_unified()`
- 充分利用缓存机制
- 合理控制API调用频率

### 3. 错误处理
- 总是检查返回结果
- 实现适当的重试机制
- 记录错误日志便于调试

## 📞 获取帮助

### 技术支持
- **GitHub Issues**: 报告问题和功能请求
- **文档**: 查看详细的API文档
- **测试**: 运行`python tests/test_tushare_integration.py`

### Tushare官方
- **官网**: https://tushare.pro/
- **文档**: https://tushare.pro/document/2
- **社区**: Tushare用户群和论坛

---

🎉 **恭喜您成功配置Tushare！现在可以享受高质量的A股数据服务了！**

💡 **建议**: 立即尝试运行`python -m cli.main`开始您的股票分析之旅！

---

**更新日期**: 2025-09-30
**版本**: v1.1 - 新增多周期数据支持（日线、周线、月线）
