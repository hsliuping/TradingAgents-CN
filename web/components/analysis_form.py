"""
分析表单组件
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
    """渲染股票分析表单"""

    st.subheader("📋 分析配置")

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

        # 在表单开始时保存当前配置（用于检测变化）
        initial_config = cached_config.copy() if cached_config else {}
        col1, col2 = st.columns(2)
        
        with col1:
            # 市场选择（使用缓存的值）
            market_options = ["美股", "A股", "港股"]
            cached_market = cached_config.get('market_type', 'A股') if cached_config else 'A股'
            try:
                market_index = market_options.index(cached_market)
            except (ValueError, TypeError):
                market_index = 1  # 默认A股

            market_type = st.selectbox(
                "选择市场 🌍",
                options=market_options,
                index=market_index,
                help="选择要分析的股票市场"
            )

            # 根据市场类型显示不同的输入提示
            cached_stock = cached_config.get('stock_symbol', '') if cached_config else ''

            if market_type == "美股":
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '美股') else '',
                    placeholder="输入美股代码，如 AAPL, TSLA, MSFT，然后按回车确认",
                    help="输入要分析的美股代码，输入完成后请按回车键确认",
                    key="us_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] 美股text_input返回值: '{stock_symbol}'")

            elif market_type == "港股":
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '港股') else '',
                    placeholder="输入港股代码，如 0700.HK, 9988.HK, 3690.HK，然后按回车确认",
                    help="输入要分析的港股代码，如 0700.HK(腾讯控股), 9988.HK(阿里巴巴), 3690.HK(美团)，输入完成后请按回车键确认",
                    key="hk_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).upper().strip()

                logger.debug(f"🔍 [FORM DEBUG] 港股text_input返回值: '{stock_symbol}'")

            else:  # A股
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'A股') else '',
                    placeholder="输入A股代码，如 000001, 600519，然后按回车确认",
                    help="输入要分析的A股代码，如 000001(平安银行), 600519(贵州茅台)，输入完成后请按回车键确认",
                    key="cn_stock_input",
                    autocomplete="off"  # 修复autocomplete警告
                ).strip()

                logger.debug(f"🔍 [FORM DEBUG] A股text_input返回值: '{stock_symbol}'")
            
            # 分析日期
            analysis_date = st.date_input(
                "分析日期 📅",
                value=datetime.date.today(),
                help="选择分析的基准日期"
            )
        
        with col2:
            # 研究深度（使用缓存的值）
            cached_depth = cached_config.get('research_depth', 3) if cached_config else 3
            research_depth = st.select_slider(
                "研究深度 🔍",
                options=[1, 2, 3, 4, 5],
                value=cached_depth,
                format_func=lambda x: {
                    1: "1级 - 快速分析",
                    2: "2级 - 基础分析",
                    3: "3级 - 标准分析",
                    4: "4级 - 深度分析",
                    5: "5级 - 全面分析"
                }[x],
                help="选择分析的深度级别，级别越高分析越详细但耗时更长"
            )
        
        # 分析师团队选择
        st.markdown("### 👥 选择分析师团队")

        col1, col2 = st.columns(2)

        # 获取缓存的分析师选择和市场类型
        cached_analysts = cached_config.get('selected_analysts', ['market', 'fundamentals']) if cached_config else ['market', 'fundamentals']
        cached_market_type = cached_config.get('market_type', 'A股') if cached_config else 'A股'

        # 检测市场类型是否发生变化
        market_type_changed = cached_market_type != market_type

        # 如果市场类型发生变化，需要调整分析师选择
        if market_type_changed:
            if market_type == "A股":
                # 切换到A股：移除社交媒体分析师
                cached_analysts = [analyst for analyst in cached_analysts if analyst != 'social']
                if len(cached_analysts) == 0:
                    cached_analysts = ['market', 'fundamentals']  # 确保至少有默认选择
            else:
                # 切换到非A股：如果只有基础分析师，添加社交媒体分析师
                if 'social' not in cached_analysts and len(cached_analysts) <= 2:
                    cached_analysts.append('social')

        with col1:
            market_analyst = st.checkbox(
                "📈 市场分析师",
                value='market' in cached_analysts,
                help="专注于技术面分析、价格趋势、技术指标"
            )

            # 始终显示社交媒体分析师checkbox，但在A股时禁用
            if market_type == "A股":
                # A股市场：显示但禁用社交媒体分析师
                social_analyst = st.checkbox(
                    "💭 社交媒体分析师",
                    value=False,
                    disabled=True,
                    help="A股市场暂不支持社交媒体分析（国内数据源限制）"
                )
                st.info("💡 A股市场暂不支持社交媒体分析，因为国内数据源限制")
            else:
                # 非A股市场：正常显示社交媒体分析师
                social_analyst = st.checkbox(
                    "💭 社交媒体分析师",
                    value='social' in cached_analysts,
                    help="分析社交媒体情绪、投资者情绪指标"
                )

        with col2:
            news_analyst = st.checkbox(
                "📰 新闻分析师",
                value='news' in cached_analysts,
                help="分析相关新闻事件、市场动态影响"
            )

            fundamentals_analyst = st.checkbox(
                "💰 基本面分析师",
                value='fundamentals' in cached_analysts,
                help="分析财务数据、公司基本面、估值水平"
            )

        # 收集选中的分析师
        selected_analysts = []
        if market_analyst:
            selected_analysts.append(("market", "市场分析师"))
        if social_analyst:
            selected_analysts.append(("social", "社交媒体分析师"))
        if news_analyst:
            selected_analysts.append(("news", "新闻分析师"))
        if fundamentals_analyst:
            selected_analysts.append(("fundamentals", "基本面分析师"))
        
        # 显示选择摘要
        if selected_analysts:
            st.success(f"已选择 {len(selected_analysts)} 个分析师: {', '.join([a[1] for a in selected_analysts])}")
        else:
            st.warning("请至少选择一个分析师")
        
        # 高级选项
        with st.expander("🔧 高级选项"):
            include_sentiment = st.checkbox(
                "包含情绪分析",
                value=True,
                help="是否包含市场情绪和投资者情绪分析"
            )
            
            include_risk_assessment = st.checkbox(
                "包含风险评估",
                value=True,
                help="是否包含详细的风险因素评估"
            )
            
            custom_prompt = st.text_area(
                "自定义分析要求",
                placeholder="输入特定的分析要求或关注点...",
                help="可以输入特定的分析要求，AI会在分析中重点关注"
            )

        # 显示输入状态提示
        if not stock_symbol:
            st.info("💡 请在上方输入股票代码，输入完成后按回车键确认")
        else:
            st.success(f"✅ 已输入股票代码: {stock_symbol}")

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

        # 在提交按钮前检测配置变化并保存
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

        # 提交按钮（不禁用，让用户可以点击）
        submitted = st.form_submit_button(
            "🚀 开始分析",
            type="primary",
            use_container_width=True
        )

    # 只有在提交时才返回数据
    if submitted and stock_symbol:  # 确保有股票代码才提交
        # 添加详细日志
        logger.debug(f"🔍 [FORM DEBUG] ===== 分析表单提交 =====")
        logger.debug(f"🔍 [FORM DEBUG] 用户输入的股票代码: '{stock_symbol}'")
        logger.debug(f"🔍 [FORM DEBUG] 市场类型: '{market_type}'")
        logger.debug(f"🔍 [FORM DEBUG] 分析日期: '{analysis_date}'")
        logger.debug(f"🔍 [FORM DEBUG] 选择的分析师: {[a[0] for a in selected_analysts]}")
        logger.debug(f"🔍 [FORM DEBUG] 研究深度: {research_depth}")

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
