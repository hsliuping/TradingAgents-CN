#!/usr/bin/env python3
"""
数据源管理器
统一管理中国股票数据源的选择和切换，支持Tushare、AKShare、BaoStock等
"""

import os
from typing import Dict, List, Optional, Any
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


class ChinaDataSource(Enum):
    """中国股票数据源枚举"""
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    TDX = "tdx"  # 中国股票数据，将被逐步淘汰


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        """初始化数据源管理器"""
        self.default_source = self._get_default_source()
        self.available_sources = self._check_available_sources()
        self.current_source = self.default_source
        
        print(f"📊 数据源管理器初始化完成")
        print(f"   默认数据源: {self.default_source.value}")
        print(f"   可用数据源: {[s.value for s in self.available_sources]}")
    
    def _get_default_source(self) -> ChinaDataSource:
        """获取默认数据源"""
        # 从环境变量获取
        env_source = os.getenv('DEFAULT_CHINA_DATA_SOURCE', 'tushare').lower()
        
        # 映射到枚举
        source_mapping = {
            'tushare': ChinaDataSource.TUSHARE,
            'akshare': ChinaDataSource.AKSHARE,
            'baostock': ChinaDataSource.BAOSTOCK,
            'tdx': ChinaDataSource.TDX
        }
        
        return source_mapping.get(env_source, ChinaDataSource.TUSHARE)
    
    def _check_available_sources(self) -> List[ChinaDataSource]:
        """检查可用的数据源"""
        available = []
        
        # 检查Tushare
        try:
            import tushare as ts
            token = os.getenv('TUSHARE_TOKEN')
            if token:
                available.append(ChinaDataSource.TUSHARE)
                print("✅ Tushare数据源可用")
            else:
                print("⚠️ Tushare数据源不可用: 未设置TUSHARE_TOKEN")
        except ImportError:
            print("⚠️ Tushare数据源不可用: 库未安装")
        
        # 检查AKShare
        try:
            import akshare as ak
            available.append(ChinaDataSource.AKSHARE)
            print("✅ AKShare数据源可用")
        except ImportError:
            print("⚠️ AKShare数据源不可用: 库未安装")
        
        # 检查BaoStock
        try:
            import baostock as bs
            available.append(ChinaDataSource.BAOSTOCK)
            print("✅ BaoStock数据源可用")
        except ImportError:
            print("⚠️ BaoStock数据源不可用: 库未安装")
        
        # 检查TDX (通达信)
        try:
            import pytdx
            available.append(ChinaDataSource.TDX)
            print("⚠️ TDX数据源可用 (将被淘汰)")
        except ImportError:
            print("ℹ️ TDX数据源不可用: 库未安装")
        
        return available
    
    def get_current_source(self) -> ChinaDataSource:
        """获取当前数据源"""
        return self.current_source
    
    def set_current_source(self, source: ChinaDataSource) -> bool:
        """设置当前数据源"""
        if source in self.available_sources:
            self.current_source = source
            print(f"✅ 数据源已切换到: {source.value}")
            return True
        else:
            print(f"❌ 数据源不可用: {source.value}")
            return False
    
    def get_data_adapter(self):
        """获取当前数据源的适配器"""
        if self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_adapter()
        elif self.current_source == ChinaDataSource.AKSHARE:
            return self._get_akshare_adapter()
        elif self.current_source == ChinaDataSource.BAOSTOCK:
            return self._get_baostock_adapter()
        elif self.current_source == ChinaDataSource.TDX:
            return self._get_tdx_adapter()
        else:
            raise ValueError(f"不支持的数据源: {self.current_source}")
    
    def _get_tushare_adapter(self):
        """获取Tushare适配器"""
        try:
            from .tushare_adapter import get_tushare_adapter
            return get_tushare_adapter()
        except ImportError as e:
            print(f"❌ Tushare适配器导入失败: {e}")
            return None
    
    def _get_akshare_adapter(self):
        """获取AKShare适配器"""
        try:
            from .akshare_utils import get_akshare_provider
            return get_akshare_provider()
        except ImportError as e:
            print(f"❌ AKShare适配器导入失败: {e}")
            return None
    
    def _get_baostock_adapter(self):
        """获取BaoStock适配器"""
        try:
            from .baostock_utils import get_baostock_provider
            return get_baostock_provider()
        except ImportError as e:
            print(f"❌ BaoStock适配器导入失败: {e}")
            return None
    
    def _get_tdx_adapter(self):
        """获取TDX适配器 (已弃用)"""
        print("⚠️ 警告: TDX数据源已弃用，建议使用Tushare")
        try:
            from .tdx_utils import get_tdx_provider
            return get_tdx_provider()
        except ImportError as e:
            print(f"❌ TDX适配器导入失败: {e}")
            return None
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> str:
        """
        获取股票数据的统一接口
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            str: 格式化的股票数据
        """
        print(f"📊 使用{self.current_source.value}数据源获取{symbol}数据")
        
        try:
            if self.current_source == ChinaDataSource.TUSHARE:
                return self._get_tushare_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.AKSHARE:
                return self._get_akshare_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.BAOSTOCK:
                return self._get_baostock_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.TDX:
                return self._get_tdx_data(symbol, start_date, end_date)
            else:
                return f"❌ 不支持的数据源: {self.current_source.value}"
                
        except Exception as e:
            print(f"❌ {self.current_source.value}数据获取失败: {e}")
            return self._try_fallback_sources(symbol, start_date, end_date)
    
    def _get_tushare_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用Tushare获取数据"""
        from .interface import get_china_stock_data_tushare
        return get_china_stock_data_tushare(symbol, start_date, end_date)
    
    def _get_akshare_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用AKShare获取数据"""
        # 这里需要实现AKShare的统一接口
        from .akshare_utils import get_akshare_provider
        provider = get_akshare_provider()
        data = provider.get_stock_data(symbol, start_date, end_date)
        
        if data is not None and not data.empty:
            result = f"股票代码: {symbol}\n"
            result += f"数据期间: {start_date} 至 {end_date}\n"
            result += f"数据条数: {len(data)}条\n\n"
            result += "最新数据:\n"
            result += data.tail(5).to_string(index=False)
            return result
        else:
            return f"❌ 未能获取{symbol}的股票数据"
    
    def _get_baostock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用BaoStock获取数据"""
        # 这里需要实现BaoStock的统一接口
        from .baostock_utils import get_baostock_provider
        provider = get_baostock_provider()
        data = provider.get_stock_data(symbol, start_date, end_date)
        
        if data is not None and not data.empty:
            result = f"股票代码: {symbol}\n"
            result += f"数据期间: {start_date} 至 {end_date}\n"
            result += f"数据条数: {len(data)}条\n\n"
            result += "最新数据:\n"
            result += data.tail(5).to_string(index=False)
            return result
        else:
            return f"❌ 未能获取{symbol}的股票数据"
    
    def _get_tdx_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用TDX获取数据 (已弃用)"""
        print("⚠️ 警告: 正在使用已弃用的TDX数据源")
        from .tdx_utils import get_china_stock_data
        return get_china_stock_data(symbol, start_date, end_date)
    
    def _try_fallback_sources(self, symbol: str, start_date: str, end_date: str) -> str:
        """尝试备用数据源"""
        print(f"🔄 {self.current_source.value}失败，尝试备用数据源...")
        
        # 备用数据源优先级: Tushare > AKShare > BaoStock > TDX
        fallback_order = [
            ChinaDataSource.TUSHARE,
            ChinaDataSource.AKSHARE,
            ChinaDataSource.BAOSTOCK,
            ChinaDataSource.TDX
        ]
        
        for source in fallback_order:
            if source != self.current_source and source in self.available_sources:
                try:
                    print(f"🔄 尝试备用数据源: {source.value}")
                    original_source = self.current_source
                    self.current_source = source
                    
                    result = self.get_stock_data(symbol, start_date, end_date)
                    
                    # 恢复原数据源
                    self.current_source = original_source
                    
                    if "❌" not in result:
                        print(f"✅ 备用数据源{source.value}获取成功")
                        return result
                        
                except Exception as e:
                    print(f"❌ 备用数据源{source.value}也失败: {e}")
                    continue
        
        return f"❌ 所有数据源都无法获取{symbol}的数据"
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息"""
        try:
            if self.current_source == ChinaDataSource.TUSHARE:
                from .interface import get_china_stock_info_tushare
                info_str = get_china_stock_info_tushare(symbol)
                # 解析字符串返回为字典格式
                return self._parse_stock_info_string(info_str, symbol)
            else:
                adapter = self.get_data_adapter()
                if adapter and hasattr(adapter, 'get_stock_info'):
                    return adapter.get_stock_info(symbol)
                else:
                    return {'symbol': symbol, 'name': f'股票{symbol}', 'source': self.current_source.value}
                    
        except Exception as e:
            print(f"❌ 获取股票信息失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'unknown', 'error': str(e)}
    
    def _parse_stock_info_string(self, info_str: str, symbol: str) -> Dict:
        """解析股票信息字符串为字典"""
        try:
            info = {'symbol': symbol, 'source': self.current_source.value}
            lines = info_str.split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if '股票名称' in key:
                        info['name'] = value
                    elif '所属行业' in key:
                        info['industry'] = value
                    elif '所属地区' in key:
                        info['area'] = value
                    elif '上市市场' in key:
                        info['market'] = value
                    elif '上市日期' in key:
                        info['list_date'] = value
            
            return info
            
        except Exception as e:
            print(f"⚠️ 解析股票信息失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': self.current_source.value}


# 全局数据源管理器实例
_data_source_manager = None

def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _data_source_manager
    if _data_source_manager is None:
        _data_source_manager = DataSourceManager()
    return _data_source_manager


def get_china_stock_data_unified(symbol: str, start_date: str, end_date: str) -> str:
    """
    统一的中国股票数据获取接口
    自动使用配置的数据源，支持备用数据源
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        str: 格式化的股票数据
    """
    manager = get_data_source_manager()
    return manager.get_stock_data(symbol, start_date, end_date)


def get_china_stock_info_unified(symbol: str) -> Dict:
    """
    统一的中国股票信息获取接口
    
    Args:
        symbol: 股票代码
        
    Returns:
        Dict: 股票基本信息
    """
    manager = get_data_source_manager()
    return manager.get_stock_info(symbol)
