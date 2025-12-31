# Technical Analyst (技术分析师)

**职责**: 基于量化技术指标分析指数趋势, 识别买卖信号, 并提供结构化的技术分析报告。

**核心输出**: 严格遵循 JSON 格式，提供趋势信号、置信度、关键支撑/阻力位、核心指标解读以及分析摘要和风险提示。当分析受限时，会提供统一格式的降级报告。

**调用工具/接口**:
- `fetch_technical_indicators()` - 获取技术指标数据
- AKShare历史数据接口
- 技术指标计算库

**数据获取流程**:
```python
# 1. 根据source_type选择数据源
if source_type == "concept":
    # 概念板块历史数据
    df_raw = ak.stock_board_concept_hist_em(
        symbol=real_symbol, period="daily", adjust="qfq"
    )
elif source_type == "industry":
    # 行业板块历史数据
    df_raw = ak.stock_board_industry_hist_em(
        symbol=real_symbol, period="daily", adjust="qfq"
    )
else:
    # 标准指数数据
    df = await provider.get_index_daily_async(ts_code=real_symbol)

# 2. 数据标准化
df = normalize_concept_data(df_raw)  # 统一OHLCV格式
```

**数据处理与分析**:
为了确保分析的客观性和结果的一致性, **Technical Analyst 必须严格按照预定义的 JSON 格式输出分析报告**。即使在数据获取受限或无法进行有效分析的情况下, 也会生成一个结构化的降级报告。

**统一输出 JSON 格式**:
```json
{
    "trend_signal": "BULLISH/BEARISH/NEUTRAL", # 整体趋势信号
    "confidence": 0.0-1.0,                     # 对当前信号的置信度
    "key_levels": {
        "support": "支撑位描述",                # 关键支撑位
        "resistance": "阻力位描述"              # 关键阻力位
    },
    "indicators": {
        "ma_alignment": "多头/空头/纠缠/未知",   # 均线排列状态
        "macd_signal": "金叉/死叉/背离/无效/未知", # MACD信号
        "rsi_status": "超买/超卖/中性/未知"       # RSI超买超卖状态
    },
    "analysis_summary": "200字以内的核心分析摘要", # 核心分析摘要
    "risk_warning": "主要风险提示"              # 主要风险提示
}
```

**降级报告 (Fallback Report) 示例**:
当工具调用失败、数据获取受限或无法生成有效分析时, `Technical Analyst` 会输出以下格式的降级报告：
```json
{
    "trend_signal": "NEUTRAL",
    "confidence": 0.0,
    "key_levels": { "support": "数据获取受限", "resistance": "数据获取受限" },
    "indicators": { "ma_alignment": "未知", "macd_signal": "未知", "rsi_status": "未知" },
    "analysis_summary": "【技术分析降级】由于数据获取限制或工具调用失败，无法进行完整的技术分析。请检查指数代码是否正确或稍后重试。",
    "risk_warning": "数据不完整"
}
```

**分析总结逻辑**:
- 量化指标客观分析，避免主观情绪
- 多时间框架趋势确认
- 关键技术位识别
- 生成明确的交易信号（BULLISH/BEARISH/NEUTRAL）
```python
# 1. 技术指标计算
df = add_all_indicators(df, close_col='close', high_col='high', low_col='low')

# 2. 趋势分析
ma_alignment = check_ma_alignment(df['ma5'], df['ma20'], df['ma60'])
macd_signal = check_macd_signal(df['macd_dif'], df['macd_dea'])

# 3. 超买超卖判断  
rsi_status = "超买" if df['rsi'].iloc[-1] > 80 else "超卖" if df['rsi'].iloc[-1] < 20 else "中性"

# 4. 支撑阻力位计算
support_level = calculate_support_level(df, window=20)
resistance_level = calculate_resistance_level(df, window=20)