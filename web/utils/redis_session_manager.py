"""
Session manager based on Redis - the most reliable cross-page refresh state persistence solution
"""

import streamlit as st
import json
import time
import hashlib
import os
from typing import Optional, Dict, Any

class RedisSessionManager:
    """Session manager based on Redis"""
    
    def __init__(self):
        self.redis_client = None
        self.use_redis = self._init_redis()
        self.session_prefix = "streamlit_session:"
        self.max_age_hours = 24  # Session validity period 24 hours
        
    def _init_redis(self) -> bool:
        """Initialize Redis connection"""
        try:
            # First check the REDIS_ENABLED environment variable
            redis_enabled = os.getenv('REDIS_ENABLED', 'false').lower()
            if redis_enabled != 'true':
                return False

            import redis

            # Get Redis configuration from environment variables
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD', None)
            redis_db = int(os.getenv('REDIS_DB', 0))
            
            # Create Redis connection
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            return True
            
        except Exception as e:
            # Only show connection failed warning if Redis is enabled
            redis_enabled = os.getenv('REDIS_ENABLED', 'false').lower()
            if redis_enabled == 'true':
                st.warning(f"⚠️ Redis connection failed, using file storage: {e}")
            return False
    
    def _get_session_key(self) -> str:
        """Generate session key"""
        try:
            # Try to get Streamlit session information
            if hasattr(st, 'session_state') and hasattr(st.session_state, '_get_session_id'):
                session_id = st.session_state._get_session_id()
                return f"{self.session_prefix}{session_id}"
            
            # If session_id cannot be obtained, use IP+UserAgent hash
            # Note: This is a fallback solution, which may not be accurate
            import streamlit.web.server.websocket_headers as wsh
            headers = wsh.get_websocket_headers()
            
            user_agent = headers.get('User-Agent', 'unknown')
            x_forwarded_for = headers.get('X-Forwarded-For', 'unknown')
            
            # Generate a unique identifier based on user information
            unique_str = f"{user_agent}_{x_forwarded_for}_{int(time.time() / 3600)}"  # Group by hour
            session_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
            
            return f"{self.session_prefix}fallback_{session_hash}"
            
        except Exception:
            # Final fallback: use timestamp
            timestamp_hash = hashlib.md5(str(int(time.time() / 3600)).encode()).hexdigest()[:16]
            return f"{self.session_prefix}timestamp_{timestamp_hash}"
    
    def save_analysis_state(self, analysis_id: str, status: str = "running",
                           stock_symbol: str = "", market_type: str = "",
                           form_config: Dict[str, Any] = None):
        """Save analysis status and form configuration"""
        try:
            session_data = {
                "analysis_id": analysis_id,
                "status": status,
                "stock_symbol": stock_symbol,
                "market_type": market_type,
                "timestamp": time.time(),
                "last_update": time.time()
            }

            # Add form configuration
            if form_config:
                session_data["form_config"] = form_config
            
            session_key = self._get_session_key()
            
            if self.use_redis:
                # Save to Redis, set expiration time
                self.redis_client.setex(
                    session_key,
                    self.max_age_hours * 3600,  # Expiration time (seconds)
                    json.dumps(session_data)
                )
            else:
                # Save to file (fallback)
                self._save_to_file(session_key, session_data)
            
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
        """Load analysis status"""
        try:
            session_key = self._get_session_key()
            
            if self.use_redis:
                # Load from Redis
                data = self.redis_client.get(session_key)
                if data:
                    return json.loads(data)
            else:
                # Load from file (fallback)
                return self._load_from_file(session_key)
            
            return None
            
        except Exception as e:
            st.warning(f"⚠️ Failed to load session state: {e}")
            return None
    
    def clear_analysis_state(self):
        """Clear analysis status"""
        try:
            session_key = self._get_session_key()
            
            if self.use_redis:
                # Delete from Redis
                self.redis_client.delete(session_key)
            else:
                # Delete from file (fallback)
                self._delete_file(session_key)
            
            # Clear session state
            keys_to_remove = ['current_analysis_id', 'analysis_running', 'last_stock_symbol', 'last_market_type']
            for key in keys_to_remove:
                if key in st.session_state:
                    del st.session_state[key]
            
        except Exception as e:
            st.warning(f"⚠️ Failed to clear session state: {e}")
    
    def _save_to_file(self, session_key: str, session_data: Dict[str, Any]):
        """Save to file (fallback solution)"""
        try:
            import os
            os.makedirs("./data", exist_ok=True)
            
            filename = f"./data/{session_key.replace(':', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            st.warning(f"⚠️ Failed to save file: {e}")
    
    def _load_from_file(self, session_key: str) -> Optional[Dict[str, Any]]:
        """Load from file (fallback solution)"""
        try:
            filename = f"./data/{session_key.replace(':', '_')}.json"
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if expired
                timestamp = data.get("timestamp", 0)
                if time.time() - timestamp < (self.max_age_hours * 3600):
                    return data
                else:
                    # Expired, delete file
                    os.remove(filename)
            
            return None
            
        except Exception as e:
            st.warning(f"⚠️ Failed to load file: {e}")
            return None
    
    def _delete_file(self, session_key: str):
        """Delete file (fallback solution)"""
        try:
            filename = f"./data/{session_key.replace(':', '_')}.json"
            if os.path.exists(filename):
                os.remove(filename)
                
        except Exception as e:
            st.warning(f"⚠️ Failed to delete file: {e}")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information"""
        try:
            session_key = self._get_session_key()
            
            debug_info = {
                "use_redis": self.use_redis,
                "session_key": session_key,
                "redis_connected": False,
                "session_state_keys": [k for k in st.session_state.keys() if 'analysis' in k.lower()]
            }
            
            if self.use_redis and self.redis_client:
                try:
                    self.redis_client.ping()
                    debug_info["redis_connected"] = True
                    debug_info["redis_info"] = {
                        "host": os.getenv('REDIS_HOST', 'localhost'),
                        "port": os.getenv('REDIS_PORT', 6379),
                        "db": os.getenv('REDIS_DB', 0)
                    }
                    
                    # Check session data
                    data = self.redis_client.get(session_key)
                    if data:
                        debug_info["session_data"] = json.loads(data)
                    else:
                        debug_info["session_data"] = None
                        
                except Exception as e:
                    debug_info["redis_error"] = str(e)
            
            return debug_info
            
        except Exception as e:
            return {"error": str(e)}

# Global Redis session manager instance
redis_session_manager = RedisSessionManager()

def get_persistent_analysis_id() -> Optional[str]:
    """Get persistent analysis ID (priority: session state > Redis session > Redis analysis data)"""
    try:
        # 1. First check session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. Check Redis session data
        session_data = redis_session_manager.load_analysis_state()
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
    """Set persistent analysis ID"""
    try:
        # Set to session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        st.session_state.last_stock_symbol = stock_symbol
        st.session_state.last_market_type = market_type
        
        # Save to Redis session
        redis_session_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type)
        
    except Exception as e:
        st.warning(f"⚠️ Failed to set persistent analysis ID: {e}")
