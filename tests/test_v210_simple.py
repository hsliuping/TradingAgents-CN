"""
简化的v2.1.0前端功能测试
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

def render_international_news_simple(news_data):
    """简化的国际新闻分析渲染"""
    
    if not news_data:
        st.info("🌍 暂无国际新闻分析数据")
        return
    
    assessment = news_data.get('impact_assessment', {})
    
    # 顶部指标栏
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        strength_color = {
            '高': '🔴', '中': '🟡', '低': '🟢'
        }.get(assessment.get('impact_strength', '低'), '🟢')
        st.metric(f"{strength_color} 影响强度", assessment.get('impact_strength', 'N/A'))
    
    with col2:
        st.metric("⏰ 影响周期", assessment.get('impact_duration', 'N/A'))
    
    with col3:
        risk_color = {
            '高': '🔴', '中': '🟡', '低': '🟢'
        }.get(assessment.get('risk_level', '低'), '🟢')
        st.metric(f"{risk_color} 风险等级", assessment.get('risk_level', 'N/A'))
    
    with col4:
        confidence = assessment.get('confidence', 0.5)
        st.metric("🎯 可信度", f"{confidence:.1%}")
    
    st.markdown("---")
    
    # 关键新闻列表
    key_news = news_data.get('key_news', [])
    if key_news:
        st.subheader("📰 关键国际新闻")
        for i, news in enumerate(key_news[:5], 1):  # 最多显示5条
            with st.expander(f"{i}. {news.get('title', '未知标题')}", expanded=i==1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**来源**: {news.get('source', '未知')}")
                    st.markdown(f"**日期**: {news.get('date', '未知')}")
                    st.markdown(f"**类型**: {news.get('type', '未知')}")
                    st.markdown(f"**影响**: {news.get('impact', '未知')}")
                    st.markdown(f"**摘要**: {news.get('summary', '无摘要')}")
                with col2:
                    impact_strength = news.get('impact_strength', '低')
                    strength_emoji = {'高': '🔴', '中': '🟡', '低': '🟢'}.get(impact_strength, '🟢')
                    st.markdown(f"{strength_emoji} **{impact_strength}**")
                    
                    if news.get('covered_by_policy_analyst'):
                        st.markdown("📋 *已覆盖*")
    
    # 整体影响评估
    overall_impact = news_data.get('overall_impact', '中性')
    st.markdown("### 📊 整体影响评估")
    st.markdown(f"**综合评估**: {overall_impact}")

def render_policy_analysis_simple(policy_data):
    """简化的政策分析渲染"""
    
    if not policy_data:
        st.info("🏛️ 暂无政策分析数据")
        return
    
    # 长期政策支持展示
    long_term = policy_data.get('long_term_policies', [])
    if long_term:
        st.subheader("🏛️ 长期政策支持")
        
        # 转换为DataFrame展示
        df_policy = pd.DataFrame(long_term)
        if not df_policy.empty:
            # 重命名列以适应中文展示
            column_mapping = {
                "name": "政策名称",
                "duration": "持续时间",
                "support_strength": "支持力度",
                "beneficiary_sectors": "受益板块",
                "policy_continuity": "政策连续性",
                "impact": "预计影响"
            }
            
            # 只保留存在的列
            available_columns = {k: v for k, v in column_mapping.items() if k in df_policy.columns}
            if available_columns:
                df_policy = df_policy.rename(columns=available_columns)
                st.dataframe(df_policy, use_container_width=True, hide_index=True)
    
    # 整体支持强度
    overall_strength = policy_data.get('overall_support_strength', '中')
    strength_color = {'强': '🟢', '中': '🟡', '弱': '🔴'}.get(overall_strength, '🟡')
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"{strength_color} 整体政策支持强度", overall_strength)
    with col2:
        # 计算长期政策数量
        long_term_count = len(long_term)
        st.metric("📋 长期政策数量", f"{long_term_count} 项")

def render_strategy_details_simple(strategy_data):
    """简化的策略详情渲染"""
    
    if not strategy_data:
        st.info("📋 暂无策略详情数据")
        return
    
    # 最终仓位显示
    final_position = strategy_data.get('final_position', 0.5)
    st.markdown(f"### 🎯 最终建议仓位: {final_position:.1%}")
    
    # 仓位构成详情
    breakdown = strategy_data.get('position_breakdown', {})
    if breakdown:
        st.subheader("📊 仓位构成详情")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            core = breakdown.get('core_holding', 0)
            st.metric("🟦 核心持仓", f"{core:.1%}", help="基于长期政策支持的稳定配置")
        
        with col2:
            tactical = breakdown.get('tactical_allocation', 0)
            st.metric("🟨 战术配置", f"{tactical:.1%}", help="短期机会的灵活配置")
        
        with col3:
            cash = breakdown.get('cash_reserve', 0)
            st.metric("⬜ 现金储备", f"{cash:.1%}", help="风险管理和流动性保障")
        
        # 仓位构成图表（更大版本）
        labels = ['核心持仓 (长期)', '战术配置 (短期)', '现金储备']
        values = [core, tactical, cash]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.3,
            marker_colors=colors,
            textinfo='label+percent',
            textposition='outside'
        )])
        fig.update_layout(
            title="仓位构成分布",
            height=400,
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01)
        )
        st.plotly_chart(fig, use_container_width=True)

def render_decision_summary_simple(decision, stock_symbol=None, strategy_details=None):
    """简化的决策摘要渲染"""
    
    st.subheader("🎯 投资决策摘要")
    
    # 如果没有决策数据，显示占位符
    if not decision:
        st.warning("暂无决策数据")
        return
    
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        action = decision.get('action', 'N/A')
        
        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入', 'SELL': '卖出', 'HOLD': '持有',
            '买入': '买入', '卖出': '卖出', '持有': '持有'
        }
        
        chinese_action = action_translation.get(action.upper(), action)
        st.metric("投资建议", chinese_action)

    with col2:
        confidence = decision.get('confidence', 0)
        if isinstance(confidence, (int, float)):
            confidence_str = f"{confidence:.1%}"
        else:
            confidence_str = str(confidence)
        st.metric("置信度", confidence_str)

    with col3:
        risk_score = decision.get('risk_score', 0)
        if isinstance(risk_score, (int, float)):
            risk_str = f"{risk_score:.1%}"
        else:
            risk_str = str(risk_score)
        st.metric("风险评分", risk_str)

    with col4:
        target_price = decision.get('target_price')
        if target_price is not None and isinstance(target_price, (int, float)) and target_price > 0:
            price_display = f"¥{target_price:.2f}"
        else:
            price_display = "待分析"
        st.metric("目标价位", price_display)
    
    # v2.1.0新增：仓位构成可视化
    if strategy_details and 'position_breakdown' in strategy_details:
        st.markdown("### 📊 建议仓位构成")
        breakdown = strategy_details['position_breakdown']
        
        # 使用Plotly绘制环形图
        labels = ['核心持仓 (长期)', '战术配置 (短期)', '现金储备']
        values = [
            breakdown.get('core_holding', 0),
            breakdown.get('tactical_allocation', 0),
            breakdown.get('cash_reserve', 1)
        ]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.4,
            marker_colors=colors
        )])
        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=200,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 显示最终仓位百分比
        final_position = strategy_details.get('final_position', 0.5)
        st.markdown(f"**🎯 建议总仓位**: {final_position:.1%}")

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
            }
        ],
        'overall_impact': '积极偏向，短期利好科技和出口板块'
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
            }
        ],
        'overall_support_strength': '强'
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
        }
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
        ["v2.1.0新功能测试", "功能演示"]
    )
    
    if test_mode == "v2.1.0新功能测试":
        st.header("🌟 v2.1.0新功能展示")
        
        mock_data = create_mock_v210_data()
        
        # 测试决策摘要
        st.subheader("📊 决策摘要测试")
        render_decision_summary_simple(
            mock_data['decision'], 
            mock_data['stock_symbol'],
            mock_data['strategy_details']
        )
        
        st.markdown("---")
        
        # 测试国际新闻分析
        st.subheader("🌍 国际新闻分析测试")
        render_international_news_simple(mock_data['international_news_analysis'])
        
        st.markdown("---")
        
        # 测试政策分析
        st.subheader("🏛️ 政策分析测试")
        render_policy_analysis_simple(mock_data['policy_analysis'])
        
        st.markdown("---")
        
        # 测试策略详情
        st.subheader("📋 策略详情测试")
        render_strategy_details_simple(mock_data['strategy_details'])
        
    elif test_mode == "功能演示":
        st.header("🎯 v2.1.0功能特性演示")
        
        st.markdown("""
        ## 🌟 v2.1.0新增功能特性
        
        ### 🌍 国际新闻分析
        - **数据源**: Bloomberg、Reuters等国际主流媒体
        - **监测内容**: 货币政策、贸易政策、地缘政治事件
        - **影响评估**: 影响强度、持续时间、风险等级、可信度
        - **智能过滤**: 自动识别与投资相关的关键新闻
        
        ### 🏛️ 政策分析
        - **长期政策**: 持续时间、支持力度、受益板块
        - **政策连续性**: 评估政策的稳定性和可持续性
        - **影响预测**: 对相关产业和市场的预期影响
        - **数据展示**: 结构化表格展示政策信息
        
        ### 📋 策略详情
        - **仓位分配**: 核心持仓(67%) + 战术配置(33%) + 现金储备
        - **可视化**: Plotly饼图展示仓位构成
        - **动态调整**: 基于市场变化的仓位调整机制
        - **触发条件**: 明确的加仓和减仓条件
        
        ### 🔄 向后兼容
        - **版本检测**: 自动识别v2.0.0和v2.1.0数据格式
        - **优雅降级**: v2.0.0数据在新界面中正常显示
        - **默认值**: 为缺失字段提供合理的默认值
        - **无错误**: 完全兼容现有功能
        """)
        
        # 显示技术实现
        st.markdown("---")
        st.subheader("🔧 技术实现亮点")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **前端技术栈**:
            - Streamlit: 快速原型开发
            - Plotly: 数据可视化
            - Pandas: 数据处理
            - CSS: 界面美化
            """)
        
        with col2:
            st.markdown("""
            **架构特性**:
            - 模块化设计
            - 组件复用
            - 错误处理
            - 响应式布局
            """)
    
    # 技术信息
    st.markdown("---")
    with st.expander("🔧 开发信息", expanded=False):
        st.markdown("""
        **开发完成内容**:
        - ✅ 分析v2.1.0后端新增功能和数据结构
        - ✅ 修改web/utils/analysis_runner.py添加v2.1.0数据解析
        - ✅ 修改web/components/results_display.py支持新数据展示
        - ✅ 实现国际新闻分析组件渲染
        - ✅ 实现策略详情可视化组件
        - ✅ 实现长期政策分析组件
        - ✅ 添加向后兼容性支持
        - ✅ 测试v2.1.0新功能展示
        
        **文件修改清单**:
        - `web/utils/analysis_runner.py`: 数据解析层增强
        - `web/components/results_display.py`: UI组件扩展
        - `test_v210_simple.py`: 功能测试脚本
        """)

if __name__ == "__main__":
    main()