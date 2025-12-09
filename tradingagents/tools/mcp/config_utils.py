import json
import logging
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # 轻量文件锁，避免并发写入损坏；若未安装则降级为无锁
    from filelock import FileLock
except Exception:  # pragma: no cover - 可选依赖
    FileLock = None  # type: ignore

try:
    from pydantic import BaseModel, Field, root_validator, validator
except ImportError:  # pragma: no cover - 兼容 pydantic v1/v2 命名
    from pydantic import BaseModel, Field, root_validator, validator  # type: ignore

logger = logging.getLogger(__name__)

BASE_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DEFAULT_CONFIG_FILE = BASE_CONFIG_DIR / "mcp_servers.json"


def _safe_is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _allowed_commands() -> set:
    env_value = os.getenv("MCP_ALLOWED_COMMANDS", "")
    return {c.strip() for c in env_value.split(",") if c.strip()}


def _allowed_roots() -> List[Path]:
    env_value = os.getenv("MCP_ALLOWED_ROOTS", "")
    roots: List[Path] = []
    for part in env_value.split(os.pathsep):
        if part.strip():
            roots.append(Path(part).expanduser().resolve())
    # 默认允许 config 目录，避免意外写入工作目录之外
    roots.append(BASE_CONFIG_DIR.resolve())
    return roots


class MCPServerConfig(BaseModel):
    """
    服务器配置模型：限制 command/args/env 字段以降低命令注入风险。
    """

    command: str = Field(..., min_length=1, max_length=256, description="可执行程序路径或名称")
    args: List[str] = Field(default_factory=list, max_items=32)
    env: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = Field(default=None, max_length=500)
    enabled: bool = Field(default=True, alias="_enabled", description="内部启用标记")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True

    @validator("command")
    def _validate_command(cls, value: str) -> str:
        value = value.strip()
        if any(ch in value for ch in ("\n", "\r", "\t")):
            raise ValueError("command 含有非法控制字符")

        allowed_commands = _allowed_commands()
        command_path = Path(value).expanduser()

        # 允许列表存在时，必须命中
        if allowed_commands:
            if command_path.name not in allowed_commands and value not in allowed_commands:
                raise ValueError("command 不在允许列表中，请配置 MCP_ALLOWED_COMMANDS")
        else:
            # 未配置 allowlist 时，仅允许相对路径，避免意外绝对路径执行
            if command_path.is_absolute():
                raise ValueError("未配置 MCP_ALLOWED_COMMANDS 时禁止使用绝对路径 command")

        # 如果是绝对路径，需落在允许根目录
        if command_path.is_absolute():
            roots = _allowed_roots()
            if not any(_safe_is_relative_to(command_path, root) for root in roots):
                raise ValueError("command 不在允许的根目录下")

        return value

    @validator("args", each_item=True)
    def _validate_args(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("args 必须为字符串列表")
        if len(value) > 512:
            raise ValueError("单个参数过长")
        return value

    @validator("env")
    def _validate_env(cls, value: Dict[str, Any]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("env key 必须为字符串")
            if len(k) > 128:
                raise ValueError("env key 过长")
            sanitized[k] = "" if v is None else str(v)
        return sanitized

    @root_validator(pre=True)
    def _ensure_enabled(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "_enabled" not in values and "enabled" not in values:
            values["_enabled"] = True
        return values

    def sanitized(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "args": list(self.args),
            "env": dict(self.env),
            "description": self.description,
            "_enabled": bool(self.enabled),
        }


class MCPConfig(BaseModel):
    mcpServers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

    class Config:
        extra = "ignore"


def get_config_path(config_file: Optional[Path] = None) -> Path:
    path = Path(config_file) if config_file else DEFAULT_CONFIG_FILE
    return path


def validate_servers_map(
    servers: Dict[str, Any],
    *,
    strict: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    校验并清理 mcpServers 映射。
    strict=True 时遇到不合法配置立即抛出异常；否则跳过并记录警告。
    """
    validated: Dict[str, Dict[str, Any]] = {}
    for name, raw in servers.items():
        try:
            model = MCPServerConfig(**raw)
            validated[name] = model.sanitized()
        except Exception as exc:
            logger.warning("[MCP] 无效配置已跳过 (%s): %s", name, exc)
            if strict:
                raise
    return validated


def load_mcp_config(config_file: Optional[Path] = None, *, strict: bool = False) -> Dict[str, Any]:
    """
    读取配置文件并进行基本校验。返回 dict 结构，确保 mcpServers 字段存在。
    """
    path = get_config_path(config_file)
    if not path.exists():
        return {"mcpServers": {}}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - 保护 IO/解析异常
        logger.error("[MCP] 读取配置失败: %s", exc)
        return {"mcpServers": {}}

    servers = data.get("mcpServers", {}) or {}
    validated = validate_servers_map(servers, strict=strict)
    return {"mcpServers": validated}


def merge_servers(
    current: Dict[str, Dict[str, Any]],
    incoming: Dict[str, Dict[str, Any]],
    *,
    strict: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    合并新旧服务器配置，保留已有 _enabled 状态。
    """
    validated = validate_servers_map(incoming, strict=strict)
    merged = dict(current)
    for name, cfg in validated.items():
        cfg["_enabled"] = bool(current.get(name, {}).get("_enabled", cfg.get("_enabled", True)))
        merged[name] = cfg
    return merged


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def write_mcp_config(config: Dict[str, Any], config_file: Optional[Path] = None) -> None:
    """
    原子写入配置并可选文件锁，避免并发写导致文件损坏。
    """
    path = get_config_path(config_file)
    payload = {"mcpServers": config.get("mcpServers", {})}
    lock_ctx = (
        FileLock(str(path) + ".lock")
        if FileLock is not None
        else nullcontext()
    )
    with lock_ctx:
        _atomic_write_json(path, payload)
