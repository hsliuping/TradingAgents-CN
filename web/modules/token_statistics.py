#!/usr/bin/env python3
"""
Token usage statistics page

Display Token usage, cost analysis, and charts
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Any

# Add project root to path
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import UI utility functions
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.ui_utils import apply_hide_deploy_button_css

from tradingagents.config.config_manager import config_manager, token_tracker, UsageRecord

def render_token_statistics():
    """Render Token statistics page"""
    # Apply CSS for hiding Deploy button
    apply_hide_deploy_button_css()
    
    st.markdown("**💰 Token usage statistics and cost analysis**")
    
    # Sidebar controls
    with st.sidebar:
        st.subheader("📊 Statistics Settings")
        
        # Time range selection
        time_range = st.selectbox(
            "Statistics time range",
            ["Today", "Last 7 Days", "Last 30 Days", "Last 90 Days", "All"],
            index=2
        )
        
        # Convert to days
        days_map = {
            "Today": 1,
            "Last 7 Days": 7,
            "Last 30 Days": 30,
            "Last 90 Days": 90,
            "All": 365  # Use one year as "All"
        }
        days = days_map[time_range]
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
        
        # Export data button
        if st.button("📥 Export Statistics Data", use_container_width=True):
            export_statistics_data(days)
    
    # Get statistics data
    try:
        stats = config_manager.get_usage_statistics(days)
        records = load_detailed_records(days)
        
        if not stats or stats.get('total_requests', 0) == 0:
            st.info(f"📊 No Token usage records found for {time_range}")
            st.markdown("""
            ### 💡 How to start recording Token usage?
            
            1. **Perform stock analysis**: Use the stock analysis feature on the homepage
            2. **Ensure API configuration**: Check if the DashScope API key is correctly configured
            3. **Enable cost tracking**: Enable Token cost tracking in the configuration management
            
            The system will automatically record all LLM call Token usage.
            """)
            return
        
        # Display overview statistics
        render_overview_metrics(stats, time_range)
        
        # Display detailed charts
        if records:
            render_detailed_charts(records, stats)
        
        # Display provider statistics
        render_provider_statistics(stats)
        
        # Display cost trends
        if records:
            render_cost_trends(records)
        
        # Display detailed records table
        render_detailed_records_table(records)
        
    except Exception as e:
        st.error(f"❌ Failed to get statistics data: {str(e)}")
        st.info("Please check your configuration file and data storage")

def render_overview_metrics(stats: Dict[str, Any], time_range: str):
    """Render overview metrics"""
    st.markdown(f"**📈 {time_range} Overview**")
    
    # Create metric cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Total Cost",
            value=f"¥{stats['total_cost']:.4f}",
            delta=None
        )
    
    with col2:
        st.metric(
            label="🔢 Total Calls",
            value=f"{stats['total_requests']:,}",
            delta=None
        )
    
    with col3:
        total_tokens = stats['total_input_tokens'] + stats['total_output_tokens']
        st.metric(
            label="📊 Total Tokens",
            value=f"{total_tokens:,}",
            delta=None
        )
    
    with col4:
        avg_cost = stats['total_cost'] / stats['total_requests'] if stats['total_requests'] > 0 else 0
        st.metric(
            label="📊 Average Cost per Call",
            value=f"¥{avg_cost:.4f}",
            delta=None
        )
    
    # Token usage distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            label="📥 Input Tokens",
            value=f"{stats['total_input_tokens']:,}",
            delta=f"{stats['total_input_tokens']/(stats['total_input_tokens']+stats['total_output_tokens'])*100:.1f}%"
        )
    
    with col2:
        st.metric(
            label="📤 Output Tokens",
            value=f"{stats['total_output_tokens']:,}",
            delta=f"{stats['total_output_tokens']/(stats['total_input_tokens']+stats['total_output_tokens'])*100:.1f}%"
        )

def render_detailed_charts(records: List[UsageRecord], stats: Dict[str, Any]):
    """Render detailed charts"""
    st.markdown("**📊 Detailed Analysis Charts**")
    
    # Token usage distribution pie chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🥧 Token Usage Distribution**")
        
        # Create pie chart data
        token_data = {
            'Token Type': ['Input Tokens', 'Output Tokens'],
            'Quantity': [stats['total_input_tokens'], stats['total_output_tokens']]
        }
        
        fig_pie = px.pie(
            values=token_data['Quantity'],
            names=token_data['Token Type'],
            title="Token Usage Distribution",
            color_discrete_sequence=['#FF6B6B', '#4ECDC4']
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.markdown("**📈 Cost vs Token Relationship**")
        
        # Create scatter plot
        df_records = pd.DataFrame([
            {
                'total_tokens': record.input_tokens + record.output_tokens,
                'cost': record.cost,
                'provider': record.provider,
                'model': record.model_name
            }
            for record in records
        ])
        
        if not df_records.empty:
            fig_scatter = px.scatter(
                df_records,
                x='total_tokens',
                y='cost',
                color='provider',
                hover_data=['model'],
                title="Cost vs Token Usage Relationship",
                labels={'total_tokens': 'Total Tokens', 'cost': 'Cost(¥)'}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

def render_provider_statistics(stats: Dict[str, Any]):
    """Render provider statistics"""
    st.markdown("**🏢 Provider Statistics**")
    
    provider_stats = stats.get('provider_stats', {})
    
    if not provider_stats:
        st.info("No provider statistics data available")
        return
    
    # Create provider comparison table
    provider_df = pd.DataFrame([
        {
            'Provider': provider,
            'Cost(¥)': f"{data['cost']:.4f}",
            'Calls': data['requests'],
            'Input Tokens': f"{data['input_tokens']:,}",
            'Output Tokens': f"{data['output_tokens']:,}",
            'Average Cost(¥)': f"{data['cost']/data['requests']:.4f}" if data['requests'] > 0 else "0.0000"
        }
        for provider, data in provider_stats.items()
    ])
    
    st.dataframe(provider_df, use_container_width=True)
    
    # Provider cost comparison chart
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost comparison bar chart
        cost_data = {provider: data['cost'] for provider, data in provider_stats.items()}
        fig_bar = px.bar(
            x=list(cost_data.keys()),
            y=list(cost_data.values()),
            title="Provider Cost Comparison",
            labels={'x': 'Provider', 'y': 'Cost(¥)'},
            color=list(cost_data.values()),
            color_continuous_scale='Viridis'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        # Call count comparison
        requests_data = {provider: data['requests'] for provider, data in provider_stats.items()}
        fig_requests = px.bar(
            x=list(requests_data.keys()),
            y=list(requests_data.values()),
            title="Provider Call Count Comparison",
            labels={'x': 'Provider', 'y': 'Call Count'},
            color=list(requests_data.values()),
            color_continuous_scale='Plasma'
        )
        st.plotly_chart(fig_requests, use_container_width=True)

def render_cost_trends(records: List[UsageRecord]):
    """Render cost trends chart"""
    st.markdown("**📈 Cost Trend Analysis**")
    
    # Aggregate data by date
    df_records = pd.DataFrame([
        {
            'date': datetime.fromisoformat(record.timestamp).date(),
            'cost': record.cost,
            'tokens': record.input_tokens + record.output_tokens,
            'provider': record.provider
        }
        for record in records
    ])
    
    if df_records.empty:
        st.info("No trend data available")
        return
    
    # Aggregate by date
    daily_stats = df_records.groupby('date').agg({
        'cost': 'sum',
        'tokens': 'sum'
    }).reset_index()
    
    # Create dual-axis chart
    fig = make_subplots(
        specs=[[{"secondary_y": True}]],
        subplot_titles=["Daily Cost and Token Usage Trend"]
    )
    
    # Add cost trend line
    fig.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['cost'],
            mode='lines+markers',
            name='Daily Cost(¥)',
            line=dict(color='#FF6B6B', width=3)
        ),
        secondary_y=False,
    )
    
    # Add Token usage trend line
    fig.add_trace(
        go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['tokens'],
            mode='lines+markers',
            name='Daily Token Count',
            line=dict(color='#4ECDC4', width=3)
        ),
        secondary_y=True,
    )
    
    # Set axis labels
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Cost(¥)", secondary_y=False)
    fig.update_yaxes(title_text="Token Count", secondary_y=True)
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

def render_detailed_records_table(records: List[UsageRecord]):
    """Render detailed records table"""
    st.markdown("**📋 Detailed Usage Records**")
    
    if not records:
        st.info("No detailed records available")
        return
    
    # Create record table
    records_df = pd.DataFrame([
        {
            'Time': datetime.fromisoformat(record.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'Provider': record.provider,
            'Model': record.model_name,
            'Input Tokens': record.input_tokens,
            'Output Tokens': record.output_tokens,
            'Total Tokens': record.input_tokens + record.output_tokens,
            'Cost(¥)': f"{record.cost:.4f}",
            'Session ID': record.session_id[:12] + '...' if len(record.session_id) > 12 else record.session_id,
            'Analysis Type': record.analysis_type
        }
        for record in sorted(records, key=lambda x: x.timestamp, reverse=True)
    ])
    
    # Paginate display
    page_size = 20
    total_records = len(records_df)
    total_pages = (total_records + page_size - 1) // page_size
    
    if total_pages > 1:
        page = st.selectbox(f"Page (Total {total_pages} pages, {total_records} records)", range(1, total_pages + 1))
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_records)
        display_df = records_df.iloc[start_idx:end_idx]
    else:
        display_df = records_df
    
    st.dataframe(display_df, use_container_width=True)

def load_detailed_records(days: int) -> List[UsageRecord]:
    """Load detailed records"""
    try:
        all_records = config_manager.load_usage_records()
        
        # Filter time range
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_records = []
        
        for record in all_records:
            try:
                record_date = datetime.fromisoformat(record.timestamp)
                if record_date >= cutoff_date:
                    filtered_records.append(record)
            except:
                continue
        
        return filtered_records
    except Exception as e:
        st.error(f"Failed to load records: {e}")
        return []

def export_statistics_data(days: int):
    """Export statistics data"""
    try:
        stats = config_manager.get_usage_statistics(days)
        records = load_detailed_records(days)
        
        # Create export data
        export_data = {
            'summary': stats,
            'detailed_records': [
                {
                    'timestamp': record.timestamp,
                    'provider': record.provider,
                    'model_name': record.model_name,
                    'input_tokens': record.input_tokens,
                    'output_tokens': record.output_tokens,
                    'cost': record.cost,
                    'session_id': record.session_id,
                    'analysis_type': record.analysis_type
                }
                for record in records
            ]
        }
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"token_statistics_{timestamp}.json"
        
        # Provide download
        st.download_button(
            label="📥 Download Statistics Data",
            data=json.dumps(export_data, ensure_ascii=False, indent=2),
            file_name=filename,
            mime="application/json"
        )
        
        st.success(f"✅ Statistics data ready for download: {filename}")
        
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")

def main():
    """Main function"""
    st.set_page_config(
        page_title="Token Statistics - TradingAgents",
        page_icon="💰",
        layout="wide"
    )
    
    render_token_statistics()

if __name__ == "__main__":
    main()