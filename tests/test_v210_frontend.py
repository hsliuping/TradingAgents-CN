"""
测试v2.1.0前端新功能展示
"""

import streamlit as st
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入测试模块
from web.components.results_display import (
    render_international_news,
    render_policy_analysis, 
    render_strategy_details,
    render_detailed_analysis,
    render_decision_summary
)

def create_mock_v210_data():
    """创建v2.1.0模拟数据"""
    
    # 模拟国际新闻分析数据
    international_news = {
        'impact_assessment': {
            'impact_strength': '高',
            'impact_duration': '短期（1-2周）',
            'risk_level': '中',
            'confidence': 0.85
        },
        'key_news': [
            {
                'title': '美联储暗示可能放缓加息步伐',
                'source': 'Bloomberg',
                'date': '2024-01-15',
                'type': '货币政策',
                'impact': '市场情绪提振，科技股受益',
                'impact_strength': '高',
                'covered_by_policy_analyst': True,
                'summary': '美联储官员最新表态显示对通胀前景更加乐观'
            },
            {
                'title': '中美贸易谈判取得积极进展',
                'source': 'Reuters',
                'date': '2024-01-14',
                'type': '贸易政策',
                'impact': '双边关系改善，出口板块利好',
                'impact_strength': '中',
                'covered_by_policy_analyst': True,
                'summary': '双方在关键技术领域达成初步共识'
            },
            {
                'title': '欧洲央行维持利率不变',
                'source': 'Financial Times',
                'date': '2024-01-13',
                'type': '货币政策',
                'impact': '对全球流动性的直接影响有限',
                'impact_strength': '低',
                'covered_by_policy_analyst': False,
                'summary': '符合市场预期，政策立场保持谨慎'
            }
        ],
        'overall_impact': '积极偏向，短期利好科技和出口板块',
        'analysis_content': '''
基于国际新闻分析，当前市场环境呈现以下特点：
1. 货币政策环境有所改善，全球流动性压力缓解
2. 中美关系出现积极信号，有利于相关板块表现
3. 欧洲市场保持稳定，对全球市场影响中性

综合评估认为，国际环境对A股市场整体偏积极，建议关注科技、新能源等受益板块。
        '''
    }
    
    # 模拟政策分析数据
    policy_analysis = {
        'long_term_policies': [
            {
                'name': '十四五规划新能源产业发展',
                'duration': '2021-2025年',
                'support_strength': '强',
                'beneficiary_sectors': '新能源、光伏、风电、储能',
                'policy_continuity': '高',
                'impact': '长期驱动新能源产业链发展'
            },
            {
                'name': '数字经济国家战略',
                'duration': '2021-2030年',
                'support_strength': '强',
                'beneficiary_sectors': '云计算、人工智能、大数据',
                'policy_continuity': '极高',
                'impact': '推动数字产业化快速发展'
            },
            {
                'name': '碳中和目标推进计划',
                'duration': '2021-2060年',
                'support_strength': '中强',
                'beneficiary_sectors': '环保、新能源、节能减排',
                'policy_continuity': '极高',
                'impact': '重塑能源结构和产业格局'
            }
        ],
        'overall_support_strength': '强',
        'analysis_content': '''
政策环境分析显示：
1. 新能源和数字经济是长期政策重点，支持力度强且连续性高
2. 碳中和目标为相关产业提供长期发展空间
3. 政策支持主要集中在科技创新和绿色转型领域

建议重点关注政策支持力度强、连续性高的板块进行长期配置。
        '''
    }
    
    # 模拟策略详情数据
    strategy_details = {
        'final_position': 0.75,
        'position_breakdown': {
            'core_holding': 0.67,
            'tactical_allocation': 0.33,
            'cash_reserve': 0.0
        },
        'adjustment_triggers': {
            'increase_condition': '国际重大利好政策确认，市场情绪显著改善',
            'increase_to': 0.9,
            'decrease_condition': '国际地缘政治风险升级，主要经济体政策转向紧缩',
            'decrease_to': 0.5
        },
        'analysis_content': '''
基于当前市场环境和政策分析，制定如下投资策略：

仓位配置逻辑：
- 核心持仓67%：基于长期政策支持的稳定配置，主要布局新能源、数字经济等政策受益板块
- 战术配置33%：捕捉短期国际新闻驱动的机会，重点关注科技、消费等弹性较大的板块
- 现金储备0%：当前市场环境积极，充分参与市场机会

动态调整机制：
- 加仓触发：国际重大利好确认，仓位提升至90%
- 减仓触发：地缘政治风险升级，仓位降低至50%

策略特点：平衡长期政策支持和短期机会把握，保持适度的灵活性应对市场变化。
        '''
    }
    
    # 模拟决策数据
    decision = {
        'action': '买入',
        'confidence': 0.85,
        'reasoning': '基于国际新闻分析和政策支持，当前市场环境积极，建议增加仓位配置',
        'target_price': 3500.0,
        'risk_score': 0.3
    }
    
    return {
        'international_news_analysis': international_news,
        'policy_analysis': policy_analysis,
        'strategy_details': strategy_details,
        'decision': decision,
        'stock_symbol': '000001'
    }

def create_mock_v200_data():
    """创建v2.0.0模拟数据（向后兼容性测试）"""
    
    return {
        'market_report': '市场技术分析报告内容...',
        'fundamentals_report': '基本面分析报告内容...',
        'sentiment_report': '市场情绪分析报告内容...',
        'news_report': '新闻事件分析报告内容...',
        'risk_assessment': '风险评估报告内容...',
        'investment_plan': '投资建议报告内容...',
        'decision': {
            'action': '持有',
            'confidence': 0.7,
            'reasoning': '市场处于震荡整理阶段，建议保持观望',
            'target_price': None,
            'risk_score': 0.5
        },
        'stock_symbol': '000002'
    }

def main():
    """主测试函数"""
    
    st.set_page_config(
        page_title="v2.1.0前端功能测试",
        page_icon="🧪",
        layout="wide"
    )
    
    st.title("🧪 v2.1.0前端新功能测试")
    st.markdown("---")
    
    # 测试选择
    test_mode = st.radio(
        "选择测试模式",
        ["v2.1.0新功能测试", "v2.0.0向后兼容性测试", "对比测试"]
    )
    
    if test_mode == "v2.1.0新功能测试":
        st.header("🌟 v2.1.0新功能展示")
        
        mock_data = create_mock_v210_data()
        
        # 测试决策摘要
        st.subheader("📊 决策摘要测试")
        render_decision_summary(
            mock_data['decision'], 
            mock_data['stock_symbol'],
            mock_data['strategy_details']
        )
        
        st.markdown("---")
        
        # 测试国际新闻分析
        st.subheader("🌍 国际新闻分析测试")
        render_international_news(mock_data['international_news_analysis'])
        
        st.markdown("---")
        
        # 测试政策分析
        st.subheader("🏛️ 政策分析测试")
        render_policy_analysis(mock_data['policy_analysis'])
        
        st.markdown("---")
        
        # 测试策略详情
        st.subheader("📋 策略详情测试")
        render_strategy_details(mock_data['strategy_details'])
        
    elif test_mode == "v2.0.0向后兼容性测试":
        st.header("🔄 v2.0.0向后兼容性测试")
        
        mock_data = create_mock_v200_data()
        
        # 测试v2.0.0数据在新组件中的表现
        st.subheader("📊 决策摘要测试（v2.0.0数据）")
        render_decision_summary(
            mock_data['decision'], 
            mock_data['stock_symbol'],
            None  # v2.0.0没有strategy_details
        )
        
        st.markdown("---")
        
        # 测试详细分析
        st.subheader("📋 详细分析测试（v2.0.0数据）")
        render_detailed_analysis(mock_data)
        
    elif test_mode == "对比测试":
        st.header("⚖️ v2.0.0 vs v2.1.0 对比测试")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### v2.0.0 版本")
            v200_data = create_mock_v200_data()
            render_decision_summary(
                v200_data['decision'], 
                v200_data['stock_symbol'],
                None
            )
        
        with col2:
            st.markdown("### v2.1.0 版本")
            v210_data = create_mock_v210_data()
            render_decision_summary(
                v210_data['decision'], 
                v210_data['stock_symbol'],
                v210_data['strategy_details']
            )
    
    # 技术信息
    st.markdown("---")
    with st.expander("🔧 技术实现信息", expanded=False):
        st.markdown("""
        **v2.1.0新增功能**:
        - 🌍 国际新闻分析：监测Bloomberg、Reuters等国际媒体
        - 🏛️ 政策分析：长期政策支持与连续性评估
        - 📋 策略详情：仓位分配与动态调整机制
        - 🔄 向后兼容：完全兼容v2.0.0数据格式
        
        **技术特性**:
        - Plotly可视化：仓位分配饼图
        - 响应式设计：适配不同屏幕尺寸
        - 错误处理：优雅处理缺失数据
        - 版本检测：自动识别数据版本
        """)

if __name__ == "__main__":
    main()