"""单端口托管启动入口（一键安装脚本配套）

用途：
  一键安装版同时提供 Web 界面与 API。Pro 版由 nginx 反代前端静态文件，
  一键安装版不使用 nginx，因此在本入口中把 frontend/dist 挂载到同一个
  FastAPI 应用上（SPA 回退），用户只访问一个地址。

用法（在安装目录根目录执行，.env 已由安装脚本生成）：
    .venv/Scripts/python installer/run_server.py   # Windows
    .venv/bin/python installer/run_server.py       # Linux / macOS
"""

import os
import sys
from pathlib import Path

# Windows 下 stdout/stderr 重定向到文件时默认 cp1252/locale 编码，中文与 emoji 输出会抛
# UnicodeEncodeError 导致启动失败，统一改为 UTF-8（errors=replace 兜底）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保项目根目录在 sys.path（venv 可能不含项目根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.main import app  # 先完成全部路由注册（/api/*、/health、/ws 等）

from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
INDEX_HTML = DIST_DIR / "index.html"

# 不应被 SPA 兜底接管的路径前缀（这些路由已在 app.main 注册，兜底路由最后注册不会抢到它们）
_NON_SPA_PREFIXES = ("api", "health", "healthz", "readyz", "docs", "redoc", "openapi.json", "ws")

_static_mounts_done = False


def mount_frontend() -> None:
    """把 frontend/dist 挂载为静态资源（幂等）"""
    global _static_mounts_done
    if _static_mounts_done:
        return
    if not DIST_DIR.is_dir():
        print(f"[run_server] 警告：未找到前端构建产物 {DIST_DIR}，本次仅提供 API 服务", file=sys.stderr)
        return
    assets_dir = DIST_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    # app.main 的根路由（返回 API 信息 JSON）与单端口托管冲突：单端口模式下 / 由前端 SPA 接管
    # （Pro 版走 nginx 反代，不经过本入口，不受影响）
    app.router.routes = [
        r
        for r in app.router.routes
        if not (getattr(r, "path", None) == "/" and getattr(r, "methods", None) == {"GET"})
    ]
    print(f"[run_server] 前端静态资源已挂载：{DIST_DIR}")
    _static_mounts_done = True


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """SPA 兜底：已存在的静态文件直接返回，其余返回 index.html"""
    if full_path.split("/", 1)[0] in _NON_SPA_PREFIXES:
        return JSONResponse({"success": False, "message": "Not Found"}, status_code=404)
    candidate = (DIST_DIR / full_path).resolve()
    # 防路径穿越
    try:
        candidate.relative_to(DIST_DIR.resolve())
    except ValueError:
        candidate = INDEX_HTML
    if candidate.is_file():
        return FileResponse(candidate)
    if INDEX_HTML.is_file():
        return FileResponse(INDEX_HTML)
    return JSONResponse({"success": False, "message": "Not Found"}, status_code=404)


def main() -> None:
    mount_frontend()
    import uvicorn

    print(f"[run_server] 访问地址：http://{settings.HOST}:{settings.PORT}")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)


if __name__ == "__main__":
    main()