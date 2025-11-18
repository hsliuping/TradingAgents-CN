# 报告详情页交易功能修复

## 问题描述

在报告详情页点击"应用到模拟交易"时，出现以下错误：

```
main.ts:52 全局错误: TypeError: account.cash.toFixed is not a function
    at Proxy.<anonymous> (ReportDetail.vue:624:34)
```

## 问题原因

后端 API 已经升级为支持多货币账户系统，返回的 `account.cash` 结构从单一数字变为多货币对象：

### 旧格式（单一货币）
```typescript
{
  cash: 1000000.00,
  realized_pnl: 0.00,
  positions_value: 500000.00,
  equity: 1500000.00
}
```

### 新格式（多货币）
```typescript
{
  cash: {
    CNY: 1000000.00,
    HKD: 0.00,
    USD: 0.00
  },
  realized_pnl: {
    CNY: 0.00,
    HKD: 0.00,
    USD: 0.00
  },
  positions_value: {
    CNY: 500000.00,
    HKD: 0.00,
    USD: 0.00
  },
  equity: {
    CNY: 1500000.00,
    HKD: 0.00,
    USD: 0.00
  }
}
```

前端代码直接调用 `account.cash.toFixed(2)` 导致错误，因为对象没有 `toFixed` 方法。

## 修复方案

### 1. 更新类型定义 (`frontend/src/api/paper.ts`)

添加多货币类型定义，并更新 `PaperAccountSummary` 接口以支持新旧格式：

```typescript
export interface CurrencyAmount {
  CNY: number
  HKD: number
  USD: number
}

export interface PaperAccountSummary {
  cash: CurrencyAmount | number  // 支持新旧格式
  realized_pnl: CurrencyAmount | number
  positions_value: CurrencyAmount
  equity: CurrencyAmount | number
  updated_at?: string
}
```

### 2. 添加辅助函数 (`frontend/src/views/Reports/ReportDetail.vue`)

创建 `getCashByCurrency` 函数，根据股票代码自动判断市场类型并返回对应货币的现金：

```typescript
// 辅助函数：根据股票代码获取对应货币的现金金额
const getCashByCurrency = (account: any, stockSymbol: string): number => {
  const cash = account.cash
  
  // 兼容旧格式（单一数字）
  if (typeof cash === 'number') {
    return cash
  }
  
  // 新格式（多货币对象）
  if (typeof cash === 'object' && cash !== null) {
    // 根据股票代码判断市场类型
    const marketType = getMarketByStockCode(stockSymbol)
    
    // 映射市场类型到货币
    const currencyMap: Record<string, keyof CurrencyAmount> = {
      'A股': 'CNY',
      '港股': 'HKD',
      '美股': 'USD'
    }
    
    const currency = currencyMap[marketType] || 'CNY'
    return cash[currency] || 0
  }
  
  return 0
}
```

### 3. 更新使用代码

在 `applyToTrading` 函数中：

**修复前：**
```typescript
const availableCash = account.cash
maxQuantity = Math.floor(availableCash / currentPrice / 100) * 100
```

**修复后：**
```typescript
const availableCash = getCashByCurrency(account, report.value.stock_symbol)
maxQuantity = Math.floor(availableCash / currentPrice / 100) * 100
```

在显示可用资金时：

**修复前：**
```typescript
`可用资金：${account.cash.toFixed(2)}元，最大可买：${maxQuantity}股`
```

**修复后：**
```typescript
`可用资金：${availableCash.toFixed(2)}元，最大可买：${maxQuantity}股`
```

## 市场类型判断逻辑

使用 `getMarketByStockCode` 函数自动识别股票市场：

- **A股**：6位数字（如 `600519`）→ 使用 CNY
- **港股**：4-5位数字或 `.HK` 后缀（如 `00700`、`0700.HK`）→ 使用 HKD
- **美股**：纯字母（如 `AAPL`）→ 使用 USD

## 测试验证

修复后应测试以下场景：

1. ✅ A股股票（如 600519）- 应使用 CNY 账户
2. ✅ 港股股票（如 00700）- 应使用 HKD 账户
3. ✅ 美股股票（如 AAPL）- 应使用 USD 账户
4. ✅ 兼容旧格式账户数据

## 相关文件

- `frontend/src/api/paper.ts` - 类型定义
- `frontend/src/views/Reports/ReportDetail.vue` - 报告详情页
- `frontend/src/utils/market.ts` - 市场类型判断工具
- `app/routers/paper.py` - 后端多货币账户实现

