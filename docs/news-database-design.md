# 市场新闻数据库设计文档

## 数据库架构

### 集合: `market_news_enhanced`

增强版新闻数据库，支持AI分析和标签系统。

### 文档结构

```javascript
{
  "_id": ObjectId,
  
  // 基础字段
  "title": "新闻标题",
  "content": "新闻内容",
  "url": "原文链接",
  "time": "14:30",
  "dataTime": ISODate("2026-01-13T14:30:00"),
  "source": "财联社电报|新浪财经|东方财富网",
  
  // 智能分类和标签
  "category": "market_overview|hot_concept|stock_alert|fund_movement|limit_up",
  "tags": [
    {"name": "AI应用", "type": "concept", "weight": 5.0},
    {"name": "002131", "type": "stock", "weight": 3.0},
    {"name": "涨停", "type": "status", "weight": 4.0}
  ],
  "keywords": ["人工智能", "芯片", "半导体"],
  
  // 实体信息
  "stocks": [
    {"code": "002131", "name": "利欧股份"}
  ],
  "subjects": ["快手概念", "ChatGPT概念"],
  
  // 情感和热度
  "sentiment": "bullish|bearish|neutral",
  "sentimentScore": 0.5,
  "hotnessScore": 35.0,
  
  // 市场状态
  "isRed": false,
  "marketStatus": ["涨停", "连阳"],
  
  // 元数据
  "createdAt": ISODate,
  "updatedAt": ISODate,
  
  // 实体数据（原始）
  "entities": {
    "stocks": [...],
    "concepts": [...],
    "fund_types": [...],
    "market_status": [...]
  }
}
```

## 索引设计

```javascript
// 时间索引（最新优先）
db.market_news_enhanced.createIndex({ "dataTime": -1 })

// 来源+时间复合索引
db.market_news_enhanced.createIndex({ 
  "source": 1, 
  "dataTime": -1 
})

// 分类+热度复合索引
db.market_news_enhanced.createIndex({ 
  "category": 1, 
  "hotnessScore": -1 
})

// 股票代码索引
db.market_news_enhanced.createIndex({ "stocks.code": 1 })

// 关键词索引
db.market_news_enhanced.createIndex({ "keywords": 1 })

// 标签名称索引
db.market_news_enhanced.createIndex({ "tags.name": 1 })

// 情感索引
db.market_news_enhanced.createIndex({ "sentiment": 1 })
```

## API端点

### 1. 增强词云API
```
GET /api/market-news/enhanced-wordcloud
参数:
  - hours: 统计最近多少小时（默认24）
  - top_n: 返回前N个词（默认50）
  - source: 指定来源（可选）

返回:
{
  "words": [
    {"word": "人工智能", "weight": 25, "count": 15},
    {"word": "涨停", "weight": 20, "count": 10}
  ],
  "total": 50,
  "hours": 24,
  "source": "全部"
}
```

### 2. 新闻分析API
```
GET /api/market-news/analytics
参数:
  - hours: 统计最近多少小时（默认24）
  - source: 指定来源（可选）

返回:
{
  "total_count": 500,
  "source_distribution": {
    "财联社电报": 300,
    "新浪财经": 150,
    "东方财富网": 50
  },
  "category_distribution": {
    "market_overview": 50,
    "hot_concept": 200,
    ...
  },
  "hot_stocks": [
    {"code": "002131", "count": 15},
    ...
  ],
  "wordcloud": [...]
}
```

### 3. 新闻搜索API
```
GET /api/market-news/search
参数:
  - keyword: 搜索关键词
  - limit: 返回数量（默认50）

返回:
{
  "keyword": "AI",
  "count": 25,
  "results": [...]
}
```

### 4. 数据同步API
```
POST /api/market-news/sync-to-enhanced-db
参数:
  - hours: 同步最近多少小时的数据（默认24）

返回:
{
  "synced_count": 500,
  "hours": 24
}
```

## 数据流程

```
1. 新闻获取
   ├── fetch_cailian_telegraph() → 财联社电报
   ├── fetch_sina_news() → 新浪财经
   └── fetch_eastmoney_news() → 东方财富网

2. 实体提取和标签生成
   ├── NewsGroupingService.extract_entities()
   │   ├── 提取股票代码/名称
   │   ├── 提取概念/板块
   │   ├── 提取资金类型
   │   └── 提取市场状态
   ├── jieba分词提取关键词
   └── 情感分析（基于关键词）

3. 智能分类和评分
   ├── classify_news_type() → 5大分类
   └── calculate_hotness_score() → 热度评分

4. 保存到数据库
   ├── market_news (原集合，兼容)
   └── market_news_enhanced (增强集合，含标签)

5. API查询
   ├── 词云数据生成
   ├── 新闻分析聚合
   └── 搜索功能
```

## 标签类型说明

| 标签类型 | 说明 | 权重 | 示例 |
|---------|------|------|------|
| concept | 概念/题材 | 5.0 | AI应用、半导体、新能源车 |
| stock | 股票 | 3.0 | 利欧股份、贵州茅台 |
| status | 市场状态 | 4.0 | 涨停、连阳、创新高 |
| fund | 资金类型 | 3.0 | 主力资金、北向资金 |
| sector | 行业 | 4.0 | 金融、医药、军工 |

## 情感分析说明

| 情感 | 分数范围 | 触发词示例 |
|------|---------|-----------|
| bullish | > 0 | 上涨、涨停、突破、利好、增长 |
| bearish | < 0 | 下跌、跌停、回调、风险、亏损 |
| neutral | = 0 | 其他 |

## 使用示例

### 前端调用词云API
```typescript
import { newsApi } from '@/api/news'

// 获取24小时词云
const wordcloud = await newsApi.getNewsKeywords(24, 50)

// 获取指定来源词云
const enhancedWordcloud = await newsApi.getEnhancedWordcloud(24, 50, '财联社电报')
```

### 搜索新闻
```typescript
// 搜索包含"A股"的新闻
const results = await newsApi.searchNews("A股", 50)
```

## 性能优化

1. **索引优化**: 核心查询字段都建立了索引
2. **聚合管道**: 使用MongoDB聚合框架进行统计分析
3. **缓存策略**: 词云数据可以缓存10分钟
4. **分页查询**: 大量数据使用分页

## 数据清理

建议定期清理旧数据：
```python
# 删除30天前的数据
cutoff = datetime.now() - timedelta(days=30)
await db.market_news_enhanced.deleteMany({
  "dataTime": {"$lt": cutoff}
})
```
