#!/usr/bin/env python3
"""
授权服务连接诊断工具

用于诊断授权服务连接问题，帮助用户排查网络、SSL、端点等问题
"""

import requests
import sys
from urllib.parse import urlparse

# 尝试导入 httpx（如果可用）
try:
    import httpx
    import asyncio
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("⚠️  httpx 模块未安装，将跳过 httpx 测试")

BASE_URL = "https://www.tradingagentscn.com/api"
ENDPOINT = f"{BASE_URL}/app/verify-token"

def test_basic_connectivity():
    """测试基础连接"""
    print("=" * 60)
    print("测试 1: 基础连接测试")
    print("=" * 60)
    
    try:
        response = requests.get("https://www.tradingagentscn.com", timeout=10)
        print(f"✅ 官网连接成功")
        print(f"   状态码: {response.status_code}")
        print(f"   URL: https://www.tradingagentscn.com")
        return True
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL 证书验证失败: {e}")
        print(f"   可能原因: 企业网络使用了中间人代理")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False

def test_api_endpoint_exists():
    """测试 API 端点是否存在"""
    print("\n" + "=" * 60)
    print("测试 2: API 端点存在性测试")
    print("=" * 60)
    
    endpoints_to_test = [
        f"{BASE_URL}/app/verify-token",
        f"{BASE_URL}/health",
        f"{BASE_URL}/",
        "https://www.tradingagentscn.com/api",
    ]
    
    for endpoint in endpoints_to_test:
        try:
            print(f"\n测试端点: {endpoint}")
            response = requests.get(endpoint, timeout=10, allow_redirects=True)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ 端点可访问")
                print(f"   响应长度: {len(response.text)} 字符")
            elif response.status_code == 404:
                print(f"   ⚠️  端点不存在 (404)")
            elif response.status_code == 405:
                print(f"   ⚠️  方法不允许 (405) - 端点存在但需要 POST")
            else:
                print(f"   ⚠️  状态码: {response.status_code}")
        except requests.exceptions.SSLError as e:
            print(f"   ❌ SSL 错误: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ 连接失败: {e}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")

async def test_httpx_connection():
    """使用 httpx 测试连接（与代码中使用的库一致）"""
    print("\n" + "=" * 60)
    print("测试 3: httpx 连接测试（模拟实际代码）")
    print("=" * 60)
    
    timeout_config = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0
    )
    
    test_data = {
        "token": "test-token",
        "device_id": "test-device",
        "app_version": "test-version"
    }
    
    try:
        print(f"连接 URL: {ENDPOINT}")
        print(f"超时配置: connect=10s, read=30s")
        print(f"请求数据: {test_data}")
        
        async with httpx.AsyncClient(
            timeout=timeout_config,
            verify=True,
            follow_redirects=True
        ) as client:
            response = await client.post(ENDPOINT, json=test_data)
            
            print(f"\n✅ 连接成功!")
            print(f"   状态码: {response.status_code}")
            print(f"   响应头: {dict(response.headers)}")
            
            try:
                response_json = response.json()
                print(f"   响应内容: {response_json}")
            except:
                print(f"   响应文本: {response.text[:200]}")
            
            return True
            
    except httpx.TimeoutException as e:
        print(f"\n❌ 请求超时")
        print(f"   错误: {e}")
        print(f"   可能原因: 网络延迟过高或服务器响应慢")
        return False
    except httpx.ConnectError as e:
        print(f"\n❌ 连接失败")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误信息: {e}")
        print(f"\n   可能的原因:")
        print(f"   1. 防火墙或代理阻止了 API 请求")
        print(f"   2. API 端点不存在: {ENDPOINT}")
        print(f"   3. 网络环境问题（企业网络、VPN）")
        print(f"   4. DNS 解析问题")
        return False
    except httpx.HTTPStatusError as e:
        print(f"\n⚠️  HTTP 状态错误")
        print(f"   状态码: {e.response.status_code}")
        print(f"   响应: {e.response.text[:200]}")
        # 401/403 等状态码表示端点存在，只是认证失败，这是正常的
        if e.response.status_code in [401, 403]:
            print(f"   ✅ 端点存在，只是认证失败（这是正常的测试结果）")
            return True
        return False
    except Exception as e:
        print(f"\n❌ 未知错误")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误信息: {e}")
        return False

def test_dns_resolution():
    """测试 DNS 解析"""
    print("\n" + "=" * 60)
    print("测试 4: DNS 解析测试")
    print("=" * 60)
    
    import socket
    
    hostname = urlparse(BASE_URL).netloc
    print(f"解析主机名: {hostname}")
    
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS 解析成功")
        print(f"   IP 地址: {ip}")
        return True
    except socket.gaierror as e:
        print(f"❌ DNS 解析失败: {e}")
        print(f"   可能原因: DNS 服务器问题或网络配置问题")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("授权服务连接诊断工具")
    print("=" * 60)
    print(f"\n测试目标: {BASE_URL}")
    print(f"API 端点: {ENDPOINT}\n")
    
    results = {}
    
    # 测试 1: 基础连接
    results["basic"] = test_basic_connectivity()
    
    # 测试 2: DNS 解析
    results["dns"] = test_dns_resolution()
    
    # 测试 3: API 端点存在性
    test_api_endpoint_exists()
    
    # 测试 4: httpx 连接（模拟实际代码）
    if HAS_HTTPX:
        results["httpx"] = asyncio.run(test_httpx_connection())
    else:
        print("\n" + "=" * 60)
        print("测试 3: httpx 连接测试（跳过 - 模块未安装）")
        print("=" * 60)
        print("⚠️  httpx 模块未安装，无法进行此测试")
        results["httpx"] = None
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    if results.get("basic") and results.get("dns"):
        print("✅ 基础连接正常")
    else:
        print("❌ 基础连接存在问题")
    
    if results.get("httpx"):
        print("✅ httpx 连接成功（授权服务可用）")
    else:
        print("❌ httpx 连接失败")
        print("\n建议:")
        print("1. 检查防火墙设置，确保允许访问 https://www.tradingagentscn.com")
        print("2. 检查代理设置，确保 API 请求不被拦截")
        print("3. 如果在企业网络，联系 IT 部门检查网络策略")
        print("4. 系统会自动使用离线缓存模式（如果之前验证过）")
    
    print("\n注意: 即使连接失败，系统也会使用离线缓存模式，不影响基本功能使用。")

if __name__ == "__main__":
    main()
