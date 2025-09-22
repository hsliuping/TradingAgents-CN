#!/usr/bin/env python3
"""
测试增强版异动监控功能
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.realtime_monitor import RealTimeMonitor, StockMonitorConfig
from tradingagents.utils.logging_manager import get_logger

logger = get_logger('test_monitoring')

def test_enhanced_monitoring():
    """测试增强版监控功能"""
    logger.info("🧪 开始测试增强版异动监控功能")
    
    # 初始化监控器
    monitor = RealTimeMonitor(
        anomaly_threshold=0.1,
        monitor_interval=300,
        redis_key_prefix="test_stock_monitor"
    )
    
    # 测试添加股票配置
    test_stocks = [
        ("000001", StockMonitorConfig(
            symbol="000001",
            anomaly_threshold=0.05,
            monitor_interval=300,
            enable_realtime_push=True,
            name="平安银行"
        )),
        ("AAPL", StockMonitorConfig(
            symbol="AAPL",
            anomaly_threshold=0.1,
            monitor_interval=600,
            enable_realtime_push=True,
            name="苹果公司"
        )),
        ("0700.HK", StockMonitorConfig(
            symbol="0700.HK",
            anomaly_threshold=0.15,
            monitor_interval=300,
            enable_realtime_push=False,
            name="腾讯控股"
        ))
    ]
    
    # 添加测试股票
    logger.info("📈 添加测试股票...")
    for symbol, config in test_stocks:
        success = monitor.add_stock_with_config(symbol, config)
        if success:
            logger.info(f"✅ 成功添加 {symbol}")
        else:
            logger.error(f"❌ 添加 {symbol} 失败")
    
    # 测试配置加载
    logger.info("📋 测试配置加载...")
    monitor.load_all_configs()
    all_configs = monitor.get_all_stock_configs()
    logger.info(f"📊 加载了 {len(all_configs)} 个股票配置")
    
    for symbol, config in all_configs.items():
        logger.info(f"📈 {symbol}: 阈值={config.anomaly_threshold}%, 间隔={config.monitor_interval}s, 推送={config.enable_realtime_push}")
    
    # 测试配置更新
    logger.info("🔄 测试配置更新...")
    if "000001" in all_configs:
        updated_config = all_configs["000001"]
        updated_config.anomaly_threshold = 0.08
        updated_config.monitor_interval = 180
        
        success = monitor.update_stock_config("000001", updated_config)
        if success:
            logger.info("✅ 配置更新成功")
        else:
            logger.error("❌ 配置更新失败")
    
    # 测试删除股票
    logger.info("🗑️ 测试删除股票...")
    if "0700.HK" in all_configs:
        success = monitor.remove_stock("0700.HK")
        if success:
            logger.info("✅ 删除股票成功")
        else:
            logger.error("❌ 删除股票失败")
    
    # 验证删除后的状态
    logger.info("🔍 验证删除后状态...")
    monitor.load_all_configs()
    final_configs = monitor.get_all_stock_configs()
    logger.info(f"📊 最终配置数量: {len(final_configs)}")
    
    # 清理测试数据
    logger.info("🧹 清理测试数据...")
    for symbol in list(final_configs.keys()):
        monitor.remove_stock(symbol)
    
    logger.info("✅ 测试完成")

if __name__ == "__main__":
    test_enhanced_monitoring()