import os
import sys
import faulthandler

# 🔧 确保项目根目录在 sys.path 中，以便能够导入 app 模块
# 这对于便携版特别重要，因为虚拟环境可能不包含项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 🔧 启用 faulthandler 捕获 segfault 等崩溃
# 崩溃时会将 Python 调用栈输出到 logs/crash.log
logs_dir = os.path.join(project_root, "logs")
os.makedirs(logs_dir, exist_ok=True)
crash_log_path = os.path.join(logs_dir, "crash.log")
crash_log_file = open(crash_log_path, "w")
faulthandler.enable(file=crash_log_file)
print(f"🔧 Faulthandler enabled, crash log: {crash_log_path}")

import uvicorn

def main():
    # 🔧 使用 pydantic settings 读取配置（会自动加载 .env 文件）
    # 而不是 os.getenv()（只读取系统环境变量，不加载 .env）
    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

if __name__ == "__main__":
    main()