#!/usr/bin/env python3
"""
测试前后端集成
验证任务提交和状态查询的完整流程
"""

import requests
import time
import json

def test_frontend_backend_integration():
    """测试前后端集成"""
    
    base_url = "http://localhost:8100"
    
    print("🧪 测试前后端集成")
    print("=" * 40)
    
    # 1. 登录
    print("🔐 登录中...")
    try:
        login_response = requests.post(f"{base_url}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        
        if login_response.status_code != 200:
            print(f"❌ 登录失败: {login_response.status_code}")
            print(f"响应内容: {login_response.text}")
            return False
        
        login_data = login_response.json()
        token = login_data["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ 登录成功")
        
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return False
    
    # 2. 提交分析任务（模拟前端请求）
    print("\n📊 提交分析任务...")
    
    # 模拟前端发送的请求格式
    analysis_request = {
        "stock_code": "000001",
        "parameters": {
            "market_type": "A股",
            "analysis_date": "2024-01-15",
            "research_depth": "快速",
            "selected_analysts": ["market"],
            "include_sentiment": True,
            "include_risk": True,
            "language": "zh",
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-plus"
        }
    }
    
    try:
        submit_start = time.time()
        submit_response = requests.post(f"{base_url}/api/analysis/single", 
                                      json=analysis_request, 
                                      headers=headers,
                                      timeout=10)
        
        submit_time = time.time() - submit_start
        print(f"⏱️ 任务提交耗时: {submit_time:.2f}秒")
        
        if submit_response.status_code != 200:
            print(f"❌ 任务提交失败: {submit_response.status_code}")
            print(f"响应内容: {submit_response.text}")
            return False
        
        submit_data = submit_response.json()
        print(f"✅ 任务提交成功")
        print(f"📋 响应格式: {json.dumps(submit_data, indent=2, ensure_ascii=False)}")
        
        # 检查响应格式是否符合前端期望
        if not submit_data.get("success"):
            print("❌ 响应中缺少 success 字段")
            return False
        
        if not submit_data.get("data"):
            print("❌ 响应中缺少 data 字段")
            return False
        
        if not submit_data["data"].get("task_id"):
            print("❌ 响应中缺少 task_id 字段")
            return False
        
        task_id = submit_data["data"]["task_id"]
        print(f"📝 获取到任务ID: {task_id}")
        
    except Exception as e:
        print(f"❌ 提交任务异常: {e}")
        return False
    
    # 3. 查询任务状态（模拟前端轮询）
    print(f"\n🔍 查询任务状态...")
    
    try:
        status_response = requests.get(f"{base_url}/api/analysis/tasks/{task_id}/status", 
                                     headers=headers, 
                                     timeout=10)
        
        if status_response.status_code != 200:
            print(f"❌ 状态查询失败: {status_response.status_code}")
            print(f"响应内容: {status_response.text}")
            return False
        
        status_data = status_response.json()
        print(f"✅ 状态查询成功")
        print(f"📊 状态响应: {json.dumps(status_data, indent=2, ensure_ascii=False)}")
        
        # 检查状态响应格式
        if not status_data.get("success"):
            print("❌ 状态响应中缺少 success 字段")
            return False
        
        if not status_data.get("data"):
            print("❌ 状态响应中缺少 data 字段")
            return False
        
        task_status = status_data["data"].get("status")
        progress = status_data["data"].get("progress", 0)
        message = status_data["data"].get("message", "")
        
        print(f"📈 任务状态: {task_status}")
        print(f"📊 进度: {progress}%")
        print(f"💬 消息: {message}")
        
    except Exception as e:
        print(f"❌ 状态查询异常: {e}")
        return False
    
    # 4. 测试任务列表
    print(f"\n📋 测试任务列表...")
    
    try:
        tasks_response = requests.get(f"{base_url}/api/analysis/tasks", 
                                    headers=headers, 
                                    timeout=10)
        
        if tasks_response.status_code != 200:
            print(f"❌ 任务列表查询失败: {tasks_response.status_code}")
            print(f"响应内容: {tasks_response.text}")
        else:
            tasks_data = tasks_response.json()
            print(f"✅ 任务列表查询成功")
            tasks = tasks_data.get("data", {}).get("tasks", [])
            print(f"📝 任务数量: {len(tasks)}")
            
            if tasks:
                latest_task = tasks[0]
                print(f"📋 最新任务: {latest_task.get('task_id', 'N/A')[:8]}... - {latest_task.get('status', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 任务列表查询异常: {e}")
    
    # 5. 总结
    print(f"\n📈 集成测试总结:")
    print(f"  ✅ 登录成功")
    print(f"  ✅ 任务提交成功 (耗时: {submit_time:.2f}秒)")
    print(f"  ✅ 状态查询成功")
    print(f"  ✅ 响应格式正确")
    print(f"  📝 任务ID: {task_id}")
    print(f"  📊 当前状态: {task_status} ({progress}%)")
    
    if submit_time < 3.0:
        print("🎉 API响应迅速，异步实现成功！")
    else:
        print("⚠️ API响应较慢，可能需要优化")
    
    return True

if __name__ == "__main__":
    print(f"🚀 开始集成测试: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_frontend_backend_integration()
    
    print(f"\n✅ 测试完成: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("🎊 前后端集成测试成功！")
    else:
        print("🔧 需要进一步调试")
