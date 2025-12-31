# China Market Analyst (中国市场分析师)

**职责**: 作为专业的中国股市分析师，深度理解A股的独特性（如涨跌停制度、T+1交易、融资融券等）、中国经济政策（货币/财政政策）、行业板块轮动规律，以及监管环境（证监会政策、退市制度、注册制）和市场情绪。重点关注技术面、基本面、政策面、资金面和市场风格的分析。

**核心输出**: 专业的中文分析报告，重点突出中国股市的特色，并在报告末尾附上Markdown表格总结关键发现和投资建议。

**调用工具/接口**:
- `get_china_stock_data()` - 获取中国股票数据
- `get_china_market_overview()` - 获取中国市场概览
- `get_YFin_data()` - 获取Yahoo Finance数据 (备用数据源)

**数据获取流程**:
```python
# 1. 获取股票市场信息，自动识别A股/港股，并获取公司名称
market_info = StockUtils.get_market_info(ticker)
company_name = _get_company_name_for_china_market(ticker, market_info)

# 2. 调用中国股票数据工具和市场概览工具
chinese_stock_data = get_china_stock_data(ticker=ticker, date=current_date)
china_market_overview = get_china_market_overview(date=current_date)
# 备用数据源
yfin_data = get_YFin_data(ticker=ticker)
```

**数据处理与分析**:
`China Market Analyst` 基于 `get_china_stock_data`、`get_china_market_overview` 和 `get_YFin_data` 等工具获取的真实数据，结合中国股市涨跌停板限制、ST股票、科创板/创业板、国企改革、中美关系等特色，进行全面的技术面、基本面、政策面、资金面和市场风格分析。最终生成专业的中文分析报告，并在报告末尾附上Markdown表格总结关键发现和投资建议。

**降级方案**:
如果无法获取有效数据或分析失败，`China Market Analyst` 将提供带有失败原因的简化报告，例如：“中国市场分析失败：[失败原因]”。