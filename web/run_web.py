#!/usr/bin/env python3
"""
TradingAgents-CN Web应用启动脚本
"""

import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

def check_dependencies():
    """检查必要的依赖是否已安装"""

    required_packages = ['streamlit', 'plotly']
    missing_packages = []

    for package in required_packages:
        try:
            if package == 'streamlit':
                import streamlit
            elif package == 'plotly':
                import plotly
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        logger.error(f"❌ 缺少必要的依赖包: {', '.join(missing_packages)}")
        logger.info(f"请运行以下命令安装:")
        logger.info(f"pip install {' '.join(missing_packages)}")
        return False

    logger.info(f"✅ 依赖包检查通过")
    return True

def clean_cache_files(force_clean=False):
    """
    清理Python缓存文件，避免Streamlit文件监控错误

    Args:
        force_clean: 是否强制清理，默认False（可选清理）
    """

    project_root = Path(__file__).parent.parent

    # 安全的缓存目录搜索，避免递归错误
    cache_dirs = []
    try:
        # 限制搜索深度，避免循环符号链接问题
        for root, dirs, files in os.walk(project_root):
            # 限制搜索深度为5层，避免过深递归
            depth = root.replace(str(project_root), '').count(os.sep)
            if depth >= 5:
                dirs[:] = []  # 不再深入搜索
                continue

            # 跳过已知的问题目录
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '.venv', 'env', '.tox'}]

            if '__pycache__' in dirs:
                cache_dirs.append(Path(root) / '__pycache__')

    except (OSError, RecursionError) as e:
        logger.warning(f"⚠️ 缓存搜索遇到问题: {e}")
        logger.info(f"💡 跳过缓存清理，继续启动应用")

    if not cache_dirs:
        logger.info(f"✅ 无需清理缓存文件")
        return

    # 检查环境变量是否禁用清理（使用强健的布尔值解析）
    try:
        from tradingagents.config.env_utils import parse_bool_env
        skip_clean = parse_bool_env('SKIP_CACHE_CLEAN', False)
    except ImportError:
        # 回退到原始方法
        skip_clean = os.getenv('SKIP_CACHE_CLEAN', 'false').lower() == 'true'

    if skip_clean and not force_clean:
        logger.info(f"⏭️ 跳过缓存清理（SKIP_CACHE_CLEAN=true）")
        return

    project_root = Path(__file__).parent.parent

    # 安全地查找缓存目录，避免递归深度问题
    cache_dirs = []
    try:
        # 只在特定目录中查找，避免深度递归
        search_dirs = [
            project_root / "web",
            project_root / "tradingagents",
            project_root / "tests",
            project_root / "scripts",
            project_root / "examples"
        ]

        for search_dir in search_dirs:
            if search_dir.exists():
                try:
                    # 使用有限深度的搜索，最多3层深度
                    for root, dirs, files in os.walk(search_dir):
                        # 限制搜索深度
                        level = len(Path(root).relative_to(search_dir).parts)
                        if level > 3:
                            dirs.clear()  # 不再深入搜索
                            continue

                        if Path(root).name == "__pycache__":
                            cache_dirs.append(Path(root))

                except (RecursionError, OSError) as e:
                    logger.warning(f"跳过目录 {search_dir}: {e}")
                    continue

    except Exception as e:
        logger.warning(f"查找缓存目录时出错: {e}")
        logger.info(f"✅ 跳过缓存清理")
        return

    if not cache_dirs:
        logger.info(f"✅ 无需清理缓存文件")
        return

    if not force_clean:
        # 可选清理：只清理项目代码的缓存，不清理虚拟环境
        project_cache_dirs = [d for d in cache_dirs if 'env' not in str(d)]
        if project_cache_dirs:
            logger.info(f"🧹 清理项目缓存文件...")
            for cache_dir in project_cache_dirs:
                try:
                    import shutil
                    shutil.rmtree(cache_dir)
                    logger.info(f"  ✅ 已清理: {cache_dir.relative_to(project_root)}")
                except Exception as e:
                    logger.error(f"  ⚠️ 清理失败: {cache_dir.relative_to(project_root)} - {e}")
            logger.info(f"✅ 项目缓存清理完成")
        else:
            logger.info(f"✅ 无需清理项目缓存")
    else:
        # 强制清理：清理所有缓存
        logger.info(f"🧹 强制清理所有缓存文件...")
        for cache_dir in cache_dirs:
            try:
                import shutil
                shutil.rmtree(cache_dir)
                logger.info(f"  ✅ 已清理: {cache_dir.relative_to(project_root)}")
            except Exception as e:
                logger.error(f"  ⚠️ 清理失败: {cache_dir.relative_to(project_root)} - {e}")
        logger.info(f"✅ 所有缓存清理完成")

def check_api_keys():
    """检查API密钥配置"""
    
    from dotenv import load_dotenv
    
    # 加载环境变量
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
    
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    
    if not dashscope_key or not finnhub_key:
        logger.warning(f"⚠️ API密钥配置不完整")
        logger.info(f"请确保在.env文件中配置以下密钥:")
        if not dashscope_key:
            logger.info(f"  - DASHSCOPE_API_KEY (阿里百炼)")
        if not finnhub_key:
            logger.info(f"  - FINNHUB_API_KEY (金融数据)")
        logger.info(f"\n配置方法:")
        logger.info(f"1. 复制 .env.example 为 .env")
        logger.info(f"2. 编辑 .env 文件，填入真实API密钥")
        return False
    
    logger.info(f"✅ API密钥配置完成")
    return True

# 在文件顶部添加导入
import signal
import psutil

# 修改 main() 函数中的启动部分
def main():
    """主函数"""
    
    logger.info(f"🚀 TradingAgents-CN Web应用启动器")
    logger.info(f"=")
    
    # 清理缓存文件（可选，避免Streamlit文件监控错误）
    clean_cache_files(force_clean=False)
    
    # 检查依赖
    logger.debug(f"🔍 检查依赖包...")
    if not check_dependencies():
        return
    
    # 检查API密钥
    logger.info(f"🔑 检查API密钥...")
    if not check_api_keys():
        logger.info(f"\n💡 提示: 您仍可以启动Web应用查看界面，但无法进行实际分析")
        response = input("是否继续启动? (y/n): ").lower().strip()
        if response != 'y':
            return
    
    # 启动Streamlit应用
    logger.info(f"\n🌐 启动Web应用...")
    
    web_dir = Path(__file__).parent
    app_file = web_dir / "app.py"
    
    if not app_file.exists():
        logger.error(f"❌ 找不到应用文件: {app_file}")
        return
    
    # 构建Streamlit命令
    config_dir = web_dir.parent / ".streamlit"
    cmd = [
        sys.executable, "-m", "streamlit", "run", 
        str(app_file),
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "auto",
        "--server.runOnSave", "true"
    ]
    
    # 如果配置目录存在，添加配置路径
    if config_dir.exists():
        logger.info(f"📁 使用配置目录: {config_dir}")
        # Streamlit会自动查找.streamlit/config.toml文件
    
    logger.info(f"执行命令: {' '.join(cmd)}")
    logger.info(f"\n🎉 Web应用启动中...")
    logger.info(f"📱 浏览器将自动打开 http://localhost:8501")
    logger.info(f"⏹️  按 Ctrl+C 停止应用")
    logger.info(f"=")
    
    # 创建进程对象而不是直接运行
    process = None
    
    def signal_handler(signum, frame):
        """信号处理函数"""
        logger.info(f"\n\n⏹️ 接收到停止信号，正在关闭Web应用...")
        if process:
            try:
                # 终止进程及其子进程
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                
                # 等待进程结束
                parent.wait(timeout=5)
                logger.info(f"✅ Web应用已成功停止")
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                logger.warning(f"⚠️ 强制终止进程")
                if process:
                    process.kill()
        sys.exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动Streamlit进程
        process = subprocess.Popen(cmd, cwd=web_dir)
        process.wait()  # 等待进程结束
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"\n❌ 启动失败: {e}")

if __name__ == "__main__":
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-clean":
            # 设置环境变量跳过清理
            import os
            os.environ['SKIP_CACHE_CLEAN'] = 'true'
            logger.info(f"🚀 启动模式: 跳过缓存清理")
        elif sys.argv[1] == "--force-clean":
            # 强制清理所有缓存
            logger.info(f"🚀 启动模式: 强制清理所有缓存")
            clean_cache_files(force_clean=True)
        elif sys.argv[1] == "--help":
            logger.info(f"🚀 TradingAgents-CN Web应用启动器")
            logger.info(f"=")
            logger.info(f"用法:")
            logger.info(f"  python run_web.py           # 默认启动（清理项目缓存）")
            logger.info(f"  python run_web.py --no-clean      # 跳过缓存清理")
            logger.info(f"  python run_web.py --force-clean   # 强制清理所有缓存")
            logger.info(f"  python run_web.py --help          # 显示帮助")
            logger.info(f"\n环境变量:")
            logger.info(f"  SKIP_CACHE_CLEAN=true       # 跳过缓存清理")
            exit(0)

    main()
