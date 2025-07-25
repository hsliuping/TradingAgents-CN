"""
侧边栏组件
"""

import streamlit as st
import os
import sys
from pathlib import Path

# 添加项目根目录到路径，以便导入config_manager
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.config.config_manager import config_manager

def render_sidebar():
    """渲染侧边栏配置"""

    with st.sidebar:
        # AI模型配置
        st.markdown("### 🧠 AI模型配置")

        # 加载并筛选启用的模型
        all_models = config_manager.load_models()
        enabled_models = [m for m in all_models if m.enabled]

        # 获取可用的供应商
        available_providers = sorted(list(set(m.provider for m in enabled_models)))
        
        # 默认选择
        default_provider = "dashscope" if "dashscope" in available_providers else (available_providers if available_providers else None)

        if not available_providers:
            st.error("没有可用的模型。请在“配置管理”页面添加并启用模型。")
            llm_provider = None
            llm_model = None
        else:
            # LLM提供商选择
            llm_provider = st.selectbox(
                "LLM提供商",
                options=available_providers,
                index=available_providers.index(default_provider) if default_provider in available_providers else 0,
                format_func=lambda x: x.capitalize(),
                help="选择AI模型提供商"
            )

            # 根据选择的提供商筛选模型
            models_for_provider = [m.model_name for m in enabled_models if m.provider == llm_provider]
            
            if not models_for_provider:
                st.error(f"提供商 {llm_provider} 下没有启用的模型。")
                llm_model = None
            else:
                # 模型选择
                llm_model = st.selectbox(
                    "模型版本",
                    options=models_for_provider,
                    index=0,
                    help=f"选择用于分析的 {llm_provider.capitalize()} 模型"
                )
        
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
            elif expected_format == "google" and key.startswith("AIza") and len(key) >= 32:
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
        **版本**: 1.0.0
        **框架**: Streamlit + LangGraph
        **AI模型**: {llm_provider.upper()} - {llm_model}
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
    
    return {
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'enable_memory': enable_memory,
        'enable_debug': enable_debug,
        'max_tokens': max_tokens
    }
