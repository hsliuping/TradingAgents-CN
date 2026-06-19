#!/usr/bin/env python3
"""
测试前端显示问题的脚本
"""

import requests
import time
import json

def test_frontend_display():
    """测试前端显示问题"""
    print("🔍 测试前端显示问题")
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
            "stock_code": "000004",  # 使用新的股票代码
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2025-08-20",
                "research_depth": "快速",
                "selected_analysts": ["market"],
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
                
                if status == "completed":
                    print("✅ 分析任务完成!")
                    break
                elif status == "failed":
                    print(f"❌ 分析任务失败")
                    return False
            
            time.sleep(5)
        else:
            print(f"⏰ 任务执行超时")
            return False
        
        # 4. 测试新的result端点
        print(f"\n4. 测试新的result端点...")
        result_response = requests.get(
            f"{base_url}/api/analysis/tasks/{task_id}/result",
            headers=headers
        )
        
        if result_response.status_code == 200:
            result_data = result_response.json()
            print(f"✅ 成功获取分析结果")
            
            # 检查数据结构
            data = result_data["data"]
            print(f"\n📊 结果数据结构检查:")
            print(f"   stock_code: {data.get('stock_code', 'NOT_FOUND')}")
            print(f"   stock_symbol: {data.get('stock_symbol', 'NOT_FOUND')}")
            print(f"   analysis_date: {data.get('analysis_date', 'NOT_FOUND')}")
            
            # 检查reports字段
            reports = data.get('reports', {})
            if reports:
                print(f"✅ 找到reports字段，包含 {len(reports)} 个报告:")
                for report_type, content in reports.items():
                    if isinstance(content, str):
                        print(f"   - {report_type}: {len(content)} 字符")
                    else:
                        print(f"   - {report_type}: {type(content)}")
            else:
                print(f"❌ 未找到reports字段或为空")
                
                # 检查detailed_analysis字段
                detailed_analysis = data.get('detailed_analysis')
                if detailed_analysis:
                    print(f"⚠️ 但找到detailed_analysis字段: {type(detailed_analysis)}")
                    if isinstance(detailed_analysis, dict):
                        print(f"   detailed_analysis键: {list(detailed_analysis.keys())}")
                        for key, value in detailed_analysis.items():
                            if isinstance(value, str) and len(value) > 50:
                                print(f"   - {key}: {len(value)} 字符 (可作为报告)")
                else:
                    print(f"❌ 也未找到detailed_analysis字段")
            
            return True
        else:
            print(f"❌ 获取分析结果失败: {result_response.status_code}")
            print(f"   响应: {result_response.text}")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_frontend_display()
    if success:
        print("\n🎉 前端显示测试成功!")
    else:
        print("\n💥 前端显示测试失败!")
