import unittest
from examples.quant.simple_strategy import simple_quant_strategy

class TestSimpleStrategy(unittest.TestCase):
    def test_buy_signal(self):
        data = {'price': 110, 'ma': 100}
        self.assertEqual(simple_quant_strategy(data), "BUY")

    def test_sell_signal(self):
        data = {'price': 90, 'ma': 100}
        self.assertEqual(simple_quant_strategy(data), "SELL")

if __name__ == "__main__":
    unittest.main()