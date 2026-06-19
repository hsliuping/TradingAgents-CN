#!/usr/bin/env python3
"""
测试房地产相关的API调用
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:8100"

def test_real_estate_screening():
    """测试房地产筛选"""
    print("🏠 测试房地产相关筛选")
    print("=" * 50)
    
    # 1. 获取访问令牌
    print("\n1. 获取访问令牌...")
    auth_response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    if auth_response.status_code != 200:
        print(f"❌ 登录失败: {auth_response.status_code}")
        return False
    
    token = auth_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ 登录成功")
    
    # 2. 测试行业API
    print("\n2. 获取所有行业...")
    response = requests.get(f"{BASE_URL}/api/screening/industries", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        industries = data.get("industries", [])
        
        print(f"✅ 获取到 {len(industries)} 个行业")
        
        # 查找房地产相关行业
        real_estate_industries = []
        for industry in industries:
            industry_name = industry['label']
            if any(keyword in industry_name for keyword in ['房', '地产', '建筑', '装修', '家居']):
                real_estate_industries.append(industry)
        
        print(f"\n🏠 房地产相关行业 ({len(real_estate_industries)}个):")
        for industry in real_estate_industries:
            print(f"  - {industry['label']} ({industry['count']}只股票)")
        
        # 3. 测试不同的房地产相关筛选
        test_industries = []
        if real_estate_industries:
            test_industries = [ind['label'] for ind in real_estate_industries[:3]]  # 测试前3个
        else:
            # 如果没找到，尝试一些可能的名称
            test_industries = ['房地产开发', '建筑装饰', '建筑材料', '家居用品']
        
        print(f"\n3. 测试房地产相关行业筛选...")
        for industry_name in test_industries:
            print(f"\n🔍 测试行业: {industry_name}")
            
            # 构造筛选条件 - 降低市值门槛到100亿
            screening_request = {
                "conditions": {
                    "logic": "AND",
                    "children": [
                        {"field": "industry", "op": "in", "value": [industry_name]},
                        {"field": "market_cap", "op": "between", "value": [1000000, 9007199254740991]}  # 100亿以上
                    ]
                },
                "order_by": [{"field": "market_cap", "direction": "desc"}],
                "limit": 10
            }
            
            response = requests.post(f"{BASE_URL}/api/screening/run", 
                                   json=screening_request, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                total = result.get("total", 0)
                items = result.get("items", [])
                
                print(f"  ✅ 找到 {total} 只股票")
                if items:
                    print(f"  📊 前3只股票:")
                    for i, stock in enumerate(items[:3]):
                        market_cap = stock.get('total_mv', 0)
                        print(f"    {i+1}. {stock.get('code', 'N/A')} - {stock.get('name', 'N/A')} - {market_cap:.2f}亿元")
                else:
                    print(f"  ⚠️ 该行业没有100亿以上市值的股票")
            else:
                print(f"  ❌ 筛选失败: {response.status_code}")
                print(f"     响应: {response.text}")
        
        return True
    else:
        print(f"❌ 获取行业列表失败: {response.status_code}")
        print(f"   响应内容: {response.text}")
        return False

if __name__ == "__main__":
    success = test_real_estate_screening()
    
    if success:
        print("\n🎉 房地产行业测试完成！")
    else:
        print("\n❌ 房地产行业测试失败！")
