#!/usr/bin/env python3
"""
TradingAgents-CN 后端直接启动脚本
控制日志级别，减少不必要的文件监控日志
"""

import uvicorn
import logging
import sys
import os

# 添加app目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def setup_logging():
    """设置日志配置"""
    # 设置watchfiles日志级别为WARNING，减少文件变化日志
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

    # 设置uvicorn日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # 确保webapi日志正常显示
    logging.getLogger("webapi").setLevel(logging.INFO)

    # 设置根日志级别
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    """主函数"""
    print("🚀 启动 TradingAgents-CN 后端服务...")
    
    # 设置日志
    setup_logging()
    
    # 启动uvicorn服务器
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8100,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
        access_log=True,
        # 减少文件监控的敏感度
        reload_delay=0.5,
        # 忽略某些文件类型的变化
        reload_excludes=["*.pyc", "*.pyo", "__pycache__", ".git", "*.log"]
    )

if __name__ == "__main__":
    main()
