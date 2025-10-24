"""
Sidebar component.
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
from web.utils.auth_manager import auth_manager

logger = logging.getLogger(__name__)

def get_version():
    """Read the project version from the VERSION file."""
    try:
        version_file = project_root / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        else:
            return "unknown"
    except Exception as e:
        logger.warning(f"Unable to read version file: {e}")
        return "unknown"

def render_sidebar():
    """Render the sidebar configuration."""

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

    # 侧边栏特定样式（全局样式在global_sidebar.css中）
    st.markdown("""
    <style>
    /* 侧边栏宽度和基础样式已在global_sidebar.css中定义 */

    /* 侧边栏特定的内边距和组件样式 */
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] > div > div,
    .css-1d391kg,
    .css-1lcbmhc,
    .css-1cypcdb {
        padding-top: 0.2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 0.75rem !important;
    }

    /* 优化selectbox容器 */
    section[data-testid="stSidebar"] .stSelectbox {
        margin-bottom: 0.4rem !important;
        width: 100% !important;
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
        margin-top: 0rem !important;
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

    /* 减少侧边栏顶部空白 */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* 减少第一个元素的顶部边距 */
    section[data-testid="stSidebar"] .element-container:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 减少标题的顶部边距 */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        margin-top: 0 !important;
        padding-top: 0 !important;
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

        # Initialize session state, prioritizing saved values
        if 'llm_provider' not in st.session_state:
            st.session_state.llm_provider = saved_config['provider']
            logger.debug(f"🔧 [Persistence] Restored llm_provider: {st.session_state.llm_provider}")
        if 'model_category' not in st.session_state:
            st.session_state.model_category = saved_config['category']
            logger.debug(f"🔧 [Persistence] Restored model_category: {st.session_state.model_category}")
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = saved_config['model']
            logger.debug(f"🔧 [Persistence] Restored llm_model: {st.session_state.llm_model}")

        # Display current session state (debug)
        logger.debug(f"🔍 [Session State] Current - provider: {st.session_state.llm_provider}, category: {st.session_state.model_category}, model: {st.session_state.llm_model}")

        # AI model configuration
        st.markdown("### 🧠 AI Model Configuration")

        # LLM provider selection
        llm_provider = st.selectbox(
            "LLM Provider",
            options=["dashscope", "deepseek", "google", "openai", "openrouter", "siliconflow", "custom_openai", "qianfan"],
            index=["dashscope", "deepseek", "google", "openai", "openrouter", "siliconflow", "custom_openai", "qianfan"].index(st.session_state.llm_provider) if st.session_state.llm_provider in ["dashscope", "deepseek", "google", "openai", "openrouter", "siliconflow", "custom_openai", "qianfan"] else 0,
            format_func=lambda x: {
                "dashscope": "🇨🇳 Alibaba Bailian",
                "deepseek": "🚀 DeepSeek V3",
                "google": "🌟 Google AI",
                "openai": "🤖 OpenAI",
                "openrouter": "🌐 OpenRouter",
                "siliconflow": "🇨🇳 SiliconFlow",
                "custom_openai": "🔧 Custom OpenAI Endpoint",
                "qianfan": "🧠 ERNIE Bot (Qianfan)"
            }[x],
            help="Choose the AI model provider",
            key="llm_provider_select"
        )

        # Update session state and persistence
        if st.session_state.llm_provider != llm_provider:
            logger.info(f"🔄 [Persistence] Provider changed: {st.session_state.llm_provider} → {llm_provider}")
            st.session_state.llm_provider = llm_provider
            # Clear model when provider changes
            st.session_state.llm_model = ""
            st.session_state.model_category = "openai"  # Reset to default category
            logger.info("🔄 [Persistence] Cleared model selection")

            # Save to persistent storage
            save_model_selection(llm_provider, st.session_state.model_category, "")
        else:
            st.session_state.llm_provider = llm_provider

        # Show different model options based on provider
        if llm_provider == "dashscope":
            dashscope_options = ["qwen-turbo", "qwen-plus-latest", "qwen-max"]

            # 获取当前选择的索引
            current_index = 1  # 默认选择qwen-plus-latest
            if st.session_state.llm_model in dashscope_options:
                current_index = dashscope_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "Model Version",
                options=dashscope_options,
                index=current_index,
                format_func=lambda x: {
                    "qwen-turbo": "Turbo - Fast",
                    "qwen-plus-latest": "Plus - Balanced",
                    "qwen-max": "Max - Most capable"
                }[x],
                help="Select the Alibaba Bailian model for analysis",
                key="dashscope_model_select"
            )

            # Update session state and persistence
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] DashScope model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] DashScope model saved: {llm_model}")

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
        elif llm_provider == "siliconflow":
            siliconflow_options = ["Qwen/Qwen3-30B-A3B-Thinking-2507", "Qwen/Qwen3-30B-A3B-Instruct-2507", "Qwen/Qwen3-235B-A22B-Thinking-2507", "Qwen/Qwen3-235B-A22B-Instruct-2507","deepseek-ai/DeepSeek-R1", "zai-org/GLM-4.5", "moonshotai/Kimi-K2-Instruct"]

            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in siliconflow_options:
                current_index = siliconflow_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "Select a SiliconFlow model",
                options=siliconflow_options,
                index=current_index,
                format_func=lambda x: {
                    "Qwen/Qwen3-30B-A3B-Thinking-2507": "Qwen3-30B-A3B-Thinking-2507 - 30B reasoning",
                    "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen3-30B-A3B-Instruct-2507 - 30B instruction",
                    "Qwen/Qwen3-235B-A22B-Thinking-2507": "Qwen3-235B-A22B-Thinking-2507 - 235B reasoning",
                    "Qwen/Qwen3-235B-A22B-Instruct-2507": "Qwen3-235B-A22B-Instruct-2507 - 235B instruction",
                    "deepseek-ai/DeepSeek-R1": "DeepSeek-R1",
                    "zai-org/GLM-4.5": "GLM-4.5 - Zhipu",
                    "moonshotai/Kimi-K2-Instruct": "Kimi-K2-Instruct",
                }[x],
                help="Select the SiliconFlow model for analysis",
                key="siliconflow_model_select"
            )

            # Update session state and persistence
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] SiliconFlow model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] SiliconFlow model saved: {llm_model}")

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

        elif llm_provider == "deepseek":
            deepseek_options = ["deepseek-chat"]

            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in deepseek_options:
                current_index = deepseek_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "Select a DeepSeek model",
                options=deepseek_options,
                index=current_index,
                format_func=lambda x: {
                    "deepseek-chat": "DeepSeek Chat - General-purpose model for stock analysis"
                }[x],
                help="Select the DeepSeek model for analysis",
                key="deepseek_model_select"
            )

            # Update session state and persistence
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] DeepSeek model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] DeepSeek model saved: {llm_model}")

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

        elif llm_provider == "google":
            google_options = [
                "gemini-2.5-pro", 
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.5-pro-002",
                "gemini-2.5-flash-002",
                "gemini-2.0-flash",
                "gemini-2.5-flash-lite-preview-06-17", 
                "gemini-1.5-pro", 
                "gemini-1.5-flash"
            ]

            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in google_options:
                current_index = google_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "Select a Google model",
                options=google_options,
                index=current_index,
                format_func=lambda x: {
                    "gemini-2.5-pro": "Gemini 2.5 Pro - 🚀 Latest flagship",
                    "gemini-2.5-flash": "Gemini 2.5 Flash - ⚡ Fastest option",
                    "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite - 💡 Lightweight and quick",
                    "gemini-2.5-flash-lite-preview-06-17": "Gemini 2.5 Flash Lite Preview - ⚡ Ultra-fast (1.45s)",
                    "gemini-2.5-pro-002": "Gemini 2.5 Pro-002 - 🔧 Optimized release",
                    "gemini-2.5-flash-002": "Gemini 2.5 Flash-002 - ⚡ Optimized speed",
                    "gemini-2.0-flash": "Gemini 2.0 Flash - 🚀 Recommended (1.87s)",
                    "gemini-1.5-pro": "Gemini 1.5 Pro - ⚖️ Strong performance (2.25s)",
                    "gemini-1.5-flash": "Gemini 1.5 Flash - 💨 Fast response (2.87s)"
                }[x],
                help="Select the Google Gemini model for analysis",
                key="google_model_select"
            )

            # Update session state and persistence
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] Google model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] Google model saved: {llm_model}")

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
        elif llm_provider == "qianfan":
            qianfan_options = [
                "ernie-3.5-8k",
                "ernie-4.0-turbo-8k",
                "ERNIE-Speed-8K",
                "ERNIE-Lite-8K"
            ]

            current_index = 0
            if st.session_state.llm_model in qianfan_options:
                current_index = qianfan_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                "Select an ERNIE Bot model",
                options=qianfan_options,
                index=current_index,
                format_func=lambda x: {
                    "ernie-3.5-8k": "ERNIE 3.5 8K - ⚡ Fast and efficient",
                    "ernie-4.0-turbo-8k": "ERNIE 4.0 Turbo 8K - 🚀 Advanced reasoning",
                    "ERNIE-Speed-8K": "ERNIE Speed 8K - 🏃 Ultra-fast responses",
                    "ERNIE-Lite-8K": "ERNIE Lite 8K - 💡 Lightweight and cost-effective"
                }[x],
                help="Select the ERNIE Bot (Qianfan) model for analysis",
                key="qianfan_model_select"
            )

            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] Qianfan model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] Qianfan model saved: {llm_model}")

            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
        elif llm_provider == "openai":
             openai_options = [
                 "gpt-4o",
                 "gpt-4o-mini",
                 "gpt-4-turbo",
                 "gpt-4",
                 "gpt-3.5-turbo"
             ]

             # 获取当前选择的索引
             current_index = 0
             if st.session_state.llm_model in openai_options:
                 current_index = openai_options.index(st.session_state.llm_model)

             llm_model = st.selectbox(
                 "Select an OpenAI model",
                 options=openai_options,
                 index=current_index,
                 format_func=lambda x: {
                     "gpt-4o": "GPT-4o - Latest flagship",
                     "gpt-4o-mini": "GPT-4o Mini - Lightweight flagship",
                     "gpt-4-turbo": "GPT-4 Turbo - Enhanced",
                     "gpt-4": "GPT-4 - Classic",
                     "gpt-3.5-turbo": "GPT-3.5 Turbo - Cost effective"
                 }[x],
                 help="Select the OpenAI model for analysis",
                 key="openai_model_select"
             )

             # Quick selection buttons
             st.markdown("**Quick Picks:**")

             col1, col2 = st.columns(2)
             with col1:
                 if st.button("🚀 GPT-4o", key="quick_gpt4o", use_container_width=True):
                     model_id = "gpt-4o"
                     st.session_state.llm_model = model_id
                     save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                     logger.debug(f"💾 [Persistence] Quick pick GPT-4o: {model_id}")
                     st.rerun()

             with col2:
                 if st.button("⚡ GPT-4o Mini", key="quick_gpt4o_mini", use_container_width=True):
                     model_id = "gpt-4o-mini"
                     st.session_state.llm_model = model_id
                     save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                     logger.debug(f"💾 [Persistence] Quick pick GPT-4o Mini: {model_id}")
                     st.rerun()

             # Update session state and persistence
             if st.session_state.llm_model != llm_model:
                 logger.debug(f"🔄 [Persistence] OpenAI model changed: {st.session_state.llm_model} → {llm_model}")
             st.session_state.llm_model = llm_model
             logger.debug(f"💾 [Persistence] OpenAI model saved: {llm_model}")

             # Save to persistent storage
             save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

             # OpenAI configuration hint
             st.info("💡 **OpenAI configuration**: Set OPENAI_API_KEY in your .env file")
        elif llm_provider == "custom_openai":
            st.markdown("### 🔧 Custom OpenAI Endpoint Configuration")

            # 初始化session state
            if 'custom_openai_base_url' not in st.session_state:
                st.session_state.custom_openai_base_url = "https://api.openai.com/v1"
            if 'custom_openai_api_key' not in st.session_state:
                st.session_state.custom_openai_api_key = ""

            # API端点URL配置
            base_url = st.text_input(
                "API endpoint URL",
                value=st.session_state.custom_openai_base_url,
                placeholder="https://api.openai.com/v1",
                help="Enter the OpenAI-compatible API endpoint URL, such as a relay service or local deployment",
                key="custom_openai_base_url_input"
            )

            # 更新session state
            st.session_state.custom_openai_base_url = base_url

            # API密钥配置
            api_key = st.text_input(
                "API key",
                value=st.session_state.custom_openai_api_key,
                type="password",
                placeholder="sk-...",
                help="Enter the API key, or set CUSTOM_OPENAI_API_KEY in the .env file",
                key="custom_openai_api_key_input"
            )

            # 更新session state
            st.session_state.custom_openai_api_key = api_key
            
            # 模型选择
            custom_openai_options = [
                "gpt-4o",
                "gpt-4o-mini", 
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
                "claude-3.5-sonnet",
                "claude-3-opus",
                "claude-3-sonnet",
                "claude-3-haiku",
                "gemini-pro",
                "gemini-1.5-pro",
                "llama-3.1-8b",
                "llama-3.1-70b",
                "llama-3.1-405b",
                "custom-model"
            ]
            
            # 获取当前选择的索引
            current_index = 0
            if st.session_state.llm_model in custom_openai_options:
                current_index = custom_openai_options.index(st.session_state.llm_model)
            
            llm_model = st.selectbox(
                "Select a model",
                options=custom_openai_options,
                index=current_index,
                format_func=lambda x: {
                    "gpt-4o": "GPT-4o - OpenAI flagship",
                    "gpt-4o-mini": "GPT-4o Mini - Lightweight flagship",
                    "gpt-4-turbo": "GPT-4 Turbo - Enhanced",
                    "gpt-4": "GPT-4 - Classic",
                    "gpt-3.5-turbo": "GPT-3.5 Turbo - Budget friendly",
                    "claude-3.5-sonnet": "Claude 3.5 Sonnet - Anthropic flagship",
                    "claude-3-opus": "Claude 3 Opus - High performance",
                    "claude-3-sonnet": "Claude 3 Sonnet - Balanced",
                    "claude-3-haiku": "Claude 3 Haiku - Fast",
                    "gemini-pro": "Gemini Pro - Google AI",
                    "gemini-1.5-pro": "Gemini 1.5 Pro - Enhanced",
                    "llama-3.1-8b": "Llama 3.1 8B - Meta open source",
                    "llama-3.1-70b": "Llama 3.1 70B - Large open source",
                    "llama-3.1-405b": "Llama 3.1 405B - Extra large open source",
                    "custom-model": "Custom model name"
                }[x],
                help="Choose which model to use. Supports any OpenAI-compatible model name",
                key="custom_openai_model_select"
            )

            # 如果选择了自定义模型，显示输入框
            if llm_model == "custom-model":
                custom_model_name = st.text_input(
                    "Custom model name",
                    value="",
                    placeholder="e.g.: gpt-4-custom, claude-3.5-sonnet-custom",
                    help="Enter the custom model identifier",
                    key="custom_model_name_input"
                )
                if custom_model_name:
                    llm_model = custom_model_name

            # Update session state and persistence
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] Custom OpenAI model changed: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] Custom OpenAI model saved: {llm_model}")

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

            # Quick endpoint presets
            st.markdown("**🚀 Quick endpoint presets:**")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🌐 OpenAI Official", key="quick_openai_official", use_container_width=True):
                    st.session_state.custom_openai_base_url = "https://api.openai.com/v1"
                    st.rerun()

                if st.button("🇨🇳 OpenAI Relay 1", key="quick_openai_relay1", use_container_width=True):
                    st.session_state.custom_openai_base_url = "https://api.openai-proxy.com/v1"
                    st.rerun()

            with col2:
                if st.button("🏠 Local deployment", key="quick_local_deploy", use_container_width=True):
                    st.session_state.custom_openai_base_url = "http://localhost:8000/v1"
                    st.rerun()
                
                if st.button("🇨🇳 OpenAI Relay 2", key="quick_openai_relay2", use_container_width=True):
                    st.session_state.custom_openai_base_url = "https://api.openai-sb.com/v1"
                    st.rerun()
            
            # 配置验证
            if base_url and api_key:
                st.success("✅ Configuration saved")
                st.info(f"**Endpoint**: `{base_url}`")
                st.info(f"**Model**: `{llm_model}`")
            elif base_url:
                st.warning("⚠️ Please enter an API key")
            else:
                st.warning("⚠️ Please configure the API endpoint URL and key")
            
            # 配置说明
            st.markdown("""
            **📖 Configuration guide:**
            - **API endpoint URL**: The base URL of an OpenAI-compatible service
            - **API key**: The API key for the selected service
            - **Model**: Choose or enter a model name

            **🔧 Supported service types:**
            - Official OpenAI API
            - OpenAI relay services
            - Self-hosted OpenAI-compatible services
            - Any other API that follows the OpenAI format
            """)
        else:  # openrouter
            # OpenRouter model category selection
            model_category = st.selectbox(
                "Model category",
                options=["openai", "anthropic", "meta", "google", "custom"],
                index=["openai", "anthropic", "meta", "google", "custom"].index(st.session_state.model_category) if st.session_state.model_category in ["openai", "anthropic", "meta", "google", "custom"] else 0,
                format_func=lambda x: {
                    "openai": "🤖 OpenAI (GPT series)",
                    "anthropic": "🧠 Anthropic (Claude series)",
                    "meta": "🦙 Meta (Llama series)",
                    "google": "🌟 Google (Gemini series)",
                    "custom": "✏️ Custom model"
                }[x],
                help="Select a vendor family or enter a custom model",
                key="model_category_select"
            )

            # Update session state and persistence
            if st.session_state.model_category != model_category:
                logger.debug(f"🔄 [Persistence] Model category changed: {st.session_state.model_category} → {model_category}")
                st.session_state.llm_model = ""  # Reset model selection when category changes
            st.session_state.model_category = model_category

            # Save to persistent storage
            save_model_selection(st.session_state.llm_provider, model_category, st.session_state.llm_model)

            # Display different models based on vendor
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
                    "Select an OpenAI model",
                    options=openai_options,
                    index=current_index,
                    format_func=lambda x: {
                        "openai/o4-mini-high": "🚀 o4 Mini High - Latest o4 series",
                        "openai/o3-pro": "🚀 o3 Pro - Latest pro reasoning",
                        "openai/o3-mini-high": "o3 Mini High - High-performance reasoning",
                        "openai/o3-mini": "o3 Mini - Reasoning model",
                        "openai/o1-pro": "o1 Pro - Professional reasoning",
                        "openai/o1-mini": "o1 Mini - Lightweight reasoning",
                        "openai/gpt-4o-2024-11-20": "GPT-4o (2024-11-20) - Latest release",
                        "openai/gpt-4o-mini": "GPT-4o Mini - Lightweight flagship",
                        "openai/gpt-4-turbo": "GPT-4 Turbo - Enhanced classic",
                        "openai/gpt-3.5-turbo": "GPT-3.5 Turbo - Budget friendly"
                    }[x],
                    help="OpenAI GPT and o-series models, including the latest o4",
                    key="openai_model_select"
                )

                # Update session state and persistence
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] OpenAI model changed: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] OpenAI model saved: {llm_model}")

                # Save to persistent storage
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
                    "Select an Anthropic model",
                    options=anthropic_options,
                    index=current_index,
                    format_func=lambda x: {
                        "anthropic/claude-opus-4": "🚀 Claude Opus 4 - Latest flagship",
                        "anthropic/claude-sonnet-4": "🚀 Claude Sonnet 4 - Latest balanced",
                        "anthropic/claude-haiku-4": "🚀 Claude Haiku 4 - Latest fast",
                        "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet - Current flagship",
                        "anthropic/claude-3.5-haiku": "Claude 3.5 Haiku - Rapid responses",
                        "anthropic/claude-3.5-sonnet-20241022": "Claude 3.5 Sonnet (2024-10-22)",
                        "anthropic/claude-3.5-haiku-20241022": "Claude 3.5 Haiku (2024-10-22)",
                        "anthropic/claude-3-opus": "Claude 3 Opus - Powerful performance",
                        "anthropic/claude-3-sonnet": "Claude 3 Sonnet - Balanced",
                        "anthropic/claude-3-haiku": "Claude 3 Haiku - Efficient"
                    }[x],
                    help="Anthropic Claude series models, including the latest Claude 4",
                    key="anthropic_model_select"
                )

                # Update session state and persistence
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Anthropic model changed: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Anthropic model saved: {llm_model}")

                # Save to persistent storage
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
                    "Select a Meta model",
                    options=meta_options,
                    index=current_index,
                    format_func=lambda x: {
                        "meta-llama/llama-4-maverick": "🚀 Llama 4 Maverick - Latest flagship",
                        "meta-llama/llama-4-scout": "🚀 Llama 4 Scout - Latest preview",
                        "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B - Powerful",
                        "meta-llama/llama-3.2-90b-vision-instruct": "Llama 3.2 90B Vision - Multimodal",
                        "meta-llama/llama-3.1-405b-instruct": "Llama 3.1 405B - Extra large",
                        "meta-llama/llama-3.1-70b-instruct": "Llama 3.1 70B - Balanced",
                        "meta-llama/llama-3.2-11b-vision-instruct": "Llama 3.2 11B Vision - Lightweight multimodal",
                        "meta-llama/llama-3.1-8b-instruct": "Llama 3.1 8B - Efficient",
                        "meta-llama/llama-3.2-3b-instruct": "Llama 3.2 3B - Lightweight",
                        "meta-llama/llama-3.2-1b-instruct": "Llama 3.2 1B - Ultra light"
                    }[x],
                    help="Meta Llama series models, including the latest Llama 4",
                    key="meta_model_select"
                )

                # Update session state and persistence
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Meta model changed: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Meta model saved: {llm_model}")

                # Save to persistent storage
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)
            elif model_category == "google":
                google_openrouter_options = [
                    "google/gemini-2.5-pro",
                    "google/gemini-2.5-flash",
                    "google/gemini-2.5-flash-lite",
                    "google/gemini-2.5-pro-002",
                    "google/gemini-2.5-flash-002",
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
                    "Select a Google model",
                    options=google_openrouter_options,
                    index=current_index,
                    format_func=lambda x: {
                        "google/gemini-2.5-pro": "🚀 Gemini 2.5 Pro - Latest flagship",
                        "google/gemini-2.5-flash": "⚡ Gemini 2.5 Flash - Latest fast",
                        "google/gemini-2.5-flash-lite": "💡 Gemini 2.5 Flash Lite - Lightweight",
                        "google/gemini-2.5-pro-002": "🔧 Gemini 2.5 Pro-002 - Optimized",
                        "google/gemini-2.5-flash-002": "⚡ Gemini 2.5 Flash-002 - Optimized speed",
                        "google/gemini-2.0-flash-001": "Gemini 2.0 Flash - Stable",
                        "google/gemini-2.0-flash-lite-001": "Gemini 2.0 Flash Lite",
                        "google/gemini-1.5-pro": "Gemini 1.5 Pro - Professional",
                        "google/gemini-1.5-flash": "Gemini 1.5 Flash - Fast",
                        "google/gemma-3-27b-it": "Gemma 3 27B - Latest open-source large",
                        "google/gemma-3-12b-it": "Gemma 3 12B - Open-source mid-size",
                        "google/gemma-2-27b-it": "Gemma 2 27B - Open-source classic"
                    }[x],
                    help="Google Gemini and Gemma models, including the latest Gemini 2.5",
                    key="google_openrouter_model_select"
                )

                # Update session state and persistence
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Google OpenRouter model changed: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Google OpenRouter model saved: {llm_model}")

                # Save to persistent storage
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

            else:  # custom
                st.markdown("### ✏️ Custom model")

                # Initialize custom model session state
                if 'custom_model' not in st.session_state:
                    st.session_state.custom_model = ""

                # Custom model input - use session state as default value
                default_value = st.session_state.custom_model if st.session_state.custom_model else "anthropic/claude-3.7-sonnet"

                llm_model = st.text_input(
                    "Enter model ID",
                    value=default_value,
                    placeholder="e.g.: anthropic/claude-3.7-sonnet",
                    help="Enter any model ID supported by OpenRouter",
                    key="custom_model_input"
                )

                # Quick selection of popular models
                st.markdown("**Quick select popular models:**")

                # Full-width buttons, one per row
                if st.button("🧠 Claude 3.7 Sonnet - Latest conversational model", key="claude37", use_container_width=True):
                    model_id = "anthropic/claude-3.7-sonnet"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] Quick select Claude 3.7 Sonnet: {model_id}")
                    st.rerun()

                if st.button("💎 Claude 4 Opus - Top performance model", key="claude4opus", use_container_width=True):
                    model_id = "anthropic/claude-opus-4"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] Quick select Claude 4 Opus: {model_id}")
                    st.rerun()

                if st.button("🤖 GPT-4o - OpenAI flagship model", key="gpt4o", use_container_width=True):
                    model_id = "openai/gpt-4o"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] Quick select GPT-4o: {model_id}")
                    st.rerun()

                if st.button("🦙 Llama 4 Scout - Latest Meta model", key="llama4", use_container_width=True):
                    model_id = "meta-llama/llama-4-scout"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] Quick select Llama 4 Scout: {model_id}")
                    st.rerun()

                if st.button("🌟 Gemini 2.5 Pro - Google multimodal", key="gemini25", use_container_width=True):
                    model_id = "google/gemini-2.5-pro"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(st.session_state.llm_provider, st.session_state.model_category, model_id)
                    logger.debug(f"💾 [Persistence] Quick select Gemini 2.5 Pro: {model_id}")
                    st.rerun()

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Custom model changed: {st.session_state.llm_model} → {llm_model}")
                st.session_state.custom_model = llm_model
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Custom model saved: {llm_model}")

                # Save to persistent storage
                save_model_selection(st.session_state.llm_provider, st.session_state.model_category, llm_model)

                # Model validation hints
                if llm_model:
                    st.success(f"✅ Current model: `{llm_model}`")

                    # Provide helpful links
                    st.markdown("""
                    **📚 Explore more models:**
                    - [OpenRouter model list](https://openrouter.ai/models)
                    - [Anthropic model docs](https://docs.anthropic.com/claude/docs/models-overview)
                    - [OpenAI model docs](https://platform.openai.com/docs/models)
                    """)
                else:
                    st.warning("⚠️ Please enter a valid model ID")

            # OpenRouter special note
            st.info("💡 **OpenRouter setup**: Set OPENROUTER_API_KEY in the .env file, or use OPENAI_API_KEY if you only rely on OpenRouter")
        
        # Advanced settings
        with st.expander("⚙️ Advanced settings"):
            enable_memory = st.checkbox(
                "Enable memory",
                value=False,
                help="Enable agent memory (may impact performance)"
            )

            enable_debug = st.checkbox(
                "Debug mode",
                value=False,
                help="Enable verbose debug output"
            )

            max_tokens = st.slider(
                "Maximum output length",
                min_value=1000,
                max_value=8000,
                value=4000,
                step=500,
                help="Maximum number of output tokens for the AI model"
            )

        st.markdown("---")

        # System configuration
        st.markdown("**🔧 System configuration**")

        # API key status
        st.markdown("**🔑 API key status**")

        def validate_api_key(key, expected_format):
            """Validate API key format."""
            if not key:
                return "Not configured", "error"

            if expected_format == "dashscope" and key.startswith("sk-") and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "deepseek" and key.startswith("sk-") and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "finnhub" and len(key) >= 20:
                return f"{key[:8]}...", "success"
            elif expected_format == "tushare" and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "google" and key.startswith("AIza") and len(key) >= 32:
                return f"{key[:8]}...", "success"
            elif expected_format == "openai" and key.startswith("sk-") and len(key) >= 40:
                return f"{key[:8]}...", "success"
            elif expected_format == "anthropic" and key.startswith("sk-") and len(key) >= 40:
                return f"{key[:8]}...", "success"
            elif expected_format == "reddit" and len(key) >= 10:
                return f"{key[:8]}...", "success"
            else:
                return f"{key[:8]}... (unexpected format)", "warning"

        # Required API keys
        st.markdown("*Required configuration:*")

        # Alibaba Bailian
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        status, level = validate_api_key(dashscope_key, "dashscope")
        if level == "success":
            st.success(f"✅ Alibaba Bailian: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Alibaba Bailian: {status}")
        else:
            st.error("❌ Alibaba Bailian: Not configured")

        # FinnHub
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        status, level = validate_api_key(finnhub_key, "finnhub")
        if level == "success":
            st.success(f"✅ FinnHub: {status}")
        elif level == "warning":
            st.warning(f"⚠️ FinnHub: {status}")
        else:
            st.error("❌ FinnHub: Not configured")

        # Optional API keys
        st.markdown("*Optional configuration:*")

        # DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        status, level = validate_api_key(deepseek_key, "deepseek")
        if level == "success":
            st.success(f"✅ DeepSeek: {status}")
        elif level == "warning":
            st.warning(f"⚠️ DeepSeek: {status}")
        else:
            st.info("ℹ️ DeepSeek: Not configured")

        # Tushare
        tushare_key = os.getenv("TUSHARE_TOKEN")
        status, level = validate_api_key(tushare_key, "tushare")
        if level == "success":
            st.success(f"✅ Tushare: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Tushare: {status}")
        else:
            st.info("ℹ️ Tushare: Not configured")

        # Google AI
        google_key = os.getenv("GOOGLE_API_KEY")
        status, level = validate_api_key(google_key, "google")
        if level == "success":
            st.success(f"✅ Google AI: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Google AI: {status}")
        else:
            st.info("ℹ️ Google AI: Not configured")

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

        # System information
        st.markdown("**ℹ️ System information**")

        st.info(f"""
        **Version**: {get_version()}
        **Framework**: Streamlit + LangGraph
        **AI model**: {st.session_state.llm_provider.upper()} - {st.session_state.llm_model}
        **Data sources**: Tushare + FinnHub API
        """)

        # Admin utilities
        if auth_manager and auth_manager.check_permission("admin"):
            st.markdown("---")
            st.markdown("### 🔧 Admin tools")

            if st.button("📊 User activity log", key="user_activity_btn", use_container_width=True):
                st.session_state.page = "user_activity"

            if st.button("⚙️ System settings", key="system_settings_btn", use_container_width=True):
                st.session_state.page = "system_settings"

        # Help links
        st.markdown("**📚 Help resources**")

        st.markdown("""
        - [📖 User guide](https://github.com/TauricResearch/TradingAgents)
        - [🐛 Issue tracker](https://github.com/TauricResearch/TradingAgents/issues)
        - [💬 Community discussions](https://github.com/TauricResearch/TradingAgents/discussions)
        - [🔧 API key configuration](../docs/security/api_keys_security.md)
        """)

    # Ensure we return session state values rather than local variables
    final_provider = st.session_state.llm_provider
    final_model = st.session_state.llm_model

    logger.debug(f"🔄 [Session State] Returning config - provider: {final_provider}, model: {final_model}")

    return {
        'llm_provider': final_provider,
        'llm_model': final_model,
        'enable_memory': enable_memory,
        'enable_debug': enable_debug,
        'max_tokens': max_tokens
    }
