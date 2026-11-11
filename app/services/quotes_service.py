"""
QuotesService: 提供A股批量实时快照获取（AKShare东方财富 spot 接口），带内存TTL缓存。
- AKShare 失败时降级到本机通达信 tqcenter HTTP 接口（可选兜底，见 ADR-001；客户端不在则静默跳过）。
- 仅用于筛选返回前对 items 进行行情富集。

通达信双通道职责划分（P5，见 docs/05-design/v4.0/data-architecture-problems-and-optimization.md §6）：
- tqcenter HTTP（本文件，127.0.0.1:17709）= 行情实时数据通道（低延迟）
- tdx-mcp MCP 工具 = 股票信息 / 基本面查询通道（core/tools/mcp/，data_source 标注 "mcp:<server>"）
- QMT = xtquant SDK 直连，保持现状不 MCP 化（app/services/data_sources/qmt_adapter.py）
"""
from __future__ import annotations

import asyncio
import json
import time
import logging
import urllib.error
import urllib.request
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_TQ_HTTP_URL = 'http://127.0.0.1:17709/'
_TQ_HTTP_TIMEOUT = 5.0


class _TqUnavailable(RuntimeError):
    """tqcenter 不可达或返回异常（兜底场景静默降级）。"""


def _tq_call(method: str, params: dict | None = None) -> dict:
    """调用本机通达信 tqcenter HTTP JSON-RPC。

    拷贝自 core/pro/domain_models/pig_cycle/futures.py 的 _tdx_call
    （跨包小函数各留一份的既有约定），接口详见 docs/03-development/decisions/001-quotes-tqcenter-fallback.md。
    """
    payload = {'id': 1, 'method': method, 'params': params or {}}
    req = urllib.request.Request(
        _TQ_HTTP_URL,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=_TQ_HTTP_TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, ConnectionError, OSError, TimeoutError) as e:
        raise _TqUnavailable(f'tqcenter 不可达：{type(e).__name__}: {e}') from e
    result = body.get('result') if isinstance(body, dict) else None
    if not isinstance(result, dict) or result.get('ErrorId') != '0':
        raise _TqUnavailable(f'tqcenter 返回异常：{str(body)[:200]}')
    return result


def _to_tdx_code(code: str) -> str:
    """6位A股代码 → tqcenter 代码（002714 → 002714.SZ）；已带后缀原样返回。"""
    if '.' in code:
        return code.upper()
    if code.startswith(('60', '68', '9')):
        return f'{code}.SH'
    if code.startswith(('0', '3')):
        return f'{code}.SZ'
    if code.startswith(('4', '8')):
        return f'{code}.BJ'
    return code


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        # 处理字符串中的逗号/百分号/空白
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s.endswith("%"):
                s = s[:-1]
            if s == "-" or s == "":
                return None
            return float(s)
        # 处理 pandas/numpy 数值
        return float(v)
    except Exception:
        return None


class QuotesService:
    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = ttl_seconds
        self._cache_ts: float = 0.0
        self._cache: Dict[str, Dict[str, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """获取一批股票的近实时快照（最新价、涨跌幅、成交额）。
        - 优先使用缓存；缓存超时或为空则刷新一次全市场快照。
        - 返回仅包含请求的 codes。
        """
        codes = [c.strip() for c in codes if c]
        now = time.time()
        async with self._lock:
            if self._cache and (now - self._cache_ts) < self._ttl:
                return {c: q for c, q in self._cache.items() if c in codes and q}
            # 刷新缓存（阻塞IO放到线程）
            data = await asyncio.to_thread(self._fetch_spot_akshare)
            if not data:
                # AKShare 失败（外网故障/限频）时降级本机通达信 tqcenter（ADR-001）
                data = await asyncio.to_thread(self._fetch_spot_tdx, codes)
            self._cache = data
            self._cache_ts = time.time()
            return {c: q for c, q in self._cache.items() if c in codes and q}

    def _fetch_spot_akshare(self) -> Dict[str, Dict[str, Optional[float]]]:
        """通过 AKShare 东方财富全市场快照接口拉取行情，并标准化为字典。
        预期列（常见）：代码、名称、最新价、涨跌幅、成交额。
        不同版本可能有差异，做多列名兼容。
        """
        try:
            import akshare as ak  # 已在项目中使用，不额外安装
            df = ak.stock_zh_a_spot_em()
            if df is None or getattr(df, "empty", True):
                logger.warning("AKShare spot 返回空数据")
                return {}
            # 兼容常见列名
            code_col = next((c for c in ["代码", "代码code", "symbol", "股票代码"] if c in df.columns), None)
            price_col = next((c for c in ["最新价", "现价", "最新价(元)", "price", "最新"] if c in df.columns), None)
            pct_col = next((c for c in ["涨跌幅", "涨跌幅(%)", "涨幅", "pct_chg"] if c in df.columns), None)
            amount_col = next((c for c in ["成交额", "成交额(元)", "amount", "成交额(万元)"] if c in df.columns), None)

            if not code_col or not price_col:
                logger.error(f"AKShare spot 缺少必要列: code={code_col}, price={price_col}")
                return {}

            result: Dict[str, Dict[str, Optional[float]]] = {}
            for _, row in df.iterrows():  # type: ignore
                code_raw = row.get(code_col)
                if not code_raw:
                    continue
                # 标准化股票代码：移除前导0，然后补齐到6位
                code_str = str(code_raw).strip()
                # 如果是纯数字，移除前导0后补齐到6位
                if code_str.isdigit():
                    code_clean = code_str.lstrip('0') or '0'  # 移除前导0，如果全是0则保留一个0
                    code = code_clean.zfill(6)  # 补齐到6位
                else:
                    code = code_str.zfill(6)
                close = _safe_float(row.get(price_col))
                pct = _safe_float(row.get(pct_col)) if pct_col else None
                amt = _safe_float(row.get(amount_col)) if amount_col else None
                # 若成交额单位为万元，统一转换为元（部分接口是万元，这里不强转，保持原样由前端展示单位）
                result[code] = {"close": close, "pct_chg": pct, "amount": amt}
            logger.info(f"AKShare spot 拉取完成: {len(result)} 条")
            return result
        except Exception as e:
            logger.error(f"获取AKShare实时快照失败: {e}")
            return {}

    def _fetch_spot_tdx(self, codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """兜底（ADR-001）：经本机通达信 tqcenter 批量拉日K（get_market_data 支持 stock_list 批量）。

        - 现价取最后一根收盘（盘中为实时价，收盘后为最新收盘），涨跌幅 = 最后两根收盘比值-1，
          成交额 = 最后一根 Amount × 10000（tqcenter Amount 口径为万元，实测验证）。
        - 用日K而非快照（get_market_snapshot 逐票、不支持批量），且客户端数据陈旧时
          Now=0、LastClose 停在旧一交易日，快照会导致现价差一日且无涨跌；日K两根一次出三字段。
        - 客户端不可达（_TqUnavailable）直接中止返回空结果，Docker/无客户端用户零感知。
        """
        try:
            r = _tq_call('get_market_data', {
                'stock_list': [_to_tdx_code(c) for c in codes],
                'period': '1d',
                'count': 2,
                'dividend_type': 'none',
            })
        except _TqUnavailable as e:
            logger.info(f"tqcenter 兜底中止（不可达）: {e}")
            return {}
        value = r.get('Value') or {}
        result: Dict[str, Dict[str, Optional[float]]] = {}
        for code in codes:
            kv = value.get(_to_tdx_code(code)) or {}
            closes = [v for v in (_safe_float(x) for x in (kv.get('Close') or [])) if v and v > 0]
            if not closes:
                continue
            close = closes[-1]
            pct: Optional[float] = None
            if len(closes) >= 2 and closes[-2] > 0:
                pct = round((close / closes[-2] - 1) * 100, 2)
            amounts = [_safe_float(x) for x in (kv.get('Amount') or [])]
            amount = amounts[-1] * 10000 if amounts and amounts[-1] and amounts[-1] > 0 else None
            result[code] = {"close": close, "pct_chg": pct, "amount": amount}
        logger.info(f"tqcenter 兜底拉取完成: {len(result)}/{len(codes)} 条")
        return result


_quotes_service: Optional[QuotesService] = None


def get_quotes_service() -> QuotesService:
    global _quotes_service
    if _quotes_service is None:
        _quotes_service = QuotesService(ttl_seconds=30)
    return _quotes_service

