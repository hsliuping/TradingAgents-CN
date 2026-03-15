"""
金融知识库初始数据

包含 ~55 条结构化知识文档，分为 4 个类别：
- concept: 金融概念（A 股市场核心知识）~16 条
- tool_guide: 工具使用指南（系统工具最佳实践）~14 条
- methodology: 分析方法论（标准分析流程）~7 条
- pattern: 问题模式映射（常见问题 → 工具映射）~15 条
"""

from typing import List, Dict, Any

# ============================================================
# 金融概念类 (concept) — ~16 条
# ============================================================

CONCEPT_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "concept_sector_system",
        "category": "concept",
        "title": "A股板块体系",
        "content": (
            "A股有三种板块类型（同花顺分类）："
            "行业板块(N)包含行业分类和主题概念板块，如白酒、半导体、光伏设备、华为概念、小米汽车、ChatGPT概念等，"
            "一只股票可同时属于多个行业/概念板块，共400+个板块；"
            "概念板块(S)是统计型板块，如昨日涨停、次新股、QFII重仓等量化筛选板块，共126个；"
            "地域板块(R)按上市公司注册地分类，如浙江板块、深圳板块，共33个。"
            "重要：查询概念股（如小米汽车、华为概念）时应搜索行业板块(N)，不是概念板块(S)。"
            "板块数据来源为同花顺/Tushare。"
        ),
        "tags": ["板块", "行业", "概念", "地域", "同花顺"],
        "priority": 1,
    },
    {
        "id": "concept_stock",
        "category": "concept",
        "title": "概念股",
        "content": (
            "概念股是指属于同花顺行业板块(N类型)中主题概念分类的成分股。"
            "例如'光伏概念股'就是同花顺'光伏概念(885531.TI)'板块下的所有A股公司；"
            "'小米汽车概念股'就是同花顺'小米汽车(886064.TI)'板块下给小米汽车配套的A股上市公司。"
            "查询概念股需要用板块工具搜索对应板块名称（类型N），然后获取成分股列表。"
            "注意：概念板块名称可能与用户描述不完全一致，需要用关键词搜索匹配。"
            "常见概念板块示例：小米概念、小米汽车、华为概念、特斯拉概念、人工智能、AIGC概念、机器人概念、芯片概念、新能源汽车、白酒概念等。"
        ),
        "tags": ["概念股", "板块", "成分股"],
        "priority": 1,
    },
    {
        "id": "concept_leading_stock",
        "category": "concept",
        "title": "龙头股",
        "content": (
            "龙头股是板块内市值最大或涨幅领先的代表性股票，通常具有较强的带动效应。"
            "识别龙头股的方法：查看板块成分股列表，按总市值或流通市值排序取前几名；"
            "或按近期涨幅排序，涨幅领先的是短期龙头。"
            "龙头股变化频繁，需要实时查询板块成分股数据。"
        ),
        "tags": ["龙头股", "板块", "市值"],
        "priority": 2,
    },
    {
        "id": "concept_north_flow",
        "category": "concept",
        "title": "北向资金",
        "content": (
            "北向资金指通过沪深港通从香港流入A股的境外资金。"
            "沪股通买上海市场股票，深股通买深圳市场股票。"
            "北向资金常被称为'聪明钱'，其流入流出被视为重要市场信号。"
            "北向资金净买入增加通常视为看多信号，净卖出增加视为看空信号。"
            "可关注北向资金的每日净流入金额、累计净流入、以及重仓个股变化。"
        ),
        "tags": ["北向资金", "外资", "沪深港通", "聪明钱"],
        "priority": 2,
    },
    {
        "id": "concept_margin_trading",
        "category": "concept",
        "title": "两融（融资融券）",
        "content": (
            "两融指融资融券交易。融资是投资者借钱买股票（看多），融券是借股票卖出（看空）。"
            "融资余额增加表示杠杆资金看多，减少表示去杠杆。"
            "两融数据反映市场风险偏好和杠杆资金动向，是重要的市场情绪指标。"
            "注意：两融余额绝对值意义有限，重点关注边际变化（增减趋势）。"
        ),
        "tags": ["两融", "融资融券", "杠杆", "市场情绪"],
        "priority": 3,
    },
    {
        "id": "concept_limit_up_down",
        "category": "concept",
        "title": "涨跌停制度",
        "content": (
            "A股主板涨跌停幅度为10%（ST股为5%），科创板和创业板为20%，北交所为30%。"
            "涨停表示买盘强劲股价达到当日最大涨幅，跌停表示卖盘强劲达到最大跌幅。"
            "涨停家数与跌停家数的比值是重要的市场情绪指标：涨停家数远多于跌停，市场情绪偏多。"
            "连续涨停称为'连板'，连板高度反映市场投机热度。"
        ),
        "tags": ["涨跌停", "涨停", "跌停", "市场情绪"],
        "priority": 3,
    },
    {
        "id": "concept_a_share_lot_size",
        "category": "concept",
        "title": "A股整手交易与零股规则",
        "content": (
            "A股普通股票交易通常以100股为1手，正常买入和卖出都应按100股整数倍申报。"
            "因此基于仓位比例推导执行建议时，不能直接给出30股、60股、80股这类普通交易无法成交的数量。"
            "只有因配股、送转、拆分等历史原因形成的零股，才可能在卖出时出现不足100股的情况，但这不是常规交易建议的默认前提。"
            "如果需要把比例规则换算成股数，应先结合当前持仓按100股整数倍取整，再说明剩余零头的处理方式。"
        ),
        "tags": ["A股", "整手", "100股", "零股", "交易规则"],
        "priority": 1,
    },
    {
        "id": "concept_pe_pb_roe",
        "category": "concept",
        "title": "核心估值指标PE/PB/ROE",
        "content": (
            "PE(市盈率)=股价/每股收益，反映投资者愿意为每单位收益支付的价格，PE越低估值越便宜（但要结合行业）。"
            "PB(市净率)=股价/每股净资产，适合重资产行业估值，PB<1称为'破净'。"
            "ROE(净资产收益率)=净利润/净资产，衡量公司盈利能力，ROE>15%通常认为较好。"
            "不同行业PE/PB合理区间差异很大：科技股PE通常高于银行股。"
        ),
        "tags": ["PE", "PB", "ROE", "估值", "基本面"],
        "priority": 2,
    },
    {
        "id": "concept_technical_indicators",
        "category": "concept",
        "title": "常用技术指标",
        "content": (
            "MACD(指数平滑异同移动平均线)：判断趋势方向和强度，金叉看多、死叉看空。"
            "RSI(相对强弱指标)：衡量超买超卖，RSI>70超买，RSI<30超卖。"
            "KDJ(随机指标)：判断超买超卖和短期转折，K线上穿D线为金叉。"
            "BOLL(布林带)：判断价格波动区间和支撑压力位，价格触及上轨可能回调，触及下轨可能反弹。"
            "技术指标需要结合使用，单一指标容易产生误判。"
        ),
        "tags": ["MACD", "RSI", "KDJ", "BOLL", "技术分析"],
        "priority": 2,
    },
    {
        "id": "concept_fund_flow",
        "category": "concept",
        "title": "资金流向",
        "content": (
            "资金流向指市场中资金的流入和流出方向，是判断市场热点和情绪的重要依据。"
            "主力资金流入表示大资金看好，流出表示大资金离场。"
            "板块资金流向可以发现当前市场热点板块；个股资金流向可以判断主力动向。"
            "北向资金流向、两融余额变化也是重要的资金面指标。"
        ),
        "tags": ["资金流向", "主力资金", "热点"],
        "priority": 3,
    },
    {
        "id": "concept_market_breadth",
        "category": "concept",
        "title": "市场宽度",
        "content": (
            "市场宽度指上涨和下跌股票的比例，是衡量市场整体健康程度的指标。"
            "当指数上涨但上涨股票数量减少（市场宽度收窄），可能预示上涨动力不足。"
            "涨跌家数比、涨停跌停家数比、量能分布都是市场宽度指标。"
            "健康的上涨应该伴随广泛的个股参与（市场宽度扩大）。"
        ),
        "tags": ["市场宽度", "涨跌比", "大盘"],
        "priority": 3,
    },
    {
        "id": "concept_industry_chain",
        "category": "concept",
        "title": "产业链与供应链",
        "content": (
            "产业链指一个产业从原材料到终端产品的完整链条。"
            "例如新能源汽车产业链包含：上游（锂矿、钴矿）→ 中游（电池、电机）→ 下游（整车、充电桩）。"
            "产业链分析有助于理解行业上下游关系和利润分配。"
            "在A股中，产业链相关公司通常归入同一个概念板块，可通过搜索概念板块获取产业链公司。"
        ),
        "tags": ["产业链", "供应链", "上下游"],
        "priority": 3,
    },
    {
        "id": "concept_sector_rotation",
        "category": "concept",
        "title": "板块轮动",
        "content": (
            "板块轮动指市场热点在不同板块之间切换的现象。"
            "典型轮动规律：经济复苏期看金融地产 → 扩张期看消费科技 → 过热期看周期资源 → 衰退期看防御性板块。"
            "观察板块轮动可通过资金流向排名、板块涨跌幅排名来判断。"
            "短期轮动（日内/周级别）更多受资金和情绪驱动，长期轮动与经济周期相关。"
        ),
        "tags": ["板块轮动", "热点", "经济周期"],
        "priority": 3,
    },
    {
        "id": "concept_financial_reports",
        "category": "concept",
        "title": "A股财报披露",
        "content": (
            "A股上市公司需定期披露财务报告：年报(1-4月底)、一季报(4月底前)、半年报(8月底前)、三季报(10月底前)。"
            "财报包含利润表（营收、净利润）、资产负债表（资产、负债）、现金流量表（经营/投资/筹资现金流）。"
            "财报季通常伴随较大的股价波动，业绩超预期可能带来上涨，不及预期可能下跌。"
            "分析财报重点关注：营收增长率、净利润增长率、毛利率变化、现金流质量。"
        ),
        "tags": ["财报", "年报", "季报", "财务分析"],
        "priority": 2,
    },
    {
        "id": "concept_index",
        "category": "concept",
        "title": "A股主要指数",
        "content": (
            "上证指数(000001)：上海交易所全部A股加权指数，反映沪市整体走势。"
            "深证成指(399001)：深圳交易所成分股指数。"
            "创业板指(399006)：创业板代表性指数，偏成长风格。"
            "沪深300(000300)：沪深两市最大300只股票，代表大盘蓝筹。"
            "中证500(000905)：中盘股代表。中证1000(000852)：小盘股代表。"
            "科创50(000688)：科创板代表。"
        ),
        "tags": ["指数", "上证", "深证", "沪深300", "创业板"],
        "priority": 2,
    },
    {
        "id": "concept_financial_statements",
        "category": "concept",
        "title": "三大财务报表",
        "content": (
            "上市公司三大核心财务报表：利润表、资产负债表、现金流量表。"
            "利润表反映公司一段时间内的经营成果，核心指标：营业收入、净利润、毛利率、净利率、费用率。"
            "资产负债表反映公司某一时点的财务状况，核心指标：总资产、总负债、资产负债率、流动比率、速动比率。"
            "现金流量表反映公司现金的来源和去向，分三部分：经营活动现金流（核心造血能力）、"
            "投资活动现金流（资本开支和投资）、筹资活动现金流（融资和分红）。"
            "分析财务报表要三表联动：利润表看盈利能力，资产负债表看财务安全，现金流量表验证盈利质量。"
            "自由现金流 = 经营现金流 + 投资现金流，是衡量公司真实造血能力的关键指标。"
            "系统提供 5 个专项财务工具：get_income_analysis（利润表）、get_balance_sheet_analysis（资产负债表）、"
            "get_cashflow_analysis（现金流）、get_dividend_data（分红）、get_main_business（主营构成），"
            "可按需精确获取某一类财务数据。"
        ),
        "tags": ["财务报表", "利润表", "资产负债表", "现金流量表", "财务分析"],
        "priority": 1,
    },
    {
        "id": "concept_dividend_strategy",
        "category": "concept",
        "title": "分红投资策略与进场时机",
        "content": (
            "高分红股票投资策略核心知识："
            "一、分红关键时间节点：年报发布（3-4月）→ 分红预案公告 → 股东大会通过 → 股权登记日 → 除权除息日 → 派息日。"
            "二、进场时机分析："
            "1) 最佳布局期：年报预告/快报发布后（1-3月），确认业绩和分红能力，此时市场尚未充分反映分红预期，提前2-3个月布局；"
            "2) 分红预案公告前1-2周：散户和短线资金开始抢权，推高股价，机构投资者通常更早布局；"
            "3) 除权除息日前后：除息日股价会自动下调（扣除分红金额），短期看似'亏损'，但长期来看优质高分红股会'填权'（股价回升至除息前水平）；"
            "4) 不建议在除权除息日前几天追高买入，容易买在'抢权行情'的高点。"
            "三、填权与贴权："
            "填权指除息后股价逐步回升至除息前水平，说明公司基本面好、市场认可；"
            "贴权指除息后股价继续下跌，说明市场对公司前景不看好。优质高分红股更容易填权。"
            "四、分红税收规则（A股）："
            "持股超过1年：免征红利税；持股1个月-1年：按10%征收；持股不足1个月：按20%征收。"
            "因此长期持有高分红股税收成本最低，短期进出反而不划算。"
            "五、选股标准："
            "1) 连续3年以上稳定分红；2) 股息率 > 3%（优秀 > 5%）；"
            "3) 分红比例30%-70%为宜（过高可能不可持续）；4) 经营现金流充裕（分红来源于真实利润）；"
            "5) 所在行业成熟稳定（如银行、公用事业、消费等）。"
            "六、稳健投资者建议：在年报季（3-4月）筛选连续高分红股，在确认分红方案后逐步建仓，"
            "持有超过1年以上享受免税分红，通过'股息再投资'实现复利增长。"
        ),
        "tags": ["分红", "股息", "投资策略", "进场时机", "除权除息", "填权", "高分红"],
        "priority": 1,
    },
]


# ============================================================
# 工具使用指南类 (tool_guide) — ~14 条
# ============================================================

TOOL_GUIDE_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "tool_analyze_sector_by_name",
        "category": "tool_guide",
        "title": "analyze_sector_by_name 工具指南",
        "content": (
            "analyze_sector_by_name 是一站式板块综合分析工具，传入 sector_name（板块名称关键词）即可。"
            "适用场景：'XX板块前景'、'XX概念股分析'、'XX行业投资机会'、'XX板块龙头'。"
            "该工具会自动搜索匹配的板块，获取板块走势、成分股、资金流向等综合信息。"
            "参数 sector_name 应传入用户提到的板块/行业/概念关键词，无需传入股票代码。"
            "如果用户问'XX概念股有哪些'，也可以用这个工具，它会返回成分股列表。"
        ),
        "tags": ["板块", "工具", "analyze_sector_by_name"],
        "priority": 1,
    },
    {
        "id": "tool_get_sector_constituents",
        "category": "tool_guide",
        "title": "get_sector_constituents 工具指南",
        "content": (
            "get_sector_constituents 获取板块成分股列表，参数 sector_name 传入板块名称关键词。"
            "适用场景：'XX概念股有哪些'、'XX板块有哪些股票'、'XX板块龙头是谁'。"
            "返回结果包含成分股代码、名称、市值等信息，可按市值排序找龙头。"
            "注意：如果搜索不到完全匹配的板块，会返回最接近的匹配结果。"
        ),
        "tags": ["板块", "成分股", "工具", "get_sector_constituents"],
        "priority": 1,
    },
    {
        "id": "tool_search_sector",
        "category": "tool_guide",
        "title": "search_sector 工具指南",
        "content": (
            "search_sector 根据关键词搜索匹配的板块列表，参数 sector_name 传入搜索关键词。"
            "适用场景：不确定具体板块名称时先搜索，或者查看与某关键词相关的所有板块。"
            "返回匹配的板块列表（包含板块代码、名称、类型），可据此选择具体板块进一步分析。"
            "搜索关键词越精确匹配越好，如搜索'光伏'比'新能源'更精确。"
        ),
        "tags": ["板块", "搜索", "工具", "search_sector"],
        "priority": 2,
    },
    {
        "id": "tool_stock_fundamentals",
        "category": "tool_guide",
        "title": "get_stock_fundamentals_unified 工具指南",
        "content": (
            "get_stock_fundamentals_unified 获取个股基本面数据，参数 ticker 传入 6 位股票代码。"
            "返回数据包含：PE/PB/ROE 等估值指标、营收/净利润等财务数据、行业对比等。"
            "适用场景：分析某只股票的估值是否合理、财务状况是否健康。"
            "注意：ticker 必须是 6 位数字代码（如 601012），不能传入股票名称。"
        ),
        "tags": ["基本面", "个股", "工具", "get_stock_fundamentals_unified"],
        "priority": 1,
    },
    {
        "id": "tool_technical_indicators",
        "category": "tool_guide",
        "title": "get_technical_indicators 工具指南",
        "content": (
            "get_technical_indicators 获取个股技术指标，参数 ticker 传入股票代码。"
            "返回 MACD、RSI、KDJ、BOLL 等常用技术指标数据。"
            "适用场景：判断某只股票的技术面走势、超买超卖状态、支撑压力位。"
            "建议与行情数据(get_stock_market_data_unified)配合使用，全面分析技术面。"
        ),
        "tags": ["技术指标", "个股", "工具", "get_technical_indicators"],
        "priority": 2,
    },
    {
        "id": "tool_china_market_overview",
        "category": "tool_guide",
        "title": "get_china_market_overview 工具指南",
        "content": (
            "get_china_market_overview 获取A股市场整体概况，无需传入股票代码。"
            "返回各大指数涨跌、涨跌家数、成交额等市场宏观数据。"
            "适用场景：用户问'大盘怎么样'、'今天市场行情'、'整体市场环境'。"
            "该工具提供市场全貌快照，适合作为分析起点。"
        ),
        "tags": ["大盘", "市场", "工具", "get_china_market_overview"],
        "priority": 1,
    },
    {
        "id": "tool_north_flow",
        "category": "tool_guide",
        "title": "get_north_flow 工具指南",
        "content": (
            "get_north_flow 获取北向资金（沪深港通）流入流出数据。"
            "返回每日北向资金净流入/流出金额、沪股通和深股通分别的数据。"
            "适用场景：用户问'北向资金'、'外资动向'、'沪深港通资金'。"
            "北向资金大幅流入通常被视为积极信号。"
        ),
        "tags": ["北向资金", "外资", "工具", "get_north_flow"],
        "priority": 2,
    },
    {
        "id": "tool_fund_flow_data",
        "category": "tool_guide",
        "title": "get_fund_flow_data 工具指南",
        "content": (
            "get_fund_flow_data 获取板块或个股资金流向数据。"
            "适用场景：'板块资金流向排名'、'主力资金流入流出'、'市场热点板块'。"
            "通过资金流向可以发现当前市场最受关注的板块和个股。"
            "主力资金净流入排名靠前的板块/个股通常是近期热点。"
        ),
        "tags": ["资金流向", "主力", "工具", "get_fund_flow_data"],
        "priority": 2,
    },
    {
        "id": "tool_peer_comparison",
        "category": "tool_guide",
        "title": "get_peer_comparison 工具指南",
        "content": (
            "get_peer_comparison 进行同行业对比分析，参数 ticker 传入股票代码。"
            "返回同行业公司的估值对比（PE/PB）、盈利对比（ROE/毛利率）、成长对比（营收/利润增速）。"
            "适用场景：'XX和YY哪个好'、'XX在行业中排名'、'同行业对比'。"
            "对比分析有助于判断个股在行业中的相对位置。"
        ),
        "tags": ["对比", "同业", "工具", "get_peer_comparison"],
        "priority": 2,
    },
    {
        "id": "tool_get_income_analysis",
        "category": "tool_guide",
        "title": "get_income_analysis 利润表分析工具指南",
        "content": (
            "get_income_analysis 分析股票的利润表核心指标，参数 ticker 传入 6 位股票代码（如 600519）。"
            "返回数据包含：营业收入、净利润、毛利率、净利率、费用率（销售/管理/研发/财务费用率）等，"
            "支持最近 N 个季度的多期趋势展示。参数 periods 控制分析期数，默认 8 个季度。"
            "适用场景：'茅台营收利润增长怎么样'、'最近几年利润趋势'、'毛利率净利率多少'、'盈利能力分析'。"
            "与 get_stock_fundamentals_unified 的区别：本工具专注利润表细节，提供更详细的多期趋势和费用结构分析。"
            "数据来源为 Tushare 利润表(income)和财务指标(fina_indicator)，优先从 MongoDB 缓存读取。"
        ),
        "tags": ["利润表", "财务分析", "工具", "get_income_analysis", "营收", "净利润", "毛利率"],
        "priority": 1,
    },
    {
        "id": "tool_get_balance_sheet_analysis",
        "category": "tool_guide",
        "title": "get_balance_sheet_analysis 资产负债表分析工具指南",
        "content": (
            "get_balance_sheet_analysis 分析股票的资产负债表，参数 ticker 传入 6 位股票代码。"
            "返回数据包含：总资产、总负债、净资产、资产负债率、流动比率、速动比率、"
            "资产结构（货币资金、应收账款、存货、固定资产等占比）。支持多期趋势展示。"
            "适用场景：'资产负债率高不高'、'现金储备够不够'、'财务是否健康'、'偿债能力分析'。"
            "参数 periods 控制分析期数，默认 8 个季度。"
            "重点关注：资产负债率是否超过行业均值、流动比率是否 > 1、货币资金能否覆盖短期负债。"
        ),
        "tags": ["资产负债表", "财务分析", "工具", "get_balance_sheet_analysis", "负债率", "偿债能力"],
        "priority": 1,
    },
    {
        "id": "tool_get_cashflow_analysis",
        "category": "tool_guide",
        "title": "get_cashflow_analysis 现金流量表分析工具指南",
        "content": (
            "get_cashflow_analysis 分析股票的现金流量表，参数 ticker 传入 6 位股票代码。"
            "返回数据包含：经营活动现金流(OCF)、投资活动现金流(ICF)、筹资活动现金流(FCF)、"
            "自由现金流(OCF+ICF)、现金流质量（经营现金流/净利润比值）。支持多期趋势展示。"
            "适用场景：'经营现金流好不好'、'自由现金流充裕吗'、'现金流质量如何'、'公司造血能力'。"
            "参数 periods 控制分析期数，默认 8 个季度。"
            "优质公司特征：经营现金流持续为正、自由现金流充裕、OCF/净利润 > 1（盈利质量高）。"
        ),
        "tags": ["现金流", "财务分析", "工具", "get_cashflow_analysis", "自由现金流", "经营现金流"],
        "priority": 1,
    },
    {
        "id": "tool_get_dividend_data",
        "category": "tool_guide",
        "title": "get_dividend_data 分红送股数据工具指南",
        "content": (
            "get_dividend_data 获取股票的历史分红送股数据，参数 ticker 传入 6 位股票代码。"
            "返回数据包含：每年的现金分红（每股派息）、送股比例、转增比例、股权登记日、除权除息日、派息日。"
            "参数 years 控制查询年数，默认 5 年。"
            "适用场景：'最近几年分红情况'、'股息率多少'、'分红比例'、'分红送股历史'、'高分红股票'。"
            "数据来源为 Tushare dividend 接口（需 2000 积分以上权限）。"
            "分析分红数据时关注：连续分红年数、股息率稳定性、分红比例是否合理（30%-70%为宜）。"
            "配合 get_income_analysis 和 get_cashflow_analysis 可以判断分红的可持续性。"
        ),
        "tags": ["分红", "股息", "工具", "get_dividend_data", "送股", "派息"],
        "priority": 1,
    },
    {
        "id": "tool_get_main_business",
        "category": "tool_guide",
        "title": "get_main_business 主营业务构成工具指南",
        "content": (
            "get_main_business 获取股票的主营业务收入构成，参数 ticker 传入 6 位股票代码。"
            "返回数据包含：按产品/业务分类的收入金额、收入占比、毛利率；按地区分类的收入分布。"
            "参数 periods 控制分析期数，默认 4 期。"
            "适用场景：'主营业务构成'、'收入来源结构'、'各业务占比'、'毛利率最高的业务'。"
            "数据来源为 Tushare fina_mainbz 接口。"
            "分析主营业务可了解公司核心竞争力和收入多元化程度。"
        ),
        "tags": ["主营业务", "收入构成", "工具", "get_main_business", "业务结构"],
        "priority": 1,
    },
]



# ============================================================
# 分析方法论类 (methodology) — ~7 条
# ============================================================

METHODOLOGY_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "method_sector_analysis",
        "category": "methodology",
        "title": "板块分析标准流程",
        "content": (
            "板块分析标准流程：1) 用 analyze_sector_by_name 获取板块整体概况（走势、涨跌幅、成交额）；"
            "2) 用 get_sector_constituents 查看板块成分股，按市值排序找出龙头股；"
            "3) 用 get_sector_daily 查看板块近期走势和趋势方向；"
            "4) 对重点龙头股用 get_stock_fundamentals_unified 做基本面深入分析；"
            "5) 用 get_fund_flow_data 查看板块资金流向，判断资金关注度。"
        ),
        "tags": ["板块分析", "方法论", "流程"],
        "priority": 1,
    },
    {
        "id": "method_stock_analysis",
        "category": "methodology",
        "title": "个股综合分析标准流程",
        "content": (
            "个股综合分析流程：1) 基本面概览：用 get_stock_fundamentals_unified 获取 PE/PB/ROE 等估值指标快速判断；"
            "2) 财务深度（可选）：如需深入分析，用 get_income_analysis 看利润趋势、get_balance_sheet_analysis 看负债水平、"
            "get_cashflow_analysis 看现金流质量、get_dividend_data 看分红历史、get_main_business 看业务结构；"
            "3) 技术面：用 get_technical_indicators 获取 MACD/RSI/KDJ/BOLL，判断趋势和超买超卖；"
            "4) 行情面：用 get_stock_market_data_unified 获取价格走势和成交量，观察量价配合；"
            "5) 消息面：用 get_stock_news_unified 获取相关新闻，了解近期事件和情绪；"
            "6) 综合判断：结合基本面估值+技术面趋势+消息面催化，给出全面分析。"
            "建议并行获取数据以提高效率。基本面概览够用时不必调用全部财务细分工具。"
        ),
        "tags": ["个股分析", "方法论", "流程"],
        "priority": 1,
    },
    {
        "id": "method_market_analysis",
        "category": "methodology",
        "title": "大盘/市场分析标准流程",
        "content": (
            "大盘分析流程：1) 用 get_china_market_overview 获取市场全景（指数涨跌、涨跌家数、成交额）；"
            "2) 用 get_limit_stats 查看涨停跌停情况，判断市场情绪；"
            "3) 用 get_fund_flow_data 查看板块资金流向排名，发现当日热点；"
            "4) 用 get_north_flow 查看北向资金动向，判断外资态度；"
            "5) 综合以上数据给出市场整体判断：趋势、情绪、热点、资金面。"
        ),
        "tags": ["大盘", "市场分析", "方法论"],
        "priority": 1,
    },
    {
        "id": "method_comparison",
        "category": "methodology",
        "title": "个股对比分析流程",
        "content": (
            "对比分析流程：1) 用 get_peer_comparison 获取同行业对比数据；"
            "2) 对比维度：估值（PE/PB哪个更便宜）、盈利（ROE/毛利率谁更强）、"
            "成长性（营收/利润增速谁更快）、市值规模；"
            "3) 用 get_stock_fundamentals_unified 分别获取详细基本面做深度对比；"
            "4) 总结各公司优劣势，不做买卖推荐，只呈现客观数据对比。"
        ),
        "tags": ["对比分析", "方法论", "同业"],
        "priority": 2,
    },
    {
        "id": "method_concept_stock_query",
        "category": "methodology",
        "title": "概念股查询流程",
        "content": (
            "概念股查询流程：1) 用 analyze_sector_by_name 或 get_sector_constituents 传入概念关键词；"
            "2) 系统会自动搜索同花顺行业板块(N类型，包含所有概念板块)并返回匹配结果；"
            "3) 如果需要详细了解某只概念股，再用个股分析工具深入分析；"
            "4) 注意：概念板块名称可能与用户表述不同，如用户说'小米概念'对应板块名可能是'小米汽车'。"
            "关键词匹配不到时，尝试缩短关键词重新搜索。"
        ),
        "tags": ["概念股", "查询", "方法论"],
        "priority": 1,
    },
    {
        "id": "method_financial_deep_analysis",
        "category": "methodology",
        "title": "财务深度分析流程",
        "content": (
            "财务深度分析流程（适用于需要详细了解公司财务状况的场景）："
            "1) 盈利能力：用 get_income_analysis 查看营收利润趋势、毛利率/净利率变化、费用结构；"
            "2) 财务安全：用 get_balance_sheet_analysis 查看资产负债率、流动比率、资产结构，判断偿债能力；"
            "3) 现金质量：用 get_cashflow_analysis 查看经营/投资/筹资现金流，计算自由现金流和 OCF/净利润比值；"
            "4) 业务结构：用 get_main_business 查看收入来源构成和各业务毛利率，了解核心竞争力；"
            "5) 分红能力：用 get_dividend_data 查看历史分红情况，判断公司回报股东的意愿和能力；"
            "6) 综合判断：盈利持续增长 + 负债率合理 + 现金流充裕 + 主营业务清晰 + 稳定分红 = 财务优质公司。"
            "如只需快速概览，用 get_stock_fundamentals_unified 即可，无需逐一调用 5 个细分工具。"
        ),
        "tags": ["财务分析", "方法论", "深度分析", "流程"],
        "priority": 1,
    },
    {
        "id": "method_dividend_analysis",
        "category": "methodology",
        "title": "分红投资分析流程",
        "content": (
            "分红投资分析流程（适用于'高分红股票怎么选'、'什么时候买分红股'等问题）："
            "1) 用 get_dividend_data 获取目标股票近 5 年分红记录，确认是否连续分红、股息率水平；"
            "2) 用 get_income_analysis 确认利润是否稳定增长（分红的基础是持续盈利）；"
            "3) 用 get_cashflow_analysis 确认经营现金流充裕（确保分红来自真实利润而非借债分红）；"
            "4) 用 get_balance_sheet_analysis 确认负债率合理（高负债公司分红不可持续）；"
            "5) 评估进场时机：最佳布局期为年报季（3-4月）确认分红方案后、除息日前 2-3 个月逐步建仓；"
            "避免在除息日前几天追高（抢权行情风险大）。"
            "6) 持有建议：持股超 1 年免征红利税，配合股息再投资实现复利。"
        ),
        "tags": ["分红", "投资分析", "方法论", "高分红", "进场时机"],
        "priority": 1,
    },
]


# ============================================================
# 问题模式映射类 (pattern) — ~15 条
# ============================================================

PATTERN_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "pattern_concept_stock",
        "category": "pattern",
        "title": "概念股查询模式",
        "content": (
            "用户问'XX概念股有哪些'、'XX概念股'、'XX相关股票'时，属于概念股查询。"
            "核心工具：get_sector_constituents(sector_name=XX) 或 analyze_sector_by_name(sector_name=XX)。"
            "不需要 ticker 参数，直接用概念关键词搜索。"
            "示例：'小米汽车概念股' → sector_name='小米汽车'；'光伏概念股' → sector_name='光伏'。"
        ),
        "tags": ["概念股", "模式", "板块"],
        "priority": 1,
    },
    {
        "id": "pattern_sector_analysis",
        "category": "pattern",
        "title": "板块分析模式",
        "content": (
            "用户问'XX板块怎么样'、'XX行业前景'、'XX板块投资机会'时，属于板块分析。"
            "核心工具：analyze_sector_by_name(sector_name=XX关键词)。"
            "该工具会综合返回板块走势、成分股、资金流向等信息。"
            "如需更深入分析，可追加 get_sector_daily 和 get_fund_flow_data。"
        ),
        "tags": ["板块分析", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_market_overview",
        "category": "pattern",
        "title": "大盘/市场概览模式",
        "content": (
            "用户问'大盘怎么样'、'今天市场行情'、'整体市场'、'A股走势'时，属于市场概览。"
            "核心工具：get_china_market_overview（市场全景）。"
            "补充工具：get_limit_stats（涨跌停统计）、get_fund_flow_data（资金流向）。"
            "如用户关心外资则加 get_north_flow。"
        ),
        "tags": ["大盘", "市场", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_stock_analysis",
        "category": "pattern",
        "title": "个股分析模式",
        "content": (
            "用户问'XX股票怎么样'、'帮我分析XX'、'XX值不值得买'时，属于个股分析。"
            "需要 ticker（股票代码），如果用户只给了名称，需要先查找代码。"
            "推荐并行调用：get_stock_fundamentals_unified + get_stock_market_data_unified + "
            "get_technical_indicators + get_stock_news_unified。"
        ),
        "tags": ["个股", "分析", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_comparison",
        "category": "pattern",
        "title": "个股对比模式",
        "content": (
            "用户问'XX和YY哪个好'、'XX对比YY'、'同行业对比'时，属于对比分析。"
            "核心工具：get_peer_comparison(ticker=XX代码)。"
            "补充：get_stock_fundamentals_unified 分别获取各公司基本面。"
        ),
        "tags": ["对比", "模式"],
        "priority": 2,
    },
    {
        "id": "pattern_north_flow",
        "category": "pattern",
        "title": "北向资金查询模式",
        "content": (
            "用户问'北向资金'、'外资动向'、'沪深港通'、'外资在买什么'时，属于北向资金查询。"
            "核心工具：get_north_flow。"
            "可配合 get_china_market_overview 了解市场背景。"
        ),
        "tags": ["北向资金", "外资", "模式"],
        "priority": 2,
    },
    {
        "id": "pattern_technical_analysis",
        "category": "pattern",
        "title": "技术分析模式",
        "content": (
            "用户问'XX技术面'、'XX支撑位压力位'、'XX MACD/KDJ'时，属于技术分析。"
            "核心工具：get_technical_indicators(ticker=XX代码)。"
            "补充：get_stock_market_data_unified 获取K线走势配合分析。"
        ),
        "tags": ["技术分析", "模式"],
        "priority": 2,
    },
    {
        "id": "pattern_hot_sector",
        "category": "pattern",
        "title": "热点板块查询模式",
        "content": (
            "用户问'今天什么板块热'、'热点板块'、'资金在流向哪'、'板块轮动'时，属于热点板块查询。"
            "核心工具：get_fund_flow_data（板块资金流向排名）。"
            "补充：get_china_market_overview 了解整体市场背景、get_limit_stats 看涨停板集中的板块。"
        ),
        "tags": ["热点", "板块", "资金", "模式"],
        "priority": 2,
    },
    {
        "id": "pattern_margin_trading",
        "category": "pattern",
        "title": "两融查询模式",
        "content": (
            "用户问'融资余额'、'两融数据'、'杠杆资金'时，属于两融查询。"
            "核心工具：get_margin_trading。"
            "两融数据反映杠杆资金动向，融资余额增加表示看多情绪上升。"
        ),
        "tags": ["两融", "融资融券", "模式"],
        "priority": 3,
    },
    {
        "id": "pattern_limit_stats",
        "category": "pattern",
        "title": "涨跌停统计模式",
        "content": (
            "用户问'今天涨停多少家'、'跌停情况'、'连板高度'、'市场情绪'时，属于涨跌停统计。"
            "核心工具：get_limit_stats。"
            "涨停家数vs跌停家数的比值是重要的市场情绪指标。连板高度反映投机热度。"
        ),
        "tags": ["涨跌停", "市场情绪", "模式"],
        "priority": 3,
    },
    {
        "id": "pattern_income_profit",
        "category": "pattern",
        "title": "利润/营收分析模式",
        "content": (
            "用户问'营收利润增长怎么样'、'利润趋势'、'毛利率多少'、'净利率'、'盈利能力'、"
            "'费用率'、'营收增速'时，属于利润表分析。"
            "核心工具：get_income_analysis(ticker=股票代码, periods=8)。"
            "该工具返回详细的利润表多期趋势，包含毛利率、净利率、费用结构等。"
            "如果只需快速概览，get_stock_fundamentals_unified 也包含基本盈利指标。"
        ),
        "tags": ["利润", "营收", "毛利率", "净利率", "盈利", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_financial_health",
        "category": "pattern",
        "title": "财务健康/资产负债分析模式",
        "content": (
            "用户问'资产负债率高不高'、'财务是否健康'、'负债情况'、'现金储备'、"
            "'偿债能力'、'流动比率'时，属于资产负债表分析。"
            "核心工具：get_balance_sheet_analysis(ticker=股票代码)。"
            "返回资产负债率、流动比率、速动比率、资产结构等多维度分析。"
            "如果同时关心现金流，配合 get_cashflow_analysis 使用。"
        ),
        "tags": ["负债率", "财务健康", "资产负债", "偿债", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_cashflow_query",
        "category": "pattern",
        "title": "现金流分析模式",
        "content": (
            "用户问'现金流好不好'、'自由现金流'、'经营现金流'、'造血能力'、"
            "'现金流质量'时，属于现金流量表分析。"
            "核心工具：get_cashflow_analysis(ticker=股票代码)。"
            "返回经营/投资/筹资三大现金流、自由现金流、OCF/净利润比值等。"
            "现金流是验证盈利质量的关键指标：有利润但没有现金流入可能存在问题。"
        ),
        "tags": ["现金流", "自由现金流", "经营现金流", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_dividend_query",
        "category": "pattern",
        "title": "分红/股息查询模式",
        "content": (
            "用户问'分红情况'、'股息率'、'分红比例'、'送股转增'、'高分红股票'、"
            "'分红什么时候进场'、'除权除息'时，属于分红分析。"
            "核心工具：get_dividend_data(ticker=股票代码, years=5)。"
            "如果用户问投资策略（如'高分红股票什么时候买'），需要结合分红投资策略知识回答，"
            "包括：最佳布局期（年报季3-4月）、避免除息前追高、持股超1年免红利税等。"
            "配合 get_income_analysis 和 get_cashflow_analysis 可判断分红可持续性。"
        ),
        "tags": ["分红", "股息", "除权除息", "高分红", "模式"],
        "priority": 1,
    },
    {
        "id": "pattern_main_business",
        "category": "pattern",
        "title": "主营业务查询模式",
        "content": (
            "用户问'主营业务是什么'、'收入来源'、'业务构成'、'各产品占比'、"
            "'靠什么赚钱'时，属于主营业务分析。"
            "核心工具：get_main_business(ticker=股票代码)。"
            "返回按产品和地区分类的收入构成及各业务毛利率。"
            "了解公司主营业务有助于判断核心竞争力和未来增长潜力。"
        ),
        "tags": ["主营业务", "收入构成", "业务结构", "模式"],
        "priority": 1,
    },
]


# ============================================================
# 汇总所有知识文档
# ============================================================

def get_all_knowledge_documents() -> List[Dict[str, Any]]:
    """返回所有知识文档的列表"""
    return (
        CONCEPT_DOCUMENTS
        + TOOL_GUIDE_DOCUMENTS
        + METHODOLOGY_DOCUMENTS
        + PATTERN_DOCUMENTS
    )
