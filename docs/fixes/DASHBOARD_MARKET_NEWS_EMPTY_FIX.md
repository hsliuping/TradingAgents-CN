# 仪表台市场快讯显示为空的问题修复

## 📋 问题描述

用户报告：仪表台的市场快讯区域没有显示任何内容。

## 🔍 问题分析

### 1. 数据库检查

运行检查脚本：
```bash
python scripts/check_news_data.py
```

**检查结果**：
- ✅ 数据库中有 **214,288 条新闻数据**
- ❌ 但是**最近 24 小时没有新闻数据**
- 📅 最新的新闻日期是 **2025-10-11**（今天是 2025-10-23）

### 2. 前端代码分析

<augment_code_snippet path="frontend/src/views/Dashboard/index.vue" mode="EXCERPT">
````typescript
const loadMarketNews = async () => {
  try {
    const response = await newsApi.getLatestNews(undefined, 10, 24)  // 查询最近 24 小时
    if (response.success && response.data) {
      marketNews.value = response.data.news.map((item: any) => ({
        id: item.id || item.title,
        title: item.title,
        time: item.publish_time,
        url: item.url,
        source: item.source
      }))
    }
  } catch (error) {
    console.error('加载市场快讯失败:', error)
    marketNews.value = []
  }
}
````
</augment_code_snippet>

**问题原因**：
- 前端默认查询最近 **24 小时**的新闻
- 数据库中最新的新闻是 **12 天前**的
- 查询结果为空，导致市场快讯区域显示"暂无市场快讯"

### 3. 后端 API 分析

<augment_code_snippet path="app/services/news_data_service.py" mode="EXCERPT">
````python
async def get_latest_news(
    self,
    symbol: str = None,
    limit: int = 10,
    hours_back: int = 24  # 默认回溯 24 小时
) -> List[Dict[str, Any]]:
    """获取最新新闻"""
    start_time = datetime.utcnow() - timedelta(hours=hours_back)
    
    params = NewsQueryParams(
        symbol=symbol,
        start_time=start_time,  # 只查询 start_time 之后的新闻
        limit=limit,
        sort_by="publish_time",
        sort_order=-1
    )
    
    return await self.query_news(params)
````
</augment_code_snippet>

**API 逻辑**：
- 后端根据 `hours_back` 参数计算 `start_time`
- 只返回 `publish_time >= start_time` 的新闻
- 如果时间范围内没有新闻，返回空数组

---

## ✅ 解决方案

### 方案 1：前端智能回退（已实施）

**修改文件**：`frontend/src/views/Dashboard/index.vue`

**修改内容**：
```typescript
const loadMarketNews = async () => {
  try {
    // 先尝试获取最近 24 小时的新闻
    let response = await newsApi.getLatestNews(undefined, 10, 24)
    
    // 如果最近 24 小时没有新闻，则获取最新的 10 条（不限时间）
    if (response.success && response.data && response.data.news.length === 0) {
      console.log('最近 24 小时没有新闻，获取最新的 10 条新闻（不限时间）')
      response = await newsApi.getLatestNews(undefined, 10, 24 * 365) // 回溯 1 年
    }
    
    if (response.success && response.data) {
      marketNews.value = response.data.news.map((item: any) => ({
        id: item.id || item.title,
        title: item.title,
        time: item.publish_time,
        url: item.url,
        source: item.source
      }))
    }
  } catch (error) {
    console.error('加载市场快讯失败:', error)
    marketNews.value = []
  }
}
```

**修复逻辑**：
1. ✅ 先尝试获取最近 24 小时的新闻
2. ✅ 如果结果为空，则回溯 1 年（`24 * 365` 小时）
3. ✅ 确保即使没有最新新闻，也能显示数据库中最新的 10 条新闻

**优点**：
- ✅ 快速修复，无需等待新闻同步
- ✅ 用户立即可以看到新闻内容
- ✅ 不影响后端 API

**缺点**：
- ⚠️ 显示的是旧新闻，不是实时新闻

---

### 方案 2：同步最新新闻（推荐）

#### 2.1 使用命令行脚本

**运行脚本**：
```bash
# Windows PowerShell
.\.venv\Scripts\python scripts/sync_market_news.py

# Linux / Mac
python scripts/sync_market_news.py
```

**脚本功能**：
- 从东方财富等数据源获取最新的市场新闻
- 默认回溯 24 小时
- 每个数据源最多获取 50 条新闻
- 自动去重，避免重复保存

**输出示例**：
```
================================================================================
📰 同步市场新闻
================================================================================

⏰ 回溯时间: 24 小时
📊 每个数据源最大新闻数: 50

🔄 开始同步新闻...

================================================================================
✅ 同步完成
================================================================================

⏱️  耗时: 12.34 秒
📊 同步结果:
   - 总新闻数: 50
   - 新增新闻: 45
   - 重复新闻: 5

📡 数据源统计:
   - akshare:
     • 获取: 50 条
     • 新增: 45 条
     • 重复: 5 条

💡 提示:
   - 刷新前端仪表板即可看到最新新闻
   - 建议定期运行此脚本以保持新闻数据最新
```

#### 2.2 使用前端界面

**操作步骤**：
1. 打开仪表板页面
2. 在市场快讯区域找到"同步市场新闻"按钮
3. 点击按钮，等待同步完成
4. 刷新页面查看最新新闻

#### 2.3 使用后端 API

**API 端点**：`POST /api/news-data/sync/start`

**请求示例**：
```bash
curl -X POST "http://localhost:8000/api/news-data/sync/start" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "symbol": null,
    "data_sources": null,
    "hours_back": 24,
    "max_news_per_source": 50
  }'
```

**响应示例**：
```json
{
  "success": true,
  "data": {
    "sync_type": "market",
    "hours_back": 24,
    "max_news_per_source": 50,
    "total_news": 50,
    "new_news": 45,
    "duplicate_news": 5
  },
  "message": "新闻同步成功"
}
```

---

## 🔧 定期同步建议

### 1. 使用 Cron 定时任务（Linux / Mac）

**编辑 crontab**：
```bash
crontab -e
```

**添加定时任务**（每小时同步一次）：
```cron
0 * * * * cd /path/to/TradingAgents-CN && .venv/bin/python scripts/sync_market_news.py >> logs/news_sync.log 2>&1
```

### 2. 使用 Windows 任务计划程序

**创建任务**：
1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器：每小时
4. 操作：启动程序
   - 程序：`d:\code\TradingAgents-CN\.venv\Scripts\python.exe`
   - 参数：`scripts/sync_market_news.py`
   - 起始于：`d:\code\TradingAgents-CN`

### 3. 使用后台 Worker（推荐）

**配置定时任务**：
在 `app/worker.py` 中添加定时任务，每小时自动同步新闻。

---

## 📊 验证修复

### 1. 检查数据库

```bash
python scripts/check_news_data.py
```

**预期输出**：
```
⏰ 最近 24 小时的新闻:
   数量: 45 条
```

### 2. 检查前端

1. 刷新仪表板页面
2. 查看市场快讯区域
3. 应该显示最新的 10 条新闻

### 3. 检查 API

```bash
curl -X GET "http://localhost:8000/api/news-data/latest?limit=10&hours_back=24" \
  -H "Authorization: Bearer <your_token>"
```

**预期响应**：
```json
{
  "success": true,
  "data": {
    "limit": 10,
    "hours_back": 24,
    "total_count": 10,
    "news": [
      {
        "title": "新闻标题",
        "source": "东方财富",
        "publish_time": "2025-10-23 10:00:00",
        "url": "https://..."
      },
      ...
    ]
  }
}
```

---

## 📝 总结

### 问题根源

- ❌ 数据库中的新闻数据过期（最新的是 12 天前）
- ❌ 前端默认查询最近 24 小时的新闻
- ❌ 查询结果为空，导致市场快讯区域显示为空

### 修复方案

1. ✅ **前端智能回退**（已实施）
   - 如果最近 24 小时没有新闻，则回溯 1 年
   - 确保即使没有最新新闻，也能显示内容

2. ✅ **同步最新新闻**（推荐）
   - 运行 `python scripts/sync_market_news.py`
   - 或在前端点击"同步市场新闻"按钮
   - 或调用 API：`POST /api/news-data/sync/start`

3. ✅ **定期同步**（长期解决）
   - 使用 Cron 或 Windows 任务计划程序
   - 或配置后台 Worker 定时任务
   - 建议每小时同步一次

### 修复效果

- ✅ 用户立即可以看到新闻内容（即使是旧新闻）
- ✅ 同步最新新闻后，显示实时新闻
- ✅ 定期同步确保新闻数据始终最新

---

## 🔗 相关文件

- `frontend/src/views/Dashboard/index.vue` - 仪表板组件
- `frontend/src/api/news.ts` - 新闻 API 模块
- `app/routers/news_data.py` - 新闻数据路由
- `app/services/news_data_service.py` - 新闻数据服务
- `scripts/sync_market_news.py` - 新闻同步脚本
- `scripts/check_news_data.py` - 新闻数据检查脚本

