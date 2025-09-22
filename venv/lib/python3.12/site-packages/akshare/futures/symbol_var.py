#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/7/21 15:00
Desc: 期货品种映射表
"""

import re

from akshare.futures import cons


def symbol_varieties(contract_code: str):
    """
    查找到具体合约代码, 返回大写字母的品种名称
    :param contract_code: ru1801
    :return: RU
    """
    symbol_detail = "".join(re.findall(r"\D", contract_code)).upper().strip()
    if symbol_detail == "PTA":
        symbol_detail = "TA"
    return symbol_detail


def symbol_market(symbol_detail: str = "SC"):
    """
    映射出市场代码
    :param symbol_detail:
    :return:
    """
    var_item = symbol_varieties(symbol_detail)
    for market_item, contract_items in cons.market_exchange_symbols.items():
        if var_item in contract_items:
            return market_item


def find_chinese(chinese_string: str):
    """
    查找中文字符
    :param chinese_string: 中文字符串
    :return:
    """
    p = re.compile(r"[\u4e00-\u9fa5]")
    res = re.findall(p, chinese_string)
    return "".join(res)


def chinese_to_english(chinese_var: str):
    """
    映射期货品种中文名称和英文缩写
    :param chinese_var: 期货品种中文名称
    :return: 对应的英文缩写
    """
    chinese_list = [
        "橡胶",
        "天然橡胶",
        "石油沥青",
        "沥青",
        "沥青仓库",
        "沥青(仓库)",
        "沥青厂库",
        "沥青(厂库)",
        "热轧卷板",
        "热轧板卷",
        "燃料油",
        "白银",
        "线材",
        "螺纹钢",
        "铅",
        "铜",
        "铝",
        "锌",
        "黄金",
        "钯金",
        "锡",
        "镍",
        "纸浆",
        "豆一",
        "大豆",
        "豆二",
        "胶合板",
        "玉米",
        "玉米淀粉",
        "聚乙烯",
        "LLDPE",
        "LDPE",
        "豆粕",
        "豆油",
        "大豆油",
        "棕榈油",
        "纤维板",
        "鸡蛋",
        "聚氯乙烯",
        "PVC",
        "聚丙烯",
        "PP",
        "焦炭",
        "焦煤",
        "铁矿石",
        "乙二醇",
        "强麦",
        "强筋小麦",
        " 强筋小麦",
        "硬冬白麦",
        "普麦",
        "硬白小麦",
        "硬白小麦（）",
        "皮棉",
        "棉花",
        "一号棉",
        "白糖",
        "PTA",
        "菜籽油",
        "菜油",
        "早籼稻",
        "早籼",
        "甲醇",
        "柴油",
        "玻璃",
        "油菜籽",
        "菜籽",
        "菜籽粕",
        "菜粕",
        "动力煤",
        "粳稻",
        "晚籼稻",
        "晚籼",
        "硅铁",
        "锰硅",
        "硬麦",
        "棉纱",
        "苹果",
        "原油",
        "中质含硫原油",
        "尿素",
        "20号胶",
        "苯乙烯",
        "不锈钢",
        "粳米",
        "20号胶20",
        "红枣",
        "不锈钢仓库",
        "纯碱",
        "液化石油气",
        "低硫燃料油",
        "纸浆仓库",
        "石油沥青厂库",
        "石油沥青仓库",
        "螺纹钢仓库",
        "螺纹钢厂库",
        "纸浆厂库",
        "低硫燃料油仓库",
        "低硫燃料油厂库",
        "短纤",
        "涤纶短纤",
        "生猪",
        "花生",
        "工业硅",
        "氧化铝",
        "丁二烯橡胶",
        "碳酸锂",
        "氧化铝仓库",
        "氧化铝厂库",
        "烧碱",
        "丁二烯橡胶仓库",
        "丁二烯橡胶厂库",
        "PX",
        "原木",
        "瓶片",
        "纯苯",
        "多晶硅",
    ]
    english_list = [
        "RU",
        "RU",
        "BU",
        "BU",
        "BU",
        "BU",
        "BU2",
        "BU2",
        "HC",
        "HC",
        "FU",
        "AG",
        "WR",
        "RB",
        "PB",
        "CU",
        "AL",
        "ZN",
        "AU",
        "AU",
        "SN",
        "NI",
        "SP",
        "A",
        "A",
        "B",
        "BB",
        "C",
        "CS",
        "L",
        "L",
        "L",
        "M",
        "Y",
        "Y",
        "P",
        "FB",
        "JD",
        "V",
        "V",
        "PP",
        "PP",
        "J",
        "JM",
        "I",
        "EG",
        "WH",
        "WH",
        "WH",
        "PM",
        "PM",
        "PM",
        "PM",
        "CF",
        "CF",
        "CF",
        "SR",
        "TA",
        "OI",
        "OI",
        "RI",
        "ER",
        "MA",
        "MA",
        "FG",
        "RS",
        "RS",
        "RM",
        "RM",
        "ZC",
        "JR",
        "LR",
        "LR",
        "SF",
        "SM",
        "WT",
        "CY",
        "AP",
        "SC",
        "SC",
        "UR",
        "NR",
        "EB",
        "SS",
        "RR",
        "NR",
        "CJ",
        "SS",
        "SA",
        "PG",
        "LU",
        "SP",
        "BU",
        "BU",
        "RB",
        "RB",
        "SP",
        "LU",
        "LU",
        "PF",
        "PF",
        "LH",
        "PK",
        "SI",
        "AO",
        "BR",
        "LC",
        "AO",
        "AO",
        "SH",
        "BR",
        "BR",
        "PX",
        "LG",
        "PR",
        "BZ",
        "PS",
    ]
    pos = chinese_list.index(chinese_var)
    return english_list[pos]


if __name__ == "__main__":
    print(chinese_to_english("苹果"))
    symbol = "rb1801"

    var = symbol_varieties("rb1808")
    print(var)

    market = symbol_market("SP")
    print(market)

    chi = find_chinese("a对方水电费dc大V")
    print(chi)
