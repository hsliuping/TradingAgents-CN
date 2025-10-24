"""
Analysis form component.
"""

import streamlit as st
import datetime

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger

# 导入用户活动记录器
try:
    from ..utils.user_activity_logger import user_activity_logger
except ImportError:
    user_activity_logger = None

logger = get_logger('web')


def render_analysis_form():
    """Render the stock analysis form."""

    st.subheader("📋 Analysis Configuration")

    # 获取缓存的表单配置（确保不为None）
    cached_config = st.session_state.get('form_config') or {}

    # 调试信息（只在没有分析运行时记录，避免重复）
    if not st.session_state.get('analysis_running', False):
        if cached_config:
            logger.debug(f"📊 [配置恢复] 使用缓存配置: {cached_config}")
        else:
            logger.debug("📊 [配置恢复] 使用默认配置")

    # 创建表单
    with st.form("analysis_form", clear_on_submit=False):

        # Save the current configuration for change detection
        initial_config = cached_config.copy() if cached_config else {}
        col1, col2 = st.columns(2)
        
        with col1:
            # Market selection (uses cached values when available)
            market_options = ["美股", "A股", "港股"]
            cached_market = cached_config.get('market_type', 'A股') if cached_config else 'A股'
            try:
                market_index = market_options.index(cached_market)
            except (ValueError, TypeError):
                market_index = 1  # 默认A股

            market_type = st.selectbox(
                "Select Market 🌍",
                options=market_options,
                index=market_index,
                format_func=lambda x: {
                    "美股": "U.S. Market",
                    "A股": "Mainland China A-shares",
                    "港股": "Hong Kong Market"
                }[x],
                help="Choose the stock market you want to analyze"
            )

            # Display different input hints based on the market
            cached_stock = cached_config.get('stock_symbol', '') if cached_config else ''

            if market_type == "美股":
                stock_symbol = st.text_input(
                    "Ticker Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '美股') else '',
                    placeholder="Enter a U.S. ticker, e.g. AAPL, TSLA, MSFT, then press Enter",
                    help="Provide the U.S. stock ticker you want to analyze and press Enter when finished",
                    key="us_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] U.S. market text_input returned: '{stock_symbol}'")

            elif market_type == "港股":
                stock_symbol = st.text_input(
                    "Ticker Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '港股') else '',
                    placeholder="Enter a Hong Kong ticker, e.g. 0700.HK, 9988.HK, 3690.HK, then press Enter",
                    help="Provide the Hong Kong ticker (e.g. 0700.HK for Tencent) and press Enter when finished",
                    key="hk_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] Hong Kong text_input returned: '{stock_symbol}'")

            else:  # A股
                stock_symbol = st.text_input(
                    "Ticker Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'A股') else '',
                    placeholder="Enter an A-share code, e.g. 000001, 600519, then press Enter",
                    help="Provide the Mainland China ticker (e.g. 000001 for Ping An Bank) and press Enter when finished",
                    key="cn_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).strip()

                logger.debug(f"🔍 [FORM DEBUG] A-share text_input returned: '{stock_symbol}'")
            
            # 分析日期
            analysis_date = st.date_input(
                "Analysis Date 📅",
                value=datetime.date.today(),
                help="Choose the reference date for the analysis"
            )

        with col2:
            # 研究深度（使用缓存的值）
            cached_depth = cached_config.get('research_depth', 3) if cached_config else 3
            research_depth = st.select_slider(
                "Research Depth 🔍",
                options=[1, 2, 3, 4, 5],
                value=cached_depth,
                format_func=lambda x: {
                    1: "Level 1 - Quick overview",
                    2: "Level 2 - Foundational",
                    3: "Level 3 - Standard",
                    4: "Level 4 - In-depth",
                    5: "Level 5 - Comprehensive"
                }[x],
                help="Select how deep the analysis should go. Higher levels are more detailed but take longer"
            )

        # Analyst team selection
        st.markdown("### 👥 Choose Analyst Team")

        col1, col2 = st.columns(2)

        # 获取缓存的分析师选择和市场类型
        cached_analysts = cached_config.get('selected_analysts', ['market', 'fundamentals']) if cached_config else ['market', 'fundamentals']
        cached_market_type = cached_config.get('market_type', 'A股') if cached_config else 'A股'

        # Detect whether the market type changed
        market_type_changed = cached_market_type != market_type

        # 如果市场类型发生变化，需要调整分析师选择
        if market_type_changed:
            if market_type == "A股":
                # Switching to A-shares: remove the social media analyst
                cached_analysts = [analyst for analyst in cached_analysts if analyst != 'social']
                if len(cached_analysts) == 0:
                    cached_analysts = ['market', 'fundamentals']  # 确保至少有默认选择
            else:
                # Switching away from A-shares: add the social media analyst when helpful
                if 'social' not in cached_analysts and len(cached_analysts) <= 2:
                    cached_analysts.append('social')

        with col1:
            market_analyst = st.checkbox(
                "📈 Market Analyst",
                value='market' in cached_analysts,
                help="Focuses on technical signals, price trends, and indicators"
            )

            # Always show the social analyst checkbox, but disable it for A-shares
            if market_type == "A股":
                # A-shares: display but disable the social media analyst
                social_analyst = st.checkbox(
                    "💭 Social Media Analyst",
                    value=False,
                    disabled=True,
                    help="Social sentiment data is not available for A-share markets"
                )
                st.info("💡 Social media analysis is unavailable for A-share markets due to data source limits")
            else:
                # 非A股市场：正常显示社交媒体分析师
                social_analyst = st.checkbox(
                    "💭 Social Media Analyst",
                    value='social' in cached_analysts,
                    help="Analyzes social media sentiment and investor mood indicators"
                )

        with col2:
            news_analyst = st.checkbox(
                "📰 News Analyst",
                value='news' in cached_analysts,
                help="Evaluates relevant news events and market narratives"
            )

            fundamentals_analyst = st.checkbox(
                "💰 Fundamentals Analyst",
                value='fundamentals' in cached_analysts,
                help="Reviews financial statements, business fundamentals, and valuation"
            )

        # Collect selected analysts
        selected_analysts = []
        if market_analyst:
            selected_analysts.append(("market", "Market Analyst"))
        if social_analyst:
            selected_analysts.append(("social", "Social Media Analyst"))
        if news_analyst:
            selected_analysts.append(("news", "News Analyst"))
        if fundamentals_analyst:
            selected_analysts.append(("fundamentals", "Fundamentals Analyst"))

        # Display selection summary
        if selected_analysts:
            st.success(f"Selected {len(selected_analysts)} analysts: {', '.join([a[1] for a in selected_analysts])}")
        else:
            st.warning("Please choose at least one analyst")
        
        # 高级选项
        with st.expander("🔧 Advanced Options"):
            include_sentiment = st.checkbox(
                "Include sentiment analysis",
                value=True,
                help="Toggle market and investor sentiment insights"
            )

            include_risk_assessment = st.checkbox(
                "Include risk assessment",
                value=True,
                help="Add a detailed breakdown of risk factors"
            )

            custom_prompt = st.text_area(
                "Custom analysis instructions",
                placeholder="Add any special requirements or focus areas...",
                help="Share specific points you want the AI to emphasize"
            )

        # Display hints about the input state
        if not stock_symbol:
            st.info("💡 Enter a ticker above and press Enter to confirm")
        else:
            st.success(f"✅ Ticker captured: {stock_symbol}")

        # 添加JavaScript来改善用户体验
        st.markdown("""
        <script>
        // 监听输入框的变化，提供更好的用户反馈
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input[type="text"]');
            inputs.forEach(input => {
                input.addEventListener('input', function() {
                    if (this.value.trim()) {
                        this.style.borderColor = '#00ff00';
                        this.title = '按回车键确认输入';
                    } else {
                        this.style.borderColor = '';
                        this.title = '';
                    }
                });
            });
        });
        </script>
        """, unsafe_allow_html=True)

        # Track configuration changes before the submit button
        current_config = {
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'research_depth': research_depth,
            'selected_analysts': [a[0] for a in selected_analysts],
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }

        # 如果配置发生变化，立即保存（即使没有提交）
        if current_config != initial_config:
            st.session_state.form_config = current_config
            try:
                from utils.smart_session_manager import smart_session_manager
                current_analysis_id = st.session_state.get('current_analysis_id', 'form_config_only')
                smart_session_manager.save_analysis_state(
                    analysis_id=current_analysis_id,
                    status=st.session_state.get('analysis_running', False) and 'running' or 'idle',
                    stock_symbol=stock_symbol,
                    market_type=market_type,
                    form_config=current_config
                )
                logger.debug(f"📊 [配置自动保存] 表单配置已更新")
            except Exception as e:
                logger.warning(f"⚠️ [配置自动保存] 保存失败: {e}")

        # Submit button (kept enabled so users can retry)
        submitted = st.form_submit_button(
            "🚀 Start analysis",
            type="primary",
            use_container_width=True
        )

    # 只有在提交时才返回数据
    if submitted and stock_symbol:  # 确保有股票代码才提交
        # 添加详细日志
        logger.debug("🔍 [FORM DEBUG] ===== Analysis form submitted =====")
        logger.debug(f"🔍 [FORM DEBUG] Stock symbol: '{stock_symbol}'")
        logger.debug(f"🔍 [FORM DEBUG] Market type: '{market_type}'")
        logger.debug(f"🔍 [FORM DEBUG] Analysis date: '{analysis_date}'")
        logger.debug(f"🔍 [FORM DEBUG] Analyst choices: {[a[0] for a in selected_analysts]}")
        logger.debug(f"🔍 [FORM DEBUG] Research depth: {research_depth}")

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

        # 记录用户分析请求活动
        if user_activity_logger:
            try:
                user_activity_logger.log_analysis_request(
                    symbol=stock_symbol,
                    market=market_type,
                    analysis_date=str(analysis_date),
                    research_depth=research_depth,
                    analyst_team=[a[0] for a in selected_analysts],
                    details={
                        'include_sentiment': include_sentiment,
                        'include_risk_assessment': include_risk_assessment,
                        'has_custom_prompt': bool(custom_prompt),
                        'form_source': 'analysis_form'
                    }
                )
                logger.debug(f"📊 [用户活动] 已记录分析请求: {stock_symbol}")
            except Exception as e:
                logger.warning(f"⚠️ [用户活动] 记录失败: {e}")

        logger.info(f"📊 [Config Cache] Form configuration saved: {form_config}")

        logger.debug(f"🔍 [FORM DEBUG] Returning form data: {form_data}")
        logger.debug("🔍 [FORM DEBUG] ===== Form submission finished =====")

        return form_data
    elif submitted and not stock_symbol:
        # User clicked submit without a ticker
        logger.error("🔍 [FORM DEBUG] Submission failed: stock symbol missing")
        st.error("❌ Please enter a ticker symbol before submitting")
        return {'submitted': False}
    else:
        return {'submitted': False}
