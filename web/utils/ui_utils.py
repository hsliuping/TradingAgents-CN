#!/usr/bin/env python3
"""
UI工具函数
提供通用的UI组件和样式
"""

import streamlit as st

def apply_hide_deploy_button_css():
    """
    应用隐藏Deploy按钮和工具栏的CSS样式
    在所有页面中调用此函数以确保一致的UI体验
    """
    st.markdown("""
    <style>
        /* 隐藏Streamlit顶部工具栏和Deploy按钮 - 多种选择器确保兼容性 */
        .stAppToolbar {
            display: none !important;
        }
        
        header[data-testid="stHeader"] {
            display: none !important;
        }
        
        .stDeployButton {
            display: none !important;
        }
        
        /* 新版本Streamlit的Deploy按钮选择器 */
        [data-testid="stToolbar"] {
            display: none !important;
        }
        
        [data-testid="stDecoration"] {
            display: none !important;
        }
        
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
        
        /* 隐藏整个顶部区域 */
        .stApp > header {
            display: none !important;
        }
        
        .stApp > div[data-testid="stToolbar"] {
            display: none !important;
        }
        
        /* 隐藏主菜单按钮 */
        #MainMenu {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* 隐藏页脚 */
        footer {
            visibility: hidden !important;
            display: none !important;
        }
        
        /* 隐藏"Made with Streamlit"标识 */
        .viewerBadge_container__1QSob {
            display: none !important;
        }
        
        /* 隐藏所有可能的工具栏元素 */
        div[data-testid="stToolbar"] {
            display: none !important;
        }
        
        /* 隐藏右上角的所有按钮 */
        .stApp > div > div > div > div > section > div {
            padding-top: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def apply_common_styles():
    """
    应用通用的页面样式
    包括隐藏Deploy按钮和其他美化样式
    """
    # 隐藏Deploy按钮
    apply_hide_deploy_button_css()
    
    # 其他通用样式
    st.markdown("""
    <style>
        /* 应用样式 */
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