def simple_quant_strategy(data):
    """
    最简单的量化策略示例
    :param data: 输入数据（如价格序列）
    :return: 交易信号
    """
    # 示例：均线策略
    if data['price'] > data['ma']:
        return "BUY"
    else:
        return "SELL"