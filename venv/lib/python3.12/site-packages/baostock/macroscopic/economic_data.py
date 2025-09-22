# -*- coding:utf-8 -*-
"""
宏观数据，宏观经济数据
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
@copyright: baostock System & alpha.All Rights Reserved.
"""
import time
import zlib
import datetime
import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.util.stringutil as strUtil
import baostock.common.context as conx
import baostock.util.socketutil as sock
import baostock.data.messageheader as msgheader


def query_deposit_rate_data(start_date="", end_date=""):
    """存款利率
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_deposit_rate_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYDEPOSITRATEDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYDEPOSITRATEDATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_loan_rate_data(start_date="", end_date=""):
    """贷款利率
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_loan_rate_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYLOANRATEDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYLOANRATEDATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_required_reserve_ratio_data(start_date="", end_date="", yearType="0"):
    """存款准备金率
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    @param yearType: 日期类型，默认0为公告日期，1为生效日期
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    if yearType is None or yearType == "":
        print("年份类别输入有误，请修改。")
        data.error_msg = "年份类别输入有误，请修改。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_required_reserve_ratio_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date) + "," + str(yearType)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUREYREQUIREDRESERVERATIODATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUREYREQUIREDRESERVERATIODATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.yearType = body_arr[9]
        data.setFields(body_arr[10])

    return data


def query_money_supply_data_month(start_date="", end_date=""):
    """货币供应量
    @param sart_date: 起始年月yyyy-MM，包含次此日期，可为空
    @param end_date: 结束年月yyyy-MM，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_year_month_date(start_date):
            pass
        else:
            print("起始日期格式不正确，应为：yyyy-mm，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，应为：yyyy-mm，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_year_month_date(end_date):
            pass
        else:
            print("结束日期格式不正确，应为：yyyy-mm，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，应为：yyyy-mm，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(start_date, '%Y-%m')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_money_supply_data_month," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYMONEYSUPPLYDATAMONTH_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYMONEYSUPPLYDATAMONTH_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_money_supply_data_year(start_date="", end_date=""):
    """货币供应量（年底余额）
    @param sart_date: 起始年份yyyy，包含次此年份，可为空
    @param end_date: 结束年份yyyy，包含次此年份，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_year_date(start_date):
            pass
        else:
            print("起始日期格式不正确，应为：yyyy，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，应为：yyyy，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_year_date(end_date):
            pass
        else:
            print("结束日期格式不正确，应为：yyyy，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，应为：yyyy，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(start_date, '%Y')
        end_date_time = datetime.datetime.strptime(end_date, '%Y')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_money_supply_data_year," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYMONEYSUPPLYDATAYEAR_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYMONEYSUPPLYDATAYEAR_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data





def query_cpi_data(start_date="", end_date=""):
    """居民价格消费指数
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_cpi_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYCPIDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYCPIDATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_ppi_data(start_date="", end_date=""):
    """工业品出厂价格指数
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_ppi_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYPPIDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYPPIDATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_pmi_data(start_date="", end_date=""):
    """采购经理人指数
    @param sart_date: 起始日期，包含次此日期，可为空
    @param end_date: 结束日期，包含次此日期，可为空
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = ""
    else:
        if strUtil.is_valid_date(start_date):
            pass
        else:
            print("起始日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "起始日期格式不正确，请修改。"
            return data
    if end_date is None or end_date == "":
        end_date = ""
    else:
        if strUtil.is_valid_date(end_date):
            pass
        else:
            print("结束日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "结束日期格式不正确，请修改。"
            return data
    if start_date != "" and end_date != "":
        start_date_time = datetime.datetime.strptime(
            start_date, '%Y-%m-%d')
        end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        if end_date_time < start_date_time:
            print("起始日期大于结束日期，请修改。")
            data.error_code = cons.BSERR_START_BIGTHAN_END
            data.error_msg = "起始日期大于结束日期，请修改。"
            return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_pmi_data," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(start_date) + "," + str(end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYPMIDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYPMIDATA_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data

