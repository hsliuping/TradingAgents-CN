---
name: stock-info-explorer
description: >-
  A Yahoo Finance (yfinance) powered financial analysis tool.
  Get real-time quotes, generate high-resolution charts with moving averages + indicators (RSI/MACD/Bollinger/VWAP/ATR),
  summarize fundamentals, and run a one-shot report that outputs both a text summary and a Pro chart.
---

# Stock Information Explorer

This skill fetches OHLCV data from Yahoo Finance via `yfinance` and computes technical indicators **locally** (no API key required).

## Commands

### 1) Real-time Quotes (`price`)
```bash
uv run --script scripts/yf.py price TSLA
# shorthand
uv run --script scripts/yf.py TSLA
```

### 2) Fundamental Summary (`fundamentals`)
```bash
uv run --script scripts/yf.py fundamentals NVDA
```

### 3) ASCII Trend (`history`)
```bash
uv run --script scripts/yf.py history AAPL 6mo
```

### 4) Professional Chart (`pro`)
Generates a high-resolution PNG chart. By default it includes **Volume** and **Moving Averages (MA5/20/60)**.

```bash
# candle (default)
uv run --script scripts/yf.py pro 000660.KS 6mo

# line
uv run --script scripts/yf.py pro 000660.KS 6mo line
```

#### Indicators (optional)
Add flags to include indicator panels/overlays.

```bash
uv run --script scripts/yf.py pro TSLA 6mo --rsi --macd --bb
uv run --script scripts/yf.py pro TSLA 6mo --vwap --atr
```

- `--rsi` : RSI(14)
- `--macd`: MACD(12,26,9)
- `--bb`  : Bollinger Bands(20,2)
- `--vwap`: VWAP (cumulative for the selected range)
- `--atr` : ATR(14)

### 5) One-shot Report (`report`) ⭐
Prints a compact text summary (price + fundamentals + indicator signals) and automatically generates a **Pro chart with BB + RSI + MACD**.

```bash
uv run --script scripts/yf.py report 000660.KS 6mo
# output includes: CHART_PATH:/tmp/<...>.png
```

## Ticker Examples
- US stocks: `AAPL`, `NVDA`, `TSLA`
- KR stocks: `005930.KS`, `000660.KS`
- Crypto: `BTC-USD`, `ETH-KRW`
- Forex: `USDKRW=X`

## Notes / Limitations
- Indicators are **computed locally** from price data (Yahoo does not reliably provide precomputed indicator series).
- Data quality may vary by ticker/market (e.g., missing volume for some symbols).

---
Korean note: 실시간 시세 + 펀더멘털 + 기술지표(차트/요약)까지 한 번에 처리하는 종합 주식 분석 스킬입니다.
