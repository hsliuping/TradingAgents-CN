#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/20 20:51
Desc: 修大成主页-Risk Lab-Realized Volatility; Oxford-Man Institute of Quantitative Finance Realized Library
"""

import json

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def article_oman_rv(symbol: str = "FTSE", index: str = "rk_th2") -> pd.DataFrame:
    """
    Oxford-Man Institute of Quantitative Finance Realized Library 的数据
    :param symbol: str ['AEX', 'AORD', 'BFX', 'BSESN', 'BVLG', 'BVSP', 'DJI', 'FCHI', 'FTMIB', 'FTSE', 'GDAXI', 'GSPTSE', 'HSI', 'IBEX', 'IXIC', 'KS11', 'KSE', 'MXX', 'N225', 'NSEI', 'OMXC20', 'OMXHPI', 'OMXSPI', 'OSEAX', 'RUT', 'SMSI', 'SPX', 'SSEC', 'SSMI', 'STI', 'STOXX50E']
    :param index: str 指标 ['medrv', 'rk_twoscale', 'bv', 'rv10', 'rv5', 'rk_th2', 'rv10_ss', 'rsv', 'rv5_ss', 'bv_ss', 'rk_parzen', 'rsv_ss']
    :return: pandas.DataFrame

    The Oxford-Man Institute's "realised library" contains daily non-parametric measures of how volatility financial assets or indexes were in the past. Each day's volatility measure depends solely on financial data from that day. They are driven by the use of the latest innovations in econometric modelling and theory to design them, while we draw our high frequency data from the Thomson Reuters DataScope Tick History database. Realised measures are not volatility forecasts. However, some researchers use these measures as an input into forecasting models. The aim of this line of research is to make financial markets more transparent by exposing how volatility changes through time.

    This Library is used as the basis of some of our own research, which effects its scope, and is made available here to encourage the more widespread exploitation of these methods. It is given 'as is' and solely for informational purposes, please read the disclaimer.

    The volatility data can be visually explored. We make the complete up-to-date dataset available for download. Lists of assets covered and realized measures available are also available.
    | Symbol    | Name                                      | Earliest Available | Latest Available  |
    |-----------|-------------------------------------------|--------------------|-------------------|
    | .AEX      | AEX index                                 | January 03, 2000   | November 28, 2019 |
    | .AORD     | All Ordinaries                            | January 04, 2000   | November 28, 2019 |
    | .BFX      | Bell 20 Index                             | January 03, 2000   | November 28, 2019 |
    | .BSESN    | S&P BSE Sensex                            | January 03, 2000   | November 28, 2019 |
    | .BVLG     | PSI All-Share Index                       | October 15, 2012   | November 28, 2019 |
    | .BVSP     | BVSP BOVESPA Index                        | January 03, 2000   | November 28, 2019 |
    | .DJI      | Dow Jones Industrial Average              | January 03, 2000   | November 27, 2019 |
    | .FCHI     | CAC 40                                    | January 03, 2000   | November 28, 2019 |
    | .FTMIB    | FTSE MIB                                  | June 01, 2009      | November 28, 2019 |
    | .FTSE     | FTSE 100                                  | January 04, 2000   | November 28, 2019 |
    | .GDAXI    | DAX                                       | January 03, 2000   | November 28, 2019 |
    | .GSPTSE   | S&P/TSX Composite index                   | May 02, 2002       | November 28, 2019 |
    | .HSI      | HANG SENG Index                           | January 03, 2000   | November 28, 2019 |
    | .IBEX     | IBEX 35 Index                             | January 03, 2000   | November 28, 2019 |
    | .IXIC     | Nasdaq 100                                | January 03, 2000   | November 27, 2019 |
    | .KS11     | Korea Composite Stock Price Index (KOSPI) | January 04, 2000   | November 28, 2019 |
    | .KSE      | Karachi SE 100 Index                      | January 03, 2000   | November 28, 2019 |
    | .MXX      | IPC Mexico                                | January 03, 2000   | November 28, 2019 |
    | .N225     | Nikkei 225                                | February 02, 2000  | November 28, 2019 |
    | .NSEI     | NIFTY 50                                  | January 03, 2000   | November 28, 2019 |
    | .OMXC20   | OMX Copenhagen 20 Index                   | October 03, 2005   | November 28, 2019 |
    | .OMXHPI   | OMX Helsinki All Share Index              | October 03, 2005   | November 28, 2019 |
    | .OMXSPI   | OMX Stockholm All Share Index             | October 03, 2005   | November 28, 2019 |
    | .OSEAX    | Oslo Exchange All-share Index             | September 03, 2001 | November 28, 2019 |
    | .RUT      | Russel 2000                               | January 03, 2000   | November 27, 2019 |
    | .SMSI     | Madrid General Index                      | July 04, 2005      | November 28, 2019 |
    | .SPX      | S&P 500 Index                             | January 03, 2000   | November 27, 2019 |
    | .SSEC     | Shanghai Composite Index                  | January 04, 2000   | November 28, 2019 |
    | .SSMI     | Swiss Stock Market Index                  | January 04, 2000   | November 28, 2019 |
    | .STI      | Straits Times Index                       | January 03, 2000   | November 28, 2019 |
    | .STOXX50E | EURO STOXX 50                             | January 03, 2000   | November 28, 2019 |
    """
    url = "https://realized.oxford-man.ox.ac.uk/theme/js/visualization-data.js?20191111113154"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "lxml")
    soup_text = soup.find("p").get_text()
    data_json = json.loads(soup_text[soup_text.find("{") : soup_text.rfind("};") + 1])
    date_list = data_json[f".{symbol}"]["dates"]
    temp_df = pd.DataFrame([date_list, data_json[f".{symbol}"][index]["data"]]).T
    temp_df.index = pd.to_datetime(temp_df.iloc[:, 0], unit="ms")
    temp_df = temp_df.iloc[:, 1]
    temp_df.index.name = "date"
    temp_df.name = f"{symbol}-{index}"
    return temp_df


def article_oman_rv_short(symbol: str = "FTSE") -> pd.DataFrame:
    """
    Oxford-Man Institute of Quantitative Finance Realized Library 的数据
    :param symbol: str FTSE: FTSE 100, GDAXI: DAX, RUT: Russel 2000, SPX: S&P 500 Index, STOXX50E: EURO STOXX 50, SSEC: Shanghai Composite Index, N225: Nikkei 225
    :return: pandas.DataFrame

    The Oxford-Man Institute's "realised library" contains daily non-parametric measures of how volatility financial assets or indexes were in the past. Each day's volatility measure depends solely on financial data from that day. They are driven by the use of the latest innovations in econometric modelling and theory to design them, while we draw our high frequency data from the Thomson Reuters DataScope Tick History database. Realised measures are not volatility forecasts. However, some researchers use these measures as an input into forecasting models. The aim of this line of research is to make financial markets more transparent by exposing how volatility changes through time.

    This Library is used as the basis of some of our own research, which effects its scope, and is made available here to encourage the more widespread exploitation of these methods. It is given 'as is' and solely for informational purposes, please read the disclaimer.

    The volatility data can be visually explored. We make the complete up-to-date dataset available for download. Lists of assets covered and realized measures available are also available.
    """
    url = "https://realized.oxford-man.ox.ac.uk/theme/js/front-page-chart.js"
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "realized.oxford-man.ox.ac.uk",
        "Pragma": "no-cache",
        "Referer": "https://realized.oxford-man.ox.ac.uk/?from=groupmessage&isappinstalled=0",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36",
    }

    res = requests.get(url, headers=headers, verify=False)
    soup = BeautifulSoup(res.text, "lxml")
    soup_text = soup.find("p").get_text()
    data_json = json.loads(soup_text[soup_text.find("{") : soup_text.rfind("}") + 1])
    temp_df = pd.DataFrame(data_json[f".{symbol}"]["data"])
    temp_df.index = pd.to_datetime(temp_df.iloc[:, 0], unit="ms")
    temp_df = temp_df.iloc[:, 1]
    temp_df.index.name = "date"
    temp_df.name = f"{symbol}"
    return temp_df


def article_rlab_rv(symbol: str = "39693") -> pd.DataFrame:
    """
    修大成主页-Risk Lab-Realized Volatility
    :param symbol: str 股票代码
    :return: pandas.DataFrame
    1996-01-02    0.000000
    1996-01-04    0.000000
    1996-01-05    0.000000
    1996-01-09    0.000000
    1996-01-10    0.000000
                    ...
    2019-11-04    0.175107
    2019-11-05    0.185112
    2019-11-06    0.210373
    2019-11-07    0.240808
    2019-11-08    0.199549
    Name: RV, Length: 5810, dtype: float64

    Website
    https://dachxiu.chicagobooth.edu/

    Objective
    We provide up-to-date daily annualized realized volatilities for individual stocks, ETFs, and future contracts, which are estimated from high-frequency data. We are in the process of incorporating equities from global markets.

    Data
    We collect trades at their highest frequencies available (up to every millisecond for US equities after 2007), and clean them using the prevalent national best bid and offer (NBBO) that are available up to every second. The mid-quotes are calculated based on the NBBOs, so their highest sampling frequencies are also up to every second.

    Methodology
    We provide quasi-maximum likelihood estimates of volatility (QMLE) based on moving-average models MA(q), using non-zero returns of transaction prices (or mid-quotes if available) sampled up to their highest frequency available, for days with at least 12 observations. We select the best model (q) using Akaike Information Criterion (AIC). For comparison, we report realized volatility (RV) estimates using 5-minute and 15-minute subsampled returns.

    References
    1. “When Moving-Average Models Meet High-Frequency Data: Uniform Inference on Volatility”, by Rui Da and Dacheng Xiu. 2017.
    2. “Quasi-Maximum Likelihood Estimation of Volatility with High Frequency Data”, by Dacheng Xiu. Journal of Econometrics, 159 (2010), 235-250.
    3. “How Often to Sample A Continuous-time Process in the Presence of Market Microstructure Noise”, by Yacine Aït-Sahalia, Per Mykland, and Lan Zhang. Review of Financial Studies, 18 (2005), 351–416.
    4. “The Distribution of Exchange Rate Volatility”, by Torben Andersen, Tim Bollerslev, Francis X. Diebold, and Paul Labys. Journal of the American Statistical Association, 96 (2001), 42-55.
    5. “Econometric Analysis of Realized Volatility and Its Use in Estimating Stochastic Volatility Models”, by Ole E Barndorff‐Nielsen and Neil Shephard. Journal of the Royal Statistical Society: Series B, 64 (2002), 253-280.
    """
    print("由于服务器在国外, 请稍后, 如果访问失败, 请使用代理工具")
    url = "https://dachxiu.chicagobooth.edu/data.php"
    payload = {"ticker": symbol}
    res = requests.get(url, params=payload, verify=False)
    soup = BeautifulSoup(res.text, "lxml")
    title_fore = (
        pd.DataFrame(soup.find("p").get_text().split(symbol)).iloc[0, 0].strip()
    )
    title_list = (
        pd.DataFrame(soup.find("p").get_text().split(symbol))
        .iloc[1, 0]
        .strip()
        .split("\n")
    )
    title_list.insert(0, title_fore)
    temp_df = pd.DataFrame(soup.find("p").get_text().split(symbol)).iloc[2:, :]
    temp_df = temp_df.iloc[:, 0].str.split(" ", expand=True)
    temp_df = temp_df.iloc[:, 1:]
    temp_df.iloc[:, -1] = temp_df.iloc[:, -1].str.replace(r"\n", "")
    temp_df.reset_index(inplace=True)
    temp_df.index = pd.to_datetime(temp_df.iloc[:, 1], format="%Y%m%d", errors="coerce")
    temp_df = temp_df.iloc[:, 1:]
    data_se = temp_df.iloc[:, 1]
    data_se.name = "RV"
    temp_df = data_se.astype("float", errors="ignore")
    temp_df.index.name = "date"
    return temp_df


if __name__ == "__main__":
    article_rlab_rv_df = article_rlab_rv(symbol="39693")
    print(article_rlab_rv_df)

    article_oman_rv_short_df = article_oman_rv_short(symbol="FTSE")
    print(article_oman_rv_short_df)

    article_oman_rv_df = article_oman_rv(symbol="FTSE", index="rk_th2")
    print(article_oman_rv_df)
