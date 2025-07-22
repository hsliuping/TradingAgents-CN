"""
Session persistence manager - a solution that does not rely on cookies
Using Redis/file storage + browser fingerprint to implement state persistence across page refreshes
"""

import streamlit as st
import hashlib
import time
import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

class SessionPersistenceManager:
    """Session persistence manager"""
    
    def __init__(self):
        self.session_file_prefix = "session_"
        self.max_age_hours = 24  # Session validity period 24 hours
        
    def _get_browser_fingerprint(self) -> str:
        """Generates a browser fingerprint (based on available information)"""
        try:
            # Get Streamlit session information
            session_id = st.runtime.get_instance().get_client(st.session_state._get_session_id()).session.id
            
            # Use session_id as fingerprint
            fingerprint = hashlib.md5(session_id.encode()).hexdigest()[:12]
            return f"browser_{fingerprint}"
            
        except Exception:
            # If session_id cannot be obtained, use timestamp as fallback
            timestamp = str(int(time.time() / 3600))  # Group by hour
            fingerprint = hashlib.md5(timestamp.encode()).hexdigest()[:12]
            return f"fallback_{fingerprint}"
    
    def _get_session_file_path(self, fingerprint: str) -> str:
        """Gets the session file path"""
        return f"./data/{self.session_file_prefix}{fingerprint}.json"
    
    def save_analysis_state(self, analysis_id: str, status: str = "running", 
                           stock_symbol: str = "", market_type: str = ""):
        """Saves analysis state to persistent storage"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            
            session_data = {
                "analysis_id": analysis_id,
                "status": status,
                "stock_symbol": stock_symbol,
                "market_type": market_type,
                "timestamp": time.time(),
                "fingerprint": fingerprint,
                "last_update": time.time()
            }
            
            # Save to file
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # Also save to session state
            st.session_state.current_analysis_id = analysis_id
            st.session_state.analysis_running = (status == 'running')
            st.session_state.last_stock_symbol = stock_symbol
            st.session_state.last_market_type = market_type
            
            return True
            
        except Exception as e:
            st.warning(f"⚠️ Failed to save session state: {e}")
            return False
    
    def load_analysis_state(self) -> Optional[Dict[str, Any]]:
        """Loads analysis state from persistent storage"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            # Check if file exists
            if not os.path.exists(session_file):
                return None
            
            # Read session data
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Check if expired
            timestamp = session_data.get("timestamp", 0)
            if time.time() - timestamp > (self.max_age_hours * 3600):
                # Expired, delete file
                os.remove(session_file)
                return None
            
            return session_data
            
        except Exception as e:
            st.warning(f"⚠️ Failed to load session state: {e}")
            return None
    
    def clear_analysis_state(self):
        """Clears analysis state"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            # Delete file
            if os.path.exists(session_file):
                os.remove(session_file)
            
            # Clear session state
            keys_to_remove = ['current_analysis_id', 'analysis_running', 'last_stock_symbol', 'last_market_type']
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]
            
        except Exception as e:
            st.warning(f"⚠️ Failed to clear session state: {e}")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Gets debug information"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            debug_info = {
                "fingerprint": fingerprint,
                "session_file": session_file,
                "file_exists": os.path.exists(session_file),
                "session_state_keys": [k for k in st.session_state.keys() if 'analysis' in k.lower()]
            }
            
            if os.path.exists(session_file):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    debug_info["session_data"] = session_data
                    debug_info["age_hours"] = (time.time() - session_data.get("timestamp", 0)) / 3600
                except Exception as e:
                    debug_info["file_error"] = str(e)
            
            return debug_info
            
        except Exception as e:
            return {"error": str(e)}

# Global session persistence manager instance
session_persistence = SessionPersistenceManager()

def get_persistent_analysis_id() -> Optional[str]:
    """Gets the persistent analysis ID (priority: session state > session file > Redis/file)"""
    try:
        # 1. First check session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. Check session file
        session_data = session_persistence.load_analysis_state()
        if session_data:
            analysis_id = session_data.get('analysis_id')
            if analysis_id:
                # Restore to session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (session_data.get('status') == 'running')
                st.session_state.last_stock_symbol = session_data.get('stock_symbol', '')
                st.session_state.last_market_type = session_data.get('market_type', '')
                return analysis_id
        
        # 3. Finally restore the latest analysis from Redis/file
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
    """Sets the persistent analysis ID"""
    try:
        # Set to session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        st.session_state.last_stock_symbol = stock_symbol
        st.session_state.last_market_type = market_type
        
        # Save to session file
        session_persistence.save_analysis_state(analysis_id, status, stock_symbol, market_type)
        
    except Exception as e:
        st.warning(f"⚠️ Failed to set persistent analysis ID: {e}")
