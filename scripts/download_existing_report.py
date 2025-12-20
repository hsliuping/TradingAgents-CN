import requests
import sys
import os

API_BASE = "http://localhost:8000/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 200:
            return resp.json()["data"]["access_token"]
        else:
            print(f"❌ 登录失败: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 连接服务器失败: {e}")
        sys.exit(1)

def download_pdf(token, task_id, output_file):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE}/reports/{task_id}/download"
    params = {"format": "pdf"}
    
    print(f"📥 正在下载任务 {task_id} 的 PDF 报告...")
    try:
        resp = requests.get(url, params=params, headers=headers)
        
        if resp.status_code == 200:
            # 写入文件
            with open(output_file, "wb") as f:
                f.write(resp.content)
            
            abs_path = os.path.abspath(output_file)
            print(f"✅ 下载成功！")
            print(f"📄 文件保存位置: {abs_path}")
            print(f"📦 文件大小: {len(resp.content) / 1024:.2f} KB")
        else:
            print(f"❌ 下载失败: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ 下载过程出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python download_existing_report.py <task_id> [output_file]")
        sys.exit(1)
        
    task_id = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"report_{task_id}.pdf"
    
    token = login()
    download_pdf(token, task_id, output_file)
