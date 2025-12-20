import requests
import time
import sys
import os
import json

# 配置
API_BASE = "http://localhost:8000/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login_or_register():
    print(f"尝试登录用户 {USERNAME}...")
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 200:
            print("✅ 登录成功")
            # 处理可能的响应结构差异
            data = resp.json()
            if "data" in data and "access_token" in data["data"]:
                return data["data"]["access_token"]
            elif "access_token" in data:
                return data["access_token"]
            else:
                print(f"❌ 响应中未找到 access_token: {data}")
                sys.exit(1)
        else:
             print(f"❌ 登录失败: {resp.status_code} - {resp.text}")
             sys.exit(1)
    except Exception as e:
        print(f"⚠️ 登录请求异常: {e}")
        sys.exit(1)

def run_analysis(token, symbol):
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "symbol": symbol,
        "parameters": {
            "analysis_type": "index",  # 指定为指数分析
            "market_type": "A股",
            "research_depth": "快速"   # 测试用快速模式
        }
    }
    
    print(f"🚀 提交指数分析任务: {symbol} (类型: index)...")
    resp = requests.post(f"{API_BASE}/analysis/single", json=data, headers=headers)
    if resp.status_code != 200:
        print(f"❌ 提交失败: {resp.text}")
        sys.exit(1)
        
    result = resp.json()
    task_id = result.get("task_id") or result.get("data", {}).get("task_id")
    
    if not task_id:
        print(f"❌ 未能获取 Task ID: {result}")
        sys.exit(1)
        
    print(f"✅ 任务已提交，Task ID: {task_id}")
    return task_id

def wait_for_completion(token, task_id):
    headers = {"Authorization": f"Bearer {token}"}
    print("⏳ 等待任务完成...")
    start_time = time.time()
    
    while True:
        try:
            resp = requests.get(f"{API_BASE}/analysis/tasks/{task_id}/status", headers=headers)
            if resp.status_code != 200:
                print(f"⚠️ 查询状态失败: {resp.text}")
                time.sleep(2)
                continue
                
            data = resp.json()
            # 兼容不同的响应结构
            task_data = data.get("data", data)
            status = task_data.get("status")
            progress = task_data.get("progress", 0)
            
            elapsed = int(time.time() - start_time)
            print(f"\r[{elapsed}s] 状态: {status}, 进度: {progress}%", end="", flush=True)
            
            if status == "completed":
                print("\n✅ 任务完成！")
                return True
            if status == "failed":
                error = task_data.get("error", "未知错误")
                print(f"\n❌ 任务失败: {error}")
                return False
                
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断")
            sys.exit(1)
        except Exception as e:
            print(f"\n⚠️ 轮询异常: {e}")
            time.sleep(2)

def download_pdf(token, task_id, filename):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"📥 正在下载 PDF 到 {filename}...")
    
    url = f"{API_BASE}/reports/{task_id}/download"
    params = {"format": "pdf"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, stream=True)
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ 下载成功: {filename}")
        else:
            print(f"❌ 下载失败 (HTTP {resp.status_code}): {resp.text}")
            if "wkhtmltopdf" in resp.text or "not available" in resp.text:
                print("💡 提示: 服务器缺少 wkhtmltopdf，无法生成 PDF。尝试下载 Markdown...")
                download_markdown(token, task_id, filename.replace(".pdf", ".md"))
    except Exception as e:
        print(f"❌ 下载过程出错: {e}")

def download_markdown(token, task_id, filename):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"📥 正在下载 Markdown 到 {filename}...")
    
    url = f"{API_BASE}/reports/{task_id}/download"
    params = {"format": "markdown"}
    
    resp = requests.get(url, params=params, headers=headers, stream=True)
    if resp.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ 下载成功: {filename}")
    else:
        print(f"❌ Markdown 下载也失败: {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python download_index_report.py <指数名称/代码> [输出文件名]")
        print("示例: python download_index_report.py 半导体 semiconductor_report.pdf")
        sys.exit(1)
        
    symbol = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"{symbol}_report.pdf"
    
    # 检查API服务是否就绪
    try:
        requests.get(f"{API_BASE}/health")
    except:
        print("❌ 无法连接到后端服务，请确保服务已启动 (localhost:8000)")
        sys.exit(1)
        
    token = login_or_register()
    task_id = run_analysis(token, symbol)
    if wait_for_completion(token, task_id):
        download_pdf(token, task_id, output_file)
