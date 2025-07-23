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
            options=["dashscope", "deepseek", "google", "openai"],
            index=0,
            format_func=lambda x: {
                "dashscope": "Alibaba Qwen",
                "deepseek": "DeepSeek V3",
                "google": "Google AI",
                "openai": "OpenAI"
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
        elif llm_provider == "openai":
            openai_models = [
                "gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"
            ]
            openai_model_labels = {
                "gpt-4o": "GPT-4o (Latest, Fastest, Most Capable)",
                "gpt-4-turbo": "GPT-4 Turbo",
                "gpt-4": "GPT-4 (Standard)",
                "gpt-3.5-turbo": "GPT-3.5 Turbo"
            }
            llm_model = st.selectbox(
                "Select OpenAI Model",
                options=openai_models,
                index=0,
                format_func=lambda x: openai_model_labels.get(x, x),
                help="Select the OpenAI model for analysis"
            )

        # Change to multiselect for memory and debug options
        memory_debug_options = st.multiselect(
            "Memory & Debug Options",
            ["Memory", "Debug"],
            default=["Memory"],
            help="Enable memory, debug mode, or both"
        )
        enable_memory = "Memory" in memory_debug_options
        enable_debug = "Debug" in memory_debug_options

        # Task presets with new names and tooltips
        task_presets = {
            "Creative": {"temperature": 1.2, "top_p": 0.9, "max_tokens": 500, "frequency_penalty": 0.8, "presence_penalty": 0.6},
            "Serious": {"temperature": 0.3, "top_p": 1.0, "max_tokens": 200, "frequency_penalty": 0.0, "presence_penalty": 0.0},
            "Brainstorm": {"temperature": 1.0, "top_p": 0.8, "max_tokens": 300, "frequency_penalty": 0.6, "presence_penalty": 1.0},
            "Summary": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 150, "frequency_penalty": 0.5, "presence_penalty": 0.3},
        }
        base_task_names = list(task_presets.keys())
        task_names = base_task_names + ["Custom"]
        task_tooltips = {
            "Creative": "Generate creative, narrative, or open-ended content.",
            "Serious": "Produce precise, factual, and technical explanations.",
            "Brainstorm": "Generate new ideas or explore possibilities.",
            "Summary": "Summarize information in a concise and balanced way.",
            "Custom": "Custom parameter settings."
        }

        # Use session state to allow auto-fill but also manual override
        if 'llm_params' not in st.session_state:
            st.session_state.llm_params = task_presets[base_task_names[0]].copy()
            st.session_state.last_task = base_task_names[0]

        # Detect if user is customizing (not matching preset)
        def is_custom(params, preset):
            return any(params[k] != preset[k] for k in preset)

        # Place Task Type selectbox above the LLM Parameters expander
        selected_task = st.selectbox(
            "Task Type",
            options=task_names,
            index=task_names.index(st.session_state.get('last_task', base_task_names[0])),
            help=task_tooltips.get(st.session_state.get('last_task', base_task_names[0]), "Choose the type of task for recommended LLM settings"),
            key="llm_task_type_selectbox",
            label_visibility="visible"
        )

        # Group all LLM parameter sliders into an expander for a cleaner UI
        with st.expander("LLM Parameters", expanded=True):
            # Custom CSS for compact Task Type selectbox
            st.markdown(
                """
                <style>
                .llm-task-type-label {
                    font-size: 0.95rem !important;
                    margin-bottom: 0.1rem !important;
                }
                div[data-testid=\"stSelectbox\"] > label.llm-task-type-label {
                    font-size: 0.95rem !important;
                    margin-bottom: 0.1rem !important;
                }
                div[data-testid=\"stSelectbox\"] > div > div {
                    min-height: 28px !important;
                    font-size: 0.95rem !important;
                    padding-top: 2px !important;
                    padding-bottom: 2px !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            # If a preset is selected (not Custom), update sliders to preset values
            if selected_task in base_task_names:
                if st.session_state.get('last_task') != selected_task or st.session_state.get('last_task') == 'Custom':
                    st.session_state.llm_params = task_presets[selected_task].copy()
                st.session_state.last_task = selected_task

            # Sliders for all parameters, initialized from session state
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.llm_params["temperature"],
                step=0.05,
                help="Controls randomness/creativity of AI output"
            )
            top_p = st.slider(
                "Top-P",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.llm_params["top_p"],
                step=0.01,
                help="Controls nucleus sampling for diversity"
            )
            max_tokens = st.slider(
                "Max Tokens",
                min_value=50,
                max_value=2000,
                value=st.session_state.llm_params["max_tokens"],
                step=10,
                help="Maximum number of tokens in the output"
            )
            frequency_penalty = st.slider(
                "Frequency Penalty",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.llm_params["frequency_penalty"],
                step=0.05,
                help="Penalizes repeated tokens in the output"
            )
            presence_penalty = st.slider(
                "Presence Penalty",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.llm_params["presence_penalty"],
                step=0.05,
                help="Penalizes new topic introduction in the output"
            )
            # Update session state if user changes any slider
            st.session_state.llm_params = {
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty
            }
            # If the selected task is not Custom, but the params don't match the preset, switch to Custom
            if selected_task in base_task_names and is_custom(st.session_state.llm_params, task_presets[selected_task]):
                st.session_state.last_task = 'Custom'
                selected_task = 'Custom'
            # If the selected task is Custom, keep the sliders as they are
            # (no action needed)

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
        'task_type': selected_task,
        'temperature': temperature,
        'top_p': top_p,
        'max_tokens': max_tokens,
        'frequency_penalty': frequency_penalty,
        'presence_penalty': presence_penalty
    }
