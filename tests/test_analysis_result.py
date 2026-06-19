#!/usr/bin/env python3
"""
测试分析结果数据结构
"""
import requests
import json
from datetime import datetime

def test_analysis_result():
    """测试分析结果的数据结构"""
    base_url = "http://localhost:8100"
    
    # 登录获取token
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(
        f"{base_url}/api/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"❌ 登录失败: {response.status_code}")
        return
    
    result = response.json()
    if not result.get("success"):
        print(f"❌ 登录失败: {result.get('message')}")
        return
    
    token = result["data"]["access_token"]
    print(f"✅ 登录成功")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # 获取报告列表
        print("\n1. 获取报告列表...")
        reports_response = requests.get(
            f"{base_url}/api/reports/list?page_size=1",
            headers=headers
        )
        
        if reports_response.status_code != 200:
            print(f"❌ 获取报告列表失败: {reports_response.status_code}")
            return
        
        reports_data = reports_response.json()
        if not reports_data.get("success") or not reports_data["data"]["reports"]:
            print("❌ 没有找到报告")
            return
        
        # 获取第一个报告的详情
        first_report = reports_data["data"]["reports"][0]
        report_id = first_report["id"]
        
        print(f"\n2. 获取报告详情: {report_id}")
        detail_response = requests.get(
            f"{base_url}/api/reports/{report_id}/detail",
            headers=headers
        )
        
        if detail_response.status_code != 200:
            print(f"❌ 获取报告详情失败: {detail_response.status_code}")
            return
        
        detail_data = detail_response.json()
        if not detail_data.get("success"):
            print(f"❌ 获取报告详情失败: {detail_data.get('message')}")
            return
        
        report_detail = detail_data["data"]
        
        print(f"\n📊 报告数据结构分析:")
        print(f"   报告ID: {report_detail.get('id')}")
        print(f"   股票代码: {report_detail.get('stock_symbol')}")
        print(f"   分析日期: {report_detail.get('analysis_date')}")
        print(f"   状态: {report_detail.get('status')}")
        
        # 检查关键字段
        print(f"\n🔍 关键字段检查:")
        print(f"   有 decision 字段: {bool(report_detail.get('decision'))}")
        print(f"   有 state 字段: {bool(report_detail.get('state'))}")
        print(f"   有 reports 字段: {bool(report_detail.get('reports'))}")
        print(f"   有 recommendation 字段: {bool(report_detail.get('recommendation'))}")
        
        # 显示所有顶级字段
        print(f"\n📋 所有顶级字段:")
        for key in sorted(report_detail.keys()):
            value = report_detail[key]
            if isinstance(value, dict):
                print(f"   {key}: dict (包含 {len(value)} 个键)")
                if key == 'reports':
                    print(f"      reports 子键: {list(value.keys())}")
            elif isinstance(value, list):
                print(f"   {key}: list (包含 {len(value)} 个元素)")
            else:
                print(f"   {key}: {type(value).__name__} = {str(value)[:100]}")
        
        # 如果有 reports 字段，详细分析
        if report_detail.get('reports'):
            print(f"\n📄 Reports 字段详细分析:")
            reports = report_detail['reports']
            for key, content in reports.items():
                if isinstance(content, str):
                    print(f"   {key}: 字符串 ({len(content)} 字符)")
                    print(f"      前100字符: {content[:100]}...")
                else:
                    print(f"   {key}: {type(content).__name__}")
        
        # 保存完整数据到文件用于分析
        with open('analysis_result_sample.json', 'w', encoding='utf-8') as f:
            json.dump(report_detail, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 完整数据已保存到 analysis_result_sample.json")
        
        # 模拟前端的数据处理逻辑
        print(f"\n🎭 模拟前端数据处理:")
        
        # 检查是否会显示结果
        has_decision = bool(report_detail.get('decision'))
        has_state = bool(report_detail.get('state'))
        has_reports = bool(report_detail.get('reports'))
        
        print(f"   showResults 条件: analysisResults 存在 = True")
        print(f"   decision 部分显示: {has_decision}")
        print(f"   reports 部分显示 (state): {has_state}")
        print(f"   reports 部分显示 (reports): {has_reports}")
        print(f"   reports 部分显示 (任一): {has_state or has_reports}")
        
        # 模拟 getAnalysisReports 函数
        reports_data = None
        if report_detail.get('reports'):
            reports_data = report_detail['reports']
            print(f"   使用 data.reports")
        elif report_detail.get('state'):
            reports_data = report_detail['state']
            print(f"   使用 data.state")
        else:
            print(f"   没有找到报告数据")
            return
        
        # 检查报告映射
        report_mappings = [
            'market_report', 'fundamentals_report', 'news_report', 'sentiment_report',
            'investment_plan', 'trader_investment_plan', 'final_trade_decision',
            'research_team_decision', 'risk_management_decision',
            'investment_debate_state', 'risk_debate_state'
        ]
        
        found_reports = []
        for key in report_mappings:
            if key in reports_data and reports_data[key]:
                found_reports.append(key)
        
        print(f"   找到的报告模块: {found_reports}")
        print(f"   报告数量: {len(found_reports)}")
        
        if len(found_reports) == 0:
            print(f"   ⚠️ 没有找到任何报告模块！")
            print(f"   实际的键: {list(reports_data.keys())}")
        
    except Exception as e:
        print(f"❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    test_analysis_result()
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
