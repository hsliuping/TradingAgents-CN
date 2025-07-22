"""
Analysis form component
"""

import streamlit as st
import datetime

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')


def render_analysis_form():
    """Render stock analysis form"""

    st.subheader("📋 Analysis Configuration")

    # Get cached form configuration (ensure it's not None)
    cached_config = st.session_state.get('form_config') or {}

    # Debug information (only log when no analysis is running, to avoid repetition)
    if not st.session_state.get('analysis_running', False):
        if cached_config:
            logger.info(f"📊 [Configuration Recovery] Using cached configuration: {cached_config}")
        else:
            logger.info("📊 [Configuration Recovery] Using default configuration")

    # Create form
    with st.form("analysis_form", clear_on_submit=False):

        # Save current configuration at the start of the form (to detect changes)
        initial_config = cached_config.copy() if cached_config else {}
        col1, col2 = st.columns(2)
        
        with col1:
            # Market selection (using cached value)
            market_options = ["US Stocks", "A-Shares", "HK Stocks"]
            cached_market = cached_config.get('market_type', 'A-Shares') if cached_config else 'A-Shares'
            try:
                market_index = market_options.index(cached_market)
            except (ValueError, TypeError):
                market_index = 1  # Default A-Share

            market_type = st.selectbox(
                "Select Market 🌍",
                options=market_options,
                index=market_index,
                help="Choose the stock market to analyze"
            )

            # Display different input prompts based on market type
            cached_stock = cached_config.get('stock_symbol', '') if cached_config else ''

            if market_type == "US Stocks":
                stock_symbol = st.text_input(
                    "Stock Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'US Stocks') else '',
                    placeholder="Enter US stock symbol, e.g., AAPL, TSLA, MSFT, then press Enter to confirm",
                    help="Enter the US stock symbol you want to analyze. Press Enter after input.",
                    key="us_stock_input",
                    autocomplete="off"  # Fix autocomplete warning
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] US text_input return value: '{stock_symbol}'")

            elif market_type == "HK Stocks":
                stock_symbol = st.text_input(
                    "Stock Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'HK Stocks') else '',
                    placeholder="Enter HK stock symbol, e.g., 0700.HK, 9988.HK, 3690.HK, then press Enter to confirm",
                    help="Enter the HK stock symbol you want to analyze, e.g., 0700.HK (Tencent Holdings), 9988.HK (Alibaba), 3690.HK (Meituan), press Enter after input.",
                    key="hk_stock_input",
                    autocomplete="off"  # Fix autocomplete warning
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] HK text_input return value: '{stock_symbol}'")

            else:  # A-Share
                stock_symbol = st.text_input(
                    "Stock Symbol 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'A-Shares') else '',
                    placeholder="Enter A-Share symbol, e.g., 000001, 600519, then press Enter to confirm",
                    help="Enter the A-Share symbol you want to analyze, e.g., 000001 (Ping An Bank), 600519 (Guizhou Moutai), press Enter after input.",
                    key="cn_stock_input",
                    autocomplete="off"  # Fix autocomplete warning
                ).strip()

                logger.debug(f"🔍 [FORM DEBUG] A-Share text_input return value: '{stock_symbol}'")
            
            # Analysis date
            analysis_date = st.date_input(
                "Analysis Date 📅",
                value=datetime.date.today(),
                help="Choose the base date for analysis"
            )
        
        with col2:
            # Research depth (using cached value)
            cached_depth = cached_config.get('research_depth', 3) if cached_config else 3
            research_depth = st.select_slider(
                "Research Depth 🔍",
                options=[1, 2, 3, 4, 5],
                value=cached_depth,
                format_func=lambda x: {
                    1: "Level 1 - Quick Analysis",
                    2: "Level 2 - Basic Analysis",
                    3: "Level 3 - Standard Analysis",
                    4: "Level 4 - Deep Analysis",
                    5: "Level 5 - Comprehensive Analysis"
                }[x],
                help="Choose the analysis depth level, with higher levels providing more detailed analysis but longer duration"
            )
        
        # Analyst team selection
        st.markdown("### 👥 Select Analyst Team")
        
        col1, col2 = st.columns(2)
        
        # Get cached analyst selection
        cached_analysts = cached_config.get('selected_analysts', ['market', 'fundamentals']) if cached_config else ['market', 'fundamentals']

        with col1:
            market_analyst = st.checkbox(
                "📈 Market Analyst",
                value='market' in cached_analysts,
                help="Focus on technical analysis, price trends, and technical indicators"
            )

            social_analyst = st.checkbox(
                "💭 Social Media Analyst",
                value='social' in cached_analysts,
                help="Analyze social media sentiment and investor sentiment indicators"
            )

        with col2:
            news_analyst = st.checkbox(
                "📰 News Analyst",
                value='news' in cached_analysts,
                help="Analyze relevant news events and market dynamics"
            )

            fundamentals_analyst = st.checkbox(
                "💰 Fundamental Analyst",
                value='fundamentals' in cached_analysts,
                help="Analyze financial data, company fundamentals, and valuation levels"
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
            selected_analysts.append(("fundamentals", "Fundamental Analyst"))
        
        # Display selection summary
        if selected_analysts:
            st.success(f"Selected {len(selected_analysts)} analysts: {', '.join([a[1] for a in selected_analysts])}")
        else:
            st.warning("Please select at least one analyst")
        
        # Advanced options
        with st.expander("🔧 Advanced Options"):
            include_sentiment = st.checkbox(
                "Include Sentiment Analysis",
                value=True,
                help="Whether to include market sentiment and investor sentiment analysis"
            )
            
            include_risk_assessment = st.checkbox(
                "Include Risk Assessment",
                value=True,
                help="Whether to include a detailed risk factor assessment"
            )
            
            custom_prompt = st.text_area(
                "Custom Analysis Requirements",
                placeholder="Enter specific analysis requirements or focus points...",
                help="You can enter specific analysis requirements, and AI will focus on them during analysis"
            )

        # Display input status prompt
        if not stock_symbol:
            st.info("💡 Please enter the stock symbol above, and press Enter to confirm after input.")
        else:
            st.success(f"✅ Stock symbol entered: {stock_symbol}")

        # Add JavaScript to improve user experience
        st.markdown("""
        <script>
        // Listen for input field changes to provide better user feedback
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input[type="text"]');
            inputs.forEach(input => {
                input.addEventListener('input', function() {
                    if (this.value.trim()) {
                        this.style.borderColor = '#00ff00';
                        this.title = 'Press Enter to confirm input';
                    } else {
                        this.style.borderColor = '';
                        this.title = '';
                    }
                });
            });
        });
        </script>
        """, unsafe_allow_html=True)

        # Detect configuration changes and save before the submit button
        current_config = {
            'stock_symbol': stock_symbol,
            'market_type': market_type,
            'research_depth': research_depth,
            'selected_analysts': [a[0] for a in selected_analysts],
            'include_sentiment': include_sentiment,
            'include_risk_assessment': include_risk_assessment,
            'custom_prompt': custom_prompt
        }

        # Save immediately if configuration changes (even if not submitted)
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
                logger.debug(f"📊 [Configuration Auto-saved] Form configuration updated")
            except Exception as e:
                logger.warning(f"⚠️ [Configuration Auto-saved] Save failed: {e}")

        # Submit button (do not disable, allow user to click)
        submitted = st.form_submit_button(
            "🚀 Start Analysis",
            type="primary",
            use_container_width=True
        )

    # Only return data if submitted
    if submitted and stock_symbol:  # Ensure stock symbol is entered before submitting
        # Add detailed logs
        logger.debug(f" [FORM DEBUG] ===== Analysis Form Submission =====")
        logger.debug(f"🔍 [FORM DEBUG] User input stock symbol: '{stock_symbol}'")
        logger.debug(f"🔍 [FORM DEBUG] Market type: '{market_type}'")
        logger.debug(f"🔍 [FORM DEBUG] Analysis date: '{analysis_date}'")
        logger.debug(f"🔍 [FORM DEBUG] Selected analysts: {[a[0] for a in selected_analysts]}")
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

        # Save form configuration to cache and persistent storage
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

        # Save to persistent storage
        try:
            from utils.smart_session_manager import smart_session_manager
            # Get current analysis ID (if any)
            current_analysis_id = st.session_state.get('current_analysis_id', 'form_config_only')
            smart_session_manager.save_analysis_state(
                analysis_id=current_analysis_id,
                status=st.session_state.get('analysis_running', False) and 'running' or 'idle',
                stock_symbol=stock_symbol,
                market_type=market_type,
                form_config=form_config
            )
        except Exception as e:
            logger.warning(f"⚠️ [Configuration Persistence] Save failed: {e}")

        logger.info(f"📊 [Configuration Cache] Form configuration saved: {form_config}")

        logger.debug(f"🔍 [FORM DEBUG] Returned form data: {form_data}")
        logger.debug(f"�� [FORM DEBUG] ===== Form Submission End =====")

        return form_data
    elif submitted and not stock_symbol:
        # User clicked submit but did not enter stock symbol
        logger.error(f"🔍 [FORM DEBUG] Submission failed: stock symbol is empty")
        st.error("❌ Please enter the stock symbol before submitting")
        return {'submitted': False}
    else:
        return {'submitted': False}
