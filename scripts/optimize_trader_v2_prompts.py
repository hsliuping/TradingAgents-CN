"""
优化 trader_v2 的提示词模板

修复问题：
1. 分离系统提示词和用户提示词（当前只有系统提示词）
2. 移除 risk_assessment（风险评估在交易计划之后进行）
3. 明确可用的数据源：market_report、fundamentals_report、news_report、report_sector_report、report_index_report、report_bull_report、report_bear_report
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MongoDB 连接配置
MONGODB_HOST = os.getenv("MONGODB_HOST", "127.0.0.1")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "tradingagents")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "tradingagents123")
MONGODB_AUTH_SOURCE = os.getenv("MONGODB_AUTH_SOURCE", "admin")

def get_connection_string():
    """构建 MongoDB 连接字符串"""
    if MONGODB_USERNAME and MONGODB_PASSWORD:
        return f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={MONGODB_AUTH_SOURCE}"
    return f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"

# 系统提示词（角色和职责，不包含输出格式）
SYSTEM_PROMPT = """你是一位专业交易员，负责根据投资计划生成具体的交易指令。

## 你的职责

1. **交易方向确定**：根据投资计划确定交易方向（买入/卖出/持有）
2. **价格设定**：确定买入价格（市价/限价）和卖出价格
3. **仓位管理**：确定交易数量（考虑资金管理和风险控制）
4. **风险控制**：设置止损位和止盈位
5. **执行策略**：考虑市场流动性和交易时机

## 交易原则

- **严格执行投资计划**：基于投资计划中的建议（买入/持有/卖出）制定交易指令
- **合理的风险控制**：设置止损位，控制单笔交易风险
- **明确的交易参数**：提供清晰的买入价、数量、止损、止盈
- **考虑市场流动性**：确保交易指令可执行
- **资金管理**：根据投资计划中的仓位建议合理分配资金

## 重要说明

- **风险评估不在本阶段**：风险评估是在交易计划制定之后由风险经理进行的，你不需要进行风险评估
- **基于已有数据**：你只能使用提供的分析报告（市场分析、基本面分析、新闻分析、板块分析、大盘分析、看涨报告、看跌报告）来制定交易计划
- **遵循投资计划**：投资计划中的 action、target_price、position_ratio 等字段是你的主要参考依据"""

# 用户提示词模板（包含数据占位符）
USER_PROMPT_TEMPLATE = """请为 {{company_name}}（{{ticker}}）生成具体的交易计划：

## 基本信息
- **股票代码**：{{ticker}}
- **公司名称**：{{company_name}}
- **分析日期**：{{analysis_date}}
- **货币单位**：{{currency_name}}（{{currency_symbol}}）
- **当前价格**：{{current_price}}
- **所属行业**：{{industry}}
- **市场类型**：{{market_name}}

## 投资计划

{{investment_plan}}

## 可用分析报告

### 1. 市场分析报告
{{market_report}}

### 2. 基本面分析报告
{{fundamentals_report}}

### 3. 新闻分析报告
{{news_report}}

### 4. 板块分析报告
{{report_sector_report}}

### 5. 大盘分析报告
{{report_index_report}}

### 6. 看涨研究报告
{{report_bull_report}}

### 7. 看跌研究报告
{{report_bear_report}}

## 历史交易记录（如有）

{{historical_trades}}

## 任务要求

请基于上述投资计划和各类分析报告，生成详细的交易计划，包括：

1. **交易方向**：买入/卖出/持有（必须与投资计划中的 action 一致）
2. **建议价格**：买入价或卖出价（参考投资计划中的 target_price）
3. **交易数量**：建议买入/卖出的数量或仓位比例（参考投资计划中的 position_ratio）
4. **止损位**：风险控制止损价格
5. **止盈位**：利润锁定止盈价格
6. **执行策略**：市价单还是限价单，分批建仓还是一次性建仓
7. **风险提示**：交易执行中需要注意的风险点

**重要提示**：
- 必须严格按照投资计划中的 action 来确定交易方向
- 目标价格应参考投资计划中的 target_price，但可以根据当前市场价格进行微调
- 仓位比例应参考投资计划中的 position_ratio
- 止损位和止盈位应基于技术分析和风险控制原则设定
- 使用 {{currency_name}}（{{currency_symbol}}）作为货币单位"""

def optimize_trader_v2_templates():
    """优化 trader_v2 的提示词模板"""
    client = MongoClient(get_connection_string())
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("优化 trader_v2 提示词模板")
    print("=" * 80)
    
    # 查找所有 trader_v2 模板
    templates = list(collection.find({
        "agent_type": "trader_v2",
        "agent_name": "trader_v2",
        "status": "active"
    }))
    
    print(f"\n找到 {len(templates)} 个 trader_v2 模板\n")
    
    for template in templates:
        preference = template.get('preference_type', 'neutral')
        template_id = template.get('_id')
        
        print(f"\n{'=' * 80}")
        print(f"处理模板: preference_type={preference}, _id={template_id}")
        print(f"{'=' * 80}")
        
        # 获取当前内容
        content = template.get('content', {})
        current_system = content.get('system_prompt', '')
        current_user = content.get('user_prompt', '')
        
        print(f"\n当前 system_prompt 长度: {len(current_system)}")
        print(f"当前 user_prompt 长度: {len(current_user)}")
        
        # 更新内容
        new_content = {
            **content,  # 保留其他字段（如 output_format、analysis_requirements 等）
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": USER_PROMPT_TEMPLATE
        }
        
        # 更新数据库
        result = collection.update_one(
            {"_id": template_id},
            {"$set": {"content": new_content}}
        )
        
        if result.modified_count > 0:
            print(f"✅ 成功更新模板: preference_type={preference}")
        else:
            print(f"⚠️ 模板未更新: preference_type={preference}")
    
    # 如果没有模板，创建一个默认的
    if len(templates) == 0:
        print("\n未找到现有模板，创建默认模板...")
        default_template = {
            "agent_type": "trader_v2",
            "agent_name": "trader_v2",
            "preference_type": "neutral",
            "is_system": True,
            "status": "active",
            "content": {
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": USER_PROMPT_TEMPLATE,
                "output_format": """请以结构化的方式输出交易计划，包括：
- 交易方向（买入/卖出/持有）
- 建议价格
- 交易数量
- 止损位
- 止盈位
- 执行策略
- 风险提示"""
            }
        }
        
        result = collection.insert_one(default_template)
        print(f"✅ 创建默认模板: _id={result.inserted_id}")
    
    client.close()
    print("\n" + "=" * 80)
    print("优化完成！")
    print("=" * 80)

if __name__ == "__main__":
    optimize_trader_v2_templates()

