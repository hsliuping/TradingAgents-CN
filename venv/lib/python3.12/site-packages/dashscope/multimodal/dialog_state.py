# dialog_state.py

from enum import Enum


class DialogState(Enum):
    """
    对话状态枚举类，定义了对话机器人可能处于的不同状态。

    Attributes:
        IDLE (str): 表示机器人处于空闲状态。
        LISTENING (str): 表示机器人正在监听用户输入。
        THINKING (str): 表示机器人正在思考。
        RESPONDING (str): 表示机器人正在生成或回复中。
    """
    IDLE = 'Idle'
    LISTENING = 'Listening'
    THINKING = 'Thinking'
    RESPONDING = 'Responding'


class StateMachine:
    """
    状态机类，用于管理机器人的状态转换。

    Attributes:
        current_state (DialogState): 当前状态。
    """

    def __init__(self):
        # 初始化状态机时设置初始状态为IDLE
        self.current_state = DialogState.IDLE

    def change_state(self, new_state: str) -> None:
        """
        更改当前状态到指定的新状态。

        Args:
            new_state (str): 要切换到的新状态。

        Raises:
            ValueError: 如果尝试切换到一个无效的状态，则抛出此异常。
        """
        if new_state in [state.value for state in DialogState]:
            self.current_state = DialogState(new_state)
        else:
            raise ValueError("无效的状态类型")

    def get_current_state(self) -> DialogState:
        """
        获取当前状态。

        Returns:
            DialogState: 当前状态。
        """
        return self.current_state
