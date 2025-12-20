'''
Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
Date: 2025-12-20 23:57:07
LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
LastEditTime: 2025-12-21 00:03:23
FilePath: /TradingAgents-CN-Test/scripts/inspect_task_result.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
import requests
import json
import sys

API_BASE = "http://localhost:8000/api"
USERNAME = "admin"
PASSWORD = "admin123"
TASK_ID = "70e3c300-135d-45dd-ba9f-638978d58516"

def login():
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 200:
            return resp.json()["data"]["access_token"]
        else:
            print(f"❌ Login failed: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

def get_task_result(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/analysis/tasks/{TASK_ID}/status"
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            # Dump the full JSON to inspect structure
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Failed to get task: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    token = login()
    get_task_result(token)
