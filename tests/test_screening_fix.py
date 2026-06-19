#!/usr/bin/env python3
"""
测试修复后的筛选功能
"""

import asyncio
import sys
import os
import requests
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_screening_api():
    """测试筛选API"""
    print("🧪 测试修复后的筛选功能...")
    
    base_url = "http://localhost:8100"
    
    try:
        # 1. 登录获取token
        print("🔐 登录中...")
        login_response = requests.post(f"{base_url}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        
        if login_response.status_code != 200:
            print(f"❌ 登录失败: {login_response.status_code}")
            return False
        
        login_data = login_response.json()
        token = login_data["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ 登录成功")
        
        # 2. 测试筛选API
        print("\n📊 测试筛选API...")
        
        # 模拟前端发送的筛选请求
        screening_request = {
            "market": "CN",
            "conditions": {
                "logic": "AND",
                "children": [
                    {
                        "field": "market_cap",
                        "op": "between", 
                        "value": [1000000, 50000000]  # 100亿到5000亿（万元）
                    }
                ]
            },
            "order_by": [
                {
                    "field": "market_cap",
                    "direction": "desc"
                }
            ],
            "limit": 10,
            "offset": 0
        }
        
        print(f"📋 筛选条件: {json.dumps(screening_request, indent=2, ensure_ascii=False)}")
        
        # 发送筛选请求
        screening_response = requests.post(
            f"{base_url}/api/screening/run",
            json=screening_request,
            headers=headers,
            timeout=30
        )
        
        if screening_response.status_code != 200:
            print(f"❌ 筛选失败: {screening_response.status_code}")
            print(f"响应内容: {screening_response.text}")
            return False
        
        screening_data = screening_response.json()
        print(f"✅ 筛选成功!")
        print(f"📊 结果统计:")
        print(f"  - 总数量: {screening_data.get('total', 0)}")
        print(f"  - 返回数量: {len(screening_data.get('items', []))}")
        
        # 显示前5个结果
        items = screening_data.get('items', [])
        if items:
            print(f"📋 前5个结果:")
            for i, item in enumerate(items[:5], 1):
                print(f"  {i}. {item.get('code', 'N/A')} - 市值: {item.get('total_mv', 'N/A')}亿")
        
        # 3. 测试更复杂的筛选条件
        print("\n🔧 测试复杂筛选条件...")
        
        complex_request = {
            "market": "CN",
            "conditions": {
                "logic": "AND",
                "children": [
                    {
                        "field": "market_cap",
                        "op": "between",
                        "value": [500000, 20000000]  # 50亿到2000亿
                    }
                ]
            },
            "order_by": [
                {
                    "field": "market_cap", 
                    "direction": "desc"
                }
            ],
            "limit": 15,
            "offset": 0
        }
        
        complex_response = requests.post(
            f"{base_url}/api/screening/run",
            json=complex_request,
            headers=headers,
            timeout=30
        )
        
        if complex_response.status_code == 200:
            complex_data = complex_response.json()
            print(f"✅ 复杂筛选成功!")
            print(f"📊 结果统计:")
            print(f"  - 总数量: {complex_data.get('total', 0)}")
            print(f"  - 返回数量: {len(complex_data.get('items', []))}")
        else:
            print(f"❌ 复杂筛选失败: {complex_response.status_code}")
        
        print("\n🎉 筛选功能测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

if __name__ == "__main__":
    test_screening_api()
