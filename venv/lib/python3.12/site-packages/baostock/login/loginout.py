# -*- coding:utf-8 -*-
"""
登录登出
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
"""
import zlib
import baostock.util.socketutil as sock
import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.data.messageheader as msgheader
import datetime
import baostock.common.context as conx


def login(user_id='anonymous', password='123456', options=0):
    """登录系统
    :param user_id:用户ID
    :param password:密码
    :param options:可选项，00.5.00版本暂未使用
    :return: ResultData()
    """

    data = rs.ResultData()
    if user_id is None or user_id == "":
        print("用户ID不能为空。")
        data.error_msg = "用户ID不能为空。"
        data.error_code = cons.BSERR_USERNAME_EMPTY
        return data

    setattr(conx, "user_id", user_id)

    if password is None or password == "":
        print("密码不能为空。")
        data.error_msg = "密码不能为空。"
        data.error_code = cons.BSERR_PASSWORD_EMPTY
        return data

    # 组织体信息
    msg_body = "login" + cons.MESSAGE_SPLIT + user_id + cons.MESSAGE_SPLIT + \
        password + cons.MESSAGE_SPLIT + str(options)

    # 组织头信息
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_LOGIN_REQUEST, len(msg_body))
    head_body = msg_header + msg_body

    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))

    # 发送并接收消息
    mySocketUtil = sock.SocketUtil()
    # 创建连接
    mySocketUtil.connect()

    receive_data = sock.send_msg(
        head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]

    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)

    data.msg_type = header_arr[1]
    data.msg_body_length = header_arr[2]

    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        print("login success!")
        data.method = body_arr[2]
        data.user_id = body_arr[3]
    else:
        print("login failed!")

    return data


def logout(user_id='anonymous'):
    """登出系统，默认用户ID：anonymous
    :param user_id:用户ID
    :return:ResultData()
    """

    now_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    if hasattr(conx, "user_id"):
        user_id = getattr(conx, "user_id")
        if user_id is None or user_id == "":
            print("you don't login, logout failed!")
            return

    # 组织体信息
    msg_body = "logout" + cons.MESSAGE_SPLIT + \
        user_id + cons.MESSAGE_SPLIT + now_time

    # 组织头信息
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_LOGOUT_REQUEST, len(msg_body))

    head_body = msg_header + msg_body

    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))

    # 发送并接收消息
    receive_data = sock.send_msg(
        head_body + cons.MESSAGE_SPLIT + str(crc32str))

    data = rs.ResultData()

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]

    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)

    data.msg_type = header_arr[1]
    data.msg_body_length = header_arr[2]

    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        print("logout success!")
        data.method = body_arr[2]
        data.user_id = body_arr[3]
    else:
        print("logout failed!")

    if hasattr(conx, "default_socket"):
        if getattr(conx, "default_socket") is not None:
            getattr(conx, "default_socket").close()

    return data


