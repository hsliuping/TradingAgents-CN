#!/usr/bin/env python3
"""
测试API分析功能的脚本
"""

import requests
import time
import json

def test_api_analysis():
    """测试API分析功能"""
    print("🔍 测试API分析功能")
    print("=" * 60)
    
    # API基础URL
    base_url = "http://localhost:8100"
    
    try:
        # 1. 检查API健康状态
        print("1. 检查API健康状态...")
        health_response = requests.get(f"{base_url}/api/health")
        if health_response.status_code == 200:
            print("✅ API服务正常运行")
        else:
            print(f"❌ API服务异常: {health_response.status_code}")
            return False
        
        # 2. 提交分析请求
        print("\n2. 提交分析请求...")
        analysis_request = {
            "stock_code": "000002",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2025-08-20",
                "research_depth": "快速",
                "selected_analysts": ["market"],  # 只使用市场分析师进行快速测试
                "include_sentiment": False,
                "include_risk": False,
                "language": "zh-CN",
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max"
            }
        }
        
        # 添加认证头（如果需要）
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer admin_token"  # 使用管理员token
        }
        
        response = requests.post(
            f"{base_url}/api/analysis/single",
            json=analysis_request,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get("task_id")
            print(f"✅ 分析任务已提交: {task_id}")
        else:
            print(f"❌ 提交分析请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
        
        # 3. 监控任务状态
        print(f"\n3. 监控任务状态...")
        max_wait_time = 300  # 最多等待5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_response = requests.get(
                f"{base_url}/api/analysis/tasks/{task_id}/status",
                headers=headers
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data.get("status")
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "")
                
                print(f"   状态: {status}, 进度: {progress}%, 消息: {message}")
                
                if status == "completed":
                    print("✅ 分析任务完成!")
                    
                    # 获取分析结果
                    result_response = requests.get(
                        f"{base_url}/api/analysis/tasks/{task_id}/result",
                        headers=headers
                    )
                    
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        print(f"\n📊 分析结果:")
                        print(f"   股票代码: {result_data.get('stock_code')}")
                        print(f"   分析日期: {result_data.get('analysis_date')}")
                        
                        # 检查报告内容
                        reports = result_data.get('reports', {})
                        for report_type, content in reports.items():
                            if isinstance(content, str) and len(content) > 0:
                                print(f"   {report_type}: 有内容 (长度: {len(content)})")
                            else:
                                print(f"   {report_type}: 无内容或为空")
                        
                        return True
                    else:
                        print(f"❌ 获取分析结果失败: {result_response.status_code}")
                        return False
                        
                elif status == "failed":
                    print(f"❌ 分析任务失败: {message}")
                    return False
                    
            else:
                print(f"❌ 查询任务状态失败: {status_response.status_code}")
                return False
            
            # 等待5秒后再次查询
            time.sleep(5)
        
        print(f"⏰ 任务执行超时 (超过{max_wait_time}秒)")
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_api_analysis()
    if success:
        print("\n🎉 API分析功能测试成功!")
    else:
        print("\n💥 API分析功能测试失败!")
