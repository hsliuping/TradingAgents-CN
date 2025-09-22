# -*- coding:utf-8 -*-
"""
估值指标，季频
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
@copyright: baostock System & alpha.All Rights Reserved.
"""
import time
import zlib
import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.util.stringutil as strUtil
import baostock.common.context as conx
import baostock.util.socketutil as sock
import baostock.data.messageheader as msgheader


def query_dividend_data(code, year=None, yearType="report"):
    """估值指标（季频）,股息分红
    @param code: 证券代码，不可为空
    @param year: 年份，为空时默认当前年份
    @param yearType: 年份类别，默认为"report":预案公告年份，可选项"operate":除权除息年份
    """

    data = rs.ResultData()

    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())
    if yearType is None or yearType == "":
        print("年份类别输入有误，请修改。")
        data.error_msg = "年份类别输入有误，请修改。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_dividend_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, yearType)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYDIVIDENDDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYDIVIDENDDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.yearType = body_arr[9]
        data.setFields(body_arr[10])

    return data


def query_adjust_factor(code, start_date=None, end_date=None):
    """复权因子信息
    @param code: 证券代码，不可为空
    @param start_date: 起始除权除息日期，为空时默认2015-01-01）
    @param end_date: 终止除权除息日期，为空时默认当前时间
    """

    data = rs.ResultData()

    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if start_date is None or start_date == "":
        start_date = cons.DEFAULT_START_DATE
    if end_date is None or end_date == "":
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_adjust_factor", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, start_date, end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_ADJUSTFACTOR_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_ADJUSTFACTOR_REQUEST
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
        data.code = body_arr[7]
        data.start_date = body_arr[8]
        data.end_date = body_arr[9]
        data.setFields(body_arr[10])

    return data


def query_profit_data(code, year=None, quarter=None):
    """季频盈利能力
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_profit_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_PROFITDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_PROFITDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data


def query_operation_data(code, year=None, quarter=None):
    """季频营运能力
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_operation_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_OPERATIONDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_OPERATIONDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data


def query_growth_data(code, year=None, quarter=None):
    """季频成长能力
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_growth_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYGROWTHDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYGROWTHDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data


def query_dupont_data(code, year=None, quarter=None):
    """季频杜邦指数
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_dupont_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYDUPONTDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYDUPONTDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data


def query_balance_data(code, year=None, quarter=None):
    """季频偿债能力
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_balance_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYBALANCEDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYBALANCEDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data


def query_cash_flow_data(code, year=None, quarter=None):
    """季频现金流量
    @param code: 证券代码，不可为空
    @param year: 统计年份，为空时默认当前年
    @param quarter: 统计季度，为空时默认当前季度
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if year is None or year == "":
        year = time.strftime("%Y", time.localtime())  # 当前年份
    if quarter is None or quarter == "":
        quarter = (int(time.strftime("%m", time.localtime())) + 2) // 3  # 当前季度
    elif quarter not in [1, 2, 3, 4] and quarter not in ["1", "2", "3", "4"]:
        print("季度填写错误，请检查。填写范围：1，2，3，4")
        data.error_msg = "季度填写错误，请检查。填写范围：1，2，3，4"
        data.error_code = cons.BSERR_PARAM_ERR
    year = str(year)
    if not year.isdigit():
        print("年份输入有误，请修改。")
        data.error_msg = "年份输入有误，请修改。"
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

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_cash_flow_data", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, year, quarter)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYCASHFLOWDATA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYCASHFLOWDATA_REQUEST
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
        data.code = body_arr[7]
        data.year = body_arr[8]
        data.quarter = body_arr[9]
        data.setFields(body_arr[10])
    return data
