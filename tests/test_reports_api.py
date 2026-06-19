#!/usr/bin/env python3
"""
测试分析报告API功能
"""
import requests
import json
import time
from datetime import datetime

def login_and_get_token(base_url):
    """登录并获取token"""
    login_data = {
        "username": "admin",
        "password": "admin123"
    }

    response = requests.post(
        f"{base_url}/api/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            token = result["data"]["access_token"]
            print(f"✅ 登录成功，获取到token")
            return token
        else:
            print(f"❌ 登录失败: {result.get('message', '未知错误')}")
            return None
    else:
        print(f"❌ 登录请求失败: {response.status_code}")
        print(f"   错误信息: {response.text}")
        return None

def test_reports_api():
    """测试报告API功能"""
    base_url = "http://localhost:8100"

    # 先登录获取token
    print("0. 登录获取token...")
    token = login_and_get_token(base_url)
    if not token:
        print("❌ 无法获取token，测试终止")
        return False

    # 使用真实token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        print("🧪 测试分析报告API功能")
        print("=" * 50)
        
        # 1. 检查API健康状态
        print("\n1. 检查API健康状态...")
        health_response = requests.get(f"{base_url}/api/health")
        if health_response.status_code == 200:
            print("✅ API服务正常运行")
        else:
            print(f"❌ API服务异常: {health_response.status_code}")
            return False
        
        # 2. 获取报告列表
        print("\n2. 获取报告列表...")
        reports_response = requests.get(
            f"{base_url}/api/reports/list",
            headers=headers
        )
        
        if reports_response.status_code == 200:
            reports_data = reports_response.json()
            print(f"✅ 报告列表获取成功")
            print(f"   总数: {reports_data['data']['total']}")
            print(f"   当前页: {reports_data['data']['page']}")
            print(f"   每页数量: {reports_data['data']['page_size']}")
            print(f"   报告数量: {len(reports_data['data']['reports'])}")
            
            # 显示前几个报告
            reports = reports_data['data']['reports']
            if reports:
                print(f"\n📋 前3个报告:")
                for i, report in enumerate(reports[:3]):
                    print(f"   {i+1}. {report['stock_code']} - {report['analysis_date']}")
                    print(f"      ID: {report['id']}")
                    print(f"      状态: {report['status']}")
                    print(f"      分析师: {', '.join(report['analysts'])}")
                    print(f"      创建时间: {report['created_at']}")
                
                # 3. 测试获取报告详情
                if reports:
                    test_report = reports[0]
                    print(f"\n3. 获取报告详情...")
                    print(f"   测试报告ID: {test_report['id']}")
                    
                    detail_response = requests.get(
                        f"{base_url}/api/reports/{test_report['id']}/detail",
                        headers=headers
                    )
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        print(f"✅ 报告详情获取成功")
                        
                        report_detail = detail_data['data']
                        print(f"   股票代码: {report_detail['stock_symbol']}")
                        print(f"   分析日期: {report_detail['analysis_date']}")
                        print(f"   摘要长度: {len(report_detail.get('summary', ''))}")
                        
                        # 检查报告模块
                        reports_content = report_detail.get('reports', {})
                        print(f"   报告模块数量: {len(reports_content)}")
                        for module_name, content in reports_content.items():
                            if isinstance(content, str):
                                print(f"     - {module_name}: {len(content)} 字符")
                            else:
                                print(f"     - {module_name}: {type(content)}")
                        
                        # 4. 测试下载报告
                        print(f"\n4. 测试下载报告...")
                        download_response = requests.get(
                            f"{base_url}/api/reports/{test_report['id']}/download?format=markdown",
                            headers=headers
                        )
                        
                        if download_response.status_code == 200:
                            print(f"✅ 报告下载成功")
                            print(f"   文件大小: {len(download_response.content)} 字节")
                            print(f"   Content-Type: {download_response.headers.get('content-type')}")
                            
                            # 保存下载的文件用于检查
                            filename = f"test_download_{test_report['stock_code']}.md"
                            with open(filename, 'wb') as f:
                                f.write(download_response.content)
                            print(f"   已保存到: {filename}")
                        else:
                            print(f"❌ 报告下载失败: {download_response.status_code}")
                            print(f"   错误信息: {download_response.text}")
                        
                        # 5. 测试获取特定模块内容
                        if reports_content:
                            module_name = list(reports_content.keys())[0]
                            print(f"\n5. 测试获取模块内容...")
                            print(f"   测试模块: {module_name}")
                            
                            module_response = requests.get(
                                f"{base_url}/api/reports/{test_report['id']}/content/{module_name}",
                                headers=headers
                            )
                            
                            if module_response.status_code == 200:
                                module_data = module_response.json()
                                print(f"✅ 模块内容获取成功")
                                print(f"   模块名称: {module_data['data']['module']}")
                                print(f"   内容类型: {module_data['data']['content_type']}")
                                print(f"   内容长度: {len(str(module_data['data']['content']))}")
                            else:
                                print(f"❌ 模块内容获取失败: {module_response.status_code}")
                    else:
                        print(f"❌ 报告详情获取失败: {detail_response.status_code}")
                        print(f"   错误信息: {detail_response.text}")
            else:
                print("⚠️ 没有找到报告，可能需要先运行一些分析任务")
        else:
            print(f"❌ 报告列表获取失败: {reports_response.status_code}")
            print(f"   错误信息: {reports_response.text}")
            return False
        
        # 6. 测试搜索功能
        print(f"\n6. 测试搜索功能...")
        search_response = requests.get(
            f"{base_url}/api/reports/list?search_keyword=000001",
            headers=headers
        )
        
        if search_response.status_code == 200:
            search_data = search_response.json()
            print(f"✅ 搜索功能正常")
            print(f"   搜索结果数量: {len(search_data['data']['reports'])}")
        else:
            print(f"❌ 搜索功能失败: {search_response.status_code}")
        
        print(f"\n🎉 报告API测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_reports_with_filters():
    """测试带筛选条件的报告查询"""
    base_url = "http://localhost:8100"

    # 获取token
    token = login_and_get_token(base_url)
    if not token:
        print("❌ 无法获取token，跳过筛选测试")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    print(f"\n🔍 测试筛选功能...")
    
    # 测试不同的筛选条件
    filters = [
        {"status_filter": "completed"},
        {"start_date": "2025-08-01", "end_date": "2025-08-31"},
        {"stock_code": "000001"},
        {"page": 1, "page_size": 5}
    ]
    
    for i, filter_params in enumerate(filters):
        print(f"\n   测试筛选 {i+1}: {filter_params}")
        
        params = "&".join([f"{k}={v}" for k, v in filter_params.items()])
        response = requests.get(
            f"{base_url}/api/reports/list?{params}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 筛选成功，结果数量: {len(data['data']['reports'])}")
        else:
            print(f"   ❌ 筛选失败: {response.status_code}")

if __name__ == "__main__":
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = test_reports_api()
    
    if success:
        test_reports_with_filters()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
