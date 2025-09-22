#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/9 18:30
Desc: 东方财富网-概念板-行情中心-日K-筹码分布
https://quote.eastmoney.com/concept/sz000001.html
"""

import json
from datetime import datetime

import pandas as pd
import requests
import py_mini_racer


def stock_cyq_em(symbol: str = "000001", adjust: str = "") -> pd.DataFrame:
    """
    东方财富网-概念板-行情中心-日K-筹码分布
    https://quote.eastmoney.com/concept/sz000001.html
    :param symbol: 股票代码
    :type symbol: str
    :param adjust: choice of {"qfq": "前复权", "hfq": "后复权", "": "不复权"}
    :type adjust: str
    :return: 筹码分布
    :rtype: pandas.DataFrame
    """
    html_str = """
    // @ts-nocheck

    /**
     * 计算分布及相关指标
     * @param {number} index 当前选中的K线的索引
     * @return {{x: Array.<number>, y: Array.<number>}}
     */
    /**
    this.range = 120;
    */
    function CYQCalculator(index, klinedata) {
        var maxprice = 0;
        var minprice = 0;
        var factor = 150;
        var start = this.range ? Math.max(0, index - this.range + 1) : 0;
        /**
         * K图数据[time,open,close,high,low,volume,amount,amplitude,turnoverRate]
         */
        var kdata = klinedata.slice(start, Math.max(1, index + 1));
        if (kdata.length === 0) throw 'invaild index';
        for (var i = 0; i < kdata.length; i++) {
            var elements = kdata[i];
            maxprice = !maxprice ? elements.high : Math.max(maxprice, elements.high);
            minprice = !minprice ? elements.low : Math.min(minprice, elements.low);
        }

        // 精度不小于0.01 产品逻辑
        var accuracy = Math.max(0.01, (maxprice - minprice) / (factor - 1));
        /**
         * 值域
         * @type {Array.<number>}
         */
        var yrange = [];
        for (var i = 0; i < factor; i++) {
            yrange.push((minprice + accuracy * i).toFixed(2) / 1);
        }
        /**
         * 横轴数据
         */
        var xdata = createNumberArray(factor);

        for (var i = 0; i < kdata.length; i++) {
            var eles = kdata[i];

            var open = eles.open,
                close = eles.close,
                high = eles.high,
                low = eles.low,
                avg = (open + close + high + low) / 4,
                turnoverRate = Math.min(1, eles.hsl / 100 || 0);

            var H = Math.floor((high - minprice) / accuracy),
                L = Math.ceil((low - minprice) / accuracy),
                // G点坐标, 一字板时, X为进度因子
                GPoint = [high == low ? factor - 1 : 2 / (high - low), Math.floor((avg - minprice) / accuracy)];
            // 衰减
            for (var n = 0; n < xdata.length; n++) {
                xdata[n] *= (1 - turnoverRate);
            }

            if (high == low) {
                // 一字板时，画矩形面积是三角形的2倍
                xdata[GPoint[1]] += GPoint[0] * turnoverRate / 2;
            } else {
                for (var j = L; j <= H; j++) {
                    var curprice = minprice + accuracy * j;
                    if (curprice <= avg) {
                        // 上半三角叠加分布分布
                        if (Math.abs(avg - low) < 1e-8) {
                            xdata[j] += GPoint[0] * turnoverRate;
                        } else {
                            xdata[j] += (curprice - low) / (avg - low) * GPoint[0] * turnoverRate;
                        }
                    } else {
                        // 下半三角叠加分布分布
                        if (Math.abs(high - avg) < 1e-8) {
                            xdata[j] += GPoint[0] * turnoverRate;
                        } else {
                            xdata[j] += (high - curprice) / (high - avg) * GPoint[0] * turnoverRate;
                        }
                    }
                }
            }

        }


        var currentprice = klinedata[index].close;
        var totalChips = 0;
        for (var i = 0; i < factor; i++) {
            var x = xdata[i].toPrecision(12) / 1;
            //if (x < 0) xdata[i] = 0;
            totalChips += x;
        }
        var result = new CYQData();
        result.x = xdata;
        result.y = yrange;
        result.benefitPart = result.getBenefitPart(currentprice);
        result.avgCost = getCostByChip(totalChips * 0.5).toFixed(2);
        result.percentChips = {
            '90': result.computePercentChips(0.9),
            '70': result.computePercentChips(0.7)
        };
        return result;

        /**
         * 获取指定筹码处的成本
         * @param {number} chip 堆叠筹码
         */
        function getCostByChip(chip) {
            var result = 0,
                sum = 0;
            for (var i = 0; i < factor; i++) {
                var x = xdata[i].toPrecision(12) / 1;
                if (sum + x > chip) {
                    result = minprice + i * accuracy;
                    break;
                }
                sum += x;
            }
            return result;
        }

        /**
         * 筹码分布数据
         */
        function CYQData() {
            /**
             * 筹码堆叠
             * @type {Array.<number>}
             */
            this.x = arguments[0];
            /**
             * 价格分布
             * @type {Array.<number>}
             */
            this.y = arguments[1];
            /**
             * 获利比例
             * @type {number}
             */
            this.benefitPart = arguments[2];
            /**
             * 平均成本
             * @type {number}
             */
            this.avgCost = arguments[3];
            /**
             * 百分比筹码
             * @type {{Object.<string, {{priceRange: number[], concentration: number}}>}}
             */
            this.percentChips = arguments[4];
            /**
             * 计算指定百分比的筹码
             * @param {number} percent 百分比大于0，小于1
             */
            this.computePercentChips = function (percent) {
                if (percent > 1 || percent < 0) throw 'argument "percent" out of range';
                var ps = [(1 - percent) / 2, (1 + percent) / 2];
                var pr = [getCostByChip(totalChips * ps[0]), getCostByChip(totalChips * ps[1])];
                return {
                    priceRange: [pr[0].toFixed(2), pr[1].toFixed(2)],
                    concentration: pr[0] + pr[1] === 0 ? 0 : (pr[1] - pr[0]) / (pr[0] + pr[1])
                };
            };
            /**
             * 获取指定价格的获利比例
             * @param {number} price 价格
             */
            this.getBenefitPart = function (price) {
                var below = 0;
                for (var i = 0; i < factor; i++) {
                    var x = xdata[i].toPrecision(12) / 1;
                    if (price >= minprice + i * accuracy) {
                        below += x;
                    }
                }
                return totalChips == 0 ? 0 : below / totalChips;
            };
        }
    }


    function createNumberArray(count) {
        var array = [];
        for (var i = 0; i < count; i++) {
            array.push(0);
        }
        return array;
    }
    """
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(html_str)
    adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
    market_code = 1 if symbol.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": f"{market_code}.{symbol}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": adjust_dict[adjust],
        "end": datetime.now().date().strftime("%Y%m%d"),
        "lmt": "210",
    }
    r = requests.get(url, params=params)
    data_json = r.json()
    temp_df = pd.DataFrame([item.split(",") for item in data_json["data"]["klines"]])
    temp_df.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "volume_money",
        "zf",
        "zdf",
        "zde",
        "hsl",
    ]
    for item in temp_df.columns[1:]:
        temp_df[item] = pd.to_numeric(temp_df[item])
    temp_df["index"] = range(0, len(temp_df))
    records = temp_df.to_dict(orient="records")
    date_list = []
    benefit_part = []
    avg_cost = []
    pct_70_low = []
    pct_70_high = []
    pct_90_low = []
    pct_90_high = []
    pct_70_con = []
    pct_90_con = []
    for i in range(0, len(records)):
        mcode = js_code.call("CYQCalculator", i, records)
        date_list.append(records[i]["date"])
        benefit_part.append(mcode["benefitPart"])
        avg_cost.append(mcode["avgCost"])
        pct_70_low.append(mcode["percentChips"]["70"]["priceRange"][0])
        pct_70_high.append(mcode["percentChips"]["70"]["priceRange"][1])
        pct_90_low.append(mcode["percentChips"]["90"]["priceRange"][0])
        pct_90_high.append(mcode["percentChips"]["90"]["priceRange"][1])
        pct_70_con.append(mcode["percentChips"]["70"]["concentration"])
        pct_90_con.append(mcode["percentChips"]["90"]["concentration"])
    temp_df = pd.DataFrame(
        [
            date_list,
            benefit_part,
            avg_cost,
            pct_90_low,
            pct_90_high,
            pct_90_con,
            pct_70_low,
            pct_70_high,
            pct_70_con,
        ]
    ).T
    temp_df.columns = [
        "日期",
        "获利比例",
        "平均成本",
        "90成本-低",
        "90成本-高",
        "90集中度",
        "70成本-低",
        "70成本-高",
        "70集中度",
    ]
    temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
    temp_df["获利比例"] = pd.to_numeric(temp_df["获利比例"], errors="coerce")
    temp_df["平均成本"] = pd.to_numeric(temp_df["平均成本"], errors="coerce")
    temp_df["90成本-低"] = pd.to_numeric(temp_df["90成本-低"], errors="coerce")
    temp_df["90成本-高"] = pd.to_numeric(temp_df["90成本-高"], errors="coerce")
    temp_df["90集中度"] = pd.to_numeric(temp_df["90集中度"], errors="coerce")
    temp_df["70成本-低"] = pd.to_numeric(temp_df["70成本-低"], errors="coerce")
    temp_df["70成本-高"] = pd.to_numeric(temp_df["70成本-高"], errors="coerce")
    temp_df["70集中度"] = pd.to_numeric(temp_df["70集中度"], errors="coerce")
    temp_df = temp_df.iloc[-90:, :].copy()
    temp_df.reset_index(inplace=True, drop=True)
    return temp_df


if __name__ == "__main__":
    stock_cyq_em_df = stock_cyq_em(symbol="000001", adjust="")
    print(stock_cyq_em_df)
