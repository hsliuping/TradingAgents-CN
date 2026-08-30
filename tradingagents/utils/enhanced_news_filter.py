"""
增强新闻过滤器 - 集成规则过滤
本地语义模型（sentence-transformers）与本地分类模型（transformers/torch）已移除，
统一使用远程 API 方案，此处仅保留规则过滤。
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# 导入基础过滤器
from .news_filter import NewsRelevanceFilter, create_news_filter, get_company_name

logger = logging.getLogger(__name__)

class EnhancedNewsFilter(NewsRelevanceFilter):
    """增强新闻过滤器（基于规则过滤）"""

    def __init__(self, stock_code: str, company_name: str, use_semantic: bool = True, use_local_model: bool = False):
        """
        初始化增强过滤器

        Args:
            stock_code: 股票代码
            company_name: 公司名称
            use_semantic: 已废弃（本地语义模型已移除，忽略该参数）
            use_local_model: 已废弃（本地分类模型已移除，忽略该参数）
        """
        super().__init__(stock_code, company_name)
        # 本地语义/分类模型（sentence-transformers / transformers / torch）已移除，
        # 仅保留规则过滤。保留参数以兼容旧调用方，但不再加载本地模型。
        self.use_semantic = False
        self.use_local_model = False

    def calculate_enhanced_relevance_score(self, title: str, content: str) -> Dict[str, float]:
        """
        计算增强相关性评分（当前仅规则过滤）

        Args:
            title: 新闻标题
            content: 新闻内容

        Returns:
            Dict: 包含各种评分的字典
        """
        # 1. 基础规则评分
        rule_score = super().calculate_relevance_score(title, content)

        # 本地语义/分类模型已移除，评分固定为 0（保持最终评分权重与历史一致）
        semantic_score = 0
        classification_score = 0

        # 2. 综合评分（加权平均）
        weights = {
            'rule': 0.4,          # 规则过滤权重40%
            'semantic': 0.35,     # 语义相似度权重35%（已移除）
            'classification': 0.25  # 分类模型权重25%（已移除）
        }

        final_score = (
            weights['rule'] * rule_score +
            weights['semantic'] * semantic_score +
            weights['classification'] * classification_score
        )

        logger.debug(f"[增强过滤器] 综合评分 - 规则:{rule_score:.1f}, "
                    f"语义:{semantic_score:.1f}, 分类:{classification_score:.1f}, 最终:{final_score:.1f}")

        return {
            'rule_score': rule_score,
            'semantic_score': semantic_score,
            'classification_score': classification_score,
            'final_score': final_score,
        }

    def filter_news_enhanced(self, news_df: pd.DataFrame, min_score: float = 40) -> pd.DataFrame:
        """
        增强新闻过滤

        Args:
            news_df: 原始新闻DataFrame
            min_score: 最低综合评分阈值

        Returns:
            pd.DataFrame: 过滤后的新闻DataFrame，包含详细评分信息
        """
        if news_df.empty:
            logger.warning("[增强过滤器] 输入新闻DataFrame为空")
            return news_df

        logger.info(f"[增强过滤器] 开始增强过滤，原始数量: {len(news_df)}条，最低评分阈值: {min_score}")

        filtered_news = []

        for idx, row in news_df.iterrows():
            title = row.get('新闻标题', row.get('标题', ''))
            content = row.get('新闻内容', row.get('内容', ''))

            # 计算增强评分
            scores = self.calculate_enhanced_relevance_score(title, content)

            if scores['final_score'] >= min_score:
                row_dict = row.to_dict()
                row_dict.update(scores)  # 添加所有评分信息
                filtered_news.append(row_dict)

                logger.debug(f"[增强过滤器] 保留新闻 (综合评分: {scores['final_score']:.1f}): {title[:50]}...")
            else:
                logger.debug(f"[增强过滤器] 过滤新闻 (综合评分: {scores['final_score']:.1f}): {title[:50]}...")

        # 创建过滤后的DataFrame
        if filtered_news:
            filtered_df = pd.DataFrame(filtered_news)
            # 按综合评分排序
            filtered_df = filtered_df.sort_values('final_score', ascending=False)
            logger.info(f"[增强过滤器] 增强过滤完成，保留 {len(filtered_df)}条 新闻")
        else:
            filtered_df = pd.DataFrame()
            logger.warning(f"[增强过滤器] 所有新闻都被过滤，无符合条件的新闻")

        return filtered_df


def create_enhanced_news_filter(ticker: str, use_semantic: bool = True, use_local_model: bool = False) -> EnhancedNewsFilter:
    """
    创建增强新闻过滤器的便捷函数

    Args:
        ticker: 股票代码
        use_semantic: 已废弃（本地语义模型已移除，忽略该参数）
        use_local_model: 已废弃（本地分类模型已移除，忽略该参数）

    Returns:
        EnhancedNewsFilter: 配置好的增强过滤器实例
    """
    company_name = get_company_name(ticker)
    return EnhancedNewsFilter(ticker, company_name, use_semantic, use_local_model)


# 使用示例
if __name__ == "__main__":
    # 测试增强过滤器
    import pandas as pd

    # 模拟新闻数据
    test_news = pd.DataFrame([
        {
            '新闻标题': '招商银行发布2024年第三季度业绩报告',
            '新闻内容': '招商银行今日发布第三季度财报，净利润同比增长8%，资产质量持续改善...'
        },
        {
            '新闻标题': '上证180ETF指数基金（530280）自带杠铃策略',
            '新闻内容': '数据显示，上证180指数前十大权重股分别为贵州茅台、招商银行600036...'
        },
        {
            '新闻标题': '银行ETF指数(512730)多只成分股上涨',
            '新闻内容': '银行板块今日表现强势，招商银行、工商银行等多只成分股上涨...'
        },
        {
            '新闻标题': '招商银行与某科技公司签署战略合作协议',
            '新闻内容': '招商银行宣布与知名科技公司达成战略合作，将在数字化转型方面深度合作...'
        }
    ])

    print("=== 测试增强新闻过滤器 ===")

    # 创建增强过滤器（仅使用规则过滤，避免模型依赖）
    enhanced_filter = create_enhanced_news_filter('600036', use_semantic=False, use_local_model=False)

    # 过滤新闻
    filtered_news = enhanced_filter.filter_news_enhanced(test_news, min_score=30)

    print(f"原始新闻: {len(test_news)}条")
    print(f"过滤后新闻: {len(filtered_news)}条")

    if not filtered_news.empty:
        print("\n过滤后的新闻:")
        for _, row in filtered_news.iterrows():
            print(f"- {row['新闻标题']} (综合评分: {row['final_score']:.1f})")
            print(f"  规则评分: {row['rule_score']:.1f}, 语义评分: {row['semantic_score']:.1f}, 分类评分: {row['classification_score']:.1f}")
