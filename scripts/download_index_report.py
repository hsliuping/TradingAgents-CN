#!/usr/bin/env python3
"""
指数分析报告生成工具

此脚本用于连接 TradingAgents-CN 后端服务，提交指数分析任务，并下载生成的分析报告。
支持自动登录、任务状态轮询和 PDF/Markdown 报告下载。

使用方法:
    python scripts/download_index_report.py --index <指数名称或代码> [--output <文件名>] [--depth <深度>]

示例:
    python scripts/download_index_report.py --index 半导体 --depth 深度 --output semiconductor_report.pdf
"""

import requests
import time
import sys
import os
import json
import argparse

# 配置
API_BASE = "http://localhost:8000/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login_or_register():
    """登录系统获取 Token"""
    print(f"🔑 尝试登录用户 {USERNAME}...")
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
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 无法连接到后端服务 {API_BASE}")
        print("💡 请确保后端服务已启动: python -m app.main")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ 登录请求异常: {e}")
        sys.exit(1)

def run_analysis(token, symbol, depth):
    """提交分析任务"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "symbol": symbol,
        "parameters": {
            "analysis_type": "index",  # 指定为指数分析
            "market_type": "A股",
            "research_depth": depth   # 使用参数指定的深度
        }
    }
    
    print(f"🚀 提交指数分析任务: {symbol} (类型: index, 深度: {depth})...")
    try:
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
    except Exception as e:
        print(f"❌ 提交任务异常: {e}")
        sys.exit(1)

def wait_for_completion(token, task_id):
    """等待任务完成"""
    headers = {"Authorization": f"Bearer {token}"}
    print("⏳ 等待任务完成 (按 Ctrl+C 取消)...")
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
            # 动态显示进度条
            bar_len = 20
            filled_len = int(bar_len * progress / 100)
            bar = '█' * filled_len + '-' * (bar_len - filled_len)
            
            print(f"\r[{elapsed}s] 状态: {status} [{bar}] {progress}%", end="", flush=True)
            
            if status == "completed":
                print("\n✅ 任务完成！")
                return True
            if status == "failed":
                error = task_data.get("error", "未知错误")
                print(f"\n❌ 任务失败: {error}")
                # 尝试打印更详细的错误信息
                if "traceback" in task_data:
                    print(f"Traceback: {task_data['traceback']}")
                return False
                
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断等待")
            sys.exit(1)
        except Exception as e:
            print(f"\n⚠️ 轮询异常: {e}")
            time.sleep(2)

def download_pdf(token, task_id, filename):
    """下载 PDF 报告"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 确保文件名以 .pdf 结尾
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
        
    print(f"📥 正在下载 PDF 到 {filename}...")
    
    # 尝试直接下载 PDF
    try:
        resp = requests.get(f"{API_BASE}/reports/{task_id}/download?format=pdf", headers=headers, stream=True)
        
        if resp.status_code == 200:
            with open(filename, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"✅ PDF 下载成功: {filename}")
            print(f"📄 文件大小: {os.path.getsize(filename) / 1024:.2f} KB")
        else:
            print(f"❌ PDF 下载失败: {resp.status_code} - {resp.text}")
            # 尝试下载 Markdown 作为后备
            md_filename = filename.replace('.pdf', '.md')
            print(f"⚠️ 尝试下载 Markdown 到 {md_filename}...")
            resp = requests.get(f"{API_BASE}/reports/{task_id}/download?format=markdown", headers=headers, stream=True)
            if resp.status_code == 200:
                with open(md_filename, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Markdown 下载成功: {md_filename}")
            else:
                 print(f"❌ Markdown 下载也失败: {resp.status_code}")
                 
    except Exception as e:
        print(f"❌ 下载过程异常: {e}")

def main():
    parser = argparse.ArgumentParser(description='TradingAgents-CN 指数分析报告生成工具')
    parser.add_argument('--index', required=True, help='指数名称或代码 (例如: 半导体, sh000001)')
    parser.add_argument('--output', default='report.pdf', help='输出文件名 (默认: report.pdf)')
    parser.add_argument('--depth', default='深度', choices=['快速', '深度', '详细'], help='研究深度 (默认: 深度)')
    
    args = parser.parse_args()

    # 设置默认下载目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(project_root, "文档")
    
    # 处理输出路径
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(docs_dir, output_path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print("=" * 50)
    print(f"📊 开始指数分析任务")
    print(f"🎯 目标指数: {args.index}")
    print(f"🔍 分析深度: {args.depth}")
    print(f"📂 保存路径: {output_path}")
    print("=" * 50)
    
    token = login_or_register()
    task_id = run_analysis(token, args.index, args.depth)
    if wait_for_completion(token, task_id):
        download_pdf(token, task_id, output_path)

if __name__ == "__main__":
    main()
