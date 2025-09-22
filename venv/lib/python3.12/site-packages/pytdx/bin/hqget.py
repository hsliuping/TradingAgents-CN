# coding=utf-8
from __future__ import unicode_literals

import os
import sys
import click

from collections import OrderedDict
import pprint

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

from pytdx.hq import TdxHq_API
from pytdx.params import TDXParams
from pytdx.config.hosts import hq_hosts
import pandas as pd
import pickle
from functools import reduce


# 让pandas 显示全部数据
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

mtstr = os.getenv("TDX_MT", "")
mt = False
if mtstr:
    mt = True

api = TdxHq_API(multithread=mt)


def get_security_quotes(params):
    market, code = params
    stocks = api.get_security_quotes([(int(market), code),])
    return (stocks)

def get_security_bars(params):
    category, market, code, start, count = params
    return (api.get_security_bars(int(category), int(market), code, int(start), int(count)))

def get_security_count(params):
    return (api.get_security_count(int(params[0])))

def get_security_list(params):
    return (api.get_security_list(int(params[0]), int(params[1])))

def get_index_bars(params):
    category, market, code, start, count = params
    return (api.get_index_bars(int(category), int(market), code, int(start), int(count)))

def get_minute_time_data(params):
    return (api.get_minute_time_data(int(params[0]), params[1]))

def get_history_minute_time_data(params):
    return (api.get_history_minute_time_data(int(params[0]), params[1], int(params[2])))

def get_transaction_data(params):
    return (api.get_transaction_data(int(params[0]), params[1], int(params[2]), int(params[3])))

def get_history_transaction_data(params):
    return (api.get_history_transaction_data(int(params[0]), params[1], int(params[2]), int(params[3]), int(params[4])))

def get_company_info_category(params):
    return (api.get_company_info_category(int(params[0]), params[1]))

def get_company_info_content(params):
    return (api.get_company_info_content(int(params[0]), params[1].encode("utf-8"), params[2].encode("utf-8"), int(params[3]), int(params[4])))

def get_xdxr_info(params):
    return (api.get_xdxr_info(int(params[0]), params[1]))

def get_finance_info(params):
    return (api.get_finance_info(int(params[0]), params[1]))

FUNCTION_LIST = OrderedDict(
    [
        (1, ['获取股票行情', '参数：市场代码， 股票代码， 如： 0,000001 或 1,600300', get_security_quotes, '0,000001']),
        (2, ['获取k线', '''category-> K线种类
0 5分钟K线 1 15分钟K线 2 30分钟K线 3 1小时K线 4 日K线
5 周K线
6 月K线
7 1分钟
8 1分钟K线 9 日K线
10 季K线
11 年K线
market -> 市场代码 0:深圳，1:上海
stockcode -> 证券代码;
start -> 指定的范围开始位置;
count -> 用户要请求的 K 线数目，最大值为 800

如： 9,0,000001,0,100''', get_security_bars, '9,0,000001,0,100']),
        (3, ['获取市场股票数量', '参数：市场代码， 股票代码， 如： 0 或 1', get_security_count, '0']),
        (4, ['获取股票列表', '参数：市场代码, 起始位置， 数量  如： 0,0 或 1,100', get_security_list, '0,0']),
        (5, ['获取指数k线', """参数:
category-> K线种类
0 5分钟K线 1 15分钟K线 2 30分钟K线 3 1小时K线 4 日K线
5 周K线
6 月K线
7 1分钟
8 1分钟K线 9 日K线
10 季K线
11 年K线
market -> 市场代码 0:深圳，1:上海
stockCode -> 证券代码;
start -> 指定的范围开始位置; count -> 用户要请求的 K 线数目
如：9,1,000001,0,100""", get_index_bars, '9,1,000001,0,100']),
        (6, ['查询分时行情', "参数：市场代码， 股票代码， 如： 0,000001 或 1,600300", get_minute_time_data, '0,000001']),
        (7, ['查询历史分时行情', '参数：市场代码， 股票代码，时间 如： 0,000001,20161209 或 1,600300,20161209', get_history_minute_time_data, '0,000001,20161209']),
        (8, ['查询分笔成交', '参数：市场代码， 股票代码，起始位置， 数量 如： 0,000001,0,10', get_transaction_data, '0,000001,0,10']),
        (9, ['查询历史分笔成交', '参数：市场代码， 股票代码，起始位置，日期 数量 如： 0,000001,0,10,20170209', get_history_transaction_data, '0,000001,0,10,20170209']),
        (10, ['查询公司信息目录','参数：市场代码， 股票代码， 如： 0,000001 或 1,600300', get_company_info_category, '0,000001']),
        (11, ['读取公司信息详情', '参数：市场代码， 股票代码, 文件名, 起始位置， 数量, 如：0,000001,000001.txt,2054363,9221', get_company_info_content, '0,000001,000001.txt,0,10']),
        (12, ['读取除权除息信息', '参数：市场代码， 股票代码， 如： 0,000001 或 1,600300', get_xdxr_info, '0,000001']),
        (13, ['读取财务信息', '参数：市场代码， 股票代码， 如： 0,000001 或 1,600300', get_finance_info, '0,000001']),
    ]
)

#  1 :               招商证券深圳行情    119.147.212.81:7709
#  2 :             华泰证券(南京电信)    221.231.141.60:7709
#  3 :             华泰证券(上海电信)    101.227.73.20:7709
#  4 :           华泰证券(上海电信二)    101.227.77.254:7709
#  5 :        zz

SERVERS = OrderedDict([
(1, ['招商证券深圳行情', '119.147.212.81:7709']),
(2, ['华泰证券(南京电信)', '221.231.141.60:7709']),
(3, ['华泰证券(上海电信)', '101.227.73.20:7709']),
(4, ['华泰证券(上海电信二)', '101.227.77.254:7709']),
(5, ['华泰证券(深圳电信)', '14.215.128.18:7709']),
(6, ['华泰证券(武汉电信)', '59.173.18.140:7709']),
(7, ['华泰证券(天津联通)', '60.28.23.80:7709']),
(8, ['华泰证券(沈阳联通)', '218.60.29.136:7709']),
(9, ['华泰证券(南京联通)', '122.192.35.44:7709']),
(10, ['华泰证券(南京联通)', '122.192.35.44:7709']),
])

def connect():
    while True:
        click.secho("请选择服务器")
        click.secho("-" * 20)
        for k,v in SERVERS.items():
            click.secho("[%d] :%s (%s)" % (k, v[0], v[1]))
        click.secho("-" * 20)
        num = click.prompt("请输入序号 ", type=int, default=1)
        if num not in SERVERS:
            click.echo("序号错误")
            continue
        ip,port = SERVERS[num][1].split(":")

        c = api.connect(ip, int(port))
        if not c:
            raise Exception("无法连接")
        else:
            break

def connect_to(ipandport):
    ip, port = ipandport.split(":")
    c = api.connect(ip, int(port))
    if not c:
        raise Exception("无法连接")

def disconnect():
    api.disconnect()

if sys.version_info[0] == 2:
    reload(sys)
    sys.setdefaultencoding('utf8')

FUNCTION_LIST_STR = "0 : 使用交互式接口\n"
for x, y in FUNCTION_LIST.items():
    FUNCTION_LIST_STR = FUNCTION_LIST_STR + str(x) + " : " + y[0] + "\n"

@click.command()
@click.option('-f', '--function', default=0, type=click.INT, help="选择使用的功能" + "\n" + FUNCTION_LIST_STR)
@click.option('--df/--no-df', default=True, help="是否使用Pandas Dataframe显示")
@click.option('-o', '--output', default="-", help="保存到文件，默认不保存")
@click.option('-s', '--server', default="-", type=click.STRING, help="连接的服务器，设定之后直接连接该服务器，无需选择" )
@click.option('--all/--no-all', default=False, help="显示全部服务器列表")
def main(function, df, output, server, all):
    """
    股票行情获取程序， 作者RainX<i@rainx.cc>
    """

    if all:
        global SERVERS
        SERVERS = OrderedDict([(idx+1, [host[0], "%s:%s" % (host[1], host[2])]) for idx, host in enumerate(hq_hosts)])

    click.secho("连接中.... ", fg="green")
    if server == '-':
        connect()
    else:
        connect_to(server)

    click.secho("连接成功！", fg="green")
    if function == 0:

        while True:
            click.secho("-" * 20)
            click.secho("功能列表：")
            for (k,v) in FUNCTION_LIST.items():
                click.secho(str(k) + " : " + v[0], bold=True)
                last = k + 1
            click.secho(str(last) + " : 退出断开连接", bold=True)
            click.secho("-" * 20)
            value = click.prompt('请输入要使用的功能', type=int)
            if value == last:
                break
            run_function(df, value)
            click.secho("-" * 20)
            click.echo("按任意键继续")
            click.getchar()
    elif function in FUNCTION_LIST.keys():
        value = function
        result = run_function(df, value)

        if (result is not None) and (output != "-"):
            click.secho("写入结果到 " + output)
            if isinstance(result, pd.DataFrame):
                result.to_csv(output)
            else:
                with open(output, "wb") as f:
                    pickle.dump(result, f)

    click.secho("断开连接中.... ", fg="green")
    disconnect()
    click.secho("断开连接成功！", fg="green")


def run_function(df, value):
    click.secho("你选择的是功能 " + str(value) + " : " + FUNCTION_LIST[value][0])
    click.secho("-" * 20)
    click.secho(FUNCTION_LIST[value][1])
    params_str = click.prompt("请输入参数 ", type=str, default=FUNCTION_LIST[value][3])
    params = [p.strip() for p in params_str.split(",")]
    click.secho("-" * 20)
    try:
        result = FUNCTION_LIST[value][2](params)
        if df:
            result = api.to_df(result)
            click.secho(str(result), bold=True)
            return result
        else:
            pprint.pprint(result)
            return result
    except Exception as e:
        import traceback
        print('-' * 60)
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)
        click.secho("发生错误，错误信息为： " + str(e), fg='red')


if __name__ == '__main__':
    main()