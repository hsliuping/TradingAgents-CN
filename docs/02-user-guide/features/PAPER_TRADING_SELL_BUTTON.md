# 模拟交易持仓增加卖出按钮

## 📋 功能描述

在模拟交易页面的持仓表格中，增加"卖出"按钮，方便用户快速卖出持仓股票。

### 用户需求

用户希望在持仓表格的操作列中，除了"详情"和"分析"按钮外，还能有"卖出"按钮，实现一键卖出功能。

## ✅ 实现方案

### 1. 增加卖出按钮

在持仓表格的操作列中增加"卖出"按钮：

**修改前**：
```vue
<el-table-column label="操作" width="150">
  <template #default="{ row }">
    <el-button size="small" type="primary" link @click="viewStockDetail(row.code)">
      详情
    </el-button>
    <el-button size="small" type="success" link @click="goAnalysisWithCode(row.code)">
      分析
    </el-button>
  </template>
</el-table-column>
```

**修改后**：
```vue
<el-table-column label="操作" width="200">
  <template #default="{ row }">
    <el-button size="small" type="primary" link @click="viewStockDetail(row.code)">
      详情
    </el-button>
    <el-button size="small" type="success" link @click="goAnalysisWithCode(row.code)">
      分析
    </el-button>
    <el-button size="small" type="danger" link @click="sellPosition(row)">
      卖出
    </el-button>
  </template>
</el-table-column>
```

### 2. 实现卖出函数

```typescript
// 卖出持仓
async function sellPosition(position: any) {
  if (!position || !position.code) return
  
  try {
    // 确认卖出
    await ElMessageBox.confirm(
      `确认卖出 ${position.name || position.code}？\n\n当前持仓：${position.quantity} 股\n均价：${fmtPrice(position.avg_cost)}\n最新价：${fmtPrice(position.last_price)}`,
      '卖出确认',
      {
        confirmButtonText: '确认卖出',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 提交卖出订单
    const payload = {
      side: 'sell' as const,
      code: position.code,
      quantity: position.quantity
    }
    
    const res = await paperApi.placeOrder(payload)
    if (res.success) {
      ElMessage.success('卖出成功')
      await refreshAll()
    } else {
      ElMessage.error(res.message || '卖出失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('卖出失败:', error)
      ElMessage.error(error?.message || '卖出失败')
    }
  }
}
```

## 📊 功能展示

### 持仓表格

```
┌────────────────────────────────────────────────────────────────────────────┐
│ 持仓                                                                        │
├────────┬──────┬──────┬──────┬────────┬────────┬──────────────────────────┤
│ 代码   │ 名称 │ 数量 │ 均价 │ 最新价 │ 浮盈   │ 操作                     │
├────────┼──────┼──────┼──────┼────────┼────────┼──────────────────────────┤
│ 300750 │ 宁德 │ 100  │380.40│ 402.00 │2160.00 │ [详情] [分析] [卖出]    │
│        │ 时代 │      │      │        │        │                          │
├────────┼──────┼──────┼──────┼────────┼────────┼──────────────────────────┤
│ 601288 │ 农业 │28900 │ 6.67 │  6.67  │  0.00  │ [详情] [分析] [卖出]    │
│        │ 银行 │      │      │        │        │                          │
└────────┴──────┴──────┴──────┴────────┴────────┴──────────────────────────┘
```

### 卖出确认对话框

```
┌─────────────────────────────────────┐
│ ⚠️  卖出确认                         │
├─────────────────────────────────────┤
│                                      │
│ 确认卖出 农业银行？                  │
│                                      │
│ 当前持仓：28900 股                   │
│ 均价：6.67                           │
│ 最新价：6.67                         │
│                                      │
│         [取消]  [确认卖出]           │
└─────────────────────────────────────┘
```

## 🔧 技术实现

### 卖出流程

```
1. 用户点击"卖出"按钮
   ↓
2. 显示确认对话框
   - 股票名称/代码
   - 当前持仓数量
   - 均价
   - 最新价
   ↓
3. 用户确认
   ↓
4. 提交卖出订单
   - side: 'sell'
   - code: 股票代码
   - quantity: 持仓数量（全部卖出）
   ↓
5. 刷新页面数据
   - 账户信息
   - 持仓列表
   - 订单记录
```

### 关键代码

#### 1. 确认对话框

```typescript
await ElMessageBox.confirm(
  `确认卖出 ${position.name || position.code}？\n\n当前持仓：${position.quantity} 股\n均价：${fmtPrice(position.avg_cost)}\n最新价：${fmtPrice(position.last_price)}`,
  '卖出确认',
  {
    confirmButtonText: '确认卖出',
    cancelButtonText: '取消',
    type: 'warning'
  }
)
```

#### 2. 提交订单

```typescript
const payload = {
  side: 'sell' as const,
  code: position.code,
  quantity: position.quantity  // 全部卖出
}

const res = await paperApi.placeOrder(payload)
```

#### 3. 刷新数据

```typescript
if (res.success) {
  ElMessage.success('卖出成功')
  await refreshAll()  // 刷新账户、持仓、订单
}
```

## 🎯 功能特点

### 1. 一键卖出

- ✅ 点击"卖出"按钮即可快速卖出
- ✅ 自动填充持仓数量（全部卖出）
- ✅ 无需手动输入参数

### 2. 安全确认

- ✅ 显示完整的持仓信息
- ✅ 用户必须确认才能执行
- ✅ 可以取消操作

### 3. 实时反馈

- ✅ 卖出成功后显示提示
- ✅ 自动刷新页面数据
- ✅ 持仓列表实时更新

### 4. 错误处理

- ✅ 捕获异常并显示错误信息
- ✅ 取消操作不显示错误
- ✅ 完善的错误提示

## 🧪 测试步骤

### 测试1：正常卖出

1. 打开模拟交易页面
2. 在持仓表格中找到一个持仓
3. 点击"卖出"按钮
4. 验证确认对话框显示：
   - 股票名称正确
   - 持仓数量正确
   - 均价和最新价正确
5. 点击"确认卖出"
6. 验证：
   - 显示"卖出成功"提示
   - 持仓列表更新（该持仓消失）
   - 订单记录增加一条卖出订单
   - 账户现金增加

### 测试2：取消卖出

1. 点击"卖出"按钮
2. 在确认对话框中点击"取消"
3. 验证：
   - 对话框关闭
   - 没有执行卖出操作
   - 持仓不变

### 测试3：卖出失败

1. 模拟后端错误（如网络断开）
2. 点击"卖出"按钮并确认
3. 验证：
   - 显示错误提示
   - 持仓不变

### 测试4：多个持仓

1. 创建多个持仓
2. 依次卖出每个持仓
3. 验证：
   - 每次卖出都正确
   - 持仓列表逐个减少
   - 账户现金逐步增加

## 📝 修改的文件

### 前端

**文件**：`frontend/src/views/PaperTrading/index.vue`

**修改内容**：
1. ✅ 持仓表格操作列宽度：`150` → `200`
2. ✅ 增加"卖出"按钮
3. ✅ 新增 `sellPosition()` 函数

**代码行数**：约 40 行

## 🎉 完成效果

### 修改前

```
操作列：[详情] [分析]
```

### 修改后

```
操作列：[详情] [分析] [卖出]
```

### 用户体验提升

1. ✅ **操作更便捷**：无需手动下单，一键卖出
2. ✅ **信息更清晰**：确认对话框显示完整信息
3. ✅ **流程更简单**：3步完成卖出（点击 → 确认 → 完成）
4. ✅ **反馈更及时**：实时更新持仓和账户信息

## 🚀 后续优化建议

### 1. 部分卖出

支持用户输入卖出数量，而不是全部卖出：

```typescript
// 显示输入框让用户选择卖出数量
const { value: quantity } = await ElMessageBox.prompt(
  `当前持仓：${position.quantity} 股\n请输入卖出数量：`,
  '卖出',
  {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputPattern: /^\d+$/,
    inputErrorMessage: '请输入有效的数量',
    inputValue: String(position.quantity)  // 默认全部卖出
  }
)
```

### 2. 止盈止损

支持设置止盈止损价格：

```typescript
// 止盈：当价格达到目标价时自动卖出
// 止损：当价格跌破止损价时自动卖出
```

### 3. 批量卖出

支持选择多个持仓批量卖出：

```vue
<el-table :data="positions" @selection-change="handleSelectionChange">
  <el-table-column type="selection" width="55" />
  <!-- ... -->
</el-table>

<el-button @click="batchSell">批量卖出</el-button>
```

### 4. 卖出策略

支持不同的卖出策略：

- **全部卖出**：卖出所有持仓
- **卖出一半**：卖出50%持仓
- **卖出盈利部分**：只卖出盈利的部分
- **自定义数量**：用户输入卖出数量

## 📚 相关文档

- [模拟交易API](../app/routers/paper.py)
- [模拟交易页面](../frontend/src/views/PaperTrading/index.vue)
- [Element Plus MessageBox](https://element-plus.org/zh-CN/component/message-box.html)

