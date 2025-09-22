#coding: utf-8

from __future__ import unicode_literals

import os
import tempfile
import click
import struct
import six
import zipfile
import uuid
import shutil

if six.PY2:
    from urllib import urlretrieve
else:
    from urllib.request import urlretrieve



TRADE_DLL_KEY = "http://rainx1982.coding.me/tts/Trade.dll"
TDX_TRADE_SEVER_KEY = "http://rainx1982.coding.me/tts/TdxTradeServer-Release-1.8_20180326103850.zip"



def main():

    # 1 give me a tmp dir

    base_dir = tempfile.gettempdir()
    dll_path = os.path.join(base_dir, "dll")
    download_path = os.path.join(base_dir, "download")
    try:
        if not os.path.isdir(dll_path):
            os.makedirs(dll_path)
    finally:
        pass

    try:
        if not os.path.isdir(download_path):
            os.makedirs(download_path)
    finally:
        pass

    # 2 确认是否要安装

    to_say = """
你好，您执行本命令将会启动TdxTradeServer程序的安装流程，安装程序会安装TdxTradeServer以及配置好其依赖的trade.dll,

注意： trade.dll来源于网络，TdxTradeServer仅对trade.dll做简单的封装，使其可以用于rest api ，并提供pytdx调用。
本程序没有对通达信的传输协议做任何研究，所有trade.dll和其绑定方式来源于网络。

[rest       ]   TdxTradeServer : https://github.com/rainx/TdxTradeServer
[client api ]   pytdx : https://github.com/rainx/pytdx

是否继续，将下载对应的trade.dll并配置。

Created by rainx with love!

    """
    click.secho(to_say, fg='green')

    yes_to_continue()

    se("开始下载trade.dll...")
    trade_dll_template = os.path.join(dll_path, "trade.dll")
    urlretrieve(TRADE_DLL_KEY, trade_dll_template)
    se("下载完成....")

    se("为了可以使用trade.dll，需要绑定账号")
    acc = click.prompt("请输入您的账号")
    se("您输入的账号是 {}".format(acc), fg="green")
    sig = make_sig(acc)
    se("正在生成可用的trade.dll绑定：sig is [{}]".format(sig))
    with open(trade_dll_template, 'rb') as f:
        content = f.read()

    real_trade_dll_name = "trade_pytdx_{}.dll".format(acc)
    real_trade_dll_path = os.path.join(dll_path, real_trade_dll_name)
    lenof_sig = len(sig)

    with open(real_trade_dll_path, "wb") as f:
        start_offset = 1132713
        f.write(content[:start_offset])
        f.write(sig)
        f.write(content[start_offset + lenof_sig:])
    se("写入完成，文件名称为 ： {}".format(real_trade_dll_path))

    se("开始下载TdxTradeServer....")
    download_and_setup_tdx_trade_server(download_path, dll_path, real_trade_dll_name)


def download_and_setup_tdx_trade_server(download_path, dll_path, real_trade_dll_name):
    zip_file_path = os.path.join(download_path, "tts.zip")
    urlretrieve(TDX_TRADE_SEVER_KEY, zip_file_path)
    print(download_path)

    if os.path.isfile(zip_file_path):
        se("下载完成")
    else:
        raise SystemExit("下载失败")

    se("开始解压")
    zf = zipfile.ZipFile(file=zip_file_path)
    zf.extractall(dll_path)
    zf.close()
    se("解压完成")

    config_file_content, bind_ip, bind_port, enc_key, enc_iv = gen_config_file(real_trade_dll_name)

    config_file_name = "TdxTradeServer.ini"
    with open(os.path.join(dll_path, config_file_name), "w") as f:
        f.write(config_file_content)
    se("配置文件写入完成，文件名 TdxTradeServer.ini")
    while True:
        _dir = click.prompt("请选择程序放置的路径", "C:\\TdxTradeServer")
        if os.path.exists(_dir):
            click.secho("该目录已存在，请选择一个新的路径")
        else:
            break

    os.makedirs(_dir)
    os.rmdir(_dir)
    shutil.copytree(dll_path, _dir)
    se("复制完成！ 请在路径 {} 下运行 TdxTradeServer.exe 启动服务".format(_dir), fg="green")

    se("客户端您可以使用pytdx的trade模块进行连接，下面是一小段示例代码演示如何初始化对象")

    demo_code = """
import os
from pytdx.trade import TdxTradeApi
api = TdxTradeApi(endpoint="http://{}:{}/api", enc_key=b"{}", enc_iv=b"{}")
print("---Ping---")
result = api.ping()
print(result)

print("---登入---")
acc = os.getenv("TDX_ACCOUNT", "") ###### 你的账号
password = os.getenv("TDX_PASS", "") ###### 你的密码
result = api.logon("<ip addr>", 7708,
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

    print("---登出---")
    print(api.logoff(client_id))
    """.format(bind_ip, bind_port, enc_key, enc_iv)

    demo_sample = """
from pytdx.trade import TdxTradeApi
api = TdxTradeApi(endpoint="http://{}:{}/api", enc_key=b"{}", enc_iv=b"{}")
    """.format(bind_ip, bind_port, enc_key, enc_iv)

    print("-"*30)
    print(demo_sample)
    print("-"*30)

    demo_path = os.path.join(_dir, "demo.py")
    with open(demo_path, "w") as f:
        f.write(demo_code)
    se("pytdx demo 演示代码在 {}".format(demo_path),fg="blue")
    se("注意 v1.5版本之后已经支持多账号版本，关于如何配置使用多账号版本，请参考 https://github.com/rainx/TdxTradeServer", fg="red")
    se("Happy Trading!", fg="green")


def gen_config_file(real_trade_dll_name):
    se("开始生成配置文件..")
    random_uuid = uuid.uuid1().hex
    enc_key = random_uuid[:16]
    enc_iv = random_uuid[16:]
    se("生成的enc_key = [{}] , enc_iv = [{}]".format(enc_key, enc_iv))
    bind_ip = click.prompt('请输入绑定的ip地址', default="127.0.0.1")
    bind_port = click.prompt('请输入绑定的端口号', default="19820")
    config_file_content = """bind={}
port={}
trade_dll_path={}
transport_enc_key={}
transport_enc_iv={}
""".format(bind_ip, bind_port, real_trade_dll_name, enc_key, enc_iv)

    return config_file_content, bind_ip, bind_port, enc_key, enc_iv



def yes_to_continue():
    while True:
        c = click.prompt('是否继续，继续请输入y, 退出输入n? ', default="y")
        if c.lower() == 'n':
            click.secho("您选择了退出")
            raise SystemExit("need to exit")
        elif c.lower() == "y" or c == "":
            return

def make_sig(acc):

    if type(acc) is six.text_type:
        acc = acc.encode("utf-8")

    a3 = 0x55e
    # 奇数位
    gpdm = acc[::2]
    # print("奇数位 ：{}".format(gpdm))

    result = b""
    for c in gpdm:

        if six.PY2:
            (c,) = struct.unpack("b", c)

        _next = True
        a = c
        b = a3 >> 0x8
        c = a ^ b
        a3 = (0x207f * (a3 + c) - 0x523d) & 0xffff
        j = 64
        while _next:
            j += 1
            if j > 90:
                break
            k = 91
            while _next:
                k -= 1
                if k < 65:
                    break

                temp = 1755 + c - k
                if temp % 26 == 0 and temp // 26 == j:

                    result += struct.pack("bb", j, k)
                    _next = False
    return result


def se(*args, **kwargs):
    _args = list(args)
    _args[0] = "[    pytdx   ] " + _args[0]
    click.secho(*_args, **kwargs)

if __name__ == '__main__':
    try:
        main()
        # gen_config_file()
    except SystemExit:
        exit()

