"""stock_news_cn 能力：A股个股新闻（实时快照事件流）

粒度 stock_event：单只股票的新闻条目列表（事件流，非时间序列）。

数据口径：
- 两源适配器均委托各自 provider 高层方法 get_stock_news（保留重试/
  Docker curl_cffi 回退/多源轮询/权限检测语义），高层方法已输出收敛的
  结构化 Dict 列表（title/content/publish_time 等），适配器包装为
  DataFrame 交门面标准化。
- tushare 新闻接口为付费功能：无权限时高层方法返回 None，经门面
  契约降级到下一源（akshare 免费源接管）。

媒体源命名约定：新闻条目自带"媒体来源"（新浪财经/东方财富/央视财经），
与门面附加的数据来源标记列 source（tushare/akshare）同名冲突——门面
标准化会无条件覆盖 source 列，故两源均注册 field_mapping
{"source": "media_source"}，把媒体来源改名为 media_source 后再进入
标准化（rename 发生在门面附加 source 之前，语义无损）。

排序约定：publish_time 降序（最新在前）——tushare 高层方法按
publish_time 倒序排序，akshare 东财接口原生最新在前。

参数口径：
- hours_back 为 tushare 语义（回溯小时数，默认 24）；akshare 东财
  接口无时间窗口参数（原生返回最新新闻），实现内忽略该参数。
- keywords 字段值实为关键词列表（list），DataFrame 中以 object 列承载。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_NEWS_CN_SCHEMA = CapabilitySchema(
    capability_id="stock_news_cn",
    grain=GRAIN_STOCK_EVENT,
    description="A股个股新闻（结构化条目：标题/正文/发布时间/媒体来源/情绪等，按 publish_time 降序）",
    fields=[
        CapabilityField("title", "str", True, "新闻标题（两源均过滤空标题）"),
        CapabilityField("content", "str", False, "新闻正文"),
        CapabilityField("summary", "str", False, "新闻摘要（tushare 为正文前 200 字截断）"),
        CapabilityField("url", "str", False, "新闻链接（tushare 新闻接口不提供，为空串）"),
        CapabilityField("media_source", "str", False, "媒体来源（新浪财经/东方财富/央视财经等，经 field_mapping 从 source 改名）"),
        CapabilityField("author", "str", False, "作者（tushare 无，空串）"),
        CapabilityField("publish_time", "date", False, "发布时间（datetime 类型，已由高层方法解析）"),
        CapabilityField("category", "str", False, "新闻分类（高层方法内部分类器输出）"),
        CapabilityField("sentiment", "str", False, "情绪标签（positive/neutral/negative）"),
        CapabilityField("sentiment_score", "float", False, "情绪得分（akshare 输出；tushare 无，NaN）"),
        CapabilityField("keywords", "str", False, "关键词列表（值实为 list，object 列承载）"),
        CapabilityField("importance", "str", False, "重要性（high/medium/low）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字或带交易所后缀）"),
        CapabilityParam("limit", "int", False, "返回条数上限（默认 10）"),
        CapabilityParam("hours_back", "int", False, "回溯小时数（tushare 语义，默认 24；akshare 实现内忽略）"),
    ],
)

register_schema(STOCK_NEWS_CN_SCHEMA)
