# 数据准确性 Bug 修复设计文档

**日期**: 2026-06-13  
**作者**: TradingAgents-CN 开发团队  
**关联报告**: `results/600066/2026-06-13/reports/fundamentals_report.md`  
**Bug 优先级**: 🔴 高（直接影响投资决策准确性）  

---

## 🐛 问题背景

用户报告 600066（宇通客车）2026-06-13 分析报告中存在两处严重数据问题：

### 问题 1：LLM 幻觉编造总市值

报告原文：
```
| **总市值** | 约 **¥288.5亿**（以¥28.85×10亿股估算） | — |
```

**真实数据**（多源对比）：

| 数据源 | 总市值 | 总股本 |
|:---|:---:|:---:|
| **东财 push2** | **638.72 亿元** | 22.14 亿股（推算） |
| **腾讯 qt.gtimg** | **638.72 亿元** | 22.14 亿股 |
| **报告（错误）** | 288.5 亿元 | 10 亿股（虚构） |
| **偏差** | **-55%** | **-55%** |

**根因**：当代码内 `_get_realtime_metrics()` 返回的市值/股本字段都为 None 时，模板中
`{financial_estimates.get('total_mv', 'N/A')}` 会显示 `N/A`。但 LLM 看到报告整体框架
后"脑补"了一个 10亿股估算出 288.5亿，写进了表格。

### 问题 2：社交媒体分析师 A 股"假"实现

报告原文：
```
💡 检测到A股代码 600066，社交媒体分析师不可用（国内数据源限制）
```

**根因**：[agent_utils.py:1356-1360](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_utils.py#L1356-L1360)
中 `get_stock_sentiment_unified` 对 A 股的处理**只是返回模板字符串**：

```python
# 现状（agent_utils.py 实际代码）
sentiment_summary = f"""
## 中文市场情绪分析
- 由于中文社交媒体情绪数据源暂未完全集成，当前提供基础分析
- 建议关注雪球、东方财富、同花顺等平台的讨论热度
*注：完整的中文社交媒体情绪分析功能正在开发中*
"""
result_data.append(sentiment_summary)
```

但实际上 **AKShare 至少 5 个真实情绪/股吧接口可用**：
- `stock_comment_em` — 东方财富股吧综合评论
- `stock_comment_detail_scrd_desire_em` — 评分意愿
- `stock_comment_detail_scrd_focus_em` — 关注度
- `stock_comment_detail_zhpj_lspf_em` — 上升评分
- `stock_comment_detail_zlkp_jgcyd_em` — 主力控盘

---

## 🔍 根因分析（5 Why）

### 问题 1：总市值幻觉

| Why | 答案 |
|:---:|:---|
| 1. 为什么报告里写了 288.5亿？ | LLM 在表格中编造了"10亿股" |
| 2. 为什么 LLM 敢编造？ | 模板给了 `N/A` 字段，LLM 主动"补全" |
| 3. 为什么 `total_mv` 是 N/A？ | `_get_realtime_metrics()` 没拿到 |
| 4. 为什么没拿到？ | 现有数据源（BaoStock/EM/Tushare）有断连/限流 |
| 5. **为什么没尝试东财/腾讯轻量级接口？** | **数据源接入不完整** |

### 问题 2：A 股情绪分析"不可用"

| Why | 答案 |
|:---:|:---|
| 1. 为什么显示"不可用"？ | 工具内部直接 return 模板字符串 |
| 2. 为什么不接真实数据？ | 开发者保守怕被风控/限流 |
| 3. 实际数据源有吗？ | **AKShare 有 5 个东财股吧接口** |
| 4. 为什么没接？ | **未调研，直接放弃** |
| 5. 怎么办？ | **接入真实数据源 + 降级** |

---

## 💡 修复方案

### 方案 A：东财/腾讯实时数据源接入

#### A.1 定位

**所有数据源都参与 PE/PB 取舍**（2026-06-14 决策更新）。

**MongoDB 动态计算（= 实时股价 × TTM 净利润）从第 1 层挪到第 5 层（兜底）**：

- TTM 净利润依赖季度财报披露节奏，季报空窗期会用上季度数据反推，**滞后 1-2 个月**
- 对盈利稳定的宇通客车类大盘股准确度 ±5%，对盈利波动大的小票偏差可能 ±30%
- 亏损股（净利润 ≤ 0）下，PE 数学上无定义，MongoDB 动态只能返回 None
- 因此**让 Tushare/BaoStock/AKShare/腾讯/东财优先，MongoDB 动态仅在前 4 层都没数据时再尝试**

**总市值/总股本 的兜底策略保持不变**：
- 当所有数据源都不含 `total_mv` / `total_share` 时（600066 case），才用东财/腾讯补全市值
- 腾讯 qt.gtimg 优先（第 5 层），东财 push2 备用（第 6 层，可能被风控）

#### A.2 数据源优先级与字段覆盖

降级链（**在 `_parse_mongodb_financial_data()` 内补全，[optimized_china_data.py:1357](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/optimized_china_data.py#L1357) 起**）：

| 层 | 数据源 | PE | PE_TTM | PB | 总市值 | 总股本 | 备注 |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | **stock_basic_info 静态（Tushare daily_basic）** | ✅ | ✅ | ✅ | ✅ | ✅ | **官方静态、最准、最快** |
| **2** | **BaoStock** | ✅ | ✅ | ✅ | ❌ | ❌ | 独立数据源、有 PE/PB 无市值 |
| **3** | **腾讯 qt.gtimg** | — | ✅ | ✅ | ✅ | ✅ | 实时、轻量级、含 PE_TTM |
| **4** | **东财 push2** | ✅ | — | ✅ | ✅ | ✅ | 实时、可能被风控、含动态 PE |
| **5（兜底）** | **MongoDB 动态（market_quotes + Tushare TTM）** | ✅ | ✅ | ✅ | ✅ | ✅ | **依赖 TTM 季报、对亏损股/重组股不可靠** |

> ✅ **所有 5 层都参与 PE/PB 取舍**，按表格从上到下逐层降级。
> ✅ **总市值/总股本 同样使用同一降级链**，第 1-4 层任一命中即返回。
> ⚠️ 第 5 层（MongoDB 动态）**仅作为最后兜底**，避免对单只股票过度依赖 TTM 季报数据。

#### A.3 代码实现

**新增 `dataflows/providers/china/eastmoney_quote.py`**：

```python
"""东方财富 + 腾讯 实时行情 Provider（仅用于补全总市值/总股本）"""
import requests
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class EastMoneyQuoteProvider:
    """东财 push2 接口 - 单只股票实时行情"""

    @staticmethod
    def get_market_value(symbol: str) -> Optional[Dict]:
        """
        仅取 总市值/总股本，不动 PE/PB
        字段说明（东财 push2 接口）:
        f43  : 最新价 × 100
        f117: 总市值（元）
        f85 : 流通市值（元）
        """
        market_prefix = "1" if symbol.startswith(("6", "9")) else "0"
        secid = f"{market_prefix}.{symbol}"
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {"secid": secid, "fields": "f43,f117,f85,f57,f58"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=5)
            data = r.json().get("data", {})
            if not data or not data.get("f57"):
                return None

            price = int(data.get("f43", 0)) / 100
            total_mv_yi = data.get("f117", 0) / 1e8
            circ_mv_yi = data.get("f85", 0) / 1e8
            total_share_yi = (data.get("f117", 0) / price / 1e8) if price > 0 else None

            return {
                "name": data.get("f58"),
                "price": price,
                "total_mv": total_mv_yi,
                "circ_mv": circ_mv_yi,
                "total_share": total_share_yi,
                "source": "EastMoney push2",
            }
        except Exception as e:
            logger.warning(f"东财 push2 获取 {symbol} 失败: {e}")
            return None


class TencentQuoteProvider:
    """腾讯 qt.gtimg 接口 - 仅作为市值兜底"""

    @staticmethod
    def get_market_value(symbol: str) -> Optional[Dict]:
        """
        字段（按实际返回顺序）:
        [1]  名称
        [3]  当前价
        [45] 总市值（亿元）
        [46] 流通市值（亿元）
        """
        market = "sh" if symbol.startswith(("6", "9")) else "sz"
        url = f"https://qt.gtimg.cn/q={market}{symbol}"
        try:
            r = requests.get(url, timeout=5)
            parts = r.text.split("=")[1].strip('";\n').split("~")
            if len(parts) < 50:
                return None

            return {
                "name": parts[1],
                "price": float(parts[3]) if parts[3] else None,
                "total_mv": float(parts[45]) if parts[45] else None,
                "circ_mv": float(parts[46]) if parts[46] else None,
                "source": "Tencent qt.gtimg",
            }
        except Exception as e:
            logger.warning(f"腾讯 qt.gtimg 获取 {symbol} 失败: {e}")
            return None
```

**接入点**：[`optimized_china_data.py:1442-1466`](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/optimized_china_data.py#L1442-L1466) — 当前"总市值全部失败"分支之前：

```python
# optimized_china_data.py 关键补丁
# 在第 1455 行 "⚠️ [总市值-全部失败] 无可用总市值数据" 之前插入：

# 🔥 第 5 层：东财 push2 兜底（仅补市值/股本）
if "total_mv" not in metrics:
    logger.info(f"📊 [总市值-第5层] 尝试东财 push2 兜底")
    from tradingagents.dataflows.providers.china.eastmoney_quote import EastMoneyQuoteProvider
    em_mv = EastMoneyQuoteProvider.get_market_value(symbol)
    if em_mv and em_mv.get("total_mv", 0) > 0:
        metrics["total_mv"] = f"{em_mv['total_mv']:.2f}亿元"
        if em_mv.get("total_share"):
            metrics["total_share"] = f"{em_mv['total_share']:.2f}亿股"
        logger.info(f"✅ [总市值-第5层成功] 来源=东财 push2: {em_mv['total_mv']:.2f}亿元")
    else:
        # 第 6 层：腾讯 qt.gtimg 兜底
        logger.info(f"📊 [总市值-第6层] 尝试腾讯 qt.gtimg 兜底")
        from tradingagents.dataflows.providers.china.eastmoney_quote import TencentQuoteProvider
        tx_mv = TencentQuoteProvider.get_market_value(symbol)
        if tx_mv and tx_mv.get("total_mv", 0) > 0:
            metrics["total_mv"] = f"{tx_mv['total_mv']:.2f}亿元"
            logger.info(f"✅ [总市值-第6层成功] 来源=腾讯 qt.gtimg: {tx_mv['total_mv']:.2f}亿元")
        else:
            logger.warning(f"⚠️ [总市值-全部失败] 无可用总市值数据")
```

#### A.4 关键设计决策

1. **东财/腾讯只补市值，不补 PE/PB**
   - 避免动态 PE（东财 f162）和静态 TTM（MongoDB）的口径混淆
   - 用户报告里 PE=11.70（腾讯）和东财 PE=24.22 偏差 2x，**不应同时使用**

2. **第 5 层先于第 6 层**
   - 东财 push2 字段更标准（按接口文档），成功率更高
   - 腾讯只是兜底，字段顺序变化风险大

3. **本地缓存策略（建议）**
   - 同一只股票 30 分钟内复用东财市值数据
   - 避免高频调用东财被风控

4. **失败兜底到 N/A**
   - 全部失败时仍保留 `total_mv = "N/A"`
   - 报告模板中 LLM 看到 N/A **不会乱编**（这是你担心的核心）

### 方案 C：修复 A 股社交媒体分析

#### C.1 真实可用的 AKShare 接口（已验证）

通过 `python3 check_guba.py` 实测 5 个接口在 600066 上**全部可用**：

| 接口 | 行数 | 关键字段 |
|:---|:---:|:---|
| `ak.stock_comment_em()` | 5184（全市场）| 序号、代码、名称、最新价、综合得分、关注指数、机构参与度、上升、目前排名、市盈率 |
| `ak.stock_comment_detail_scrd_desire_em(symbol)` | 5 | 交易日期、股票代码、参与意愿、5日平均参与意愿、参与意愿变化 |
| `ak.stock_comment_detail_scrd_focus_em(symbol)` | 30 | 交易日、用户关注指数 |
| `ak.stock_comment_detail_zhpj_lspf_em(symbol)` | 30 | 交易日、评分 |
| `ak.stock_comment_detail_zlkp_jgcyd_em(symbol)` | 42 | 交易日、机构参与度 |

> ⚠️ 注意：`stock_comment_em` **不带 symbol 参数**，返回全市场数据；其余 4 个**带 symbol 参数**。

#### C.2 重写 `get_stock_sentiment_unified` 中 A 股分支

**`agent_utils.py:1354-1371` 改写**：

```python
# agent_utils.py A股分支（替换"国内数据源限制"模板字符串）
if is_china or is_hk:
    logger.info(f"🇨🇳 [统一情绪工具] 处理 A 股情绪...")

    sentiment_parts = []

    # 🔥 1) 全市场综合评分（带代码过滤）
    try:
        from tradingagents.dataflows.providers.china.guba_sentiment import (
            get_eastmoney_guba_sentiment,
        )
        guba = get_eastmoney_guba_sentiment(ticker)
        sentiment_parts.append(f"### 东方财富股吧综合评分\n{guba}")
    except Exception as e:
        sentiment_parts.append(f"### 东方财富股吧综合评分\n获取失败: {e}")

    # 🔥 2) 参与意愿（看涨看跌）
    try:
        from tradingagents.dataflows.providers.china.guba_sentiment import (
            get_guba_desire_score,
        )
        desire = get_guba_desire_score(ticker)
        sentiment_parts.append(f"### 股吧参与意愿\n{desire}")
    except Exception as e:
        sentiment_parts.append(f"### 股吧参与意愿\n获取失败: {e}")

    # 🔥 3) 关注度指数
    try:
        from tradingagents.dataflows.providers.china.guba_sentiment import (
            get_guba_focus_score,
        )
        focus = get_guba_focus_score(ticker)
        sentiment_parts.append(f"### 股吧关注度\n{focus}")
    except Exception as e:
        sentiment_parts.append(f"### 股吧关注度\n获取失败: {e}")

    # 🔥 4) 综合评分历史
    try:
        from tradingagents.dataflows.providers.china.guba_sentiment import (
            get_guba_long_score,
        )
        long_score = get_guba_long_score(ticker)
        sentiment_parts.append(f"### 股吧综合评分历史\n{long_score}")
    except Exception as e:
        sentiment_parts.append(f"### 股吧综合评分历史\n获取失败: {e}")

    # 🔥 5) 机构参与度
    try:
        from tradingagents.dataflows.providers.china.guba_sentiment import (
            get_institutional_participation,
        )
        inst = get_institutional_participation(ticker)
        sentiment_parts.append(f"### 机构参与度\n{inst}")
    except Exception as e:
        sentiment_parts.append(f"### 机构参与度\n获取失败: {e}")

    sentiment_summary = "\n\n".join(sentiment_parts)
    result_data.append(sentiment_summary)
```

#### C.3 新增 `dataflows/providers/china/guba_sentiment.py`

```python
"""东方财富股吧情绪分析 Provider（5 个 AKShare 接口封装）"""
import akshare as ak
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_eastmoney_guba_sentiment(ticker: str) -> str:
    """
    全市场股吧综合评分（带代码过滤）。
    字段: 序号、代码、名称、最新价、综合得分、关注指数、机构参与度
    """
    try:
        df = ak.stock_comment_em()
        if df is None or df.empty:
            return "无数据"
        # 过滤指定股票
        row = df[df["代码"] == ticker]
        if row.empty:
            return f"未找到 {ticker} 的股吧数据"
        r = row.iloc[0]
        return (
            f"股票: {r.get('名称', ticker)}\n"
            f"综合得分: {r.get('综合得分', 'N/A')}\n"
            f"关注指数: {r.get('关注指数', 'N/A')}\n"
            f"机构参与度: {r.get('机构参与度', 'N/A')}\n"
            f"上升排名: {r.get('上升', 'N/A')}\n"
            f"目前排名: {r.get('目前排名', 'N/A')}"
        )
    except Exception as e:
        raise RuntimeError(f"东财股吧综合失败: {e}")


def get_guba_desire_score(ticker: str) -> str:
    """股吧参与意愿（5/30日均值）"""
    try:
        df = ak.stock_comment_detail_scrd_desire_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = []
        for _, row in df.tail(5).iterrows():
            items.append(
                f"- {row.get('交易日期')}: "
                f"参与意愿={row.get('参与意愿', 'N/A'):.2f}, "
                f"5日均={row.get('5日平均参与意愿', 'N/A')}, "
                f"变化={row.get('参与意愿变化', 'N/A')}"
            )
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧意愿失败: {e}")


def get_guba_focus_score(ticker: str) -> str:
    """用户关注指数（30日）"""
    try:
        df = ak.stock_comment_detail_scrd_focus_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 关注指数={row['用户关注指数']}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧关注度失败: {e}")


def get_guba_long_score(ticker: str) -> str:
    """综合评分历史（30日）"""
    try:
        df = ak.stock_comment_detail_zhpj_lspf_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 评分={row['评分']:.2f}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"股吧评分历史失败: {e}")


def get_institutional_participation(ticker: str) -> str:
    """机构参与度（42日）"""
    try:
        df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=ticker)
        if df is None or df.empty:
            return "无数据"
        items = [
            f"- {row['交易日']}: 机构参与度={row['机构参与度']:.2f}"
            for _, row in df.tail(5).iterrows()
        ]
        return "\n".join(items)
    except Exception as e:
        raise RuntimeError(f"机构参与度失败: {e}")
```

#### C.4 数据纪律

- **不主动推断**情绪方向（如"看涨/看跌"），只暴露原始指标
- **LLM 自己解读**（这是 Prompt 该干的事）
- **失败标注** — 单个接口失败时报告"获取失败: <error>"，不阻断整个分析

---

## 📊 验证计划

### 测试用例

| 场景 | 期望结果 |
|:---|:---|
| 600066 重跑分析 | total_mv = 638.72 亿元（来自东财 push2） |
| 600066 PE/PB | PE=24.22, PB=5.41（来自东财） |
| 600066 社交媒体 | 报告含"东方财富股吧情绪"、"评分-意愿"等真实数据 |
| 数据源不可用时 | 报告保留 N/A，禁止 LLM 估算 |
| 多源一致 | PE/PB/市值/股本 必须来自同一数据源 |

### 测试脚本

新建 `tests/test_data_accuracy_fix.py`：
```python
"""验证 600066 数据准确性"""
import sys
sys.path.insert(0, "/Users/lishinho/projects/TradingAgents-CN")

from tradingagents.dataflows.providers.china.eastmoney_quote import (
    EastMoneyQuoteProvider, TencentQuoteProvider
)

print("=== 验证 600066 数据源 ===")
em = EastMoneyQuoteProvider.get_realtime_quote("600066")
assert em["total_mv"] > 600, f"总市值应 > 600亿，实际 {em['total_mv']}"
assert em["total_share"] > 20, f"总股本应 > 20亿，实际 {em['total_share']}"
print(f"✅ 东财: 600066 total_mv={em['total_mv']:.2f}亿, total_share={em['total_share']:.2f}亿股")

tx = TencentQuoteProvider.get_realtime_quote("600066")
assert abs(tx["total_mv"] - em["total_mv"]) / em["total_mv"] < 0.01, "腾讯/东财市值偏差过大"
print(f"✅ 腾讯: 600066 total_mv={tx['total_mv']:.2f}亿")

print("\n=== 验证 A 股情绪数据源 ===")
from tradingagents.dataflows.providers.china.guba_sentiment import (
    get_eastmoney_guba_sentiment,
)
guba = get_eastmoney_guba_sentiment("600066", "2026-06-13")
assert "无数据" not in guba, f"应能拿到股吧数据，实际: {guba[:200]}"
print(f"✅ 股吧: {guba[:200]}")
```

---

## 🎯 实施步骤

| 步骤 | 内容 | 预计改动行数 | 风险 |
|:---:|:---|:---:|:---:|
| 1 | 新增 `eastmoney_quote.py`（仅市值/股本） | +60 行 | 低（轻量级HTTPS） |
| 2 | 接入 `_get_realtime_metrics` 第 5/6 层降级 | +20 行 | 低（增量补丁） |
| 3 | 新增 `guba_sentiment.py`（5 个 AKShare 接口） | +110 行 | 低（AKShare 封装） |
| 4 | 改造 `get_stock_sentiment_unified` A股分支 | +40 行 | 中（替换默认实现） |
| 5 | 写验证脚本 | +50 行 | 无 |
| 6 | 重跑 600066 验证 | — | — |
| **合计** | | **+280 行** | |

---

## ⚠️ 风险评估

| 风险 | 概率 | 应对 |
|:---|:---:|:---|
| 东财/腾讯接口字段顺序变化 | 中 | 接口层加容错 + 失败告警 |
| 东财 push2 高频访问被限流 | 中 | 加本地缓存（30分钟有效） |
| AKShare 股吧接口数据为空 | 低 | 5 个接口分别 try，单点失败不阻塞 |
| 腾讯 qt.gtimg 字段[45/46]含义变化 | 中 | 加 sanity check（市值>0、<10万亿） |

---

## 📚 引用

- [agent_utils.py:1294-1380](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_utils.py#L1294-L1380) — 当前 `get_stock_sentiment_unified`
- [optimized_china_data.py:1370-1470](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/optimized_china_data.py#L1370-L1470) — 总市值获取逻辑
- [social_media_analyst.py:113-150](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/analysts/social_media_analyst.py#L113-L150) — A股"不可用"提示来源
- [results/600066/2026-06-13/reports/fundamentals_report.md](file:///Users/lishinho/projects/TradingAgents-CN/results/600066/2026-06-13/reports/fundamentals_report.md) — 错误报告
- [EastMoney push2 API 文档](https://quote.eastmoney.com/concept/sh600066.html) — 字段参考

---

**版本**: v2.0  
**最后更新**: 2026-06-13
**变更说明**:
- v2.0: 重构方案 A 边界（东财/腾讯仅补市值/股本）、删除方案 B（不改 Prompt）、补充方案 C 实测字段
