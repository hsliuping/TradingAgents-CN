"""
分析表单组件
"""

import streamlit as st
import datetime

def render_analysis_form():
    """渲染股票分析表单"""
    
    st.subheader("📋 分析配置")

    # 移除st.form，改为实时组件
    col1, col2 = st.columns(2)
    
    with col1:
        # 初始化session_state
        if "market_type" not in st.session_state:
            st.session_state.market_type = "A股"
        if "analysis_date" not in st.session_state:
            st.session_state.analysis_date = datetime.date.today()
        
        # 初始化 session_state，记录当前市场和代码是否已被用户修改过
        if "stock_symbol" not in st.session_state:
            st.session_state.stock_symbol = ""

        if "user_typed_stock_symbol" not in st.session_state:
            st.session_state.user_typed_stock_symbol = False

        # 市场选择
        market_type = st.selectbox(
            "选择市场 🌍",
            options=["美股", "A股"],
            help="选择要分析的股票市场",
            key="market_type"
        )

        # 设置 placeholder 和默认推荐（但不作为真正的输入值）
        if market_type == "美股":
            placeholder = "输入美股代码，如 AAPL, TSLA, MSFT"
            suggested_symbol = "AAPL"
        else:
            placeholder = "输入A股代码，如 000001, 600519"
            suggested_symbol = "000001"

        # 处理股票代码输入
        def handle_input_change():
            st.session_state.user_typed_stock_symbol = True

        stock_symbol = st.text_input(
            "股票代码 📈",
            value=(
                st.session_state.stock_symbol
                if st.session_state.user_typed_stock_symbol
                else ""
            ),
            placeholder=placeholder,
            help="请输入股票代码进行分析",
            key="stock_symbol_input",
            on_change=handle_input_change
        )

        # 去除空格 & 处理大小写
        stock_symbol = stock_symbol.strip().upper()

        # 如果用户没有输入过，我们就不记录 symbol
        if stock_symbol:
            st.session_state.stock_symbol = stock_symbol

        
        # 分析日期
        analysis_date = st.date_input(
            "分析日期 📅",
            help="选择分析的基准日期",
            key="analysis_date"
        )
    
    with col2:
        # 研究深度
        if "research_depth" not in st.session_state:
            st.session_state.research_depth = 3
        
        research_depth = st.select_slider(
            "研究深度 🔍",
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: {
                1: "1级 - 快速分析",
                2: "2级 - 基础分析",
                3: "3级 - 标准分析",
                4: "4级 - 深度分析",
                5: "5级 - 全面分析"
            }[x],
            help="选择分析的深度级别，级别越高分析越详细但耗时更长",
            key="research_depth"
        )
    
    # 分析师团队选择
    st.markdown("### 👥 选择分析师团队")
    
    col1, col2 = st.columns(2)

    if "market_analyst" not in st.session_state:
        st.session_state.market_analyst = True
    if "social_analyst" not in st.session_state:
        st.session_state.social_analyst = False
    if "news_analyst" not in st.session_state:
        st.session_state.news_analyst = False
    if "fundamentals_analyst" not in st.session_state:
        st.session_state.fundamentals_analyst = True

    with col1:
        market_analyst = st.checkbox(
            "📈 市场分析师",
            help="专注于技术面分析、价格趋势、技术指标",
            key="market_analyst"
        )
        
        social_analyst = st.checkbox(
            "💭 社交媒体分析师",
            help="分析社交媒体情绪、投资者情绪指标",
            key="social_analyst"
        )
    
    with col2:
        news_analyst = st.checkbox(
            "📰 新闻分析师",
            help="分析相关新闻事件、市场动态影响",
            key="news_analyst"
        )
        
        fundamentals_analyst = st.checkbox(
            "💰 基本面分析师",
            help="分析财务数据、公司基本面、估值水平",
            key="fundamentals_analyst"
        )
    
    # 收集选中的分析师
    selected_analysts = []
    if st.session_state.market_analyst:
        selected_analysts.append(("market", "市场分析师"))
    if st.session_state.social_analyst:
        selected_analysts.append(("social", "社交媒体分析师"))
    if st.session_state.news_analyst:
        selected_analysts.append(("news", "新闻分析师"))
    if st.session_state.fundamentals_analyst:
        selected_analysts.append(("fundamentals", "基本面分析师"))
    
    # 显示选择摘要
    if selected_analysts:
        st.success(f"已选择 {len(selected_analysts)} 个分析师: {', '.join([a[1] for a in selected_analysts])}")
    else:
        st.warning("请至少选择一个分析师")
    
    if "include_sentiment" not in st.session_state:
        st.session_state.include_sentiment = True
    if "include_risk_assessment" not in st.session_state:
        st.session_state.include_risk_assessment = True
    if "custom_prompt" not in st.session_state:
        st.session_state.custom_prompt = ""

    # 高级选项
    with st.expander("🔧 高级选项"):
        include_sentiment = st.checkbox(
            "包含情绪分析",
            help="是否包含市场情绪和投资者情绪分析",
            key="include_sentiment"
        )
        
        include_risk_assessment = st.checkbox(
            "包含风险评估",
            help="是否包含详细的风险因素评估",
            key="include_risk_assessment"
        )
        
        custom_prompt = st.text_area(
            "自定义分析要求",
            placeholder="输入特定的分析要求或关注点...",
            help="可以输入特定的分析要求，AI会在分析中重点关注",
            key="custom_prompt"
        )

    # 替代原来的submit按钮
    submitted = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True
    )

    # 返回数据
    if submitted:
        return {
            'submitted': True,
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'analysis_date': str(analysis_date),
            'analysts': [a[0] for a in selected_analysts],
            'research_depth': research_depth,
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }
    else:
        return {'submitted': False}

