"""
市场快讯分组聚合服务
实现新闻的智能分组、聚合和排序
"""
import re
import jieba
import jieba.analyse
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger("webapi")


class NewsGroupingService:
    """新闻分组聚合服务"""

    # 股票代码模式 (6位数字)
    STOCK_CODE_PATTERN = re.compile(r'\b(\d{6})\b')

    # 股票名称模式 (匹配中文股票名，2-4个汉字)
    STOCK_NAME_PATTERN = re.compile(r'([\u4e00-\u9fa5]{2,4})(?:\(|（)\d{6}(?:\)|）)')

    # 概念/板块关键词模式
    CONCEPT_PATTERNS = [
        r'([\u4e00-\u9fa5]+)概念(?:上涨|涨|跌|回调)',
        r'([\u4e00-\u9fa5]+)板块(?:上涨|涨|跌|回调)',
        r'([\u4e00-\u9fa5]+)主题(?:活跃|异动)',
    ]

    # 资金类型关键词
    FUND_KEYWORDS = {
        '主力资金': ['主力资金', '大单', '超大单'],
        '杠杆资金': ['两融', '融资融券', '融资客', '杠杆资金'],
        '北向资金': ['北向资金', '外资', '沪股通', '深股通'],
        '龙虎榜': ['龙虎榜', '涨停', '跌停'],
        '机构资金': ['机构', '基金', '社保', 'QFII'],
    }

    # 市场状态关键词
    MARKET_STATUS_KEYWORDS = {
        '涨停': ['涨停', '封板'],
        '跌停': ['跌停'],
        '连阳': ['连阳', '连涨'],
        '连阴': ['连阴', '连跌'],
        '创新高': ['创新高', '历史新高', '阶段新高'],
        '创新低': ['创新低', '历史新低', '阶段新低'],
    }

    # 市场大盘关键词
    MARKET_OVERVIEW_KEYWORDS = [
        'A股', '两市', '大盘', '沪指', '深指', '创业板', '科创板',
        '成交额', '成交量', '万亿', '两融余额',
    ]

    # 涨停板相关关键词
    LIMIT_UP_KEYWORDS = ['涨停', '封单', '封板', '连板', '一字板']

    @classmethod
    def extract_entities(cls, title: str, content: str = "") -> Dict[str, Any]:
        """
        从新闻标题和内容中提取实体信息

        返回:
        {
            'stocks': [{'code': '002131', 'name': '利欧股份'}],
            'sectors': ['半导体', '新能源车'],
            'concepts': ['AI应用', 'ChatGPT'],
            'fund_types': ['主力资金', '杠杆资金'],
            'market_status': ['涨停', '连阳'],
            'is_market_overview': bool,
            'is_limit_up_related': bool,
            'limit_data': {'count': 57, 'amount': 1000000000}  # 解析涨停数量/金额
        }
        """
        entities = {
            'stocks': [],
            'sectors': [],
            'concepts': [],
            'fund_types': [],
            'market_status': [],
            'is_market_overview': False,
            'is_limit_up_related': False,
            'limit_data': {},
        }

        full_text = f"{title} {content}"

        # 1. 提取股票代码和名称
        # 匹配 "股票名(代码)" 或 "股票名（代码）"
        stock_matches = cls.STOCK_NAME_PATTERN.findall(full_text)
        for name in stock_matches:
            # 尝试从文本中找到对应的代码
            code_match = re.search(rf'{name}[（(](\d{{6}})[）)]', full_text)
            if code_match:
                entities['stocks'].append({
                    'code': code_match.group(1),
                    'name': name
                })

        # 匹配单独的股票代码
        standalone_codes = cls.STOCK_CODE_PATTERN.findall(full_text)
        for code in standalone_codes:
            # 检查是否已经匹配过
            if not any(s['code'] == code for s in entities['stocks']):
                entities['stocks'].append({
                    'code': code,
                    'name': None
                })

        # 2. 提取概念/板块 (使用jieba分词+关键词匹配)
        words = jieba.cut(full_text)
        concept_keywords = [
            '半导体', '新能源车', 'AI应用', 'ChatGPT', '多模态AI',
            '快手', '小红书', '电商', '社交媒体', '人工智能',
            '芯片', '锂电池', '光伏', '风电', '储能',
            '医药', '生物', '疫苗', '医疗器械',
            '军工', '航空航天', '卫星',
            '金融', '银行', '证券', '保险',
            '地产', '建筑', '建材',
            '白酒', '食品', '农业',
        ]

        for word in words:
            if word in concept_keywords:
                if word not in entities['concepts']:
                    entities['concepts'].append(word)

        # 使用模式匹配提取概念
        for pattern in cls.CONCEPT_PATTERNS:
            matches = re.findall(pattern, full_text)
            for match in matches:
                if match not in entities['concepts']:
                    entities['concepts'].append(match)

        # 3. 提取资金类型
        for fund_type, keywords in cls.FUND_KEYWORDS.items():
            for keyword in keywords:
                if keyword in full_text:
                    if fund_type not in entities['fund_types']:
                        entities['fund_types'].append(fund_type)
                    break

        # 4. 提取市场状态
        for status, keywords in cls.MARKET_STATUS_KEYWORDS.items():
            for keyword in keywords:
                if keyword in full_text:
                    if status not in entities['market_status']:
                        entities['market_status'].append(status)
                    break

        # 5. 判断是否为市场大盘新闻
        for keyword in cls.MARKET_OVERVIEW_KEYWORDS:
            if keyword in title:
                entities['is_market_overview'] = True
                break

        # 6. 判断是否为涨停板相关新闻，并提取数据
        for keyword in cls.LIMIT_UP_KEYWORDS:
            if keyword in title:
                entities['is_limit_up_related'] = True
                break

        # 提取涨停数量
        count_match = re.search(r'(\d+)只?[股家].*?涨停', full_text)
        if count_match:
            entities['limit_data']['count'] = int(count_match.group(1))

        # 提取封单金额
        amount_match = re.search(r'封单.*?(\d+\.?\d*)[万亿]', full_text)
        if amount_match:
            amount_str = amount_match.group(1)
            if '亿' in amount_match.group(0):
                entities['limit_data']['amount'] = float(amount_str) * 100000000
            elif '万' in amount_match.group(0):
                entities['limit_data']['amount'] = float(amount_str) * 10000

        return entities

    @classmethod
    def classify_news_type(cls, entities: Dict[str, Any]) -> str:
        """
        根据提取的实体对新闻进行分类

        返回分类:
        - 'market_overview': 市场大盘与指标
        - 'hot_concept': 热点概念/题材集群
        - 'stock_alert': 个股重要公告与异动
        - 'fund_movement': 资金动向汇总
        - 'limit_up': 涨停板相关
        """
        # 优先级判断
        if entities['is_market_overview']:
            return 'market_overview'

        if entities['is_limit_up_related']:
            return 'limit_up'

        # 如果有明确的概念关键词
        if entities['concepts'] and not entities['stocks']:
            return 'hot_concept'

        # 如果有具体股票
        if entities['stocks']:
            if entities['fund_types'] or entities['market_status']:
                return 'stock_alert'
            return 'stock_alert'

        # 如果主要是资金相关
        if entities['fund_types'] and len(entities['fund_types']) >= 2:
            return 'fund_movement'

        # 默认为概念类
        return 'hot_concept'

    @classmethod
    def calculate_hotness_score(cls, news: Dict[str, Any], entities: Dict[str, Any]) -> float:
        """
        计算新闻的热度分数

        综合考虑:
        - 是否有涨停数据 (权重: 30)
        - 资金类型数量 (权重: 10/种)
        - 概念数量 (权重: 5/个)
        - 是否为市场大盘 (权重: 20)
        - 股票数量 (权重: 3/只)
        """
        score = 0.0

        # 涨停数据加分
        if entities.get('limit_data', {}).get('count'):
            score += 30
        if entities.get('limit_data', {}).get('amount'):
            score += 20

        # 资金类型加分
        score += len(entities['fund_types']) * 10

        # 概念加分
        score += len(entities['concepts']) * 5

        # 市场大盘加分
        if entities['is_market_overview']:
            score += 20

        # 股票加分
        score += len(entities['stocks']) * 3

        # 市场状态加分
        score += len(entities['market_status']) * 5

        return score

    @classmethod
    def group_news(cls, news_list: List[Dict[str, Any]], strategy: str = "dynamic_hot") -> Dict[str, Any]:
        """
        对新闻列表进行分组聚合

        Args:
            news_list: 原始新闻列表
            strategy: 排序策略 ("dynamic_hot" 或 "timeline")

        Returns:
        {
            'market_overview': [...],
            'hot_concepts': [
                {
                    'concept_name': 'AI应用',
                    'news': [...],
                    'stats': {'count': 5, 'total_score': 150}
                },
                ...
            ],
            'stock_alerts': [...],
            'fund_movements': [...],
            'limit_up': [...],
            'summary': {...}
        }
        """
        # 为每条新闻提取实体并分类
        processed_news = []
        for news in news_list:
            entities = cls.extract_entities(
                news.get('title', ''),
                news.get('content', '')
            )
            news_type = cls.classify_news_type(entities)
            hotness_score = cls.calculate_hotness_score(news, entities)

            processed_news.append({
                **news,
                '_entities': entities,
                '_type': news_type,
                '_hotness_score': hotness_score
            })

        # 按类型分组
        groups = {
            'market_overview': [],
            'hot_concepts': defaultdict(list),
            'stock_alerts': [],
            'fund_movements': [],
            'limit_up': [],
        }

        for news in processed_news:
            news_type = news['_type']

            if news_type == 'market_overview':
                groups['market_overview'].append(news)
            elif news_type == 'hot_concept':
                # 按概念分组
                concepts = news['_entities']['concepts']
                if concepts:
                    # 使用第一个概念作为主概念
                    main_concept = concepts[0]
                    groups['hot_concepts'][main_concept].append(news)
                else:
                    # 没有明确概念的，归为"其他"
                    groups['hot_concepts']['其他'].append(news)
            elif news_type == 'stock_alert':
                groups['stock_alerts'].append(news)
            elif news_type == 'fund_movement':
                groups['fund_movements'].append(news)
            elif news_type == 'limit_up':
                groups['limit_up'].append(news)

        # 对每个分组内的新闻按时间排序
        for group_name in ['market_overview', 'stock_alerts', 'fund_movements', 'limit_up']:
            groups[group_name].sort(
                key=lambda x: x.get('dataTime', ''),
                reverse=True
            )

        # 处理热点概念分组
        hot_concepts_list = []
        for concept_name, concept_news in groups['hot_concepts'].items():
            # 计算该概念的总热度
            total_score = sum(n['_hotness_score'] for n in concept_news)

            # 按时间排序
            concept_news.sort(
                key=lambda x: x.get('dataTime', ''),
                reverse=True
            )

            hot_concepts_list.append({
                'concept_name': concept_name,
                'news': concept_news,
                'stats': {
                    'count': len(concept_news),
                    'total_score': total_score,
                    'avg_score': total_score / len(concept_news) if concept_news else 0
                }
            })

        # 构建结果
        result = {
            'market_overview': groups['market_overview'],
            'hot_concepts': hot_concepts_list,
            'stock_alerts': groups['stock_alerts'],
            'fund_movements': groups['fund_movements'],
            'limit_up': groups['limit_up'],
            'summary': {
                'total_news': len(news_list),
                'market_overview_count': len(groups['market_overview']),
                'hot_concept_count': len(hot_concepts_list),
                'stock_alert_count': len(groups['stock_alerts']),
                'fund_movement_count': len(groups['fund_movements']),
                'limit_up_count': len(groups['limit_up']),
            }
        }

        # 应用排序策略
        if strategy == "dynamic_hot":
            # 动态热点优先：按平均热度排序概念
            result['hot_concepts'].sort(
                key=lambda x: x['stats']['avg_score'],
                reverse=True
            )
        else:
            # 时间线优先：按最新新闻时间排序
            result['hot_concepts'].sort(
                key=lambda x: x['news'][0].get('dataTime', '') if x['news'] else '',
                reverse=True
            )

        return result


# 便捷函数
def extract_news_entities(title: str, content: str = "") -> Dict[str, Any]:
    """提取新闻实体"""
    return NewsGroupingService.extract_entities(title, content)


def group_market_news(news_list: List[Dict[str, Any]], strategy: str = "dynamic_hot") -> Dict[str, Any]:
    """对市场新闻进行分组聚合"""
    return NewsGroupingService.group_news(news_list, strategy)
