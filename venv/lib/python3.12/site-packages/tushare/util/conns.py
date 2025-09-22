# -*- coding:utf-8 -*- 
"""
connection for api 
Created on 2017/09/23
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
from tushare.stock import cons as ct


def api(retry_count=3):
    from pytdx.hq import TdxHq_API
    for _ in range(retry_count):
        try:
            api = TdxHq_API(heartbeat=True)
            api.connect(ct._get_server(), ct.T_PORT)
        except Exception as e:
            print(e)
        else:
            return api
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def xapi(retry_count=3):
    from pytdx.exhq import TdxExHq_API
    for _ in range(retry_count):
        try:
            api = TdxExHq_API(heartbeat=True)
            api.connect(ct._get_xserver(), ct.X_PORT)
        except Exception as e:
            print(e)
        else:
            return api
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def xapi_x(retry_count=3):
    from pytdx.exhq import TdxExHq_API
    for _ in range(retry_count):
        try:
            api = TdxExHq_API(heartbeat=True)
            api.connect(ct._get_xxserver(), ct.X_PORT)
        except Exception as e:
            print(e)
        else:
            return api
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def get_apis():
    return api(), xapi()


def close_apis(conn):
    api, xapi = conn
    try:
        api.disconnect()
        xapi.disconnect()
    except Exception as e:
        print(e)
