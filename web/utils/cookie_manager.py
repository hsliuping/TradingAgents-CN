"""
Cookie管理器 - 解决Streamlit session state页面刷新丢失的问题
"""

import streamlit as st
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    COOKIES_AVAILABLE = True
except ImportError:
    COOKIES_AVAILABLE = False
    st.warning("⚠️ streamlit-cookies-manager 未安装，Cookie功能不可用")

class CookieManager:
    """Cookie管理器，用于持久化存储分析状态"""

    def __init__(self):
        self.cookie_name = "tradingagents_analysis_state"
        self.max_age_days = 7  # Cookie有效期7天

        # 初始化Cookie管理器
        if COOKIES_AVAILABLE:
            try:
                self.cookies = EncryptedCookieManager(
                    prefix="tradingagents_",
                    password="tradingagents_secret_key_2025"  # 固定密钥
                )

                # 检查Cookie管理器是否准备就绪
                if not self.cookies.ready():
                    # 如果没有准备就绪，先显示等待信息，然后停止执行
                    st.info("🔄 正在初始化Cookie管理器，请稍候...")
                    st.stop()

            except Exception as e:
                st.warning(f"⚠️ Cookie管理器初始化失败: {e}")
                self.cookies = None
        else:
            self.cookies = None
    
    def set_analysis_state(self, analysis_id: str, status: str = "running",
                          stock_symbol: str = "", market_type: str = ""):
        """设置分析状态到cookie"""
        try:
            state_data = {
                "analysis_id": analysis_id,
                "status": status,
                "stock_symbol": stock_symbol,
                "market_type": market_type,
                "timestamp": time.time(),
                "created_at": datetime.now().isoformat()
            }

            # 存储到session state（作为备份）
            st.session_state[f"cookie_{self.cookie_name}"] = state_data

            # 使用专业的Cookie管理器设置cookie
            if self.cookies:
                self.cookies[self.cookie_name] = json.dumps(state_data)
                self.cookies.save()

            return True

        except Exception as e:
            st.error(f"❌ 设置分析状态失败: {e}")
            return False
    
    def get_analysis_state(self) -> Optional[Dict[str, Any]]:
        """从cookie获取分析状态"""
        try:
            # 首先尝试从session state获取（如果存在）
            session_data = st.session_state.get(f"cookie_{self.cookie_name}")
            if session_data:
                return session_data

            # 尝试从cookie获取
            if self.cookies and self.cookie_name in self.cookies:
                cookie_data = self.cookies[self.cookie_name]
                if cookie_data:
                    state_data = json.loads(cookie_data)

                    # 检查是否过期（7天）
                    timestamp = state_data.get("timestamp", 0)
                    if time.time() - timestamp < (self.max_age_days * 24 * 3600):
                        # 恢复到session state
                        st.session_state[f"cookie_{self.cookie_name}"] = state_data
                        return state_data
                    else:
                        # 过期了，清除cookie
                        self.clear_analysis_state()

            return None

        except Exception as e:
            st.warning(f"⚠️ 获取分析状态失败: {e}")
            return None
    
    def clear_analysis_state(self):
        """清除分析状态"""
        try:
            # 清除session state
            if f"cookie_{self.cookie_name}" in st.session_state:
                del st.session_state[f"cookie_{self.cookie_name}"]

            # 清除cookie
            if self.cookies and self.cookie_name in self.cookies:
                del self.cookies[self.cookie_name]
                self.cookies.save()

        except Exception as e:
            st.warning(f"⚠️ 清除分析状态失败: {e}")

    def get_debug_info(self) -> Dict[str, Any]:
        """获取调试信息"""
        debug_info = {
            "cookies_available": COOKIES_AVAILABLE,
            "cookies_ready": self.cookies.ready() if self.cookies else False,
            "cookies_object": self.cookies is not None,
            "session_state_keys": [k for k in st.session_state.keys() if 'cookie' in k.lower() or 'analysis' in k.lower()]
        }

        if self.cookies:
            try:
                debug_info["cookie_keys"] = list(self.cookies.keys())
                debug_info["cookie_count"] = len(self.cookies)
            except Exception as e:
                debug_info["cookie_error"] = str(e)

        return debug_info
    


# 全局cookie管理器实例
cookie_manager = CookieManager()

def get_persistent_analysis_id() -> Optional[str]:
    """获取持久化的分析ID（优先级：session state > cookie > Redis/文件）"""
    try:
        # 1. 首先检查session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. 检查cookie
        cookie_state = cookie_manager.get_analysis_state()
        if cookie_state:
            analysis_id = cookie_state.get('analysis_id')
            if analysis_id:
                # 恢复到session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (cookie_state.get('status') == 'running')
                return analysis_id
        
        # 3. 最后从Redis/文件恢复
        from .async_progress_tracker import get_latest_analysis_id
        latest_id = get_latest_analysis_id()
        if latest_id:
            st.session_state.current_analysis_id = latest_id
            return latest_id
        
        return None
        
    except Exception as e:
        st.warning(f"⚠️ 获取持久化分析ID失败: {e}")
        return None

def set_persistent_analysis_id(analysis_id: str, status: str = "running", 
                              stock_symbol: str = "", market_type: str = ""):
    """设置持久化的分析ID"""
    try:
        # 设置到session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        
        # 设置到cookie
        cookie_manager.set_analysis_state(analysis_id, status, stock_symbol, market_type)
        
    except Exception as e:
        st.warning(f"⚠️ 设置持久化分析ID失败: {e}")
