"""quant_db(PostgreSQL)访问:K线 / 估值 / 名称映射。凭据只读环境变量,不硬编码。"""
import os
import pg8000.native

_CONN = None


def _conn():
    global _CONN
    if _CONN is None:
        missing = [k for k in ("QUANTDB_HOST", "QUANTDB_PORT", "QUANTDB_USER", "QUANTDB_PASS")
                   if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"缺少环境变量 {missing};请 source claude_native/.env")
        _CONN = pg8000.native.Connection(
            user=os.environ["QUANTDB_USER"],
            password=os.environ["QUANTDB_PASS"],
            host=os.environ["QUANTDB_HOST"],
            port=int(os.environ["QUANTDB_PORT"]),
            database=os.environ.get("QUANTDB_NAME", "quant_db"),
            timeout=30,
        )
    return _CONN


def _ts_code(code: str) -> str:
    """600845 -> 600845.SH;000938 -> 000938.SZ。"""
    code = code.strip().split(".")[0]
    suffix = "SH" if code[0] in ("6", "5", "9") else "SZ"
    return f"{code}.{suffix}"


def get_name(code: str) -> str:
    rows = _conn().run(
        "SELECT name FROM stock_basic WHERE ts_code = :t LIMIT 1", t=_ts_code(code))
    return rows[0][0] if rows else ""


def get_kline(code: str, limit: int = 90) -> list:
    """返回按日期升序最近 limit 条:[{trade_date, open, high, low, close, pre_close, vol, amount}]。"""
    rows = _conn().run(
        """SELECT trade_date, open, high, low, close, pre_close, vol, amount
           FROM kline_daily WHERE ts_code = :t
           ORDER BY trade_date DESC LIMIT :n""",
        t=_ts_code(code), n=limit)
    cols = ["trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"]
    out = [dict(zip(cols, r)) for r in rows]
    out.reverse()
    return [{k: (float(v) if k != "trade_date" and v is not None else v)
             for k, v in d.items()} for d in out]


def _latest_partition(prefix: str) -> str:
    rows = _conn().run(
        """SELECT tablename FROM pg_tables
           WHERE tablename LIKE :p ORDER BY tablename DESC LIMIT 1""", p=f"{prefix}%")
    return rows[0][0] if rows else prefix


def get_valuation(code: str) -> dict:
    """最近一期 pe/pe_ttm/pb/total_mv/circ_mv/turnover_rate;失败返回含 _error。"""
    try:
        tbl = _latest_partition("daily_basic")
        rows = _conn().run(
            f"""SELECT pe, pe_ttm, pb, total_mv, circ_mv, turnover_rate, trade_date
                FROM {tbl} WHERE ts_code = :t ORDER BY trade_date DESC LIMIT 1""",
            t=_ts_code(code))
        if not rows:
            return {}
        cols = ["pe", "pe_ttm", "pb", "total_mv", "circ_mv", "turnover_rate", "trade_date"]
        d = dict(zip(cols, rows[0]))
        return {k: (float(v) if k != "trade_date" and v is not None else v) for k, v in d.items()}
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}
