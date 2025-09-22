# -*- coding:utf-8 -*-
'''
Created on 2014/07/31
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
'''

VERSION = '1.0.3'
K_LABELS = ['D', 'W', 'M']
K_MIN_LABELS = ['5', '15', '30', '60']
K_TYPE = {'D': 'akdaily', 'W': 'akweekly', 'M': 'akmonthly'}
TT_K_TYPE = {'D': 'day', 'W': 'week', 'M': 'month'}
FQ_KEY = ['qfqday', 'hfqday', 'day']
INDEX_LABELS = ['sh', 'sz', 'hs300', 'sz50', 'cyb', 'zxb', 'zx300', 'zh500']
INDEX_LIST = {'sh': 'sh000001', 'sz': 'sz399001', 'hs300': 'sh000300',
              'sz50': 'sh000016', 'zxb': 'sz399005', 'cyb': 'sz399006', 
              'zx300': 'sz399008', 'zh500':'sh000905'}
P_TYPE = {'http': 'http://', 'ftp': 'ftp://'}
PAGE_NUM = [40, 60, 80, 100]
FORMAT = lambda x: '%.2f' % x
FORMAT4 = lambda x: '%.4f' % x
DOMAINS = {'sina': 'sina.com.cn', 'sinahq': 'sinajs.cn',
           'ifeng': 'ifeng.com', 'sf': 'finance.sina.com.cn',
           'vsf': 'vip.stock.finance.sina.com.cn', 
           'idx': 'www.csindex.com.cn', '163': 'money.163.com',
           'em': 'eastmoney.com', 'sseq': 'query.sse.com.cn',
           'sse': 'www.sse.com.cn', 'szse': 'www.szse.cn',
           'oss': 'file.tushare.org', 'idxip':'115.29.204.48',
           'shibor': 'www.shibor.org', 'mbox':'www.cbooo.cn',
           'tt': 'gtimg.cn', 'gw': 'gw.com.cn',
           'v500': 'value500.com', 'sstar': 'stock.stockstar.com',
           'dfcf': 'nufm.dfcfw.com'}
PAGES = {'fd': 'index.phtml', 'dl': 'downxls.php', 'jv': 'json_v2.php',
         'cpt': 'newFLJK.php', 'ids': 'newSinaHy.php', 'lnews':'rollnews_ch_out_interface.php',
         'ntinfo':'vCB_BulletinGather.php', 'hs300b':'000300cons.xls',
         'hs300w':'000300closeweight.xls','sz50b':'000016cons.xls',
         'dp':'all_fpya.php', '163dp':'fpyg.html',
         'emxsg':'JS.aspx', '163fh':'jjcgph.php',
         'newstock':'vRPD_NewStockIssue.php', 'zz500b':'000905cons.xls',
         'zz500wt':'000905closeweight.xls',
         't_ticks':'vMS_tradedetail.php', 'dw': 'downLoad.html',
         'qmd':'queryMargin.do', 'szsefc':'ShowReport.szse',
         'ssecq':'commonQuery.do', 'sinadd':'cn_bill_download.php', 'ids_sw':'SwHy.php',
         'idx': 'index.php', 'index': 'index.html'}
TICK_COLUMNS = ['time', 'price', 'change', 'volume', 'amount', 'type']
TODAY_TICK_COLUMNS = ['time', 'price', 'pchange', 'change', 'volume', 'amount', 'type']
DAY_TRADING_COLUMNS = ['code', 'symbol', 'name', 'changepercent',
                       'trade', 'open', 'high', 'low', 'settlement', 'volume', 'turnoverratio',
                       'amount', 'per', 'pb', 'mktcap', 'nmc']
REPORT_COLS = ['code', 'name', 'eps', 'eps_yoy', 'bvps', 'roe',
               'epcf', 'net_profits', 'profits_yoy', 'distrib', 'report_date']
FORECAST_COLS = ['code', 'name', 'type', 'report_date', 'pre_eps', 'range']
PROFIT_COLS = ['code', 'name', 'roe', 'net_profit_ratio',
               'gross_profit_rate', 'net_profits', 'eps', 'business_income', 'bips']
OPERATION_COLS = ['code', 'name', 'arturnover', 'arturndays', 'inventory_turnover',
                  'inventory_days', 'currentasset_turnover', 'currentasset_days']
GROWTH_COLS = ['code', 'name', 'mbrg', 'nprg', 'nav', 'targ', 'epsg', 'seg']
DEBTPAYING_COLS = ['code', 'name', 'currentratio',
                   'quickratio', 'cashratio', 'icratio', 'sheqratio', 'adratio']
CASHFLOW_COLS = ['code', 'name', 'cf_sales', 'rateofreturn',
                 'cf_nm', 'cf_liabilities', 'cashflowratio']
DAY_PRICE_COLUMNS = ['date', 'open', 'high', 'close', 'low', 'volume', 'price_change', 'p_change',
                     'ma5', 'ma10', 'ma20', 'v_ma5', 'v_ma10', 'v_ma20', 'turnover']
INX_DAY_PRICE_COLUMNS = ['date', 'open', 'high', 'close', 'low', 'volume', 'price_change', 'p_change',
                         'ma5', 'ma10', 'ma20', 'v_ma5', 'v_ma10', 'v_ma20']
LIVE_DATA_COLS = ['name', 'open', 'pre_close', 'price', 'high', 'low', 'bid', 'ask', 'volume', 'amount',
                  'b1_v', 'b1_p', 'b2_v', 'b2_p', 'b3_v', 'b3_p', 'b4_v', 'b4_p', 'b5_v', 'b5_p',
                  'a1_v', 'a1_p', 'a2_v', 'a2_p', 'a3_v', 'a3_p', 'a4_v', 'a4_p', 'a5_v', 'a5_p', 'date', 'time', 's']
FOR_CLASSIFY_COLS = ['code','name']
FOR_CLASSIFY_B_COLS = ['date', 'code','name']
FOR_CLASSIFY_W_COLS = ['date','code', 'name', 'weight']
FOR_CLASSIFY_W5_COLS = ['date','code', 'name', 'weight']
TSDATA_CLASS = '%s%s/tsdata/industry/%s.csv'
THE_FIELDS = ['code','symbol','name','changepercent','trade','open','high','low','settlement','volume','turnoverratio']
KLINE_TT_COLS_MINS = ['date', 'open', 'close', 'high', 'low', 'volume']
KLINE_TT_COLS = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'turnoverratio']
TICK_PRICE_URL = '%smarket.%s/%s?date=%s&symbol=%s'
TICK_PRICE_URL_TT = '%sstock.%s/data/%s?appn=detail&action=download&c=%s&d=%s'
TICK_PRICE_URL_NT = '%squotes.%s/cjmx/%s/%s/%s.xls'
TODAY_TICKS_PAGE_URL = '%s%s/quotes_service/api/%s/CN_Transactions.getAllPageTime?date=%s&symbol=%s'
TODAY_TICKS_URL = '%s%s/quotes_service/view/%s?symbol=%s&date=%s&page=%s'
KLINE_TT_URL = '%sweb.ifzq.%s/appstock/app/%skline/get?_var=kline_day%s&param=%s,%s,%s,%s,640,%s&r=0.%s'
KLINE_TT_MIN_URL = '%sifzq.%s/appstock/app/kline/mkline?param=%s,m%s,,640&_var=m%s_today&r=0.%s'
DAY_PRICE_URL = '%sapi.finance.%s/%s/?code=%s&type=last'
LIVE_DATA_URL = '%shq.%s/rn=%s&list=%s'
DAY_PRICE_MIN_URL = '%sapi.finance.%s/akmin?scode=%s&type=%s'
SINA_DAY_PRICE_URL = '%s%s/quotes_service/api/%s/Market_Center.getHQNodeData?num=200&sort=code&asc=0&node=%s&symbol=&_s_r_a=page&page=%s'
# SINA_DAY_PRICE_URL = '%s%s/quotes_service/api/%s/Market_Center.getHQNodeData?num=10000&node=%s'
REPORT_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/mainindex/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
FORECAST_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/performance/%s?s_i=&s_a=&s_c=&s_type=&reportdate=%s&quarter=%s&p=%s&num=%s'
PROFIT_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/profit/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
OPERATION_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/operation/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
GROWTH_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/grow/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
DEBTPAYING_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/debtpaying/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
CASHFLOW_URL = '%s%s/q/go.php/vFinanceAnalyze/kind/cashflow/%s?s_i=&s_a=&s_c=&reportdate=%s&quarter=%s&p=%s&num=%s'
SHIBOR_TYPE ={'Shibor': 'Shibor数据', 'Quote': '报价数据', 'Tendency': 'Shibor均值数据',
              'LPR': 'LPR数据', 'LPR_Tendency': 'LPR均值数据'}
SHIBOR_DATA_URL = '%s%s/shibor/web/html/%s?nameNew=Historical_%s_Data_%s.xls&downLoadPath=data&nameOld=%s%s.xls&shiborSrc=http://www.shibor.org/shibor/'
ALL_STOCK_BASICS_FILE = P_TYPE['http'] + DOMAINS['oss'] + '/tsdata/%sall%s.csv'
ALL_DAY_FILE = P_TYPE['http'] + DOMAINS['oss'] + '/tsdata/h/%s%s.csv'
ALL_CAL_FILE = '%s%s/tsdata/calAll.csv'%(P_TYPE['http'], DOMAINS['oss'])
SINA_CONCEPTS_INDEX_URL = '%smoney.%s/q/view/%s?param=class'
ET_CONCEPTS_INDEX_URL = '%s%s/EM_Finance2014NumericApplication/JS.aspx?type=CT&cmd=C._BKGN&js=[(x)]&sty=FPGBKI&st=c&sr=-1&p=1&ps=5000&cb=&token=7bc05d0d4c3c22ef9fca8c2a912d779c&v=0.0%s'
SINA_INDUSTRY_INDEX_URL = '%s%s/q/view/%s'
SINA_DATA_DETAIL_URL = '%s%s/quotes_service/api/%s/Market_Center.getHQNodeData?page=%s&num=1000&sort=symbol&asc=1&node=%s&symbol=&_s_r_a=page'
SINA_BALANCESHEET_URL = 'http://money.finance.sina.com.cn/corp/go.php/vDOWN_BalanceSheet/displaytype/4/stockid/%s/ctrl/all.phtml'
SINA_PROFITSTATEMENT_URL = 'http://money.finance.sina.com.cn/corp/go.php/vDOWN_ProfitStatement/displaytype/4/stockid/%s/ctrl/all.phtml'
SINA_CASHFLOW_URL = 'http://money.finance.sina.com.cn/corp/go.php/vDOWN_CashFlow/displaytype/4/stockid/%s/ctrl/all.phtml'
INDEX_C_COMM = 'sseportal/ps/zhs/hqjt/csi'
HS300_CLASSIFY_URL_FTP = '%s%s/uploads/file/autofile/closeweight/%s'
SZ_CLASSIFY_URL_FTP = '%s%s/uploads/file/autofile/cons/%s'
HS300_CLASSIFY_URL_HTTP = '%s%s/%s/%s'
BDI_URL = '%s%s/BDI.asp'
HIST_FQ_URL = '%s%s/corp/go.php/vMS_FuQuanMarketHistory/stockid/%s.phtml?year=%s&jidu=%s'
HIST_INDEX_URL = '%s%s/corp/go.php/vMS_MarketHistory/stockid/%s/type/S.phtml?year=%s&jidu=%s'
HIST_FQ_FACTOR_URL = '%s%s/api/json.php/BasicStockSrv.getStockFuQuanData?symbol=%s&type=hfq'
ADJ_FAC_URL = '%s%s/tsdata/f/factor/%s.csv'
MG_URL = '%s%s/tsdata/rzrq/%s/%s%s.csv'
MG_ZSL_URL = '%s%s/tsdata/rzrq/%s/zsl/%s_%s.csv'
GPZY_URL = '%s%s/tsdata/gpzy/%s.csv'
GPZY_D_URL = '%s%s/tsdata/gpzy/%s.csv'
SHS_FAC_URL = '%s%s/tsdata/shares/%s.csv'
ZF = '%s%s/tsdata/%s.csv'
INDEX_HQ_URL = '''%shq.%s/rn=xppzh&list=sh000001,sh000002,sh000003,sh000008,sh000009,sh000010,sh000011,sh000012,sh000016,sh000017,sh000300,sh000905,sz399001,sz399002,sz399003,sz399004,sz399005,sz399006,sz399008,sz399100,sz399101,sz399106,sz399107,sz399108,sz399333,sz399606'''
SSEQ_CQ_REF_URL = '%s%s/assortment/stock/list/name'
ALL_STK_URL = '%s%s/all.csv'
SINA_DD = '%s%s/quotes_service/view/%s?symbol=%s&num=60&page=1&sort=ticktime&asc=0&volume=%s&amount=0&type=0&day=%s'
BOX = 'boxOffice'
MOVIE_BOX = '%s%s/%s/GetHourBoxOffice?d=%s'
BOXOFFICE_DAY = '%s%s/%s/GetDayBoxOffice?num=%s&d=%s'
BOXOFFICE_MONTH = '%s%s/%s/getMonthBox?sdate=%s'
BOXOFFICE_CBD = '%s%s/%s/getCBD?pIndex=%s&dt=%s'
SHIBOR_COLS = ['date', 'ON', '1W', '2W', '1M', '3M', '6M', '9M', '1Y']
SHIBOR_Q_COLS = ['date', 'bank', 'ON', '1W', '2W', '1M', '3M', '6M', '9M', '1Y']
QUOTE_COLS = ['date', 'bank', 'ON_B', 'ON_A', '1W_B', '1W_A', '2W_B', '2W_A', '1M_B', '1M_A',
                    '3M_B', '3M_A', '6M_B', '6M_A', '9M_B', '9M_A', '1Y_B', '1Y_A']
SHIBOR_MA_COLS = ['date', 'ON_5', 'ON_10', 'ON_20', '1W_5', '1W_10', '1W_20','2W_5', '2W_10', '2W_20',
                  '1M_5', '1M_10', '1M_20', '3M_5', '3M_10', '3M_20', '6M_5', '6M_10', '6M_20',
                  '9M_5', '9M_10', '9M_20','1Y_5', '1Y_10', '1Y_20']
LPR_COLS = ['date', '1Y']
KTYPE = {
         'D'     : 9,
         'XD'    : 4,
         'W'     : 5,
         'M'     : 6,
         'Q'     : 10,
         'Y'     : 11,
         '1MIN'  : 8,
         '5MIN'  : 0,
         '15MIN' : 1,
         '30MIN' : 2,
         '60MIN' : 3,
         }
ASSET = {
         'E' : 'get_security_bars',
         'INDEX' : 'get_index_bars',
         'X' : 'get_instrument_bars',
         }
KTYPE_LOW_COLS = ['D', 'XD', 'W', 'M', 'Q', 'Y']
KTYPE_ARR = ['1MIN', '5MIN', '15MIN', '30MIN', '60MIN']
BAR_E_COLS = ['code', 'open', 'close', 'high', 'low', 'vol', 'amount']
BAR_X_COLS = ['code', 'open', 'close', 'high', 'low', 'price', 'position','trade']
BAR_X_FUTURE_COLS = ['code', 'open', 'close', 'high', 'low', 'avg_price', 'position', 'vol']
BAR_X_FUTURE_RL_COLS = ['code', 'open', 'close', 'high', 'low', 'vol', 'avg_price', 'position']
BAR_X_OTHER_COLS = ['code', 'open', 'close', 'high', 'low', 'vol']
T_DROP_COLS = ['year', 'month', 'day', 'hour','minute']
LPR_MA_COLS = ['date', '1Y_5', '1Y_10', '1Y_20']
INDEX_HEADER = 'code,name,open,preclose,close,high,low,0,0,volume,amount,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,d,c,3,\n'
INDEX_COLS = ['code', 'name', 'change', 'open', 'preclose', 'close', 'high', 'low', 'volume', 'amount']
HIST_FQ_COLS = ['date', 'open', 'high', 'close', 'low', 'volume', 'amount', 'factor']
SINA_DD_COLS = ['code', 'name', 'time', 'price', 'volume', 'preprice', 'type']
GLOBAL_HQ_SYMBOL = 'sh000001,hkHSI,znb_UKX,znb_DAX,znb_INDEXCF,znb_CAC,znb_SMI,znb_FTSEMIB,znb_MADX,znb_OMX,znb_SPX,znb_HEX,znb_OSEAX,znb_ISEQ,znb_AEX,znb_ICEXI,znb_NKY,znb_TWSE,znb_FSSTI,znb_KOSPI,znb_FBMKLCI,znb_SET,znb_JCI,znb_PCOMP,znb_KSE100,znb_SENSEX,znb_VNINDEX,znb_CSEALL,znb_SASEIDX,znb_SPTSX,znb_MEXBOL,znb_IBOV,znb_MERVAL,znb_AS51,znb_NZSE50FG,znb_CASE,znb_JALSH,sz399001,znb_INDU,znb_CCMP'
GLOBAL_HQ_COLS = ['symbol', 'name', 'price', 'chga', 'chgp', 'datetime']
INST_PLK_F = 'ts_instrument.plk'
PROFIT_DIVIS = ['code',    
                'name',    
                'year',  
                'bshares',  
                'incshares',
                'totals', 
                'cash',
                'plandate',    
                'regdate',    
                'exdate',    
                'eventproc',
                'anndate']
HIST_FQ_FACTOR_COLS = ['code','value']
DATA_GETTING_TIPS = '[Getting data:]'
DATA_GETTING_FLAG = '#'
DATA_ROWS_TIPS = '%s rows data found.Please wait for a moment.'
DATA_INPUT_ERROR_MSG = 'date input error.'
MSG_NOT_CONNECTED = '服务器连接为空，请通过ts.get_apis()获取'
NETWORK_URL_ERROR_MSG = '获取失败，请检查网络.'
DATE_CHK_MSG = '年度输入错误：请输入1989年以后的年份数字，格式：YYYY'
DATE_CHK_Q_MSG = '季度输入错误：请输入1、2、3或4数字'
TOP_PARAS_MSG = 'top有误，请输入整数或all.'
LHB_MSG = '周期输入有误，请输入数字5、10、30或60'
TOKEN_F_P = 'tk.csv'
TOKEN_ERR_MSG = '请设置tushare pro的token凭证码，如果没有请访问https://tushare.pro注册申请'
BOX_INPUT_ERR_MSG = '请输入YYYY-MM格式的年月数据'
TICK_SRCS = ['sn', 'tt', 'nt']
TICK_SRC_ERROR = '数据源代码只能输入sn,tt,nt其中之一'
INDEX_SYMBOL = {'399990': 'sz399990', '000006': 'sh000006', '399998': 'sz399998', 
                '399436': 'sz399436', '399678': 'sz399678', '399804': 'sz399804', 
                '000104': 'sh000104', '000070': 'sh000070', '399613': 'sz399613', 
                '399690': 'sz399690', '399928': 'sz399928', '000928': 'sh000928', 
                '000986': 'sh000986', '399806': 'sz399806', '000032': 'sh000032', 
                '000005': 'sh000005', '399381': 'sz399381', '399908': 'sz399908', 
                '000908': 'sh000908', '399691': 'sz399691', '000139': 'sh000139', 
                '399427': 'sz399427', '399248': 'sz399248', '000832': 'sh000832', 
                '399901': 'sz399901', '399413': 'sz399413', '000901': 'sh000901', 
                '000078': 'sh000078', '000944': 'sh000944', '000025': 'sh000025', 
                '399944': 'sz399944', '399307': 'sz399307', '000052': 'sh000052', 
                '399680': 'sz399680', '399232': 'sz399232', '399993': 'sz399993', 
                '000102': 'sh000102', '000950': 'sh000950', '399950': 'sz399950', 
                '399244': 'sz399244', '399925': 'sz399925', '000925': 'sh000925', 
                '000003': 'sh000003', '000805': 'sh000805', '000133': 'sh000133', 
                '399677': 'sz399677', '399319': 'sz399319', '399397': 'sz399397', 
                '399983': 'sz399983', '399654': 'sz399654', '399440': 'sz399440', 
                '000043': 'sh000043', '000012': 'sh000012', '000833': 'sh000833', 
                '000145': 'sh000145', '000053': 'sh000053', '000013': 'sh000013', 
                '000022': 'sh000022', '000094': 'sh000094', '399299': 'sz399299', 
                '000101': 'sh000101', '399817': 'sz399817', '399481': 'sz399481', 
                '399434': 'sz399434', '399301': 'sz399301', '000029': 'sh000029', 
                '399812': 'sz399812', '399441': 'sz399441', '000098': 'sh000098', 
                '399557': 'sz399557', '000068': 'sh000068', '399298': 'sz399298', 
                '399302': 'sz399302', '000961': 'sh000961', '000959': 'sh000959', 
                '399961': 'sz399961', '000126': 'sh000126', '000036': 'sh000036', 
                '399305': 'sz399305', '000116': 'sh000116', '399359': 'sz399359', 
                '399810': 'sz399810', '000062': 'sh000062', '399618': 'sz399618', 
                '399435': 'sz399435', '000149': 'sh000149', '000819': 'sh000819', 
                '000020': 'sh000020', '000061': 'sh000061', '000016': 'sh000016', 
                '000028': 'sh000028', '399809': 'sz399809', '000999': 'sh000999', 
                '399238': 'sz399238', '000100': 'sh000100', '399979': 'sz399979', 
                '000979': 'sh000979', '399685': 'sz399685', '000152': 'sh000152', 
                '000153': 'sh000153', '399318': 'sz399318', '000853': 'sh000853', 
                '000040': 'sh000040', '399693': 'sz399693', '000076': 'sh000076', 
                '000017': 'sh000017', '000134': 'sh000134', '399989': 'sz399989', 
                '000042': 'sh000042', '000066': 'sh000066', '000008': 'sh000008', 
                '000002': 'sh000002', '000001': 'sh000001', '000011': 'sh000011', 
                '000031': 'sh000031', '399403': 'sz399403', '000951': 'sh000951', 
                '399951': 'sz399951', '000092': 'sh000092', '399234': 'sz399234', 
                '000823': 'sh000823', '399986': 'sz399986', '399647': 'sz399647', 
                '000050': 'sh000050', '000073': 'sh000073', '399357': 'sz399357', 
                '000940': 'sh000940', '000107': 'sh000107', '000048': 'sh000048', 
                '399411': 'sz399411', '399366': 'sz399366', '399373': 'sz399373', 
                '000015': 'sh000015', '000021': 'sh000021', '000151': 'sh000151', 
                '000851': 'sh000851', '000058': 'sh000058', '399404': 'sz399404', 
                '399102': 'sz399102', '399431': 'sz399431', '399971': 'sz399971', 
                '000125': 'sh000125', '000069': 'sh000069', '000063': 'sh000063', 
                '399395': 'sz399395', '000038': 'sh000038', '399240': 'sz399240', 
                '399903': 'sz399903', '000989': 'sh000989', '399321': 'sz399321', 
                '399675': 'sz399675', '399235': 'sz399235', '000057': 'sh000057', 
                '000056': 'sh000056', '000903': 'sh000903', '399310': 'sz399310', 
                '000004': 'sh000004', '000019': 'sh000019', '399919': 'sz399919', 
                '000974': 'sh000974', '000919': 'sh000919', '399635': 'sz399635', 
                '399663': 'sz399663', '399106': 'sz399106', '399107': 'sz399107', 
                '399555': 'sz399555', '000090': 'sh000090', '000155': 'sh000155', 
                '000060': 'sh000060', '399636': 'sz399636', '000816': 'sh000816', 
                '000010': 'sh000010', '399671': 'sz399671', '000035': 'sh000035', 
                '399352': 'sz399352', '399683': 'sz399683', '399554': 'sz399554', 
                '399409': 'sz399409', '000018': 'sh000018', '399101': 'sz399101', 
                '000992': 'sh000992', '399416': 'sz399416', '399918': 'sz399918', 
                '399379': 'sz399379', '399674': 'sz399674', '399239': 'sz399239', 
                '399384': 'sz399384', '399367': 'sz399367', '000918': 'sh000918', 
                '000914': 'sh000914', '399914': 'sz399914', '000054': 'sh000054', 
                '000806': 'sh000806', '399619': 'sz399619', '399015': 'sz399015', 
                '399393': 'sz399393', '399313': 'sz399313', '399231': 'sz399231', 
                '000846': 'sh000846', '000854': 'sh000854', '399010': 'sz399010', 
                '399666': 'sz399666', '399387': 'sz399387', '399399': 'sz399399', 
                '000026': 'sh000026', '399934': 'sz399934', '000150': 'sh000150', 
                '000934': 'sh000934', '399317': 'sz399317', '000138': 'sh000138', 
                '399371': 'sz399371', '399394': 'sz399394', '399659': 'sz399659', 
                '399665': 'sz399665', '399931': 'sz399931', '000161': 'sh000161', 
                '399380': 'sz399380', '000931': 'sh000931', '399704': 'sz399704', 
                '399616': 'sz399616', '000817': 'sh000817', '399303': 'sz399303', 
                '399629': 'sz399629', '399624': 'sz399624', '399009': 'sz399009', 
                '399233': 'sz399233', '399103': 'sz399103', '399242': 'sz399242', 
                '399627': 'sz399627', '000971': 'sh000971', '399679': 'sz399679', 
                '399912': 'sz399912', '000982': 'sh000982', '399668': 'sz399668', 
                '000096': 'sh000096', '399982': 'sz399982', '000849': 'sh000849', 
                '000148': 'sh000148', '399364': 'sz399364', '000912': 'sh000912', 
                '000129': 'sh000129', '000055': 'sh000055', '000047': 'sh000047', '399355': 'sz399355', '399622': 'sz399622', '000033': 'sh000033', '399640': 'sz399640', '000852': 'sh000852', '399966': 'sz399966', '399615': 'sz399615', '399802': 'sz399802', '399602': 'sz399602', '000105': 'sh000105', '399660': 'sz399660', '399672': 'sz399672', 
                '399913': 'sz399913', '399420': 'sz399420', '000159': 'sh000159', '399314': 'sz399314', '399652': 'sz399652', 
                '399369': 'sz399369', '000913': 'sh000913', '000065': 'sh000065', 
                '000808': 'sh000808', '399386': 'sz399386', '399100': 'sz399100', 
                '000997': 'sh000997', '000990': 'sh000990', '000093': 'sh000093', '399637': 'sz399637', '399439': 'sz399439', '399306': 'sz399306', '000855': 'sh000855', '000123': 'sh000123', '399623': 'sz399623', 
                '399312': 'sz399312', '399249': 'sz399249', '399311': 'sz399311', '399975': 'sz399975', '399356': 'sz399356', 
                '399400': 'sz399400', '399676': 'sz399676', '000136': 'sh000136', '399361': 'sz399361', '399974': 'sz399974', '399995': 'sz399995', '399316': 'sz399316', '399701': 'sz399701', '000300': 'sh000300', '000030': 'sh000030', '000976': 'sh000976', '399686': 'sz399686', '399108': 'sz399108', '399374': 'sz399374', 
                '000906': 'sh000906', '399707': 'sz399707', '000064': 'sh000064', '399633': 'sz399633', '399300': 'sz399300', '399628': 'sz399628', '399398': 'sz399398', '000034': 'sh000034', 
                '399644': 'sz399644', '399905': 'sz399905', '399626': 'sz399626', 
                '399625': 'sz399625', '000978': 'sh000978', '399664': 'sz399664', '399682': 'sz399682', '399322': 'sz399322', '000158': 'sh000158', '000842': 'sh000842', '399550': 'sz399550', '399423': 'sz399423', '399978': 'sz399978', '399996': 'sz399996', '000905': 'sh000905', 
                '000007': 'sh000007', '000827': 'sh000827', '399655': 'sz399655', '399401': 'sz399401', '399650': 'sz399650', '000963': 'sh000963', '399661': 'sz399661', '399922': 'sz399922', '000091': 'sh000091', '399375': 'sz399375', '000922': 'sh000922', '399702': 'sz399702', '399963': 'sz399963', '399011': 'sz399011', '399012': 'sz399012', 
                '399383': 'sz399383', '399657': 'sz399657', '399910': 'sz399910', '399351': 'sz399351', '000910': 'sh000910', '000051': 'sh000051', '399376': 'sz399376', '399639': 'sz399639', '000821': 'sh000821', '399360': 'sz399360', '399604': 'sz399604', '399315': 'sz399315', '399658': 'sz399658', '000135': 'sh000135', 
                '000059': 'sh000059', '399006': 'sz399006', 
                '399320': 'sz399320', '000991': 'sh000991', '399606': 'sz399606', 
                '399428': 'sz399428', '399406': 'sz399406', '399630': 'sz399630', '000802': 'sh000802', '399803': 'sz399803', '000071': 'sh000071', '399358': 'sz399358', 
                '399013': 'sz399013', '399385': 'sz399385', '399008': 'sz399008', '399649': 'sz399649', 
                '399673': 'sz399673', '399418': 'sz399418', '399370': 'sz399370', '000814': 'sh000814', 
                '399002': 'sz399002', '399814': 'sz399814', '399641': 'sz399641', '399001': 'sz399001', 
                '399662': 'sz399662', '399706': 'sz399706', '399932': 'sz399932', '000095': 'sh000095', '000932': 'sh000932', '399965': 'sz399965', '399363': 'sz399363', '399354': 'sz399354', '399638': 'sz399638', '399648': 'sz399648', '399608': 'sz399608', '000939': 'sh000939', '399939': 'sz399939', '399365': 'sz399365', '399382': 'sz399382', '399631': 'sz399631', '399612': 'sz399612', '399611': 'sz399611', '399645': 'sz399645', 
                '399324': 'sz399324', '399552': 'sz399552', '000858': 'sh000858', '000045': 'sh000045', 
                '000121': 'sh000121', '399703': 'sz399703', '399003': 'sz399003', 
                '399348': 'sz399348', '399389': 'sz399389', '399007': 'sz399007', '399391': 'sz399391', '000973': 'sh000973', 
                '000984': 'sh000984', '000969': 'sh000969', '000952': 'sh000952', '399332': 'sz399332', '399952': 'sz399952', '399553': 'sz399553', '000856': 'sh000856', 
                '399969': 'sz399969', '399643': 'sz399643', '399402': 'sz399402', '399372': 'sz399372', '399632': 'sz399632', '399344': 'sz399344', '399808': 'sz399808', '399620': 'sz399620', '000103': 'sh000103', '399911': 'sz399911', '000993': 'sh000993', '000983': 'sh000983', '399687': 'sz399687', '399933': 'sz399933', '000933': 'sh000933', '399437': 'sz399437', '399433': 'sz399433', '000046': 'sh000046', '000911': 'sh000911', '000114': 'sh000114', '000049': 'sh000049', '399392': 'sz399392', '399653': 'sz399653', '000975': 'sh000975', '000044': 'sh000044', '399378': 'sz399378', '000828': 'sh000828', '399634': 'sz399634', 
                '399005': 'sz399005', '000162': 'sh000162', '399333': 'sz399333', '000122': 'sh000122', '399646': 'sz399646', '000077': 'sh000077', '000074': 'sh000074', '399656': 'sz399656', '399396': 'sz399396', '399415': 'sz399415', '399408': 'sz399408', '000115': 'sh000115', '000987': 'sh000987', '399362': 'sz399362', '000841': 'sh000841', '000141': 'sh000141', '000120': 'sh000120', '399992': 'sz399992', '000807': 'sh000807', '399350': 'sz399350', '000009': 'sh000009', '000998': 'sh000998', '399390': 'sz399390', '399405': 'sz399405', '000099': 'sh000099', '399337': 'sz399337', '000142': 'sh000142', '399419': 'sz399419', '399407': 'sz399407', '000909': 'sh000909', '000119': 'sh000119', '399909': 'sz399909', '399805': 'sz399805', '000996': 'sh000996', '000847': 'sh000847', '000130': 'sh000130', '399377': 'sz399377', '399388': 'sz399388', '399610': 'sz399610', '000958': 'sh000958', 
                '399958': 'sz399958', '000075': 'sh000075', '399346': 'sz399346', '000147': 'sh000147', '000132': 'sh000132', '000108': 'sh000108', '399642': 'sz399642', '000977': 'sh000977', '399689': 'sz399689', '399335': 'sz399335', '399977': 'sz399977', '399972': 'sz399972', '399970': 'sz399970', '399004': 'sz399004', '399341': 'sz399341', '399330': 'sz399330', '399917': 'sz399917', '000160': 'sh000160', '399432': 'sz399432', '399429': 'sz399429', '000917': 'sh000917', 
                '000128': 'sh000128', '000067': 'sh000067', '000079': 'sh000079', '399236': 'sz399236', '399994': 'sz399994', '399237': 'sz399237', '000966': 'sh000966', '000957': 'sh000957', '399328': 'sz399328', 
                '399353': 'sz399353', '399957': 'sz399957', '399412': 'sz399412', '000904': 'sh000904', '399904': 'sz399904', '399410': 'sz399410', '000027': 'sh000027', '399667': 'sz399667', '000857': 'sh000857', 
                '000131': 'sh000131', '000964': 'sh000964', '399339': 'sz399339', '399964': 'sz399964', '399991': 'sz399991', '399417': 'sz399417', '000146': 'sh000146', '399551': 'sz399551', '000137': 'sh000137', '000118': 'sh000118', '399976': 'sz399976', '000109': 'sh000109', '399681': 'sz399681', '399438': 'sz399438', '000117': 'sh000117', '399614': 'sz399614', '399669': 'sz399669', '000111': 'sh000111', '399670': 'sz399670', '000097': 'sh000097', '000106': 'sh000106', '000039': 'sh000039', '399935': 'sz399935', '000935': 'sh000935', '399813': 'sz399813', '000037': 'sh000037', '399811': 'sz399811', '399705': 'sz399705', '399556': 'sz399556', '000113': 'sh000113', '000072': 'sh000072', '399651': 'sz399651', '399617': 'sz399617', '399684': 'sz399684', '000041': 'sh000041', '399807': 'sz399807', '399959': 'sz399959', '399967': 'sz399967', '399326': 'sz399326', '399688': 'sz399688', '399368': 'sz399368', '399241': 'sz399241', '399696': 'sz399696', '000850': 'sh000850', '000110': 'sh000110', '399621': 'sz399621', '399243': 'sz399243', 
                '399973': 'sz399973', '399987': 'sz399987', '000112': 'sh000112', '399997': 'sz399997', 
                '000915': 'sh000915', '000916': 'sh000916',
                'hkHSI':'hkHSI'}
MKTS = {
'TP': [1,  1,'临时股'],
'OZ': [4, 12, '郑州商品期权'],
'OD': [5, 12, '大连商品期权'],
'OS': [6, 12, '上海商品期权'],
'QQ': [8, 12, '上海个股期权'],
'FH': [27, 5,    '香港指数'],
'QZ': [28, 3,   '郑州商品'],
'QD': [29, 3,    '大连商品'],
'QS': [30,  3,  '上海期货'],
'KH': [31,  2,  '香港主板'],
'KR': [32,  2,  '香港权证'],
'FU': [33,  8, '开放式基金'],
'FB': [34,  9, '货币型基金'],
'LC': [35,  8,'招商理财产品'],
'LB': [36,  9,'招商货币产品'],
'FW': [37, 11,  '国际指数'],
'HG': [38, 10,'国内宏观指标'],
'CH': [40, 11, '中国概念股'],
'MG': [41, 11,'美股知名公司'],
'HB': [43,  1, 'B股转H股'],
'SB': [44,  1,  '股份转让'],
'CZ': [47,  3,  '股指期货'],
'KG': [48,  2, '香港创业板'],
'KT': [49,  2,'香港信托基金'],
'GY': [54,  6, '国债预发行'],
'MA': [60,  3,'主力期货合约'],
'ZZ': [62,  5,  '中证指数'],
'GH': [71,  2,   '港股通'],
'SZ': [0,   0, 'SHENZHEN'],
'SH': [1,   1, 'SHANGHAI']
}
SLIST = ['180.153.18.170', '180.153.18.171', '202.108.253.130', '202.108.253.131', '60.191.117.167', '115.238.56.198', '218.75.126.9', '115.238.90.165',
             '124.160.88.183', '60.12.136.250', '218.108.98.244', '218.108.47.69', '14.17.75.71', '180.153.39.51']
XXLIST = ['61.152.107.141']
XLIST = ['121.14.110.210', '119.147.212.76', '113.105.73.86', '119.147.171.211', '119.147.164.57', '119.147.164.58', '61.49.50.180', '61.49.50.181',
         '61.135.142.85', '61.135.149.181', '114.80.80.210', '222.73.49.15', '221.194.181.176']
T_PORT = 7709
X_PORT = 7727

import sys
PY3 = (sys.version_info[0] >= 3)
def _write_head():
    sys.stdout.write(DATA_GETTING_TIPS)
    sys.stdout.flush()

def _write_console():
    sys.stdout.write(DATA_GETTING_FLAG)
    sys.stdout.flush()
    
def _write_tips(tip):
    sys.stdout.write(DATA_ROWS_TIPS%tip)
    sys.stdout.flush()

def _write_msg(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()
    
def _check_input(year, quarter):
    if isinstance(year, str) or year < 1989 :
        raise TypeError(DATE_CHK_MSG)
    elif quarter is None or isinstance(quarter, str) or quarter not in [1, 2, 3, 4]:
        raise TypeError(DATE_CHK_Q_MSG)
    else:
        return True
    
def _check_lhb_input(last):
    if last not in [5, 10, 30, 60]:
        raise TypeError(LHB_MSG)
    else:
        return True



def _market_code(code):
        code = str(code)
        if code[0] in ['5', '6', '9'] or code[:3] in ['009', '100', '110', '112', \
                                                      '113', '120', '129', '181', \
                                                      '126', '201', '202', '203', \
                                                      '204', '190', '191']:
            return 1
        return 0

def _idx_market_code(code):
        code = str(code)
        if code[0] in ['0']:
            return 1
        if code[:3] in ['399']:
            return 0
        return code


def _code_to_symbol(code):
    '''
        生成symbol代码标志
    '''
    if code in INDEX_LABELS:
        return INDEX_LIST[code]
    else:
        if len(code) != 6 :
            return code
        else:
            return 'sh%s'%code if code[:1] in ['5', '6', '9'] or code[:2] in ['11', '13'] else 'sz%s'%code

        
def _code_to_symbol_dgt(code):
    '''
        生成symbol代码标志
    '''
    if code in INDEX_LABELS:
        return INDEX_LIST[code]
    else:
        if len(code) != 6 :
            return code
        else:
            return '0%s'%code if code[:1] in ['5', '6', '9'] else '1%s'%code


def _get_server():
    import random
    ips = SLIST
    random.shuffle(ips)
    return ips[0]

def _get_xserver():
    import random
    ips = XLIST
    random.shuffle(ips)
    return ips[0]

def _get_xxserver():
    import random
    ips = XXLIST
    random.shuffle(ips)
    return ips[0]