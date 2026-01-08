"""
TradingAgents-CN Backend Entry Point
支持 python -m app 启动方式
"""

import uvicorn
import sys
import os
from pathlib import Path

# ============================================================================
# 全局 UTF-8 编码设置（必须在最开始，支持 emoji 和中文）
# ============================================================================
if sys.platform == 'win32':
    try:
        # 1. 设置环境变量，让 Python 全局使用 UTF-8
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'

        # 2. 设置标准输出和错误输出为 UTF-8
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

        # 3. 尝试设置控制台代码页为 UTF-8 (65001)
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass

    except Exception as e:
        # 如果设置失败，打印警告但继续运行
        print(f"Warning: Failed to set UTF-8 encoding: {e}", file=sys.stderr)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 检查并打印.env文件加载信息
def check_env_file():
    """检查并打印.env文件加载信息"""
    import logging
    logger = logging.getLogger("app.startup")
    
    logger.info("🔍 检查环境配置文件...")

    # 检查当前工作目录
    current_dir = Path.cwd()
    logger.info(f"📂 当前工作目录: {current_dir}")

    # 检查项目根目录
    logger.info(f"📂 项目根目录: {project_root}")
    
    # 检查可能的.env文件位置（按优先级排序）
    env_locations = [
        project_root / ".env",          # 优先：项目根目录（标准位置）
        current_dir / ".env",           # 次选：当前工作目录
        Path(__file__).parent / ".env"  # 最后：app目录下（不推荐）
    ]

    env_found = False

    for env_path in env_locations:
        if env_path.exists():
            if not env_found:  # 只显示第一个找到的文件详情
                logger.info(f"✅ 找到.env文件: {env_path}")
                logger.info(f"📏 文件大小: {env_path.stat().st_size} bytes")
                env_found = True

                # 读取并显示部分内容（隐藏敏感信息）
                try:
                    with open(env_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    logger.info(f"📄 .env文件内容预览 (共{len(lines)}行):")
                    for i, line in enumerate(lines[:10]):  # 只显示前10行
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # 隐藏敏感信息
                            if any(keyword in line.upper() for keyword in ['SECRET', 'PASSWORD', 'TOKEN', 'KEY']):
                                key = line.split('=')[0] if '=' in line else line
                                logger.info(f"  {key}=***")
                            else:
                                logger.info(f"  {line}")
                    if len(lines) > 10:
                        logger.info(f"  ... (还有{len(lines) - 10}行)")
                except Exception as e:
                    logger.warning(f"⚠️ 读取.env文件时出错: {e}")
            else:
                # 如果已经找到一个，只记录其他位置也有文件（可能重复）
                logger.debug(f"ℹ️  其他位置也有.env文件: {env_path}")

    if not env_found:
        logger.warning("⚠️ 未找到.env文件，将使用默认配置")
        logger.info(f"💡 提示: 请在项目根目录 ({project_root}) 创建 .env 文件")
    
    logger.info("-" * 50)

try:
    from app.core.config import settings
    from app.core.dev_config import DEV_CONFIG
except Exception as e:
    import traceback
    print(f"❌ 导入配置模块失败: {e}")
    print("📋 详细错误信息:")
    print("-" * 50)
    traceback.print_exc()
    print("-" * 50)
    sys.exit(1)


def main():
    """主启动函数"""
    import logging
    logger = logging.getLogger("app.startup")
    
    logger.info("🚀 Starting TradingAgents-CN Backend...")
    logger.info(f"📍 Host: {settings.HOST}")
    logger.info(f"🔌 Port: {settings.PORT}")
    logger.info(f"🐛 Debug Mode: {settings.DEBUG}")
    logger.info(f"📚 API Docs: http://{settings.HOST}:{settings.PORT}/docs" if settings.DEBUG else "📚 API Docs: Disabled in production")
    
    # 打印关键配置信息
    logger.info("🔧 关键配置信息:")
    logger.info(f"  📊 MongoDB: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}/{settings.MONGODB_DATABASE}")
    logger.info(f"  🔴 Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
    logger.info(f"  🔐 JWT Secret: {'已配置' if settings.JWT_SECRET != 'change-me-in-production' else '⚠️ 使用默认值'}")
    logger.info(f"  📝 日志级别: {settings.LOG_LEVEL}")
    
    # 检查环境变量加载状态
    logger.info("🌍 环境变量加载状态:")
    env_vars_to_check = [
        ('MONGODB_HOST', settings.MONGODB_HOST, 'localhost'),
        ('MONGODB_PORT', str(settings.MONGODB_PORT), '27017'),
        ('MONGODB_DATABASE', settings.MONGODB_DATABASE, 'tradingagents'),
        ('REDIS_HOST', settings.REDIS_HOST, 'localhost'),
        ('REDIS_PORT', str(settings.REDIS_PORT), '6379'),
        ('JWT_SECRET', '***' if settings.JWT_SECRET != 'change-me-in-production' else settings.JWT_SECRET, 'change-me-in-production')
    ]
    
    for env_name, current_value, default_value in env_vars_to_check:
        status = "✅ 已设置" if current_value != default_value else "⚠️ 默认值"
        logger.info(f"  {env_name}: {current_value} ({status})")
    
    logger.info("-" * 50)

    # 获取uvicorn配置
    uvicorn_config = DEV_CONFIG.get_uvicorn_config(settings.DEBUG)

    # 设置简化的日志配置
    logger.info("🔧 正在设置日志配置...")
    try:
        from app.core.logging_config import setup_logging as app_setup_logging
        app_setup_logging(settings.LOG_LEVEL)
    except Exception:
        # 回退到开发环境简化日志配置
        DEV_CONFIG.setup_logging(settings.DEBUG)
    logger.info("✅ 日志配置设置完成")

    # 在日志系统初始化后检查.env文件
    logger.info("📋 Configuration Loading Phase:")
    check_env_file()

    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            **uvicorn_config
        )
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        import traceback
        logger.error(f"❌ Failed to start server: {e}")
        logger.error("📋 详细错误信息:")
        logger.error("-" * 50)
        traceback.print_exc()
        logger.error("-" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
