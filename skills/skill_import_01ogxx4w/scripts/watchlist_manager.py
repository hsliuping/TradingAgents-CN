#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值监控 Watchlist 管理工具

作者: 弗兰克小斯基（Frankski）
Copyright (c) 2026 弗兰克小斯基（Frankski）. All rights reserved.

使用许可:
- 允许个人学习、研究、非商业用途使用
- 允许修改后个人使用
- 禁止直接复制核心算法用于商业产品或竞争性服务
- 禁止移除或修改作者署名后重新分发

免责声明: 本脚本提供的分析结果仅供参考，不构成投资建议。
"""

import json
import os
import argparse
from datetime import datetime

# 数据文件路径
WATCHLIST_FILE = os.path.expanduser("~/.valuation_watchlist.json")


def load_watchlist():
    """加载 watchlist"""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"stocks": [], "created_at": datetime.now().isoformat()}
    return {"stocks": [], "created_at": datetime.now().isoformat()}


def save_watchlist(watchlist):
    """保存 watchlist"""
    watchlist["updated_at"] = datetime.now().isoformat()
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def add_stock(code, name=None, target_pe_low=None, target_pe_high=None, 
              target_pb_low=None, target_pb_high=None, notes=None):
    """
    添加股票到 watchlist
    
    Args:
        target_pe_low: 目标买入 PE（低于此值视为机会）
        target_pe_high: 目标卖出 PE（高于此值视为高估）
        target_pb_low/high: 同理，针对 PB
    """
    watchlist = load_watchlist()
    
    # 检查是否已存在
    for stock in watchlist["stocks"]:
        if stock["code"] == code:
            print(f"股票 {code} 已在 watchlist 中")
            return False
    
    stock_data = {
        "code": code,
        "name": name or code,
        "added_at": datetime.now().isoformat(),
        "target": {
            "pe_low": target_pe_low,
            "pe_high": target_pe_high,
            "pb_low": target_pb_low,
            "pb_high": target_pb_high
        },
        "notes": notes or ""
    }
    
    watchlist["stocks"].append(stock_data)
    save_watchlist(watchlist)
    
    print(f"已添加 {code} ({name or code}) 到 watchlist")
    return True


def remove_stock(code):
    """从 watchlist 移除股票"""
    watchlist = load_watchlist()
    
    original_len = len(watchlist["stocks"])
    watchlist["stocks"] = [s for s in watchlist["stocks"] if s["code"] != code]
    
    if len(watchlist["stocks"]) < original_len:
        save_watchlist(watchlist)
        print(f"已从 watchlist 移除 {code}")
        return True
    else:
        print(f"股票 {code} 不在 watchlist 中")
        return False


def list_stocks():
    """列出所有 watchlist 股票"""
    watchlist = load_watchlist()
    
    if not watchlist["stocks"]:
        print("Watchlist 为空")
        return []
    
    print(f"\n📋 Watchlist ({len(watchlist['stocks'])} 只股票)")
    print("-" * 60)
    
    for stock in watchlist["stocks"]:
        target = stock.get("target", {})
        pe_range = f"PE: {target.get('pe_low', '-')}~{target.get('pe_high', '-')}"
        pb_range = f"PB: {target.get('pb_low', '-')}~{target.get('pb_high', '-')}"
        notes = stock.get("notes", "")[:30]
        
        print(f"  {stock['code']:8s} {stock['name']:10s} | {pe_range:20s} | {pb_range:20s}")
        if notes:
            print(f"           备注: {notes}")
    
    print()
    return watchlist["stocks"]


def check_alerts():
    """
    检查估值预警
    需要配合 valuation_snapshot.py 使用
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from valuation_snapshot import get_stock_valuation
    
    watchlist = load_watchlist()
    alerts = []
    
    print("\n🔍 检查估值预警...")
    print("-" * 60)
    
    for stock in watchlist["stocks"]:
        code = stock["code"]
        target = stock.get("target", {})
        
        # 获取实时估值
        val = get_stock_valuation(code)
        if not val:
            continue
        
        current_pe = val.get("pe_ttm")
        current_pb = val.get("pb")
        
        alert_msgs = []
        
        # PE 预警
        if current_pe and target.get("pe_low") and current_pe <= target["pe_low"]:
            alert_msgs.append(f"PE {current_pe:.2f} ≤ 目标 {target['pe_low']}")
        if current_pe and target.get("pe_high") and current_pe >= target["pe_high"]:
            alert_msgs.append(f"PE {current_pe:.2f} ≥ 目标 {target['pe_high']}")
        
        # PB 预警
        if current_pb and target.get("pb_low") and current_pb <= target["pb_low"]:
            alert_msgs.append(f"PB {current_pb:.2f} ≤ 目标 {target['pb_low']}")
        if current_pb and target.get("pb_high") and current_pb >= target["pb_high"]:
            alert_msgs.append(f"PB {current_pb:.2f} ≥ 目标 {target['pb_high']}")
        
        if alert_msgs:
            alert = {
                "code": code,
                "name": val.get("name", code),
                "current_price": val.get("price"),
                "current_pe": current_pe,
                "current_pb": current_pb,
                "alerts": alert_msgs
            }
            alerts.append(alert)
            
            print(f"\n⚠️  {code} {val.get('name', '')}")
            print(f"   当前: 价格 {current_pe:.2f}, PE {current_pe:.2f}x, PB {current_pb:.2f}x")
            for msg in alert_msgs:
                print(f"   🔔 {msg}")
    
    if not alerts:
        print("✅ 无预警触发")
    
    print()
    return alerts


def main():
    parser = argparse.ArgumentParser(description='估值监控 Watchlist 管理')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # add 命令
    add_parser = subparsers.add_parser('add', help='添加股票')
    add_parser.add_argument('code', help='股票代码')
    add_parser.add_argument('--name', help='股票名称')
    add_parser.add_argument('--pe-low', type=float, help='目标买入 PE')
    add_parser.add_argument('--pe-high', type=float, help='目标卖出 PE')
    add_parser.add_argument('--pb-low', type=float, help='目标买入 PB')
    add_parser.add_argument('--pb-high', type=float, help='目标卖出 PB')
    add_parser.add_argument('--notes', help='备注')
    
    # remove 命令
    remove_parser = subparsers.add_parser('remove', help='移除股票')
    remove_parser.add_argument('code', help='股票代码')
    
    # list 命令
    subparsers.add_parser('list', help='列出所有股票')
    
    # check 命令
    subparsers.add_parser('check', help='检查估值预警')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_stock(
            args.code, args.name, 
            args.pe_low, args.pe_high,
            args.pb_low, args.pb_high,
            args.notes
        )
    elif args.command == 'remove':
        remove_stock(args.code)
    elif args.command == 'list':
        list_stocks()
    elif args.command == 'check':
        check_alerts()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
