#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试调试接口
"""
import requests
import json
from datetime import datetime

# 调试接口地址
DEBUG_API_URL = "http://127.0.0.1:3000/api/templates/debug/analyst"

# 测试请求
test_request = {
    "analyst_type": "fundamentals",
    "template_id": "",  # 不指定模板ID，使用默认模板
    "use_current": False,
    "llm": {
        "provider": "dashscope",
        "model": "qwen-plus",
        "temperature": 0.7,
        "max_tokens": 4000,
        "backend_url": "",
        "api_key": ""
    },
    "stock": {
        "symbol": "000001",
        "analysis_date": "2025-11-17"
    }
}

def test_debug_interface():
    """测试调试接口"""
    print("=" * 80)
    print("🔍 [测试] 调试接口测试")
    print("=" * 80)
    print(f"📝 请求地址: {DEBUG_API_URL}")
    print(f"📝 请求数据: {json.dumps(test_request, indent=2, ensure_ascii=False)}")
    print("=" * 80)
    
    try:
        # 发送请求
        print("📤 发送请求...")
        response = requests.post(DEBUG_API_URL, json=test_request, timeout=300)
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功！")
            print("=" * 80)
            print("📊 响应数据:")
            print("=" * 80)
            
            if result.get("success"):
                data = result.get("data", {})
                print(f"✅ 分析类型: {data.get('analyst_type')}")
                print(f"✅ 股票代码: {data.get('symbol')}")
                print(f"✅ 分析日期: {data.get('analysis_date')}")
                print(f"✅ 报告长度: {data.get('report_length')} 字符")
                print(f"✅ 调试模式: {data.get('debug_mode')}")
                
                # 打印模板信息
                template = data.get("template", {})
                if template:
                    print("\n📋 模板信息:")
                    print(f"   来源: {template.get('source')}")
                    print(f"   模板ID: {template.get('template_id')}")
                    print(f"   版本: {template.get('version')}")
                    print(f"   Agent类型: {template.get('agent_type')}")
                    print(f"   Agent名称: {template.get('agent_name')}")
                    print(f"   偏好类型: {template.get('preference_type')}")
                    print(f"   状态: {template.get('status')}")
                
                # 打印报告摘要
                report = data.get("report", "")
                if report:
                    print("\n📄 报告摘要 (前500字符):")
                    print("-" * 80)
                    print(report[:500])
                    if len(report) > 500:
                        print("...")
                    print("-" * 80)
                else:
                    print("⚠️ 报告为空")
            else:
                print(f"❌ 请求失败: {result.get('message')}")
        else:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            print(f"📝 响应内容: {response.text}")
    
    except requests.exceptions.Timeout:
        print("❌ 请求超时（300秒）")
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保服务器正在运行")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_debug_interface()

