"""
MCP HTTP 适配器

提供通过 HTTP/HTTPS 协议与远程 MCP 服务器通信的能力。
支持认证头、指数退避重试和 SSL 证书验证。
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


class MCPHTTPError(Exception):
    """MCP HTTP 通信错误"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class MCPHTTPAdapter:
    """
    MCP HTTP 适配器
    
    通过 HTTP/HTTPS 协议与远程 MCP 服务器通信。
    支持：
    - HTTP/HTTPS 连接
    - 认证头
    - 指数退避重试
    - SSL 证书验证
    - 连接池管理
    """
    
    # 默认配置
    DEFAULT_TIMEOUT = 30.0  # 秒
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # 秒
    DEFAULT_MAX_DELAY = 60.0  # 秒
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        verify_ssl: bool = True,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        """
        初始化 HTTP 适配器
        
        Args:
            url: MCP 服务器 URL
            headers: 请求头（包括认证头）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            verify_ssl: 是否验证 SSL 证书
            base_delay: 重试基础延迟（秒）
            max_delay: 重试最大延迟（秒）
        """
        self.url = url.rstrip('/')
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # 创建 HTTP 客户端
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
        
        # 状态跟踪
        self._is_connected = False
        self._last_error: Optional[str] = None
        self._retry_count = 0
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected
    
    @property
    def last_error(self) -> Optional[str]:
        """获取最后一次错误信息"""
        return self._last_error
    
    def _get_sync_client(self) -> httpx.Client:
        """获取同步 HTTP 客户端"""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self.headers,
            )
        return self._sync_client
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """获取异步 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self.headers,
            )
        return self._client
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        计算指数退避延迟
        
        Args:
            attempt: 当前重试次数（从 0 开始）
            
        Returns:
            延迟时间（秒）
        """
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        带重试的 HTTP 请求
        
        Args:
            method: HTTP 方法
            endpoint: 端点路径
            **kwargs: 传递给 httpx 的其他参数
            
        Returns:
            HTTP 响应
            
        Raises:
            MCPHTTPError: 请求失败
        """
        url = urljoin(self.url + '/', endpoint.lstrip('/'))
        client = await self._get_async_client()
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                self._is_connected = True
                self._last_error = None
                self._retry_count = 0
                return response
            except httpx.TimeoutException as e:
                last_exception = e
                self._last_error = f"请求超时: {e}"
                logger.warning(
                    "[MCP HTTP] 请求超时 (尝试 %d/%d): %s",
                    attempt + 1, self.max_retries + 1, url
                )
            except httpx.HTTPStatusError as e:
                last_exception = e
                self._last_error = f"HTTP 错误 {e.response.status_code}: {e}"
                # 4xx 错误不重试
                if 400 <= e.response.status_code < 500:
                    raise MCPHTTPError(str(e), e.response.status_code)
                logger.warning(
                    "[MCP HTTP] HTTP 错误 (尝试 %d/%d): %s",
                    attempt + 1, self.max_retries + 1, e
                )
            except httpx.RequestError as e:
                last_exception = e
                self._last_error = f"请求错误: {e}"
                logger.warning(
                    "[MCP HTTP] 请求错误 (尝试 %d/%d): %s",
                    attempt + 1, self.max_retries + 1, e
                )
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt)
                self._retry_count = attempt + 1
                logger.info("[MCP HTTP] 等待 %.1f 秒后重试...", delay)
                await asyncio.sleep(delay)
        
        # 所有重试都失败
        self._is_connected = False
        raise MCPHTTPError(
            f"请求失败，已重试 {self.max_retries} 次: {last_exception}"
        )
    
    def _sync_request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        带重试的同步 HTTP 请求
        """
        url = urljoin(self.url + '/', endpoint.lstrip('/'))
        client = self._get_sync_client()
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                self._is_connected = True
                self._last_error = None
                self._retry_count = 0
                return response
            except httpx.TimeoutException as e:
                last_exception = e
                self._last_error = f"请求超时: {e}"
            except httpx.HTTPStatusError as e:
                last_exception = e
                self._last_error = f"HTTP 错误 {e.response.status_code}: {e}"
                if 400 <= e.response.status_code < 500:
                    raise MCPHTTPError(str(e), e.response.status_code)
            except httpx.RequestError as e:
                last_exception = e
                self._last_error = f"请求错误: {e}"
            
            if attempt < self.max_retries:
                delay = self._calculate_retry_delay(attempt)
                self._retry_count = attempt + 1
                time.sleep(delay)
        
        self._is_connected = False
        raise MCPHTTPError(
            f"请求失败，已重试 {self.max_retries} 次: {last_exception}"
        )

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出可用工具
        
        Returns:
            工具列表，每个工具包含 name、description、inputSchema
        """
        try:
            response = await self._request_with_retry("GET", "/tools")
            data = response.json()
            return data.get("tools", [])
        except MCPHTTPError:
            raise
        except Exception as e:
            logger.error("[MCP HTTP] 列出工具失败: %s", e)
            raise MCPHTTPError(f"列出工具失败: {e}")
    
    def list_tools_sync(self) -> List[Dict[str, Any]]:
        """同步版本的列出工具"""
        try:
            response = self._sync_request_with_retry("GET", "/tools")
            data = response.json()
            return data.get("tools", [])
        except MCPHTTPError:
            raise
        except Exception as e:
            logger.error("[MCP HTTP] 列出工具失败: %s", e)
            raise MCPHTTPError(f"列出工具失败: {e}")
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            response = await self._request_with_retry(
                "POST",
                f"/tools/{tool_name}",
                json={"arguments": arguments}
            )
            return response.json()
        except MCPHTTPError:
            raise
        except Exception as e:
            logger.error("[MCP HTTP] 调用工具失败: %s", e)
            raise MCPHTTPError(f"调用工具 {tool_name} 失败: {e}")
    
    def call_tool_sync(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """同步版本的调用工具"""
        try:
            response = self._sync_request_with_retry(
                "POST",
                f"/tools/{tool_name}",
                json={"arguments": arguments}
            )
            return response.json()
        except MCPHTTPError:
            raise
        except Exception as e:
            logger.error("[MCP HTTP] 调用工具失败: %s", e)
            raise MCPHTTPError(f"调用工具 {tool_name} 失败: {e}")
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            True 如果服务器健康，否则 False
        """
        try:
            response = await self._request_with_retry("GET", "/health")
            return response.status_code == 200
        except MCPHTTPError:
            return False
        except Exception:
            return False
    
    def health_check_sync(self) -> bool:
        """同步版本的健康检查"""
        try:
            response = self._sync_request_with_retry("GET", "/health")
            return response.status_code == 200
        except MCPHTTPError:
            return False
        except Exception:
            return False
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._is_connected = False
    
    def close_sync(self):
        """同步关闭连接"""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
        self._is_connected = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_sync()
    
    def get_retry_delays(self, num_retries: int) -> List[float]:
        """
        获取重试延迟序列（用于测试）
        
        Args:
            num_retries: 重试次数
            
        Returns:
            延迟时间列表
        """
        return [self._calculate_retry_delay(i) for i in range(num_retries)]
