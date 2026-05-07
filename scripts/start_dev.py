#!/usr/bin/env python3
"""
开发环境启动脚本
支持按服务分别启动，方便调试

用法:
  python scripts/start_dev.py docker 3.0       # 启动 v3.0 的 MongoDB+Redis
  python scripts/start_dev.py backend 3.0      # 启动 v3.0 后端
  python scripts/start_dev.py frontend 3.0     # 启动 v3.0 前端
  python scripts/start_dev.py status           # 查看各版本端口配置
"""

import argparse
import subprocess
import sys
import os
import signal
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
os.chdir(project_root)

VERSION_CONFIG = {
    "2.0": {"project": "ta-v201", "mongodb": 27017, "redis": 6379, "backend": 8000, "frontend": 3000},
    "2.1": {"project": "ta-v210", "mongodb": 27018, "redis": 6380, "backend": 8001, "frontend": 3001},
    "3.0": {"project": "ta-v3",   "mongodb": 27019, "redis": 6381, "backend": 8002, "frontend": 3002},
}


def cmd_status():
    print("\n  开发环境端口配置")
    print("  " + "=" * 40)
    for v in ["2.0", "2.1", "3.0"]:
        c = VERSION_CONFIG[v]
        print(f"  v{v}:")
        print(f"    MongoDB:  {c['mongodb']}")
        print(f"    Redis:    {c['redis']}")
        print(f"    Backend:  {c['backend']}  -> http://127.0.0.1:{c['backend']}")
        print(f"    Frontend: {c['frontend']} -> http://localhost:{c['frontend']}")
        print()


def cmd_docker(version):
    config = VERSION_CONFIG[version]
    compose_file = project_root / "docker" / "docker-compose.dev.yml"
    if not compose_file.exists():
        print(f"[ERROR] {compose_file} not found")
        sys.exit(1)

    env = os.environ.copy()
    env["MONGODB_PORT"] = str(config["mongodb"])
    env["REDIS_PORT"] = str(config["redis"])

    print(f"[Docker] Starting MongoDB ({config['mongodb']}) + Redis ({config['redis']})...")
    print(f"  Project: {config['project']}")
    subprocess.run(
        ["docker-compose", "-p", config["project"], "-f", str(compose_file), "up", "-d"],
        env=env,
    )
    print(f"[OK] Docker services started (project: {config['project']})")
    print(f"  MongoDB: mongodb://admin:tradingagents123@localhost:{config['mongodb']}/tradingagents?authSource=admin")
    print(f"  Redis:   redis://:tradingagents123@localhost:{config['redis']}/0")


def cmd_backend(version, port=None):
    config = VERSION_CONFIG[version]
    backend_port = port or config["backend"]

    os.environ["PORT"] = str(backend_port)
    os.environ["HOST"] = "127.0.0.1"
    os.environ["MONGODB_HOST"] = "localhost"
    os.environ["MONGODB_PORT"] = str(config["mongodb"])
    os.environ["REDIS_HOST"] = "localhost"
    os.environ["REDIS_PORT"] = str(config["redis"])

    print(f"[Backend] Starting FastAPI + Uvicorn...")
    print(f"  Port: {backend_port}")
    print(f"  URL:  http://127.0.0.1:{backend_port}")
    print(f"  Docs: http://127.0.0.1:{backend_port}/docs")

    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(backend_port), "--log-level", "info",
        ])
    except KeyboardInterrupt:
        print("\n[INFO] Backend stopped")


def cmd_frontend(version, port=None):
    config = VERSION_CONFIG[version]
    frontend_port = port or config["frontend"]

    os.environ["VITE_PORT"] = str(frontend_port)
    os.environ["VITE_API_TARGET"] = f"http://localhost:{config['backend']}"

    frontend_dir = project_root / "frontend"
    print(f"[Frontend] Starting Vite dev server...")
    print(f"  Port: {frontend_port}")
    print(f"  URL:  http://localhost:{frontend_port}")
    print(f"  API proxy -> http://localhost:{config['backend']}")

    try:
        subprocess.run(["npm", "run", "dev"], cwd=str(frontend_dir))
    except KeyboardInterrupt:
        print("\n[INFO] Frontend stopped")


def main():
    parser = argparse.ArgumentParser(description="TradingAgents-CN 开发环境启动器")
    parser.add_argument("command", choices=["docker", "backend", "frontend", "status"],
                        help="docker=启动MongoDB+Redis, backend=启动后端, frontend=启动前端, status=查看端口配置")
    parser.add_argument("version", nargs="?", choices=["2.0", "2.1", "3.0"],
                        help="版本号 (2.0, 2.1, 3.0)")
    parser.add_argument("--port", type=int, default=0, help="手动指定端口")
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
        return

    if not args.version:
        parser.error("该命令需要指定版本号，如: start_dev.py backend 3.0")

    if args.command == "docker":
        cmd_docker(args.version)
    elif args.command == "backend":
        cmd_backend(args.version, args.port or None)
    elif args.command == "frontend":
        cmd_frontend(args.version, args.port or None)


if __name__ == "__main__":
    main()
