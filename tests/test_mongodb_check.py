#!/usr/bin/env python3
"""
检查MongoDB中的分析记录
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入MongoDB报告管理器
try:
    from web.utils.mongodb_report_manager import mongodb_report_manager
    print(f"✅ MongoDB报告管理器导入成功")
except ImportError as e:
    print(f"❌ MongoDB报告管理器导入失败: {e}")
    if __name__ == "__main__":
        # 手动运行时保持原有退出行为
        sys.exit(1)
    # pytest 收集时跳过整个模块，避免 sys.exit 中断收集
    import pytest
    pytest.skip(f"MongoDB报告管理器导入失败，跳过检查脚本: {e}", allow_module_level=True)

def check_mongodb_connection():
    """检查MongoDB连接状态"""
    print(f"\n🔍 检查MongoDB连接状态...")
    print(f"连接状态: {mongodb_report_manager.connected}")
    
    if not mongodb_report_manager.connected:
        print(f"❌ MongoDB未连接")
        return False
    
    print(f"✅ MongoDB连接正常")
    return True

def check_analysis_records():
    """检查分析记录"""
    print(f"\n📊 检查分析记录...")
    
    try:
        # 获取所有记录
        all_reports = mongodb_report_manager.get_all_reports(limit=50)
        print(f"总记录数: {len(all_reports)}")
        
        if not all_reports:
            print(f"⚠️ MongoDB中没有分析记录")
            return
        
        # 显示最近的记录
        print(f"\n📋 最近的分析记录:")
        for i, report in enumerate(all_reports[:5]):
            print(f"\n记录 {i+1}:")
            print(f"  分析ID: {report.get('analysis_id', 'N/A')}")
            print(f"  股票代码: {report.get('stock_symbol', 'N/A')}")
            print(f"  分析日期: {report.get('analysis_date', 'N/A')}")
            print(f"  状态: {report.get('status', 'N/A')}")
            print(f"  分析师: {report.get('analysts', [])}")
            print(f"  研究深度: {report.get('research_depth', 'N/A')}")
            
            # 检查报告内容
            reports = report.get('reports', {})
            print(f"  报告模块数量: {len(reports)}")
            
            if reports:
                print(f"  报告模块:")
                for module_name, content in reports.items():
                    content_length = len(content) if isinstance(content, str) else 0
                    print(f"    - {module_name}: {content_length} 字符")
                    
                    # 检查内容是否为空或只是占位符
                    if content_length == 0:
                        print(f"      ⚠️ 内容为空")
                    elif isinstance(content, str) and ("暂无详细分析" in content or "演示数据" in content):
                        print(f"      ⚠️ 内容为演示数据或占位符")
                    else:
                        print(f"      ✅ 内容正常")
            else:
                print(f"  ⚠️ 没有报告内容")
                
    except Exception as e:
        print(f"❌ 检查分析记录失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

def check_specific_stock(stock_symbol="000001"):
    """检查特定股票的记录"""
    print(f"\n🔍 检查股票 {stock_symbol} 的记录...")
    
    try:
        reports = mongodb_report_manager.get_analysis_reports(
            limit=10, 
            stock_symbol=stock_symbol
        )
        
        print(f"股票 {stock_symbol} 的记录数: {len(reports)}")
        
        if reports:
            latest_report = reports[0]
            print(f"\n最新记录详情:")
            print(f"  分析ID: {latest_report.get('analysis_id')}")
            print(f"  时间戳: {latest_report.get('timestamp')}")
            print(f"  状态: {latest_report.get('status')}")
            
            reports_content = latest_report.get('reports', {})
            if reports_content:
                print(f"\n报告内容详情:")
                for module_name, content in reports_content.items():
                    if isinstance(content, str):
                        preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"\n{module_name}:")
                        print(f"  长度: {len(content)} 字符")
                        print(f"  预览: {preview}")
        else:
            print(f"⚠️ 没有找到股票 {stock_symbol} 的记录")
            
    except Exception as e:
        print(f"❌ 检查特定股票记录失败: {e}")

def main():
    print(f"🔍 MongoDB分析记录检查工具")
    print(f"=" * 50)
    
    # 检查连接
    if not check_mongodb_connection():
        return
    
    # 检查所有记录
    check_analysis_records()
    
    # 检查特定股票
    check_specific_stock("000001")
    
    print(f"\n🎉 检查完成")

if __name__ == "__main__":
    main()