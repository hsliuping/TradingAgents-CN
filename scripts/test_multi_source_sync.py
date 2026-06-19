#!/usr/bin/env python3
"""
测试多数据源同步功能
验证数据源分级和fallback机制
"""
import os
import sys
import requests
import json
import time
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_api_endpoint(url: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """测试API端点"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        if response.ok:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_section(title: str):
    """打印章节标题"""
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print('='*60)

def print_result(test_name: str, result: Dict[str, Any]):
    """打印测试结果"""
    if result["success"]:
        print(f"✅ {test_name}: 成功")
        if "data" in result:
            data = result["data"]
            if isinstance(data, dict) and "data" in data:
                # 提取关键信息
                inner_data = data["data"]
                if isinstance(inner_data, dict):
                    for key, value in inner_data.items():
                        if key in ["total", "inserted", "updated", "errors", "status"]:
                            print(f"   {key}: {value}")
    else:
        print(f"❌ {test_name}: 失败")
        print(f"   错误: {result['error']}")

def main():
    """主测试函数"""
    base_url = "http://localhost:8100"
    
    print("🚀 多数据源同步功能测试")
    print(f"测试服务器: {base_url}")
    
    # 1. 测试数据源状态
    print_section("数据源状态检查")
    
    result = test_api_endpoint(f"{base_url}/api/sync/multi-source/sources/status")
    print_result("获取数据源状态", result)
    
    if result["success"]:
        sources = result["data"]
        print("\n📊 数据源详情:")
        for source in sources:
            status = "✅ 可用" if source["available"] else "❌ 不可用"
            print(f"   {source['name']:10} (优先级: {source['priority']}) - {status}")
            print(f"      {source['description']}")
    
    # 2. 测试数据源连接
    print_section("数据源连接测试")
    
    result = test_api_endpoint(f"{base_url}/api/sync/multi-source/test-sources", "POST")
    print_result("测试数据源连接", result)
    
    if result["success"] and "data" in result and "test_results" in result["data"]:
        test_results = result["data"]["test_results"]
        print("\n🧪 连接测试结果:")
        for test_result in test_results:
            print(f"\n   📡 {test_result['name']} (优先级: {test_result['priority']}):")
            for test_name, test_data in test_result["tests"].items():
                status = "✅" if test_data["success"] else "❌"
                print(f"      {test_name:15}: {status} {test_data['message']}")
    
    # 3. 获取同步建议
    print_section("同步建议")
    
    result = test_api_endpoint(f"{base_url}/api/sync/multi-source/recommendations")
    print_result("获取同步建议", result)
    
    if result["success"] and "data" in result:
        recommendations = result["data"]
        
        if recommendations.get("primary_source"):
            primary = recommendations["primary_source"]
            print(f"\n💡 推荐主数据源: {primary['name']} (优先级: {primary['priority']})")
            print(f"   原因: {primary['reason']}")
        
        if recommendations.get("fallback_sources"):
            print(f"\n🔄 备用数据源:")
            for fallback in recommendations["fallback_sources"]:
                print(f"   - {fallback['name']} (优先级: {fallback['priority']})")
        
        if recommendations.get("suggestions"):
            print(f"\n📋 建议:")
            for suggestion in recommendations["suggestions"]:
                print(f"   • {suggestion}")
        
        if recommendations.get("warnings"):
            print(f"\n⚠️  警告:")
            for warning in recommendations["warnings"]:
                print(f"   • {warning}")
    
    # 4. 检查当前同步状态
    print_section("当前同步状态")
    
    result = test_api_endpoint(f"{base_url}/api/sync/multi-source/status")
    print_result("获取同步状态", result)
    
    if result["success"] and "data" in result:
        status_data = result["data"]
        print(f"\n📊 同步状态详情:")
        print(f"   状态: {status_data.get('status', 'unknown')}")
        print(f"   任务: {status_data.get('job', 'unknown')}")
        if status_data.get("last_trade_date"):
            print(f"   最后交易日: {status_data['last_trade_date']}")
        if status_data.get("data_sources_used"):
            print(f"   使用的数据源: {status_data['data_sources_used']}")
    
    # 5. 运行多数据源同步（可选）
    print_section("多数据源同步测试")
    
    user_input = input("\n是否运行完整的多数据源同步？这可能需要几分钟时间。(y/N): ").strip().lower()
    
    if user_input in ['y', 'yes']:
        print("🔄 开始多数据源同步...")
        start_time = time.time()
        
        result = test_api_endpoint(f"{base_url}/api/sync/multi-source/stock_basics/run", "POST")
        print_result("运行多数据源同步", result)
        
        if result["success"] and "data" in result:
            sync_data = result["data"]
            duration = time.time() - start_time
            
            print(f"\n📈 同步结果:")
            print(f"   状态: {sync_data.get('status', 'unknown')}")
            print(f"   总数: {sync_data.get('total', 0)}")
            print(f"   插入: {sync_data.get('inserted', 0)}")
            print(f"   更新: {sync_data.get('updated', 0)}")
            print(f"   错误: {sync_data.get('errors', 0)}")
            print(f"   耗时: {duration:.2f}秒")
            
            if sync_data.get("data_sources_used"):
                print(f"   使用的数据源: {sync_data['data_sources_used']}")
    else:
        print("⏭️  跳过同步测试")
    
    # 6. 测试指定数据源优先级
    print_section("指定数据源优先级测试")
    
    user_input = input("\n是否测试指定数据源优先级？(y/N): ").strip().lower()
    
    if user_input in ['y', 'yes']:
        preferred_sources = input("请输入优先使用的数据源（用逗号分隔，如: akshare,baostock）: ").strip()
        
        if preferred_sources:
            print(f"🎯 使用指定数据源优先级: {preferred_sources}")
            
            url = f"{base_url}/api/sync/multi-source/stock_basics/run?preferred_sources={preferred_sources}"
            result = test_api_endpoint(url, "POST")
            print_result("指定数据源同步", result)
            
            if result["success"] and "data" in result:
                sync_data = result["data"]
                print(f"\n📈 指定数据源同步结果:")
                print(f"   状态: {sync_data.get('status', 'unknown')}")
                if sync_data.get("data_sources_used"):
                    print(f"   实际使用的数据源: {sync_data['data_sources_used']}")
    else:
        print("⏭️  跳过指定数据源测试")
    
    print_section("测试完成")
    print("🎉 多数据源同步功能测试完成！")
    print("\n💡 使用建议:")
    print("   1. 确保至少配置一个数据源（推荐Tushare）")
    print("   2. 配置多个数据源以提供冗余")
    print("   3. 定期检查数据源状态")
    print("   4. 根据需要调整数据源优先级")

if __name__ == "__main__":
    main()
