# 价格显示格式化更新

## 更新概述

在大模型配置的价格显示中，统一使用6位小数格式，确保价格显示的精确性，特别是对于非常低价格的模型。

## 更新内容

### 1. 添加价格格式化函数

在 `frontend/src/views/Settings/ConfigManagement.vue` 中添加了 `formatPrice` 函数：

```typescript
// 🆕 格式化价格显示（保持6位小数）
const formatPrice = (price: number | undefined | null) => {
  if (price === undefined || price === null) {
    return '0.000000'
  }
  return price.toFixed(6)
}
```

### 2. 更新价格显示

在模型卡片的定价信息部分，使用 `formatPrice` 函数格式化价格：

**修改前：**
```vue
<span class="pricing-value">
  {{ model.input_price_per_1k || 0 }} {{ model.currency || 'CNY' }}/1K
</span>
```

**修改后：**
```vue
<span class="pricing-value">
  {{ formatPrice(model.input_price_per_1k) }} {{ model.currency || 'CNY' }}/1K
</span>
```

## 显示效果

### 修改前
- 输入: `0.003 USD/1K`
- 输出: `0.015000000000000001 USD/1K`

### 修改后
- 输入: `0.003000 USD/1K`
- 输出: `0.015000 USD/1K`

## 注意事项

1. **输入精度提升**：在编辑对话框中，价格输入框支持 6 位小数（`:precision="6"`），步进值为 `0.000001`
2. **显示精度统一**：在列表显示时，统一使用6位小数，确保价格显示的精确性
3. **空值处理**：当价格为 `undefined` 或 `null` 时，显示为 `0.000000`
4. **适用场景**：特别适合显示非常低价格的模型，如某些免费或极低价格的模型（如 `0.000001 USD/1K`）

## 测试建议

1. 测试不同价格值的显示：
   - 整数价格：`1` → `1.000000`
   - 一位小数：`0.5` → `0.500000`
   - 两位小数：`0.15` → `0.150000`
   - 多位小数：`0.003` → `0.003000`
   - 极低价格：`0.000001` → `0.000001`
   - 空值：`null` → `0.000000`

2. 测试编辑功能：
   - 输入 `0.000001`，保存后显示为 `0.000001`
   - 输入 `0.0015`，保存后显示为 `0.001500`
   - 输入 `0.015`，保存后显示为 `0.015000`
   - 输入 `1.5`，保存后显示为 `1.500000`

## 相关文件

- `frontend/src/views/Settings/ConfigManagement.vue`：模型配置列表页面
- `frontend/src/views/Settings/components/LLMConfigDialog.vue`：模型配置编辑对话框

