"""
登录组件
提供用户登录界面
"""

import streamlit as st
import time
import sys
from pathlib import Path
import base64

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入认证管理器 - 使用全局变量确保在整个模块中可用
auth_manager = None

# 尝试多种导入路径
try:
    # 尝试相对导入（从 web 目录运行时）
    from ..utils.auth_manager import AuthManager, auth_manager as imported_auth_manager
    auth_manager = imported_auth_manager
except ImportError:
    try:
        # 尝试从 web.utils 导入（从项目根目录运行时）
        from web.utils.auth_manager import AuthManager, auth_manager as imported_auth_manager
        auth_manager = imported_auth_manager
    except ImportError:
        try:
            # 尝试直接从 utils 导入
            from utils.auth_manager import AuthManager, auth_manager as imported_auth_manager
            auth_manager = imported_auth_manager
        except ImportError:
            try:
                # 尝试绝对路径导入
                import sys
                from pathlib import Path
                web_utils_path = Path(__file__).parent.parent / "utils"
                sys.path.insert(0, str(web_utils_path))
                from auth_manager import AuthManager, auth_manager as imported_auth_manager
                auth_manager = imported_auth_manager
            except ImportError:
                # 如果都失败了，创建一个简单的认证管理器
                class SimpleAuthManager:
                    def __init__(self):
                        self.authenticated = False
                        self.current_user = None
                    
                    def is_authenticated(self):
                        return st.session_state.get('authenticated', False)
                    
                    def authenticate(self, username, password):
                        # 简单的认证逻辑
                        if username == "admin" and password == "admin123":
                            return True, {"username": username, "role": "admin"}
                        elif username == "user" and password == "user123":
                            return True, {"username": username, "role": "user"}
                        return False, None
                    
                    def logout(self):
                        st.session_state.authenticated = False
                        st.session_state.user_info = None
                    
                    def get_current_user(self):
                        return st.session_state.get('user_info')
                    
                    def require_permission(self, permission):
                        return self.is_authenticated()
                
                auth_manager = SimpleAuthManager()

def get_base64_image(image_path):
    """将图片转换为base64编码"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

def render_login_form():
    """渲染登录表单"""
    
    # 现代化登录页面样式
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        font-family: 'Inter', sans-serif;
    }
    
    .login-container {
        max-width: 550px;
        margin: 0.5rem auto;
        padding: 2.5rem 2rem;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    .login-title {
        color: #2d3748;
        margin-bottom: 0.5rem;
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        white-space: nowrap;
        overflow: visible;
        text-overflow: clip;
    }
    
    .login-subtitle {
        color: #718096;
        font-size: 1.1rem;
        font-weight: 400;
        margin-bottom: 0;
    }
    
    .login-form {
        margin-top: 1rem;
    }
    
    .stTextInput > div > div > input {
        background: rgba(247, 250, 252, 0.8);
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 0.75rem 1rem;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        background: white;
    }
    
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
    
    .login-tips {
        background: linear-gradient(135deg, #e6fffa 0%, #f0fff4 100%);
        border: 1px solid #9ae6b4;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1.5rem;
        text-align: center;
    }
    
    .login-tips-icon {
        font-size: 1.2rem;
        margin-right: 0.5rem;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-top: 2rem;
    }
    
    .feature-card {
        background: rgba(255, 255, 255, 0.7);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.3);
        transition: all 0.3s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    }
    
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    .feature-title {
        font-weight: 600;
        color: #2d3748;
        margin-bottom: 0.5rem;
    }
    
    .feature-desc {
        color: #718096;
        font-size: 0.9rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 主登录容器
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <h1 class="login-title">🚀 TradingAgents-CN</h1>
            <p class="login-subtitle">AI驱动的股票交易分析平台 · 让投资更智能</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 登录表单
    with st.container():
        st.markdown('<div class="login-form">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🔐 用户登录")
            username = st.text_input(
                "用户名", 
                placeholder="请输入您的用户名", 
                key="username_input",
                label_visibility="collapsed"
            )
            password = st.text_input(
                "密码", 
                type="password", 
                placeholder="请输入您的密码", 
                key="password_input",
                label_visibility="collapsed"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🚀 立即登录", use_container_width=True, key="login_button"):
                if username and password:
                    # 使用auth_manager.login()方法来确保前端缓存被正确保存
                    if auth_manager.login(username, password):
                        st.success("✅ 登录成功！正在为您跳转...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 用户名或密码错误，请重试")
                else:
                    st.warning("⚠️ 请输入完整的登录信息")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 功能特色展示
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <div class="feature-title">智能分析</div>
            <div class="feature-desc">AI驱动的股票分析</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🔍</div>
            <div class="feature-title">深度研究</div>
            <div class="feature-desc">全方位市场洞察</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <div class="feature-title">实时数据</div>
            <div class="feature-desc">最新市场信息</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🛡️</div>
            <div class="feature-title">风险控制</div>
            <div class="feature-desc">智能风险评估</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar_user_info():
    """在侧边栏渲染用户信息"""
    
    if not auth_manager.is_authenticated():
        return
    
    user_info = auth_manager.get_current_user()
    if not user_info:
        return
    
    # 侧边栏用户信息样式
    st.sidebar.markdown("""
    <style>
    .sidebar-user-info {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .sidebar-user-name {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
        text-align: center;
    }
    
    .sidebar-user-role {
        background: rgba(255, 255, 255, 0.2);
        padding: 0.2rem 0.6rem;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: 500;
        text-align: center;
        margin-bottom: 0.5rem;
        backdrop-filter: blur(10px);
    }
    
    .sidebar-user-status {
        font-size: 0.8rem;
        opacity: 0.9;
        text-align: center;
        margin-bottom: 0.8rem;
    }
    
    .sidebar-logout-btn {
        width: 100% !important;
        background: rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(10px) !important;
    }
    
    .sidebar-logout-btn:hover {
        background: rgba(255, 255, 255, 0.3) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 获取用户角色的中文显示
    role_display = {
        'admin': '管理员',
        'user': '普通用户'
    }.get(user_info.get('role', 'user'), '用户')
    
    # 获取登录时间
    login_time = st.session_state.get('login_time')
    login_time_str = ""
    if login_time:
        import datetime
        login_dt = datetime.datetime.fromtimestamp(login_time)
        login_time_str = login_dt.strftime("%H:%M")
    
    # 渲染用户信息
    st.sidebar.markdown(f"""
    <div class="sidebar-user-info">
        <div class="sidebar-user-name">👋 {user_info['username']}</div>
        <div class="sidebar-user-role">{role_display}</div>
        <div class="sidebar-user-status">
            🌟 在线中 {f'· {login_time_str}登录' if login_time_str else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar_logout():
    """在侧边栏底部渲染退出按钮"""
    
    if not auth_manager.is_authenticated():
        return
    
    # 退出按钮样式
    st.sidebar.markdown("""
    <style>
    .sidebar-logout-container {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .sidebar-logout-btn {
        width: 100% !important;
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 10px rgba(255, 107, 107, 0.3) !important;
    }
    
    .sidebar-logout-btn:hover {
        background: linear-gradient(135deg, #ff5252 0%, #d32f2f 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.4) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 添加分隔线和退出按钮
    st.sidebar.markdown('<div class="sidebar-logout-container">', unsafe_allow_html=True)
    if st.sidebar.button("🚪 安全退出", use_container_width=True, key="sidebar_logout_btn"):
        auth_manager.logout()
        st.sidebar.success("✅ 已安全退出，感谢使用！")
        time.sleep(1)
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

def render_user_info():
    """渲染用户信息栏"""
    
    if not auth_manager.is_authenticated():
        return
    
    user_info = auth_manager.get_current_user()
    if not user_info:
        return
    
    # 现代化用户信息栏样式
    st.markdown("""
    <style>
    .user-info-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .user-welcome {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    
    .user-name {
        font-size: 1.4rem;
        font-weight: 600;
        margin: 0;
    }
    
    .user-role {
        background: rgba(255, 255, 255, 0.2);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        backdrop-filter: blur(10px);
    }
    
    .user-details {
        display: flex;
        align-items: center;
        gap: 1rem;
        opacity: 0.9;
        font-size: 0.95rem;
    }
    
    .logout-btn {
        background: rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 10px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(10px) !important;
    }
    
    .logout-btn:hover {
        background: rgba(255, 255, 255, 0.3) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 获取用户角色的中文显示
    role_display = {
        'admin': '管理员',
        'user': '普通用户'
    }.get(user_info.get('role', 'user'), '用户')
    
    # 获取登录时间
    login_time = st.session_state.get('login_time')
    login_time_str = ""
    if login_time:
        import datetime
        login_dt = datetime.datetime.fromtimestamp(login_time)
        login_time_str = login_dt.strftime("%H:%M")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown(f"""
        <div class="user-info-container">
            <div class="user-welcome">
                <div>
                    <h3 class="user-name">👋 欢迎回来，{user_info['username']}</h3>
                    <div class="user-details">
                        <span>🎯 {role_display}</span>
                        {f'<span>🕐 {login_time_str} 登录</span>' if login_time_str else ''}
                        <span>🌟 在线中</span>
                    </div>
                </div>
                <div class="user-role">{role_display}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("🚪 安全退出", use_container_width=True, type="secondary", key="logout_btn"):
            auth_manager.logout()
            st.success("✅ 已安全退出，感谢使用！")
            time.sleep(1)
            st.rerun()

def check_authentication():
    """检查用户认证状态"""
    global auth_manager
    if auth_manager is None:
        return False
    return auth_manager.is_authenticated()

def require_permission(permission: str):
    """要求特定权限"""
    global auth_manager
    if auth_manager is None:
        return False
    return auth_manager.require_permission(permission)