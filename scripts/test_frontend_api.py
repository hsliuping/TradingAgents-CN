#!/usr/bin/env python3
"""
测试前端API接口
验证多数据源同步相关的API端点是否正常工作
"""
import requests
import json
import time

def test_api_endpoint(url, method="GET", data=None):
    """测试API端点"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        if response.ok:
            return {"success": True, "data": response.json(), "status": response.status_code}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "status": response.status_code}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_result(test_name, result):
    """打印测试结果"""
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print('='*60)
    
    if result["success"]:
        print(f"✅ 状态: 成功 (HTTP {result.get('status', 'N/A')})")
        if "data" in result:
            data = result["data"]
            print(f"📊 响应数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ 状态: 失败")
        print(f"🔍 错误: {result['error']}")

def main():
    """主测试函数"""
    base_url = "http://localhost:8100"
    
    print("🚀 前端API接口测试")
    print(f"测试服务器: {base_url}")
    
    # 测试用例列表
    test_cases = [
        {
            "name": "获取数据源状态",
            "url": f"{base_url}/api/sync/multi-source/sources/status",
            "method": "GET"
        },
        {
            "name": "获取同步状态",
            "url": f"{base_url}/api/sync/multi-source/status",
            "method": "GET"
        },
        {
            "name": "获取同步建议",
            "url": f"{base_url}/api/sync/multi-source/recommendations",
            "method": "GET"
        },
        {
            "name": "测试数据源连接",
            "url": f"{base_url}/api/sync/multi-source/test-sources",
            "method": "POST"
        },
        {
            "name": "清空同步缓存",
            "url": f"{base_url}/api/sync/multi-source/cache",
            "method": "DELETE"
        }
    ]
    
    # 执行测试
    results = {}
    for test_case in test_cases:
        print(f"\n🔄 正在测试: {test_case['name']}...")
        result = test_api_endpoint(
            test_case["url"], 
            test_case["method"], 
            test_case.get("data")
        )
        results[test_case["name"]] = result
        print_result(test_case["name"], result)
        
        # 短暂延迟避免请求过快
        time.sleep(1)
    
    # 测试同步操作（可选）
    print(f"\n{'='*60}")
    print("🤔 是否要测试同步操作？")
    user_input = input("输入 'y' 开始同步测试，其他键跳过: ").strip().lower()
    
    if user_input == 'y':
        print("\n🔄 测试同步操作...")
        
        # 测试运行同步
        sync_result = test_api_endpoint(
            f"{base_url}/api/sync/multi-source/stock_basics/run",
            "POST"
        )
        print_result("运行多数据源同步", sync_result)
        
        if sync_result["success"]:
            # 如果同步启动成功，监控状态
            print("\n📊 监控同步状态...")
            for i in range(10):  # 最多监控10次
                time.sleep(3)
                status_result = test_api_endpoint(
                    f"{base_url}/api/sync/multi-source/status",
                    "GET"
                )
                
                if status_result["success"]:
                    status = status_result["data"]["data"]["status"]
                    print(f"   状态检查 {i+1}: {status}")
                    
                    if status not in ["running"]:
                        print(f"   ✅ 同步完成，最终状态: {status}")
                        break
                else:
                    print(f"   ❌ 状态检查失败: {status_result['error']}")
                    break
    
    # 生成测试报告
    print(f"\n{'='*60}")
    print("📋 测试报告")
    print('='*60)
    
    success_count = sum(1 for result in results.values() if result["success"])
    total_count = len(results)
    
    print(f"📊 总测试数: {total_count}")
    print(f"✅ 成功数: {success_count}")
    print(f"❌ 失败数: {total_count - success_count}")
    print(f"📈 成功率: {success_count/total_count*100:.1f}%")
    
    print(f"\n📝 详细结果:")
    for test_name, result in results.items():
        status = "✅ 成功" if result["success"] else "❌ 失败"
        print(f"   {test_name}: {status}")
        if not result["success"]:
            print(f"      错误: {result['error']}")
    
    # 前端访问建议
    print(f"\n💡 前端访问建议:")
    print(f"   1. 确保后端服务运行在 {base_url}")
    print(f"   2. 前端开发服务器通常运行在 http://localhost:3000 或 http://localhost:5173")
    print(f"   3. 访问多数据源同步页面: http://localhost:3000/system/sync")
    print(f"   4. 检查浏览器控制台是否有CORS或其他错误")
    
    print(f"\n🎉 测试完成！")

if __name__ == "__main__":
    main()
