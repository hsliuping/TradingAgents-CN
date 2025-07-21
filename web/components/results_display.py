"""
分析结果显示组件
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# 导入导出功能
from utils.report_exporter import render_export_buttons

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

def render_results(results):
    """渲染分析结果"""

    if not results:
        st.warning("暂无分析结果")
        return

    # 添加CSS确保结果内容不被右侧遮挡
    st.markdown("""
    <style>
    /* 确保分析结果内容有足够的右边距 */
    .element-container, .stMarkdown, .stExpander {
        margin-right: 1.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* 特别处理展开组件 */
    .streamlit-expanderHeader {
        margin-right: 1rem !important;
    }

    /* 确保文本内容不被截断 */
    .stMarkdown p, .stMarkdown div {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    </style>
    """, unsafe_allow_html=True)

    stock_symbol = results.get('stock_symbol', 'N/A')
    decision = results.get('decision', {})
    state = results.get('state', {})
    is_demo = results.get('is_demo', False)

    st.markdown("---")
    st.header(f"📊 {stock_symbol} 分析结果")

    # 如果是演示数据，显示提示
    if is_demo:
        st.info("🎭 **演示模式**: 当前显示的是模拟分析数据，用于界面演示。要获取真实分析结果，请配置正确的API密钥。")
        if results.get('demo_reason'):
            with st.expander("查看详细信息"):
                st.text(results['demo_reason'])

    # 投资决策摘要
    render_decision_summary(decision, stock_symbol)

    # 分析配置信息
    render_analysis_info(results)

    # 详细分析报告
    render_detailed_analysis(state)

    # 风险提示
    render_risk_warning(is_demo)
    
    # 导出报告功能
    render_export_buttons(results)

def render_analysis_info(results):
    """渲染分析配置信息"""

    with st.expander("📋 分析配置信息", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            llm_provider = results.get('llm_provider', 'dashscope')
            provider_name = {
                'dashscope': '阿里百炼',
                'google': 'Google AI'
            }.get(llm_provider, llm_provider)

            st.metric(
                label="LLM提供商",
                value=provider_name,
                help="使用的AI模型提供商"
            )

        with col2:
            llm_model = results.get('llm_model', 'N/A')
            logger.debug(f"🔍 [DEBUG] llm_model from results: {llm_model}")
            model_display = {
                'qwen-turbo': 'Qwen Turbo',
                'qwen-plus': 'Qwen Plus',
                'qwen-max': 'Qwen Max',
                'gemini-2.0-flash': 'Gemini 2.0 Flash',
                'gemini-1.5-pro': 'Gemini 1.5 Pro',
                'gemini-1.5-flash': 'Gemini 1.5 Flash'
            }.get(llm_model, llm_model)

            st.metric(
                label="AI模型",
                value=model_display,
                help="使用的具体AI模型"
            )

        with col3:
            analysts = results.get('analysts', [])
            logger.debug(f"🔍 [DEBUG] analysts from results: {analysts}")
            analysts_count = len(analysts) if analysts else 0

            st.metric(
                label="分析师数量",
                value=f"{analysts_count}个",
                help="参与分析的AI分析师数量"
            )

        # 显示分析师列表
        if analysts:
            st.write("**参与的分析师:**")
            analyst_names = {
                'market': '📈 市场技术分析师',
                'fundamentals': '💰 基本面分析师',
                'news': '📰 新闻分析师',
                'social_media': '💭 社交媒体分析师',
                'risk': '⚠️ 风险评估师'
            }

            analyst_list = [analyst_names.get(analyst, analyst) for analyst in analysts]
            st.write(" • ".join(analyst_list))

def render_decision_summary(decision, stock_symbol=None):
    """渲染投资决策摘要"""

    st.subheader("🎯 投资决策摘要")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        action = decision.get('action', 'N/A')

        # 将英文投资建议转换为中文
        action_translation = {
            'BUY': '买入',
            'SELL': '卖出',
            'HOLD': '持有',
            '买入': '买入',
            '卖出': '卖出',
            '持有': '持有'
        }

        # 获取中文投资建议
        chinese_action = action_translation.get(action.upper(), action)

        action_color = {
            'BUY': 'normal',
            'SELL': 'inverse',
            'HOLD': 'off',
            '买入': 'normal',
            '卖出': 'inverse',
            '持有': 'off'
        }.get(action.upper(), 'normal')

        st.metric(
            label="投资建议",
            value=chinese_action,
            help="基于AI分析的投资建议"
        )

    with col2:
        confidence = decision.get('confidence', 0)
        if isinstance(confidence, (int, float)):
            confidence_str = f"{confidence:.1%}"
            confidence_delta = f"{confidence-0.5:.1%}" if confidence != 0 else None
        else:
            confidence_str = str(confidence)
            confidence_delta = None

        st.metric(
            label="置信度",
            value=confidence_str,
            delta=confidence_delta,
            help="AI对分析结果的置信度"
        )

    with col3:
        risk_score = decision.get('risk_score', 0)
        if isinstance(risk_score, (int, float)):
            risk_str = f"{risk_score:.1%}"
            risk_delta = f"{risk_score-0.3:.1%}" if risk_score != 0 else None
        else:
            risk_str = str(risk_score)
            risk_delta = None

        st.metric(
            label="风险评分",
            value=risk_str,
            delta=risk_delta,
            delta_color="inverse",
            help="投资风险评估分数"
        )

    with col4:
        target_price = decision.get('target_price')
        logger.debug(f"🔍 [DEBUG] target_price from decision: {target_price}, type: {type(target_price)}")
        logger.debug(f"🔍 [DEBUG] decision keys: {list(decision.keys()) if isinstance(decision, dict) else 'Not a dict'}")

        # 根据股票代码确定货币符号
        def is_china_stock(ticker_code):
            import re

            return re.match(r'^\d{6}$', str(ticker_code)) if ticker_code else False

        is_china = is_china_stock(stock_symbol)
        currency_symbol = "¥" if is_china else "$"

        # 处理目标价格显示
        if target_price is not None and isinstance(target_price, (int, float)) and target_price > 0:
            price_display = f"{currency_symbol}{target_price:.2f}"
            help_text = "AI预测的目标价位"
        else:
            price_display = "待分析"
            help_text = "目标价位需要更详细的分析才能确定"

        st.metric(
            label="目标价位",
            value=price_display,
            help=help_text
        )
    
    # 分析推理
    if 'reasoning' in decision and decision['reasoning']:
        with st.expander("🧠 AI分析推理", expanded=True):
            st.markdown(decision['reasoning'])

def render_detailed_analysis(state):
    """渲染详细分析报告"""
    
    st.subheader("📋 详细分析报告")
    
    # 定义分析模块
    analysis_modules = [
        {
            'key': 'market_report',
            'title': '📈 市场技术分析',
            'icon': '📈',
            'description': '技术指标、价格趋势、支撑阻力位分析'
        },
        {
            'key': 'fundamentals_report', 
            'title': '💰 基本面分析',
            'icon': '💰',
            'description': '财务数据、估值水平、盈利能力分析'
        },
        {
            'key': 'sentiment_report',
            'title': '💭 市场情绪分析', 
            'icon': '💭',
            'description': '投资者情绪、社交媒体情绪指标'
        },
        {
            'key': 'news_report',
            'title': '📰 新闻事件分析',
            'icon': '📰', 
            'description': '相关新闻事件、市场动态影响分析'
        },
        {
            'key': 'risk_assessment',
            'title': '⚠️ 风险评估',
            'icon': '⚠️',
            'description': '风险因素识别、风险等级评估'
        },
        {
            'key': 'investment_plan',
            'title': '📋 投资建议',
            'icon': '📋',
            'description': '具体投资策略、仓位管理建议'
        }
    ]
    
    # 创建标签页
    tabs = st.tabs([f"{module['icon']} {module['title']}" for module in analysis_modules])
    
    for i, (tab, module) in enumerate(zip(tabs, analysis_modules)):
        with tab:
            if module['key'] in state and state[module['key']]:
                st.markdown(f"*{module['description']}*")
                
                # 格式化显示内容
                content = state[module['key']]
                if isinstance(content, str):
                    st.markdown(content)
                elif isinstance(content, dict):
                    # 如果是字典，格式化显示
                    for key, value in content.items():
                        st.subheader(key.replace('_', ' ').title())
                        st.write(value)
                else:
                    st.write(content)
            else:
                st.info(f"暂无{module['title']}数据")

def render_risk_warning(is_demo=False):
    """渲染风险提示"""

    st.markdown("---")
    st.subheader("⚠️ 重要风险提示")

    # 使用Streamlit的原生组件而不是HTML
    if is_demo:
        st.warning("**演示数据**: 当前显示的是模拟数据，仅用于界面演示")
        st.info("**真实分析**: 要获取真实分析结果，请配置正确的API密钥")

    st.error("""
    **投资风险提示**:
    - **仅供参考**: 本分析结果仅供参考，不构成投资建议
    - **投资风险**: 股票投资有风险，可能导致本金损失
    - **理性决策**: 请结合多方信息进行理性投资决策
    - **专业咨询**: 重大投资决策建议咨询专业财务顾问
    - **自担风险**: 投资决策及其后果由投资者自行承担
    """)

    # 添加时间戳
    st.caption(f"分析生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def create_price_chart(price_data):
    """创建价格走势图"""
    
    if not price_data:
        return None
    
    fig = go.Figure()
    
    # 添加价格线
    fig.add_trace(go.Scatter(
        x=price_data['date'],
        y=price_data['price'],
        mode='lines',
        name='股价',
        line=dict(color='#1f77b4', width=2)
    ))
    
    # 设置图表样式
    fig.update_layout(
        title="股价走势图",
        xaxis_title="日期",
        yaxis_title="价格 ($)",
        hovermode='x unified',
        showlegend=True
    )
    
    return fig

def create_sentiment_gauge(sentiment_score):
    """创建情绪指标仪表盘"""
    
    if sentiment_score is None:
        return None
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = sentiment_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "市场情绪指数"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 25], 'color': "lightgray"},
                {'range': [25, 50], 'color': "gray"},
                {'range': [50, 75], 'color': "lightgreen"},
                {'range': [75, 100], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    return fig
