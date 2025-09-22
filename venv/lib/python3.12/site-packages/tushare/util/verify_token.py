#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
token 验证
Created on 2023/12/06
@author: Monday
@group : waditu
@contact:
"""
from typing import Optional
from tushare.util.upass import get_token, set_token
import requests
from requests.adapters import HTTPAdapter, Retry
from tushare.stock import cons as ct


# 自定义异常类，用于权限不足时抛出异常
class PermissionError(Exception):
    pass


# 装饰器函数，用于进行权限验证
def require_permission(event_name, event_detail):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # event_name = kwargs["event_name"]
            # event_detail = kwargs["event_detail"]
            # 检查用户权限
            token = get_token()
            if token:
                try:
                    r = verify_token(token, event_name, event_detail).json()
                except Exception as err:
                    raise PermissionError(f"验证token出错，{err}")
                if r.get("message") == "success":
                    # 如果有足够权限，调用原始函数
                    return func(*args, **kwargs)
                else:
                    print(f"验证token出错，{r.text}")
                    raise PermissionError(f"{r['msg']}")
            else:
                raise PermissionError(ct.TOKEN_ERR_MSG)

        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def verify_token(token: Optional[str] = None, event_name: Optional[str] = "string",
                 event_detail: Optional[str] = "string"):
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1)
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    url = "https://api.tushare.pro/dataapi/sdk-event"
    data = {"user_token": token,
            "event_name": event_name,
            "event_detail": event_detail}
    response = session.post(url, headers=headers, json=data)
    return response


# 使用装饰器进行权限验证
@require_permission(event_name="xxx", event_detail="xxx")
def admin_only_function():
    print("ssss")


if __name__ == '__main__':
    set_token("asdasdasa")
    admin_only_function()  # 正常情况，输出执行信息
