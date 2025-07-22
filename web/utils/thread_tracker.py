"""
Analyze thread tracker
Used to track and detect the alive status of analysis threads
"""

import threading
import time
from typing import Dict, Optional
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('web')

class ThreadTracker:
    """Thread tracker"""
    
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
    
    def register_thread(self, analysis_id: str, thread: threading.Thread):
        """Register analysis thread"""
        with self._lock:
            self._threads[analysis_id] = thread
            logger.info(f"📊 [Thread Tracker] Register analysis thread: {analysis_id}")
    
    def unregister_thread(self, analysis_id: str):
        """Unregister analysis thread"""
        with self._lock:
            if analysis_id in self._threads:
                del self._threads[analysis_id]
                logger.info(f"📊 [Thread Tracker] Unregister analysis thread: {analysis_id}")
    
    def is_thread_alive(self, analysis_id: str) -> bool:
        """Check if analysis thread is alive"""
        with self._lock:
            thread = self._threads.get(analysis_id)
            if thread is None:
                return False
            
            is_alive = thread.is_alive()
            if not is_alive:
                # Thread is dead, auto-clean up
                del self._threads[analysis_id]
                logger.info(f"📊 [Thread Tracker] Thread is dead, auto-cleaning up: {analysis_id}")
            
            return is_alive
    
    def get_alive_threads(self) -> Dict[str, threading.Thread]:
        """Get all alive threads"""
        with self._lock:
            alive_threads = {}
            dead_threads = []
            
            for analysis_id, thread in self._threads.items():
                if thread.is_alive():
                    alive_threads[analysis_id] = thread
                else:
                    dead_threads.append(analysis_id)
            
            # Clean up dead threads
            for analysis_id in dead_threads:
                del self._threads[analysis_id]
                logger.info(f"📊 [Thread Tracker] Cleaning up dead thread: {analysis_id}")
            
            return alive_threads
    
    def cleanup_dead_threads(self):
        """Clean up all dead threads"""
        self.get_alive_threads()  # This will automatically clean up dead threads
    
    def get_thread_info(self, analysis_id: str) -> Optional[Dict]:
        """Get thread info"""
        with self._lock:
            thread = self._threads.get(analysis_id)
            if thread is None:
                return None
            
            return {
                'analysis_id': analysis_id,
                'thread_name': thread.name,
                'thread_id': thread.ident,
                'is_alive': thread.is_alive(),
                'is_daemon': thread.daemon
            }
    
    def get_all_thread_info(self) -> Dict[str, Dict]:
        """Get all thread info"""
        with self._lock:
            info = {}
            for analysis_id, thread in self._threads.items():
                info[analysis_id] = {
                    'analysis_id': analysis_id,
                    'thread_name': thread.name,
                    'thread_id': thread.ident,
                    'is_alive': thread.is_alive(),
                    'is_daemon': thread.daemon
                }
            return info

# Global thread tracker instance
thread_tracker = ThreadTracker()

def register_analysis_thread(analysis_id: str, thread: threading.Thread):
    """Register analysis thread"""
    thread_tracker.register_thread(analysis_id, thread)

def unregister_analysis_thread(analysis_id: str):
    """Unregister analysis thread"""
    thread_tracker.unregister_thread(analysis_id)

def is_analysis_thread_alive(analysis_id: str) -> bool:
    """Check if analysis thread is alive"""
    return thread_tracker.is_thread_alive(analysis_id)

def get_analysis_thread_info(analysis_id: str) -> Optional[Dict]:
    """Get analysis thread info"""
    return thread_tracker.get_thread_info(analysis_id)

def cleanup_dead_analysis_threads():
    """Clean up all dead analysis threads"""
    thread_tracker.cleanup_dead_threads()

def get_all_analysis_threads() -> Dict[str, Dict]:
    """Get all analysis thread info"""
    return thread_tracker.get_all_thread_info()

def check_analysis_status(analysis_id: str) -> str:
    """
    Check analysis status
    Returns: 'running', 'completed', 'failed', 'not_found'
    """
    # First check if thread is alive
    if is_analysis_thread_alive(analysis_id):
        return 'running'
    
    # Thread does not exist, check progress data to determine final status
    try:
        from .async_progress_tracker import get_progress_by_id
        progress_data = get_progress_by_id(analysis_id)
        
        if progress_data:
            status = progress_data.get('status', 'unknown')
            if status in ['completed', 'failed']:
                return status
            else:
                # Status shows running but thread is dead, indicating abnormal termination
                return 'failed'
        else:
            return 'not_found'
    except Exception as e:
        logger.error(f"📊 [Status Check] Failed to check progress data: {e}")
        return 'not_found'
