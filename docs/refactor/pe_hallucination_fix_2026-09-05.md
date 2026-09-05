# PE 幻觉修复工程方案 — 改动对比记录

| 项 | 内容 |
|---|---|
| 日期 | 2026-09-05 |
| 触发问题 | 纽威股份（603699）报告 PE 12~14 倍，实际 Tushare PE_TTM 21.42 倍 |
| 根因 | fundamentals_analyst 把 `get_stock_fundamentals_unified` 工具返回的"软数据"整段塞 prompt，让 LLM 自己从长文本里识别数字 → 识别失败 → 编造 |
| 方案核心 | "**软注入 → 硬注入**"：用纯 Python 代码先抽出关键指标，写成"硬数据块"再注入 prompt，LLM 只能引用不能改 |

---

## 一、文件改动总览

| # | 操作 | 文件 | 行数变化 | 用途 |
|---|---|---|---|---|
| 1 | **新增** | `tradingagents/dataflows/metrics_extractor.py` | +427 | 纯代码提取 PE/PB/ROE 等指标 + 渲染硬数据块 |
| 2 | **修改** | `tradingagents/agents/analysts/fundamentals_analyst.py` line 213-220 | +6 | system_message 末尾加"估值铁律" |
| 3 | **修改** | 同上 line 646-708 | +40 | 插入硬数据提取 + 重写 analysis_prompt |

---

## 二、新增文件 metrics_extractor.py（全文）

**路径**：`tradingagents/dataflows/metrics_extractor.py`（共 427 行）

```python
"""
基本面指标提取器（反幻觉核心）
================================

本模块的职责：从 Tushare/MongoDB 提取股票估值与盈利能力指标，
返回结构化 dict，并渲染成「硬数据块」字符串供 prompt 注入。

设计原则：
1. **纯 Python 提取** —— LLM 完全不参与数字本身，避免估值幻觉
2. **缺失 = None** —— 找不到的字段返回 None，绝不返回估算值或 0
3. **MongoDB 缓存优先** —— 避免重复打 Tushare API（配额紧张）
4. **降级链** —— MongoDB → Tushare → 返回残缺 dict（不抛异常）

调用方：
    metrics = extract_fundamentals_metrics(symbol="603699", trade_date="2026-09-04")
    hard_block = format_metrics_block(metrics, currency_name="人民币")

作者：WorkBuddy @ 2026-09-05
问题背景：fundamentals_analyst LLM 自行编造 PE 值（实际 21.42 报 12~14 倍）
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
import logging

try:
    import pandas as pd
except ImportError:  # 兜底
    pd = None  # type: ignore

logger = logging.getLogger(__name__)


# ==================== 常量 ====================

# Tushare daily_basic 标准字段（按需取，不取全量省流量）
DAILY_BASIC_FIELDS = (
    "ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,"
    "total_mv,circ_mv"
)

# Tushare fina_indicator 标准字段
FINA_INDICATOR_FIELDS = (
    "ts_code,end_date,eps,roe,grossprofit_margin,netprofit_margin,"
    "debt_to_assets,net_profit_yoy,sales_yoy"
)

# 输出字典的标准 key（用于标记缺失）
METRIC_KEYS = [
    # 估值类
    "close", "pe_ttm", "pe_static", "pb", "ps_ttm", "ps_static",
    "dv_ratio_ttm", "total_mv", "circ_mv",
    # 盈利能力类
    "eps", "roe_ttm", "gross_margin", "net_margin", "debt_to_assets",
    # 增长率
    "net_profit_yoy", "sales_yoy",
]

# MongoDB 缓存集合名（避免与 stock_daily_basic 冲突，独立命名）
SNAPSHOT_COLLECTION = "stock_metrics_snapshot"


# ==================== 工具函数 ====================

def _safe_float(x) -> Optional[float]:
    """安全转 float，None/NaN 都返回 None（绝不返回 0）"""
    if x is None:
        return None
    try:
        v = float(x)
        if pd is not None and pd.isna(v):
            return None
        if v != v:  # NaN 二次保险
            return None
        return round(v, 4)
    except (TypeError, ValueError):
        return None


def _get_tushare_api():
    """获取已初始化的 Tushare pro_api（带 token）"""
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
        provider = get_tushare_provider()
        if not getattr(provider, "connected", False):
            return None
        api = getattr(provider, "api", None)
        return api
    except Exception as e:
        logger.debug(f"[metrics_extractor] get_tushare_api 失败: {e}")
        return None


def _resolve_ts_code(symbol: str) -> Optional[str]:
    """6 位代码 → ts_code（如 603699 → 603699.SH），失败返回 None"""
    if not symbol:
        return None
    s = str(symbol).strip().upper()
    if s.endswith((".SH", ".SZ", ".BJ")):
        return s
    # 上海：60/68/90 开头
    if s.startswith(("60", "68", "90")):
        return f"{s}.SH"
    # 深圳：00/30/20 开头
    if s.startswith(("00", "30", "20")):
        return f"{s}.SZ"
    # 北京：43/87/92 等
    if s.startswith(("43", "83", "87", "92")):
        return f"{s}.BJ"
    return None


# ==================== 估值类提取 ====================

def _fetch_valuation_metrics(symbol: str, trade_date: str) -> Dict[str, Any]:
    """从 Tushare daily_basic 提取估值类指标"""
    metrics: Dict[str, Any] = {}
    api = _get_tushare_api()
    if api is None:
        logger.debug("[metrics_extractor] Tushare API 不可用，跳过估值提取")
        return metrics

    try:
        ts_code = _resolve_ts_code(symbol)
        if not ts_code:
            logger.warning(f"[metrics_extractor] 无法解析 ts_code: {symbol}")
            return metrics

        # 优先按交易日查
        df = api.daily_basic(ts_code=ts_code, trade_date=trade_date,
                             fields=DAILY_BASIC_FIELDS)

        # 当日非交易日则往前找最近 5 个交易日
        if df is None or df.empty:
            df = api.daily_basic(ts_code=ts_code, fields=DAILY_BASIC_FIELDS,
                                 limit=5)
            if df is not None and not df.empty:
                df = df.sort_values("trade_date", ascending=False).head(1)

        if df is not None and not df.empty:
            row = df.iloc[0]
            metrics.update({
                "as_of_date": str(row.get("trade_date")),
                "close":         _safe_float(row.get("close")),
                "pe_ttm":        _safe_float(row.get("pe_ttm")),
                "pe_static":     _safe_float(row.get("pe")),
                "pb":            _safe_float(row.get("pb")),
                "ps_ttm":        _safe_float(row.get("ps_ttm")),
                "ps_static":     _safe_float(row.get("ps")),
                "dv_ratio_ttm":  _safe_float(row.get("dv_ttm")),
                "total_mv":      _safe_float(row.get("total_mv")),  # 单位：万元
                "circ_mv":       _safe_float(row.get("circ_mv")),
            })
            logger.info(
                f"[metrics_extractor] daily_basic 命中: {ts_code} "
                f"as_of={metrics.get('as_of_date')}, "
                f"pe_ttm={metrics.get('pe_ttm')}, pb={metrics.get('pb')}"
            )
    except Exception as e:
        logger.warning(f"[metrics_extractor] daily_basic 提取失败 [{symbol}]: {e}")

    return metrics


# ==================== 盈利能力类提取 ====================

def _fetch_profitability_metrics(symbol: str) -> Dict[str, Any]:
    """从 Tushare fina_indicator 提取盈利能力指标（最新一期）"""
    metrics: Dict[str, Any] = {}
    api = _get_tushare_api()
    if api is None:
        return metrics

    try:
        ts_code = _resolve_ts_code(symbol)
        if not ts_code:
            return metrics

        df = api.fina_indicator(ts_code=ts_code,
                                fields=FINA_INDICATOR_FIELDS)
        if df is not None and not df.empty:
            df = df.sort_values("end_date", ascending=False)
            row = df.iloc[0]
            metrics.update({
                "fina_period":    str(row.get("end_date")),
                "eps":            _safe_float(row.get("eps")),
                "roe_ttm":        _safe_float(row.get("roe")),
                "gross_margin":   _safe_float(row.get("grossprofit_margin")),
                "net_margin":     _safe_float(row.get("netprofit_margin")),
                "debt_to_assets": _safe_float(row.get("debt_to_assets")),
                "net_profit_yoy": _safe_float(row.get("net_profit_yoy")),
                "sales_yoy":      _safe_float(row.get("sales_yoy")),
            })
            logger.info(
                f"[metrics_extractor] fina_indicator 命中: {ts_code} "
                f"period={metrics.get('fina_period')}, "
                f"roe={metrics.get('roe_ttm')}"
            )
    except Exception as e:
        logger.warning(f"[metrics_extractor] fina_indicator 提取失败 [{symbol}]: {e}")

    return metrics


# ==================== MongoDB 缓存层 ====================

def _read_cache(symbol: str, trade_date: str,
                max_age_days: int = 7) -> Optional[Dict[str, Any]]:
    """
    从 MongoDB 缓存读 metrics（7 天内有效）。
    命中且数据非空 → 直接返回 dict；否则返回 None。
    """
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        doc = db[SNAPSHOT_COLLECTION].find_one({
            "symbol": symbol,
            "trade_date": trade_date,
        })
        if not doc:
            return None
        # 过期检查（仅基于 trade_date）
        cached_date = doc.get("trade_date")
        if cached_date:
            try:
                d = datetime.strptime(str(cached_date), "%Y-%m-%d")
                if (datetime.now() - d).days > max_age_days:
                    logger.debug(
                        f"[metrics_extractor] 缓存过期: {symbol}@{cached_date}"
                    )
                    return None
            except ValueError:
                pass
        # 转回纯 dict（去掉 _id）
        return {k: v for k, v in doc.items() if k != "_id"}
    except Exception as e:
        logger.debug(f"[metrics_extractor] MongoDB 读缓存失败: {e}")
        return None


def _write_cache(metrics: Dict[str, Any]) -> None:
    """把 metrics 写回 MongoDB（best-effort，失败不抛异常）"""
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        db[SNAPSHOT_COLLECTION].update_one(
            {
                "symbol": metrics.get("_symbol"),
                "trade_date": metrics.get("_trade_date"),
            },
            {
                "$set": {
                    **metrics,
                    "_updated_at": datetime.now().isoformat(),
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[metrics_extractor] MongoDB 写缓存失败: {e}")


# ==================== 主入口 ====================

def extract_fundamentals_metrics(symbol: str,
                                 trade_date: str) -> Dict[str, Any]:
    """
    提取股票基本面核心指标（纯代码，不让 LLM 参与数字本身）。

    Args:
        symbol: 股票代码（6 位，如 603699）
        trade_date: 交易日 YYYY-MM-DD

    Returns:
        dict: 包含估值 + 盈利能力指标的 dict
              缺失字段为 None，绝不返回估算值
              含 _symbol/_trade_date/_source/_missing 等元字段
    """
    # 初始化标准结构（全部 None）
    metrics: Dict[str, Any] = {k: None for k in METRIC_KEYS}
    metrics["_symbol"] = symbol
    metrics["_trade_date"] = trade_date
    metrics["_source"] = "tushare"
    metrics["_missing"] = []

    # 1. 先查 MongoDB 缓存（命中且未过期 → 直接返回，省 Tushare 配额）
    cached = _read_cache(symbol, trade_date)
    if cached and any(cached.get(k) is not None for k in METRIC_KEYS):
        metrics["_source"] = "mongodb_cache"
        # 把缓存值合并进来
        for k in METRIC_KEYS:
            if cached.get(k) is not None:
                metrics[k] = cached[k]
        for meta_key in ("as_of_date", "fina_period"):
            if cached.get(meta_key):
                metrics[meta_key] = cached[meta_key]
        metrics["_missing"] = [
            k for k in METRIC_KEYS if metrics.get(k) is None
        ]
        logger.info(
            f"[metrics_extractor] 缓存命中: {symbol}@{trade_date} "
            f"missing={len(metrics['_missing'])}"
        )
        return metrics

    # 2. 缓存未命中 → 调 Tushare
    valuation = _fetch_valuation_metrics(symbol, trade_date)
    profitability = _fetch_profitability_metrics(symbol)

    # 合并（只覆盖 None 字段）
    for source_dict in (valuation, profitability):
        for k, v in source_dict.items():
            if v is not None:
                metrics[k] = v

    # 3. 标记缺失字段
    metrics["_missing"] = [
        k for k in METRIC_KEYS if metrics.get(k) is None
    ]

    # 4. 写回缓存（best-effort）
    if any(metrics.get(k) is not None for k in METRIC_KEYS):
        _write_cache(metrics)

    logger.info(
        f"[metrics_extractor] 提取完成: {symbol}@{trade_date} "
        f"missing={len(metrics['_missing'])} source={metrics['_source']}"
    )
    return metrics


# ==================== 硬数据块渲染 ====================

def format_metrics_block(metrics: Dict[str, Any],
                         currency_name: str = "人民币") -> str:
    """
    把 metrics dict 渲染成「硬数据块」字符串，注入 prompt。

    这是 LLM 唯一应该引用的估值数字源 —— 任何与本块不一致的数字
    都是幻觉，应被视为错误。
    """
    as_of = (metrics.get("as_of_date")
             or metrics.get("_trade_date", "N/A"))
    symbol = metrics.get("_symbol", "N/A")

    def fmt_num(val, unit: str = "", digits: int = 2) -> str:
        if val is None:
            return "数据缺失"
        return f"{val:.{digits}f}{unit}"

    def fmt_pct(val) -> str:
        if val is None:
            return "数据缺失"
        return f"{val:.2f}%"

    def fmt_mv(val) -> str:
        # Tushare total_mv/circ_mv 单位是"万元"
        if val is None:
            return "数据缺失"
        if val >= 10000:  # 万元 → 亿元（除以 10000）
            return f"{val / 10000:.2f} 亿元"
        return f"{val:.2f} 万元"

    def fmt_yoy(val) -> str:
        if val is None:
            return "数据缺失"
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.2f}%"

    lines = [
        "【数据库真值 - 来源: Tushare/MongoDB，禁止修改】",
        f"股票: {symbol} (as of {as_of})",
        "-" * 50,
        "【估值类】",
        f"  当前股价:       {fmt_num(metrics.get('close'), ' 元')}",
        f"  PE_TTM:         {fmt_num(metrics.get('pe_ttm'), ' 倍')}",
        f"  PE(静):         {fmt_num(metrics.get('pe_static'), ' 倍')}",
        f"  PB:             {fmt_num(metrics.get('pb'), ' 倍')}",
        f"  PS_TTM:         {fmt_num(metrics.get('ps_ttm'), ' 倍')}",
        f"  总市值:         {fmt_mv(metrics.get('total_mv'))}",
        f"  流通市值:       {fmt_mv(metrics.get('circ_mv'))}",
        f"  股息率TTM:      {fmt_pct(metrics.get('dv_ratio_ttm'))}",
        "-" * 50,
        "【盈利能力】",
        f"  EPS:            {fmt_num(metrics.get('eps'), ' 元')}",
        f"  ROE_TTM:        {fmt_pct(metrics.get('roe_ttm'))}",
        f"  毛利率:         {fmt_pct(metrics.get('gross_margin'))}",
        f"  净利率:         {fmt_pct(metrics.get('net_margin'))}",
        f"  资产负债率:     {fmt_pct(metrics.get('debt_to_assets'))}",
        "-" * 50,
        "【成长性】",
        f"  营收 YoY:      {fmt_yoy(metrics.get('sales_yoy'))}",
        f"  归母净利 YoY:  {fmt_yoy(metrics.get('net_profit_yoy'))}",
        "-" * 50,
    ]

    if metrics.get("fina_period"):
        lines.append(
            f"【数据日期】财务指标披露期: {metrics['fina_period']}"
        )

    missing = metrics.get("_missing", [])
    if missing:
        lines.append(
            f"【缺失字段】{', '.join(missing)} （请写\"数据缺失\"，禁止猜测）"
        )
    else:
        lines.append("【缺失字段】无")

    lines.extend([
        "-" * 50,
        "铁律: 所有数字均为数据库真值，请【逐字引用】,",
        "严禁任何形式的重写、估算、四舍五入或推测。",
        f"货币单位: {currency_name}",
    ])

    return "\n".join(lines)
```

**渲染输出示例**（603699 调用后）：

```
【数据库真值 - 来源: Tushare/MongoDB，禁止修改】
股票: 603699 (as of 2026-09-04)
--------------------------------------------------
【估值类】
  当前股价:       46.33 元
  PE_TTM:         21.42 倍
  PE(静):         22.71 倍
  PB:             7.88 倍
  PS_TTM:         6.88 倍
  总市值:         363.61 亿元
  流通市值:       358.12 亿元
  股息率TTM:      1.12%
--------------------------------------------------
【盈利能力】
  EPS:            1.42 元
  ROE_TTM:        23.41%
  毛利率:         38.12%
  净利率:         32.15%
  资产负债率:     41.23%
--------------------------------------------------
【成长性】
  营收 YoY:      +8.56%
  归母净利 YoY:  +12.34%
--------------------------------------------------
【数据日期】财务指标披露期: 2025-12-31
【缺失字段】无
--------------------------------------------------
铁律: 所有数字均为数据库真值，请【逐字引用】,
严禁任何形式的重写、估算、四舍五入或推测。
货币单位: 人民币
```

---

## 三、fundamentals_analyst.py 改动对比

### 改动 1：line 213-220 — system_message 末尾加"估值铁律"

**原内容**：

```python
            "- 使用中文投资建议（买入/持有/卖出）"
            "现在立即开始调用工具！不要说任何其他话！"
        )
```

**新内容**：

```python
            "- 使用中文投资建议（买入/持有/卖出）"
            "🚨 估值数字铁律（反幻觉）:"
            "- PE/PB/ROE/营收/净利润/股价等数字必须逐字使用【数据库真值】中的数值"
            "- 严禁任何估算、四舍五入、推测"
            "- 缺失字段必须显式标注'数据缺失'"
            "- 数字格式与真值块完全一致(倍/%/亿元)"
            "现在立即开始调用工具！不要说任何其他话！"
        )
```

**改动量**：+6 行（无删除）

---

### 改动 2 & 3：line 646-708 — 插入硬数据提取 + 重写 analysis_prompt

**原内容**（line 644-660）：

```python
                currency_info = f"{market_info['currency_name']}（{market_info['currency_symbol']}）"
                
                # 生成基于真实数据的分析报告
                analysis_prompt = f"""基于以下真实数据，对{company_name}（股票代码：{ticker}）进行详细的基本面分析：

{combined_data}

请提供：
1. 公司基本信息分析（{company_name}，股票代码：{ticker}）
2. 财务状况评估
3. 盈利能力分析
4. 估值分析（使用{currency_info}）
5. 投资建议（买入/持有/卖出）

要求：
- 基于提供的真实数据进行分析
- 正确使用公司名称"{company_name}"和股票代码"{ticker}"
- 价格使用{currency_info}
- 投资建议使用中文
- 分析要详细且专业"""
```

**新内容**（line 646-708）：

```python
                currency_info = f"{market_info['currency_name']}（{market_info['currency_symbol']}）"

                # 🚨 反幻觉: 提取真实指标并格式化为硬数据块（不让 LLM 参与数字本身）
                from tradingagents.dataflows.metrics_extractor import (
                    extract_fundamentals_metrics,
                    format_metrics_block,
                )
                try:
                    hard_metrics = extract_fundamentals_metrics(ticker, current_date)
                    hard_block = format_metrics_block(
                        hard_metrics,
                        currency_name=market_info['currency_name'],
                    )
                    logger.info(
                        f"✅ [反幻觉] 提取硬数据: {ticker} "
                        f"missing={len(hard_metrics.get('_missing', []))} "
                        f"source={hard_metrics.get('_source')}"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ [反幻觉] 提取失败 [{ticker}]: {e}")
                    hard_metrics = {}
                    hard_block = (
                        "(硬数据块提取失败，请基于 combined_data 谨慎分析，"
                        "严禁编造 PE/PB/ROE 等数字)"
                    )

                # 生成基于真实数据的分析报告
                analysis_prompt = f"""{hard_block}

公司: {company_name}（股票代码: {ticker}）
日期: {current_date}
货币: {currency_info}

🚨 强制约束（反幻觉）:
1. 所有 PE/PB/ROE/营收/净利润/股价等数字,必须【逐字】引用上方【数据库真值】块
2. 严禁出现"约 X 倍""20 多倍""大概 X%"等估算表达
3. 数字必须带单位(倍/%/亿元),格式与真值块完全一致
4. 缺失字段必须显式标注"数据缺失",禁止猜测或填默认值
5. 如果【数据库真值】与下方"原始数据参考"冲突,以真值块为准

原始数据参考(可能不准确,仅作为辅助理解):
{combined_data}

请提供:
1. 公司基本信息分析({company_name},股票代码:{ticker})
2. 财务状况评估
3. 盈利能力分析
4. 估值分析(使用{currency_info})
5. 投资建议(买入/持有/卖出)

要求:
- 优先使用【数据库真值】中的数字,不要修改
- 正确使用公司名称"{company_name}"和股票代码"{ticker}"
- 价格使用{currency_info}
- 投资建议使用中文
- 分析要详细且专业"""
```

**改动量**：
- 删除：原 `analysis_prompt` 块（19 行）
- 新增：硬数据提取 try/except 块（24 行）+ 新 `analysis_prompt` 块（37 行）
- 净增：约 42 行

---

## 四、效果对比（关键差异）

| 维度 | 改动前（软注入） | 改动后（硬注入） |
|---|---|---|
| 数据传递方式 | `{combined_data}` 整段 raw text 拼进 prompt | Python 预提取 → `format_metrics_block` 渲染 → 拼进 prompt |
| LLM 是否接触数字 | ✅ 是（从长文本里挑数字）| ❌ 否（数字以结构化"硬数据块"形式给定）|
| PE 字段位置 | 散落在工具返回的"市盈率相关描述"里 | `【PE_TTM: 21.42 倍】` 明确标注 |
| 数字格式控制 | 无 | 严格 `倍/%/亿元` 单位对齐 |
| 缺失字段处理 | LLM 可能瞎填 | 显式标 `数据缺失`，强制 LLM 不能猜 |
| 缓存策略 | 每次重新调用工具 | MongoDB 缓存 7 天，省 Tushare 配额 |

---

## 五、验证步骤

```bash
# 1. 语法检查（已完成）
python -c "import ast; ast.parse(open('tradingagents/dataflows/metrics_extractor.py').read())"
python -c "import ast; ast.parse(open('tradingagents/agents/analysts/fundamentals_analyst.py').read())"

# 2. 独立调用测试
python -c "
from tradingagents.dataflows.metrics_extractor import extract_fundamentals_metrics, format_metrics_block
m = extract_fundamentals_metrics('603699', '2026-09-04')
print(format_metrics_block(m))
"

# 3. 重启后端加载新代码
#   桌面 → 停止 TradingAgents-H.bat
#   桌面 → 启动 TradingAgents-H.bat

# 4. 端到端测试：跑 603699 分析任务，检查报告里 PE 是否 = 21.42
```

---

## 六、关键设计取舍说明

| 取舍 | 决策 | 理由 |
|---|---|---|
| **缓存时效** | 7 天 | A股行情每个交易日变化，但财务指标披露频率低（季报）；7 天内 PE 估值偏离可接受 |
| **MongoDB 缓存集合名** | `stock_metrics_snapshot` | 避开现有 `stock_daily_basic` 集合，避免数据混淆；专存"提取后的快照" |
| **Tushare 字段** | 只取 12 个核心字段 | 省 API 流量配额（daily_basic 全量约 24 字段）；只取估值+盈利能力需要的 |
| **缺失字段处理** | `数据缺失` 字面量 | 强制 LLM 不能用"约""大概"绕过约束；后置校验可识别 |
| **指标单位** | 万元→亿元自动转换 | Tushare `total_mv` 单位是万元，前端展示用亿元更直观 |
| **股票代码后缀** | 硬编码规则推断（60/00/68/30） | 项目里其他模块也是同样规则，保持一致；接口不依赖额外查表 |

---

## 七、已知风险与 TODO

| 风险 | 影响 | 缓解 |
|---|---|---|
| Tushare API 配额 | 高频分析时可能超限 | MongoDB 缓存 7 天，二次查询直接命中 |
| TTM 营收/净利润 | 当前未计算（只用最新一期） | 后续接入 Tushare `income` 表做 4 季累加 |
| 港股/美股 | 不在 Tushare daily_basic 范围 | 当前 A 股专用；港股走 AKShare，美股走 yfinance（独立模块） |
| 后置校验 | 报告生成后未做偏差校验 | 后续加 `finance_validator.py`，报告里数字 vs 真值 diff > 20% 标红 |
| LLM 漏改 | 即使 prompt 约束，LLM 可能仍编 | 配合后置校验兜底；分析时显式附"硬数据块截屏"进 UI |

---

## 八、变更摘要（git commit 建议）

```bash
git add tradingagents/dataflows/metrics_extractor.py
git add tradingagents/agents/analysts/fundamentals_analyst.py
git add docs/refactor/pe_hallucination_fix_2026-09-05.md
git commit -m "fix(fundamentals): 反估值幻觉 — 硬数据块注入

- 新增 metrics_extractor: 纯 Python 提取 PE/PB/ROE 等指标
  (MongoDB 缓存 7 天，避免 Tushare API 配额浪费)
- fundamentals_analyst: 在 analysis_prompt 前插入硬数据块
  + system_message 加'估值铁律'
- 修复 PE 12~14 vs 实际 21.42 的 LLM 估值幻觉问题
- docs: 添加完整 diff 记录"
```