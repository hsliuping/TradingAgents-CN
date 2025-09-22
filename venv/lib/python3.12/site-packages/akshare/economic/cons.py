#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2019/10/21 21:11
Desc: 宏观经济配置文件
"""

# urls-china
JS_CHINA_CPI_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_cpi_yoy_all.js?v={}&_={}"
)
JS_CHINA_CPI_MONTHLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_cpi_mom_all.js?v={}&_={}"
)
JS_CHINA_M2_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_m2_money_supply_yoy_all.js?v={}&_={}"
)
JS_CHINA_PPI_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_ppi_yoy_all.js?v={}&_={}"
)
JS_CHINA_PMI_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_manufacturing_pmi_all.js?v={}&_={}"
)
JS_CHINA_GDP_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_gdp_yoy_all.js?v={}&_={}"
)
JS_CHINA_CX_PMI_YEARLY_URL = "https://cdn.jin10.com/dc/reports/dc_chinese_caixin_manufacturing_pmi_all.js?v={}&_={}"
JS_CHINA_CX_SERVICE_PMI_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_caixin_services_pmi_all.js?v={}&_={}"
)
JS_CHINA_FX_RESERVES_YEARLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_fx_reserves_all.js?v={}&_={}"
)
JS_CHINA_ENERGY_DAILY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_qihuo_energy_report_all.js?v={}&_={}"
)
JS_CHINA_NON_MAN_PMI_MONTHLY_URL = (
    "https://cdn.jin10.com/dc/reports/dc_chinese_non_manufacturing_pmi_all.js?v={}&_={}"
)
JS_CHINA_RMB_DAILY_URL = "https://cdn.jin10.com/dc/reports/dc_rmb_data_all.js?v={}&_={}"
JS_CHINA_MARKET_MARGIN_SZ_URL = (
    "https://cdn.jin10.com/dc/reports/dc_market_margin_sz_all.js?v={}&_={}"
)
JS_CHINA_MARKET_MARGIN_SH_URL = (
    "https://cdn.jin10.com/dc/reports/dc_market_margin_sse_all.js?v={}&_={}"
)
JS_CHINA_REPORT_URL = "https://cdn.jin10.com/dc/reports/dc_sge_report_all.js?v={}&_={}"

# urls-usa
JS_USA_INTEREST_RATE_URL = (
    "https://cdn.jin10.com/dc/reports/dc_usa_interest_rate_decision_all.js?v={}&_={}"
)
JS_USA_NON_FARM_URL = (
    "https://cdn.jin10.com/dc/reports/dc_nonfarm_payrolls_all.js?v={}&_={}"
)
JS_USA_UNEMPLOYMENT_RATE_URL = (
    "https://cdn.jin10.com/dc/reports/dc_usa_unemployment_rate_all.js??v={}&_={}"
)
JS_USA_EIA_CRUDE_URL = (
    "https://cdn.jin10.com/dc/reports/dc_eia_crude_oil_all.js?v={}&_={}"
)
JS_USA_INITIAL_JOBLESS_URL = (
    "https://cdn.jin10.com/dc/reports/dc_initial_jobless_all.js?v={}&_={}"
)
JS_USA_CORE_PCE_PRICE_URL = (
    "https://cdn.jin10.com/dc/reports/dc_usa_core_pce_price_all.js?v={}&_={}"
)
JS_USA_CPI_MONTHLY_URL = "https://cdn.jin10.com/dc/reports/dc_usa_cpi_all.js?v={}&_={}"
JS_USA_LMCI_URL = "https://cdn.jin10.com/dc/reports/dc_usa_lmci_all.js?v={}&_={}"
JS_USA_ADP_NONFARM_URL = (
    "https://cdn.jin10.com/dc/reports/dc_adp_nonfarm_employment_all.js?v={}&_={}"
)
JS_USA_GDP_MONTHLY_URL = "https://cdn.jin10.com/dc/reports/dc_usa_gdp_all.js?v={}&_={}"
JS_USA_EIA_CRUDE_PRODUCE_URL = (
    "https://cdn.jin10.com/dc/reports/dc_eia_crude_oil_produce_all.js?v={}&_={}"
)

# urls-euro
JS_EURO_RATE_DECISION_URL = (
    "https://cdn.jin10.com/dc/reports/dc_interest_rate_decision_all.js?v={}&_={}"
)

# urls-constitute
JS_CONS_GOLD_ETF_URL = "https://cdn.jin10.com/dc/reports/dc_etf_gold_all.js?v={}&_={}"
JS_CONS_SLIVER_ETF_URL = (
    "https://cdn.jin10.com/dc/reports/dc_etf_sliver_all.js?v={}&_={}"
)
JS_CONS_OPEC_URL = "https://cdn.jin10.com/dc/reports/dc_opec_report_all.js??v={}&_={}"

usa_name_url_map = {
    "美联储决议报告": "//datacenter.jin10.com/reportType/dc_usa_interest_rate_decision",
    "美国非农就业人数报告": "//datacenter.jin10.com/reportType/dc_nonfarm_payrolls",
    "美国失业率报告": "//datacenter.jin10.com/reportType/dc_usa_unemployment_rate",
    "美国CPI月率报告": "//datacenter.jin10.com/reportType/dc_usa_cpi",
    "美国初请失业金人数报告": "//datacenter.jin10.com/reportType/dc_initial_jobless",
    "美国核心PCE物价指数年率报告": "//datacenter.jin10.com/reportType/dc_usa_core_pce_price",
    "美国EIA原油库存报告": "//datacenter.jin10.com/reportType/dc_eia_crude_oil",
    "美联储劳动力市场状况指数报告": "//datacenter.jin10.com/reportType/dc_usa_lmci",
    "美国ADP就业人数报告": "//datacenter.jin10.com/reportType/dc_adp_nonfarm_employment",
    "美国国内生产总值(GDP)报告": "//datacenter.jin10.com/reportType/dc_usa_gdp",
    "美国原油产量报告": "//datacenter.jin10.com/reportType/dc_eia_crude_oil_produce",
    "美国零售销售月率报告": "//datacenter.jin10.com/reportType/dc_usa_retail_sales",
    "美国商品期货交易委员会CFTC外汇类非商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_nc_report",
    "美国NFIB小型企业信心指数报告": "//datacenter.jin10.com/reportType/dc_usa_nfib_small_business",
    "贝克休斯钻井报告": "//datacenter.jin10.com/reportType/dc_rig_count_summary",
    "美国谘商会消费者信心指数报告": "//datacenter.jin10.com/reportType/dc_usa_cb_consumer_confidence",
    "美国FHFA房价指数月率报告": "//datacenter.jin10.com/reportType/dc_usa_house_price_index",
    "美国个人支出月率报告": "//datacenter.jin10.com/reportType/dc_usa_personal_spending",
    "美国生产者物价指数(PPI)报告": "//datacenter.jin10.com/reportType/dc_usa_ppi",
    "美国成屋销售总数年化报告": "//datacenter.jin10.com/reportType/dc_usa_exist_home_sales",
    "美国成屋签约销售指数月率报告": "//datacenter.jin10.com/reportType/dc_usa_pending_home_sales",
    "美国S&P/CS20座大城市房价指数年率报告": "//datacenter.jin10.com/reportType/dc_usa_spcs20",
    "美国进口物价指数报告": "//datacenter.jin10.com/reportType/dc_usa_import_price",
    "美国营建许可总数报告": "//datacenter.jin10.com/reportType/dc_usa_building_permits",
    "美国商品期货交易委员会CFTC商品类非商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_c_report",
    "美国挑战者企业裁员人数报告": "//datacenter.jin10.com/reportType/dc_usa_job_cuts",
    "美国实际个人消费支出季率初值报告": "//datacenter.jin10.com/reportType/dc_usa_real_consumer_spending",
    "美国贸易帐报告": "//datacenter.jin10.com/reportType/dc_usa_trade_balance",
    "美国经常帐报告": "//datacenter.jin10.com/reportType/dc_usa_current_account",
    "美国API原油库存报告": "//datacenter.jin10.com/reportType/dc_usa_api_crude_stock",
    "美国工业产出月率报告": "//datacenter.jin10.com/reportType/dc_usa_industrial_production",
    "美国耐用品订单月率报告": "//datacenter.jin10.com/reportType/dc_usa_durable_goods_orders",
    "美国工厂订单月率报告": "//datacenter.jin10.com/reportType/dc_usa_factory_orders",
    "Markit服务业PMI终值": "//datacenter.jin10.com/reportType/dc_usa_services_pmi",
    "商业库存月率": "//datacenter.jin10.com/reportType/dc_usa_business_inventories",
    "美国ISM非制造业PMI": "//datacenter.jin10.com/reportType/dc_usa_ism_non_pmi",
    "NAHB房产市场指数": "//datacenter.jin10.com/reportType/dc_usa_nahb_house_market_index",
    "新屋开工总数年化": "//datacenter.jin10.com/reportType/dc_usa_house_starts",
    "美国新屋销售总数年化": "//datacenter.jin10.com/reportType/dc_usa_new_home_sales",
    "美国Markit制造业PMI初值报告": "//datacenter.jin10.com/reportType/dc_usa_pmi",
    "美国ISM制造业PMI报告": "//datacenter.jin10.com/reportType/dc_usa_ism_pmi",
    "美国密歇根大学消费者信心指数初值报告": "//datacenter.jin10.com/reportType/dc_usa_michigan_consumer_sentiment",
    "美国出口价格指数报告": "//datacenter.jin10.com/reportType/dc_usa_export_price",
    "美国核心生产者物价指数(PPI)报告": "//datacenter.jin10.com/reportType/dc_usa_core_ppi",
    "美国核心CPI月率报告": "//datacenter.jin10.com/reportType/dc_usa_core_cpi",
    "美国EIA俄克拉荷马州库欣原油库存报告": "//datacenter.jin10.com/reportType/dc_eia_cushing_oil",
    "美国EIA精炼油库存报告": "//datacenter.jin10.com/reportType/dc_eia_distillates_stocks",
    "美国EIA天然气库存报告": "//datacenter.jin10.com/reportType/dc_eia_natural_gas",
    "美国EIA汽油库存报告": "//datacenter.jin10.com/reportType/dc_eia_gasoline",
}
china_name_url_map = {
    "郑州商品交易所期货每日行情": "//datacenter.jin10.com/reportType/dc_czce_futures_data",
    "中国CPI年率报告": "//datacenter.jin10.com/reportType/dc_chinese_cpi_yoy",
    "中国PPI年率报告": "//datacenter.jin10.com/reportType/dc_chinese_ppi_yoy",
    "中国以美元计算出口年率报告": "//datacenter.jin10.com/reportType/dc_chinese_exports_yoy",
    "中国以美元计算进口年率报告": "//datacenter.jin10.com/reportType/dc_chinese_imports_yoy",
    "中国以美元计算贸易帐报告": "//datacenter.jin10.com/reportType/dc_chinese_trade_balance",
    "中国规模以上工业增加值年率报告": "//datacenter.jin10.com/reportType/dc_chinese_industrial_production_yoy",
    "中国官方制造业PMI报告": "//datacenter.jin10.com/reportType/dc_chinese_manufacturing_pmi",
    "中国财新制造业PMI终值报告": "//datacenter.jin10.com/reportType/dc_chinese_caixin_manufacturing_pmi",
    "中国财新服务业PMI报告": "//datacenter.jin10.com/reportType/dc_chinese_caixin_services_pmi",
    "中国外汇储备报告": "//datacenter.jin10.com/reportType/dc_chinese_fx_reserves",
    "中国M2货币供应年率报告": "//datacenter.jin10.com/reportType/dc_chinese_m2_money_supply_yoy",
    "中国GDP年率报告": "//datacenter.jin10.com/reportType/dc_chinese_gdp_yoy",
    "人民币汇率中间价报告": "//datacenter.jin10.com/reportType/dc_rmb_data",
    "在岸人民币成交量报告": "//datacenter.jin10.com/reportType/dc_dollar_rmb_report",
    "上海期货交易所期货合约行情": "//datacenter.jin10.com/reportType/dc_shfe_futures_data",
    "中国CPI月率报告": "//datacenter.jin10.com/reportType/dc_chinese_cpi_mom",
    "大连商品交易所期货每日行情": "//datacenter.jin10.com/reportType/dc_dce_futures_data",
    "中国金融期货交易所期货每日行情": "//datacenter.jin10.com/reportType/dc_cffex_futures_data",
    "同业拆借报告": "//datacenter.jin10.com/reportType/dc_shibor",
    "香港同业拆借报告": "//datacenter.jin10.com/reportType/dc_hk_market_info",
    "深圳融资融券报告": "//datacenter.jin10.com/reportType/dc_market_margin_sz",
    "上海融资融券报告": "//datacenter.jin10.com/reportType/dc_market_margin_sse",
    "上海黄金交易所报告": "//datacenter.jin10.com/reportType/dc_sge_report",
    "上海期货交易所仓单日报": "//datacenter.jin10.com/reportType/dc_shfe_daily_stock",
    "大连商品交易所仓单日报": "//datacenter.jin10.com/reportType/dc_dce_daily_stock",
    "郑州商品交易所仓单日报": "//datacenter.jin10.com/reportType/dc_czce_daily_stock",
    "上海期货交易所指定交割仓库库存周报": "//datacenter.jin10.com/reportType/dc_shfe_weekly_stock",
    "CCI指数5500大卡动力煤价格报告": "//datacenter.jin10.com/reportType/dc_cci_report",
    "沿海六大电厂库存动态报告": "//datacenter.jin10.com/reportType/dc_qihuo_energy_report",
    "国内期货市场实施热度报告": "//datacenter.jin10.com/reportType/dc_futures_market_realtime",
    "中国官方非制造业PMI报告": "//datacenter.jin10.com/reportType/dc_chinese_non_manufacturing_pmi",
}
euro_name_url_map = {
    "欧元区未季调贸易帐报告": "//datacenter.jin10.com/reportType/dc_eurozone_trade_balance_mom",
    "欧元区季度GDP年率报告": "//datacenter.jin10.com/reportType/dc_eurozone_gdp_yoy",
    "欧元区CPI年率报告": "//datacenter.jin10.com/reportType/dc_eurozone_cpi_yoy",
    "欧元区PPI月率报告": "//datacenter.jin10.com/reportType/dc_eurozone_ppi_mom",
    "欧元区零售销售月率报告": "//datacenter.jin10.com/reportType/dc_eurozone_retail_sales_mom",
    "欧元区季调后就业人数季率报告": "//datacenter.jin10.com/reportType/dc_eurozone_employment_change_qoq",
    "欧元区失业率报告": "//datacenter.jin10.com/reportType/dc_eurozone_unemployment_rate_mom",
    "欧元区CPI月率报告": "//datacenter.jin10.com/reportType/dc_eurozone_cpi_mom",
    "欧元区经常帐报告": "//datacenter.jin10.com/reportType/dc_eurozone_current_account_mom",
    "欧元区工业产出月率报告": "//datacenter.jin10.com/reportType/dc_eurozone_industrial_production_mom",
    "欧元区制造业PMI初值报告": "//datacenter.jin10.com/reportType/dc_eurozone_manufacturing_pmi",
    "欧元区服务业PMI终值报告": "//datacenter.jin10.com/reportType/dc_eurozone_services_pmi",
    "欧元区ZEW经济景气指数报告": "//datacenter.jin10.com/reportType/dc_eurozone_zew_economic_sentiment",
    "欧元区Sentix投资者信心指数报告": "//datacenter.jin10.com/reportType/dc_eurozone_sentix_investor_confidence",
}
world_central_bank_map = {
    "美联储决议报告": "//datacenter.jin10.com/reportType/dc_usa_interest_rate_decision",
    "欧洲央行决议报告": "//datacenter.jin10.com/reportType/dc_interest_rate_decision",
    "新西兰联储决议报告": "//datacenter.jin10.com/reportType/dc_newzealand_interest_rate_decision",
    "中国央行决议报告": "//datacenter.jin10.com/reportType/dc_china_interest_rate_decision",
    "瑞士央行决议报告": "//datacenter.jin10.com/reportType/dc_switzerland_interest_rate_decision",
    "英国央行决议报告": "//datacenter.jin10.com/reportType/dc_english_interest_rate_decision",
    "澳洲联储决议报告": "//datacenter.jin10.com/reportType/dc_australia_interest_rate_decision",
    "日本央行决议报告": "//datacenter.jin10.com/reportType/dc_japan_interest_rate_decision",
    "印度央行决议报告": "//datacenter.jin10.com/reportType/dc_india_interest_rate_decision",
    "俄罗斯央行决议报告": "//datacenter.jin10.com/reportType/dc_russia_interest_rate_decision",
    "巴西央行决议报告": "//datacenter.jin10.com/reportType/dc_brazil_interest_rate_decision",
}
constitute_report_map = {
    "全球最大黄金ETF—SPDR Gold Trust持仓报告": "//datacenter.jin10.com/reportType/dc_etf_gold",
    "全球最大白银ETF--iShares Silver Trust持仓报告": "//datacenter.jin10.com/reportType/dc_etf_sliver",
    "芝加哥商业交易所（CME）能源类商品成交量报告": "//datacenter.jin10.com/reportType/dc_cme_energy_report",
    "美国商品期货交易委员会CFTC外汇类非商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_nc_report",
    "美国商品期货交易委员会CFTC商品类非商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_c_report",
    "芝加哥商业交易所（CME）金属类商品成交量报告": "//datacenter.jin10.com/reportType/dc_cme_report",
    "芝加哥商业交易所（CME）外汇类商品成交量报告": "//datacenter.jin10.com/reportType/dc_cme_fx_report",
    "伦敦金属交易所（LME）库存报告": "//datacenter.jin10.com/reportType/dc_lme_report",
    "伦敦金属交易所（LME）持仓报告": "//datacenter.jin10.com/reportType/dc_lme_traders_report",
    "美国商品期货交易委员会CFTC商品类商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_merchant_goods",
    "美国商品期货交易委员会CFTC外汇类商业持仓报告": "//datacenter.jin10.com/reportType/dc_cftc_merchant_currency",
}
other_map = {
    "投机情绪报告": "//datacenter.jin10.com/reportType/dc_ssi_trends",
    "外汇实时波动监控": "//datacenter.jin10.com/reportType/dc_myFxBook_heat_map",
    "外汇相关性报告": "//datacenter.jin10.com/reportType/dc_myFxBook_correlation",
    "加密货币实时行情": "//datacenter.jin10.com/reportType/dc_bitcoin_current",
}
main_map = {
    "全球最大黄金ETF—SPDR Gold Trust持仓报告": "//datacenter.jin10.com/reportType/dc_etf_gold",
    "全球最大白银ETF--iShares Silver Trust持仓报告": "//datacenter.jin10.com/reportType/dc_etf_sliver",
    "美国非农就业人数报告": "//datacenter.jin10.com/reportType/dc_nonfarm_payrolls",
    "投机情绪报告": "//datacenter.jin10.com/reportType/dc_ssi_trends",
    "数据达人 — 复合报告": "//datacenter.jin10.com/reportType/dc_complex_report?complexType=1",
    "投行订单": "//datacenter.jin10.com/banks_orders",
    "行情报价": "//datacenter.jin10.com/price_wall",
    "美国EIA原油库存报告": "//datacenter.jin10.com/reportType/dc_eia_crude_oil",
    "欧佩克报告": "//datacenter.jin10.com/reportType/dc_opec_report",
}
