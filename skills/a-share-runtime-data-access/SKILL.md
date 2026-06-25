---
name: a-share-runtime-data-access
description: Use when the task requires reading A-share stock data, financial data, valuation context, or querying local stock collections through core.skill_runtime runtime interfaces.
metadata: '{"nanobot":{"always":true}}'
---

# A-share Runtime Data Access

Use this skill when the user asks for A-share local data retrieval, quote lookup, financial period lookup, valuation context building, technical indicator lookup, or schema inspection through the project's public runtime interfaces and local tools.

## Scope

- Only handle A-share data in this workflow.
- Do not switch to multi-market logic unless the user explicitly changes scope.
- Prefer the project's public runtime interfaces over direct database access.

## First Read

Before fetching data, read these documents in order:

1. `docs/design/runtime-interfaces/skill-runtime-overview.md`
2. `docs/design/runtime-interfaces/local-data-access-design.md`
3. `docs/design/runtime-interfaces/project-access-and-governance.md`

If you need concrete function signatures or allowed collections, then read:

1. `core/skill_runtime/data_access.py`
2. `core/skill_runtime/project_access.py`
3. `core/skill_runtime/catalog.py`

## Runtime Rules

- Prefer `core.skill_runtime.data_access` for business-semantic data access.
- Use `core.skill_runtime.project_access` only when helper functions are insufficient or when inspecting schema / field coverage.
- Do not create `MongoClient` or import `pymongo` directly.
- Do not bypass `core.skill_runtime` by reading lower-level provider or database modules unless the user explicitly asks for code archaeology.
- For technical analysis, prefer the project's local technical tools and materialized snapshots over ad hoc indicator calculation.

## Preferred Helpers

For common A-share tasks, prefer these helpers first:

1. `get_stock_basic_info(symbol)`
2. `get_market_quotes(symbol)`
3. `get_latest_stock_price(symbol)`
4. `get_stock_daily_quotes(symbol, start_date, end_date)`
5. `get_stock_financial_periods(symbol)`
6. `get_stock_financial_data(symbol)`
7. `get_stock_valuation_context(symbol)`
8. `get_stock_news(symbol)`
9. `query_stock_collection(collection, ...)`
10. `inspect_stock_collection_schema(collection, ...)`

For technical-analysis tasks, prefer these entry points first:

1. `core.tools.implementations.market.technical_factor_bundle_tool.get_technical_factor_bundle_tool`
2. `core.tools.implementations.market.technical_indicators.get_technical_indicators`

Use the factor bundle first when the user needs structured MA20, RSI14, KDJ, or MACD values.
Use `get_technical_indicators` only when the user wants a readable technical-analysis report rather than a structured factor payload.

When checking freshness or explaining discrepancies, inspect these components in order:

1. `stock_technical_indicators` latest `trade_date`
2. `market_quotes` latest `trade_date`
3. `app/services/technical_indicator_materialization_service.py`
4. `app/main.py` technical indicator materialization job configuration

## How To Execute In Embedded Nanobot

The embedded nanobot runtime does not expose `core.skill_runtime` as a first-class tool yet.
When you need actual data, do this:

1. Read the design docs and target runtime module.
2. If the goal is only validation, inspection, or one-time probing, write a short temporary Python script under `temp/`.
3. Run the script with `C:\TradingAgentsCN\env\Scripts\python.exe` using the `exec` tool.
4. Summarize the returned data clearly for the user.

Do not treat a `temp/*.py` script as the final artifact when the logic is clearly reusable.
If the requested logic is parameterizable and should work for other stocks or other future runs, use the temp script only as a short validation probe and then promote the implementation into a reusable skill.

For technical-analysis tasks in embedded nanobot, use this execution pattern:

1. If the user wants structured technical values, call `get_technical_factor_bundle_tool` from a temp script.
2. If the user wants a textual technical interpretation, call `get_technical_indicators` from a temp script.
3. If the tool result conflicts with price data, compare `stock_technical_indicators.trade_date` against `market_quotes.trade_date` before concluding there is a bug.

For embedded runtime work, apply this boundary:

1. use temp scripts for fast verification and data access that the runtime does not yet expose directly
2. if the output is becoming a named reusable capability, convert it into a skill instead of leaving it in `temp/`
3. if the task is still exploratory and the reusable shape is not yet confirmed, say that explicitly

## Windows Execution Rule

On Windows, do not rely on inline `python -c` snippets for runtime verification.
Prefer writing a temporary `.py` file and then executing it. This avoids quoting and shell-expansion issues.

## Minimal Script Pattern

```python
from pathlib import Path
import sys

repo = Path(r"C:\TradingAgentsCN")
sys.path.insert(0, str(repo))

from core.skill_runtime.data_access import get_stock_basic_info

data = get_stock_basic_info("600519")
print(data)
```

## Helper Selection Guide

- If the user asks for one stock's snapshot, start with `get_stock_basic_info` or `get_stock_valuation_context`.
- If the user asks for multi-period fundamentals, start with `get_stock_financial_periods`.
- If the user asks for technical indicators, start with `get_technical_factor_bundle_tool`.
- If the user asks for a prose-style technical reading, use `get_technical_indicators` after confirming the requested date range.
- If the user asks for local collection availability or fields, start with `inspect_stock_collection_schema`.
- If the user asks for a direct collection sample, use `query_stock_collection` only after confirming the collection is publicly exposed in `catalog.py`.

## Response Expectations

- State which runtime interface you used.
- If data is empty, state whether the helper returned no records or the collection/helper is not exposed.
- When validation fails, report whether the problem is instruction gap, interface usage error, or missing underlying data.