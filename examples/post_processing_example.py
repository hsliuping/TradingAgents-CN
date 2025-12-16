"""
后处理Agent使用示例

展示如何在工作流中使用后处理Agent
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents.post_processors import (
    ReportSaverAgent,
    EmailNotifierAgent,
    SystemNotifierAgent
)


def example_1_basic_report_saving():
    """示例1：基本的报告保存"""
    print("\n" + "="*60)
    print("示例1：基本的报告保存")
    print("="*60)
    
    # 创建报告保存Agent
    saver = ReportSaverAgent(
        operations=[
            {
                "type": "save_to_file",
                "path": "data/reports/{ticker}_{date}.json",
                "format": "json"
            }
        ]
    )
    
    # 模拟分析结果
    state = {
        "ticker": "AAPL",
        "analysis_date": "20231215",
        "market_report": "市场分析：AAPL股价稳定上涨...",
        "news_report": "新闻分析：苹果发布新产品...",
        "investment_plan": {
            "recommendation": "买入",
            "confidence_score": 0.85
        }
    }
    
    # 执行保存
    result = saver.execute(state)
    
    print(f"保存结果: {result['report_saver_status']}")


def example_2_conditional_email():
    """示例2：条件邮件通知"""
    print("\n" + "="*60)
    print("示例2：条件邮件通知（只在重要信号时发送）")
    print("="*60)
    
    # 创建邮件通知Agent（只在买入/卖出信号且置信度>0.7时发送）
    notifier = EmailNotifierAgent(
        operations=[
            {
                "type": "send_email",
                "to": "investor@example.com",
                "subject": "{ticker} 重要信号 - {recommendation}",
                "template": "important_signal",
                "use_llm_summary": False
            }
        ],
        conditions=[
            {
                "field": "investment_plan.recommendation",
                "operator": "in",
                "value": ["买入", "卖出"]
            },
            {
                "field": "investment_plan.confidence_score",
                "operator": "greater_than",
                "value": 0.7
            }
        ]
    )
    
    # 测试1：满足条件的情况
    state_strong_signal = {
        "ticker": "AAPL",
        "investment_plan": {
            "recommendation": "买入",
            "confidence_score": 0.85
        }
    }
    
    result = notifier.execute(state_strong_signal)
    print(f"强信号结果: {result['email_notifier_status']}")
    
    # 测试2：不满足条件的情况
    state_weak_signal = {
        "ticker": "AAPL",
        "investment_plan": {
            "recommendation": "持有",
            "confidence_score": 0.6
        }
    }
    
    result = notifier.execute(state_weak_signal)
    print(f"弱信号结果: {result['email_notifier_status']}")


def example_3_multiple_post_processors():
    """示例3：组合多个后处理Agent"""
    print("\n" + "="*60)
    print("示例3：组合多个后处理Agent")
    print("="*60)
    
    # 模拟完整的分析结果
    state = {
        "user_id": "user123",
        "ticker": "AAPL",
        "analysis_date": "20231215",
        "success": True,
        "market_report": "市场分析报告...",
        "news_report": "新闻分析报告...",
        "investment_plan": {
            "recommendation": "买入",
            "confidence_score": 0.85
        }
    }
    
    # 1. 保存报告
    saver = ReportSaverAgent(
        operations=[
            {
                "type": "save_to_file",
                "path": "data/reports/{ticker}_{date}.json",
                "format": "json"
            }
        ],
        conditions=[
            {"field": "success", "operator": "equals", "value": True}
        ]
    )
    
    # 2. 发送邮件
    email_notifier = EmailNotifierAgent(
        operations=[
            {
                "type": "send_email",
                "to": "user@example.com",
                "subject": "{ticker} 分析完成",
                "template": "analysis_complete"
            }
        ],
        conditions=[
            {"field": "success", "operator": "equals", "value": True}
        ]
    )
    
    # 3. 发送系统通知
    system_notifier = SystemNotifierAgent(
        operations=[
            {
                "type": "send_notification",
                "notification_type": "analysis",
                "title": "{ticker} 分析完成",
                "content": "分析已完成，请查看结果",
                "severity": "info"
            }
        ],
        conditions=[
            {"field": "success", "operator": "equals", "value": True}
        ]
    )
    
    # 依次执行所有后处理Agent
    print("\n执行后处理流程...")
    
    state = saver.execute(state)
    print(f"1. 报告保存: {state['report_saver_status']['success']}")
    
    state = email_notifier.execute(state)
    print(f"2. 邮件通知: {state['email_notifier_status']['success']}")
    
    state = system_notifier.execute(state)
    print(f"3. 系统通知: {state['system_notifier_status']['success']}")
    
    print("\n所有后处理完成！")


def example_4_complex_conditions():
    """示例4：复杂条件组合"""
    print("\n" + "="*60)
    print("示例4：复杂条件组合")
    print("="*60)
    
    # 创建具有多个复杂条件的Agent
    notifier = EmailNotifierAgent(
        operations=[
            {
                "type": "send_email",
                "to": "admin@example.com",
                "subject": "高风险交易信号",
                "template": "high_risk_alert"
            }
        ],
        conditions=[
            # 条件1：必须是买入或卖出
            {
                "field": "investment_plan.recommendation",
                "operator": "in",
                "value": ["买入", "卖出"]
            },
            # 条件2：置信度必须很高
            {
                "field": "investment_plan.confidence_score",
                "operator": "greater_than",
                "value": 0.8
            },
            # 条件3：必须有风险评估
            {
                "field": "risk_assessment",
                "operator": "exists",
                "value": None
            }
        ]
    )
    
    # 测试满足所有条件
    state = {
        "investment_plan": {
            "recommendation": "买入",
            "confidence_score": 0.9
        },
        "risk_assessment": {
            "level": "high"
        }
    }
    
    result = notifier.execute(state)
    print(f"结果: {result['email_notifier_status']}")


if __name__ == "__main__":
    # 运行所有示例
    example_1_basic_report_saving()
    example_2_conditional_email()
    example_3_multiple_post_processors()
    example_4_complex_conditions()
    
    print("\n" + "="*60)
    print("所有示例运行完成！")
    print("="*60)

