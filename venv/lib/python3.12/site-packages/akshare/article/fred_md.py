#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2020/4/10 19:58
Desc: Economic Research from Federal Reserve Bank of St. Louis
https://research.stlouisfed.org/econ/mccracken/fred-databases/
FRED-MD and FRED-QD are large macroeconomic databases designed for the empirical analysis of “big data.” The datasets of monthly and quarterly observations mimic the coverage of datasets already used in the literature, but they add three appealing features. They are updated in real-time through the FRED database. They are publicly accessible, facilitating the replication of empirical work. And they relieve the researcher of the task of incorporating data changes and revisions (a task accomplished by the data desk at the Federal Reserve Bank of St. Louis).
"""

import pandas as pd


def fred_md(date: str = "2020-01") -> pd.DataFrame:
    """
    The accompanying paper shows that factors extracted from the FRED-MD dataset share the same predictive content as those based on the various vintages of the so-called Stock-Watson data. In addition, it suggests that diffusion indexes constructed as the partial sum of the factor estimates can potentially be useful for the study of business cycle chronology.
    :param date: e.g., "2020-03"; from "2015-01" to now
    :type date: str
    :return: Monthly Data
    :rtype: pandas.DataFrame
    """
    url = (
        f"https://s3.amazonaws.com/files.fred.stlouisfed.org/fred-md/monthly/{date}.csv"
    )
    temp_df = pd.read_csv(url)
    return temp_df


def fred_qd(date: str = "2020-01") -> pd.DataFrame:
    """
    FRED-QD is a quarterly frequency companion to FRED-MD. It is designed to emulate the dataset used in "Disentangling the Channels of the 2007-2009 Recession" by Stock and Watson (2012, NBER WP No. 18094) but also contains several additional series. Comments or suggestions are welcome.
    :param date: e.g., "2020-03"; from "2015-01" to now
    :type date: str
    :return: Quarterly Data
    :rtype: pandas.DataFrame
    """
    url = f"https://s3.amazonaws.com/files.fred.stlouisfed.org/fred-md/quarterly/{date}.csv"
    temp_df = pd.read_csv(url)
    return temp_df


if __name__ == "__main__":
    fred_md_df = fred_md(date="2023-03")
    print(fred_md_df)

    fred_qd_df = fred_qd(date="2023-03")
    print(fred_qd_df)
