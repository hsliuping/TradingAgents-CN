"""
Sidebar component
"""

import streamlit as st
import os

def render_sidebar():
    """Render sidebar configuration"""

    with st.sidebar:
        # AI model configuration
        st.markdown("### 🧠 AI Model Configuration")

        # LLM provider selection
        llm_provider = st.selectbox(
            "LLM Provider",
            options=["dashscope", "deepseek", "google"],
            index=0,
            format_func=lambda x: {
                "dashscope": "Alibaba Qwen",
                "deepseek": "DeepSeek V3",
                "google": "Google AI"
            }[x],
            help="Select the AI model provider"
        )

        # Show different model options based on provider
        if llm_provider == "dashscope":
            llm_model = st.selectbox(
                "Model Version",
                options=["qwen-turbo", "qwen-plus-latest", "qwen-max"],
                index=1,
                format_func=lambda x: {
                    "qwen-turbo": "Turbo - Fast",
                    "qwen-plus-latest": "Plus - Balanced",
                    "qwen-max": "Max - Strongest"
                }[x],
                help="Select the Alibaba Qwen model for analysis"
            )
        elif llm_provider == "deepseek":
            llm_model = st.selectbox(
                "Select DeepSeek Model",
                options=["deepseek-chat"],
                index=0,
                format_func=lambda x: {
                    "deepseek-chat": "DeepSeek Chat - General conversation model, suitable for stock analysis"
                }[x],
                help="Select the DeepSeek model for analysis"
            )
        elif llm_provider == "google":
            llm_model = st.selectbox(
                "Select Google Model",
                options=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
                index=0,
                format_func=lambda x: {
                    "gemini-2.0-flash": "Gemini 2.0 Flash (Recommended)",
                    "gemini-1.5-pro": "Gemini 1.5 Pro (Powerful)",
                    "gemini-1.5-flash": "Gemini 1.5 Flash (Fast)"
                }[x],
                help="Select the Google Gemini model for analysis"
            )

        # Memory and debug options
        enable_memory = st.checkbox("Enable Memory Function", value=True, help="Allow AI to learn and remember analysis history")
        enable_debug = st.checkbox("Debug Mode", value=False, help="Show detailed analysis process information")
        max_tokens = st.slider("Max Output Length", min_value=256, max_value=4096, value=1024, step=256, help="Control the detail level of AI responses")
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=0.7,
            step=0.05,
            help="Controls randomness/creativity of AI output"
        )

        st.markdown("---")

        # System info
        st.markdown("**ℹ️ System Information**")
        st.info(f"""
        **Version**: 1.0.0
        **Framework**: Streamlit + LangGraph
        **AI Model**: {llm_provider.upper()} - {llm_model}
        **Data Source**: Tushare + FinnHub API
        """)

        # Help links
        st.markdown("**📚 Help Resources**")
        st.markdown("""
        - [📖 Documentation](https://github.com/TauricResearch/TradingAgents)
        - [🐛 Report Issues](https://github.com/TauricResearch/TradingAgents/issues)
        - [💬 Discussion Community](https://github.com/TauricResearch/TradingAgents/discussions)
        - [🔧 API Key Configuration](../docs/security/api_keys_security.md)
        """)

    return {
        'llm_provider': llm_provider,
        'llm_model': llm_model,
        'enable_memory': enable_memory,
        'enable_debug': enable_debug,
        'max_tokens': max_tokens,
        'temperature': temperature
    }
