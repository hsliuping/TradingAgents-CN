# AKShare 导入错误修复文档（架构规范版）

## 📋 问题描述

在股票分析过程中，新闻获取模块出现以下错误：

```
ModuleNotFoundError: No module named 'tradingagents.dataflows.news.akshare_utils'
```

同时还有一个类型错误：

```
TypeError: limit must be an integer, not <class 'float'>
```

## 🏗️ 架构规范

根据项目架构规范：
- ✅ **所有数据接口必须统一在 `tradingagents/dataflows/providers/` 目录管理**
- ❌ **禁止在其他模块随便引入数据接口（如直接 `import akshare`）**
- ✅ **应该通过 Provider 层统一访问数据源**

## 🔍 问题分析

### 问题 1：AKShare 导入错误

**错误代码**：
```python
from .akshare_utils import get_stock_news_em
```

**根本原因**：
- `tradingagents/dataflows/news/` 目录下没有 `akshare_utils.py` 文件
- 代码尝试导入不存在的模块

**正确做法**：
- 通过 `AKShareProvider` 统一访问 AKShare 数据
- 遵循项目架构规范

**影响范围**：
- `tradingagents/dataflows/news/realtime_news.py` 中有 3 处错误导入
- `tradingagents/agents/utils/agent_utils.py` 中有 1 处错误导入

### 问题 2：MongoDB limit 参数类型错误

**错误代码**：
```python
cursor = collection.find(query).sort('publish_time', -1).limit(max_news)
```

**根本原因**：
- `max_news` 参数可能是浮点数（从配置或 LLM 传入）
- MongoDB 的 `limit()` 方法要求整数参数

**影响范围**：
- `tradingagents/tools/unified_news_tool.py` 第 135 行

## ✅ 解决方案

### 修复 1：在 AKShareProvider 中添加同步方法

**文件**：`tradingagents/dataflows/providers/china/akshare.py`

**新增方法**：`get_stock_news_sync()` - 同步版本的新闻获取方法

```python
def get_stock_news_sync(self, symbol: str = None, limit: int = 10) -> Optional[pd.DataFrame]:
    """
    获取股票新闻（同步版本，返回原始 DataFrame）

    Args:
        symbol: 股票代码，为None时获取市场新闻
        limit: 返回数量限制

    Returns:
        新闻 DataFrame 或 None
    """
    if not self.is_available():
        return None

    try:
        import akshare as ak

        if symbol:
            # 获取个股新闻
            self.logger.debug(f"📰 获取AKShare个股新闻: {symbol}")

            # 标准化股票代码
            symbol_6 = symbol.zfill(6)

            # 获取东方财富个股新闻
            news_df = ak.stock_news_em(symbol=symbol_6)

            if news_df is not None and not news_df.empty:
                self.logger.info(f"✅ {symbol} AKShare新闻获取成功: {len(news_df)} 条")
                return news_df.head(limit) if limit else news_df
            else:
                self.logger.warning(f"⚠️ {symbol} 未获取到AKShare新闻数据")
                return None
        else:
            # 获取市场新闻
            self.logger.debug("📰 获取AKShare市场新闻")
            news_df = ak.news_cctv()

            if news_df is not None and not news_df.empty:
                self.logger.info(f"✅ AKShare市场新闻获取成功: {len(news_df)} 条")
                return news_df.head(limit) if limit else news_df
            else:
                self.logger.warning("⚠️ 未获取到AKShare市场新闻数据")
                return None

    except Exception as e:
        self.logger.error(f"❌ AKShare新闻获取失败: {e}")
        return None
```

### 修复 2：更正 realtime_news.py 中的导入

**文件**：`tradingagents/dataflows/news/realtime_news.py`

#### 修改位置 1：第 739-744 行（A股东方财富新闻）

**修改前**：
```python
try:
    logger.info(f"[新闻分析] 尝试导入 akshare_utils.get_stock_news_em")
    from .akshare_utils import get_stock_news_em
    logger.info(f"[新闻分析] 成功导入 get_stock_news_em 函数")
```

**修改后**：
```python
try:
    logger.info(f"[新闻分析] 尝试通过 AKShare Provider 获取新闻")
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    provider = AKShareProvider()
    logger.info(f"[新闻分析] 成功创建 AKShare Provider 实例")
```

#### 修改位置 2：第 751-756 行（调用东方财富 API）

**修改前**：
```python
news_df = get_stock_news_em(clean_ticker, max_news=10)
```

**修改后**：
```python
news_df = provider.get_stock_news_sync(symbol=clean_ticker, limit=10)
```

#### 修改位置 3：第 312-331 行（中文财经新闻）

**修改前**：
```python
try:
    logger.info(f"[中文财经新闻] 尝试导入 AKShare 工具")
    from .akshare_utils import get_stock_news_em

    # ...

    news_df = get_stock_news_em(clean_ticker)
```

**修改后**：
```python
try:
    logger.info(f"[中文财经新闻] 尝试通过 AKShare Provider 获取新闻")
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    provider = AKShareProvider()

    # ...

    news_df = provider.get_stock_news_sync(symbol=clean_ticker)
```

#### 修改位置 4：第 863-873 行（港股新闻）

**修改前**：
```python
try:
    from .akshare_utils import get_stock_news_em

    # ...

    news_df = get_stock_news_em(clean_ticker, max_news=10)
```

**修改后**：
```python
try:
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    provider = AKShareProvider()

    # ...

    news_df = provider.get_stock_news_sync(symbol=clean_ticker, limit=10)
```

### 修复 3：更正 agent_utils.py 中的导入

**文件**：`tradingagents/agents/utils/agent_utils.py`

#### 修改位置：第 1305-1325 行（统一新闻工具）

**修改前**：
```python
# 导入AKShare新闻获取函数
from tradingagents.dataflows.akshare_utils import get_stock_news_em

# 获取东方财富新闻
news_df = get_stock_news_em(clean_ticker)

if not news_df.empty:
    # 格式化东方财富新闻
    em_news_items = []
    for _, row in news_df.iterrows():
        news_title = row.get('标题', '')
        news_time = row.get('时间', '')
        news_url = row.get('链接', '')
```

**修改后**：
```python
# 通过 AKShare Provider 获取新闻
from tradingagents.dataflows.providers.china.akshare import AKShareProvider

provider = AKShareProvider()

# 获取东方财富新闻
news_df = provider.get_stock_news_sync(symbol=clean_ticker)

if news_df is not None and not news_df.empty:
    # 格式化东方财富新闻
    em_news_items = []
    for _, row in news_df.iterrows():
        # AKShare 返回的字段名
        news_title = row.get('新闻标题', '') or row.get('标题', '')
        news_time = row.get('发布时间', '') or row.get('时间', '')
        news_url = row.get('新闻链接', '') or row.get('链接', '')
```

### 修复 4：确保 max_news 是整数

**文件**：`tradingagents/tools/unified_news_tool.py`

**修改位置**：第 107 行

**修改前**：
```python
try:
    from tradingagents.dataflows.cache.app_adapter import get_mongodb_client
    from datetime import timedelta

    client = get_mongodb_client()
```

**修改后**：
```python
try:
    from tradingagents.dataflows.cache.app_adapter import get_mongodb_client
    from datetime import timedelta

    # 🔧 确保 max_news 是整数（防止传入浮点数）
    max_news = int(max_news)

    client = get_mongodb_client()
```

## 📊 修复效果

### 修复前

```
❌ [新闻分析] 东方财富新闻获取失败: No module named 'tradingagents.dataflows.news.akshare_utils'
❌ [统一新闻工具] 从数据库获取新闻失败: limit must be an integer, not <class 'float'>
⚠️ [统一新闻工具] 数据库中没有 600519 的新闻，尝试其他新闻源...
```

### 修复后（预期）

```
✅ [新闻分析] 成功导入 akshare 模块
✅ [新闻分析] 东方财富API调用成功，获取到 10 条新闻
✅ [统一新闻工具] 从数据库获取新闻成功
```

## 🔧 正确的使用方式

### ✅ 推荐：通过 Provider 访问

```python
from tradingagents.dataflows.providers.china.akshare import AKShareProvider

# 创建 Provider 实例
provider = AKShareProvider()

# 获取个股新闻（同步版本）
news_df = provider.get_stock_news_sync(symbol="600519", limit=10)

# 获取个股新闻（异步版本）
news_list = await provider.get_stock_news(symbol="600519", limit=10)
```

### ❌ 错误：直接导入 akshare

```python
# ❌ 不要这样做！违反架构规范
import akshare as ak
news_df = ak.stock_news_em(symbol="600519")

# ❌ 不要这样做！模块不存在
from tradingagents.dataflows.akshare_utils import get_stock_news_em
```

### 📊 返回数据格式

**同步版本** (`get_stock_news_sync`)：
- 返回：`pd.DataFrame` 或 `None`
- 字段：
  - `新闻标题`：新闻标题
  - `新闻内容`：新闻正文
  - `发布时间`：发布时间
  - `新闻来源`：来源媒体
  - `新闻链接`：原文链接

**异步版本** (`get_stock_news`)：
- 返回：`List[Dict]` 或 `None`
- 字段：
  - `symbol`：股票代码
  - `title`：新闻标题
  - `content`：新闻内容
  - `summary`：新闻摘要
  - `url`：新闻链接
  - `source`：新闻来源
  - `publish_time`：发布时间
  - `sentiment`：情绪分析
  - `keywords`：关键词
  - `importance`：重要性

### 参数说明

- `symbol`：股票代码（6位数字，不带后缀）
  - A股示例：`"600519"`（贵州茅台）
  - 港股示例：`"00700"`（腾讯控股）
- `limit`：返回数量限制（默认 10）

## 📝 相关文件

### 修改的文件

1. ✅ `tradingagents/dataflows/providers/china/akshare.py`
   - 新增了 `get_stock_news_sync()` 同步方法
   - 提供统一的数据访问接口

2. ✅ `tradingagents/dataflows/news/realtime_news.py`
   - 修复了 3 处 AKShare 导入错误
   - 改用 `AKShareProvider` 访问数据

3. ✅ `tradingagents/agents/utils/agent_utils.py`
   - 修复了 1 处 AKShare 导入错误
   - 改用 `AKShareProvider` 访问数据
   - 修正了字段名称映射

4. ✅ `tradingagents/tools/unified_news_tool.py`
   - 添加了 `max_news` 参数类型转换

### 架构说明

```
tradingagents/
├── dataflows/
│   ├── providers/          # ✅ 数据接口统一管理层
│   │   ├── china/
│   │   │   └── akshare.py  # AKShare 数据提供器
│   │   ├── us/
│   │   └── ...
│   └── news/               # 新闻聚合层
│       └── realtime_news.py # 通过 Provider 访问数据
├── agents/
│   └── utils/
│       └── agent_utils.py  # 通过 Provider 访问数据
└── tools/
    └── unified_news_tool.py
```

### 相关文档

- `docs/guides/news-analysis-guide.md` - 新闻分析使用指南
- `docs/features/news-analysis-system.md` - 新闻分析系统架构
- `docs/NEWS_SENTIMENT_ANALYSIS.md` - 新闻情绪分析文档

## 🧪 测试建议

### 测试 1：验证 Provider 访问

```python
from tradingagents.dataflows.providers.china.akshare import AKShareProvider

# 创建 Provider 实例
provider = AKShareProvider()

# 测试获取贵州茅台新闻
news_df = provider.get_stock_news_sync(symbol="600519", limit=10)
if news_df is not None:
    print(f"✅ 获取到 {len(news_df)} 条新闻")
    print(news_df.head())
else:
    print("❌ 获取新闻失败")
```

### 测试 2：验证新闻工具

```python
from tradingagents.tools.unified_news_tool import UnifiedNewsAnalyzer

# 创建分析器
analyzer = UnifiedNewsAnalyzer(toolkit)

# 测试获取新闻（传入浮点数）
news = analyzer.get_stock_news_unified("600519", max_news=10.0)
print(news)
```

### 测试 3：完整分析流程

1. **重启后端服务**
2. **发起股票分析**（如 `600519`）
3. **查看日志**，应该看到：
   ```
   ✅ [新闻分析] 成功创建 AKShare Provider 实例
   ✅ [新闻分析] 东方财富API调用成功
   ✅ 600519 AKShare新闻获取成功: 10 条
   ```

## 📅 修复日期

2025-10-12

## 🎯 总结

| 问题 | 原因 | 解决方案 | 状态 |
|------|------|----------|------|
| **AKShare 导入错误** | 导入不存在的模块 | 通过 `AKShareProvider` 统一访问 | ✅ 已修复 |
| **MongoDB limit 类型错误** | 传入浮点数参数 | 添加 `int()` 类型转换 | ✅ 已修复 |
| **架构规范违反** | 直接导入数据接口 | 遵循 Provider 层架构 | ✅ 已修复 |

**修复文件**：
- ✅ `tradingagents/dataflows/providers/china/akshare.py` - 新增同步方法
- ✅ `tradingagents/dataflows/news/realtime_news.py` - 3 处修复
- ✅ `tradingagents/agents/utils/agent_utils.py` - 1 处修复
- ✅ `tradingagents/tools/unified_news_tool.py` - 类型转换

**影响**：
- ✅ 新闻获取功能恢复正常
- ✅ A股、港股新闻可以正常获取
- ✅ 数据库查询不再报错
- ✅ 遵循项目架构规范
- ✅ 统一数据访问接口

**架构优势**：
- ✅ **统一管理**：所有数据接口在 `providers/` 目录统一管理
- ✅ **易于维护**：修改数据源只需修改 Provider
- ✅ **可测试性**：Provider 可以独立测试
- ✅ **可扩展性**：添加新数据源只需实现新 Provider

**建议**：
- 重启后端服务以应用修复
- 测试新闻获取功能
- 监控日志确认修复生效
- 后续开发遵循 Provider 层架构规范

