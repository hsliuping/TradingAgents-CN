"""
# 作 者：84028
# 时 间：2024/2/21 22:16
# tsdpsdk
"""
# -*- coding: utf-8 -*-

# ------------------------------
# @Time    : 2023/6/15
# @Author  : gao
# @File    : tgw_login.py
# @Project : AmazingQuant
# ------------------------------
import tgw


class TgwLogSpi(tgw.ILogSpi):
    def __init__(self, log_level=2):
        self.log_level = log_level
        super().__init__()

    def OnLog(self, level, log, len):
        pass

    def OnLogon(self, data):
        pass


def login(username, password, host, port):
    log_spi = TgwLogSpi()
    tgw.SetLogSpi(log_spi)

    # 第二步，登录
    cfg = tgw.Cfg()
    cfg.username = username
    cfg.password = password

    cfg.server_vip = host
    cfg.server_port = port
    success = tgw.Login(cfg, tgw.ApiMode.kInternetMode)

    if not success:
        print("login fail")
        exit(0)
