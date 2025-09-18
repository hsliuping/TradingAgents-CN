"""
新闻过滤集成模块
将新闻过滤器集成到现有的新闻获取流程中
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

def integrate_news_filtering(original_get_stock_news_em):
    """
    装饰器：为get_stock_news_em函数添加新闻过滤功能
    
    Args:
        original_get_stock_news_em: 原始的get_stock_news_em函数
        
    Returns:
        包装后的函数，具有新闻过滤功能
    """
    def filtered_get_stock_news_em(symbol: str, enable_filter: bool = True, min_score: float = 30, 
                                  use_semantic: bool = False, use_local_model: bool = False) -> pd.DataFrame:
        """
        增强版get_stock_news_em，集成新闻过滤功能
        
        Args:
            symbol: 股票代码
            enable_filter: 是否启用新闻过滤
            min_score: 最低相关性评分阈值
            use_semantic: 是否使用语义相似度过滤
            use_local_model: 是否使用本地分类模型
            
        Returns:
            pd.DataFrame: 过滤后的新闻数据
        """
        logger.info(f"[新闻过滤集成] 开始获取 {symbol} 的新闻，过滤开关: {enable_filter}")
        
        # 调用原始函数获取新闻
        start_time = datetime.now()
        try:
            news_df = original_get_stock_news_em(symbol)
            fetch_time = (datetime.now() - start_time).total_seconds()
            
            if news_df.empty:
                logger.warning(f"[新闻过滤集成] 原始函数未获取到 {symbol} 的新闻数据")
                return news_df
            
            logger.info(f"[新闻过滤集成] 原始新闻获取成功: {len(news_df)}条，耗时: {fetch_time:.2f}秒")
            
            # 如果不启用过滤，直接返回原始数据
            if not enable_filter:
                logger.info(f"[新闻过滤集成] 过滤功能已禁用，返回原始新闻数据")
                return news_df
            
            # 启用新闻过滤
            filter_start_time = datetime.now()
            
            try:
                # 导入过滤器
                from tradingagents.utils.enhanced_news_filter import create_enhanced_news_filter
                
                # 创建过滤器
                news_filter = create_enhanced_news_filter(
                    symbol, 
                    use_semantic=use_semantic, 
                    use_local_model=use_local_model
                )
                
                # 执行过滤
                filtered_df = news_filter.filter_news_enhanced(news_df, min_score=min_score)
                
                filter_time = (datetime.now() - filter_start_time).total_seconds()
                
                # 记录过滤统计
                original_count = len(news_df)
                filtered_count = len(filtered_df)
                filter_rate = (original_count - filtered_count) / original_count * 100 if original_count > 0 else 0
                
                logger.info(f"[新闻过滤集成] 新闻过滤完成:")
                logger.info(f"  - 原始新闻: {original_count}条")
                logger.info(f"  - 过滤后新闻: {filtered_count}条")
                logger.info(f"  - 过滤率: {filter_rate:.1f}%")
                logger.info(f"  - 过滤耗时: {filter_time:.2f}秒")
                
                if not filtered_df.empty:
                    avg_score = filtered_df['final_score'].mean()
                    max_score = filtered_df['final_score'].max()
                    logger.info(f"  - 平均评分: {avg_score:.1f}")
                    logger.info(f"  - 最高评分: {max_score:.1f}")
                
                return filtered_df
                
            except Exception as filter_error:
                logger.error(f"[新闻过滤集成] 新闻过滤失败: {filter_error}")
                logger.error(f"[新闻过滤集成] 返回原始新闻数据作为备用")
                return news_df
                
        except Exception as fetch_error:
            logger.error(f"[新闻过滤集成] 原始新闻获取失败: {fetch_error}")
            return pd.DataFrame()  # 返回空DataFrame
    
    return filtered_get_stock_news_em


def patch_akshare_utils():
    """
    为akshare_utils模块的get_stock_news_em函数添加过滤功能
    """
    try:
        from tradingagents.dataflows import akshare_utils
        
        # 保存原始函数
        if not hasattr(akshare_utils, '_original_get_stock_news_em'):
            akshare_utils._original_get_stock_news_em = akshare_utils.get_stock_news_em
            
            # 应用过滤装饰器
            akshare_utils.get_stock_news_em = integrate_news_filtering(
                akshare_utils._original_get_stock_news_em
            )
            
            logger.info("[新闻过滤集成] ✅ 成功为akshare_utils.get_stock_news_em添加过滤功能")
        else:
            logger.info("[新闻过滤集成] akshare_utils.get_stock_news_em已经被增强")
            
    except Exception as e:
        logger.error(f"[新闻过滤集成] 无法增强akshare_utils.get_stock_news_em: {e}")


def create_filtered_realtime_news_function():
    """
    创建增强版的实时新闻获取函数
    """
    def get_filtered_realtime_stock_news(ticker: str, curr_date: str, hours_back: int = 6, 
                                       enable_filter: bool = True, min_score: float = 30) -> str:
        """
        增强版实时新闻获取函数，集成新闻过滤
        
        Args:
            ticker: 股票代码
            curr_date: 当前日期
            hours_back: 回溯小时数
            enable_filter: 是否启用新闻过滤
            min_score: 最低相关性评分阈值
            
        Returns:
            str: 格式化的新闻报告
        """
        logger.info(f"[增强实时新闻] 开始获取 {ticker} 的过滤新闻")
        
        try:
            # 导入原始函数
            from tradingagents.dataflows.realtime_news_utils import get_realtime_stock_news
            
            # 调用原始函数获取新闻
            original_report = get_realtime_stock_news(ticker, curr_date, hours_back)
            
            if not enable_filter:
                logger.info(f"[增强实时新闻] 过滤功能已禁用，返回原始报告")
                return original_report
            
            # 如果启用过滤且是A股，尝试重新获取并过滤
            if any(suffix in ticker for suffix in ['.SH', '.SZ', '.SS', '.XSHE', '.XSHG']) or \
               (not '.' in ticker and ticker.isdigit()):
                
                logger.info(f"[增强实时新闻] 检测到A股代码，尝试使用过滤版东方财富新闻")
                
                try:
                    from tradingagents.dataflows.akshare_utils import get_stock_news_em
                    
                    # 清理股票代码
                    clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                                    .replace('.XSHE', '').replace('.XSHG', '')
                    
                    # 先获取原始新闻
                    original_news_df = get_stock_news_em(clean_ticker)
                     
                    if enable_filter and not original_news_df.empty:
                         # 应用新闻过滤
                         from tradingagents.utils.news_filter import create_news_filter
                         news_filter = create_news_filter(clean_ticker)
                         filtered_news_df = news_filter.filter_news(original_news_df, min_score=min_score)
                         
                         # 记录过滤统计
                         filter_stats = news_filter.get_filter_statistics(original_news_df, filtered_news_df)
                         logger.info(f"[新闻过滤集成] 新闻过滤完成:")
                         logger.info(f"  - 原始新闻: {len(original_news_df)}条")
                         logger.info(f"  - 过滤后新闻: {len(filtered_news_df)}条")
                         logger.info(f"  - 过滤率: {filter_stats['filter_rate']:.1f}%")
                    else:
                         filtered_news_df = original_news_df
                    
                    if not filtered_news_df.empty:
                        # 构建过滤后的报告
                        news_count = len(filtered_news_df)
                        
                        report = f"# {ticker} 过滤新闻报告\n\n"
                        report += f"📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        report += f"📊 过滤后新闻总数: {news_count}条\n"
                        report += f"🔍 过滤阈值: {min_score}分\n\n"
                        
                        # 添加过滤统计信息
                        if 'final_score' in filtered_news_df.columns:
                            avg_score = filtered_news_df['final_score'].mean()
                            max_score = filtered_news_df['final_score'].max()
                            report += f"📈 平均相关性评分: {avg_score:.1f}分\n"
                            report += f"🏆 最高相关性评分: {max_score:.1f}分\n\n"
                        
                        # 添加新闻内容
                        for idx, (_, row) in enumerate(filtered_news_df.iterrows()):
                            report += f"### {row.get('新闻标题', '无标题')}\n"
                            report += f"📅 {row.get('发布时间', '无时间')}\n"
                            
                            if 'final_score' in row:
                                report += f"⭐ 相关性评分: {row['final_score']:.1f}分\n"
                            
                            report += f"🔗 {row.get('新闻链接', '无链接')}\n\n"
                            report += f"{row.get('新闻内容', '无内容')}\n\n"
                        
                        logger.info(f"[增强实时新闻] ✅ 成功生成过滤新闻报告，包含 {news_count} 条高质量新闻")
                        return report
                    else:
                        logger.warning(f"[增强实时新闻] 过滤后无符合条件的新闻，返回原始报告")
                        return original_report
                        
                except Exception as filter_error:
                    logger.error(f"[增强实时新闻] 新闻过滤失败: {filter_error}")
                    return original_report
            else:
                logger.info(f"[增强实时新闻] 非A股代码，返回原始报告")
                return original_report
                
        except Exception as e:
            logger.error(f"[增强实时新闻] 增强新闻获取失败: {e}")
            return f"❌ 新闻获取失败: {str(e)}"
    
    return get_filtered_realtime_stock_news


# 自动应用补丁
def apply_news_filtering_patches():
    """
    自动应用新闻过滤补丁
    """
    logger.info("[新闻过滤集成] 开始应用新闻过滤补丁...")
    
    # 1. 增强akshare_utils
    patch_akshare_utils()
    
    # 2. 创建增强版实时新闻函数
    enhanced_function = create_filtered_realtime_news_function()
    
    logger.info("[新闻过滤集成] ✅ 新闻过滤补丁应用完成")
    
    return enhanced_function


if __name__ == "__main__":
    # 测试集成功能
    print("=== 测试新闻过滤集成 ===")
    
    # 应用补丁
    enhanced_news_function = apply_news_filtering_patches()
    
    # 测试增强版函数
    test_result = enhanced_news_function(
        ticker="600036",
        curr_date="2024-07-28",
        enable_filter=True,
        min_score=30
    )
    
    print(f"测试结果长度: {len(test_result)} 字符")
    print(f"测试结果预览: {test_result[:200]}...")