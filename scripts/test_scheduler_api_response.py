"""
测试定时任务 API 响应格式
验证返回的数据结构是否正确
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:8100"
USERNAME = "admin"
PASSWORD = "admin123"


def login() -> str:
    """登录并获取 token"""
    print("🔐 正在登录...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            token = data["data"]["access_token"]
            print(f"✅ 登录成功")
            return token
    
    print(f"❌ 登录失败")
    return None


def test_jobs_response(token: str):
    """测试任务列表响应格式"""
    print("\n📋 测试任务列表响应格式...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/api/scheduler/jobs", headers=headers)
    
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n响应体结构:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 检查响应格式
        print(f"\n✅ 响应格式检查:")
        print(f"  - success: {data.get('success')}")
        print(f"  - message: {data.get('message')}")
        print(f"  - data 类型: {type(data.get('data'))}")
        
        if isinstance(data.get('data'), list):
            print(f"  - data 长度: {len(data.get('data'))}")
            if len(data.get('data')) > 0:
                print(f"\n第一个任务的结构:")
                print(json.dumps(data['data'][0], indent=2, ensure_ascii=False))
        else:
            print(f"  ⚠️ data 不是数组！实际类型: {type(data.get('data'))}")
            print(f"  实际内容: {data.get('data')}")
    else:
        print(f"❌ 请求失败: {response.text}")


def test_stats_response(token: str):
    """测试统计信息响应格式"""
    print("\n📊 测试统计信息响应格式...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/api/scheduler/stats", headers=headers)
    
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n响应体结构:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 检查响应格式
        print(f"\n✅ 响应格式检查:")
        print(f"  - success: {data.get('success')}")
        print(f"  - message: {data.get('message')}")
        print(f"  - data 类型: {type(data.get('data'))}")
        
        if isinstance(data.get('data'), dict):
            stats = data.get('data')
            print(f"  - total_jobs: {stats.get('total_jobs')}")
            print(f"  - running_jobs: {stats.get('running_jobs')}")
            print(f"  - paused_jobs: {stats.get('paused_jobs')}")
        else:
            print(f"  ⚠️ data 不是对象！实际类型: {type(data.get('data'))}")
    else:
        print(f"❌ 请求失败: {response.text}")


def main():
    """主函数"""
    print("=" * 60)
    print("🧪 定时任务 API 响应格式测试")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        print("\n❌ 登录失败，无法继续测试")
        return
    
    # 2. 测试任务列表响应
    test_jobs_response(token)
    
    # 3. 测试统计信息响应
    test_stats_response(token)
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

