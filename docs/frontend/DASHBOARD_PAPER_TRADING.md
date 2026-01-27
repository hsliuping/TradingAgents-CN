# 仪表板增加模拟交易账户信息

## 📋 功能描述

在仪表板页面的自选股卡片下方，增加模拟交易账户信息卡片，方便用户快速查看账户状态。

### 用户需求

用户希望在仪表板页面能够快速查看模拟交易账户的关键信息，包括：
- 现金余额
- 持仓市值
- 总资产
- 已实现盈亏

## ✅ 实现方案

### 1. 增加模拟交易账户卡片

在自选股卡片下方增加新的卡片，显示账户信息：

```vue
<!-- 模拟交易账户 -->
<el-card class="paper-trading-card" style="margin-top: 24px;">
  <template #header>
    <div class="card-header">
      <span>模拟交易账户</span>
      <el-button type="text" size="small" @click="goToPaperTrading">
        查看详情 <el-icon><ArrowRight /></el-icon>
      </el-button>
    </div>
  </template>

  <div v-if="paperAccount" class="paper-account-info">
    <div class="account-item">
      <div class="account-label">现金</div>
      <div class="account-value">¥{{ formatMoney(paperAccount.cash) }}</div>
    </div>
    <div class="account-item">
      <div class="account-label">持仓市值</div>
      <div class="account-value">¥{{ formatMoney(paperAccount.positions_value) }}</div>
    </div>
    <div class="account-item">
      <div class="account-label">总资产</div>
      <div class="account-value primary">¥{{ formatMoney(paperAccount.equity) }}</div>
    </div>
    <div class="account-item">
      <div class="account-label">已实现盈亏</div>
      <div class="account-value" :class="getPnlClass(paperAccount.realized_pnl)">
        {{ paperAccount.realized_pnl >= 0 ? '+' : '' }}¥{{ formatMoney(paperAccount.realized_pnl) }}
      </div>
    </div>
  </div>

  <div v-else class="empty-state">
    <el-icon class="empty-icon"><InfoFilled /></el-icon>
    <p>暂无账户信息</p>
    <el-button type="primary" size="small" @click="goToPaperTrading">
      查看模拟交易
    </el-button>
  </div>
</el-card>
```

### 2. 添加数据加载逻辑

```typescript
// 导入 API
import { paperApi, type PaperAccountSummary } from '@/api/paper'

// 定义数据
const paperAccount = ref<PaperAccountSummary | null>(null)

// 加载模拟交易账户信息
const loadPaperAccount = async () => {
  try {
    const response = await paperApi.getAccount()
    if (response.success && response.data) {
      paperAccount.value = response.data.account
    }
  } catch (error) {
    console.error('加载模拟交易账户失败:', error)
    paperAccount.value = null
  }
}

// 在 onMounted 中调用
onMounted(async () => {
  // ... 其他加载逻辑
  await loadPaperAccount()
})
```

### 3. 添加辅助函数

```typescript
// 跳转到模拟交易页面
const goToPaperTrading = () => {
  router.push('/paper')
}

// 格式化金额（添加千分位分隔符）
const formatMoney = (value: number) => {
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

// 获取盈亏样式类
const getPnlClass = (pnl: number) => {
  if (pnl > 0) return 'price-up'
  if (pnl < 0) return 'price-down'
  return 'price-neutral'
}
```

### 4. 添加样式

```scss
.paper-trading-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .paper-account-info {
    display: flex;
    flex-direction: column;
    gap: 16px;

    .account-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px;
      background-color: var(--el-fill-color-lighter);
      border-radius: 8px;

      .account-label {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }

      .account-value {
        font-size: 16px;
        font-weight: 600;
        color: var(--el-text-color-primary);

        &.primary {
          color: var(--el-color-primary);
          font-size: 18px;
        }

        &.price-up {
          color: #f56c6c;
        }

        &.price-down {
          color: #67c23a;
        }

        &.price-neutral {
          color: var(--el-text-color-regular);
        }
      }
    }
  }

  .empty-state {
    text-align: center;
    padding: 20px 0;

    .empty-icon {
      font-size: 48px;
      color: var(--el-text-color-placeholder);
      margin-bottom: 12px;
    }

    p {
      color: var(--el-text-color-secondary);
      margin-bottom: 16px;
    }
  }
}
```

## 📊 功能展示

### 仪表板布局

```
┌─────────────────────────────────────────────────────────────────────┐
│ 欢迎使用 TradingAgents-CN                                            │
│ 现代化的多智能体股票分析学习平台，辅助你掌握更全面的市场视角分析股票                │
│                                                                      │
│ [快速分析] [股票筛选]                                                │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬──────────────────────────────────────┐
│ 快速操作                      │ 股票研究列表                            │
│                              │ ┌──────────────────────────────────┐ │
│ [单股分析]                    │ │ 300750  宁德时代  ¥402.00  +5.68%│ │
│ [批量分析]                    │ │ 601288  农业银行  ¥6.67    +0.00%│ │
│ [股票筛选]                    │ └──────────────────────────────────┘ │
│ [任务中心]                    │                                      │
│                              │ 模拟交易账户                          │
│ 最近分析                      │ ┌──────────────────────────────────┐ │
│ ┌──────────────────────────┐ │ │ 现金          ¥2,329,863.00      │ │
│ │ 601288 农业银行 已完成    │ │ │ 持仓市值      ¥1,002,160.00      │ │
│ │ 601398 工商银行 已完成    │ │ │ 总资产        ¥7,691,970.00      │ │
│ └──────────────────────────┘ │ │ 已实现盈亏    +¥0.00             │ │
│                              │ └──────────────────────────────────┘ │
│                              │                                      │
│                              │ 多数据源同步                          │
│                              │ 市场快讯                              │
└──────────────────────────────┴──────────────────────────────────────┘
```

### 账户信息卡片

```
┌─────────────────────────────────────┐
│ 模拟交易账户          [查看详情 →]  │
├─────────────────────────────────────┤
│                                      │
│ ┌─────────────────────────────────┐ │
│ │ 现金          ¥2,329,863.00     │ │
│ └─────────────────────────────────┘ │
│                                      │
│ ┌─────────────────────────────────┐ │
│ │ 持仓市值      ¥1,002,160.00     │ │
│ └─────────────────────────────────┘ │
│                                      │
│ ┌─────────────────────────────────┐ │
│ │ 总资产        ¥7,691,970.00     │ │ (蓝色高亮)
│ └─────────────────────────────────┘ │
│                                      │
│ ┌─────────────────────────────────┐ │
│ │ 已实现盈亏    +¥0.00            │ │ (红色/绿色)
│ └─────────────────────────────────┘ │
│                                      │
└─────────────────────────────────────┘
```

### 空状态

```
┌─────────────────────────────────────┐
│ 模拟交易账户          [查看详情 →]  │
├─────────────────────────────────────┤
│                                      │
│            📊                        │
│                                      │
│        暂无账户信息                  │
│                                      │
│      [查看模拟交易]                  │
│                                      │
└─────────────────────────────────────┘
```

## 🎯 功能特点

### 1. 快速查看

- ✅ 在仪表板直接查看账户信息
- ✅ 无需跳转到模拟交易页面
- ✅ 关键信息一目了然

### 2. 信息完整

- ✅ 现金余额
- ✅ 持仓市值
- ✅ 总资产（高亮显示）
- ✅ 已实现盈亏（带颜色标识）

### 3. 交互便捷

- ✅ 点击"查看详情"跳转到模拟交易页面
- ✅ 空状态提供快速入口
- ✅ 金额格式化（千分位分隔符）

### 4. 视觉友好

- ✅ 卡片式布局
- ✅ 背景色区分
- ✅ 盈亏颜色标识（红涨绿跌）
- ✅ 总资产蓝色高亮

## 🔧 技术实现

### 数据流

```
1. 页面加载
   ↓
2. onMounted() 调用 loadPaperAccount()
   ↓
3. 调用 paperApi.getAccount()
   ↓
4. 获取账户信息
   {
     account: {
       cash: 2329863.00,
       positions_value: 1002160.00,
       equity: 7691970.00,
       realized_pnl: 0.00
     }
   }
   ↓
5. 更新 paperAccount.value
   ↓
6. 渲染账户信息卡片
```

### 金额格式化

```typescript
// 输入：2329863.00
// 输出：2,329,863.00

const formatMoney = (value: number) => {
  return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}
```

### 盈亏颜色

```typescript
// 盈利：红色 (#f56c6c)
// 亏损：绿色 (#67c23a)
// 持平：灰色

const getPnlClass = (pnl: number) => {
  if (pnl > 0) return 'price-up'      // 红色
  if (pnl < 0) return 'price-down'    // 绿色
  return 'price-neutral'              // 灰色
}
```

## 📝 修改的文件

### 前端

**文件**：`frontend/src/views/Dashboard/index.vue`

**修改内容**：
1. ✅ 增加模拟交易账户卡片
2. ✅ 导入 `paperApi` 和类型定义
3. ✅ 新增 `paperAccount` 数据
4. ✅ 新增 `loadPaperAccount()` 函数
5. ✅ 新增 `goToPaperTrading()` 函数
6. ✅ 新增 `formatMoney()` 函数
7. ✅ 新增 `getPnlClass()` 函数
8. ✅ 在 `onMounted()` 中调用加载函数
9. ✅ 添加样式

**代码行数**：约 100 行

## 🧪 测试步骤

### 测试1：正常显示

1. 打开仪表板页面：`http://localhost:5173/dashboard`
2. 验证自选股卡片下方显示"模拟交易账户"卡片
3. 验证显示以下信息：
   - 现金（带千分位分隔符）
   - 持仓市值（带千分位分隔符）
   - 总资产（蓝色高亮，带千分位分隔符）
   - 已实现盈亏（带颜色标识）

### 测试2：金额格式化

1. 验证金额显示格式：
   - `2329863.00` → `¥2,329,863.00`
   - `1002160.00` → `¥1,002,160.00`
   - `7691970.00` → `¥7,691,970.00`

### 测试3：盈亏颜色

1. 验证盈亏颜色：
   - 盈利（> 0）：红色
   - 亏损（< 0）：绿色
   - 持平（= 0）：灰色

### 测试4：跳转功能

1. 点击"查看详情"按钮
2. 验证跳转到模拟交易页面：`/paper`

### 测试5：空状态

1. 模拟账户信息加载失败
2. 验证显示空状态：
   - 图标
   - "暂无账户信息"文字
   - "查看模拟交易"按钮
3. 点击按钮验证跳转

### 测试6：响应式

1. 调整浏览器窗口大小
2. 验证卡片布局正常
3. 验证在移动端显示正常

## 🎉 完成效果

### 修改前

```
仪表板右侧：
- 股票研究列表
- 多数据源同步
- 市场快讯
- 使用提示
```

### 修改后

```
仪表板右侧：
- 股票研究列表
- 模拟交易账户 ✨ (新增)
- 多数据源同步
- 市场快讯
- 使用提示
```

### 用户体验提升

1. ✅ **信息集中**：在仪表板直接查看账户状态
2. ✅ **操作便捷**：一键跳转到模拟交易页面
3. ✅ **视觉清晰**：卡片式布局，信息层次分明
4. ✅ **数据直观**：金额格式化，盈亏颜色标识

## 🚀 后续优化建议

### 1. 实时更新

支持自动刷新账户信息：

```typescript
// 每30秒自动刷新
setInterval(async () => {
  await loadPaperAccount()
}, 30000)
```

### 2. 持仓概览

显示持仓数量和浮动盈亏：

```vue
<div class="account-item">
  <div class="account-label">持仓数量</div>
  <div class="account-value">{{ positions.length }} 只</div>
</div>
<div class="account-item">
  <div class="account-label">浮动盈亏</div>
  <div class="account-value" :class="getPnlClass(unrealized_pnl)">
    {{ unrealized_pnl >= 0 ? '+' : '' }}¥{{ formatMoney(unrealized_pnl) }}
  </div>
</div>
```

### 3. 收益率

显示总收益率：

```vue
<div class="account-item">
  <div class="account-label">总收益率</div>
  <div class="account-value" :class="getPnlClass(return_rate)">
    {{ return_rate >= 0 ? '+' : '' }}{{ return_rate.toFixed(2) }}%
  </div>
</div>
```

### 4. 图表展示

使用图表展示资产分布：

```vue
<div class="asset-chart">
  <el-progress
    :percentage="(positions_value / equity * 100)"
    :format="() => `持仓 ${(positions_value / equity * 100).toFixed(1)}%`"
  />
</div>
```

## 📚 相关文档

- [模拟交易API](../app/routers/paper.py)
- [仪表板页面](../frontend/src/views/Dashboard/index.vue)
- [Element Plus Card](https://element-plus.org/zh-CN/component/card.html)

