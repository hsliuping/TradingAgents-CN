"""
Smart Session Manager - Automatically selects the best storage solution
Priority: Redis > File Storage
"""

import streamlit as st
import os
from typing import Optional, Dict, Any

class SmartSessionManager:
    """Smart Session Manager"""
    
    def __init__(self):
        self.redis_manager = None
        self.file_manager = None
        self.use_redis = self._init_redis_manager()
        self._init_file_manager()
        
    def _init_redis_manager(self) -> bool:
        """Attempts to initialize the Redis manager"""
        try:
            from .redis_session_manager import redis_session_manager
            
            # Test Redis connection
            if redis_session_manager.use_redis:
                self.redis_manager = redis_session_manager
                return True
            else:
                return False
                
        except Exception:
            return False
    
    def _init_file_manager(self):
        """Initializes the file manager"""
        try:
            from .file_session_manager import file_session_manager
            self.file_manager = file_session_manager
        except Exception as e:
            st.error(f"❌ File session manager initialization failed: {e}")
    
    def save_analysis_state(self, analysis_id: str, status: str = "running",
                           stock_symbol: str = "", market_type: str = "",
                           form_config: Dict[str, Any] = None):
        """Saves analysis status and form configuration"""
        success = False
        
        # Prioritize Redis
        if self.use_redis and self.redis_manager:
            try:
                success = self.redis_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)
                if success:
                    return True
            except Exception as e:
                st.warning(f"⚠️ Redis save failed, switching to file storage: {e}")
                self.use_redis = False

        # Use file storage as fallback
        if self.file_manager:
            try:
                success = self.file_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)
                return success
            except Exception as e:
                st.error(f"❌ File storage also failed: {e}")
                return False
        
        return False
    
    def load_analysis_state(self) -> Optional[Dict[str, Any]]:
        """Loads analysis status"""
        # Prioritize loading from Redis
        if self.use_redis and self.redis_manager:
            try:
                data = self.redis_manager.load_analysis_state()
                if data:
                    return data
            except Exception as e:
                st.warning(f"⚠️ Redis load failed, switching to file storage: {e}")
                self.use_redis = False
        
        # Load from file storage
        if self.file_manager:
            try:
                return self.file_manager.load_analysis_state()
            except Exception as e:
                st.error(f"❌ File storage load failed: {e}")
                return None
        
        return None
    
    def clear_analysis_state(self):
        """Clears analysis status"""
        # Clear data from Redis
        if self.use_redis and self.redis_manager:
            try:
                self.redis_manager.clear_analysis_state()
            except Exception:
                pass
        
        # Clear data from file
        if self.file_manager:
            try:
                self.file_manager.clear_analysis_state()
            except Exception:
                pass
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Gets debug information"""
        debug_info = {
            "storage_type": "Redis" if self.use_redis else "File Storage",
            "redis_available": self.redis_manager is not None,
            "file_manager_available": self.file_manager is not None,
            "use_redis": self.use_redis
        }
        
        # Get debug information for the currently used manager
        if self.use_redis and self.redis_manager:
            try:
                redis_debug = self.redis_manager.get_debug_info()
                debug_info.update({"redis_debug": redis_debug})
            except Exception as e:
                debug_info["redis_debug_error"] = str(e)
        
        if self.file_manager:
            try:
                file_debug = self.file_manager.get_debug_info()
                debug_info.update({"file_debug": file_debug})
            except Exception as e:
                debug_info["file_debug_error"] = str(e)
        
        return debug_info

# Global smart session manager instance
smart_session_manager = SmartSessionManager()

def get_persistent_analysis_id() -> Optional[str]:
    """Gets the persistent analysis ID"""
    try:
        # 1. First check session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. Load from session storage
        session_data = smart_session_manager.load_analysis_state()
        if session_data:
            analysis_id = session_data.get('analysis_id')
            if analysis_id:
                # Restore to session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (session_data.get('status') == 'running')
                st.session_state.last_stock_symbol = session_data.get('stock_symbol', '')
                st.session_state.last_market_type = session_data.get('market_type', '')
                return analysis_id
        
        # 3. Finally restore the latest analysis from analysis data
        try:
            from .async_progress_tracker import get_latest_analysis_id
            latest_id = get_latest_analysis_id()
            if latest_id:
                st.session_state.current_analysis_id = latest_id
                return latest_id
        except Exception:
            pass
        
        return None
        
    except Exception as e:
        st.warning(f"⚠️ Failed to get persistent analysis ID: {e}")
        return None

def set_persistent_analysis_id(analysis_id: str, status: str = "running",
                              stock_symbol: str = "", market_type: str = "",
                              form_config: Dict[str, Any] = None):
    """Sets the persistent analysis ID and form configuration"""
    try:
        # Set to session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        st.session_state.last_stock_symbol = stock_symbol
        st.session_state.last_market_type = market_type

        # Save form configuration to session state
        if form_config:
            st.session_state.form_config = form_config

        # Save to session storage
        smart_session_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)

    except Exception as e:
        st.warning(f"⚠️ Failed to set persistent analysis ID: {e}")

def get_session_debug_info() -> Dict[str, Any]:
    """Gets session manager debug information"""
    return smart_session_manager.get_debug_info()
