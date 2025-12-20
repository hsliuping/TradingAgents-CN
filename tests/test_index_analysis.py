#!/usr/bin/env python3
"""
沪深300指数分析测试脚本
测试新增的指数分析功能
"""

import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ["TUSHARE_TOKEN"] = "2876ea85cb005fb5fa17c809a98174f2d5aae8b1f830110a5ead6211"

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s'
)
logger = logging.getLogger(__name__)


async def test_semiconductor_index_analysis():
    """测试半导体指数分析"""
    
    print("\n" + "="*80)
    print("🎯 半导体指数分析测试")
    print("="*80 + "\n")
    
    try:
        # 1. 创建指数分析图
        logger.info("📊 步骤1: 创建指数分析图实例...")
        config = DEFAULT_CONFIG.copy()
        
        # 🔧 使用DeepSeek作为LLM提供商
        config["llm_provider"] = "deepseek"
        config["quick_think_llm"] = "deepseek-chat"
        config["deep_think_llm"] = "deepseek-reasoner"
        config["backend_url"] = "https://api.deepseek.com"
        
        logger.info(f"🤖 LLM配置: DeepSeek")
        logger.info(f"   - 快速模型: {config['quick_think_llm']}")
        logger.info(f"   - 深度模型: {config['deep_think_llm']}")
        logger.info(f"   - API地址: {config['backend_url']}")
        
        graph = TradingAgentsGraph(
            selected_analysts=[],  # 指数分析不需要个股分析师列表
            debug=True,
            config=config,
            analysis_type="index"  # ⭐ 指定为指数分析
        )
        logger.info("✅ 指数分析图实例创建成功\n")
        
        # 2. 准备分析参数
        index_code = "sh931865"  # 中证半导体指数 (也可用 h30184.CSI 或 931865.CSI)
        trade_date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"📋 步骤2: 准备分析参数...")
        logger.info(f"   - 指数代码: {index_code} (中证半导体产业指数)")
        logger.info(f"   - 分析日期: {trade_date}")
        logger.info(f"   - 分析类型: 指数分析\n")
        
        # 3. 执行分析
        logger.info("🚀 步骤3: 开始执行指数分析...")
        logger.info("   预计耗时: 2-5分钟\n")
        
        start_time = datetime.now()
        
        final_state, decision = await asyncio.to_thread(
            graph.propagate,
            company_name=index_code,
            trade_date=trade_date,
            progress_callback=None,
            task_id="test_semiconductor_001"
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\n✅ 分析完成! 耗时: {duration:.2f}秒\n")
        
        # 4. 展示分析结果
        print("\n" + "="*80)
        print("📊 分析结果汇总")
        print("="*80 + "\n")
        
        # 检查各个报告
        reports = {
            "宏观经济分析": final_state.get("macro_report", ""),
            "政策分析": final_state.get("policy_report", ""),
            "板块轮动分析": final_state.get("sector_report", ""),
            "综合策略建议": final_state.get("strategy_report", "")
        }
        
        for report_name, report_content in reports.items():
            print(f"\n{'─'*80}")
            print(f"📝 {report_name}")
            print(f"{'─'*80}")
            
            if report_content:
                # 截取前500个字符作为预览
                preview = report_content[:500] if len(report_content) > 500 else report_content
                print(preview)
                if len(report_content) > 500:
                    print(f"\n... (完整报告共 {len(report_content)} 字符)\n")
            else:
                print("⚠️ 报告内容为空\n")
        
        # 5. 输出完整状态信息
        print(f"\n{'='*80}")
        print("🔍 完整状态信息")
        print(f"{'='*80}\n")
        
        print(f"分析指数: {final_state.get('company_of_interest', 'N/A')}")
        print(f"分析日期: {final_state.get('trade_date', 'N/A')}")
        print(f"是否为指数: {final_state.get('is_index', False)}")
        print(f"消息数量: {len(final_state.get('messages', []))}")
        
        # 工具调用统计
        print(f"\n📊 工具调用统计:")
        print(f"  - 宏观数据工具: {final_state.get('macro_tool_call_count', 0)} 次")
        print(f"  - 政策新闻工具: {final_state.get('policy_tool_call_count', 0)} 次")
        print(f"  - 板块轮动工具: {final_state.get('sector_tool_call_count', 0)} 次")
        
        # 决策信息
        print(f"\n💡 决策信息:")
        print(f"  - 分析类型: {decision.get('analysis_type', 'N/A')}")
        print(f"  - 模型信息: {decision.get('model_info', 'N/A')}")
        if decision.get('analysis_type') == 'index':
            print(f"  - 指数代码: {decision.get('index_code', 'N/A')}")
            print(f"  - 分析日期: {decision.get('trade_date', 'N/A')}")
        
        # 6. 保存完整报告到文件 (包含Agent对话历史)
        output_dir = project_root / "data" / "analysis_results" / "index"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存简洁版报告
        output_file = output_dir / f"semiconductor_{timestamp}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"半导体指数分析报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")
            
            for report_name, report_content in reports.items():
                f.write(f"\n{'─'*80}\n")
                f.write(f"{report_name}\n")
                f.write(f"{'─'*80}\n\n")
                f.write(report_content if report_content else "无内容\n")
        
        # 保存详细版报告 (包含Agent对话和工具调用)
        detailed_file = output_dir / f"semiconductor_{timestamp}_detailed.txt"
        with open(detailed_file, "w", encoding="utf-8") as f:
            f.write(f"半导体指数分析详细报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")
            
            # 📊 基本信息
            f.write(f"\n{'═'*80}\n")
            f.write(f"📊 基本信息\n")
            f.write(f"{'═'*80}\n\n")
            f.write(f"指数代码: {final_state.get('company_of_interest', 'N/A')}\n")
            f.write(f"分析日期: {final_state.get('trade_date', 'N/A')}\n")
            f.write(f"分析类型: 指数分析\n")
            f.write(f"执行时间: {duration:.2f}秒\n")
            f.write(f"模型信息: {decision.get('model_info', 'N/A')}\n\n")
            
            # 📝 分析报告
            for report_name, report_content in reports.items():
                f.write(f"\n{'─'*80}\n")
                f.write(f"{report_name}\n")
                f.write(f"{'─'*80}\n\n")
                f.write(report_content if report_content else "无内容\n")
            
            # 🤖 Agent对话历史
            f.write(f"\n\n{'═'*80}\n")
            f.write(f"🤖 Agent对话历史\n")
            f.write(f"{'═'*80}\n\n")
            
            messages = final_state.get("messages", [])
            f.write(f"总消息数: {len(messages)}\n\n")
            
            for idx, msg in enumerate(messages, 1):
                msg_type = type(msg).__name__
                f.write(f"\n{'─'*80}\n")
                f.write(f"消息 #{idx} - {msg_type}\n")
                f.write(f"{'─'*80}\n")
                
                # 提取消息内容
                if hasattr(msg, 'content'):
                    content = msg.content
                    if isinstance(content, str):
                        # 限制每条消息的长度以避免文件过大
                        preview = content[:1000] if len(content) > 1000 else content
                        f.write(f"{preview}\n")
                        if len(content) > 1000:
                            f.write(f"\n... (完整内容共 {len(content)} 字符)\n")
                    elif isinstance(content, list):
                        # 处理包含工具调用的消息
                        for item in content:
                            if isinstance(item, dict):
                                if item.get('type') == 'text':
                                    text = item.get('text', '')
                                    preview = text[:500] if len(text) > 500 else text
                                    f.write(f"文本: {preview}\n")
                                    if len(text) > 500:
                                        f.write(f"... (共 {len(text)} 字符)\n")
                                elif item.get('type') == 'tool_use':
                                    f.write(f"\n🔧 工具调用:\n")
                                    f.write(f"  工具名: {item.get('name', 'unknown')}\n")
                                    f.write(f"  工具ID: {item.get('id', 'unknown')}\n")
                                    tool_input = str(item.get('input', {}))[:200]
                                    f.write(f"  参数: {tool_input}\n")
                            elif isinstance(item, str):
                                preview = item[:500] if len(item) > 500 else item
                                f.write(f"{preview}\n")
                                if len(item) > 500:
                                    f.write(f"... (共 {len(item)} 字符)\n")
                
                # 检查是否有工具调用
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    f.write(f"\n🔧 工具调用 ({len(msg.tool_calls)}个):\n")
                    for tc in msg.tool_calls:
                        f.write(f"  - {tc.get('name', 'unknown')}\n")
                
                # 检查是否为工具响应
                if hasattr(msg, 'name'):
                    f.write(f"\n工具名称: {msg.name}\n")
            
            # 📊 工具调用统计
            f.write(f"\n\n{'═'*80}\n")
            f.write(f"📊 工具调用统计\n")
            f.write(f"{'═'*80}\n\n")
            f.write(f"宏观数据工具: {final_state.get('macro_tool_call_count', 0)} 次\n")
            f.write(f"政策新闻工具: {final_state.get('policy_tool_call_count', 0)} 次\n")
            f.write(f"板块轮动工具: {final_state.get('sector_tool_call_count', 0)} 次\n")
            f.write(f"策略分析工具: {final_state.get('strategy_tool_call_count', 0)} 次\n")
        
        logger.info(f"\n💾 完整报告已保存至:")
        logger.info(f"   - 简洁版: {output_file}")
        logger.info(f"   - 详细版: {detailed_file}")
        
        print(f"\n{'='*80}")
        print("✅ 测试完成!")
        print(f"{'='*80}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                   半导体指数分析测试                                 ║
║                                                                    ║
║  功能: 测试新增的指数分析功能                                       ║
║  指数: sh000300 (中证半导体)                                       ║
║  预计耗时: 2-5分钟                                                  ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # 运行测试
    result = asyncio.run(test_semiconductor_index_analysis())
    
    # 退出码
    sys.exit(0 if result else 1)
