#!/usr/bin/env python3
"""
异动监控定时任务服务
集成实时监控、异动分析和消息通知的统一服务
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import json

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('anomaly_service')

# 导入核心模块
try:
    from tradingagents.dataflows.realtime_monitor import (
        RealTimeMonitor, AnomalyEvent, get_global_monitor
    )
    from tradingagents.agents.analysts.anomaly_analyst import (
        AnomalyAnalyst, AnomalyAnalysisResult, get_global_anomaly_analyst, analyze_anomaly_event
    )
    ANOMALY_MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ 异动模块导入失败: {e}")
    ANOMALY_MODULES_AVAILABLE = False


class AnomalyMonitoringService:
    """异动监控服务 - 统一管理监控、分析和通知"""
    
    def __init__(self, 
                 anomaly_threshold: float = 0.1,    # 异动阈值 0.1%
                 monitor_interval: int = 300,       # 监控间隔 5分钟 (300秒)
                 analysis_enabled: bool = True,     # 是否启用异动分析
                 notification_enabled: bool = True  # 是否启用消息通知
                 ):
        """
        初始化异动监控服务
        
        Args:
            anomaly_threshold: 异动检测阈值（百分比）
            monitor_interval: 监控间隔（秒）
            analysis_enabled: 是否启用异动分析
            notification_enabled: 是否启用消息通知
        """
        self.anomaly_threshold = anomaly_threshold
        self.monitor_interval = monitor_interval
        self.analysis_enabled = analysis_enabled
        self.notification_enabled = notification_enabled
        
        # 服务状态
        self.is_running = False
        self.service_thread = None
        
        # 核心组件
        self.monitor: Optional[RealTimeMonitor] = None
        self.analyst: Optional[AnomalyAnalyst] = None
        
        # 通知回调
        self.notification_callbacks: List[Callable[[AnomalyEvent, Optional[AnomalyAnalysisResult]], None]] = []
        
        # 统计信息
        self.stats = {
            "service_start_time": None,
            "total_anomalies_detected": 0,
            "total_analyses_completed": 0,
            "notifications_sent": 0,
            "last_anomaly_time": None,
            "monitored_stocks": set(),
            "analysis_queue_size": 0
        }
        
        logger.info(f"🎯 异动监控服务初始化完成")
        logger.info(f"   异动阈值: {anomaly_threshold}%")
        logger.info(f"   监控间隔: {monitor_interval}秒 ({monitor_interval/60:.1f}分钟)")
        logger.info(f"   异动分析: {'启用' if analysis_enabled else '禁用'}")
        logger.info(f"   消息通知: {'启用' if notification_enabled else '禁用'}")
        
        # 初始化组件
        self._init_components()
    
    def _init_components(self):
        """初始化核心组件"""
        if not ANOMALY_MODULES_AVAILABLE:
            logger.error("❌ 异动模块不可用，服务无法正常运行")
            return
        
        try:
            # 初始化实时监控器
            self.monitor = get_global_monitor()
            if self.monitor:
                # 设置监控参数
                self.monitor.anomaly_threshold = self.anomaly_threshold
                self.monitor.monitor_interval = self.monitor_interval
                
                # 注册异动回调
                self.monitor.add_anomaly_callback(self._on_anomaly_detected)
                logger.info("✅ 实时监控器初始化成功")
            else:
                logger.error("❌ 实时监控器初始化失败")
            
            # 初始化异动分析师
            if self.analysis_enabled:
                self.analyst = get_global_anomaly_analyst()
                if self.analyst:
                    logger.info("✅ 异动分析师初始化成功")
                else:
                    logger.error("❌ 异动分析师初始化失败")
            
        except Exception as e:
            logger.error(f"❌ 组件初始化失败: {e}")
    
    def start_service(self):
        """启动异动监控服务"""
        if self.is_running:
            logger.warning("⚠️ 异动监控服务已在运行中")
            return False
        
        if not ANOMALY_MODULES_AVAILABLE:
            logger.error("❌ 异动模块不可用，无法启动服务")
            return False
        
        if not self.monitor:
            logger.error("❌ 实时监控器未就绪，无法启动服务")
            return False
        
        # 检查是否有监控股票
        if not self.monitor.monitored_stocks:
            logger.warning("⚠️ 没有配置监控股票，请先添加要监控的股票")
            return False
        
        try:
            # 更新统计信息
            self.stats["service_start_time"] = datetime.now()
            self.stats["monitored_stocks"] = self.monitor.monitored_stocks.copy()
            
            # 启动实时监控
            self.monitor.start_monitoring()
            
            # 启动服务主循环
            self.is_running = True
            self.service_thread = threading.Thread(target=self._service_loop, daemon=True)
            self.service_thread.start()
            
            logger.info(f"🚀 异动监控服务已启动")
            logger.info(f"   监控股票: {len(self.monitor.monitored_stocks)}只")
            logger.info(f"   监控股票列表: {list(self.monitor.monitored_stocks)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动异动监控服务失败: {e}")
            self.is_running = False
            return False
    
    def stop_service(self):
        """停止异动监控服务"""
        if not self.is_running:
            logger.warning("⚠️ 异动监控服务未在运行")
            return
        
        try:
            # 停止服务循环
            self.is_running = False
            
            # 停止实时监控
            if self.monitor:
                self.monitor.stop_monitoring()
            
            # 等待服务线程结束
            if self.service_thread:
                self.service_thread.join(timeout=10)
            
            logger.info("⏹️ 异动监控服务已停止")
            
        except Exception as e:
            logger.error(f"❌ 停止异动监控服务失败: {e}")
    
    def add_monitored_stock(self, symbol: str) -> bool:
        """
        添加监控股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否添加成功
        """
        if not self.monitor:
            logger.error("❌ 实时监控器未就绪")
            return False
        
        result = self.monitor.add_stock(symbol)
        if result:
            self.stats["monitored_stocks"].add(symbol)
            logger.info(f"📈 已添加监控股票: {symbol}")
        
        return result
    
    def remove_monitored_stock(self, symbol: str) -> bool:
        """
        移除监控股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否移除成功
        """
        if not self.monitor:
            logger.error("❌ 实时监控器未就绪")
            return False
        
        result = self.monitor.remove_stock(symbol)
        if result:
            self.stats["monitored_stocks"].discard(symbol)
            logger.info(f"📉 已移除监控股票: {symbol}")
        
        return result
    
    def add_notification_callback(self, callback: Callable[[AnomalyEvent, Optional[AnomalyAnalysisResult]], None]):
        """
        添加通知回调函数
        
        Args:
            callback: 回调函数，接收异动事件和分析结果
        """
        self.notification_callbacks.append(callback)
        logger.info(f"📞 已添加通知回调函数: {callback.__name__}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态信息
        
        Returns:
            Dict: 服务状态信息
        """
        status = {
            "is_running": self.is_running,
            "service_config": {
                "anomaly_threshold": self.anomaly_threshold,
                "monitor_interval": self.monitor_interval,
                "analysis_enabled": self.analysis_enabled,
                "notification_enabled": self.notification_enabled
            },
            "components_status": {
                "monitor_available": self.monitor is not None,
                "analyst_available": self.analyst is not None,
                "modules_available": ANOMALY_MODULES_AVAILABLE
            },
            "statistics": self.stats.copy()
        }
        
        # 更新监控器状态
        if self.monitor:
            monitor_status = self.monitor.get_monitoring_status()
            status["monitor_status"] = monitor_status
        
        return status
    
    def get_recent_anomalies(self, symbol: str = None, limit: int = 10) -> List[AnomalyEvent]:
        """
        获取最近的异动事件
        
        Args:
            symbol: 股票代码，为None时返回所有股票的异动
            limit: 返回记录数限制
            
        Returns:
            List[AnomalyEvent]: 异动事件列表
        """
        if not self.monitor:
            return []
        
        if symbol:
            return self.monitor.get_anomaly_history(symbol, limit)
        else:
            # 获取所有监控股票的异动
            all_anomalies = []
            for stock_symbol in self.monitor.monitored_stocks:
                anomalies = self.monitor.get_anomaly_history(stock_symbol, limit)
                all_anomalies.extend(anomalies)
            
            # 按时间倒序排序
            all_anomalies.sort(key=lambda x: x.detection_time, reverse=True)
            return all_anomalies[:limit]
    
    def get_analysis_history(self, symbol: str = None, limit: int = 10) -> List[AnomalyAnalysisResult]:
        """
        获取异动分析历史
        
        Args:
            symbol: 股票代码，为None时返回所有股票的分析
            limit: 返回记录数限制
            
        Returns:
            List[AnomalyAnalysisResult]: 分析结果列表
        """
        if not self.analyst:
            return []
        
        return self.analyst.get_analysis_history(symbol, limit)
    
    def _service_loop(self):
        """服务主循环"""
        logger.info("🔄 异动监控服务循环开始")
        
        while self.is_running:
            try:
                start_time = time.time()
                
                # 执行定期维护任务
                self._perform_maintenance_tasks()
                
                # 计算执行时间
                execution_time = time.time() - start_time
                logger.debug(f"⏱️ 服务循环耗时: {execution_time:.2f}秒")
                
                # 等待下一个循环
                sleep_time = max(0, 60 - execution_time)  # 每分钟执行一次维护任务
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"❌ 服务循环异常: {e}")
                time.sleep(10)  # 异常时等待10秒再继续
        
        logger.info("🔄 异动监控服务循环结束")
    
    def _perform_maintenance_tasks(self):
        """执行定期维护任务"""
        try:
            # 更新统计信息
            self._update_statistics()
            
            # 清理过期数据（可选）
            # self._cleanup_expired_data()
            
            logger.debug("🧹 维护任务执行完成")
            
        except Exception as e:
            logger.error(f"❌ 维护任务执行失败: {e}")
    
    def _update_statistics(self):
        """更新统计信息"""
        try:
            if self.monitor:
                # 获取最新异动
                recent_anomalies = self.get_recent_anomalies(limit=1)
                if recent_anomalies:
                    self.stats["last_anomaly_time"] = recent_anomalies[0].detection_time
            
            # 更新监控股票数量
            if self.monitor:
                self.stats["monitored_stocks"] = self.monitor.monitored_stocks.copy()
            
        except Exception as e:
            logger.error(f"❌ 更新统计信息失败: {e}")
    
    def _on_anomaly_detected(self, anomaly_event: AnomalyEvent):
        """
        异动检测回调函数
        
        Args:
            anomaly_event: 异动事件
        """
        try:
            logger.warning(f"🚨 检测到异动: {anomaly_event.symbol} {anomaly_event.name} "
                         f"{'上涨' if anomaly_event.anomaly_type == 'surge' else '下跌'} "
                         f"{abs(anomaly_event.change_percent):.2f}%")
            
            # 更新统计信息
            self.stats["total_anomalies_detected"] += 1
            self.stats["last_anomaly_time"] = anomaly_event.detection_time
            
            # 执行异动分析
            analysis_result = None
            if self.analysis_enabled and self.analyst:
                asyncio.run(self._analyze_anomaly_async(anomaly_event))
            
            # 发送通知
            if self.notification_enabled:
                self._send_notifications(anomaly_event, analysis_result)
            
        except Exception as e:
            logger.error(f"❌ 处理异动事件失败: {e}")
    
    async def _analyze_anomaly_async(self, anomaly_event: AnomalyEvent):
        """
        异步执行异动分析
        
        Args:
            anomaly_event: 异动事件
        """
        try:
            logger.info(f"🔍 开始分析异动: {anomaly_event.symbol}")
            
            # 执行异动分析
            analysis_result = await analyze_anomaly_event(anomaly_event)
            
            # 更新统计信息
            self.stats["total_analyses_completed"] += 1
            
            logger.info(f"✅ 异动分析完成: {anomaly_event.symbol} "
                       f"结论: {analysis_result.investment_suggestion} "
                       f"置信度: {analysis_result.confidence_score:.2f}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 异动分析失败: {e}")
            return None
    
    def _send_notifications(self, anomaly_event: AnomalyEvent, analysis_result: Optional[AnomalyAnalysisResult]):
        """
        发送异动通知
        
        Args:
            anomaly_event: 异动事件
            analysis_result: 分析结果（可选）
        """
        try:
            # 触发所有通知回调
            for callback in self.notification_callbacks:
                try:
                    callback(anomaly_event, analysis_result)
                    self.stats["notifications_sent"] += 1
                except Exception as e:
                    logger.error(f"❌ 通知回调执行失败 {callback.__name__}: {e}")
            
            if self.notification_callbacks:
                logger.info(f"📢 已发送异动通知: {anomaly_event.symbol} "
                           f"(共{len(self.notification_callbacks)}个回调)")
            
        except Exception as e:
            logger.error(f"❌ 发送异动通知失败: {e}")


# 全局异动监控服务实例
_global_anomaly_service = None

def get_global_anomaly_service() -> AnomalyMonitoringService:
    """获取全局异动监控服务实例"""
    global _global_anomaly_service
    if _global_anomaly_service is None:
        _global_anomaly_service = AnomalyMonitoringService()
    return _global_anomaly_service


def start_anomaly_monitoring(
    stocks: List[str], 
    anomaly_threshold: float = 0.1,
    monitor_interval: int = 300
) -> bool:
    """
    便捷函数：启动异动监控
    
    Args:
        stocks: 要监控的股票代码列表
        anomaly_threshold: 异动阈值
        monitor_interval: 监控间隔（秒）
        
    Returns:
        bool: 是否启动成功
    """
    service = get_global_anomaly_service()
    
    # 配置监控参数
    service.anomaly_threshold = anomaly_threshold
    service.monitor_interval = monitor_interval
    
    # 添加监控股票
    for stock in stocks:
        service.add_monitored_stock(stock)
    
    # 启动服务
    return service.start_service()


def stop_anomaly_monitoring():
    """便捷函数：停止异动监控"""
    service = get_global_anomaly_service()
    service.stop_service()


# 示例通知回调函数
def console_notification_callback(anomaly_event: AnomalyEvent, analysis_result: Optional[AnomalyAnalysisResult]):
    """控制台通知回调示例"""
    print(f"\n🚨 异动提醒:")
    print(f"   股票: {anomaly_event.symbol} {anomaly_event.name}")
    print(f"   类型: {'🔺 上涨' if anomaly_event.anomaly_type == 'surge' else '🔻 下跌'}")
    print(f"   幅度: {abs(anomaly_event.change_percent):.2f}%")
    print(f"   价格: {anomaly_event.previous_price:.2f} → {anomaly_event.trigger_price:.2f}")
    print(f"   时间: {anomaly_event.detection_time.strftime('%H:%M:%S')}")
    
    if analysis_result:
        print(f"   建议: {analysis_result.investment_suggestion}")
        print(f"   风险: {analysis_result.risk_level}")
        print(f"   置信度: {analysis_result.confidence_score:.0%}")


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试异动监控服务")
    
    # 创建服务
    service = AnomalyMonitoringService(
        anomaly_threshold=0.1,
        monitor_interval=60,  # 1分钟用于测试
        analysis_enabled=True,
        notification_enabled=True
    )
    
    # 添加通知回调
    service.add_notification_callback(console_notification_callback)
    
    # 添加监控股票
    service.add_monitored_stock("000001")  # 平安银行
    service.add_monitored_stock("000002")  # 万科A
    
    # 启动服务
    if service.start_service():
        print("✅ 异动监控服务启动成功")
        
        try:
            # 运行5分钟
            time.sleep(300)
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断")
        finally:
            service.stop_service()
            print("⏹️ 异动监控服务已停止")
    else:
        print("❌ 异动监控服务启动失败") 