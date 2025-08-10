import streamlit as st
import json
from pathlib import Path
import os
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent # web/components/sidebar.py -> web/components -> web -> project_root
sys.path.insert(0, str(project_root))

# 导入自定义组件
from web.utils.persistence import load_model_selection, save_model_selection
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')


def load_models_from_config():
    """从 config/models.json 加载模型配置"""
    config_path = project_root / "config" / "models.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def render_sidebar():
    """渲染侧边栏配置"""
    models_config = load_models_from_config()

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
            st.session_state.llm_provider = saved_config.get('provider', 'dashscope')
            logger.debug(f"🔧 [Persistence] 恢复 llm_provider: {st.session_state.llm_provider}")
        if 'model_category' not in st.session_state:
            st.session_state.model_category = saved_config.get('category', 'openai')
            logger.debug(f"🔧 [Persistence] 恢复 model_category: {st.session_state.model_category}")
        if 'llm_model' not in st.session_state:
            st.session_state.llm_model = saved_config.get('model', '')
            logger.debug(f"🔧 [Persistence] 恢复 llm_model: {st.session_state.llm_model}")
        if 'memory_provider' not in st.session_state:
            st.session_state.memory_provider = saved_config.get('memory_provider')
            logger.debug(f"🔧 [Persistence] 恢复 memory_provider: {st.session_state.memory_provider}")
        if 'memory_model' not in st.session_state:
            st.session_state.memory_model = saved_config.get('memory_model')
            logger.debug(f"🔧 [Persistence] 恢复 memory_model: {st.session_state.memory_model}")

        # 显示当前session state状态（调试用）
        logger.debug(f"🔍 [Session State] 当前状态 - provider: {st.session_state.llm_provider}, category: {st.session_state.model_category}, model: {st.session_state.llm_model}")

        # AI模型配置
        st.markdown("### 🧠 AI模型配置")

        # LLM提供商选择
        provider_options = list(models_config.keys())
        provider_display = {
            "dashscope": "🇨🇳 阿里百炼",
            "deepseek": "🚀 DeepSeek V3",
            "google": "🌟 Google AI",
            "openrouter": "🌐 OpenRouter",
            "硅基流动": "🔥 硅基流动"
        }

        llm_provider = st.selectbox(
            "LLM提供商",
            options=provider_options,
            index=provider_options.index(st.session_state.llm_provider) if st.session_state.llm_provider in provider_options else 0,
            format_func=lambda x: provider_display.get(x, x),
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
            save_model_selection(
                llm_provider,
                st.session_state.model_category,
                "",
                st.session_state.get('memory_provider'),
                st.session_state.get('memory_model')
            )
        else:
            st.session_state.llm_provider = llm_provider

        # 根据提供商显示不同的模型选项
        if llm_provider == "openrouter":
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
            save_model_selection(
                st.session_state.llm_provider,
                model_category,
                st.session_state.llm_model,
                st.session_state.get('memory_provider'),
                st.session_state.get('memory_model')
            )

            # 根据厂商显示不同的模型
            if model_category == "openai":
                openai_models = models_config.get("openrouter", {}).get("openai", {})
                openai_options = list(openai_models.keys())

                current_index = 0
                if st.session_state.llm_model in openai_options:
                    current_index = openai_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择OpenAI模型",
                    options=openai_options,
                    index=current_index,
                    format_func=lambda x: openai_models.get(x, {}).get('description', x) if isinstance(openai_models.get(x), dict) else x,
                    help="OpenAI公司的GPT和o系列模型，包含最新o4",
                    key="openai_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] OpenAI模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] OpenAI模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(
                    st.session_state.llm_provider,
                    st.session_state.model_category,
                    llm_model,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
            elif model_category == "anthropic":
                anthropic_models = models_config.get("openrouter", {}).get("anthropic", {})
                anthropic_options = list(anthropic_models.keys())

                current_index = 0
                if st.session_state.llm_model in anthropic_options:
                    current_index = anthropic_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Anthropic模型",
                    options=anthropic_options,
                    index=current_index,
                    format_func=lambda x: anthropic_models.get(x, {}).get('description', x) if isinstance(anthropic_models.get(x), dict) else x,
                    help="Anthropic公司的Claude系列模型，包含最新Claude 4",
                    key="anthropic_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Anthropic模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Anthropic模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(
                    st.session_state.llm_provider,
                    st.session_state.model_category,
                    llm_model,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
            elif model_category == "meta":
                meta_models = models_config.get("openrouter", {}).get("meta", {})
                meta_options = list(meta_models.keys())

                current_index = 0
                if st.session_state.llm_model in meta_options:
                    current_index = meta_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Meta模型",
                    options=meta_options,
                    index=current_index,
                    format_func=lambda x: meta_models.get(x, {}).get('description', x) if isinstance(meta_models.get(x), dict) else x,
                    help="Meta公司的Llama系列模型，包含最新Llama 4",
                    key="meta_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Meta模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Meta模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(
                    st.session_state.llm_provider,
                    st.session_state.model_category,
                    llm_model,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
            elif model_category == "google":
                google_models = models_config.get("openrouter", {}).get("google", {})
                google_openrouter_options = list(google_models.keys())

                current_index = 0
                if st.session_state.llm_model in google_openrouter_options:
                    current_index = google_openrouter_options.index(st.session_state.llm_model)

                llm_model = st.selectbox(
                    "选择Google模型",
                    options=google_openrouter_options,
                    index=current_index,
                    format_func=lambda x: google_models.get(x, {}).get('description', x) if isinstance(google_models.get(x), dict) else x,
                    help="Google公司的Gemini/Gemma系列模型，包含最新Gemini 2.5",
                    key="google_openrouter_model_select"
                )

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] Google OpenRouter模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] Google OpenRouter模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(
                    st.session_state.llm_provider,
                    st.session_state.model_category,
                    llm_model,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )

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
                    save_model_selection(
                        st.session_state.llm_provider,
                        st.session_state.model_category,
                        model_id,
                        st.session_state.get('memory_provider'),
                        st.session_state.get('memory_model')
                    )
                    logger.debug(f"💾 [Persistence] 快速选择Claude 3.7 Sonnet: {model_id}")
                    st.rerun()

                if st.button("💎 Claude 4 Opus - 顶级性能模型", key="claude4opus", use_container_width=True):
                    model_id = "anthropic/claude-opus-4"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(
                        st.session_state.llm_provider,
                        st.session_state.model_category,
                        model_id,
                        st.session_state.get('memory_provider'),
                        st.session_state.get('memory_model')
                    )
                    logger.debug(f"💾 [Persistence] 快速选择Claude 4 Opus: {model_id}")
                    st.rerun()

                if st.button("🤖 GPT-4o - OpenAI旗舰模型", key="gpt4o", use_container_width=True):
                    model_id = "openai/gpt-4o"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(
                        st.session_state.llm_provider,
                        st.session_state.model_category,
                        model_id,
                        st.session_state.get('memory_provider'),
                        st.session_state.get('memory_model')
                    )
                    logger.debug(f"💾 [Persistence] 快速选择GPT-4o: {model_id}")
                    st.rerun()

                if st.button("🦙 Llama 4 Scout - Meta最新模型", key="llama4", use_container_width=True):
                    model_id = "meta-llama/llama-4-scout"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(
                        st.session_state.llm_provider,
                        st.session_state.model_category,
                        model_id,
                        st.session_state.get('memory_provider'),
                        st.session_state.get('memory_model')
                    )
                    logger.debug(f"💾 [Persistence] 快速选择Llama 4 Scout: {model_id}")
                    st.rerun()

                if st.button("🌟 Gemini 2.5 Pro - Google多模态", key="gemini25", use_container_width=True):
                    model_id = "google/gemini-2.5-pro"
                    st.session_state.custom_model = model_id
                    st.session_state.llm_model = model_id
                    save_model_selection(
                        st.session_state.llm_provider,
                        st.session_state.model_category,
                        model_id,
                        st.session_state.get('memory_provider'),
                        st.session_state.get('memory_model')
                    )
                    logger.debug(f"💾 [Persistence] 快速选择Gemini 2.5 Pro: {model_id}")
                    st.rerun()

                # 更新session state和持久化存储
                if st.session_state.llm_model != llm_model:
                    logger.debug(f"🔄 [Persistence] 自定义模型变更: {st.session_state.llm_model} → {llm_model}")
                st.session_state.custom_model = llm_model
                st.session_state.llm_model = llm_model
                logger.debug(f"💾 [Persistence] 自定义模型已保存: {llm_model}")

                # 保存到持久化存储
                save_model_selection(
                    st.session_state.llm_provider,
                    st.session_state.model_category,
                    llm_model,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )

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
        else:  # 处理其他提供商
            provider_models = models_config.get(llm_provider, {})
            model_options = list(provider_models.keys())

            current_index = 0
            if st.session_state.llm_model in model_options:
                current_index = model_options.index(st.session_state.llm_model)

            llm_model = st.selectbox(
                f"选择{llm_provider}模型",
                options=model_options,
                index=current_index,
                format_func=lambda x: provider_models.get(x, {}).get('description', x) if isinstance(provider_models.get(x), dict) else x,
                help=f"选择用于分析的{llm_provider}模型",
                key=f"{llm_provider}_model_select"
            )

            # 更新session state和持久化存储
            if st.session_state.llm_model != llm_model:
                logger.debug(f"🔄 [Persistence] {llm_provider}模型变更: {st.session_state.llm_model} → {llm_model}")
            st.session_state.llm_model = llm_model
            logger.debug(f"💾 [Persistence] {llm_provider}模型已保存: {llm_model}")

            # 保存到持久化存储
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                llm_model,
                st.session_state.get('memory_provider'),
                st.session_state.get('memory_model')
            )

        # 高级设置
        with st.expander("⚙️ 高级设置"):
            enable_memory = st.checkbox(
                "启用记忆功能",
                value=st.session_state.get('enable_memory', False),
                help="启用智能体记忆功能（可能影响性能）"
            )
            st.session_state.enable_memory = enable_memory

            # 矢量模型配置
            st.markdown("##### 🧠 矢量模型配置")

            # 矢量模型提供商 (复用主模型的provider_options和provider_display)
            # provider_options 和 provider_display 已在前面定义

            # 设置默认值，确保健壮性
            default_memory_provider = st.session_state.get('memory_provider')
            # 如果保存的值无效或不存在，则安全地回退到列表的第一个选项
            if not default_memory_provider or default_memory_provider not in provider_options:
                default_memory_provider = provider_options[0] if provider_options else None

            if default_memory_provider:
                memory_provider = st.selectbox(
                    "矢量模型提供商",
                    options=provider_options, # 复用主模型的选项
                    index=provider_options.index(default_memory_provider),
                    format_func=lambda x: provider_display.get(x, x), # 复用主模型的显示格式
                    help="为矢量模型选择一个提供商"
                )
            else:
                st.warning("⚠️ models.json中未配置任何模型提供商。")
                memory_provider = None
            st.session_state.memory_provider = memory_provider

            # 矢量模型名称 - 基于提供商恢复历史或按提供商默认
            provider_to_model = st.session_state.get('memory_models_by_provider', {})
            restored_memory_model = provider_to_model.get(memory_provider) if memory_provider else None
            # 提供商默认映射（可与后端文档一致）
            provider_defaults = {
                "dashscope": "text-embedding-v4",
                "deepseek": "text-embedding-v1",
                "openai": "text-embedding-3-small",
                "google": "embedding-001",
                "openrouter": "text-embedding-3",
                "硅基流动": "BAAI/bge-m3",
            }
            default_memory_model = restored_memory_model or provider_defaults.get(memory_provider, "text-embedding-v4")

            memory_model = st.text_input(
                "矢量模型名称",
                value=default_memory_model,
                placeholder="例如: text-embedding-v4",
                help="输入矢量模型的具体名称",
                key=f"memory_model_input_{memory_provider}"
            )
            st.session_state.memory_model = memory_model
            # 在修改时维护映射
            if memory_provider and memory_model:
                if 'memory_models_by_provider' not in st.session_state:
                    st.session_state['memory_models_by_provider'] = {}
                st.session_state['memory_models_by_provider'][memory_provider] = memory_model

            enable_debug = st.checkbox(
                "调试模式",
                value=st.session_state.get('enable_debug', False),
                help="启用详细的调试信息输出"
            )
            st.session_state.enable_debug = enable_debug

            max_tokens = st.slider(
                "最大输出长度",
                min_value=1000,
                max_value=8000,
                value=st.session_state.get('max_tokens', 4000),
                step=500,
                help="AI模型的最大输出token数量"
            )
            st.session_state.max_tokens = max_tokens

            # 保存所有高级设置
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                st.session_state.llm_model,
                memory_provider,
                memory_model
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
        st.markdown("**� 帮助资源**")

        st.markdown("""
        - [📖 使用文档](https://github.com/TauricResearch/TradingAgents)
        - [🐛 问题反馈](https://github.com/TauricResearch/TradingAgents/issues)
        - [💬 讨论社区](https://github.com/TauricResearch/TradingAgents/discussions)
        - [🔧 API密钥配置](../docs/security/api_keys_security.md)
        """)

    # 确保返回session state中的值，而不是局部变量
    final_provider = st.session_state.get('llm_provider')
    final_model = st.session_state.get('llm_model')
    final_memory_provider = st.session_state.get('memory_provider')
    final_memory_model = st.session_state.get('memory_model')

    logger.debug(f"� [Session State] 返回配置 - provider: {final_provider}, model: {final_model}, memory_provider: {final_memory_provider}, memory_model: {final_memory_model}")

    return {
        'llm_provider': final_provider,
        'llm_model': final_model,
        'enable_memory': st.session_state.get('enable_memory', False),
        'enable_debug': st.session_state.get('enable_debug', False),
        'max_tokens': st.session_state.get('max_tokens', 4000),
        'memory_provider': final_memory_provider,
        'memory_model': final_memory_model
    }
