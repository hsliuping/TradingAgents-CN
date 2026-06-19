#!/usr/bin/env python3
"""
测试API返回的数据格式
"""

import requests
import time
import json

def test_api_format():
    """测试API返回的数据格式"""
    print("🔍 测试API返回的数据格式")
    print("=" * 60)
    
    # API基础URL
    base_url = "http://localhost:8100"
    
    try:
        # 1. 登录获取token
        print("1. 登录获取token...")
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        login_response = requests.post(
            f"{base_url}/api/auth/login",
            json=login_data
        )
        
        if login_response.status_code == 200:
            login_result = login_response.json()
            access_token = login_result["data"]["access_token"]
            print("✅ 登录成功，获取到token")
        else:
            print(f"❌ 登录失败: {login_response.status_code}")
            return False
        
        # 2. 提交分析请求
        print("\n2. 提交分析请求...")
        analysis_request = {
            "stock_code": "000008",  # 使用新的股票代码
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2025-08-20",
                "research_depth": "快速",
                "selected_analysts": ["market"],  # 只选择一个分析师进行快速测试
                "include_sentiment": False,
                "include_risk": False,
                "language": "zh-CN",
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max"
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.post(
            f"{base_url}/api/analysis/single",
            json=analysis_request,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result["data"]["task_id"]
            print(f"✅ 分析任务已提交: {task_id}")
        else:
            print(f"❌ 提交分析请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
        
        # 3. 等待任务完成
        print(f"\n3. 等待任务完成...")
        for i in range(60):  # 最多等待5分钟
            status_response = requests.get(
                f"{base_url}/api/analysis/tasks/{task_id}/status",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data["data"]["status"]
                progress = status_data["data"].get("progress", 0)
                message = status_data["data"].get("message", "")
                
                print(f"   状态: {status}, 进度: {progress}%, 消息: {message}")
                
                if status == "completed":
                    print("✅ 分析任务完成!")
                    break
                elif status == "failed":
                    print(f"❌ 分析任务失败: {message}")
                    return False
            
            time.sleep(5)
        else:
            print(f"⏰ 任务执行超时")
            return False
        
        # 4. 测试API返回的数据格式
        print(f"\n4. 测试API返回的数据格式...")
        result_response = requests.get(
            f"{base_url}/api/analysis/tasks/{task_id}/result",
            headers=headers
        )
        
        if result_response.status_code == 200:
            result_data = result_response.json()
            data = result_data["data"]
            
            print(f"✅ 成功获取分析结果")
            print(f"   stock_symbol: {data.get('stock_symbol')}")
            print(f"   analysts: {data.get('analysts', [])}")
            
            # 检查reports字段的数据类型
            reports = data.get('reports', {})
            if reports:
                print(f"✅ API返回包含 {len(reports)} 个报告:")
                for report_type, content in reports.items():
                    content_type = type(content).__name__
                    if isinstance(content, str):
                        print(f"   ✅ {report_type}: {content_type} ({len(content)} 字符)")
                        # 检查内容是否包含有效的文本
                        if len(content.strip()) > 10:
                            print(f"      预览: {content[:100].replace(chr(10), ' ')}...")
                        else:
                            print(f"      ⚠️ 内容过短: '{content}'")
                    else:
                        print(f"   ❌ {report_type}: {content_type} (应该是str)")
                        print(f"      值: {content}")
                
                # 验证前端期望的字段
                expected_fields = ['market_report', 'fundamentals_report', 'investment_plan', 'final_trade_decision']
                print(f"\n🎯 检查前端期望的字段:")
                for field in expected_fields:
                    if field in reports:
                        content = reports[field]
                        if isinstance(content, str) and len(content.strip()) > 10:
                            print(f"   ✅ {field}: 有效字符串内容")
                        else:
                            print(f"   ⚠️ {field}: 内容无效或过短")
                    else:
                        print(f"   ❌ {field}: 缺失")
                
                return True
            else:
                print(f"❌ API返回未包含reports字段")
                return False
        else:
            print(f"❌ 获取API结果失败: {result_response.status_code}")
            print(f"   响应: {result_response.text}")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_api_format()
    if success:
        print("\n🎉 API数据格式测试成功!")
    else:
        print("\n💥 API数据格式测试失败!")
