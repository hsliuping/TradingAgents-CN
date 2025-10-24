#!/usr/bin/env python3
"""
TradingAgents-CN Streamlit web interface.
Streamlit-based stock analysis web application.
"""

import streamlit as st
import os
import sys
import json
from pathlib import Path
import datetime
import time
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入日志模块
try:
    from tradingagents.utils.logging_manager import get_logger
    logger = get_logger('web')
except ImportError:
    # 如果无法导入，使用标准logging
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('web')

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

# 导入自定义组件
from components.sidebar import render_sidebar
from components.header import render_header
from components.analysis_form import render_analysis_form
from components.results_display import render_results
from components.login import render_login_form, check_authentication, render_user_info, render_sidebar_user_info, render_sidebar_logout, require_permission
from components.user_activity_dashboard import render_user_activity_dashboard, render_activity_summary_widget
from utils.api_checker import check_api_keys
from utils.analysis_runner import run_stock_analysis, validate_analysis_params, format_analysis_results
from utils.progress_tracker import SmartStreamlitProgressDisplay, create_smart_progress_callback
from utils.async_progress_tracker import AsyncProgressTracker
from components.async_progress_display import display_unified_progress
from utils.smart_session_manager import get_persistent_analysis_id, set_persistent_analysis_id
from utils.auth_manager import auth_manager
from utils.user_activity_logger import user_activity_logger

# 设置页面配置
st.set_page_config(
    page_title="TradingAgents-CN Stock Analysis Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# 自定义CSS样式
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
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
    
    /* 全局样式 */
    .stApp {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* 主容器样式 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* 主标题样式 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .main-subtitle {
        font-size: 1.2rem;
        opacity: 0.9;
        font-weight: 400;
    }
    
    /* 卡片样式 */
    .metric-card {
        background: rgba(255, 255, 255, 0.9);
        padding: 1.5rem;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        margin: 0.5rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(20px);
        transition: all 0.3s ease;
        text-align: center;
    }
    
    .metric-card h4 {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }
    
    .metric-card p {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin: 0;
        font-size: 0.9rem;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
    }
    
    .analysis-section {
        background: rgba(255, 255, 255, 0.95);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        margin: 1.5rem 0;
        border: 1px solid rgba(255, 255, 255, 0.3);
        backdrop-filter: blur(20px);
    }
    
    /* 按钮样式 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* 输入框样式 */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.9);
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        background: white;
    }
    
    /* 侧边栏样式 */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
    }
    
    /* 状态框样式 */
    .success-box {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #9ae6b4;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(154, 230, 180, 0.3);
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        border: 1px solid #f6d55c;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(255, 234, 167, 0.3);
    }
    
    .error-box {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border: 1px solid #f1556c;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(245, 198, 203, 0.3);
    }
    
    /* 进度条样式 */
    .stProgress > div > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.7);
        border-radius: 12px;
        padding: 0.5rem 1rem;
        border: 1px solid rgba(255, 255, 255, 0.3);
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* 数据框样式 */
    .dataframe {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* 图表容器样式 */
    .js-plotly-plot {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """初始化会话状态"""
    # 初始化认证相关状态
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'login_time' not in st.session_state:
        st.session_state.login_time = None
    
    # 初始化分析相关状态
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'last_analysis_time' not in st.session_state:
        st.session_state.last_analysis_time = None
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None
    if 'form_config' not in st.session_state:
        st.session_state.form_config = None

    # 尝试从最新完成的分析中恢复结果
    if not st.session_state.analysis_results:
        try:
            from utils.async_progress_tracker import get_latest_analysis_id, get_progress_by_id
            from utils.analysis_runner import format_analysis_results

            latest_id = get_latest_analysis_id()
            if latest_id:
                progress_data = get_progress_by_id(latest_id)
                if (progress_data and
                    progress_data.get('status') == 'completed' and
                    'raw_results' in progress_data):

                    # 恢复分析结果
                    raw_results = progress_data['raw_results']
                    formatted_results = format_analysis_results(raw_results)

                    if formatted_results:
                        st.session_state.analysis_results = formatted_results
                        st.session_state.current_analysis_id = latest_id
                        # 检查分析状态
                        analysis_status = progress_data.get('status', 'completed')
                        st.session_state.analysis_running = (analysis_status == 'running')
                        # 恢复股票信息
                        if 'stock_symbol' in raw_results:
                            st.session_state.last_stock_symbol = raw_results.get('stock_symbol', '')
                        if 'market_type' in raw_results:
                            st.session_state.last_market_type = raw_results.get('market_type', '')
                        logger.info(f"📊 [结果恢复] 从分析 {latest_id} 恢复结果，状态: {analysis_status}")

        except Exception as e:
            logger.warning(f"⚠️ [结果恢复] 恢复失败: {e}")

    # 使用cookie管理器恢复分析ID（优先级：session state > cookie > Redis/文件）
    try:
        persistent_analysis_id = get_persistent_analysis_id()
        if persistent_analysis_id:
            # 使用线程检测来检查分析状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(persistent_analysis_id)

            # 只在状态变化时记录日志，避免重复
            current_session_status = st.session_state.get('last_logged_status')
            if current_session_status != actual_status:
                logger.info(f"📊 [状态检查] 分析 {persistent_analysis_id} 实际状态: {actual_status}")
                st.session_state.last_logged_status = actual_status

            if actual_status == 'running':
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = persistent_analysis_id
            elif actual_status in ['completed', 'failed']:
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = persistent_analysis_id
            else:  # not_found
                logger.warning(f"📊 [状态检查] 分析 {persistent_analysis_id} 未找到，清理状态")
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = None
    except Exception as e:
        # 如果恢复失败，保持默认值
        logger.warning(f"⚠️ [状态恢复] 恢复分析状态失败: {e}")
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None

    # 恢复表单配置
    try:
        from utils.smart_session_manager import smart_session_manager
        session_data = smart_session_manager.load_analysis_state()

        if session_data and 'form_config' in session_data:
            st.session_state.form_config = session_data['form_config']
            # 只在没有分析运行时记录日志，避免重复
            if not st.session_state.get('analysis_running', False):
                logger.info("📊 [配置恢复] 表单配置已恢复")
    except Exception as e:
        logger.warning(f"⚠️ [配置恢复] 表单配置恢复失败: {e}")

def check_frontend_auth_cache():
    """检查前端缓存并尝试恢复登录状态"""
    from utils.auth_manager import auth_manager
    
    logger.info("🔍 开始检查前端缓存恢复")
    logger.info(f"📊 当前认证状态: {st.session_state.get('authenticated', False)}")
    logger.info(f"🔗 URL参数: {dict(st.query_params)}")
    
    # 如果已经认证，确保状态同步
    if st.session_state.get('authenticated', False):
        # 确保auth_manager也知道用户已认证
        if not auth_manager.is_authenticated() and st.session_state.get('user_info'):
            logger.info("🔄 同步认证状态到auth_manager")
            try:
                auth_manager.login_user(
                    st.session_state.user_info, 
                    st.session_state.get('login_time', time.time())
                )
                logger.info("✅ 认证状态同步成功")
            except Exception as e:
                logger.warning(f"⚠️ 认证状态同步失败: {e}")
        else:
            logger.info("✅ 用户已认证，跳过缓存检查")
        return
    
    # 检查URL参数中是否有恢复信息
    try:
        import base64
        restore_data = st.query_params.get('restore_auth')
        
        if restore_data:
            logger.info("📥 发现URL中的恢复参数，开始恢复登录状态")
            # 解码认证数据
            auth_data = json.loads(base64.b64decode(restore_data).decode())
            
            # 兼容旧格式（直接是用户信息）和新格式（包含loginTime）
            if 'userInfo' in auth_data:
                user_info = auth_data['userInfo']
                # 使用当前时间作为新的登录时间，避免超时问题
                # 因为前端已经验证了lastActivity没有超时
                login_time = time.time()
            else:
                # 旧格式兼容
                user_info = auth_data
                login_time = time.time()
                
            logger.info(f"✅ 成功解码用户信息: {user_info.get('username', 'Unknown')}")
            logger.info(f"🕐 使用当前时间作为登录时间: {login_time}")
            
            # 恢复登录状态
            if auth_manager.restore_from_cache(user_info, login_time):
                # 清除URL参数
                del st.query_params['restore_auth']
                logger.info(f"✅ 从前端缓存成功恢复用户 {user_info['username']} 的登录状态")
                logger.info("🧹 已清除URL恢复参数")
                # 立即重新运行以应用恢复的状态
                logger.info("🔄 触发页面重新运行")
                st.rerun()
            else:
                logger.error("❌ 恢复登录状态失败")
                # 恢复失败，清除URL参数
                del st.query_params['restore_auth']
        else:
            # 如果没有URL参数，注入前端检查脚本
            logger.info("📝 没有URL恢复参数，注入前端检查脚本")
            inject_frontend_cache_check()
    except Exception as e:
        logger.warning(f"⚠️ 处理前端缓存恢复失败: {e}")
        # 如果恢复失败，清除可能损坏的URL参数
        if 'restore_auth' in st.query_params:
            del st.query_params['restore_auth']

def inject_frontend_cache_check():
    """注入前端缓存检查脚本"""
    logger.info("📝 准备注入前端缓存检查脚本")
    
    # 如果已经注入过，不重复注入
    if st.session_state.get('cache_script_injected', False):
        logger.info("⚠️ 前端脚本已注入，跳过重复注入")
        return
    
    # 标记已注入
    st.session_state.cache_script_injected = True
    logger.info("✅ 标记前端脚本已注入")
    
    cache_check_js = """
    <script>
    // 前端缓存检查和恢复
    function checkAndRestoreAuth() {
        console.log('🚀 开始执行前端缓存检查');
        console.log('📍 当前URL:', window.location.href);
        
        try {
            // 检查URL中是否已经有restore_auth参数
            const currentUrl = new URL(window.location);
            if (currentUrl.searchParams.has('restore_auth')) {
                console.log('🔄 URL中已有restore_auth参数，跳过前端检查');
                return;
            }
            
            const authData = localStorage.getItem('tradingagents_auth');
            console.log('🔍 检查localStorage中的认证数据:', authData ? '存在' : '不存在');
            
            if (!authData) {
                console.log('🔍 前端缓存中没有登录状态');
                return;
            }
            
            const data = JSON.parse(authData);
            console.log('📊 解析的认证数据:', data);
            
            // 验证数据结构
            if (!data.userInfo || !data.userInfo.username) {
                console.log('❌ 认证数据结构无效，清除缓存');
                localStorage.removeItem('tradingagents_auth');
                return;
            }
            
            const now = Date.now();
            const timeout = 10 * 60 * 1000; // 10分钟
            const timeSinceLastActivity = now - data.lastActivity;
            
            console.log('⏰ 时间检查:', {
                now: new Date(now).toLocaleString(),
                lastActivity: new Date(data.lastActivity).toLocaleString(),
                timeSinceLastActivity: Math.round(timeSinceLastActivity / 1000) + '秒',
                timeout: Math.round(timeout / 1000) + '秒'
            });
            
            // 检查是否超时
            if (timeSinceLastActivity > timeout) {
                localStorage.removeItem('tradingagents_auth');
                console.log('⏰ 登录状态已过期，自动清除');
                return;
            }
            
            // 更新最后活动时间
            data.lastActivity = now;
            localStorage.setItem('tradingagents_auth', JSON.stringify(data));
            console.log('🔄 更新最后活动时间');
            
            console.log('✅ 从前端缓存恢复登录状态:', data.userInfo.username);
            
            // 保留现有的URL参数，只添加restore_auth参数
            // 传递完整的认证数据，包括原始登录时间
            const restoreData = {
                userInfo: data.userInfo,
                loginTime: data.loginTime
            };
            const restoreParam = btoa(JSON.stringify(restoreData));
            console.log('📦 生成恢复参数:', restoreParam);
            
            // 保留所有现有参数
            const existingParams = new URLSearchParams(currentUrl.search);
            existingParams.set('restore_auth', restoreParam);
            
            // 构建新URL，保留现有参数
            const newUrl = currentUrl.origin + currentUrl.pathname + '?' + existingParams.toString();
            console.log('🔗 准备跳转到:', newUrl);
            console.log('📋 保留的URL参数:', Object.fromEntries(existingParams));
            
            window.location.href = newUrl;
            
        } catch (e) {
            console.error('❌ 前端缓存恢复失败:', e);
            localStorage.removeItem('tradingagents_auth');
        }
    }
    
    // 延迟执行，确保页面完全加载
    console.log('⏱️ 设置1000ms延迟执行前端缓存检查');
    setTimeout(checkAndRestoreAuth, 1000);
    </script>
    """
    
    st.components.v1.html(cache_check_js, height=0)

def main():
    """主应用程序"""

    # 初始化会话状态
    initialize_session_state()

    # 检查前端缓存恢复
    check_frontend_auth_cache()

    # 检查用户认证状态
    if not auth_manager.is_authenticated():
        # 最后一次尝试从session state恢复认证状态
        if (st.session_state.get('authenticated', False) and 
            st.session_state.get('user_info') and 
            st.session_state.get('login_time')):
            logger.info("🔄 从session state恢复认证状态")
            try:
                auth_manager.login_user(
                    st.session_state.user_info, 
                    st.session_state.login_time
                )
                logger.info(f"✅ 成功从session state恢复用户 {st.session_state.user_info.get('username', 'Unknown')} 的认证状态")
            except Exception as e:
                logger.warning(f"⚠️ 从session state恢复认证状态失败: {e}")
        
        # 如果仍然未认证，显示登录页面
        if not auth_manager.is_authenticated():
            render_login_form()
            return

    # 全局侧边栏CSS样式 - 确保所有页面一致
    st.markdown("""
    <style>
    /* 统一侧边栏宽度为320px */
    section[data-testid="stSidebar"] {
        width: 320px !important;
        min-width: 320px !important;
        max-width: 320px !important;
    }

    /* 侧边栏内容容器 */
    section[data-testid="stSidebar"] > div {
        width: 320px !important;
        min-width: 320px !important;
        max-width: 320px !important;
    }

    /* 主内容区域适配320px侧边栏 */
    .main .block-container {
        width: calc(100vw - 336px) !important;
        max-width: calc(100vw - 336px) !important;
    }

    /* 选择框宽度适配320px侧边栏 */
    section[data-testid="stSidebar"] .stSelectbox > div > div,
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        width: 100% !important;
        min-width: 260px !important;
        max-width: 280px !important;
    }

    /* 侧边栏标题样式 */
    section[data-testid="stSidebar"] h1 {
        font-size: 1.2rem !important;
        line-height: 1.3 !important;
        margin-bottom: 1rem !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    /* 隐藏侧边栏的隐藏按钮 - 更全面的选择器 */
    button[kind="header"],
    button[data-testid="collapsedControl"],
    .css-1d391kg,
    .css-1rs6os,
    .css-17eq0hr,
    .css-1lcbmhc,
    .css-1y4p8pa,
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"],
    [data-testid="collapsedControl"],
    .stSidebar button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* 隐藏侧边栏顶部区域的特定按钮（更精确的选择器，避免影响表单按钮） */
    section[data-testid="stSidebar"] > div:first-child > button[kind="header"],
    section[data-testid="stSidebar"] > div:first-child > div > button[kind="header"],
    section[data-testid="stSidebar"] .css-1lcbmhc > button[kind="header"],
    section[data-testid="stSidebar"] .css-1y4p8pa > button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* 调整侧边栏内容的padding */
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* 调整主内容区域，设置8px边距 - 使用更强的选择器 */
    .main .block-container,
    section.main .block-container,
    div.main .block-container,
    .stApp .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
        max-width: none !important;
        width: calc(100% - 16px) !important;
    }

    /* 确保内容不被滚动条遮挡 */
    .stApp > div {
        overflow-x: auto !important;
    }

    /* 调整详细分析报告的右边距 */
    .element-container {
        margin-right: 8px !important;
    }

    /* 优化侧边栏标题和元素间距 */
    .sidebar .sidebar-content {
        padding: 0.5rem 0.3rem !important;
    }

    /* 调整侧边栏内所有元素的间距 */
    section[data-testid="stSidebar"] .element-container {
        margin-bottom: 0.5rem !important;
    }

    /* 调整侧边栏分隔线的间距 */
    section[data-testid="stSidebar"] hr {
        margin: 0.8rem 0 !important;
    }

    /* 简化功能选择区域样式 */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }

    /* 这些样式已在global_sidebar.css中定义 */

    /* 防止水平滚动条出现 */
    .main .block-container {
        overflow-x: visible !important;
    }

    /* 强制设置8px边距给所有可能的容器 */
    .stApp,
    .stApp > div,
    .stApp > div > div,
    .main,
    .main > div,
    .main > div > div,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewContainer"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* 特别处理列容器 */
    div[data-testid="column"],
    .css-1d391kg,
    .css-1r6slb0,
    .css-12oz5g7,
    .css-1lcbmhc {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* 容器宽度已在global_sidebar.css中定义 */

    /* 优化使用指南区域的样式 */
    div[data-testid="column"]:last-child {
        background-color: #f8f9fa !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin-left: 8px !important;
        border: 1px solid #e9ecef !important;
    }

    /* 使用指南内的展开器样式 */
    div[data-testid="column"]:last-child .streamlit-expanderHeader {
        background-color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #dee2e6 !important;
        font-weight: 500 !important;
    }

    /* 使用指南内的文本样式 */
    div[data-testid="column"]:last-child .stMarkdown {
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }

    /* 使用指南标题样式 */
    div[data-testid="column"]:last-child h1 {
        font-size: 1.3rem !important;
        color: #495057 !important;
        margin-bottom: 1rem !important;
    }
    </style>

    <script>
    // JavaScript来强制隐藏侧边栏按钮
    function hideSidebarButtons() {
        // 隐藏所有可能的侧边栏控制按钮
        const selectors = [
            'button[kind="header"]',
            'button[data-testid="collapsedControl"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            '[data-testid="collapsedControl"]',
            '.css-1d391kg',
            '.css-1rs6os',
            '.css-17eq0hr',
            '.css-1lcbmhc button',
            '.css-1y4p8pa button'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
            });
        });
    }

    // 页面加载后执行
    document.addEventListener('DOMContentLoaded', hideSidebarButtons);

    // 定期检查并隐藏按钮（防止动态生成）
    setInterval(hideSidebarButtons, 1000);

    // 强制修改页面边距为8px
    function forceOptimalPadding() {
        const selectors = [
            '.main .block-container',
            '.stApp',
            '.stApp > div',
            '.main',
            '.main > div',
            'div[data-testid="stAppViewContainer"]',
            'section[data-testid="stMain"]',
            'div[data-testid="column"]'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.paddingLeft = '8px';
                el.style.paddingRight = '8px';
                el.style.marginLeft = '0px';
                el.style.marginRight = '0px';
            });
        });

        // 特别处理主容器宽度
        const mainContainer = document.querySelector('.main .block-container');
        if (mainContainer) {
            mainContainer.style.width = 'calc(100vw - 336px)';
            mainContainer.style.maxWidth = 'calc(100vw - 336px)';
        }
    }

    // 页面加载后执行
    document.addEventListener('DOMContentLoaded', forceOptimalPadding);

    // 定期强制应用样式
    setInterval(forceOptimalPadding, 500);
    </script>
    """, unsafe_allow_html=True)

    # Add debugging helper buttons (only shown in debug mode)
    if os.getenv('DEBUG_MODE') == 'true':
        if st.button("🔄 Clear session state"):
            st.session_state.clear()
            st.experimental_rerun()

    # 渲染页面头部
    render_header()

    # Sidebar layout - keep the title at the top
    st.sidebar.title("🤖 TradingAgents Platform")
    st.sidebar.markdown("---")

    # Page navigation - display user info below the title
    render_sidebar_user_info()

    # Add a divider between user info and the feature navigation
    st.sidebar.markdown("---")

    # Add feature navigation header
    st.sidebar.markdown("**🎯 Feature navigation**")

    page = st.sidebar.selectbox(
        "Switch feature module",
        ["📊 Stock analysis", "⚙️ Configuration", "💾 Cache management", "💰 Token usage", "📋 Activity log", "📈 Analysis history", "🔧 System status"],
        label_visibility="collapsed"
    )
    
    # 记录页面访问活动
    try:
        user_activity_logger.log_page_visit(
            page_name=page,
            page_params={
                "page_url": f"/app?page={page.split(' ')[1] if ' ' in page else page}",
                "page_type": "main_navigation",
                "access_method": "sidebar_selectbox"
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log page visit: {e}")

    # Add a divider between the feature selector and AI model configuration
    st.sidebar.markdown("---")

    # Render different content depending on the selected page
    if page == "⚙️ Configuration":
        # Check configuration permissions
        if not require_permission("config"):
            return
        try:
            from modules.config_management import render_config_management
            render_config_management()
        except ImportError as e:
            st.error(f"Failed to load configuration management module: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "💾 Cache management":
        # Check admin permissions
        if not require_permission("admin"):
            return
        try:
            from modules.cache_management import main as cache_main
            cache_main()
        except ImportError as e:
            st.error(f"Failed to load cache management module: {e}")
        return
    elif page == "💰 Token usage":
        # Check configuration permissions
        if not require_permission("config"):
            return
        try:
            from modules.token_statistics import render_token_statistics
            render_token_statistics()
        except ImportError as e:
            st.error(f"Failed to load token statistics module: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "📋 Activity log":
        # Check admin permissions
        if not require_permission("admin"):
            return
        try:
            from components.operation_logs import render_operation_logs
            render_operation_logs()
        except ImportError as e:
            st.error(f"Failed to load operation log module: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "📈 Analysis history":
        # Check analysis permissions
        if not require_permission("analysis"):
            return
        try:
            from components.analysis_results import render_analysis_results
            render_analysis_results()
        except ImportError as e:
            st.error(f"Failed to load analysis results module: {e}")
            st.info("Please ensure all dependencies are installed")
        return
    elif page == "🔧 System status":
        # Check admin permissions
        if not require_permission("admin"):
            return
        st.header("🔧 System status")
        st.info("System status tools are under development...")
        return

    # Default to the stock analysis page
    # Check analysis permissions
    if not require_permission("analysis"):
        return

    # Check API keys
    api_status = check_api_keys()

    if not api_status['all_configured']:
        st.error("⚠️ API keys are not fully configured. Please update the required keys first.")

        with st.expander("📋 API key configuration guide", expanded=True):
            st.markdown("""
            ### 🔑 Required API keys

            1. **Alibaba DashScope API key** (`DASHSCOPE_API_KEY`)
               - Get it from: https://dashscope.aliyun.com/
               - Purpose: LLM inference

            2. **Finnhub financial data API key** (`FINNHUB_API_KEY`)
               - Get it from: https://finnhub.io/
               - Purpose: Stock market data

            ### ⚙️ How to configure

            1. Copy `.env.example` at the project root to `.env`
            2. Edit `.env` and fill in your real API keys
            3. Restart the web application

            ```bash
            # .env example
            DASHSCOPE_API_KEY=sk-your-dashscope-key
            FINNHUB_API_KEY=your-finnhub-key
            ```
            """)

        # 显示当前API密钥状态
        st.subheader("🔍 Current API key status")
        for key, status in api_status['details'].items():
            if status['configured']:
                st.success(f"✅ {key}: {status['display']}")
            else:
                st.error(f"❌ {key}: not configured")
        
        return
    
    # 渲染侧边栏
    config = render_sidebar()
    
    # 添加使用指南显示切换
    # 如果正在分析或有分析结果，默认隐藏使用指南
    default_show_guide = not (st.session_state.get('analysis_running', False) or st.session_state.get('analysis_results') is not None)
    
    # 如果用户没有手动设置过，使用默认值
    if 'user_set_guide_preference' not in st.session_state:
        st.session_state.user_set_guide_preference = False
        st.session_state.show_guide_preference = default_show_guide
    
    show_guide = st.sidebar.checkbox(
        "📖 Show usage guide",
        value=st.session_state.get('show_guide_preference', default_show_guide),
        help="Show or hide the guide on the right",
        key="guide_checkbox"
    )
    
    # 记录用户的选择
    if show_guide != st.session_state.get('show_guide_preference', default_show_guide):
        st.session_state.user_set_guide_preference = True
        st.session_state.show_guide_preference = show_guide

    # 添加状态清理按钮
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Reset analysis state", help="Clear stale analysis state to resolve continuous refresh issues"):
        # 清理session state
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None
        st.session_state.analysis_results = None

        # 清理所有自动刷新状态
        keys_to_remove = []
        for key in st.session_state.keys():
            if 'auto_refresh' in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state[key]

        # 清理死亡线程
        from utils.thread_tracker import cleanup_dead_analysis_threads
        cleanup_dead_analysis_threads()

        st.sidebar.success("✅ Analysis state cleared")
        st.rerun()

    # 在侧边栏底部添加退出按钮
    render_sidebar_logout()

    # 主内容区域 - 根据是否显示指南调整布局
    if show_guide:
        col1, col2 = st.columns([2, 1])  # 2:1 ratio keeps the guide slimmer
    else:
        col1 = st.container()
        col2 = None
    
    with col1:
        # 1. 分析配置区域

        st.header("⚙️ Analysis configuration")

        # 渲染分析表单
        try:
            form_data = render_analysis_form()

            # 验证表单数据格式
            if not isinstance(form_data, dict):
                st.error(f"⚠️ Unexpected form data type: {type(form_data)}")
                form_data = {'submitted': False}

        except Exception as e:
            st.error(f"❌ Failed to render the form: {e}")
            form_data = {'submitted': False}

        # 避免显示调试信息
        if form_data and form_data != {'submitted': False}:
            # 只在调试模式下显示表单数据
            if os.getenv('DEBUG_MODE') == 'true':
                st.write("Debug - Form data:", form_data)

        # 添加接收日志
        if form_data.get('submitted', False):
            logger.debug(f"🔍 [APP DEBUG] ===== Main app received form data =====")
            logger.debug(f"🔍 [APP DEBUG] Received form_data: {form_data}")
            logger.debug(f"🔍 [APP DEBUG] Stock symbol: '{form_data['stock_symbol']}'")
            logger.debug(f"🔍 [APP DEBUG] Market type: '{form_data['market_type']}'")

        # 检查是否提交了表单
        if form_data.get('submitted', False) and not st.session_state.get('analysis_running', False):
            # 只有在没有分析运行时才处理新的提交
            # 验证分析参数
            is_valid, validation_errors = validate_analysis_params(
                stock_symbol=form_data['stock_symbol'],
                analysis_date=form_data['analysis_date'],
                analysts=form_data['analysts'],
                research_depth=form_data['research_depth'],
                market_type=form_data.get('market_type', '美股')
            )

            if not is_valid:
                # 显示验证错误
                for error in validation_errors:
                    st.error(error)
            else:
                # 执行分析
                st.session_state.analysis_running = True

                # 清空旧的分析结果
                st.session_state.analysis_results = None
                logger.info("🧹 [新分析] 清空旧的分析结果")
                
                # 自动隐藏使用指南（除非用户明确设置要显示）
                if not st.session_state.get('user_set_guide_preference', False):
                    st.session_state.show_guide_preference = False
                    logger.info("📖 [界面] 开始分析，自动隐藏使用指南")

                # 生成分析ID
                import uuid
                analysis_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # 保存分析ID和表单配置到session state和cookie
                form_config = st.session_state.get('form_config', {})
                set_persistent_analysis_id(
                    analysis_id=analysis_id,
                    status="running",
                    stock_symbol=form_data['stock_symbol'],
                    market_type=form_data.get('market_type', '美股'),
                    form_config=form_config
                )

                # 创建异步进度跟踪器
                async_tracker = AsyncProgressTracker(
                    analysis_id=analysis_id,
                    analysts=form_data['analysts'],
                    research_depth=form_data['research_depth'],
                    llm_provider=config['llm_provider']
                )

                # 创建进度回调函数
                def progress_callback(message: str, step: int = None, total_steps: int = None):
                    async_tracker.update_progress(message, step)

                # 显示启动成功消息和加载动效
                st.success(f"🚀 Analysis started! Analysis ID: {analysis_id}")

                # 添加加载动效
                with st.spinner("🔄 Initializing analysis..."):
                    time.sleep(1.5)  # 让用户看到反馈

                st.info(f"📊 Running analysis: {form_data.get('market_type', 'US Market')} {form_data['stock_symbol']}")
                st.info("""
                ⏱️ The page will refresh automatically in 6 seconds...

                📋 **Where to find progress:**
                After the refresh, scroll to the "📊 Stock analysis" section for real-time updates.
                """)

                # 确保AsyncProgressTracker已经保存初始状态
                time.sleep(0.1)  # 等待100毫秒确保数据已写入

                # 设置分析状态
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = analysis_id
                st.session_state.last_stock_symbol = form_data['stock_symbol']
                st.session_state.last_market_type = form_data.get('market_type', '美股')

                # 自动启用自动刷新选项（设置所有可能的key）
                auto_refresh_keys = [
                    f"auto_refresh_unified_{analysis_id}",
                    f"auto_refresh_unified_default_{analysis_id}",
                    f"auto_refresh_static_{analysis_id}",
                    f"auto_refresh_streamlit_{analysis_id}"
                ]
                for key in auto_refresh_keys:
                    st.session_state[key] = True

                # 在后台线程中运行分析（立即启动，不等待倒计时）
                import threading

                def run_analysis_in_background():
                    try:
                        results = run_stock_analysis(
                            stock_symbol=form_data['stock_symbol'],
                            analysis_date=form_data['analysis_date'],
                            analysts=form_data['analysts'],
                            research_depth=form_data['research_depth'],
                            llm_provider=config['llm_provider'],
                            market_type=form_data.get('market_type', '美股'),
                            llm_model=config['llm_model'],
                            progress_callback=progress_callback
                        )

                        # 标记分析完成并保存结果（不访问session state）
                        async_tracker.mark_completed("✅ Analysis finished successfully!", results=results)

                        # 自动保存分析结果到历史记录
                        try:
                            from components.analysis_results import save_analysis_result
                            
                            save_success = save_analysis_result(
                                analysis_id=analysis_id,
                                stock_symbol=form_data['stock_symbol'],
                                analysts=form_data['analysts'],
                                research_depth=form_data['research_depth'],
                                result_data=results,
                                status="completed"
                            )
                            
                            if save_success:
                                logger.info(f"💾 [后台保存] 分析结果已保存到历史记录: {analysis_id}")
                            else:
                                logger.warning(f"⚠️ [后台保存] 保存失败: {analysis_id}")
                                
                        except Exception as save_error:
                            logger.error(f"❌ [后台保存] 保存异常: {save_error}")

                        logger.info(f"✅ [Analysis completed] Stock analysis finished: {analysis_id}")

                    except Exception as e:
                        # 标记分析失败（不访问session state）
                        async_tracker.mark_failed(str(e))
                        
                        # 保存失败的分析记录
                        try:
                            from components.analysis_results import save_analysis_result
                            
                            save_analysis_result(
                                analysis_id=analysis_id,
                                stock_symbol=form_data['stock_symbol'],
                                analysts=form_data['analysts'],
                                research_depth=form_data['research_depth'],
                                result_data={"error": str(e)},
                                status="failed"
                            )
                            logger.info(f"💾 [Failure record] Analysis failure saved: {analysis_id}")
                            
                        except Exception as save_error:
                            logger.error(f"❌ [失败记录] 保存异常: {save_error}")
                        
                        logger.error(f"❌ [Analysis failed] {analysis_id}: {e}")

                    finally:
                        # 分析结束后注销线程
                        from utils.thread_tracker import unregister_analysis_thread
                        unregister_analysis_thread(analysis_id)
                        logger.info(f"🧵 [Thread cleanup] Analysis thread unregistered: {analysis_id}")

                # 启动后台分析线程
                analysis_thread = threading.Thread(target=run_analysis_in_background)
                analysis_thread.daemon = True  # 设置为守护线程，这样主程序退出时线程也会退出
                analysis_thread.start()

                # 注册线程到跟踪器
                from utils.thread_tracker import register_analysis_thread
                register_analysis_thread(analysis_id, analysis_thread)

                logger.info(f"🧵 [Background analysis] Analysis thread started: {analysis_id}")

                # 分析已在后台线程中启动，显示启动信息并刷新页面
                st.success("🚀 Analysis has started and is running in the background...")

                # 显示启动信息
                st.info("⏱️ The page will refresh automatically to display analysis progress...")

                # 等待2秒让用户看到启动信息，然后刷新页面
                time.sleep(2)
                st.rerun()

        # 2. 股票分析区域（只有在有分析ID时才显示）
        current_analysis_id = st.session_state.get('current_analysis_id')
        if current_analysis_id:
            st.markdown("---")

            st.header("📊 Stock analysis")

            # 使用线程检测来获取真实状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(current_analysis_id)
            is_running = (actual_status == 'running')

            # 同步session state状态
            if st.session_state.get('analysis_running', False) != is_running:
                st.session_state.analysis_running = is_running
                logger.info(f"🔄 [Status sync] Updated analysis state: {is_running} (thread check: {actual_status})")

            # 获取进度数据用于显示
            from utils.async_progress_tracker import get_progress_by_id
            progress_data = get_progress_by_id(current_analysis_id)

            # 显示分析信息
            if is_running:
                st.info(f"🔄 Analysis in progress: {current_analysis_id}")
            else:
                if actual_status == 'completed':
                    st.success(f"✅ Analysis completed: {current_analysis_id}")

                elif actual_status == 'failed':
                    st.error(f"❌ Analysis failed: {current_analysis_id}")
                else:
                    st.warning(f"⚠️ Analysis status unknown: {current_analysis_id}")

            # 显示进度（根据状态决定是否显示刷新控件）
            progress_col1, progress_col2 = st.columns([4, 1])
            with progress_col1:
                st.markdown("### 📊 Analysis progress")

            is_completed = display_unified_progress(current_analysis_id, show_refresh_controls=is_running)

            # 如果分析正在进行，显示提示信息（不添加额外的自动刷新）
            if is_running:
                st.info("⏱️ The analysis is running. Use the auto-refresh controls below to follow updates.")

            # 如果分析刚完成，尝试恢复结果
            if is_completed and not st.session_state.get('analysis_results') and progress_data:
                if 'raw_results' in progress_data:
                    try:
                        from utils.analysis_runner import format_analysis_results
                        raw_results = progress_data['raw_results']
                        formatted_results = format_analysis_results(raw_results)
                        if formatted_results:
                            st.session_state.analysis_results = formatted_results
                            st.session_state.analysis_running = False
                            logger.info(f"📊 [结果同步] 恢复分析结果: {current_analysis_id}")

                            # 自动保存分析结果到历史记录
                            try:
                                from components.analysis_results import save_analysis_result
                                
                                # 从进度数据中获取分析参数
                                stock_symbol = progress_data.get('stock_symbol', st.session_state.get('last_stock_symbol', 'unknown'))
                                analysts = progress_data.get('analysts', [])
                                research_depth = progress_data.get('research_depth', 3)
                                
                                # 保存分析结果
                                save_success = save_analysis_result(
                                    analysis_id=current_analysis_id,
                                    stock_symbol=stock_symbol,
                                    analysts=analysts,
                                    research_depth=research_depth,
                                    result_data=raw_results,
                                    status="completed"
                                )
                                
                                if save_success:
                                    logger.info(f"💾 [结果保存] 分析结果已保存到历史记录: {current_analysis_id}")
                                else:
                                    logger.warning(f"⚠️ [结果保存] 保存失败: {current_analysis_id}")
                                    
                            except Exception as save_error:
                                logger.error(f"❌ [结果保存] 保存异常: {save_error}")

                            # 检查是否已经刷新过，避免重复刷新
                            refresh_key = f"results_refreshed_{current_analysis_id}"
                            if not st.session_state.get(refresh_key, False):
                                st.session_state[refresh_key] = True
                                st.success("📊 Analysis results restored and saved. Refreshing the page...")
                                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                                time.sleep(1)
                                st.rerun()
                            else:
                                # 已经刷新过，不再刷新
                                st.success("📊 Analysis results restored and saved!")
                    except Exception as e:
                        logger.warning(f"⚠️ [结果同步] 恢复失败: {e}")

            if is_completed and st.session_state.get('analysis_running', False):
                # 分析刚完成，更新状态
                st.session_state.analysis_running = False
                st.success("🎉 Analysis complete! Refreshing to display the report...")

                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                time.sleep(1)
                st.rerun()



        # 3. 分析报告区域（只有在有结果且分析完成时才显示）

        current_analysis_id = st.session_state.get('current_analysis_id')
        analysis_results = st.session_state.get('analysis_results')
        analysis_running = st.session_state.get('analysis_running', False)

        # 检查是否应该显示分析报告
        # 1. 有分析结果且不在运行中
        # 2. 或者用户点击了"查看报告"按钮
        show_results_button_clicked = st.session_state.get('show_analysis_results', False)

        should_show_results = (
            (analysis_results and not analysis_running and current_analysis_id) or
            (show_results_button_clicked and analysis_results)
        )

        # 调试日志
        logger.info(f"🔍 [布局调试] 分析报告显示检查:")
        logger.info(f"  - analysis_results存在: {bool(analysis_results)}")
        logger.info(f"  - analysis_running: {analysis_running}")
        logger.info(f"  - current_analysis_id: {current_analysis_id}")
        logger.info(f"  - show_results_button_clicked: {show_results_button_clicked}")
        logger.info(f"  - should_show_results: {should_show_results}")

        if should_show_results:
            st.markdown("---")
            st.header("📋 Analysis report")
            render_results(analysis_results)
            logger.info(f"✅ [布局] 分析报告已显示")

            # 清除查看报告按钮状态，避免重复触发
            if show_results_button_clicked:
                st.session_state.show_analysis_results = False
    
    # 只有在显示指南时才渲染右侧内容
    if show_guide and col2 is not None:
        with col2:
            st.markdown("### ℹ️ Usage guide")

            # 快速开始指南
            with st.expander("🎯 Quick start", expanded=True):
                st.markdown("""
                ### 📋 Step-by-step

                1. **Enter a stock symbol**
                   - Mainland China A-share examples: `000001` (Ping An Bank), `600519` (Kweichow Moutai), `000858` (Wuliangye)
                   - U.S. market examples: `AAPL` (Apple), `TSLA` (Tesla), `MSFT` (Microsoft)
                   - Hong Kong market examples: `00700` (Tencent), `09988` (Alibaba)

                   ⚠️ **Important:** Press **Enter** after typing the symbol to confirm the input.

                2. **Pick an analysis date**
                   - Defaults to today
                   - Choose a past date for a backtest-style analysis

                3. **Select analyst roles**
                   - At least one analyst must be selected
                   - Combining multiple analysts yields a more comprehensive report

                4. **Set the research depth**
                   - Levels 1-2: Quick overview
                   - Level 3: Standard analysis (recommended)
                   - Levels 4-5: Deep research

                5. **Start the analysis**
                   - Wait for the AI workflow to complete
                   - Review the generated report

                ### 💡 Tips

                - **A-shares are the default**: No extra setup is needed for mainland China symbols
                - **Symbol formats**: A-shares use six-digit numeric codes (e.g., `000001`)
                - **Fresh data**: Fetches the latest market data and news
                - **Multi-angle output**: Combines technical, fundamental, and sentiment perspectives
                """)

            # 分析师说明
            with st.expander("👥 Analyst teams explained"):
                st.markdown("""
                ### 🎯 Specialist analyst groups

                - **📈 Market analyst**
                  - Technical indicator reviews (candles, moving averages, MACD, etc.)
                  - Price trend projections
                  - Support and resistance analysis

                - **💭 Social media analyst**
                  - Investor sentiment tracking
                  - Social buzz analytics
                  - Market sentiment indicators

                - **📰 News analyst**
                  - Impact of breaking news and events
                  - Policy interpretation
                  - Industry trend monitoring

                - **💰 Fundamental analyst**
                  - Financial statement analysis
                  - Valuation modelling
                  - Industry benchmarking
                  - Profitability evaluation

                💡 **Tip:** Combine multiple analysts to obtain richer recommendations.
                """)

            # 模型选择说明
            with st.expander("🧠 AI model overview"):
                st.markdown("""
                ### 🤖 Suggested LLM tiers

                - **qwen-turbo**:
                  - Fast responses for quick lookups
                  - Lower cost, perfect for frequent usage
                  - Typical response time: 2–5 seconds

                - **qwen-plus**:
                  - Balanced performance for everyday workflows ⭐
                  - A solid mix of accuracy and speed
                  - Typical response time: 5–10 seconds

                - **qwen-max**:
                  - Highest performance, best for deep-dive research
                  - Delivers maximum accuracy and depth
                  - Typical response time: 10–20 seconds

                💡 **Recommendation:** Use `qwen-plus` for daily tasks and switch to `qwen-max` for mission-critical decisions.
                """)

            # 常见问题
            with st.expander("❓ Frequently asked questions"):
                st.markdown("""
                ### 🔍 Answers

                **Q: Why doesn't the stock symbol input respond?**
                A: Press **Enter** after typing the symbol—this is required by Streamlit inputs.

                **Q: What is the format for A-share symbols?**
                A: A-share tickers are six-digit numbers such as `000001`, `600519`, or `000858`.

                **Q: How long does the analysis take?**
                A: Depending on research depth and model choice, it usually takes 30 seconds to 2 minutes.

                **Q: Can the app analyse Hong Kong stocks?**
                A: Yes. Enter the five-digit HKEX symbol, e.g., `00700`, `09988`.

                **Q: How far back can historical data go?**
                A: Typically up to the past five years for analysis.
                """)

            # 风险提示
            st.warning("""
            ⚠️ **Investment risk notice**

            - The generated insights are for reference only and do not constitute investment advice.
            - Investing involves risk. Please evaluate carefully before entering the market.
            - Combine the report with additional research and professional guidance.
            - Consult a licensed advisor for major investment decisions.
            - AI analysis has limitations, and market conditions can change rapidly.
            """)
        
        # 显示系统状态
        if st.session_state.last_analysis_time:
            st.info(f"🕒 上次分析时间: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
