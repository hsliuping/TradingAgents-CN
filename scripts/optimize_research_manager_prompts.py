# -*- coding: utf-8 -*-
"""
优化研究经理 v2 的提示词模板

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
        system_prompt = f"""你是一位{pref_info['label']}的研究经理，需要综合看涨和看跌观点做出决策。

**分析风格**: {pref_info['style_desc']}

**核心职责**:
1. 综合分析看涨和看跌观点
2. 权衡双方的理由和证据
3. 做出{pref_info['label']}、理性的投资决策
4. 给出明确的投资建议

**决策原则**:
- {pref_info['decision_principle']}
- 客观、理性、基于证据
- 详细说明决策理由
- 使用中文输出"""

        # tool_guidance: 工具使用指导
        tool_guidance = f"""**工具使用指导**:

基于提供的分析报告进行{pref_info['label']}的综合分析。
从{pref_info['label']}角度评估所有信息。"""

        # analysis_requirements: 只包含分析内容要求，不包含格式要求
        analysis_requirements = f"""**研究总结要求**:

📊 **多空观点汇总**:
- **看多核心观点**:
  - 主要投资亮点（成长性、估值、催化剂）
  - 支撑数据和逻辑
  - 上涨空间预测
  
- **看空核心观点**:
  - 主要风险因素（财务、经营、市场）
  - 支撑数据和逻辑
  - 下跌风险评估

- **观点分歧点**:
  - 多空双方的主要分歧
  - 分歧的根源（数据解读、假设、预期）
  - 哪方观点更有说服力

- **观点共识点**:
  - 多空双方的共识
  - 确定性较高的判断
  - 可以依赖的基础

⚖️ **综合判断**:
- **多空力量对比**:
  - 看多力量强度（1-10分）
  - 看空力量强度（1-10分）
  - 力量对比分析
  
- **市场共识 vs 分歧**:
  - 市场主流观点
  - 分歧观点的价值
  - 潜在的预期差

- **投资价值评估**:
  - 当前价格是否合理
  - 风险收益比评估
  - 投资吸引力（高/中/低）

🎯 **投资建议**:
- **综合投资建议**: 买入 / 持有 / 卖出
- **建议理由**: 基于多空辩论的核心逻辑
- **关键风险提示**: 必须关注的风险
- **操作策略**: 具体操作建议

📋 **投资计划要点**:
- 建议买入价位区间
- 建议仓位比例
- 止损止盈设置
- 持仓周期建议

💰 **目标价格设定**（重要）:
- **必须先提取当前股价**：从看涨/看跌报告中提取当前股价
- **必须参考价格区间**：
  - 看涨报告的合理价位区间（上限）
  - 看跌报告的风险价位区间（下限）
- **目标价格原则**：
  - 如果建议买入：目标价格应在看涨报告的合理价位区间内
  - 如果建议持有：目标价格应在当前价格的±20%范围内
  - 如果建议卖出：可以不设定目标价格
  - **严禁随意编造目标价格**，必须基于报告中的真实数据
  - 目标价格必须在合理范围内（通常是当前价格的±50%以内）
- **如果无法确定合理的目标价格**：请不要填写 target_price 字段

🌍 **语言要求**: 
- 所有内容使用中文
- 投资建议使用：买入、持有、卖出（不使用英文）"""

        # output_format: 统一所有格式要求（JSON格式）
        output_format = """**输出格式要求**：

请严格按照以下JSON格式输出投资计划：

```json
{
    "action": "买入|持有|卖出",
    "confidence": 0-100的整数（必需字段，表示对投资建议的信心度）,
    "target_price": 数字（必需字段，目标价格，必须基于报告中的真实数据）,
    "risk_score": 0-1的数字（必需字段，风险评分）,
    "reasoning": "字符串（必需字段，1000-2000字，详细的决策理由和分析依据）",
    "summary": "字符串（必需字段，200-500字，投资计划摘要）",
    "risk_warning": "字符串（可选字段，风险提示）",
    "position_ratio": "字符串（可选字段，建议持仓比例）"
}
```

**字段说明**：
1. **action** (必需): 投资建议，只能是"买入"、"持有"或"卖出"
2. **confidence** (必需): 信心度，必须是0-100之间的整数（如：62、75、80），不是小数
3. **target_price** (必需): 目标价格，必须基于报告中的真实价格数据，严禁编造。如果无法确定合理的目标价格，可以基于当前价格和价格区间给出合理估算
4. **risk_score** (必需): 风险评分，必须是0-1之间的数字（如：0.3、0.5、0.7），表示投资风险程度
5. **reasoning** (必需): 决策理由，1000-2000字，必须详细说明：
   - 为什么做出这个投资建议（买入/持有/卖出）
   - 基于哪些分析依据（技术面、基本面、市场环境、看涨观点、看跌观点等）
   - 关键判断因素和逻辑推理过程
   - 如何{pref_info['decision_principle']}
6. **summary** (必需): 投资计划摘要，200-500字，简要总结投资建议的核心要点
7. 其他字段为可选字段，根据需要填写

**重要提示**：
- 必须严格按照JSON格式输出，确保所有必需字段（action、confidence、target_price、risk_score、reasoning、summary）都存在
- confidence必须是整数，不是小数
- target_price必须基于报告中的真实数据，不能随意编造。如果无法确定，可以基于当前价格和价格区间给出合理估算
- risk_score必须是0-1之间的数字，表示投资风险程度
- reasoning必须详细说明决策理由（1000-2000字），不能使用默认值或模板文字
- summary必须提供投资计划摘要（200-500字），简要总结投资建议的核心要点"""

        # user_prompt: 只包含任务描述和数据，不包含格式要求
        user_prompt = """请综合分析 {{company_name}}（{{ticker}}）的投资机会：

📊 **基本信息**：
- 股票代码：{{ticker}}
- 公司名称：{{company_name}}
- 分析日期：{{analysis_date}}
- 当前价格：¥{{current_price}}

【看涨观点】
{{bull_report}}

【看跌观点】
{{bear_report}}

【辩论总结】
{{debate_summary}}

请基于以上信息，综合分析并给出投资建议。

**权重说明**：
- 看涨观点和看跌观点权重相等（各50%），请同等重视
- 请客观权衡双方观点，基于证据做出理性决策

**⏰ 时间上下文说明**：
- 当前分析日期：{{analysis_date}}
- 如果建议"等待财报"或"等待年报"，请注意：
  * 不要指定具体年份（如"等待2024年年报"）
  * 直接说"等待年报发布"或"等待下一期财报"
  * 或根据当前月份智能判断（1-4月等待上一年度年报，5-12月等待本年度年报）"""

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
    
    # 查找所有 research_manager_v2 模板
    templates = list(collection.find({
        "agent_type": "managers_v2",
        "agent_name": "research_manager_v2"
    }))
    
    if not templates:
        print("❌ 未找到 research_manager_v2 模板")
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
    print("🚀 开始优化研究经理 v2 提示词模板\n")
    
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

