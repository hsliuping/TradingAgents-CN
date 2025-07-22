#!/usr/bin/env python3
"""
TradingAgents-CN Web Application Startup Script
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

def check_dependencies():
    """Check if all required dependencies are installed"""

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
        logger.error(f"❌ Missing required packages: {', '.join(missing_packages)}")
        logger.info(f"Please run the following command to install:")
        logger.info(f"pip install {' '.join(missing_packages)}")
        return False

    logger.info(f"✅ Dependency check passed")
    return True

def clean_cache_files(force_clean=False):
    """
    Clean Python cache files to avoid Streamlit file watcher errors

    Args:
        force_clean: whether to force clean, default False (optional clean)
    """

    project_root = Path(__file__).parent.parent
    cache_dirs = list(project_root.rglob("__pycache__"))

    if not cache_dirs:
        logger.info(f"✅ No cache files need to be cleaned")
        return

    # Check if environment variable is set to disable cleaning
    import os
    skip_clean = os.getenv('SKIP_CACHE_CLEAN', 'false').lower() == 'true'

    if skip_clean and not force_clean:
        logger.info(f"⏭️ Skipping cache cleanup (SKIP_CACHE_CLEAN=true)")
        return

    if not force_clean:
        # Optional cleanup: only clean project code cache, not virtual environment
        project_cache_dirs = [d for d in cache_dirs if 'env' not in str(d)]
        if project_cache_dirs:
            logger.info(f"🧹 Cleaning project cache files...")
            for cache_dir in project_cache_dirs:
                try:
                    import shutil
                    shutil.rmtree(cache_dir)
                    logger.info(f"  ✅ Cleaned: {cache_dir.relative_to(project_root)}")
                except Exception as e:
                    logger.error(f"  ⚠️ Cleanup failed: {cache_dir.relative_to(project_root)} - {e}")
            logger.info(f"✅ Project cache cleanup completed")
        else:
            logger.info(f"✅ No project cache to clean")
    else:
        # Force cleanup: clean all cache
        logger.info(f"🧹 Forcing cleanup of all cache files...")
        for cache_dir in cache_dirs:
            try:
                import shutil
                shutil.rmtree(cache_dir)
                logger.info(f"  ✅ Cleaned: {cache_dir.relative_to(project_root)}")
            except Exception as e:
                logger.error(f"  ⚠️ Cleanup failed: {cache_dir.relative_to(project_root)} - {e}")
        logger.info(f"✅ All cache cleanup completed")

def check_api_keys():
    """Check API key configuration"""
    
    from dotenv import load_dotenv
    
    # Load environment variables
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
    
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    
    if not dashscope_key or not finnhub_key:
        logger.warning(f"⚠️ API key configuration incomplete")
        logger.info(f"Please ensure the following keys are configured in your .env file:")
        if not dashscope_key:
            logger.info(f"  - DASHSCOPE_API_KEY (Aliyun)")
        if not finnhub_key:
            logger.info(f"  - FINNHUB_API_KEY (Financial Data)")
        logger.info(f"\nConfiguration method:")
        logger.info(f"1. Copy .env.example to .env")
        logger.info(f"2. Edit the .env file and enter the actual API keys")
        return False
    
    logger.info(f"✅ API key configuration completed")
    return True

# Add imports at the top of the file
import signal
import psutil

# Modify the main() function's startup part
def main():
    """Main function"""
    
    logger.info(f"🚀 TradingAgents-CN Web Application Launcher")
    logger.info(f"=")
    
    # Clean cache files (optional, to avoid Streamlit file watcher errors)
    clean_cache_files(force_clean=False)
    
    # Check dependencies
    logger.debug(f"🔍 Checking dependencies...")
    if not check_dependencies():
        return
    
    # Check API keys
    logger.info(f"🔑 Checking API keys...")
    if not check_api_keys():
        logger.info(f"\n💡 Hint: You can still start the Web application to view the interface, but you cannot perform actual analysis")
        response = input("Do you want to continue starting? (y/n): ").lower().strip()
        if response != 'y':
            return
    
    # Start Streamlit application
    logger.info(f"\n🌐 Starting Web application...")
    
    web_dir = Path(__file__).parent
    app_file = web_dir / "app.py"
    
    if not app_file.exists():
        logger.error(f"❌ Application file not found: {app_file}")
        return
    
    # Build Streamlit command
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
    
    # If config directory exists, add config path
    if config_dir.exists():
        logger.info(f"📁 Using config directory: {config_dir}")
        # Streamlit will automatically find the .streamlit/config.toml file
    
    logger.info(f"Executing command: {' '.join(cmd)}")
    logger.info(f"\n🎉 Web application starting...")
    logger.info(f"📱 Browser will automatically open http://localhost:8501")
    logger.info(f"⏹️  Press Ctrl+C to stop the application")
    logger.info(f"=")
    
    # Create process object instead of running directly
    process = None
    
    def signal_handler(signum, frame):
        """Signal handler function"""
        logger.info(f"\n\n⏹️ Received stop signal, closing Web application...")
        if process:
            try:
                # Terminate process and its children
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                
                # Wait for process to end
                parent.wait(timeout=5)
                logger.info(f"✅ Web application successfully stopped")
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                logger.warning(f"⚠️ Forcing process termination")
                if process:
                    process.kill()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start Streamlit process
        process = subprocess.Popen(cmd, cwd=web_dir)
        process.wait()  # Wait for process to end
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"\n❌ Startup failed: {e}")

if __name__ == "__main__":
    import sys

    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-clean":
            # Set environment variable to skip cleanup
            import os
            os.environ['SKIP_CACHE_CLEAN'] = 'true'
            logger.info(f"🚀 Startup mode: Skipping cache cleanup")
        elif sys.argv[1] == "--force-clean":
            # Force clean all cache
            logger.info(f"🚀 Startup mode: Forcing all cache cleanup")
            clean_cache_files(force_clean=True)
        elif sys.argv[1] == "--help":
            logger.info(f"🚀 TradingAgents-CN Web Application Launcher")
            logger.info(f"=")
            logger.info(f"Usage:")
            logger.info(f"  python run_web.py           # Default startup (clean project cache)")
            logger.info(f"  python run_web.py --no-clean      # Skip cache cleanup")
            logger.info(f"  python run_web.py --force-clean   # Force clean all cache")
            logger.info(f"  python run_web.py --help          # Show help")
            logger.info(f"\nEnvironment variables:")
            logger.info(f"  SKIP_CACHE_CLEAN=true       # Skip cache cleanup")
            exit(0)

    main()
