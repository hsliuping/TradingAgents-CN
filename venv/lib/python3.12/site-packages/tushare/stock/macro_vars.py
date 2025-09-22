# -*- coding:utf-8 -*- 

P_TYPE = {'http':'http://','ftp':'ftp://'}
DOMAINS = {'sina':'sina.com.cn','sinahq':'sinajs.cn','ifeng':'ifeng.com'}
MACRO_TYPE = ['nation','price','fininfo']
MACRO_URL = '%smoney.finance.%s/mac/api/jsonp.php/SINAREMOTECALLCALLBACK%s/MacPage_Service.get_pagedata?cate=%s&event=%s&from=0&num=%s&condition=&_=%s'
GDP_YEAR_COLS = ['year','gdp','pc_gdp','gnp','pi','si','industry','cons_industry','ti','trans_industry','lbdy']
GDP_QUARTER_COLS = ['quarter','gdp','gdp_yoy','pi','pi_yoy','si','si_yoy','ti','ti_yoy']
GDP_FOR_COLS = ['year','end_for','for_rate','asset_for','asset_rate','goods_for','goods_rate']
GDP_PULL_COLS = ['year','gdp_yoy','pi','si','industry','ti']
GDP_CONTRIB_COLS = ['year','gdp_yoy','pi','si','industry','ti']
CPI_COLS = ['month','cpi']
PPI_COLS = ['month','ppiip','ppi','qm','rmi','pi','cg','food','clothing','roeu','dcg']
DEPOSIT_COLS = ['date','deposit_type','rate']
LOAN_COLS = ['date','loan_type','rate']
RRR_COLS = ['date','before','now','changed']
MONEY_SUPPLY_COLS = ['month','m2','m2_yoy','m1','m1_yoy','m0','m0_yoy','cd','cd_yoy','qm','qm_yoy','ftd','ftd_yoy','sd','sd_yoy','rests','rests_yoy']
MONEY_SUPPLY_BLA_COLS = ['year','m2','m1','m0','cd','qm','ftd','sd','rests']
GOLD_AND_FOREIGN_CURRENCY_RESERVES = ['month','gold','foreign_reserves']

def random(n=13):
    from random import randint
    start = 10**(n-1)
    end = (10**n)-1
    return str(randint(start, end))