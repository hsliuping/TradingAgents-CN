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
                        # GDP数据按时间降序排列（最新的在最前）
                        latest_gdp = gdp_df.iloc[0]
                        macro_data['gdp'] = {
                            'quarter': str(latest_gdp.get('季度', 'N/A')),
                            'value': float(latest_gdp.get('国内生产总值-绝对值', 0)),
                            'growth_rate': float(latest_gdp.get('国内生产总值-同比增长', 0))
                        }
                        logger.info(f"✅ [指数数据提供者] GDP数据获取成功: {macro_data['gdp']['quarter']}")
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] GDP数据为空")
                        macro_data['gdp'] = {'quarter': 'N/A', 'value': 0, 'growth_rate': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] GDP数据获取失败: {e}")
                    macro_data['gdp'] = {'quarter': 'N/A', 'value': 0, 'growth_rate': 0}
                
                # 2.2 获取CPI数据（月度）
                try:
                    # 使用 macro_china_cpi_monthly 获取月度CPI年率
                    cpi_df = self.ak.macro_china_cpi_monthly()
                    if not cpi_df.empty:
                        # 过滤掉 NaN 值
                        cpi_df = cpi_df.dropna(subset=['今值'])
                        if not cpi_df.empty:
                            latest_cpi = cpi_df.iloc[-1] # 按时间升序
                            macro_data['cpi'] = {
                                'month': str(latest_cpi.get('日期', 'N/A')),
                                'value': float(latest_cpi.get('今值', 0)), # CPI年率
                                'year_on_year': float(latest_cpi.get('今值', 0)) # 这里今值就是同比
                            }
                            logger.info(f"✅ [指数数据提供者] CPI数据获取成功: {macro_data['cpi']['month']}")
                        else:
                            macro_data['cpi'] = {'month': 'N/A', 'value': 0, 'year_on_year': 0}
                    else:
                        logger.warning(f"⚠️ [指数数据提供者] CPI数据为空")
                        macro_data['cpi'] = {'month': 'N/A', 'value': 0, 'year_on_year': 0}
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] CPI数据获取失败: {e}")
                    macro_data['cpi'] = {'month': 'N/A', 'value': 0, 'year_on_year': 0}
                
                # 2.3 获取PMI数据（月度）
                try:
                    pmi_df = self.ak.macro_china_pmi_yearly()
                    if not pmi_df.empty:
                        pmi_df = pmi_df.dropna(subset=['今值'])
                        if not pmi_df.empty:
                            latest_pmi = pmi_df.iloc[-1]
                            macro_data['pmi'] = {
                                'month': str(latest_pmi.get('日期', 'N/A')),
                                'manufacturing': float(latest_pmi.get('今值', 50)),
                                'non_manufacturing': 50.0 # 暂时无法获取非制造业PMI，设为中性
                            }
                            logger.info(f"✅ [指数数据提供者] PMI数据获取成功: {macro_data['pmi']['month']}")
                        else:
                             macro_data['pmi'] = {'month': 'N/A', 'manufacturing': 50, 'non_manufacturing': 50}
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
                        m2_df = m2_df.dropna(subset=['今值'])
                        if not m2_df.empty:
                            latest_m2 = m2_df.iloc[-1]
                            macro_data['m2'] = {
                                'month': str(latest_m2.get('日期', 'N/A')),
                                'value': 0, # M2余额暂无法直接获取
                                'growth_rate': float(latest_m2.get('今值', 0)) # M2年率
                            }
                            logger.info(f"✅ [指数数据提供者] M2数据获取成功: {macro_data['m2']['month']}")
                        else:
                             macro_data['m2'] = {'month': 'N/A', 'value': 0, 'growth_rate': 0}
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

    def get_market_funds_flow(self) -> Dict[str, Any]:
        """获取市场资金流向（北向资金、两融余额等）"""
        # 模拟数据，实际应调用 ak.stock_hsgt_hist_em 等接口
        return {
            "northbound": {"net_inflow": 15.2, "trend": "inflow"},
            "southbound": {"net_inflow": 5.8, "trend": "inflow"},
            "margin_balance": {"value": 16500, "change": 120},
            "turnover_rate": 2.5
        }

    def get_index_valuation(self, index_code: str) -> Dict[str, Any]:
        """
        获取指数估值数据
        
        Args:
            index_code: 指数代码，如 "sh000300"
            
        Returns:
            Dict: 包含PE, PB, 股息率等
        """
        import re
        # 提取数字代码
        code_match = re.search(r'\d{6}', index_code)
        if not code_match:
            logger.warning(f"⚠️ [指数数据提供者] 无法从 {index_code} 提取数字代码")
            return {}
            
        pure_code = code_match.group(0)
        
        try:
            # 使用 ak.stock_zh_index_value_csindex 获取中证指数估值
            # 注意：此接口主要支持中证系列指数
            df = self.ak.stock_zh_index_value_csindex(symbol=pure_code)
            
            if not df.empty:
                latest = df.iloc[0] # 按日期降序，取最新的
                
                valuation_data = {
                    "pe": float(latest.get('市盈率1', 0)), # 静态PE
                    "pe_ttm": float(latest.get('市盈率2', 0)), # 滚动PE
                    "dividend_yield": float(latest.get('股息率1', 0)),
                    "date": str(latest.get('日期', '')),
                    "evaluation": "N/A" # 暂无法自动判断高估低估
                }
                
                # 尝试计算PB（如果接口不提供，这里可能缺失）
                valuation_data["pb"] = 0
                
                return valuation_data
                
            return {}
        except Exception as e:
            logger.warning(f"⚠️ [指数数据提供者] 获取指数估值失败: {e}")
            # 降级返回空字典
            return {}

    def get_index_technicals(self, index_code: str) -> Dict[str, Any]:
        """获取指数技术指标"""
        # 模拟数据
        return {
            "ma": {"ma5": 3050, "ma20": 3020, "ma60": 2980, "trend": "bullish"},
            "macd": {"dif": 15.5, "dea": 10.2, "macd": 5.3, "signal": "golden_cross"},
            "rsi": {"rsi6": 65, "rsi12": 58, "rsi24": 52},
            "kdj": {"k": 75, "d": 70, "j": 80},
            "volume": {"trend": "increasing"}
        }

    def get_index_constituents(self, index_code: str) -> List[Dict[str, Any]]:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码，如 "sh000300"
        """
        import re
        code_match = re.search(r'\d{6}', index_code)
        if not code_match:
            return []
            
        pure_code = code_match.group(0)
        
        try:
            df = self.ak.index_stock_cons(symbol=pure_code)
            if not df.empty:
                constituents = []
                for _, row in df.head(10).iterrows(): # 只取前10大权重股
                    # index_stock_cons 返回: 品种代码, 品种名称, 纳入日期
                    constituents.append({
                        "code": row.get('品种代码'),
                        "name": row.get('品种名称'),
                        "weight": 0, # 暂无权重数据
                        "price": 0, # 暂无价格数据
                        "change_pct": 0
                    })
                return constituents
            return []
        except Exception as e:
            logger.warning(f"⚠️ [指数数据提供者] 获取成分股失败: {e}")
            return []
    
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

    def get_multi_source_news(self, keywords: str = None, lookback_days: int = 1) -> List[Dict[str, Any]]:
        """
        获取多源聚合新闻 (7x24小时快讯)
        
        整合来源:
        1. 财联社 (CLS)
        2. 新浪财经 (Sina)
        3. 同花顺 (THS)
        4. 富途牛牛 (Futu)
        
        Args:
            keywords: 搜索关键词（可选）
            lookback_days: 回溯天数 (默认1天，因为是快讯)
            
        Returns:
            List[Dict[str, Any]]: 聚合后的新闻列表
        """
        logger.info(f"🌐 [指数数据提供者] 获取多源聚合新闻, keywords={keywords}")
        
        # 1. 检查缓存 (缓存键包含关键词，因为过滤是在获取后进行的，但为了效率我们缓存原始聚合数据)
        # 这里为了简单，我们只缓存全量数据，然后过滤
        cache_key = f"multi_source_news_raw_{datetime.now().strftime('%Y%m%d_%H')}" # 按小时缓存
        
        all_news = []
        cached = False
        
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    # 检查是否过期 (30分钟过期，因为是快讯)
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < 1800:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取多源新闻")
                        all_news = cached_data.get("data", [])
                        cached = True
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")

        if not cached:
            # 2. 从各个源获取数据
            
            # 2.1 财联社
            try:
                if hasattr(self.ak, 'stock_info_global_cls'):
                    df = self.ak.stock_info_global_cls()
                    if not df.empty:
                        for _, row in df.iterrows():
                            # 格式: 标题, 内容, 发布日期, 发布时间
                            pub_time = f"{row.get('发布日期', '')} {row.get('发布时间', '')}".strip()
                            all_news.append({
                                'title': row.get('标题', '')[:50] + '...' if row.get('标题') else '无标题', # CLS标题往往就是内容
                                'content': row.get('标题', ''), # CLS内容在标题里，或者有content列
                                'date': pub_time,
                                'source': '财联社',
                                'url': ''
                            })
                        logger.info(f"✅ [指数数据提供者] 获取财联社新闻: {len(df)}条")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 财联社新闻获取失败: {e}")

            # 2.2 新浪财经
            try:
                if hasattr(self.ak, 'stock_info_global_sina'):
                    df = self.ak.stock_info_global_sina()
                    if not df.empty:
                        for _, row in df.iterrows():
                            # 格式: 时间, 内容
                            # 新浪返回的时间通常是 HH:MM:SS，需要加上日期
                            time_str = row.get('时间', '')
                            if len(time_str) < 12: # 只有时间
                                time_str = f"{datetime.now().strftime('%Y-%m-%d')} {time_str}"
                                
                            all_news.append({
                                'title': row.get('内容', '')[:30] + '...',
                                'content': row.get('内容', ''),
                                'date': time_str,
                                'source': '新浪财经',
                                'url': ''
                            })
                        logger.info(f"✅ [指数数据提供者] 获取新浪财经新闻: {len(df)}条")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 新浪财经新闻获取失败: {e}")

            # 2.3 同花顺
            try:
                if hasattr(self.ak, 'stock_info_global_ths'):
                    df = self.ak.stock_info_global_ths()
                    if not df.empty:
                        for _, row in df.iterrows():
                            title = row.get('标题', '')
                            content = row.get('内容', '')
                            if not title and content:
                                title = content[:30] + '...'
                            
                            all_news.append({
                                'title': title,
                                'content': content,
                                'date': row.get('发布时间', '') if '发布时间' in row else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'source': '同花顺',
                                'url': row.get('链接', '')
                            })
                        logger.info(f"✅ [指数数据提供者] 获取同花顺新闻: {len(df)}条")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 同花顺新闻获取失败: {e}")
                
            # 2.4 富途牛牛
            try:
                if hasattr(self.ak, 'stock_info_global_futu'):
                    df = self.ak.stock_info_global_futu()
                    if not df.empty:
                        for _, row in df.iterrows():
                            title = row.get('标题', '')
                            content = row.get('内容', '')
                            if not title and content:
                                title = content[:30] + '...'
                                
                            all_news.append({
                                'title': title,
                                'content': content,
                                'date': row.get('发布时间', '') if '发布时间' in row else datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'source': '富途牛牛',
                                'url': row.get('链接', '')
                            })
                        logger.info(f"✅ [指数数据提供者] 获取富途牛牛新闻: {len(df)}条")
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 富途牛牛新闻获取失败: {e}")

            # 3. 缓存数据
            if self.cache is not None and all_news:
                try:
                    cache_doc = {
                        "cache_key": cache_key,
                        "data": all_news,
                        "created_at": datetime.utcnow()
                    }
                    self.cache.index_cache.update_one(
                        {"cache_key": cache_key},
                        {"$set": cache_doc},
                        upsert=True
                    )
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")

        # 4. 过滤和排序
        filtered_news = []
        
        # 日期过滤
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        
        for news in all_news:
            # 简单的关键词过滤
            if keywords:
                if keywords.lower() not in news['title'].lower() and keywords.lower() not in news['content'].lower():
                    continue
            
            filtered_news.append(news)
            
        # 按时间倒序排序 (尝试解析日期，解析失败则放到最后)
        def parse_date(x):
            try:
                return pd.to_datetime(x['date'])
            except:
                return datetime.min
                
        filtered_news.sort(key=parse_date, reverse=True)
        
        return filtered_news

    def get_sector_news(self, sector_name: str, lookback_days: int = 7) -> List[Dict[str, Any]]:
        """
        获取特定板块/概念的新闻
        
        Args:
            sector_name: 板块或概念名称 (如: "半导体", "医药", "新能源")
            lookback_days: 回溯天数，默认7天
            
        Returns:
            List[Dict[str, Any]]: 新闻列表
        """
        logger.info(f"🏭 [指数数据提供者] 获取板块新闻, sector={sector_name}, lookback_days={lookback_days}")
        
        # 1. 检查缓存
        cache_key = f"sector_news_{sector_name}_{lookback_days}"
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl['sector']:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取{sector_name}板块新闻")
                        return cached_data.get("data", [])
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")
        
        # 2. 从AKShare获取数据
        news_list = []
        try:
            # 使用东方财富新闻接口，直接传入板块名称
            news_df = self.ak.stock_news_em(symbol=sector_name)
            
            if not news_df.empty:
                count = 0
                cutoff_date = datetime.now() - timedelta(days=lookback_days)
                
                for _, row in news_df.iterrows():
                    # 简单处理日期，假设是最近的
                    # 东方财富返回格式通常为 'YYYY-MM-DD HH:MM:SS'
                    pub_time_str = row.get('发布时间', '')
                    try:
                        pub_time = pd.to_datetime(pub_time_str)
                        if pub_time < cutoff_date:
                            continue
                    except:
                        pass # 解析失败则保留，假设是最近的
                        
                    news_item = {
                        'title': row.get('新闻标题', ''),
                        'content': row.get('新闻内容', ''),
                        'date': pub_time_str,
                        'source': f'东方财富-{sector_name}',
                        'url': row.get('新闻链接', '')
                    }
                    news_list.append(news_item)
                    count += 1
                    if count >= 20: # 限制条数
                        break
                
                logger.info(f"✅ [指数数据提供者] 获取{sector_name}板块新闻成功: {count}条")
            else:
                logger.warning(f"⚠️ [指数数据提供者] 未找到{sector_name}板块相关新闻")
                
        except Exception as e:
            logger.error(f"❌ [指数数据提供者] 板块新闻获取失败: {e}")
            
        # 3. 缓存数据
        if self.cache is not None and news_list:
            try:
                cache_doc = {
                    "cache_key": cache_key,
                    "data": news_list,
                    "created_at": datetime.utcnow()
                }
                self.cache.index_cache.update_one(
                    {"cache_key": cache_key},
                    {"$set": cache_doc},
                    upsert=True
                )
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")
                
        return news_list

    def get_international_news(self, keywords: str = None, lookback_days: int = 7) -> List[Dict[str, Any]]:
        """
        获取国际新闻（国内源）
        
        Args:
            keywords: 搜索关键词（可选，用于过滤）
            lookback_days: 回溯天数，默认7天
            
        Returns:
            List[Dict[str, Any]]: 新闻列表
        """
        logger.info(f"🌍 [指数数据提供者] 获取国际新闻(国内源), keywords={keywords}, lookback_days={lookback_days}")
        
        # 1. 检查缓存
        cache_key = f"intl_news_cn_{lookback_days}"
        if self.cache is not None:
            try:
                cached_data = self.cache.index_cache.find_one({"cache_key": cache_key})
                if cached_data:
                    cache_time = cached_data.get("created_at")
                    if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self.cache_ttl['news']:
                        logger.info(f"✅ [指数数据提供者] 从缓存获取国际新闻")
                        # 如果有关键词，进行过滤
                        news_data = cached_data.get("data", [])
                        if keywords:
                            filtered_news = [
                                n for n in news_data 
                                if keywords.lower() in n['title'].lower() or keywords.lower() in n['content'].lower()
                            ]
                            return filtered_news
                        return news_data
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存读取失败: {e}")
        
        # 2. 从AKShare获取新闻
        news_list = []
        
        try:
            # 如果提供了关键词，优先尝试直接用关键词搜索
            if keywords:
                try:
                    logger.info(f"🔍 [指数数据提供者] 尝试使用关键词直接搜索: {keywords}")
                    # 处理多关键词情况，取第一个或主要关键词
                    # 假设keywords可能包含多个词，用空格分隔
                    search_key = keywords.split()[0] if ' ' in keywords else keywords
                    
                    news_df = self.ak.stock_news_em(symbol=search_key)
                    if not news_df.empty:
                        count = 0
                        for _, row in news_df.iterrows():
                            pub_time = row.get('发布时间', '')
                            news_item = {
                                'title': row.get('新闻标题', ''),
                                'content': row.get('新闻内容', ''),
                                'date': pub_time,
                                'source': f'东方财富-{search_key}',
                                'url': row.get('新闻链接', '')
                            }
                            news_list.append(news_item)
                            count += 1
                            if count >= 20: break
                        logger.info(f"✅ [指数数据提供者] 关键词搜索成功: {count}条")
                        # 如果直接搜索成功，直接返回（需排序）
                        return news_list
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] 关键词搜索失败: {e}，将尝试通用源")

            sources = ["美股", "全球"]
            for source in sources:
                try:
                    news_df = self.ak.stock_news_em(symbol=source)
                    if not news_df.empty:
                        # 转换日期格式并过滤
                        # 注意：东方财富返回的发布时间格式可能不统一，这里做简单处理
                        # 通常是 'YYYY-MM-DD HH:MM:SS'
                        
                        count = 0
                        for _, row in news_df.iterrows():
                            pub_time = row.get('发布时间', '')
                            # 简单日期过滤逻辑：假设返回的是最近的新闻
                            # 如果需要严格过滤，需要解析日期字符串
                            
                            news_item = {
                                'title': row.get('新闻标题', ''),
                                'content': row.get('新闻内容', ''),
                                'date': pub_time,
                                'source': f'东方财富-{source}',
                                'url': row.get('新闻链接', '')
                            }
                            
                            news_list.append(news_item)
                            count += 1
                            if count >= 20: # 每个源限制20条
                                break
                                
                        logger.info(f"✅ [指数数据提供者] 获取{source}新闻成功: {count}条")
                except Exception as e:
                    logger.warning(f"⚠️ [指数数据提供者] 获取{source}新闻失败: {e}")
            
        except Exception as e:
            logger.error(f"❌ [指数数据提供者] 国际新闻获取失败: {e}")
            
        # 3. 缓存数据 (缓存全量数据，不过滤关键词)
        if self.cache is not None and news_list:
            try:
                cache_doc = {
                    "cache_key": cache_key,
                    "data": news_list,
                    "created_at": datetime.utcnow()
                }
                self.cache.index_cache.update_one(
                    {"cache_key": cache_key},
                    {"$set": cache_doc},
                    upsert=True
                )
            except Exception as e:
                logger.warning(f"⚠️ [指数数据提供者] 缓存写入失败: {e}")
        
        # 4. 关键词过滤
        if keywords:
            filtered_news = [
                n for n in news_list 
                if keywords.lower() in n['title'].lower() or keywords.lower() in n['content'].lower()
            ]
            return filtered_news
            
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
    
    def get_index_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取指数日线数据 (基类默认实现返回None，由子类实现)
        """
        logger.warning(f"⚠️ [指数数据提供者] get_index_daily 未实现，请使用 HybridIndexDataProvider")
        return None


# 全局实例
_index_data_provider = None


def get_index_data_provider() -> IndexDataProvider:
    """获取全局指数数据提供者实例 (优先返回 HybridIndexDataProvider)"""
    global _index_data_provider
    if _index_data_provider is None:
        try:
            from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
            _index_data_provider = HybridIndexDataProvider()
            logger.info("✅ 已初始化 HybridIndexDataProvider")
        except ImportError:
            logger.warning("⚠️ HybridIndexDataProvider 导入失败，回退到基础 IndexDataProvider")
            _index_data_provider = IndexDataProvider()
    return _index_data_provider
