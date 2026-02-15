"""
中国 A 股专用 Sizer
全仓买入，按 100 股（1手）取整
"""
import backtrader as bt


class CNAllInSizer(bt.Sizer):
    """
    中国 A 股全仓 Sizer：使用全部可用资金，按 100 股取整
    未指定仓位时默认全仓
    """
    params = (("stake", 100),)  # 最小交易单位 100 股

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            price = data.close[0] or 1.0
            if price <= 0:
                return 0
            # 全仓：可用资金 / 价格，向下取整到 100 股
            size = int(cash / price)
            size = (size // self.p.stake) * self.p.stake
            return max(0, size)
        # 卖出时由 broker 处理（平仓全部）
        return self.broker.getposition(data).size
