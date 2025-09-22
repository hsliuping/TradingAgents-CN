#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/5/16 19:00
Desc: 债券-集思录-可转债
集思录：https://www.jisilu.cn/data/cbnew/#cb
"""

from io import StringIO
import pandas as pd
import requests
import time

from akshare.utils import demjson


def bond_cb_index_jsl() -> pd.DataFrame:
    """
    首页-可转债-集思录可转债等权指数
    https://www.jisilu.cn/web/data/cb/index
    :return: 集思录可转债等权指数
    :rtype: pandas.DataFrame
    """
    url = "https://www.jisilu.cn/webapi/cb/index_history/"
    r = requests.get(url)
    data_dict = demjson.decode(r.text)["data"]
    temp_df = pd.DataFrame(data_dict)
    return temp_df


def bond_cb_jsl(cookie: str = None) -> pd.DataFrame:
    """
    集思录可转债
    https://www.jisilu.cn/data/cbnew/#cb
    :param cookie: 输入获取到的游览器 cookie
    :type cookie: str
    :return: 集思录可转债
    :rtype: pandas.DataFrame
    """
    url = "https://www.jisilu.cn/data/cbnew/cb_list_new/"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "content-length": "220",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "cookie": cookie,
        "origin": "https://www.jisilu.cn",
        "pragma": "no-cache",
        "referer": "https://www.jisilu.cn/data/cbnew/",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.164 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
    }
    params = {
        "___jsl": f"LST___t={int(time.time() * 1000)}",
    }
    payload = {
        "fprice": "",
        "tprice": "",
        "curr_iss_amt": "",
        "volume": "",
        "svolume": "",
        "premium_rt": "",
        "ytm_rt": "",
        "market": "",
        "rating_cd": "",
        "is_search": "N",
        "market_cd[]": "shmb",  # noqa: F601
        "market_cd[]": "shkc",  # noqa: F601
        "market_cd[]": "szmb",  # noqa: F601
        "market_cd[]": "szcy",  # noqa: F601
        "btype": "",
        "listed": "Y",
        "qflag": "N",
        "sw_cd": "",
        "bond_ids": "",
        "rp": "50",
    }
    r = requests.post(url, params=params, json=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame([item["cell"] for item in data_json["rows"]])
    temp_df.rename(
        columns={
            "bond_id": "代码",
            "bond_nm": "转债名称",
            "price": "现价",
            "increase_rt": "涨跌幅",
            "stock_id": "正股代码",
            "stock_nm": "正股名称",
            "sprice": "正股价",
            "sincrease_rt": "正股涨跌",
            "pb": "正股PB",
            "convert_price": "转股价",
            "convert_value": "转股价值",
            "premium_rt": "转股溢价率",
            "dblow": "双低",
            "rating_cd": "债券评级",
            "put_convert_price": "回售触发价",
            "force_redeem_price": "强赎触发价",
            "convert_amt_ratio": "转债占比",
            "maturity_dt": "到期时间",
            "year_left": "剩余年限",
            "curr_iss_amt": "剩余规模",
            "volume": "成交额",
            "turnover_rt": "换手率",
            "ytm_rt": "到期税前收益",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "代码",
            "转债名称",
            "现价",
            "涨跌幅",
            "正股代码",
            "正股名称",
            "正股价",
            "正股涨跌",
            "正股PB",
            "转股价",
            "转股价值",
            "转股溢价率",
            "债券评级",
            "回售触发价",
            "强赎触发价",
            "转债占比",
            "到期时间",
            "剩余年限",
            "剩余规模",
            "成交额",
            "换手率",
            "到期税前收益",
            "双低",
        ]
    ]
    temp_df["到期时间"] = pd.to_datetime(temp_df["到期时间"], errors="coerce").dt.date
    temp_df["现价"] = pd.to_numeric(temp_df["现价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["正股价"] = pd.to_numeric(temp_df["正股价"], errors="coerce")
    temp_df["正股涨跌"] = pd.to_numeric(temp_df["正股涨跌"], errors="coerce")
    temp_df["正股PB"] = pd.to_numeric(temp_df["正股PB"], errors="coerce")
    temp_df["转股价"] = pd.to_numeric(temp_df["转股价"], errors="coerce")
    temp_df["转股价值"] = pd.to_numeric(temp_df["转股价值"], errors="coerce")
    temp_df["转股溢价率"] = pd.to_numeric(temp_df["转股溢价率"], errors="coerce")
    temp_df["回售触发价"] = pd.to_numeric(temp_df["回售触发价"], errors="coerce")
    temp_df["强赎触发价"] = pd.to_numeric(temp_df["强赎触发价"], errors="coerce")
    temp_df["转债占比"] = pd.to_numeric(temp_df["转债占比"], errors="coerce")
    temp_df["剩余年限"] = pd.to_numeric(temp_df["剩余年限"], errors="coerce")
    temp_df["剩余规模"] = pd.to_numeric(temp_df["剩余规模"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["到期税前收益"] = pd.to_numeric(temp_df["到期税前收益"], errors="coerce")
    return temp_df


def bond_cb_redeem_jsl() -> pd.DataFrame:
    """
    集思录可转债-强赎
    https://www.jisilu.cn/data/cbnew/#redeem
    :return: 集思录可转债-强赎
    :rtype: pandas.DataFrame
    """
    url = "https://www.jisilu.cn/data/cbnew/redeem_list/"
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "5",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.jisilu.cn",
        "Origin": "https://www.jisilu.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.jisilu.cn/data/cbnew/",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/101.0.4951.67 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "___jsl": "LST___t=1653394005966",
    }
    payload = {
        "rp": "50",
    }
    r = requests.post(url, params=params, json=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame([item["cell"] for item in data_json["rows"]])
    temp_df.rename(
        columns={
            "bond_id": "代码",
            "bond_nm": "名称",
            "price": "现价",
            "stock_id": "正股代码",
            "stock_nm": "正股名称",
            "margin_flg": "-",
            "btype": "-",
            "orig_iss_amt": "规模",
            "curr_iss_amt": "剩余规模",
            "convert_dt": "转股起始日",
            "convert_price": "转股价",
            "next_put_dt": "-",
            "redeem_dt": "-",
            "force_redeem": "-",
            "redeem_flag": "-",
            "redeem_price": "-",
            "redeem_price_ratio": "强赎触发比",
            "real_force_redeem_price": "强赎价",
            "redeem_remain_days": "-",
            "redeem_real_days": "-",
            "redeem_total_days": "-",
            "recount_dt": "-",
            "redeem_count_days": "-",
            "redeem_tc": "强赎条款",
            "sprice": "正股价",
            "delist_dt": "最后交易日",
            "maturity_dt": "到期日",
            "redeem_icon": "强赎状态",
            "redeem_orders": "-",
            "at_maturity": "-",
            "redeem_count": "强赎天计数",
            "after_next_put_dt": "-",
            "force_redeem_price": "强赎触发价",
        },
        inplace=True,
    )

    temp_df = temp_df[
        [
            "代码",
            "名称",
            "现价",
            "正股代码",
            "正股名称",
            "规模",
            "剩余规模",
            "转股起始日",
            "最后交易日",
            "到期日",
            "转股价",
            "强赎触发比",
            "强赎触发价",
            "正股价",
            "强赎价",
            "强赎天计数",
            "强赎条款",
            "强赎状态",
        ]
    ]
    temp_df["现价"] = pd.to_numeric(temp_df["现价"], errors="coerce")
    temp_df["规模"] = pd.to_numeric(temp_df["规模"], errors="coerce")
    temp_df["剩余规模"] = pd.to_numeric(temp_df["剩余规模"], errors="coerce")
    temp_df["转股起始日"] = pd.to_datetime(
        temp_df["转股起始日"], errors="coerce"
    ).dt.date
    temp_df["最后交易日"] = pd.to_datetime(
        temp_df["最后交易日"], errors="coerce"
    ).dt.date
    temp_df["到期日"] = pd.to_datetime(temp_df["到期日"], errors="coerce").dt.date
    temp_df["转股价"] = pd.to_numeric(temp_df["转股价"], errors="coerce")
    temp_df["强赎触发比"] = pd.to_numeric(
        temp_df["强赎触发比"].str.strip("%"), errors="coerce"
    )
    temp_df["强赎触发价"] = pd.to_numeric(temp_df["强赎触发价"], errors="coerce")
    temp_df["正股价"] = pd.to_numeric(temp_df["正股价"], errors="coerce")
    temp_df["强赎价"] = pd.to_numeric(temp_df["强赎价"], errors="coerce")
    temp_df["强赎天计数"] = temp_df["强赎天计数"].replace(
        r"^.*?(\d{1,2}\/\d{1,2} \| \d{1,2}).*?$", r"\1", regex=True
    )
    temp_df["强赎状态"] = temp_df["强赎状态"].map(
        {
            "R": "已公告强赎",
            "O": "公告要强赎",
            "G": "公告不强赎",
            "B": "已满足强赎条件",
            "": "",
        }
    )
    return temp_df


def bond_cb_adj_logs_jsl(symbol: str = "128013") -> pd.DataFrame:
    """
    集思录-可转债转股价-调整记录
    https://www.jisilu.cn/data/cbnew/#cb
    :param symbol: 可转债代码
    :type symbol: str
    :return: 转股价调整记录
    :rtype: pandas.DataFrame
    """
    url = f"https://www.jisilu.cn/data/cbnew/adj_logs/?bond_id={symbol}"
    r = requests.get(url)
    data_text = r.text
    if "</table>" not in data_text:
        # 1. 该可转债没有转股价调整记录，服务端返回文本 '暂无数据'
        # 2. 无效可转债代码，服务端返回 {"timestamp":1639565628,"isError":1,"msg":"无效代码格式"}
        # 以上两种情况，返回空的 DataFrame
        return pd.DataFrame()
    else:
        temp_df = pd.read_html(StringIO(data_text), parse_dates=True)[0]
        temp_df.columns = [item.replace(" ", "") for item in temp_df.columns]
        temp_df["下修前转股价"] = pd.to_numeric(
            temp_df["下修前转股价"], errors="coerce"
        )
        temp_df["下修后转股价"] = pd.to_numeric(
            temp_df["下修后转股价"], errors="coerce"
        )
        temp_df["下修底价"] = pd.to_numeric(temp_df["下修底价"], errors="coerce")
        temp_df["股东大会日"] = pd.to_datetime(
            temp_df["股东大会日"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
        temp_df["新转股价生效日期"] = pd.to_datetime(
            temp_df["新转股价生效日期"], format="%Y-%m-%d", errors="coerce"
        ).dt.date
        return temp_df


if __name__ == "__main__":
    bond_cb_index_jsl_df = bond_cb_index_jsl()
    print(bond_cb_index_jsl_df)

    bond_cb_jsl_df = bond_cb_jsl(cookie="")
    print(bond_cb_jsl_df)

    bond_cb_redeem_jsl_df = bond_cb_redeem_jsl()
    print(bond_cb_redeem_jsl_df)

    bond_cb_adj_logs_jsl_df = bond_cb_adj_logs_jsl(symbol="128013")
    print(bond_cb_adj_logs_jsl_df)
