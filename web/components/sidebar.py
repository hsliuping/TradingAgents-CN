"""
侧边栏组件
"""

import streamlit as st
import os
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from web.utils.persistence import load_model_selection, save_model_selection

logger = logging.getLogger(__name__)

def render_sidebar():
    """渲染侧边栏配置"""

    # 添加localStorage支持的JavaScript
    st.markdown("""
    <script>
    // 保存到localStorage
    function saveToLocalStorage(key, value) {
        localStorage.setItem('tradingagents_' + key, value);
        console.log('Saved to localStorage:', key, value);
    }

    // 从localStorage读取
    function loadFromLocalStorage(key, defaultValue) {
        const value = localStorage.getItem('tradingagents_' + key);
        console.log('Loaded from localStorage:', key, value || defaultValue);
        return value || defaultValue;
    }

    // 页面加载时恢复设置
    window.addEventListener('load', function() {
        console.log('Page loaded, restoring settings...');
    });
    </script>
    """, unsafe_allow_html=True)

    # 优化侧边栏样式
    st.markdown("""
    <style>
    /* 优化侧边栏宽度 - 调整为320px */
    section[data-testid="stSidebar"] {
        width: 320px !important;
        min-width: 320px !important;
        max-width: 320px !important;
    }

    /* 优化侧边栏内容容器 */
    section[data-testid="stSidebar"] > div {
        width: 320px !important;
        min-width: 320px !important;
        max-width: 320px !important;
    }

    /* 强制减少侧边栏内边距 - 多种选择器确保生效 */
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] > div > div,
    .css-1d391kg,
    .css-1lcbmhc,
    .css-1cypcdb {
        padding-top: 0.75rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 0.75rem !important;
    }

    /* 侧边栏内所有元素的边距控制 */
    section[data-testid="stSidebar"] * {
        box-sizing: border-box !important;
    }

    /* 优化selectbox容器 */
    section[data-testid="stSidebar"] .stSelectbox {
        margin-bottom: 0.4rem !important;
        width: 100% !important;
    }

    /* 优化selectbox下拉框 - 调整为适合320px */
    section[data-testid="stSidebar"] .stSelectbox > div > div,
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        width: 100% !important;
        min-width: 260px !important;
        max-width: 280px !important;
    }

    /* 优化下拉框选项文本 */
    section[data-testid="stSidebar"] .stSelectbox label {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.2rem !important;
    }

    /* 优化文本输入框 */
    section[data-testid="stSidebar"] .stTextInput > div > div > input {
        font-size: 0.8rem !important;
        padding: 0.3rem 0.5rem !important;
        width: 100% !important;
    }

    /* 优化按钮样式 */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        font-size: 0.8rem !important;
        padding: 0.3rem 0.5rem !important;
        margin: 0.1rem 0 !important;
        border-radius: 0.3rem !important;
    }

    /* 优化标题样式 */
    section[data-testid="stSidebar"] h3 {
        font-size: 1rem !important;
        margin-bottom: 0.5rem !important;
        margin-top: 0.3rem !important;
        padding: 0 !important;
    }

    /* 优化info框样式 */
    section[data-testid="stSidebar"] .stAlert {
        padding: 0.4rem !important;
        margin: 0.3rem 0 !important;
        font-size: 0.75rem !important;
    }

    /* 优化markdown文本 */
    section[data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0.3rem !important;
        padding: 0 !important;
    }

    /* 优化分隔线 */
    section[data-testid="stSidebar"] hr {
        margin: 0.75rem 0 !important;
    }

    /* 确保下拉框选项完全可见 - 调整为适合320px */
    .stSelectbox [data-baseweb="select"] {
        min-width: 260px !important;
        max-width: 280px !important;
    }

    /* 优化下拉框选项列表 */
    .stSelectbox [role="listbox"] {
        min-width: 260px !important;
        max-width: 290px !important;
    }

    /* 额外的边距控制 - 确保左右边距减小 */
    .sidebar .element-container {
        padding: 0 !important;
        margin: 0.2rem 0 !important;
    }

    /* 强制覆盖默认样式 */
    .css-1d391kg .element-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # 使用组件来从localStorage读取并初始化session state
        st.markdown("""
        <div id="localStorage-reader" style="display: none;">
            <script>
            // 从localStorage读取设置并发送给Streamlit
            const provider = loadFromLocalStorage('llm_provider', 'dashscope');
            const category = loadFromLocalStorage('model_category', 'openai');
            const model = loadFromLocalStorage('llm_model', '');

            // 通过自定义事件发送数据
            window.parent.postMessage({
                type: 'localStorage_data',
                provider: provider,
                category: category,
                model: model
            }, '*');
            </script>
        </div>
        """, unsafe_allow_html=True)

        # 从持久化存储加载配置
        saved_config = load_model_selection()

        # 初始化session state，优先使用保存的配置
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = saved_config['provider']
            logger.debug(f"🔧 [Persistence] 恢复 llm_provider: {st.session_state.llm_provider}")
        if 'model_category' not in st.session_state:
            st.session_state.model_category = saved_config['category']
            logger.debug(f"🔧 [Persistence] 恢复 model_category: {st.session_state.model_category}")
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = saved_config['model']
            logger.debug(f"🔧 [Persistence] 恢复 llm_model: {st.session_state.llm_model}")

        # 显示当前session state状态（调试用）
        logger.debug(f"🔍 [Session State] 当前状态 - provider: {st.session_state.llm_provider}, category: {st.session_state.model_category}, model: {st.session_state.llm_model}")

        # AI模型配置
        st.markdown("### 🧠 AI模型配置")

        # LLM提供商选择
        llm_provider = st.selectbox(
            "LLM提供商",
            options=["dashscope", "deepseek", "google", "openrouter"],
            index=["dashscope", "deepseek", "google", "openrouter"].index(st.session_state.llm_provider) if st.session_state.llm_provider in ["dashscope", "deepseek", "google", "openrouter"] else 0,
            format_func=lambda x: {
                "dashscope": "🇨🇳 阿里百炼",
                "deepseek": "🚀 DeepSeek V3",
                "google": "🌟 Google AI",
                "openrouter": "🌐 OpenRouter"
            }[x],
            help="选择AI模型提供商",
            key="llm_provider_select"
        )

        # 更新session state和持久化存储
        if st.session_state.llm_provider != llm_provider:
            logger.info(f"🔄 [Persistence] 提供商变更: {st.session_state.llm_provider} → {llm_provider}")
            st.session_state.llm_provider = llm_provider
            # 提供商变更时清空模型选择
            st.session_state.llm_model = ""
            st.session_state.model_category = "openai"  # 重置为默认类别
            logger.info(f"🔄 [Persistence] 清空模型选择")

            # 保存到持久化存储
            save_model_selection(llm_provider, st.session_state.model_category, "")
        else:
            st.session_state.llm_provider = llm_provider

        # 根据提供商显示不同的模型选项
        if llm_provider == "dashscope":
            dashscope_options = ["qwen-turbo", "qwen-plus-latest", "qwen-max"]

            # 获取当前选择的索引
            current_index = 1  # 默认选择qwen-plus-latest
            if st.session_state.llm_model in dashscope_options:
                current_index = dashscope_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "模型版本",
                options=dashscope_options,
                index=current_index,
                format_func=lambda x: {
                    "qwen-turbo": "Turbo - 快速",
                    "qwen-plus-latest": "Plus - 平衡",
                    "qwen-max": "Max - 最强"
                }[x],
                help="选择用于分析的阿里百炼模型",
                key="dashscope_model_select"
            )

            # 更新session state和持久化存储
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] DashScope模型变更: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] DashScope模型已保存: {llm_model}")

            # 保存到持久化存储
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
        elif llm_provider == "deepseek":
            deepseek_options = ["deepseek-chat"]

            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in deepseek_options:
                current_index = deepseek_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "选择DeepSeek模型",
                options=deepseek_options,
                index=current_index,
                format_func=lambda x: {
                    "deepseek-chat": "DeepSeek Chat - 通用对话模型，适合股票分析"
                }[x],
                help="选择用于分析的DeepSeek模型",
                key="deepseek_model_select"
            )

            # 更新session state和持久化存储
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] DeepSeek模型变更: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] DeepSeek模型已保存: {llm_model}")

            # 保存到持久化存储
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

        elif llm_provider == "google":
            google_options = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in google_options:
                current_index = google_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "选择Google模型",
                options=google_options,
                index=current_index,
                format_func=lambda x: {
                    "gemini-2.0-flash": "Gemini 2.0 Flash - 推荐使用",
                    "gemini-1.5-pro": "Gemini 1.5 Pro - 强大性能",
                    "gemini-1.5-flash": "Gemini 1.5 Flash - 快速响应"
                }[x],
                help="选择用于分析的Google Gemini模型",
                key="google_model_select"
            )

            # 更新session state和持久化存储
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] Google模型变更: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] Google模型已保存: {llm_model}")

            # 保存到持久化存储
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
        else:  # openrouter
            # OpenRouter模型分类选择
            model_category = st.selectbox(
                "模型类别",
                options=["openai", "anthropic", "meta", "google", "custom"],
                index=["openai", "anthropic", "meta", "google", "custom"].index(st.session_state.model_category) if st.session_state.model_category in ["openai", "anthropic", "meta", "google", "custom"] else 0,
                format_func=lambda x: {
                    "openai": "🤖 OpenAI (GPT系列)",
                    "anthropic": "🧠 Anthropic (Claude系列)",
                    "meta": "🦙 Meta (Llama系列)",
                    "google": "🌟 Google (Gemini系列)",
                    "custom": "✏️ 自定义模型"
                }[x],
                help="选择模型厂商类别或自定义输入",
                key="model_category_select"
            )

            # 更新session state和持久化存储
            if st.session_state.model_category != model_category:
                logger.debug(f"🔄 [Persistence] 模型类别变更: {st.session_state.model_category} → {model_category}")
                st.session_state.llm_model = ""  # 类别变更时清空模型选择
            st.session_state.model_category = model_category

            # 保存到持久化存储
            save_model_selection(st.session_state.llm_provider, model_category, st.session_state.llm_model)

            # 根据厂商显示不同的模型
            if model_category == "openai":
                openai_options = [
                    "openai/o4-mini-high",
                    "openai/o3-pro",
                    "openai/o3-mini-high",
                    "openai/o3-mini",
                    "openai/o1-pro",
                    "openai/o1-mini",
                    "openai/gpt-4o-2024-11-20",
                    "openai/gpt-4o-mini",
                    "openai/gpt-4-turbo",
                    "openai/gpt-3.5-turbo"
                ]

                # 获取当前选择的索引
                current_index = 0
                if st.session_state.llm_model in openai_options:
                    current_index = openai_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择OpenAI模型",
                    options=openai_options,
                    index=current_index,
                    format_func=lambda x: {
                        "openai/o4-mini-high": "🚀 o4 Mini High - 最新o4系列",
                        "openai/o3-pro": "🚀 o3 Pro - 最新推理专业版",
                        "openai/o3-mini-high": "o3 Mini High - 高性能推理",
                        "openai/o3-mini": "o3 Mini - 推理模型",
                        "openai/o1-pro": "o1 Pro - 专业推理",
                        "openai/o1-mini": "o1 Mini - 轻量推理",
                        "openai/gpt-4o-2024-11-20": "GPT-4o (2024-11-20) - 最新版",
                        "openai/gpt-4o-mini": "GPT-4o Mini - 轻量旗舰",
                        "openai/gpt-4-turbo": "GPT-4 Turbo - 经典强化",
                        "openai/gpt-3.5-turbo": "GPT-3.5 Turbo - 经济实用"
                    }[x],
                    help="OpenAI公司的GPT和o系列模型，包含最新o4",
                    key="openai_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] OpenAI模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] OpenAI模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
            elif model_category == "anthropic":
                anthropic_options = [
                    "anthropic/claude-opus-4",
                    "anthropic/claude-sonnet-4",
                    "anthropic/claude-haiku-4",
                    "anthropic/claude-3.5-sonnet",
                    "anthropic/claude-3.5-haiku",
                    "anthropic/claude-3.5-sonnet-20241022",
                    "anthropic/claude-3.5-haiku-20241022",
                    "anthropic/claude-3-opus",
                    "anthropic/claude-3-sonnet",
                    "anthropic/claude-3-haiku"
                ]

                # 获取当前选择的索引
                current_index = 0
                if st.session_state.llm_model in anthropic_options:
                    current_index = anthropic_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Anthropic模型",
                    options=anthropic_options,
                    index=current_index,
                    format_func=lambda x: {
                        "anthropic/claude-opus-4": "🚀 Claude Opus 4 - 最新顶级模型",
                        "anthropic/claude-sonnet-4": "🚀 Claude Sonnet 4 - 最新平衡模型",
                        "anthropic/claude-haiku-4": "🚀 Claude Haiku 4 - 最新快速模型",
                        "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet - 当前旗舰",
                        "anthropic/claude-3.5-haiku": "Claude 3.5 Haiku - 快速响应",
                        "anthropic/claude-3.5-sonnet-20241022": "Claude 3.5 Sonnet (2024-10-22)",
                        "anthropic/claude-3.5-haiku-20241022": "Claude 3.5 Haiku (2024-10-22)",
                        "anthropic/claude-3-opus": "Claude 3 Opus - 强大性能",
                        "anthropic/claude-3-sonnet": "Claude 3 Sonnet - 平衡版",
                        "anthropic/claude-3-haiku": "Claude 3 Haiku - 经济版"
                    }[x],
                    help="Anthropic公司的Claude系列模型，包含最新Claude 4",
                    key="anthropic_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Anthropic模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Anthropic模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
            elif model_category == "meta":
                meta_options = [
                    "meta-llama/llama-4-maverick",
                    "meta-llama/llama-4-scout",
                    "meta-llama/llama-3.3-70b-instruct",
                    "meta-llama/llama-3.2-90b-vision-instruct",
                    "meta-llama/llama-3.1-405b-instruct",
                    "meta-llama/llama-3.1-70b-instruct",
                    "meta-llama/llama-3.2-11b-vision-instruct",
                    "meta-llama/llama-3.1-8b-instruct",
                    "meta-llama/llama-3.2-3b-instruct",
                    "meta-llama/llama-3.2-1b-instruct"
                ]

                # 获取当前选择的索引
                current_index = 0
                if st.session_state.llm_model in meta_options:
                    current_index = meta_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Meta模型",
                    options=meta_options,
                    index=current_index,
                    format_func=lambda x: {
                        "meta-llama/llama-4-maverick": "🚀 Llama 4 Maverick - 最新旗舰",
                        "meta-llama/llama-4-scout": "🚀 Llama 4 Scout - 最新预览",
                        "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B - 强大性能",
                        "meta-llama/llama-3.2-90b-vision-instruct": "Llama 3.2 90B Vision - 多模态",
                        "meta-llama/llama-3.1-405b-instruct": "Llama 3.1 405B - 超大模型",
                        "meta-llama/llama-3.1-70b-instruct": "Llama 3.1 70B - 平衡性能",
                        "meta-llama/llama-3.2-11b-vision-instruct": "Llama 3.2 11B Vision - 轻量多模态",
                        "meta-llama/llama-3.1-8b-instruct": "Llama 3.1 8B - 高效模型",
                        "meta-llama/llama-3.2-3b-instruct": "Llama 3.2 3B - 轻量级",
                        "meta-llama/llama-3.2-1b-instruct": "Llama 3.2 1B - 超轻量"
                    }[x],
                    help="Meta公司的Llama系列模型，包含最新Llama 4",
                    key="meta_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Meta模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Meta模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
            elif model_category == "google":
                google_openrouter_options = [
                    "google/gemini-2.5-pro",
                    "google/gemini-2.5-flash",
                    "google/gemini-2.5-flash-lite",
                    "google/gemini-2.0-flash-001",
                    "google/gemini-2.0-flash-lite-001",
                    "google/gemini-1.5-pro",
                    "google/gemini-1.5-flash",
                    "google/gemma-3-27b-it",
                    "google/gemma-3-12b-it",
                    "google/gemma-2-27b-it"
                ]

                # 获取当前选择的索引
                current_index = 0
                if st.session_state.llm_model in google_openrouter_options:
                    current_index = google_openrouter_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Google模型",
                    options=google_openrouter_options,
                    index=current_index,
                    format_func=lambda x: {
                        "google/gemini-2.5-pro": "🚀 Gemini 2.5 Pro - 最新旗舰",
                        "google/gemini-2.5-flash": "🚀 Gemini 2.5 Flash - 最新快速",
                        "google/gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite - 轻量版",
                        "google/gemini-2.0-flash-001": "Gemini 2.0 Flash - 稳定版",
                        "google/gemini-2.0-flash-lite-001": "Gemini 2.0 Flash Lite",
                        "google/gemini-1.5-pro": "Gemini 1.5 Pro - 专业版",
                        "google/gemini-1.5-flash": "Gemini 1.5 Flash - 快速版",
                        "google/gemma-3-27b-it": "Gemma 3 27B - 最新开源大模型",
                        "google/gemma-3-12b-it": "Gemma 3 12B - 开源中型模型",
                        "google/gemma-2-27b-it": "Gemma 2 27B - 开源经典版"
                    }[x],
                    help="Google公司的Gemini/Gemma系列模型，包含最新Gemini 2.5",
                    key="google_openrouter_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Google OpenRouter模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Google OpenRouter模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

            else:  # custom
                st.markdown("### ✏️ 自定义模型")

                # 初始化自定义模型session state
                if 'custom_model' not in st.session_state:
                    st.session_state.custom_model = ""

                # 自定义模型输入 - 使用session state作为默认值
                default_value = st.session_state.custom_model if st.session_state.custom_model else "anthropic/claude-3.7-sonnet"

                llm_model = st.text_input(
                    "输入模型ID",
                    value=default_value,
                    placeholder="例如: anthropic/claude-3.7-sonnet",
                    help="输入OpenRouter支持的任何模型ID",
                    key="custom_model_input"
                )

                # 常用模型快速选择
                st.markdown("**快速选择常用模型:**")

                # 长条形按钮，每个占一行
                if st.button("🧠 Claude 3.7 Sonnet - 最新对话模型", key="claude37", use_container_width=True):
                    model_id = "anthropic/claude-3.7-sonnet"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] 快速选择Claude 3.7 Sonnet: {model_id}")
                    st.rerun()

                if st.button("💎 Claude 4 Opus - 顶级性能模型", key="claude4opus", use_container_width=True):
                    model_id = "anthropic/claude-opus-4"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] 快速选择Claude 4 Opus: {model_id}")
                    st.rerun()

                if st.button("🤖 GPT-4o - OpenAI旗舰模型", key="gpt4o", use_container_width=True):
                    model_id = "openai/gpt-4o"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] 快速选择GPT-4o: {model_id}")
                    st.rerun()

                if st.button("🦙 Llama 4 Scout - Meta最新模型", key="llama4", use_container_width=True):
                    model_id = "meta-llama/llama-4-scout"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] 快速选择Llama 4 Scout: {model_id}")
                    st.rerun()

                if st.button("🌟 Gemini 2.5 Pro - Google多模态", key="gemini25", use_container_width=True):
                    model_id = "google/gemini-2.5-pro"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] 快速选择Gemini 2.5 Pro: {model_id}")
                    st.rerun()

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] 自定义模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.custom_model = llm_model
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] 自定义模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

                # 模型验证提示
                if llm_model:
                    st.success(f"✅ 当前模型: `{llm_model}`")

                    # 提供模型查找链接
                    st.markdown("""
                    **📚 查找更多模型:**
                    - [OpenRouter模型列表](https://openrouter.ai/models)
                    - [Anthropic模型文档](https://docs.anthropic.com/claude/docs/models-overview)
                    - [OpenAI模型文档](https://platform.openai.com/docs/models)
                    """)
                else:
                    st.warning("⚠️ 请输入有效的模型ID")

            # OpenRouter特殊提示
            st.info("💡 **OpenRouter配置**: 在.env文件中设置OPENROUTER_API_KEY，或者如果只用OpenRouter可以设置OPENAI_API_KEY")
        
        # 高级设置
        with st.expander("⚙️ 高级设置"):
            enable_memory = st.checkbox(
                "启用记忆功能",
                value=False,
                help="启用智能体记忆功能（可能影响性能）"
            )
            
            enable_debug = st.checkbox(
                "调试模式",
                value=False,
                help="启用详细的调试信息输出"
            )
            
            max_tokens = st.slider(
                "最大输出长度",
                min_value=1000,
                max_value=8000,
                value=4000,
                step=500,
                help="AI模型的最大输出token数量"
            )
        
        st.markdown("---")

        # 系统配置
        st.markdown("**🔧 系统配置**")

        # API密钥状态
        st.markdown("**🔑 API密钥状态**")

        def validate_api_key(key, expected_format):
            """验证API密钥格式"""
            if not key:
                return "未配置", "error"

            if expected_format == "dashscope" and key.startswith("sk-") and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "deepseek" and key.startswith("sk-") and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "finnhub" and len(key) >= 20:
                return f"{key[:8]}...", "success"
            elif expected_format == "tushare" and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "google" and key: # 直接判断Google Key是否存在，不再校验格式
                return f"{key[:8]}...", "success"
            elif expected_format == "openai" and key.startswith("sk-") and len(key) >= 40:
                return f"{key[:8]}...", "success"
            elif expected_format == "anthropic" and key.startswith("sk-") and len(key) >= 40:
                return f"{key[:8]}...", "success"
            elif expected_format == "reddit" and len(key) >= 10:
                return f"{key[:8]}...", "success"
            else:
                return f"{key[:8]}... (格式异常)", "warning"

        # 必需的API密钥
        st.markdown("*必需配置:*")

        # 阿里百炼
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        status, level = validate_api_key(dashscope_key, "dashscope")
        if level == "success":
            st.success(f"✅ 阿里百炼: {status}")
        elif level == "warning":
            st.warning(f"⚠️ 阿里百炼: {status}")
        else:
            st.error("❌ 阿里百炼: 未配置")

        # FinnHub
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        status, level = validate_api_key(finnhub_key, "finnhub")
        if level == "success":
            st.success(f"✅ FinnHub: {status}")
        elif level == "warning":
            st.warning(f"⚠️ FinnHub: {status}")
        else:
            st.error("❌ FinnHub: 未配置")

        # 可选的API密钥
        st.markdown("*可选配置:*")

        # DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        status, level = validate_api_key(deepseek_key, "deepseek")
        if level == "success":
            st.success(f"✅ DeepSeek: {status}")
        elif level == "warning":
            st.warning(f"⚠️ DeepSeek: {status}")
        else:
            st.info("ℹ️ DeepSeek: 未配置")

        # Tushare
        tushare_key = os.getenv("TUSHARE_TOKEN")
        status, level = validate_api_key(tushare_key, "tushare")
        if level == "success":
            st.success(f"✅ Tushare: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Tushare: {status}")
        else:
            st.info("ℹ️ Tushare: 未配置")

        # Google AI
        google_key = os.getenv("GOOGLE_API_KEY")
        status, level = validate_api_key(google_key, "google")
        if level == "success":
            st.success(f"✅ Google AI: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Google AI: {status}")
        else:
            st.info("ℹ️ Google AI: 未配置")

        # OpenAI (如果配置了且不是默认值)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key != "your_openai_api_key_here":
            status, level = validate_api_key(openai_key, "openai")
            if level == "success":
                st.success(f"✅ OpenAI: {status}")
            elif level == "warning":
                st.warning(f"⚠️ OpenAI: {status}")

        # Anthropic (如果配置了且不是默认值)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
            status, level = validate_api_key(anthropic_key, "anthropic")
            if level == "success":
                st.success(f"✅ Anthropic: {status}")
            elif level == "warning":
                st.warning(f"⚠️ Anthropic: {status}")

        st.markdown("---")

        # 系统信息
        st.markdown("**ℹ️ 系统信息**")
        
        st.info(f"""
        **版本**: cn-0.1.12
        **框架**: Streamlit + LangGraph
        **AI模型**: {st.session_state.llm_provider.upper()} - {st.session_state.llm_model}
        **数据源**: Tushare + FinnHub API
        """)
        
        # 帮助链接
        st.markdown("**📚 帮助资源**")
        
        st.markdown("""
        - [📖 使用文档](https://github.com/TauricResearch/TradingAgents)
        - [🐛 问题反馈](https://github.com/TauricResearch/TradingAgents/issues)
        - [💬 讨论社区](https://github.com/TauricResearch/TradingAgents/discussions)
        - [🔧 API密钥配置](../docs/security/api_keys_security.md)
        """)
    
    # 确保返回session state中的值，而不是局部变量
    final_provider = st.session_state.llm_provider
    final_model = st.session_state.llm_model

    logger.debug(f"🔄 [Session State] 返回配置 - provider: {final_provider}, model: {final_model}")

    return {
        'llm_provider': final_provider,
        'llm_model': final_model,
        'enable_memory': enable_memory,
        'enable_debug': enable_debug,
        'max_tokens': max_tokens
    }
