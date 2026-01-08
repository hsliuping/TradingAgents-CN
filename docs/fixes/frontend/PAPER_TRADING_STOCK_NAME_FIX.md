# 模拟交易增加股票名称和股票详情页跳转

## 📋 问题描述

用户反馈模拟交易页面存在三个问题：

1. **缺少股票名称**：持仓和订单记录中只显示股票代码，没有显示股票名称
2. **跳转错误**：点击股票代码跳转到分析页面，而不是股票详情页
3. **分析参数错误**：点击"分析"按钮后，URL 参数格式不正确

### 用户期望

1. ✅ 在持仓和订单记录中显示股票名称
2. ✅ 点击股票代码跳转到股票详情页（`/stocks/:code`）
3. ✅ 点击"分析"按钮后，URL 格式为 `?stock=601288&market=A股`

## ✅ 修复方案

### 1. 增加股票名称列

#### 持仓表格

**修改前**：
```vue
<el-table-column label="代码" width="120">
  <template #default="{ row }">
    <el-link type="primary" @click="viewStockDetail(row.code)">
      {{ row.code }}
    </el-link>
  </template>
</el-table-column>
<el-table-column prop="quantity" label="数量" width="100" />
```

**修改后**：
```vue
<el-table-column label="代码" width="100">
  <template #default="{ row }">
    <el-link type="primary" @click="viewStockDetail(row.code)">
      {{ row.code }}
    </el-link>
  </template>
</el-table-column>
<el-table-column label="名称" width="100">
  <template #default="{ row }">{{ row.name || '-' }}</template>
</el-table-column>
<el-table-column prop="quantity" label="数量" width="100" />
```

#### 订单记录表格

**修改前**：
```vue
<el-table-column label="代码" width="120">
  <template #default="{ row }">
    <el-link type="primary" @click="viewStockDetail(row.code)">
      {{ row.code }}
    </el-link>
  </template>
</el-table-column>
<el-table-column prop="price" label="成交价" width="120" />
```

**修改后**：
```vue
<el-table-column label="代码" width="100">
  <template #default="{ row }">
    <el-link type="primary" @click="viewStockDetail(row.code)">
      {{ row.code }}
    </el-link>
  </template>
</el-table-column>
<el-table-column label="名称" width="100">
  <template #default="{ row }">{{ row.name || '-' }}</template>
</el-table-column>
<el-table-column prop="price" label="成交价" width="100" />
```

### 2. 批量获取股票名称

由于后端返回的持仓和订单数据中不包含股票名称，需要在前端批量获取：

```typescript
// 批量获取股票名称
async function fetchStockNames(items: any[]) {
  if (!items || items.length === 0) return
  
  // 获取所有唯一的股票代码
  const codes = [...new Set(items.map(item => item.code).filter(Boolean))]
  
  // 并行获取所有股票的名称
  await Promise.all(
    codes.map(async (code) => {
      try {
        const res = await stocksApi.getQuote(code)
        if (res.success && res.data && res.data.name) {
          // 更新所有包含该代码的项目
          items.forEach(item => {
            if (item.code === code) {
              item.name = res.data.name
            }
          })
        }
      } catch (error) {
        console.warn(`获取股票 ${code} 名称失败:`, error)
      }
    })
  )
}
```

**在获取持仓和订单后调用**：

```typescript
async function fetchPositions() {
  try {
    loading.value.positions = true
    const res = await paperApi.getPositions()
    if (res.success) {
      positions.value = res.data.items || []
      // 批量获取股票名称
      await fetchStockNames(positions.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取持仓失败')
  } finally {
    loading.value.positions = false
  }
}

async function fetchOrders() {
  try {
    loading.value.orders = true
    const res = await paperApi.getOrders(50)
    if (res.success) {
      orders.value = res.data.items || []
      // 批量获取股票名称
      await fetchStockNames(orders.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取订单失败')
  } finally {
    loading.value.orders = false
  }
}
```

### 3. 修改跳转逻辑

#### 3.1 查看股票详情

**修改前**：
```typescript
// 查看股票详情
function viewStockDetail(stockCode: string) {
  if (!stockCode) return
  // 跳转到分析页面（带股票代码）
  router.push({ name: 'SingleAnalysis', query: { code: stockCode } })
}
```

**修改后**：
```typescript
// 查看股票详情（跳转到股票详情页）
function viewStockDetail(stockCode: string) {
  if (!stockCode) return
  // 跳转到股票详情页
  router.push({ name: 'StockDetail', params: { code: stockCode } })
}
```

#### 3.2 跳转到分析页面

**修改前**：
```typescript
// 跳转到分析页面（带股票代码）
function goAnalysisWithCode(stockCode: string) {
  if (!stockCode) return
  router.push({ name: 'SingleAnalysis', query: { code: stockCode } })
}
// URL: /analysis/single?code=601288 ❌
```

**修改后**：
```typescript
// 跳转到分析页面（带股票代码和市场）
function goAnalysisWithCode(stockCode: string) {
  if (!stockCode) return
  // 根据股票代码判断市场
  const market = getMarketByCode(stockCode)
  router.push({ name: 'SingleAnalysis', query: { stock: stockCode, market } })
}

// 根据股票代码判断市场
function getMarketByCode(code: string): string {
  if (!code) return 'A股'

  // 6位数字 = A股
  if (/^\d{6}$/.test(code)) {
    return 'A股'
  }

  // 包含 .HK = 港股
  if (code.includes('.HK') || code.includes('.hk')) {
    return '港股'
  }

  // 其他 = 美股
  return '美股'
}
// URL: /analysis/single?stock=601288&market=A股 ✅
```

### 4. 导入必要的API

```typescript
import { stocksApi } from '@/api/stocks'
```

## 📊 效果展示

### 持仓表格

| 代码 | 名称 | 数量 | 均价 | 最新价 | 浮盈 | 操作 |
|------|------|------|------|--------|------|------|
| [300750](点击跳转) | 宁德时代 | 100 | 380.40 | 402.00 | 2160.00 | 详情 分析 |
| [601288](点击跳转) | 农业银行 | 28900 | 6.67 | 6.67 | 0.00 | 详情 分析 |

### 订单记录表格

| 时间 | 方向 | 代码 | 名称 | 成交价 | 数量 | 状态 | 关联分析 |
|------|------|------|------|--------|------|------|----------|
| 2025/10/04 11:40:53 | 买入 | [601288](点击跳转) | 农业银行 | 6.67 | 28900 | 已成交 | [查看报告] |
| 2025/09/28 22:29:39 | 买入 | [300750](点击跳转) | 宁德时代 | 380.40 | 100 | 已成交 | - |

## 🔧 技术实现

### 股票详情页路由

```typescript
{
  path: '/stocks',
  name: 'Stocks',
  component: () => import('@/layouts/BasicLayout.vue'),
  meta: {
    title: '股票详情',
    icon: 'TrendCharts',
    requiresAuth: true,
    hideInMenu: true,
    transition: 'fade'
  },
  children: [
    {
      path: ':code',
      name: 'StockDetail',
      component: () => import('@/views/Stocks/Detail.vue'),
      meta: {
        title: '股票详情',
        requiresAuth: true,
        hideInMenu: true,
        transition: 'fade'
      }
    }
  ]
}
```

### 获取股票名称API

使用 `stocksApi.getQuote()` 获取股票行情，其中包含股票名称：

```typescript
// API 定义
export interface QuoteResponse {
  code: string
  name?: string        // 股票名称
  market?: string
  price?: number
  change_percent?: number
  // ...
}

// 使用示例
const res = await stocksApi.getQuote('601288')
console.log(res.data.name)  // "农业银行"
```

### 性能优化

1. **并行请求**：使用 `Promise.all()` 并行获取所有股票名称
2. **去重**：使用 `Set` 去除重复的股票代码
3. **错误处理**：单个股票获取失败不影响其他股票

```typescript
// 获取所有唯一的股票代码
const codes = [...new Set(items.map(item => item.code).filter(Boolean))]

// 并行获取所有股票的名称
await Promise.all(
  codes.map(async (code) => {
    try {
      const res = await stocksApi.getQuote(code)
      // 更新名称
    } catch (error) {
      console.warn(`获取股票 ${code} 名称失败:`, error)
    }
  })
)
```

## 🧪 测试步骤

### 测试1：持仓表格显示股票名称

1. 打开模拟交易页面
2. 查看持仓表格
3. 验证每个持仓都显示股票名称
4. 验证股票名称正确（如 601288 显示"农业银行"）

### 测试2：订单记录显示股票名称

1. 查看订单记录表格
2. 验证每个订单都显示股票名称
3. 验证股票名称正确

### 测试3：点击股票代码跳转到详情页

1. 在持仓表格中点击股票代码（如 601288）
2. 验证跳转到股票详情页
3. 验证 URL 为 `/stocks/601288`
4. 验证页面显示完整的股票详情（K线图、基本面、新闻等）

5. 在订单记录中点击股票代码
6. 验证同样跳转到股票详情页

### 测试4：性能测试

1. 创建多个持仓（5-10个不同股票）
2. 刷新页面
3. 验证股票名称快速加载（并行请求）
4. 验证没有重复请求（去重机制）

## 📝 修改的文件

### 前端

**文件**：`frontend/src/views/PaperTrading/index.vue`

**修改内容**：
1. ✅ 导入 `stocksApi`
2. ✅ 持仓表格增加"名称"列
3. ✅ 订单记录表格增加"名称"列
4. ✅ 新增 `fetchStockNames()` 函数
5. ✅ 修改 `fetchPositions()` 调用 `fetchStockNames()`
6. ✅ 修改 `fetchOrders()` 调用 `fetchStockNames()`
7. ✅ 修改 `viewStockDetail()` 跳转到股票详情页

## 🎯 修复效果

### 修改前后对比

| 功能 | 修改前 | 修改后 |
|------|--------|--------|
| 持仓股票名称 | 无 ❌ | 显示名称 ✅ |
| 订单股票名称 | 无 ❌ | 显示名称 ✅ |
| 点击代码跳转 | 分析页面 ❌ | 股票详情页 ✅ |
| 详情页URL | `/analysis/single?code=xxx` | `/stocks/xxx` ✅ |
| 点击"分析"按钮 | `?code=601288` ❌ | `?stock=601288&market=A股` ✅ |
| 页面内容 | 分析表单 | 完整股票详情 ✅ |

### 用户体验提升

1. ✅ **信息更完整**：同时显示代码和名称，更易识别
2. ✅ **跳转更准确**：直接查看股票详情，而不是分析表单
3. ✅ **操作更便捷**：一键查看K线图、基本面、新闻等信息
4. ✅ **性能优化**：并行请求，快速加载

## 🚀 后续优化建议

### 1. 后端优化

在后端返回持仓和订单数据时，直接包含股票名称：

```python
# app/routers/paper.py
async def get_positions():
    positions = await db["paper_positions"].find(...).to_list(None)
    
    for p in positions:
        code6 = p.get("code")
        # 从 stock_basic_info 获取股票名称
        stock_info = await db["stock_basic_info"].find_one({"code": code6})
        p["name"] = stock_info.get("name") if stock_info else None
    
    return positions
```

**优点**：
- 减少前端请求次数
- 提高加载速度
- 简化前端逻辑

### 2. 缓存优化

在前端缓存股票名称，避免重复请求：

```typescript
// 股票名称缓存
const stockNameCache = new Map<string, string>()

async function getStockName(code: string): Promise<string> {
  // 检查缓存
  if (stockNameCache.has(code)) {
    return stockNameCache.get(code)!
  }
  
  // 获取名称
  const res = await stocksApi.getQuote(code)
  const name = res.data?.name || code
  
  // 存入缓存
  stockNameCache.set(code, name)
  
  return name
}
```

### 3. 加载状态优化

显示加载状态，提升用户体验：

```vue
<el-table-column label="名称" width="100">
  <template #default="{ row }">
    <span v-if="row.name">{{ row.name }}</span>
    <el-skeleton v-else :rows="1" animated />
  </template>
</el-table-column>
```

## 📚 相关文档

- [股票详情页](../frontend/src/views/Stocks/Detail.vue)
- [股票API](../frontend/src/api/stocks.ts)
- [模拟交易API](../app/routers/paper.py)
- [路由配置](../frontend/src/router/index.ts)

