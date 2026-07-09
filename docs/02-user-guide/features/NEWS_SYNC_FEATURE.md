# 新闻数据同步功能

## 📋 功能概述

**更新日期**: 2025-09-30
**版本**: v1.4

为 Tushare 和 AKShare 数据源添加了新闻数据同步功能，支持从多个新闻源获取股票相关新闻，并提供情绪分析和关键词提取。

## 🎯 主要特性

### 1. 多数据源支持

#### Tushare 新闻源
- **sina** - 新浪财经
- **eastmoney** - 东方财富
- **10jqka** - 同花顺
- **wallstreetcn** - 华尔街见闻
- **cls** - 财联社
- **yicai** - 第一财经
- **jinrongjie** - 金融界
- **yuncaijing** - 云财经
- **fenghuang** - 凤凰财经

#### AKShare 新闻源
- **东方财富** - 个股新闻（stock_news_em）
- **CCTV** - 市场新闻（news_cctv）

### 2. 智能去重

- 基于 URL、标题和发布时间的唯一标识
- 自动过滤重复新闻
- 支持跨数据源去重

### 3. 情绪分析（Tushare & AKShare）

- 自动分析新闻情绪（positive/negative/neutral）
- 提供情绪分数（-1.0 到 1.0）
- 基于财经关键词的智能分析
- 支持积极/消极关键词权重计算

### 4. 关键词提取（Tushare & AKShare）

- 自动提取财经相关关键词
- 支持多种关键词类型（股票、公司、市场、政策等）
- 最多提取10个关键词

### 5. 新闻分类（Tushare & AKShare）

- 自动分类新闻类型
- 支持类别：
  - company_announcement（公司公告）
  - policy_news（政策新闻）
  - industry_news（行业新闻）
  - market_news（市场新闻）
  - research_report（研究报告）
  - general（一般新闻）

### 6. 重要性评估（Tushare & AKShare）

- 自动评估新闻重要性
- 三个级别：high（高）、medium（中）、low（低）
- 基于关键词和内容分析

### 7. 灵活的同步选项

- 可指定回溯时间（Tushare：默认24小时，最多7天）
- 可限制每只股票的新闻数量
- 支持选择性同步（仅同步新闻数据）

## 📊 数据结构

### 新闻数据模型

```javascript
{
  // 股票信息
  "symbol": "000001",           // 股票代码
  "full_symbol": "000001.SZ",   // 完整代码
  "market": "CN",               // 市场
  "symbols": ["000001"],        // 相关股票列表
  
  // 新闻内容
  "title": "新闻标题",
  "content": "新闻正文内容",
  "summary": "新闻摘要",
  "url": "https://...",         // 新闻链接
  "source": "sina",             // 新闻来源
  "author": "作者名",
  
  // 时间信息
  "publish_time": "2025-09-30 12:00:00",  // 发布时间
  
  // 分类和标签
  "category": "general",        // 分类
  "sentiment": "neutral",       // 情绪 (positive/negative/neutral)
  "sentiment_score": 0.0,       // 情绪分数 (-1.0 到 1.0)
  "keywords": ["关键词1", "关键词2"],  // 关键词
  "importance": "medium",       // 重要性 (high/medium/low)
  "language": "zh-CN",          // 语言
  
  // 元数据
  "data_source": "tushare",     // 数据源
  "created_at": "2025-09-30 12:00:00",
  "updated_at": "2025-09-30 12:00:00",
  "version": 1
}
```

### 数据库集合

新闻数据存储在 MongoDB 的 `stock_news` 集合中。

## 🔧 使用方法

### CLI 命令

#### Tushare 数据源

##### 1. 仅同步新闻数据

```bash
# 同步所有股票的新闻（默认回溯24小时）
python cli/tushare_init.py --full --sync-items news
```

##### 2. 同步新闻和其他数据

```bash
# 同步基础信息和新闻
python cli/tushare_init.py --full --sync-items basic_info,news

# 同步历史数据、财务数据和新闻
python cli/tushare_init.py --full --sync-items historical,financial,news
```

##### 3. 完整初始化（包含新闻）

```bash
# 完整初始化，包含所有数据类型
python cli/tushare_init.py --full --sync-items basic_info,historical,financial,quotes,news
```

#### AKShare 数据源

##### 1. 仅同步新闻数据

```bash
# 同步所有股票的新闻
python cli/akshare_init.py --full --sync-items news
```

##### 2. 同步新闻和其他数据

```bash
# 同步基础信息和新闻
python cli/akshare_init.py --full --sync-items basic_info,news

# 同步历史数据、财务数据和新闻
python cli/akshare_init.py --full --sync-items historical,financial,news
```

##### 3. 完整初始化（包含新闻）

```bash
# 完整初始化，包含所有数据类型
python cli/akshare_init.py --full --sync-items basic_info,historical,financial,quotes,news
```

### Python API

#### 1. 使用同步服务

```python
from app.worker.tushare_sync_service import get_tushare_sync_service

# 获取同步服务
sync_service = await get_tushare_sync_service()

# 同步所有股票的新闻
result = await sync_service.sync_news_data(
    hours_back=24,              # 回溯24小时
    max_news_per_stock=20       # 每只股票最多20条新闻
)

# 同步指定股票的新闻
result = await sync_service.sync_news_data(
    symbols=["000001", "600000"],
    hours_back=48,
    max_news_per_stock=50
)
```

#### 2. 使用初始化服务

```python
from app.worker.tushare_init_service import get_tushare_init_service

# 获取初始化服务
init_service = await get_tushare_init_service()

# 运行完整初始化（包含新闻）
result = await init_service.run_full_initialization(
    historical_days=365,
    sync_items=['basic_info', 'historical', 'news']
)
```

#### 3. 直接使用 Provider

```python
from tradingagents.dataflows.providers.tushare_provider import get_tushare_provider

# 获取 Provider
provider = get_tushare_provider()
await provider.connect()

# 获取单只股票的新闻
news_data = await provider.get_stock_news(
    symbol="000001",
    limit=20,
    hours_back=24
)
```

## 📈 同步结果统计

同步完成后会返回详细的统计信息：

```python
{
    "total_processed": 100,      # 处理的股票总数
    "success_count": 98,         # 成功数量
    "error_count": 2,            # 错误数量
    "news_count": 1234,          # 获取的新闻总数
    "duration": 120.5,           # 耗时（秒）
    "errors": [...]              # 错误列表
}
```

## 🎯 功能特性对比

| 功能 | Tushare | AKShare |
|------|---------|---------|
| 新闻源数量 | 9个 | 2个 |
| 回溯时间 | 可配置（默认24小时） | 由API决定 |
| 情绪分析 | ✅ | ✅ |
| 情绪分数 | ✅ | ✅ |
| 关键词提取 | ✅ | ✅ |
| 新闻分类 | ✅ | ✅ |
| 重要性评估 | ✅ | ✅ |
| 数据质量 | 高（需权限） | 中（免费） |
| API限制 | 有速率限制 | 较宽松 |

## ⚠️ 注意事项

### 1. 权限要求

- 新闻数据需要 Tushare 新闻权限
- 部分新闻源可能需要付费权限
- 免费用户可能只能访问部分新闻源

### 2. 限制说明

- 默认回溯时间：24小时
- 最大回溯时间：7天
- 每只股票默认最多获取20条新闻
- 受 Tushare API 速率限制约束

### 3. 数据质量

- 新闻数据的完整性取决于数据源
- 部分新闻可能缺少作者、摘要等字段
- 情绪分析结果仅供参考

### 4. 性能考虑

- 新闻同步速度受网络和 API 限制影响
- 建议在非交易时间进行大批量同步
- 可以使用 `--sync-items news` 单独同步新闻

## 🔍 故障排查

### 问题1: 未获取到新闻数据

**可能原因**:
- Tushare 账户没有新闻权限
- 指定时间段内没有新闻
- API 调用频率超限

**解决方法**:
- 检查 Tushare 账户权限
- 增加回溯时间范围
- 等待一段时间后重试

### 问题2: 新闻保存失败

**可能原因**:
- 新闻数据缺少必需字段（URL、标题等）
- MongoDB 连接问题
- 数据格式不正确

**解决方法**:
- 检查日志中的详细错误信息
- 验证 MongoDB 连接状态
- 联系技术支持

### 问题3: 同步速度慢

**可能原因**:
- 网络延迟
- API 速率限制
- 股票数量过多

**解决方法**:
- 使用更快的网络连接
- 减少每批次处理的股票数量
- 分批次进行同步

## 📚 相关文档

- [多周期数据同步更新](./MULTI_PERIOD_DATA_SYNC_UPDATE.md)
- [多数据源同步指南](./MULTI_SOURCE_SYNC_GUIDE.md)
- [Tushare 使用指南](./TUSHARE_USAGE_GUIDE.md)

## 🔄 更新历史

### v1.4 (2025-09-30)
- ✅ 添加 Tushare 新闻数据同步功能
- ✅ 添加 AKShare 新闻数据同步功能
- ✅ 支持多新闻源（Tushare 9个，AKShare 2个）
- ✅ 实现智能去重
- ✅ 添加情绪分析（positive/negative/neutral）
- ✅ 添加情绪分数计算（-1.0 到 1.0）
- ✅ 添加关键词提取（最多10个）
- ✅ 添加新闻分类（6种类别）
- ✅ 添加重要性评估（high/medium/low）
- ✅ 更新 CLI 工具（tushare_init.py 和 akshare_init.py）
- ✅ 更新文档

## 📞 技术支持

如有问题或建议，请：
1. 查看相关文档
2. 检查日志文件
3. 提交 Issue
4. 联系技术支持团队

