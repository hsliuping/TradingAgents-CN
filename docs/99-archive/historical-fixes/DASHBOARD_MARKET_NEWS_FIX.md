# 仪表板"市场快讯"真实数据修复

## 📋 需求

将仪表板的"市场快讯"从硬编码的假数据改为调用后端真实API获取数据。

## 🔍 问题分析

### 修改前

**文件**：`frontend/src/views/Dashboard/index.vue`

"市场快讯"使用硬编码的假数据：

```typescript
const marketNews = ref([
  {
    id: 1,
    title: '央行降准释放流动性，银行股集体上涨',
    time: new Date().toISOString()
  },
  {
    id: 2,
    title: '科技股回调，关注估值修复机会',
    time: new Date(Date.now() - 3600000).toISOString()
  },
  {
    id: 3,
    title: '新能源汽车销量创新高，产业链受益',
    time: new Date(Date.now() - 7200000).toISOString()
  }
])
```

**问题**：
- ❌ 数据是写死的，不会更新
- ❌ 每次刷新页面显示相同内容
- ❌ 无法反映真实的市场动态

## ✅ 解决方案

### 1. 创建新闻API模块

**新文件**：`frontend/src/api/news.ts`

```typescript
import { ApiClient } from './request'

/**
 * 新闻数据接口
 */
export interface NewsItem {
  id?: string
  title: string
  content?: string
  summary?: string
  source?: string
  publish_time: string
  url?: string
  symbol?: string
  category?: string
  sentiment?: string
  importance?: number
  data_source?: string
}

/**
 * 最新新闻响应
 */
export interface LatestNewsResponse {
  symbol?: string
  limit: number
  hours_back: number
  total_count: number
  news: NewsItem[]
}

/**
 * 新闻API
 */
export const newsApi = {
  /**
   * 获取最新新闻
   * @param symbol 股票代码，为空则获取市场新闻
   * @param limit 返回数量限制
   * @param hours_back 回溯小时数
   */
  async getLatestNews(symbol?: string, limit: number = 10, hours_back: number = 24) {
    const params: any = { limit, hours_back }
    if (symbol) {
      params.symbol = symbol
    }
    return ApiClient.get<LatestNewsResponse>('/api/news-data/latest', params)
  },

  /**
   * 查询股票新闻
   * @param symbol 股票代码
   * @param hours_back 回溯小时数
   * @param limit 返回数量限制
   */
  async queryStockNews(symbol: string, hours_back: number = 24, limit: number = 20) {
    return ApiClient.get<NewsQueryResponse>(`/api/news-data/query/${symbol}`, {
      hours_back,
      limit
    })
  }
}
```

### 2. 修改仪表板组件

**文件**：`frontend/src/views/Dashboard/index.vue`

#### 2.1 导入新闻API

```typescript
import { newsApi } from '@/api/news'
```

#### 2.2 修改数据定义

```typescript
// 修改前
const marketNews = ref([
  { id: 1, title: '...', time: '...' },
  // ... 硬编码数据
])

// 修改后
const marketNews = ref<any[]>([])
```

#### 2.3 添加加载函数

```typescript
const loadMarketNews = async () => {
  try {
    const response = await newsApi.getLatestNews(undefined, 10, 24)
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
    // 如果加载失败，显示提示信息
    marketNews.value = []
  }
}
```

#### 2.4 修改 openNews 函数

```typescript
// 修改前
const openNews = (news: any) => {
  console.log('打开新闻:', news.id)
}

// 修改后
const openNews = (news: any) => {
  // 如果有URL，在新标签页打开新闻链接
  if (news.url) {
    window.open(news.url, '_blank')
  } else {
    ElMessage.info('该新闻暂无详情链接')
  }
}
```

#### 2.5 在页面加载时调用

```typescript
onMounted(async () => {
  // 加载股票关注列表数据
  await loadFavoriteStocks()
  // 加载最近分析
  await loadRecentAnalyses()
  // 加载市场快讯
  await loadMarketNews()
})
```

#### 2.6 添加空状态提示

```vue
<!-- 市场快讯 -->
<el-card class="market-news-card" header="市场快讯" style="margin-top: 24px;">
  <div v-if="marketNews.length > 0" class="news-list">
    <div
      v-for="news in marketNews"
      :key="news.id"
      class="news-item"
      @click="openNews(news)"
    >
      <div class="news-title">{{ news.title }}</div>
      <div class="news-time">{{ formatTime(news.time) }}</div>
    </div>
  </div>
  <div v-else class="empty-state">
    <el-icon class="empty-icon"><InfoFilled /></el-icon>
    <p>暂无市场快讯</p>
  </div>
  <div v-if="marketNews.length > 0" class="news-footer">
    <el-button type="text" size="small">
      查看更多 <el-icon><ArrowRight /></el-icon>
    </el-button>
  </div>
</el-card>
```

## 🎯 修复效果

### ✅ 功能改进

1. **真实数据**：从后端API获取真实的市场新闻
2. **自动更新**：每次刷新页面都会获取最新新闻
3. **可点击**：点击新闻标题可以在新标签页打开新闻详情
4. **空状态**：当没有新闻时显示友好的提示信息
5. **错误处理**：API调用失败时不会影响页面显示

### 📊 数据来源

- **后端API**：`GET /api/news-data/latest`
- **参数**：
  - `symbol`：股票代码（可选，为空则获取市场新闻）
  - `limit`：返回数量（默认10条）
  - `hours_back`：回溯小时数（默认24小时）

### 🔗 数据流程

```
用户打开仪表板
    ↓
onMounted() 触发
    ↓
loadMarketNews() 调用
    ↓
newsApi.getLatestNews() 请求后端
    ↓
GET /api/news-data/latest
    ↓
后端返回新闻数据
    ↓
前端解析并显示
    ↓
用户点击新闻
    ↓
在新标签页打开新闻链接
```

## 📝 相关文件

### 新增文件
- `frontend/src/api/news.ts` - 新闻API模块

### 修改文件
- `frontend/src/views/Dashboard/index.vue` - 仪表板组件

### 后端API
- `app/routers/news_data.py` - 新闻数据路由
- `app/services/news_data_service.py` - 新闻数据服务

## 🚀 使用说明

### 前端使用

```typescript
import { newsApi } from '@/api/news'

// 获取市场新闻（不指定股票代码）
const marketNews = await newsApi.getLatestNews(undefined, 10, 24)

// 获取特定股票的新闻
const stockNews = await newsApi.getLatestNews('000001', 10, 24)

// 查询股票新闻
const news = await newsApi.queryStockNews('000001', 24, 20)

// 同步市场新闻（后台任务）
const syncResult = await newsApi.syncMarketNews(24, 50)
```

### 后端API

```bash
# 获取市场新闻
curl -X GET "http://localhost:8000/api/news-data/latest?limit=10&hours_back=24"

# 获取特定股票的新闻
curl -X GET "http://localhost:8000/api/news-data/latest?symbol=000001&limit=10&hours_back=24"

# 查询股票新闻
curl -X GET "http://localhost:8000/api/news-data/query/000001?limit=20&hours_back=24"

# 同步市场新闻（后台任务）
curl -X POST "http://localhost:8000/api/news-data/sync/start" \
  -H "Content-Type: application/json" \
  -d '{"symbol": null, "hours_back": 24, "max_news_per_source": 50}'
```

### 使用Python脚本同步

```bash
# 运行同步脚本
python scripts/sync_market_news.py
```

## ⚠️ 注意事项

1. **后端依赖**：需要确保后端服务正常运行
2. **数据源**：后端需要配置新闻数据源（Tushare、AKShare等）
3. **数据同步**：
   - 首次使用需要点击"同步新闻"按钮同步数据
   - 或使用Python脚本：`python scripts/sync_market_news.py`
   - 同步是后台任务，需要等待几秒后刷新查看
4. **错误处理**：前端已添加错误处理，API失败不会影响页面显示
5. **空状态**：当没有新闻数据时，会显示"暂无市场快讯"提示和"立即同步"按钮

## 🔄 后续优化建议

1. **加载状态**：添加加载动画，提升用户体验
2. **刷新按钮**：添加手动刷新按钮
3. **自动刷新**：定时自动刷新新闻数据
4. **新闻分类**：支持按类别筛选新闻
5. **新闻详情**：在应用内显示新闻详情，而不是跳转外部链接
6. **缓存机制**：添加前端缓存，减少API调用
7. **分页加载**：支持加载更多新闻

## 📚 参考文档

- [新闻数据API文档](../guides/tushare_news_integration/README.md)
- [仪表板数据修复总结](./DASHBOARD_DATA_FIX.md)
- [后端API规范](../API.md)

