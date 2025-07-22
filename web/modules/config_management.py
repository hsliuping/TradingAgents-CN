#!/usr/bin/env python3
"""
Configuration Management Page
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from typing import List

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import UI utility functions
sys.path.append(str(Path(__file__).parent.parent))
from utils.ui_utils import apply_hide_deploy_button_css

from tradingagents.config.config_manager import (
    config_manager, ModelConfig, PricingConfig
)


def render_config_management():
    """Render configuration management page"""
    # Apply CSS to hide Deploy button
    apply_hide_deploy_button_css()
    
    st.title("⚙️ Configuration Management")

    # Show .env config status
    render_env_status()

    # Sidebar function selection
    st.sidebar.title("Configuration Options")
    page = st.sidebar.selectbox(
        "Select Function",
        ["Model Configuration", "Pricing Settings", "Usage Statistics", "System Settings"]
    )
    
    if page == "Model Configuration":
        render_model_config()
    elif page == "Pricing Settings":
        render_pricing_config()
    elif page == "Usage Statistics":
        render_usage_statistics()
    elif page == "System Settings":
        render_system_settings()


def render_model_config():
    """Render model configuration page"""
    st.markdown("**🤖 Model Configuration**")

    # Load existing configuration
    models = config_manager.load_models()

    # Display current configuration
    st.markdown("**Current Model Configuration**")
    
    if models:
        # Create DataFrame for display
        model_data = []
        env_status = config_manager.get_env_config_status()

        for i, model in enumerate(models):
            # Check API key source
            env_has_key = env_status["api_keys"].get(model.provider.lower(), False)
            api_key_display = "***" + model.api_key[-4:] if model.api_key else "Not set"
            if env_has_key:
                api_key_display += " (.env)"

            model_data.append({
                "Index": i,
                "Provider": model.provider,
                "Model Name": model.model_name,
                "API Key": api_key_display,
                "Max Tokens": model.max_tokens,
                "Temperature": model.temperature,
                "Status": "✅ Enabled" if model.enabled else "❌ Disabled"
            })
        
        df = pd.DataFrame(model_data)
        st.dataframe(df, use_container_width=True)
        
        # Edit model configuration
        st.markdown("**Edit Model Configuration**")
        
        # Select model to edit
        model_options = [f"{m.provider} - {m.model_name}" for m in models]
        selected_model_idx = st.selectbox("Select model to edit", range(len(model_options)),
                                         format_func=lambda x: model_options[x],
                                         key="select_model_to_edit")
        
        if selected_model_idx is not None:
            model = models[selected_model_idx]

            # Check if from .env
            env_has_key = env_status["api_keys"].get(model.provider.lower(), False)
            if env_has_key:
                st.info(f"💡 This model's API key comes from the .env file. Changes to the .env file require a restart of the application.")

            col1, col2 = st.columns(2)

            with col1:
                new_api_key = st.text_input("API Key", value=model.api_key, type="password", key=f"edit_api_key_{selected_model_idx}")
                if env_has_key:
                    st.caption("⚠️ This key comes from the .env file, Web modifications may be overwritten")
                new_max_tokens = st.number_input("Max Tokens", value=model.max_tokens, min_value=1000, max_value=32000, key=f"edit_max_tokens_{selected_model_idx}")
                new_temperature = st.slider("Temperature", 0.0, 2.0, model.temperature, 0.1, key=f"edit_temperature_{selected_model_idx}")

            with col2:
                new_enabled = st.checkbox("Enable Model", value=model.enabled, key=f"edit_enabled_{selected_model_idx}")
                new_base_url = st.text_input("Custom API Address (Optional)", value=model.base_url or "", key=f"edit_base_url_{selected_model_idx}")
            
            if st.button("Save Configuration", type="primary", key=f"save_model_config_{selected_model_idx}"):
                # Update model configuration
                models[selected_model_idx] = ModelConfig(
                    provider=model.provider,
                    model_name=model.model_name,
                    api_key=new_api_key,
                    base_url=new_base_url if new_base_url else None,
                    max_tokens=new_max_tokens,
                    temperature=new_temperature,
                    enabled=new_enabled
                )
                
                config_manager.save_models(models)
                st.success("✅ Configuration saved!")
                st.rerun()
    
    else:
        st.warning("No model configuration found")
    
    # Add new model
    st.markdown("**Add New Model**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_provider = st.selectbox("Provider", ["dashscope", "openai", "google", "anthropic", "other"], key="new_provider")
        new_model_name = st.text_input("Model Name", placeholder="e.g., gpt-4, qwen-plus-latest", key="new_model_name")
        new_api_key = st.text_input("API Key", type="password", key="new_api_key")

    with col2:
        new_max_tokens = st.number_input("Max Tokens", value=4000, min_value=1000, max_value=32000, key="new_max_tokens")
        new_temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1, key="new_temperature")
        new_enabled = st.checkbox("Enable Model", value=True, key="new_enabled")
    
    if st.button("Add Model", key="add_new_model"):
        if new_provider and new_model_name and new_api_key:
            new_model = ModelConfig(
                provider=new_provider,
                model_name=new_model_name,
                api_key=new_api_key,
                max_tokens=new_max_tokens,
                temperature=new_temperature,
                enabled=new_enabled
            )
            
            models.append(new_model)
            config_manager.save_models(models)
            st.success("✅ New model added!")
            st.rerun()
        else:
            st.error("Please fill in all required fields")


def render_pricing_config():
    """Render pricing configuration page"""
    st.markdown("**💰 Pricing Settings**")

    # Load existing pricing
    pricing_configs = config_manager.load_pricing()

    # Display current pricing
    st.markdown("**Current Pricing Configuration**")
    
    if pricing_configs:
        pricing_data = []
        for i, pricing in enumerate(pricing_configs):
            pricing_data.append({
                "Index": i,
                "Provider": pricing.provider,
                "Model Name": pricing.model_name,
                "Input Price (per 1K token)": f"{pricing.input_price_per_1k} {pricing.currency}",
                "Output Price (per 1K token)": f"{pricing.output_price_per_1k} {pricing.currency}",
                "Currency": pricing.currency
            })
        
        df = pd.DataFrame(pricing_data)
        st.dataframe(df, use_container_width=True)
        
        # Edit pricing
        st.markdown("**Edit Pricing**")
        
        pricing_options = [f"{p.provider} - {p.model_name}" for p in pricing_configs]
        selected_pricing_idx = st.selectbox("Select pricing to edit", range(len(pricing_options)),
                                          format_func=lambda x: pricing_options[x],
                                          key="select_pricing_to_edit")
        
        if selected_pricing_idx is not None:
            pricing = pricing_configs[selected_pricing_idx]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                new_input_price = st.number_input("Input Price (per 1K token)",
                                                value=pricing.input_price_per_1k,
                                                min_value=0.0, step=0.001, format="%.6f",
                                                key=f"edit_input_price_{selected_pricing_idx}")

            with col2:
                new_output_price = st.number_input("Output Price (per 1K token)",
                                                 value=pricing.output_price_per_1k,
                                                 min_value=0.0, step=0.001, format="%.6f",
                                                 key=f"edit_output_price_{selected_pricing_idx}")

            with col3:
                new_currency = st.selectbox("Currency", ["CNY", "USD", "EUR"],
                                          index=["CNY", "USD", "EUR"].index(pricing.currency),
                                          key=f"edit_currency_{selected_pricing_idx}")
            
            if st.button("Save Pricing", type="primary", key=f"save_pricing_config_{selected_pricing_idx}"):
                pricing_configs[selected_pricing_idx] = PricingConfig(
                    provider=pricing.provider,
                    model_name=pricing.model_name,
                    input_price_per_1k=new_input_price,
                    output_price_per_1k=new_output_price,
                    currency=new_currency
                )
                
                config_manager.save_pricing(pricing_configs)
                st.success("✅ Pricing saved!")
                st.rerun()
    
    # Add new pricing
    st.markdown("**Add New Pricing**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_provider = st.text_input("Provider", placeholder="e.g., openai, dashscope", key="new_pricing_provider")
        new_model_name = st.text_input("Model Name", placeholder="e.g., gpt-4, qwen-plus", key="new_pricing_model")
        new_currency = st.selectbox("Currency", ["CNY", "USD", "EUR"], key="new_pricing_currency")

    with col2:
        new_input_price = st.number_input("Input Price (per 1K token)", min_value=0.0, step=0.001, format="%.6f", key="new_pricing_input")
        new_output_price = st.number_input("Output Price (per 1K token)", min_value=0.0, step=0.001, format="%.6f", key="new_pricing_output")
    
    if st.button("Add Pricing", key="add_new_pricing"):
        if new_provider and new_model_name:
            new_pricing = PricingConfig(
                provider=new_provider,
                model_name=new_model_name,
                input_price_per_1k=new_input_price,
                output_price_per_1k=new_output_price,
                currency=new_currency
            )
            
            pricing_configs.append(new_pricing)
            config_manager.save_pricing(pricing_configs)
            st.success("✅ New pricing added!")
            st.rerun()
        else:
            st.error("Please fill in provider and model name")


def render_usage_statistics():
    """Render usage statistics page"""
    st.markdown("**📊 Usage Statistics**")

    # Time range selection
    col1, col2 = st.columns(2)
    with col1:
        days = st.selectbox("Time Range for Statistics", [7, 30, 90, 365], index=1, key="stats_time_range")
    with col2:
        st.metric("Statistical Period", f"Last {days} days")

    # Get statistical data
    stats = config_manager.get_usage_statistics(days)

    if stats["total_requests"] == 0:
        st.info("📝 No usage records yet")
        return

    # Overall statistics
    st.markdown("**📈 Overall Statistics**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cost", f"¥{stats['total_cost']:.4f}")
    
    with col2:
        st.metric("Total Requests", f"{stats['total_requests']:,}")
    
    with col3:
        st.metric("Input Tokens", f"{stats['total_input_tokens']:,}")
    
    with col4:
        st.metric("Output Tokens", f"{stats['total_output_tokens']:,}")
    
    # Provider statistics
    if stats["provider_stats"]:
        st.markdown("**🏢 Provider Statistics**")
        
        provider_data = []
        for provider, data in stats["provider_stats"].items():
            provider_data.append({
                "Provider": provider,
                "Cost": f"¥{data['cost']:.4f}",
                "Requests": data['requests'],
                "Input Tokens": f"{data['input_tokens']:,}",
                "Output Tokens": f"{data['output_tokens']:,}",
                "Average Cost/Request": f"¥{data['cost']/data['requests']:.6f}" if data['requests'] > 0 else "¥0"
            })
        
        df = pd.DataFrame(provider_data)
        st.dataframe(df, use_container_width=True)
        
        # Cost distribution pie chart
        if len(provider_data) > 1:
            fig = px.pie(
                values=[stats["provider_stats"][p]["cost"] for p in stats["provider_stats"]],
                names=list(stats["provider_stats"].keys()),
                title="Cost Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Usage trend
    st.markdown("**📈 Usage Trend**")
    
    records = config_manager.load_usage_records()
    if records:
        # Aggregate by date
        daily_stats = {}
        for record in records:
            try:
                date = datetime.fromisoformat(record.timestamp).date()
                if date not in daily_stats:
                    daily_stats[date] = {"cost": 0, "requests": 0}
                daily_stats[date]["cost"] += record.cost
                daily_stats[date]["requests"] += 1
            except:
                continue
        
        if daily_stats:
            dates = sorted(daily_stats.keys())
            costs = [daily_stats[date]["cost"] for date in dates]
            requests = [daily_stats[date]["requests"] for date in dates]
            
            # Create dual-axis chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=dates, y=costs,
                mode='lines+markers',
                name='Daily Cost (¥)',
                yaxis='y'
            ))
            
            fig.add_trace(go.Scatter(
                x=dates, y=requests,
                mode='lines+markers',
                name='Daily Requests',
                yaxis='y2'
            ))
            
            fig.update_layout(
                title='Usage Trend',
                xaxis_title='Date',
                yaxis=dict(title='Cost (¥)', side='left'),
                yaxis2=dict(title='Requests', side='right', overlaying='y'),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)


def render_system_settings():
    """Render system settings page"""
    st.markdown("**🔧 System Settings**")

    # Load current settings
    settings = config_manager.load_settings()

    st.markdown("**Basic Settings**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        default_provider = st.selectbox(
            "Default Provider",
            ["dashscope", "openai", "google", "anthropic"],
            index=["dashscope", "openai", "google", "anthropic"].index(
                settings.get("default_provider", "dashscope")
            ),
            key="settings_default_provider"
        )

        enable_cost_tracking = st.checkbox(
            "Enable Cost Tracking",
            value=settings.get("enable_cost_tracking", True),
            key="settings_enable_cost_tracking"
        )

        currency_preference = st.selectbox(
            "Preferred Currency",
            ["CNY", "USD", "EUR"],
            index=["CNY", "USD", "EUR"].index(
                settings.get("currency_preference", "CNY")
            ),
            key="settings_currency_preference"
        )
    
    with col2:
        default_model = st.text_input(
            "Default Model",
            value=settings.get("default_model", "qwen-turbo"),
            key="settings_default_model"
        )

        cost_alert_threshold = st.number_input(
            "Cost Alert Threshold",
            value=settings.get("cost_alert_threshold", 100.0),
            min_value=0.0,
            step=10.0,
            key="settings_cost_alert_threshold"
        )

        max_usage_records = st.number_input(
            "Max Usage Records",
            value=settings.get("max_usage_records", 10000),
            min_value=1000,
            max_value=100000,
            step=1000,
            key="settings_max_usage_records"
        )

    auto_save_usage = st.checkbox(
        "Auto-save Usage Records",
        value=settings.get("auto_save_usage", True),
        key="settings_auto_save_usage"
    )
    
    if st.button("Save Settings", type="primary", key="save_system_settings"):
        new_settings = {
            "default_provider": default_provider,
            "default_model": default_model,
            "enable_cost_tracking": enable_cost_tracking,
            "cost_alert_threshold": cost_alert_threshold,
            "currency_preference": currency_preference,
            "auto_save_usage": auto_save_usage,
            "max_usage_records": max_usage_records
        }
        
        config_manager.save_settings(new_settings)
        st.success("✅ Settings saved!")
        st.rerun()
    
    # Data Management
    st.markdown("**Data Management**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Export Config", help="Export all configurations to a JSON file", key="export_config"):
            # Implement configuration export functionality here
            st.info("Configuration export functionality under development...")
    
    with col2:
        if st.button("Clear Usage Records", help="Clear all usage records", key="clear_usage_records"):
            if st.session_state.get("confirm_clear", False):
                config_manager.save_usage_records([])
                st.success("✅ Usage records cleared!")
                st.session_state.confirm_clear = False
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning("⚠️ Click again to confirm clearing")
    
    with col3:
        if st.button("Reset Config", help="Reset all configurations to default values", key="reset_all_config"):
            if st.session_state.get("confirm_reset", False):
                # Delete config files, re-initialize
                import shutil
                if config_manager.config_dir.exists():
                    shutil.rmtree(config_manager.config_dir)
                config_manager._init_default_configs()
                st.success("✅ Config reset!")
                st.session_state.confirm_reset = False
                st.rerun()
            else:
                st.session_state.confirm_reset = True
                st.warning("⚠️ Click again to confirm resetting")


def render_env_status():
    """Display .env config status"""
    st.markdown("**📋 Config Status Overview**")

    # Get .env config status
    env_status = config_manager.get_env_config_status()

    # Display .env file status
    col1, col2 = st.columns(2)

    with col1:
        if env_status["env_file_exists"]:
            st.success("✅ .env file exists")
        else:
            st.error("❌ .env file does not exist")
            st.info("💡 Please copy .env.example to .env and configure API keys")

    with col2:
        # Count configured API keys
        configured_keys = sum(1 for configured in env_status["api_keys"].values() if configured)
        total_keys = len(env_status["api_keys"])
        st.metric("API Key Configuration", f"{configured_keys}/{total_keys}")

    # Detailed API key status
    with st.expander("🔑 Detailed API Key Status", expanded=False):
        api_col1, api_col2 = st.columns(2)

        with api_col1:
            st.write("**Large Model API Keys:**")
            for provider, configured in env_status["api_keys"].items():
                if provider in ["dashscope", "openai", "google", "anthropic"]:
                    status = "✅ Configured" if configured else "❌ Not Configured"
                    provider_name = {
                        "dashscope": "Ali BaiLian",
                        "openai": "OpenAI",
                        "google": "Google AI",
                        "anthropic": "Anthropic"
                    }.get(provider, provider)
                    st.write(f"- {provider_name}: {status}")

        with api_col2:
            st.write("**Other API Keys:**")
            finnhub_status = "✅ Configured" if env_status["api_keys"]["finnhub"] else "❌ Not Configured"
            st.write(f"- FinnHub (Financial Data): {finnhub_status}")

            reddit_status = "✅ Configured" if env_status["other_configs"]["reddit_configured"] else "❌ Not Configured"
            st.write(f"- Reddit API: {reddit_status}")

    # Config priority explanation
    st.info("""
    📌 **Config Priority Explanation:**
    - API keys are prioritized from the `.env` file
    - Web interface is a supplementary and management tool
    - Modifications to the `.env` file require a restart of the application
    - It is recommended to use the `.env` file to manage sensitive information
    """)

    st.divider()


def main():
    """Main function"""
    st.set_page_config(
        page_title="Configuration Management - TradingAgents",
        page_icon="⚙️",
        layout="wide"
    )
    
    render_config_management()

if __name__ == "__main__":
    main()
