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
        f57  : 股票代码
        f58  : 股票名称
        f85  : 流通市值（元）
        f117 : 总市值（元）
        f162 : 动态 PE × 100
        f167 : PB × 100

        注：东财 stock/get 接口的 f115 字段对个股查询不返回有效值（始终为0），
            若需 PS 请用 clist 批量接口或自算。当前项目暂不使用 PS。
        """
        market_prefix = "1" if symbol.startswith(("6", "9")) else "0"
        secid = f"{market_prefix}.{symbol}"
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {"secid": secid, "fields": "f43,f57,f58,f85,f117,f162,f167"}
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
            pe_dynamic = int(data.get("f162", 0)) / 100 if data.get("f162") else None
            pb = int(data.get("f167", 0)) / 100 if data.get("f167") else None

            return {
                "name": data.get("f58"),
                "price": price,
                "total_mv": total_mv_yi,
                "circ_mv": circ_mv_yi,
                "total_share": total_share_yi,
                "pe_dynamic": pe_dynamic,
                "pb": pb,
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
        字段（按实际返回顺序，2026-06 实测）:
        [3]  名称
        [39] PE_TTM（静态）
        [44] 流通市值（亿元）← 2026-07 实测确认，东财 f85 不可靠，用此字段
        [45] 总市值（亿元）
        [46] PB（市净率）
        [52] 动态 PE
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
                "circ_mv": float(parts[44]) if parts[44] else None,
                "total_mv": float(parts[45]) if parts[45] else None,
                "pe_ttm": float(parts[39]) if parts[39] else None,
                "pe_dynamic": float(parts[52]) if parts[52] else None,
                "pb": float(parts[46]) if parts[46] else None,
                "source": "Tencent qt.gtimg",
            }
        except Exception as e:
            logger.warning(f"腾讯 qt.gtimg 获取 {symbol} 失败: {e}")
            return None
