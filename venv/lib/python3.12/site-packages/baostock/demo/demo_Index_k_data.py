import baostock as bs
import pandas as pd

#### 登陆系统 ####
lg = bs.login()
# 显示登陆返回信息
print('login respond error_code:'+lg.error_code)
print('login respond  error_msg:'+lg.error_msg)

#### 获取指数(综合指数、规模指数、一级行业指数、二级行业指数、策略指数、成长指数、价值指数、主题指数)K线数据 ####
##综合指数，例如：sh.000001 上证指数，sz.399106 深证综指 等；
##规模指数，例如：sh.000016 上证50，sh.000300 沪深300，sh.000905 中证500，sz.399001 深证成指等；
##一级行业指数，例如：sh.000037 上证医药，sz.399433 国证交运 等；
##二级行业指数，例如：sh.000952 300地产，sz.399951 300银行 等；
##策略指数，例如：sh.000050 50等权，sh.000982 500等权 等；
##成长指数，例如：sz.399376 小盘成长 等；
##价值指数，例如：sh.000029 180价值 等；
##主题指数，例如：sh.000015 红利指数，sh.000063 上证周期 等；

# 详细指标参数，参见“历史行情指标参数”章节
rs = bs.query_history_k_data_plus("sh.600000",
    "date,code,open,high,low,close,preclose,volume,amount,pctChg",
    start_date='2017-01-01', end_date='2017-06-30', 
    frequency="d", adjustflag="3")
print('query_history_k_data_plus respond error_code:'+rs.error_code)
print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)

#### 打印结果集 ####
data_list = []
while (rs.error_code == '0') & rs.next():
    # 获取一条记录，将记录合并在一起
    data_list.append(rs.get_row_data())
result = pd.DataFrame(data_list, columns=rs.fields)
#### 结果集输出到csv文件 ####   
result.to_csv("D:\\history_Index_k_data.csv", index=False)
print(result)

#### 登出系统 ####
bs.logout()