#!/bin/bash
# TradingAgents-CN MiMo 金融分析 CLI 启动脚本
# 用法: ./analyze.sh 600519 "这只股票到今年年底还能持有吗？"

cd "$(dirname "$0")"
python mimo_analyze.py "$@"
