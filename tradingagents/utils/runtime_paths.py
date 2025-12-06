"""
运行时路径管理工具

统一管理所有运行时输出目录，确保日志、数据、缓存、结果等
都收敛到单一的 runtime 根目录下，便于部署与清理。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, os.PathLike]

# 以仓库根目录为基准，保证相对路径稳定
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_base_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    """
    解析运行时根目录：
    优先级 TA_RUNTIME_DIR > TRADINGAGENTS_RUNTIME_DIR > 参数 > "runtime"
    若为相对路径，则相对于项目根目录。
    """
    candidate = (
        os.getenv("TA_RUNTIME_DIR")
        or os.getenv("TRADINGAGENTS_RUNTIME_DIR")
        or runtime_dir
        or "runtime"
    )
    base = Path(candidate)
    if not base.is_absolute():
        base = _PROJECT_ROOT / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def resolve_path(path: PathLike, runtime_dir: Optional[PathLike] = None) -> Path:
    """
    将相对路径解析到运行时根目录下，并确保父目录存在。
    绝对路径会被直接返回。
    """
    candidate = Path(path)
    if candidate.is_absolute():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    base = _resolve_base_dir(runtime_dir)
    target = base / candidate
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def ensure_subdir(relative: PathLike, runtime_dir: Optional[PathLike] = None) -> Path:
    """创建并返回运行时子目录。"""
    base = _resolve_base_dir(runtime_dir)
    target = base / Path(relative)
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_runtime_base_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    """获取（并创建）运行时根目录。"""
    return _resolve_base_dir(runtime_dir)


def get_logs_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("logs", runtime_dir)


def get_data_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("data", runtime_dir)


def get_cache_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("cache", runtime_dir)


def get_results_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("results", runtime_dir)


def get_analysis_results_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir(Path("data") / "analysis_results", runtime_dir)


def get_eval_results_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("eval_results", runtime_dir)


def get_uploads_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir("uploads", runtime_dir)


def get_backups_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir(Path("data") / "backups", runtime_dir)


def get_exports_dir(runtime_dir: Optional[PathLike] = None) -> Path:
    return ensure_subdir(Path("data") / "exports", runtime_dir)


__all__ = [
    "get_runtime_base_dir",
    "resolve_path",
    "ensure_subdir",
    "get_logs_dir",
    "get_data_dir",
    "get_cache_dir",
    "get_results_dir",
    "get_analysis_results_dir",
    "get_eval_results_dir",
    "get_uploads_dir",
    "get_backups_dir",
    "get_exports_dir",
]
