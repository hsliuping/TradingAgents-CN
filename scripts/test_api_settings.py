#!/usr/bin/env python3
"""
测试 API 返回的系统设置
"""

import requests
import json

def main():
    """主函数"""
    print("=" * 60)
    print("📊 测试 API 返回的系统设置")
    print("=" * 60)
    
    try:
        # 调用 API（不需要认证，因为是本地测试）
        response = requests.get("http://127.0.0.1:8100/api/config/settings", timeout=5)
        
        if response.status_code == 401:
            print("\n⚠️  需要认证，尝试登录...")
            # 登录获取 token (使用 JSON)
            login_response = requests.post(
                "http://127.0.0.1:8100/api/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=5
            )
            print(f"登录响应状态: {login_response.status_code}")
            print(f"登录响应内容: {login_response.text}")

            if login_response.status_code == 200:
                login_data = login_response.json()
                token = login_data.get("data", {}).get("access_token")
                if token:
                    print(f"获取到 token: {token[:50]}...")
                    # 重新请求
                    response = requests.get(
                        "http://127.0.0.1:8100/api/config/settings",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5
                    )
                else:
                    print(f"❌ 无法从响应中获取 token")
            else:
                print(f"❌ 登录失败")
        
        if response.status_code == 200:
            settings = response.json()
            print(f"\n✅ API 返回的系统设置 (共 {len(settings)} 项):\n")
            
            # 打印模型相关的设置
            print("模型相关设置:")
            for key in ['default_model', 'quick_analysis_model', 'deep_analysis_model']:
                value = settings.get(key)
                print(f"  {key}: {value}")
            
            print(f"\n所有设置:")
            print(json.dumps(settings, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ API 请求失败: {response.status_code}")
            print(f"响应: {response.text}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

