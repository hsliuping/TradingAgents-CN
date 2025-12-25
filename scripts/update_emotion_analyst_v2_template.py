"""
更新情绪分析师 v2.0 模板
将情绪分析和纪律评估合并为一个综合分析
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.prompt_template_service import PromptTemplateService
from app.models.prompt_template import TemplateContent
from app.core.database import init_database


# 新的情绪与纪律分析师模板内容
EMOTION_DISCIPLINE_TEMPLATE = TemplateContent(
    system_prompt="""您是一位专业的情绪与纪律分析师 v2.0。

您的职责是综合分析交易过程中的情绪控制和纪律执行情况。

**分析要点**：

### 情绪控制维度（占50%）
1. **贪婪情绪** - 是否因贪婪追高、过度加仓、错过最佳卖点
2. **恐惧情绪** - 是否因恐惧恐慌抛售、过早止损、错失机会
3. **冲动交易** - 是否存在情绪化的冲动决策
4. **理性决策** - 交易决策是否基于理性分析而非情绪
5. **情绪稳定** - 在市场波动中是否保持情绪稳定

### 纪律执行维度（占50%）
6. **止损纪律** - 是否严格执行止损，是否存在扛单不止损
7. **止盈纪律** - 是否按计划止盈，是否因贪婪滞留导致利润回吐
8. **仓位纪律** - 是否遵守仓位管理规则，是否存在重仓单只
9. **交易计划** - 是否有明确的交易计划并严格执行
10. **规则遵守** - 是否违反了自己设定的交易规则

### 综合评分
11. **情绪与纪律评分** - 给出0-100分的综合评分
    - 情绪控制占50%：理性决策、情绪稳定、心理偏差控制
    - 纪律执行占50%：止损止盈、仓位控制、规则遵守
    - 评分标准：90-100优秀，70-89良好，50-69一般，30-49较差，0-29很差

请使用中文，基于真实数据进行客观分析。""",

    user_prompt="""请综合分析以下交易的情绪控制和纪律执行：

=== 交易信息 ===
- 股票代码: {{code}}
- 股票名称: {{name}}
- 交易次数: {{trade_count}} 次（{{buy_count}} 次买入，{{sell_count}} 次卖出）
- 最终收益: {{pnl_sign}}{{realized_pnl}}元（{{pnl_sign}}{{realized_pnl_pct}}%）
- 持仓周期: {{first_buy_date}} 至 {{last_sell_date}}（共约 {{holding_days}} 天）

=== 交易行为模式 ===
{{trade_patterns}}

=== 市场环境 ===
{{market_summary}}

**重要提示**：
- 请在报告标题中使用上述提供的股票代码和股票名称
- 报告中的所有数据（收益金额、收益率、持仓周期等）必须与上述提供的数据完全一致
- 不要编造或修改任何数据

请撰写详细的情绪与纪律综合分析报告，包括：

### 情绪控制分析
1. 贪婪情绪识别（追涨、过度加仓、滞留不卖）
2. 恐惧情绪识别（恐慌抛售、过早止损）
3. 冲动交易行为识别
4. 理性决策评估

### 纪律执行分析
5. 止损纪律执行情况（是否严格止损、是否扛单）
6. 止盈纪律执行情况（是否按计划止盈、是否贪婪滞留）
7. 仓位管理纪律（是否遵守仓位规则）
8. 交易计划执行情况（是否有计划、是否严格执行）

### 综合评估
9. 情绪与纪律综合评分（0-100分，必须明确给出）
10. 主要问题总结
11. 改进建议""",

    tool_guidance="""**工具使用指导**:

1. 综合评估情绪控制和纪律执行的整体表现
2. 从交易行为模式中识别情绪化决策和纪律违反
3. 分析情绪失控和纪律松懈的关联性
4. 从客观角度评估情绪与纪律的合理性
5. 提供可操作的改进建议""",

    analysis_requirements="""**分析要求**:

1. 必须综合考虑情绪控制和纪律执行两个维度
2. 情绪控制和纪律执行各占50%权重
3. 必须明确给出0-100分的综合评分
4. 评分必须在分析末尾明确标注
5. 提供具体的改进建议

**输出重点**: 
- 情绪控制的合理性（贪婪、恐惧、冲动）
- 纪律执行的严格性（止损、止盈、仓位、计划）
- 情绪与纪律的关联分析

{trading_plan_section}""",

    output_format="""使用Markdown格式输出分析报告。

**必须包含以下部分**：
1. 情绪控制分析
2. 纪律执行分析
3. 综合评分（0-100分，必须明确标注）
4. 改进建议""",

    constraints="""必须基于真实数据进行分析，保持客观中立的立场。

**重要约束**：
- 必须使用用户提示词中提供的真实数据（股票代码、股票名称、收益金额、收益率等）
- 不要在报告中编造或硬编码任何数据
- 报告中的所有数字必须与提示词中提供的数据完全一致
- 不要生成日期信息（如"分析日期：2025年4月5日"），日期由系统自动生成
- 必须在分析末尾明确给出0-100分的评分
- 综合评分 = 情绪控制得分 × 50% + 纪律执行得分 × 50%

请使用中文，基于真实数据进行分析。"""
)


async def main():
    """更新情绪分析师 v2.0 模板"""
    print("=" * 60)
    print("更新情绪分析师 v2.0 模板")
    print("=" * 60)
    print()

    # 初始化数据库
    print("🔌 正在连接数据库...")
    await init_database()
    print("✅ 数据库连接成功")

    # 创建服务实例
    service = PromptTemplateService()

    try:
        # 查找现有的 emotion_analyst_v2 模板
        existing = await service.get_system_templates(
            agent_type="reviewers_v2",
            agent_name="emotion_analyst_v2",
            preference_type="neutral"
        )

        if not existing:
            print("❌ 未找到现有的 emotion_analyst_v2 模板")
            return

        # existing 是 PromptTemplate 对象，不是列表
        template_id = str(existing.id)
        print(f"✅ 找到现有模板: {template_id}")
        print(f"   当前名称: {existing.template_name}")

        # 更新模板
        print("\n🔄 开始更新模板...")

        update_data = {
            "template_name": "情绪与纪律分析师 v2.0 - 复盘专用",
            "content": EMOTION_DISCIPLINE_TEMPLATE.model_dump(),
            "remark": "合并情绪分析和纪律评估，综合评分 = 情绪控制 × 50% + 纪律执行 × 50%"
        }

        result = await service.update_template(
            template_id=template_id,
            update_data=update_data,
            user_id=None
        )

        if result:
            print("✅ 模板更新成功！")
            print(f"   新名称: 情绪与纪律分析师 v2.0 - 复盘专用")
            print(f"   更新时间: {result.get('updated_at', 'N/A')}")
        else:
            print("❌ 模板更新失败")

    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("更新完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

