# Sector Analyst (板块分析师)

**职责**: 全面分析板块资金流向和涨跌幅，识别领涨/领跌板块、判断板块轮动特征，并结合政策分析识别热点主题。

**核心输出**: 严格遵循 JSON 格式，提供领涨/领跌板块、轮动趋势、热点主题、分析摘要、置信度和情绪评分。当分析受限时，会提供统一格式的降级报告。

**调用工具/接口**:
- `fetch_sector_rotation()` - 获取板块资金流向
- `fetch_index_constituents()` - 获取指数成分股
- `fetch_sector_news()` - 获取板块新闻
- `fetch_stock_sector_info()` - 查询股票所属板块

**数据获取流程**:
```python
# 1. 板块资金流向数据
provider = get_index_data_provider()
sector_data = await provider.get_sector_flows_async()

# 2. 特定板块深度分析
if target_sector:
    specific_data = await provider.akshare_provider.get_sector_fund_flow(
        sector_name=target_sector
    )

# 3. 数据维度
# - 领涨/领跌板块排行
# - 资金净流入/流出统计
# - 板块换手率数据
# - 个股所属板块定位
```

**数据处理与分析**:
`Sector Analyst` 会在不同 `session_type` (早盘/尾盘/盘后) 下，动态调整分析侧重点，结合板块资金流向、涨跌幅、政策报告等信息，进行领涨/领跌板块识别、轮动特征判断和热点主题挖掘。分析报告将严格遵循统一的 JSON 格式输出，即使数据获取受限，也会提供结构化的降级报告。

**统一输出 JSON 格式**:
```json
{
  "top_sectors": ["新能源车", "半导体", "消费电子"], # 领涨板块
  "bottom_sectors": ["房地产", "煤炭", "钢铁"],     # 领跌板块
  "rotation_trend": "成长→价值|价值→成长|大盘→小盘等", # 板块轮动趋势
  "hot_themes": ["AI", "新能源", "自主可控"],       # 热点主题
  "analysis_summary": "100字以内的精炼总结",         # 精炼分析总结
  "confidence": 0.0-1.0,                             # 对分析的置信度
  "sentiment_score": -1.0到1.0                         # 板块情绪评分
}
```

**降级报告 (Fallback Report) 示例**:
当工具调用失败、数据获取受限或无法生成有效分析时，`Sector Analyst` 会输出以下格式的降级报告：
```json
{
  "top_sectors": ["数据获取受限"],
  "bottom_sectors": ["数据获取受限"],
  "rotation_trend": "无法判断",
  "hot_themes": ["数据获取受限"],
  "analysis_summary": "由于数据获取限制，无法进行完整的板块分析。建议稍后重试。",
  "confidence": 0.3,
  "sentiment_score": 0.0
}
```

**分析总结逻辑**:
- 实时资金流向分析
- 板块轮动规律识别
- 政策与资金流向交叉验证
- 挖掘潜在热点主题