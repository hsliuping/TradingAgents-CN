"""
测试定时任务管理前端功能
验证后端 API 是否正常工作
"""

import requests
import json
from typing import Dict, Any

# 配置
BASE_URL = "http://localhost:8100"
USERNAME = "admin"
PASSWORD = "admin123"

# 全局变量
token = None


def login() -> str:
    """登录并获取 token"""
    print("🔐 正在登录...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            token = data["data"]["access_token"]
            print(f"✅ 登录成功，Token: {token[:20]}...")
            return token
        else:
            print(f"❌ 登录失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 登录请求失败: {response.status_code}")
        return None


def get_headers() -> Dict[str, str]:
    """获取请求头"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def test_get_jobs():
    """测试获取任务列表"""
    print("\n📋 测试获取任务列表...")
    response = requests.get(
        f"{BASE_URL}/api/scheduler/jobs",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            jobs = data["data"]
            print(f"✅ 获取任务列表成功，共 {len(jobs)} 个任务")
            
            # 显示前 5 个任务
            for i, job in enumerate(jobs[:5], 1):
                print(f"  {i}. {job['name']} - {job['trigger']} - {'已暂停' if job['paused'] else '运行中'}")
            
            return jobs
        else:
            print(f"❌ 获取任务列表失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 请求失败: {response.status_code}")
        print(f"   响应: {response.text}")
        return None


def test_get_stats():
    """测试获取统计信息"""
    print("\n📊 测试获取统计信息...")
    response = requests.get(
        f"{BASE_URL}/api/scheduler/stats",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            stats = data["data"]
            print(f"✅ 获取统计信息成功")
            print(f"   总任务数: {stats['total_jobs']}")
            print(f"   运行中: {stats['running_jobs']}")
            print(f"   已暂停: {stats['paused_jobs']}")
            print(f"   调度器状态: {'运行中' if stats['scheduler_running'] else '已停止'}")
            return stats
        else:
            print(f"❌ 获取统计信息失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return None


def test_get_job_detail(job_id: str):
    """测试获取任务详情"""
    print(f"\n🔍 测试获取任务详情: {job_id}")
    response = requests.get(
        f"{BASE_URL}/api/scheduler/jobs/{job_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            job = data["data"]
            print(f"✅ 获取任务详情成功")
            print(f"   任务名称: {job['name']}")
            print(f"   触发器: {job['trigger']}")
            print(f"   状态: {'已暂停' if job['paused'] else '运行中'}")
            print(f"   下次执行: {job.get('next_run_time', '已暂停')}")
            return job
        else:
            print(f"❌ 获取任务详情失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return None


def test_pause_job(job_id: str):
    """测试暂停任务"""
    print(f"\n⏸️  测试暂停任务: {job_id}")
    response = requests.post(
        f"{BASE_URL}/api/scheduler/jobs/{job_id}/pause",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"✅ 暂停任务成功: {data.get('message')}")
            return True
        else:
            print(f"❌ 暂停任务失败: {data.get('message')}")
            return False
    else:
        print(f"❌ 请求失败: {response.status_code}")
        print(f"   响应: {response.text}")
        return False


def test_resume_job(job_id: str):
    """测试恢复任务"""
    print(f"\n▶️  测试恢复任务: {job_id}")
    response = requests.post(
        f"{BASE_URL}/api/scheduler/jobs/{job_id}/resume",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print(f"✅ 恢复任务成功: {data.get('message')}")
            return True
        else:
            print(f"❌ 恢复任务失败: {data.get('message')}")
            return False
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False


def test_get_history(job_id: str = None):
    """测试获取执行历史"""
    if job_id:
        print(f"\n📜 测试获取任务执行历史: {job_id}")
        url = f"{BASE_URL}/api/scheduler/jobs/{job_id}/history"
    else:
        print(f"\n📜 测试获取所有执行历史")
        url = f"{BASE_URL}/api/scheduler/history"
    
    response = requests.get(
        url,
        headers=get_headers(),
        params={"limit": 10}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            history = data["data"]["history"]
            total = data["data"]["total"]
            print(f"✅ 获取执行历史成功，共 {total} 条记录")
            
            # 显示前 5 条记录
            for i, record in enumerate(history[:5], 1):
                print(f"  {i}. {record['job_id']} - {record['action']} - {record['status']} - {record['timestamp']}")
            
            return history
        else:
            print(f"❌ 获取执行历史失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return None


def test_health():
    """测试健康检查"""
    print("\n💚 测试健康检查...")
    response = requests.get(
        f"{BASE_URL}/api/scheduler/health",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            health = data["data"]
            print(f"✅ 健康检查成功")
            print(f"   状态: {health['status']}")
            print(f"   运行中: {health['running']}")
            print(f"   时间: {health['timestamp']}")
            return health
        else:
            print(f"❌ 健康检查失败: {data.get('message')}")
            return None
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return None


def main():
    """主函数"""
    global token
    
    print("=" * 60)
    print("🧪 定时任务管理前端功能测试")
    print("=" * 60)
    
    # 1. 登录
    token = login()
    if not token:
        print("\n❌ 登录失败，无法继续测试")
        return
    
    # 2. 测试健康检查
    test_health()
    
    # 3. 测试获取统计信息
    stats = test_get_stats()
    
    # 4. 测试获取任务列表
    jobs = test_get_jobs()
    if not jobs:
        print("\n❌ 无法获取任务列表，停止测试")
        return
    
    # 5. 测试获取任务详情（使用第一个任务）
    if jobs:
        first_job = jobs[0]
        test_get_job_detail(first_job["id"])
    
    # 6. 测试暂停和恢复任务（使用第一个运行中的任务）
    running_jobs = [job for job in jobs if not job["paused"]]
    if running_jobs:
        test_job = running_jobs[0]
        print(f"\n🎯 选择任务进行暂停/恢复测试: {test_job['name']}")
        
        # 暂停任务
        if test_pause_job(test_job["id"]):
            # 恢复任务
            test_resume_job(test_job["id"])
    
    # 7. 测试获取执行历史
    test_get_history()
    if jobs:
        test_get_history(jobs[0]["id"])
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

