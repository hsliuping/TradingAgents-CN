"""
数据质量验证器
在基本面数据进入LLM之前进行合理性校验，防止异常数据误导分析
"""
from typing import Dict, Any, Optional, List, Tuple
import math

# 行业合理估值范围映射表
# 格式: (行业关键词) -> {pe: (下界, 上界), pb: (下界, 上界)}
INDUSTRY_VALUATION_RANGES = {
    "白酒":       {"pe": (10, 50),   "pb": (2, 15)},
    "银行":       {"pe": (3, 12),    "pb": (0.2, 1.5)},
    "证券":       {"pe": (8, 35),    "pb": (0.5, 3)},
    "保险":       {"pe": (5, 25),    "pb": (0.3, 2.5)},
    "黄金":       {"pe": (8, 40),    "pb": (1, 5)},
    "有色金属":   {"pe": (8, 40),    "pb": (1, 5)},
    "矿业":       {"pe": (8, 40),    "pb": (1, 5)},
    "钢铁":       {"pe": (5, 30),    "pb": (0.5, 3)},
    "航空":       {"pe": (5, 50),    "pb": (0.5, 3)},
    "物流":       {"pe": (8, 30),    "pb": (1, 3.5)},
    "医药":       {"pe": (15, 60),   "pb": (2, 10)},
    "消费":       {"pe": (10, 50),   "pb": (2, 10)},
}

# PE/PB 的绝对合理范围（任何行业不应超出）
GLOBAL_PE_RANGE = (1, 200)
GLOBAL_PB_RANGE = (0.05, 50)


def detect_industry(company_name: str, sector: str = "") -> List[str]:
    """从公司名称和板块信息中检测所属行业"""
    text = f"{company_name} {sector}"
    matched = []
    for keyword in INDUSTRY_VALUATION_RANGES:
        if keyword in text:
            matched.append(keyword)
    return matched


def validate_pe(
    pe: Optional[float],
    company_name: str,
    sector: str = "",
    stock_code: str = ""
) -> Dict[str, Any]:
    """
    验证 PE 合理性，返回验证结果和修正建议

    Args:
        pe: 原始 PE 值
        company_name: 公司名称
        sector: 板块/行业信息
        stock_code: 股票代码

    Returns:
        {
            "original": 原始PE,
            "is_valid": 是否合理,
            "severity": "normal" | "warning" | "error",
            "message": 验证信息,
            "suggested_action": "use_as_is" | "flag_for_llm" | "use_annual_instead",
            "industry_pe_range": 行业PE范围或None,
        }
    """
    if pe is None or math.isnan(pe) or pe <= 0:
        return {
            "original": pe,
            "is_valid": False,
            "severity": "error",
            "message": f"PE 无效 (值={pe})",
            "suggested_action": "flag_for_llm",
            "industry_pe_range": None,
        }

    # 检查全局范围
    if pe < GLOBAL_PE_RANGE[0] or pe > GLOBAL_PE_RANGE[1]:
        return {
            "original": pe,
            "is_valid": False,
            "severity": "error",
            "message": f"PE={pe:.1f} 超出全局合理范围 [{GLOBAL_PE_RANGE[0]}, {GLOBAL_PE_RANGE[1]}]",
            "suggested_action": "flag_for_llm",
            "industry_pe_range": None,
        }

    # 检查行业范围
    industries = detect_industry(company_name, sector)
    industry_pe_range = None

    for ind in industries:
        ind_range = INDUSTRY_VALUATION_RANGES[ind]["pe"]
        if industry_pe_range is None:
            industry_pe_range = list(ind_range)
        else:
            # 合并范围
            industry_pe_range[0] = min(industry_pe_range[0], ind_range[0])
            industry_pe_range[1] = max(industry_pe_range[1], ind_range[1])

    if industry_pe_range:
        low, high = industry_pe_range
        if pe < low * 0.3:  # 低于行业下限70%以上
            return {
                "original": pe,
                "is_valid": True,  # 可能有效但需要标注
                "severity": "warning",
                "message": f"PE={pe:.1f} 远低于行业{industries}范围 [{low}, {high}]，"
                          f"可能是TTM利润异常导致，建议核实年报数据",
                "suggested_action": "flag_for_llm",
                "industry_pe_range": (low, high),
            }
        elif pe > high * 1.5:  # 高于行业上限50%以上
            return {
                "original": pe,
                "is_valid": True,
                "severity": "warning",
                "message": f"PE={pe:.1f} 远超行业{industries}范围 [{low}, {high}]，"
                          f"可能是TTM利润异常偏低导致",
                "suggested_action": "flag_for_llm",
                "industry_pe_range": (low, high),
            }
        elif pe < low or pe > high:
            return {
                "original": pe,
                "is_valid": True,
                "severity": "normal",
                "message": f"PE={pe:.1f} 略超出行业{industries}范围 [{low}, {high}]，在可接受偏差内",
                "suggested_action": "use_as_is",
                "industry_pe_range": (low, high),
            }

    return {
        "original": pe,
        "is_valid": True,
        "severity": "normal",
        "message": f"PE={pe:.1f} 在合理范围内",
        "suggested_action": "use_as_is",
        "industry_pe_range": industry_pe_range,
    }


def validate_pb(
    pb: Optional[float],
    company_name: str,
    sector: str = ""
) -> Dict[str, Any]:
    """验证 PB 合理性"""
    if pb is None or math.isnan(pb) or pb <= 0:
        return {
            "original": pb, "is_valid": False,
            "severity": "error", "suggested_action": "flag_for_llm",
            "message": f"PB 无效 (值={pb})",
        }
    if pb < GLOBAL_PB_RANGE[0] or pb > GLOBAL_PB_RANGE[1]:
        return {
            "original": pb, "is_valid": False,
            "severity": "error", "suggested_action": "flag_for_llm",
            "message": f"PB={pb:.2f} 超出全局合理范围",
        }
    return {
        "original": pb, "is_valid": True,
        "severity": "normal", "suggested_action": "use_as_is",
        "message": f"PB={pb:.2f} 在合理范围内",
    }


def annotate_fundamentals_with_validation(
    fundamentals_data: Dict[str, Any],
    company_name: str,
    sector: str = "",
    stock_code: str = "",
) -> Dict[str, Any]:
    """
    对基本面数据添加验证注解，在传给LLM之前标注数据质量

    返回新增的验证字段，而非修改原始数据
    """
    annotations = {}

    # PE 验证
    pe = fundamentals_data.get("pe")
    if pe is not None:
        pe_check = validate_pe(pe, company_name, sector, stock_code)
        annotations["pe_validation"] = pe_check
        if pe_check["severity"] == "warning":
            # 添加年报参考提示
            annotations["pe_annual_hint"] = (
                "⚠️ 注意：当前PE为TTM（滚动12个月）数据，可能因单季利润波动失真。"
                "建议参考年报净利重新计算。"
            )

    # PB 验证
    pb = fundamentals_data.get("pb")
    if pb is not None:
        pb_check = validate_pb(pb, company_name, sector)
        annotations["pb_validation"] = pb_check

    return annotations
