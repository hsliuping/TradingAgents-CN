"""
AKShare 是基于 Python 的开源财经数据接口库，实现对股票、期货、期权、基金、债券、外汇、加密货币等金
融产品的量价数据，基本面数据和另类数据从数据采集，数据清洗到数据下载的工具，满足金融数据科学
家，数据科学爱好者在数据获取方面的需求。它的特点是利用 AKShare 获取的是基于可信任数据源
发布的原始数据，广大数据科学家可以利用原始数据进行再加工，从而得出科学的结论。如果您使用其他编程语言或软件
请使用 AKTools 来快速搭建 AKShare HTTP API 接口。
"""

"""
版本更新记录:
0.1.13
更新所有基于 fushare 的接口
0.1.14
更新 requirements.txt 文件
0.1.15
自动安装所需要的 packages
0.1.16
修正部分函数命名
0.1.17
更新版本号自动管理
0.1.18
更新说明文档
0.1.19
修正 cot.py 中请求错误
0.1.20
修正 __doc__
0.1.21
修复 __doc__
0.1.22
修复命名和绘图
0.1.23
修复错误机制
0.1.24
增加奇货可查所有指数数据获取接口
0.1.25
修复 qhck 接口
0.1.26
修复代码格式问题
0.1.27
修复说明格式问题
0.1.28
更新说明文档
0.1.29
规范说明文档格式
0.1.30
规范说明文档格式
0.1.31
规范 cot.py 函数说明
0.1.32
update futures_basis.py
0.1.33
增加奇货可查数据三个接口:
get_qhkc_index, get_qhkc_index_trend, get_qhkc_index_profit_loss
使用方法请 help(get_qhkc_index) 查看
0.1.34
增加奇货可查-资金数据三个接口:
get_qhkc_fund_position_change, get_qhkc_fund_bs, get_qhkc_fund_position
使用方法请 help(get_qhkc_fund_position_change) 查看
0.1.35
增加奇货可查-工具-外盘比价接口:
get_qhkc_tool_foreign
使用方法请 help(get_qhkc_tool_foreign) 查看
0.1.36
增加奇货可查-工具-各地区经济数据接口:
get_qhkc_tool_gdp
使用方法请 help(get_qhkc_tool_gdp) 查看
0.1.37
增加中国银行间市场交易商协会-债券接口
get_bond_bank
使用方法请 help(get_bond_bank) 查看
0.1.38
修正
0.1.39
模块化处理
0.1.40
统一接口函数参数 start --> start_day; end --> end_day
0.1.41
更新大连商品交易所-苯乙烯-EB品种
0.1.42
更新上海期货交易所-上海国际能源交易中心-20号胶-NR品种
更新上海期货交易所-不锈钢-SS品种
0.1.43
修复 example --> qhkc_api.py 函数调用
0.1.44
修复 example --> daily_run.py 函数调用
0.1.45
修复 akdocker.md 函数接口调用说明和感谢单位
0.1.46
修复 akdocker.md 图片显示
0.1.47
修复 akdocker.md 增加说明部分
0.1.48
更新大连商品交易所-粳米-RR品种
0.1.49
增加智道智科-私募指数数据接口
使用方法请 help(get_zdzk_fund_index) 查看
0.1.50
更新 akdocker.md 文件
0.1.51
更新官方文档: https://akshare.akfamily.xyz
0.1.52
增加量化策略和量化平台板块
0.1.53
增加期货品种列表和名词解释
0.1.54
修改 AkShare的初衷, 增加管理期货策略指数
0.1.55
新增 99 期货库存数据接口
0.1.56
修复 99 期货库存数据接口
0.1.57
更新 md 文件数据接口
0.1.58
更新 md 文件数据接口
0.1.59
更新 md 文件数据接口
0.1.60
更新 致谢部分, 申明借鉴和引用的 package
0.1.61
更新说明文档
0.1.62
提供英为财情-股票指数-全球股指与期货指数数据接口
https://cn.investing.com/indices/
0.1.63
更新说明文档-致谢英为财情
0.1.64
更新 get_country_index 返回格式为日期索引
0.1.65
更新 get_country_index 返回格式数据开盘, 收盘, 高, 低为浮点型
0.1.66
提供英为财情-股票指数-全球股指与期货指数数据接口
https://cn.investing.com/rates-bonds/
新增 get_country_bond 返回格式数据开盘, 收盘, 高, 低为浮点型
0.1.67
更新说明文档-私募指数数据说明
0.1.68
更新说明文档-私募指数数据说明-增加图片
0.1.69
更新说明文档-债券说明格式调整
0.1.70
更新大商所, 郑商所商品期权数据接口
0.1.71
更新大商所, 郑商所, 上期所商品期权数据接口
0.1.72
修改大商所, 郑商所, 上期所商品期权数据接口
增加函数说明
更新说明文档-期权部分
0.1.73
更新说明文档-期权部分
0.1.74
更新说明文档格式调整
0.1.75
新增外汇接口, 银行间债券市场行情数据接口
0.1.76
更新说明文档
0.1.77
新增全球期货历史数据查询接口
0.1.78
新增全球宏观数据-中国宏观数据
年度、月度CPI数据, 年度M2数据
0.1.79
更新说明文档
0.1.80
更新说明文档-刷新
0.1.81
新增全球宏观数据-中国宏观数据
中国年度PPI数据
中国年度PMI数据
中国年度GDP数据
中国年度财新PMI数据
中国外汇储备数据
中国电力能源数据
中国年度非制造业PMI数据
人民币中间报价汇率
0.1.82
新增全球宏观数据-美国宏观数据
美联储利率决议报告
美国非农就业人数报告
美国失业率报告
美国EIA原油库存报告
0.1.83
更新说明文档
0.1.84
新增全球宏观数据-美国宏观数据
美国初请失业金人数报告
美国核心PCE物价指数年率报告
美国CPI月率报告
美联储劳动力市场状况指数报告
美国ADP就业人数报告
美国国内生产总值(GDP)报告
美国原油产量报告
新增全球宏观数据-欧洲宏观数据
欧洲央行决议报告
新增全球宏观数据-机构宏观数据
全球最大黄金ETF—SPDR Gold Trust持仓报告
全球最大白银ETF--iShares Silver Trust持仓报告
欧佩克报告
0.1.85
新增期货-仓单有效期接口
0.1.86
更新说明文档
0.1.87
新增和讯财经-企业社会责任数据接口
0.1.88
更新说明文档
0.1.89
更新requirements.txt
0.1.90
更新setup.py
0.1.91
新增和讯财经-中国概念股行情及日频历史数据接口
0.1.92
更新说明文档
0.1.93
新增交易法门-套利工具-跨期价差(自由价差)数据接口
0.1.94
新增生意社-商品与期货-现期图数据接口
新增西本新干线-指数数据
0.1.95
新增新浪财经-期货-实时数据接口
0.1.96
修正新浪财经-期货-实时数据接口-返回 current_price 字段为实时数据
0.1.97
修正新浪财经-期货-实时数据接口-返回 current_price 和 ask_price 字段为实时数据
0.1.98
修正版本更新错误
0.1.99
增加自动安装 pillow
0.2.1
增加港股当日(时点)行情数据和历史数据(前复权和后复权因子)
0.2.2
增加美股当日(时点)行情数据和历史数据(前复权因子)
0.2.3
增加金融期权
0.2.4
增加加密货币行情接口
0.2.5
增加 AKShare 接口导图
0.2.6
更新港股数据接口和说明文档
0.2.7
更新 qhkc_web 接口注释和说明文档
0.2.8
更新说明文档
0.2.9
更新A+H股数据实时行情数据和历史行情数据(后复权)
0.2.10
更新说明文档
0.2.11
更新说明文档
0.2.12
增加A股实时行情数据和历史行情数据
0.2.13
统一股票接口命名
0.2.14
统一股票接口命名, 去除 get
0.2.15
增加科创板实时行情数据和历史行情数据
0.2.16
增加银保监分局本级行政处罚数据
0.2.17
更新说明文档
0.2.18
修正银保监分局本级行政处罚数据接口字段命名
0.2.19
增加 Nodejs 安装说明
0.2.20
增加 Realized Library 接口
0.2.21
更新说明文档
0.2.22
更新说明文档
0.2.23
修正银保监分局本级行政处罚数据接口反扒升级-修改完成
0.2.24
增加FF多因子模型数据接口
0.2.25
更新说明文档
0.2.26
修正期货-实时行情: 接口命名, 字段补充及限制访问速度
0.2.27
增加新浪-外盘期货实时行情数据接口
0.2.28
修正新浪-外盘期货实时行情数据引入
更新文档
0.2.29
更新文档
0.2.30
监管-银保监: 反扒措施在变化, 更新接口
修正期货-国内-实时行情接口订阅问题
0.2.31
修正期货-国内-金融期货实时行情接口订阅问题
0.2.32
更新说明文档
0.2.33
更新说明文档-期货-外盘
0.2.34
新增新浪-指数实时行情和历史行情接口
0.2.35
新增新浪-指数和A股实时行情列表获取问题
0.2.36
新增腾讯财经-A股分笔行情历史数据
0.2.37
新增金十数据-实时监控接口
0.2.38
更新说明文档
0.2.39
更新说明文档目录结构
0.2.40
更新专题板块
0.2.41
更新说明文件
0.2.42
更新 MindMap
0.2.43
重构说明文档-模块化处理, 将 github 说明文档和 docs 在线文档分开处理
重构私募指数接口
0.2.44
增加日出和日落模块
0.2.45
增加河北空气指数数据
0.2.46
更新 requirements.txt
0.2.47
添加初始化文件
0.2.48
添加 websocket-client
0.2.49
南华期货-南华商品指数
0.2.50
修正英为财情-指数板块的成交量显示问题
0.2.51
消除部分警告信息
0.2.52
基差数据缺失错误提示修正
0.2.53
统一南华期货-商品指数历史走势-收益率指数
新增南华期货-商品指数历史走势-价格指数
新增南华期货-商品指数历史走势-波动率指数
0.2.54
添加 numpy 依赖
0.2.55
更新已实现波动率的说明文档
统一 ff_crr --> article_ff_crr
0.2.56
新增经济政策不确定性(EPU)数据接口
更新说明文档
修改示例说明
0.2.57
修改 air_hebei 接口, 默认返回全部城市
0.2.58
新增微博指数
0.2.59
增加西本新干线说明文档
0.2.60
新增百度指数
0.2.61
修正河北空气数据代码
0.2.62
新增百度搜索指数
新增百度资讯指数
新增百度媒体指数
0.2.63
更新指数-legend代码
0.2.64
fix pillow>=6.2.0
0.2.65
新增谷歌指数
0.2.66
修正南华指数URL硬编码问题
0.2.67
修正 get_futures_index 函数中上海期货交易所
CU 出现 cuefp 数据导致指数合成异常的问题
0.2.68
降低 Python 版本要求
0.2.69
降低python版本要求到 Python3.7.1
0.2.70
适配 VNPY 使用
0.2.71
交易法门数据接口
0.2.72
申万行业一级指数-实时
0.2.73
更新纯碱期货数据接口
0.2.74
新增AQI空气质量数据接口
0.2.75
新增申万一级指数接口
0.2.76
统一交易法门登录和数据获取接口
0.2.77
清除冗余函数
0.2.78
Python 降级
0.2.79
Python 降级
0.2.80
Python 3.6
0.2.81
html5lib
0.2.82
websockets-8.1
0.2.83
修复 weibo_index 函数日期格式问题
0.2.84
修复 baidu_index 接口
0.2.85
临时修复 baidu_index 接口
0.2.86
lxml 降级
0.2.87
lxml 降级
更新安装时的错误处理
0.2.88
pypinyin 降级
0.2.89
全国空气质量数据数据格式规范为数值型
0.2.90
更新注册仓单的产品参数和异常错误
0.2.91
世界五百强公司排名接口
0.2.92
更新中国债券市场行情数据接口
0.2.93
增加自动测试模型
0.2.94
增加私募基金管理人信息公示接口
0.2.95
增加中国证券投资基金业协会-信息公示
0.2.96
修复交易法门登录验证码
由于交易法门-数据部分权限缘故, 需要注册后方可使用
0.2.97
更新说明文档
0.2.98
增加甲醇期权和PTA期权
0.2.99
更新外汇数据接口, 规范格式
0.3.0
猫眼电影实时票房
0.3.1
更新说明文档
0.3.2
更新说明文档
0.3.3
更新外盘期货行情订阅时, 统一字段名称与网页端一致
0.3.4
新增能源-碳排放权数据
0.3.5
新增世界各大城市生活成本数据
0.3.6
商品现货价格指数
0.3.7
修复百度指数日期问题
0.3.8
新增中国宏观数据接口和文档说明
0.3.9
新增中国宏观杠杆率数据
0.3.10
修改金融期权数据接口
0.3.11
修复实时票房数据接口
0.3.12
新增新浪主力连续接口
0.3.13
新增新浪主力连续列表
0.3.14
中国倒闭公司名单
0.3.15
中国独角兽名单
中国千里马名单
0.3.16
东方财富-机构调研
0.3.17
东方财富网-数据中心-特色数据-机构调研
机构调研统计
机构调研详细
0.3.18
修复自动测试接口
0.3.19
修复融资融券字段名匹配问题
增加东方财富网-数据中心-特色数据-股票质押
0.3.20
东方财富网-数据中心-特色数据-股权质押
东方财富网-数据中心-特色数据-股权质押-股权质押市场概况: https://data.eastmoney.com/gpzy/marketProfile.aspx
东方财富网-数据中心-特色数据-股权质押-上市公司质押比例: https://data.eastmoney.com/gpzy/pledgeRatio.aspx
东方财富网-数据中心-特色数据-股权质押-重要股东股权质押明细: https://data.eastmoney.com/gpzy/pledgeDetail.aspx
东方财富网-数据中心-特色数据-股权质押-质押机构分布统计-证券公司: https://data.eastmoney.com/gpzy/distributeStatistics.aspx
东方财富网-数据中心-特色数据-股权质押-质押机构分布统计-银行: https://data.eastmoney.com/gpzy/distributeStatistics.aspx
东方财富网-数据中心-特色数据-股权质押-行业数据: https://data.eastmoney.com/gpzy/industryData.aspx
0.3.21
东方财富网-数据中心-特色数据-商誉
东方财富网-数据中心-特色数据-商誉-A股商誉市场概况: https://data.eastmoney.com/sy/scgk.html
东方财富网-数据中心-特色数据-商誉-商誉减值预期明细: https://data.eastmoney.com/sy/yqlist.html
东方财富网-数据中心-特色数据-商誉-个股商誉减值明细: https://data.eastmoney.com/sy/jzlist.html
东方财富网-数据中心-特色数据-商誉-个股商誉明细: https://data.eastmoney.com/sy/list.html
东方财富网-数据中心-特色数据-商誉-行业商誉: https://data.eastmoney.com/sy/hylist.html
0.3.22
期货规则-交易日历数据表
更新2020交易日历数据
0.3.23
东方财富网-数据中心-特色数据-股票账户统计: https://data.eastmoney.com/cjsj/gpkhsj.html
0.3.24
移除-交易法门系列老函数
因为交易法门网站需要会员登录后访问数据
0.3.25
增加-交易法门-工具-套利分析接口
增加-交易法门-工具-交易规则接口
0.3.26
增加-交易法门-数据-农产品-豆油
增加-交易法门-数据-黑色系-焦煤
增加-交易法门-工具-持仓分析-期货分析
增加-交易法门-工具-持仓分析-持仓分析
0.3.27
交易法门-说明文档
0.3.28
增加-股票指数-股票指数成份股接口
0.3.29
增加-股票指数-股票指数成份股接口-代码注释
0.3.30
增加-义乌小商品指数
0.3.31
修复-银保监分局本级行政处罚数据接口
接口重命名为: bank_fjcf_table_detail
0.3.32
新增-中国电煤价格指数
0.3.33
修复-银保监分局本级行政处罚数据接口-20200108新增字段后适应
0.3.34
增加-交易法门-工具-期限分析-基差日报
增加-交易法门-工具-期限分析-基差分析
增加-交易法门-工具-期限分析-期限结构
增加-交易法门-工具-期限分析-价格季节性
0.3.35
更新说明文档
0.3.36
# 交易法门-工具-仓单分析
增加-交易法门-工具-仓单分析-仓单日报
增加-交易法门-工具-仓单分析-仓单查询
增加-交易法门-工具-仓单分析-虚实盘比查询
# 交易法门-工具-资讯汇总
增加-交易法门-工具-资讯汇总-研报查询
增加-交易法门-工具-资讯汇总-交易日历
# 交易法门-工具-资金分析
增加-交易法门-工具-资金分析-资金流向
0.3.37
更新说明文档
0.3.38
修改-交易法门-工具-资金分析-资金流向函数的字段和说明文档
0.3.39
金十数据中心-经济指标-央行利率-主要央行利率
美联储利率决议报告
欧洲央行决议报告
新西兰联储决议报告
中国央行决议报告
瑞士央行决议报告
英国央行决议报告
澳洲联储决议报告
日本央行决议报告
俄罗斯央行决议报告
印度央行决议报告
巴西央行决议报告
macro_euro_gdp_yoy #  金十数据中心-经济指标-欧元区-国民经济运行状况-经济状况-欧元区季度GDP年率报告
macro_euro_cpi_mom #  金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI月率报告
macro_euro_cpi_yoy #  金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区CPI年率报告
macro_euro_ppi_mom #  金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区PPI月率报告
macro_euro_retail_sales_mom #  金十数据中心-经济指标-欧元区-国民经济运行状况-物价水平-欧元区零售销售月率报告
macro_euro_employment_change_qoq #  金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区季调后就业人数季率报告
macro_euro_unemployment_rate_mom #  金十数据中心-经济指标-欧元区-国民经济运行状况-劳动力市场-欧元区失业率报告
macro_euro_trade_balance #  金十数据中心-经济指标-欧元区-贸易状况-欧元区未季调贸易帐报告
macro_euro_current_account_mom #  金十数据中心-经济指标-欧元区-贸易状况-欧元区经常帐报告
macro_euro_industrial_production_mom #  金十数据中心-经济指标-欧元区-产业指标-欧元区工业产出月率报告
macro_euro_manufacturing_pmi #  金十数据中心-经济指标-欧元区-产业指标-欧元区制造业PMI初值报告
macro_euro_services_pmi #  金十数据中心-经济指标-欧元区-产业指标-欧元区服务业PMI终值报告
macro_euro_zew_economic_sentiment #  金十数据中心-经济指标-欧元区-领先指标-欧元区ZEW经济景气指数报告
macro_euro_sentix_investor_confidence #  金十数据中心-经济指标-欧元区-领先指标-欧元区Sentix投资者信心指数报告
0.3.40
修复-欧洲央行决议报告
0.3.41
增加-东方财富网-经济数据-银行间拆借利率
0.3.42
# 中国
macro_china_gdp_yearly  # 金十数据中心-经济指标-中国-国民经济运行状况-经济状况-中国GDP年率报告
macro_china_cpi_yearly  # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI年率报告
macro_china_cpi_monthly  # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国CPI月率报告
macro_china_ppi_yearly  # 金十数据中心-经济指标-中国-国民经济运行状况-物价水平-中国PPI年率报告
macro_china_exports_yoy  # 金十数据中心-经济指标-中国-贸易状况-以美元计算出口年率报告
macro_china_imports_yoy  # 金十数据中心-经济指标-中国-贸易状况-以美元计算进口年率
macro_china_trade_balance  # 金十数据中心-经济指标-中国-贸易状况-以美元计算贸易帐(亿美元)
macro_china_industrial_production_yoy  # 金十数据中心-经济指标-中国-产业指标-规模以上工业增加值年率
macro_china_pmi_yearly  # 金十数据中心-经济指标-中国-产业指标-官方制造业PMI
macro_china_cx_pmi_yearly  # 金十数据中心-经济指标-中国-产业指标-财新制造业PMI终值
macro_china_cx_services_pmi_yearly  # 金十数据中心-经济指标-中国-产业指标-财新服务业PMI
macro_china_non_man_pmi  # 金十数据中心-经济指标-中国-产业指标-中国官方非制造业PMI
macro_china_fx_reserves_yearly  # 金十数据中心-经济指标-中国-金融指标-外汇储备(亿美元)
macro_china_m2_yearly  # 金十数据中心-经济指标-中国-金融指标-M2货币供应年率
macro_china_shibor_all  # 金十数据中心-经济指标-中国-金融指标-上海银行业同业拆借报告
macro_china_hk_market_info  # 金十数据中心-经济指标-中国-金融指标-人民币香港银行同业拆息
macro_china_daily_energy  # 金十数据中心-经济指标-中国-其他-中国日度沿海六大电库存数据
macro_china_rmb  # 金十数据中心-经济指标-中国-其他-中国人民币汇率中间价报告
macro_china_market_margin_sz  # 金十数据中心-经济指标-中国-其他-深圳融资融券报告
macro_china_market_margin_sh  # 金十数据中心-经济指标-中国-其他-上海融资融券报告
macro_china_au_report  # 金十数据中心-经济指标-中国-其他-上海黄金交易所报告
macro_china_ctci  # 发改委-中国电煤价格指数-全国综合电煤价格指数
macro_china_ctci_detail  # 发改委-中国电煤价格指数-各价区电煤价格指数
macro_china_ctci_detail_hist  # 发改委-中国电煤价格指数-历史电煤价格指数
macro_china_money_supply  # 中国货币供应量
# 美国
macro_usa_gdp_monthly  # 金十数据中心-经济指标-美国-经济状况-美国GDP
macro_usa_cpi_monthly  # 金十数据中心-经济指标-美国-物价水平-美国CPI月率报告
macro_usa_core_cpi_monthly  # 金十数据中心-经济指标-美国-物价水平-美国核心CPI月率报告
macro_usa_personal_spending  # 金十数据中心-经济指标-美国-物价水平-美国个人支出月率报告
macro_usa_retail_sales  # 金十数据中心-经济指标-美国-物价水平-美国零售销售月率报告
macro_usa_import_price  # 金十数据中心-经济指标-美国-物价水平-美国进口物价指数报告
macro_usa_export_price  # 金十数据中心-经济指标-美国-物价水平-美国出口价格指数报告
macro_usa_lmci  # 金十数据中心-经济指标-美国-劳动力市场-LMCI
macro_usa_unemployment_rate  # 金十数据中心-经济指标-美国-劳动力市场-失业率-美国失业率报告
macro_usa_job_cuts  # 金十数据中心-经济指标-美国-劳动力市场-失业率-美国挑战者企业裁员人数报告
macro_usa_non_farm  # 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国非农就业人数报告
macro_usa_adp_employment  # 金十数据中心-经济指标-美国-劳动力市场-就业人口-美国ADP就业人数报告
macro_usa_core_pce_price  # 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国核心PCE物价指数年率报告
macro_usa_real_consumer_spending  # 金十数据中心-经济指标-美国-劳动力市场-消费者收入与支出-美国实际个人消费支出季率初值报告
macro_usa_trade_balance  # 金十数据中心-经济指标-美国-贸易状况-美国贸易帐报告
macro_usa_current_account  # 金十数据中心-经济指标-美国-贸易状况-美国经常帐报告
macro_usa_rig_count  # 金十数据中心-经济指标-美国-产业指标-制造业-贝克休斯钻井报告
# 金十数据中心-经济指标-美国-产业指标-制造业-美国个人支出月率报告
macro_usa_ppi  # 金十数据中心-经济指标-美国-产业指标-制造业-美国生产者物价指数(PPI)报告
macro_usa_core_ppi  # 金十数据中心-经济指标-美国-产业指标-制造业-美国核心生产者物价指数(PPI)报告
macro_usa_api_crude_stock  # 金十数据中心-经济指标-美国-产业指标-制造业-美国API原油库存报告
macro_usa_pmi  # 金十数据中心-经济指标-美国-产业指标-制造业-美国Markit制造业PMI初值报告
macro_usa_ism_pmi  # 金十数据中心-经济指标-美国-产业指标-制造业-美国ISM制造业PMI报告
macro_usa_nahb_house_market_index  # 金十数据中心-经济指标-美国-产业指标-房地产-美国NAHB房产市场指数报告
macro_usa_house_starts  # 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋开工总数年化报告
macro_usa_new_home_sales  # 金十数据中心-经济指标-美国-产业指标-房地产-美国新屋销售总数年化报告
macro_usa_building_permits  # 金十数据中心-经济指标-美国-产业指标-房地产-美国营建许可总数报告
macro_usa_exist_home_sales  # 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋销售总数年化报告
macro_usa_house_price_index  # 金十数据中心-经济指标-美国-产业指标-房地产-美国FHFA房价指数月率报告
macro_usa_spcs20 # 金十数据中心-经济指标-美国-产业指标-房地产-美国S&P/CS20座大城市房价指数年率报告
macro_usa_pending_home_sales  # 金十数据中心-经济指标-美国-产业指标-房地产-美国成屋签约销售指数月率报告
macro_usa_cb_consumer_confidence  # 金十数据中心-经济指标-美国-领先指标-美国谘商会消费者信心指数报告
macro_usa_nfib_small_business # 金十数据中心-经济指标-美国-领先指标-美国NFIB小型企业信心指数报告
macro_usa_michigan_consumer_sentiment # 金十数据中心-经济指标-美国-领先指标-美国密歇根大学消费者信心指数初值报告
macro_usa_eia_crude_rate  # 金十数据中心-经济指标-美国-其他-美国EIA原油库存报告
macro_usa_initial_jobless  # 金十数据中心-经济指标-美国-其他-美国初请失业金人数报告
macro_usa_crude_inner  # 金十数据中心-经济指标-美国-其他-美国原油产量报告
0.3.43
增加-交易法门-数据-黑色系-焦煤
0.3.44
更新宏观数据
macro_cons_gold_volume  # 全球最大黄金ETF—SPDR Gold Trust持仓报告
macro_cons_gold_change  # 全球最大黄金ETF—SPDR Gold Trust持仓报告
macro_cons_gold_amount  # 全球最大黄金ETF—SPDR Gold Trust持仓报告
macro_cons_silver_volume  # 全球最大白银ETF--iShares Silver Trust持仓报告
macro_cons_silver_change  # 全球最大白银ETF--iShares Silver Trust持仓报告
macro_cons_silver_amount  # 全球最大白银ETF--iShares Silver Trust持仓报告
macro_cons_opec_month  # 欧佩克报告-月度
0.3.45
增加中国证券投资基金业协会-信息公示
# 中国证券投资基金业协会-信息公示-会员信息
amac_member_info # 中国证券投资基金业协会-信息公示-会员信息-会员机构综合查询
# 中国证券投资基金业协会-信息公示-从业人员信息
amac_person_org_list # 中国证券投资基金业协会-信息公示-从业人员信息-基金从业人员资格注册信息
# 中国证券投资基金业协会-信息公示-私募基金管理人公示
amac_manager_info # 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人综合查询
amac_manager_classify_info # 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人分类公示
amac_member_sub_info # 中国证券投资基金业协会-信息公示-私募基金管理人公示-证券公司私募基金子公司管理人信息公示
# 中国证券投资基金业协会-信息公示-基金产品
amac_fund_info # 中国证券投资基金业协会-信息公示-基金产品-私募基金管理人基金产品
amac_securities_info # 中国证券投资基金业协会-信息公示-基金产品-证券公司集合资管产品公示
amac_aoin_info # 中国证券投资基金业协会-信息公示-基金产品-证券公司直投基金
amac_fund_sub_info # 中国证券投资基金业协会-信息公示-基金产品公示-证券公司私募投资基金
amac_fund_account_info # 中国证券投资基金业协会-信息公示-基金产品公示-基金公司及子公司集合资管产品公示
amac_fund_abs # 中国证券投资基金业协会-信息公示-基金产品公示-资产支持专项计划
amac_futures_info # 中国证券投资基金业协会-信息公示-基金产品公示-期货公司集合资管产品公示
# 中国证券投资基金业协会-信息公示-诚信信息
amac_manager_cancelled_info # 中国证券投资基金业协会-信息公示-诚信信息-已注销私募基金管理人名单
0.3.46
更新-商品期权-菜籽粕期权接口
修复 get_sector_futures 字段名问题
0.3.47
增加-商品期权-郑州商品交易所-期权-历史数据
0.3.48
修复 macro_cons_opec_month 接口数据更新问题
0.3.49
新增-交易法门-工具-仓单分析-虚实盘比日报接口
0.3.50
更新-说明文档
0.3.51
修复 macro_cons_opec_month 接口数据更新问题, 统一数据接口跟网页端统一
修复-百度指数-由用户输入cookie来访问数据及说明文档
0.3.52
新增-英为财情-外汇-货币对历史数据
0.3.53
修复-macro_usa_rig_count-接口返回数据
修复-rate_interbank-文档注释
0.3.54
新增-事件接口
新增-事件接口新型冠状病毒-网易
新增-事件接口新型冠状病毒-丁香园
0.3.55
更新-事件接口新型冠状病毒
0.3.56
更新-事件接口新型冠状病毒-全国疫情趋势图
0.3.57
更新-事件接口新型冠状病毒-分省地区
一些细节修复
0.3.58
新增-财富排行榜(英文版)
0.3.59
新增-currency_name_code-接口
0.3.60
修复-财富排行榜(英文版)-索引乱序问题
0.3.61
修复-事件接口新型冠状病毒-hospital-接口
0.3.62
修复-20200203交易日问题
0.3.63
修复-事件接口新型冠状病毒-网易接口
0.3.64
修复-事件接口新型冠状病毒-丁香园接口
0.3.65
修复-calendar.json 问题, 感谢 fxt0706
0.3.66
修复-epu_index-加载问题
0.3.67
修复-option_commodity-json数据加载问题
0.3.68
更名函数 movie_board -> box_office_spot
0.3.69
新增-epidemic_baidu
百度-新型冠状病毒肺炎-疫情实时大数据报告
0.3.70
修复-epidemic_dxy-字段问题
0.3.71
修复-epidemic_dxy-具体省份字段问题
0.3.72
新增-百度迁徙地图接口
0.3.73
修复文字表述
0.3.74
修复-epidemic_163-数据更新问题
0.3.75
修复-epidemic_dxy-图片显示问题
0.3.76
新增-stock_zh_index_daily_tx-补充新浪指数的数据缺失问题
0.3.77
修复-epidemic_163-数据更新问题
0.3.78
新增-bond_china_yield-中国债券信息网-国债及其他债券收益率曲线
0.3.79
修改-bond_china_yield-参数
0.3.80
新增-基金数据接口
0.3.81
新增-基金数据接口-净值
0.3.82
新增-小区查询
新增-相同行程查询
0.3.83
新增-交易法门-工具-套利分析-FullCarry
修改-交易法门-工具-期限分析-基差分析
0.3.84
新增-货币对-投机情绪报告
0.3.85
修复-epidemic_area_detail-增加下载进度提示
0.3.86
修复-epidemic_dxy-完善图片获取
0.3.87
新增-债券质押式回购成交明细数据
新增-细化到地市的疫情历史数据20200123至今
0.3.88
新增-交易法门-工具-持仓分析-持仓季节性
修复-epidemic_163
0.3.89
新增-epidemic_163-数据说明接口
0.3.90
修复-epidemic_dxy
0.3.91
修复-get_receipt-MA数值问题
0.3.92
新增-奇货可查接口测试
0.3.93
新增-奇货可查接口测试-代码补全
0.3.94
修复-epidemic_dxy
0.3.95
新增-债券-沪深债券
新增-债券-沪深可转债
0.3.96
修复-baidu_search_index-异常
0.3.97
新增-特许经营数据
0.3.98
修复-get_receipt-MA数值问题条件判断
0.3.99
修复-air_hebei-代码格式
0.4.1
修复-pandas-版本降级
0.4.2
修复-epidemic_baidu
0.4.3
新增-慈善中国
0.4.4
新增-epidemic_history-疫情所有历史数据
0.4.5
完善-慈善中国-类型注解
0.4.6
修复-charity_china_report
0.4.7
新增-测试接口
0.4.8
修复-epidemic_hist_all
修复-epidemic_hist_city
修复-epidemic_hist_province
0.4.9
新增-option_cffex_hs300_list_sina
新增-option_cffex_hs300_spot_sina
新增-option_cffex_hs300_daily_sina
新增-option_sse_list_sina
新增-option_sse_expire_day_sina
新增-option_sse_codes_sina
新增-option_sse_spot_price_sina
新增-option_sse_underlying_spot_price_sina
新增-option_sse_greeks_sina
新增-option_sse_minute_sina
新增-option_sse_daily_sina
0.4.10
修复-金十数据websocket接口
0.4.11
新增-交易法门-工具-资金分析-资金流向
新增-交易法门-工具-资金分析-沉淀资金
新增-交易法门-工具-资金分析-资金季节性
新增-交易法门-工具-资金分析-成交排名
0.4.12
新增-微博舆情报告
0.4.13
新增-Python3.8.1支持
0.4.14
修复-get_receipt-CZCE问题
0.4.15
修复-hf_subscribe_exchange_symbol-在Linux Python 3.8.1 报错问题
0.4.16
修复-get_js_dc_current
0.4.17
新增-知识图谱
0.4.18: fix: use tqdm replace print hints
0.4.19: fix: use tqdm replace print hints in energy_carbon.py and charity_china.py
0.4.20: add: jyfm_tools_position_structure and jyfm_tools_symbol_handbook
0.4.21: fix: macro_cons_opec_month print hints
0.4.22: fix: add tqdm desc
0.4.23: fix: add tqdm stock_zh_a_spot desc
0.4.24: fix: add get_us_stock_name to get the u.s. stock name
0.4.25: fix: upload setup.py file and set automate release and deploy
0.4.26: fix: bond_spot_quote and docs
0.4.27: test: automate test
0.4.28: test: automate test
0.4.29: feats: add currency interface
0.4.30: fix: futures_roll_yield.py/get_roll_yield: CUefp error
0.4.31: format: format currency.py
0.4.32: fix: bond_china.py
0.4.33: add: jyfm_tools_futures_arbitrage_matrix for jyfm futures
0.4.34: fix: get_czce_rank_table history-20171228 format
0.4.35: fix: get_czce_rank_table history-20071228 format
0.4.36: fix: macro_cons_opec_month
0.4.37: add: get_ine_daily to fetch SC and NR data
0.4.38: add: futures_sgx_daily to fetch futures data from sgx
0.4.39: refactor: migration.py/covid_19_163 interface
0.4.40: refactor: migration.py interface
0.4.41: fix: cot.py get_rank_sum_daily interface
0.4.42: add: wdbank.py test
0.4.43: add: wdbank.py dependencies
0.4.44: add: tool github
0.4.45: add: fund_public file and docs
0.4.46: add: macro_china_lpr
0.4.47: add: stock_em_analyst
0.4.48: add: stock_comment_em
0.4.49: add: stock_em_hsgt
0.4.50: fix: stock_em_sy_yq_list
0.4.51: add: stock_tfp_em
0.4.52: fix: migration.py
0.4.53: fix: futures_hq_sina.py
0.4.54: add: futures_foreign
0.4.55: fix: macro_constitute.py
0.4.56: add: index_vix
0.4.57: fix: covid-19; desc: delete pic show
0.4.58: add: qhkc api
0.4.59: add: jyfm_tools
0.4.60: fix: covid_19_dxy and cot.py
0.4.61: fix: cot.py dict keys use strip
0.4.62: fix: add PG into cons.py map_dict
0.4.63: add: energy_oil to add energy_oil_hist and energy_oil_detail
0.4.64: add: futures_em_spot_stock
0.4.65: add: futures_global_commodity_name_url_map
0.4.66: fix: fund_em.py timezone transfer
0.4.67: fix: covid covid_19_area_detail
0.4.68: fix: marco_usa
0.4.69: add: futures_cfmmc
0.4.70: add: covid_19 CSSE 数据接口
0.4.71: add: argus
0.4.72: add: stock_zh_tick_163
0.4.73: add: stock_zh_tick_tx_js
0.4.74: fix: stock_zh_tick_163 return tips
0.4.75: fix: nh_index
0.4.76: add: fred_md
0.4.77: fix: get_dce_option_daily
0.4.78: add: internal_flow_history
0.4.79: add: stock_dxsyl_em
0.4.80: fix: covid and docs
0.4.81: add: stock_yjyg_em and stock_yysj_em
0.4.82: fix: futures_xgx_index
0.4.83: fix: fortune_500.py
0.4.84: fix: a and kcb stock return format
0.4.85: fix: a and kcb stock field
0.4.86: add: hf_sp_500
0.4.87: fix: jinshi data update
0.4.88: fix: macro_china
0.4.89: fix: macro_other
0.4.90: fix: stock_zh_a and stock_zh_kcb return adjusted stock price
0.4.91: add: futures_inventory_em
0.4.92: fix: adjust hk_stock_sina, us_stock_sina
0.4.93: fix: air_quality
0.4.94: fix: air_quality path
0.4.95: add: js file
0.4.96: fix: format air interface
0.4.97: fix: interbank_rate_em.py add need_page parameter to control update content
0.4.98: add: mplfinance package
0.4.99: add: fund_em
0.5.1: fix: add PG to futures list
0.5.2: fix: air_zhenqi.py rename air_city_dict to air_city_table
0.5.3: add: add two fields into covid_163
0.5.4: fix: fix request_fun timeout and error type
0.5.5: fix: fund_graded_fund_daily_em return fields
0.5.6: fix: stock_us_sina.py rename columns
0.5.7: fix: import akshare only load functions
0.5.8: add: macro_china_money_supply
0.5.9: add: macro_china_new_house_price, macro_china_enterprise_boom_index, macro_china_national_tax_receipts
0.5.10: fix: zh_stock_ah_tx
0.5.11: fix: fund_em return fields
0.5.12: fix: add date to fund_em daily function
0.5.13: add: stock_fund
0.5.14: add: stock_market_fund_flow, stock_sector_fund_flow, stock_individual_fund_flow_rank
0.5.15: fix: baidu_index
0.5.16: add: fund_value_estimation_em
0.5.17: fix: delete macro_euro zero value
0.5.18: add: stock_financial_abstract, stock_financial_analysis_indicator
0.5.19: add: stock_add_stock, stock_ipo_info, stock_history_dividend_detail, stock_history_dividend
0.5.20: add: stock_restricted_shares, stock_circulate_stock_holder
0.5.21: add: futures_dce_position_rank
0.5.22: fix: fix futures_dce_position_rank return format
0.5.23: add: stock_sector_spot, stock_sector_detail
0.5.24: fix: futures_dce_position_rank
0.5.25: fix: futures_dce_position_rank return fields
0.5.26: add: stock_info
0.5.27: add: stock_hsgt_hold_stock_em
0.5.28: add: stock_fund_stock_holder, stock_main_stock_holder
0.5.29: fix: stock_em_sy
0.5.30: fix: air_zhenqi.py
0.5.31: fix: add futures_dce_position_rank_other to fix futures_dce_position_rank at 20160104
0.5.32: fix: futures_dce_position_rank_other return format
0.5.33: add: zh_bond_cov_sina and set pandas version
0.5.34: fix: set pandas version > 0.25
0.5.35: add: bond_cov_comparison and bond_zh_cov
0.5.36: fix: stock_info_sz_name_code return code format
0.5.37: add: stock_hold
0.5.38: fix: futures_dce_position_rank_other exchange symbol and variety
0.5.39: add: stock_recommend
0.5.40: fix: stock_recommend output format
0.5.41: fix: deprecated requests-html module
0.5.42: fix: reformat investing interface
0.5.43: fix: qhck interface
0.5.44: add: LME holding and stock report
0.5.45: fix: transform the data type of stock_zh_a_spot output
0.5.46: add: CFTC holding and stock
0.5.47: fix: fix index_investing_global interface
0.5.48: fix: fix stock_info_a_code_name interface
0.5.49: fix: fix stock_zh_a_daily interface
0.5.50: fix: fix get_roll_yield_bar interface
0.5.51: add: stock_summary
0.5.52: fix: fix get_roll_yield_bar interface
0.5.53: add: add watch_jinshi_quotes interface
0.5.54: add: add stock_price_js interface
0.5.55: add: add futures_czce_warehouse_receipt interface
0.5.56: add: add futures_dce_warehouse_receipt, futures_shfe_warehouse_receipt interface
0.5.57: fix: fix macro data interface
0.5.58: add: add stock_qsjy_em interface
0.5.59: fix: fix fund interface
0.5.60: fix: add index_bloomberg_billionaires interface
0.5.61: fix: fix futures_rule interface
0.5.62: add: add stock_a_pe, stock_a_pb interface
0.5.63: add: add stock_a_lg_indicator interface
0.5.64: add: add stock_a_high_low_statistics interface
0.5.65: add: add stock_a_below_net_asset_statistics interface
0.5.66: fix: fix stock_zh_a_daily default return unadjusted data
0.5.67: fix: fix R and MATLAB compatibility issues
0.5.68: add: add option_commodity_sina interface
0.5.69: fix: fix option_commodity_sina interface
0.5.70: merge: merge #4048
0.5.71: add: add tool_trade_date_hist interface
0.5.72: add: add fund_etf_category_sina, fund_etf_hist_sina interface
0.5.73: add: add stock_report_disclosure interface
0.5.74: add: add stock_zh_a_minute interface
0.5.75: add: add futures_zh_minute_sina interface
0.5.76: add: add option_finance_minute_sina interface
0.5.77: fix: fix currency_hist interface return data format
0.5.78: add: add hold field in futures_zh_minute_sina interface
0.5.79: add: add stock_report_fund_hold interface
0.5.80: fix: fix PG to futures cons file
0.5.81: add: add stock_zh_index_hist_csindex interface
0.5.82: fix: fix LU to futures cons file
0.5.83: fix: fix qhkc broker_positions_process interface
0.5.84: fix: fix tool_trade_date_hist_sina interface and update calendar.json
0.5.85: add: add index_stock_hist interface
0.5.86: fix: fix code format
0.5.87: fix: fix cot interface
0.5.88: fix: fix stock_account_statistics_em interface
0.5.89: add: add macro_china_new_financial_credit interface
0.5.90: add: add stock_sina_lhb interface
0.5.91: fix: fix covid for python3.8
0.5.92: fix: fix futures_daily_bar interface
0.5.93: add: add macro_china_fx_gold interface
0.5.94: add: add stock_zh_index_daily_em, bond_cb_jsl interface
0.5.95: fix: fix get_dce_option_daily interface
0.5.96: add: add stock_hsgt_hist_em interface
0.5.97: fix: fix remove mplfinance package in requirements.txt
0.5.98: add: add stock_hk_eniu_indicator interface
0.5.99: fix: fix stock_zh_ah_daily interface
0.6.1: fix: fix stock_zh_ah_daily interface set default value
0.6.2: fix: fix stock_zh_a_minute interface and add adjust parameter
0.6.3: fix: fix stock_zh_a_minute interface
0.6.4: add: add macro_china interface
0.6.5: add: add macro_china_wbck interface
0.6.6: fix: fix macro_china_wbck interface
0.6.7: add: add index_stock_cons_sina interface
0.6.8: fix: fix option_commodity interface
0.6.9: fix: fix stock_gpzy_pledge_ratio_em interface
0.6.10: add: add macro_china_hb, macro_china_gksccz, macro_china_bond_public interface
0.6.11: fix: fix python version should be 3.7 later
0.6.12: fix: fix stock_gpzy_distribute_statistics_company_em interface
0.6.13: add: add stock_us_fundamental interface
0.6.14: fix: fix stock_us_fundamental interface
0.6.15: fix: fix macro_china_market_margin_sh interface
0.6.16: fix: fix stock_us_daily time period and adjust for specific stock
0.6.17: fix: fix stock_js_weibo_report interface
0.6.18: fix: fix get_shfe_option_daily interface column name
0.6.19: fix: fix stock_hk_daily interface to process non-dividend stock
0.6.20: fix: fix covid_baidu interface
0.6.21: fix: fix futures_hf_spot interface
0.6.22: fix: fix stock_zh_index_daily_tx interface
0.6.23: fix: fix currency_hist interface
0.6.24: fix: fix stock_zh_kcb_spot interface
0.6.25: add: add stock_register_kcb interface
0.6.26: add: add stock_em_sy_list interface
0.6.27: fix: fix stock_sector_detail interface
0.6.28: add: add stock_register_cyb interface
0.6.29: fix: fix stock_zh_a_daily interface
0.6.30: add: add energy interface
0.6.31: fix: fix energy interface
0.6.32: fix: fix docs interface
0.6.33: fix: fix get_roll_yield_bar interface
0.6.34: fix: fix currency_investing and futures_inventory_em interface and add index_stock_cons_csindex interface
0.6.35: fix: fix get_futures_daily interface
0.6.36: fix: fix stock_info_a_code_name interface
0.6.37: fix: fix stock_sector_detail interface
0.6.38: fix: fix get_futures_daily interface
0.6.39: add: add stock_xgsglb_em interface
0.6.40: add: add stock_zh_a_new interface
0.6.41: fix: fix get_ine_daily interface
0.6.42: add: add bond_futures_deliverable_coupons interface
0.6.43: fix: fix bond_futures_deliverable_coupons interface
0.6.44: add: add futures_comex_inventory interface
0.6.45: add: add macro_china_xfzxx interface
0.6.46: add: add macro_china_reserve_requirement_ratio interface
0.6.47: fix: fix franchise_china interface
0.6.48: fix: fix get_rank_sum interface
0.6.49: fix: fix get_dce_rank_table interface
0.6.50: add: add macro_china_hgjck, macro_china_consumer_goods_retail interface
0.6.51: fix: fix macro_china_hgjck interface
0.6.52: add: add macro_china_society_electricity interface
0.6.53: add: add macro_china_society_traffic_volume interface
0.6.54: add: add macro_china_postal_telecommunicational interface
0.6.55: add: add macro_china_international_tourism_fx interface
0.6.56: add: add macro_china_swap_rate interface
0.6.57: fix: fix stock_sina_lhb_detail_daily interface
0.6.58: add: add bond_china_close_return interface
0.6.59: add: add macro_china_passenger_load_factor interface
0.6.60: fix: fix stock_sina_lhb_ggtj interface
0.6.61: fix: fix option_czce_hist interface
0.6.62: fix: fix sunrise_daily interface
0.6.63: fix: fix get_roll_yield_bar interface
0.6.64: add: add macro_china_insurance interface
0.6.65: add: add macro_china_supply_of_money interface
0.6.66: add: add support for python 3.9.0
0.6.67: add: add macro_china_foreign_exchange_gold interface
0.6.68: add: add macro_china_retail_price_index interface
0.6.69: fix: fix box_office_spot interface
0.6.70: fix: fix bond_investing_global interface
0.6.71: fix: fix futures_return_index_nh interface
0.6.72: fix: fix get_receipt interface
0.6.73: add: add news_cctv interface
0.6.74: fix: fix macro and acm interface
0.6.75: add: add movie_boxoffice interface
0.6.76: fix: fix remove execjs dependence
0.6.77: add: add macro_china_real_estate interface
0.6.78: fix: fix movie_boxoffice interface
0.6.79: fix: split movie_boxoffice to single interface
0.6.80: fix: movie_boxoffice interface
0.6.81: fix: fix stock_report_fund_hold interface
0.6.82: fix: fix stock_comment_em interface
0.6.83: add: add crypto_hist and crypto_name_url_table interface
0.6.84: fix: fix crypto_hist interface
0.6.85: fix: fix stock_a_pb and stock_a_pe interface
0.6.86: fix: fix stock_zh_a_minute interface
0.6.87: fix: remove email interface
0.6.88: fix: fix get_dce_rank_table interface
0.6.89: fix: fix get_dce_rank_table interface
0.6.90: add: add fund_em_rank interface
0.6.91: fix: fix get_futures_daily interface
0.6.92: add: add repo_rate_hist interface
0.6.93: fix: fix stock_report_fund_hold interface
0.6.94: fix: fix docs interface
0.6.95: fix: fix macro_china_market_margin_sh interface
0.6.96: fix: fix stock_zh_a_daily interface
0.6.97: add: add stock_hsgt_board_rank_em interface
0.6.98: fix: fix fortune_rank interface
0.6.99: add: add forbes_rank interface
0.7.1: fix: fix futures_dce_position_rank interface
0.7.2: add: add xincaifu_rank interface
0.7.3: add: add hurun_rank interface
0.7.4: fix: fix hurun_rank interface
0.7.5: add: add currency_pair_map interface
0.7.6: fix: fix stock_jgdy_detail_em interface
0.7.7: fix: fix stock_info interface
0.7.8: fix: fix bond_cb_jsl interface
0.7.9: fix: fix stock_jgdy_detail_em interface
0.7.10: fix: fix match_main_contract interface
0.7.11: fix: fix stock_analyst_rank_em and stock_analyst_detail_em interface
0.7.12: add: add stock_zh_a_cdr_daily interface
0.7.13: fix: fix stock_zh_a_cdr_daily and stock_zh_a_daily interface
0.7.14: fix: fix get_receipt interface
0.7.15: add: add futures_contract_detail interface
0.7.16: fix: fix futures_zh_spot interface
0.7.17: del: del zdzk interface
0.7.18: fix: fix stock_zh_a_daily interface
0.7.19: fix: fix stock_zh_a_daily interface
0.7.20: fix: fix stock_jgdy_tj_em interface
0.7.21: fix: fix zh_stock_kcb_report interface
0.7.22: fix: fix zh_stock_kcb_report interface
0.7.23: fix: fix fund_open_fund_info_em interface
0.7.24: fix: fix futures_spot_price_daily interface
0.7.25: add: add option_current_em interface
0.7.26: fix: fix option_current_em interface
0.7.27: add: add js_news interface
0.7.28: fix: fix js_news interface
0.7.29: fix: fix macro_china_market_margin_sh interface
0.7.30: add: add nlp_answer interface
0.7.31: fix: fix index_sw interface
0.7.32: add: add index_cni interface
0.7.33: add: add more index_cni interface
0.7.34: add: add stock_dzjy_sctj interface
0.7.35: add: add stock_dzjy_mrmx interface
0.7.36: add: add stock_dzjy_mrtj interface
0.7.37: add: add stock_dzjy_hygtj interface
0.7.38: add: add stock_dzjy_hyyybtj interface
0.7.39: add: add stock_dzjy_yybph interface
0.7.40: fix: fix js_news interface
0.7.41: add: add stock_yzxdr_em interface
0.7.42: fix: fix fund_etf_fund_daily_em interface
0.7.43: fix: fix match_main_contract interface
0.7.44: fix: fix stock_hk_daily interface
0.7.45: fix: fix stock_yzxdr_em interface
0.7.46: fix: fix option_czce_hist interface
0.7.47: fix: fix bond_zh_cov interface
0.7.48: fix: fix futures_dce_position_rank interface
0.7.49: fix: fix stock_us_zh_spot interface
0.7.50: fix: fix stock_hsgt_stock_statistics_em interface
0.7.51: fix: fix stock_us_daily interface
0.7.52: fix: fix stock_sector_fund_flow_rank interface
0.7.53: fix: fix stock_yzxdr_em interface
0.7.54: add: add stock_a_code_to_symbol interface
0.7.55: add: add stock_news_em interface
0.7.56: fix: fix stock_news_em interface
0.7.57: fix: fix xlrd support
0.7.58: fix: fix stock_zh_a_tick_tx_js support
0.7.59: fix: fix read_excel support
0.7.60: fix: fix fund_open_fund_daily_em interface
0.7.61: fix: fix calendar.json interface
0.7.62: fix: fix QQ group interface
0.7.63: add: add bond_summary_sse interface
0.7.64: fix: fix macro_cons_gold_volume interface
0.7.65: fix: fix fund_value_estimation_em interface
0.7.66: fix: fix fund_value_estimation_em interface
0.7.67: fix: fix get_dce_daily interface
0.7.68: fix: fix stock_zh_index_spot interface
0.7.69: fix: fix covid_19 interface
0.7.70: fix: fix get_dce_rank_table interface
0.7.71: fix: fix stock_us_daily interface
0.7.72: fix: fix get_ine_daily interface
0.7.73: add: add macro_china_money_supply interface
0.7.74: fix: fix stock_zh_a_minute interface
0.7.75: add: add bond_cash_summary_sse interface
0.7.76: fix: fix get_rank_sum_daily interface
0.7.77: fix: fix get_inventory_data interface
0.7.78: fix: fix futures_inventory_99 interface
0.7.79: fix: fix stock_a_below_net_asset_statistics interface
0.7.80: add: add bank_rank_banker interface
0.7.81: add: add macro_china_stock_market_cap interface
0.7.82: fix: fix macro_china_stock_market_cap interface
0.7.83: fix: fix stock_news_em interface
0.7.84: fix: fix covid_19_dxy interface
0.7.85: add: add futures_spot_price_previous interface
0.7.86: add: add fund_em_hk_rank interface
0.7.87: add: add fund_em_lcx_rank interface
0.7.88: fix: fix bond_repo_zh_tick interface
0.7.89: fix: fix stock_hk_daily interface
0.7.90: fix: fix stock_gpzy_pledge_ratio_em interface
0.7.91: fix: fix stock_report_disclosure interface
0.7.92: add: add fund_hk_fund_hist_em interface
0.7.93: add: add fund_portfolio_hold_em interface
0.7.94: fix: fix futures_spot_price_previous interface
0.7.95: add: add covid_19_trace interface
0.7.96: fix: fix bond_spot_quote interface
0.7.97: fix: fix bond_spot_deal interface
0.7.98: fix: fix stock_report_fund_hold interface
0.7.99: fix: fix stock_zh_a_daily interface
0.8.1: add: add stock_report_fund_hold_detail interface
0.8.2: fix: fix option_finance_board interface
0.8.3: fix: fix stock_zh_a_daily interface
0.8.4: fix: fix option interface
0.8.5: fix: fix bond_investing_global interface
0.8.6: add: add macro_china_shrzgm interface
0.8.7: add: add stock_zh_a_tick_163_now interface
0.8.8: fix: fix add PK to CZCE
0.8.9: add: add futures delivery and spot interface
0.8.10: fix: fix fund_portfolio_hold_em interface
0.8.11: add: add futures_to_spot_dce interface
0.8.12: add: add futures_delivery_shfe interface
0.8.13: fix: fix stock_us_daily interface
0.8.14: fix: fix fund_open_fund_rank_em interface
0.8.15: fix: fix chinese_to_english interface
0.8.16: fix: fix stock_a_pe interface
0.8.17: add: add stock_financial_report_sina interface
0.8.18: fix: fix futures_spot_price_daily interface
0.8.19: add: add stock_margin_sse interface
0.8.20: add: add stock_margin_detail_sse interface
0.8.21: fix: fix stock_szse_summary interface
0.8.22: fix: fix stock_zh_a_daily interface
0.8.23: fix: fix covid_19_dxy interface
0.8.24: fix: fix fund_value_estimation_em interface
0.8.25: fix: fix stock_zh_index_daily_tx interface
0.8.26: fix: fix stock_hk_daily interface
0.8.27: fix: fix get_dce_rank_table interface
0.8.28: fix: fix stock_analyst_rank_em interface
0.8.29: add: add fund_rating interface
0.8.30: add: add fund_manager interface
0.8.31: fix: fix stock_zh_a_minute interface
0.8.32: fix: fix get_dce_rank_table interface
0.8.33: add: add stock_profit_forecast interface
0.8.34: fix: fix index_investing_global interface
0.8.35: add: add bond_zh_us_rate interface
0.8.36: add: add stock_fhps_em interface
0.8.37: add: add stock_yjkb_em interface
0.8.38: fix: fix get_czce_daily interface
0.8.39: add: add stock_board_concept_cons_ths interface
0.8.40: fix: fix stock_board_concept_cons_ths interface
0.8.41: fix: fix energy_carbon_bj interface
0.8.42: fix: fix stock_zh_a_daily interface
0.8.43: fix: fix stock_yjyg_em interface
0.8.44: fix: fix stock_comment_em interface
0.8.45: add: add stock_sse_deal_daily interface
0.8.46: fix: fix stock_board_concept_cons_ths interface
0.8.47: add: add stock_board_concept_info_ths interface
0.8.48: fix: fix fund_rating_sh fund_rating_zs fund_rating_ja interface
0.8.49: add: add stock_yjbb_em interface
0.8.50: fix: fix stock_zh_index_spot interface
0.8.51: fix: fix stock_zh_a_spot interface
0.8.52: add: add stock_zcfz_em, stock_lrb_em, stock_xjll_em interface
0.8.53: fix: fix stock_zcfz_em interface
0.8.54: fix: fix stock_register_kcb interface
0.8.55: add: add stock_ipo_declare interface
0.8.56: fix: fix index_bloomberg_billionaires interface
0.8.57: fix: fix hurun_rank interface
0.8.58: add: add hurun_rank interface
0.8.59: fix: fix get_sector_futures interface
0.8.60: fix: fix currency_hist interface
0.8.61: fix: fix stock_hsgt_hold_stock_em interface
0.8.62: fix: fix stock_zh_a_tick_163 interface
0.8.63: fix: fix futures_zh_daily_sina interface
0.8.64: fix: fix futures_inventory_em interface
0.8.65: fix: fix futures_hq_spot_df interface
0.8.66: fix: fix currency_hist interface
0.8.67: fix: fix requirements.txt interface
0.8.68: fix: fix bond_investing_global interface
0.8.69: fix: fix stock_board_concept_cons_ths interface
0.8.70: add: add stock_board_concept_index_ths interface
0.8.71: fix: fix remove obor fold
0.8.72: fix: fix stock_board_concept_index_ths interface
0.8.73: add: add stock_board_industry_index_ths interface
0.8.74: fix: fix test interface
0.8.75: fix: fix stock_board_industry_index_ths interface
0.8.76: add: add stock_notice_report interface
0.8.77: fix: fix rate_interbank interface
0.8.78: fix: fix stock_board_concept_index_ths interface
0.8.79: add: add stock_lh_yyb_most, stock_lh_yyb_capital, stock_lh_yyb_control interface
0.8.80: fix: fix stock_yjkb_em interface
0.8.81: add: add crypto_bitcoin_hold_report interface
0.8.82: fix: fix energy_carbon_hb interface
0.8.83: fix: fix get_czce_daily interface
0.8.84: fix: fix amac_fund_abs interface
0.8.85: fix: fix rename amac_person_org_list to amac_person_fund_org_list interface
0.8.86: add: add amac_person_bond_org_list interface
0.8.87: add: add stock_fund_flow_concept interface
0.8.88: add: add stock_fund_flow_industry interface
0.8.89: add: add stock_fund_flow_individual interface
0.8.90: add: add stock_fund_flow_big_deal interface
0.8.91: add: add stock_ggcg_em interface
0.8.92: fix: fix stock_zh_a_daily interface
0.8.93: fix: fix bond_spot_deal interface
0.8.94: fix: fix stock_us_daily interface
0.8.95: add: add fund_new_found_em interface
0.8.96: fix: fix get_czce_rank_table interface
0.8.97: add: add stock_wc_hot_top interface
0.8.98: add: add index_kq interface
0.8.99: fix: fix stock_individual_fund_flow_rank interface
0.9.1: fix: fix stock_profit_forecast interface
0.9.2: fix: fix get_futures_daily interface
0.9.3: fix: fix get_futures_daily interface
0.9.4: fix: fix get_shfe_daily interface
0.9.5: add: add stock_hot_rank_wc interface
0.9.6: fix: fix stock_hot_rank_wc interface
0.9.7: fix: fix stock_hot_rank_wc interface
0.9.8: fix: fix forbes_rank interface
0.9.9: fix: fix stock_a_below_net_asset_statistics interface
0.9.10: fix: fix stock_hot_rank_wc interface
0.9.11: add: add drewry_wci_index interface
0.9.12: fix: fix bond_investing_global interface
0.9.13: fix: fix currency_hist interface
0.9.14: fix: fix futures_global_commodity_hist interface
0.9.15: add: add index_kq_fashion interface
0.9.16: add: add index_eri interface
0.9.17: fix: fix futures_global_commodity_hist interface
0.9.18: fix: fix stock_dxsyl_em interface
0.9.19: add: add stock_market_activity_legu interface
0.9.20: fix: fix stock_individual_fund_flow_rank interface
0.9.21: add: add index_cflp_price interface
0.9.22: add: add index_cflp_volume interface
0.9.23: fix: fix index_cflp_volume interface
0.9.24: fix: fix stock_info_sz_name_code interface
0.9.25: add: add car_gasgoo_sale_rank interface
0.9.26: fix: fix stock_hk_daily interface
0.9.27: fix: fix stock_report_fund_hold interface
0.9.28: add: add stock_average_position_legu interface
0.9.29: add: add stock_em_qbzf interface
0.9.30: add: add stock_em_pg interface
0.9.31: fix: fix index_investing_global interface
0.9.32: fix: fix bond_investing_global interface
0.9.33: add: add marco_china_hk interface
0.9.34: fix: fix get_futures_daily interface
0.9.35: fix: fix stock_zh_a_daily interface
0.9.36: fix: fix stock_zh_a_daily hfq and qfq interface
0.9.37: fix: fix stock_hot_rank_wc interface
0.9.38: add: add stock_zt_pool_em interface
0.9.39: fix: fix stock_us_daily interface
0.9.40: fix: fix bond_cov_comparison interface
0.9.41: fix: fix stock_zt_pool_previous_em interface
0.9.42: add: add stock_zt_pool_strong_em interface
0.9.43: fix: fix stock_zt_pool_strong_em interface
0.9.44: fix: fix stock_zt_pool_sub_new_em interface
0.9.45: fix: fix stock_zt_pool_em interface
0.9.46: fix: fix spot_goods interface
0.9.47: fix: fix futures_comex_inventory interface
0.9.48: fix: fix stock_zcfz_em interface
0.9.49: fix: fix stock_hk_daily interface
0.9.50: fix: fix futures_spot_stock interface
0.9.51: fix: fix stock_hk_daily interface
0.9.52: fix: remove internal_flow_history interface
0.9.53: add: add stock_zh_a_alerts_cls interface
0.9.54: fix: fix bond_zh_us_rate interface
0.9.55: fix: fix index_vix interface
0.9.56: fix: fix macro_fx_sentiment interface
0.9.57: fix: fix stock_zh_a_alerts_cls interface
0.9.58: add: add stock_staq_net_stop interface
0.9.59: fix: fix covid_19_baidu interface
0.9.60: fix: fix currency_convert interface
0.9.61: fix: fix stock_info_sz_name_code interface
0.9.62: add: add stock_zh_a_gdhs interface
0.9.63: fix: fix stock_zh_a_gdhs interface
0.9.64: add: add futures_sina_hold_pos interface
0.9.65: fix: fix bond_zh_us_rate interface
0.9.66: fix: fix set urllib3==1.25.11
0.9.67: fix: fix stock_hsgt_hold_stock_em interface
0.9.68: fix: fix stock_zh_a_tick_tx interface
0.9.69: add: add currency_boc_sina interface
0.9.70: add: add stock_zh_a_hist interface
0.9.71: fix: fix stock_zh_a_hist interface
0.9.72: fix: fix stock_zh_a_hist interface
0.9.73: fix: fix stock_zh_a_tick_tx_js interface
0.9.74: add: add stock_changes_em interface
0.9.75: add: add stock_hk_spot_em, stock_hk_hist interface
0.9.76: add: add stock_us_spot_em, stock_us_hist interface
0.9.77: fix: fix stock_us_hist interface
0.9.78: fix: fix rename python file name interface
0.9.79: add: add crypto_bitcoin_cme interface
0.9.80: fix: fix futures_display_main_sina interface
0.9.81: add: add crypto_crix interface
0.9.82: fix: fix crypto_crix interface
0.9.83: fix: fix crypto_crix interface
0.9.84: fix: fix rename futures_hq_spot to futures_foreign_commodity_realtime interface
0.9.85: fix: fix rate_interbank interface
0.9.86: add: add fund_aum_em interface
0.9.87: fix: fix death_company interface
0.9.88: fix: fix stock_financial_analysis_indicator interface
0.9.89: fix: fix fund_manager interface
0.9.90: fix: fix stock_a_below_net_asset_statistics interface
0.9.91: fix: fix stock_yjbb_em interface
0.9.92: fix: fix stock_tfp_em interface
0.9.93: fix: fix stock_zh_a_gdhs interface
0.9.94: add: add macro_china_qyspjg, macro_china_fdi interface
0.9.95: fix: fix stock_board_concept_index_ths interface
0.9.96: fix: fix stock_info_sz_name_code interface
0.9.97: fix: fix urllib3 version at 1.25.8
0.9.98: fix: fix js_news interface
0.9.99: fix: fix news_cctv interface
1.0.1: add: add macro_usa_phs interface
1.0.2: fix: fix macro_usa_phs interface
1.0.3: add: add macro_germany interface
1.0.4: fix: fix macro_china interface
1.0.5: add: add macro_china_gyzjz interface
1.0.6: fix: fix get_receipt interface
1.0.7: fix: fix get_ine_daily interface
1.0.8: fix: fix macro_china_cpi interface
1.0.9: fix: fix stock_zh_a_gdhs interface
1.0.10: fix: fix stock_zh_a_spot_em interface
1.0.11: fix: fix stock_board_industry_name_ths interface
1.0.12: fix: fix macro_china_money_supply interface
1.0.13: fix: fix rename stock_board_concept_index_ths to stock_board_concept_hist_ths interface
1.0.14: add: add stock_board_concept_cons_em and stock_board_concept_hist_em interface
1.0.15: fix: fix stock_hk_hist interface
1.0.16: fix: fix tool_trade_date_hist_sina interface
1.0.17: fix: fix calendar.json interface
1.0.18: fix: fix reformat macro_china_national_tax_receipts, macro_china_hgjck, macro_china_stock_market_cap interface
1.0.19: fix: fix marco_china_hk interface
1.0.20: fix: fix bond_zh_hs_cov_daily interface
1.0.21: fix: fix charity_china interface
1.0.22: fix: fix stock_xgsglb_em interface
1.0.23: fix: fix stock_dxsyl_em interface
1.0.24: fix: fix stock_board_concept_hist_em interface
1.0.25: fix: fix get_receipt interface
1.0.26: add: add energy_carbon_domestic interface
1.0.27: fix: fix get_roll_yield_bar interface
1.0.28: add: add covid_19_baidu interface
1.0.29: fix: fix covid_19_baidu interface
1.0.30: fix: fix option_czce_hist interface
1.0.31: fix: fix futures_foreign_commodity_realtime interface
1.0.32: fix: fix covid_19_baidu interface
1.0.33: fix: fix bond_china_close_return interface
1.0.34: fix: fix bond_china_close_return interface
1.0.35: fix: fix bond_cb_jsl interface
1.0.36: fix: fix stock_hsgt_north_net_flow_in_em interface
1.0.37: add: add macro_swiss interface
1.0.38: add: add macro_japan interface
1.0.39: add: add macro_uk interface
1.0.40: add: add stock_szse_margin interface
1.0.41: add: add macro_australia interface
1.0.42: fix: fix index_stock_hist interface
1.0.43: fix: fix stock_margin_detail_szse interface
1.0.44: fix: fix stock_margin_detail_szse interface
1.0.45: fix: fix option_dce_daily interface and rename interface in option_commodity
1.0.46: add: add futures_hog_info interface
1.0.47: fix: fix futures_hog_info interface
1.0.48: add: add macro_canada interface
1.0.49: fix: fix stock_individual_fund_flow interface
1.0.50: fix: fix stock_jgdy_tj_em interface
1.0.51: add: add sport_olympic_hist interface
1.0.52: add: add stock_financial_hk interface
1.0.53: fix: fix tool_trade_date_hist_sina interface
1.0.54: fix: fix macro_china_gdp_yearly interface
1.0.55: fix: fix macro_china_freight_index interface
1.0.56: add: add stock_a_ttm_lyr interface
1.0.57: add: add stock_a_all_pb interface
1.0.58: add: add futures_hog_rank interface
1.0.59: fix: fix futures_zh_daily_sina interface
1.0.60: fix: fix futures_main_sina interface
1.0.61: fix: fix stock_a_all_pb interface
1.0.62: add: add futures_egg_price interface
1.0.63: fix: fix remove jyfm interface
1.0.64: fix: fix rename zh_stock_kcb_report to stock_zh_kcb_report_em interface
1.0.65: fix: fix stock_gpzy_pledge_ratio_detail_em interface
1.0.66: fix: fix macro_cons_opec_month interface
1.0.67: fix: fix futures_sgx_daily interface
1.0.68: fix: remove agoyal_stock_return interface
1.0.69: fix: remove bank_rank_banker interface
1.0.70: fix: remove watch_jinshi_quotes interface
1.0.71: fix: remove watch_argus interface
1.0.72: fix: fix amac_fund_abs interface
1.0.73: add: add bond_cash_summary_sse interface
1.0.74: fix: fix bond_zh_hs_cov_spot interface
1.0.75: fix: fix bond_futures_deliverable_coupons interface
1.0.76: fix: fix stock_financial_hk_analysis_indicator_em interface
1.0.77: fix: fix macro_china_m2_yearly interface
1.0.78: add: add reits_realtime_em, reits_info_jsl interface
1.0.79: fix: fix news_cctv interface
1.0.80: add: add stock_zh_a_hist_min_em, stock_zh_a_hist_pre_min_em interface
1.0.81: add: add stock_us_hist_min_em, stock_hk_hist_min_em interface
1.0.82: fix: fix bond_zh_cov interface
1.0.83: fix: fix macro_china interface
1.0.84: add: add bond_zh_cov_info interface
1.0.85: fix: fix stock_report_fund_hold interface
1.0.86: fix: fix stock_zt_pool_dtgc_em interface
1.0.87: fix: fix macro_china_swap_rate interface
1.0.88: fix: fix stock_zh_a_hist_min_em interface
1.0.89: fix: fix stock_hk_hist_min_em interface
1.0.90: fix: fix stock_us_hist_min_em interface
1.0.91: fix: fix stock_zh_a_hist_min_em interface
1.0.92: fix: fix stock_zh_a_hist interface
1.0.93: fix: fix stock_hk_hist_min_em interface
1.0.94: fix: fix stock_zh_a_new interface
1.0.95: fix: fix stock_zh_a_daily interface
1.0.96: add: add stock_zh_a_st_em interface
1.0.97: fix: fix futures_spot_stock interface
1.0.98: add: add stock_zh_a_new_em interface
1.0.99: fix: fix stock_hot_rank_wc interface
1.1.1: add: add index_investing_global_from_url interface
1.1.2: add: add stock_us_pink_spot_em interface
1.1.3: add: add stock_us_famous_spot_em interface
1.1.4: fix: fix stock_average_position_legu interface
1.1.5: add: add stock_rank_forecast_cninfo interface
1.1.6: fix: fix futures_zh_minute_sina interface
1.1.7: fix: fix covid_19_trace interface
1.1.8: add: add stock_industry_pe_ratio_cninfo interface
1.1.9: fix: fix stock_price_js interface
1.1.10: fix: fix stock_hsgt_hold_stock_em interface
1.1.11: fix: fix stock_fund_flow_concept interface
1.1.12: fix: fix stock_fund_flow_industry interface
1.1.13: add: add stock_dividents_cninfo interface
1.1.14: fix: fix stock_fund_flow_concept interface
1.1.15: add: add stock_new_gh_cninfo interface
1.1.16: fix: fix stock_jgdy_detail_em interface
1.1.17: fix: fix stock_jgdy_tj_em interface
1.1.18: fix: fix stock_fund_flow_concept and stock_fund_flow_industry interface
1.1.19: add: add stock_new_ipo_cninfo interface
1.1.20: fix: fix stock_a_pe interface
1.1.21 fix: fix setuptools==57.5.0 package
1.1.22 fix: fix remove demjson package
1.1.23 fix: fix update urllib3 package
1.1.24 fix: fix email address
1.1.25 add: add stock_hold_num_cninfo interface
1.1.26 fix: fix stock_fund_flow_concept interface
1.1.27 add: add stock_hold_control_cninfo interface
1.1.28 fix: fix move project to AKFamily interface
1.1.29 fix: fix urllib3>=1.25.8 package
1.1.30 fix: fix stock_zh_index_hist_csindex interface
1.1.31 add: add stock_hold_management_detail_cninfo interface
1.1.32 add: add sw_index_representation_spot interface
1.1.33 fix: fix sw_index_xxx interface
1.1.34 fix: fix drewry_wci_index interface
1.1.35 fix: fix fund_etf_category_sina interface
1.1.36 fix: fix sw_index_daily_indicator interface
1.1.37 fix: fix drewry_wci_index interface
1.1.38 add: add futures_comm_info interface
1.1.39 fix: fix futures_comm_info interface
1.1.40 fix: fix remove covid_19_history interface
1.1.41 add: add stock_zh_b_sina interface
1.1.42 fix: fix stock_zh_a_minute interface
1.1.43 add: add stock_cg_guarantee_cninfo interface
1.1.44 fix: fix stock_zh_index_daily interface
1.1.45 fix: fix stock_zh_index_daily_tx interface
1.1.46 fix: fix remove watch_jinshi_fx interface
1.1.47 fix: fix stock_jgdy_tj_em and stock_jgdy_detail_em interface
1.1.48 fix: fix rename fund_em_portfolio_hold to fund_portfolio_hold_em interface
1.1.49 fix: fix stock_jgdy_tj_em and stock_jgdy_detail_em interface
1.1.50 add: add stock_cg_lawsuit_cninfo interface
1.1.51 fix: fix stock_hot_rank_wc interface
1.1.52 add: add stock_cg_equity_mortgage_cninfo interface
1.1.53 fix: fix index_detail_hist_adjust_cni interface
1.1.54 fix: fix stock_board_concept_hist_ths interface
1.1.55 fix: fix stock_sina_lhb_ggtj and stock_sina_lhb_jgzz interface
1.1.56 add: add fund_aum_hist_em interface
1.1.57 fix: fix stock_sina_lhb_ggtj and stock_sina_lhb_jgzz interface
1.1.58 add: add bond_treasure_issue_cninfo interface
1.1.59 add: add bond_local_government_issue_cninfo interface
1.1.60 add: add bond_corporate_issue_cninfo interface
1.1.61 add: add bond_cov_issue_cninfo interface
1.1.62 fix: fix bond_zh_us_rate interface
1.1.63 add: add bond_cov_stock_issue_cninfo interface
1.1.64 add: add fund_report_stock_cninfo interface
1.1.65 fix: fix stock_notice_report interface
1.1.66 add: add fund_report_industry_allocation_cninfo interface
1.1.67 fix: fix stock_zh_index_hist_csindex interface
1.1.68 fix: fix index_stock_cons_csindex interface
1.1.69 add: add fund_scale_open_sina interface
1.1.70 add: add fund_scale_close_sina interface
1.1.71 add: add fund_scale_structured_sina interface
1.1.72 add: add fund_report_asset_allocation_cninfo interface
1.1.73 add: add stock_zh_index_value_csindex interface
1.1.74 fix: fix fund_etf_fund_info_em interface
1.1.75 add: add index_value_hist_funddb interface
1.1.76 fix: fix amac_fund_info interface
1.1.77 fix: fix stock_zh_a_tick_163_now interface
1.1.78 add: add stock_hsgt_individual_em interface
1.1.79 fix: fix stock_jgdy_tj_em interface
1.1.80 add: add support for Python 3.10 interface
1.1.81 add: add stock_hsgt_individual_detail_em interface
1.1.82 fix: fix stock_tfp_em interface
    1. rename stock_em_tfp to stock_tfp_em
    2. reformat output data type
1.1.83 add: add stock_ipo_benefit_ths interface
1.1.84 fix: fix stock_board_industry_index_ths interface
    1. add start_date and end_date parameters
1.1.85 fix: fix stock_hsgt_stock_statistics_em interface
1.1.86 fix: fix stock_hsgt_stock_statistics_em interface
1.1.87 fix: fix stock_hsgt_hist_em interface
1.1.88 fix: fix stock_sector_spot interface
1.1.89 fix: fix stock_sector_detail interface
1.1.90 fix: fix stock_board_concept_name_ths interface
1.1.91 fix: fix stock_hsgt_individual_detail_em interface
1.1.92 add: add stock_rank_cxg_ths interface
1.1.93 add: add stock_rank_cxd_ths interface
1.1.94 fix: fix fund_portfolio_hold_em interface
1.1.95 fix: fix stock_board_concept_hist_ths interface
1.1.96 add: add bond_zh_hs_cov_min interface
1.1.97 add: add stock_rank_lxsz_ths interface
1.1.98 add: add stock_rank_lxxd_ths interface
1.1.99 add: add stock_rank_cxfl_ths interface
1.2.1 add: add stock_rank_cxsl_ths interface
1.2.2 fix: fix zh_subscribe_exchange_symbol interface
1.2.3 add: add stock_rank_xstp_ths interface
1.2.4 fix: fix fund_portfolio_hold_em interface
1.2.5 fix: fix index_stock_hist interface
1.2.6 add: add stock_rank_xxtp_ths interface
1.2.7 add: add stock_rank_ljqd_ths interface
1.2.8 add: add stock_rank_ljqs_ths interface
1.2.9 fix: fix stock_zh_a_gdhs interface
1.2.10 fix: fix bond_zh_hs_daily interface
1.2.11 add: add stock_zh_a_gdhs_detail_em interface
1.2.12 fix: fix stock_zh_a_gdhs interface
1.2.13 add: add stock_rank_xzjp_ths interface
1.2.14 add: add sw_index_second_spot interface
1.2.15 fix: fix stock_board_industry_name_ths interface
1.2.16 add: add stock_board_cons_ths interface
1.2.17 fix: fix amac_fund_info interface
1.2.18 fix: fix amac interface
1.2.19 fix: fix amac cons.py interface
1.2.20 fix: fix stock_zh_a_spot_em interface
1.2.21 fix: fix stock_zh_a_hist interface
1.2.22 fix: fix amac_fund_info interface
1.2.23 add: add video_tv interface
1.2.24 fix: fix car_gasgoo_sale_rank interface
1.2.25 fix: fix amac_manager_classify_info interface
1.2.26 fix: fix amac interface
1.2.27 add: add online_value_artist interface
1.2.28 add: add club_rank_game interface
1.2.29 add: add player_rank_game interface
1.2.30 add: add business_value_artist interface
1.2.31 fix: fix stock_zt_pool_em interface
1.2.32 add: add video_variety_show interface
1.2.33 add: add fund_fh_em interface
1.2.34 fix: fix fund_open_fund_info_em interface
1.2.35 fix: fix fund_open_fund_info_em interface
1.2.36 add: add stock_info_bj_name_code interface
1.2.37 fix: fix stock_info_a_code_name interface
1.2.38 fix: fix futures_foreign_commodity_realtime interface
1.2.39 fix: fix stock_info_sh_delist interface
1.2.40 add: add fund_scale_change_em interface
1.2.41 add: add fund_hold_structure_em interface
1.2.42 fix: fix fund_manager interface
1.2.43 fix: fix get_czce_daily interface
1.2.44 add: add futures_index_cscidx interface
1.2.45 fix: fix stock_info_a_code_name interface
1.2.46 add: add stock_board_industry_cons_em interface
1.2.47 fix: fix covid_19_dxy interface
1.2.48 fix: fix covid_19_dxy interface
1.2.49 fix: fix rate_interbank interface
1.2.50 fix: fix futures_price_index_nh interface
1.2.51 add: add futures_hq_subscribe_exchange_symbol interface
1.2.52 fix: fix futures_foreign_commodity_realtime interface
1.2.53 add: add get_ine_daily interface
1.2.54 fix: fix bond_zh_hs_cov_min interface
1.2.55 add: add stock_repurchase_em interface
1.2.56 fix: fix stock_zh_a_tick_163 interface
1.2.57 add: add stock_us_hist_fu interface
1.2.58 fix: fix stock_board_concept_hist_ths interface
1.2.59 fix: fix macro_china_hk interface
1.2.60 fix: fix macro_china_hk interface
1.2.61 fix: fix stock_board_concept_hist_ths interface
1.2.62 fix: fix stock_dzjy_sctj interface
1.2.63 add: add spot_hist_sge interface
1.2.64 add: add spot_silver_benchmark_sge interface
1.2.65 remove: remove wdbank interface
1.2.66 add: add spot_golden_benchmark_sge interface
1.2.67 fix: fix air_quality_hebei interface
1.2.68 fix: fix stock_financial_hk_analysis_indicator_em interface
1.2.69 fix: fix get_futures_daily interface
1.2.70 fix: fix sw_index_spot interface
1.2.71 add: add sw_index_third_info interface
1.2.72 add: add sw_index_third_cons interface
1.2.73 fix: fix sw_index_third_cons interface
1.2.74 fix: fix macro_australia and macro_canada interface
1.2.75 fix: fix docs interface
1.2.76 fix: fix amac_person_fund_org_list interface
1.2.77 add: add bond_cb_adj_logs_jsl interface
1.2.78 fix: fix amac_person_fund_org_list interface
1.2.79 fix: fix amac_person_fund_org_list interface
1.2.80 fix: fix sw_index_daily interface
1.2.81 fix: fix stock_us_hist_fu interface
1.2.82 fix: fix spot_symbol_table_sge interface
1.2.83 fix: fix macro_bank interface
1.2.84 fix: fix repo_rate_hist interface
1.2.85 fix: fix repo_rate_hist interface
1.2.86 add: add stock_a_pe_and_pb interface
1.2.87 add: add stock_hk_ggt_components_em interface
1.2.88 fix: fix futures_nh_index interface
1.2.89 fix: fix futures_index_cscidx interface
1.2.90 fix: fix stock_board_industry_index_ths interface
1.2.91 fix: fix fund_etf_hist_sina interface
1.2.92 fix: fix futures_zh_spot interface
1.2.93 fix: fix fund_manager interface
1.2.94 fix: fix fund_new_found_em interface
1.2.95 add: add stock_individual_info_em interface
1.2.96 fix: fix match_main_contract interface
1.2.97 fix: fix stock_profit_forecast interface
1.2.98 fix: fix futures_spot_stock interface
1.2.99 fix: fix PYPI info
1.3.1 fix: fix option_shfe_daily interface
1.3.2 fix: remove github interface
1.3.3 fix: fix stock_em_ztb interface
1.3.4 fix: fix stock_hsgt_stock_statistics_em interface
1.3.5 fix: update QQ info
1.3.6 fix: fix stock_dzjy_sctj interface
1.3.7 fix: fix stock_hsgt_north_xxxx interface
1.3.8 fix: fix stock_info_change_name interface
1.3.9 add: add index_sugar_msweet interface
1.3.10 fix: fix index_sugar_msweet interface
1.3.11 fix: fix index_cflp_price interface
1.3.12 add: add index_inner_quote_sugar_msweet interface
1.3.13 fix: fix stock_zh_a_tick_163 interface
1.3.14 fix: fix stock_zh_a_scr_report interface
1.3.15 fix: fix option_current_em interface
1.3.16 fix: fix stock_account_statistics_em interface
1.3.17 fix: fix stock_sse_deal_daily interface
1.3.18 fix: fix stock_sse_summary interface
1.3.19 add: add index_stock_cons_weight_csindex interface
1.3.20 fix: fix index_cni_xx interface
1.3.21 fix: fix index_detail_hist_adjust_cni interface
1.3.22 fix: fix hf_sp_500 interface
1.3.23 fix: fix macro_china_gksccz interface
1.3.24 fix: fix macro_china_bond_public interface
1.3.25 fix: fix stock_hk_hist interface
1.3.26 fix: fix stock_us_spot_em interface
1.3.27 fix: fix stock_us_hist interface
1.3.28 fix: fix stock_zh_a_hist interface
1.3.29 fix: fix update calendar.json to 2022
1.3.30 fix: fix stock_zh_index_daily_em interface
1.3.31 fix: fix stock_dzjy_mrmx interface
1.3.32 fix: fix stock_dzjy_mrtj interface
1.3.33 fix: fix stock_dzjy_yybph interface
1.3.34 fix: fix stock_history_dividend interface
1.3.35 add: add fund_purchase_em interface
1.3.36 fix: fix futures_inventory_99 interface
1.3.37 fix: fix stock_financial_analysis_indicator interface
1.3.38 fix: fix index_value_name_funddb interface
1.3.39 fix: fix macro_china_hb interface
1.3.40 add: add stock_gdfx_free_holding_analyse_em interface
1.3.41 add: add stock_gdfx_free_top_10_em interface
1.3.42 add: add stock_gdfx_free_holding_detail_em interface
1.3.43 add: add stock_gdfx_free_holding_change_em interface
1.3.44 fix: fix stock_board_concept_name_ths interface
1.3.45 add: add stock_gdfx_holding_change_em interface
1.3.46 fix: fix futures_main_sina interface
1.3.47 add: add stock_gdfx_free_holding_statistics_em interface
1.3.48 add: add stock_gdfx_free_holding_teamwork_em interface
1.3.49 fix: fix fund_open_fund_info_em interface
1.3.50 fix: fix stock_notice_report interface
1.3.51 fix: fix futures_comm_info interface
1.3.52 fix: fix stock_hsgt_individual_detail_em interface
1.3.53 fix: fix sw_index_cons interface
1.3.54 fix: fix stock_em_qbzf interface
1.3.55 fix: fix futures_comm_info interface
1.3.56 fix: fix stock_hsgt_board_rank_em interface
1.3.57 fix: fix futures_main_sina interface
1.3.58 fix: fix stock_margin_detail_szse interface
1.3.59 add: add covid_19_risk_area interface
1.3.60 fix: fix covid_19_risk_area interface
1.3.61 fix: fix futures_zh_spot interface
1.3.62 fix: fix option_sse_spot_price_sina interface
1.3.63 fix: fix option_finance_minute_sina interface
1.3.64 fix: fix futures_foreign_commodity_realtime interface
1.3.65 fix: fix option_sse_codes_sina interface
1.3.66 fix: fix option_commodity_hist_sina interface
1.3.67 add: add option_lhb_em interface
1.3.68 fix: fix stock_hsgt_board_rank_em interface
1.3.69 fix: fix stock_gdfx_free_holding_statistics_em interface
1.3.70 fix: fix option_sse_spot_price_sina interface
1.3.71 fix: fix stock_history_dividend_detail interface
1.3.72 add: add option_value_analysis_em interface
1.3.73 fix: fix stock_info_sh_delist interface
1.3.74 fix: fix option_value_analysis_em interface
1.3.75 add: add option_risk_analysis_em interface
1.3.76 add: add option_premium_analysis_em interface
1.3.77 fix: fix sw_index_daily_indicator interface
1.3.78 fix: fix forbes_rank interface
1.3.79 add: add dockerfile for aktools interface
1.3.80 fix: fix dockerfile for aktools interface
1.3.81 fix: fix release_and_deploy interface
1.3.82 fix: fix dockerfile interface
1.3.83 fix: fix dockerfile-jupyter
1.3.84 fix: fix release_and_deploy
1.3.85 fix: fix release_and_deploy.yml
1.3.86 fix: fix master_dev_check.yml
1.3.87 fix: fix master_dev_check.yml
1.3.88 fix: fix master_dev_check.yml
1.3.89 fix: fix master_dev_check.yml
1.3.90 fix: fix master_dev_check.yml
1.3.91 fix: fix master_dev_check.yml
1.3.92 fix: fix docker image of akshare for jupyter and aktools
1.3.93 fix: fix docs
1.3.94 fix: fix akdocker.md
1.3.95 fix: fix covid_19_risk_area interface
1.3.96 fix: fix bond_china_close_return interface
1.3.97 fix: fix stock_us_hist interface
1.3.98 fix: fix stock_hk_hist interface
1.3.99 fix: fix index_yw interface
1.4.1 fix: fix index_yw interface
1.4.2 add: add index_dei_cx interface
1.4.3 add: add index_ii_cx interface
1.4.4 add: add index_si_cx interface
1.4.5 add: add index_pmi_com_cx interface
1.4.6 add: add index_pmi_man_cx interface
1.4.7 add: add index_pmi_ser_cx interface
1.4.8 add: add sport_olympic_winter_hist interface
1.4.9 fix: fix macro_cnbs interface
1.4.10 fix: fix get_futures_daily interface
1.4.11 fix: fix futures_spot_price_previous interface
1.4.12 add: add stock_hot_rank_em interface
1.4.13 add: add stock_hot_rank_detail_em interface
1.4.14 add: add index_bi_cx interface
1.4.15 add: add stock_hot_rank_detail_realtime_em interface
1.4.16 fix: fix stock_hot_rank_detail_em interface
1.4.17 fix: fix stock_hot_rank_wc interface
1.4.18 fix: fix stock_hot_rank_wc interface
1.4.19 fix: fix stock_price_js interface
1.4.20 add: add index_awpr_cx interface
1.4.21 fix: fix stock_zt_pool_em interface
1.4.22 fix: fix option_sse_greeks_sina interface
1.4.23 fix: rename all interface in option_finance_sina.py
1.4.24 fix: fix stock_em_jgdy_tj interface
1.4.25 add: add index_ci_cx interface
1.4.26 fix: fix fund_purchase_em interface
1.4.27 add: add index_cci_cx interface
1.4.28 fix: fix stock_info_sz_name_code interface
1.4.29 fix: fix stock_gdfx_free_holding_statistics_em interface
1.4.30 add: add index_li_cx interface
1.4.31 fix: fix docs interface
1.4.32 add: add index_neaw_cx interface
1.4.33 fix: fix docs interface
1.4.34 add: add index_neaw_cx interface
1.4.35 fix: fix stock_yysj_em interface
1.4.36 add: add index_nei_cx interface
1.4.37 add: add index_ti_cx interface
1.4.38 fix: fix stock_fund_flow_individual interface
1.4.39 add: add index_zh_a_hist_min_em interface
1.4.40 add: add index_code_id_map_em interface
1.4.41 fix: fix stock_hk_ggt_components_em interface
1.4.42 add: add stock_hot_keyword_em interface
1.4.43 fix: fix stock_fhps_em interface
1.4.44 fix: fix stock_dxsyl_em interface
1.4.45 fix: fix air_quality_rank interface
1.4.46 fix: fix energy_oil_detail interface
1.4.47 add: add interface change log
1.4.48 fix: fix stock_sse_deal_daily interface
1.4.49 fix: fix stock_sse_deal_daily interface
1.4.50 add: add stock_hot_rank_detail_realtime_em interface
1.4.51 add: add stock_hot_keyword_em interface
1.4.52 add: add stock_hot_rank_latest_em interface
1.4.53 add: add stock_hot_rank_relate_em interface
1.4.54 fix: fix stock_hot_rank_relate_em interface
1.4.55 fix: fix energy_carbon interface
1.4.56 fix: fix index_detail_hist_cni and index_detail_cni interface
1.4.57 fix: fix bond_spot_quote interface
1.4.58 fix: fix stock_zh_kcb_daily interface
1.4.59 add: add stock_zh_a_hist_163 interface
1.4.60 fix: fix stock_zh_a_hist_163 interface
1.4.61 fix: fix get_dce_daily interface
1.4.62 fix: fix option_finance_board interface
1.4.63 fix: fix macro_china_swap_rate interface
1.4.64 fix: fix bond_china_close_return interface
1.4.65 fix: fix spot_hist_sge interface
1.4.66 fix: fix stock_gpzy_profile_em interface
1.4.67 fix: fix crypto_name_url_table interface
1.4.68 fix: fix crypto_hist interface
1.4.69 fix: fix crypto_js_spot interface
1.4.70 add: add stock_lhb_detail_em interface
1.4.71 add: add stock_lhb_stock_detail_em interface
1.4.72 add: add stock_lhb_stock_statistic_em interface
1.4.73 add: add stock_lhb_jgmmtj_em interface
1.4.74 fix: fix stock_lhb_stock_detail_em interface
1.4.75 fix: fix stock_lhb_stock_detail_em interface
1.4.76 add: add stock_lhb_stock_statistic_em interface
1.4.77 fix: fix stock_hk_ggt_components_em interface
1.4.78 add: add remove matplotlib module and support cache
1.4.79 add: add stock_board_industry_hist_min_em interface
1.4.80 add: add stock_board_concept_hist_min_em interface
1.4.81 add: add fund_portfolio_change_em interface
1.4.82 fix: fix stock_a_code_to_symbol interface
1.4.83 add: add stock_us_code_table_fu interface
1.4.84 fix: fix fund_portfolio_change_em interface
1.4.85 add: add fund_portfolio_bond_hold_em interface
1.4.86 fix: fix rename all interface in fund_aum_em.py
1.4.87 add: add fund_portfolio_industry_allocation_em interface
1.4.88 fix: fix fund_new_found_em interface
1.4.89 fix: fix stock_us_hist interface
1.4.90 add: add macro_china_bank_financing interface
1.4.91 fix: fix macro_china_new_financial_credit interface
1.4.92 add: add stock_lhb_hyyyb_em interface
1.4.93 add: add macro_china_insurance_income interface
1.4.94 add: add macro_china_mobile_number interface
1.4.95 add: add bond_zh_cov_value_analysis interface
1.4.96 fix: fix stock_sse_deal_daily interface
1.4.97 fix: fix bond_spot_deal interface
1.4.98 fix: fix stock_board_industry_hist_em interface
1.4.99 add: add macro_china_vegetable_basket interface
1.5.1 add: add macro_china_agricultural_product interface
1.5.2 add: add macro_china_agricultural_index interface
1.5.3 add: add macro_china_energy_index interface
1.5.4 add: add macro_china_commodity_price_index interface
1.5.5 add: add macro_global_sox_index interface
1.5.6 add: add macro_china_yw_electronic_index interface
1.5.7 add: add macro_china_construction_index interface
1.5.8 add: add macro_china_construction_price_index interface
1.5.9 fix: fix air_quality_hist interface
1.5.10 fix: fix stock_gpzy_pledge_ratio_em and stock_gpzy_profile_em interface
1.5.11 add: add index_bloomberg_billionaires_hist interface
1.5.12 fix: fix stock_gpzy_pledge_ratio_detail_em interface
1.5.13 add: add macro_china_lpi_index interface
1.5.14 add: add macro_china_bdti_index interface
1.5.15 fix: fix bond_cb_jsl interface
1.5.16 fix: fix stock_info_sh_delist interface
1.5.17 add: add macro_china_bsi_index interface
1.5.18 fix: fix fund_open_fund_rank_em interface
1.5.19 add: add futures_correlation_nh interface
1.5.20 add: add futures_board_index_nh interface
1.5.21 add: add futures_variety_index_nh interface
1.5.22 fix: fix futures_correlation_nh interface
1.5.23 fix: fix stock_board_concept_name_em interface
1.5.24 fix: fix stock_profit_forecast interface
1.5.25 fix: fix stock_analyst_rank_em and stock_analyst_detail_em interface
1.5.26 fix: fix stock_comment_em interface
1.5.27 fix: fix stock_comment_em interface
1.5.28 fix: fix bond_zh_cov interface
1.5.29 fix: fix index_zh_a_hist_min_em interface
1.5.30 fix: fix hurun_rank interface
1.5.31 fix: fix stock_individual_info_em interface
1.5.32 add: add stock_comment_detail_zlkp_jgcyd_em interface
1.5.33 fix: fix fund_fh_em interface
1.5.34 fix: fix stock_gpzy_industry_data_em interface
1.5.35 add: add stock_comment_detail_zhpj_lspf_em interface
1.5.36 add: add stock_comment_detail_scrd_focus_em interface
1.5.37 add: add stock_comment_detail_scrd_desire_em interface
1.5.38 add: add stock_comment_detail_scrd_cost_em interface
1.5.39 add: add stock_comment_detail_scrd_desire_daily_em interface
1.5.40 fix: fix js_news interface
1.5.41 fix: fix stock_margin_underlying_info_szse interface
1.5.42 fix: fix stock_zt_pool_dtgc_em interface
1.5.43 fix: fix stock_zt_pool_em interface
1.5.44 fix: fix futures_to_spot_czce interface
1.5.45 add: add stock_hot_deal_xq interface
1.5.46 fix: fix stock_yzxdr_em interface
1.5.47 fix: fix macro_china_lpr interface
1.5.48 fix: fix futures_return_index_nh interface
1.5.49 add: add stock_inner_trade_xq interface
1.5.50 fix: fix covid_19_baidu interface
1.5.51 fix: fix stock_zh_a_tick_163 interface
1.5.52 fix: fix stock_ggcg_em interface
1.5.53 fix: fix stock_zcfz_em interface
1.5.54 fix: fix stock_lrb_em interface
1.5.55 add: add stock_balance_sheet_by_report_em interface
1.5.56 add: add stock_balance_sheet_by_yearly_em interface
1.5.57 add: add stock_profit_sheet_by_report_em interface
1.5.58 add: add stock_profit_sheet_by_quarterly_em interface
1.5.59 add: add stock_profit_sheet_by_yearly_em interface
1.5.60 fix: fix sw_index_second_spot interface
1.5.61 add: add stock_cash_flow_sheet_by_report_em interface
1.5.62 add: add stock_cash_flow_sheet_by_quarterly_em interface
1.5.63 fix: fix import path problem
1.5.64 fix: fix stock_cash_flow_sheet_by_yearly_em interface
1.5.65 fix: fix stock_repurchase_em interface
1.5.66 fix: fix crypto_hist interface
1.5.67 add: add test function
1.5.68 fix: fix test function
1.5.69 fix: fix setup.py
1.5.70 fix: fix stock_zh_a_spot interface
1.5.71 fix: fix import path problem
1.5.72 add: add news_economic_baidu interface
1.5.73 fix: fix stock_notice_report interface
1.5.74 add: add news_trade_notify_suspend_baidu interface
1.5.75 fix: fix stock_financial_analysis_indicator interface
1.5.76 add: add news_report_time_baidu interface
1.5.77 fix: fix remove numpy dependency
1.5.78 fix: fix stock_szse_summary interface
1.5.79 add: add stock_szse_area_summary interface
1.5.80 add: add stock_szse_sector_summary interface
1.5.81 fix: fix macro_china_gdp_yearly interface
1.5.82 add: add option_risk_indicator_sse interface
1.5.83 fix: fix energy_oil_hist, energy_oil_detail interface
1.5.84 fix: fix stock_three_report_em interface
1.5.85 fix: fix stock_zh_a_hist interface
1.5.86 fix: fix stock_us_fundamental interface
1.5.87 fix: fix stock_tfp_em interface
1.5.88 fix: fix stock_board_concept_name_ths interface
1.5.89 fix: fix stock_info_sh_name_code interface
1.5.90 fix: fix macro_china_bond_public interface
1.5.91 add: add bond_cb_index_jsl interface
1.5.92 fix: fix rate_interbank interface
1.5.93 fix: fix stock_zh_a_hist interface
1.5.94 add: add bond_cb_redeem_jsl interface
1.5.95 fix: fix stock_zh_a_hist_163 interface
1.5.96 fix: fix macro_bank_usa_interest_rate interface
1.5.97 fix: fix stock_zh_a_hist interface
1.5.98 fix: fix news_cctv interface
1.5.99 fix: fix stock_zh_a_hist_163 interface
1.6.1 fix: fix stock_info_sh_name_code interface
1.6.2 fix: fix macro_china_cpi interface
1.6.3 fix: fix stock_info_a_code_name and stock_info_sh_delist interface
1.6.4 fix: fix stock_info_a_code_name interface
1.6.5 fix: fix stock_board_cons_ths interface
1.6.6 fix: fix fund_etf_hist_sina interface
1.6.7 add: add futures_zh_realtime interface
1.6.8 fix: fix futures_zh_spot interface
1.6.9 fix: fix stock_zh_a_spot_em interface
1.6.10 add: add stock_sh_a_spot_em interface
1.6.11 add: add stock_sz_a_spot_em interface
1.6.12 add: add stock_bj_a_spot_em interface
1.6.13 add: add stock_new_a_spot_em interface
1.6.14 fix: fix stock_hsgt_board_rank_em interface
1.6.15 fix: fix bond_zh_cov_info interface
1.6.16 fix: fix baidu_search_index interface
1.6.17 fix: fix stock_new_a_spot_em interface
1.6.18 fix: fix stock_zh_a_spot_em interface
1.6.19 fix: fix stock_comment_detail_zlkp_jgcyd_em interface
1.6.20 fix: fix stock_board_industry_name_em and code_id_map_em interface
1.6.21 fix: fix baidu_search_index interface
1.6.22 add: add stock_kc_a_spot_em interface
1.6.23 fix: fix bond_cb_index_jsl interface
1.6.24 fix: fix bond_cb_index_jsl interface
1.6.25 fix: fix bond_cb_index_jsl interface
1.6.26 fix: fix bond_cb_index_jsl interface
1.6.27 fix: fix currency_boc_sina interface
1.6.28 add: add currency_boc_safe interface
1.6.29 fix: fix stock_board_industry_name_em interface
1.6.30 fix: fix stock_info_a_code_name interface
1.6.31 fix: fix stock_gdfx_free_holding_detail_em interface
1.6.32 fix: fix get_czce_daily interface
1.6.33 fix: fix stock_report_fund_hold_detail interface
1.6.34 fix: fix fx_spot_quote interface
1.6.35 fix: fix stock_zh_index_hist_csindex interface
1.6.36 fix: fix option_finance_board interface
1.6.37 fix: remove futures_inventory_99 interface
1.6.38 add: add stock_zygc_ym interface
1.6.39 fix: fix futures_symbol_mark interface
1.6.40 add: add stock_mda_ym interface
1.6.41 add: add futures_inventory_99 interface
1.6.42 fix: fix stock_balance_sheet_by_yearly_em interface
1.6.43 fix: fix futures_inventory_99 interface
1.6.44 fix: fix futures_inventory_em interface
1.6.45 fix: fix stock_zh_index_hist_csindex interface
1.6.46 fix: fix fund_open_fund_info_em interface
1.6.47 fix: fix stock_zh_a_minute interface
1.6.48 fix: fix stock_report_disclosure interface
1.6.49 fix: fix stock_zh_a_alerts_cls interface
1.6.50 add: add stock_industry_category_cninfo interface
1.6.51 fix: fix stock_analyst_detail_em interface
1.6.52 fix: fix index_zh_a_hist interface
1.6.53 fix: fix fx_spot_quote interface
1.6.54 fix: fix stock_hsgt_hold_stock_em interface
1.6.55 fix: fix stock_gdfx_free_holding_analyse_em interface
1.6.56 fix: fix index_zh_a_hist interface
1.6.57 fix: fix stock_info_sh_name_code interface
1.6.58 fix: fix stock_gdfx_holding_analyse_em interface
1.6.59 add: add stock_industry_change_cninfo interface
1.6.60 add: add stock_telegraph_cls interface
1.6.61 fix: fix futures_shfe_warehouse_receipt interface
1.6.62 fix: fix futures_zh_spot interface
1.6.63 fix: fix fund_portfolio_em and futures_roll_yield interface
1.6.64 fix: fix index_investing_global interface
1.6.65 fix: fix bond_cb_redeem_jsl interface
1.6.66 fix: fix stock_balance_sheet_by_report_em interface
1.6.67 fix: fix stock_zh_a_alerts_cls interface
1.6.68 fix: fix stock_zh_a_minute interface
1.6.69 add: add fund_info_index_em interface
1.6.70 add: add bond_zh_hs_cov_pre_min interface
1.6.71 fix: fix bond_zh_hs_cov_pre_min interface
1.6.72 add: add futures_news_shmet interface
1.6.73 fix: fix macro_china_rmb interface
1.6.74 add: add option_cffex_zz1000_list_sina interface
1.6.75 add: add option_cffex_zz1000_spot_sina interface
1.6.76 add: add pycryptodomex library
1.6.77 fix: fix stock_telegraph_cls interface
1.6.78 fix: fix stock_telegraph_cls interface
1.6.79 fix: fix fund_rating_all interface
1.6.80 fix: fix index_investing_global interface
1.6.81 fix: fix currency_hist interface
1.6.82 fix: fix option_cffex_hs300_spot_sina interface
1.6.83 fix: fix option_dce_daily interface
1.6.84 fix: fix stock_zt_pool_em interface
1.6.85 fix: fix option_finance_board interface
1.6.86 fix: fix stock_gpzy_distribute_statistics_bank_em interface
1.6.87 fix: fix stock_ggcg_em interface
1.6.88 fix: fix option_cffex_zz1000_spot_sina interface
1.6.89 fix: fix stock_board_concept_name_ths interface
1.6.90 fix: fix macro_china_cpi_yearly interface
1.6.91 fix: fix forbes_rank interface
1.6.92 fix: fix hurun_rank interface
1.6.93 fix: fix index_vix interface
1.6.94 fix: fix macro_china_hk_market_info interface
1.6.95 fix: fix energy_oil_detail interface
1.6.96 fix: fix macro_china_bond_public interface
1.6.97 fix: fix macro_china_real_estate interface
1.6.98 fix: fix macro_china_real_estate interface
1.6.99 fix: fix macro_china_fx_gold interface
1.7.1 fix: fix fund_etf_fund_info_em interface
1.7.2 fix: fix futures_egg_price_yearly interface
1.7.3 fix: fix stock_profit_sheet_by_report_em interface
1.7.4 fix: fix stock_analyst_rank_em interface
1.7.5 fix: fix fund_fh_em interface
1.7.6 fix: fix covid_19_risk_area interface
1.7.7 add: add index_level_one_hist_sw interface
1.7.8 add: add index_style_index_hist_sw interface
1.7.9 add: add index_market_representation_hist_sw interface
1.7.10 fix: fix option_czce_daily interface
1.7.11 fix: fix bond_cash_summary_sse interface
1.7.12 fix: fix stock_repurchase_em interface
1.7.13 fix: fix stock_balance_sheet_by_yearly_em interface
1.7.14 fix: fix covid_19_risk_area interface
1.7.15 fix: fix news_economic_baidu interface
1.7.16 fix: fix crypto_js_spot interface
1.7.17 fix: fix bond_cb_jsl interface
1.7.18 fix: fix stock_lhb_jgmmtj_em interface
1.7.19 fix: fix index_value_name_funddb interface
1.7.20 fix: fix crypto_js_spot interface
1.7.21 fix: fix futures_hog_info interface
1.7.22 add: add index_investing_global_area_index_name_url interface
1.7.23 fix: fix rename futures_pig_info and futures_pig_rank interface
1.7.24 fix: fix amac_manager_classify_info interface
1.7.25 add: add news_trade_notify_dividend_baidu interface
1.7.26 add: add bond_new_composite_index_cbond interface
1.7.27 fix: fix stock_qsjy_em interface
1.7.28 fix: fix stock_info_sh_name_code interface
1.7.29 fix: fix stock_us_daily interface
1.7.30 fix: fix bond_cb_index_jsl interface
1.7.31 fix: fix stock_a_lg_indicator interface
1.7.32 fix: fix stock_a_ttm_lyr interface
1.7.33 fix: fix stock_zh_ah_daily interface
1.7.34 fix: fix bond_cb_jsl interface
1.7.35 fix: fix stock_market_fund_flow interface
1.7.36 fix: fix rename branch master to main
1.7.37 add: add sw_index_first_info interface
1.7.38 add: add sw_index_second_info interface
1.7.39 add: add stock_sgt_settlement_exchange_rate_szse interface
1.7.40 add: add stock_sgt_settlement_exchange_rate_sse interface
1.7.41 add: add stock_sgt_reference_exchange_rate_sse interface
1.7.42 add: add stock_sgt_reference_exchange_rate_szse interface
1.7.43 fix: fix stock_a_all_pb interface
1.7.44 add: add stock_allotment_cninfo interface
1.7.45 add: add stock_hk_valuation_baidu interface
1.7.46 fix: fix stock_hk_valuation_baidu interface
1.7.47 add: add stock_zh_valuation_baidu interface
1.7.48 add: add stock_zh_vote_baidu interface
1.7.49 add: add futures_news_baidu interface
1.7.50 add: add stock_hot_search_baidu interface
1.7.51 fix: fix stock_a_lg_indicator interface
1.7.52 fix: fix stock_sse_summary interface
1.7.53 add: add stock_buffett_index_lg interface
1.7.54 fix: fix stock_a_lg_indicator interface
1.7.55 add: add fx_quote_baidu interface
1.7.56 fix: fix stock_buffett_index_lg interface
1.7.57 fix: fix stock_a_high_low_statistics interface
1.7.58 fix: fix bond_cb_redeem_jsl interface
1.7.59 fix: fix stock_a_high_low_statistics interface
1.7.60 fix: fix stock_zh_a_spot_em interface
1.7.61 add: add option_50etf_qvix interface
1.7.62 add: add option_300etf_qvix interface
1.7.63 add: add option_300etf_min_qvix interface
1.7.64 add: add option_50etf_min_qvix interface
1.7.65 fix: fix futures_rule interface
1.7.66 add: add index_realtime_sw interface
1.7.67 fix: fix xincaifu_rank interface
1.7.68 fix: fix hurun_rank interface
1.7.69 add: add index_hist_sw interface
1.7.70 fix: fix index_hist_sw interface
1.7.71 add: add support for Python 3.11
1.7.72 add: add index_min_sw interface
1.7.73 fix: fix stock_zh_index_daily_tx interface
1.7.74 fix: fix futures_news_baidu interface
1.7.75 add: add index_component_sw interface
1.7.76 fix: fix macro_euro_gdp_yoy interface
1.7.77 fix: fix index_value_hist_funddb interface
1.7.78 add: add index_analysis_sw interface
1.7.79 fix: fix macro_germany interface
1.7.80 fix: fix stock_a_below_net_asset_statistics interface
1.7.81 fix: fix macro_swiss_svme interface
1.7.82 fix: fix index_analysis_daily_sw interface
1.7.83 fix: fix macro_japan interface
1.7.84 add: add bond_info_cm interface
1.7.85 fix: fix stock_board_industry_hist_em interface
1.7.86 fix: fix bond_info_cm interface
1.7.87 fix: fix macro_uk interface
1.7.88 fix: fix stock_news_em interface
1.7.89 fix: fix stock_zh_index_daily_tx interface
1.7.90 fix: fix stock_yjbb_em interface
1.7.91 fix: fix futures_price_index_nh interface
1.7.92 fix: fix fund_portfolio_hold_em interface
1.7.93 fix: fix sw_index_third_cons interface
1.7.94 fix: fix fund_portfolio_hold_em interface
1.7.95 fix: fix spot_golden_benchmark_sge interface
1.7.96 fix: fix futures_hog_info interface
1.7.97 add: add index_hog_spot_price interface
1.7.98 fix: fix stock_zh_a_gdhs interface
1.7.99 fix: fix stock_lhb_detail_daily_sina interface
1.8.1 fix: fix stock_dxsyl_em interface
1.8.2 fix: fix fund_portfolio_hold_em interface
1.8.3 fix: fix stock_pg_em interface
1.8.4 fix: fix macro_china_hgjck interface
1.8.5 fix: fix stock_a_lg_indicator interface
1.8.6 fix: fix stock_market_activity_legu interface
1.8.7 fix: fix stock_a_below_net_asset_statistics interface
1.8.8 fix: fix macro_china_gdp interface
1.8.9 fix: fix stock_a_ttm_lyr interface
1.8.10 fix: fix stock_a_all_pb interface
1.8.11 fix: fix macro_china_ppi interface
1.8.12 fix: fix stock_yjyg_em interface
1.8.13 fix: fix macro_china_new_house_price interface
1.8.14 add: add stock_board_industry_summary_ths interface
1.8.15 fix: fix stock_price_js interface
1.8.16 fix: fix macro_china_swap_rate interface
1.8.17 fix: fix macro_china_fdi interface
1.8.18 add: add stock_hsgt_fund_flow_summary_em interface
1.8.19 fix: fix stock_balance_sheet_by_yearly_em interface
1.8.20 fix: fix stock_board_concept_hist_em interface
1.8.21 fix: fix stock_board_concept_hist_em interface
1.8.22 fix: fix stock_margin_detail_szse interface
1.8.23 add: add stock_restricted_release_summary_em interface
1.8.24 fix: fix stock_ipo_benefit_ths interface
1.8.25 fix: fix stock_circulate_stock_holder interface
1.8.26 fix: fix bond_china_close_return_map interface
1.8.27 fix: fix fund_cf_em interface
1.8.28 fix: fix fund_fh_rank_em interface
1.8.29 fix: fix baidu_search_index interface
1.8.30 fix: fix index_value_name_funddb interface
1.8.31 fix: fix get_dce_daily interface
1.8.32 fix: fix js_news interface
1.8.33 fix: fix stock_hot_rank_em interface
1.8.34 add: add stock_a_gxl_lg interface
1.8.35 add: add stock_hk_gxl_lg interface
1.8.36 add: add stock_a_congestion_lg interface
1.8.37 add: add fund_stock_position_lg interface
1.8.38 fix: fix macro_cons_gold interface
1.8.39 add: add stock_board_change_em interface
1.8.40 add: add fund_balance_position_lg interface
1.8.41 add: add futures_index_ccidx interface
1.8.42 add: add get_gfex_daily interface
1.8.43 add: add stock_ebs_lg interface
1.8.44 fix: fix stock_info_bj_name_code interface
1.8.45 fix: fix calendar.json
1.8.46 fix: fix get_roll_yield_bar interface
1.8.47 add: add option_cffex_sz50_list_sina interface
1.8.48 add: add fund_etf_hist_em interface
1.8.49 fix: fix futures_comm_info interface
1.8.50 fix: fix stock_us_daily interface
1.8.51 fix: fix fortune_rank interface
1.8.52 fix: fix index_value_hist_funddb interface
1.8.53 fix: fix stock_hot_rank_wc interface
1.8.54 fix: fix get_roll_yield_bar interface
1.8.55 fix: fix macro_usa_pmi interface
1.8.56 fix: fix stock_hk_valuation_baidu interface
1.8.57 fix: fix stock_szse_summary interface
1.8.58 fix: fix get_calendar interface
1.8.59 fix: fix stock_zh_valuation_baidu interface
1.8.60 fix: fix hurun_rank interface
1.8.61 fix: fix futures_comm_info interface
1.8.62 fix: fix stock_board_industry_index_ths interface
1.8.63 fix: fix stock_cash_flow_sheet_by_report_em interface
1.8.64 fix: fix stock_ggcg_em interface
1.8.65 fix: fix get_roll_yield_bar interface
1.8.66 fix: fix python 3.7.x support
1.8.67 fix: fix python warning 3.7.x support
1.8.68 fix: fix stock_individual_fund_flow interface
1.8.69 fix: fix stock_individual_fund_flow_rank interface
1.8.70 add: add stock_market_pe_lg interface
1.8.71 add: add stock_zygc_em interface
1.8.72 fix: fix drewry_wci_index interface
1.8.73 add: add stock_zyjs_ths interface
1.8.74 fix: fix drewry_wci_index interface
1.8.75 add: add stock_cy_a_spot_em interface
1.8.76 remove: remove js_news and ws interface
1.8.77 fix: fix stock_analyst_rank_em interface
1.8.78 fix: fix stock_profit_forecast interface
1.8.79 fix: fix stock_hk_valuation_baidu interface
1.8.80 fix: fix stock_profit_forecast interface
1.8.81 fix: fix futures_hog_info interface
1.8.82 fix: fix stock_fund_stock_holder interface
1.8.83 fix: fix stock_info_sh_name_code interface
1.8.84 remove: remove stock_zh_a_scr_report interface
1.8.85 fix: fix stock_info_sh_name_code interface
1.8.86 fix: fix stock_info_sh_delist interface
1.8.87 fix: fix stock_info_sz_change_name interface
1.8.88 fix: fix stock_info_sz_delist interface
1.8.89 fix: fix sunrise_city_list interface
1.8.90 fix: fix bond_info_detail_cm interface
1.8.91 fix: fix sunrise_monthly interface
1.8.92 fix: fix stock_institute_hold interface
1.8.93 fix: fix stock_gdfx_holding_detail_em interface
1.8.94 fix: fix Dockerfile
1.8.95 fix: fix index_zh_a_hist interface
1.8.96 fix: fix option_finance_board interface
1.8.97 fix: fix futures_egg_price_yearly interface
1.8.98 fix: fix stock_info_sz_delist interface
1.8.99 add: add futures_news_shmet interface
1.9.1 fix: fix index_value_name_funddb interface
1.9.2 fix: fix stock_xgsglb_em interface
1.9.3 fix: fix fx_quote_baidu interface
1.9.4 fix: fix drewry_wci_index interface
1.9.5 fix: fix stock_info_a_code_name interface
1.9.6 fix: fix futures_hog_info interface
1.9.7 add: add stock_profit_forecast_ths interface
1.9.8 fix: fix stock_hk_valuation_baidu interface
1.9.9 add: add macro_shipping_bci interface
1.9.10 add: add macro_shipping_bcti interface
1.9.11 add: add stock_sector_fund_flow_hist interface
1.9.12 fix: fix stock_hot_rank_wc interface
1.9.13 fix: fix stock_zh_valuation_baidu interface
1.9.14 fix: fix option_risk_analysis_em interface
1.9.15 fix: fix stock_hk_daily interface
1.9.16 fix: fix stock_financial_abstract interface
1.9.17 add: add stock_board_industry_spot_em interface
1.9.18 fix: fix macro_china_market_margin_sh interface
1.9.19 fix: fix macro_cnbs interface
1.9.20 fix: fix fund_financial_fund_info_em interface
1.9.21 fix: fix fund_financial_fund_info_em interface
1.9.22 fix: fix fund_hk_fund_hist_em interface
1.9.23 fix: fix bond_cb_redeem_jsl interface
1.9.24 fix: fix bond_cb_adj_logs_jsl interface
1.9.25 add: add stock_hk_hot_rank_em interface
1.9.26 fix: fix bond_cb_jsl interface
1.9.27 fix: fix fund_exchange_rank_em interface
1.9.28 fix: fix stock_financial_report_sina interface
1.9.29 fix: fix stock_a_lg_indicator interface
1.9.30 fix: fix stock_a_lg_indicator interface
1.9.31 fix: fix amac_fund_info interface
1.9.32 fix: fix bank_fjcf_table_detail interface
1.9.33 add: add stock_hk_main_board_spot_em interface
1.9.34 fix: fix stock_zh_a_tick_tx_js interface
1.9.35 fix: fix stock_a_lg_indicator interface
1.9.36 fix: fix stock_market_pe_lg interface
1.9.37 fix: fix stock_hk_indicator_eniu interface
1.9.38 fix: fix stock_a_lg_indicator interface
1.9.39 fix: fix fund_stock_position_lg interface
1.9.40 fix: fix stock_profit_forecast_em interface
1.9.41 fix: fix stock_a_indicator_lg interface
1.9.42 add: add stock_bid_ask_em interface
1.9.43 fix: fix stock_a_congestion_lg interface
1.9.44 fix: fix stock_a_high_low_statistics interface
1.9.45 add: add stock_fhps_detail_ths interface
1.9.46 fix: fix stock_a_gxl_lg interface
1.9.47 fix: fix option_dce_daily interface
1.9.48 fix: fix index_stock_cons interface
1.9.49 add: add stock_lhb_yybph_em interface
1.9.50 fix: fix stock_a_all_pb interface
1.9.51 fix: fix get_shfe_daily interface
1.9.52 fix: fix get_shfe_rank_table interface
1.9.53 fix: fix get_ine_daily interface
1.9.54 fix: fix stock_board_concept_cons_ths interface
1.9.55 fix: fix stock_zh_valuation_baidu interface
1.9.56 fix: fix get_receipt interface
1.9.57 fix: fix stock_lhb_detail_em interface
1.9.58 add: add option_gfex_daily interface
1.9.59 fix: fix stock_hot_search_baidu interface
1.9.60 add: add stock_hk_fhpx_detail_ths interface
1.9.61 fix: fix stock_lhb_detail_daily_sina interface
1.9.62 fix: fix bond_zh_us_rate interface
1.9.63 fix: fix get_czce_rank_table interface
1.9.64 fix: fix stock_a_indicator_lg interface
1.9.65 fix: fix stock_hot_search_baidu interface
1.9.66 fix: fix match_main_contract interface
1.9.67 fix: fix futures_zh_daily_sina interface
1.9.68 fix: fix stock_lh_yyb_capital interface
1.9.69 fix: fix stock_lh_yyb_capital interface
1.9.70 fix: fix stock_szse_sector_summary interface
1.9.71 fix: fix stock_lh_yyb_most interface
1.9.72 fix: fix fund_manager interface
1.9.73 add: add bond_zh_cov_info_ths interface
1.9.74 fix: fix get_shfe_rank_table interface
1.9.75 fix: fix stock_board_industry_index_ths interface
1.9.76 fix: fix stock_sector_detail interface
1.9.77 fix: fix stock_hot_rank_wc interface
1.9.78 fix: fix macro_usa_gdp_monthly interface
1.9.79 fix: fix stock_sse_deal_daily interface
1.9.80 fix: fix futures_spot_price interface
1.9.81 add: add stock_hk_index_spot_sina interface
1.9.82 fix: fix currency_boc_safe interface
1.9.83 add: add stock_concept_fund_flow_hist interface
1.9.84 fix: fix stock_hk_fhpx_detail_ths interface
1.9.85 fix: fix option_dce_daily interface
1.9.86 fix: fix index_kq_fz interface
1.9.87 add: add option_minute_em interface
1.9.88 fix: fix setup.py
1.9.89 fix: fix index_kq_fz interface
1.9.90 fix: fix stock_sse_deal_daily interface
1.9.91 add: add stock_financial_abstract_ths interface
1.9.92 fix: fix article_ff_crr interface
1.9.93 fix: fix index_level_one_hist_sw interface
1.9.94 fix: fix stock_a_indicator_lg interface
1.9.95 fix: fix stock_zh_index_hist_csindex interface
1.9.96 fix: fix stock_hold_control_cninfo interface
1.9.97 fix: fix stock_industry_category_cninfo interface
1.9.98 fix: fix stock_hold_control_cninfo interface
1.9.99 fix: fix stock_hold_num_cninfo interface
1.10.1 fix: fix stock_hold_control_cninfo interface
1.10.2 fix: fix stock_gdfx_holding_detail_em interface
1.10.3 fix: fix stock_gdfx_holding_analyse_em interface
1.10.4 fix: fix futures_return_index_nh interface
1.10.5 fix: fix index_level_one_hist_sw interface
1.10.6 fix: fix futures_nh_volatility_index interface
1.10.7 fix: fix option_finance_board interface
1.10.8 fix: fix futures_volatility_index_nh interface
1.10.9 fix: fix bond_zh_hs_cov_min interface
1.10.10 fix: fix stock_zh_a_hist interface
1.10.11 fix: fix stock_zh_a_hist_pre_min_em interface
1.10.12 fix: fix bond_cb_adj_logs_jsl interface
1.10.13 fix: fix stock_share_change_cninfo interface
1.10.14 fix: fix bond_zh_hs_cov_min interface
1.10.15 fix: fix bond_zh_hs_cov_pre_min interface
1.10.16 fix: fix bond_zh_hs_cov_min interface
1.10.17 fix: fix stock_allotment_cninfo interface
1.10.18 fix: fix index_yw interface
1.10.19 fix: fix bond_treasure_issue_cninfo interface
1.10.20 fix: fix stock_new_gh_cninfo interface
1.10.21 fix: fix fund_report_stock_cninfo interface
1.10.22 fix: fix macro_china_cpi_monthly interface
1.10.23 fix: fix index_kq_fz interface
1.10.24 fix: fix stock_zh_a_daily interface
1.10.25 fix: fix index_sugar_msweet interface
1.10.26 add: add stock_hot_up_em interface
1.10.27 fix: fix stock_hot_up_em interface
1.10.28 fix: fix stock_hot_up_em interface
1.10.29 fix: fix stock_zh_index_daily_em interface
1.10.30 fix: fix stock_info_sz_name_code interface
1.10.31 fix: fix zh_subscribe_exchange_symbol interface
1.10.32 fix: fix get_cffex_daily interface
1.10.33 fix: fix index_sugar_msweet interface
1.10.34 fix: fix futures_display_main_sina interface
1.10.35 add: add get_gfex_receipt interface
1.10.36 fix: fix stock_sy_profile_em interface
1.10.37 rem: rem index_stock_hist interface
1.10.38 fix: fix stock_board_industry_hist_min_em interface
1.10.39 fix: fix stock_board_concept_hist_min_em interface
1.10.40 fix: fix futures_news_baidu interface
1.10.41 add: add fund_lof_hist_em interface
1.10.42 fix: fix fund_rating_all interface
1.10.43 rem: rem index_vix interface
1.10.44 fix: fix get_shfe_rank_table interface
1.10.45 fix: fix stock_zh_a_minute interface
1.10.46 fix: fix index_value_hist_funddb interface
1.10.47 add: add stock_esg_rate_sina interface
1.10.48 add: add stock_esg_hz_sina interface
1.10.49 fix: fix stock_hot_rank_em interface
1.10.50 fix: fix car_energy_sale_cpca interface
1.10.51 fix: fix fund_money_rank_em interface
1.10.52 fix: fix stock_financial_hk_report_em interface
1.10.53 fix: fix index_stock_cons_csindex interface
1.10.54 fix: fix macro_usa_core_cpi_monthly interface
1.10.55 fix: fix macro_usa_personal_spending interface
1.10.56 fix: fix stock_zh_b_daily interface
1.10.57 fix: fix stock_zh_valuation_baidu interface
1.10.58 fix: fix fund_etf_hist_em interface
1.10.59 add: add fund_announcement_personnel_em interface
1.10.60 add: add macro_usa_cpi_yoy interface
1.10.61 fix: fix macro_cnbs interface
1.10.62 fix: fix index_hist_sw interface
1.10.63 fix: fix stock_esg_hz_sina interface
1.10.64 fix: fix stock_zh_b_spot interface
1.10.65 fix: fix macro_china_lpr interface
1.10.66 fix: fix stock_financial_report_sina interface
1.10.67 rem: rem futures_egg_price_yearly interface
1.10.68 fix: fix option_gfex_daily interface
1.10.69 fix: fix currency_latest interface
1.10.70 fix: fix stock_zh_a_hist interface
1.10.71 fix: fix stock_us_hist interface
1.10.72 fix: fix stock_financial_hk_report_em interface
1.10.73 add: add stock_irm_cninfo interface
1.10.74 add: add stock_sns_sseinfo interface
1.10.75 add: add macro_china_urban_unemployment interface
1.10.76 fix: fix stock_notice_report interface
1.10.77 add: add bond_cb_profile_sina interface
1.10.78 fix: fix get_cffex_rank_table interface
1.10.79 add: add stock_hold_management_detail_em interface
1.10.80 fix: fix macro_china_gyzjz interface
1.10.81 fix: fix stock_bid_ask_em interface
1.10.82 fix: fix currency_boc_sina interface
1.10.83 add: add stock_industry_clf_hist_sw interface
1.10.84 fix: fix stock_us_fundamental interface
1.10.85 fix: fix stock_hot_rank_wc interface
1.10.86 add: add stock_gddh_em interface
1.10.87 add: add stock_zdhtmx_em interface
1.10.88 add: add stock_research_report_em interface
1.10.89 add: add stock_share_hold_change_bse interface
1.10.90 fix: fix futures_comex_inventory interface
1.10.91 fix: fix stock_share_hold_change_szse interface
1.10.92 fix: fix stock_individual_fund_flow interface
1.10.93 add: add stock_ipo_summary_cninfo interface
1.10.94 add: add macro_china_nbs_nation interface
1.10.95 fix: fix crypto_bitcoin_cme interface
1.10.96 fix: fix stock_hk_daily interface
1.10.97 fix: fix stock_financial_analysis_indicator interface
1.10.98 fix: fix get_cffex_rank_table interface
1.10.99 fix: fix crypto_bitcoin_cme interface
1.11.1 add: add index_us_stock_sina interface
1.11.2 fix: fix stock_a_below_net_asset_statistics interface
1.11.3 fix: fix stock_a_high_low_statistics interface
1.11.4 fix: fix bond_cb_profile_sina interface
1.11.5 fix: fix macro_china_hk_cpi interface
1.11.6 fix: fix futures_main_sina interface
1.11.7 fix: fix get_futures_daily interface
1.11.8 fix: fix news_economic_baidu interface
1.11.9 fix: fix currency_boc_safe interface
1.11.10 fix: fix bond_new_composite_index_cbond interface
1.11.11 fix: fix spot_hist_sge interface
1.11.12 fix: fix stock_board_concept_hist_ths interface
1.11.13 fix: fix futures_comm_info interface
1.11.14 fix: fix migration_area_baidu interface
1.11.15 fix: fix stock_dividend_cninfo interface
1.11.16 fix: fix stock_dividend_cninfo interface
1.11.17 fix: fix futures_spot_price_daily interface
1.11.18 fix: fix get_rank_sum_daily interface
1.11.19 fix: fix drewry_wci_index interface
1.11.20 fix: fix option_dce_daily interface
1.11.21 fix: fix get_dce_daily interface
1.11.22 fix: fix option_dce_daily interface
1.11.23 fix: fix macro_china_society_traffic_volume interface
1.11.24 fix: fix macro_china_postal_telecommunicational interface
1.11.25 fix: fix macro_china_central_bank_balance interface
1.11.26 fix: fix macro_china_supply_of_money interface
1.11.27 fix: fix stock_margin_detail_szse interface
1.11.28 fix: fix stock_margin_detail_szse interface
1.11.29 fix: fix bond_new_composite_index_cbond interface
1.11.30 fix: fix stock_zh_a_st_em interface
1.11.31 fix: fix futures_dce_warehouse_receipt interface
1.11.32 add: add stock_margin_ratio_pa interface
1.11.33 add: add stock_intraday_em interface
1.11.34 add: add stock_board_concept_graph_ths interface
1.11.35 fix: fix stock_board_concept_hist_ths interface
1.11.36 add: add stock_fear_greed_funddb interface
1.11.37 fix: fix index_fear_greed_funddb interface
1.11.38 fix: fix setup.py interface
1.11.39 fix: fix index_option_50etf_qvix interface
1.11.40 fix: fix index_option_300etf_qvix interface
1.11.41 fix: fix index_weibo_sina interface
1.11.42 fix: fix stock_gpzy_pledge_ratio_em interface
1.11.43 fix: fix get_futures_daily interface
1.11.44 add: add stock_cyq_em interface
1.11.45 add: add stock_balance_sheet_by_report_delisted_em interface
1.11.46 add: add akracer support
1.11.47 add: add akracer 0.0.8 support
1.11.48 fix: fix installation.md
1.11.49 add: add aarch64 support
1.11.50 fix: fix amac_fund_abs support
1.11.51 fix: fix stock_zh_a_daily interface
1.11.52 fix: fix fund_scale_change_em interface
1.11.53 add: add stock_zh_a_hist_tx interface
1.11.54 fix: fix fund_portfolio_hold_em interface
1.11.55 fix: fix fund_portfolio_bond_hold_em interface
1.11.56 fix: fix stock_balance_sheet_by_report_delisted_em interface
1.11.57 fix: fix stock_zt_pool_em interface
1.11.58 fix: fix bond_china_close_return interface
1.11.59 fix: fix fund_portfolio_change_em interface
1.11.60 fix: fix bond_china_close_return interface
1.11.61 fix: fix fund_manager_em interface
1.11.62 fix: fix stock_zt_pool_dtgc_em interface
1.11.63 fix: fix fund_scale_open_sina interface
1.11.64 fix: fix futures_settlement_price_sgx interface
1.11.65 fix: fix futures_index_ccidx interface
1.11.66 fix: fix fund_scale_structured_sina interface
1.11.67 fix: fix currency_boc_sina interface
1.11.68 fix: fix fund_aum_em interface
1.11.69 add: add futures_gfex_position_rank interface
1.11.70 fix: fix futures_gfex_position_rank interface
1.11.71 fix: fix stock_balance_sheet_by_report_em interface
1.11.72 fix: fix get_rank_sum_daily interface
1.11.73 fix: fix futures_comex_inventory interface
1.11.74 fix: fix stock_comment_em interface
1.11.75 fix: fix futures_comex_inventory interface
1.11.76 fix: fix option_czce_daily interface
1.11.77 fix: fix futures_zh_spot interface
1.11.78 add: add stock_financial_benefit_ths interface
1.11.79 fix: fix get_receipt interface
1.11.80 fix: fix stock_cash_flow_sheet_by_report_em interface
1.11.81 fix: fix stock_gdfx_free_holding_detail_em interface
1.11.82 fix: fix bond_zh_us_rate interface
1.11.83 fix: fix stock_zt_pool_strong_em interface
1.11.84 fix: fix fund_name_em interface
1.11.85 fix: fix stock_market_activity_legu interface
1.11.86 fix: fix stock_telegraph_cls interface
1.11.87 fix: fix futures_board_index_nh interface
1.11.88 fix: fix macro_china_swap_rate interface
1.11.89 fix: fix bond_zh_us_rate interface
1.11.90 fix: fix futures_rule interface
1.11.91 fix: remove stock_us_fundamental interface
1.11.92 fix: fix get_gfex_receipt interface
1.11.93 fix: fix stock_zh_a_hist_pre_min_em interface
1.11.94 fix: fix index_zh_a_hist_min_em interface
1.11.95 fix: fix fund_etf_hist_min_em interface
1.11.96 fix: fix fund_rating_all interface
1.11.97 add: add stock_zh_a_disclosure_report_cninfo interface
1.11.98 fix: fix stock_zh_a_disclosure_report_cninfo interface
1.11.99 fix: fix stock_zh_index_spot interface
1.12.1 fix: fix futures_comm_info interface
1.12.2 fix: fix hurun_rank interface
1.12.3 fix: fix stock_gdfx_free_holding_teamwork_em interface
1.12.4 fix: fix tool_trade_date_hist_sina interface
1.12.5 fix: fix stock_zh_a_gdhs interface
1.12.6 fix: fix fund_open_fund_info_em interface
1.12.7 fix: fix option_gfex_daily interface
1.12.8 fix: fix fund_open_fund_info_em interface
1.12.9 add: add fund_individual_basic_info_xq interface
1.12.10 fix: fix stock_add_stock interface
1.12.11 add: add stock_zh_index_spot_em interface
1.12.12 fix: fix stock_zh_index_daily interface
1.12.13 fix: fix index_stock_cons_csindex interface
1.12.14 add: add stock_hk_profit_forecast_et interface
1.12.15 fix: fix stock_hk_profit_forecast_et interface
1.12.16 fix: fix stock_hot_follow_xq interface
1.12.17 fix: fix option_current_em interface
1.12.18 fix: fix stock_board_industry_index_ths interface
1.12.19 fix: fix stock_hk_profit_forecast_et interface
1.12.20 fix: fix futures_inventory_99 interface
1.12.21 fix: fix stock_hsgt_hold_stock_em interface
1.12.22 fix: fix stock_hsgt_board_rank_em interface
1.12.23 fix: fix fund_etf_hist_min_em interface
1.12.24 fix: fix stock_hk_index_spot_em interface
1.12.25 fix: fix fund_individual_basic_info_xq interface
1.12.26 fix: fix index_stock_info interface
1.12.27 fix: fix stock_hk_fhpx_detail_ths interface
1.12.28 fix: fix futures_foreign_commodity_realtime interface
1.12.29 add: add stock_individual_spot_xq interface
1.12.30 fix: fix futures_settlement_price_sgx interface
1.12.31 add: add futures_global_em interface
1.12.32 fix: fix energy_oil_hist interface
1.12.33 fix: fix futures_global_em interface
1.12.34 fix: fix repo_rate_hist interface
1.12.35 fix: fix article_epu_index interface
1.12.36 fix: fix bond_china_close_return interface
1.12.37 fix: fix futures_delivery_shfe interface
1.12.38 fix: fix futures_to_spot_dce interface
1.12.39 fix: fix futures_gfex_warehouse_receipt interface
1.12.40 fix: fix futures_to_spot_dce interface
1.12.41 fix: fix sw_index_third_cons interface
1.12.42 fix: fix stock_news_em interface
1.12.43 fix: fix macro_china_market_margin_sh interface
1.12.44 fix: fix stock_zh_ah_daily interface
1.12.45 fix: fix stock_individual_spot_xq interface
1.12.46 fix: fix futures_contract_detail interface
1.12.47 fix: fix stock_zh_ah_daily interface
1.12.48 fix: fix option_minute_em interface
1.12.49 fix: fix stock_dxsyl_em interface
1.12.50 fix: fix bond_china_close_return interface
1.12.51 add: add stock_hsgt_fund_min_em interface
1.12.52 fix: fix stock_rank_cxg_ths interface
1.12.53 fix: fix stock_rank_xzjp_ths interface
1.12.54 fix: fix stock_gpzy_pledge_ratio_detail_em interface
1.12.55 fix: fix stock_us_hist interface
1.12.56 fix: fix stock_a_indicator_lg interface
1.12.57 fix: fix bank_fjcf_table_detail interface
1.12.58 fix: fix stock_ipo_summary_cninfo interface
1.12.59 fix: fix movie_boxoffice_realtime interface
1.12.60 fix: fix movie_boxoffice_daily interface
1.12.61 fix: fix stock_bid_ask_em interface
1.12.62 fix: fix stock_fund_flow_individual interface
1.12.63 add: add akqmt interface
1.12.64 fix: fix stock_board_industry_index_ths interface
1.12.65 fix: fix futures_foreign_commodity_realtime interface
1.12.66 fix: fix stock_board_industry_hist_em interface
1.12.67 fix: fix index_hist_sw interface
1.12.68 fix: fix option_finance_board interface
1.12.69 fix: fix futures_hold_pos_sina interface
1.12.70 fix: fix stock_lhb_detail_daily_sina interface
1.12.71 fix: fix stock_zh_ah_spot interface
1.12.72 fix: fix stock_hot_rank_wc interface
1.12.73 fix: fix stock_individual_spot_xq interface
1.12.74 add: add futures_contract_info_czce interface
1.12.75 add: add futures_contract_info_ine interface
1.12.76 fix: fix bond_zh_hs_spot interface
1.12.77 fix: fix futures_contract_info_shfe interface
1.12.78 fix: fix stock_info_sh_delist interface
1.12.79 fix: fix futures_main_sina interface
1.12.80 fix: fix get_czce_daily interface
1.12.81 fix: fix macro_china_bond_public interface
1.12.82 fix: fix stock_tfp_em interface
1.12.83 fix: fix stock_sector_fund_flow_rank interface
1.12.84 fix: fix stock_market_fund_flow interface
1.12.85 fix: fix stock_sector_fund_flow_summary interface
1.12.86 fix: fix fund_etf_spot_em interface
1.12.87 fix: fix fortune_rank interface
1.12.88 fix: fix fund_etf_spot_em interface
1.12.89 fix: fix bond_china_yield interface
1.12.90 fix: fix fund_etf_spot_em interface
1.12.91 add: add stock_info_global_em interface
1.12.92 fix: fix fund_etf_hist_min_em interface
1.12.93 fix: fix bond_debt_nafmii interface
1.12.94 fix: fix stock_hk_index_daily_em interface
1.12.95 add: add futures_hog_core interface
1.12.96 fix: fix stock_bid_ask_em interface
1.12.97 fix: fix stock_zh_a_hist_min_em interface
1.12.98 fix: fix bond_zh_cov interface
1.12.99 fix: fix index_hog_spot_price interface
1.13.1 fix: fix futures_spot_stock interface
1.13.2 add: add stock_main_fund_flow interface
1.13.3 fix: fix stock_main_fund_flow interface
1.13.4 fix: fix stock_individual_spot_xq interface
1.13.5 fix: fix stock_main_fund_flow interface
1.13.6 fix: fix stock_board_concept_name_ths interface
1.13.7 add: add futures_fees_info interface
1.13.8 fix: fix fund_etf_hist_em interface
1.13.9 chore: remove pyarrow deps
1.13.10 fix: fix news_trade_notify_dividend_baidu interface
1.13.11 fix: fix option_minute_em interface
1.13.12 fix: fix stock_zyjs_ths interface
1.13.13 fix: fix car_market_cpca interface
1.13.14 fix: fix futures_fees_info interface
1.13.15 add: add car_market_man_rank_cpca interface
1.13.16 add: add car_market_cate_cpca interface
1.13.17 fix: fix stock_zcfz_em interface
1.13.18 fix: fix macro_china_pmi_yearly interface
1.13.19 add: add car_market_country_cpca interface
1.13.20 fix: fix stock_zh_a_disclosure_report_cninfo interface
1.13.21 fix: fix stock_yjkb_em interface
1.13.22 fix: fix amac_manager_cancelled_info interface
1.13.23 add: add macro_usa_cme_merchant_goods_holding interface
1.13.24 fix: fix futures_spot_sys interface
1.13.25 fix: fix futures_zh_daily_sina interface
1.13.26 fix: fix option_sse_minute_sina interface
1.13.27 add: add stock_esg_msci_sina interface
1.13.28 fix: fix stock_restricted_release_queue_em interface
1.13.29 fix: fix stock_esg_msci_sina interface
1.13.30 fix: fix futures_contract_info_shfe interface
1.13.31 fix: fix stock_individual_spot_xq interface
1.13.32 fix: fix futures_contract_info_czce interface
1.13.33 fix: fix index_realtime_fund_sw interface
1.13.34 fix: fix bank_fjcf_table_detail interface
1.13.35 fix: fix stock_margin_szse interface
1.13.36 fix: fix stock_hsgt_hist_em interface
1.13.37 fix: fix stock_hk_index_daily_sina interface
1.13.38 fix: fix stock_market_activity_legu interface
1.13.39 add: add index_news_sentiment_scope interface
1.13.40 fix: fix index_fear_greed_funddb interface
1.13.41 fix: fix stock_sy_hy_em interface
1.13.42 fix: fix index_fear_greed_funddb interface
1.13.43 fix: fix stock_account_statistics_em interface
1.13.44 fix: fix stock_lhb_stock_statistic_em interface
1.13.45 fix: fix futures_stock_shfe_js interface
1.13.46 fix: fix futures_stock_shfe_js interface
1.13.47 fix: fix stock_a_indicator_lg interface
1.13.48 fix: fix stock_hk_indicator_eniu interface
1.13.49 fix: fix stock_ipo_summary_cninfo interface
1.13.50 fix: fix news_cctv interface
1.13.51 fix: fix stock_market_activity_legu interface
1.13.52 fix: fix stock_market_pb_lg interface
1.13.53 fix: fix stock_index_pe_lg interface
1.13.54 fix: fix stock_tfp_em interface
1.13.55 fix: fix sunrise_monthly interface
1.13.56 fix: fix currency_boc_safe interface
1.13.57 fix: fix stock_a_below_net_asset_statistics interface
1.13.58 fix: fix stock_lhb_jgmmtj_em interface
1.13.59 fix: fix stock_lhb_jgstatistic_em interface
1.13.60 fix: fix stock_zh_a_disclosure_report_cninfo interface
1.13.61 fix: fix stock_lhb_hyyyb_em interface
1.13.62 fix: fix index_fear_greed_funddb interface
1.13.63 fix: fix index_detail_hist_cni interface
1.13.64 fix: fix stock_lh_yyb_most interface
1.13.65 fix: fix stock_financial_report_sina interface
1.13.66 fix: fix stock_lhb_yytj_sina interface
1.13.67 fix: fix bond_info_cm interface
1.13.68 fix: fix rate_interbank interface
1.13.69 fix: fix get_shfe_rank_table interface
1.13.70 fix: fix stock_irm_cninfo interface
1.13.71 fix: fix stock_fhps_detail_ths interface
1.13.72 fix: fix futures_contract_info_shfe interface
1.13.73 fix: fix futures_shfe_warehouse_receipt interface
1.13.74 add: add macro_info_ws interface
1.13.75 add: add spot_price_qh interface
1.13.76 fix: fix macro_china_lpr interface
1.13.77 fix: fix stock_news_em interface
1.13.78 fix: fix futures_gfex_position_rank interface
1.13.79 fix: fix stock_industry_category_cninfo interface
1.13.80 fix: fix stock_irm_cninfo interface
1.13.81 fix: fix futures_dce_position_rank interface
1.13.82 fix: fix futures_dce_position_rank interface
1.13.83 fix: fix stock_balance_sheet_by_report_em interface
1.13.84 fix: fix index_hist_sw interface
1.13.85 fix: fix stock_news_em interface
1.13.86 fix: fix futures_foreign_commodity_realtime interface
1.13.87 fix: fix index_detail_cni interface
1.13.88 fix: fix index_price_cflp interface
1.13.89 fix: fix stock_zh_index_daily interface
1.13.90 fix: fix stock_zh_valuation_baidu interface
1.13.91 fix: fix stock_buffett_index_lg interface
1.13.92 fix: fix bond_china_close_return interface
1.13.93 add: add index_neei_cx interface
1.13.94 fix: fix stock_share_change_cninfo interface
1.13.95 fix: fix stock_allotment_cninfo interface
1.13.96 fix: fix stock_dividend_cninfo interface
1.13.97 fix: fix fund_portfolio_hold_em interface
1.13.98 fix: fix stock_financial_analysis_indicator interface
1.13.99 fix: fix macro_china_swap_rate interface
1.14.1 fix: fix energy_carbon_hb interface
1.14.2 fix: fix fund_portfolio_hold_em interface
1.14.3 fix: fix stock_industry_clf_hist_sw interface
1.14.4 add: add stock_margin_account_info interface
1.14.5 fix: fix stock_margin_account_info interface
1.14.6 fix: fix stock_register_kcb interface
1.14.7 fix: fix index_stock_info interface
1.14.8 add: add stock_register_sz interface
1.14.9 fix: fix bond_zh_hs_spot interface
1.14.10 fix: fix bond_cov_issue_cninfo interface
1.14.11 fix: fix bond_treasure_issue_cninfo interface
1.14.12 fix: fix get_tqdm function
1.14.13 fix: fix option_minute_em interface
1.14.14 fix: fix option_shfe_daily interface
1.14.15 fix: fix energy_carbon_domestic interface
1.14.16 fix: fix index_hist_sw interface
1.14.17 fix: fix stock_board_industry_summary_ths interface
1.14.18 fix: fix currency_pair_map interface
1.14.19 fix: fix bond_china_close_return interface
1.14.20 fix: fix option_risk_indicator_sse interface
1.14.21 fix: fix stock_info_global_cls interface
1.14.22 fix: fix macro_china_nbs_nation interface
1.14.23 fix: fix macro_china_nbs_nation interface
1.14.24 fix: fix macro_china_bond_public interface
1.14.25 add: add option_comm_info interface
1.14.26 fix: fix futures_fees_info interface
1.14.27 fix: fix nlp_ownthink interface
1.14.28 fix: fix news_trade_notify_dividend_baidu interface
1.14.29 fix: fix stock_individual_spot_xq interface
1.14.30 fix: fix stock_us_hist_min_em interface
1.14.31 fix: fix option_shfe_daily interface
1.14.32 add: add stock_concept_cons_futu interface
1.14.33 fix: fix stock_concept_cons_futu interface
1.14.34 add: add macro_rmb_loan interface
1.14.35 add: add macro_rmb_deposit interface
1.14.36 fix: fix option_czce_daily interface
1.14.37 fix: fix stock_zh_kcb_report_em interface
1.14.38 fix: fix stock_industry_clf_hist_sw interface
1.14.39 fix: fix stock_zh_b_daily interface
1.14.40 fix: fix fund_open_fund_rank_em interface
1.14.41 fix: fix fund_report_asset_allocation_cninfo interface
1.14.42 fix: fix stock_new_gh_cninfo interface
1.14.43 fix: fix stock_share_change_cninfo interface
1.14.44 fix: fix stock_hk_famous_spot_em interface
1.14.45 fix: fix option_lhb_em interface
1.14.46 add: add spot_hog_soozhu interface
1.14.47 fix: fix spot_hog_soozhu interface
1.14.48 add: add spot_hog_year_trend_soozhu interface
1.14.49 fix: fix fortune_rank interface
1.14.50 add: add spot_hog_lean_price_soozhu interface
1.14.51 add: add stock_news_main_cx interface
1.14.52 fix: fix stock_esg_hz_sina interface
1.14.53 add: add spot_hog_three_way_soozhu interface
1.14.54 fix: fix stock_individual_info_em interface
1.14.55 add: add spot_hog_crossbred_soozhu interface
1.14.56 add: add spot_corn_price_soozhu interface
1.14.57 add: add spot_soybean_price_soozhu interface
1.14.58 add: add spot_mixed_feed_soozhu interface
1.14.59 fix: fix macro_cnbs interface
1.14.60 fix: fix bond_zh_cov_info_ths interface
1.14.61 fix: fix stock_fund_flow_individual interface
1.14.62 fix: fix stock_zt_pool_em interface
1.14.63 add: add spot_quotations_sge interface
1.14.64 fix: fix stock_board_industry_spot_em interface
1.14.65 fix: fix option_dce_daily interface
1.14.66 fix: fix stock_profit_forecast_ths interface
1.14.67 fix: fix futures_foreign_commodity_realtime interface
1.14.68 fix: fix fund_scale_open_sina interface
1.14.69 fix: fix stock_zygc_ym interface
1.14.70 fix: fix setup.py
1.14.71 fix: fix stock_mda_ym interface
1.14.72 fix: fix fund_etf_hist_min_em interface
1.14.73 fix: fix stock_gpzy_profile_em interface
1.14.74 fix: fix stock_gpzy_pledge_ratio_em interface
1.14.75 fix: fix stock_sy_hy_em interface
1.14.76 fix: fix stock_sy_em interface
1.14.77 fix: fix stock_zh_b_daily interface
1.14.78 fix: fix stock_analyst_rank_em interface
1.14.79 add: add stock_zcfz_bj_em interface
1.14.80 fix: fix stock_hot_rank_wc interface
1.14.81 fix: fix stock_hsgt_hist_em interface
1.14.82 fix: fix stock_comment_detail_scrd_desire_daily_em interface
1.14.83 fix: fix stock_comment_detail_zhpj_lspf_em interface
1.14.84 fix: fix drewry_wci_index interface
1.14.85 fix: fix stock_profit_forecast_em interface
1.14.86 fix: fix stock_comment_detail_scrd_focus_em interface
1.14.87 fix: fix stock_hot_search_baidu interface
1.14.88 fix: fix stock_hot_rank_relate_em interface
1.14.89 fix: fix bond_spot_deal interface
1.14.90 fix: fix stock_board_change_em interface
1.14.91 fix: fix stock_history_dividend interface
1.14.92 add: add qdii_a_index_jsl interface
1.14.93 fix: fix stock_zt_pool_em interface
1.14.94 fix: fix stock_zt_pool_strong_em interface
1.14.95 fix: fix stock_zt_pool_sub_new_em interface
1.14.96 fix: fix stock_zt_pool_sub_new_em interface
1.14.97 fix: fix stock_profile_cninfo interface
1.14.98 fix: fix futures_hold_pos_sina interface
1.14.99 fix: fix stock_a_ttm_lyr interface
1.15.1 fix: fix stock_a_all_pb interface
1.15.2 fix: fix stock_index_pe_lg interface
1.15.3 fix: fix stock_share_change_cninfo interface
1.15.4 fix: fix stock_allotment_cninfo interface
1.15.5 fix: fix stock_individual_spot_xq interface
1.15.6 fix: fix qdii_e_index_jsl interface
1.15.7 fix: fix index_hist_sw interface
1.15.8 fix: fix fund_individual_basic_info_xq interface
1.15.9 fix: fix index_analysis_weekly_sw interface
1.15.10 add: add volatility_yz_rv indicator
1.15.11 fix: fix stock_individual_spot_xq interface
1.15.12 fix: fix stock_shareholder_change_ths interface
1.15.13 fix: fix stock_inner_trade_xq interface
1.15.14 fix: fix macro_bank_usa_interest_rate interface
1.15.15 add: add macro_bank_china_interest_rate interface
1.15.16 fix: fix macro_bank_usa_interest_rate interface
1.15.17 fix: fix news_trade_notify_dividend_baidu interface
1.15.18 fix: fix stock_share_hold_change_sse interface
1.15.19 fix: fix stock_share_hold_change_szse interface
1.15.20 fix: fix rv_from_stock_zh_a_hist_min_em interface
1.15.21 fix: fix get_futures_daily interface
1.15.22 fix: fix air_quality_hebei interface
1.15.23 fix: fix stock_sector_fund_flow_summary interface
1.15.24 fix: fix get_dce_daily interface
1.15.25 fix: fix stock_news_main_cx interface
1.15.26 fix: fix option_dce_daily interface
1.15.27 fix: fix stock_zh_index_spot_em interface
1.15.28 fix: fix stock_hk_valuation_baidu interface
1.15.29 fix: fix option_dce_daily interface
1.15.30 fix: fix fund_etf_category_sina interface
1.15.31 fix: fix stock_zt_pool_strong_em interface
1.15.32 fix: fix stock_info_global_cls interface
1.15.33 add: add stock_value_em interface
1.15.34 fix: fix fund_open_fund_rank_em interface
1.15.35 fix: fix futures_spot_price_daily interface
1.15.36 fix: fix futures_global_em interface
1.15.37 fix: fix stock_individual_spot_xq interface
1.15.38 fix: fix futures_contract_info_ine interface
1.15.39 fix: fix macro_china_new_house_price interface
1.15.40 fix: fix macro_china_fdi interface
1.15.41 fix: fix macro_china_fdi interface
1.15.42 fix: fix get_roll_yield_bar interface
1.15.43 fix: fix macro_china_urban_unemployment interface
1.15.44 fix: fix index_detail_hist_adjust_cni interface
1.15.45 fix: fix stock_jgdy_detail_em interface
1.15.46 fix: fix fund_etf_fund_info_em interface
1.15.47 fix: fix stock_individual_spot_xq interface
1.15.48 fix: fix stock_mda_ym interface
1.15.49 fix: fix option_dce_daily interface
1.15.50 fix: fix stock_gpzy_profile_em interface
1.15.51 fix: fix stock_gpzy_pledge_ratio_em interface
1.15.52 fix: fix stock_zh_index_hist_csindex interface
1.15.53 fix: fix futures_inventory_99 interface
1.15.54 fix: fix stock_sy_profile_em interface
1.15.55 fix: fix fund_etf_spot_em interface
1.15.56 fix: fix spot_goods interface
1.15.57 fix: fix add 2025 trade date
1.15.58 fix: fix futures_hold_pos_sina interface
1.15.59 fix: fix stock_sy_hy_em interface
1.15.60 fix: fix stock_hot_keyword_em interface
1.15.61 fix: fix stock_zt_pool_strong_em interface
1.15.62 fix: fix stock_zt_pool_sub_new_em interface
1.15.63 fix: fix stock_financial_abstract interface
1.15.64 fix: fix stock_zh_index_value_csindex interface
1.15.65 fix: fix option_czce_daily interface
1.15.66 fix: fix fund_etf_dividend_sina interface
1.15.67 fix: fix stock_hold_change_cninfo interface
1.15.68 fix: fix stock_research_report_em interface
1.15.69 fix: fix index_zh_a_hist_min_em interface
1.15.70 fix: fix stock_research_report_em interface
1.15.71 fix: fix stock_dzjy_sctj interface
1.15.72 fix: fix stock_us_spot interface
1.15.73 fix: fix stock_dzjy_hygtj interface
1.15.74 fix: fix macro_australia_retail_rate_monthly interface
1.15.75 feat: add futures_hist_em interface
1.15.76 fix: fix futures_zh_minute_sina interface
1.15.77 fix: fix option_czce_daily interface
1.15.78 fix: fix stock_yzxdr_em interface
1.15.79 fix: fix stock_new_a_spot_em interface
1.15.80 fix: fix option_gfex_vol_daily interface
1.15.81 fix: fix bank_fjcf_table_detail interface
1.15.82 fix: fix stock_individual_spot_xq interface
1.15.83 fix: fix stock_szse_sector_summary interface
1.15.84 fix: fix option_dce_daily interface
1.15.85 fix: fix stock_gddh_em interface
1.15.86 fix: fix stock_zdhtmx_em interface
1.15.87 fix: fix futures_index_ccidx interface
1.15.88 fix: fix stock_zh_a_spot_em interface
1.15.89 fix: fix stock_individual_info_em interface
1.15.90 fix: fix stock_financial_analysis_indicator interface
1.15.91 fix: fix stock_board_concept_cons_em interface
1.15.92 fix: fix stock_main_fund_flow interface
1.15.93 fix: fix fund_etf_spot_em interface
1.15.94 fix: fix stock_zh_index_spot_em interface
1.15.95 fix: fix stock_us_spot_em interface
1.15.96 fix: fix bond_cov_comparison interface
1.15.97 fix: fix stock_intraday_em interface
1.15.98 fix: fix stock_board_concept_name_em interface
1.15.99 fix: fix stock_esg_zd_sina interface
1.16.1 fix: fix stock_main_fund_flow interface
1.16.2 fix: fix stock_board_industry_hist_em interface
1.16.3 fix: fix stock_zh_index_spot_em interface
1.16.4 fix: fix stock_hk_ggt_components_em interface
1.16.5 fix: fix stock_sector_fund_flow_rank interface
1.16.6 fix: fix stock_sgt_reference_exchange_rate_sse interface
1.16.7 fix: fix fund_lof_hist_em interface
1.16.8 fix: fix option_czce_daily interface
1.16.9 fix: fix stock_sse_deal_daily interface
1.16.10 fix: fix option_risk_analysis_em interface
1.16.11 fix: fix stock_intraday_em interface
1.16.12 fix: fix bond_zh_hs_cov_daily interface
1.16.13 fix: fix futures_inventory_99 interface
1.16.14 fix: fix stock_info_global_cls interface
1.16.15 fix: fix stock_board_concept_name_em interface
1.16.16 fix: fix stock_board_concept_spot_em interface
1.16.17 fix: fix stock_research_report_em interface
1.16.18 fix: fix stock_board_concept_spot_em interface
1.16.19 fix: fix stock_profit_forecast_ths interface
1.16.20 fix: fix stock_lhb_detail_em interface
1.16.21 fix: fix stock_hk_index_daily_em interface
1.16.22 fix: fix fund_money_fund_info_em interface
1.16.23 fix: fix stock_board_industry_cons_em interface
1.16.24 fix: fix stock_financial_hk_report_em interface
1.16.25 fix: fix stock_financial_abstract_ths interface
1.16.26 add: add stock_hsgt_sh_hk_spot_em interface
1.16.27 fix: fix futures_global_em interface
1.16.28 fix: fix futures_global_hist_em interface
1.16.29 fix: fix futures_global_hist_em interface
1.16.30 add: add forex_hist_em interface
1.16.31 add: add index_global_hist_em interface
1.16.32 fix: fix news_economic_baidu interface
1.16.33 fix: fix fund_open_fund_daily_em interface
1.16.34 fix: fix stock_individual_fund_flow_rank interface
1.16.35 fix: fix futures_global_spot_em interface
1.16.36 fix: fix stock_intraday_em interface
1.16.37 fix: fix stock_board_concept_hist_em interface
1.16.38 fix: fix fund_etf_hist_em interface
1.16.39 fix: fix option_current_em interface
1.16.40 add: add stock_individual_basic_info_xq interface
1.16.41 fix: fix stock_individual_fund_flow_rank interface
1.16.42 fix: fix stock_concept_fund_flow_hist interface
1.16.43 fix: fix option_value_analysis_em interface
1.16.44 fix: fix stock_board_concept_hist_em interface
1.16.45 fix: fix option_risk_analysis_em interface
1.16.46 fix: fix stock_hk_index_spot_em interface
1.16.47 fix: fix stock_hsgt_stock_statistics_em interface
1.16.48 fix: fix stock_individual_basic_info_xq interface
1.16.49 fix: fix index_zh_a_hist_min_em interface
1.16.50 fix: fix futures_inventory_99 interface
1.16.51 fix: fix stock_individual_basic_info_xq interface
1.16.52 fix: fix stock_zh_a_spot_em interface
1.16.53 fix: fix stock_yjbb_em interface
1.16.54 fix: fix stock_zh_a_spot_em interface
1.16.55 fix: fix stock_zh_a_spot_em interface
1.16.56 fix: fix stock_zh_a_daily interface
1.16.57 fix: fix stock_market_pe_lg interface
1.16.58 fix: fix stock_zh_a_spot interface
1.16.59 fix: fix option_czce_hist interface
1.16.60 fix: fix stock_individual_fund_flow_rank interface
1.16.61 fix: fix stock_board_concept_index_ths interface
1.16.62 fix: fix stock_gdfx_free_holding_change_em interface
1.16.63 fix: fix stock_board_concept_name_ths interface
1.16.64 add: add reits_hist_em interface
1.16.65 fix: fix stock_dzjy_yybph interface
1.16.66 fix: fix macro_cons_silver interface
1.16.67 fix: fix stock_individual_basic_info_xq interface
1.16.68 fix: fix option_dce_daily interface
1.16.69 fix: fix stock_individual_spot_xq interface
1.16.70 fix: fix stock_zh_ah_spot_em interface
1.16.71 add: add stock_zh_a_gbjg_em interface
1.16.72 add: add bond_sh_buy_back_em interface
1.16.73 fix: fix stock_board_industry_hist_em interface
1.16.74 fix: fix stock_individual_spot_xq interface
1.16.75 fix: fix get_qhkc_index interface
1.16.76 fix: fix spot_quotations_sge interface
1.16.77 add: add stock_lhb_yyb_detail_em interface
1.16.78 fix: fix stock_zh_a_spot_em interface
1.16.79 fix: fix stock_individual_basic_info_xq interface
1.16.80 fix: fix stock_zh_a_disclosure_report_cninfo interface
1.16.81 fix: fix option_shfe_daily interface
1.16.82 fix: fix index_global_spot_em interface
1.16.83 fix: fix stock_individual_info_em interface
1.16.84 fix: fix stock_fhps_detail_ths interface
1.16.85 fix: fix stock_dividend_cninfo interface
1.16.86 fix: fix index_yw interface
1.16.87 fix: fix stock_zygc_em interface
1.16.88 fix: fix futures_inventory_99 interface
1.16.89 fix: fix stock_balance_sheet_by_yearly_em interface
1.16.90 fix: fix stock_hk_company_profile_em interface
1.16.91 fix: fix stock_sse_deal_daily interface
1.16.92 fix: fix bond_cb_jsl interface
1.16.93 fix: fix stock_hsgt_individual_em interface
1.16.94 fix: fix futures_fees_info interface
1.16.95 fix: fix option_shfe_daily interface
1.16.96 fix: fix stock_individual_spot_xq interface
1.16.97 fix: fix fund_open_fund_info_em interface
1.16.98 fix: fix fund_open_fund_info_em interface
1.16.99 fix: fix stock_info_sz_delist interface
1.17.1 fix: fix stock_gdfx_holding_detail_em interface
1.17.2 fix: fix stock_ggcg_em interface
1.17.3 fix: fix stock_hot_search_baidu interface
1.17.4 fix: fix stock_news_em interface
1.17.5 fix: fix stock_us_pink_spot_em interface
1.17.6 fix: fix stock_tfp_em interface
1.17.7 fix: fix futures_spot_price_daily interface
1.17.8 fix: fix forex_spot_em interface
1.17.9 fix: fix stock_zh_ab_comparison_em interface
1.17.10 fix: fix get_shfe_daily interface
1.17.11 fix: fix stock_individual_spot_xq interface
1.17.12 fix: fix get_receipt interface
1.17.13 fix: fix futures_shfe_warehouse_receipt interface
1.17.14 fix: fix forex_spot_em interface
1.17.15 fix: fix stock_comment_em interface
1.17.16 fix: fix bond_zh_cov interface
1.17.17 fix: fix stock_hk_spot interface
1.17.18 fix: fix option_dce_daily interface
1.17.19 fix: fix futures_spot_price_daily interface
1.17.20 fix: fix stock_news_em interface
1.17.21 fix: fix stock_sector_fund_flow_hist interface
1.17.22 fix: fix stock_individual_spot_xq interface
1.17.23 fix: fix get_roll_yield interface
1.17.24 fix: fix futures_inventory_99 interface
1.17.25 fix: fix get_receipt interface
1.17.26 fix: fix stock_hot_rank_detail_em interface
"""

__version__ = "1.17.26"
__author__ = "AKFamily"

import sys
import warnings

import pandas as pd

pd_main_version = int(pd.__version__.split('.')[0])

if pd_main_version < 2:
    warnings.warn(
        "为了支持更多特性，请将 Pandas 升级到 2.2.0 及以上版本！"
    )

if sys.version_info < (3, 9):
    warnings.warn(
        "为了支持更多特性，请将 Python 升级到 3.9.0 及以上版本！"
    )

del sys

"""
期权保证金 
"""
from akshare.option.option_margin import option_margin, option_margin_symbol

"""
东方财富-港股-证券资料
"""
from akshare.stock.stock_profile_em import stock_hk_company_profile_em, stock_hk_security_profile_em

"""
东方财富网-行情中心-债券市场-质押式回购
"""
from akshare.bond.bond_buy_back_em import bond_sh_buy_back_em, bond_sz_buy_back_em, bond_buy_back_hist_em

"""
东方财富-A股数据-股本结构
"""
from akshare.stock_fundamental.stock_gbjg_em import stock_zh_a_gbjg_em

"""
异步接口
"""
from akshare.stock_a.stock_zh_a_spot import stock_zh_a_spot_em as stock_zh_a_spot_em_async
from akshare.stock_a.stock_individual_fund_flow_rank import (
    stock_individual_fund_flow_rank as stock_individual_fund_flow_rank_async
)
from akshare.stock_a.stock_board_concept_name_em import stock_board_concept_name_em as stock_board_concept_name_em_async

"""
雪球-个股-公司概况-公司简介
"""
from akshare.stock_fundamental.stock_basic_info_xq import (
    stock_individual_basic_info_xq,
    stock_individual_basic_info_hk_xq,
    stock_individual_basic_info_us_xq,
)

"""
新浪财经-行情中心-环球市场
"""
from akshare.index.index_global_sina import index_global_hist_sina, index_global_name_table

"""
东方财富网-行情中心-全球指数
"""
from akshare.index.index_global_em import index_global_hist_em, index_global_spot_em

"""
东方财富网-行情中心-外汇市场-所有汇率
"""
from akshare.forex.forex_em import forex_hist_em, forex_spot_em

"""
东方财富网-行情中心-沪深港通
"""
from akshare.stock.stock_hsgt_em import stock_zh_ah_spot_em, stock_hsgt_sh_hk_spot_em

"""
东方财富-美股-财务分析-三大报表
"""
from akshare.stock_fundamental.stock_finance_us_em import (
    stock_financial_us_report_em,
    stock_financial_us_analysis_indicator_em,
)

"""
期货行情-内盘-历史行情数据-东财
"""
from akshare.futures.futures_hist_em import futures_hist_table_em, futures_hist_em

"""
巨潮资讯-数据中心-专题统计-股东股本-股本变动
"""
from akshare.stock.stock_hold_control_cninfo import stock_hold_change_cninfo

"""
基金费率
"""
from akshare.fund.fund_fee_em import fund_fee_em

"""
东方财富网-数据中心-估值分析-每日互动-每日互动-估值分析
"""
from akshare.stock_feature.stock_value_em import stock_value_em

"""
已实现波动率
"""
from akshare.cal.rv import volatility_yz_rv, rv_from_futures_zh_minute_sina, rv_from_stock_zh_a_hist_min_em

"""
QDII
"""
from akshare.qdii.qdii_jsl import qdii_a_index_jsl, qdii_e_index_jsl, qdii_e_comm_jsl

"""
财新网-财新数据通
"""
from akshare.stock.stock_news_cx import stock_news_main_cx

"""
搜猪-生猪大数据-各省均价实时排行榜
"""
from akshare.spot.spot_hog_soozhu import (
    spot_hog_soozhu,
    spot_hog_year_trend_soozhu,
    spot_hog_lean_price_soozhu,
    spot_hog_three_way_soozhu,
    spot_hog_crossbred_soozhu,
    spot_corn_price_soozhu,
    spot_soybean_price_soozhu,
    spot_mixed_feed_soozhu,
)

"""
知名港股
"""
from akshare.stock.stock_hk_famous import stock_hk_famous_spot_em

"""
同花顺-数据中心-宏观数据-股票筹资
"""
from akshare.economic.macro_finance_ths import macro_stock_finance, macro_rmb_loan, macro_rmb_deposit

"""
富途牛牛-主题投资-概念板块-成分股
"""
from akshare.stock_feature.stock_concept_futu import stock_concept_cons_futu

"""
商品期权手续费
"""
from akshare.option.option_comm_qihuo import option_comm_info, option_comm_symbol

"""
上海证券交易所-产品-股票期权-每日统计
"""
from akshare.option.option_daily_stats_sse_szse import option_daily_stats_sse, option_daily_stats_szse

"""
同花顺理财-基金数据-每日净值-ETF
"""
from akshare.fund.fund_etf_ths import fund_etf_spot_ths

"""
东方财富网-数据中心-融资融券-融资融券账户统计-两融账户信息
"""
from akshare.stock_feature.stock_margin_em import stock_margin_account_info

"""
现货走势
"""
from akshare.spot.spot_price_qh import spot_price_qh, spot_price_table_qh

"""
华尔街见闻-日历-宏观
"""
from akshare.economic.macro_info_ws import macro_info_ws

"""
数库-A股新闻情绪指数
"""
from akshare.index.index_zh_a_scope import index_news_sentiment_scope

"""
申万宏源研究-申万指数-指数发布-基金指数-实时行情
"""
from akshare.index.index_research_fund_sw import index_hist_fund_sw, index_realtime_fund_sw

"""
东方财富-财经早餐
"""
from akshare.stock_feature.stock_info import (
    stock_info_cjzc_em,
    stock_info_global_em,
    stock_info_global_ths,
    stock_info_global_futu,
    stock_info_global_sina,
    stock_info_global_cls,
    stock_info_broker_sina,
)

"""
期货交易-参数汇总查询
"""
from akshare.futures_derivative.futures_contract_info_shfe import futures_contract_info_shfe
from akshare.futures_derivative.futures_contract_info_dce import futures_contract_info_dce
from akshare.futures_derivative.futures_contract_info_czce import futures_contract_info_czce
from akshare.futures_derivative.futures_contract_info_gfex import futures_contract_info_gfex
from akshare.futures_derivative.futures_contract_info_cffex import futures_contract_info_cffex
from akshare.futures_derivative.futures_contract_info_ine import futures_contract_info_ine

"""
上海期货交易所-指定交割仓库-库存周报
"""
from akshare.futures.futures_stock_js import futures_stock_shfe_js

"""
东方财富-数据中心-沪深港通-市场概括-分时数据
"""
from akshare.stock_feature.stock_hsgt_min_em import stock_hsgt_fund_min_em

"""
东方财富网-行情中心-期货市场-国际期货
"""
from akshare.futures.futures_hf_em import futures_global_spot_em, futures_global_hist_em

"""
雪球行情数据
"""
from akshare.stock.stock_xq import (
    stock_individual_spot_xq,
)

"""
港股盈利预测
"""
from akshare.stock_fundamental.stock_profit_forecast_hk_etnet import stock_hk_profit_forecast_et

"""
巨潮资讯-首页-公告查询-信息披露
"""
from akshare.stock_feature.stock_disclosure_cninfo import (
    stock_zh_a_disclosure_relation_cninfo,
    stock_zh_a_disclosure_report_cninfo,
)

"""
东财财富-分时数据
"""
from akshare.stock.stock_intraday_sina import stock_intraday_sina

"""
股票日行情
"""
from akshare.stock_feature.stock_hist_tx import stock_zh_a_hist_tx

"""
筹码分布
"""
from akshare.stock_feature.stock_cyq_em import stock_cyq_em

"""
东财财富-分时数据
"""
from akshare.stock.stock_intraday_em import stock_intraday_em

"""
美股指数行情
"""
from akshare.index.index_stock_us_sina import index_us_stock_sina

"""
董监高及相关人员持股变动
"""
from akshare.stock.stock_share_hold import (
    stock_share_hold_change_bse,
    stock_share_hold_change_sse,
    stock_share_hold_change_szse,
)

"""
东方财富网-数据中心-研究报告-个股研报
"""
from akshare.stock_feature.stock_research_report_em import stock_research_report_em

"""
东方财富网-数据中心-重大合同-重大合同明细
"""
from akshare.stock_feature.stock_zdhtmx_em import stock_zdhtmx_em

"""
东方财富网-数据中心-股东大会
"""
from akshare.stock_feature.stock_gddh_em import stock_gddh_em

"""
东方财富网-数据中心-股市日历
"""
from akshare.stock.stock_gsrl_em import stock_gsrl_gsdt_em

"""
东方财富网-数据中心-特色数据-高管持股
"""
from akshare.stock.stock_hold_control_em import (
    stock_hold_management_detail_em,
    stock_hold_management_person_em,
)

"""
新浪财经-债券-可转债
"""
from akshare.bond.bond_cb_sina import bond_cb_profile_sina, bond_cb_summary_sina

"""
上证e互动
"""
from akshare.stock_feature.stock_sns_sseinfo import stock_sns_sseinfo

"""
互动易-提问与回答
"""
from akshare.stock_feature.stock_irm_cninfo import (
    stock_irm_cninfo,
    stock_irm_ans_cninfo,
)

"""
基金公告-人事公告
"""
from akshare.fund.fund_announcement import fund_announcement_personnel_em

"""
新浪财经-ESG评级中心
"""
from akshare.stock_feature.stock_esg_sina import (
    stock_esg_msci_sina,
    stock_esg_rft_sina,
    stock_esg_rate_sina,
    stock_esg_zd_sina,
    stock_esg_hz_sina,
)

"""
LOF 行情数据
"""
from akshare.fund.fund_lof_em import (
    fund_lof_hist_em,
    fund_lof_spot_em,
    fund_lof_hist_min_em,
)

"""
同花顺-财务指标-主要指标
"""
from akshare.stock_fundamental.stock_finance_ths import (
    stock_financial_abstract_ths,
    stock_financial_debt_ths,
    stock_financial_benefit_ths,
    stock_financial_cash_ths,
    stock_management_change_ths,
    stock_shareholder_change_ths,
)

"""
港股股票指数数据-新浪-东财
"""
from akshare.index.index_stock_hk import (
    stock_hk_index_spot_sina,
    stock_hk_index_daily_em,
    stock_hk_index_spot_em,
    stock_hk_index_daily_sina,
)

"""
同花顺-数据中心-可转债
"""
from akshare.bond.bond_cb_ths import bond_zh_cov_info_ths

"""
同花顺-港股-分红派息
"""
from akshare.stock.stock_hk_fhpx_ths import stock_hk_fhpx_detail_ths

"""
同花顺-分红融资
"""
from akshare.stock_feature.stock_fhps_ths import stock_fhps_detail_ths

"""
东方财富-行情报价
"""
from akshare.stock.stock_ask_bid_em import stock_bid_ask_em

"""
同花顺-盈利预测
"""
from akshare.stock_fundamental.stock_profit_forecast_ths import (
    stock_profit_forecast_ths,
)

"""
期货资讯
"""
from akshare.futures.futures_news_shmet import futures_news_shmet

"""
主营介绍
"""
from akshare.stock_fundamental.stock_zyjs_ths import stock_zyjs_ths

"""
东方财富-ETF 行情
"""
from akshare.fund.fund_etf_em import (
    fund_etf_hist_em,
    fund_etf_hist_min_em,
    fund_etf_spot_em,
)

"""
乐咕乐股-股债利差
"""
from akshare.stock_feature.stock_ebs_lg import stock_ebs_lg

"""
乐咕乐股-基金仓位
"""
from akshare.fund.fund_position_lg import (
    fund_stock_position_lg,
    fund_balance_position_lg,
    fund_linghuo_position_lg,
)

"""
乐咕乐股-大盘拥挤度
"""
from akshare.stock_feature.stock_congestion_lg import stock_a_congestion_lg

"""
乐咕乐股-股息率-A 股股息率
"""
from akshare.stock_feature.stock_gxl_lg import stock_a_gxl_lg, stock_hk_gxl_lg

"""
东方财富-限售解禁股
"""
from akshare.stock_fundamental.stock_restricted_em import (
    stock_restricted_release_stockholder_em,
    stock_restricted_release_summary_em,
    stock_restricted_release_detail_em,
    stock_restricted_release_queue_em,
)

"""
同花顺行业一览表
"""
from akshare.stock_feature.stock_board_industry_ths import (
    stock_board_industry_summary_ths,
)

"""
生猪市场价格指数
"""
from akshare.index.index_hog import index_hog_spot_price

"""
债券信息查询
"""
from akshare.bond.bond_info_cm import (
    bond_info_detail_cm,
    bond_info_cm,
    bond_info_cm_query,
)

"""
申万宏源研究-指数系列
"""
from akshare.index.index_research_sw import (
    index_realtime_sw,
    index_hist_sw,
    index_component_sw,
    index_min_sw,
    index_analysis_daily_sw,
    index_analysis_weekly_sw,
    index_analysis_monthly_sw,
    index_analysis_week_month_sw,
)

"""
50ETF 期权波动率指数
"""
from akshare.index.index_option_qvix import (
    index_option_50etf_qvix,
    index_option_300etf_min_qvix,
    index_option_300etf_qvix,
    index_option_50etf_min_qvix,
    index_option_1000index_min_qvix,
    index_option_1000index_qvix,
    index_option_100etf_min_qvix,
    index_option_100etf_qvix,
    index_option_300index_min_qvix,
    index_option_300index_qvix,
    index_option_500etf_min_qvix,
    index_option_500etf_qvix,
    index_option_50index_min_qvix,
    index_option_50index_qvix,
    index_option_cyb_min_qvix,
    index_option_cyb_qvix,
    index_option_kcb_min_qvix,
    index_option_kcb_qvix,
)

"""
百度股市通-外汇-行情榜单
"""
from akshare.fx.fx_quote_baidu import fx_quote_baidu

"""
乐估乐股-底部研究-巴菲特指标
"""
from akshare.stock_feature.stock_buffett_index_lg import stock_buffett_index_lg

"""
百度股市通-热搜股票
"""
from akshare.stock.stock_hot_search_baidu import stock_hot_search_baidu

"""
百度股市通- A 股或指数-股评-投票
"""
from akshare.stock_feature.stock_zh_vote_baidu import stock_zh_vote_baidu

"""
百度股市通-A 股-财务报表-估值数据
"""
from akshare.stock_feature.stock_zh_valuation_baidu import stock_zh_valuation_baidu

"""
百度股市通-港股-财务报表-估值数据
"""
from akshare.stock_feature.stock_hk_valuation_baidu import stock_hk_valuation_baidu

"""
巨潮资讯-个股-公司概况
"""
from akshare.stock.stock_profile_cninfo import stock_profile_cninfo

"""
巨潮资讯-个股-上市相关
"""
from akshare.stock.stock_ipo_summary_cninfo import stock_ipo_summary_cninfo

"""
巨潮资讯-数据浏览器-筹资指标-公司配股实施方案
"""
from akshare.stock.stock_allotment_cninfo import stock_allotment_cninfo

"""
沪深港股通-参考汇率和结算汇率
"""
from akshare.stock_feature.stock_hsgt_exchange_rate import (
    stock_sgt_reference_exchange_rate_sse,
    stock_sgt_settlement_exchange_rate_sse,
    stock_sgt_reference_exchange_rate_szse,
    stock_sgt_settlement_exchange_rate_szse,
)

"""
中国债券信息网-中债指数-中债指数族系-总指数-综合类指数
"""
from akshare.bond.bond_cbond import (
    bond_new_composite_index_cbond,
    bond_composite_index_cbond,
)

"""
行业板块
"""
from akshare.stock_feature.stock_classify_sina import stock_classify_sina

"""
主营构成
"""
from akshare.stock_fundamental.stock_zygc import stock_zygc_em

"""
人民币汇率中间价
"""
from akshare.currency.currency_safe import currency_boc_safe

"""
期权-上海证券交易所-风险指标
"""
from akshare.option.option_risk_indicator_sse import option_risk_indicator_sse

"""
全球宏观事件
"""
from akshare.news.news_baidu import (
    news_economic_baidu,
    news_trade_notify_suspend_baidu,
    news_report_time_baidu,
    news_trade_notify_dividend_baidu,
)

"""
东方财富-股票-财务分析
"""
from akshare.stock_feature.stock_three_report_em import (
    stock_balance_sheet_by_report_em,
    stock_balance_sheet_by_yearly_em,
    stock_profit_sheet_by_report_em,
    stock_profit_sheet_by_quarterly_em,
    stock_profit_sheet_by_yearly_em,
    stock_cash_flow_sheet_by_report_em,
    stock_cash_flow_sheet_by_quarterly_em,
    stock_cash_flow_sheet_by_yearly_em,
    stock_balance_sheet_by_report_delisted_em,
    stock_profit_sheet_by_report_delisted_em,
    stock_cash_flow_sheet_by_report_delisted_em,
)

"""
内部交易
"""
from akshare.stock_feature.stock_inner_trade_xq import stock_inner_trade_xq

"""
股票热度-雪球
"""
from akshare.stock_feature.stock_hot_xq import (
    stock_hot_deal_xq,
    stock_hot_follow_xq,
    stock_hot_tweet_xq,
)

"""
东方财富-股票数据-龙虎榜
"""
from akshare.stock_feature.stock_lhb_em import (
    stock_lhb_hyyyb_em,
    stock_lhb_detail_em,
    stock_lhb_stock_detail_em,
    stock_lhb_jgmmtj_em,
    stock_lhb_stock_statistic_em,
    stock_lhb_stock_detail_date_em,
    stock_lhb_yybph_em,
    stock_lhb_jgstatistic_em,
    stock_lhb_traderstatistic_em,
    stock_lhb_yyb_detail_em,
)

"""
指数行情数据
"""
from akshare.index.index_zh_em import (
    index_zh_a_hist,
    index_zh_a_hist_min_em,
    index_code_id_map_em,
)

"""
东方财富个股人气榜-A股
"""
from akshare.stock.stock_hot_rank_em import (
    stock_hot_rank_detail_em,
    stock_hot_rank_em,
    stock_hot_rank_detail_realtime_em,
    stock_hot_rank_relate_em,
    stock_hot_keyword_em,
    stock_hot_rank_latest_em,
)
from akshare.stock.stock_hot_up_em import stock_hot_up_em

"""
东方财富个股人气榜-港股
"""
from akshare.stock.stock_hk_hot_rank_em import (
    stock_hk_hot_rank_detail_em,
    stock_hk_hot_rank_latest_em,
    stock_hk_hot_rank_detail_realtime_em,
    stock_hk_hot_rank_em,
)

"""
财新指数
"""
from akshare.index.index_cx import (
    index_pmi_com_cx,
    index_pmi_man_cx,
    index_pmi_ser_cx,
    index_dei_cx,
    index_ii_cx,
    index_si_cx,
    index_fi_cx,
    index_bi_cx,
    index_ci_cx,
    index_awpr_cx,
    index_cci_cx,
    index_li_cx,
    index_neaw_cx,
    index_nei_cx,
    index_ti_cx,
    index_ai_cx,
    index_neei_cx,
    index_bei_cx,
    index_qli_cx,
)

"""
期权折溢价分析
"""
from akshare.option.option_premium_analysis_em import (
    option_premium_analysis_em,
)

"""
期权风险分析
"""
from akshare.option.option_risk_analysis_em import option_risk_analysis_em

"""
期权价值分析
"""
from akshare.option.option_value_analysis_em import option_value_analysis_em

"""
期权龙虎榜
"""
from akshare.option.option_lhb_em import option_lhb_em

"""
东方财富网-数据中心-股东分析
"""
from akshare.stock_feature.stock_gdfx_em import (
    stock_gdfx_holding_analyse_em,
    stock_gdfx_free_holding_analyse_em,
    stock_gdfx_free_top_10_em,
    stock_gdfx_top_10_em,
    stock_gdfx_free_holding_detail_em,
    stock_gdfx_holding_detail_em,
    stock_gdfx_free_holding_change_em,
    stock_gdfx_holding_change_em,
    stock_gdfx_free_holding_statistics_em,
    stock_gdfx_holding_statistics_em,
    stock_gdfx_free_holding_teamwork_em,
    stock_gdfx_holding_teamwork_em,
)

"""
中国食糖指数
"""
from akshare.index.index_sugar import (
    index_sugar_msweet,
    index_inner_quote_sugar_msweet,
    index_outer_quote_sugar_msweet,
)

"""
东方财富-个股信息
"""
from akshare.stock.stock_info_em import stock_individual_info_em

"""
上海黄金交易所-数据资讯-行情走势
"""
from akshare.spot.spot_sge import (
    spot_hist_sge,
    spot_symbol_table_sge,
    spot_silver_benchmark_sge,
    spot_golden_benchmark_sge,
    spot_quotations_sge,
)

"""
股票回购
"""
from akshare.stock.stock_repurchase_em import stock_repurchase_em

"""
东方财富-行业板块
"""
from akshare.stock.stock_board_industry_em import (
    stock_board_industry_cons_em,
    stock_board_industry_hist_em,
    stock_board_industry_hist_min_em,
    stock_board_industry_name_em,
    stock_board_industry_spot_em,
)

"""
天天基金网-基金数据-规模变动
"""
from akshare.fund.fund_scale_em import (
    fund_scale_change_em,
    fund_hold_structure_em,
)

"""
天天基金网-基金数据-分红送配
"""
from akshare.fund.fund_fhsp_em import fund_cf_em, fund_fh_rank_em, fund_fh_em

"""
艺恩-艺人
"""
from akshare.movie.artist_yien import (
    online_value_artist,
    business_value_artist,
)

"""
艺恩-视频放映
"""
from akshare.movie.video_yien import video_variety_show, video_tv

"""
同花顺-数据中心-技术选股
"""
from akshare.stock_feature.stock_technology_ths import (
    stock_rank_cxg_ths,
    stock_rank_cxd_ths,
    stock_rank_lxsz_ths,
    stock_rank_lxxd_ths,
    stock_rank_cxfl_ths,
    stock_rank_cxsl_ths,
    stock_rank_xstp_ths,
    stock_rank_xxtp_ths,
    stock_rank_ljqd_ths,
    stock_rank_ljqs_ths,
    stock_rank_xzjp_ths,
)

"""
沪深港通持股
"""
from akshare.stock_feature.stock_hsgt_em import (
    stock_hsgt_individual_em,
    stock_hsgt_individual_detail_em,
    stock_hsgt_fund_flow_summary_em,
)

"""
基金规模
"""
from akshare.fund.fund_scale_sina import (
    fund_scale_open_sina,
    fund_scale_close_sina,
    fund_scale_structured_sina,
)

"""
巨潮资讯-数据中心-专题统计-基金报表
"""
from akshare.fund.fund_report_cninfo import (
    fund_report_stock_cninfo,
    fund_report_industry_allocation_cninfo,
    fund_report_asset_allocation_cninfo,
)

"""
巨潮资讯-数据中心-专题统计-债券报表-债券发行
"""
from akshare.bond.bond_issue_cninfo import (
    bond_treasure_issue_cninfo,
    bond_local_government_issue_cninfo,
    bond_corporate_issue_cninfo,
    bond_cov_issue_cninfo,
    bond_cov_stock_issue_cninfo,
)

"""
巨潮资讯-数据中心-专题统计-公司治理-股权质押
"""
from akshare.stock.stock_cg_equity_mortgage import (
    stock_cg_equity_mortgage_cninfo,
)

"""
巨潮资讯-数据中心-专题统计-公司治理-公司诉讼
"""
from akshare.stock.stock_cg_lawsuit import stock_cg_lawsuit_cninfo

"""
巨潮资讯-数据中心-专题统计-公司治理-对外担保
"""
from akshare.stock.stock_cg_guarantee import stock_cg_guarantee_cninfo

"""
B 股
"""
from akshare.stock.stock_zh_b_sina import (
    stock_zh_b_spot,
    stock_zh_b_daily,
    stock_zh_b_minute,
)

"""
期货手续费
"""
from akshare.futures.futures_comm_qihuo import futures_comm_info
from akshare.futures.futures_comm_ctp import futures_fees_info

"""
实际控制人持股变动
"""
from akshare.stock.stock_hold_control_cninfo import (
    stock_hold_control_cninfo,
    stock_hold_management_detail_cninfo,
)

"""
股东人数及持股集中度
"""
from akshare.stock.stock_hold_num_cninfo import stock_hold_num_cninfo

"""
新股过会
"""
from akshare.stock.stock_new_cninfo import (
    stock_new_gh_cninfo,
    stock_new_ipo_cninfo,
)

"""
个股分红
"""
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo

"""
公司股本变动
"""
from akshare.stock.stock_share_changes_cninfo import stock_share_change_cninfo

"""
行业分类数据
"""
from akshare.stock.stock_industry_cninfo import (
    stock_industry_category_cninfo,
    stock_industry_change_cninfo,
)

"""
行业市盈率
"""
from akshare.stock.stock_industry_pe_cninfo import (
    stock_industry_pe_ratio_cninfo,
)

"""
申万宏源行业分类数据
"""

from akshare.stock.stock_industry_sw import stock_industry_clf_hist_sw

"""
投资评级
"""
from akshare.stock.stock_rank_forecast import stock_rank_forecast_cninfo

"""
美股-知名美股
"""
from akshare.stock.stock_us_famous import stock_us_famous_spot_em

"""
美股-粉单市场
"""
from akshare.stock.stock_us_pink import stock_us_pink_spot_em

"""
REITs
"""
from akshare.reits.reits_basic import reits_realtime_em, reits_hist_em

"""
全部 A 股-等权重市盈率、中位数市盈率
全部 A 股-等权重、中位数市净率
"""
from akshare.stock_feature.stock_ttm_lyr import stock_a_ttm_lyr
from akshare.stock_feature.stock_all_pb import stock_a_all_pb

"""
宏观-加拿大
"""
from akshare.economic.macro_canada import (
    macro_canada_cpi_monthly,
    macro_canada_core_cpi_monthly,
    macro_canada_bank_rate,
    macro_canada_core_cpi_yearly,
    macro_canada_cpi_yearly,
    macro_canada_gdp_monthly,
    macro_canada_new_house_rate,
    macro_canada_retail_rate_monthly,
    macro_canada_trade,
    macro_canada_unemployment_rate,
)

"""
猪肉价格信息
"""
from akshare.futures_derivative.futures_hog import (
    futures_hog_core,
    futures_hog_cost,
    futures_hog_supply,
)

"""
宏观-澳大利亚
"""
from akshare.economic.macro_australia import (
    macro_australia_bank_rate,
    macro_australia_unemployment_rate,
    macro_australia_trade,
    macro_australia_cpi_quarterly,
    macro_australia_cpi_yearly,
    macro_australia_ppi_quarterly,
    macro_australia_retail_rate_monthly,
)

"""
融资融券-深圳
"""
from akshare.stock_feature.stock_margin_szse import (
    stock_margin_underlying_info_szse,
    stock_margin_detail_szse,
    stock_margin_szse,
)

"""
英国-宏观
"""
from akshare.economic.macro_uk import (
    macro_uk_gdp_yearly,
    macro_uk_gdp_quarterly,
    macro_uk_retail_yearly,
    macro_uk_rightmove_monthly,
    macro_uk_rightmove_yearly,
    macro_uk_unemployment_rate,
    macro_uk_halifax_monthly,
    macro_uk_bank_rate,
    macro_uk_core_cpi_monthly,
    macro_uk_core_cpi_yearly,
    macro_uk_cpi_monthly,
    macro_uk_cpi_yearly,
    macro_uk_halifax_yearly,
    macro_uk_retail_monthly,
    macro_uk_trade,
)

"""
日本-宏观
"""
from akshare.economic.macro_japan import (
    macro_japan_bank_rate,
    macro_japan_core_cpi_yearly,
    macro_japan_cpi_yearly,
    macro_japan_head_indicator,
    macro_japan_unemployment_rate,
)

"""
瑞士-宏观
"""
from akshare.economic.macro_swiss import (
    macro_swiss_trade,
    macro_swiss_svme,
    macro_swiss_cpi_yearly,
    macro_swiss_gbd_yearly,
    macro_swiss_gbd_bank_rate,
    macro_swiss_gdp_quarterly,
)

"""
东方财富-概念板块
"""
from akshare.stock.stock_board_concept_em import (
    stock_board_concept_cons_em,
    stock_board_concept_hist_em,
    stock_board_concept_hist_min_em,
    stock_board_concept_name_em,
    stock_board_concept_spot_em,
)

"""
德国-经济指标
"""
from akshare.economic.macro_germany import (
    macro_germany_gdp,
    macro_germany_ifo,
    macro_germany_cpi_monthly,
    macro_germany_retail_sale_monthly,
    macro_germany_trade_adjusted,
    macro_germany_retail_sale_yearly,
    macro_germany_cpi_yearly,
    macro_germany_zew,
)

"""
基金规模和规模趋势
"""
from akshare.fund.fund_aum_em import (
    fund_aum_em,
    fund_aum_trend_em,
    fund_aum_hist_em,
)

"""
CME 比特币成交量
"""
from akshare.crypto.crypto_bitcoin_cme import crypto_bitcoin_cme

"""
盘口异动
"""
from akshare.stock_feature.stock_pankou_em import (
    stock_changes_em,
    stock_board_change_em,
)

"""
A 股东方财富
"""
from akshare.stock_feature.stock_hist_em import (
    stock_zh_a_spot_em,
    stock_bj_a_spot_em,
    stock_new_a_spot_em,
    stock_kc_a_spot_em,
    stock_cy_a_spot_em,
    stock_sh_a_spot_em,
    stock_sz_a_spot_em,
    stock_zh_b_spot_em,
    stock_zh_ab_comparison_em,
    stock_zh_a_hist,
    stock_hk_spot_em,
    stock_hk_main_board_spot_em,
    stock_hk_hist,
    stock_us_spot_em,
    stock_us_hist,
    stock_zh_a_hist_min_em,
    stock_zh_a_hist_pre_min_em,
    stock_hk_hist_min_em,
    stock_us_hist_min_em,
)

"""
中行人民币牌价历史数据查询
"""
from akshare.currency.currency_china_bank_sina import currency_boc_sina

"""
期货持仓
"""
from akshare.futures_derivative.futures_cot_sina import futures_hold_pos_sina

"""
股东户数
"""
from akshare.stock_feature.stock_gdhs import (
    stock_zh_a_gdhs,
    stock_zh_a_gdhs_detail_em,
)

"""
两网及退市
"""
from akshare.stock.stock_stop import stock_staq_net_stop

"""
涨停板行情
"""
from akshare.stock_feature.stock_ztb_em import (
    stock_zt_pool_em,
    stock_zt_pool_previous_em,
    stock_zt_pool_dtgc_em,
    stock_zt_pool_zbgc_em,
    stock_zt_pool_strong_em,
    stock_zt_pool_sub_new_em,
)

"""
中国-香港-宏观
"""
from akshare.economic.macro_china_hk import (
    macro_china_hk_cpi,
    macro_china_hk_cpi_ratio,
    macro_china_hk_trade_diff_ratio,
    macro_china_hk_gbp_ratio,
    macro_china_hk_building_amount,
    macro_china_hk_building_volume,
    macro_china_hk_gbp,
    macro_china_hk_ppi,
    macro_china_hk_rate_of_unemployment,
)

"""
增发和配股
"""
from akshare.stock_feature.stock_zf_pg import stock_qbzf_em, stock_pg_em

"""
汽车销量
"""
from akshare.other.other_car_gasgoo import car_sale_rank_gasgoo
from akshare.other.other_car_cpca import (
    car_market_cate_cpca,
    car_market_fuel_cpca,
    car_market_segment_cpca,
    car_market_country_cpca,
    car_market_man_rank_cpca,
    car_market_total_cpca,
)

"""
中国公路物流运价、运量指数
"""
from akshare.index.index_cflp import index_price_cflp, index_volume_cflp

"""
赚钱效应分析
"""
from akshare.stock_feature.stock_market_legu import stock_market_activity_legu

"""
浙江省排污权交易指数
"""
from akshare.index.index_eri import index_eri

"""
Drewry 集装箱指数
"""
from akshare.index.index_drewry import drewry_wci_index

"""
柯桥指数
"""
from akshare.index.index_kq_fz import index_kq_fz
from akshare.index.index_kq_ss import index_kq_fashion

"""
新发基金
"""
from akshare.fund.fund_init_em import fund_new_found_em

"""
高管持股
"""
from akshare.stock_feature.stock_gdzjc_em import stock_ggcg_em

"""
同花顺-数据中心-资金流向-概念资金流
"""
from akshare.stock_feature.stock_fund_flow import (
    stock_fund_flow_concept,
    stock_fund_flow_industry,
    stock_fund_flow_big_deal,
    stock_fund_flow_individual,
)

"""
比特币持仓
"""
from akshare.crypto.crypto_hold import crypto_bitcoin_hold_report

"""
证券交易营业部排行
"""
from akshare.stock_feature.stock_lh_yybpm import (
    stock_lh_yyb_capital,
    stock_lh_yyb_most,
    stock_lh_yyb_control,
)

"""
沪深 A 股公告
"""
from akshare.stock_fundamental.stock_notice import stock_notice_report

"""
首发企业申报
"""
from akshare.stock_fundamental.stock_ipo_declare import stock_ipo_declare

"""
三大报表
"""
from akshare.stock_feature.stock_report_em import (
    stock_zcfz_em,
    stock_zcfz_bj_em,
    stock_lrb_em,
    stock_xjll_em,
)

"""
业绩报告
"""
from akshare.stock_feature.stock_yjbb_em import stock_yjbb_em

"""
同花顺-概念板块
"""
from akshare.stock_feature.stock_board_concept_ths import (
    stock_board_concept_info_ths,
    stock_board_concept_summary_ths,
    stock_board_concept_index_ths,
    stock_board_concept_name_ths,
)

"""
同花顺-行业板块
"""
from akshare.stock_feature.stock_board_industry_ths import (
    stock_board_industry_name_ths,
    stock_board_industry_info_ths,
    stock_board_industry_index_ths,
    stock_ipo_benefit_ths,
    stock_xgsr_ths,
)

"""
分红配送
"""
from akshare.stock_feature.stock_fhps_em import stock_fhps_em, stock_fhps_detail_em

"""
中美国债收益率
"""
from akshare.bond.bond_em import bond_zh_us_rate

"""
盈利预测
"""
from akshare.stock_fundamental.stock_profit_forecast_em import (
    stock_profit_forecast_em,
)

"""
基金经理
"""
from akshare.fund.fund_manager import fund_manager_em

"""
基金评级
"""
from akshare.fund.fund_rating import (
    fund_rating_sh,
    fund_rating_zs,
    fund_rating_ja,
    fund_rating_all,
)

"""
融资融券数据
"""
from akshare.stock_feature.stock_margin_sse import (
    stock_margin_detail_sse,
    stock_margin_sse,
    stock_margin_ratio_pa,
)

"""
期货交割和期转现
"""
from akshare.futures.futures_to_spot import (
    futures_to_spot_czce,
    futures_to_spot_shfe,
    futures_to_spot_dce,
    futures_delivery_dce,
    futures_delivery_shfe,
    futures_delivery_czce,
    futures_delivery_match_dce,
    futures_delivery_match_czce,
)

"""
基金持仓
"""
from akshare.fund.fund_portfolio_em import (
    fund_portfolio_hold_em,
    fund_portfolio_change_em,
    fund_portfolio_bond_hold_em,
    fund_portfolio_industry_allocation_em,
)

"""
债券概览
"""
from akshare.bond.bond_summary import (
    bond_deal_summary_sse,
    bond_cash_summary_sse,
)

"""
新闻-个股新闻
"""
from akshare.news.news_stock import stock_news_em

"""
股票数据-一致行动人
"""
from akshare.stock_feature.stock_yzxdr_em import stock_yzxdr_em

"""
大宗交易
"""
from akshare.stock.stock_dzjy_em import (
    stock_dzjy_sctj,
    stock_dzjy_mrmx,
    stock_dzjy_mrtj,
    stock_dzjy_hygtj,
    stock_dzjy_yybph,
    stock_dzjy_hyyybtj,
)

"""
国证指数
"""
from akshare.index.index_cni import (
    index_hist_cni,
    index_all_cni,
    index_detail_cni,
    index_detail_hist_cni,
    index_detail_hist_adjust_cni,
)

"""
东方财富-期权
"""
from akshare.option.option_em import option_current_em

"""
科创板报告
"""
from akshare.stock.stock_zh_kcb_report import stock_zh_kcb_report_em

"""
期货合约详情
"""
from akshare.futures.futures_contract_detail import futures_contract_detail

"""
胡润排行榜
"""
from akshare.fortune.fortune_hurun import hurun_rank

"""
新财富富豪榜
"""
from akshare.fortune.fortune_xincaifu_500 import xincaifu_rank

"""
福布斯中国榜单
"""
from akshare.fortune.fortune_forbes_500 import forbes_rank

"""
回购定盘利率
"""
from akshare.rate.repo_rate import repo_rate_hist, repo_rate_query

"""
公募基金排行
"""
from akshare.fund.fund_rank_em import (
    fund_exchange_rank_em,
    fund_money_rank_em,
    fund_open_fund_rank_em,
    fund_hk_rank_em,
    fund_lcx_rank_em,
)

"""
电影票房
"""
from akshare.movie.movie_yien import (
    movie_boxoffice_cinema_daily,
    movie_boxoffice_cinema_weekly,
    movie_boxoffice_weekly,
    movie_boxoffice_daily,
    movie_boxoffice_monthly,
    movie_boxoffice_realtime,
    movie_boxoffice_yearly,
    movie_boxoffice_yearly_first_week,
)

"""
新闻联播文字稿
"""
from akshare.news.news_cctv import news_cctv

"""
债券收盘收益率曲线历史数据
"""
from akshare.bond.bond_china_money import (
    bond_china_close_return,
    macro_china_bond_public,
    macro_china_swap_rate,
    bond_china_close_return_map,

)

"""
COMEX黄金-白银库存
"""
from akshare.futures.futures_comex_em import futures_comex_inventory

"""
A 股-特别标的
"""
from akshare.stock.stock_zh_a_special import (
    stock_zh_a_new,
    stock_zh_a_st_em,
    stock_zh_a_new_em,
    stock_zh_a_stop_em,
)

"""
东方财富-注册制审核
"""
from akshare.stock_fundamental.stock_register_em import (
    stock_register_kcb,
    stock_register_cyb,
    stock_register_bj,
    stock_register_db,
    stock_register_sh,
    stock_register_sz
)

"""
新浪财经-龙虎榜
"""
from akshare.stock_feature.stock_lhb_sina import (
    stock_lhb_detail_daily_sina,
    stock_lhb_ggtj_sina,
    stock_lhb_jgmx_sina,
    stock_lhb_jgzz_sina,
    stock_lhb_yytj_sina,
)

"""
中证指数
"""
from akshare.index.index_stock_zh_csindex import (
    stock_zh_index_hist_csindex,
    stock_zh_index_value_csindex,
)

"""
股票基金持仓数据
"""
from akshare.stock.stock_fund_hold import (
    stock_report_fund_hold,
    stock_report_fund_hold_detail,
)

"""
期货分钟数据
"""
from akshare.futures.futures_zh_sina import (
    futures_zh_minute_sina,
    futures_zh_daily_sina,
    futures_zh_realtime,
    futures_symbol_mark,
    match_main_contract,
    futures_zh_spot,
)

"""
股票财务报告预约披露
"""
from akshare.stock_feature.stock_yjyg_cninfo import stock_report_disclosure

"""
基金行情
"""
from akshare.fund.fund_etf_sina import (
    fund_etf_hist_sina,
    fund_etf_category_sina,
    fund_etf_dividend_sina,
)

"""
交易日历
"""
from akshare.tool.trade_date_hist import tool_trade_date_hist_sina

"""
commodity option
"""
from akshare.option.option_commodity_sina import (
    option_commodity_contract_table_sina,
    option_commodity_contract_sina,
    option_commodity_hist_sina,
)

"""
A 股PE和PB
"""
from akshare.stock_feature.stock_a_pe_and_pb import (
    stock_market_pb_lg,
    stock_index_pb_lg,
    stock_market_pe_lg,
    stock_index_pe_lg,
)
from akshare.stock_feature.stock_a_indicator import (
    stock_a_indicator_lg,
    stock_hk_indicator_eniu,
)
from akshare.stock_feature.stock_a_high_low import stock_a_high_low_statistics
from akshare.stock_feature.stock_a_below_net_asset_statistics import (
    stock_a_below_net_asset_statistics,
)

"""
彭博亿万富豪指数
"""
from akshare.fortune.fortune_bloomberg import (
    index_bloomberg_billionaires,
    index_bloomberg_billionaires_hist,
)

"""
stock-券商业绩月报
"""
from akshare.stock_feature.stock_qsjy_em import stock_qsjy_em

"""
futures-warehouse-receipt
"""
from akshare.futures.futures_warehouse_receipt import (
    futures_czce_warehouse_receipt,
    futures_dce_warehouse_receipt,
    futures_shfe_warehouse_receipt,
    futures_gfex_warehouse_receipt,
)

"""
stock-js
"""
from akshare.stock.stock_us_js import stock_price_js

"""
stock-summary
"""
from akshare.stock.stock_summary import (
    stock_sse_summary,
    stock_szse_summary,
    stock_sse_deal_daily,
    stock_szse_area_summary,
    stock_szse_sector_summary,
)

"""
股票-机构推荐池
"""
from akshare.stock_fundamental.stock_recommend import (
    stock_institute_recommend,
    stock_institute_recommend_detail,
)

"""
股票-机构持股
"""
from akshare.stock_fundamental.stock_hold import (
    stock_institute_hold_detail,
    stock_institute_hold,
)

"""
stock-info
"""
from akshare.stock.stock_info import (
    stock_info_sh_delist,
    stock_info_sz_delist,
    stock_info_a_code_name,
    stock_info_sh_name_code,
    stock_info_bj_name_code,
    stock_info_sz_name_code,
    stock_info_sz_change_name,
    stock_info_change_name,
)

"""
stock-sector
"""
from akshare.stock.stock_industry import stock_sector_spot, stock_sector_detail

"""
stock-fundamental
"""
from akshare.stock_fundamental.stock_finance_sina import (
    stock_financial_abstract,
    stock_financial_report_sina,
    stock_financial_analysis_indicator,
    stock_add_stock,
    stock_ipo_info,
    stock_history_dividend_detail,
    stock_history_dividend,
    stock_circulate_stock_holder,
    stock_restricted_release_queue_sina,
    stock_fund_stock_holder,
    stock_main_stock_holder,
)

"""
stock-HK-fundamental
"""
from akshare.stock_fundamental.stock_finance_hk_em import (
    stock_financial_hk_analysis_indicator_em,
    stock_financial_hk_report_em,
)

"""
stock_fund
"""
from akshare.stock.stock_fund_em import (
    stock_individual_fund_flow,
    stock_market_fund_flow,
    stock_sector_fund_flow_rank,
    stock_individual_fund_flow_rank,
    stock_sector_fund_flow_summary,
    stock_sector_fund_flow_hist,
    stock_concept_fund_flow_hist,
    stock_main_fund_flow,
)

"""
air-quality
"""
from akshare.air.air_zhenqi import (
    air_quality_hist,
    air_quality_rank,
    air_quality_watch_point,
    air_city_table,
)

"""
hf
"""
from akshare.hf.hf_sp500 import hf_sp_500

"""
stock_yjyg_em
"""
from akshare.stock_feature.stock_yjyg_em import (
    stock_yjyg_em,
    stock_yysj_em,
    stock_yjkb_em,
)

"""
stock
"""
from akshare.stock_feature.stock_dxsyl_em import (
    stock_dxsyl_em,
    stock_xgsglb_em,
)

"""
article
"""
from akshare.article.fred_md import fred_md, fred_qd

"""
中证商品指数
"""
from akshare.futures.futures_index_ccidx import (
    futures_index_min_ccidx,
    futures_index_ccidx,
)

"""
futures_em_spot_stock
"""
from akshare.futures.futures_spot_stock_em import futures_spot_stock

"""
energy_oil
"""
from akshare.energy.energy_oil_em import energy_oil_detail, energy_oil_hist

"""
futures-foreign
"""
from akshare.futures.futures_foreign import (
    futures_foreign_detail,
    futures_foreign_hist,
)

"""
stock-em-tfp
"""
from akshare.stock_feature.stock_tfp_em import stock_tfp_em

"""
stock-em-hsgt
"""
from akshare.stock_feature.stock_hsgt_em import (
    stock_hk_ggt_components_em,
    stock_hsgt_hold_stock_em,
    stock_hsgt_hist_em,
    stock_hsgt_institution_statistics_em,
    stock_hsgt_stock_statistics_em,
    stock_hsgt_board_rank_em,
)

"""
stock-em-comment
"""
from akshare.stock_feature.stock_comment_em import (
    stock_comment_em,
    stock_comment_detail_zlkp_jgcyd_em,
    stock_comment_detail_scrd_focus_em,
    stock_comment_detail_zhpj_lspf_em,
    stock_comment_detail_scrd_desire_em,
    stock_comment_detail_scrd_desire_daily_em,
)

"""
stock-em-analyst
"""
from akshare.stock_feature.stock_analyst_em import (
    stock_analyst_detail_em,
    stock_analyst_rank_em,
)

"""
新加坡期货交易所
"""
from akshare.futures.futures_settlement_price_sgx import futures_settlement_price_sgx

"""
currency interface
"""
from akshare.currency.currency import (
    currency_convert,
    currency_currencies,
    currency_history,
    currency_latest,
    currency_time_series,
)

"""
知识图谱
"""
from akshare.nlp.nlp_interface import nlp_ownthink, nlp_answer

"""
微博舆情报告
"""
from akshare.stock.stock_weibo_nlp import (
    stock_js_weibo_nlp_time,
    stock_js_weibo_report,
)

"""
金融期权-新浪
"""
from akshare.option.option_finance_sina import (
    option_cffex_sz50_list_sina,
    option_cffex_sz50_spot_sina,
    option_cffex_sz50_daily_sina,
    option_cffex_hs300_list_sina,
    option_cffex_hs300_spot_sina,
    option_cffex_hs300_daily_sina,
    option_cffex_zz1000_list_sina,
    option_cffex_zz1000_spot_sina,
    option_cffex_zz1000_daily_sina,
    option_sse_list_sina,
    option_sse_expire_day_sina,
    option_sse_codes_sina,
    option_sse_spot_price_sina,
    option_sse_underlying_spot_price_sina,
    option_sse_greeks_sina,
    option_sse_minute_sina,
    option_sse_daily_sina,
    option_finance_minute_sina,
    option_minute_em,
)

"""
债券-沪深债券
"""
from akshare.bond.bond_zh_sina import bond_zh_hs_daily, bond_zh_hs_spot
from akshare.bond.bond_zh_cov import (
    bond_zh_hs_cov_daily,
    bond_zh_hs_cov_spot,
    bond_cov_comparison,
    bond_zh_cov,
    bond_zh_cov_info,
    bond_zh_hs_cov_min,
    bond_zh_hs_cov_pre_min,
    bond_zh_cov_value_analysis,
)
from akshare.bond.bond_convert import (
    bond_cb_jsl,
    bond_cb_adj_logs_jsl,
    bond_cb_index_jsl,
    bond_cb_redeem_jsl,
)

"""
基金数据接口
"""
from akshare.fund.fund_em import (
    fund_open_fund_daily_em,
    fund_open_fund_info_em,
    fund_etf_fund_daily_em,
    fund_etf_fund_info_em,
    fund_financial_fund_daily_em,
    fund_financial_fund_info_em,
    fund_name_em,
    fund_info_index_em,
    fund_graded_fund_daily_em,
    fund_graded_fund_info_em,
    fund_money_fund_daily_em,
    fund_money_fund_info_em,
    fund_value_estimation_em,
    fund_hk_fund_hist_em,
    fund_purchase_em,
)

"""
百度迁徙地图接口
"""
from akshare.event.migration import (
    migration_area_baidu,
    migration_scale_baidu,
)

"""
英为财情-外汇-货币对历史数据
"""
from akshare.fx.currency_investing import (
    currency_pair_map,
)

"""
商品期权-郑州商品交易所-期权-历史数据
"""
from akshare.option.option_czce import option_czce_hist

"""
宏观-经济数据-银行间拆借利率
"""
from akshare.interest_rate.interbank_rate_em import rate_interbank

"""
金十数据中心-外汇情绪
"""
from akshare.economic.macro_other import macro_fx_sentiment

"""
金十数据中心-经济指标-欧元区
"""
from akshare.economic.macro_euro import (
    macro_euro_gdp_yoy,
    macro_euro_cpi_mom,
    macro_euro_cpi_yoy,
    macro_euro_current_account_mom,
    macro_euro_employment_change_qoq,
    macro_euro_industrial_production_mom,
    macro_euro_manufacturing_pmi,
    macro_euro_ppi_mom,
    macro_euro_retail_sales_mom,
    macro_euro_sentix_investor_confidence,
    macro_euro_services_pmi,
    macro_euro_trade_balance,
    macro_euro_unemployment_rate_mom,
    macro_euro_zew_economic_sentiment,
    macro_euro_lme_holding,
    macro_euro_lme_stock,
)

"""
金十数据中心-经济指标-央行利率-主要央行利率
"""
from akshare.economic.macro_bank import (
    macro_bank_australia_interest_rate,
    macro_bank_brazil_interest_rate,
    macro_bank_brazil_interest_rate,
    macro_bank_china_interest_rate,
    macro_bank_english_interest_rate,
    macro_bank_euro_interest_rate,
    macro_bank_india_interest_rate,
    macro_bank_japan_interest_rate,
    macro_bank_newzealand_interest_rate,
    macro_bank_russia_interest_rate,
    macro_bank_switzerland_interest_rate,
    macro_bank_usa_interest_rate,
)

"""
义乌小商品指数
"""
from akshare.index.index_yw import index_yw

"""
股票指数-股票指数-成份股
"""
from akshare.index.index_cons import (
    index_stock_info,
    index_stock_cons,
    index_stock_cons_sina,
    index_stock_cons_csindex,
    index_stock_cons_weight_csindex,
    stock_a_code_to_symbol,
)

"""
东方财富-股票账户
"""
from akshare.stock_feature.stock_account_em import stock_account_statistics_em

"""
期货规则
"""
from akshare.futures.futures_rule import futures_rule

"""
东方财富-商誉专题
"""
from akshare.stock_feature.stock_sy_em import (
    stock_sy_profile_em,
    stock_sy_yq_em,
    stock_sy_jz_em,
    stock_sy_em,
    stock_sy_hy_em,
)

"""
东方财富-股票质押
"""
from akshare.stock_feature.stock_gpzy_em import (
    stock_gpzy_pledge_ratio_em,
    stock_gpzy_profile_em,
    stock_gpzy_distribute_statistics_bank_em,
    stock_gpzy_distribute_statistics_company_em,
    stock_gpzy_industry_data_em,
    stock_gpzy_pledge_ratio_detail_em,
)

"""
东方财富-机构调研
"""
from akshare.stock_feature.stock_jgdy_em import (
    stock_jgdy_tj_em,
    stock_jgdy_detail_em,
)

"""
新浪主力连续接口
"""
from akshare.futures_derivative.futures_index_sina import (
    futures_main_sina,
    futures_display_main_sina,
)

"""
中国宏观杠杆率数据
"""
from akshare.economic.marco_cnbs import macro_cnbs

"""
大宗商品-现货价格指数
"""
from akshare.index.index_spot import spot_goods

"""
成本-世界各大城市生活成本
"""
from akshare.cost.cost_living import cost_living

"""
能源-碳排放权
"""
from akshare.energy.energy_carbon import (
    energy_carbon_domestic,
    energy_carbon_bj,
    energy_carbon_eu,
    energy_carbon_gz,
    energy_carbon_hb,
    energy_carbon_sz,
)

"""
中国证券投资基金业协会-信息公示
"""
from akshare.fund.fund_amac import (
    amac_manager_info,
    amac_member_info,
    amac_member_sub_info,
    amac_aoin_info,
    amac_fund_account_info,
    amac_fund_info,
    amac_fund_sub_info,
    amac_futures_info,
    amac_manager_cancelled_info,
    amac_securities_info,
    amac_fund_abs,
    amac_manager_classify_info,
    amac_person_fund_org_list,
    amac_person_bond_org_list,
)

"""
申万行业一级
"""
from akshare.index.index_sw import (
    sw_index_third_cons,
    sw_index_first_info,
    sw_index_second_info,
    sw_index_third_info,
)

"""
经济政策不确定性指数
"""
from akshare.article.epu_index import article_epu_index

"""
空气-河北
"""
from akshare.air.air_hebei import air_quality_hebei

"""
日出和日落
"""
from akshare.air.sunrise_tad import sunrise_daily, sunrise_monthly

"""
新浪-指数实时行情和历史行情
"""
from akshare.stock.stock_zh_a_tick_tx import (
    stock_zh_a_tick_tx_js,
)

"""
新浪-指数实时行情和历史行情
"""
from akshare.index.index_stock_zh import (
    stock_zh_index_daily,
    stock_zh_index_spot_sina,
    stock_zh_index_spot_em,
    stock_zh_index_daily_tx,
    stock_zh_index_daily_em,
)

"""
外盘期货实时行情
"""
from akshare.futures.futures_hq_sina import (
    futures_foreign_commodity_realtime,
    futures_foreign_commodity_subscribe_exchange_symbol,
    futures_hq_subscribe_exchange_symbol,
)

"""
FF多因子数据接口
"""
from akshare.article.ff_factor import article_ff_crr

"""
Realized Library 接口
"""
from akshare.article.risk_rv import (
    article_oman_rv,
    article_oman_rv_short,
    article_rlab_rv,
)

"""
银保监分局本级行政处罚数据
"""
from akshare.bank.bank_cbirc_2020 import bank_fjcf_table_detail

"""
科创板股票
"""
from akshare.stock.stock_zh_kcb_sina import (
    stock_zh_kcb_spot,
    stock_zh_kcb_daily,
)

"""
A股
"""
from akshare.stock.stock_zh_a_sina import (
    stock_zh_a_spot,
    stock_zh_a_daily,
    stock_zh_a_minute,
    stock_zh_a_cdr_daily,
)

"""
A+H股
"""
from akshare.stock.stock_zh_ah_tx import (
    stock_zh_ah_spot,
    stock_zh_ah_daily,
    stock_zh_ah_name,
)

"""
加密货币
"""
from akshare.economic.macro_other import crypto_js_spot

"""
金融期权
"""
from akshare.option.option_finance import (
    option_finance_board,
    option_finance_sse_underlying,
)

"""
新浪-美股实时行情数据和历史行情数据(前复权)
"""
from akshare.stock.stock_us_sina import (
    stock_us_daily,
    stock_us_spot,
    get_us_stock_name,
)

"""
新浪-港股实时行情数据和历史数据(前复权和后复权因子)
"""
from akshare.stock.stock_hk_sina import stock_hk_daily, stock_hk_spot

"""
生意社-商品与期货-现期图数据
"""
from akshare.futures_derivative.futures_spot_sys import futures_spot_sys

"""
全球宏观-机构宏观
"""
from akshare.economic.macro_constitute import (
    macro_cons_gold,
    macro_cons_silver,
    macro_cons_opec_month,
)

"""
全球宏观-美国宏观
"""
from akshare.economic.macro_usa import (
    macro_usa_eia_crude_rate,
    macro_usa_non_farm,
    macro_usa_unemployment_rate,
    macro_usa_adp_employment,
    macro_usa_core_pce_price,
    macro_usa_cpi_monthly,
    macro_usa_cpi_yoy,
    macro_usa_crude_inner,
    macro_usa_gdp_monthly,
    macro_usa_initial_jobless,
    macro_usa_lmci,
    macro_usa_api_crude_stock,
    macro_usa_building_permits,
    macro_usa_business_inventories,
    macro_usa_cb_consumer_confidence,
    macro_usa_core_cpi_monthly,
    macro_usa_core_ppi,
    macro_usa_current_account,
    macro_usa_durable_goods_orders,
    macro_usa_trade_balance,
    macro_usa_spcs20,
    macro_usa_services_pmi,
    macro_usa_rig_count,
    macro_usa_retail_sales,
    macro_usa_real_consumer_spending,
    macro_usa_ppi,
    macro_usa_pmi,
    macro_usa_personal_spending,
    macro_usa_pending_home_sales,
    macro_usa_nfib_small_business,
    macro_usa_new_home_sales,
    macro_usa_nahb_house_market_index,
    macro_usa_michigan_consumer_sentiment,
    macro_usa_exist_home_sales,
    macro_usa_export_price,
    macro_usa_factory_orders,
    macro_usa_house_price_index,
    macro_usa_house_starts,
    macro_usa_import_price,
    macro_usa_industrial_production,
    macro_usa_ism_non_pmi,
    macro_usa_ism_pmi,
    macro_usa_job_cuts,
    macro_usa_cftc_nc_holding,
    macro_usa_cftc_c_holding,
    macro_usa_cftc_merchant_currency_holding,
    macro_usa_cftc_merchant_goods_holding,
    macro_usa_cme_merchant_goods_holding,
    macro_usa_phs,
)

"""
全球宏观-中国宏观
"""
from akshare.economic.macro_china import (
    macro_china_bank_financing,
    macro_china_insurance_income,
    macro_china_mobile_number,
    macro_china_vegetable_basket,
    macro_china_agricultural_product,
    macro_china_agricultural_index,
    macro_china_energy_index,
    macro_china_commodity_price_index,
    macro_global_sox_index,
    macro_china_yw_electronic_index,
    macro_china_construction_index,
    macro_china_construction_price_index,
    macro_china_lpi_index,
    macro_china_bdti_index,
    macro_china_bsi_index,
    macro_china_cpi_monthly,
    macro_china_cpi_yearly,
    macro_china_m2_yearly,
    macro_china_fx_reserves_yearly,
    macro_china_cx_pmi_yearly,
    macro_china_pmi_yearly,
    macro_china_daily_energy,
    macro_china_non_man_pmi,
    macro_china_rmb,
    macro_china_gdp_yearly,
    macro_china_shrzgm,
    macro_china_ppi_yearly,
    macro_china_cx_services_pmi_yearly,
    macro_china_market_margin_sh,
    macro_china_market_margin_sz,
    macro_china_au_report,
    macro_china_exports_yoy,
    macro_china_hk_market_info,
    macro_china_imports_yoy,
    macro_china_trade_balance,
    macro_china_shibor_all,
    macro_china_industrial_production_yoy,
    macro_china_gyzjz,
    macro_china_lpr,
    macro_china_new_house_price,
    macro_china_enterprise_boom_index,
    macro_china_national_tax_receipts,
    macro_china_new_financial_credit,
    macro_china_fx_gold,
    macro_china_money_supply,
    macro_china_stock_market_cap,
    macro_china_cpi,
    macro_china_gdp,
    macro_china_ppi,
    macro_china_pmi,
    macro_china_gdzctz,
    macro_china_hgjck,
    macro_china_czsr,
    macro_china_whxd,
    macro_china_wbck,
    macro_china_xfzxx,
    macro_china_reserve_requirement_ratio,
    macro_china_consumer_goods_retail,
    macro_china_society_electricity,
    macro_china_society_traffic_volume,
    macro_china_postal_telecommunicational,
    macro_china_international_tourism_fx,
    macro_china_passenger_load_factor,
    macro_china_freight_index,
    macro_china_central_bank_balance,
    macro_china_insurance,
    macro_china_supply_of_money,
    macro_china_foreign_exchange_gold,
    macro_china_retail_price_index,
    macro_china_real_estate,
    macro_china_qyspjg,
    macro_china_fdi,
    macro_shipping_bci,
    macro_shipping_bcti,
    macro_shipping_bdi,
    macro_shipping_bpi,
    macro_china_urban_unemployment,
)

"""
全球宏观-中国宏观-国家统计局
"""
from akshare.economic.macro_china_nbs import (
    macro_china_nbs_nation,
    macro_china_nbs_region
)

"""
外汇
"""
from akshare.fx.fx_quote import fx_pair_quote, fx_spot_quote, fx_swap_quote

"""
债券行情
"""
from akshare.bond.bond_china import (
    bond_spot_quote,
    bond_spot_deal,
    bond_china_yield,
)

"""
商品期权
"""
from akshare.option.option_commodity import (
    option_dce_daily,
    option_czce_daily,
    option_shfe_daily,
    option_gfex_vol_daily,
    option_gfex_daily,
)

"""
99期货-期货库存数据
"""
from akshare.futures.futures_inventory_99 import futures_inventory_99

"""
东方财富-期货库存数据
"""
from akshare.futures.futures_inventory_em import futures_inventory_em

"""
中国银行间市场交易商协会
"""
from akshare.bond.bond_nafmii import bond_debt_nafmii

"""
奇货可查-工具模块
"""
from akshare.qhkc_web.qhkc_tool import qhkc_tool_foreign, qhkc_tool_gdp

"""
奇货可查-指数模块
"""
from akshare.qhkc_web.qhkc_index import (
    get_qhkc_index,
    get_qhkc_index_trend,
    get_qhkc_index_profit_loss,
)

"""
奇货可查-资金模块
"""
from akshare.qhkc_web.qhkc_fund import (
    get_qhkc_fund_money_change,
    get_qhkc_fund_bs,
    get_qhkc_fund_position,
)

"""
大宗商品现货价格及基差
"""
from akshare.futures.futures_basis import (
    futures_spot_price_daily,
    futures_spot_price,
    futures_spot_price_previous,
)

"""
期货持仓成交排名数据
"""
from akshare.futures.cot import (
    get_rank_sum_daily,
    get_rank_sum,
    get_shfe_rank_table,
    get_czce_rank_table,
    get_dce_rank_table,
    get_cffex_rank_table,
    futures_dce_position_rank,
    futures_dce_position_rank_other,
    futures_gfex_position_rank,
)

"""
大宗商品期货仓单数据
"""
from akshare.futures.receipt import get_receipt

"""
大宗商品期货展期收益率数据
"""
from akshare.futures.futures_roll_yield import (
    get_roll_yield_bar,
    get_roll_yield,
)

"""
交易所日线行情数据
"""
from akshare.futures.futures_daily_bar import (
    get_cffex_daily,
    get_czce_daily,
    get_shfe_daily,
    get_dce_daily,
    get_futures_daily,
    get_ine_daily,
    get_gfex_daily,
)

"""
雪球基金数据
"""
from akshare.fund.fund_xq import (
    fund_individual_basic_info_xq,
    fund_individual_achievement_xq,
    fund_individual_analysis_xq,
    fund_individual_profit_probability_xq,
    fund_individual_detail_info_xq,
    fund_individual_detail_hold_xq,
)

"""
异常处理模块
"""
from .exceptions import (
    AkshareException,
    APIError,
    DataParsingError,
    InvalidParameterError,
    NetworkError,
    RateLimitError,
)

"""
Pro API 设置
"""
from akshare.pro.data_pro import pro_api
from akshare.utils.token_process import set_token, get_token

"""
AKQMT 设置
"""
try:
    from akqmt import xt_api
except ImportError as e:
    pass
