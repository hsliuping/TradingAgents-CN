#!/usr/bin/env python3
"""
调试API响应格式
"""

import requests
import json
from pymongo import MongoClient
import os
from dotenv import load_dotenv

def debug_api_response():
    """调试API响应格式"""
    print("🔍 调试API响应格式")
    print("=" * 60)
    
    # 获取最新的任务ID
    try:
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量获取MongoDB配置
        mongodb_host = os.getenv("MONGODB_HOST", "localhost")
        mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
        mongodb_username = os.getenv("MONGODB_USERNAME")
        mongodb_password = os.getenv("MONGODB_PASSWORD")
        mongodb_database = os.getenv("MONGODB_DATABASE", "tradingagents")
        mongodb_auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
        
        # 构建连接参数
        connect_kwargs = {
            "host": mongodb_host,
            "port": mongodb_port,
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 5000
        }

        # 如果有用户名和密码，添加认证信息
        if mongodb_username and mongodb_password:
            connect_kwargs.update({
                "username": mongodb_username,
                "password": mongodb_password,
                "authSource": mongodb_auth_source
            })
        
        # 连接MongoDB
        client = MongoClient(**connect_kwargs)
        db = client[mongodb_database]
        
        # 获取最新的任务
        reports_collection = db['analysis_reports']
        latest_report = reports_collection.find_one(
            {"source": "api", "task_id": {"$exists": True}},
            sort=[("created_at", -1)]
        )
        
        if not latest_report:
            print("❌ 没有找到任务")
            return
        
        task_id = latest_report["task_id"]
        stock_symbol = latest_report["stock_symbol"]
        print(f"📋 使用任务: {task_id} ({stock_symbol})")
        
        client.close()
        
    except Exception as e:
        print(f"❌ 获取任务ID失败: {e}")
        return
    
    # API基础URL
    base_url = "http://localhost:8100"
    
    try:
        # 1. 登录获取token
        print("\n1. 登录获取token...")
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
            print("✅ 登录成功")
        else:
            print(f"❌ 登录失败: {login_response.status_code}")
            return
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        # 2. 获取任务状态
        print(f"\n2. 获取任务状态...")
        status_response = requests.get(
            f"{base_url}/api/analysis/tasks/{task_id}/status",
            headers=headers
        )
        
        print(f"   状态码: {status_response.status_code}")
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"   响应结构: {list(status_data.keys())}")
            if "data" in status_data:
                print(f"   data字段: {list(status_data['data'].keys())}")
        else:
            print(f"   错误响应: {status_response.text}")
            return
        
        # 3. 获取分析结果
        print(f"\n3. 获取分析结果...")
        result_response = requests.get(
            f"{base_url}/api/analysis/tasks/{task_id}/result",
            headers=headers
        )
        
        print(f"   状态码: {result_response.status_code}")
        if result_response.status_code == 200:
            result_data = result_response.json()
            print(f"   响应结构: {list(result_data.keys())}")
            
            if "data" in result_data:
                data = result_data["data"]
                print(f"   data字段: {list(data.keys())}")
                
                # 重点检查reports字段
                if "reports" in data:
                    reports = data["reports"]
                    print(f"\n📊 reports字段详细分析:")
                    print(f"   类型: {type(reports)}")
                    
                    if isinstance(reports, dict):
                        print(f"   包含 {len(reports)} 个报告:")
                        for key, value in reports.items():
                            print(f"      - {key}:")
                            print(f"        类型: {type(value)}")
                            if isinstance(value, str):
                                print(f"        长度: {len(value)} 字符")
                                print(f"        前50字符: {repr(value[:50])}")
                            elif value is None:
                                print(f"        值: None")
                            else:
                                print(f"        值: {value}")
                    else:
                        print(f"   ❌ reports不是字典类型: {reports}")
                else:
                    print(f"   ❌ 没有reports字段")
                
                # 保存完整响应到文件用于调试
                with open("debug_api_response.json", "w", encoding="utf-8") as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2, default=str)
                print(f"\n💾 完整响应已保存到 debug_api_response.json")
                
        else:
            print(f"   错误响应: {result_response.text}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    debug_api_response()
