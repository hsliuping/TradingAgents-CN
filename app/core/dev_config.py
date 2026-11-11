"""
开发环境配置
优化开发体验，减少不必要的文件监控
"""

import logging
from typing import List, Optional


class DevConfig:
    """开发环境配置类"""
    
    # 文件监控配置
    RELOAD_DIRS: List[str] = ["app"]
    
    # 排除的文件和目录
    RELOAD_EXCLUDES: List[str] = [
        # Python缓存文件
        "__pycache__",
        "*.pyc",
        "*.pyo", 
        "*.pyd",
        
        # 版本控制
        ".git",
        ".gitignore",
        
        # 测试和缓存
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        
        # 日志文件
        "*.log",
        "logs",
        
        # 临时文件
        "*.tmp",
        "*.temp",
        "*.swp",
        "*.swo",
        
        # 系统文件
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
        
        # IDE文件
        ".vscode",
        ".idea",
        "*.sublime-*",
        
        # 数据文件
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        
        # 配置文件（避免敏感信息重载）
        ".env",
        ".env.local",
        ".env.production",
        
        # 文档和静态文件
        "*.md",
        "*.txt",
        "*.json",
        "*.yaml",
        "*.yml",
        "*.toml",
        
        # 前端文件
        "node_modules",
        "dist",
        "build",
        "*.js",
        "*.css",
        "*.html",
        
        # 其他
        "requirements*.txt",
        "Dockerfile*",
        "docker-compose*"
    ]
    
    # 只监控的文件类型
    RELOAD_INCLUDES: List[str] = [
        "*.py"
    ]
    
    # 重载延迟（秒）
    RELOAD_DELAY: float = 0.5
    
    # 日志配置
    LOG_LEVEL: str = "info"
    
    # 是否显示访问日志
    ACCESS_LOG: bool = True
    
    @classmethod
    def get_uvicorn_config(cls, debug: bool = True) -> dict:
        """获取uvicorn配置"""
        # 统一禁用reload，避免日志配置冲突
        return {
            "reload": False,  # 禁用自动重载，手动重启
            "log_level": cls.LOG_LEVEL,
            "access_log": cls.ACCESS_LOG,
            # 确保使用我们自定义的日志配置
            "log_config": None  # 禁用uvicorn默认日志配置，使用我们的配置
        }
    
    @classmethod
    def setup_logging(cls, debug: bool = True):
        """设置简化的日志配置"""
        # 统一的日志格式（共享初始化函数，日志治理 §5.3）
        from core.utils.logging_setup import setup_cli_logging
        setup_cli_logging(
            "INFO",
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            force=True,  # 强制重新配置，覆盖之前的设置
        )

        if debug:
            # 开发环境：减少噪音日志
            logging.getLogger("watchfiles").setLevel(logging.ERROR)
            logging.getLogger("watchfiles.main").setLevel(logging.ERROR)
            logging.getLogger("watchfiles.watcher").setLevel(logging.ERROR)

            # 确保重要日志正常显示
            logging.getLogger("webapi").setLevel(logging.INFO)
            logging.getLogger("app.core.database").setLevel(logging.INFO)
            logging.getLogger("uvicorn.error").setLevel(logging.INFO)

            # 测试webapi logger是否工作
            webapi_logger = logging.getLogger("webapi")
            webapi_logger.info("🔧 DEV_CONFIG: webapi logger 测试消息")
        else:
            # 生产环境：更严格的日志控制
            logging.getLogger("watchfiles").setLevel(logging.ERROR)
            logging.getLogger("uvicorn").setLevel(logging.WARNING)


# 开发环境快捷配置
DEV_CONFIG = DevConfig()
