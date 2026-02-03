#!/usr/bin/env python3
"""
测试分析结果保存功能
模拟分析完成后的保存过程
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

def create_mock_analysis_results():
    """创建模拟的分析结果数据"""
    return {
        'stock_symbol': 'TEST123',
        'analysis_date': '2025-07-31',
        'analysts': ['market_analyst', 'fundamentals_analyst', 'trader_agent'],
        'research_depth': 3,
        'state': {
            'market_report': """# TEST123 股票技术分析报告

## 📈 价格趋势分析
当前股价呈现上涨趋势，技术指标向好。

## 📊 技术指标
- RSI: 65.2 (偏强)
- MACD: 金叉向上
- 成交量: 放量上涨

## 🎯 操作建议
建议在回调时买入，目标价位上涨15%。
""",
            'fundamentals_report': """# TEST123 基本面分析报告

## 💰 财务状况
公司财务状况良好，盈利能力强。

## 📊 关键指标
- ROE: 18.5%
- PE: 15.2倍
- 净利润增长: 15.2%

## 💡 投资价值
估值合理，具有投资价值。
""",
            'final_trade_decision': """# TEST123 最终分析结果

## 🎯 投资建议
**行动**: 买入
**置信度**: 85%
**目标价格**: 上涨15-20%

## 💡 决策依据
基于技术面和基本面综合分析，建议买入。
"""
        },
        'decision': {
            'action': 'buy',
            'confidence': 0.85,
            'target_price': 'up 15-20%',
            'reasoning': '技术面和基本面都支持买入决策'
        },
        'summary': 'TEST123股票综合分析显示具有良好投资潜力，建议买入。'
    }

def test_save_analysis_result():
    """测试保存分析结果"""
    print("🧪 测试分析结果保存功能")
    print("=" * 40)
    
    try:
        # 导入保存函数
        from web.components.analysis_results import save_analysis_result
        
        # 创建模拟数据
        analysis_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stock_symbol = "TEST123"
        analysts = ['market_analyst', 'fundamentals_analyst', 'trader_agent']
        research_depth = 3
        result_data = create_mock_analysis_results()
        
        print(f"📝 测试数据:")
        print(f"   分析ID: {analysis_id}")
        print(f"   股票代码: {stock_symbol}")
        print(f"   分析师: {analysts}")
        print(f"   研究深度: {research_depth}")
        
        # 执行保存
        print(f"\n💾 开始保存分析结果...")
        success = save_analysis_result(
            analysis_id=analysis_id,
            stock_symbol=stock_symbol,
            analysts=analysts,
            research_depth=research_depth,
            result_data=result_data,
            status="completed"
        )
        
        if success:
            print("✅ 分析结果保存成功！")
            
            # 检查文件是否创建
            print(f"\n📁 检查保存的文件:")
            
            # 检查JSON文件
            from web.components.analysis_results import get_analysis_results_dir
            results_dir = get_analysis_results_dir()
            json_file = results_dir / f"analysis_{analysis_id}.json"
            
            if json_file.exists():
                print(f"✅ JSON文件已创建: {json_file}")
            else:
                print(f"❌ JSON文件未找到: {json_file}")
            
            # 检查详细报告目录
            import os
            from pathlib import Path
            
            # 获取项目根目录
            project_root = Path(__file__).parent
            results_dir_env = os.getenv("TRADINGAGENTS_RESULTS_DIR", "./data/analysis_results")
            
            if not os.path.isabs(results_dir_env):
                detailed_results_dir = project_root / results_dir_env
            else:
                detailed_results_dir = Path(results_dir_env)
            
            analysis_date = datetime.now().strftime('%Y-%m-%d')
            reports_dir = detailed_results_dir / stock_symbol / analysis_date / "reports"
            
            print(f"📂 详细报告目录: {reports_dir}")
            
            if reports_dir.exists():
                print("✅ 详细报告目录已创建")
                
                # 列出报告文件
                report_files = list(reports_dir.glob("*.md"))
                if report_files:
                    print(f"📄 报告文件 ({len(report_files)} 个):")
                    for file in report_files:
                        print(f"   - {file.name}")
                else:
                    print("⚠️ 报告目录存在但无文件")
            else:
                print(f"❌ 详细报告目录未创建: {reports_dir}")
            
        else:
            print("❌ 分析结果保存失败")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mongodb_save():
    """测试MongoDB保存"""
    print(f"\n🗄️ 测试MongoDB保存...")
    
    try:
        from web.utils.mongodb_report_manager import mongodb_report_manager
        
        if not mongodb_report_manager.connected:
            print("❌ MongoDB未连接")
            return False
        
        # 获取当前记录数
        before_count = len(mongodb_report_manager.get_analysis_reports(limit=1000))
        print(f"📊 保存前MongoDB记录数: {before_count}")
        
        # 执行测试保存
        test_save_analysis_result()
        
        # 获取保存后记录数
        after_count = len(mongodb_report_manager.get_analysis_reports(limit=1000))
        print(f"📊 保存后MongoDB记录数: {after_count}")
        
        if after_count > before_count:
            print("✅ MongoDB记录增加，保存成功")
            return True
        else:
            print("⚠️ MongoDB记录数未增加")
            return False
            
    except Exception as e:
        print(f"❌ MongoDB测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 分析结果保存功能测试")
    print("=" * 50)
    
    # 测试基本保存功能
    save_success = test_save_analysis_result()
    
    # 测试MongoDB保存
    mongodb_success = test_mongodb_save()
    
    print(f"\n🎉 测试完成")
    print(f"📄 文件保存: {'✅ 成功' if save_success else '❌ 失败'}")
    print(f"🗄️ MongoDB保存: {'✅ 成功' if mongodb_success else '❌ 失败'}")

if __name__ == "__main__":
    main()
