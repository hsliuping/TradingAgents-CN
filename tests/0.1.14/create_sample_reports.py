#!/usr/bin/env python3
"""
创建示例分析报告
用于测试Web界面的报告显示功能
"""

import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

def create_sample_report(stock_symbol: str, stock_name: str):
    """创建示例分析报告"""
    
    # 分析结果数据
    analysis_results = {
        "summary": f"{stock_name}({stock_symbol}) 综合分析显示该股票具有良好的投资潜力，建议关注。",
        "analysts": ["market_analyst", "fundamentals_analyst", "trader_agent"]
    }
    
    # 报告内容
    reports = {
        "final_trade_decision": f"""# {stock_name}({stock_symbol}) 最终分析结果

## 📊 投资建议
**行动**: 买入
**置信度**: 85%
**风险评分**: 25%
**目标价格**: 当前价格上涨15-20%

## 🎯 关键要点
- 技术面显示上涨趋势
- 基本面财务状况良好
- 市场情绪积极
- 风险可控

## 💡 分析推理
基于多维度分析，该股票在技术面、基本面和市场情绪方面都表现良好。技术指标显示突破关键阻力位，成交量放大确认上涨趋势。基本面分析显示公司财务稳健，盈利能力强。综合评估建议买入并持有。

## ⚠️ 风险提示
- 市场整体波动风险
- 行业政策变化风险
- 建议设置止损位
""",

        "fundamentals_report": f"""# {stock_name}({stock_symbol}) 基本面分析报告

## 📈 财务指标分析
### 盈利能力
- **净利润增长率**: 15.2% (同比)
- **ROE**: 18.5%
- **ROA**: 12.3%
- **毛利率**: 35.8%

### 偿债能力
- **资产负债率**: 45.2%
- **流动比率**: 2.1
- **速动比率**: 1.8
- **利息保障倍数**: 8.5

### 运营能力
- **总资产周转率**: 1.2
- **存货周转率**: 6.8
- **应收账款周转率**: 9.2

## 🏢 公司基本情况
- **行业地位**: 行业龙头企业
- **主营业务**: 稳定增长
- **市场份额**: 持续扩大
- **竞争优势**: 技术领先，品牌知名度高

## 📊 估值分析
- **PE**: 15.2倍 (合理估值区间)
- **PB**: 2.1倍
- **PEG**: 0.8 (低于1，具有投资价值)

## 💰 投资亮点
1. 财务状况稳健，盈利能力强
2. 行业地位稳固，竞争优势明显
3. 估值合理，具有投资价值
4. 分红政策稳定，股东回报良好
""",

        "market_report": f"""# {stock_name}({stock_symbol}) 技术面分析报告

## 📈 价格趋势分析
### 短期趋势 (5-20日)
- **趋势方向**: 上涨
- **支撑位**: ¥45.20
- **阻力位**: ¥52.80
- **当前位置**: 突破前期高点

### 中期趋势 (20-60日)
- **趋势方向**: 上涨
- **主要支撑**: ¥42.50
- **目标位**: ¥55.00
- **趋势强度**: 强

## 📊 技术指标分析
### 趋势指标
- **MA5**: 48.50 (价格在均线上方)
- **MA20**: 46.80 (多头排列)
- **MA60**: 44.20 (长期上涨趋势)

### 动量指标
- **RSI(14)**: 68.5 (偏强，未超买)
- **MACD**: 金叉向上
- **KDJ**: K=75, D=68, J=82 (强势区域)

### 成交量分析
- **成交量**: 放量上涨
- **量价关系**: 价涨量增，健康上涨
- **换手率**: 3.2% (活跃)

## 🎯 操作建议
### 买入信号
- 突破前期高点
- 成交量配合
- 技术指标向好

### 关键位置
- **买入位**: ¥48.00-49.00
- **止损位**: ¥45.00
- **目标位**: ¥55.00

## ⚠️ 风险提示
- 注意大盘整体走势
- 关注成交量变化
- 设置合理止损位
"""
    }
    
    return analysis_results, reports

def main():
    """主函数"""
    print("🎨 创建示例分析报告...")
    
    try:
        from web.utils.mongodb_report_manager import mongodb_report_manager
        
        if not mongodb_report_manager.connected:
            print("❌ MongoDB未连接")
            return
        
        # 创建多个示例报告
        sample_stocks = [
            ("DEMO001", "示例科技股"),
            ("DEMO002", "示例银行股"),
            ("DEMO003", "示例消费股"),
            ("000001", "平安银行"),
            ("000002", "万科A")
        ]
        
        success_count = 0
        
        for stock_symbol, stock_name in sample_stocks:
            print(f"📝 创建 {stock_name}({stock_symbol}) 的分析报告...")
            
            analysis_results, reports = create_sample_report(stock_symbol, stock_name)
            
            success = mongodb_report_manager.save_analysis_report(
                stock_symbol=stock_symbol,
                analysis_results=analysis_results,
                reports=reports
            )
            
            if success:
                success_count += 1
                print(f"✅ {stock_name} 报告创建成功")
            else:
                print(f"❌ {stock_name} 报告创建失败")
        
        print(f"\n🎉 完成！成功创建 {success_count}/{len(sample_stocks)} 个示例报告")
        print("💡 现在可以在Web界面中查看这些报告了")
        
    except Exception as e:
        print(f"❌ 创建示例报告失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
