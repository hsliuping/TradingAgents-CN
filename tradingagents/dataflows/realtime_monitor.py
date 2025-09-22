#!/usr/bin/env python3
"""
股票实时监控模块
支持分时数据获取、异动检测和智能分析
"""

import os
import time
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
import pandas as pd

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('realtime_monitor')

# 导入数据源
from tradingagents.dataflows.tushare_adapter import TushareDataAdapter
from tradingagents.dataflows.akshare_utils import AKShareProvider
from tradingagents.dataflows.db_cache_manager import DatabaseCacheManager

# 导入Redis管理器
try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ Redis未安装，将使用内存缓存")


@dataclass
class StockRealTimeData:
    """实时股票数据结构"""
    symbol: str
    name: str
    current_price: float
    last_price: float  # 上一个监控周期的价格
    change_amount: float
    change_percent: float
    volume: int
    timestamp: datetime
    market_type: str = "A股"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockRealTimeData':
        """从字典创建对象"""
        data = data.copy()
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class StockMonitorConfig:
    """股票监控配置"""
    symbol: str
    anomaly_threshold: float = 0.1  # 异动阈值（百分比）
    monitor_interval: int = 300     # 监控间隔（秒）
    enable_realtime_push: bool = True  # 是否启用实时推送
    name: str = ""                  # 股票名称
    created_time: datetime = None
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['created_time'] = self.created_time.isoformat()
        data['last_updated'] = self.last_updated.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockMonitorConfig':
        """从字典创建对象"""
        data = data.copy()
        if isinstance(data.get('created_time'), str):
            data['created_time'] = datetime.fromisoformat(data['created_time'])
        if isinstance(data.get('last_updated'), str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


@dataclass
class AnomalyEvent:
    """异动事件数据结构"""
    symbol: str
    name: str
    anomaly_type: str  # 'surge' 上涨, 'drop' 下跌
    change_percent: float
    trigger_price: float
    previous_price: float
    detection_time: datetime
    volume: int
    analysis_pending: bool = True
    analysis_result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['detection_time'] = self.detection_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnomalyEvent':
        """从字典创建对象"""
        data = data.copy()
        if isinstance(data['detection_time'], str):
            data['detection_time'] = datetime.fromisoformat(data['detection_time'])
        return cls(**data)


class RealTimeMonitor:
    """实时股票监控器"""
    
    def __init__(self, 
                 anomaly_threshold: float = 0.1,  # 异动阈值 0.1%
                 monitor_interval: int = 300,     # 监控间隔 5分钟
                 redis_key_prefix: str = "stock_monitor"):
        """
        初始化实时监控器
        
        Args:
            anomaly_threshold: 异动检测阈值（百分比）
            monitor_interval: 监控间隔（秒）
            redis_key_prefix: Redis键前缀
        """
        self.anomaly_threshold = anomaly_threshold
        self.monitor_interval = monitor_interval
        self.redis_key_prefix = redis_key_prefix
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_thread = None
        self.monitored_stocks = set()
        
        # 股票配置管理
        self.stock_configs: Dict[str, StockMonitorConfig] = {}
        
        # 数据提供者
        self.tushare_adapter = None
        self.akshare_provider = None
        self.db_cache_manager = None
        self.redis_client = None
        
        # 回调函数
        self.anomaly_callbacks: List[Callable[[AnomalyEvent], None]] = []
        
        logger.info(f"📊 实时监控器初始化 - 异动阈值: {anomaly_threshold}%, 监控间隔: {monitor_interval}秒")
        
        # 初始化数据源和缓存
        self._init_data_sources()
        
        # 加载已保存的股票配置
        self.load_all_configs()
        self._init_redis()
    
    def _init_data_sources(self):
        """初始化数据源"""
        try:
            # 初始化Tushare适配器（用于历史数据）
            self.tushare_adapter = TushareDataAdapter(enable_cache=True)
            logger.info("✅ Tushare数据源初始化成功")
        except Exception as e:
            logger.error(f"❌ Tushare数据源初始化失败: {e}")
        
        try:
            # 初始化AKShare提供者（用于实时数据）
            self.akshare_provider = AKShareProvider()
            logger.info("✅ AKShare数据源初始化成功")
        except Exception as e:
            logger.error(f"❌ AKShare数据源初始化失败: {e}")
        
        try:
            # 初始化数据库缓存管理器
            self.db_cache_manager = DatabaseCacheManager()
            logger.info("✅ 数据库缓存管理器初始化成功")
        except Exception as e:
            logger.error(f"❌ 数据库缓存管理器初始化失败: {e}")
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis不可用，使用内存缓存")
            return
        
        try:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD")
            redis_db = int(os.getenv("REDIS_DB", "0"))
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_timeout=5
            )
            
            # 测试连接
            self.redis_client.ping()
            logger.info(f"✅ Redis连接成功: {redis_host}:{redis_port}")
            
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            self.redis_client = None
    
    def add_stock(self, symbol: str) -> bool:
        """
        添加要监控的股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 验证股票代码有效性
            if not self._validate_stock_symbol(symbol):
                logger.error(f"❌ 无效的股票代码: {symbol}")
                return False
            
            self.monitored_stocks.add(symbol)
            logger.info(f"📈 已添加监控股票: {symbol}")
            
            # 添加到历史股票列表并永久保存到Redis
            self._add_to_historical_stocks(symbol)
            
            # 初始化股票的历史价格数据
            self._init_stock_price_history(symbol)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加监控股票失败 {symbol}: {e}")
            return False
    
    def add_stock_with_config(self, symbol: str, config: StockMonitorConfig = None) -> bool:
        """
        添加股票到监控列表，并设置配置
        
        Args:
            symbol: 股票代码
            config: 监控配置，如果为None则使用默认配置
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 验证股票代码
            if not self._validate_stock_symbol(symbol):
                logger.error(f"❌ 无效的股票代码: {symbol}")
                return False
            
            # 创建默认配置
            if config is None:
                config = StockMonitorConfig(
                    symbol=symbol,
                    anomaly_threshold=self.anomaly_threshold,
                    monitor_interval=self.monitor_interval
                )
            
            # 保存配置
            self._save_stock_config(config)
            
            # 添加到监控列表
            self.monitored_stocks.add(symbol)
            self.stock_configs[symbol] = config
            
            logger.info(f"📈 已添加监控股票: {symbol} (阈值: {config.anomaly_threshold}%)")
            
            # 添加到历史股票列表并永久保存到Redis
            self._add_to_historical_stocks(symbol)
            
            # 初始化股票的历史价格数据
            self._init_stock_price_history(symbol)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加监控股票失败 {symbol}: {e}")
            return False
    
    def update_stock_config(self, symbol: str, config: StockMonitorConfig) -> bool:
        """
        更新股票监控配置
        
        Args:
            symbol: 股票代码
            config: 新的监控配置
            
        Returns:
            bool: 是否更新成功
        """
        try:
            if symbol not in self.stock_configs:
                logger.warning(f"⚠️ 股票 {symbol} 不在监控列表中")
                return False
            
            config.last_updated = datetime.now()
            self.stock_configs[symbol] = config
            self._save_stock_config(config)
            
            logger.info(f"✅ 已更新 {symbol} 监控配置")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新 {symbol} 配置失败: {e}")
            return False
    
    def get_stock_config(self, symbol: str) -> Optional[StockMonitorConfig]:
        """
        获取股票监控配置
        
        Args:
            symbol: 股票代码
            
        Returns:
            StockMonitorConfig: 配置对象，如果不存在返回None
        """
        return self.stock_configs.get(symbol)
    
    def get_all_stock_configs(self) -> Dict[str, StockMonitorConfig]:
        """
        获取所有股票监控配置
        
        Returns:
            Dict[str, StockMonitorConfig]: 所有股票配置
        """
        return self.stock_configs.copy()
    
    def _save_stock_config(self, config: StockMonitorConfig):
        """
        保存股票配置到Redis
        
        Args:
            config: 股票配置
        """
        try:
            if self.redis_client:
                config_key = f"{self.redis_key_prefix}:config:{config.symbol}"
                config_data = json.dumps(config.to_dict(), ensure_ascii=False)
                self.redis_client.set(config_key, config_data)
                logger.debug(f"💾 已保存 {config.symbol} 配置到Redis")
        except Exception as e:
            logger.error(f"❌ 保存 {config.symbol} 配置失败: {e}")
    
    def _load_stock_config(self, symbol: str) -> Optional[StockMonitorConfig]:
        """
        从Redis加载股票配置
        
        Args:
            symbol: 股票代码
            
        Returns:
            StockMonitorConfig: 配置对象，如果不存在返回None
        """
        try:
            if self.redis_client:
                config_key = f"{self.redis_key_prefix}:config:{symbol}"
                config_data = self.redis_client.get(config_key)
                if config_data:
                    if isinstance(config_data, bytes):
                        config_data = config_data.decode('utf-8')
                    config_dict = json.loads(config_data)
                    return StockMonitorConfig.from_dict(config_dict)
        except Exception as e:
            logger.error(f"❌ 加载 {symbol} 配置失败: {e}")
        return None
    
    def load_all_configs(self):
        """从Redis加载所有股票配置"""
        try:
            if not self.redis_client:
                return
            
            # 获取所有配置键
            pattern = f"{self.redis_key_prefix}:config:*"
            config_keys = self.redis_client.keys(pattern)
            
            for key in config_keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                
                # 提取股票代码
                symbol = key.split(':')[-1]
                config = self._load_stock_config(symbol)
                if config:
                    self.stock_configs[symbol] = config
                    self.monitored_stocks.add(symbol)
            
            logger.info(f"📋 已加载 {len(self.stock_configs)} 个股票配置")
            
        except Exception as e:
            logger.error(f"❌ 加载股票配置失败: {e}")
    
    def _delete_stock_config(self, symbol: str):
        """
        从Redis删除股票配置
        
        Args:
            symbol: 股票代码
        """
        try:
            if self.redis_client:
                config_key = f"{self.redis_key_prefix}:config:{symbol}"
                deleted_count = self.redis_client.delete(config_key)
                if deleted_count > 0:
                    logger.debug(f"🗑️ 已从Redis删除 {symbol} 配置")
                else:
                    logger.debug(f"⚠️ Redis中未找到 {symbol} 配置")
        except Exception as e:
            logger.error(f"❌ 删除 {symbol} 配置失败: {e}")
    
    def add_stocks_batch(self, symbols: List[str]) -> Dict[str, bool]:
        """
        批量添加股票到监控列表
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            Dict[str, bool]: 每个股票的添加结果
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.add_stock(symbol)
        
        success_count = sum(results.values())
        logger.info(f"📊 批量添加股票结果: {success_count}/{len(symbols)} 成功")
        return results
    
    def remove_stock(self, symbol: str) -> bool:
        """
        移除监控的股票
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否移除成功
        """
        try:
            if symbol in self.monitored_stocks:
                self.monitored_stocks.remove(symbol)
                
                # 从股票配置中移除
                if symbol in self.stock_configs:
                    del self.stock_configs[symbol]
                
                # 从Redis中删除配置数据
                self._delete_stock_config(symbol)
                
                logger.info(f"📉 已移除监控股票: {symbol}")
                return True
            else:
                logger.warning(f"⚠️ 股票 {symbol} 不在监控列表中")
                return False
                
        except Exception as e:
            logger.error(f"❌ 移除监控股票失败 {symbol}: {e}")
            return False
    
    def add_anomaly_callback(self, callback: Callable[[AnomalyEvent], None]):
        """
        添加异动事件回调函数
        
        Args:
            callback: 回调函数，接收AnomalyEvent参数
        """
        self.anomaly_callbacks.append(callback)
        logger.info(f"📞 已添加异动回调函数: {callback.__name__}")
    
    def start_monitoring(self):
        """开始监控"""
        if self.is_monitoring:
            logger.warning("⚠️ 监控已在运行中")
            return
        
        if not self.monitored_stocks:
            logger.warning("⚠️ 没有要监控的股票")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"🚀 开始监控 {len(self.monitored_stocks)} 只股票")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            logger.warning("⚠️ 监控未在运行")
            return
        
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        logger.info("⏹️ 监控已停止")
    
    def _monitoring_loop(self):
        """监控主循环"""
        logger.info("🔄 监控循环开始")
        
        while self.is_monitoring:
            try:
                start_time = time.time()
                
                # 检查所有监控的股票
                for symbol in list(self.monitored_stocks):
                    try:
                        self._check_stock_anomaly(symbol)
                    except Exception as e:
                        logger.error(f"❌ 检查股票 {symbol} 异动失败: {e}")
                
                # 计算执行时间
                execution_time = time.time() - start_time
                logger.debug(f"⏱️ 本轮监控耗时: {execution_time:.2f}秒")
                
                # 等待下一个监控周期
                sleep_time = max(0, self.monitor_interval - execution_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"❌ 监控循环异常: {e}")
                time.sleep(10)  # 异常时等待10秒再继续
        
        logger.info("🔄 监控循环结束")
    
    def _check_stock_anomaly(self, symbol: str):
        """
        检查单只股票的异动情况
        
        Args:
            symbol: 股票代码
        """
        logger.debug(f"🔍 检查股票异动: {symbol}")
        
        # 获取当前实时数据
        current_data = self._get_realtime_data(symbol)
        if not current_data:
            logger.warning(f"⚠️ 无法获取 {symbol} 实时数据")
            return
        
        # 获取上一次的价格数据
        previous_price = self._get_previous_price(symbol)
        if previous_price is None:
            logger.info(f"📊 {symbol} 首次获取价格数据，存储基准价格")
            self._store_current_price(symbol, current_data.current_price)
            return
        
        # 计算涨跌幅
        change_percent = abs((current_data.current_price - previous_price) / previous_price * 100)
        
        logger.debug(f"📈 {symbol} 价格变化: {previous_price:.2f} -> {current_data.current_price:.2f} ({change_percent:.3f}%)")
        
        # 获取个股配置的异动阈值
        stock_config = self.stock_configs.get(symbol)
        threshold = stock_config.anomaly_threshold if stock_config else self.anomaly_threshold
        
        # 检查是否触发异动阈值
        if change_percent >= threshold:
            anomaly_type = 'surge' if current_data.current_price > previous_price else 'drop'
            
            # 创建异动事件
            anomaly_event = AnomalyEvent(
                symbol=symbol,
                name=current_data.name,
                anomaly_type=anomaly_type,
                change_percent=change_percent if anomaly_type == 'surge' else -change_percent,
                trigger_price=current_data.current_price,
                previous_price=previous_price,
                detection_time=datetime.now(),
                volume=current_data.volume
            )
            
            logger.warning(f"🚨 检测到异动 {symbol}: {anomaly_type} {change_percent:.3f}%")
            
            # 存储异动事件
            self._store_anomaly_event(anomaly_event)
            
            # 触发回调函数
            self._trigger_anomaly_callbacks(anomaly_event)
        
        # 更新价格历史
        self._store_current_price(symbol, current_data.current_price)
    
    def _get_realtime_data(self, symbol: str) -> Optional[StockRealTimeData]:
        """
        获取股票实时数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            StockRealTimeData: 实时数据，获取失败时返回None
        """
        try:
            # 优先使用AKShare获取实时数据
            if self.akshare_provider:
                data = self.akshare_provider.get_realtime_quote(symbol)
                if data is not None and not data.empty:
                    row = data.iloc[0]
                    return StockRealTimeData(
                        symbol=symbol,
                        name=str(row.get('name', symbol)),
                        current_price=float(row.get('price', 0)),
                        last_price=0,  # 将在调用方设置
                        change_amount=float(row.get('change', 0)),
                        change_percent=float(row.get('pct_chg', 0)),
                        volume=int(row.get('volume', 0)),
                        timestamp=datetime.now(),
                        market_type="A股"
                    )
            
            # 备用方案：使用Tushare最新数据
            if self.tushare_adapter:
                data = self.tushare_adapter.get_stock_data(symbol, data_type="realtime")
                if data is not None and not data.empty:
                    row = data.iloc[0]
                    return StockRealTimeData(
                        symbol=symbol,
                        name=str(row.get('name', symbol)),
                        current_price=float(row.get('close', 0)),
                        last_price=0,
                        change_amount=float(row.get('change', 0)),
                        change_percent=float(row.get('pct_chg', 0)),
                        volume=int(row.get('vol', 0)),
                        timestamp=datetime.now(),
                        market_type="A股"
                    )
            
            logger.warning(f"⚠️ 无法获取 {symbol} 实时数据")
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 实时数据失败: {e}")
            return None
    
    def _get_previous_price(self, symbol: str) -> Optional[float]:
        """
        获取股票的上一次价格
        
        Args:
            symbol: 股票代码
            
        Returns:
            float: 上一次价格，没有历史数据时返回None
        """
        key = f"{self.redis_key_prefix}:price:{symbol}"
        
        try:
            if self.redis_client:
                price_str = self.redis_client.get(key)
                if price_str:
                    return float(price_str)
            
            # Redis不可用时的内存缓存备用方案
            # 这里可以扩展使用MongoDB或本地文件存储
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 历史价格失败: {e}")
            return None
    
    def _store_current_price(self, symbol: str, price: float):
        """
        存储当前价格到Redis
        
        Args:
            symbol: 股票代码
            price: 当前价格
        """
        key = f"{self.redis_key_prefix}:price:{symbol}"
        
        try:
            if self.redis_client:
                # 存储价格，设置过期时间为1小时
                self.redis_client.setex(key, 3600, str(price))
                logger.debug(f"💾 已存储 {symbol} 价格: {price}")
            
        except Exception as e:
            logger.error(f"❌ 存储 {symbol} 价格失败: {e}")
    
    def _store_anomaly_event(self, event: AnomalyEvent):
        """
        存储异动事件
        
        Args:
            event: 异动事件
        """
        try:
            # 存储到Redis列表
            if self.redis_client:
                key = f"{self.redis_key_prefix}:anomalies:{event.symbol}"
                event_json = json.dumps(event.to_dict(), ensure_ascii=False)
                
                # 添加到列表头部
                self.redis_client.lpush(key, event_json)
                
                # 保留最新1000条记录（增加存储量）
                self.redis_client.ltrim(key, 0, 999)
                
                # 设置为永久不过期（移除expire调用）
                # 异动数据作为重要历史数据，需要永久保存
                
                logger.info(f"💾 已存储异动事件: {event.symbol} {event.anomaly_type}")
            
            # 可以扩展存储到MongoDB进行长期保存
            
        except Exception as e:
            logger.error(f"❌ 存储异动事件失败: {e}")
    
    def _trigger_anomaly_callbacks(self, event: AnomalyEvent):
        """
        触发异动事件回调函数
        
        Args:
            event: 异动事件
        """
        for callback in self.anomaly_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"❌ 异动回调函数执行失败 {callback.__name__}: {e}")
    
    def _validate_stock_symbol(self, symbol: str) -> bool:
        """
        验证股票代码有效性（支持A股和美股）
        
        Args:
            symbol: 股票代码
            
        Returns:
            bool: 是否有效
        """
        if not symbol:
            return False
        
        symbol = symbol.upper().strip()
        
        # A股代码验证：6位数字
        if len(symbol) == 6 and symbol.isdigit():
            # 基本的A股代码格式验证
            # 包括主板、中小板、创业板、科创板、新股等
            if symbol.startswith(('000', '001', '002', '003', '300', '600', '601', '603', '688', '920', '421', '430')):
                logger.debug(f"✅ A股代码格式验证通过: {symbol}")
                return True
        
        # 美股代码验证：1-5位字母，可包含数字和点号
        elif 1 <= len(symbol) <= 5 and symbol.replace('.', '').isalnum():
            # 美股代码通常是字母组合，可能包含数字
            # 例如: AAPL, GOOGL, MSFT, BRK.A, BRK.B 等
            if any(c.isalpha() for c in symbol):
                logger.debug(f"✅ 美股代码格式验证通过: {symbol}")
                return True
        
        # 港股代码验证：4-5位数字（如 0700.HK）
        elif len(symbol) >= 4 and (symbol.isdigit() or symbol.endswith('.HK')):
            if symbol.endswith('.HK'):
                base_code = symbol[:-3]
                if base_code.isdigit() and len(base_code) <= 5:
                    logger.debug(f"✅ 港股代码格式验证通过: {symbol}")
                    return True
            elif symbol.isdigit() and len(symbol) <= 5:
                logger.debug(f"✅ 港股代码格式验证通过: {symbol}")
                return True
        
        # 如果格式验证未通过，尝试通过数据源验证
        # 这样可以支持一些特殊的股票代码
        try:
            logger.debug(f"🔍 通过数据源验证股票代码: {symbol}")
            test_data = self._get_realtime_data(symbol)
            if test_data is not None:
                logger.info(f"✅ 通过数据验证确认 {symbol} 有效")
                return True
            else:
                logger.warning(f"⚠️ 数据源无法获取 {symbol} 数据")
                return False
        except Exception as e:
            logger.warning(f"⚠️ 验证股票代码 {symbol} 时出错: {e}")
            return False
    
    def _add_to_historical_stocks(self, symbol: str):
        """
        添加股票到历史监控列表并永久保存到Redis
        
        Args:
            symbol: 股票代码
        """
        try:
            if self.redis_client:
                # 使用Redis Set存储历史股票列表
                historical_key = f"{self.redis_key_prefix}:historical_stocks"
                self.redis_client.sadd(historical_key, symbol)
                
                # 存储股票信息（包括添加时间）
                info_key = f"{self.redis_key_prefix}:stock_info:{symbol}"
                stock_info = {
                    "symbol": symbol,
                    "added_time": datetime.now().isoformat(),
                    "total_anomalies": 0,
                    "last_monitored": datetime.now().isoformat()
                }
                self.redis_client.hset(info_key, mapping=stock_info)
                
                logger.info(f"📋 已添加 {symbol} 到历史股票列表")
                
        except Exception as e:
            logger.error(f"❌ 添加 {symbol} 到历史列表失败: {e}")
    
    def get_historical_stocks(self) -> List[Dict[str, Any]]:
        """
        获取历史监控过的所有股票列表
        
        Returns:
            List[Dict]: 股票信息列表
        """
        try:
            if not self.redis_client:
                return []
            
            historical_key = f"{self.redis_key_prefix}:historical_stocks"
            symbols = self.redis_client.smembers(historical_key)
            
            stocks_info = []
            for symbol in symbols:
                if isinstance(symbol, bytes):
                    symbol = symbol.decode('utf-8')
                
                info_key = f"{self.redis_key_prefix}:stock_info:{symbol}"
                stock_info = self.redis_client.hgetall(info_key)
                
                if stock_info:
                    # 转换字节为字符串
                    decoded_info = {}
                    for k, v in stock_info.items():
                        if isinstance(k, bytes):
                            k = k.decode('utf-8')
                        if isinstance(v, bytes):
                            v = v.decode('utf-8')
                        decoded_info[k] = v
                    
                    # 获取异动次数
                    anomaly_key = f"{self.redis_key_prefix}:anomalies:{symbol}"
                    anomaly_count = self.redis_client.llen(anomaly_key)
                    decoded_info["total_anomalies"] = anomaly_count
                    
                    stocks_info.append(decoded_info)
            
            # 按添加时间排序
            stocks_info.sort(key=lambda x: x.get('added_time', ''), reverse=True)
            return stocks_info
            
        except Exception as e:
            logger.error(f"❌ 获取历史股票列表失败: {e}")
            return []
    
    def _init_stock_price_history(self, symbol: str):
        """
        初始化股票价格历史数据
        
        Args:
            symbol: 股票代码
        """
        try:
            # 获取最新价格作为基准
            current_data = self._get_realtime_data(symbol)
            if current_data:
                self._store_current_price(symbol, current_data.current_price)
                logger.info(f"📊 初始化 {symbol} 基准价格: {current_data.current_price}")
            
        except Exception as e:
            logger.error(f"❌ 初始化 {symbol} 价格历史失败: {e}")
    
    def get_anomaly_history(self, symbol: str, limit: int = 10) -> List[AnomalyEvent]:
        """
        获取股票的异动历史
        
        Args:
            symbol: 股票代码
            limit: 返回记录数限制
            
        Returns:
            List[AnomalyEvent]: 异动事件列表
        """
        try:
            if not self.redis_client:
                return []
            
            key = f"{self.redis_key_prefix}:anomalies:{symbol}"
            events_json = self.redis_client.lrange(key, 0, limit - 1)
            
            events = []
            for event_json in events_json:
                try:
                    event_data = json.loads(event_json)
                    events.append(AnomalyEvent.from_dict(event_data))
                except Exception as e:
                    logger.error(f"❌ 解析异动事件失败: {e}")
            
            return events
            
        except Exception as e:
            logger.error(f"❌ 获取 {symbol} 异动历史失败: {e}")
            return []
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """
        获取监控状态信息
        
        Returns:
            Dict: 监控状态信息
        """
        return {
            "is_monitoring": self.is_monitoring,
            "monitored_stocks": list(self.monitored_stocks),
            "anomaly_threshold": self.anomaly_threshold,
            "monitor_interval": self.monitor_interval,
            "data_sources": {
                "tushare": self.tushare_adapter is not None,
                "akshare": self.akshare_provider is not None,
                "redis": self.redis_client is not None,
                "database": self.db_cache_manager is not None
            }
        }


# 全局监控器实例
_global_monitor = None

def get_global_monitor() -> RealTimeMonitor:
    """获取全局监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = RealTimeMonitor()
    return _global_monitor


if __name__ == "__main__":
    # 测试代码
    monitor = RealTimeMonitor(anomaly_threshold=0.1, monitor_interval=60)
    
    def on_anomaly(event: AnomalyEvent):
        print(f"异动提醒: {event.symbol} {event.name} {event.anomaly_type} {event.change_percent:.2f}%")
    
    monitor.add_anomaly_callback(on_anomaly)
    monitor.add_stock("000001")  # 平安银行
    monitor.add_stock("000002")  # 万科A
    
    print("开始监控...")
    monitor.start_monitoring()
    
    try:
        time.sleep(300)  # 运行5分钟
    except KeyboardInterrupt:
        print("停止监控...")
    finally:
        monitor.stop_monitoring() 