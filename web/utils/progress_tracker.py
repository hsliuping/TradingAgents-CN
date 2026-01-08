"""
智能进度跟踪器
根据分析师数量、研究深度动态计算进度和时间预估
"""

import time
from typing import Optional, Callable, Dict, List
import streamlit as st

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('progress')

class SmartAnalysisProgressTracker:
    """智能分析进度跟踪器"""

    def __init__(self, analysts: List[str], research_depth: int, llm_provider: str, callback: Optional[Callable] = None):
        self.callback = callback
        self.analysts = analysts
        self.research_depth = research_depth
        self.llm_provider = llm_provider
        self.steps = []
        self.current_step = 0
        self.start_time = time.time()

        # 根据分析师数量和研究深度动态生成步骤
        self.analysis_steps = self._generate_dynamic_steps()
        self.estimated_duration = self._estimate_total_duration()

    def _generate_dynamic_steps(self) -> List[Dict]:
        """根据分析师数量动态生成分析步骤"""
        steps = [
            {"name": "数据验证", "description": "验证股票代码并预获取数据", "weight": 0.05},
            {"name": "环境准备", "description": "检查API密钥和环境配置", "weight": 0.02},
            {"name": "成本预估", "description": "预估分析成本", "weight": 0.01},
            {"name": "参数配置", "description": "配置分析参数和模型", "weight": 0.02},
            {"name": "引擎初始化", "description": "初始化AI分析引擎", "weight": 0.05},
        ]

        # 为每个分析师添加专门的步骤
        analyst_weight = 0.8 / len(self.analysts)  # 80%的时间用于分析师工作
        for analyst in self.analysts:
            analyst_name = self._get_analyst_display_name(analyst)
            steps.append({
                "name": f"{analyst_name}分析",
                "description": f"{analyst_name}正在进行专业分析",
                "weight": analyst_weight
            })

        # 最后的整理步骤
        steps.append({"name": "结果整理", "description": "整理分析结果和生成报告", "weight": 0.05})

        return steps

    def _get_analyst_display_name(self, analyst: str) -> str:
        """获取分析师显示名称"""
        name_map = {
            'market': '市场分析师',
            'fundamentals': '基本面分析师',
            'technical': '技术分析师',
            'sentiment': '情绪分析师',
            'risk': '风险分析师'
        }
        return name_map.get(analyst, analyst)

    def _estimate_total_duration(self) -> float:
        """根据分析师数量、研究深度、模型类型预估总时长（秒）"""
        # 基础时间（秒）- 环境准备、配置等
        base_time = 60

        # 每个分析师的实际耗时（基于真实测试数据）
        analyst_base_time = {
            1: 180,  # 快速分析：每个分析师约3分钟
            2: 360,  # 标准分析：每个分析师约6分钟
            3: 600   # 深度分析：每个分析师约10分钟
        }.get(self.research_depth, 360)

        analyst_time = len(self.analysts) * analyst_base_time

        # 模型速度影响（基于实际测试）
        model_multiplier = {
            'dashscope': 1.0,  # 阿里百炼速度适中
            'deepseek': 0.7,   # DeepSeek较快
            'google': 1.3      # Google较慢
        }.get(self.llm_provider, 1.0)

        # 研究深度额外影响（工具调用复杂度）
        depth_multiplier = {
            1: 0.8,  # 快速分析，较少工具调用
            2: 1.0,  # 基础分析，标准工具调用
            3: 1.3   # 标准分析，更多工具调用和推理
        }.get(self.research_depth, 1.0)

        total_time = (base_time + analyst_time) * model_multiplier * depth_multiplier
        return total_time
    
    def update(self, message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
        """更新进度"""
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        # 记录步骤
        self.steps.append({
            'message': message,
            'timestamp': current_time,
            'elapsed': elapsed_time
        })

        # 根据消息内容自动判断当前步骤
        if step is None:
            step = self._detect_step_from_message(message)

        if step is not None:
            # 特殊处理：如果检测到"模块完成"，推进到下一步
            if "模块完成" in message and step == self.current_step:
                # 分析师完成，推进到下一步
                next_step = min(step + 1, len(self.analysis_steps) - 1)
                self.current_step = next_step
                logger.info(f"📊 [进度更新] 分析师完成，推进到步骤 {self.current_step + 1}/{len(self.analysis_steps)}")
            # 防止步骤倒退：只有当检测到的步骤大于等于当前步骤时才更新
            elif step >= self.current_step:
                self.current_step = step
                logger.debug(f"📊 [进度更新] 步骤推进到 {self.current_step + 1}/{len(self.analysis_steps)}")
            else:
                logger.debug(f"📊 [进度更新] 忽略倒退步骤：检测到步骤{step + 1}，当前步骤{self.current_step + 1}")

        # 如果是完成消息，确保进度为100%
        if "分析完成" in message or "分析成功" in message or "✅ 分析完成" in message:
            self.current_step = len(self.analysis_steps) - 1
            logger.info(f"📊 [进度更新] 分析完成，设置为最终步骤 {self.current_step + 1}/{len(self.analysis_steps)}")

        # 调用回调函数
        if self.callback:
            progress = self._calculate_weighted_progress()
            remaining_time = self._estimate_remaining_time(progress, elapsed_time)
            self.callback(message, self.current_step, len(self.analysis_steps), progress, elapsed_time, remaining_time)

    def _calculate_weighted_progress(self) -> float:
        """根据步骤权重计算进度"""
        if self.current_step >= len(self.analysis_steps):
            return 1.0

        # 如果是最后一步，返回100%
        if self.current_step == len(self.analysis_steps) - 1:
            return 1.0

        completed_weight = sum(step["weight"] for step in self.analysis_steps[:self.current_step])
        total_weight = sum(step["weight"] for step in self.analysis_steps)

        return min(completed_weight / total_weight, 1.0)

    def _estimate_remaining_time(self, progress: float, elapsed_time: float) -> float:
        """基于预估总时长计算剩余时间"""
        if progress >= 1.0:
            return 0.0

        # 使用预估的总时长（固定值）
        # 预计剩余 = 预估总时长 - 已用时间
        return max(self.estimated_duration - elapsed_time, 0)
    
    def _detect_step_from_message(self, message: str) -> Optional[int]:
        """根据消息内容智能检测当前步骤"""
        message_lower = message.lower()

        # 开始分析阶段 - 只匹配最初的开始消息
        if "🚀 开始股票分析" in message:
            return 0
        # 数据验证阶段
        elif "验证" in message or "预获取" in message or "数据准备" in message:
            return 0
        # 环境准备阶段
        elif "环境" in message or "api" in message_lower or "密钥" in message:
            return 1
        # 成本预估阶段
        elif "成本" in message or "预估" in message:
            return 2
        # 参数配置阶段
        elif "配置" in message or "参数" in message:
            return 3
        # 引擎初始化阶段
        elif "初始化" in message or "引擎" in message:
            return 4
        # 分析师工作阶段 - 根据分析师名称和工具调用匹配
        elif any(analyst_name in message for analyst_name in ["市场分析师", "基本面分析师", "技术分析师", "情绪分析师", "风险分析师"]):
            # 找到对应的分析师步骤
            for i, step in enumerate(self.analysis_steps):
                if "分析师" in step["name"]:
                    # 检查消息中是否包含对应的分析师类型
                    if "市场" in message and "市场" in step["name"]:
                        return i
                    elif "基本面" in message and "基本面" in step["name"]:
                        return i
                    elif "技术" in message and "技术" in step["name"]:
                        return i
                    elif "情绪" in message and "情绪" in step["name"]:
                        return i
                    elif "风险" in message and "风险" in step["name"]:
                        return i
        # 工具调用阶段 - 检测分析师正在使用工具
        elif "工具调用" in message or "正在调用" in message or "tool" in message.lower():
            # 如果当前步骤是分析师步骤，保持当前步骤
            if self.current_step < len(self.analysis_steps) and "分析师" in self.analysis_steps[self.current_step]["name"]:
                return self.current_step
        # 模块开始/完成日志
        elif "模块开始" in message or "模块完成" in message:
            # 从日志中提取分析师类型
            if "market_analyst" in message or "market" in message or "市场" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "市场" in step["name"]:
                        return i
            elif "fundamentals_analyst" in message or "fundamentals" in message or "基本面" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "基本面" in step["name"]:
                        return i
            elif "technical_analyst" in message or "technical" in message or "技术" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "技术" in step["name"]:
                        return i
            elif "sentiment_analyst" in message or "sentiment" in message or "情绪" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "情绪" in step["name"]:
                        return i
            elif "risk_analyst" in message or "risk" in message or "风险" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "风险" in step["name"]:
                        return i
            elif "graph_signal_processing" in message or "signal" in message or "信号" in message:
                for i, step in enumerate(self.analysis_steps):
                    if "信号" in step["name"] or "整理" in step["name"]:
                        return i
        # 结果整理阶段
        elif "整理" in message or "结果" in message:
            return len(self.analysis_steps) - 1
        # 完成阶段
        elif "完成" in message or "成功" in message:
            return len(self.analysis_steps) - 1

        return None
    
    def get_current_step_info(self) -> Dict:
        """获取当前步骤信息"""
        if self.current_step < len(self.analysis_steps):
            return self.analysis_steps[self.current_step]
        return {"name": "完成", "description": "分析已完成", "weight": 0}

    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        return self._calculate_weighted_progress() * 100

    def get_elapsed_time(self) -> float:
        """获取已用时间"""
        return time.time() - self.start_time

    def get_estimated_total_time(self) -> float:
        """获取预估总时间"""
        return self.estimated_duration

    def format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"

class SmartStreamlitProgressDisplay:
    """智能Streamlit进度显示组件"""

    def __init__(self, container):
        self.container = container
        self.progress_bar = None
        self.status_text = None
        self.step_info = None
        self.time_info = None
        self.setup_display()

    def setup_display(self):
        """设置显示组件"""
        with self.container:
            st.markdown("### 📊 分析进度")
            self.progress_bar = st.progress(0)
            self.status_text = st.empty()
            self.step_info = st.empty()
            self.time_info = st.empty()

    def update(self, message: str, current_step: int, total_steps: int, progress: float, elapsed_time: float, remaining_time: float):
        """更新显示"""
        # 更新进度条
        self.progress_bar.progress(progress)

        # 更新状态文本
        self.status_text.markdown(f"**当前状态:** 📋 {message}")

        # 更新步骤信息
        step_text = f"**进度:** 第 {current_step + 1} 步，共 {total_steps} 步 ({progress:.1%})"
        self.step_info.markdown(step_text)

        # 更新时间信息
        time_text = f"**已用时间:** {self._format_time(elapsed_time)}"
        if remaining_time > 0:
            time_text += f" | **预计剩余:** {self._format_time(remaining_time)}"

        self.time_info.markdown(time_text)
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def clear(self):
        """清除显示"""
        self.container.empty()

def create_smart_progress_callback(display: SmartStreamlitProgressDisplay, analysts: List[str], research_depth: int, llm_provider: str) -> Callable:
    """创建智能进度回调函数"""
    tracker = SmartAnalysisProgressTracker(analysts, research_depth, llm_provider)

    def callback(message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
        # 如果明确指定了步骤和总步骤，使用旧的固定模式（兼容性）
        if step is not None and total_steps is not None and total_steps == 10:
            # 兼容旧的10步模式，但使用智能时间预估
            progress = step / max(total_steps - 1, 1) if total_steps > 1 else 1.0
            progress = min(progress, 1.0)
            elapsed_time = tracker.get_elapsed_time()
            remaining_time = tracker._estimate_remaining_time(progress, elapsed_time)
            display.update(message, step, total_steps, progress, elapsed_time, remaining_time)
        else:
            # 使用新的智能跟踪模式
            tracker.update(message, step, total_steps)
            current_step = tracker.current_step
            total_steps_count = len(tracker.analysis_steps)
            progress = tracker.get_progress_percentage() / 100
            elapsed_time = tracker.get_elapsed_time()
            remaining_time = tracker._estimate_remaining_time(progress, elapsed_time)
            display.update(message, current_step, total_steps_count, progress, elapsed_time, remaining_time)

    return callback

# 向后兼容的函数
def create_progress_callback(display, analysts=None, research_depth=2, llm_provider="dashscope") -> Callable:
    """创建进度回调函数（向后兼容）"""
    if hasattr(display, '__class__') and 'Smart' in display.__class__.__name__:
        return create_smart_progress_callback(display, analysts or ['market', 'fundamentals'], research_depth, llm_provider)
    else:
        # 旧版本兼容
        tracker = SmartAnalysisProgressTracker(analysts or ['market', 'fundamentals'], research_depth, llm_provider)

        def callback(message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
            if step is not None and total_steps is not None:
                progress = step / max(total_steps - 1, 1) if total_steps > 1 else 1.0
                progress = min(progress, 1.0)
                elapsed_time = tracker.get_elapsed_time()
                display.update(message, step, total_steps, progress, elapsed_time)
            else:
                tracker.update(message, step, total_steps)
                current_step = tracker.current_step
                total_steps_count = len(tracker.analysis_steps)
                progress = tracker.get_progress_percentage() / 100
                elapsed_time = tracker.get_elapsed_time()
                display.update(message, current_step, total_steps_count, progress, elapsed_time)

        return callback
