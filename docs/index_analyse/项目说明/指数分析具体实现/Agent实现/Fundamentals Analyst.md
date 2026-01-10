# Fundamentals Analyst (基本面分析师)

**职责**: 全面分析股票基本面，包括公司基本信息，财务数据，盈利能力，以及PE、PB、PEG等估值指标，判断当前股价是被低估或高估，并提供合理价位区间和目标价位建议。

**核心输出**: 包含公司基本信息和财务数据分析，PE、PB、PEG等估值指标分析，当前股价是否被低估或高估的判断，合理价位区间和目标价位建议，以及基于基本面的投资建议。

**调用工具/接口**:
- `get_stock_fundamentals_unified()` - 获取统一股票基本面数据 (该工具内部会自动识别股票类型并调用相应数据源)

**数据获取流程**:
```python
# 1. 获取股票市场信息，自动识别A股/港股/美股
market_info = StockUtils.get_market_info(ticker)
# 2. 获取公司名称
company_name = _get_company_name_for_fundamentals(ticker, market_info)
# 3. 调用统一基本面数据工具，获取财务报表、估值比率等综合数据
combined_data = get_stock_fundamentals_unified(
    ticker=ticker,
    start_date=start_date, # 过去10天，确保数据覆盖
    end_date=current_date,
    curr_date=current_date
)
```

**数据处理与分析**:
`Fundamentals Analyst` 使用统一的 `get_stock_fundamentals_unified` 工具获取股票的综合基本面数据，包括财务报表和各种估值比率。分析师基于这些数据，对公司的基本信息、财务状况、盈利能力和估值进行深入分析，判断股票是被低估还是高估，并给出合理的价位区间、目标价位和投资建议（买入/持有/卖出）。

**降级方案**:
如果无法获取有效的基本面数据或分析失败，`Fundamentals Analyst` 将提供带有失败原因的简化报告，例如：“基本面分析失败：[失败原因]”或“由于数据获取限制，无法进行完整的分析。建议检查数据源连接或降低分析复杂度。”