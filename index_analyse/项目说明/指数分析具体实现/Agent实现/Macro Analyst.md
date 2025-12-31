# Macro Analyst (宏观经济分析师)

**职责**: 分析宏观经济指标，判断经济周期阶段，评估流动性状况，并给出宏观情绪评分。

**核心输出**: 严格遵循 JSON 格式，提供经济周期、流动性、关键指标、分析摘要、置信度、情绪评分及数据说明。当分析受限时，会提供统一格式的降级报告。

**调用工具/接口**:
- `fetch_macro_data()` - 获取宏观经济数据 (GDP, CPI, PMI, M2, LPR等)

**数据获取流程**:
```python
# 1. 宏观数据获取
provider = get_index_data_provider()
macro_data = await provider.get_macro_data(end_date=query_date)

# 2. 数据源组成
# - GDP增长率 (季度数据)
# - CPI消费者物价指数 (月度数据)
# - PMI采购经理人指数 (月度数据)
# - M2货币供应量 (月度数据)
# - LPR贷款市场报价利率 (月度数据)
```

**数据处理与分析**:
为了确保分析的客观性和输出的一致性，`Macro Analyst` 必须严格按照预定义的 JSON 格式输出分析报告，即使在数据获取受限或无法进行有效分析的情况下，也会生成一个结构化的降级报告。

**统一输出 JSON 格式**:
```json
{
  "economic_cycle": "复苏|扩张|滞胀|衰退",       # 经济周期判断
  "liquidity": "宽松|中性|紧缩",               # 流动性评估
  "key_indicators": ["GDP增速X%", "CPI同比X%", "PMI=XX"], # 关键宏观指标
  "analysis_summary": "100字以内的精炼总结",     # 精炼总结
  "confidence": 0.0-1.0,                     # 对分析的置信度
  "sentiment_score": -1.0到1.0,              # 宏观情绪评分
  "data_note": "关于数据时效性的说明"           # 数据时效性说明
}
```

**降级报告 (Fallback Report) 示例**:
当工具调用失败、数据获取受限或无法生成有效分析时，`Macro Analyst` 会输出以下格式的降级报告：
```json
{
  "economic_cycle": "中性",
  "liquidity": "中性",
  "key_indicators": ["数据获取受限"],
  "analysis_summary": "【宏观分析降级】由于数据获取限制，无法进行完整的宏观分析。建议稍后重试。",
  "confidence": 0.3,
  "sentiment_score": 0.0,
  "data_note": "注意：宏观数据通常为历史数据，非实时数据。GDP、CPI等数据更新频率较低。"
}
```

**分析总结逻辑**:
- 结合经济周期、流动性、估值三维度
- 计算宏观情绪评分 (-1.0 到 1.0)
- 生成400字以上专业分析报告
- 提取JSON结构化数据供下游使用