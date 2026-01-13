"""
市场快讯API路由
提供财联社电报、新浪财经、东方财富网等实时快讯接口
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import httpx
import json
import re
import jieba
import jieba.analyse
from collections import Counter

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.core.database import get_mongo_db

router = APIRouter(prefix="/api/market-news", tags=["市场快讯"])
logger = logging.getLogger("webapi")

# 缓存存储（实际生产应使用Redis）
_telegraph_cache = {
    "财联社电报": [],
    "新浪财经": [],
    "东方财富网": []
}
_global_indexes_cache = None
_industry_rank_cache = []

# 缓存时间
_cache_time = {
    "财联社电报": None,
    "新浪财经": None,
    "东方财富网": None
}


async def fetch_cailian_telegraph():
    """获取财联社电报数据"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://www.cls.cn/nodeapi/telegraphList",
                headers={
                    "Referer": "https://www.cls.cn/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            data = response.json()

            telegraphs = []
            if data.get("error") == 0 and data.get("data"):
                roll_data = data["data"].get("roll_data", [])
                for item in roll_data:
                    ctime = item.get("ctime", 0)
                    data_time = datetime.fromtimestamp(ctime)

                    # 获取主题标签
                    subjects = []
                    if item.get("subjects"):
                        subjects = [s.get("subject_name", "") for s in item["subjects"]]

                    telegraphs.append({
                        "id": str(item.get("id", "")),
                        "title": item.get("title", ""),
                        "content": item.get("content", ""),
                        "time": data_time.strftime("%H:%M:%S"),
                        "dataTime": data_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "url": item.get("shareurl", ""),
                        "source": "财联社电报",
                        "isRed": item.get("level") != "C",
                        "subjects": subjects
                    })
            return telegraphs
    except Exception as e:
        logger.error(f"获取财联社电报失败: {e}")
        return []


async def fetch_sina_news():
    """获取新浪财经数据"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            timestamp = int(datetime.now().timestamp())
            url = f"https://zhibo.sina.com.cn/api/zhibo/feed?callback=callback&page=1&page_size=20&zhibo_id=152&tag_id=0&dire=f&dpc=1&type=0&_={timestamp}"

            response = await client.get(
                url,
                headers={
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )

            # 解析JSONP格式
            content = response.text
            content = content.replace("try{callback(", "").replace(");}catch(e){};", "")

            data = json.loads(content)
            telegraphs = []

            if data.get("result") and data["result"].get("data"):
                feed_data = data["result"]["data"].get("feed", {})
                feed_list = feed_data.get("list", [])
                for item in feed_list:
                    rich_text = item.get("rich_text", "")
                    # 从【】中提取标题
                    title_match = re.search(r"【(.*?)】", rich_text)
                    title = title_match.group(1) if title_match else ""

                    create_time = item.get("create_time", "")
                    time_str = create_time.split(" ")[1] if " " in create_time else ""

                    # 获取标签
                    tags = item.get("tag", [])
                    subjects = [t.get("name", "") for t in tags if isinstance(t, dict)]

                    # 检查是否是焦点新闻
                    is_focus = any(s.get("name") == "焦点" for s in tags if isinstance(s, dict))

                    telegraphs.append({
                        "id": str(item.get("id", "")),
                        "title": title,
                        "content": rich_text,
                        "time": time_str,
                        "dataTime": create_time,
                        "source": "新浪财经",
                        "isRed": is_focus,
                        "subjects": subjects
                    })
            return telegraphs
    except Exception as e:
        logger.error(f"获取新浪财经失败: {e}")
        return []


async def fetch_eastmoney_news(limit=50):
    """获取东方财富网新闻数据（使用AKShare）"""
    try:
        import akshare as ak

        # 获取新闻
        df_news = ak.stock_news_em()

        if df_news is None or df_news.empty:
            logger.warning("东方财富网新闻数据为空")
            return []

        telegraphs = []
        for _, row in df_news.head(limit).iterrows():
            try:
                # 解析时间
                publish_time = str(row.get('发布时间') or row.get('time') or '')

                # 尝试解析时间格式
                time_str = publish_time
                data_time = publish_time
                try:
                    if ' ' in publish_time:
                        time_parts = publish_time.split(' ')
                        if len(time_parts) >= 2:
                            time_str = time_parts[1] if ':' in time_parts[1] else publish_time
                except:
                    pass

                title = str(row.get('新闻标题') or row.get('标题') or row.get('title') or '')
                content = title  # 东方财富网新闻只有标题，没有正文
                source = str(row.get('文章来源') or row.get('来源') or row.get('source') or '东方财富网')
                url = str(row.get('新闻链接') or row.get('url') or '')

                telegraphs.append({
                    "id": hash(url) if url else hash(title),
                    "title": title,
                    "content": content,
                    "time": time_str,
                    "dataTime": data_time,
                    "url": url,
                    "source": source,
                    "isRed": False,
                    "subjects": []
                })
            except Exception as e:
                logger.warning(f"解析东方财富网新闻条目失败: {e}")
                continue

        logger.info(f"从东方财富网获取到 {len(telegraphs)} 条新闻")
        return telegraphs

    except ImportError:
        logger.error("AKShare未安装，无法获取东方财富网新闻")
        return []
    except Exception as e:
        logger.error(f"获取东方财富网新闻失败: {e}")
        return []


async def save_news_to_db(news_list: List[Dict], source: str):
    """保存新闻到数据库"""
    try:
        db = get_mongo_db()
        collection = db.market_news

        # 批量插入/更新新闻
        for news in news_list:
            try:
                # 检查是否已存在（根据URL或标题+时间）
                existing = None
                if news.get("url"):
                    existing = await collection.find_one({"url": news["url"]})
                elif news.get("title") and news.get("dataTime"):
                    existing = await collection.find_one({
                        "title": news["title"],
                        "dataTime": news["dataTime"]
                    })

                news_doc = {
                    **news,
                    "source": source,
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now()
                }

                if existing:
                    # 更新已存在的新闻
                    await collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": news_doc}
                    )
                else:
                    # 插入新新闻
                    await collection.insert_one(news_doc)

            except Exception as e:
                logger.warning(f"保存单条新闻失败: {e}")
                continue

        logger.info(f"成功保存 {len(news_list)} 条 {source} 新闻到数据库")

    except Exception as e:
        logger.error(f"保存新闻到数据库失败: {e}")


async def fetch_global_indexes():
    """获取全球股指数据"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rank/indexRankDetail2",
                headers={
                    "Referer": "https://stockapp.finance.qq.com/mstats",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            data = response.json()

            if data.get("data"):
                return data["data"]
            return {}
    except Exception as e:
        logger.error(f"获取全球股指失败: {e}")
        return {}


async def fetch_industry_rank(sort: str = "0", count: int = 150):
    """获取行业排名数据"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://proxy.finance.qq.com/ifzqgtimg/appstock/app/mktHs/rank?l={count}&p=1&t=01/averatio&ordertype=&o={sort}"
            response = await client.get(
                url,
                headers={
                    "Referer": "https://stockapp.finance.qq.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            data = response.json()

            if data.get("data"):
                return data["data"]
            return []
    except Exception as e:
        logger.error(f"获取行业排名失败: {e}")
        return []


@router.get("/telegraph")
async def get_telegraph_list(
    source: str = Query(..., description="新闻来源"),
    current_user: dict = Depends(get_current_user)
):
    """获取电报列表"""
    try:
        # 如果缓存为空或过期，刷新数据
        if not _telegraph_cache.get(source) or (
            _cache_time.get(source) and
            (datetime.now() - _cache_time[source]).seconds > 60
        ):
            await refresh_telegraph_data(source)

        data = _telegraph_cache.get(source, [])
        return ok(data=data, message=f"获取{source}成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/refresh")
async def refresh_telegraph_list(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """刷新电报列表"""
    try:
        source = request.get("source", "财联社电报")
        await refresh_telegraph_data(source)
        data = _telegraph_cache.get(source, [])
        return ok(data=data, message=f"刷新成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")


async def refresh_telegraph_data(source: str):
    """刷新指定来源的数据"""
    if source == "财联社电报":
        news_list = await fetch_cailian_telegraph()
        _telegraph_cache[source] = news_list
        _cache_time[source] = datetime.now()
        # 保存到数据库
        await save_news_to_db(news_list, "财联社电报")
    elif source == "新浪财经":
        news_list = await fetch_sina_news()
        _telegraph_cache[source] = news_list
        _cache_time[source] = datetime.now()
        # 保存到数据库
        await save_news_to_db(news_list, "新浪财经")
    elif source == "东方财富网":
        news_list = await fetch_eastmoney_news()
        _telegraph_cache[source] = news_list
        _cache_time[source] = datetime.now()
        # 保存到数据库
        await save_news_to_db(news_list, "东方财富网")


@router.get("/global-indexes")
async def get_global_stock_indexes(current_user: dict = Depends(get_current_user)):
    """获取全球股指数据"""
    try:
        global _global_indexes_cache
        if _global_indexes_cache is None:
            _global_indexes_cache = await fetch_global_indexes()
        return ok(data=_global_indexes_cache, message="获取成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/industry-rank")
async def get_industry_rank(
    sort: str = Query("0"),
    count: int = Query(150),
    current_user: dict = Depends(get_current_user)
):
    """获取行业排名"""
    try:
        global _industry_rank_cache
        if not _industry_rank_cache:
            _industry_rank_cache = await fetch_industry_rank(sort, count)

        return ok(data=_industry_rank_cache, message="获取成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/keywords")
async def get_news_keywords(
    hours: int = Query(24, description="统计最近多少小时的关键词"),
    top_n: int = Query(50, description="返回前N个关键词"),
    current_user: dict = Depends(get_current_user)
):
    """获取新闻关键词分析"""
    try:
        db = get_mongo_db()
        collection = db.market_news

        # 计算时间范围
        start_time = datetime.now() - timedelta(hours=hours)

        # 从数据库获取最近的新闻
        cursor = await collection.find({
            "createdAt": {"$gte": start_time}
        }).to_list(None)

        # 提取所有标题和内容
        all_text = []
        for news in cursor:
            if news.get("title"):
                all_text.append(news["title"])
            if news.get("content"):
                all_text.append(news["content"])

        # 使用jieba进行关键词分析
        if not all_text:
            return ok(data={"keywords": [], "total_news": 0}, message="暂无新闻数据")

        # 合并所有文本
        combined_text = " ".join(all_text)

        # 提取关键词
        keywords_with_scores = jieba.analyse.extract_tags(combined_text, topK=top_n, withWeight=True)

        keywords = [{"keyword": k, "weight": float(w)} for k, w in keywords_with_scores]

        # 按来源统计新闻数量
        news_by_source = await collection.aggregate([
            {"$match": {"createdAt": {"$gte": start_time}}},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}}
        ]).to_list(None)

        source_stats = {item["_id"]: item["count"] for item in news_by_source}

        return ok(data={
            "keywords": keywords,
            "total_news": len(cursor),
            "source_stats": source_stats,
            "time_range": f"最近{hours}小时"
        }, message="关键词分析完成")

    except Exception as e:
        logger.error(f"关键词分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/ai-summary")
async def ai_summary_market_news(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """AI市场资讯总结"""
    try:
        question = request.get("question", "总结和分析当前股票市场新闻中的投资机会和风险点")
        # TODO: 调用LLM服务生成总结
        summary = _mock_ai_summary(question)
        return ok(data={
            "content": summary["content"],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modelName": summary.get("model", "Qwen2.5-72B")
        }, message="AI总结生成成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


def _mock_ai_summary(question):
    return {
        "content": f"""# 市场资讯总结

## 主要市场动态

1. **A股市场表现积极**：今日市场震荡上行，科技板块表现强势
2. **资金流向**：北向资金净流入超50亿元，显示外资信心
3. **政策环境**：央行继续实施稳健货币政策，流动性充裕

## 投资机会

- **科技板块**：半导体、人工智能概念表现强势，建议关注龙头个股
- **新能源车**：销量持续攀升，行业景气度提升
- **券商板块**：午后异动拉升，可能预示市场情绪好转

## 风险提示

- 外围市场波动，需关注美联储政策动向
- 部分热门板块短期涨幅较大，注意回调风险

*注：本分析基于当前市场公开信息，仅供参考，不构成投资建议。投资需谨慎，风险自担。*
""",
        "model": "Qwen2.5-72B"
    }


@router.get("/grouped")
async def get_grouped_news(
    source: Optional[str] = Query(None, description="新闻来源，不指定则获取所有来源"),
    strategy: str = Query("dynamic_hot", description="排序策略: dynamic_hot(动态热点优先) 或 timeline(时间线优先)"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取分组聚合后的市场新闻

    按照以下逻辑分组:
    1. market_overview: 市场大盘与指标 (影响整个市场的消息)
    2. hot_concepts: 热点概念/题材集群 (当日最活跃的主题投资线)
    3. limit_up: 涨停与资金动向汇总 (涨停板、封单等统计)
    4. stock_alerts: 个股重要公告与异动 (具体公司的公告、龙虎榜等)
    5. fund_movements: 资金动向汇总 (跨越不同板块的综合性资金报告)
    """
    try:
        from app.services.news_grouping_service import group_market_news

        # 收集所有来源的新闻
        all_news = []

        # 如果指定了来源，只获取该来源
        if source:
            if not _telegraph_cache.get(source) or (
                _cache_time.get(source) and
                (datetime.now() - _cache_time[source]).seconds > 60
            ):
                await refresh_telegraph_data(source)
            all_news = _telegraph_cache.get(source, [])
        else:
            # 获取所有来源的新闻
            for src in ["财联社电报", "新浪财经", "东方财富网"]:
                if not _telegraph_cache.get(src) or (
                    _cache_time.get(src) and
                    (datetime.now() - _cache_time[src]).seconds > 60
                ):
                    await refresh_telegraph_data(src)
                all_news.extend(_telegraph_cache.get(src, []))

        # 如果没有新闻，返回空结果
        if not all_news:
            return ok(data={
                "market_overview": [],
                "hot_concepts": [],
                "stock_alerts": [],
                "fund_movements": [],
                "limit_up": [],
                "summary": {
                    "total_news": 0,
                    "market_overview_count": 0,
                    "hot_concept_count": 0,
                    "stock_alert_count": 0,
                    "fund_movement_count": 0,
                    "limit_up_count": 0,
                }
            }, message="暂无新闻数据")

        # 应用分组聚合
        grouped_result = group_market_news(all_news, strategy)

        return ok(data=grouped_result, message="获取分组新闻成功")

    except Exception as e:
        logger.error(f"获取分组新闻失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.post("/refresh-grouped")
async def refresh_grouped_news(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    刷新并获取分组聚合后的市场新闻

    可以指定刷新特定的新闻来源
    """
    try:
        from app.services.news_grouping_service import group_market_news

        source = request.get("source")  # 可选：指定刷新哪个来源
        strategy = request.get("strategy", "dynamic_hot")

        # 刷新指定来源或所有来源
        if source:
            await refresh_telegraph_data(source)
            all_news = _telegraph_cache.get(source, [])
        else:
            for src in ["财联社电报", "新浪财经", "东方财富网"]:
                await refresh_telegraph_data(src)
            all_news = []
            for src in ["财联社电报", "新浪财经", "东方财富网"]:
                all_news.extend(_telegraph_cache.get(src, []))

        # 应用分组聚合
        grouped_result = group_market_news(all_news, strategy)

        return ok(data=grouped_result, message="刷新并获取分组新闻成功")

    except Exception as e:
        logger.error(f"刷新分组新闻失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")


# ==================== 增强数据库 API ====================

@router.on_event("startup")
async def init_news_database():
    """初始化新闻数据库索引"""
    try:
        from app.services.news_database_service import NewsDatabaseService
        await NewsDatabaseService.ensure_indexes()
        logger.info("新闻数据库索引初始化完成")
    except Exception as e:
        logger.warning(f"新闻数据库索引初始化失败: {e}")


@router.get("/analytics")
async def get_news_analytics(
    hours: int = Query(24, description="统计最近多少小时的数据"),
    source: Optional[str] = Query(None, description="指定来源"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取新闻分析数据
    
    返回:
    - 总数统计
    - 来源分布
    - 分类分布
    - 情感分布
    - 热门股票
    - 热门概念
    - 词云数据
    """
    try:
        from app.services.news_database_service import NewsDatabaseService
        from datetime import timedelta
        
        start_date = datetime.now() - timedelta(hours=hours)
        
        sources = [source] if source else None
        analytics = await NewsDatabaseService.get_news_analytics(
            start_date=start_date,
            sources=sources
        )
        
        return ok(data=analytics, message="获取分析数据成功")
        
    except Exception as e:
        logger.error(f"获取新闻分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/enhanced-wordcloud")
async def get_enhanced_wordcloud(
    hours: int = Query(24, description="统计最近多少小时"),
    top_n: int = Query(50, description="返回前N个词"),
    source: Optional[str] = Query(None, description="指定来源"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取增强词云数据
    
    基于数据库中存储的新闻关键词生成词云，支持:
    - 权重计算
    - 分类过滤
    - 时间范围
    """
    try:
        from app.services.news_database_service import NewsDatabaseService
        
        wordcloud_data = await NewsDatabaseService.get_wordcloud_data(
            hours=hours,
            top_n=top_n,
            source=source
        )
        
        return ok(data={
            "words": wordcloud_data,
            "total": len(wordcloud_data),
            "hours": hours,
            "source": source or "全部"
        }, message="获取词云数据成功")
        
    except Exception as e:
        logger.error(f"获取词云数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/search")
async def search_news(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(50, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """
    搜索新闻
    
    支持在标题、内容、关键词、标签中搜索
    """
    try:
        from app.services.news_database_service import NewsDatabaseService
        
        results = await NewsDatabaseService.search_news(
            keyword=keyword,
            limit=limit
        )
        
        return ok(data={
            "keyword": keyword,
            "count": len(results),
            "results": results
        }, message=f"搜索到 {len(results)} 条结果")
        
    except Exception as e:
        logger.error(f"搜索新闻失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/sync-to-enhanced-db")
async def sync_to_enhanced_database(
    hours: int = Query(24, description="同步最近多少小时的数据"),
    current_user: dict = Depends(get_current_user)
):
    """
    将现有数据同步到增强数据库
    
    从market_news集合读取数据，重新提取标签后保存到market_news_enhanced
    """
    try:
        from app.services.news_database_service import NewsDatabaseService
        
        db = get_mongo_db()
        old_collection = db.market_news
        
        # 查询最近的数据
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cursor = old_collection.find({"createdAt": {"$gte": cutoff_time}}).limit(500)
        
        synced_count = 0
        async for doc in cursor:
            source = doc.get("source", "未知")
            news_dict = {
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "url": doc.get("url"),
                "time": doc.get("time", ""),
                "dataTime": doc.get("dataTime"),
                "isRed": doc.get("isRed", False),
                "subjects": doc.get("subjects", [])
            }
            
            count = await NewsDatabaseService.save_news([news_dict], source)
            synced_count += count
        
        return ok(data={
            "synced_count": synced_count,
            "hours": hours
        }, message=f"成功同步 {synced_count} 条数据")
        
    except Exception as e:
        logger.error(f"同步数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")
