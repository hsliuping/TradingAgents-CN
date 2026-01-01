"""
社媒消息数据模型
用于验证和格式化社媒消息数据
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class AuthorInfo(BaseModel):
    """作者信息"""
    author_id: str = Field(..., description="作者ID")
    author_name: str = Field(..., description="作者名称")
    verified: bool = Field(default=False, description="是否认证")
    influence_score: Optional[float] = Field(default=0.0, description="影响力评分")
    followers_count: Optional[int] = Field(default=0, description="粉丝数")
    avatar_url: Optional[str] = Field(default=None, description="头像URL")


class EngagementInfo(BaseModel):
    """互动数据"""
    views: int = Field(default=0, description="浏览量")
    likes: int = Field(default=0, description="点赞数")
    shares: int = Field(default=0, description="转发/分享数")
    comments: int = Field(default=0, description="评论数")
    engagement_rate: Optional[float] = Field(default=0.0, description="互动率")


class SocialMediaMessageModel(BaseModel):
    """社媒消息数据模型（用于验证）"""
    message_id: str = Field(..., description="消息ID，唯一标识")
    platform: str = Field(..., description="平台类型：weibo/wechat/douyin/xiaohongshu/zhihu/twitter/reddit")
    symbol: str = Field(..., description="股票代码")
    market: Optional[str] = Field(default=None, description="市场类型：A股/港股/美股（可选，会根据股票代码自动识别）")
    message_type: str = Field(default="post", description="消息类型：post/comment/repost/reply")
    content: str = Field(..., description="消息内容")
    media_urls: Optional[List[str]] = Field(default=[], description="媒体URL列表")
    hashtags: Optional[List[str]] = Field(default=[], description="话题标签列表")
    author: AuthorInfo = Field(..., description="作者信息")
    engagement: EngagementInfo = Field(default_factory=EngagementInfo, description="互动数据")
    publish_time: datetime = Field(..., description="发布时间")
    sentiment: Optional[str] = Field(default="neutral", description="情绪：positive/negative/neutral")
    sentiment_score: Optional[float] = Field(default=0.0, ge=-1.0, le=1.0, description="情绪评分：-1到1")
    keywords: Optional[List[str]] = Field(default=[], description="关键词列表")
    topics: Optional[List[str]] = Field(default=[], description="话题列表")
    importance: Optional[str] = Field(default="low", description="重要性：low/medium/high")
    credibility: Optional[str] = Field(default="medium", description="可信度：low/medium/high")
    location: Optional[Dict[str, str]] = Field(default=None, description="地理位置信息")
    language: str = Field(default="none", description="语言代码（MongoDB文本索引支持：none/english/spanish/french/german/portuguese/russian/chinese）")
    data_source: str = Field(default="manual", description="数据来源：manual/crawler/api")
    crawler_version: Optional[str] = Field(default="1.0", description="爬虫版本")

    @validator('platform')
    def validate_platform(cls, v):
        """验证平台类型"""
        valid_platforms = ['weibo', 'wechat', 'douyin', 'xiaohongshu', 'zhihu', 'twitter', 'reddit', 'xueqiu', 'eastmoney']
        if v.lower() not in valid_platforms:
            raise ValueError(f"平台类型必须是以下之一: {', '.join(valid_platforms)}")
        return v.lower()

    @validator('message_type')
    def validate_message_type(cls, v):
        """验证消息类型"""
        valid_types = ['post', 'comment', 'repost', 'reply', 'article', 'video']
        if v.lower() not in valid_types:
            raise ValueError(f"消息类型必须是以下之一: post, comment, repost, reply, article, video")
        return v.lower()

    @validator('sentiment')
    def validate_sentiment(cls, v):
        """验证情绪类型"""
        if v and v.lower() not in ['positive', 'negative', 'neutral']:
            raise ValueError("情绪类型必须是: positive, negative, neutral")
        return v.lower() if v else 'neutral'

    @validator('importance')
    def validate_importance(cls, v):
        """验证重要性"""
        if v and v.lower() not in ['low', 'medium', 'high']:
            raise ValueError("重要性必须是: low, medium, high")
        return v.lower() if v else 'low'
    
    @validator('market')
    def validate_market(cls, v):
        """验证市场类型"""
        if v:
            valid_markets = ['A股', '港股', '美股', 'china_a', 'hong_kong', 'us']
            if v not in valid_markets:
                # 尝试标准化
                v_lower = v.lower()
                if v_lower in ['a股', 'china', 'china_a', 'cn']:
                    return 'A股'
                elif v_lower in ['港股', 'hong_kong', 'hk', 'hongkong']:
                    return '港股'
                elif v_lower in ['美股', 'us', 'usa', 'america']:
                    return '美股'
                else:
                    raise ValueError(f"市场类型必须是以下之一: A股, 港股, 美股")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于保存到数据库）"""
        result = self.dict()
        # 处理嵌套对象
        if isinstance(result.get('author'), dict):
            result['author'] = result['author']
        if isinstance(result.get('engagement'), dict):
            result['engagement'] = result['engagement']
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialMediaMessageModel':
        """从字典创建模型实例"""
        # 处理嵌套对象
        if 'author' in data and isinstance(data['author'], dict):
            data['author'] = AuthorInfo(**data['author'])
        if 'engagement' in data and isinstance(data['engagement'], dict):
            data['engagement'] = EngagementInfo(**data['engagement'])
        return cls(**data)

