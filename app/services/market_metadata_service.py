"""
市场元数据推断工具
"""

from typing import Dict, Optional


BJ_PREFIXES = (
    "430", "440", "830", "831", "832", "833", "835", "836", "837", "838", "839",
    "870", "871", "872", "873", "874", "875", "876", "877", "878", "879",
    "880", "881", "882", "883", "884", "885", "886", "887", "888", "889",
)


def infer_market_metadata(market: Optional[str], code: Optional[str]) -> Dict[str, Optional[str]]:
    """根据市场与股票代码推断交易所、板块和标准代码。"""
    market_label = str(market or "A股").strip()
    raw_code = str(code or "").strip().upper()

    if raw_code.endswith(".HK"):
        raw_code = raw_code[:-3]

    if market_label == "港股":
        normalized = (raw_code.lstrip("0") or "0").zfill(5) if raw_code.isdigit() else raw_code
        return {
            "market": "港股",
            "exchange": "香港交易所",
            "exchange_code": "SEHK",
            "board": None,
            "full_symbol": f"{normalized}.HK" if normalized and normalized.isdigit() else None,
        }

    if market_label == "美股":
        return {
            "market": "美股",
            "exchange": None,
            "exchange_code": None,
            "board": None,
            "full_symbol": raw_code or None,
        }

    if not raw_code.isdigit():
        return {
            "market": "A股",
            "exchange": None,
            "exchange_code": None,
            "board": None,
            "full_symbol": None,
        }

    normalized_code = raw_code.zfill(6)

    if normalized_code.startswith(BJ_PREFIXES) or normalized_code[:1] in {"4", "8"}:
        return {
            "market": "A股",
            "exchange": "北京证券交易所",
            "exchange_code": "BSE",
            "board": "北交所",
            "full_symbol": f"{normalized_code}.BJ",
        }

    if normalized_code.startswith("68"):
        return {
            "market": "A股",
            "exchange": "上海证券交易所",
            "exchange_code": "SSE",
            "board": "科创板",
            "full_symbol": f"{normalized_code}.SH",
        }

    if normalized_code.startswith("30"):
        return {
            "market": "A股",
            "exchange": "深圳证券交易所",
            "exchange_code": "SZSE",
            "board": "创业板",
            "full_symbol": f"{normalized_code}.SZ",
        }

    if normalized_code.startswith("60"):
        return {
            "market": "A股",
            "exchange": "上海证券交易所",
            "exchange_code": "SSE",
            "board": "主板",
            "full_symbol": f"{normalized_code}.SH",
        }

    if normalized_code.startswith(("00", "001", "002", "003", "20")):
        return {
            "market": "A股",
            "exchange": "深圳证券交易所",
            "exchange_code": "SZSE",
            "board": "主板",
            "full_symbol": f"{normalized_code}.SZ",
        }

    return {
        "market": "A股",
        "exchange": None,
        "exchange_code": None,
        "board": None,
        "full_symbol": None,
    }

