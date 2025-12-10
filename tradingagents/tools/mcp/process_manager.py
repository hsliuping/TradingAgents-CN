"""
MCP 进程管理器

提供 stdio MCP 服务器进程的管理、监控和崩溃恢复功能。
"""
import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """进程信息"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    process: Optional[subprocess.Popen] = None
    start_time: Optional[datetime] = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None


@dataclass
class RestartPolicy:
    """重启策略"""
    max_restarts: int = 3  # 最大重启次数
    restart_window: int = 300  # 重启窗口（秒）
    restart_delay: float = 1.0  # 重启延迟（秒）
    max_restart_delay: float = 60.0  # 最大重启延迟（秒）


class ProcessManager:
    """
    MCP 进程管理器
    
    功能：
    - 启动和停止 stdio 服务器进程
    - 监控进程状态
    - 自动重启崩溃的进程
    - 实施重启限制防止无限循环
    """
    
    def __init__(self, restart_policy: Optional[RestartPolicy] = None):
        """
        初始化进程管理器
        
        Args:
            restart_policy: 重启策略
        """
        self.restart_policy = restart_policy or RestartPolicy()
        self._processes: Dict[str, ProcessInfo] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_process_exit: Optional[Callable[[str, int], None]] = None
    
    def set_exit_callback(self, callback: Callable[[str, int], None]):
        """
        设置进程退出回调
        
        Args:
            callback: 回调函数，参数为 (进程名, 退出码)
        """
        self._on_process_exit = callback
    
    def start_process(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        启动进程
        
        Args:
            name: 进程名称
            command: 命令
            args: 参数
            env: 环境变量
            
        Returns:
            是否成功启动
        """
        if name in self._processes and self._processes[name].process:
            proc = self._processes[name].process
            if proc.poll() is None:
                logger.warning(f"[ProcessManager] 进程 {name} 已在运行")
                return True
        
        try:
            # 合并环境变量
            import os
            full_env = {**os.environ, **(env or {})}
            
            # 启动进程
            process = subprocess.Popen(
                [command] + args,
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # 记录进程信息
            self._processes[name] = ProcessInfo(
                name=name,
                command=command,
                args=args,
                env=env or {},
                process=process,
                start_time=datetime.now(),
            )
            
            logger.info(f"[ProcessManager] 进程 {name} 已启动 (PID: {process.pid})")
            return True
            
        except FileNotFoundError:
            logger.error(f"[ProcessManager] 命令未找到: {command}")
            self._processes[name] = ProcessInfo(
                name=name,
                command=command,
                args=args,
                env=env or {},
                error_message=f"命令未找到: {command}",
            )
            return False
        except Exception as e:
            logger.error(f"[ProcessManager] 启动进程 {name} 失败: {e}")
            self._processes[name] = ProcessInfo(
                name=name,
                command=command,
                args=args,
                env=env or {},
                error_message=str(e),
            )
            return False
    
    def stop_process(self, name: str, timeout: float = 5.0) -> bool:
        """
        停止进程
        
        Args:
            name: 进程名称
            timeout: 等待超时（秒）
            
        Returns:
            是否成功停止
        """
        if name not in self._processes:
            return True
        
        info = self._processes[name]
        if not info.process:
            return True
        
        try:
            # 尝试优雅终止
            info.process.terminate()
            try:
                info.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 强制终止
                info.process.kill()
                info.process.wait(timeout=1)
            
            info.exit_code = info.process.returncode
            info.process = None
            logger.info(f"[ProcessManager] 进程 {name} 已停止")
            return True
            
        except Exception as e:
            logger.error(f"[ProcessManager] 停止进程 {name} 失败: {e}")
            return False
    
    def is_running(self, name: str) -> bool:
        """
        检查进程是否在运行
        
        Args:
            name: 进程名称
            
        Returns:
            是否在运行
        """
        if name not in self._processes:
            return False
        
        info = self._processes[name]
        if not info.process:
            return False
        
        return info.process.poll() is None
    
    def get_process_info(self, name: str) -> Optional[ProcessInfo]:
        """
        获取进程信息
        
        Args:
            name: 进程名称
            
        Returns:
            进程信息
        """
        return self._processes.get(name)
    
    def _should_restart(self, name: str) -> bool:
        """
        检查是否应该重启进程
        
        Args:
            name: 进程名称
            
        Returns:
            是否应该重启
        """
        info = self._processes.get(name)
        if not info:
            return False
        
        # 检查重启次数
        if info.restart_count >= self.restart_policy.max_restarts:
            # 检查是否在重启窗口内
            if info.last_restart:
                elapsed = (datetime.now() - info.last_restart).total_seconds()
                if elapsed < self.restart_policy.restart_window:
                    logger.warning(
                        f"[ProcessManager] 进程 {name} 在 {self.restart_policy.restart_window}s "
                        f"内已重启 {info.restart_count} 次，停止重启"
                    )
                    return False
                else:
                    # 重置重启计数
                    info.restart_count = 0
        
        return True
    
    def _get_restart_delay(self, name: str) -> float:
        """
        获取重启延迟（指数退避）
        
        Args:
            name: 进程名称
            
        Returns:
            延迟时间（秒）
        """
        info = self._processes.get(name)
        if not info:
            return self.restart_policy.restart_delay
        
        delay = self.restart_policy.restart_delay * (2 ** info.restart_count)
        return min(delay, self.restart_policy.max_restart_delay)
    
    async def _restart_process(self, name: str):
        """
        重启进程
        
        Args:
            name: 进程名称
        """
        info = self._processes.get(name)
        if not info:
            return
        
        # 等待延迟
        delay = self._get_restart_delay(name)
        logger.info(f"[ProcessManager] 等待 {delay:.1f}s 后重启进程 {name}")
        await asyncio.sleep(delay)
        
        # 重启
        info.restart_count += 1
        info.last_restart = datetime.now()
        
        success = self.start_process(
            name,
            info.command,
            info.args,
            info.env,
        )
        
        if success:
            logger.info(f"[ProcessManager] 进程 {name} 重启成功 (第 {info.restart_count} 次)")
        else:
            logger.error(f"[ProcessManager] 进程 {name} 重启失败")
    
    async def _monitor_loop(self):
        """监控循环"""
        logger.info("[ProcessManager] 开始监控进程")
        
        while self._running:
            for name, info in list(self._processes.items()):
                if not info.process:
                    continue
                
                # 检查进程状态
                exit_code = info.process.poll()
                if exit_code is not None:
                    # 进程已退出
                    info.exit_code = exit_code
                    info.process = None
                    
                    logger.warning(
                        f"[ProcessManager] 进程 {name} 意外退出 (退出码: {exit_code})"
                    )
                    
                    # 触发回调
                    if self._on_process_exit:
                        try:
                            self._on_process_exit(name, exit_code)
                        except Exception as e:
                            logger.error(f"[ProcessManager] 退出回调失败: {e}")
                    
                    # 检查是否应该重启
                    if self._should_restart(name):
                        asyncio.create_task(self._restart_process(name))
            
            await asyncio.sleep(1)
        
        logger.info("[ProcessManager] 停止监控进程")
    
    async def start_monitoring(self):
        """开始监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """停止监控"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    def stop_all(self):
        """停止所有进程"""
        for name in list(self._processes.keys()):
            self.stop_process(name)
        self._processes.clear()
