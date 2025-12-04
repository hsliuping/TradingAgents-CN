# 分析报告应用到模拟交易功能

## 📋 功能概述

将股票分析报告中的投资建议（买入/卖出）一键应用到模拟交易系统，实现从分析到交易的无缝衔接。

## 🎯 功能特点

### 1. 智能解析投资建议
- ✅ 自动识别买入/卖出操作
- ✅ 提取目标价格
- ✅ 获取置信度和风险等级
- ✅ 支持中英文建议格式

### 2. 智能计算交易参数
- ✅ **获取实时价格**：自动获取股票当前价格
- ✅ **买入**：根据可用资金自动计算
  - 建议使用20%可用资金
  - 以100股为单位
  - 显示最大可买数量
- ✅ **卖出**：根据当前持仓计算
  - 建议全部卖出
  - 检查持仓是否充足
- ✅ **用户可修改**：价格和数量都可以自由修改

### 3. 安全确认机制
- ✅ 交易前弹出确认对话框
- ✅ 显示完整交易信息
- ✅ 显示账户状态
- ✅ 用户确认后才执行

### 4. 完整交易记录
- ✅ 记录交易来源（analysis_id）
- ✅ 关联分析报告
- ✅ 便于后续回测和评估

## 🚀 使用方法

### 步骤1：查看分析报告
1. 进入"分析报告"页面
2. 点击任意报告查看详情

### 步骤2：应用到交易
1. 在报告详情页，点击右上角"应用到交易"按钮
2. 系统自动解析投资建议
3. 弹出交易确认对话框

### 步骤3：确认并修改交易信息
确认对话框显示：
- 股票代码
- 操作类型（买入/卖出）
- **目标价格**（预期最高价，仅供参考）
- **当前价格**（实时获取）
- **交易价格**（可修改，默认为当前价格）
- **交易数量**（可修改，100股为单位）
- 预计金额（自动计算）
- 置信度
- 风险等级
- 账户状态（可用资金/当前持仓）

### 步骤4：执行交易
1. 根据需要修改交易价格和数量
2. 确认信息无误后，点击"确认下单"
3. 系统提交订单到模拟交易系统
4. 自动跳转到模拟交易页面

## 📊 投资建议格式

### 标准格式
```
投资建议：买入
目标价格：7.8元（预期最高价）
决策依据：农业银行具备政策支持、稳定盈利和低估值优势...
```

**说明**：
- **目标价格**：预期股价可以涨到的最高价格（用于参考）
- **买入价格**：使用当前实时价格（系统自动获取）
- **用户可修改**：在确认对话框中可以修改实际交易价格和数量

### 支持的格式变体
```
操作: buy；目标价: 7.8；置信度: 0.75
```

```
建议：卖出
目标价：45.0元
```

## 🔧 技术实现

### 前端实现

#### 1. 解析投资建议
```typescript
const parseRecommendation = () => {
  const rec = report.value.recommendation || ''
  const traderPlan = report.value.reports?.trader_investment_plan || ''
  
  // 解析操作类型
  let action: 'buy' | 'sell' | null = null
  if (rec.includes('买入') || rec.toLowerCase().includes('buy')) {
    action = 'buy'
  } else if (rec.includes('卖出') || rec.toLowerCase().includes('sell')) {
    action = 'sell'
  }
  
  // 解析目标价格
  const priceMatch = rec.match(/目标价[格]?[：:]\s*([0-9.]+)/)
  const targetPrice = priceMatch ? parseFloat(priceMatch[1]) : null
  
  return { action, targetPrice, confidence, riskLevel }
}
```

#### 2. 获取实时价格
```typescript
// 获取当前实时价格
let currentPrice = 10 // 默认价格
try {
  const quoteRes = await stocksApi.getQuote(report.value.stock_symbol)
  if (quoteRes.success && quoteRes.data && quoteRes.data.price) {
    currentPrice = quoteRes.data.price
  }
} catch (error) {
  console.warn('获取实时价格失败，使用默认价格')
}
```

#### 3. 计算交易数量
```typescript
if (action === 'buy') {
  // 买入：使用20%可用资金，基于当前价格计算
  const availableCash = account.cash
  maxQuantity = Math.floor(availableCash / currentPrice / 100) * 100
  suggestedQuantity = Math.floor(maxQuantity * 0.2)
  suggestedQuantity = Math.max(100, suggestedQuantity)
} else {
  // 卖出：全部持仓
  suggestedQuantity = currentPosition.quantity
}
```

#### 4. 可编辑的确认对话框
```typescript
// 用户可修改的价格和数量
let tradePrice = currentPrice
let tradeQuantity = suggestedQuantity

await ElMessageBox({
  title: '确认交易',
  message: h('div', { style: 'line-height: 2;' }, [
    // 显示目标价格（仅供参考）
    h('p', [
      h('strong', '目标价格：'),
      h('span', { style: 'color: #E6A23C;' }, `${targetPrice.toFixed(2)}元`),
      h('span', { style: 'color: #909399; font-size: 12px;' }, '(预期最高价)')
    ]),
    // 显示当前价格
    h('p', [
      h('strong', '当前价格：'),
      h('span', `${currentPrice.toFixed(2)}元`)
    ]),
    // 可编辑的交易价格
    h(ElInputNumber, {
      modelValue: tradePrice,
      'onUpdate:modelValue': (val: number) => { tradePrice = val },
      min: 0.01,
      precision: 2,
      step: 0.01
    }),
    // 可编辑的交易数量
    h(ElInputNumber, {
      modelValue: tradeQuantity,
      'onUpdate:modelValue': (val: number) => { tradeQuantity = val },
      min: 100,
      max: maxQuantity,
      step: 100
    })
  ])
})
```

#### 5. 执行交易
```typescript
// 使用用户修改后的价格和数量
const orderRes = await paperApi.placeOrder({
  code: report.value.stock_symbol,
  side: action,
  quantity: tradeQuantity,  // 用户修改后的数量
  analysis_id: report.value.analysis_id
})
```

### 后端API

#### 下单接口
```
POST /api/paper/order
```

**请求参数**：
```json
{
  "code": "601288",
  "side": "buy",
  "quantity": 100,
  "analysis_id": "abc123"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "order": {
      "code": "601288",
      "side": "buy",
      "quantity": 100,
      "price": 7.8,
      "amount": 780.0,
      "status": "filled",
      "created_at": "2025-10-04T12:00:00Z"
    }
  }
}
```

## 📝 数据流程

```
用户查看报告
    ↓
点击"应用到交易"
    ↓
解析投资建议
    ↓
获取账户信息
    ↓
计算交易数量
    ↓
显示确认对话框
    ↓
用户确认
    ↓
调用下单API
    ↓
提交订单
    ↓
跳转到模拟交易页面
```

## ⚠️ 注意事项

### 1. 按钮显示条件
只有当报告包含明确的买入或卖出建议时，才显示"应用到交易"按钮。

### 2. 价格处理
- **目标价格**：从报告中解析，仅作为预期最高价参考
- **当前价格**：自动获取实时行情价格
- **交易价格**：默认使用当前价格，用户可以修改
- 如果无法获取实时价格，使用默认价格（10元）

### 3. 数量限制
- 买入：受可用资金限制
- 卖出：受当前持仓限制
- 最小交易单位：100股

### 4. 风险提示
- 这是模拟交易，不涉及真实资金
- 投资建议仅供参考
- 实际交易需谨慎决策

## 🔄 后续优化建议

### 1. 高级功能
- [ ] 支持自定义交易数量
- [ ] 支持设置止损价
- [ ] 支持分批建仓
- [ ] 支持定时交易

### 2. 风控功能
- [ ] 单笔交易金额限制
- [ ] 单日交易次数限制
- [ ] 持仓集中度检查
- [ ] 风险等级匹配

### 3. 交易计划
- [ ] 保存为交易计划草稿
- [ ] 设置触发条件
- [ ] 批量管理计划
- [ ] 计划执行提醒

### 4. 回测分析
- [ ] 记录交易来源
- [ ] 分析报告准确率
- [ ] 策略收益统计
- [ ] 优化建议算法

## 📚 相关文件

### 前端文件
- `frontend/src/views/Reports/ReportDetail.vue` - 报告详情页
- `frontend/src/api/paper.ts` - 模拟交易API

### 后端文件
- `app/routers/paper.py` - 模拟交易路由
- `app/routers/reports.py` - 报告路由

### 数据库集合
- `paper_accounts` - 模拟账户
- `paper_positions` - 持仓记录
- `paper_orders` - 订单记录
- `analysis_reports` - 分析报告

## 🎉 使用示例

### 示例1：买入操作

**报告内容**：
```
投资建议：买入
目标价格：7.8元（预期最高价）
置信度：0.85
风险等级：中等
```

**交易确认对话框**：
- 股票代码：601288
- 操作类型：买入
- 目标价格：7.8元（预期最高价，仅供参考）
- 当前价格：7.80元（实时获取）
- 交易价格：7.80元（可修改）
- 交易数量：2000股（可修改）
- 预计金额：15,600元（自动计算）
- 置信度：85.0%
- 风险等级：中等
- 可用资金：100,000元，最大可买：12800股

### 示例2：卖出操作

**报告内容**：
```
投资建议：卖出
目标价格：48.0元（预期最高价）
置信度：0.75
风险等级：高
```

**交易确认对话框**：
- 股票代码：002475
- 操作类型：卖出
- 目标价格：48.0元（预期最高价，仅供参考）
- 当前价格：47.50元（实时获取）
- 交易价格：47.50元（可修改）
- 交易数量：1000股（可修改）
- 预计金额：47,500元（自动计算）
- 置信度：75.0%
- 风险等级：高
- 当前持仓：1000股

## 📞 问题反馈

如有问题或建议，请联系开发团队或提交Issue。

---

**版本**：v0.1.16
**更新日期**：2025-10-04
**作者**：TradingAgents-CN Team

