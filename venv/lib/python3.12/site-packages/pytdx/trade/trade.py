# -*- coding: utf-8 -*-
"""
Created on Mon Aug 21 14:24:31 2017

Trade 模块需要配合TdxTradeServer使用...

@author: RainX
"""
import requests
import urllib
import json
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from pytdx.log import log
except ImportError:
    log = lambda x:None

try:
    import pandas as pd
except ImportError as e:
    pass


class TdxTradeApiParams:

    """
    0 资金
    1 股份
    2 当日委托
    3 当日成交
    4 可撤单
    5 股东代码
    6 融资余额
    7 融券余额
    8 可融证券
    9
    10
    11
    12 可申购新股查询
    13 新股申购额度查询
    14 配号查询
    15 中签查询
    """
    QUERY_CATEGORY_CASH     = 0
    QUERY_CATEGORY_STOCKS   = 1
    QUERY_CATEGORY_ORDER_OF_TODAY       = 2
    QUERY_CATEGORY_DEAL_OF_TODAY        = 3
    QUERY_CATEGORY_CANCELABLE_ORDER     = 4
    QUERY_CATEGORY_SHAREHOLDERS_CODE    = 5
    QUERY_CATEGORY_BALANCE_OF_MARGIN_LOAN   = 6
    QUERY_CATEGORY_BALANCE_OF_STOCK_LOAN    = 7
    QUERY_CATEGORY_OPERABLE_MARGIN_SOTCK    = 8

    QUERY_CATEGORY_NEW_STOCKS       = 12
    QUERY_CATEGORY_NEW_STOCKS_QUOTA = 13
    QUERY_CATEGORY_NEW_STOCK_NUMBER = 14
    QUERY_CATEGORY_NEW_STOCK_HIT    = 15




class TdxTradeApi(object):
    def __init__(self, endpoint="http://127.0.0.1:10092/api", encoding="utf-8", enc_key=None, enc_iv=None):

        self._endpoint = endpoint
        self._encoding = "utf-8"
        if enc_key == None or enc_iv == None:
            self._transport_enc = False
            self._transport_enc_key = None
            self._transport_enc_iv = None
            self._cipher = None
        else:
            self._transport_enc = True
            self._transport_enc_key = enc_key
            self._transport_enc_iv = enc_iv
            backend = default_backend()
            self._cipher = Cipher(algorithms.AES(enc_key), modes.CBC(enc_iv), backend=backend)

        self._session = requests.Session()

    def call(self, func, params=None):

        json_obj = {
            "func": func
        }

        if params is not None:
            json_obj["params"] = params

        if self._transport_enc:
            data_to_send = self.encrypt(json_obj)
            response = self._session.post(self._endpoint, data=data_to_send)
        else:
            response = self._session.post(self._endpoint, json=json_obj)
        response.encoding = self._encoding
        text = response.text

        if self._transport_enc:
            decoded_text = self.decrypt(text)
            log.debug(decoded_text)
            return json.loads(decoded_text)
        else:
            return json.loads(text)

    def encrypt(self, source_obj):
        encrypter = self._cipher.encryptor()
        source = json.dumps(source_obj)
        source = source.encode(self._encoding)
        need_to_padding = 16 - (len(source) % 16)
        if need_to_padding > 0:
            source = source + b'\x00' * need_to_padding
        enc_data = encrypter.update(source) + encrypter.finalize()
        b64_enc_data = base64.encodebytes(enc_data)
        return urllib.parse.quote(b64_enc_data)

    def decrypt(self, source):
        decrypter = self._cipher.decryptor()
        source = urllib.parse.unquote(source)
        source = base64.decodebytes(source.encode("utf-8"))
        data_bytes = decrypter.update(source) + decrypter.finalize()
        return data_bytes.rstrip(b"\x00").decode(self._encoding)

    def data_to_df(self, result):
        if 'data' in result:
            data = result['data']
            return pd.DataFrame(data=data)

    #------ functions

    def ping(self):

        return self.call("ping", {})

    def logon(self, ip, port, version, yyb_id, account_id, trade_account, jy_passwrod, tx_password):
        return self.call("logon",{
            "ip": ip,
            "port": port,
            "version": version,
            "yyb_id": yyb_id,
            "account_no": account_id,
            "trade_account": trade_account,
            "jy_password": jy_passwrod,
            "tx_password": tx_password
        })

    def logoff(self, client_id):
        return self.call("logoff", {
            "client_id": client_id
        })

    def query_data(self, client_id, category):
        return self.call("query_data", {
            "client_id": client_id,
            "category": category
        })

    def send_order(self, client_id, category, price_type, gddm, zqdm, price, quantity):
        return self.call("send_order", {
            'client_id': client_id,
            'category': category,
            'price_type': price_type,
            'gddm': gddm,
            'zqdm': zqdm,
            'price': price,
            'quantity': quantity
        })

    def cancel_order(self, client_id, exchange_id, hth):
        return self.call("cancel_order", {
            'client_id': client_id,
            'exchange_id': exchange_id,
            'hth': hth
        })

    def get_quote(self, client_id, code):
        return self.call("get_quote", {
            'client_id': client_id,
            'code': code,
        })

    def repay(self, client_id, amount):
        return self.call("repay", {
            'client_id': client_id,
            'amount': amount
        })

    def query_history_data(self, client_id, category, begin_date, end_date):
        return self.call('query_history_data', {
            'client_id': client_id,
            'category': category,
            'begin_date': begin_date,
            'end_date': end_date
        })

    def query_datas(self, client_id, categories):
        return self.call('query_datas', {
            'client_id': client_id,
            'categories': categories
        })

    def get_quotes(self, client_id, codes):
        return self.call("get_quotes", {
            'client_id': client_id,
            'zqdms': codes
        })

    def send_orders(self, client_id, orders):
        """
        发送订单
        :param client_id:
        :param orders:
        格式
        [
            {
                "category": xx,
                "price_type" :xx,
                "price": xx,
                "gddm": xx,
                "zqdm": xx,
                "quantity": xx,
            },
            {
            ....
            },
            {
            ....
            }
        ]

        :return:
        """
        return self.call("send_orders", {
            'client_id': client_id,
            "orders": orders
        })

    def cancel_orders(self, client_id, orders):
        """
        撤销订单
        :param client_id:
        :param orders:
        格式
        [
            {
                "exchange_id": xx,
                "hth": xx
            },
            {
            ....
            },
            {
            ....
            }
        ]

        :return:
        """
        return self.call("cancel_orders", {
            'client_id': client_id,
            "orders": orders
        })

    def get_active_clients(self):
        return self.call(func="get_active_clients")

if __name__ == "__main__":
    import os
    #api = TdxTradeApi(endpoint="http://10.11.5.215:10092/api", enc_key=b"4f1cf3fec4c84c84", enc_iv=b"0c78abc083b011e7")
    api = TdxTradeApi(endpoint="http://10.11.5.215:10092/api")
    print("---Ping---")
    result = api.ping()
    print(result)

    print("---登入---")
    acc = os.getenv("TDX_ACCOUNT", "")
    password = os.getenv("TDX_PASS", "")
    result = api.logon("202.108.253.186", 7708,
              "8.23", 32,
              acc, acc, password, "")

    print(result)

    if result["success"]:
        client_id = result["data"]["client_id"]

        for i in (0,1,2,3,4,5,6,7,8,12,13,14,15):
            print("---查询信息 cate=%d--" % i)
            print(api.data_to_df(api.query_data(client_id, i)))


        print("---查询报价---")
        print(api.data_to_df(api.get_quote(client_id, '600315')))

        print("---批量查询报价---")
        print(api.data_to_df(api.get_quotes(client_id, ['600315', '000001'])))

        print("---批量查询信息")
        print(api.data_to_df(api.query_datas(client_id, [0,1,2])))

        print("---登出---")
        print(api.logoff(client_id))





