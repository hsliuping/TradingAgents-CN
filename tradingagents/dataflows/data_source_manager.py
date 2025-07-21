#!/usr/bin/env python3
"""
数据源管理器
统一管理中国股票数据源的选择和切换，支持Tushare、AKShare、BaoStock等
"""

import os
import time
from typing import Dict, List, Optional, Any
from enum import Enum
import warnings

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')
warnings.filterwarnings('ignore')

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_dataflow_logging
logger = setup_dataflow_logging()


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
        
        logger.info(f"📊 数据源管理器初始化完成")
        logger.info(f"   默认数据源: {self.default_source.value}")
        logger.info(f"   可用数据源: {[s.value for s in self.available_sources]}")
    
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
                logger.info("✅ Tushare数据源可用")
            else:
                logger.warning("⚠️ Tushare数据源不可用: 未设置TUSHARE_TOKEN")
        except ImportError:
            logger.warning("⚠️ Tushare数据源不可用: 库未安装")
        
        # 检查AKShare
        try:
            import akshare as ak
            available.append(ChinaDataSource.AKSHARE)
            logger.info("✅ AKShare数据源可用")
        except ImportError:
            logger.warning("⚠️ AKShare数据源不可用: 库未安装")
        
        # 检查BaoStock
        try:
            import baostock as bs
            available.append(ChinaDataSource.BAOSTOCK)
            logger.info(f"✅ BaoStock数据源可用")
        except ImportError:
            logger.warning(f"⚠️ BaoStock数据源不可用: 库未安装")
        
        # 检查TDX (通达信)
        try:
            import pytdx
            available.append(ChinaDataSource.TDX)
            logger.warning(f"⚠️ TDX数据源可用 (将被淘汰)")
        except ImportError:
            logger.info(f"ℹ️ TDX数据源不可用: 库未安装")
        
        return available
    
    def get_current_source(self) -> ChinaDataSource:
        """获取当前数据源"""
        return self.current_source
    
    def set_current_source(self, source: ChinaDataSource) -> bool:
        """设置当前数据源"""
        if source in self.available_sources:
            self.current_source = source
            logger.info(f"✅ 数据源已切换到: {source.value}")
            return True
        else:
            logger.error(f"❌ 数据源不可用: {source.value}")
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
            logger.error(f"❌ Tushare适配器导入失败: {e}")
            return None
    
    def _get_akshare_adapter(self):
        """获取AKShare适配器"""
        try:
            from .akshare_utils import get_akshare_provider
            return get_akshare_provider()
        except ImportError as e:
            logger.error(f"❌ AKShare适配器导入失败: {e}")
            return None
    
    def _get_baostock_adapter(self):
        """获取BaoStock适配器"""
        try:
            from .baostock_utils import get_baostock_provider
            return get_baostock_provider()
        except ImportError as e:
            logger.error(f"❌ BaoStock适配器导入失败: {e}")
            return None
    
    def _get_tdx_adapter(self):
        """获取TDX适配器 (已弃用)"""
        logger.warning(f"⚠️ 警告: TDX数据源已弃用，建议使用Tushare")
        try:
            from .tdx_utils import get_tdx_provider
            return get_tdx_provider()
        except ImportError as e:
            logger.error(f"❌ TDX适配器导入失败: {e}")
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
        # 记录详细的输入参数
        logger.info(f"📊 [数据获取] 开始获取股票数据",
                   extra={
                       'symbol': symbol,
                       'start_date': start_date,
                       'end_date': end_date,
                       'data_source': self.current_source.value,
                       'event_type': 'data_fetch_start'
                   })

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] DataSourceManager.get_stock_data 接收到的股票代码: '{symbol}' (类型: {type(symbol)})")
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 当前数据源: {self.current_source.value}")

        start_time = time.time()

        try:
            # 根据数据源调用相应的获取方法
            if self.current_source == ChinaDataSource.TUSHARE:
                logger.info(f"🔍 [股票代码追踪] 调用 Tushare 数据源，传入参数: symbol='{symbol}'")
                result = self._get_tushare_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.AKSHARE:
                result = self._get_akshare_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.BAOSTOCK:
                result = self._get_baostock_data(symbol, start_date, end_date)
            elif self.current_source == ChinaDataSource.TDX:
                result = self._get_tdx_data(symbol, start_date, end_date)
            else:
                result = f"❌ 不支持的数据源: {self.current_source.value}"

            # 记录详细的输出结果
            duration = time.time() - start_time
            result_length = len(result) if result else 0
            is_success = result and "❌" not in result and "错误" not in result

            if is_success:
                logger.info(f"✅ [数据获取] 成功获取股票数据",
                           extra={
                               'symbol': symbol,
                               'start_date': start_date,
                               'end_date': end_date,
                               'data_source': self.current_source.value,
                               'duration': duration,
                               'result_length': result_length,
                               'result_preview': result[:200] + '...' if result_length > 200 else result,
                               'event_type': 'data_fetch_success'
                           })
                return result
            else:
                logger.warning(f"⚠️ [数据获取] 数据质量异常，尝试降级到其他数据源",
                              extra={
                                  'symbol': symbol,
                                  'start_date': start_date,
                                  'end_date': end_date,
                                  'data_source': self.current_source.value,
                                  'duration': duration,
                                  'result_length': result_length,
                                  'result_preview': result[:200] + '...' if result_length > 200 else result,
                                  'event_type': 'data_fetch_warning'
                              })

                # 数据质量异常时也尝试降级到其他数据源
                fallback_result = self._try_fallback_sources(symbol, start_date, end_date)
                if fallback_result and "❌" not in fallback_result and "错误" not in fallback_result:
                    logger.info(f"✅ [数据获取] 降级成功获取数据")
                    return fallback_result
                else:
                    logger.error(f"❌ [数据获取] 所有数据源都无法获取有效数据")
                    return result  # 返回原始结果（包含错误信息）

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [数据获取] 异常失败: {e}",
                        extra={
                            'symbol': symbol,
                            'start_date': start_date,
                            'end_date': end_date,
                            'data_source': self.current_source.value,
                            'duration': duration,
                            'error': str(e),
                            'event_type': 'data_fetch_exception'
                        }, exc_info=True)
            return self._try_fallback_sources(symbol, start_date, end_date)
    
    def _get_tushare_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用Tushare获取数据"""
        logger.debug(f"📊 [Tushare] 调用参数: symbol={symbol}, start_date={start_date}, end_date={end_date}")

        # 添加详细的股票代码追踪日志
        logger.info(f"🔍 [股票代码追踪] _get_tushare_data 接收到的股票代码: '{symbol}' (类型: {type(symbol)})")
        logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
        logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")
        logger.info(f"🔍 [DataSourceManager详细日志] _get_tushare_data 开始执行")
        logger.info(f"🔍 [DataSourceManager详细日志] 当前数据源: {self.current_source.value}")

        start_time = time.time()
        try:
            from .interface import get_china_stock_data_tushare
            logger.info(f"🔍 [股票代码追踪] 调用 get_china_stock_data_tushare，传入参数: symbol='{symbol}'")
            logger.info(f"🔍 [DataSourceManager详细日志] 开始调用interface.get_china_stock_data_tushare...")

            result = get_china_stock_data_tushare(symbol, start_date, end_date)

            duration = time.time() - start_time
            logger.info(f"🔍 [DataSourceManager详细日志] interface调用完成，耗时: {duration:.3f}秒")
            logger.info(f"🔍 [股票代码追踪] get_china_stock_data_tushare 返回结果前200字符: {result[:200] if result else 'None'}")
            logger.info(f"🔍 [DataSourceManager详细日志] 返回结果类型: {type(result)}")
            logger.info(f"🔍 [DataSourceManager详细日志] 返回结果长度: {len(result) if result else 0}")

            logger.debug(f"📊 [Tushare] 调用完成: 耗时={duration:.2f}s, 结果长度={len(result) if result else 0}")

            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [Tushare] 调用失败: {e}, 耗时={duration:.2f}s", exc_info=True)
            logger.error(f"❌ [DataSourceManager详细日志] 异常类型: {type(e).__name__}")
            logger.error(f"❌ [DataSourceManager详细日志] 异常信息: {str(e)}")
            import traceback
            logger.error(f"❌ [DataSourceManager详细日志] 异常堆栈: {traceback.format_exc()}")
            raise
    
    def _get_akshare_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """使用AKShare获取数据"""
        logger.debug(f"📊 [AKShare] 调用参数: symbol={symbol}, start_date={start_date}, end_date={end_date}")

        start_time = time.time()
        try:
            # 这里需要实现AKShare的统一接口
            from .akshare_utils import get_akshare_provider
            provider = get_akshare_provider()
            data = provider.get_stock_data(symbol, start_date, end_date)

            duration = time.time() - start_time

            if data is not None and not data.empty:
                result = f"股票代码: {symbol}\n"
                result += f"数据期间: {start_date} 至 {end_date}\n"
                result += f"数据条数: {len(data)}条\n\n"
                result += "最新数据:\n"
                result += data.tail(5).to_string(index=False)

                logger.debug(f"📊 [AKShare] 调用成功: 耗时={duration:.2f}s, 数据条数={len(data)}, 结果长度={len(result)}")
                return result
            else:
                result = f"❌ 未能获取{symbol}的股票数据"
                logger.warning(f"⚠️ [AKShare] 数据为空: 耗时={duration:.2f}s")
                return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ [AKShare] 调用失败: {e}, 耗时={duration:.2f}s", exc_info=True)
            return f"❌ AKShare获取{symbol}数据失败: {e}"
    
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
        logger.warning(f"⚠️ 警告: 正在使用已弃用的TDX数据源")
        from .tdx_utils import get_china_stock_data
        return get_china_stock_data(symbol, start_date, end_date)
    
    def _try_fallback_sources(self, symbol: str, start_date: str, end_date: str) -> str:
        """尝试备用数据源 - 避免递归调用"""
        logger.error(f"🔄 {self.current_source.value}失败，尝试备用数据源...")

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
                    logger.info(f"🔄 尝试备用数据源: {source.value}")

                    # 直接调用具体的数据源方法，避免递归
                    if source == ChinaDataSource.TUSHARE:
                        result = self._get_tushare_data(symbol, start_date, end_date)
                    elif source == ChinaDataSource.AKSHARE:
                        result = self._get_akshare_data(symbol, start_date, end_date)
                    elif source == ChinaDataSource.BAOSTOCK:
                        result = self._get_baostock_data(symbol, start_date, end_date)
                    elif source == ChinaDataSource.TDX:
                        result = self._get_tdx_data(symbol, start_date, end_date)
                    else:
                        logger.warning(f"⚠️ 未知数据源: {source.value}")
                        continue

                    if "❌" not in result:
                        logger.info(f"✅ 备用数据源{source.value}获取成功")
                        return result
                    else:
                        logger.warning(f"⚠️ 备用数据源{source.value}返回错误结果")

                except Exception as e:
                    logger.error(f"❌ 备用数据源{source.value}也失败: {e}")
                    continue
        
        return f"❌ 所有数据源都无法获取{symbol}的数据"
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取股票基本信息，支持降级机制"""
        logger.info(f"📊 [股票信息] 开始获取{symbol}基本信息...")

        # 首先尝试当前数据源
        try:
            if self.current_source == ChinaDataSource.TUSHARE:
                from .interface import get_china_stock_info_tushare
                info_str = get_china_stock_info_tushare(symbol)
                result = self._parse_stock_info_string(info_str, symbol)

                # 检查是否获取到有效信息
                if result.get('name') and result['name'] != f'股票{symbol}':
                    logger.info(f"✅ [股票信息] Tushare成功获取{symbol}信息")
                    return result
                else:
                    logger.warning(f"⚠️ [股票信息] Tushare返回无效信息，尝试降级...")
                    return self._try_fallback_stock_info(symbol)
            else:
                adapter = self.get_data_adapter()
                if adapter and hasattr(adapter, 'get_stock_info'):
                    result = adapter.get_stock_info(symbol)
                    if result.get('name') and result['name'] != f'股票{symbol}':
                        logger.info(f"✅ [股票信息] {self.current_source.value}成功获取{symbol}信息")
                        return result
                    else:
                        logger.warning(f"⚠️ [股票信息] {self.current_source.value}返回无效信息，尝试降级...")
                        return self._try_fallback_stock_info(symbol)
                else:
                    logger.warning(f"⚠️ [股票信息] {self.current_source.value}不支持股票信息获取，尝试降级...")
                    return self._try_fallback_stock_info(symbol)

        except Exception as e:
            logger.error(f"❌ [股票信息] {self.current_source.value}获取失败: {e}")
            return self._try_fallback_stock_info(symbol)

    def _try_fallback_stock_info(self, symbol: str) -> Dict:
        """尝试使用备用数据源获取股票基本信息"""
        logger.info(f"🔄 [股票信息] {self.current_source.value}失败，尝试备用数据源...")

        # 获取所有可用数据源
        available_sources = self.available_sources.copy()

        # 移除当前数据源
        if self.current_source.value in available_sources:
            available_sources.remove(self.current_source.value)

        # 尝试所有备用数据源
        for source_name in available_sources:
            try:
                source = ChinaDataSource(source_name)
                logger.info(f"🔄 [股票信息] 尝试备用数据源: {source_name}")

                # 根据数据源类型获取股票信息
                if source == ChinaDataSource.TUSHARE:
                    from .interface import get_china_stock_info_tushare
                    info_str = get_china_stock_info_tushare(symbol)
                    result = self._parse_stock_info_string(info_str, symbol)
                elif source == ChinaDataSource.AKSHARE:
                    result = self._get_akshare_stock_info(symbol)
                elif source == ChinaDataSource.BAOSTOCK:
                    result = self._get_baostock_stock_info(symbol)
                else:
                    # 尝试通用适配器
                    original_source = self.current_source
                    self.current_source = source
                    adapter = self.get_data_adapter()
                    self.current_source = original_source

                    if adapter and hasattr(adapter, 'get_stock_info'):
                        result = adapter.get_stock_info(symbol)
                    else:
                        logger.warning(f"⚠️ [股票信息] {source_name}不支持股票信息获取")
                        continue

                # 检查是否获取到有效信息
                if result.get('name') and result['name'] != f'股票{symbol}':
                    logger.info(f"✅ [股票信息] 备用数据源{source_name}成功获取{symbol}信息")
                    return result
                else:
                    logger.warning(f"⚠️ [股票信息] 备用数据源{source_name}返回无效信息")

            except Exception as e:
                logger.error(f"❌ [股票信息] 备用数据源{source_name}失败: {e}")
                continue

        # 所有数据源都失败，返回默认值
        logger.error(f"❌ [股票信息] 所有数据源都无法获取{symbol}的基本信息")
        return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'unknown'}

    def _get_akshare_stock_info(self, symbol: str) -> Dict:
        """使用AKShare获取股票基本信息"""
        try:
            import akshare as ak

            # 尝试获取个股信息
            stock_info = ak.stock_individual_info_em(symbol=symbol)

            if stock_info is not None and not stock_info.empty:
                # 转换为字典格式
                info = {'symbol': symbol, 'source': 'akshare'}

                # 提取股票名称
                name_row = stock_info[stock_info['item'] == '股票简称']
                if not name_row.empty:
                    info['name'] = name_row['value'].iloc[0]
                else:
                    info['name'] = f'股票{symbol}'

                # 提取其他信息
                info['area'] = '未知'  # AKShare没有地区信息
                info['industry'] = '未知'  # 可以通过其他API获取
                info['market'] = '未知'  # 可以根据股票代码推断
                info['list_date'] = '未知'  # 可以通过其他API获取

                return info
            else:
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'akshare'}

        except Exception as e:
            logger.error(f"❌ [股票信息] AKShare获取失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'akshare', 'error': str(e)}

    def _get_baostock_stock_info(self, symbol: str) -> Dict:
        """使用BaoStock获取股票基本信息"""
        try:
            import baostock as bs

            # 转换股票代码格式
            if symbol.startswith('6'):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"

            # 登录BaoStock
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"❌ [股票信息] BaoStock登录失败: {lg.error_msg}")
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'baostock'}

            # 查询股票基本信息
            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != '0':
                bs.logout()
                logger.error(f"❌ [股票信息] BaoStock查询失败: {rs.error_msg}")
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'baostock'}

            # 解析结果
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            # 登出
            bs.logout()

            if data_list:
                # BaoStock返回格式: [code, code_name, ipoDate, outDate, type, status]
                info = {'symbol': symbol, 'source': 'baostock'}
                info['name'] = data_list[0][1]  # code_name
                info['area'] = '未知'  # BaoStock没有地区信息
                info['industry'] = '未知'  # BaoStock没有行业信息
                info['market'] = '未知'  # 可以根据股票代码推断
                info['list_date'] = data_list[0][2]  # ipoDate

                return info
            else:
                return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'baostock'}

        except Exception as e:
            logger.error(f"❌ [股票信息] BaoStock获取失败: {e}")
            return {'symbol': symbol, 'name': f'股票{symbol}', 'source': 'baostock', 'error': str(e)}

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
            logger.error(f"⚠️ 解析股票信息失败: {e}")
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
    from tradingagents.utils.logging_init import get_logger


    # 添加详细的股票代码追踪日志
    logger.info(f"🔍 [股票代码追踪] data_source_manager.get_china_stock_data_unified 接收到的股票代码: '{symbol}' (类型: {type(symbol)})")
    logger.info(f"🔍 [股票代码追踪] 股票代码长度: {len(str(symbol))}")
    logger.info(f"🔍 [股票代码追踪] 股票代码字符: {list(str(symbol))}")

    manager = get_data_source_manager()
    logger.info(f"🔍 [股票代码追踪] 调用 manager.get_stock_data，传入参数: symbol='{symbol}', start_date='{start_date}', end_date='{end_date}'")
    result = manager.get_stock_data(symbol, start_date, end_date)
    logger.info(f"🔍 [股票代码追踪] manager.get_stock_data 返回结果前200字符: {result[:200] if result else 'None'}")
    return result


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
