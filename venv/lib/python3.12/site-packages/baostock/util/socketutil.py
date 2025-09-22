# -*- coding:utf-8 -*-
"""
获取默认socket
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
"""
import time
import socket
import threading
import zlib
import baostock.common.contants as cons
import baostock.common.context as context


class SocketUtil(object):
    """Socket工具类"""
    # 记录第一个被创建对象的引用
    instance = None
    # 记录是否执行过初始化动作
    init_flag = False

    def __new__(cls, *args, **kwargs):
        # 1. 判断类属性是否是空对象
        if cls.instance is None:
            # 2. 调用父类的方法，为第一个对象分配空间
            cls.instance = super().__new__(cls)
        # 3. 返回类属性保存的对象引用
        return cls.instance

    def __init__(self):
        SocketUtil.init_flag = True

    def connect(self):
        """创建连接"""
        try:
            mySockect = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mySockect.connect((cons.BAOSTOCK_SERVER_IP, cons.BAOSTOCK_SERVER_PORT))
        except Exception:
            print("服务器连接失败，请稍后再试。")
        setattr(context, "default_socket", mySockect)


def get_default_socket():
    """获取默认连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((cons.BAOSTOCK_SERVER_IP, cons.BAOSTOCK_SERVER_PORT))
    except Exception:
        print("服务器连接失败，请稍后再试。")
        return None
    return sock


def send_msg(msg):
    """发送消息，并接受消息 """
    try:
        # default_socket = get_default_socket()
        if hasattr(context, "default_socket"):
            default_socket = getattr(context, "default_socket")
            if default_socket is not None:
                # str 类型 -> bytes 类型
                # msg = msg + "<![CDATA[]]>"  # 在消息结尾追加“消息之间的分隔符”，压缩时的分隔符
                msg = msg + "\n"  # 在消息结尾追加“消息之间的分隔符”，不压缩时的分隔符
                default_socket.send(bytes(msg, encoding='utf-8'))
                receive = b""
                while True:
                    recv = default_socket.recv(8192)
                    receive += recv
                    # 判断是否读取完
                    if receive[-13:] == b"<![CDATA[]]>\n":  # 压缩时的结尾分隔符长度
                    # if receive[-1:] == b"\n":  # 不压缩时的结尾分隔符长度
                        break
                # return bytes.decode(zlib.decompress(receive))  # 进行解压
                head_bytes = receive[0:cons.MESSAGE_HEADER_LENGTH]
                head_str = bytes.decode(head_bytes)
                head_arr = head_str.split(cons.MESSAGE_SPLIT)
                if head_arr[1] in cons.COMPRESSED_MESSAGE_TYPE_TUPLE:
                    # 消息体需要解压
                    head_inner_length = int(head_arr[2])
                    body_str = bytes.decode(zlib.decompress(receive[cons.MESSAGE_HEADER_LENGTH:cons.MESSAGE_HEADER_LENGTH + head_inner_length]))
                    return head_str + body_str
                else:
                    return bytes.decode(receive)  # 不进行解压
            else:
                return None
        else:
            print("you don't login.")
    except Exception as ex:
        print(ex)
        print("接收数据异常，请稍后再试。")


