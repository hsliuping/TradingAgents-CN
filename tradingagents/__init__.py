#!/usr/bin/env python3
"""
TradingAgents-CN Core Module

This is a multi-agent stock analysis system that supports comprehensive analysis of A-shares, Hong Kong shares, and US shares.
"""

__version__ = "0.1.8"
__author__ = "TradingAgents-CN Team"
__description__ = "Multi-agent stock analysis system for Chinese markets"

# Import core modules
try:
    from .config import config_manager
    from .utils import logging_manager
except ImportError:
    # If import fails, it does not affect the basic functionality of the module
    pass

__all__ = [
    "__version__",
    "__author__", 
    "__description__"
]