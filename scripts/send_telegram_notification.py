#!/usr/bin/env python3
"""
Telegram 通知脚本
"""

import sys
import os
import json
import argparse
from datetime import datetime
import pytz

try:
    import requests
except ImportError:
    print("❌ requests 库未安装")
    print("请运行: pip install requests")
    sys.exit(1)


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.tz = pytz.timezone('Asia/Shanghai')
    
    def get_current_time(self):
        """获取当前北京时间"""
        return datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
    
    def send_message(self, text, parse_mode='HTML'):
        """
        发送文本消息
        """
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Telegram 消息发送成功")
                return True
            else:
                print(f"❌ Telegram 消息发送失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 发送消息异常: {str(e)}")
            return False
    
    def format_analysis_results(self, results):
        """
        格式化分析结果
        """
        lines = [
            "<b>📊 A股等突破扫描结果</b>",
            f"<i>北京时间: {self.get_current_time()}</i>",
            ""
        ]
        
        if 'results' in results:
            total = len(results['results'])
            if total > 0:
                lines.append(f"<b>✅ 扫描股票: {total} 只</b>")
                lines.append("")
                
                # 按涨幅排序
                sorted_results = sorted(
                    results['results'],
                    key=lambda x: x['change_rate'],
                    reverse=True
                )
                
                # 显示前 5 个
                for i, stock in enumerate(sorted_results[:5], 1):
                    signal = stock.get('signal', '⚪')
                    change = stock['change_rate']
                    price = stock['price']
                    name = stock['name']
                    
                    lines.append(
                        f"{i}. {signal} <code>{stock['symbol']}</code> {name}"
                    )
                    lines.append(
                        f"   价格: ¥{price:.2f}  涨幅: {change:+.2f}%"
                    )
                    
                    analysis = stock.get('analysis', '')
                    if analysis:
                        lines.append(f"   {analysis}")
                    lines.append("")
                
                if total > 5:
                    lines.append(f"... 还有 {total - 5} 只股票")
        
        if results.get('error_count', 0) > 0:
            lines.append(f"<i>⚠️  错误数: {results['error_count']}</i>")
        
        return "\n".join(lines)
    
    def send_analysis_results(self, results_file):
        """
        发送分析结果
        """
        try:
            if not os.path.exists(results_file):
                print(f"❌ 结果文件不存在: {results_file}")
                return False
            
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # 格式化消息
            message = self.format_analysis_results(results)
            
            # 分割长消息 (Telegram 限制 4096 字符)
            if len(message) > 4000:
                # 分成多条消息
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for i, chunk in enumerate(chunks):
                    print(f"\n发送分片消息 {i+1}/{len(chunks)}...")
                    self.send_message(chunk)
            else:
                self.send_message(message)
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ 发送结果失败: {str(e)}")
            return False


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='Telegram 通知脚本')
    parser.add_argument('--bot_token', required=True, help='Telegram Bot Token')
    parser.add_argument('--chat_id', required=True, help='Chat ID')
    parser.add_argument('--analysis_file', default='analysis_results.json', help='分析结果文件')
    parser.add_argument('--status', default='success', help='执行状态')
    
    args = parser.parse_args()
    
    # 创建通知器
    notifier = TelegramNotifier(args.bot_token, args.chat_id)
    
    # 发送结果
    success = notifier.send_analysis_results(args.analysis_file)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
