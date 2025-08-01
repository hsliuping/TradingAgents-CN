#!/usr/bin/env python3
"""
股票分析结果缓存管理系统
支持按股票代码和分析日期进行永久缓存
"""

import json
import os
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pathlib import Path

from tradingagents.utils.logging_manager import get_logger
logger = get_logger('analysis_cache')

class AnalysisCache:
    """股票分析结果缓存管理器"""
    
    def __init__(self, cache_dir: str = None):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录，默认为 data/analysis_cache
        """
        if cache_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            cache_dir = project_root / "data" / "analysis_cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 分析缓存初始化完成，缓存目录: {self.cache_dir}")
    
    def _get_cache_key(self, symbol: str, analysis_date: str = None) -> str:
        """
        生成缓存键
        
        Args:
            symbol: 股票代码
            analysis_date: 分析日期，格式为 YYYY-MM-DD，默认为今天
            
        Returns:
            str: 缓存键
        """
        if analysis_date is None:
            analysis_date = date.today().strftime('%Y-%m-%d')
        
        # 确保股票代码大写
        symbol = symbol.upper().strip()
        
        return f"{symbol}_{analysis_date}"
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """
        获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Path: 缓存文件路径
        """
        return self.cache_dir / f"{cache_key}.json"
    
    def save_analysis(self, symbol: str, analysis_data: Dict[str, Any], analysis_date: str = None) -> bool:
        """
        保存分析结果到缓存
        
        Args:
            symbol: 股票代码
            analysis_data: 分析数据
            analysis_date: 分析日期，默认为今天
            
        Returns:
            bool: 是否保存成功
        """
        try:
            cache_key = self._get_cache_key(symbol, analysis_date)
            cache_file = self._get_cache_file_path(cache_key)
            
            # 准备缓存数据
            cache_data = {
                'symbol': symbol.upper().strip(),
                'analysis_date': analysis_date or date.today().strftime('%Y-%m-%d'),
                'cached_time': datetime.now().isoformat(),
                'data': analysis_data
            }
            
            # 写入文件
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"✅ 分析结果已缓存: {symbol} ({analysis_date or '今天'})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存分析缓存失败: {symbol} - {e}")
            return False
    
    def load_analysis(self, symbol: str, analysis_date: str = None) -> Optional[Dict[str, Any]]:
        """
        从缓存加载分析结果
        
        Args:
            symbol: 股票代码
            analysis_date: 分析日期，默认为今天
            
        Returns:
            Optional[Dict]: 分析数据，如果不存在则返回None
        """
        try:
            cache_key = self._get_cache_key(symbol, analysis_date)
            cache_file = self._get_cache_file_path(cache_key)
            
            if not cache_file.exists():
                logger.debug(f"📭 缓存文件不存在: {cache_key}")
                return None
            
            # 读取文件
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            logger.info(f"📦 已加载分析缓存: {symbol} ({analysis_date or '今天'})")
            return cache_data
            
        except Exception as e:
            logger.error(f"❌ 加载分析缓存失败: {symbol} - {e}")
            return None
    
    def exists(self, symbol: str, analysis_date: str = None) -> bool:
        """
        检查缓存是否存在
        
        Args:
            symbol: 股票代码
            analysis_date: 分析日期
            
        Returns:
            bool: 缓存是否存在
        """
        cache_key = self._get_cache_key(symbol, analysis_date)
        cache_file = self._get_cache_file_path(cache_key)
        return cache_file.exists()
    
    def list_cached_analyses(self, symbol: str = None) -> List[Dict[str, str]]:
        """
        列出缓存的分析结果
        
        Args:
            symbol: 可选，筛选特定股票代码
            
        Returns:
            List[Dict]: 缓存列表，包含symbol, date, cache_key等信息
        """
        try:
            cached_files = []
            
            for cache_file in self.cache_dir.glob("*.json"):
                cache_key = cache_file.stem
                
                # 解析缓存键
                parts = cache_key.split('_')
                if len(parts) >= 2:
                    file_symbol = '_'.join(parts[:-1])  # 支持包含下划线的股票代码
                    file_date = parts[-1]
                    
                    # 如果指定了股票代码，则过滤
                    if symbol and file_symbol.upper() != symbol.upper():
                        continue
                    
                    cached_files.append({
                        'symbol': file_symbol,
                        'date': file_date,
                        'cache_key': cache_key,
                        'file_path': str(cache_file),
                        'file_size': cache_file.stat().st_size,
                        'modified_time': datetime.fromtimestamp(cache_file.stat().st_mtime).isoformat()
                    })
            
            # 按日期排序（最新的在前）
            cached_files.sort(key=lambda x: x['date'], reverse=True)
            
            logger.info(f"📋 找到 {len(cached_files)} 个缓存文件")
            return cached_files
            
        except Exception as e:
            logger.error(f"❌ 列出缓存文件失败: {e}")
            return []
    
    def delete_analysis(self, symbol: str, analysis_date: str = None) -> bool:
        """
        删除指定的分析缓存
        
        Args:
            symbol: 股票代码
            analysis_date: 分析日期
            
        Returns:
            bool: 是否删除成功
        """
        try:
            cache_key = self._get_cache_key(symbol, analysis_date)
            cache_file = self._get_cache_file_path(cache_key)
            
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"🗑️ 已删除分析缓存: {symbol} ({analysis_date or '今天'})")
                return True
            else:
                logger.warning(f"⚠️ 缓存文件不存在: {cache_key}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 删除分析缓存失败: {symbol} - {e}")
            return False
    
    def cleanup_old_cache(self, days: int = 30) -> int:
        """
        清理旧的缓存文件（开发模式下不使用，生产环境可以使用）
        
        Args:
            days: 保留天数
            
        Returns:
            int: 删除的文件数量
        """
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            for cache_file in self.cache_dir.glob("*.json"):
                file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if file_time < cutoff_time:
                    cache_file.unlink()
                    deleted_count += 1
            
            logger.info(f"🧹 清理了 {deleted_count} 个旧缓存文件（超过{days}天）")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ 清理缓存失败: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_files = len(cache_files)
            total_size = sum(f.stat().st_size for f in cache_files)
            
            # 按股票分组统计
            symbol_stats = {}
            for cache_file in cache_files:
                cache_key = cache_file.stem
                parts = cache_key.split('_')
                if len(parts) >= 2:
                    symbol = '_'.join(parts[:-1])
                    if symbol not in symbol_stats:
                        symbol_stats[symbol] = 0
                    symbol_stats[symbol] += 1
            
            return {
                'total_files': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'cache_directory': str(self.cache_dir),
                'symbol_count': len(symbol_stats),
                'symbol_stats': symbol_stats
            }
            
        except Exception as e:
            logger.error(f"❌ 获取缓存统计失败: {e}")
            return {}


# 全局缓存实例
_global_cache = None

def get_global_cache() -> AnalysisCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = AnalysisCache()
    return _global_cache


def cache_analysis_result(symbol: str, analysis_data: Dict[str, Any], analysis_date: str = None) -> bool:
    """
    便捷函数：缓存分析结果
    
    Args:
        symbol: 股票代码
        analysis_data: 分析数据
        analysis_date: 分析日期
        
    Returns:
        bool: 是否缓存成功
    """
    cache = get_global_cache()
    return cache.save_analysis(symbol, analysis_data, analysis_date)


def load_cached_analysis(symbol: str, analysis_date: str = None) -> Optional[Dict[str, Any]]:
    """
    便捷函数：加载缓存的分析结果
    
    Args:
        symbol: 股票代码
        analysis_date: 分析日期
        
    Returns:
        Optional[Dict]: 分析数据
    """
    cache = get_global_cache()
    return cache.load_analysis(symbol, analysis_date)


def is_analysis_cached(symbol: str, analysis_date: str = None) -> bool:
    """
    便捷函数：检查分析是否已缓存
    
    Args:
        symbol: 股票代码
        analysis_date: 分析日期
        
    Returns:
        bool: 是否已缓存
    """
    cache = get_global_cache()
    return cache.exists(symbol, analysis_date)