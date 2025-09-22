#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/10/27 22:30
Desc: 雪球基金-基金详情
https://danjuanfunds.com/funding/003545
"""

import pandas as pd
import requests


def fund_individual_basic_info_xq(
    symbol: str = "000001", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-基金详情
    https://danjuanfunds.com/djapi/fund/675091
    :param symbol: 基金代码
    :type symbol: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 基金信息
    :rtype: pandas.DataFrame
    """
    url = f"https://danjuanfunds.com/djapi/fund/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    json_data = r.json()["data"]
    temp_df = pd.json_normalize(json_data)
    temp_df.rename(
        columns={
            "fd_code": "基金代码",
            "fd_name": "基金名称",
            "fd_full_name": "基金全称",
            "found_date": "成立时间",
            "totshare": "最新规模",
            "keeper_name": "基金公司",
            "manager_name": "基金经理",
            "trup_name": "托管银行",
            "type_desc": "基金类型",
            "rating_source": "评级机构",
            "rating_desc": "基金评级",
            "invest_orientation": "投资策略",
            "invest_target": "投资目标",
            "performance_bench_mark": "业绩比较基准",
        },
        inplace=True,
    )
    if "评级机构" not in temp_df.columns:
        temp_df["评级机构"] = pd.NA
    temp_df = temp_df[
        [
            "基金代码",
            "基金名称",
            "基金全称",
            "成立时间",
            "最新规模",
            "基金公司",
            "基金经理",
            "托管银行",
            "基金类型",
            "评级机构",
            "基金评级",
            "投资策略",
            "投资目标",
            "业绩比较基准",
        ]
    ]
    temp_df = temp_df.T.reset_index()
    temp_df.columns = ["item", "value"]
    return temp_df


def fund_individual_achievement_xq(
    symbol: str = "000001", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-基金业绩
    https://danjuanfunds.com/djapi/fundx/base/fund/achievement/675091
    :param symbol: 基金代码
    :type symbol: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 基金业绩
    :rtype: pandas.DataFrame
    """
    url = f"https://danjuanfunds.com/djapi/fundx/base/fund/achievement/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    json_data = r.json()["data"]
    combined_df = None
    type_dict = {
        "annual_performance_list": "年度业绩",
        "stage_performance_list": "阶段业绩",
    }
    for k, v in type_dict.items():
        temp_df = pd.DataFrame.from_dict(json_data[k], orient="columns")
        temp_df["type"] = v
        temp_df = temp_df[
            [
                "type",
                "period_time",
                "self_nav",
                "self_max_draw_down",
                "self_nav_rank",
            ]
        ]
        temp_df.columns = [
            "业绩类型",
            "周期",
            "本产品区间收益",
            "本产品最大回撒",
            "周期收益同类排名",
        ]
        combined_df = pd.concat([combined_df, temp_df], ignore_index=True)
    combined_df = combined_df.map(
        lambda x: x if "%" not in str(x) else x.replace("%", "")
    )
    combined_df[["本产品区间收益", "本产品最大回撒"]] = combined_df[
        ["本产品区间收益", "本产品最大回撒"]
    ].astype(float)
    return combined_df


def fund_individual_analysis_xq(
    symbol: str = "000001", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-基金数据分析
    https://danjuanfunds.com/djapi/fund/base/quote/data/index/analysis/675091
    :param symbol: 基金代码
    :type symbol: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 基金数据分析
    :rtype: pandas.DataFrame
    """
    url = f"https://danjuanfunds.com/djapi/fund/base/quote/data/index/analysis/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    json_data = r.json()["data"]["index_data_list"]
    temp_df = pd.json_normalize(json_data)
    temp_df = temp_df[
        [
            "index_time_period",
            "investment_cost_performance",
            "risk_control",
            "self_index.volatility_rank",
            "self_index.sharpe_rank",
            "self_index.max_draw_down",
        ]
    ]
    temp_df.columns = [
        "周期",
        "较同类风险收益比",
        "较同类抗风险波动",
        "年化波动率",
        "年化夏普比率",
        "最大回撤",
    ]
    temp_df = temp_df.map(lambda x: x if "%" not in str(x) else x.replace("%", ""))
    temp_df[["年化波动率", "最大回撤"]] *= 100
    temp_df["较同类风险收益比"] = pd.to_numeric(
        temp_df["较同类风险收益比"], errors="coerce"
    )
    temp_df["较同类抗风险波动"] = pd.to_numeric(
        temp_df["较同类抗风险波动"], errors="coerce"
    )
    temp_df["年化波动率"] = pd.to_numeric(temp_df["年化波动率"], errors="coerce")
    temp_df["年化夏普比率"] = pd.to_numeric(temp_df["年化夏普比率"], errors="coerce")
    temp_df["最大回撤"] = pd.to_numeric(temp_df["最大回撤"], errors="coerce")
    return temp_df


def fund_individual_profit_probability_xq(
    symbol: str = "000001", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-盈利概率-历史任意时点买入，持有满 X 年，盈利概率 Y%
    https://danjuanfunds.com/djapi/fundx/base/fund/profit/ratio/675091
    :param symbol: 基金代码
    :type symbol: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 盈利概率
    :rtype: pandas.DataFrame
    """
    url = f"https://danjuanfunds.com/djapi/fundx/base/fund/profit/ratio/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    json_data = r.json()["data"]["data_list"]
    temp_df = pd.DataFrame.from_dict(json_data, orient="columns")
    temp_df = temp_df[
        [
            "holding_time",
            "profit_ratio",
            "average_income",
        ]
    ]
    temp_df.columns = [
        "持有时长",
        "盈利概率",
        "平均收益",
    ]
    temp_df = temp_df.map(lambda x: x if "%" not in str(x) else x.replace("%", ""))
    temp_df["盈利概率"] = pd.to_numeric(temp_df["盈利概率"], errors="coerce")
    temp_df["平均收益"] = pd.to_numeric(temp_df["平均收益"], errors="coerce")
    return temp_df


def fund_individual_detail_info_xq(
    symbol: str = "000001", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-交易规则
    https://danjuanfunds.com/djapi/fund/detail/675091
    :param symbol: 基金代码
    :type symbol: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 交易规则
    :rtype: pandas.DataFrame
    """
    url = f"https://danjuanfunds.com/djapi/fund/detail/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    json_data = r.json()["data"]
    combined_df = None
    rate_type_dict = {
        "declare_rate_table": "买入规则",
        "withdraw_rate_table": "卖出规则",
        "other_rate_table": "其他费用",
    }
    for k, v in rate_type_dict.items():
        temp_df = pd.DataFrame.from_dict(json_data["fund_rates"][k], orient="columns")
        temp_df["rate_type"] = v
        temp_df = temp_df[
            [
                "rate_type",
                "name",
                "value",
            ]
        ]
        temp_df.columns = [
            "费用类型",
            "条件或名称",
            "费用",
        ]
        combined_df = pd.concat(objs=[combined_df, temp_df], ignore_index=True)
        combined_df["费用"] = pd.to_numeric(combined_df["费用"], errors="coerce")
    return combined_df


def fund_individual_detail_hold_xq(
    symbol: str = "002804", date: str = "20231231", timeout: float = None
) -> pd.DataFrame:
    """
    雪球基金-持仓
    https://danjuanfunds.com/rn/fund-detail/archive?id=103&code=002804
    :param symbol: 基金代码
    :type symbol: str
    :param date: 财报日期
    :type date: str
    :param timeout: choice of None or a positive float number
    :type timeout: float
    :return: 雪球基金-持仓
    :rtype: pandas.DataFrame
    """
    url = "https://danjuanfunds.com/djapi/fundx/base/fund/record/asset/percent"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.149 Safari/537.36"
    }
    params = {
        "fund_code": f"{symbol}",
        "report_date": f"{'-'.join([date[:4], date[4:6], date[6:]])}",
    }
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    data_json = r.json()
    temp_df = pd.DataFrame.from_dict(data_json["data"]["chart_list"], orient="columns")
    temp_df = temp_df[
        [
            "type_desc",
            "percent",
        ]
    ]
    temp_df.columns = [
        "资产类型",
        "仓位占比",
    ]
    temp_df["仓位占比"] = pd.to_numeric(temp_df["仓位占比"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    fund_individual_basic_info_xq_df = fund_individual_basic_info_xq(symbol="000005")
    print(fund_individual_basic_info_xq_df)

    fund_individual_achievement_xq_df = fund_individual_achievement_xq(symbol="000001")
    print(fund_individual_achievement_xq_df)

    fund_individual_analysis_xq_df = fund_individual_analysis_xq(symbol="000001")
    print(fund_individual_analysis_xq_df)

    fund_individual_profit_probability_xq_df = fund_individual_profit_probability_xq(
        symbol="000001"
    )
    print(fund_individual_profit_probability_xq_df)

    fund_individual_detail_info_xq_df = fund_individual_detail_info_xq(symbol="000001")
    print(fund_individual_detail_info_xq_df)

    fund_individual_detail_hold_xq_df = fund_individual_detail_hold_xq(
        symbol="002804", date="20231231"
    )
    print(fund_individual_detail_hold_xq_df)
