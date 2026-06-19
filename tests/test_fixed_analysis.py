#!/usr/bin/env python3
"""
测试修复后的分析功能
"""

import requests
import time
import json
from pathlib import Path

def test_fixed_analysis():
    """测试修复后的分析功能"""
    print("🔍 测试修复后的分析功能")
    print("=" * 60)

    # API基础URL
    base_url = "http://localhost:8100"

    try:
        # 1. 检查API健康状态
        print("1. 检查API健康状态...")
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API服务正常运行")
        else:
            print(f"❌ API服务异常: {response.status_code}")
            return False

        # 2. 登录获取token
        print("\n2. 登录获取token...")
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
            print(f"   响应: {login_response.text}")
            return False
        
        # 3. 提交分析请求
        print("\n3. 提交分析请求...")
        analysis_request = {
            "stock_code": "000001",  # 使用不同的股票代码测试
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

        # 使用获取到的token
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
            task_id = result.get("task_id")
            print(f"✅ 分析任务已提交: {task_id}")
        else:
            print(f"❌ 提交分析请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
        
        # 4. 监控任务状态
        print(f"\n4. 监控任务状态...")
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

                    # 5. 检查文件保存（应该使用正确的股票代码）
                    print(f"\n5. 检查文件保存...")
                    
                    # 检查data目录（应该是000001而不是UNKNOWN）
                    data_dir = Path("data/analysis_results/000001/2025-08-20")
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
                                    
                                # 检查市场分析报告内容
                                market_report = reports_dir / "market_report.md"
                                if market_report.exists():
                                    with open(market_report, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                        if len(content) > 100:
                                            print(f"✅ 市场分析报告有内容 (长度: {len(content)})")
                                            # 检查是否包含正确的股票代码
                                            if "000001" in content:
                                                print(f"✅ 报告包含正确的股票代码: 000001")
                                            else:
                                                print(f"⚠️ 报告中未找到股票代码000001")
                                        else:
                                            print(f"⚠️ 市场分析报告内容过短")
                            else:
                                print(f"⚠️ reports目录存在但没有报告文件")
                        else:
                            print(f"❌ reports目录不存在")
                    else:
                        print(f"❌ 分析结果目录不存在: {data_dir}")
                        # 检查是否还是保存到UNKNOWN目录
                        unknown_dir = Path("data/analysis_results/UNKNOWN/2025-08-20")
                        if unknown_dir.exists():
                            print(f"⚠️ 文件保存到了UNKNOWN目录，股票代码传递有问题")
                    
                    # 6. 获取分析结果
                    print(f"\n6. 获取分析结果...")
                    result_response = requests.get(
                        f"{base_url}/api/analysis/tasks/{task_id}/result",
                        headers=headers
                    )
                    
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        print(f"✅ 成功获取分析结果")
                        print(f"   股票代码: {result_data.get('stock_code')}")
                        print(f"   股票符号: {result_data.get('stock_symbol')}")
                        print(f"   分析日期: {result_data.get('analysis_date')}")
                        
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
    success = test_fixed_analysis()
    if success:
        print("\n🎉 修复后的分析功能测试成功!")
    else:
        print("\n💥 修复后的分析功能测试失败!")
