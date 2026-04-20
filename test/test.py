# cls_calendar_spider.py - 财联社投资日历爬虫（正式版）
import requests
import execjs
import time
import json
from datetime import datetime

class CLSCalendarSpider:
    def __init__(self):
        self.session = requests.Session()
        
        # 先访问首页获取 Cookie
        self.session.get('https://www.cls.cn/', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=10)
        
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://www.cls.cn/investKalendar',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': 'https://www.cls.cn',
        }
        
        self.api_url = 'https://www.cls.cn/api/calendar/web/list'
        self.ctx = self._init_js_context()
    
    def _init_js_context(self):
        """初始化 JS 加密上下文"""
        js_code = """
        const crypto = require('crypto');
        
        function generateSign(params, cookieUU) {
            var timestamp = new Date().getTime().toString();
            var prefix = '12b6bb84e093532';
            var signStr = prefix + (cookieUU || '') + '/api/calendar/web' + timestamp;
            return crypto.createHash('md5').update(signStr).digest('hex');
        }
        
        global.generateSign = generateSign;
        """
        return execjs.compile(js_code)
    
    def get_sign(self, params, cookie_uu=''):
        """生成 sign 签名"""
        return self.ctx.call('generateSign', params, cookie_uu)
    
    def get_calendar_data(self, last_time=None, flag=0, type_=0):
        """获取投资日历数据"""
        if last_time is None:
            last_time = int(time.time() * 1000)
        
        params = {
            'app': 'CailianpressWeb',
            'flag': flag,
            'os': 'web',
            'sv': '8.4.6',
            'type': type_,
            'last_time': last_time,
            'rn': str(time.time()),
        }
        
        sign = self.get_sign(params)
        params['sign'] = sign
        
        try:
            resp = self.session.get(
                self.api_url, 
                params=params, 
                headers=self.headers, 
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            # ✅ 修正判断逻辑：code 可能是 200 或 0
            if data.get('code') in [0, 200] and data.get('data') is not None:
                return {'success': True, 'data': data}
            else:
                return {'success': False, 'error': data.get('msg', '未知错误'), 'data': data}
                
        except Exception as e:
            return {'success': False, 'error': str(e), 'data': None}
    
    def parse_events(self, result):
        """解析日历事件"""
        if not result['success'] or not result['data']:
            return []
        
        events = []
        calendar_list = result['data'].get('data', [])
        
        for day in calendar_list:
            date = day.get('calendar_day', '')
            week = day.get('week', '')
            items = day.get('items', [])
            
            for item in items:
                event = {
                    'date': date,
                    'week': week,
                    'time': item.get('calendar_time', ''),
                    'title': item.get('title', ''),
                    'star': item.get('event', {}).get('star', 0),
                    'country': item.get('event', {}).get('country', ''),
                    'type': item.get('type', 0),
                    'id': item.get('id', 0),
                }
                events.append(event)
        
        return events
    
    def get_date_range(self, start_date, end_date):
        """
        按日期范围获取日历数据
        
        Args:
            start_date: '2026-02-22'
            end_date: '2026-03-22'
        """
        from datetime import datetime, timedelta
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        all_events = []
        current = start
        
        print(f"开始获取 {start_date} 至 {end_date} 的日历数据...")
        
        while current <= end:
            last_time = int(current.timestamp() * 1000)
            print(f"\n[{current.strftime('%Y-%m-%d')}] 请求中...", end=' ')
            
            result = self.get_calendar_data(last_time=last_time)
            
            if result['success']:
                events = self.parse_events(result)
                all_events.extend(events)
                print(f"获取 {len(events)} 条事件")
            else:
                print(f"失败: {result['error']}")
            
            # 休眠避免被封
            time.sleep(1)
            current += timedelta(days=1)
        
        return all_events
    
    def save_to_json(self, events, filename='cls_calendar.json'):
        """保存数据到 JSON 文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 数据已保存到 {filename}")
    
    def save_to_csv(self, events, filename='cls_calendar.csv'):
        """保存数据到 CSV 文件"""
        import csv
        if not events:
            print("无数据可保存")
            return
        
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
        print(f"\n✅ 数据已保存到 {filename}")


# ============ 使用示例 ============
if __name__ == '__main__':
    print("=" * 70)
    print("财联社投资日历爬虫 - 正式版")
    print("=" * 70)
    
    spider = CLSCalendarSpider()
    
    # 方式1: 获取最新日历数据
    print("\n【方式1】获取最新日历数据")
    print("-" * 70)
    result = spider.get_calendar_data()
    
    if result['success']:
        events = spider.parse_events(result)
        print(f"\n✅ 成功获取 {len(events)} 条事件\n")
        
        # 打印前5条
        for i, event in enumerate(events[:5], 1):
            print(f"{i}. [{event['date']} {event['week']}] {event['title']}")
            print(f"   重要度: {'★' * event['star']}  国家: {event['country']}")
        
        # 保存数据
        spider.save_to_json(events)
        spider.save_to_csv(events)
    else:
        print(f"\n❌ 获取失败: {result['error']}")
    
    # 方式2: 按日期范围获取（取消注释使用）
    # print("\n【方式2】按日期范围获取")
    # print("-" * 70)
    # events = spider.get_date_range('2026-02-22', '2026-03-22')
    # spider.save_to_json(events, 'cls_calendar_range.json')