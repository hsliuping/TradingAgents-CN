#!/usr/bin/env python3
"""
重启API服务并测试保存功能的脚本
"""

import requests
import time
import json
import subprocess
import os
from pathlib import Path

def check_api_running():
    """检查API是否在运行"""
    try:
        response = requests.get("http://localhost:8100/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_analysis_with_save():
    """测试分析功能和保存功能"""
    print("🔍 测试分析功能和保存功能")
    print("=" * 60)
    
    # API基础URL
    base_url = "http://localhost:8100"
    
    try:
        # 1. 检查API健康状态
        print("1. 检查API健康状态...")
        if not check_api_running():
            print("❌ API服务未运行")
            return False
        print("✅ API服务正常运行")
        
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
        
        # 添加认证头
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer admin_token"
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
                    
                    # 4. 检查文件保存
                    print(f"\n4. 检查文件保存...")
                    
                    # 检查data目录
                    data_dir = Path("data/analysis_results/000002/2025-08-20")
                    if data_dir.exists():
                        print(f"✅ 分析结果目录存在: {data_dir}")
                        
                        # 检查reports目录
                        reports_dir = data_dir / "reports"
                        if reports_dir.exists():
                            report_files = list(reports_dir.glob("*.md"))
                            if report_files:
                                print(f"✅ 找到 {len(report_files)} 个报告文件:")
                                for file in report_files:
                                    print(f"   - {file.name}")
                            else:
                                print(f"⚠️ reports目录存在但没有报告文件")
                        else:
                            print(f"❌ reports目录不存在")
                    else:
                        print(f"❌ 分析结果目录不存在: {data_dir}")
                    
                    # 5. 获取分析结果
                    print(f"\n5. 获取分析结果...")
                    result_response = requests.get(
                        f"{base_url}/api/analysis/tasks/{task_id}/result",
                        headers=headers
                    )
                    
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        print(f"✅ 成功获取分析结果")
                        print(f"   股票代码: {result_data.get('stock_code')}")
                        print(f"   分析日期: {result_data.get('analysis_date')}")
                        
                        # 检查结果内容
                        if 'detailed_analysis' in result_data:
                            detailed = result_data['detailed_analysis']
                            print(f"   详细分析: {type(detailed)}")
                            if isinstance(detailed, dict):
                                print(f"   详细分析键: {list(detailed.keys())}")
                        
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
    success = test_analysis_with_save()
    if success:
        print("\n🎉 分析和保存功能测试成功!")
    else:
        print("\n💥 分析和保存功能测试失败!")
