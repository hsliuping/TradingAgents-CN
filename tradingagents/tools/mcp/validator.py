"""
MCP 配置验证工具

提供配置文件验证、命令路径安全检查和 URL 格式验证功能。
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .config_utils import MCPServerConfig, MCPServerType, load_mcp_config

logger = logging.getLogger(__name__)


class ValidationError:
    """验证错误"""
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # error, warning, info
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }
    
    def __repr__(self) -> str:
        return f"ValidationError({self.severity}: {self.field} - {self.message})"


class ValidationResult:
    """验证结果"""
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.valid_servers: List[str] = []
        self.invalid_servers: List[str] = []
    
    @property
    def is_valid(self) -> bool:
        """配置是否有效（没有错误）"""
        return len(self.errors) == 0
    
    def add_error(self, field: str, message: str):
        """添加错误"""
        self.errors.append(ValidationError(field, message, "error"))
    
    def add_warning(self, field: str, message: str):
        """添加警告"""
        self.warnings.append(ValidationError(field, message, "warning"))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "isValid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "validServers": self.valid_servers,
            "invalidServers": self.invalid_servers,
        }


# 危险字符模式
DANGEROUS_CHARS = re.compile(r'[;&|`$(){}[\]<>]')

# 允许的命令（默认）
DEFAULT_ALLOWED_COMMANDS = {"uvx", "npx", "python", "python3", "node", "npm"}


def validate_command_path(command: str, allowed_commands: Optional[set] = None) -> Tuple[bool, Optional[str]]:
    """
    验证命令路径安全性
    
    Args:
        command: 命令字符串
        allowed_commands: 允许的命令集合
        
    Returns:
        (是否有效, 错误消息)
    """
    if not command:
        return False, "命令不能为空"
    
    command = command.strip()
    
    # 检查危险字符
    if DANGEROUS_CHARS.search(command):
        return False, f"命令包含危险字符: {command}"
    
    # 检查控制字符
    if any(ch in command for ch in ("\n", "\r", "\t")):
        return False, "命令包含非法控制字符"
    
    # 检查允许列表
    allowed = allowed_commands or DEFAULT_ALLOWED_COMMANDS
    command_name = Path(command).name
    
    if command_name not in allowed and command not in allowed:
        return False, f"命令 '{command_name}' 不在允许列表中"
    
    return True, None


def validate_url_format(url: str) -> Tuple[bool, Optional[str]]:
    """
    验证 URL 格式
    
    Args:
        url: URL 字符串
        
    Returns:
        (是否有效, 错误消息)
    """
    if not url:
        return False, "URL 不能为空"
    
    url = url.strip()
    
    # 检查协议
    if not url.startswith(("http://", "https://")):
        return False, "URL 必须以 http:// 或 https:// 开头"
    
    # 解析 URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "URL 缺少主机名"
    except Exception as e:
        return False, f"URL 解析失败: {e}"
    
    # 检查长度
    if len(url) > 2048:
        return False, "URL 过长（最大 2048 字符）"
    
    return True, None


def validate_server_config(
    name: str,
    config: Dict[str, Any],
    allowed_commands: Optional[set] = None,
) -> Tuple[bool, List[ValidationError]]:
    """
    验证单个服务器配置
    
    Args:
        name: 服务器名称
        config: 服务器配置字典
        allowed_commands: 允许的命令集合
        
    Returns:
        (是否有效, 错误列表)
    """
    errors: List[ValidationError] = []
    
    # 获取服务器类型
    server_type = config.get("type", "stdio")
    
    if server_type == "stdio":
        # 验证 stdio 配置
        command = config.get("command")
        if not command:
            errors.append(ValidationError(
                f"{name}.command",
                "stdio 类型服务器需要 'command' 字段"
            ))
        else:
            is_valid, error_msg = validate_command_path(command, allowed_commands)
            if not is_valid:
                errors.append(ValidationError(f"{name}.command", error_msg))
        
        # 验证 args
        args = config.get("args", [])
        if not isinstance(args, list):
            errors.append(ValidationError(
                f"{name}.args",
                "args 必须是字符串数组"
            ))
        else:
            for i, arg in enumerate(args):
                if not isinstance(arg, str):
                    errors.append(ValidationError(
                        f"{name}.args[{i}]",
                        "参数必须是字符串"
                    ))
                elif len(arg) > 512:
                    errors.append(ValidationError(
                        f"{name}.args[{i}]",
                        "参数过长（最大 512 字符）"
                    ))
    
    elif server_type == "http":
        # 验证 HTTP 配置
        url = config.get("url")
        if not url:
            errors.append(ValidationError(
                f"{name}.url",
                "http 类型服务器需要 'url' 字段"
            ))
        else:
            is_valid, error_msg = validate_url_format(url)
            if not is_valid:
                errors.append(ValidationError(f"{name}.url", error_msg))
        
        # 验证 headers
        headers = config.get("headers", {})
        if not isinstance(headers, dict):
            errors.append(ValidationError(
                f"{name}.headers",
                "headers 必须是对象"
            ))
    
    else:
        errors.append(ValidationError(
            f"{name}.type",
            f"未知的服务器类型: {server_type}"
        ))
    
    # 验证环境变量
    env = config.get("env", {})
    if not isinstance(env, dict):
        errors.append(ValidationError(
            f"{name}.env",
            "env 必须是对象"
        ))
    
    # 验证健康检查配置
    health_check = config.get("healthCheck")
    if health_check:
        if not isinstance(health_check, dict):
            errors.append(ValidationError(
                f"{name}.healthCheck",
                "healthCheck 必须是对象"
            ))
        else:
            interval = health_check.get("interval", 60)
            if not isinstance(interval, int) or interval < 10 or interval > 3600:
                errors.append(ValidationError(
                    f"{name}.healthCheck.interval",
                    "interval 必须是 10-3600 之间的整数"
                ))
            
            timeout = health_check.get("timeout", 10)
            if not isinstance(timeout, int) or timeout < 1 or timeout > 60:
                errors.append(ValidationError(
                    f"{name}.healthCheck.timeout",
                    "timeout 必须是 1-60 之间的整数"
                ))
    
    return len(errors) == 0, errors


def validate_config_file(
    config_path: Path,
    allowed_commands: Optional[set] = None,
) -> ValidationResult:
    """
    验证配置文件
    
    Args:
        config_path: 配置文件路径
        allowed_commands: 允许的命令集合
        
    Returns:
        验证结果
    """
    result = ValidationResult()
    
    # 检查文件是否存在
    if not config_path.exists():
        result.add_warning("file", f"配置文件不存在: {config_path}")
        return result
    
    # 读取并解析 JSON
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error("file", f"JSON 解析失败: {e}")
        return result
    except Exception as e:
        result.add_error("file", f"读取文件失败: {e}")
        return result
    
    # 检查 mcpServers 字段
    servers = data.get("mcpServers")
    if servers is None:
        result.add_warning("mcpServers", "配置文件缺少 mcpServers 字段")
        return result
    
    if not isinstance(servers, dict):
        result.add_error("mcpServers", "mcpServers 必须是对象")
        return result
    
    # 验证每个服务器
    for name, config in servers.items():
        if not isinstance(config, dict):
            result.add_error(name, "服务器配置必须是对象")
            result.invalid_servers.append(name)
            continue
        
        is_valid, errors = validate_server_config(name, config, allowed_commands)
        
        if is_valid:
            result.valid_servers.append(name)
        else:
            result.invalid_servers.append(name)
            for error in errors:
                result.errors.append(error)
    
    return result


def validate_config_dict(
    config: Dict[str, Any],
    allowed_commands: Optional[set] = None,
) -> ValidationResult:
    """
    验证配置字典
    
    Args:
        config: 配置字典
        allowed_commands: 允许的命令集合
        
    Returns:
        验证结果
    """
    result = ValidationResult()
    
    servers = config.get("mcpServers", {})
    if not isinstance(servers, dict):
        result.add_error("mcpServers", "mcpServers 必须是对象")
        return result
    
    for name, server_config in servers.items():
        if not isinstance(server_config, dict):
            result.add_error(name, "服务器配置必须是对象")
            result.invalid_servers.append(name)
            continue
        
        is_valid, errors = validate_server_config(name, server_config, allowed_commands)
        
        if is_valid:
            result.valid_servers.append(name)
        else:
            result.invalid_servers.append(name)
            for error in errors:
                result.errors.append(error)
    
    return result
