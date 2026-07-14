"""广发证券股票市值与估值 Provider

通过广发证券 Skills MCP 接口获取：
1. 市值与估值对比（common_basic_post）：总市值、PE/PB 及行业均值、历史百分位
2. 财务指标对比（compare_indicator_post）：盈利/资本结构/现金流/成长/运营 5 大维度

API 文档：https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call
API key 从环境变量 GF_SKILLS_APIKEY 读取（未设置时使用内置默认 key）。
"""
import os
import logging
from typing import Optional, Dict, List

import requests

logger = logging.getLogger(__name__)


# 默认 API key（用户提供的测试 key，建议生产环境用环境变量覆盖）
_DEFAULT_APIKEY = "5f88795d-832f-4eda-8ad6-aaff84839aeb"
_API_URL = "https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call"
_TIMEOUT = 8  # 秒


def _to_gf_code(symbol: str) -> Optional[str]:
    """6位股票代码 → 广发格式（带市场前缀大写）

    600011 / 900001 / 688xxx → SHxxxxxx
    000xxx / 002xxx / 300xxx / 200xxx → SZxxxxxx
    """
    if not symbol or not isinstance(symbol, str):
        return None
    code = symbol.strip().upper()
    # 已经是广发格式
    if code.startswith(("SH", "SZ", "BJ")):
        return code
    if not code.isdigit() or len(code) != 6:
        return None
    if code.startswith(("6", "9", "688")):
        return f"SH{code}"
    if code.startswith(("4", "8")):  # 北交所
        return f"BJ{code}"
    return f"SZ{code}"


# 行业同业映射表（用于工具2的对比股选择）
# key: 股票代码（6位）, value: 同业对比股（6位）
# 注：工具2要求传2只股票，这里挑选同行业的代表性公司做对比
_INDUSTRY_PEER_MAP = {
    # 电力
    "600011": "600027",  # 华能国际 → 华电国际
    "600027": "600011",  # 华电国际 → 华能国际
    "600023": "600011",  # 浙能电力 → 华能国际
    "600795": "600011",  # 国电电力 → 华能国际
    "601991": "600011",  # 大唐发电 → 华能国际
    # 银行
    "601398": "601939",  # 工商银行 → 建设银行
    "601939": "601398",  # 建设银行 → 工商银行
    "601288": "601398",  # 农业银行 → 工商银行
    "601988": "601398",  # 中国银行 → 工商银行
    "600036": "601398",  # 招商银行 → 工商银行
    # 白酒
    "600519": "000858",  # 贵州茅台 → 五粮液
    "000858": "600519",  # 五粮液 → 贵州茅台
    # 保险
    "601318": "601628",  # 中国平安 → 中国人寿
    "601628": "601318",  # 中国人寿 → 中国平安
    # 券商
    "600030": "601688",  # 中信证券 → 华泰证券
    "601688": "600030",  # 华泰证券 → 中信证券
    # 房地产
    "000002": "600048",  # 万科A → 保利发展
    "600048": "000002",  # 保利发展 → 万科A
    # 家电
    "000333": "600690",  # 美的集团 → 海尔智家
    "600690": "000333",  # 海尔智家 → 美的集团
    # 医药
    "600276": "000538",  # 恒瑞医药 → 云南白药
    "000538": "600276",  # 云南白药 → 恒瑞医药
    # 新能源/电池
    "300750": "002594",  # 宁德时代 → 比亚迪
    "002594": "300750",  # 比亚迪 → 宁德时代
    # 科技/半导体
    "688981": "603501",  # 中芯国际 → 韦尔股份
    "603501": "688981",  # 韦尔股份 → 中芯国际
    # 汽车整车
    "600104": "601238",  # 上汽集团 → 广汽集团
    "601238": "600104",  # 广汽集团 → 上汽集团
    # 钢铁
    "600019": "600010",  # 宝钢股份 → 包钢股份
    "600010": "600019",  # 包钢股份 → 宝钢股份
    # 煤炭
    "601088": "600188",  # 中国神华 → 兖矿能源
    "600188": "601088",  # 兖矿能源 → 中国神华
    # 石油
    "601857": "600028",  # 中国石油 → 中国石化
    "600028": "601857",  # 中国石化 → 中国石油
}

# 通用 fallback 对比股（找不到同业时用）——沪深300成分股中流动性好的标的
_FALLBACK_PEER = "600027"  # 华电国际，作为电力股相对中性


def _get_peer(symbol: str) -> str:
    """获取同业对比股代码（6位）"""
    return _INDUSTRY_PEER_MAP.get(symbol, _FALLBACK_PEER)


def _call_api(service_name: str, tool_name: str, args: dict) -> Optional[dict]:
    """调用广发 Skills MCP 接口"""
    apikey = os.getenv("GF_SKILLS_APIKEY", _DEFAULT_APIKEY)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }
    payload = {
        "service_name": service_name,
        "tool_name": tool_name,
        "args": args,
    }
    try:
        r = requests.post(_API_URL, json=payload, headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        resp = r.json()
        # 响应格式：{"data": {...}, "msg": "", "retcode": 0}
        # 内层：{"data": [...]/{...}, "msg": "ok", "retcode": 0}
        if resp.get("retcode") != 0:
            logger.warning(f"⚠️ [广发] 接口返回错误: {resp.get('msg')}")
            return None
        inner = resp.get("data", {})
        if isinstance(inner, dict) and inner.get("retcode") not in (0, None):
            logger.warning(f"⚠️ [广发] 业务返回错误: {inner.get('msg')}")
            return None
        return inner
    except requests.Timeout:
        logger.warning(f"⚠️ [广发] 接口超时 ({_TIMEOUT}s)")
        return None
    except Exception as e:
        logger.warning(f"⚠️ [广发] 接口调用失败: {type(e).__name__}: {e}")
        return None


class GFQuoteProvider:
    """广发证券股票市值与估值 Provider"""

    @staticmethod
    def get_valuation(symbol: str) -> Optional[dict]:
        """工具1：市值与估值对比（单股即可）

        返回字段：
        - total_mv: 总市值（亿元）
        - pe_ttm: 市盈率TTM
        - pe_ttm_avg: PE行业均值
        - pe_ttm_percent: PE历史百分位（0-100）
        - pb: 市净率
        - pb_avg: PB行业均值
        - pb_percent: PB历史百分位（0-100）
        - list_date: 上市日期
        - name: 股票名称
        - trade_date: 行情日期
        """
        gf_code = _to_gf_code(symbol)
        if not gf_code:
            logger.warning(f"⚠️ [广发] 股票代码格式错误: {symbol}")
            return None

        inner = _call_api("quant", "common_basic_post", {"stock_codes": [gf_code]})
        if not inner:
            return None

        data_list = inner.get("data", [])
        if not data_list or not isinstance(data_list, list):
            logger.warning(f"⚠️ [广发] 工具1返回空数据: {symbol}")
            return None

        item = data_list[0]
        basic = item.get("basic", {}) or {}
        valuation = item.get("valuation", {}) or {}

        total_mv = basic.get("total_marketcap")
        pe_ttm = valuation.get("pettm")
        pb = valuation.get("pb")

        # 全部为空则视为无效
        if total_mv is None and pe_ttm is None and pb is None:
            return None

        return {
            "name": item.get("stock_name"),
            "stock_code": item.get("stock_code"),
            "list_date": basic.get("list_date"),
            "total_mv": float(total_mv) if total_mv is not None else None,
            "pe_ttm": float(pe_ttm) if pe_ttm is not None else None,
            "pe_ttm_avg": float(valuation["pettm_avg"]) if valuation.get("pettm_avg") is not None else None,
            "pe_ttm_percent": float(valuation["pettm_percent"]) if valuation.get("pettm_percent") is not None else None,
            "pb": float(pb) if pb is not None else None,
            "pb_avg": float(valuation["pb_avg"]) if valuation.get("pb_avg") is not None else None,
            "pb_percent": float(valuation["pb_percent"]) if valuation.get("pb_percent") is not None else None,
            "trade_date": valuation.get("trade_date"),
            "source": "GF-Skills common_basic_post",
        }

    @staticmethod
    def get_financial_indicators(
        symbol: str, year: str, report_type: int
    ) -> Optional[dict]:
        """工具2：财务指标对比（必须传2只股票）

        Args:
            symbol: 6位股票代码
            year: 报告年份，如 "2024"
            report_type: 报告期类型 1=一季报 6=中报 9=三季报 12=年报

        返回目标股票的财务指标字典（已从对比结果中提取出目标股票）：
            - roe: ROE（%）
            - net_profit2totalincome: 营业净利率（%）
            - sale_gross_rate: 销售毛利率（%）
            - liablity2asset: 资产负债率（%）
            - equity2asset: 股东权益/总资产（%）
            - liab2equity: 产权比率
            - quick_ratio: 速动比率
            - cashflow_oper2income: 收现比
            - net_cashflow_oper2net_profit: 净现比
            - net_cashflow_oper_ps: 每股经营现金流
            - operate_income_yoy: 营收同比（%）
            - net_profit_yoy: 净利润同比（%）
            - total_asset_yoy: 总资产增长率（%）
            - equity_growth_rate: 净资产增长率（%）
            - inventory_turnover: 存货周转率
            - acctreceivable_turnover: 应收账款周转率
            - currentasset_turnover: 流动资产周转率
            - totalasset_turnover: 总资产周转率
            - goodwill2equity: 商誉/股东权益（%）
            - interest_coverage_ratio: 利息保障倍数
            - end_date: 财报截止日期
            - peer_stock_code: 对比股代码
            - peer_stock_name: 对比股名称
        """
        if report_type not in (1, 6, 9, 12):
            logger.warning(f"⚠️ [广发] report_type 必须是 1/6/9/12，收到: {report_type}")
            return None

        gf_code = _to_gf_code(symbol)
        if not gf_code:
            return None

        peer_code = _get_peer(symbol)
        gf_peer = _to_gf_code(peer_code)

        inner = _call_api("quant", "compare_indicator_post", {
            "report_type": report_type,
            "stock_codes": [gf_code, gf_peer],
            "year": str(year),
        })
        if not inner:
            return None

        data_obj = inner.get("data", {})
        data_list = data_obj.get("data", []) if isinstance(data_obj, dict) else []
        if not data_list:
            logger.warning(f"⚠️ [广发] 工具2返回空数据: {symbol}")
            return None

        # 从对比结果中提取目标股票
        target = next((x for x in data_list if x.get("stock_code") == gf_code), None)
        peer = next((x for x in data_list if x.get("stock_code") == gf_peer), None)

        if not target:
            logger.warning(f"⚠️ [广发] 工具2未找到目标股票 {gf_code}，返回: {data_list}")
            return None

        result = {k: v for k, v in target.items() if v is not None}
        result["peer_stock_code"] = peer.get("stock_code") if peer else None
        result["peer_stock_name"] = peer.get("stock_name") if peer else None
        result["source"] = "GF-Skills compare_indicator_post"
        return result
