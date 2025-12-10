"""
MCP 健康监控系统

提供对 MCP 服务器的健康状态监控能力。
支持周期性健康检查、状态跟踪和错误报告。
"""
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config_utils import MCPServerConfig

logger = logging.getLogger(__name__)


class ServerStatus(str, Enum):
    """服务器状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"
    STOPPED = "stopped"


class ServerHealthInfo:
    """服务器健康信息"""
    
    def __init__(
        self,
        status: ServerStatus = ServerStatus.UNKNOWN,
        last_check: Optional[datetime] = None,
        error: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ):
        self.status = status
        self.last_check = last_check
        self.error = error
        self.latency_ms = latency_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "lastCheck": self.last_check.isoformat() if self.last_check else None,
            "error": self.error,
            "latencyMs": self.latency_ms,
        }


class HealthMonitor:
    """
    MCP 服务器健康监控器
    
    功能：
    - 周期性检查服务器健康状态
    - 跟踪服务器状态变化
    - 记录健康检查失败详情
    - 触发状态变化回调
    """
    
    def __init__(self):
        """初始化健康监控器"""
        self._server_health: Dict[str, ServerHealthInfo] = {}
        self._check_tasks: Dict[str, asyncio.Task] = {}
        self._health_check_funcs: Dict[str, Callable[[], bool]] = {}
        self._running = False
        self._on_status_change: Optional[Callable[[str, ServerStatus, ServerStatus], None]] = None
    
    def register_server(
        self,
        server_name: str,
        health_check_func: Callable[[], bool],
        initial_status: ServerStatus = ServerStatus.UNKNOWN,
    ):
        """
        注册服务器进行健康监控
        
        Args:
            server_name: 服务器名称
            health_check_func: 健康检查函数，返回 True 表示健康
            initial_status: 初始状态
        """
        self._server_health[server_name] = ServerHealthInfo(status=initial_status)
        self._health_check_funcs[server_name] = health_check_func
        logger.info("[HealthMonitor] 注册服务器: %s", server_name)
    
    def unregister_server(self, server_name: str):
        """
        取消注册服务器
        
        Args:
            server_name: 服务器名称
        """
        if server_name in self._check_tasks:
            self._check_tasks[server_name].cancel()
            del self._check_tasks[server_name]
        
        if server_name in self._server_health:
            del self._server_health[server_name]
        
        if server_name in self._health_check_funcs:
            del self._health_check_funcs[server_name]
        
        logger.info("[HealthMonitor] 取消注册服务器: %s", server_name)
    
    def set_status_change_callback(
        self,
        callback: Callable[[str, ServerStatus, ServerStatus], None]
    ):
        """
        设置状态变化回调
        
        Args:
            callback: 回调函数，参数为 (server_name, old_status, new_status)
        """
        self._on_status_change = callback
    
    def get_server_status(self, server_name: str) -> ServerStatus:
        """
        获取服务器状态
        
        Args:
            server_name: 服务器名称
            
        Returns:
            服务器状态
        """
        if server_name not in self._server_health:
            return ServerStatus.UNKNOWN
        return self._server_health[server_name].status
    
    def get_server_health_info(self, server_name: str) -> Optional[ServerHealthInfo]:
        """
        获取服务器健康信息
        
        Args:
            server_name: 服务器名称
            
        Returns:
            健康信息，如果服务器未注册则返回 None
        """
        return self._server_health.get(server_name)
    
    def get_all_server_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有服务器状态
        
        Returns:
            服务器名称到健康信息的映射
        """
        return {
            name: info.to_dict()
            for name, info in self._server_health.items()
        }
    
    def _update_status(
        self,
        server_name: str,
        new_status: ServerStatus,
        error: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ):
        """
        更新服务器状态
        
        Args:
            server_name: 服务器名称
            new_status: 新状态
            error: 错误信息
            latency_ms: 延迟（毫秒）
        """
        if server_name not in self._server_health:
            self._server_health[server_name] = ServerHealthInfo()
        
        old_status = self._server_health[server_name].status
        
        self._server_health[server_name].status = new_status
        self._server_health[server_name].last_check = datetime.now()
        self._server_health[server_name].error = error
        self._server_health[server_name].latency_ms = latency_ms
        
        # 状态变化时记录日志并触发回调
        if old_status != new_status:
            logger.info(
                "[HealthMonitor] 服务器 %s 状态变化: %s -> %s",
                server_name, old_status.value, new_status.value
            )
            if self._on_status_change:
                try:
                    self._on_status_change(server_name, old_status, new_status)
                except Exception as e:
                    logger.error("[HealthMonitor] 状态变化回调失败: %s", e)

    async def check_server_health(
        self,
        server_name: str,
        timeout: float = 10.0,
    ) -> ServerStatus:
        """
        检查单个服务器的健康状态
        
        Args:
            server_name: 服务器名称
            timeout: 超时时间（秒）
            
        Returns:
            服务器状态
        """
        if server_name not in self._health_check_funcs:
            logger.warning("[HealthMonitor] 服务器 %s 未注册", server_name)
            return ServerStatus.UNKNOWN
        
        health_check_func = self._health_check_funcs[server_name]
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 在线程池中运行同步健康检查函数
            loop = asyncio.get_event_loop()
            is_healthy = await asyncio.wait_for(
                loop.run_in_executor(None, health_check_func),
                timeout=timeout
            )
            
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if is_healthy:
                self._update_status(
                    server_name,
                    ServerStatus.HEALTHY,
                    latency_ms=latency_ms
                )
                return ServerStatus.HEALTHY
            else:
                self._update_status(
                    server_name,
                    ServerStatus.DEGRADED,
                    error="健康检查返回 False",
                    latency_ms=latency_ms
                )
                return ServerStatus.DEGRADED
                
        except asyncio.TimeoutError:
            self._update_status(
                server_name,
                ServerStatus.DEGRADED,
                error=f"健康检查超时 ({timeout}s)"
            )
            logger.warning("[HealthMonitor] 服务器 %s 健康检查超时", server_name)
            return ServerStatus.DEGRADED
            
        except Exception as e:
            self._update_status(
                server_name,
                ServerStatus.UNREACHABLE,
                error=str(e)
            )
            logger.error("[HealthMonitor] 服务器 %s 健康检查失败: %s", server_name, e)
            return ServerStatus.UNREACHABLE
    
    async def _monitor_server(
        self,
        server_name: str,
        interval: int,
        timeout: int,
    ):
        """
        持续监控单个服务器
        
        Args:
            server_name: 服务器名称
            interval: 检查间隔（秒）
            timeout: 超时时间（秒）
        """
        logger.info(
            "[HealthMonitor] 开始监控服务器 %s (间隔: %ds, 超时: %ds)",
            server_name, interval, timeout
        )
        
        while self._running:
            try:
                await self.check_server_health(server_name, timeout=timeout)
            except Exception as e:
                logger.error("[HealthMonitor] 监控服务器 %s 时出错: %s", server_name, e)
            
            await asyncio.sleep(interval)
    
    async def start_monitoring(
        self,
        server_configs: Dict[str, "MCPServerConfig"],
    ):
        """
        开始监控所有服务器
        
        Args:
            server_configs: 服务器配置映射
        """
        self._running = True
        
        for name, config in server_configs.items():
            if not config.enabled:
                self._update_status(name, ServerStatus.STOPPED)
                continue
            
            health_check = config.healthCheck
            if health_check is None or not health_check.enabled:
                self._update_status(name, ServerStatus.UNKNOWN)
                continue
            
            if name not in self._health_check_funcs:
                logger.warning("[HealthMonitor] 服务器 %s 没有注册健康检查函数", name)
                continue
            
            # 创建监控任务
            task = asyncio.create_task(
                self._monitor_server(
                    name,
                    interval=health_check.interval,
                    timeout=health_check.timeout,
                )
            )
            self._check_tasks[name] = task
        
        logger.info("[HealthMonitor] 开始监控 %d 个服务器", len(self._check_tasks))
    
    async def stop_monitoring(self):
        """停止所有监控任务"""
        self._running = False
        
        for name, task in self._check_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._check_tasks.clear()
        logger.info("[HealthMonitor] 已停止所有监控任务")
    
    def mark_server_stopped(self, server_name: str):
        """
        标记服务器为已停止
        
        Args:
            server_name: 服务器名称
        """
        self._update_status(server_name, ServerStatus.STOPPED)
        
        # 取消该服务器的监控任务
        if server_name in self._check_tasks:
            self._check_tasks[server_name].cancel()
            del self._check_tasks[server_name]
    
    def mark_server_unknown(self, server_name: str):
        """
        标记服务器状态为未知（健康检查禁用时使用）
        
        Args:
            server_name: 服务器名称
        """
        self._update_status(server_name, ServerStatus.UNKNOWN)
