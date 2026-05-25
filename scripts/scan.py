#!/usr/bin/env python3
"""
股票行情扫描脚本 - A股等突破扫描
"""

import sys
import os
import json
import traceback
from datetime import datetime
import pytz

try:
    import akshare as ak
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请运行: pip install akshare pandas numpy")
    sys.exit(1)


class StockScanner:
    """股票扫描器"""
    
    def __init__(self):
        self.tz = pytz.timezone('Asia/Shanghai')
        self.results = []
        self.errors = []
        
    def get_current_time(self):
        """获取当前北京时间"""
        return datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
    
    def scan_a_stock(self, symbol_list=None):
        """
        扫描A股行情
        """
        if symbol_list is None:
            symbol_list = ['000001', '000858', '001979', '000333']  # 平安银行、五粮液、小鹏汽车、美的集团
        
        print(f"📊 A股等突破扫描")
        print(f"扫描时间: {self.get_current_time()}")
        print(f"扫描股票: {', '.join(symbol_list)}")
        print("="*60)
        
        try:
            # 获取实时行情
            stock_data = ak.stock_zh_a_spot()
            
            if stock_data is None or stock_data.empty:
                self.errors.append("❌ 无法获取A股实时行情")
                return
            
            # 过滤目标股票
            for symbol in symbol_list:
                target = stock_data[stock_data['代码'] == symbol]
                if target.empty:
                    self.errors.append(f"⚠️ 股票代码 {symbol} 未找到")
                    continue
                
                row = target.iloc[0]
                self.process_stock(symbol, row)
            
        except Exception as e:
            error_msg = f"❌ 获取行情失败: {str(e)}"
            self.errors.append(error_msg)
            print(error_msg)
            traceback.print_exc()
    
    def process_stock(self, symbol, row):
        """
        处理单个股票数据
        """
        try:
            name = row.get('名称', '未知')
            price = float(row.get('最新价', 0))
            change_rate = float(row.get('涨跌幅', 0))
            change_amount = float(row.get('涨跌额', 0))
            volume = float(row.get('成交量', 0))
            high = float(row.get('最高', 0))
            low = float(row.get('最低', 0))
            
            # 分析突破信号
            analysis = self.analyze_breakthrough(price, change_rate, high, low)
            
            result = {
                'symbol': symbol,
                'name': name,
                'price': price,
                'change_rate': change_rate,
                'change_amount': change_amount,
                'volume': volume,
                'high': high,
                'low': low,
                'analysis': analysis,
                'signal': '🔴' if change_rate < -5 else '🟢' if change_rate > 5 else '⚪'
            }
            
            self.results.append(result)
            self.print_result(result)
            
        except Exception as e:
            self.errors.append(f"❌ 处理 {symbol} 失败: {str(e)}")
    
    def analyze_breakthrough(self, price, change_rate, high, low):
        """
        分析突破信号
        """
        signals = []
        
        if change_rate > 5:
            signals.append(f"📈 强势上升 (+{change_rate:.2f}%)")
        elif change_rate > 2:
            signals.append(f"📉 温和上升 (+{change_rate:.2f}%)")
        elif change_rate < -5:
            signals.append(f"📉 剧烈下跌 ({change_rate:.2f}%)")
        elif change_rate < -2:
            signals.append(f"📉 温和下跌 ({change_rate:.2f}%)")
        else:
            signals.append(f"➡️ 振荡 ({change_rate:.2f}%)")
        
        # 价格位置分析
        if high > 0:
            price_ratio = (price - low) / (high - low) if (high - low) > 0 else 0
            if price_ratio > 0.8:
                signals.append("⚡ 接近日高")
            elif price_ratio < 0.2:
                signals.append("💡 接近日低")
        
        return ' | '.join(signals) if signals else "无明显信号"
    
    def print_result(self, result):
        """
        打印单个结果
        """
        print(f"\n{result['signal']} {result['symbol']} {result['name']}")
        print(f"   价格: ¥{result['price']:.2f}  "
              f"涨幅: {result['change_rate']:+.2f}%  "
              f"涨额: ¥{result['change_amount']:+.2f}")
        print(f"   分析: {result['analysis']}")
    
    def print_summary(self):
        """
        打印摘要
        """
        print("\n" + "="*60)
        print("📋 扫描摘要")
        print("="*60)
        print(f"\n✅ 成功扫描: {len(self.results)} 只股票")
        
        if self.results:
            print("\n📊 涨幅排序:")
            sorted_results = sorted(self.results, key=lambda x: x['change_rate'], reverse=True)
            for i, r in enumerate(sorted_results[:5], 1):
                print(f"  {i}. {r['symbol']} {r['name']:8} "
                      f"{r['change_rate']:+.2f}% "
                      f"¥{r['price']:.2f}")
        
        if self.errors:
            print(f"\n⚠️ 错误信息: {len(self.errors)} 条")
            for error in self.errors[:3]:
                print(f"   {error}")
        
        print(f"\n⏰ 扫描完成: {self.get_current_time()}")
        print("="*60 + "\n")
    
    def export_json(self, filename='analysis_results.json'):
        """
        导出结果为 JSON
        """
        output = {
            'timestamp': self.get_current_time(),
            'results': self.results,
            'errors': self.errors,
            'total': len(self.results),
            'error_count': len(self.errors)
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 结果已导出: {filename}")
        return output


def main():
    """
    主函数
    """
    try:
        scanner = StockScanner()
        
        # 从命令行或环境变量获取股票列表
        symbols = os.getenv('STOCK_SYMBOLS', '000001,000858,001979,000333').split(',')
        symbols = [s.strip() for s in symbols if s.strip()]
        
        # 执行扫描
        scanner.scan_a_stock(symbols)
        
        # 打印摘要
        scanner.print_summary()
        
        # 导出结果
        scanner.export_json('analysis_results.json')
        
        # 返回成功
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 脚本执行失败: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
