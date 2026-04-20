# 货币单位使用指南
# Currency Unit Guide

## 📋 概述 / Overview

TradingAgents-CN 支持多种货币单位的模型定价，不同的 LLM 厂家使用不同的货币进行计费。

TradingAgents-CN supports multiple currency units for model pricing. Different LLM providers use different currencies for billing.

## 💱 货币单位规范 / Currency Standards

### 国内厂家 / Domestic Providers

以下厂家使用 **人民币（CNY）** 计费：

The following providers use **Chinese Yuan (CNY)** for billing:

| 厂家 Provider | 货币 Currency | 说明 Notes |
|--------------|---------------|-----------|
| 阿里百炼 (DashScope) | CNY | 通义千问系列模型 |
| DeepSeek | CNY | DeepSeek 系列模型 |
| 智谱AI (Zhipu) | CNY | GLM 系列模型 |
| 百度千帆 (Qianfan) | CNY | 文心一言系列 |
| 腾讯混元 (Tencent) | CNY | 混元系列模型 |
| 月之暗面 (Moonshot) | CNY | Kimi 系列模型 |
| 零一万物 (01.AI) | CNY | Yi 系列模型 |

### 国际厂家 / International Providers

以下厂家使用 **美元（USD）** 计费：

The following providers use **US Dollar (USD)** for billing:

| 厂家 Provider | 货币 Currency | 说明 Notes |
|--------------|---------------|-----------|
| OpenAI | USD | GPT 系列模型 |
| Google | USD | Gemini 系列模型 |
| Anthropic | USD | Claude 系列模型 |
| Mistral AI | USD | Mistral 系列模型 |
| Cohere | USD | Command 系列模型 |
| OpenRouter | USD | 多模型聚合平台 |
| SiliconFlow | USD | 硅基流动平台 |

## 💰 定价示例 / Pricing Examples

### 国内厂家定价示例 / Domestic Provider Example

```json
{
  "provider": "dashscope",
  "model_name": "qwen-turbo",
  "input_price_per_1k": 0.0003,
  "output_price_per_1k": 0.0006,
  "currency": "CNY"
}
```

**说明 / Explanation**:
- 输入：0.0003 元/1000 tokens
- 输出：0.0006 元/1000 tokens
- Input: ¥0.0003 per 1K tokens
- Output: ¥0.0006 per 1K tokens

### 国际厂家定价示例 / International Provider Example

```json
{
  "provider": "openai",
  "model_name": "gpt-4o",
  "input_price_per_1k": 0.005,
  "output_price_per_1k": 0.015,
  "currency": "USD"
}
```

**说明 / Explanation**:
- 输入：0.005 美元/1000 tokens
- 输出：0.015 美元/1000 tokens
- Input: $0.005 per 1K tokens
- Output: $0.015 per 1K tokens

## 🔄 汇率换算 / Currency Conversion

### 当前汇率参考 / Current Exchange Rate Reference

```
1 USD ≈ 7.2 CNY (2025年参考汇率)
1 USD ≈ 7.2 CNY (2025 Reference Rate)
```

### 成本对比示例 / Cost Comparison Example

假设使用 10,000 输入 tokens 和 2,000 输出 tokens：

Assuming 10,000 input tokens and 2,000 output tokens:

**通义千问 Turbo (CNY)**:
```
成本 = (10 × 0.0003) + (2 × 0.0006) = 0.0042 元
Cost = (10 × 0.0003) + (2 × 0.0006) = ¥0.0042
```

**GPT-4o (USD)**:
```
成本 = (10 × 0.005) + (2 × 0.015) = 0.08 美元 ≈ 0.576 元
Cost = (10 × 0.005) + (2 × 0.015) = $0.08 ≈ ¥0.576
```

## 📊 前端显示规范 / Frontend Display Standards

### 价格显示格式 / Price Display Format

在前端界面中，价格应该明确显示货币单位：

In the frontend interface, prices should clearly display the currency unit:

```vue
<!-- 正确示例 / Correct Example -->
<span>{{ price }} {{ currency }}/1K tokens</span>
<!-- 显示: 0.005 USD/1K tokens -->

<!-- 错误示例 / Wrong Example -->
<span>¥{{ price }}/1K tokens</span>
<!-- 不应该硬编码货币符号 / Should not hardcode currency symbol -->
```

### 货币符号映射 / Currency Symbol Mapping

```javascript
const currencySymbols = {
  'CNY': '¥',
  'USD': '$',
  'EUR': '€',
  'GBP': '£',
  'JPY': '¥'
}
```

## ⚙️ 配置说明 / Configuration Guide

### 添加新模型定价 / Adding New Model Pricing

在配置新模型时，请确保正确设置货币单位：

When configuring a new model, ensure the currency unit is set correctly:

```python
# Python 配置示例
PricingConfig(
    provider="openai",
    model_name="gpt-4o-mini",
    input_price_per_1k=0.00015,
    output_price_per_1k=0.0006,
    currency="USD"  # 国际厂家使用 USD
)

PricingConfig(
    provider="dashscope",
    model_name="qwen-max",
    input_price_per_1k=0.02,
    output_price_per_1k=0.06,
    currency="CNY"  # 国内厂家使用 CNY
)
```

### 前端配置示例 / Frontend Configuration Example

```typescript
// TypeScript 配置示例
const modelConfig = {
  provider: 'google',
  model_name: 'gemini-2.5-pro',
  input_price_per_1k: 0.00125,
  output_price_per_1k: 0.005,
  currency: 'USD'  // Google 使用 USD
}
```

## ⚠️ 注意事项 / Important Notes

### 1. 价格更新 / Price Updates

- 厂家价格可能随时调整，请定期检查官方定价
- Provider prices may change at any time, please check official pricing regularly
- 官方定价链接见 [MODEL_PRICING_GUIDE.md](./MODEL_PRICING_GUIDE.md)

### 2. 汇率波动 / Exchange Rate Fluctuations

- 汇率会影响国际厂家的实际成本
- Exchange rates affect the actual cost of international providers
- 建议定期更新汇率参考值
- It's recommended to update exchange rate references regularly

### 3. 支付方式 / Payment Methods

- **国内厂家**: 通常支持支付宝、微信支付、银行转账
- **Domestic Providers**: Usually support Alipay, WeChat Pay, bank transfer
- **国际厂家**: 通常需要国际信用卡或 PayPal
- **International Providers**: Usually require international credit cards or PayPal

### 4. 发票和税务 / Invoices and Taxes

- **国内厂家**: 可开具增值税发票
- **Domestic Providers**: Can issue VAT invoices
- **国际厂家**: 价格通常不含税，可能需要额外支付税费
- **International Providers**: Prices usually exclude taxes, additional taxes may apply

## 🔗 相关资源 / Related Resources

- [模型定价指南](./MODEL_PRICING_GUIDE.md) - 详细的模型定价信息
- [配置管理文档](./CONFIG_WIZARD.md) - 配置管理说明
- [使用统计文档](./USAGE_STATISTICS_AND_PRICING.md) - 使用统计和成本分析

---

**最后更新 / Last Updated**: 2025年10月 / October 2025  
**版本 / Version**: v1.0
