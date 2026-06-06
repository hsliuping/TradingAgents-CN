"""主控预取:quant_db + a-stock-data → 紧凑 _data.json(供 Workflow 只读)。"""
import json
import os
import sys
import datetime
import tradingagents_db as db
import tradingagents_astock as astock
import tradingagents_indicators as ind

OUT_DIR = os.path.join(os.path.dirname(__file__), "_tmp")


def _last(vals):
    for v in reversed(vals):
        if v is not None:
            return round(v, 4)
    return None


def build(code: str) -> dict:
    code = code.strip().split(".")[0]
    name = db.get_name(code)
    kline = db.get_kline(code, 90)
    closes = [r["close"] for r in kline]
    indicators = {}
    errors = []
    if len(closes) >= 20:
        m = ind.macd(closes)
        b = ind.boll(closes, 20)
        indicators = {
            "ma": {w: _last(ind.ma(closes, w)) for w in (5, 10, 20, 60)},
            "rsi": {w: _last(ind.rsi(closes, w)) for w in (6, 12, 24)},
            "macd": {"dif": round(m["dif"][-1], 4), "dea": round(m["dea"][-1], 4),
                      "hist": round(m["hist"][-1], 4)},
            "boll": {"upper": _last(b["upper"]), "mid": _last(b["mid"]), "lower": _last(b["lower"])},
            "last_close": closes[-1] if closes else None,
        }
    else:
        errors.append("kline_insufficient")
    if not name and not kline:
        errors.append("quantdb_miss")

    asd = astock.collect(code)
    for k, v in asd.items():
        if isinstance(v, dict) and "_error" in v:
            errors.append(f"astock.{k}:{v['_error'][:60]}")

    as_of = kline[-1]["trade_date"] if kline else datetime.date.today().strftime("%Y%m%d")
    return {
        "meta": {"code": code, "name": name, "as_of_date": as_of,
                  "stock_info": asd.get("stock_info")},
        "tech": {"kline_tail": kline[-30:], "indicators": indicators},
        "funda": {"valuation_db": db.get_valuation(code),
                   "valuation_realtime": asd.get("valuation_realtime"),
                   "snapshot": asd.get("snapshot")},
        "news": {"research": asd.get("research"), "hotspot_reason": asd.get("hotspot_reason")},
        "senti": {"moneyflow": asd.get("moneyflow"), "lhb": asd.get("lhb"),
                   "margin": asd.get("margin"), "holders": asd.get("holders")},
        "errors": errors,
    }


def main():
    if len(sys.argv) < 2:
        print("用法: tradingagents_fetch.py <code|code,code,...>", file=sys.stderr)
        sys.exit(1)
    codes = [c for c in sys.argv[1].replace(" ", "").split(",") if c]
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}
    for c in codes:
        data = build(c)
        path = os.path.join(OUT_DIR, f"{data['meta']['code']}_data.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        results[data["meta"]["code"]] = path
        print(f"[ok] {c} {data['meta']['name']} as_of={data['meta']['as_of_date']} "
              f"errors={len(data['errors'])} -> {path}")
    with open(os.path.join(OUT_DIR, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
