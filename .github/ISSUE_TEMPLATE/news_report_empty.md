---
title: "[Bug] CLI模式下新闻分析报告为空 — PyArrow正则兼容 + 缺少Fallback导致新闻获取失败"
labels: bug, news, pyarrow
---

## 问题描述

在 CLI 模式下运行 `TradingAgents-CN` 分析 A 股（如 `603565`），**新闻分析报告始终为空**。日志中新闻分析师只输出一行 "我将先调用工具获取最新新闻数据。" 就跳过了，生成的 `news_report.md` 文件内容无效。

## 环境信息

- Python 3.14.4
- akshare 1.18.60
- pandas (ArrowDtype / PyArrow 后端)
- MongoDB 未启用 (`USE_MONGODB_STORAGE=false`)
- 操作系统: macOS

## 根因分析

### 问题1: AKShare PyArrow 正则兼容问题（直接原因）

`get_stock_news_sync()` 调用 `ak.stock_news_em(symbol=symbol_6)`。

AKShare 的 `stock_news_em()` 在第116行执行 `str.replace(r"\\u3000", "", regex=True)`。在 PyArrow 后端（pandas ArrowDtype）下，正则引擎由 PyArrow 提供，它对 `\u` 转义序列的校验比 Python 的 `re` 模块更严格，抛出：

```
pyarrow.lib.ArrowInvalid: Invalid regular expression: invalid escape sequence: \u
```

### 问题2: 缺少 Fallback 机制（架构缺陷）

`get_stock_news_sync()` 在 `ak.stock_news_em()` 重试3次全部失败后，直接 `return None`。但项目已有的 `_get_stock_news_direct()` 方法（直接调用东方财富 API，绕开 AKShare 的 regex 清洗逻辑）**完全可以正常工作**，却从未被作为 fallback 调用。

### 问题3: 统一新闻工具绕弯路

`unified_news_tool.py` 的 `_get_a_share_news()` 在数据库（MongoDB）空时，先走 `_sync_news_from_akshare()`（异步线程+事件循环，超时30秒，模式脆弱），全部失败后才尝试东方财富。这个中间步骤徒增延迟且经常失败。

## 修复方案

### 修复1: `tradingagents/dataflows/providers/china/akshare.py`

`get_stock_news_sync()` 中，当 `ak.stock_news_em()` 重试3次全部失败后，不再直接返回 None，而是 fallback 到 `_get_stock_news_direct()` 直接调用东方财富 API。

### 修复2: `tradingagents/tools/unified_news_tool.py`

- **跳过脆弱步骤**: 数据库空时，不再调用 `_sync_news_from_akshare()`，直接走东方财富
- **增强日志**: 将所有 `logger.warning` 降级的失败日志升级为 `logger.error`，每个失败路径写清楚原因

## 验证

修复后，统一新闻工具成功获取10条东方财富新闻，返回 2990 字符：

```
✅ 603565 直接调用东方财富 API 获取新闻成功: 10 条
✅ 东方财富新闻获取成功: 2828 字符
统一新闻工具返回长度: 2990 字符
```

示例新闻标题：
- "中谷物流(603565).SH：2025年年报净利润为20.01亿元"
- "13.33亿元主力资金今日撤离交通运输板块"
- "52股今日获机构买入评级"
