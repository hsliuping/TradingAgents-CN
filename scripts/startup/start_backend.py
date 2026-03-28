#!/usr/bin/env python3
"""
TradingAgents-CN Backend Launcher
快速启动脚本
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """启动后端服务"""
    print("🚀 TradingAgents-CN Backend Launcher")
    print("=" * 50)
    
    # 确保在项目根目录
    project_root = Path(__file__).resolve().parents[2]
    os.chdir(project_root)
    
    # 检查Python版本
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ is required")
        sys.exit(1)
    
    # 检查app目录是否存在
    if not (project_root / "app").exists():
        print("❌ app directory not found")
        sys.exit(1)
    
    print("✅ Environment check passed")
    print("🔄 Starting backend server...")
    print("-" * 50)
    
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
