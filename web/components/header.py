"""
Header component for the page
"""

import streamlit as st

def render_header():
    """Render the page header"""
    
    # Main title
    st.markdown("""
    <div class="main-header">
        <h1>🚀 TradingAgents-CN Stock Analysis Platform</h1>
        <p>A multi-agent LLM-based financial trading decision framework</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature highlights
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h4>🤖 Multi-Agent Collaboration</h4>
            <p>Professional analyst team working together</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4>🇨🇳 Chinese Optimization</h4>
            <p>AI models optimized for Chinese users</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h4>📊 Real-Time Data</h4>
            <p>Get the latest stock market data</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h4>🎯 Professional Advice</h4>
            <p>AI-based investment decision recommendations</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Divider
    st.markdown("---")
