#!/usr/bin/env python3
"""
测试后端非阻塞功能
验证分析任务提交后，API服务器仍然可以响应其他请求
"""

import asyncio
import aiohttp
import time
import json

async def test_non_blocking_analysis():
    """测试非阻塞分析功能"""
    
    base_url = "http://localhost:8100"
    
    # 首先登录获取token
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    async with aiohttp.ClientSession() as session:
        print("🔐 正在登录...")
        async with session.post(f"{base_url}/api/auth/login", json=login_data) as resp:
            if resp.status != 200:
                print(f"❌ 登录失败: {resp.status}")
                return
            
            login_result = await resp.json()
            token = login_result["data"]["access_token"]
            print("✅ 登录成功")
        
        # 设置认证头
        headers = {"Authorization": f"Bearer {token}"}
        
        # 提交分析任务
        analysis_data = {
            "stock_code": "000001",
            "parameters": {
                "market_type": "A股",
                "research_depth": "标准",
                "selected_analysts": ["market", "fundamentals"],
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-plus"
            }
        }
        
        print("📊 提交分析任务...")
        start_time = time.time()
        
        async with session.post(f"{base_url}/api/analysis/single", 
                               json=analysis_data, 
                               headers=headers) as resp:
            submit_time = time.time() - start_time
            print(f"⏱️ 任务提交耗时: {submit_time:.2f}秒")
            
            if resp.status != 200:
                print(f"❌ 任务提交失败: {resp.status}")
                text = await resp.text()
                print(f"错误信息: {text}")
                return
            
            result = await resp.json()
            task_id = result["data"]["task_id"]
            print(f"✅ 任务提交成功，任务ID: {task_id}")
        
        # 立即测试其他API是否仍然响应
        print("\n🔍 测试其他API响应性...")
        
        # 测试健康检查
        test_start = time.time()
        async with session.get(f"{base_url}/api/health") as resp:
            health_time = time.time() - test_start
            print(f"🏥 健康检查响应时间: {health_time:.2f}秒 - 状态: {resp.status}")
        
        # 测试用户信息
        test_start = time.time()
        async with session.get(f"{base_url}/api/auth/me", headers=headers) as resp:
            me_time = time.time() - test_start
            print(f"👤 用户信息响应时间: {me_time:.2f}秒 - 状态: {resp.status}")
        
        # 测试任务状态查询
        test_start = time.time()
        async with session.get(f"{base_url}/api/analysis/tasks/{task_id}/status", 
                              headers=headers) as resp:
            status_time = time.time() - test_start
            print(f"📋 任务状态响应时间: {status_time:.2f}秒 - 状态: {resp.status}")
            
            if resp.status == 200:
                status_result = await resp.json()
                print(f"📊 任务状态: {status_result['data']['status']}")
        
        # 等待几秒后再次检查任务状态
        print("\n⏳ 等待5秒后再次检查任务状态...")
        await asyncio.sleep(5)
        
        async with session.get(f"{base_url}/api/analysis/tasks/{task_id}/status", 
                              headers=headers) as resp:
            if resp.status == 200:
                status_result = await resp.json()
                print(f"📊 5秒后任务状态: {status_result['data']['status']}")
                print(f"📈 任务进度: {status_result['data'].get('progress', 0)}%")
            else:
                print(f"❌ 状态查询失败: {resp.status}")

async def test_concurrent_requests():
    """测试并发请求"""
    print("\n🔄 测试并发请求...")
    
    base_url = "http://localhost:8100"
    
    async def make_health_check():
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            async with session.get(f"{base_url}/api/health") as resp:
                duration = time.time() - start_time
                return resp.status, duration
    
    # 并发发送10个健康检查请求
    tasks = [make_health_check() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    print("🏥 并发健康检查结果:")
    for i, (status, duration) in enumerate(results):
        print(f"  请求 {i+1}: 状态 {status}, 耗时 {duration:.3f}秒")
    
    avg_time = sum(duration for _, duration in results) / len(results)
    print(f"📊 平均响应时间: {avg_time:.3f}秒")

if __name__ == "__main__":
    print("🧪 开始测试后端非阻塞功能")
    print("=" * 50)
    
    asyncio.run(test_non_blocking_analysis())
    asyncio.run(test_concurrent_requests())
    
    print("\n✅ 测试完成")
