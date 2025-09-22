# -*- coding:utf-8 -*- 
import codecs
import os

__version__ = '1.4.21'
__author__ = 'Jimmy Liu'

"""
for trading data
"""
from tushare.stock.trading import (get_hist_data, get_tick_data,
                                   get_today_all, get_realtime_quotes,
                                   get_h_data, get_today_ticks,
                                   get_index, get_hists,
                                   get_k_data, get_day_all,
                                   get_sina_dd, bar, tick,
                                   get_markets, quotes,
                                   get_instrument, reset_instrument)

"""
for trading data
"""
from tushare.stock.fundamental import (get_stock_basics, get_report_data,
                                       get_profit_data,
                                       get_operation_data, get_growth_data,
                                       get_debtpaying_data, get_cashflow_data,
                                       get_balance_sheet, get_profit_statement, get_cash_flow)

"""
for macro data
"""
from tushare.stock.macro import (get_gdp_year, get_gdp_quarter,
                                 get_gdp_for, get_gdp_pull,
                                 get_gdp_contrib, get_cpi,
                                 get_ppi, get_deposit_rate,
                                 get_loan_rate, get_rrr,
                                 get_money_supply, get_money_supply_bal,
                                 get_gold_and_foreign_reserves)

"""
for classifying data
"""
from tushare.stock.classifying import (get_industry_classified, get_concept_classified,
                                       get_area_classified, get_gem_classified,
                                       get_sme_classified, get_st_classified,
                                       get_hs300s, get_sz50s, get_zz500s,
                                       get_terminated, get_suspended)

"""
for macro data
"""
from tushare.stock.newsevent import (get_latest_news, latest_content,
                                     get_notices, notice_content,
                                     guba_sina)

"""
for reference
moneyflow_hsgt:沪深港通资金流向
"""
from tushare.stock.reference import (profit_data, forecast_data,
                                     xsg_data, fund_holdings,
                                     new_stocks, new_cbonds, sh_margins,
                                     sh_margin_details,
                                     sz_margins, sz_margin_details,
                                     top10_holders, profit_divis,
                                     moneyflow_hsgt, margin_detail,
                                     margin_target, margin_offset,
                                     margin_zsl, stock_issuance,
                                     stock_pledged, pledged_detail)

"""
for shibor
"""
from tushare.stock.shibor import (shibor_data, shibor_quote_data,
                                  shibor_ma_data, lpr_data,
                                  lpr_ma_data)

"""
for tushare pro api
"""
from tushare.pro.data_pro import (pro_api, pro_bar, subs, ht_subs, pro_bar_vip)

"""
for LHB
"""
from tushare.stock.billboard import (top_list, cap_tops, broker_tops,
                                     inst_tops, inst_detail)

"""
for utils
"""
from tushare.util.dateu import (trade_cal, is_holiday)

from tushare.internet.boxoffice import (realtime_boxoffice, day_boxoffice,
                                        day_cinema, month_boxoffice)

from tushare.internet.indexes import (bdi)

"""
for fund data
"""
from tushare.fund.nav import (get_nav_open, get_nav_close, get_nav_grading,
                              get_nav_history, get_fund_info)

"""
for trader API
"""
from tushare.trader.trader import TraderAPI

"""
for futures API
"""
from tushare.futures.intlfutures import (get_intlfuture)

from tushare.stock.globals import (global_realtime)

from tushare.util.mailmerge import (MailMerge)

"""
for futures API
"""
from tushare.futures.domestic import (get_cffex_daily, get_czce_daily,
                                      get_dce_daily, get_future_daily,
                                      get_shfe_daily, get_shfe_vwap)

from tushare.coins.market import (coins_tick, coins_bar,
                                  coins_snapshot, coins_trade)

from tushare.util.conns import (get_apis, close_apis)

from tushare.util.upass import (get_token, set_token)

"""
for quotes API
"""
# from tushare.stock.rtqc import (realtime_quote, realtime_list)
from tushare.stock.rtq import (realtime_quote, realtime_list)
from tushare.stock.histroy_divide import (realtime_tick)
