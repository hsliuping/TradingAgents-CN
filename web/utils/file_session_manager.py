"""
File-based session manager - a reliable solution not relying on Redis
Applicable when Redis is not available or Redis connection fails
"""

import streamlit as st
import json
import time
import hashlib
import os
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

class FileSessionManager:
    """File-based session manager"""
    
    def __init__(self):
        self.data_dir = Path("./data/sessions")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = 24  # Session validity period 24 hours
        
    def _get_browser_fingerprint(self) -> str:
        """Generate browser fingerprint"""
        try:
            # Method 1: Use a fixed session identifier
            # Check if the session identifier is already saved in session_state
            if hasattr(st.session_state, 'file_session_fingerprint'):
                return st.session_state.file_session_fingerprint

            # Method 2: Find the most recent session file (within 24 hours)
            current_time = time.time()
            recent_files = []

            for session_file in self.data_dir.glob("*.json"):
                try:
                    file_age = current_time - session_file.stat().st_mtime
                    if file_age < (24 * 3600):  # Files within 24 hours
                        recent_files.append((session_file, file_age))
                except:
                    continue

            if recent_files:
                # Use the newest session file
                recent_files.sort(key=lambda x: x[1])  # Sort by file age
                newest_file = recent_files[0][0]
                fingerprint = newest_file.stem
                # Save to session_state for subsequent use
                st.session_state.file_session_fingerprint = fingerprint
                return fingerprint

            # Method 3: Create a new session
            fingerprint = f"session_{uuid.uuid4().hex[:12]}"
            st.session_state.file_session_fingerprint = fingerprint
            return fingerprint

        except Exception:
            # Method 4: Final fallback
            fingerprint = f"fallback_{uuid.uuid4().hex[:8]}"
            if hasattr(st, 'session_state'):
                st.session_state.file_session_fingerprint = fingerprint
            return fingerprint
    
    def _get_session_file_path(self, fingerprint: str) -> Path:
        """Get session file path"""
        return self.data_dir / f"{fingerprint}.json"
    
    def _cleanup_old_sessions(self):
        """Clean up expired session files"""
        try:
            current_time = time.time()
            max_age_seconds = self.max_age_hours * 3600
            
            for session_file in self.data_dir.glob("*.json"):
                try:
                    # Check file modification time
                    file_age = current_time - session_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        session_file.unlink()
                except Exception:
                    continue
                    
        except Exception:
            pass  # Cleanup failure does not affect main functionality
    
    def save_analysis_state(self, analysis_id: str, status: str = "running",
                           stock_symbol: str = "", market_type: str = "",
                           form_config: Dict[str, Any] = None):
        """Save analysis status and form configuration"""
        try:
            # Clean up expired files
            self._cleanup_old_sessions()

            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)

            session_data = {
                "analysis_id": analysis_id,
                "status": status,
                "stock_symbol": stock_symbol,
                "market_type": market_type,
                "timestamp": time.time(),
                "last_update": time.time(),
                "fingerprint": fingerprint
            }

            # Add form configuration
            if form_config:
                session_data["form_config"] = form_config
            
            # Save to file
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            # Also save to session state
            st.session_state.current_analysis_id = analysis_id
            st.session_state.analysis_running = (status == 'running')
            st.session_state.last_stock_symbol = stock_symbol
            st.session_state.last_market_type = market_type
            st.session_state.session_fingerprint = fingerprint

            return True
            
        except Exception as e:
            st.warning(f"⚠️ Failed to save session state: {e}")
            return False
    
    def load_analysis_state(self) -> Optional[Dict[str, Any]]:
        """Load analysis status"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)

            # Check if file exists
            if not session_file.exists():
                return None

            # Read session data
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Check if expired
            timestamp = session_data.get("timestamp", 0)
            if time.time() - timestamp > (self.max_age_hours * 3600):
                # Expired, delete file
                session_file.unlink()
                return None

            return session_data
            
        except Exception as e:
            st.warning(f"⚠️ Failed to load session state: {e}")
            return None
    
    def clear_analysis_state(self):
        """Clear analysis status"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            # Delete file
            if session_file.exists():
                session_file.unlink()
            
            # Clear session state
            keys_to_remove = ['current_analysis_id', 'analysis_running', 'last_stock_symbol', 'last_market_type', 'session_fingerprint']
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]
            
        except Exception as e:
            st.warning(f"⚠️ Failed to clear session state: {e}")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information"""
        try:
            fingerprint = self._get_browser_fingerprint()
            session_file = self._get_session_file_path(fingerprint)
            
            debug_info = {
                "fingerprint": fingerprint,
                "session_file": str(session_file),
                "file_exists": session_file.exists(),
                "data_dir": str(self.data_dir),
                "session_state_keys": [k for k in st.session_state.keys() if 'analysis' in k.lower() or 'session' in k.lower()]
            }
            
            # Count session files
            session_files = list(self.data_dir.glob("*.json"))
            debug_info["total_session_files"] = len(session_files)
            debug_info["session_files"] = [f.name for f in session_files]
            
            if session_file.exists():
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

# Global file session manager instance
file_session_manager = FileSessionManager()

def get_persistent_analysis_id() -> Optional[str]:
    """Get persistent analysis ID (priority: session state > file session > Redis/file)"""
    try:
        # 1. First check session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. Check file session data
        session_data = file_session_manager.load_analysis_state()
        if session_data:
            analysis_id = session_data.get('analysis_id')
            if analysis_id:
                # Restore to session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (session_data.get('status') == 'running')
                st.session_state.last_stock_symbol = session_data.get('stock_symbol', '')
                st.session_state.last_market_type = session_data.get('market_type', '')
                st.session_state.session_fingerprint = session_data.get('fingerprint', '')

                # Restore form configuration
                if 'form_config' in session_data:
                    st.session_state.form_config = session_data['form_config']

                return analysis_id
        
        # 3. Finally restore the latest analysis from Redis/file
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
    """Set persistent analysis ID and form configuration"""
    try:
        # Set to session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        st.session_state.last_stock_symbol = stock_symbol
        st.session_state.last_market_type = market_type

        # Save form configuration to session state
        if form_config:
            st.session_state.form_config = form_config

        # Save to file session
        file_session_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)
        
    except Exception as e:
        st.warning(f"⚠️ Failed to set persistent analysis ID: {e}")
