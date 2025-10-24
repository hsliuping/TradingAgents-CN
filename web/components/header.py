"""
Page header component.
"""

import streamlit as st

def render_header():
    """Render the page header."""
    
    # Main title
    st.markdown("""
    <div class="main-header">
        <h1>🚀 TradingAgents-CN Stock Analysis Platform</h1>
        <p>A multi-agent large language model framework for Chinese financial trading decisions</p>
    </div>
    """, unsafe_allow_html=True)

    # Feature highlights
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <h4>🤖 Agent Collaboration</h4>
            <p>Specialized analyst teams working together</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4>🇨🇳 Chinese Optimization</h4>
            <p>Models tuned for Chinese-speaking users</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h4>📊 Real-time Data</h4>
            <p>Access the latest stock market information</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h4>🎯 Professional Guidance</h4>
            <p>AI-powered investment decision insights</p>
        </div>
        """, unsafe_allow_html=True)

    # Divider
    st.markdown("---")
