from google.protobuf import json_format

from tushare.subs.model.min import TsMin
from tushare.subs.model.tick import TsTick, TsTickIdx, TsTickOpt, TsTickFuture

datatype_map = {
    "TICK": 1,
    "TRANSACTION": 2,
    "ORDER": 3,
    "1MIN": 20,
    "5MIN": 21,
    "15MIN": 22,
    "30MIN": 23,
    "60MIN": 24,
    "1DAY": 25,
    "15SECOND": 26
}
datatype_map1 = {v: k for k, v in datatype_map.items()}


def _to_float(value):
    try:
        return float(value) / 10000
    except:
        return value


def recursive_to_price_float(data):
    if isinstance(data, dict):
        for k, v in data.items():
            if k.endswith('Px'):
                data[k] = _to_float(v)
            elif k.endswith('PriceQueue'):
                data[k] = [_to_float(v) for v in v]
            elif isinstance(v, dict):
                recursive_to_price_float(v)


def convert_ts_model(inst_data):
    recursive_to_price_float(inst_data)
    ts_inst = None
    if 'MIN' in inst_data.get('marketDataType'):
        ts_inst = convert_min_model(inst_data['marketDataType'].split('_')[-1].lower(), inst_data.get('mdKLine'))
    elif '15S' in inst_data.get('marketDataType'):
        ts_inst = convert_min_model(inst_data['marketDataType'].split('_')[-1].lower(), inst_data.get('mdKLine'))
    elif 'TICK' in inst_data.get('marketDataType') and 'mdStock' in inst_data:
        ts_inst = convert_tick_stock(inst_data.get('mdStock'))
    elif 'TICK' in inst_data.get('marketDataType') and 'mdFund' in inst_data:
        ts_inst = convert_tick_stock(inst_data.get('mdFund'))
    elif 'TICK' in inst_data.get('marketDataType') and 'mdBond' in inst_data:
        ts_inst = convert_tick_stock(inst_data.get('mdBond'))
    elif 'TICK' in inst_data.get('marketDataType') and 'mdIndex' in inst_data:
        ts_inst = convert_tick_index(inst_data.get('mdIndex'))
    elif 'TICK' in inst_data.get('marketDataType') and 'mdOption' in inst_data:
        ts_inst = convert_tick_option(inst_data.get('mdOption'))

    return ts_inst and dict(ts_inst) or None


def convert_min_model(freq, md_kline) -> TsMin:
    ds = str(md_kline.get('MDDate'))
    ts = str(md_kline.get('MDTime'))
    inst: TsMin = TsMin(
        ts_code=md_kline.get('HTSCSecurityID'),
        freq=freq,
        trade_time=f'{ds[:4]}-{ds[4:6]}-{ds[6:]} {ts[:-7]}:{ts[-7:-5]}',
        open=md_kline.get('OpenPx'),
        close=md_kline.get('ClosePx'),
        high=md_kline.get('HighPx'),
        low=md_kline.get('LowPx'),
        vol=md_kline.get('TotalVolumeTrade'),
        amount=md_kline.get('TotalValueTrade'),
        open_int=md_kline.get('KLineCategory', None)
    )
    return inst


def convert_tick_stock(md_stock) -> TsTick:
    ds = str(md_stock.get('MDDate'))
    ts = str(md_stock.get('MDTime'))
    inst: TsTick = TsTick(
        ts_code=md_stock.get('HTSCSecurityID'),
        name='',
        trade_time=f'{ds[:4]}-{ds[4:6]}-{ds[6:]} {ts[:-7]}:{ts[-7:-5]}:{ts[-5:-3]}',
        pre_price=md_stock.get('PreClosePx'),
        price=md_stock.get('LastPx'),
        open=md_stock.get('OpenPx'),
        high=md_stock.get('HighPx'),
        low=md_stock.get('LowPx'),
        close=md_stock.get('ClosePx'),
        vol=md_stock.get('TotalVolumeTrade'),
        amount=md_stock.get('TotalValueTrade'),
        count=md_stock.get('NumTrades')
    )
    for i, v in enumerate(md_stock.get('SellPriceQueue')):
        setattr(inst, f'ask_price{i+1}', v)
    for i, v in enumerate(md_stock.get('SellOrderQtyQueue')):
        setattr(inst, f'ask_volume{i+1}', v)
    for i, v in enumerate(md_stock.get('BuyPriceQueue')):
        setattr(inst, f'bid_price{i+1}', v)
    for i, v in enumerate(md_stock.get('BuyOrderQtyQueue')):
        setattr(inst, f'bid_volume{i+1}', v)

    return inst


def convert_tick_index(md_index) -> TsTickIdx:
    ds = str(md_index.get('MDDate'))
    ts = str(md_index.get('MDTime'))
    inst: TsTickIdx = TsTickIdx(
        ts_code=md_index.get('HTSCSecurityID'),
        name='',
        trade_time=f'{ds[:4]}-{ds[4:6]}-{ds[6:]} {ts[:-7]}:{ts[-7:-5]}:{ts[-5:-3]}',
        pre_close_price=md_index.get('PreClosePx'),
        last_price=int(md_index.get('LastPx', 0)),
        open_price=md_index.get('OpenPx'),
        high_price=md_index.get('HighPx'),
        low_price=md_index.get('LowPx'),
        close_price=md_index.get('ClosePx'),
        volume=md_index.get('TotalVolumeTrade'),
        amount=md_index.get('TotalValueTrade')
    )
    return inst


def convert_tick_option(md_option) -> TsTickOpt:
    ds = str(md_option.get('MDDate'))
    ts = str(md_option.get('MDTime'))
    inst: TsTickOpt = TsTickOpt(
        ts_code=md_option.get('HTSCSecurityID'),
        instrument_id='',
        trade_time=f'{ds[:4]}-{ds[4:6]}-{ds[6:]} {ts[:-7]}:{ts[-7:-5]}:{ts[-5:-3]}',
        pre_price=md_option.get('PreClosePx'),
        price=md_option.get('LastPx'),
        open=md_option.get('OpenPx'),
        high=md_option.get('HighPx'),
        low=md_option.get('LowPx'),
        close=md_option.get('ClosePx'),
        open_int=md_option.get('OpenInterest'),
        vol=md_option.get('TotalVolumeTrade'),
        amount=md_option.get('TotalValueTrade'),
        num=md_option.get('NumTrades'),
        ask_price1=md_option.get('BuyPriceQueue')[0],
        ask_volume1=md_option.get('BuyOrderQtyQueue')[0],
        bid_price1=md_option.get('SellPriceQueue')[0],
        bid_volume1=md_option.get('SellOrderQtyQueue')[0],
        pre_delta=md_option.get('PreDelta'),
        curr_delta=md_option.get('CurrDelta'),
        dif_price1=md_option.get('DiffPx1'),
        dif_price2=md_option.get('DiffPx2'),
        high_limit_price=md_option.get('MaxPx'),
        low_limit_price=md_option.get('MinPx'),
        refer_price=md_option.get('ReferencePx'),
    )
    return inst


def convert_tick_future(md_future) -> TsTickFuture:
    ds = str(md_future.get('MDDate'))
    ts = str(md_future.get('MDTime'))
    inst: TsTickFuture = TsTickFuture(
        ts_code=md_future.get('HTSCSecurityID'),
        trade_time=f'{ds[:4]}-{ds[4:6]}-{ds[6:]} {ts[:-7]}:{ts[-7:-5]}:{ts[-5:-3]}',
        pre_price=md_future.get('PreClosePx'),
        price=md_future.get('LastPx'),
        open=md_future.get('OpenPx'),
        high=md_future.get('HighPx'),
        low=md_future.get('LowPx'),
        close=md_future.get('ClosePx'),
        open_int=md_future.get('OpenInterest'),
        vol=md_future.get('TotalVolumeTrade'),
        amount=md_future.get('TotalValueTrade'),
        num=md_future.get('NumTrades'),
        ask_price1=md_future.get('BuyPriceQueue')[0],
        ask_volume1=md_future.get('BuyOrderQtyQueue')[0],
        bid_price1=md_future.get('SellPriceQueue')[0],
        bid_volume1=md_future.get('SellOrderQtyQueue')[0],
        pre_delta=md_future.get('PreDelta'),
        curr_delta=md_future.get('CurrDelta'),
        dif_price1=md_future.get('DiffPx1'),
        dif_price2=md_future.get('DiffPx2'),
        high_limit_price=md_future.get('MaxPx'),
        low_limit_price=md_future.get('MinPx'),
        refer_price=md_future.get('ReferencePx'),
        pre_settle_price=md_future.get('PreSettlePrice'),
        settle_price=md_future.get('SettlePrice'),
    )
    return inst

