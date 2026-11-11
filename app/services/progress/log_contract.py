"""进度日志文案契约表（显式契约，见 docs/05-design/v4.0/logging-governance.md §5.2）。

⚠️ 契约约定：前端进度条靠正则解析日志文案驱动（ProgressLogHandler）。
**修改下列任一日志文案（或新增进度阶段）必须同步修改本表**，否则前端进度条会静默失效。
把隐性契约集中成显性契约，是日志文案清理/规范化的前提（解锁反向依赖）。

中期规划（§5.2）：进度事件迁移为结构化字段（logger extra 带 event），届时本表整体废弃。
"""

# 日志文案 → 前端进度展示（匹配顺序即优先级，正则对 message 小写后匹配）
PROGRESS_LOG_PATTERNS: dict[str, str] = {
    # 基础阶段
    r"验证.*股票代码|检查.*数据源": "📋 准备阶段",
    r"检查.*API.*密钥|环境.*配置": "🔧 环境检查",
    r"预估.*成本|成本.*估算": "💰 成本估算",
    r"配置.*参数|参数.*设置": "⚙️ 参数设置",
    r"初始化.*引擎|启动.*引擎": "🚀 启动引擎",

    # 分析师阶段
    r"市场分析师.*开始|开始.*市场分析|市场.*数据.*分析": "📊 市场分析师正在分析",
    r"基本面分析师.*开始|开始.*基本面分析|财务.*数据.*分析": "💼 基本面分析师正在分析",
    r"新闻分析师.*开始|开始.*新闻分析|新闻.*数据.*分析": "📰 新闻分析师正在分析",
    r"社交媒体分析师.*开始|开始.*社交媒体分析|情绪.*分析": "💬 社交媒体分析师正在分析",

    # 研究团队阶段
    r"看涨研究员|多头研究员|bull.*researcher|积极证据研究员": "🐂 积极证据研究员构建论据",
    r"看跌研究员|空头研究员|bear.*researcher|谨慎证据研究员": "🐻 谨慎证据研究员识别风险",
    r"研究.*辩论|辩论.*开始|debate.*start|多情景研究": "🎯 多情景研究进行中",
    r"研究经理|research.*manager|研究整合员": "👔 研究整合员汇总",

    # 研究整合阶段
    r"交易员.*决策|trader.*decision|制定.*交易策略|研究整合员.*汇总|研究整合.*意见": "🧩 研究整合员汇总",

    # 风险管理阶段
    r"激进.*风险|risky.*risk|高弹性情景": "🔥 高弹性情景研究",
    r"保守.*风险|conservative.*risk|防御情景": "🛡️ 防御情景研究",
    r"中性.*风险|neutral.*risk|基准情景": "⚖️ 基准情景研究",
    r"风险经理|risk.*manager|风险评估师": "🎯 风险评估师形成结论",

    # 最终阶段
    r"信号处理|signal.*process|结果处理": "📡 结果处理",
    r"生成.*报告|report.*generat": "📊 生成研究报告",
    r"分析.*完成|analysis.*complet": "✅ 研究完成",
}

# 只有包含这些关键词的日志才会进入契约匹配（快速预筛）
PROGRESS_KEYWORDS: tuple[str, ...] = (
    "开始", "完成", "分析", "处理", "执行", "生成",
    "start", "complete", "analysis", "process", "execute", "generate",
)

# 需要挂载进度日志处理器的 logger 名称（tradingagents 域固定名 logger）
MONITORED_LOGGERS: tuple[str, ...] = (
    "agents",
    "tradingagents",
    "agents.analysts",
    "agents.researchers",
    "agents.traders",
    "agents.managers",
    "agents.risk_mgmt",
)
