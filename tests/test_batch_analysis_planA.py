#!/usr/bin/env python3
"""
测试方案A的批量分析链路：
- POST /api/analysis/batch 提交
- 读取返回的 mapping[{stock_code, task_id}]
- 轮询 /api/analysis/tasks/{task_id}/status 直至 completed
- 获取 /api/analysis/tasks/{task_id}/result 并验证关键字段
"""
import time
import json
import requests

BASE_URL = "http://localhost:8100"
USERNAME = "admin"
PASSWORD = "admin123"

STOCKS = ["000001", "000002"]


def login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    assert data.get("success"), f"login failed: {data}"
    return data["data"]["access_token"]


def submit_batch(token: str):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "title": "测试批量分析-方案A",
        "description": "自动化测试",
        "stock_codes": STOCKS,
        "parameters": {
            "market_type": "A股",
            "research_depth": "标准",
            "selected_analysts": ["market", "fundamentals"],
            "include_sentiment": True,
            "include_risk": True,
            "language": "zh-CN"
        }
    }
    r = requests.post(f"{BASE_URL}/api/analysis/batch", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    assert data.get("success"), f"batch submit failed: {data}"
    mapping = data["data"].get("mapping", [])
    assert len(mapping) == len(STOCKS), f"mapping size mismatch: {mapping}"
    return data["data"]["batch_id"], mapping


def poll_status(token: str, task_id: str, timeout_sec: int = 300):
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    while time.time() - start < timeout_sec:
        r = requests.get(f"{BASE_URL}/api/analysis/tasks/{task_id}/status", headers=headers, timeout=20)
        if r.status_code != 200:
            time.sleep(2)
            continue
        data = r.json()
        if data.get("success"):
            status = data["data"].get("status")
            if status == "completed":
                return True
            elif status == "failed":
                print(f"❌ 任务失败: {task_id}")
                return False
        time.sleep(3)
    print(f"⏰ 任务超时: {task_id}")
    return False


def fetch_result(token: str, task_id: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/analysis/tasks/{task_id}/result", headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    assert data.get("success"), f"get result failed: {data}"
    return data["data"]


def main():
    print("开始方案A批量链路测试...")
    token = login()
    print("✅ 登录成功")

    batch_id, mapping = submit_batch(token)
    print(f"✅ 批量提交成功 batch_id={batch_id}，任务数={len(mapping)}")

    all_ok = True
    results = {}
    for m in mapping:
        stock = m["stock_code"]
        task_id = m["task_id"]
        print(f"⏳ 等待任务完成: {stock} ({task_id})")
        ok = poll_status(token, task_id, timeout_sec=420)
        all_ok = all_ok and ok
        if ok:
            res = fetch_result(token, task_id)
            results[stock] = res
            # 验证关键字段
            assert "decision" in res and isinstance(res["decision"], dict), f"missing decision for {stock}"
            assert "summary" in res and isinstance(res["summary"], str), f"missing summary for {stock}"
            assert "recommendation" in res and isinstance(res["recommendation"], str), f"missing recommendation for {stock}"
            assert "reports" in res and isinstance(res["reports"], dict), f"missing reports for {stock}"
            print(f"🎉 {stock} 结果OK：summary={len(res['summary'])} chars, rec={len(res['recommendation'])} chars")
        else:
            print(f"❌ 任务未完成: {stock} ({task_id})")

    with open('batch_results_sample.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("💾 已保存结果样本到 batch_results_sample.json")

    if all_ok:
        print("✅ 方案A批量链路测试通过！")
    else:
        print("⚠️ 部分任务未完成或失败，请检查日志")


if __name__ == '__main__':
    main()

