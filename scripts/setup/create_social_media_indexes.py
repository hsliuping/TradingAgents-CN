"""
创建社媒消息集合的数据库索引
优化查询性能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_indexes():
    """创建社媒消息集合的索引"""
    try:
        # 连接数据库
        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB]
        collection = db.social_media_messages

        logger.info("🔄 开始创建社媒消息集合索引...")

        # 1. 唯一索引：message_id + platform + symbol（防止重复）
        # 🔥 将symbol也作为唯一性的一部分，这样同一个消息ID和平台，如果股票代码不同，会被视为不同的消息
        try:
            # 先删除旧的唯一索引（如果存在）
            try:
                collection.drop_index("idx_message_id_platform")
                logger.info("🔄 删除旧唯一索引: message_id + platform")
            except:
                pass
            
            collection.create_index(
                [("message_id", 1), ("platform", 1), ("symbol", 1)],
                unique=True,
                name="idx_message_id_platform_symbol"
            )
            logger.info("✅ 创建唯一索引: message_id + platform + symbol")
        except Exception as e:
            logger.warning(f"⚠️ 唯一索引创建失败（可能已存在或数据冲突）: {e}")
            logger.info("   提示：如果数据中存在重复的message_id+platform但symbol不同，需要先清理数据")

        # 2. 股票代码索引（最常用查询）
        collection.create_index(
            [("symbol", 1), ("publish_time", -1)],
            name="idx_symbol_publish_time"
        )
        logger.info("✅ 创建索引: symbol + publish_time")
        
        # 2.1 市场类型索引
        collection.create_index(
            [("market", 1), ("publish_time", -1)],
            name="idx_market_publish_time"
        )
        logger.info("✅ 创建索引: market + publish_time")
        
        # 2.2 股票代码+市场类型索引
        collection.create_index(
            [("symbol", 1), ("market", 1), ("publish_time", -1)],
            name="idx_symbol_market_time"
        )
        logger.info("✅ 创建索引: symbol + market + publish_time")

        # 3. 平台索引
        collection.create_index(
            [("platform", 1), ("publish_time", -1)],
            name="idx_platform_publish_time"
        )
        logger.info("✅ 创建索引: platform + publish_time")

        # 4. 情绪索引
        collection.create_index(
            [("sentiment", 1), ("publish_time", -1)],
            name="idx_sentiment_publish_time"
        )
        logger.info("✅ 创建索引: sentiment + publish_time")

        # 5. 发布时间索引（用于时间范围查询）
        collection.create_index(
            [("publish_time", -1)],
            name="idx_publish_time"
        )
        logger.info("✅ 创建索引: publish_time")

        # 6. 作者影响力索引
        collection.create_index(
            [("author.influence_score", -1)],
            name="idx_author_influence"
        )
        logger.info("✅ 创建索引: author.influence_score")

        # 7. 互动率索引
        collection.create_index(
            [("engagement.engagement_rate", -1)],
            name="idx_engagement_rate"
        )
        logger.info("✅ 创建索引: engagement.engagement_rate")

        # 8. 关键词索引（用于关键词搜索）
        collection.create_index(
            [("keywords", 1)],
            name="idx_keywords"
        )
        logger.info("✅ 创建索引: keywords")

        # 9. 话题标签索引
        collection.create_index(
            [("hashtags", 1)],
            name="idx_hashtags"
        )
        logger.info("✅ 创建索引: hashtags")

        # 10. 全文搜索索引（用于内容搜索）
        try:
            collection.create_index(
                [("content", "text"), ("keywords", "text"), ("hashtags", "text")],
                name="idx_text_search",
                default_language="none"  # 中文全文搜索
            )
            logger.info("✅ 创建全文搜索索引: content + keywords + hashtags")
        except Exception as e:
            logger.warning(f"⚠️ 全文搜索索引创建失败（可能已存在）: {e}")

        # 11. 复合索引：股票 + 平台 + 时间（常用组合查询）
        collection.create_index(
            [("symbol", 1), ("platform", 1), ("publish_time", -1)],
            name="idx_symbol_platform_time"
        )
        logger.info("✅ 创建复合索引: symbol + platform + publish_time")

        # 12. 数据来源索引
        collection.create_index(
            [("data_source", 1), ("publish_time", -1)],
            name="idx_data_source_time"
        )
        logger.info("✅ 创建索引: data_source + publish_time")

        # 获取索引列表
        indexes = collection.list_indexes()
        index_list = [idx['name'] for idx in indexes]
        
        logger.info(f"✅ 索引创建完成！当前共有 {len(index_list)} 个索引:")
        for idx_name in index_list:
            logger.info(f"   - {idx_name}")

        return True

    except Exception as e:
        logger.error(f"❌ 创建索引失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = create_indexes()
    sys.exit(0 if success else 1)

