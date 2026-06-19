#!/usr/bin/env python3
"""
测试新的行业API
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:8100"

def test_industries_api():
    """测试行业API"""
    print("🧪 测试行业API")
    print("=" * 50)
    
    # 1. 获取访问令牌
    print("\n1. 获取访问令牌...")
    auth_response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })

    if auth_response.status_code != 200:
        print(f"❌ 登录失败: {auth_response.status_code}")
        print(f"   响应内容: {auth_response.text}")
        return False

    auth_data = auth_response.json()
    print(f"   登录响应: {auth_data}")

    # 尝试不同的token字段名和路径
    token = None

    # 检查嵌套结构 data.access_token
    if "data" in auth_data and isinstance(auth_data["data"], dict):
        data = auth_data["data"]
        for key in ["access_token", "token", "accessToken"]:
            if key in data:
                token = data[key]
                break

    # 检查顶级字段
    if not token:
        for key in ["access_token", "token", "accessToken"]:
            if key in auth_data:
                token = auth_data[key]
                break

    if not token:
        print(f"❌ 无法找到访问令牌，响应数据: {auth_data}")
        return False

    headers = {"Authorization": f"Bearer {token}"}
    print("✅ 登录成功")
    
    # 2. 测试行业API
    print("\n2. 测试行业API...")
    response = requests.get(f"{BASE_URL}/api/screening/industries", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        industries = data.get("industries", [])
        total = data.get("total", 0)
        
        print(f"✅ 行业API成功，返回 {total} 个行业")
        print(f"\n📊 前10个行业（按股票数量排序）:")
        
        for i, industry in enumerate(industries[:10]):
            print(f"  {i+1:2d}. {industry['label']} ({industry['count']}只股票)")
        
        if len(industries) > 10:
            print(f"  ... 还有 {len(industries) - 10} 个行业")
        
        # 检查银行、证券、保险是否在列表中
        print(f"\n🏦 金融行业检查:")
        financial_industries = ['银行', '证券', '保险']
        for fin_industry in financial_industries:
            found = next((ind for ind in industries if ind['label'] == fin_industry), None)
            if found:
                print(f"  ✅ {fin_industry}: {found['count']}只股票")
            else:
                print(f"  ❌ {fin_industry}: 未找到")
        
        return True
    else:
        print(f"❌ 行业API失败: {response.status_code}")
        print(f"   响应内容: {response.text}")
        return False

if __name__ == "__main__":
    success = test_industries_api()
    
    if success:
        print("\n🎉 行业API测试成功！")
        print("前端现在可以动态加载真实的行业数据了。")
    else:
        print("\n❌ 行业API测试失败！")
        print("需要检查后端API实现。")
