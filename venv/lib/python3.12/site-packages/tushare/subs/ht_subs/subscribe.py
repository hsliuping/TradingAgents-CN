"""
# 作 者：84028
# 时 间：2024/2/28 21:00
# tsdpsdk
"""
import logging
import os
import time
from concurrent.futures.thread import ThreadPoolExecutor
from functools import wraps
from typing import Optional, Callable

from google.protobuf import json_format

from tushare.subs.ht_subs.covert import datatype_map, convert_ts_model

import sys

logger = logging.getLogger(__name__)

com_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(com_path)
sys.path.append(f'{com_path}/com')
sys.path.append(f"{com_path}/com/model")
sys.path.append(f"{com_path}/com/interface")
sys.path.append(f"{com_path}/com/libs")

thread_pool = ThreadPoolExecutor()


class InsightSubscribe(object):

    def __init__(self, user='', password='', ip='221.131.138.171', port=9362):
        self.user = user
        self.password = password
        self.ip = ip
        self.port = port

        open_trace = False
        open_file_log = False
        open_cout_log = False
        get_interface().init(open_trace, open_file_log, open_cout_log)

        self.login()
        self.subscribe_id_elements = set()
        self.subscribe_callbacks = set()
        self.subscribe_types = set()
        self.subscribe_codes = set()

    def login(self):
        istoken = False
        certfolder = f"{com_path}/com/cert"
        backup_list = mdc_gateway_interface.BackupList()
        get_interface().login(self.ip, self.port, self.user, self.password, istoken, certfolder, backup_list)

    def subscribe_start(self):
        """统一订阅app上所有的types-codes, 启动监听程序"""
        interface = get_interface()
        callback = OnRecvMarkertData()
        callback.OnMarketData = self.subscribe_callback
        interface.setCallBack(callback)
        interface.subscribeById(MDSubscribe.COVERAGE, list(self.subscribe_id_elements))

    def subscribe_callback(self, record):
        """回调所有的注册函数"""
        for cb in self.subscribe_callbacks:
            cb(record)

    def subscribe_register(self, datatypes=None, codes=None):
        if not datatypes or not codes:
            raise Exception("订阅内容不能为空！")
        market_data_type_list = []
        for datatype in datatypes:
            datatype = datatype.upper()
            if datatype not in datatype_map:
                raise Exception(f'非法的数据据类型 {datatype}')
            market_data_type_list.append(datatype_map[datatype])
        for code in codes:
            id_element = mdc_gateway_interface.SubscribeByIdElement(code, market_data_type_list)
            self.subscribe_id_elements.add(id_element)

        def decorator(func):
            # 回调函数
            def callback_func(record):
                inst_data = json_format.MessageToDict(record)
                # 判断type类型
                if record.marketDataType in market_data_type_list:
                    pass
                else:       # 没有命中
                    return
                # 判断 codes
                for v in inst_data.values():
                    if isinstance(v, dict) and 'HTSCSecurityID' in v:
                        _code = v['HTSCSecurityID']
                        if _code in codes:
                            break
                else:       # 没有命中
                    return
                # 回调函数
                try:
                    ts_record = convert_ts_model(inst_data)
                    thread_pool.submit(func, ts_record, inst_data)
                except Exception as ee:
                    logger.error(str(ee), exc_info=True)
            self.subscribe_callbacks.add(callback_func)

            @wraps(func)
            def inner(*args, **kwargs):
                """ should receive a message-value parameter """
                return func(*args, **kwargs)

            return inner
        return decorator

    @staticmethod
    def register_playback(datatype='', codes=None, start_date='20211103090000', end_date='20211103150000'):
        if not codes:
            raise Exception("订阅内容不能为空！")
        if '-' in start_date or ':' in start_date:
            start_date = start_date.replace('-', '').replace(' ', '').replace(':', '')
        if '-' in end_date or ':' in end_date:
            end_date = end_date.replace('-', '').replace(' ', '').replace(':', '')
        datatype = datatype.upper()
        if datatype.upper() not in datatype_map:
            raise Exception(f'非法的数据据类型 {datatype}')

        def decorator(func):
            # 回调函数
            def on_func(record):
                try:
                    for inst in record.marketDataStream.marketDataList.marketDatas:
                        inst_data = json_format.MessageToDict(inst)
                        ts_record = convert_ts_model(inst_data)
                        thread_pool.submit(func, ts_record, inst_data)
                except Exception as ee:
                    logger.error(str(ee), exc_info=True)
            callback = OnRecvMarkertData()
            callback.OnPlaybackPayload = on_func
            interface = get_interface()
            interface.setCallBack(callback)
            interface.playCallback(codes, datatype_map[datatype], MDPlayback.NO_EXRIGHTS, start_date, end_date)

            @wraps(func)
            def inner(*args, **kwargs):
                """ should receive a message-value parameter """
                return func(*args, **kwargs)
            return inner
        return decorator

    def run(self, stop_when: Optional[Callable] = None):
        """
        Parameters
        ----------
        stop_when  可执行对象， 当执行返回True时，退出订阅循环

        Returns
        -------
        """
        if self.subscribe_callbacks:
            self.subscribe_start()
            if isinstance(stop_when, Callable):
                while True:
                    time.sleep(5)
                    if stop_when():
                        return
            else:
                print("input 'stop' to exit >>>")
                line = input()
                if line == 'stop':
                    print("sync: input-->>" + str(line) + ",then exit this sync.")


def demo1(username, password):
    app = InsightSubscribe(user=username, password=password)

    @app.subscribe_register(datatypes=['TICK'], codes=["000001.SZ"])
    def print_subscribe_message(ts_record={}, ht_record_dict={}, *args, **kwargs):
        """
        订阅数据类型datatypes，并指定codes列表，
            datatype TICK, TRANSACTION, ORDER, 1MIN, 5MIN, 15MIN, 30MIN, 60MIN, 1DAY, 15SECOND
        :param
            ts_record_list:
                数据类型：列表
                字段说明参考 tushare.subs.model.min 和 tushare.subs.model.tick
            ht_record_dict
                数据类型：字典
                字段说明参考华泰的数据格式
        :return:
        """
        print(ts_record, ht_record_dict)
        logger.info('用户定义业务代码输出 print_message(%s)' % str(ts_record))

    # 程序启动后等待， 输入stop后推出
    app.run()


def demo2(username, password):
    app = InsightSubscribe(user=username, password=password)

    @app.register_playback(datatype='TICK', codes=["000001.SZ"], start_date='2021092413000000', end_date='20210924150000')
    def print_playback_message(ts_record={}, ht_record_dict={}, *args, **kwargs):
        """
        订阅数据类型datatype，并指定codes列表，
            datatype TICK, TRANSACTION, ORDER, 1MIN, 5MIN, 15MIN, 30MIN, 60MIN, 1DAY, 15SECOND
        :param
            ts_record_list:
                数据类型：列表
                字段说明参考 tushare.subs.model.min 和 tushare.subs.model.tick
            ht_record_dict
                数据类型：字典
                字段说明参考华泰的数据格式
        :return:
        """
        print(ts_record, ht_record_dict)
        logger.info('用户定义业务代码输出 print_message(%s)' % str(ts_record))

    # 数据回访完程序自动结束
    app.run()