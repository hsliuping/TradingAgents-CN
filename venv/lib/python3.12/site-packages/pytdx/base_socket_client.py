# coding=utf-8

#
# Just for practising
#


import os
import socket
import sys
import pandas as pd

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(
        os.path.dirname(os.path.realpath(__file__))))

from pytdx.log import DEBUG, log
from pytdx.errors import TdxConnectionError, TdxFunctionCallError

import threading
import datetime
import time
from pytdx.heartbeat import HqHeartBeatThread
import functools
from pytdx.parser.raw_parser import RawParser


CONNECT_TIMEOUT = 5.000
RECV_HEADER_LEN = 0x10
DEFAULT_HEARTBEAT_INTERVAL = 10.0


"""
In [7]: 0x7e
Out[7]: 126

In [5]: len(body)
Out[5]: 8066

In [6]: len(body)/126
Out[6]: 64.01587301587301

In [7]: len(body)%126
Out[7]: 2

In [8]: (len(body)-2)/126
Out[8]: 64.0
"""


def update_last_ack_time(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kw):
        self.last_ack_time = time.time()
        log.debug("last ack time update to " + str(self.last_ack_time))
        current_exception = None
        try:
            ret = func(self, *args, **kw)
        except Exception as e:
            current_exception = e
            log.debug("hit exception on req exception is " + str(e))
            if self.auto_retry:
                for time_interval in self.retry_strategy.gen():
                    try:
                        time.sleep(time_interval)
                        self.disconnect()
                        self.connect(self.ip, self.port)
                        ret = func(self, *args, **kw)
                        if ret:
                            return ret
                    except Exception as retry_e:
                        current_exception = retry_e
                        log.debug(
                            "hit exception on *retry* req exception is " + str(retry_e))

                log.debug("perform auto retry on req ")

            self.last_transaction_failed = True
            ret = None
            if self.raise_exception:
                to_raise = TdxFunctionCallError("calling function error")
                to_raise.original_exception = current_exception if current_exception else None
                raise to_raise
        """
        如果raise_exception=True 抛出异常
        如果raise_exception=False 返回None
        """
        return ret
    return wrapper


class RetryStrategy(object):
    @classmethod
    def gen(cls):
        raise NotImplementedError("need to override")


class DefaultRetryStrategy(RetryStrategy):
    """
    默认的重试策略，您可以通过写自己的重试策略替代本策略, 改策略主要实现gen方法，该方法是一个生成器，
    返回下次重试的间隔时间, 单位为秒，我们会使用 time.sleep在这里同步等待之后进行重新connect,然后再重新发起
    源请求，直到gen结束。
    """
    @classmethod
    def gen(cls):
        # 默认重试4次 ... 时间间隔如下
        for time_interval in [0.1, 0.5, 1, 2]:
            yield time_interval


class TrafficStatSocket(socket.socket):
    """
    实现支持流量统计的socket类
    """

    def __init__(self, sock, mode):
        super(TrafficStatSocket, self).__init__(sock, mode)
        # 流量统计相关
        self.send_pkg_num = 0  # 发送次数
        self.recv_pkg_num = 0  # 接收次数
        self.send_pkg_bytes = 0  # 发送字节
        self.recv_pkg_bytes = 0  # 接收字节数
        self.first_pkg_send_time = None  # 第一个数据包发送时间

        self.last_api_send_bytes = 0  # 最近的一次api调用的发送字节数
        self.last_api_recv_bytes = 0  # 最近一次api调用的接收字节数


class BaseSocketClient(object):

    def __init__(self, multithread=False, heartbeat=False, auto_retry=False, raise_exception=False):
        self.need_setup = True
        if multithread or heartbeat:
            self.lock = threading.Lock()
        else:
            self.lock = None

        self.client = None
        self.heartbeat = heartbeat
        self.heartbeat_thread = None
        self.stop_event = None
        self.heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL  # 默认10秒一个心跳包
        self.last_ack_time = time.time()
        self.last_transaction_failed = False
        self.ip = None
        self.port = None

        # 是否重试
        self.auto_retry = auto_retry
        # 可以覆盖这个属性，使用新的重试策略
        self.retry_strategy = DefaultRetryStrategy()
        # 是否在函数调用出错的时候抛出异常
        self.raise_exception = raise_exception

    def connect(self, ip='101.227.73.20', port=7709, time_out=CONNECT_TIMEOUT, bindport=None, bindip='0.0.0.0'):
        """

        :param ip:  服务器ip 地址
        :param port:  服务器端口
        :param time_out: 连接超时时间
        :param bindport: 绑定的本地端口
        :param bindip: 绑定的本地ip
        :return: 是否连接成功 True/False
        """

        self.client = TrafficStatSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(time_out)
        log.debug("connecting to server : %s on port :%d" % (ip, port))
        try:
            self.ip = ip
            self.port = port
            if bindport is not None:
                self.client.bind((bindip, bindport))
            self.client.connect((ip, port))
        except socket.timeout as e:
            # print(str(e))
            log.debug("connection expired")
            if self.raise_exception:
                raise TdxConnectionError("connection timeout error")
            return False
        except Exception as e:
            if self.raise_exception:
                raise TdxConnectionError("other errors")
            return False

        log.debug("connected!")

        if self.need_setup:
            self.setup()

        if self.heartbeat:
            self.stop_event = threading.Event()
            self.heartbeat_thread = HqHeartBeatThread(
                self, self.stop_event, self.heartbeat_interval)
            self.heartbeat_thread.start()
        return self

    def disconnect(self):

        if self.heartbeat_thread and \
                self.heartbeat_thread.is_alive():
            self.stop_event.set()

        if self.client:
            log.debug("disconnecting")
            try:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
                self.client = None
            except Exception as e:
                log.debug(str(e))
                if self.raise_exception:
                    raise TdxConnectionError("disconnect err")
            log.debug("disconnected")

    def close(self):
        """
        disconnect的别名，为了支持 with closing(obj): 语法
        :return:
        """
        self.disconnect()

    def get_traffic_stats(self):
        """
        获取流量统计的信息
        :return:
        """
        if self.client.first_pkg_send_time is not None:
            total_seconds = (datetime.datetime.now() -
                             self.client.first_pkg_send_time).total_seconds()
            if total_seconds != 0:
                send_bytes_per_second = self.client.send_pkg_bytes // total_seconds
                recv_bytes_per_second = self.client.recv_pkg_bytes // total_seconds
            else:
                send_bytes_per_second = None
                recv_bytes_per_second = None
        else:
            total_seconds = None
            send_bytes_per_second = None
            recv_bytes_per_second = None

        return {
            "send_pkg_num": self.client.send_pkg_num,
            "recv_pkg_num": self.client.recv_pkg_num,
            "send_pkg_bytes": self.client.send_pkg_bytes,
            "recv_pkg_bytes": self.client.recv_pkg_bytes,
            "first_pkg_send_time": self.client.first_pkg_send_time,
            "total_seconds": total_seconds,
            "send_bytes_per_second": send_bytes_per_second,
            "recv_bytes_per_second": recv_bytes_per_second,
            "last_api_send_bytes": self.client.last_api_send_bytes,
            "last_api_recv_bytes": self.client.last_api_recv_bytes,
        }

    # for debuging and testing protocol
    def send_raw_pkg(self, pkg):
        cmd = RawParser(self.client, lock=self.lock)
        cmd.setParams(pkg)
        return cmd.call_api()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def to_df(self, v):
        if isinstance(v, list):
            return pd.DataFrame(data=v)
        elif isinstance(v, dict):
            return pd.DataFrame(data=[v, ])
        else:
            return pd.DataFrame(data=[{'value': v}])
