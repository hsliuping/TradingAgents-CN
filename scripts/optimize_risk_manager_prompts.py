# -*- coding: utf-8 -*-
"""
优化风险经理 v2 的提示词模板

优化内容：
1. 格式统一：output_format 改为 JSON 格式（与其他 Manager Agent 一致）
2. 角色分离：system_prompt 只包含角色和职责，不包含格式要求
3. 消除冲突：格式要求统一在 output_format 字段
4. 目标一致：各字段职责清晰，无重复和冲突
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

from pymongo import MongoClient

# 数据库连接
host = os.getenv('MONGODB_HOST', 'localhost') if 'MONGODB_HOST' in os.environ else 'localhost'
port = os.getenv('MONGODB_PORT', '27017') if 'MONGODB_PORT' in os.environ else '27017'
username = os.getenv('MONGODB_USERNAME', '') if 'MONGODB_USERNAME' in os.environ else ''
password = os.getenv('MONGODB_PASSWORD', '') if 'MONGODB_PASSWORD' in os.environ else ''
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents') if 'MONGODB_DATABASE' in os.environ else 'tradingagents'
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin') if 'MONGODB_AUTH_SOURCE' in os.environ else 'admin'

if username and password:
    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
else:
    mongo_uri = f"mongodb://{host}:{port}/{db_name}"

print(f"📊 连接数据库: {host}:{port}/{db_name}\n")
client = MongoClient(mongo_uri)
db = client[db_name]


def get_optimized_templates():
    """获取优化后的模板内容"""
    
    templates = {}
    
    # 定义三种偏好的模板
    preferences = {
        "aggressive": {
            "label": "激进",
            "style_desc": "激进的分析风格，更倾向于发现投资机会，强调成长潜力，积极寻找买入理由",
            "decision_principle": "更关注上涨潜力和成长机会，在风险可控的前提下，倾向于给出买入建议",
            "risk_tolerance": "较高的风险承受能力",
            "constraint": "必须从激进角度进行分析，保持一致的分析立场"
        },
        "neutral": {
            "label": "中性",
            "style_desc": "中性的分析风格，客观评估，平衡分析，提供理性判断",
            "decision_principle": "客观权衡看涨和看跌观点，基于证据做出理性决策",
            "risk_tolerance": "平衡的风险收益比",
            "constraint": "必须从中性角度进行分析，保持一致的分析立场"
        },
        "conservative": {
            "label": "保守",
            "style_desc": "保守的分析风格，更关注风险评估，强调安全边际，识别潜在问题",
            "decision_principle": "更关注风险因素，在确认安全边际的前提下，谨慎给出投资建议",
            "risk_tolerance": "较低的风险承受能力",
            "constraint": "必须从保守角度进行分析，保持一致的分析立场"
        }
    }
    
    for pref_key, pref_info in preferences.items():
        # system_prompt: 只包含角色定义和职责，不包含格式要求
        system_prompt = f"""你是一位{pref_info['label']}的风险管理者，需要综合各方风险观点做出风险评估，并生成最终分析结果。

**分析风格**: {pref_info['style_desc']}

**核心职责**:
1. 综合分析激进、保守、中性三方的风险观点
2. 识别关键风险因素
3. 评估风险的可能性和影响
4. 形成{pref_info['label']}、理性的风险评估
5. 提出风险控制建议
6. **综合投资建议、交易计划、风险评估，生成最终分析结果**

**决策原则**:
- {pref_info['decision_principle']}
- {pref_info['risk_tolerance']}
- 客观、理性、基于证据
- 给出明确的风险评级
- 详细说明风险评估理由
- 使用中文输出"""

        # tool_guidance: 工具使用指导
        tool_guidance = f"""**工具使用指导**:

基于提供的风险观点进行{pref_info['label']}的风险评估。
从{pref_info['label']}角度评估所有风险信息。"""

        # analysis_requirements: 只包含分析内容要求，不包含格式要求
        analysis_requirements = """**风险评估总结要求**:

⚖️ **风险观点汇总**:
- **激进观点**（收益导向）:
  - 收益潜力评估
  - 建议仓位和策略
  - 风险可控性判断
  
- **保守观点**（风险导向）:
  - 风险因素识别
  - 下行风险评估
  - 安全边际要求

- **中性观点**（平衡导向）:
  - 风险收益平衡
  - 综合评估结论
  - 理性操作建议

📊 **综合风险评估**:
- **整体风险等级**: 高 / 中 / 低
  - 评级依据（技术、基本面、市场）
  - 风险量化评估
  - 风险趋势（上升/稳定/下降）

- **主要风险因素**:
  - 财务风险（负债、现金流）
  - 经营风险（竞争、市场）
  - 市场风险（估值、流动性）
  - 系统性风险（政策、宏观）

- **风险可控性**:
  - 可控风险 vs 不可控风险
  - 风险应对措施
  - 风险监控指标

🎯 **最终建议**:
- **综合仓位建议**: XX%-XX%
  - 激进建议：XX%
  - 保守建议：XX%
  - 中性建议：XX%
  - 综合权衡：XX%

- **风险控制措施**:
  - 止损位设置
  - 仓位控制规则
  - 风险对冲策略

- **操作策略**:
  - 建仓策略（一次性/分批）
  - 加减仓条件
  - 退出条件

🌍 **语言要求**: 
- 所有内容使用中文
- 建议使用：买入、持有、减仓（不使用英文）"""

        # output_format: 统一所有格式要求（JSON格式）
        output_format = """**输出格式要求**：

请严格按照以下JSON格式输出风险评估和最终分析结果：

```json
{
    "risk_level": "低/中/高",
    "risk_score": 0.0-1.0之间的数字（必需字段，风险评分）,
    "reasoning": "字符串（必需字段，1000-2000字，详细的风险评估理由和分析依据）",
    "key_risks": ["风险1", "风险2", "风险3"]（必需字段，主要风险因素列表）,
    "risk_control": "风险控制措施建议"（必需字段）,
    "investment_adjustment": "对投资计划的调整建议"（必需字段）,
    "final_trade_decision": {
        "action": "买入/持有/卖出"（必需字段）,
        "confidence": 0-100之间的整数（必需字段，表示对投资建议的信心度）,
        "target_price": 数字（必需字段，目标价格，必须基于报告中的真实数据）,
        "stop_loss": 止损价格（数字，必需字段）,
        "position_ratio": "建议仓位比例（如5%、10%）"（必需字段）,
        "reasoning": "最终分析结果的综合推理（300-600字）"（必需字段）,
        "summary": "字符串（必需字段，200-500字，投资计划摘要）",
        "risk_warning": "关键风险提示（100字以内）"（必需字段）
    }
}
```

**字段说明**：
1. **risk_level** (必需): 风险等级，只能是"低"、"中"或"高"
2. **risk_score** (必需): 风险评分，必须是0-1之间的数字（如：0.3、0.5、0.7），表示投资风险程度
3. **reasoning** (必需): 风险评估理由，1000-2000字，必须详细说明：
   - 为什么给出这个风险评估
   - 基于哪些风险因素（激进观点、保守观点、市场环境、技术面、基本面等）
   - 关键风险判断因素和逻辑推理过程
   - 如何权衡不同风险观点
4. **key_risks** (必需): 主要风险因素列表，至少包含3个主要风险因素
5. **risk_control** (必需): 风险控制措施建议，必须提供具体的风险控制措施
6. **investment_adjustment** (必需): 对投资计划的调整建议，必须基于风险评估结果给出调整建议
7. **final_trade_decision** (必需): 最终分析结果对象，必须包含所有字段：
   - **action** (必需): 投资建议，只能是"买入"、"持有"或"卖出"
   - **confidence** (必需): 信心度，必须是0-100之间的整数（如：62、75、80），不是小数
   - **target_price** (必需): 目标价格，必须基于报告中的真实价格数据，严禁编造
   - **stop_loss** (必需): 止损价格，必须是数字，建议基于当前价格和风险水平设定
   - **position_ratio** (必需): 建议仓位比例，格式如"5%"、"10%"等
   - **reasoning** (必需): 最终分析结果的综合推理，300-600字，必须详细说明：
     - 综合研究经理的投资建议（看涨/看跌观点）
     - 交易员的交易计划（买入价、止损、止盈）
     - 风险评估结果（风险等级、关键风险）
     - 得出最终的投资结论
   - **summary** (必需): 投资计划摘要，200-500字，简要总结投资建议的核心要点
   - **risk_warning** (必需): 关键风险提示，100字以内，必须明确指出关键风险

**重要提示**：
- 必须严格按照JSON格式输出，确保所有字段都存在
- 所有字段都是必需字段，不能省略任何字段
- final_trade_decision 必须包含完整的交易决策，所有子字段都是必需的
- final_trade_decision.action 必须明确：买入、持有、或卖出
- final_trade_decision.confidence 必须是整数，不是小数
- final_trade_decision.target_price 必须基于报告中的真实数据，不能随意编造
- final_trade_decision.stop_loss 必须提供止损价格，建议基于当前价格和风险水平设定
- final_trade_decision.position_ratio 必须提供建议仓位比例
- final_trade_decision.reasoning 必须详细说明最终分析结果的综合推理（300-600字）
- final_trade_decision.summary 必须提供投资计划摘要（200-500字），简要总结投资建议的核心要点
- final_trade_decision.risk_warning 必须提供关键风险提示（100字以内）
- reasoning 必须详细说明风险评估理由（1000-2000字），不能使用默认值或模板文字
- key_risks 必须提供至少3个主要风险因素
- risk_control 必须提供具体的风险控制措施
- investment_adjustment 必须基于风险评估结果给出调整建议"""

        # user_prompt: 只包含任务描述和数据，不包含格式要求
        user_prompt = """请综合分析 {{company_name}}（{{ticker}}）的投资风险：

📊 **基本信息**：
- 股票代码：{{ticker}}
- 公司名称：{{company_name}}
- 分析日期：{{analysis_date}}

【投资计划】
{{investment_plan}}

【激进风险观点】
{{risky_opinion}}

【保守风险观点】
{{safe_opinion}}

【中性风险观点】
{{neutral_opinion}}

【风险辩论总结】
{{debate_summary}}

请基于以上信息，综合分析并给出风险评估和风险控制建议。"""

        # constraints: 只包含分析立场约束，不包含格式要求
        constraints = f"""{pref_info['constraint']}。所有内容使用中文。"""

        templates[pref_key] = {
            "system_prompt": system_prompt,
            "tool_guidance": tool_guidance,
            "analysis_requirements": analysis_requirements,
            "output_format": output_format,
            "user_prompt": user_prompt,
            "constraints": constraints
        }
    
    return templates


def update_templates():
    """更新数据库中的模板"""
    collection = db['prompt_templates']
    
    # 获取优化后的模板
    optimized_templates = get_optimized_templates()
    
    # 查找所有 risk_manager_v2 模板
    templates = list(collection.find({
        "agent_type": "managers_v2",
        "agent_name": "risk_manager_v2"
    }))
    
    if not templates:
        print("❌ 未找到 risk_manager_v2 模板")
        return
    
    print(f"找到 {len(templates)} 个模板\n")
    
    updated_count = 0
    
    for template in templates:
        preference = template.get('preference_type')
        template_id = template.get('_id')
        
        if preference not in optimized_templates:
            print(f"⚠️  跳过未知偏好类型: {preference}")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"更新模板: {preference} 偏好")
        print(f"模板ID: {template_id}")
        print(f"{'=' * 80}")
        
        # 获取优化后的内容
        optimized_content = optimized_templates[preference]
        
        # 更新模板
        update_result = collection.update_one(
            {"_id": template_id},
            {
                "$set": {
                    "content.system_prompt": optimized_content["system_prompt"],
                    "content.tool_guidance": optimized_content["tool_guidance"],
                    "content.analysis_requirements": optimized_content["analysis_requirements"],
                    "content.output_format": optimized_content["output_format"],
                    "content.user_prompt": optimized_content["user_prompt"],
                    "content.constraints": optimized_content["constraints"],
                    "updated_at": datetime.now()
                }
            }
        )
        
        if update_result.modified_count > 0:
            print(f"✅ 模板更新成功")
            updated_count += 1
            
            # 打印各字段长度
            print(f"\n📊 更新后的字段长度:")
            for key, value in optimized_content.items():
                print(f"  {key}: {len(value)} 字符")
        else:
            print(f"⚠️  模板未更新（可能内容相同）")
    
    print(f"\n{'=' * 80}")
    print(f"更新完成")
    print(f"{'=' * 80}")
    print(f"总计: {len(templates)} 个模板")
    print(f"成功更新: {updated_count} 个模板")
    print(f"{'=' * 80}")


def main():
    """主函数"""
    print("🚀 开始优化风险经理 v2 提示词模板\n")
    
    try:
        update_templates()
        print("\n✅ 优化完成！")
    except Exception as e:
        print(f"\n❌ 优化失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
    client.close()

