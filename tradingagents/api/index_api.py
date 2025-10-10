#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数数据API接口
提供便捷的指数数据获取接口，基于Tushare数据源
"""

import sys
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')

# 添加dataflows目录到路径
dataflows_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dataflows')
if dataflows_path not in sys.path:
    sys.path.append(dataflows_path)

# 导入指数数据接口
try:
    from interface import (
        get_index_data_unified,
        get_index_basic_unified,
        get_market_overview_unified,
        get_index_technical_indicators
    )
    INDEX_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ 指数数据服务不可用: {e}")
    INDEX_SERVICE_AVAILABLE = False


def get_index_info(ts_code: str = None) -> Dict[str, Any]:
    """
    获取指数基础信息
    
    Args:
        ts_code: 指数代码（可选），如果不提供则返回所有指数信息
    
    Returns:
        Dict: 指数基础信息
    
    Example:
        >>> info = get_index_info('000001.SH')  # 获取上证指数信息
        >>> all_info = get_index_info()  # 获取所有指数信息
    """
    if not INDEX_SERVICE_AVAILABLE:
        return {
            'error': '指数数据服务不可用',
            'suggestion': '请检查服务配置和Tushare接口'
        }
    
    try:
        if ts_code:
            # 获取特定指数信息（通过获取基础信息然后筛选）
            all_data = get_index_basic_unified()
            if 'error' in all_data:
                return {'error': f'无法获取指数{ts_code}信息', 'details': all_data}
            
            # 这里可以进一步解析all_data来找到特定指数
            return {
                'ts_code': ts_code,
                'data': all_data,
                'message': f'指数{ts_code}基础信息获取成功'
            }
        else:
            # 获取所有指数信息
            data = get_index_basic_unified()
            if isinstance(data, str) and '❌' in data:
                return {'error': '获取指数基础信息失败', 'details': data}
            
            return {
                'data': data,
                'message': '所有指数基础信息获取成功'
            }
            
    except Exception as e:
        return {
            'error': f'获取指数信息失败: {e}',
            'ts_code': ts_code,
            'suggestion': '请检查指数代码格式或网络连接'
        }


def get_index_data(ts_code: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取指数历史数据
    
    Args:
        ts_code: 指数代码（如：000001.SH, 399001.SZ, 399300.SZ）
        start_date: 开始日期（格式：YYYY-MM-DD），默认为30天前
        end_date: 结束日期（格式：YYYY-MM-DD），默认为今天
    
    Returns:
        str: 指数数据的字符串表示或错误信息
    
    Example:
        >>> data = get_index_data('000001.SH', '2024-01-01', '2024-01-31')
        >>> print(data)
    """
    if not INDEX_SERVICE_AVAILABLE:
        return "❌ 指数数据服务不可用，请检查服务配置"
    
    # 设置默认日期
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    try:
        return get_index_data_unified(ts_code, start_date, end_date)
    except Exception as e:
        return f"❌ 获取指数{ts_code}数据失败: {e}"


def get_market_indices() -> str:
    """
    获取市场主要指数概览
    
    Returns:
        str: 市场指数概览数据
    
    Example:
        >>> overview = get_market_indices()
        >>> print(overview)
    """
    if not INDEX_SERVICE_AVAILABLE:
        return "❌ 指数数据服务不可用，请检查服务配置"
    
    try:
        return get_market_overview_unified()
    except Exception as e:
        return f"❌ 获取市场指数概览失败: {e}"


def get_index_technical_analysis(ts_code: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取指数技术分析指标
    
    Args:
        ts_code: 指数代码
        start_date: 开始日期（格式：YYYY-MM-DD），默认为60天前
        end_date: 结束日期（格式：YYYY-MM-DD），默认为今天
    
    Returns:
        str: 技术分析指标数据
    
    Example:
        >>> analysis = get_index_technical_analysis('000001.SH')
        >>> print(analysis)
    """
    if not INDEX_SERVICE_AVAILABLE:
        return "❌ 指数数据服务不可用，请检查服务配置"
    
    # 设置默认日期（技术分析需要更多历史数据）
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    
    try:
        return get_index_technical_indicators(ts_code, start_date, end_date)
    except Exception as e:
        return f"❌ 获取指数{ts_code}技术分析失败: {e}"


def search_indices(keyword: str) -> List[Dict[str, Any]]:
    """
    根据关键词搜索指数
    
    Args:
        keyword: 搜索关键词（指数代码或名称的一部分）
    
    Returns:
        List[Dict]: 匹配的指数信息列表
    
    Example:
        >>> results = search_indices('上证')
        >>> for index in results:
        ...     print(f"{index['ts_code']}: {index['name']}")
    """
    if not INDEX_SERVICE_AVAILABLE:
        return [{
            'error': '指数数据服务不可用',
            'suggestion': '请检查服务配置和Tushare接口'
        }]
    
    try:
        # 获取所有指数信息
        all_indices_data = get_index_basic_unified()
        
        if isinstance(all_indices_data, str) and '❌' in all_indices_data:
            return [{'error': '无法获取指数列表', 'details': all_indices_data}]
        
        # 简单的关键词匹配（这里需要根据实际返回的数据格式进行调整）
        matches = []
        keyword_lower = keyword.lower()
        
        # 注意：这里的实现需要根据get_index_basic_unified()的实际返回格式进行调整
        # 目前返回的是格式化的字符串，实际应用中可能需要返回结构化数据
        
        return [{
            'message': f'搜索关键词: {keyword}',
            'data': all_indices_data,
            'note': '当前返回所有指数信息，需要手动筛选'
        }]
        
    except Exception as e:
        return [{
            'error': f'搜索指数失败: {e}',
            'keyword': keyword
        }]


def get_major_indices_summary() -> Dict[str, Any]:
    """
    获取主要指数摘要信息
    
    Returns:
        Dict: 主要指数的摘要统计
    
    Example:
        >>> summary = get_major_indices_summary()
        >>> print(f"上证指数当前点位: {summary['shanghai_composite']}")
    """
    if not INDEX_SERVICE_AVAILABLE:
        return {
            'error': '指数数据服务不可用',
            'suggestion': '请检查服务配置和Tushare接口'
        }
    
    try:
        # 获取市场概览
        market_data = get_market_overview_unified()
        
        if isinstance(market_data, str) and '❌' in market_data:
            return {'error': '无法获取市场概览', 'details': market_data}
        
        return {
            'data': market_data,
            'updated_at': datetime.now().isoformat(),
            'data_source': 'Tushare',
            'message': '主要指数摘要获取成功'
        }
        
    except Exception as e:
        return {
            'error': f'获取主要指数摘要失败: {e}',
            'suggestion': '请检查网络连接和Tushare配置'
        }


def check_index_service_status() -> Dict[str, Any]:
    """
    检查指数服务状态
    
    Returns:
        Dict: 服务状态信息
    
    Example:
        >>> status = check_index_service_status()
        >>> print(f"Tushare状态: {status['tushare_status']}")
    """
    status_info = {
        'service_available': INDEX_SERVICE_AVAILABLE,
        'checked_at': datetime.now().isoformat()
    }
    
    if not INDEX_SERVICE_AVAILABLE:
        status_info.update({
            'error': '指数数据服务不可用',
            'suggestion': '请检查dataflows.interface模块和Tushare配置'
        })
        return status_info
    
    # 测试各个接口的可用性
    try:
        # 测试基础信息接口
        basic_test = get_index_basic_unified()
        basic_status = 'available' if not (isinstance(basic_test, str) and '❌' in basic_test) else 'error'
        
        # 测试市场概览接口
        overview_test = get_market_overview_unified()
        overview_status = 'available' if not (isinstance(overview_test, str) and '❌' in overview_test) else 'error'
        
        status_info.update({
            'basic_info_status': basic_status,
            'market_overview_status': overview_status,
            'tushare_integration': 'active',
            'supported_functions': [
                'get_index_data',
                'get_index_basic_info', 
                'get_market_overview',
                'get_technical_indicators'
            ]
        })
        
    except Exception as e:
        status_info.update({
            'error': f'服务状态检查失败: {e}',
            'tushare_integration': 'error'
        })
    
    return status_info


# 便捷的别名函数
get_index = get_index_info  # 别名
get_indices = get_major_indices_summary  # 别名
search = search_indices  # 别名
market_overview = get_market_indices  # 别名
technical_analysis = get_index_technical_analysis  # 别名
status = check_index_service_status  # 别名


if __name__ == '__main__':
    # 简单的命令行测试
    print("🔍 指数数据API测试")
    print("=" * 50)
    
    # 检查服务状态
    print("\n📊 服务状态检查:")
    status_info = check_index_service_status()
    for key, value in status_info.items():
        print(f"  {key}: {value}")
    
    if INDEX_SERVICE_AVAILABLE:
        # 测试获取市场概览
        print("\n📈 市场指数概览:")
        market_data = get_market_indices()
        print(market_data[:500] + "..." if len(market_data) > 500 else market_data)
        
        # 测试获取指数数据
        print("\n📊 上证指数数据:")
        index_data = get_index_data('000001.SH')
        print(index_data[:300] + "..." if len(index_data) > 300 else index_data)
        
        # 测试技术分析
        print("\n📈 技术分析:")
        tech_analysis = get_index_technical_analysis('000001.SH')
        print(tech_analysis[:300] + "..." if len(tech_analysis) > 300 else tech_analysis)
    else:
        print("\n❌ 指数服务不可用，请检查配置")