"""
工作流控制信号

跨层共享的协作式控制流异常基类：
- core 层（engine / workflow_api）识别并放行该类异常，不得吞掉或转成失败结果
- app 层继承该类实现具体语义（取消 / 暂停 / 被新执行取代）
"""


class WorkflowControlSignal(Exception):
    """工作流控制信号基类（取消 / 暂停 / 被取代等协作式中断）"""

    pass
