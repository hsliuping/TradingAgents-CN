"""
分析表单组件
"""

import streamlit as st
import datetime

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')


def render_analysis_form():
    """渲染股票分析表单"""

    st.subheader("📋 分析配置")
    
    # 初始化 session_state，记录当前市场和代码是否已被用户修改过
    if "stock_symbol" not in st.session_state:
        st.session_state.stock_symbol = ""

    if "user_typed_stock_symbol" not in st.session_state:
        st.session_state.user_typed_stock_symbol = False

    # 创建两列布局
    col1, col2 = st.columns(2)
    
    with col1:
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
        
        research_depth = st.slider(
            "研究深度 🔍",
            min_value=1,
            max_value=5,
            value=st.session_state.research_depth,
            help="1=快速分析, 5=深度研究",
            key="research_depth"
        )
        
        # 分析师选择
        if "market_analyst" not in st.session_state:
            st.session_state.market_analyst = True
        if "social_analyst" not in st.session_state:
            st.session_state.social_analyst = True
        if "news_analyst" not in st.session_state:
            st.session_state.news_analyst = True
        
        market_analyst = st.checkbox(
            "📊 市场分析师",
            help="分析技术指标、价格趋势、市场结构",
            key="market_analyst"
        )
        
        social_analyst = st.checkbox(
            "💬 社交媒体分析师",
            help="分析社交媒体情绪、投资者讨论热度",
            key="social_analyst"
        )
        
        news_analyst = st.checkbox(
            "📰 新闻分析师",
            help="分析新闻事件、公告、市场反应",
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
    
    # 初始化高级选项
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
            "自定义提示词",
            help="添加特定的分析要求或关注点",
            key="custom_prompt"
        )
    
    # 提交按钮
    submitted = st.button("🚀 开始分析", type="primary", use_container_width=True)
    
    # 处理表单提交
    if submitted and stock_symbol:
        logger.debug(f"🔍 [FORM DEBUG] ===== 表单提交开始 =====")
        logger.debug(f"🔍 [FORM DEBUG] 股票代码: {stock_symbol}")
        logger.debug(f"🔍 [FORM DEBUG] 市场类型: {market_type}")
        logger.debug(f"🔍 [FORM DEBUG] 研究深度: {research_depth}")
        logger.debug(f"🔍 [FORM DEBUG] 选中的分析师: {selected_analysts}")
        
        # 构建表单数据
        form_data = {
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

        # 保存表单配置到缓存和持久化存储
        form_config = {
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'research_depth': research_depth,
            'selected_analysts': [a[0] for a in selected_analysts],
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }
        st.session_state.form_config = form_config

        # 保存到持久化存储
        try:
            from utils.smart_session_manager import smart_session_manager
            # 获取当前分析ID（如果有的话）
            current_analysis_id = st.session_state.get('current_analysis_id', 'form_config_only')
            smart_session_manager.save_analysis_state(
                analysis_id=current_analysis_id,
                status=st.session_state.get('analysis_running', False) and 'running' or 'idle',
                stock_symbol=stock_symbol,
                market_type=market_type,
                form_config=form_config
            )
        except Exception as e:
            logger.warning(f"⚠️ [配置持久化] 保存失败: {e}")

        logger.info(f"📊 [配置缓存] 表单配置已保存: {form_config}")

        logger.debug(f"🔍 [FORM DEBUG] 返回的表单数据: {form_data}")
        logger.debug(f"🔍 [FORM DEBUG] ===== 表单提交结束 =====")

        return form_data
    elif submitted and not stock_symbol:
        # 用户点击了提交但没有输入股票代码
        logger.error(f"🔍 [FORM DEBUG] 提交失败：股票代码为空")
        st.error("❌ 请输入股票代码后再提交")
        return {'submitted': False}
    else:
        return {'submitted': False}

