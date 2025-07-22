"""
Cookie manager - to solve the problem of Streamlit session state page refresh loss
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
    st.warning("⚠️ streamlit-cookies-manager is not installed, Cookie functionality is unavailable")

class CookieManager:
    """Cookie manager, used for persistent storage of analysis state"""

    def __init__(self):
        self.cookie_name = "tradingagents_analysis_state"
        self.max_age_days = 7  # Cookie valid for 7 days

        # Initialize Cookie manager
        if COOKIES_AVAILABLE:
            try:
                self.cookies = EncryptedCookieManager(
                    prefix="tradingagents_",
                    password="tradingagents_secret_key_2025"  # Fixed key
                )

                # Check if Cookie manager is ready
                if not self.cookies.ready():
                    # If not ready, first show waiting message, then stop execution
                    st.info("🔄 Initializing Cookie manager, please wait...")
                    st.stop()

            except Exception as e:
                st.warning(f"⚠️ Cookie manager initialization failed: {e}")
                self.cookies = None
        else:
            self.cookies = None
    
    def set_analysis_state(self, analysis_id: str, status: str = "running",
                          stock_symbol: str = "", market_type: str = ""):
        """Set analysis state to cookie"""
        try:
            state_data = {
                "analysis_id": analysis_id,
                "status": status,
                "stock_symbol": stock_symbol,
                "market_type": market_type,
                "timestamp": time.time(),
                "created_at": datetime.now().isoformat()
            }

            # Store in session state (as a backup)
            st.session_state[f"cookie_{self.cookie_name}"] = state_data

            # Use professional Cookie manager to set cookie
            if self.cookies:
                self.cookies[self.cookie_name] = json.dumps(state_data)
                self.cookies.save()

            return True

        except Exception as e:
            st.error(f"❌ Failed to set analysis state: {e}")
            return False
    
    def get_analysis_state(self) -> Optional[Dict[str, Any]]:
        """Get analysis state from cookie"""
        try:
            # First try to get from session state (if it exists)
            session_data = st.session_state.get(f"cookie_{self.cookie_name}")
            if session_data:
                return session_data

            # Try to get from cookie
            if self.cookies and self.cookie_name in self.cookies:
                cookie_data = self.cookies[self.cookie_name]
                if cookie_data:
                    state_data = json.loads(cookie_data)

                    # Check if expired (7 days)
                    timestamp = state_data.get("timestamp", 0)
                    if time.time() - timestamp < (self.max_age_days * 24 * 3600):
                        # Restore to session state
                        st.session_state[f"cookie_{self.cookie_name}"] = state_data
                        return state_data
                    else:
                        # Expired, clear cookie
                        self.clear_analysis_state()

            return None

        except Exception as e:
            st.warning(f"⚠️ Failed to get analysis state: {e}")
            return None
    
    def clear_analysis_state(self):
        """Clear analysis state"""
        try:
            # Clear session state
            if f"cookie_{self.cookie_name}" in st.session_state:
                del st.session_state[f"cookie_{self.cookie_name}"]

            # Clear cookie
            if self.cookies and self.cookie_name in self.cookies:
                del self.cookies[self.cookie_name]
                self.cookies.save()

        except Exception as e:
            st.warning(f"⚠️ Failed to clear analysis state: {e}")

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information"""
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
    


# Global cookie manager instance
cookie_manager = CookieManager()

def get_persistent_analysis_id() -> Optional[str]:
    """Get persistent analysis ID (priority: session state > cookie > Redis/file)"""
    try:
        # 1. First check session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. Check cookie
        cookie_state = cookie_manager.get_analysis_state()
        if cookie_state:
            analysis_id = cookie_state.get('analysis_id')
            if analysis_id:
                # Restore to session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (cookie_state.get('status') == 'running')
                return analysis_id
        
        # 3. Finally restore from Redis/file
        from .async_progress_tracker import get_latest_analysis_id
        latest_id = get_latest_analysis_id()
        if latest_id:
            st.session_state.current_analysis_id = latest_id
            return latest_id
        
        return None
        
    except Exception as e:
        st.warning(f"⚠️ Failed to get persistent analysis ID: {e}")
        return None

def set_persistent_analysis_id(analysis_id: str, status: str = "running", 
                              stock_symbol: str = "", market_type: str = ""):
    """Set persistent analysis ID"""
    try:
        # Set to session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        
        # Set to cookie
        cookie_manager.set_analysis_state(analysis_id, status, stock_symbol, market_type)
        
    except Exception as e:
        st.warning(f"⚠️ Failed to set persistent analysis ID: {e}")
