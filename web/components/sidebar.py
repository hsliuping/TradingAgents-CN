"""
侧边栏组件
"""

import streamlit as st
import os

def render_sidebar():
    """渲染侧边栏配置"""
    
    with st.sidebar:
        st.header("🔧 系统配置")
        
        # API密钥状态
        st.subheader("🔑 API密钥状态")
        
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        
        if dashscope_key:
            st.success(f"✅ 阿里百炼: {dashscope_key[:12]}...")
        else:
            st.error("❌ 阿里百炼: 未配置")
        
        if finnhub_key:
            st.success(f"✅ 金融数据: {finnhub_key[:12]}...")
        else:
            st.error("❌ 金融数据: 未配置")
        
        st.markdown("---")
        
        # AI模型配置
        st.subheader("🧠 AI模型配置")

        # LLM提供商选择
        llm_provider = st.selectbox(
            "选择LLM提供商",
            options=["dashscope", "deepseek", "google"],
            index=0,
            format_func=lambda x: {
                "dashscope": "阿里百炼 - 国产模型",
                "deepseek": "DeepSeek V3 - 高性价比模型",
                "google": "Google AI - Gemini模型"
            }[x],
            help="选择AI模型提供商"
        )

        # 根据提供商显示不同的模型选项
        if llm_provider == "dashscope":
            llm_model = st.selectbox(
                "选择阿里百炼模型",
                options=["qwen-turbo", "qwen-plus-latest", "qwen-max"],
                index=1,
                format_func=lambda x: {
                    "qwen-turbo": "通义千问 Turbo - 快速响应",
                    "qwen-plus-latest": "通义千问 Plus - 平衡性能",
                    "qwen-max": "通义千问 Max - 最强性能"
                }[x],
                help="选择用于分析的阿里百炼模型"
            )
        elif llm_provider == "deepseek":
            llm_model = st.selectbox(
                "选择DeepSeek模型",
                options=["deepseek-chat"],
                index=0,
                format_func=lambda x: {
                    "deepseek-chat": "DeepSeek Chat - 通用对话模型，适合股票分析"
                }[x],
                help="选择用于分析的DeepSeek模型"
            )
        else:  # google
            llm_model = st.selectbox(
                "选择Google模型",
                options=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
                index=0,
                format_func=lambda x: {
                    "gemini-2.0-flash": "Gemini 2.0 Flash - 推荐使用",
                    "gemini-1.5-pro": "Gemini 1.5 Pro - 强大性能",
                    "gemini-1.5-flash": "Gemini 1.5 Flash - 快速响应"
                }[x],
                help="选择用于分析的Google Gemini模型"
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
        
        # 系统信息
        st.subheader("ℹ️ 系统信息")
        
        st.info(f"""
        **版本**: 1.0.0
        **框架**: Streamlit + LangGraph
        **AI模型**: {llm_provider.upper()} - {llm_model}
        **数据源**: Tushare + FinnHub API
        """)
        
        # 帮助链接
        st.subheader("📚 帮助资源")
        
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
