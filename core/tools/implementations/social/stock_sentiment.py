"""
统一股票情绪分析工具

自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源
优先使用用户上传的社媒数据
"""

import logging
from typing import Annotated
from datetime import datetime, timedelta
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_stock_sentiment_unified",
    name="统一股票情绪分析",
    description="获取股票市场情绪和社交媒体情绪，支持A股、港股、美股",
    category="social",
    is_online=True,
    auto_register=True
)
def get_stock_sentiment_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的股票情绪分析工具
    自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        curr_date: 当前日期（格式：YYYY-MM-DD）

    Returns:
        str: 情绪分析报告
    """
    logger.info(f"😊 [统一情绪工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"😊 [统一情绪工具] 股票类型: {market_info['market_name']}")

        result_data = []

        if is_china or is_hk:
            # 中国A股和港股：优先使用用户上传的社媒数据
            logger.info(f"🇨🇳🇭🇰 [统一情绪工具] 处理中文市场情绪...")

            # 🔥 优先查询用户上传的社媒数据（使用同步方式）
            user_uploaded_data = None
            try:
                logger.info(f"🔍 [统一情绪工具] 开始查询数据库中的社媒数据...")
                from app.core.database import get_mongo_db_sync
                
                # 清理代码后缀
                clean_ticker = ticker
                for suffix in ['.SH', '.SZ', '.SS', '.HK', '.XSHE', '.XSHG']:
                    clean_ticker = clean_ticker.replace(suffix, '')
                
                # 使用同步方式查询数据库
                db = get_mongo_db_sync()
                collection = db.social_media_messages
                
                # 查询最近7天的社媒数据
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                query = {
                    "symbol": clean_ticker,
                    "publish_time": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
                
                # 同步查询
                logger.info(f"🔍 [统一情绪工具] 查询数据库: collection=social_media_messages, symbol={clean_ticker}, time_range=最近7天")
                logger.debug(f"🔍 [统一情绪工具] 查询条件详情: {query}")
                cursor = collection.find(query).sort("publish_time", -1).limit(100)
                user_messages = list(cursor)
                logger.info(f"📊 [统一情绪工具] 数据库查询完成: 找到 {len(user_messages)} 条消息")
                
                if user_messages and len(user_messages) > 0:
                    logger.info(f"✅ [统一情绪工具] 找到 {len(user_messages)} 条用户上传的社媒数据，开始分析...")
                    user_uploaded_data = user_messages
                    
                    # 🔥 详细分析用户上传的社媒数据
                    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
                    platform_counts = {}
                    recent_messages = []
                    keyword_counts = {}
                    hashtag_counts = {}
                    total_engagement = {"views": 0, "likes": 0, "shares": 0, "comments": 0}
                    high_influence_messages = []
                    
                    for msg in user_messages:
                        sentiment = msg.get("sentiment", "neutral")
                        sentiment_counts[sentiment] += 1
                        
                        platform = msg.get("platform", "unknown")
                        platform_counts[platform] = platform_counts.get(platform, 0) + 1
                        
                        # 统计关键词
                        keywords = msg.get("keywords", [])
                        if isinstance(keywords, list):
                            for kw in keywords:
                                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
                        
                        # 统计话题标签
                        hashtags = msg.get("hashtags", [])
                        if isinstance(hashtags, list):
                            for tag in hashtags:
                                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
                        
                        # 统计互动数据
                        engagement = msg.get("engagement", {})
                        if isinstance(engagement, dict):
                            total_engagement["views"] += engagement.get("views", 0)
                            total_engagement["likes"] += engagement.get("likes", 0)
                            total_engagement["shares"] += engagement.get("shares", 0)
                            total_engagement["comments"] += engagement.get("comments", 0)
                        
                        # 收集高影响力消息（影响力评分>50或互动率高）
                        author = msg.get("author", {})
                        influence_score = author.get("influence_score", 0) if isinstance(author, dict) else 0
                        engagement_rate = engagement.get("engagement_rate", 0) if isinstance(engagement, dict) else 0
                        
                        if influence_score > 50 or engagement_rate > 5.0:
                            if len(high_influence_messages) < 3:
                                high_influence_messages.append({
                                    "content": msg.get("content", "")[:150] + "..." if len(msg.get("content", "")) > 150 else msg.get("content", ""),
                                    "platform": platform,
                                    "sentiment": sentiment,
                                    "influence_score": influence_score,
                                    "engagement_rate": engagement_rate,
                                    "author": author.get("author_name", "未知") if isinstance(author, dict) else "未知"
                                })
                        
                        # 收集最近消息摘要（优先高影响力）
                        content = msg.get("content", "")
                        if content and len(recent_messages) < 10:
                            recent_messages.append({
                                "content": content[:100] + "..." if len(content) > 100 else content,
                                "platform": platform,
                                "sentiment": sentiment,
                                "publish_time": msg.get("publish_time", ""),
                                "influence_score": influence_score
                            })
                    
                    # 按影响力排序最近消息
                    recent_messages.sort(key=lambda x: x.get("influence_score", 0), reverse=True)
                    recent_messages = recent_messages[:5]  # 只保留前5条
                    
                    # 计算情绪评分
                    total = sum(sentiment_counts.values())
                    if total > 0:
                        sentiment_score_val = (sentiment_counts["positive"] - sentiment_counts["negative"]) / total
                        if sentiment_score_val > 0.1:
                            sentiment_score = "偏多"
                        elif sentiment_score_val < -0.1:
                            sentiment_score = "偏空"
                        else:
                            sentiment_score = "中性"
                    else:
                        sentiment_score = "中性"
                    
                    # 构建详细报告
                    platform_summary = ", ".join([f"{k}({v})" for k, v in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)[:5]])
                    
                    # 热门关键词
                    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    keywords_summary = ", ".join([f"{k}({v})" for k, v in top_keywords]) if top_keywords else "无"
                    
                    # 热门话题
                    top_hashtags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    hashtags_summary = ", ".join([f"#{k}({v})" for k, v in top_hashtags]) if top_hashtags else "无"
                    
                    # 互动数据汇总
                    total_interactions = sum(total_engagement.values())
                    engagement_summary = f"总浏览量:{total_engagement['views']}, 点赞:{total_engagement['likes']}, 转发:{total_engagement['shares']}, 评论:{total_engagement['comments']}"
                    
                    # 高影响力消息
                    high_influence_summary = ""
                    if high_influence_messages:
                        # 构建高影响力消息列表（避免在f-string中使用反斜杠）
                        influence_lines = []
                        for m in high_influence_messages:
                            line = f"- [{m['platform']}] [{m['sentiment']}] 作者:{m['author']} (影响力:{m['influence_score']:.1f}, 互动率:{m['engagement_rate']:.2f}%)"
                            content_line = f"  {m['content']}"
                            influence_lines.append(f"{line}\n{content_line}")
                        high_influence_summary = f"""
### 高影响力消息（影响力评分>50或互动率>5%）
{chr(10).join(influence_lines)}
"""
                    
                    sentiment_summary = f"""## 社媒情绪分析（用户上传数据）
**股票**: {ticker}
**数据来源**: 用户上传的社媒内容
**数据量**: 共 {len(user_messages)} 条消息（最近7天）
**情绪评级**: {sentiment_score} (正向:{sentiment_counts['positive']}, 中性:{sentiment_counts['neutral']}, 负向:{sentiment_counts['negative']})
**平台分布**: {platform_summary}
**热门关键词**: {keywords_summary}
**热门话题**: {hashtags_summary}
**互动数据**: {engagement_summary}（总互动:{total_interactions}）

### 最近社媒消息摘要（按影响力排序）
{chr(10).join([f"- [{m['platform']}] [{m['sentiment']}] (影响力:{m.get('influence_score', 0):.1f}) {m['content']}" for m in recent_messages])}
{high_influence_summary}

*基于用户上传的社媒数据，数据质量更高，分析更准确*
"""
                    result_data.append(sentiment_summary)
                    
            except Exception as e:
                logger.warning(f"⚠️ [统一情绪工具] 查询用户上传社媒数据失败: {e}", exc_info=True)
                logger.info(f"🔍 [统一情绪工具] 查询参数: symbol={clean_ticker}, start_time={start_time}, end_time={end_time}")
                # 继续使用备用数据源
            
            # 如果没有用户上传的数据或数据不足，使用备用数据源
            if not user_uploaded_data or len(user_uploaded_data) < 5:
                if user_uploaded_data:
                    logger.info(f"📰 [统一情绪工具] 用户上传数据不足（{len(user_uploaded_data)}条 < 5条），使用备用数据源（新闻）...")
                else:
                    logger.info(f"📰 [统一情绪工具] 未找到用户上传的社媒数据（数据库查询返回0条或查询失败），使用备用数据源（新闻）...")
                try:
                    # 尝试使用 AKShareProvider 获取新闻进行情绪分析
                    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
                    ak_provider = AKShareProvider()
                    
                    # 清理代码后缀
                    clean_ticker = ticker
                    for suffix in ['.SH', '.SZ', '.SS', '.HK', '.XSHE', '.XSHG']:
                        clean_ticker = clean_ticker.replace(suffix, '')
                    
                    # 获取新闻 (优先使用 _get_stock_news_direct 如果公开接口不可用)
                    if hasattr(ak_provider, 'get_stock_news_sync'):
                        news_df = ak_provider.get_stock_news_sync(symbol=clean_ticker)
                    else:
                        news_df = ak_provider._get_stock_news_direct(symbol=clean_ticker)
                    
                    if news_df is not None and not news_df.empty:
                        # 简单分析
                        news_titles = []
                        # 兼容不同的列名
                        col_map = {'新闻标题': 'title', '标题': 'title', 'title': 'title'}
                        
                        for col in news_df.columns:
                            if col in col_map:
                                news_titles = news_df[col].tolist()
                                break
                        
                        if not news_titles and not news_df.empty:
                             # 如果没找到标题列，尝试第一列
                             news_titles = news_df.iloc[:, 0].astype(str).tolist()

                        # 关键词统计
                        pos_words = ['上涨', '利好', '增长', '突破', '买入', '增持', '大涨', '新高', '预增']
                        neg_words = ['下跌', '利空', '减少', '跌破', '卖出', '减持', '大跌', '新低', '亏损']
                        
                        pos_count = 0
                        neg_count = 0
                        
                        recent_titles = news_titles[:10] # 只看最近10条
                        
                        for title in recent_titles:
                            if not isinstance(title, str): continue
                            for w in pos_words:
                                if w in title: pos_count += 1
                            for w in neg_words:
                                if w in title: neg_count += 1
                                
                        sentiment_score = "中性"
                        if pos_count > neg_count: sentiment_score = "偏多"
                        if neg_count > pos_count: sentiment_score = "偏空"
                        
                        news_summary = f"""## 新闻情绪分析（备用数据源）
**股票**: {ticker}
**情绪评级**: {sentiment_score} (正向词:{pos_count}, 负向词:{neg_count})

### 最近新闻摘要
{chr(10).join(['- ' + str(t) for t in recent_titles[:5]])}

*基于最近 {len(recent_titles)} 条新闻标题分析*
"""
                        result_data.append(news_summary)
                    else:
                        if not user_uploaded_data:
                            result_data.append(f"## 中文市场情绪\n暂无相关数据（建议上传社媒数据）")
                            
                except Exception as e:
                    logger.error(f"中文情绪分析失败: {e}")
                    if not user_uploaded_data:
                        result_data.append(f"## 中文市场情绪\n分析失败: {e}，建议上传社媒数据")

        else:
            # 美股：使用Reddit情绪分析
            logger.info(f"🇺🇸 [统一情绪工具] 处理美股情绪...")

            try:
                from tradingagents.dataflows.interface import get_reddit_sentiment

                sentiment_data = get_reddit_sentiment(ticker, curr_date)
                result_data.append(f"## 美股Reddit情绪\n{sentiment_data}")
            except Exception as e:
                result_data.append(f"## 美股Reddit情绪\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 情绪分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的情绪数据源*
"""

        logger.info(f"😊 [统一情绪工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一情绪分析工具执行失败: {str(e)}"
        logger.error(f"❌ [统一情绪工具] {error_msg}")
        return error_msg

