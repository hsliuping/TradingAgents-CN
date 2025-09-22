from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TsTick(BaseModel):
    ts_code: str
    name: Optional[str]
    trade_time: Optional[datetime]
    pre_close_price: Optional[float]
    last_price: Optional[float]
    open_price: Optional[float]
    high_price: Optional[float]
    low_price: Optional[float]
    close_price: Optional[float]
    volume: Optional[int]           # 成交量
    amount: Optional[int]           # 成交金额
    count: Optional[int]            # 交易数量
    ask_price1: Optional[float]     # 申卖价, 委托档位卖1档价格
    ask_volume1: Optional[int]      # 申卖量
    bid_price1: Optional[float]     # 申买价, 委托档位买1档价格
    bid_volume1: Optional[int]      # 申买量
    ask_price2: Optional[float]
    ask_volume2: Optional[int]
    bid_price2: Optional[float]
    bid_volume2: Optional[int]
    ask_price3: Optional[float]
    ask_volume3: Optional[int]
    bid_price3: Optional[float]
    bid_volume3: Optional[int]
    ask_price4: Optional[float]
    ask_volume4: Optional[int]
    bid_price4: Optional[float]
    bid_volume4: Optional[int]
    ask_price5: Optional[float]
    ask_volume5: Optional[int]
    bid_price5: Optional[float]
    bid_volume5: Optional[int]
    ask_price6: Optional[float]
    ask_volume6: Optional[int]
    bid_price6: Optional[float]
    bid_volume6: Optional[int]
    ask_price7: Optional[float]
    ask_volume7: Optional[int]
    bid_price7: Optional[float]
    bid_volume7: Optional[int]
    ask_price8: Optional[float]
    ask_volume8: Optional[int]
    bid_price8: Optional[float]
    bid_volume8: Optional[int]
    ask_price9: Optional[float]
    ask_volume9: Optional[int]
    bid_price9: Optional[float]
    bid_volume9: Optional[int]
    ask_price10: Optional[float]
    ask_volume10: Optional[int]
    bid_price10: Optional[float]
    bid_volume10: Optional[int]


class TsTickIdx(BaseModel):
    ts_code: str
    name: Optional[str]
    trade_time: Optional[datetime]
    last_price: Optional[float]                 # last_price    单位元
    pre_close_price: Optional[float]            # pre_close_price
    high_price: Optional[float]                 # high_price
    open_price: Optional[float]                 # open_price
    low_price: Optional[float]                  # low_price
    close_price: Optional[float]                # close_price
    volume: Optional[int]                       # volume, 成交总量
    amount: Optional[float]                     # amount, 成交总金额


class TsTickOpt(BaseModel):
    ts_code: str
    instrument_id: str
    trade_time: Optional[datetime]
    pre_price: Optional[float]                  # 单位元
    price: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    open_int: Optional[int]
    vol: Optional[float]
    amount: Optional[float]
    num: Optional[int]
    ask_price1: Optional[float]
    ask_volume1: Optional[int]
    bid_price1: Optional[float]
    bid_volume1: Optional[int]
    pre_delta: Optional[float]              # 昨虚实度，暂未提供
    dif_price1: Optional[float]
    dif_price2: Optional[float]
    high_limit_price: Optional[float]
    low_limit_price: Optional[float]
    refer_price: Optional[float]            # 参考价，港股使用


class TsTickFuture(BaseModel):
    ts_code: str
    instrument_id: Optional[str]
    trade_time: Optional[datetime]
    pre_price: Optional[float]
    price: Optional[float]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    open_int: Optional[int]
    vol: Optional[int]
    amount: Optional[int]                  # 单数量
    num: Optional[int]
    ask_price1: Optional[float]
    ask_volume1: Optional[int]
    bid_price1: Optional[float]
    bid_volume1: Optional[int]
    pre_delta: Optional[float]
    curr_delta: Optional[float]
    dif_price1: Optional[float]
    dif_price2: Optional[float]
    high_limit_price: Optional[float]
    low_limit_price: Optional[float]
    refer_price: Optional[float]
    pre_settle_price: Optional[float]
    settle_price: Optional[float]
