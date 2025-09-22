"""
Yang-Zhang-s-Realized-Volatility-Automated-Estimation-in-Python
https://github.com/hugogobato/Yang-Zhang-s-Realized-Volatility-Automated-Estimation-in-Python
论文地址：https://www.jstor.org/stable/10.1086/209650
"""

import warnings

import numpy as np
import pandas as pd


def rv_from_stock_zh_a_hist_min_em(
    symbol="000001",
    start_date="2021-10-20 09:30:00",
    end_date="2024-11-01 15:00:00",
    period="1",
    adjust="hfq",
) -> pd.DataFrame:
    """
    从东方财富网获取股票的分钟级历史行情数据,并进行数据清洗和格式化为计算 yz 已实现波动率所需的数据格式
    https://quote.eastmoney.com/concept/sh603777.html?from=classic
    :param symbol: 股票代码,如"000001"
    :type symbol: str
    :param start_date: 开始日期时间,格式"YYYY-MM-DD HH:MM:SS"
    :type start_date: str
    :param end_date: 结束日期时间,格式"YYYY-MM-DD HH:MM:SS"
    :type end_date: str
    :param period: 时间周期,可选{'1','5','15','30','60'}分钟
    :type period: str
    :param adjust: 复权方式,可选{'','qfq'(前复权),'hfq'(后复权)}
    :type adjust: str
    :return: 整理后的分钟行情数据,包含Date(索引),Open,High,Low,Close列
    :rtype: pandas.DataFrame
    """
    from akshare.stock_feature.stock_hist_em import stock_zh_a_hist_min_em

    temp_df = stock_zh_a_hist_min_em(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        period=period,
        adjust=adjust,
    )
    temp_df.rename(
        columns={
            "时间": "Date",
            "开盘": "Open",
            "最高": "High",
            "最低": "Low",
            "收盘": "Close",
        },
        inplace=True,
    )
    temp_df = temp_df[temp_df["Open"] != 0]
    temp_df["Date"] = pd.to_datetime(temp_df["Date"])
    temp_df.set_index(keys="Date", inplace=True)
    return temp_df


def rv_from_futures_zh_minute_sina(
    symbol: str = "IF2008", period: str = "5"
) -> pd.DataFrame:
    """
    从新浪财经获取期货的分钟级历史行情数据,并进行数据清洗和格式化
    https://vip.stock.finance.sina.com.cn/quotes_service/view/qihuohangqing.html#titlePos_3
    :param symbol: 期货合约代码,如"IF2008"代表沪深300期货2020年8月合约
    :type symbol: str
    :param period: 时间周期,可选{'1','5','15','30','60'}分钟
    :type period: str
    :return: 整理后的分钟行情数据,包含Date(索引),Open,High,Low,Close列
    :rtype: pandas.DataFrame
    """
    from akshare.futures.futures_zh_sina import futures_zh_minute_sina

    temp_df = futures_zh_minute_sina(symbol=symbol, period=period)
    temp_df.rename(
        columns={
            "datetime": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
        },
        inplace=True,
    )
    temp_df["Date"] = pd.to_datetime(temp_df["Date"])
    temp_df.set_index(keys="Date", inplace=True)
    return temp_df


def volatility_yz_rv(data: pd.DataFrame) -> pd.DataFrame:
    """
    波动率-已实现波动率-Yang-Zhang 已实现波动率(Yang-Zhang Realized Volatility)
    https://github.com/hugogobato/Yang-Zhang-s-Realized-Volatility-Automated-Estimation-in-Python
    论文地址：https://www.jstor.org/stable/10.1086/209650
    基于以下公式计算:
    RV^2 = Vo + k*Vc + (1-k)*Vrs
    其中:
    - Vo: 隔夜波动率, Vo = 1/(n-1)*sum(Oi-Obar)^2
        Oi为标准化开盘价, Obar为标准化开盘价均值
    - Vc: 收盘波动率, Vc = 1/(n-1)*sum(ci-Cbar)^2
        ci为标准化收盘价, Cbar为标准化收盘价均值
    - k: 权重系数, k = 0.34/(1.34+(n+1)/(n-1))
        n为样本数量
    - Vrs: Rogers-Satchell波动率代理, Vrs = ui(ui-ci)+di(di-ci)
        ui = ln(Hi/Oi), ci = ln(Ci/Oi), di = ln(Li/Oi), oi = ln(Oi/Ci-1)
        Hi/Li/Ci/Oi分别为最高价/最低价/收盘价/开盘价

    :param data: 包含 OHLC(开高低收) 价格的 pandas.DataFrame
    :type data: pandas.DataFrame
    :return: 包含 Yang-Zhang 实现波动率的 pandas.DataFrame
    :rtype: pandas.DataFrame

    要求输入数据包含以下列:
    - Open: 开盘价
    - High: 最高价
    - Low: 最低价
    - Close: 收盘价
    # yang_zhang_rv formula is give as:
    # RV^2 = Vo + k*Vc + (1-k)*Vrs
    # where Vo = 1/(n-1)*sum(Oi-Obar)^2
    # with oi = normalized opening price at time t and Obar = mean of normalized opening prices
    # Vc = = 1/(n-1)*sum(ci-Cbar)^2
    # with ci = normalized close price at time t and Cbar = mean of normalized close prices
    # k = 0.34/(1.34+(n+1)/(n-1))
    # with n = total number of days or time periods considered
    # Vrs (Rogers & Satchell RV proxy) = ui(ui-ci)+di(di-ci)
    # with ui = ln(Hi/Oi), ci = ln(Ci/Oi), di=(Li/Oi), oi = ln(Oi/Ci-1)
    # where Hi = high price at time t and Li = low price at time t
    """ ""
    warnings.filterwarnings("ignore")

    data["ui"] = np.log(np.divide(data["High"][1:], data["Open"][1:]))
    data["ci"] = np.log(np.divide(data["Close"][1:], data["Open"][1:]))
    data["di"] = np.log(np.divide(data["Low"][1:], data["Open"][1:]))
    data["oi"] = np.log(np.divide(data["Open"][1:], data["Close"][: len(data) - 1]))
    data = data[1:]
    data["RS"] = data["ui"] * (data["ui"] - data["ci"]) + data["di"] * (
        data["di"] - data["ci"]
    )
    rs_var = data["RS"].groupby(pd.Grouper(freq="1D")).mean().dropna()
    vc_and_vo = data[["oi", "ci"]].groupby(pd.Grouper(freq="1D")).var().dropna()
    n = int(len(data) / len(rs_var))
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    yang_zhang_rv = np.sqrt((1 - k) * rs_var + vc_and_vo["oi"] + vc_and_vo["ci"] * k)
    yang_zhang_rv_df = pd.DataFrame(yang_zhang_rv)
    yang_zhang_rv_df.rename(columns={0: "yz_rv"}, inplace=True)
    yang_zhang_rv_df.reset_index(inplace=True)
    yang_zhang_rv_df.columns = ["date", "rv"]
    yang_zhang_rv_df["date"] = pd.to_datetime(
        yang_zhang_rv_df["date"], errors="coerce"
    ).dt.date
    return yang_zhang_rv_df


if __name__ == "__main__":
    futures_df = rv_from_futures_zh_minute_sina(symbol="IF2008", period="1")
    volatility_yz_rv_df = volatility_yz_rv(data=futures_df)
    print(volatility_yz_rv_df)

    stock_df = rv_from_stock_zh_a_hist_min_em(
        symbol="000001",
        start_date="2021-10-20 09:30:00",
        end_date="2024-11-01 15:00:00",
        period="5",
        adjust="",
    )
    volatility_yz_rv_df = volatility_yz_rv(data=stock_df)
    print(volatility_yz_rv_df)
