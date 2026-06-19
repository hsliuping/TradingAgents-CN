#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试定时任务管理功能"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8100"

def get_auth_token():
    """获取认证token"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("access_token")
        else:
            print(f"❌ 登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None


def test_list_jobs(token):
    """测试获取任务列表"""
    print("\n" + "=" * 80)
    print("1️⃣ 测试获取任务列表")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/scheduler/jobs", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            jobs = result.get("data", [])
            print(f"✅ 获取到 {len(jobs)} 个定时任务")
            
            for i, job in enumerate(jobs, 1):
                print(f"\n任务 {i}:")
                print(f"  - ID: {job.get('id')}")
                print(f"  - 名称: {job.get('name')}")
                print(f"  - 下次执行: {job.get('next_run_time')}")
                print(f"  - 状态: {'暂停' if job.get('paused') else '运行中'}")
                print(f"  - 触发器: {job.get('trigger')}")
            
            return jobs
        else:
            print(f"❌ 获取任务列表失败: {response.text}")
            return []
    except Exception as e:
        print(f"❌ 获取任务列表异常: {e}")
        return []


def test_get_job_detail(token, job_id):
    """测试获取任务详情"""
    print("\n" + "=" * 80)
    print(f"2️⃣ 测试获取任务详情: {job_id}")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/scheduler/jobs/{job_id}", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            job = result.get("data", {})
            print(f"✅ 获取任务详情成功")
            print(f"\n任务详情:")
            print(f"  - ID: {job.get('id')}")
            print(f"  - 名称: {job.get('name')}")
            print(f"  - 函数: {job.get('func')}")
            print(f"  - 参数: {job.get('kwargs')}")
            print(f"  - 下次执行: {job.get('next_run_time')}")
            print(f"  - 状态: {'暂停' if job.get('paused') else '运行中'}")
            print(f"  - 触发器: {job.get('trigger')}")
            return job
        else:
            print(f"❌ 获取任务详情失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 获取任务详情异常: {e}")
        return None


def test_pause_job(token, job_id):
    """测试暂停任务"""
    print("\n" + "=" * 80)
    print(f"3️⃣ 测试暂停任务: {job_id}")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{BASE_URL}/api/scheduler/jobs/{job_id}/pause", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('message')}")
            return True
        else:
            print(f"❌ 暂停任务失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 暂停任务异常: {e}")
        return False


def test_resume_job(token, job_id):
    """测试恢复任务"""
    print("\n" + "=" * 80)
    print(f"4️⃣ 测试恢复任务: {job_id}")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{BASE_URL}/api/scheduler/jobs/{job_id}/resume", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('message')}")
            return True
        else:
            print(f"❌ 恢复任务失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 恢复任务异常: {e}")
        return False


def test_trigger_job(token, job_id):
    """测试手动触发任务"""
    print("\n" + "=" * 80)
    print(f"5️⃣ 测试手动触发任务: {job_id}")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{BASE_URL}/api/scheduler/jobs/{job_id}/trigger", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('message')}")
            return True
        else:
            print(f"❌ 触发任务失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 触发任务异常: {e}")
        return False


def test_get_stats(token):
    """测试获取统计信息"""
    print("\n" + "=" * 80)
    print("6️⃣ 测试获取统计信息")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/scheduler/stats", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            stats = result.get("data", {})
            print(f"✅ 获取统计信息成功")
            print(f"\n统计信息:")
            print(f"  - 总任务数: {stats.get('total_jobs')}")
            print(f"  - 运行中任务数: {stats.get('running_jobs')}")
            print(f"  - 暂停任务数: {stats.get('paused_jobs')}")
            print(f"  - 调度器状态: {stats.get('scheduler_state')}")
            return stats
        else:
            print(f"❌ 获取统计信息失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 获取统计信息异常: {e}")
        return None


def test_get_history(token):
    """测试获取执行历史"""
    print("\n" + "=" * 80)
    print("7️⃣ 测试获取执行历史")
    print("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/scheduler/history?limit=10", headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            data = result.get("data", {})
            history = data.get("history", [])
            total = data.get("total", 0)
            
            print(f"✅ 获取到 {len(history)} 条执行记录（总计 {total} 条）")
            
            for i, record in enumerate(history[:5], 1):
                print(f"\n记录 {i}:")
                print(f"  - 任务ID: {record.get('job_id')}")
                print(f"  - 操作: {record.get('action')}")
                print(f"  - 状态: {record.get('status')}")
                print(f"  - 时间: {record.get('timestamp')}")
            
            return history
        else:
            print(f"❌ 获取执行历史失败: {response.text}")
            return []
    except Exception as e:
        print(f"❌ 获取执行历史异常: {e}")
        return []


def main():
    """主函数"""
    print("🚀 定时任务管理功能测试")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取认证token
    print("🔑 获取认证token...")
    token = get_auth_token()
    if not token:
        print("❌ 无法获取认证token，测试终止")
        return
    print("✅ 认证token获取成功")
    
    # 1. 获取任务列表
    jobs = test_list_jobs(token)
    
    if not jobs:
        print("\n⚠️ 没有定时任务，测试结束")
        return
    
    # 选择第一个任务进行测试
    test_job_id = jobs[0].get("id")
    print(f"\n📌 选择任务 {test_job_id} 进行测试")
    
    # 2. 获取任务详情
    test_get_job_detail(token, test_job_id)
    
    # 3. 暂停任务
    test_pause_job(token, test_job_id)
    
    # 4. 恢复任务
    test_resume_job(token, test_job_id)
    
    # 5. 手动触发任务（可选，注释掉以避免实际执行）
    # test_trigger_job(token, test_job_id)
    
    # 6. 获取统计信息
    test_get_stats(token)
    
    # 7. 获取执行历史
    test_get_history(token)
    
    print("\n" + "=" * 80)
    print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()

