"""
# 作 者：84028
# 时 间：2024/2/28 21:09
# tsdpsdk
"""
from datetime import datetime
from typing import Any

import tgw
from tushare.subs.model.tick import TsTick, TsTickIdx


def get_ts_code(_type: str, _code: str)->str:
    if _type == tgw.MarketType.kNEEQ:
        # 北交所
        return f'{_code}.BJ'
    elif _type == tgw.MarketType.kSSE:
        # 上交所
        return f'{_code}.SH'
    elif _type == tgw.MarketType.kSZSE:
        # 深交所
        return f'{_code}.SZ'
    else:
        raise Exception("未知类型，请联系管理员添加对应数据的解析！")


def get_tgw_type_and_code(_code: str) -> (Any, str):
    _code, _ext = _code.split('.', 1)
    _ext = _ext.upper()
    if _ext == 'BJ':
        # 北交所
        return tgw.MarketType.kNEEQ, _code
    elif _ext == 'SH':
        # 上交所
        return tgw.MarketType.kSSE, _code
    elif _ext == 'SZ':
        # 深交所
        return tgw.MarketType.kSZSE, _code
    else:
        raise Exception(f"未知类型，请联系管理员添加对应数据的解析！--{_ext}")


def convert_tick_index(tgw_data: dict) -> TsTickIdx:
    """
    index_demo = {
        'market_type': 101,
        'security_code': '000300',
        'orig_time': 20240227133145220, # 交易所行情数据时间
        'trading_phase_code': '',
        'pre_close_index': 3453358500,
        'open_index': 3440051600,
        'high_index': 3483385500,
        'low_index': 3437442200,
        'last_index': 3474362400,
        'close_index': 0,
        'total_volume_trade': 8934304600,
        'total_value_trade': 15930131603140000,
        'variety_category': 5
    }
    """
    item = TsTickIdx(
        ts_code=get_ts_code(tgw_data.get("market_type"), tgw_data.get("security_code")),
        name=None,
        trade_time=datetime.strptime(str(tgw_data.get('orig_time'))[:-3], '%Y%m%d%H%M%S'),
        last_price=tgw_data.get('last_index')/1000000,
        pre_close_price=tgw_data.get('pre_close_index')/1000000,
        open_price=tgw_data.get('open_index')/1000000,
        high_price=tgw_data.get('high_index')/1000000,
        low_price=tgw_data.get('low_index')/1000000,
        close_price=tgw_data.get('close_index')/1000000,
        volume=tgw_data.get('total_volume_trade')/100,
        amount=tgw_data.get('total_value_trade')/100000,
    )
    return item


def convert_tick_stock(tgw_data: dict) -> TsTick:
    """
    tick_demo = {
        'market_type': 101,
        'security_code': '600000',
        'variety_category': 1,
        'orig_time': 20240227133145832,             # 交易所行情数据时间
        'trading_phase_code': 'T111',
        'pre_close_price': 7100000,
        'open_price': 7070000,
        'high_price': 7150000,
        'low_price': 7060000,
        'last_price': 7110000,
        'close_price': 0,
        'total_volume_trade': 1621371900,
        'total_value_trade': 11528767100000,
        'bid_price1': 7110000,
        'bid_price2': 7100000,
        'bid_price3': 7090000,
        'bid_price4': 7080000,
        'bid_price5': 7070000,
        'bid_price6': 0,
        'bid_price7': 0,
        'bid_price8': 0,
        'bid_price9': 0,
        'bid_price10': 0,
        'bid_volume1': 20000,
        'bid_volume2': 26810000,
        'bid_volume3': 38450000,
        'bid_volume4': 33100000,
        'bid_volume5': 35720000,
        'bid_volume6': 0,
        'bid_volume7': 0,
        'bid_volume8': 0,
        'bid_volume9': 0,
        'bid_volume10': 0,
        'offer_price1': 7120000,
        'offer_price2': 7130000,
        'offer_price3': 7140000,
        'offer_price4': 7150000,
        'offer_price5': 7160000,
        'offer_price6': 0,
        'offer_price7': 0,
        'offer_price8': 0,
        'offer_price9': 0,
        'offer_price10': 0,
        'offer_volume1': 25400000,
        'offer_volume2': 28180000,
        'offer_volume3': 24750000,
        'offer_volume4': 63481800,
        'offer_volume5': 15723900,
        'offer_volume6': 0,
        'offer_volume7': 0,
        'offer_volume8': 0,
        'offer_volume9': 0,
        'offer_volume10': 0,
        'num_trades': 12339,
        'IOPV': 0,
        'high_limited': 7810000,
        'low_limited': 6390000
    }
    """
    extra = {}
    for i in range(1, 11):
        extra[f'ask_price{i}'] = tgw_data.get(f'offer_price{i}')/1000000
        extra[f'ask_volume{i}'] = tgw_data.get(f'offer_volume{i}')/100
        extra[f'bid_price{i}'] = tgw_data.get(f'bid_price{i}')/1000000
        extra[f'bid_volume{i}'] = tgw_data.get(f'bid_volume{i}')/100
    item = TsTick(
        ts_code=get_ts_code(tgw_data.get("market_type"), tgw_data.get("security_code")),
        name=None,
        trade_time=datetime.strptime(str(tgw_data.get('orig_time'))[:-3], '%Y%m%d%H%M%S'),
        pre_close_price=tgw_data.get("pre_close_price")/1000000,
        last_price=tgw_data.get("last_price")/1000000,
        open_price=tgw_data.get("open_price")/1000000,
        high_price=tgw_data.get("high_price")/1000000,
        low_price=tgw_data.get("low_price")/1000000,
        close_price=tgw_data.get("close_price")/1000000,
        volume=tgw_data.get("total_volume_trade")/100,
        amount=tgw_data.get("total_value_trade")/1000000,
        count=tgw_data.get("num_trades"),
        **extra
    )
    return item
