"""
初始化行业分析配置

预置 37 个 A 股主要行业大类的分析维度、关键指标、分析重点与可比公司。
行业分类依据 Tushare stock_basic_info 的 industry 字段，按业务模式与分析框架相近原则合并。

集合: industry_analysis_profiles

用法:
    python scripts/init_industry_analysis_profiles.py
    python scripts/init_industry_analysis_profiles.py --force  # 覆盖已有配置
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── 金融（4 个）────────────────────────────────────────────────

BANK_PROFILE = {
    "industry": "银行",
    "display_name": "银行业",
    "analysis_dimensions": [
        {"name": "净息差(NIM)", "description": "银行核心盈利能力指标，反映资产端收益率与负债端成本之差。降息周期下NIM承压，关注资产负债结构对冲能力", "importance": "critical", "data_source": "fundamentals"},
        {"name": "不良贷款率", "description": "资产质量核心指标，关注五级分类迁移趋势、不良生成率及核销转出节奏", "importance": "critical", "data_source": "fundamentals"},
        {"name": "拨备覆盖率", "description": "风险缓冲厚度，拨备越厚盈利调节空间越大，但过高可能暗示隐藏利润", "importance": "high", "data_source": "fundamentals"},
        {"name": "资本充足率", "description": "监管核心约束，决定分红与规模扩张天花板。关注核心一级资本充足率与TLAC达标进度", "importance": "high", "data_source": "fundamentals"},
        {"name": "ROE/ROA", "description": "股东回报率。银行ROE持续下行是全行业趋势，关注ROE是否高于权益成本", "importance": "high", "data_source": "fundamentals"},
        {"name": "信贷投放增速", "description": "反映实体信贷需求和银行风险偏好。关注对公/零售结构变化及普惠小微占比", "importance": "medium", "data_source": "fundamentals"},
        {"name": "中间业务收入占比", "description": "财富管理、结算清算、投行等非息收入占比，衡量轻资产转型进度", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "银行业分析应重点关注利率环境变化对NIM的影响、信贷投放节奏与结构、资产质量变化趋势（特别是地产和城投敞口）、以及监管政策对资本金和业务结构的约束。同时需关注存款定期化趋势对负债成本的影响。",
    "key_metrics": ["NIM", "不良率", "拨备覆盖率", "ROE", "核心一级资本充足率", "贷存比", "非息收入占比", "成本收入比"],
    "comparable_companies": ["招商银行", "兴业银行", "平安银行", "宁波银行", "邮储银行"],
}

SECURITIES_PROFILE = {
    "industry": "证券",
    "display_name": "证券业",
    "analysis_dimensions": [
        {"name": "经纪业务市占率", "description": "股基交易额市场份额，反映零售客户基础和渠道能力", "importance": "critical", "data_source": "fundamentals"},
        {"name": "投行业务收入", "description": "IPO/再融资/债券承销规模和收入，关注项目储备和审核节奏", "importance": "high", "data_source": "fundamentals"},
        {"name": "资管/AUM规模", "description": "主动管理规模、公募基金利润贡献，衡量财富管理转型成效", "importance": "high", "data_source": "fundamentals"},
        {"name": "自营投资收益率", "description": "自营盘规模和收益率，关注固收/权益配置结构和风险敞口。市场波动直接冲击利润", "importance": "high", "data_source": "fundamentals"},
        {"name": "ROE", "description": "券商ROE波动大，牛市高企熊市低迷，需关注ROE中枢是否抬升", "importance": "high", "data_source": "fundamentals"},
        {"name": "两融余额市占率", "description": "信用业务规模和市场份额，反映高净值客户粘性", "importance": "medium", "data_source": "fundamentals"},
        {"name": "场外衍生品规模", "description": "雪球/收益互换等业务规模，高ROE业务但监管趋严", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "券商是强周期行业，分析时必须结合市场环境（牛市/熊市/震荡市）判断各业务线趋势。重点关注：财富管理转型带来的收入结构变化、投行注册制下的项目储备质量、自营业务的风险敞口控制、以及行业并购整合预期。",
    "key_metrics": ["经纪市占率", "投行收入", "资管AUM", "自营收益率", "ROE", "两融余额", "杠杆率"],
    "comparable_companies": ["中信证券", "华泰证券", "东方财富", "中金公司", "国泰君安"],
}

INSURANCE_PROFILE = {
    "industry": "保险",
    "display_name": "保险业",
    "analysis_dimensions": [
        {"name": "新业务价值(NBV)", "description": "新签保单的未来利润折现，寿险核心增长指标。关注NBV增速和Margin", "importance": "critical", "data_source": "fundamentals"},
        {"name": "保费收入增速", "description": "总保费和首年保费增速，区分寿险/财险/健康险。关注代理人数量和产能", "importance": "critical", "data_source": "fundamentals"},
        {"name": "投资收益率", "description": "保险资金运用收益率，与长端利率高度相关。需关注权益/固收/另类配置结构", "importance": "high", "data_source": "fundamentals"},
        {"name": "偿付能力充足率", "description": "监管核心指标，决定业务扩张和分红能力。关注核心偿付能力充足率", "importance": "high", "data_source": "fundamentals"},
        {"name": "综合成本率(财险)", "description": "赔付率+费用率，低于100%才承保盈利。车险综改下持续承压", "importance": "high", "data_source": "fundamentals"},
        {"name": "退保率", "description": "反映保单质量和客户满意度，退保率高可能暗示产品设计或销售误导问题", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "保险分析需区分寿险和财险两条线。寿险看NBV增速和代理人产能恢复，财险看综合成本率和大灾影响。利率下行是保险股最大的宏观压制因素，需关注长端利率走势和权益市场波动对投资收益和内含价值的影响。",
    "key_metrics": ["NBV增速", "NBV Margin", "保费增速", "总投资收益率", "综合偿付能力充足率", "综合成本率", "代理人数量", "内含价值"],
    "comparable_companies": ["中国平安", "中国人寿", "中国太保", "新华保险", "中国人保"],
}

DIVERSIFIED_FINANCIAL_PROFILE = {
    "industry": "多元金融",
    "display_name": "多元金融",
    "analysis_dimensions": [
        {"name": "业务结构", "description": "融资租赁/信托/小贷/担保/AMC各自占比，不同业务周期属性差异大", "importance": "critical", "data_source": "fundamentals"},
        {"name": "杠杆率/负债率", "description": "金融企业杠杆水平决定经营弹性，高杠杆在经济下行期风险放大", "importance": "critical", "data_source": "fundamentals"},
        {"name": "资产质量", "description": "不良率/逾期率/关注类占比，反映信用风险暴露程度", "importance": "high", "data_source": "fundamentals"},
        {"name": "净息差/利差", "description": "融资成本与放款收益率之差，衡量核心盈利能力", "importance": "high", "data_source": "fundamentals"},
        {"name": "ROE", "description": "股东回报率，需关注ROE是否覆盖资金成本", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "多元金融涵盖融资租赁、信托、AMC、小贷等多种业态，需分别分析各项业务的周期属性。重点关注：宏观经济下行期的信用风险暴露、监管收紧对业务模式的影响、融资渠道和成本的变化。",
    "key_metrics": ["ROE", "不良率", "杠杆率", "净息差", "拨备覆盖率"],
    "comparable_companies": ["江苏金租", "五矿资本", "中航产融", "越秀资本", "浙江东方"],
}

# ─── 消费（5 个）────────────────────────────────────────────────

BAIJIU_PROFILE = {
    "industry": "白酒",
    "display_name": "白酒行业",
    "analysis_dimensions": [
        {"name": "品牌力与定价权", "description": "高端酒批价走势、渠道价差、终端动销率。品牌梯队决定定价权和抗周期能力", "importance": "critical", "data_source": "news"},
        {"name": "渠道库存", "description": "经销商库存天数和打款意愿，库存周期是白酒最重要先行指标", "importance": "critical", "data_source": "news"},
        {"name": "预收款/合同负债", "description": "经销商提前打款，反映渠道信心和下一季度营收确定性", "importance": "high", "data_source": "fundamentals"},
        {"name": "产品结构升级", "description": "吨价变化、高端/次高端占比提升，反映消费升级趋势", "importance": "high", "data_source": "fundamentals"},
        {"name": "营收与利润增速", "description": "量价拆分：销量增速×吨价增速，区分增长驱动因素", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率/净利率", "description": "白酒行业毛利率极高（60-90%），关注品牌结构对毛利率的拉动作用", "importance": "medium", "data_source": "fundamentals"},
        {"name": "费用率", "description": "销售费用率变化反映渠道竞争强度，管理费用率反映经营效率", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "白酒是A股最优质的赛道之一，核心逻辑是品牌护城河+消费升级+价格带扩容。分析需关注：茅台批价作为行业风向标、渠道库存周期（压货→去库存→补库存）、以及商务消费场景的恢复情况。高端酒看品牌溢价，次高端看全国化扩张，地产酒看区域深耕。",
    "key_metrics": ["批价", "吨价", "预收款", "毛利率", "ROE", "合同负债", "销售费用率", "营收增速"],
    "comparable_companies": ["贵州茅台", "五粮液", "泸州老窖", "山西汾酒", "洋河股份", "古井贡酒"],
}

FOOD_BEVERAGE_PROFILE = {
    "industry": "大众食品",
    "display_name": "大众食品饮料",
    "analysis_dimensions": [
        {"name": "市场份额", "description": "细分赛道市占率及变化趋势，龙头份额提升是核心投资逻辑", "importance": "critical", "data_source": "news"},
        {"name": "渠道覆盖", "description": "经销商数量、终端网点数、渠道下沉深度。零食量贩/即时零售等新渠道占比", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "反映品牌溢价和定价能力。关注原料成本波动对毛利率的冲击", "importance": "high", "data_source": "fundamentals"},
        {"name": "产品创新", "description": "新品收入占比、爆款产品生命周期。大单品依赖度高的公司风险集中", "importance": "high", "data_source": "news"},
        {"name": "营收增速", "description": "量价拆分：销量×均价，区分量增和价增驱动", "importance": "medium", "data_source": "fundamentals"},
        {"name": "原材料成本", "description": "大豆/小麦/糖/棕榈油/包材等价格波动直接影响毛利率", "importance": "medium", "data_source": "news"},
        {"name": "销售费用率", "description": "快消品竞争激烈，费用投放效率决定利润率", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "大众食品涵盖调味品、乳制品、休闲食品、饮料、啤酒等，核心逻辑是刚需+消费升级+渠道变革。分析需关注：细分赛道天花板和集中度提升空间、成本端（原料+包材）价格走势、渠道结构变化（传统经销商→社区团购→零食量贩→即时零售）。",
    "key_metrics": ["市占率", "毛利率", "销售费用率", "ROE", "营收增速", "净利率", "经销商数量"],
    "comparable_companies": ["海天味业", "伊利股份", "农夫山泉", "安井食品", "绝味食品", "青岛啤酒"],
}

HOME_APPLIANCE_PROFILE = {
    "industry": "家用电器",
    "display_name": "家用电器",
    "analysis_dimensions": [
        {"name": "内外销增速", "description": "外销受全球需求和贸易政策影响，内销与地产竣工和消费补贴相关", "importance": "critical", "data_source": "fundamentals"},
        {"name": "品牌溢价", "description": "高端子品牌占比（如卡萨帝/COLMO），品牌结构决定毛利率天花板", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "受原材料（铜/铝/塑料/钢板）价格、汇率、产品结构三重影响", "importance": "high", "data_source": "fundamentals"},
        {"name": "地产后周期联动", "description": "白电/厨电与地产竣工面积高度相关，关注竣工增速和保交楼进度", "importance": "high", "data_source": "news"},
        {"name": "海外产能布局", "description": "东南亚/墨西哥工厂进度，规避关税壁垒和降低制造成本", "importance": "medium", "data_source": "news"},
        {"name": "库存周转", "description": "渠道库存水平和周转天数，反映终端动销情况", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "家电行业已进入成熟期，核心逻辑从量增转向价增（产品升级+品牌出海）。分析需关注：白电龙头的高股息属性、小家电的品类创新和渠道变革、以及智能家居生态的布局。地产周期和原材料价格是最重要的外部变量。",
    "key_metrics": ["毛利率", "内外销增速", "ROE", "分红率", "库存周转天数", "汇率敞口"],
    "comparable_companies": ["美的集团", "海尔智家", "格力电器", "老板电器", "苏泊尔", "科沃斯"],
}

RETAIL_PROFILE = {
    "industry": "商贸零售",
    "display_name": "商贸零售",
    "analysis_dimensions": [
        {"name": "同店增速", "description": "同店销售增长率，是零售业最核心的运营指标，剔除新开店扰动", "importance": "critical", "data_source": "fundamentals"},
        {"name": "线上渗透率", "description": "电商/即时零售GMV占比和增速，线上占比越高成长性越强", "importance": "high", "data_source": "fundamentals"},
        {"name": "坪效/人效", "description": "单位面积/单人产出，衡量运营效率的核心指标", "importance": "high", "data_source": "fundamentals"},
        {"name": "供应链效率", "description": "自有品牌占比、SKU精简、仓储物流成本率，供应链能力决定毛利率上限", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "直接反映选品能力和品牌溢价，但需结合库存周转综合判断", "importance": "medium", "data_source": "fundamentals"},
        {"name": "门店扩张", "description": "净开店数和储备项目，但需区分内生增长和粗放扩张", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "零售业正经历渠道变革（传统商超→社区团购→即时零售→会员店）。分析需关注：业态转型方向和投入产出比、线上线下一体化运营能力、以及消费降级趋势下折扣零售的机会。传统百货和超市面临结构性压力，新型零售（会员店/折扣店）更值得关注。",
    "key_metrics": ["同店增速", "毛利率", "线上GMV占比", "坪效", "库存周转天数", "净利率"],
    "comparable_companies": ["中国中免", "永辉超市", "名创优品", "家家悦", "王府井"],
}

TEXTILE_APPAREL_PROFILE = {
    "industry": "纺织服饰",
    "display_name": "纺织服饰",
    "analysis_dimensions": [
        {"name": "品牌力", "description": "品牌认知度、复购率、客单价。运动服饰品牌壁垒最高，女装品牌迭代快", "importance": "critical", "data_source": "news"},
        {"name": "库存周转", "description": "服装行业库存是最大风险，库存天数和库龄结构反映经营质量", "importance": "critical", "data_source": "fundamentals"},
        {"name": "渠道结构", "description": "直营/加盟/电商占比，DTC直营占比越高毛利率越高但费用也越高", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "品牌溢价能力的直接体现，运动服饰60%+，大众休闲40-50%", "importance": "high", "data_source": "fundamentals"},
        {"name": "同店增速", "description": "剔除开店影响的有机增长，反映品牌势能和产品力", "importance": "high", "data_source": "fundamentals"},
        {"name": "海外订单", "description": "纺织制造端：海外品牌代工订单量，受全球消费和贸易政策影响", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "服饰行业分品牌端和制造端。品牌端看：品牌势能（国潮崛起/运动户外）、DTC转型效果、库存管理能力。制造端看：全球品牌客户订单、产能全球化布局（东南亚）、原材料（棉花/化纤）价格波动。",
    "key_metrics": ["库存周转天数", "毛利率", "同店增速", "直营占比", "电商增速", "净利率"],
    "comparable_companies": ["安踏体育", "李宁", "波司登", "申洲国际", "比音勒芬", "华利集团"],
}

# ─── 医药（4 个）────────────────────────────────────────────────

CHEMICAL_PHARMA_PROFILE = {
    "industry": "化学制药",
    "display_name": "化学制药",
    "analysis_dimensions": [
        {"name": "集采影响评估", "description": "已纳入集采品种收入占比、即将集采品种、集采后量价变化。集采是化药企业最大变量", "importance": "critical", "data_source": "news"},
        {"name": "研发管线", "description": "在研品种数量、临床阶段分布、靶点选择。仿制药向创新药转型进度", "importance": "critical", "data_source": "fundamentals"},
        {"name": "一致性评价", "description": "通过一致性评价品种数量，决定能否参加集采和享受政策红利", "importance": "high", "data_source": "news"},
        {"name": "原料药价格", "description": "原料药价格周期波动，向上周期利润率大幅改善", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "集采品种毛利率大幅下滑，需关注创新药/首仿药等高毛利品种占比", "importance": "high", "data_source": "fundamentals"},
        {"name": "研发费用率", "description": "创新转型需要持续高研发投入，10-15%为合理区间", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "化学制药正经历从仿制药向创新药的转型阵痛。分析需区分：仿制药（存量、集采压力、成本控制）、创新药（管线价值、BD交易、临床数据）。原料药板块看价格周期和CDMO转型。",
    "key_metrics": ["研发费用率", "毛利率", "集采品种占比", "创新药收入占比", "营收增速", "净利率"],
    "comparable_companies": ["恒瑞医药", "科伦药业", "人福医药", "恩华药业", "华海药业", "普洛药业"],
}

BIOPHARMA_PROFILE = {
    "industry": "生物制药",
    "display_name": "生物制药",
    "analysis_dimensions": [
        {"name": "创新药管线", "description": "管线数量、临床阶段分布（I/II/III期/NDA）、靶点差异化。管线价值是估值核心", "importance": "critical", "data_source": "fundamentals"},
        {"name": "临床数据", "description": "关键临床数据读出时间表，阳性/阴性数据对股价影响巨大", "importance": "critical", "data_source": "news"},
        {"name": "BD/对外授权", "description": "License-out交易金额和首付款，海外授权是验证管线价值的重要信号", "importance": "high", "data_source": "news"},
        {"name": "商业化能力", "description": "已上市产品销售放量情况、医保谈判结果、销售团队规模", "importance": "high", "data_source": "fundamentals"},
        {"name": "现金储备", "description": "在手现金/烧钱率，创新药企在盈利前依赖融资，现金跑道长度至关重要", "importance": "high", "data_source": "fundamentals"},
        {"name": "研发费用", "description": "研发投入规模和增速，但需关注研发效率（投入产出比）", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "生物制药是高风险高回报的赛道。分析需关注：管线梯队（FIC/BIC/Me-better分类）、关键临床数据读出节点、BD交易能力（买进/卖出管线）、以及融资环境对估值的影响。biotech和big pharma的分析逻辑差异较大。",
    "key_metrics": ["管线数量", "现金/烧钱率", "研发费用", "License-out金额", "产品收入", "市研率"],
    "comparable_companies": ["百济神州", "信达生物", "康方生物", "荣昌生物", "君实生物", "复宏汉霖"],
}

TRADITIONAL_CHINESE_MEDICINE_PROFILE = {
    "industry": "中药",
    "display_name": "中药",
    "analysis_dimensions": [
        {"name": "品牌壁垒", "description": "老字号品牌价值是中药最核心的护城河，品牌认知度决定定价权和复购率", "importance": "critical", "data_source": "news"},
        {"name": "OTC渠道", "description": "OTC终端覆盖率、药店陈列、品牌营销投入。OTC品牌消费品逻辑，受集采影响小", "importance": "critical", "data_source": "fundamentals"},
        {"name": "原材料成本", "description": "天然牛黄/麝香/三七/党参等药材价格波动，直接影响毛利率", "importance": "high", "data_source": "news"},
        {"name": "政策支持", "description": "中药审评审批改革、基药目录调整、医保支付政策变化", "importance": "high", "data_source": "news"},
        {"name": "产品梯队", "description": "核心大单品依赖度、新品储备和上市节奏", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "品牌中药毛利率通常50-70%，受原材料价格和提价节奏影响", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "中药兼具药品属性和消费品属性。品牌中药（片仔癀/同仁堂）看品牌壁垒和提价能力，OTC中药看渠道下沉和品类扩张，中药创新药看审评审批提速。政策暖风（中药十四五规划）是板块核心催化剂。",
    "key_metrics": ["毛利率", "ROE", "销售费用率", "营收增速", "大单品收入占比", "原材料库存"],
    "comparable_companies": ["片仔癀", "云南白药", "同仁堂", "华润三九", "东阿阿胶", "以岭药业"],
}

MEDICAL_DEVICE_PROFILE = {
    "industry": "医疗器械",
    "display_name": "医疗器械",
    "analysis_dimensions": [
        {"name": "国产替代率", "description": "各细分赛道国产化率及提升空间，高端影像/内窥镜/手术机器人等领域国产替代空间大", "importance": "critical", "data_source": "news"},
        {"name": "集采节奏", "description": "高值耗材集采范围扩大（从冠脉支架到骨科/眼科/牙科），集采品种和降价幅度是关键变量", "importance": "critical", "data_source": "news"},
        {"name": "海外注册", "description": "CE/FDA认证进度，海外收入占比和增速。出海是器械企业突破天花板的核心路径", "importance": "high", "data_source": "news"},
        {"name": "产品线广度", "description": "产品线覆盖科室数量和平台化程度，产品线越多抗风险能力越强", "importance": "high", "data_source": "fundamentals"},
        {"name": "研发投入", "description": "研发费用率，高端器械研发周期长（3-5年），需持续投入", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "高端器械毛利率60-80%，集采后毛利率可能下滑但量增可弥补", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "医疗器械是长坡厚雪赛道，逻辑是国产替代+进口替代+出海。分析需关注：各细分赛道空间和国产化率、集采对高值耗材的冲击、以及海外市场拓展进度。设备类（迈瑞/联影）壁垒高于耗材类。",
    "key_metrics": ["毛利率", "研发费用率", "海外收入占比", "产品线数量", "营收增速", "净利率"],
    "comparable_companies": ["迈瑞医疗", "联影医疗", "微创医疗", "乐普医疗", "惠泰医疗", "鱼跃医疗"],
}

# ─── 科技（5 个）────────────────────────────────────────────────

SEMICONDUCTOR_PROFILE = {
    "industry": "半导体",
    "display_name": "半导体",
    "analysis_dimensions": [
        {"name": "国产替代进度", "description": "在特定环节（设计/制造/封测/设备/材料）的国产化率及追赶进度", "importance": "critical", "data_source": "news"},
        {"name": "制程工艺", "description": "量产最先进制程节点，先进制程（7nm以下）决定竞争力天花板", "importance": "critical", "data_source": "fundamentals"},
        {"name": "产能利用率", "description": "晶圆厂/封测厂产能利用率，80%以上为健康水平，低于70%面临亏损", "importance": "high", "data_source": "fundamentals"},
        {"name": "景气周期", "description": "半导体周期一般3-4年，关注存储器价格、晶圆代工价格、交期变化", "importance": "high", "data_source": "news"},
        {"name": "资本开支", "description": "设备采购和产能扩张计划，晶圆厂资本开支规模巨大（百亿级），折旧压力需关注", "importance": "high", "data_source": "fundamentals"},
        {"name": "研发投入", "description": "研发费用率（通常15-25%），半导体制程进步需要持续高研发", "importance": "medium", "data_source": "fundamentals"},
        {"name": "美国制裁影响", "description": "实体清单/技术出口管制对设备采购和技术合作的影响", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "半导体是A股科技板块的核心，逻辑是国产替代+AI算力需求+周期复苏。分析需区分：设计（Fabless）看产品竞争力和下游需求，制造（Foundry）看制程和产能利用率，设备/材料看国产替代空间和验证进度。制裁是最大外部变量。",
    "key_metrics": ["毛利率", "研发费用率", "产能利用率", "营收增速", "净利率", "资本开支/折旧"],
    "comparable_companies": ["中芯国际", "韦尔股份", "北方华创", "中微公司", "海光信息", "澜起科技"],
}

CONSUMER_ELECTRONICS_PROFILE = {
    "industry": "消费电子",
    "display_name": "消费电子",
    "analysis_dimensions": [
        {"name": "下游需求", "description": "手机/PC/平板/可穿戴/TWS/XR等终端出货量趋势，新产品周期（如AI手机/PC）", "importance": "critical", "data_source": "news"},
        {"name": "客户集中度", "description": "第一大客户收入占比，苹果供应链占比过高则面临转移风险", "importance": "critical", "data_source": "fundamentals"},
        {"name": "库存周期", "description": "渠道和终端库存水位，去库存→补库存周期决定短期业绩弹性", "importance": "high", "data_source": "fundamentals"},
        {"name": "技术创新", "description": "产品升级方向（折叠屏/钛合金/潜望式/MR/AI终端），技术迭代带来ASP提升", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "消费电子毛利率普遍偏低（15-25%），产品结构升级和规模效应是提升关键", "importance": "medium", "data_source": "fundamentals"},
        {"name": "海外产能", "description": "越南/印度/墨西哥工厂布局，规避关税和降低劳动力成本", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "消费电子是周期性行业，核心驱动是终端创新周期+库存周期。分析需关注：苹果/安卓新机创新力度（是否带来换机潮）、AI终端（AI手机/AI PC）渗透率提升、以及供应链转移（果链向非果链、中国向东南亚）趋势。",
    "key_metrics": ["营收增速", "毛利率", "客户集中度", "库存周转天数", "研发费用率", "海外产能占比"],
    "comparable_companies": ["立讯精密", "歌尔股份", "蓝思科技", "舜宇光学", "传音控股", "领益智造"],
}

COMMUNICATION_EQUIPMENT_PROFILE = {
    "industry": "通信设备",
    "display_name": "通信设备",
    "analysis_dimensions": [
        {"name": "运营商资本开支", "description": "三大运营商CAPEX规模及结构（无线/传输/算力），是设备商收入核心驱动力", "importance": "critical", "data_source": "news"},
        {"name": "5G/6G渗透", "description": "5G基站建设进度和6G研发投入，5G-A/6G有望带来新一轮设备投资周期", "importance": "high", "data_source": "news"},
        {"name": "海外市场", "description": "海外收入占比和增速，受地缘政治影响大（华为/中兴在欧美受限）", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "通信设备毛利率20-35%，产品结构（高端路由器/光传输占比）决定毛利率", "importance": "high", "data_source": "fundamentals"},
        {"name": "光模块/算力", "description": "AI驱动数据中心光模块需求爆发，800G/1.6T等高速率产品升级节奏", "importance": "high", "data_source": "news"},
        {"name": "研发投入", "description": "通信设备研发费用率通常10-15%，5G/6G研发需要持续投入", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "通信设备核心逻辑是5G投资周期+AI算力网络建设。分析需区分：运营商网络设备（基站/传输/核心网）看国内CAPEX周期，光模块/数通设备看AI算力需求爆发，光纤光缆看海风/海外和价格周期。",
    "key_metrics": ["运营商CAPEX", "毛利率", "海外收入占比", "研发费用率", "营收增速", "订单增速"],
    "comparable_companies": ["中兴通讯", "中际旭创", "天孚通信", "新易盛", "紫光股份", "锐捷网络"],
}

COMPUTER_SOFTWARE_PROFILE = {
    "industry": "计算机",
    "display_name": "计算机/软件",
    "analysis_dimensions": [
        {"name": "信创国产化", "description": "党政/行业信创替换进度，操作系统/数据库/中间件/办公软件国产替代率", "importance": "critical", "data_source": "news"},
        {"name": "SaaS指标", "description": "ARR/MRR、NDR（净留存率）、LTV/CAC。SaaS模式看订阅收入占比和客户留存", "importance": "high", "data_source": "fundamentals"},
        {"name": "AI赋能", "description": "AI大模型应用布局，AI+行业解决方案落地进度和客户付费意愿", "importance": "high", "data_source": "news"},
        {"name": "订单增速", "description": "新签订单和在手订单，ToG/ToB业务订单是营收先行指标", "importance": "high", "data_source": "fundamentals"},
        {"name": "人效", "description": "人均收入和人均利润，软件公司核心效率指标", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "软件公司毛利率通常50-80%，但需关注定制化占比拉低毛利率", "importance": "medium", "data_source": "fundamentals"},
        {"name": "应收账款", "description": "ToG业务回款周期长，应收账款周转和坏账风险需重点关注", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "计算机软件行业逻辑是信创国产化+AI+数字经济。分析需区分：基础软件（OS/DB）看信创替代进度，应用软件（ERP/OA/CAX）看SaaS化转型和客户粘性，AI应用看场景落地和商业化节奏。ToG业务需关注财政支出节奏。",
    "key_metrics": ["营收增速", "毛利率", "人均收入", "研发费用率", "应收账款周转", "NDR(如有)", "订单增速"],
    "comparable_companies": ["金山办公", "用友网络", "中望软件", "广联达", "深信服", "科大讯飞"],
}

INTERNET_PROFILE = {
    "industry": "互联网",
    "display_name": "互联网",
    "analysis_dimensions": [
        {"name": "用户增长", "description": "MAU/DAU及增速，互联网平台核心资产是用户规模。关注获客成本(CAC)", "importance": "critical", "data_source": "fundamentals"},
        {"name": "ARPU/变现率", "description": "单位用户收入贡献，通过广告/电商/游戏/会员等方式变现。ARPU提升是成熟期增长引擎", "importance": "critical", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "互联网公司毛利率通常50-70%，收入结构（高毛利广告/游戏vs低毛利电商）决定毛利率", "importance": "high", "data_source": "fundamentals"},
        {"name": "政策监管", "description": "反垄断/数据安全/游戏版号/互联网金融等监管政策，互联网行业政策风险较高", "importance": "high", "data_source": "news"},
        {"name": "研发费用", "description": "AI/云计算/自动驾驶等新业务研发投入，短期拖累利润但决定长期竞争力", "importance": "medium", "data_source": "fundamentals"},
        {"name": "现金流", "description": "经营现金流和自由现金流，互联网公司盈利质量的重要验证", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "互联网行业分析需关注：用户生态（规模+粘性+变现效率）、收入增长引擎切换（移动互联网→AI）、以及政策环境变化。平台型公司看网络效应和双边匹配效率，内容型公司看IP和用户时长。",
    "key_metrics": ["MAU/DAU", "ARPU", "毛利率", "研发费用率", "经营现金流", "获客成本", "用户时长"],
    "comparable_companies": ["腾讯控股", "阿里巴巴", "美团", "拼多多", "网易", "快手"],
}

# ─── 制造（6 个）────────────────────────────────────────────────

AUTO_OEM_PROFILE = {
    "industry": "汽车整车",
    "display_name": "汽车整车",
    "analysis_dimensions": [
        {"name": "月销量", "description": "月度批发/零售/交付量，新能源汽车渗透率。销量是整车企业最核心的跟踪指标", "importance": "critical", "data_source": "news"},
        {"name": "新能源转型", "description": "新能源车型占比、混动/纯电/增程技术路线选择、电动化进度", "importance": "critical", "data_source": "fundamentals"},
        {"name": "出海进度", "description": "海外销量占比、海外工厂布局（东南亚/欧洲/南美）、关税和贸易壁垒", "importance": "high", "data_source": "news"},
        {"name": "车型周期", "description": "新车型上市节奏和爆款概率，产品大年/小年交替影响销量弹性", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "整车毛利率10-25%，受规模效应、产品结构、电池成本三重影响", "importance": "high", "data_source": "fundamentals"},
        {"name": "智能驾驶", "description": "智驾能力（NOA/城市NOA）和用户付费率，智能化是差异化竞争焦点", "importance": "medium", "data_source": "news"},
        {"name": "单车均价", "description": "ASP变化趋势，品牌向上和高端化是自主品牌的核心战略", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "汽车行业正处于电动化+智能化+全球化三重变革期。分析需关注：月销量数据（高频跟踪）、新能源渗透率提升空间、价格战烈度和盈利能力变化、以及出海战略落地进度。传统合资品牌面临份额流失，自主品牌和新势力更值得关注。",
    "key_metrics": ["月销量", "新能源渗透率", "毛利率", "单车均价", "海外销量占比", "研发费用率"],
    "comparable_companies": ["比亚迪", "长城汽车", "吉利汽车", "理想汽车", "赛力斯", "长安汽车"],
}

AUTO_PARTS_PROFILE = {
    "industry": "汽车零部件",
    "display_name": "汽车零部件",
    "analysis_dimensions": [
        {"name": "客户绑定", "description": "核心客户名单和配套车型，切入特斯拉/比亚迪/华为等头部客户是重要催化剂", "importance": "critical", "data_source": "fundamentals"},
        {"name": "产品升级", "description": "从传统零部件向电动化（热管理/电驱/电池结构件）、智能化（传感器/域控/线控）产品升级", "importance": "critical", "data_source": "fundamentals"},
        {"name": "产能利用率", "description": "产能扩张节奏和利用率，产能爬坡期利润率弹性大", "importance": "high", "data_source": "fundamentals"},
        {"name": "海外工厂", "description": "跟随客户出海建厂（墨西哥/东南亚/欧洲），本地化配套能力", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "零部件毛利率15-30%，产品结构升级和规模效应是提升关键", "importance": "high", "data_source": "fundamentals"},
        {"name": "单车价值量", "description": "配套单车价值金额，产品线扩张（从单一零件到模块化总成）提升单车价值", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "零部件行业逻辑是电动化/智能化升级+客户拓展+全球化。分析需关注：产品从传统→电动化/智能化的升级路径、切入头部客户供应链的节奏（定点→量产→放量）、以及海外工厂盈利贡献。平台型零部件公司（拓普/三花）比单一产品公司更有长期价值。",
    "key_metrics": ["毛利率", "营收增速", "前5大客户占比", "研发费用率", "单车价值量", "海外收入占比"],
    "comparable_companies": ["拓普集团", "三花智控", "德赛西威", "星宇股份", "福耀玻璃", "均胜电子"],
}

ELECTRICAL_EQUIPMENT_PROFILE = {
    "industry": "电气设备",
    "display_name": "电气设备/电力设备",
    "analysis_dimensions": [
        {"name": "电网投资", "description": "国网/南网年度投资计划和实际执行，特高压/配网/数字化是重点方向", "importance": "critical", "data_source": "news"},
        {"name": "新能源装机", "description": "光伏/风电/储能/氢能装机量及增速，设备商直接受益于下游装机增长", "importance": "critical", "data_source": "news"},
        {"name": "海外出口", "description": "变压器/开关柜/电表/逆变器等出口增速，海外电网改造需求旺盛", "importance": "high", "data_source": "fundamentals"},
        {"name": "订单增速", "description": "新增订单和在手订单规模，反映未来1-2年营收确定性", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "电力设备毛利率20-35%，受原材料（铜/硅钢/铝）价格和竞争格局影响", "importance": "high", "data_source": "fundamentals"},
        {"name": "产能扩张", "description": "产能扩张计划和资本开支，新能源设备行业扩产节奏快、需关注供需平衡", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "电力设备行业逻辑是新型电力系统建设+新能源装机增长+海外电网改造。分析需区分：电网设备（特高压/配网/数字化）看国网投资节奏，新能源设备（光伏/风电/储能）看下游装机需求和产能过剩风险，出口型设备看海外订单和关税影响。",
    "key_metrics": ["电网投资额", "订单增速", "毛利率", "海外收入占比", "营收增速", "产能利用率"],
    "comparable_companies": ["国电南瑞", "特变电工", "许继电气", "思源电气", "阳光电源", "宁德时代"],
}

ENGINEERING_MACHINERY_PROFILE = {
    "industry": "工程机械",
    "display_name": "工程机械",
    "analysis_dimensions": [
        {"name": "更新周期", "description": "挖掘机等设备8-10年更新周期，当前处于周期什么位置是关键判断", "importance": "critical", "data_source": "news"},
        {"name": "基建投资", "description": "基建投资增速和地方专项债发行节奏，是工程机械需求的核心驱动力", "importance": "critical", "data_source": "news"},
        {"name": "海外收入", "description": "海外收入占比和增速，东南亚/非洲/拉美/中东等新兴市场需求旺盛", "importance": "high", "data_source": "fundamentals"},
        {"name": "开工率", "description": "挖掘机开工小时数、设备利用率，反映终端施工活跃度", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "工程机械毛利率20-30%，受钢材成本和规模效应影响", "importance": "high", "data_source": "fundamentals"},
        {"name": "电动化", "description": "电动装载机/矿卡/混凝土机械渗透率，电动化是下一轮产品升级主线", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "工程机械是强周期行业，核心逻辑是更新周期+基建/地产需求+出口。分析需关注：挖掘机销量（月度高频数据）、地产新开工和基建投资增速、以及海外市场拓展进度。龙头公司通过全球化+多元化（农机/矿机/高机）平抑周期波动。",
    "key_metrics": ["挖机销量", "开工小时数", "海外收入占比", "毛利率", "应收账款周转", "净利率"],
    "comparable_companies": ["三一重工", "徐工机械", "中联重科", "恒立液压", "浙江鼎力", "柳工"],
}

AUTOMATION_PROFILE = {
    "industry": "自动化",
    "display_name": "自动化/工控",
    "analysis_dimensions": [
        {"name": "国产替代", "description": "PLC/伺服/变频/ DCS/机器人等细分领域国产化率，国产替代是长期成长逻辑", "importance": "critical", "data_source": "news"},
        {"name": "下游景气度", "description": "3C/光伏/锂电/汽车/物流等下游行业产能扩张节奏，直接影响自动化设备需求", "importance": "critical", "data_source": "news"},
        {"name": "订单增速", "description": "新签订单和在手订单，自动化设备交付周期1-3个月，订单是营收先行指标", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "自动化设备毛利率30-50%，核心零部件自制率越高毛利率越高", "importance": "high", "data_source": "fundamentals"},
        {"name": "人形机器人", "description": "人形机器人相关布局（减速器/丝杠/传感器/电机），是长期成长期权", "importance": "medium", "data_source": "news"},
        {"name": "研发投入", "description": "研发费用率通常8-15%，核心零部件（控制器/伺服/减速器）研发是壁垒", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "自动化行业逻辑是机器换人+国产替代+人形机器人。分析需区分：通用自动化（PLC/伺服/变频）看制造业景气度，专用自动化（光伏/锂电设备）看下游技术迭代和扩产节奏，机器人看人形机器人产业进展。自动化是制造业升级的核心受益方向。",
    "key_metrics": ["订单增速", "毛利率", "研发费用率", "营收增速", "国产替代率", "下游CAPEX"],
    "comparable_companies": ["汇川技术", "埃斯顿", "绿的谐波", "拓斯达", "中控技术", "机器人"],
}

MILITARY_PROFILE = {
    "industry": "军工",
    "display_name": "军工/航空航天",
    "analysis_dimensions": [
        {"name": "军品交付", "description": "军品订单和交付节奏，十四五后期订单有望加速落地。新型号列装是核心催化剂", "importance": "critical", "data_source": "news"},
        {"name": "型号放量", "description": "主力战机/导弹/舰船/无人机等型号批产进度和放量节奏", "importance": "critical", "data_source": "news"},
        {"name": "军民融合", "description": "民用航空（C919产业链）、商业航天、低空经济等军民融合业务收入占比", "importance": "high", "data_source": "fundamentals"},
        {"name": "改革预期", "description": "军工国企改革（资产注入/股权激励/混改），提升经营效率和利润释放", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "军品毛利率30-50%，但受审价机制影响。民品毛利率通常低于军品", "importance": "medium", "data_source": "fundamentals"},
        {"name": "研发投入", "description": "研发费用率通常5-15%，新型号研发投入大但决定长期竞争力", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "军工行业逻辑是国防现代化+新型号列装+军民融合。分析需关注：军费预算增速和装备采购结构变化、主力型号（歼-20/运-20/福建舰配套）批产进度、以及国企改革对利润释放的催化。军工信息不透明，需通过关联交易额和合同负债等财务指标间接验证。",
    "key_metrics": ["合同负债", "存货", "研发费用率", "毛利率", "营收增速", "关联交易额"],
    "comparable_companies": ["中航沈飞", "中航西飞", "航发动力", "中国船舶", "中航光电", "振华科技"],
}

# ─── 资源（4 个）────────────────────────────────────────────────

COAL_PROFILE = {
    "industry": "煤炭",
    "display_name": "煤炭",
    "analysis_dimensions": [
        {"name": "煤价", "description": "动力煤/焦煤/无烟煤价格走势，决定煤炭企业盈利的核心变量", "importance": "critical", "data_source": "news"},
        {"name": "产量", "description": "原煤产量和商品煤销量，产量增长主要来自产能核增和新建矿井投产", "importance": "critical", "data_source": "fundamentals"},
        {"name": "长协占比", "description": "长协煤占比和定价机制，长协占比越高盈利稳定性越强", "importance": "high", "data_source": "fundamentals"},
        {"name": "分红率", "description": "煤炭企业现金流充裕，高分红是核心投资逻辑。关注分红比例和股息率", "importance": "high", "data_source": "fundamentals"},
        {"name": "转型", "description": "煤化工（煤制油/煤制气/煤制烯烃）和新能源（光伏/风电/储能）转型进展", "importance": "medium", "data_source": "news"},
        {"name": "成本控制", "description": "吨煤成本变化（人工/安全/环保/税费），成本控制能力决定利润弹性", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "煤炭行业是典型周期股，核心逻辑是高股息+煤价韧性+转型。分析需关注：动力煤/焦煤价格走势、供需格局（国内产量+进口）、以及长协煤占比对盈利稳定性的影响。高分红是煤炭股的核心吸引力，但煤价下行时股息率也会缩水。",
    "key_metrics": ["煤价", "吨煤毛利", "长协占比", "分红率", "产量增速", "吨煤成本"],
    "comparable_companies": ["中国神华", "陕西煤业", "兖矿能源", "中煤能源", "潞安环能", "山西焦煤"],
}

PETROCHEMICAL_PROFILE = {
    "industry": "石油石化",
    "display_name": "石油石化",
    "analysis_dimensions": [
        {"name": "油价", "description": "布伦特/WTI原油价格走势，决定石油开采利润和炼化成本", "importance": "critical", "data_source": "news"},
        {"name": "炼化利润", "description": "裂解价差和炼化毛利，受油价、产品价格、产能利用率综合影响", "importance": "critical", "data_source": "fundamentals"},
        {"name": "上游资本开支", "description": "勘探开发投资和储量替代率，上游资本开支决定未来产量增长", "importance": "high", "data_source": "fundamentals"},
        {"name": "产量", "description": "原油/天然气产量及增速，三桶油持续增储上产", "importance": "high", "data_source": "fundamentals"},
        {"name": "化工品价差", "description": "乙烯/丙烯/PTA/聚酯等主要化工品与原料价差，反映化工业务盈利", "importance": "medium", "data_source": "news"},
        {"name": "分红率", "description": "三桶油分红比例高，高股息是重要投资逻辑", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "石油石化行业分析需区分：上游开采（看油价+产量+成本）、炼化（看裂解价差+产能+库存收益/损失）、化工（看产品价差+下游需求）。三桶油的高分红和央企估值修复是重要投资逻辑。",
    "key_metrics": ["油价", "裂解价差", "产量增速", "上游资本开支", "分红率", "ROE"],
    "comparable_companies": ["中国石油", "中国石化", "中国海油", "恒力石化", "荣盛石化", "卫星化学"],
}

NONFERROUS_METAL_PROFILE = {
    "industry": "有色金属",
    "display_name": "有色金属",
    "analysis_dimensions": [
        {"name": "商品价格", "description": "LME/上期所金属价格（铜/铝/锌/锂/钴/镍/黄金等），是盈利最核心驱动力", "importance": "critical", "data_source": "news"},
        {"name": "供需缺口", "description": "全球精炼铜/电解铝/碳酸锂供需平衡表，供需缺口决定价格方向", "importance": "critical", "data_source": "news"},
        {"name": "产能扩张", "description": "矿山/冶炼产能扩张计划和执行进度，铜矿开发周期5-10年、供给弹性低", "importance": "high", "data_source": "fundamentals"},
        {"name": "资源储量", "description": "矿石储量和品位，资源储量×商品价格=企业价值基础", "importance": "high", "data_source": "fundamentals"},
        {"name": "成本曲线", "description": "吨矿/吨金属生产成本（C1成本+AISC），成本在行业中的分位决定抗周期能力", "importance": "high", "data_source": "fundamentals"},
        {"name": "下游需求", "description": "新能源（铜/铝/锂/镍）、地产（铝/锌）、基建（铜/铝）等下游需求增速", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "有色金属是典型周期行业，核心逻辑是商品价格+供需格局+资源禀赋。分析需区分：工业金属（铜/铝/锌）看全球供需和宏观需求，新能源金属（锂/钴/镍）看电动车渗透率，贵金属（黄金）看实际利率和避险需求。",
    "key_metrics": ["金属价格", "吨矿成本", "产量增速", "资源储量", "毛利率", "现金流"],
    "comparable_companies": ["紫金矿业", "洛阳钼业", "中国铝业", "赣锋锂业", "天齐锂业", "山东黄金"],
}

CHEMICAL_PROFILE = {
    "industry": "化工",
    "display_name": "化工",
    "analysis_dimensions": [
        {"name": "产品价差", "description": "主要产品与原料价差走势，价差是化工盈利的最核心指标", "importance": "critical", "data_source": "news"},
        {"name": "产能周期", "description": "行业产能扩张周期和开工率，化工行业产能投放周期通常2-3年", "importance": "critical", "data_source": "news"},
        {"name": "下游需求", "description": "下游行业（地产/汽车/纺织/农业/新能源）需求增速，决定了化工品消耗量", "importance": "high", "data_source": "news"},
        {"name": "环保约束", "description": "环保限产政策和能耗双控，高耗能化工品面临供给收缩", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "化工品价格波动大，毛利率波动剧烈。一体化企业（从原料到终端产品）毛利率更稳定", "importance": "high", "data_source": "fundamentals"},
        {"name": "新材料", "description": "高端聚烯烃/工程塑料/电子化学品/新能源材料等新材料业务进展", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "化工行业涵盖范围广，分析需区分：大宗化工品（看行业供需和价差周期）、精细化工（看产品壁垒和下游需求）、新材料（看国产替代和客户导入）。产能周期是化工投资最重要的节奏判断。",
    "key_metrics": ["产品价差", "毛利率", "产能利用率", "ROE", "营收增速", "资本开支"],
    "comparable_companies": ["万华化学", "恒力石化", "荣盛石化", "龙佰集团", "华鲁恒升", "宝丰能源"],
}

# ─── 基建（4 个）────────────────────────────────────────────────

POWER_UTILITY_PROFILE = {
    "industry": "电力运营",
    "display_name": "电力运营",
    "analysis_dimensions": [
        {"name": "上网电价", "description": "市场化交易电价和长协电价走势，电价是电力企业收入核心变量", "importance": "critical", "data_source": "news"},
        {"name": "装机容量", "description": "总装机容量和新增装机（火电/水电/风电/光伏/核电），装机增长决定收入增长", "importance": "critical", "data_source": "fundamentals"},
        {"name": "利用小时", "description": "发电设备利用小时数，反映电力需求强度和设备效率", "importance": "high", "data_source": "fundamentals"},
        {"name": "绿电占比", "description": "风电/光伏等新能源装机占比和发电量占比，绿电占比提升是估值提升的核心逻辑", "importance": "high", "data_source": "fundamentals"},
        {"name": "燃料成本", "description": "火电：煤炭价格和天然气价格。水电：来水量。风光：光照/风力资源", "importance": "high", "data_source": "news"},
        {"name": "分红率", "description": "电力企业现金流稳定，高分红是重要投资逻辑。关注分红比例和股息率", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "电力运营行业分析需区分：火电（看煤价+电价+容量电价）、水电（看来水+分红）、核电（看审批+装机增长）、新能源（看装机增速+绿电溢价+补贴回款）。火电从周期股向公用事业股转型是重要估值逻辑变化。",
    "key_metrics": ["装机容量", "利用小时", "上网电价", "毛利率", "分红率", "绿电占比"],
    "comparable_companies": ["长江电力", "华能国际", "中国核电", "三峡能源", "龙源电力", "国投电力"],
}

CONSTRUCTION_PROFILE = {
    "industry": "建筑工程",
    "display_name": "建筑工程",
    "analysis_dimensions": [
        {"name": "订单增速", "description": "新签订单和在手订单规模，订单是建筑企业营收的先行指标（领先1-2年）", "importance": "critical", "data_source": "fundamentals"},
        {"name": "PPP项目", "description": "PPP项目投资规模和回款进度，PPP项目回款周期长、占用资金大", "importance": "high", "data_source": "fundamentals"},
        {"name": "海外工程", "description": "一带一路沿线国家工程项目和收入占比，海外工程毛利率高但风险也高", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "建筑企业毛利率普遍偏低（10-15%），关注业务结构优化（运营/投资占比提升）", "importance": "high", "data_source": "fundamentals"},
        {"name": "应收账款", "description": "应收账款周转天数和坏账风险，地产类客户回款风险需重点关注", "importance": "high", "data_source": "fundamentals"},
        {"name": "基建投资", "description": "基建投资增速和专项债发行规模，是建筑行业需求的核心驱动力", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "建筑行业分析需关注：订单增速（新签/在手）和结构（基建/房建/专业工程）、地产客户风险敞口和坏账计提、以及一带一路海外订单的恢复。建筑央企估值低、分红稳定，有估值修复逻辑。",
    "key_metrics": ["新签订单", "在手订单", "毛利率", "应收账款周转", "海外收入占比", "净利率"],
    "comparable_companies": ["中国建筑", "中国中铁", "中国交建", "中国中冶", "中国电建", "中国能建"],
}

BUILDING_MATERIALS_PROFILE = {
    "industry": "建材",
    "display_name": "建材",
    "analysis_dimensions": [
        {"name": "产能供给", "description": "水泥/玻璃/玻纤等行业产能过剩程度和去产能政策（错峰生产/产能置换）", "importance": "critical", "data_source": "news"},
        {"name": "地产+基建需求", "description": "地产新开工和施工面积、基建投资增速，决定建材需求总量", "importance": "critical", "data_source": "news"},
        {"name": "区域格局", "description": "水泥是短腿产品（运输半径200-300km），区域竞争格局和集中度比全国更重要", "importance": "high", "data_source": "fundamentals"},
        {"name": "价格/价差", "description": "水泥价格、玻璃价格、玻纤价格走势，价格是盈利最敏感变量", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "建材毛利率波动大（水泥20-40%、玻璃15-35%），受价格和成本双重影响", "importance": "high", "data_source": "fundamentals"},
        {"name": "新材料", "description": "防水材料/涂料/石膏板/减水剂等消费建材，看市场份额提升和品牌溢价", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "建材行业分析需区分：周期建材（水泥/玻璃/玻纤）看供需和价格，消费建材（防水/涂料/管材）看份额提升和品牌溢价。地产链复苏是建材板块最大的催化剂，但需关注地产需求中枢下移的长期趋势。",
    "key_metrics": ["水泥价格", "产能利用率", "毛利率", "应收账款周转", "营收增速", "市场份额"],
    "comparable_companies": ["海螺水泥", "中国建材", "东方雨虹", "北新建材", "旗滨集团", "中国巨石"],
}

STEEL_PROFILE = {
    "industry": "钢铁",
    "display_name": "钢铁",
    "analysis_dimensions": [
        {"name": "钢价", "description": "螺纹钢/热卷/冷轧/中厚板等钢材价格走势，是盈利最核心变量", "importance": "critical", "data_source": "news"},
        {"name": "铁矿石成本", "description": "铁矿石/焦炭/废钢等原料成本，铁矿价格受四大矿山供给格局影响", "importance": "critical", "data_source": "news"},
        {"name": "产能利用率", "description": "高炉开工率和电炉产能利用率，产能利用率80%以上为景气状态", "importance": "high", "data_source": "news"},
        {"name": "产品结构", "description": "板材/长材/特钢占比，高端特钢和汽车板/电工钢等产品毛利率更高", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "钢铁毛利率波动大（5-20%），吨钢毛利是核心跟踪指标", "importance": "high", "data_source": "fundamentals"},
        {"name": "地产需求", "description": "地产新开工和施工面积直接影响螺纹钢需求，基建影响板材需求", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "钢铁是典型周期行业，核心逻辑是供需关系+成本变化。分析需关注：钢价和吨钢毛利走势、铁矿石和焦炭成本、以及地产/基建/制造业三大下游需求变化。特钢企业（中信特钢）比普钢更具成长性。",
    "key_metrics": ["吨钢毛利", "钢价", "铁矿石价格", "产能利用率", "毛利率", "产品结构"],
    "comparable_companies": ["宝钢股份", "中信特钢", "华菱钢铁", "南钢股份", "鞍钢股份", "首钢股份"],
}

# ─── 服务（4 个）────────────────────────────────────────────────

REAL_ESTATE_PROFILE = {
    "industry": "房地产",
    "display_name": "房地产",
    "analysis_dimensions": [
        {"name": "销售增速", "description": "签约销售金额和销售面积增速，是房企最核心的跟踪指标", "importance": "critical", "data_source": "news"},
        {"name": "土地储备", "description": "土储规模、区域分布和楼面均价，土储集中在核心一二线城市的房企更安全", "importance": "critical", "data_source": "fundamentals"},
        {"name": "融资成本", "description": "综合融资成本和融资渠道，国企融资成本3-4%、民企6-8%，差距悬殊", "importance": "critical", "data_source": "fundamentals"},
        {"name": "政策松紧", "description": "限购/限贷/限价/税费等调控政策变化，政策是地产行业最大的外生变量", "importance": "high", "data_source": "news"},
        {"name": "负债率", "description": "净负债率、现金短债比、剔除预收款的资产负债率（三道红线），是判断财务安全的关键", "importance": "high", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "结算毛利率反映过去拿地质量，销售毛利率反映当前盈利能力", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "房地产行业正处于深度调整期，分析需关注：销售去化速度和回款能力、土储质量和减值风险、融资渠道和偿债能力。优质国企和央企（保利/华润/中海）在行业出清中受益，民企投资需谨慎。",
    "key_metrics": ["签约销售额", "净负债率", "现金短债比", "融资成本", "毛利率", "土储货值"],
    "comparable_companies": ["保利发展", "华润置地", "中海地产", "招商蛇口", "万科A", "绿城中国"],
}

TRANSPORTATION_PROFILE = {
    "industry": "交通运输",
    "display_name": "交通运输",
    "analysis_dimensions": [
        {"name": "运价", "description": "航运运价（BDI/集装箱运价）、航空票价、快递单票价格，运价是盈利核心", "importance": "critical", "data_source": "news"},
        {"name": "客座率/装载率", "description": "航空客座率、航运装载率、铁路客运上座率，反映运输效率", "importance": "high", "data_source": "fundamentals"},
        {"name": "油价", "description": "航空燃油成本占运营成本30-40%，航运燃油成本15-20%，油价波动直接影响利润", "importance": "high", "data_source": "news"},
        {"name": "汇率", "description": "航空公司大量美元负债，人民币升值产生汇兑收益、贬值产生汇兑损失", "importance": "high", "data_source": "news"},
        {"name": "航线/网络", "description": "航空国际航线恢复进度、快递网点覆盖密度、港口航线网络", "importance": "medium", "data_source": "fundamentals"},
        {"name": "毛利率", "description": "运输行业毛利率分化大（航空10-20%、快递5-10%、港口40-50%），关注变化趋势", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "交通运输涵盖多个子行业，分析需区分：航空（看出行需求+油价+汇率）、航运（看运价周期+全球贸易）、快递（看价格战+市占率）、港口/公路/铁路（看吞吐量+高股息）。",
    "key_metrics": ["运价/票价", "客座率/装载率", "毛利率", "油价", "汇率", "分红率"],
    "comparable_companies": ["中远海控", "中国国航", "顺丰控股", "上港集团", "招商公路", "京沪高铁"],
}

PUBLIC_UTILITY_PROFILE = {
    "industry": "公用事业",
    "display_name": "公用事业（燃气/水务/环保）",
    "analysis_dimensions": [
        {"name": "特许经营权", "description": "区域特许经营权是核心壁垒，特许经营期限和续期风险需关注", "importance": "critical", "data_source": "fundamentals"},
        {"name": "价格调整", "description": "燃气价格联动机制、水价调整周期、垃圾处理费调价，价格调整直接影响营收", "importance": "critical", "data_source": "news"},
        {"name": "产能扩张", "description": "供水/污水处理/固废处理/危废处置等新增产能，产能扩张是收入增长来源", "importance": "high", "data_source": "fundamentals"},
        {"name": "补贴", "description": "垃圾焚烧发电补贴、污水处理补贴等，补贴退坡是行业趋势需关注影响", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "公用事业毛利率通常30-40%，现金流稳定、具有类债券属性", "importance": "medium", "data_source": "fundamentals"},
        {"name": "分红率", "description": "公用事业经营现金流稳定，高分红是重要投资逻辑", "importance": "medium", "data_source": "fundamentals"},
    ],
    "analysis_focus": "公用事业是防御性板块，核心逻辑是特许经营权+稳健现金流+高分红。分析需关注：燃气价格联动机制是否顺畅、环保补贴退坡节奏、以及产能扩张带来的成长性。",
    "key_metrics": ["毛利率", "产能利用率", "分红率", "营收增速", "资产负债率", "经营现金流"],
    "comparable_companies": ["新奥股份", "深圳燃气", "伟明环保", "瀚蓝环境", "重庆水务", "首创环保"],
}

MEDIA_PROFILE = {
    "industry": "传媒",
    "display_name": "传媒",
    "analysis_dimensions": [
        {"name": "内容IP", "description": "核心IP储备和变现（电影/剧集/综艺/游戏/动漫），IP生命周期和爆款概率", "importance": "critical", "data_source": "news"},
        {"name": "渠道分发", "description": "电影票房/平台播放量/游戏流水/广告收入，各渠道分发能力和变现效率", "importance": "high", "data_source": "fundamentals"},
        {"name": "广告收入", "description": "广告收入占总收入比重，广告是强周期业务，受宏观经济影响大", "importance": "high", "data_source": "fundamentals"},
        {"name": "政策监管", "description": "内容审查/游戏版号/教培政策/数据安全等监管政策变化", "importance": "high", "data_source": "news"},
        {"name": "毛利率", "description": "传媒毛利率分化大（游戏60-80%、电影30-40%、广告20-30%），内容型毛利率更高", "importance": "medium", "data_source": "fundamentals"},
        {"name": "AI应用", "description": "AI降本增效（AI辅助内容创作/代码/广告投放），AI+传媒是重要催化", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "传媒行业分析需关注：内容竞争力（IP储备+爆款概率）、渠道分发效率、以及政策监管环境。AI对传媒行业的影响主要体现在降本增效（内容创作/广告投放/用户匹配）。游戏和出版是现金流较好的子行业。",
    "key_metrics": ["营收增速", "毛利率", "销售费用率", "应收账款周转", "商誉/净资产", "现金流"],
    "comparable_companies": ["分众传媒", "芒果超媒", "光线传媒", "三七互娱", "中国出版", "万达电影"],
}

# ─── 农业（1 个）────────────────────────────────────────────────

AGRICULTURE_PROFILE = {
    "industry": "农林牧渔",
    "display_name": "农林牧渔",
    "analysis_dimensions": [
        {"name": "产品价格周期", "description": "生猪/肉鸡/水产/农作物价格周期波动，猪周期（3-4年）是农业板块最重要的投资节奏", "importance": "critical", "data_source": "news"},
        {"name": "出栏量/种植面积", "description": "生猪出栏量、肉鸡出栏量、种植面积，量增是规模企业成长的核心驱动", "importance": "critical", "data_source": "fundamentals"},
        {"name": "养殖成本", "description": "完全成本（饲料+人工+折旧+防疫），成本控制能力决定周期底部盈利能力", "importance": "high", "data_source": "fundamentals"},
        {"name": "疫病/天气", "description": "非洲猪瘟/禽流感/洪涝/干旱等不可抗力，对农产品供给冲击巨大", "importance": "high", "data_source": "news"},
        {"name": "饲料成本", "description": "玉米/豆粕/鱼粉等饲料原料价格，饲料成本占养殖成本60-70%", "importance": "high", "data_source": "news"},
        {"name": "转基因", "description": "转基因作物商业化进度（玉米/大豆），是种业板块的核心催化剂", "importance": "medium", "data_source": "news"},
    ],
    "analysis_focus": "农林牧渔是强周期行业，核心逻辑是猪周期+规模化+转基因。分析需关注：猪价走势和猪周期位置（底部/上行/顶部/下行）、规模化养殖企业出栏量增长和成本控制、以及转基因商业化对种业格局的重塑。",
    "key_metrics": ["猪价/鸡价", "出栏量", "完全成本", "头均盈利", "饲料成本", "能繁母猪存栏"],
    "comparable_companies": ["牧原股份", "温氏股份", "海大集团", "隆平高科", "大北农", "圣农发展"],
}

# ─── 汇总 ────────────────────────────────────────────────────────

ALL_PROFILES = [
    # 金融
    BANK_PROFILE,
    SECURITIES_PROFILE,
    INSURANCE_PROFILE,
    DIVERSIFIED_FINANCIAL_PROFILE,
    # 消费
    BAIJIU_PROFILE,
    FOOD_BEVERAGE_PROFILE,
    HOME_APPLIANCE_PROFILE,
    RETAIL_PROFILE,
    TEXTILE_APPAREL_PROFILE,
    # 医药
    CHEMICAL_PHARMA_PROFILE,
    BIOPHARMA_PROFILE,
    TRADITIONAL_CHINESE_MEDICINE_PROFILE,
    MEDICAL_DEVICE_PROFILE,
    # 科技
    SEMICONDUCTOR_PROFILE,
    CONSUMER_ELECTRONICS_PROFILE,
    COMMUNICATION_EQUIPMENT_PROFILE,
    COMPUTER_SOFTWARE_PROFILE,
    INTERNET_PROFILE,
    # 制造
    AUTO_OEM_PROFILE,
    AUTO_PARTS_PROFILE,
    ELECTRICAL_EQUIPMENT_PROFILE,
    ENGINEERING_MACHINERY_PROFILE,
    AUTOMATION_PROFILE,
    MILITARY_PROFILE,
    # 资源
    COAL_PROFILE,
    PETROCHEMICAL_PROFILE,
    NONFERROUS_METAL_PROFILE,
    CHEMICAL_PROFILE,
    # 基建
    POWER_UTILITY_PROFILE,
    CONSTRUCTION_PROFILE,
    BUILDING_MATERIALS_PROFILE,
    STEEL_PROFILE,
    # 服务
    REAL_ESTATE_PROFILE,
    TRANSPORTATION_PROFILE,
    PUBLIC_UTILITY_PROFILE,
    MEDIA_PROFILE,
    # 农业
    AGRICULTURE_PROFILE,
]


def main():
    parser = argparse.ArgumentParser(description="初始化行业分析配置（37个行业大类）")
    parser.add_argument("--force", action="store_true", help="覆盖已有的同名行业配置")
    args = parser.parse_args()

    from pymongo import MongoClient
    from app.core.config import settings

    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collection = db["industry_analysis_profiles"]

    now = datetime.utcnow()
    created, skipped = 0, 0

    for profile in ALL_PROFILES:
        existing = collection.find_one({"industry": profile["industry"]})
        if existing and not args.force:
            print(f"⏭️  跳过已存在: {profile['industry']}")
            skipped += 1
            continue

        doc = {**profile, "is_active": True, "source": "system", "created_at": now, "updated_at": now}
        if existing and args.force:
            collection.replace_one({"_id": existing["_id"]}, doc)
            print(f"🔄 覆盖更新: {profile['industry']}")
        else:
            collection.insert_one(doc)
            print(f"✅ 创建: {profile['industry']} ({len(profile['analysis_dimensions'])} 维度, {len(profile['key_metrics'])} 指标)")
        created += 1

    client.close()

    print(f"\n📊 完成: 创建/更新 {created} 个, 跳过 {skipped} 个")
    print(f"💡 共 {len(ALL_PROFILES)} 个行业大类，覆盖 {sum(p['industry'] for p in ALL_PROFILES)} 个分析维度")


if __name__ == "__main__":
    main()