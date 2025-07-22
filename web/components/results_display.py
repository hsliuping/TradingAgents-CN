"""
Analysis result display component
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# Import export functionality
from utils.report_exporter import render_export_buttons

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

def render_results(results):
    """Render analysis results"""

    if not results:
        st.warning("No analysis results available")
        return

    # Add CSS to ensure result content is not obscured by the right side
    st.markdown("""
    <style>
    /* Ensure analysis result content has enough right margin */
    .element-container, .stMarkdown, .stExpander {
        margin-right: 1.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* Special handling for expandable components */
    .streamlit-expanderHeader {
        margin-right: 1rem !important;
    }

    /* Ensure text content is not truncated */
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
    st.header(f"📊 {stock_symbol} Analysis Results")

    # If it's demo data, show a hint
    if is_demo:
        st.info("🎭 **Demo Mode**: The current display is simulated analysis data for interface demonstration. To obtain real analysis results, please configure the correct API key.")
        if results.get('demo_reason'):
            with st.expander("View details"):
                st.text(results['demo_reason'])

    # Investment decision summary
    render_decision_summary(decision, stock_symbol)

    # Analysis configuration information
    render_analysis_info(results)

    # Detailed analysis report
    render_detailed_analysis(state)

    # Risk warning
    render_risk_warning(is_demo)
    
    # Export report functionality
    render_export_buttons(results)

def render_analysis_info(results):
    """Render analysis configuration information"""

    with st.expander("📋 Analysis Configuration Information", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            llm_provider = results.get('llm_provider', 'dashscope')
            provider_name = {
                'dashscope': 'Ali Baiyan',
                'google': 'Google AI'
            }.get(llm_provider, llm_provider)

            st.metric(
                label="LLM Provider",
                value=provider_name,
                help="AI model provider used"
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
                label="AI Model",
                value=model_display,
                help="Specific AI model used"
            )

        with col3:
            analysts = results.get('analysts', [])
            logger.debug(f"🔍 [DEBUG] analysts from results: {analysts}")
            analysts_count = len(analysts) if analysts else 0

            st.metric(
                label="Number of Analysts",
                value=f"{analysts_count} analysts",
                help="Number of AI analysts involved in analysis"
            )

        # Display analyst list
        if analysts:
            st.write("**Analysts Involved:**")
            analyst_names = {
                'market': '📈 Market Technical Analyst',
                'fundamentals': '💰 Fundamental Analyst',
                'news': '📰 News Analyst',
                'social_media': '💭 Social Media Analyst',
                'risk': '⚠️ Risk Assessor'
            }

            analyst_list = [analyst_names.get(analyst, analyst) for analyst in analysts]
            st.write(" • ".join(analyst_list))

def render_decision_summary(decision, stock_symbol=None):
    """Render investment decision summary"""

    st.subheader("🎯 Investment Decision Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        action = decision.get('action', 'N/A')

        # Translate English investment suggestions to Chinese
        action_translation = {
            'BUY': 'Buy',
            'SELL': 'Sell',
            'HOLD': 'Hold',
            '买入': 'Buy',
            '卖出': 'Sell',
            '持有': 'Hold'
        }

        # Get Chinese investment suggestion
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
            label="Investment Decision",
            value=chinese_action,
            help="Investment suggestion based on AI analysis"
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
            label="Confidence",
            value=confidence_str,
            delta=confidence_delta,
            help="AI's confidence in the analysis result"
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
            label="Risk Score",
            value=risk_str,
            delta=risk_delta,
            delta_color="inverse",
            help="Investment risk assessment score"
        )

    with col4:
        target_price = decision.get('target_price')
        logger.debug(f"🔍 [DEBUG] target_price from decision: {target_price}, type: {type(target_price)}")
        logger.debug(f"🔍 [DEBUG] decision keys: {list(decision.keys()) if isinstance(decision, dict) else 'Not a dict'}")

        # Determine currency symbol based on stock code
        def is_china_stock(ticker_code):
            import re

            return re.match(r'^\d{6}$', str(ticker_code)) if ticker_code else False

        is_china = is_china_stock(stock_symbol)
        currency_symbol = "¥" if is_china else "$"

        # Handle target price display
        if target_price is not None and isinstance(target_price, (int, float)) and target_price > 0:
            price_display = f"{currency_symbol}{target_price:.2f}"
            help_text = "AI predicted target price"
        else:
            price_display = "To be analyzed"
            help_text = "Target price requires more detailed analysis to determine"

        st.metric(
            label="Target Price",
            value=price_display,
            help=help_text
        )
    
    # Analysis reasoning
    if 'reasoning' in decision and decision['reasoning']:
        with st.expander("🧠 AI Analysis Reasoning", expanded=True):
            st.markdown(decision['reasoning'])

def render_detailed_analysis(state):
    """Render detailed analysis report"""
    
    st.subheader("📋 Detailed Analysis Report")
    
    # Define analysis modules
    analysis_modules = [
        {
            'key': 'market_report',
            'title': '📈 Market Technical Analysis',
            'icon': '📈',
            'description': 'Technical indicators, price trends, support and resistance analysis'
        },
        {
            'key': 'fundamentals_report', 
            'title': '💰 Fundamental Analysis',
            'icon': '💰',
            'description': 'Financial data, valuation levels, profitability analysis'
        },
        {
            'key': 'sentiment_report',
            'title': '💭 Market Sentiment Analysis', 
            'icon': '💭',
            'description': 'Investor sentiment, social media sentiment indicators'
        },
        {
            'key': 'news_report',
            'title': '📰 News Event Analysis',
            'icon': '📰', 
            'description': 'Related news events, market dynamic impact analysis'
        },
        {
            'key': 'risk_assessment',
            'title': '⚠️ Risk Assessment',
            'icon': '⚠️',
            'description': 'Risk factor identification, risk level assessment'
        },
        {
            'key': 'investment_plan',
            'title': '📋 Investment Suggestion',
            'icon': '📋',
            'description': 'Specific investment strategy, position management advice'
        }
    ]
    
    # Create tabs
    tabs = st.tabs([f"{module['icon']} {module['title']}" for module in analysis_modules])
    
    for i, (tab, module) in enumerate(zip(tabs, analysis_modules)):
        with tab:
            if module['key'] in state and state[module['key']]:
                st.markdown(f"*{module['description']}*")
                
                # Format content for display
                content = state[module['key']]
                if isinstance(content, str):
                    st.markdown(content)
                elif isinstance(content, dict):
                    # If it's a dictionary, format for display
                    for key, value in content.items():
                        st.subheader(key.replace('_', ' ').title())
                        st.write(value)
                else:
                    st.write(content)
            else:
                st.info(f"No {module['title']} data available")

def render_risk_warning(is_demo=False):
    """Render risk warning"""

    st.markdown("---")
    st.subheader("⚠️ Important Risk Warning")

    # Use Streamlit's native components instead of HTML
    if is_demo:
        st.warning("**Demo Data**: The current display is simulated data, only for interface demonstration.")
        st.info("**Real Analysis**: To obtain real analysis results, please configure the correct API key.")

    st.error("""
    **Investment Risk Warning**:
    - **For Reference Only**: This analysis result is for reference only and does not constitute investment advice.
    - **Investment Risk**: Stock investment carries risks, which may result in principal loss.
    - **Rational Decision**: Please make a rational investment decision based on multiple information sources.
    - **Professional Consultation**: Major investment decision suggestions should be consulted with professional financial advisors.
    - **Self-Assumed Risk**: Investment decisions and their consequences are borne by investors themselves.
    """)

    # Add timestamp
    st.caption(f"Analysis generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def create_price_chart(price_data):
    """Create price trend chart"""
    
    if not price_data:
        return None
    
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=price_data['date'],
        y=price_data['price'],
        mode='lines',
        name='Stock Price',
        line=dict(color='#1f77b4', width=2)
    ))
    
    # Set chart style
    fig.update_layout(
        title="Stock Price Trend Chart",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        hovermode='x unified',
        showlegend=True
    )
    
    return fig

def create_sentiment_gauge(sentiment_score):
    """Create sentiment indicator gauge"""
    
    if sentiment_score is None:
        return None
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = sentiment_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Market Sentiment Index"},
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
