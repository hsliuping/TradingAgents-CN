#!/usr/bin/env python3
"""
指数数据提供者
提供宏观经济、政策新闻、板块资金流向等指数分析所需数据

数据来源:
- AKShare: 宏观经济数据、板块资金流、新闻数据
- MongoDB: 数据缓存
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('agents')


class IndexDataProvider:
    """
    指数数据提供者
    
    提供指数分析所需的各类数据:
    - 宏观经济数据 (GDP, CPI, PMI, M2, LPR等)
    - 政策新闻数据
    - 板块资金流向数据
    
    所有数据均支持MongoDB缓存机制
    """
    
    def __init__(self):
        """初始化指数数据提供者"""
        self.cache = self._get_cache()
        self.cache_ttl = {
            'macro': 86400,  # 宏观数据24小时
            'news': 21600,   # 新闻6小时
            'sector': 3600   # 板块数据1小时
        }
        
        # 初始化AKShare
        self.ak = None
        self._init_akshare()
        
        logger.info("✅ [指数数据提供者] 初始化完成")
    
    def _get_cache(self):
        """获取缓存实例"""
        try:
            from tradingagents.config.database_manager import get_mongodb_client
            client = get_mongodb_client()
            if client:
                db = client.get_database('tradingagents')
                logger.info("✅ [指数数据提供者] MongoDB缓存已连接")
                return db
        except Exception as e:
            logger.warning(f"⚠️ [指数数据提供者] MongoDB缓存初始化失败: {e}，将直接从API获取数据")
        return None
    
    def _init_akshare(self):
        """初始化AKShare"""
        try:
            import akshare as ak
            self.ak = ak
            logger.info("✅ [指数数据提供者] AKShare初始化成功")
        except ImportError as e:
            logger.error(f"❌ [指数数据提供者] AKShare未安装: {e}")
            self.ak = None
    
    def get_macro_economics_data(self, end_date: str = None) -> Dict[str, Any]:
        """
        获取宏观经济数据
        
        Args:
            end_date: 查询截止日期 (格式: YYYY-MM-DD)，默认为当前日期
            
        Returns:
            Dict[str, Any]: 包含GDP、CPI、PMI、M2、LPR等指标的字典
        """
        logger.info(f"📊 [指数数据提供者] 获取宏观经济数据, end_date={end_date}")
        
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 检查缓存
        cache_key = f"macro_data_{end_date}"
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    # 检查缓存是否过期
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl['macro']:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取宏观数据")
                        return cached_data.get("data", {})
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")
        
        # 2. 从AKShare获取数据（增加重试机制）
        macro_data = {}
        
        # 增加重试机制
        max_retries = 3
        retry_delay = 1  # 重试间隔（秒）
        
        for attempt in range(max_retries):
            try:
                # 2.1 获取GDP数据（季度）
                try:
                    gdp_df = self.ak.macro_china_gdp()
                    if not gdp_df.empty:
                        latest_gdp = gdp_df.iloc[-1]
                        macro_data['gdp'] = {
                            'quarter': str(latest_gdp.get('季度', 'N/A')),
                            'value': float(latest_gdp.get('国内生产总值-绝对值', 0)),
                            'growth_rate': float(latest_gdp.get('国内生产总值-同比增长', 0))
                        }
                        logger.info(f"✅ [指数数据提供者] GDP数据获取成功")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] GDP数据为空")
                        macro_data['gdp'] = {'quarter': 'N/A', 'value': 0, 'growth_rate': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] GDP数据获取失败: {e}")
                    macro_data['gdp'] = {'quarter': 'N/A', 'value': 0, 'growth_rate': 0}
                
                # 2.2 获取CPI数据（月度）
                try:
                    cpi_df = self.ak.macro_china_cpi_yearly()
                    if not cpi_df.empty:
                        latest_cpi = cpi_df.iloc[-1]
                        macro_data['cpi'] = {
                            'month': str(latest_cpi.get('月份', 'N/A')),
                            'value': float(latest_cpi.get('全国-当月', 100)),
                            'year_on_year': float(latest_cpi.get('全国-同比', 0))
                        }
                        logger.info(f"✅ [指数数据提供者] CPI数据获取成功")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] CPI数据为空")
                        macro_data['cpi'] = {'month': 'N/A', 'value': 100, 'year_on_year': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] CPI数据获取失败: {e}")
                    macro_data['cpi'] = {'month': 'N/A', 'value': 100, 'year_on_year': 0}
                
                # 2.3 获取PMI数据（月度）
                try:
                    pmi_df = self.ak.macro_china_pmi_yearly()
                    if not pmi_df.empty:
                        latest_pmi = pmi_df.iloc[-1]
                        macro_data['pmi'] = {
                            'month': str(latest_pmi.get('月份', 'N/A')),
                            'manufacturing': float(latest_pmi.get('制造业-指数', 50)),
                            'non_manufacturing': float(latest_pmi.get('非制造业-指数', 50))
                        }
                        logger.info(f"✅ [指数数据提供者] PMI数据获取成功")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] PMI数据为空")
                        macro_data['pmi'] = {'month': 'N/A', 'manufacturing': 50, 'non_manufacturing': 50}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] PMI数据获取失败: {e}")
                    macro_data['pmi'] = {'month': 'N/A', 'manufacturing': 50, 'non_manufacturing': 50}
                
                # 2.4 获取M2货币供应量（月度）
                try:
                    m2_df = self.ak.macro_china_m2_yearly()
                    if not m2_df.empty:
                        latest_m2 = m2_df.iloc[-1]
                        macro_data['m2'] = {
                            'month': str(latest_m2.get('月份', 'N/A')),
                            'value': float(latest_m2.get('货币和准货币(M2)-数量(亿元)', 0)),
                            'growth_rate': float(latest_m2.get('货币和准货币(M2)-同比增长', 0))
                        }
                        logger.info(f"✅ [指数数据提供者] M2数据获取成功")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] M2数据为空")
                        macro_data['m2'] = {'month': 'N/A', 'value': 0, 'growth_rate': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] M2数据获取失败: {e}")
                    macro_data['m2'] = {'month': 'N/A', 'value': 0, 'growth_rate': 0}
                
                # 2.5 获取LPR利率（月度）
                try:
                    # 修复LPR数据获取方法，使用正确的AKShare接口
                    lpr_df = self.ak.macro_china_lpr()
                    if not lpr_df.empty:
                        latest_lpr = lpr_df.iloc[-1]
                        macro_data['lpr'] = {
                            'date': str(latest_lpr.get('TRADE_DATE', 'N/A')),
                            'lpr_1y': float(latest_lpr.get('LPR1Y', 0)),
                            'lpr_5y': float(latest_lpr.get('LPR5Y', 0))
                        }
                        logger.info(f"✅ [指数数据提供者] LPR数据获取成功")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] LPR数据为空")
                        macro_data['lpr'] = {'date': 'N/A', 'lpr_1y': 0, 'lpr_5y': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] LPR数据获取失败: {e}")
                    macro_data['lpr'] = {'date': 'N/A', 'lpr_1y': 0, 'lpr_5y': 0}
                
                logger.info(f"✅ [指数数据提供者] 宏观数据获取完成，共{len(macro_data)}个指标")
                break  # 成功获取数据，跳出重试循环
                
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 宏观数据获取失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:  # 不是最后一次尝试
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error(f"❌ [指数数据提供者] 宏观数据获取失败，已达到最大重试次数: {e}")
        
        # 3. 缓存数据
        if self.cache is not None and macro_data:
            try:
                cache_doc = {
                    "cache_key": cache_key,
                    "data": macro_data,
                    "created_at": datetime.utcnow(),
                    "end_date": end_date
                }
                self.cache.index_cache.update_one(
                    {"cache_key": cache_key},
                    {"$set": cache_doc},
                    upsert=True
                )
                logger.info(f"✅ [指数数据提供者] 宏观数据已缓存")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")
        
        return macro_data
    
    def get_policy_news(self, lookback_days: int = 7) -> List[Dict[str, Any]]:
        """
        获取政策新闻
        
        Args:
            lookback_days: 回溯天数，默认7天
            
        Returns:
            List[Dict[str, Any]]: 新闻列表，每条新闻包含标题、内容、时间等
        """
        logger.info(f"📰 [指数数据提供者] 获取政策新闻, lookback_days={lookback_days}")
        
        # 1. 检查缓存
        cache_key = f"policy_news_{lookback_days}"
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl['news']:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取政策新闻")
                        return cached_data.get("data", [])
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")
        
        # 2. 从AKShare获取新闻
        news_list = []
        
        try:
            # 2.1 尝试获取新闻联播文字稿（主要数据源）
            try:
                news_df = self.ak.news_cctv()
                if not news_df.empty:
                    # 只取最近lookback_days天的新闻
                    news_df['date'] = pd.to_datetime(news_df['date'])
                    cutoff_date = datetime.now() - timedelta(days=lookback_days)
                    recent_news = news_df[news_df['date'] >= cutoff_date]
                    
                    for _, row in recent_news.iterrows():
                        news_list.append({
                            'title': row.get('title', ''),
                            'content': row.get('content', ''),
                            'date': row.get('date').strftime('%Y-%m-%d') if pd.notna(row.get('date')) else '',
                            'source': '新闻联播'
                        })
                    
                    logger.info(f"✅ [指数数据提供者] 新闻联播数据获取成功，共{len(news_list)}条")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 新闻联播数据获取失败: {e}")
            
            # 2.2 降级方案：获取百度财经新闻
            if len(news_list) == 0:
                try:
                    logger.info(f"⚠️ [指数数据提供者] 使用降级方案：百度财经新闻")
                    news_df = self.ak.stock_news_em(symbol="宏观经济")
                    if not news_df.empty:
                        for _, row in news_df.head(10).iterrows():
                            news_list.append({
                                'title': row.get('新闻标题', ''),
                                'content': row.get('新闻内容', ''),
                                'date': row.get('发布时间', ''),
                                'source': '东方财富'
                            })
                        logger.info(f"✅ [指数数据提供者] 百度财经新闻获取成功，共{len(news_list)}条")
                except Exception as e2:
                    logger.warning(f"⚠️ [指数数据提供者] 百度财经新闻获取失败: {e2}")
            
        except Exception as e:
            logger.error(f"❌ [指数数据提供者] 政策新闻获取失败: {e}")
        
        # 如果仍然没有数据，返回空列表
        if len(news_list) == 0:
            logger.warning(f"⚠️ [指数数据提供者] 未获取到政策新闻，返回空列表")
            news_list = [{
                'title': '暂无政策新闻',
                'content': '当前无法获取政策新闻数据，请稍后重试',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'source': '系统提示'
            }]
        
        # 3. 缓存数据
        if self.cache is not None and news_list:
            try:
                cache_doc = {
                    "cache_key": cache_key,
                    "data": news_list,
                    "created_at": datetime.utcnow(),
                    "lookback_days": lookback_days
                }
                self.cache.index_cache.update_one(
                    {"cache_key": cache_key},
                    {"$set": cache_doc},
                    upsert=True
                )
                logger.info(f"✅ [指数数据提供者] 政策新闻已缓存")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")
        
        return news_list
    
    def get_sector_flows(self, trade_date: str = None) -> Dict[str, Any]:
        """
        获取板块资金流向
        
        Args:
            trade_date: 交易日期 (格式: YYYY-MM-DD)，默认为最新交易日
            
        Returns:
            Dict[str, Any]: 板块资金流向数据，包含top涨幅板块和资金流入数据
        """
        logger.info(f"💰 [指数数据提供者] 获取板块资金流向, trade_date={trade_date}")
        
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 检查缓存
        cache_key = f"sector_flows_{trade_date}"
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl['sector']:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取板块数据")
                        return cached_data.get("data", {})
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")
        
        # 2. 从AKShare获取板块数据（增加重试机制）
        sector_data = {
            'top_sectors': [],
            'bottom_sectors': [],
            'all_sectors': []
        }
        
        max_retries = 3
        retry_delay = 1  # 重试间隔（秒）
        
        for attempt in range(max_retries):
            try:
                # 获取东方财富板块资金流数据
                sector_df = self.ak.stock_board_industry_name_em()
                
                if not sector_df.empty:
                    # 获取涨跌幅数据
                    sector_flow_df = self.ak.stock_board_industry_summary_ths()
                    
                    if not sector_flow_df.empty:
                        # 按涨跌幅排序
                        sector_flow_df = sector_flow_df.sort_values('涨跌幅', ascending=False)
                        
                        # Top 5 领涨板块
                        for _, row in sector_flow_df.head(5).iterrows():
                            sector_data['top_sectors'].append({
                                'name': row.get('板块', ''),
                                'change_pct': float(row.get('涨跌幅', 0)),
                                'net_inflow': float(row.get('流入资金', 0)) if '流入资金' in row else 0,
                                'turnover_rate': float(row.get('换手率', 0)) if '换手率' in row else 0
                            })
                        
                        # Bottom 5 领跌板块
                        for _, row in sector_flow_df.tail(5).iterrows():
                            sector_data['bottom_sectors'].append({
                                'name': row.get('板块', ''),
                                'change_pct': float(row.get('涨跌幅', 0)),
                                'net_inflow': float(row.get('流入资金', 0)) if '流入资金' in row else 0,
                                'turnover_rate': float(row.get('换手率', 0)) if '换手率' in row else 0
                            })
                        
                        # 所有板块概况
                        for _, row in sector_flow_df.iterrows():
                            sector_data['all_sectors'].append({
                                'name': row.get('板块', ''),
                                'change_pct': float(row.get('涨跌幅', 0))
                            })
                        
                        logger.info(f"✅ [指数数据提供者] 板块数据获取成功，共{len(sector_flow_df)}个板块")
                        break  # 成功获取数据，跳出重试循环
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] 板块流向数据为空")
                else:
                    logger.warning(f"⚠️ [指数数据提供者] 板块名称数据为空")
                    
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 板块数据获取失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:  # 不是最后一次尝试
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error(f"❌ [指数数据提供者] 板块数据获取失败，已达到最大重试次数: {e}")
        
        # 3. 缓存数据
        if self.cache is not None and sector_data:
            try:
                cache_doc = {
                    "cache_key": cache_key,
                    "data": sector_data,
                    "created_at": datetime.utcnow(),
                    "trade_date": trade_date
                }
                self.cache.index_cache.update_one(
                    {"cache_key": cache_key},
                    {"$set": cache_doc},
                    upsert=True
                )
                logger.info(f"✅ [指数数据提供者] 板块数据已缓存")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")
        
        return sector_data


# 全局实例
_index_data_provider = None


def get_index_data_provider() -> IndexDataProvider:
    """获取全局指数数据提供者实例"""
    global _index_data_provider
    if _index_data_provider is None:
        _index_data_provider = IndexDataProvider()
    return _index_data_provider
