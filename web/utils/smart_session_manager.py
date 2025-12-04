"""
智能会话管理器 - 自动选择最佳存储方案
优先级：Redis > 文件存储
"""

import streamlit as st
import os
from typing import Optional, Dict, Any

class SmartSessionManager:
    """智能会话管理器"""
    
    def __init__(self):
        self.redis_manager = None
        self.file_manager = None
        self.use_redis = self._init_redis_manager()
        self._init_file_manager()
        
    def _init_redis_manager(self) -> bool:
        """尝试初始化Redis管理器"""
        try:
            from .redis_session_manager import redis_session_manager
            
            # 测试Redis连接
            if redis_session_manager.use_redis:
                self.redis_manager = redis_session_manager
                return True
            else:
                return False
                
        except Exception:
            return False
    
    def _init_file_manager(self):
        """初始化文件管理器"""
        try:
            from .file_session_manager import file_session_manager
            self.file_manager = file_session_manager
        except Exception as e:
            st.error(f"❌ 文件会话管理器初始化失败: {e}")
    
    def save_analysis_state(self, analysis_id: str, status: str = "running",
                           stock_symbol: str = "", market_type: str = "",
                           form_config: Dict[str, Any] = None):
        """保存分析状态和表单配置"""
        success = False
        
        # 优先使用Redis
        if self.use_redis and self.redis_manager:
            try:
                success = self.redis_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)
                if success:
                    return True
            except Exception as e:
                st.warning(f"⚠️ Redis保存失败，切换到文件存储: {e}")
                self.use_redis = False

        # 使用文件存储作为fallback
        if self.file_manager:
            try:
                success = self.file_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)
                return success
            except Exception as e:
                st.error(f"❌ 文件存储也失败了: {e}")
                return False
        
        return False
    
    def load_analysis_state(self) -> Optional[Dict[str, Any]]:
        """加载分析状态"""
        # 优先从Redis加载
        if self.use_redis and self.redis_manager:
            try:
                data = self.redis_manager.load_analysis_state()
                if data:
                    return data
            except Exception as e:
                st.warning(f"⚠️ Redis加载失败，切换到文件存储: {e}")
                self.use_redis = False
        
        # 从文件存储加载
        if self.file_manager:
            try:
                return self.file_manager.load_analysis_state()
            except Exception as e:
                st.error(f"❌ 文件存储加载失败: {e}")
                return None
        
        return None
    
    def clear_analysis_state(self):
        """清除分析状态"""
        # 清除Redis中的数据
        if self.use_redis and self.redis_manager:
            try:
                self.redis_manager.clear_analysis_state()
            except Exception:
                pass
        
        # 清除文件中的数据
        if self.file_manager:
            try:
                self.file_manager.clear_analysis_state()
            except Exception:
                pass
    
    def get_debug_info(self) -> Dict[str, Any]:
        """获取调试信息"""
        debug_info = {
            "storage_type": "Redis" if self.use_redis else "文件存储",
            "redis_available": self.redis_manager is not None,
            "file_manager_available": self.file_manager is not None,
            "use_redis": self.use_redis
        }
        
        # 获取当前使用的管理器的调试信息
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

# 全局智能会话管理器实例
smart_session_manager = SmartSessionManager()

def get_persistent_analysis_id() -> Optional[str]:
    """获取持久化的分析ID"""
    try:
        # 1. 首先检查session state
        if st.session_state.get('current_analysis_id'):
            return st.session_state.current_analysis_id
        
        # 2. 从会话存储加载
        session_data = smart_session_manager.load_analysis_state()
        if session_data:
            analysis_id = session_data.get('analysis_id')
            if analysis_id:
                # 恢复到session state
                st.session_state.current_analysis_id = analysis_id
                st.session_state.analysis_running = (session_data.get('status') == 'running')
                st.session_state.last_stock_symbol = session_data.get('stock_symbol', '')
                st.session_state.last_market_type = session_data.get('market_type', '')
                return analysis_id
        
        # 3. 最后从分析数据恢复最新分析
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
        st.warning(f"⚠️ 获取持久化分析ID失败: {e}")
        return None

def set_persistent_analysis_id(analysis_id: str, status: str = "running",
                              stock_symbol: str = "", market_type: str = "",
                              form_config: Dict[str, Any] = None):
    """设置持久化的分析ID和表单配置"""
    try:
        # 设置到session state
        st.session_state.current_analysis_id = analysis_id
        st.session_state.analysis_running = (status == 'running')
        st.session_state.last_stock_symbol = stock_symbol
        st.session_state.last_market_type = market_type

        # 保存表单配置到session state
        if form_config:
            st.session_state.form_config = form_config

        # 保存到会话存储
        smart_session_manager.save_analysis_state(analysis_id, status, stock_symbol, market_type, form_config)

    except Exception as e:
        st.warning(f"⚠️ 设置持久化分析ID失败: {e}")

def get_session_debug_info() -> Dict[str, Any]:
    """获取会话管理器调试信息"""
    return smart_session_manager.get_debug_info()
