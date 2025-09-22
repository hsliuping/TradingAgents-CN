#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/4/10 18:00
Desc: 接口测试文件
"""

from akshare.pro.data_pro import pro_api

pro = pro_api()

# 商品-持仓数据-多头龙虎榜
variety_positions_longs_df = pro.variety_positions(
    fields="longs", code="rb1810", date="2018-08-08"
)
print(variety_positions_longs_df)

# 商品-持仓数据-空头龙虎榜
variety_positions_shorts_df = pro.variety_positions(
    fields="shorts", code="rb1810", date="2018-08-08"
)
print(variety_positions_shorts_df)

# 商品-合约行情数据
variety_quotes_df = pro.variety_quotes(code="rb1810", date="2018-08-08")
print(variety_quotes_df)

# 商品-商品沉淀资金数据接口
variety_money_df = pro.variety_money(symbol="RB", date="2018-08-08")
print(variety_money_df)

# 商品-合约多空比数据
variety_bbr_df = pro.variety_bbr(code="rb1810", date="2018-08-08")
print(variety_bbr_df)

# 商品-合约净持仓保证金变化数据
variety_net_money_chge_df = pro.variety_net_money_chge(code="rb1810", date="2018-08-08")
print(variety_net_money_chge_df)

# 商品-合约净持仓保证金数据
variety_net_money_df = pro.variety_net_money(code="rb1810", date="2018-08-08")
print(variety_net_money_df)

# 商品-合约总持仓保证金数据
variety_total_money_df = pro.variety_total_money(code="rb1810", date="2018-08-08")
print(variety_total_money_df)

# 商品-商品的席位盈亏数据
variety_profit_df = pro.variety_profit(
    symbol="RB", start_date="2018-02-08", end_date="2018-08-08"
)
print(variety_profit_df)

# 商品-自研指标数据
variety_strategies_df = pro.variety_strategies(code="rb1810", date="2018-08-08")
print(variety_strategies_df)

# 商品-龙虎比排行数据-多头排行
variety_longhu_long_top_df = pro.variety_longhu_top(fields="long", date="2018-08-08")
print(variety_longhu_long_top_df)

# 商品-龙虎比排行数据-空头排行
variety_longhu_short_top_df = pro.variety_longhu_top(fields="short", date="2018-08-08")
print(variety_longhu_short_top_df)

# 商品-牛熊线排行数据-多头排行
variety_niuxiong_long_top_df = pro.variety_niuxiong_top(
    fields="long", date="2018-08-08"
)
print(variety_niuxiong_long_top_df)

# 商品-牛熊线排行数据-空头排行
variety_niuxiong_short_top_df = pro.variety_niuxiong_top(
    fields="short", date="2018-08-08"
)
print(variety_niuxiong_short_top_df)

# 商品-商品相关研报数据
variety_reports_df = pro.variety_reports(csymbolode="RB", date="2018-08-08")
print(variety_reports_df)

# 商品-商品列表数据
variety_all_df = pro.variety_all()
print(variety_all_df)


# 席位-商品净持仓数据
variety_net_positions_df = pro.variety_net_positions(
    symbol="RB", broker="永安期货", date="2018-08-08"
)
print(variety_net_positions_df)

# 席位-席位持仓数据
broker_positions_df = pro.broker_positions(broker="永安期货", date="2018-08-08")
print(broker_positions_df)

# 席位-席位盈亏数据
broker_calendar_df = pro.broker_calendar(
    broker="永安期货", start_date="2018-07-08", end_date="2018-08-08"
)
print(broker_calendar_df)

# 席位-席位每日大资金流动数据
broker_flow_df = pro.broker_flow(broker="永安期货", date="2018-08-08", offset="1000000")
print(broker_flow_df)

# 席位-席位多空比数据
broker_bbr_df = pro.broker_bbr(broker="永安期货", date="2018-08-08")
print(broker_bbr_df)

# 席位-席位净持仓保证金变化数据
broker_net_money_chge_df = pro.broker_net_money_chge(
    broker="永安期货", date="2018-08-08"
)
print(broker_net_money_chge_df)

# 席位-席位净持仓保证金数据
broker_net_money_df = pro.broker_net_money(broker="永安期货", date="2018-08-08")
print(broker_net_money_df)

# 席位-席位总持仓保证金数据
broker_total_money_df = pro.broker_total_money(broker="永安期货", date="2018-08-08")
print(broker_total_money_df)

# 席位-席位的商品盈亏数据
broker_profit_df = pro.broker_profit(
    broker="永安期货", start_date="2018-07-08", end_date="2018-08-08"
)
print(broker_profit_df)

# 席位-席位盈利排行
broker_in_profit_list_df = pro.broker_in_profit_list(
    start_date="2018-07-08", end_date="2018-08-08", count="10"
)
print(broker_in_profit_list_df)

# 席位-席位亏损排行
broker_in_loss_list_df = pro.broker_in_loss_list(
    start_date="2018-07-08", end_date="2018-08-08", count="10"
)
print(broker_in_loss_list_df)

# 席位-所有席位数据
broker_all_df = pro.broker_all(offset_days="365")
print(broker_all_df)

# 席位-建仓过程
broker_positions_process_df = pro.broker_positions_process(
    broker="永安期货", code="rb2010", start_date="2020-02-03", end_date="2020-06-03"
)
print(broker_positions_process_df)

# 席位-席位对对碰
broker_pk_df = pro.broker_pk(broker1="永安期货", broker2="兴证期货", symbol="RB")
print(broker_pk_df)


# 指数-指数信息
index_info_df = pro.index_info(index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959")
print(index_info_df)

# 指数-指数权重数据
index_weights_df = pro.index_weights(
    index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959", date="2018-08-08"
)
print(index_weights_df)

# 指数-指数行情数据
index_quotes_df = pro.index_quotes(
    index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959", date="2018-08-08"
)
print(index_quotes_df)

# 指数-指数沉淀资金数据
index_money_df = pro.index_money(
    index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959", date="2018-08-08"
)
print(index_money_df)

# 指数-公共指数列表
index_official_df = pro.index_official()
print(index_official_df)

# 指数-个人指数列表
index_mine_df = pro.index_mine()
print(index_mine_df)

# 指数-指数资金动向
index_trend_df = pro.index_trend(
    index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959", date="2018-08-08"
)
print(index_trend_df)

# 指数-指数的席位盈亏数据
index_profit_df = pro.index_profit(
    index_id="index0070c0eb-93ba-2da9-6633-fa70cb90e959",
    start_date="2018-07-08",
    end_date="2018-08-08",
)
print(index_profit_df)

# 基本面-基差
basis_df = pro.basis(variety="RB", date="2018-08-08")
print(basis_df)

# 基本面-期限结构
term_structure_df = pro.term_structure(variety="RB", date="2018-08-08")
print(term_structure_df)

# 基本面-库存数据
inventory_df = pro.inventory(variety="RB", date="2018-08-08")
print(inventory_df)

# 基本面-利润数据
profit_df = pro.profit(variety="RB", date="2019-12-12")
print(profit_df)

# 基本面-现货贸易商报价
trader_prices_df = pro.trader_prices(variety="RB", date="2020-03-30")
print(trader_prices_df)

# 基本面-跨期套利数据
intertemporal_arbitrage_df = pro.intertemporal_arbitrage(
    variety="RB", code1="01", code2="05", date="2018-08-08"
)
print(intertemporal_arbitrage_df)

# 基本面-自由价差数据
free_spread_df = pro.free_spread(
    variety1="RB", code1="01", variety2="HC", code2="01", date="2018-08-08"
)
print(free_spread_df)

# 基本面-自由价比数据
free_ratio_df = pro.free_ratio(
    variety1="RB", code1="01", variety2="HC", code2="01", date="2018-08-08"
)
print(free_ratio_df)

# 基本面-仓单数据
warehouse_receipt_df = pro.warehouse_receipt(variety="RB", date="2018-08-08")
print(warehouse_receipt_df)

# 基本面-仓单汇总数据
warehouse_receipt_sum_df = pro.warehouse_receipt(date="2018-08-08")
print(warehouse_receipt_sum_df)

# 基本面-虚实盘比数据
virtual_real_df = pro.virtual_real(variety="RB", code="10", date="2018-08-08")
print(virtual_real_df)


# 工具-龙虎牛熊多头合约池
long_pool_df = pro.long_pool(date="2018-08-08")
print(long_pool_df)

# 工具-龙虎牛熊空头合约池
short_pool_df = pro.short_pool(date="2018-08-08")
print(short_pool_df)


# 资金-每日净流多列表(商品)
commodity_flow_long_df = pro.commodity_flow_long(date="2018-08-08")
print(commodity_flow_long_df)

# 资金-每日净流空列表(商品)
commodity_flow_short_df = pro.commodity_flow_short(date="2018-08-08")
print(commodity_flow_short_df)

# 资金-每日净流多列表(指数)
stock_flow_long_df = pro.stock_flow_long(date="2018-08-08")
print(stock_flow_long_df)

# 资金-每日净流空列表(指数)
stock_flow_short_df = pro.stock_flow_short(date="2018-08-08")
print(stock_flow_short_df)

# 资金-每日商品保证金沉淀变化
money_in_out_df = pro.money_in_out(date="2018-08-08")
print(money_in_out_df)
