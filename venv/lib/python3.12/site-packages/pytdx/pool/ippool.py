#utf-8

import random
import threading
from functools import partial
from pytdx.log import DEBUG, log
import time
from collections import OrderedDict

"""
ips 应该还是一个 (ip ,port) 对的列表，如

[
    (ip1, port1),
    (ip2, port2),
    (ip3, port3),
]

"""

class BaseIPPool(object):

    def __init__(self, hq_class):
        self.hq_class = hq_class

    def setup(self):
        pass

    def teardown(self):
        pass

    def sync_get_top_n(self, num):
        pass

    def add_to_pool(self, ip):
        pass


class RandomIPPool(BaseIPPool):
    """
    获取一个随机的优先级列表
    """

    def __init__(self, hq_class, ips):
        """
        :param ips: ip should be a list
        """
        super(RandomIPPool, self).__init__(hq_class)
        self.ips = ips

    def get_ips(self):
        random.shuffle(self.ips)
        return self.ips

    def sync_get_top_n(self, num):
        ips= self.get_ips()
        return ips[:num]

    def add_to_pool(self, ip):
        if ip not in self.ips:
            self.ips.append(ip)


class AvailableIPPool(BaseIPPool):
    """
    测试可连接性，并根据连接速度排序
    我们启动一个新的线程，周期性的进行更新
    """

    def __init__(self, hq_class, ips):
        super(AvailableIPPool, self).__init__(hq_class)
        self.ips = ips
        self.sorted_ips = None
        self.worker_thread = None
        self.sorted_ips_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wait_interval = 20 * 60

    def setup(self):
        super(AvailableIPPool, self).setup()

        self.worker_thread = threading.Thread(target=self.run)
        self.worker_thread.start()

    def get_ips(self):
        if not self.sorted_ips:
            return self.ips
        else:
            return list(self.sorted_ips.values())

    def teardown(self):
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join()
        self.worker_thread = None

    def run(self):
        log.debug("pool thread start ")
        while not self.stop_event.is_set():
            _available_ips = self.get_all_available_ips()
            sorted_keys = sorted(_available_ips)
            with self.sorted_ips_lock:
                self.sorted_ips = OrderedDict((key, _available_ips[key]) for key in sorted_keys)
            self.stop_event.wait(self.wait_interval)

    def get_all_available_ips(self):
        """
        循环测试所有连接的连接速度和有效性
        :return:
        """
        _available_ips = OrderedDict()
        for ip in self.ips:
            ip_addr, port = ip
            api = self.hq_class(multithread=False, heartbeat=False)
            try:
                with api.connect(ip_addr, port):
                    start_ts = time.time()
                    api.do_heartbeat()
                    end_ts = time.time()
                    diff_ts = end_ts - start_ts
                    _available_ips[diff_ts] = ip
                    log.debug("time diff is %f for %s" % (diff_ts, _available_ips))
            except Exception as e:
                log.debug("can not use %s:%d the exception is %s" % (ip_addr, port, str(e)))
                continue
        return _available_ips

    def sync_get_top_n(self, num):
        _ips = list(self.get_all_available_ips().values())
        return _ips[:min(len(_ips), num)]

    def add_to_pool(self, ip):
        if ip not in self.ips:
            self.ips.append(ip)


if __name__ == "__main__":
    from pytdx.hq import TdxHq_API
    from pytdx.config.hosts import hq_hosts
    import logging
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    log.addHandler(ch)

    ips = [(v[1], v[2]) for v in hq_hosts]
    pool = AvailableIPPool(TdxHq_API, ips)
    pool.wait_interval = 60 * 5
    pool.setup()
    sleep_time = 130
    log.debug("ready to sleep %d" % sleep_time )
    time.sleep(sleep_time)
    log.debug("sleep done")
    ips = pool.get_ips()
    log.debug(str(pool.get_ips()))
    log.debug("ready to teardown")
    pool.teardown()



