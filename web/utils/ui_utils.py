#!/usr/bin/env python3
"""
UI utility functions
Provide common UI components and styles
"""

import streamlit as st

def apply_hide_deploy_button_css():
    """
    Apply CSS styles to hide the Deploy button and toolbar
    Call this function on all pages to ensure consistent UI experience
    """
    st.markdown("""
    <style>
        /* Hide Streamlit top toolbar and Deploy button - multiple selectors for compatibility */
        .stAppToolbar {
            display: none !important;
        }
        
        header[data-testid="stHeader"] {
            display: none !important;
        }
        
        .stDeployButton {
            display: none !important;
        }
        
        /* New Streamlit Deploy button selector */
        [data-testid="stToolbar"] {
            display: none !important;
        }
        
        [data-testid="stDecoration"] {
            display: none !important;
        }
        
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
        
        /* Hide the entire top area */
        .stApp > header {
            display: none !important;
        }
        
        .stApp > div[data-testid="stToolbar"] {
            display: none !important;
        }
        
        /* Hide main menu button */
        #MainMenu {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* Hide footer */
        footer {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* Hide "Made with Streamlit" badge */
        .viewerBadge_container__1QSob {
            display: none !important;
        }
        
        /* Hide all possible toolbar elements */
        div[data-testid="stToolbar"] {
            display: none !important;
        }
        
        /* Hide all buttons in the top-right corner */
        .stApp > div > div > div > div > section > div {
            padding-top: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def apply_common_styles():
    """
    Apply common page styles
    Including hiding Deploy button and other beautification styles
    """
    # Hide Deploy button
    apply_hide_deploy_button_css()
    
    # Other common styles
    st.markdown("""
    <style>
        /* Apply styles */
        .main-header {
            background: linear-gradient(90deg, #1f77b4, #ff7f0e);
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            color: white;
            text-align: center;
        }
        
        .metric-card {
            background: #f0f2f6;
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #1f77b4;
            margin: 0.5rem 0;
        }
        
        .analysis-section {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 1rem 0;
        }
        
        .success-box {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .warning-box {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .error-box {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 1rem;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)