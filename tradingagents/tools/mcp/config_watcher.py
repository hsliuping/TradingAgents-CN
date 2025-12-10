"""
MCP 配置文件监视器

提供配置文件变更检测和热重载功能。
"""
import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """
    配置文件监视器
    
    监视配置文件的变更并触发重载回调。
    使用轮询方式检测文件变更，兼容所有平台。
    """
    
    DEFAULT_POLL_INTERVAL = 5.0  # 秒
    
    def __init__(
        self,
        config_path: Path,
        on_change: Callable[[], None],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        """
        初始化配置监视器
        
        Args:
            config_path: 配置文件路径
            on_change: 文件变更时的回调函数
            poll_interval: 轮询间隔（秒）
        """
        self.config_path = Path(config_path)
        self.on_change = on_change
        self.poll_interval = poll_interval
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: Optional[float] = None
        self._last_size: Optional[int] = None
    
    def _get_file_info(self) -> tuple:
        """获取文件信息（修改时间和大小）"""
        try:
            stat = self.config_path.stat()
            return stat.st_mtime, stat.st_size
        except FileNotFoundError:
            return None, None
        except Exception as e:
            logger.warning(f"[ConfigWatcher] 获取文件信息失败: {e}")
            return None, None
    
    def _check_for_changes(self) -> bool:
        """
        检查文件是否有变更
        
        Returns:
            True 如果文件有变更
        """
        mtime, size = self._get_file_info()
        
        if mtime is None:
            # 文件不存在或无法访问
            if self._last_mtime is not None:
                # 文件被删除
                self._last_mtime = None
                self._last_size = None
                return True
            return False
        
        if self._last_mtime is None:
            # 首次检查或文件重新创建
            self._last_mtime = mtime
            self._last_size = size
            return False
        
        if mtime != self._last_mtime or size != self._last_size:
            # 文件有变更
            self._last_mtime = mtime
            self._last_size = size
            return True
        
        return False
    
    def _poll_loop(self):
        """轮询循环"""
        logger.info(f"[ConfigWatcher] 开始监视配置文件: {self.config_path}")
        
        # 初始化文件信息
        self._last_mtime, self._last_size = self._get_file_info()
        
        while self._running:
            try:
                if self._check_for_changes():
                    logger.info(f"[ConfigWatcher] 检测到配置文件变更: {self.config_path}")
                    try:
                        self.on_change()
                    except Exception as e:
                        logger.error(f"[ConfigWatcher] 重载回调失败: {e}")
            except Exception as e:
                logger.error(f"[ConfigWatcher] 检查变更时出错: {e}")
            
            time.sleep(self.poll_interval)
        
        logger.info("[ConfigWatcher] 停止监视配置文件")
    
    def start(self):
        """开始监视"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止监视"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval + 1)
            self._thread = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class AsyncConfigWatcher:
    """
    异步配置文件监视器
    
    使用 asyncio 实现的配置文件监视器。
    """
    
    DEFAULT_POLL_INTERVAL = 5.0  # 秒
    
    def __init__(
        self,
        config_path: Path,
        on_change: Callable[[], None],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        """
        初始化异步配置监视器
        
        Args:
            config_path: 配置文件路径
            on_change: 文件变更时的回调函数（可以是同步或异步）
            poll_interval: 轮询间隔（秒）
        """
        self.config_path = Path(config_path)
        self.on_change = on_change
        self.poll_interval = poll_interval
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_mtime: Optional[float] = None
        self._last_size: Optional[int] = None
    
    def _get_file_info(self) -> tuple:
        """获取文件信息"""
        try:
            stat = self.config_path.stat()
            return stat.st_mtime, stat.st_size
        except FileNotFoundError:
            return None, None
        except Exception as e:
            logger.warning(f"[AsyncConfigWatcher] 获取文件信息失败: {e}")
            return None, None
    
    def _check_for_changes(self) -> bool:
        """检查文件是否有变更"""
        mtime, size = self._get_file_info()
        
        if mtime is None:
            if self._last_mtime is not None:
                self._last_mtime = None
                self._last_size = None
                return True
            return False
        
        if self._last_mtime is None:
            self._last_mtime = mtime
            self._last_size = size
            return False
        
        if mtime != self._last_mtime or size != self._last_size:
            self._last_mtime = mtime
            self._last_size = size
            return True
        
        return False
    
    async def _poll_loop(self):
        """异步轮询循环"""
        logger.info(f"[AsyncConfigWatcher] 开始监视配置文件: {self.config_path}")
        
        self._last_mtime, self._last_size = self._get_file_info()
        
        while self._running:
            try:
                if self._check_for_changes():
                    logger.info(f"[AsyncConfigWatcher] 检测到配置文件变更: {self.config_path}")
                    try:
                        result = self.on_change()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"[AsyncConfigWatcher] 重载回调失败: {e}")
            except Exception as e:
                logger.error(f"[AsyncConfigWatcher] 检查变更时出错: {e}")
            
            await asyncio.sleep(self.poll_interval)
        
        logger.info("[AsyncConfigWatcher] 停止监视配置文件")
    
    async def start(self):
        """开始监视"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self):
        """停止监视"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
