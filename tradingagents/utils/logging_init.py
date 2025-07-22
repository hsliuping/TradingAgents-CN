#!/usr/bin/env python3
"""
Logging system initialization module
Initialize unified logging system at application startup
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.utils.logging_manager import setup_logging, get_logger


def init_logging(config_override: Optional[dict] = None) -> None:
    """
    Initialize project logging system
    
    Args:
        config_override: Optional configuration override
    """
    # Set up logging system
    logger_manager = setup_logging(config_override)
    
    # Get initialized logger
    logger = get_logger('tradingagents.init')
    
    # Log initialization info
    logger.info("🚀 TradingAgents-CN logging system initialized")
    logger.info(f"📁 Log directory: {logger_manager.config.get('handlers', {}).get('file', {}).get('directory', 'N/A')}")
    logger.info(f"📊 Log level: {logger_manager.config.get('level', 'INFO')}")
    
    # Special handling for Docker environment
    if logger_manager.config.get('docker', {}).get('enabled', False):
        logger.info("🐳 Docker environment detected, using container-optimized configuration")
    
    # Log environment info
    logger.debug(f"🔧 Python version: {sys.version}")
    logger.debug(f"📂 Working directory: {os.getcwd()}")
    logger.debug(f"🌍 Environment variable: DOCKER_CONTAINER={os.getenv('DOCKER_CONTAINER', 'false')}")


def get_session_logger(session_id: str, module_name: str = 'session') -> 'logging.Logger':
    """
    Get session-specific logger
    
    Args:
        session_id: Session ID
        module_name: Module name
        
    Returns:
        Configured logger
    """
    logger_name = f"{module_name}.{session_id[:8]}"  # Use first 8 chars of session ID
    
    # Add session ID to all log records
    class SessionAdapter:
        def __init__(self, logger, session_id):
            self.logger = logger
            self.session_id = session_id
        
        def debug(self, msg, *args, **kwargs):
            kwargs.setdefault('extra', {})['session_id'] = self.session_id
            return self.logger.debug(msg, *args, **kwargs)
        
        def info(self, msg, *args, **kwargs):
            kwargs.setdefault('extra', {})['session_id'] = self.session_id
            return self.logger.info(msg, *args, **kwargs)
        
        def warning(self, msg, *args, **kwargs):
            kwargs.setdefault('extra', {})['session_id'] = self.session_id
            return self.logger.warning(msg, *args, **kwargs)
        
        def error(self, msg, *args, **kwargs):
            kwargs.setdefault('extra', {})['session_id'] = self.session_id
            return self.logger.error(msg, *args, **kwargs)
        
        def critical(self, msg, *args, **kwargs):
            kwargs.setdefault('extra', {})['session_id'] = self.session_id
            return self.logger.critical(msg, *args, **kwargs)
    
    return SessionAdapter(logger, session_id)


def log_startup_info():
    """Log application startup info"""
    logger = get_logger('tradingagents.startup')
    
    logger.info("=" * 60)
    logger.info("🎯 TradingAgents-CN Startup")
    logger.info("=" * 60)
    
    # System info
    import platform
    logger.info(f"🖥️  System: {platform.system()} {platform.release()}")
    logger.info(f"🐍 Python: {platform.python_version()}")
    
    # Environment info
    env_info = {
        'DOCKER_CONTAINER': os.getenv('DOCKER_CONTAINER', 'false'),
        'TRADINGAGENTS_LOG_LEVEL': os.getenv('TRADINGAGENTS_LOG_LEVEL', 'INFO'),
        'TRADINGAGENTS_LOG_DIR': os.getenv('TRADINGAGENTS_LOG_DIR', './logs'),
    }
    
    for key, value in env_info.items():
        logger.info(f"🔧 {key}: {value}")
    
    logger.info("=" * 60)


def log_shutdown_info():
    """Log application shutdown info"""
    logger = get_logger('tradingagents.shutdown')
    
    logger.info("=" * 60)
    logger.info("🛑 TradingAgents-CN Shutdown")
    logger.info("=" * 60)


# Convenience functions
def setup_web_logging():
    """Set up logging for web application"""
    init_logging()
    log_startup_info()
    return get_logger('web')


def setup_analysis_logging(session_id: str):
    """Set up logging for analysis"""
    return get_session_logger(session_id, 'analysis')


def setup_dataflow_logging():
    """Set up logging for dataflows"""
    return get_logger('dataflows')


def setup_llm_logging():
    """Set up logging for LLM adapters"""
    return get_logger('llm_adapters')


if __name__ == "__main__":
    # Test logging system
    init_logging()
    log_startup_info()
    
    # Test logging for different modules
    web_logger = setup_web_logging()
    web_logger.info("Web module log test")
    
    analysis_logger = setup_analysis_logging("test-session-123")
    analysis_logger.info("Analysis module log test")
    
    dataflow_logger = setup_dataflow_logging()
    dataflow_logger.info("Dataflow module log test")
    
    llm_logger = setup_llm_logging()
    llm_logger.info("LLM adapter module log test")
    
    log_shutdown_info()
