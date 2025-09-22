"""
# 作 者：84028
# 时 间：2024/2/28 20:51
# tsdpsdk
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Union

import tgw
from ..model.tick import TsTick, TsTickIdx
from .convert import convert_tick_index, convert_tick_stock, get_tgw_type_and_code
from .login import login
from ... import get_token, set_token
from ...util.verify_token import verify_token

threadpool = ThreadPoolExecutor(5)


class TgwSubscribe(tgw.IPushSpi):
    def __init__(self, username, password, host, port=8600) -> None:
        super().__init__()
        self.callback_map = {}
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    def process_data(self, data):
        _type = data.get('variety_category')
        item = None
        if _type == tgw.VarietyCategory.kIndex:
            item = convert_tick_index(data)
        elif _type == tgw.VarietyCategory.kStock:
            item = convert_tick_stock(data)
        if item:
            func = self.callback_map.get(item.ts_code)
            if func and callable(func):
                func(item)

    def OnMDSnapshot(self, data, err):
        if data:
            threadpool.submit(self.process_data, data[0])
            pass
        else:
            print(err)

    def OnMDIndexSnapshot(self, data, err):
        if data:
            threadpool.submit(self.process_data, data[0])
        else:
            print(err)

    def register(self, ts_codes):
        def decorator(func):
            for ts_code in ts_codes:
                self.callback_map[ts_code] = func
            return func
        return decorator

    def run(self):
        token = get_token()
        r = verify_token(token, 'tgw_subscribe', self.username)
        if r.status_code == 200:
            resp_data = r.json()
            if resp_data.get("message") != "success":
                print(f"验证token出错，{r.text}")
                raise PermissionError(f"请先设置Tushare的token，{r['msg']}")

        login(username=self.username, password=self.password, host=self.host, port=self.port)
        items = []
        for ts_code in self.callback_map:
            t, c = get_tgw_type_and_code(ts_code)
            item = tgw.SubscribeItem()
            item.flag = tgw.SubscribeDataType.kSnapshot
            item.category_type = tgw.VarietyCategory.kStock
            item.security_code = c
            item.market = t
            items.append(item)
            item = tgw.SubscribeItem()
            item.flag = tgw.SubscribeDataType.kIndexSnapshot
            item.category_type = tgw.VarietyCategory.kIndex
            item.security_code = c
            item.market = t
            items.append(item)

        self.SetDfFormat(False)
        success = tgw.Subscribe(items, self)
        if success != tgw.ErrorCode.kSuccess:
            print(tgw.GetErrorMsg(success))
        while True:
            time.sleep(10)


def demo():
    set_token('xxxxxx')
    sub = TgwSubscribe(username='username', password='password', host='host', port=8600)

    @sub.register(ts_codes=['600000.SH', '000300.SH'])
    def just_print_index(data: Union[TsTick, TsTickIdx]):
        print(data)

    sub.run()
