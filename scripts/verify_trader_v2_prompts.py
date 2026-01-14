"""
验证 trader_v2 提示词模板更新结果
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

def verify_trader_v2_templates():
    """验证 trader_v2 模板"""
    client = MongoClient(get_connection_string())
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("验证 trader_v2 提示词模板")
    print("=" * 80)
    
    # 查找所有 trader_v2 模板
    templates = list(collection.find({
        "agent_type": "trader_v2",
        "agent_name": "trader_v2",
        "status": "active"
    }).sort("preference_type", 1))
    
    print(f"\n找到 {len(templates)} 个 trader_v2 模板\n")
    
    all_ok = True
    
    for template in templates:
        preference = template.get('preference_type', 'neutral')
        content = template.get('content', {})
        
        system_prompt = content.get('system_prompt', '')
        user_prompt = content.get('user_prompt', '')
        
        print(f"\n{'=' * 80}")
        print(f"模板: preference_type={preference}")
        print(f"{'=' * 80}")
        
        # 检查 system_prompt
        print(f"\n✅ System Prompt:")
        print(f"   长度: {len(system_prompt)} 字符")
        has_role = "专业交易员" in system_prompt or "交易员" in system_prompt
        has_no_output_format = "输出格式" not in system_prompt or "JSON格式" not in system_prompt
        has_no_risk_assessment = "风险评估不在本阶段" in system_prompt
        print(f"   ✓ 包含角色定义: {has_role}")
        print(f"   ✓ 不包含输出格式: {has_no_output_format}")
        print(f"   ✓ 明确说明风险评估不在本阶段: {has_no_risk_assessment}")
        
        if not has_role or not has_no_output_format or not has_no_risk_assessment:
            all_ok = False
        
        # 检查 user_prompt
        print(f"\n✅ User Prompt:")
        print(f"   长度: {len(user_prompt)} 字符")
        has_investment_plan = "{{investment_plan}}" in user_prompt
        has_market_report = "{{market_report}}" in user_prompt
        has_fundamentals_report = "{{fundamentals_report}}" in user_prompt
        has_news_report = "{{news_report}}" in user_prompt
        has_sector_report = "{{report_sector_report}}" in user_prompt
        has_index_report = "{{report_index_report}}" in user_prompt
        has_bull_report = "{{report_bull_report}}" in user_prompt
        has_bear_report = "{{report_bear_report}}" in user_prompt
        no_risk_assessment = "{{risk_assessment}}" not in user_prompt
        has_trading_requirements = "交易方向" in user_prompt and "建议价格" in user_prompt
        
        print(f"   ✓ 包含 investment_plan: {has_investment_plan}")
        print(f"   ✓ 包含 market_report: {has_market_report}")
        print(f"   ✓ 包含 fundamentals_report: {has_fundamentals_report}")
        print(f"   ✓ 包含 news_report: {has_news_report}")
        print(f"   ✓ 包含 report_sector_report: {has_sector_report}")
        print(f"   ✓ 包含 report_index_report: {has_index_report}")
        print(f"   ✓ 包含 report_bull_report: {has_bull_report}")
        print(f"   ✓ 包含 report_bear_report: {has_bear_report}")
        print(f"   ✓ 不包含 risk_assessment: {no_risk_assessment}")
        print(f"   ✓ 包含交易要求: {has_trading_requirements}")
        
        if not (has_investment_plan and has_market_report and has_fundamentals_report and 
                has_news_report and has_sector_report and has_index_report and 
                has_bull_report and has_bear_report and no_risk_assessment and has_trading_requirements):
            all_ok = False
        
        # 显示前200字符预览
        if user_prompt:
            print(f"\n   User Prompt 预览（前200字符）:")
            print(f"   {user_prompt[:200]}...")
    
    print(f"\n{'=' * 80}")
    if all_ok:
        print("✅ 所有模板验证通过！")
    else:
        print("⚠️ 部分模板存在问题，请检查")
    print(f"{'=' * 80}")
    
    client.close()

if __name__ == "__main__":
    verify_trader_v2_templates()

