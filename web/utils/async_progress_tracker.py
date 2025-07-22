#!/usr/bin/env python3
"""
Asynchronous progress tracker
Supports both Redis and file storage. The frontend polls for progress updates periodically.
"""

import json
import time
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading
from pathlib import Path

# Import logging module
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('async_progress')

"""Safely serialize objects, handling non-serializable types"""
def safe_serialize(obj):
    if hasattr(obj, 'dict'):
        # Pydantic objects
        return obj.dict()
    elif hasattr(obj, '__dict__'):
        # Regular objects, convert to dictionary
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):  # Skip private attributes
                try:
                    json.dumps(value)  # Test if serializable
                    result[key] = value
                except (TypeError, ValueError):
                    result[key] = str(value)  # Convert to string
        return result
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: safe_serialize(value) for key, value in obj.items()}
    else:
        try:
            json.dumps(obj)  # Test if serializable
            return obj
        except (TypeError, ValueError):
            return str(obj)  # Convert to string

class AsyncProgressTracker:
    """Asynchronous progress tracker"""
    
    def __init__(self, analysis_id: str, analysts: List[str], research_depth: int, llm_provider: str):
        self.analysis_id = analysis_id
        self.analysts = analysts
        self.research_depth = research_depth
        self.llm_provider = llm_provider
        self.start_time = time.time()
        
        # Generate analysis steps
        self.analysis_steps = self._generate_dynamic_steps()
        self.estimated_duration = self._estimate_total_duration()
        
        # Initialize status
        self.current_step = 0
        self.progress_data = {
            'analysis_id': analysis_id,
            'status': 'running',
            'current_step': 0,
            'total_steps': len(self.analysis_steps),
            'progress_percentage': 0.0,
            'current_step_name': self.analysis_steps[0]['name'],
            'current_step_description': self.analysis_steps[0]['description'],
            'elapsed_time': 0.0,
            'estimated_total_time': self.estimated_duration,
            'remaining_time': self.estimated_duration,
            'last_message': '准备开始分析...',
            'last_update': time.time(),
            'start_time': self.start_time,
            'steps': self.analysis_steps
        }
        
        # Try to initialize Redis, fallback to file
        self.redis_client = None
        self.use_redis = self._init_redis()
        
        if not self.use_redis:
            # Use file storage
            self.progress_file = f"./data/progress_{analysis_id}.json"
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        
        # Save initial status
        self._save_progress()
        
        logger.info(f"📊 [异步进度] 初始化完成: {analysis_id}, 存储方式: {'Redis' if self.use_redis else '文件'}")

        # Register with logging system for automatic progress updates
        try:
            from .progress_log_handler import register_analysis_tracker
            import threading

            # Use timeout mechanism to avoid deadlock
            def register_with_timeout():
                try:
                    register_analysis_tracker(self.analysis_id, self)
                    print(f"✅ [进度集成] 跟踪器注册成功: {self.analysis_id}")
                except Exception as e:
                    print(f"❌ [进度集成] 跟踪器注册失败: {e}")

            # Register in a separate thread to avoid blocking the main thread
            register_thread = threading.Thread(target=register_with_timeout, daemon=True)
            register_thread.start()
            register_thread.join(timeout=2.0)  # 2 seconds timeout

            if register_thread.is_alive():
                print(f"⚠️ [进度集成] 跟踪器注册超时，继续执行: {self.analysis_id}")

        except ImportError:
            logger.debug("📊 [异步进度] 日志集成不可用")
        except Exception as e:
            print(f"❌ [进度集成] 跟踪器注册异常: {e}")
    
    def _init_redis(self) -> bool:
        """Initialize Redis connection"""
        try:
            # First check REDIS_ENABLED environment variable
            redis_enabled_raw = os.getenv('REDIS_ENABLED', 'false')
            redis_enabled = redis_enabled_raw.lower()
            logger.info(f"🔍 [Redis检查] REDIS_ENABLED原值='{redis_enabled_raw}' -> 处理后='{redis_enabled}'")

            if redis_enabled != 'true':
                logger.info(f"📊 [异步进度] Redis已禁用，使用文件存储")
                return False

            import redis

            # Get Redis configuration from environment variables
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD', None)
            redis_db = int(os.getenv('REDIS_DB', 0))

            # Create Redis connection
            if redis_password:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    decode_responses=True
                )
            else:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )

            # Test connection
            self.redis_client.ping()
            logger.info(f"📊 [异步进度] Redis连接成功: {redis_host}:{redis_port}")
            return True
        except Exception as e:
            logger.warning(f"📊 [异步进度] Redis连接失败，使用文件存储: {e}")
            return False
    
    def _generate_dynamic_steps(self) -> List[Dict]:
        """Dynamically generate analysis steps based on analyst count and research depth"""
        steps = [
            {"name": "📋 准备阶段", "description": "验证股票代码，检查数据源可用性", "weight": 0.05},
            {"name": "🔧 环境检查", "description": "检查API密钥配置，确保数据获取正常", "weight": 0.02},
            {"name": "💰 成本估算", "description": "根据分析深度预估API调用成本", "weight": 0.01},
            {"name": "⚙️ 参数设置", "description": "配置分析参数和AI模型选择", "weight": 0.02},
            {"name": "🚀 启动引擎", "description": "初始化AI分析引擎，准备开始分析", "weight": 0.05},
        ]

        # Add specific steps for each analyst
        analyst_base_weight = 0.6 / len(self.analysts)  # 60% of time for analysts
        for analyst in self.analysts:
            analyst_info = self._get_analyst_step_info(analyst)
            steps.append({
                "name": analyst_info["name"],
                "description": analyst_info["description"],
                "weight": analyst_base_weight
            })

        # Add subsequent steps based on research depth
        if self.research_depth >= 2:
            # Standard and deep analysis include researcher debates
            steps.extend([
                {"name": "📈 多头观点", "description": "从乐观角度分析投资机会和上涨潜力", "weight": 0.06},
                {"name": "📉 空头观点", "description": "从谨慎角度分析投资风险和下跌可能", "weight": 0.06},
                {"name": "🤝 观点整合", "description": "综合多空观点，形成平衡的投资建议", "weight": 0.05},
            ])

        # All depths include trading decisions
        steps.append({"name": "💡 投资建议", "description": "基于分析结果制定具体的买卖建议", "weight": 0.06})

        if self.research_depth >= 3:
            # Deep analysis includes detailed risk assessment
            steps.extend([
                {"name": "🔥 激进策略", "description": "评估高风险高收益的投资策略", "weight": 0.03},
                {"name": "🛡️ 保守策略", "description": "评估低风险稳健的投资策略", "weight": 0.03},
                {"name": "⚖️ 平衡策略", "description": "评估风险收益平衡的投资策略", "weight": 0.03},
                {"name": "🎯 风险控制", "description": "制定风险控制措施和止损策略", "weight": 0.04},
            ])
        else:
            # Simplified risk assessment for fast and standard analysis
            steps.append({"name": "⚠️ 风险提示", "description": "识别主要投资风险并提供风险提示", "weight": 0.05})

        # Final organization steps
        steps.append({"name": "📊 生成报告", "description": "整理所有分析结果，生成最终投资报告", "weight": 0.04})

        # Rebalance weights to ensure total sum is 1.0
        total_weight = sum(step["weight"] for step in steps)
        for step in steps:
            step["weight"] = step["weight"] / total_weight

        return steps
    
    def _get_analyst_display_name(self, analyst: str) -> str:
        """Get analyst display name (for compatibility)"""
        name_map = {
            'market': '市场分析师',
            'fundamentals': '基本面分析师',
            'technical': '技术分析师',
            'sentiment': '情绪分析师',
            'risk': '风险分析师'
        }
        return name_map.get(analyst, f'{analyst}分析师')

    def _get_analyst_step_info(self, analyst: str) -> Dict[str, str]:
        """Get analyst step information (name and description)"""
        analyst_info = {
            'market': {
                "name": "📊 市场分析",
                "description": "分析股价走势、成交量、市场热度等市场表现"
            },
            'fundamentals': {
                "name": "💼 基本面分析",
                "description": "分析公司财务状况、盈利能力、成长性等基本面"
            },
            'technical': {
                "name": "📈 技术分析",
                "description": "分析K线图形、技术指标、支撑阻力等技术面"
            },
            'sentiment': {
                "name": "💭 情绪分析",
                "description": "分析市场情绪、投资者心理、舆论倾向等"
            },
            'news': {
                "name": "📰 新闻分析",
                "description": "分析相关新闻、公告、行业动态对股价的影响"
            },
            'social_media': {
                "name": "🌐 社交媒体",
                "description": "分析社交媒体讨论、网络热度、散户情绪等"
            },
            'risk': {
                "name": "⚠️ 风险分析",
                "description": "识别投资风险、评估风险等级、制定风控措施"
            }
        }

        return analyst_info.get(analyst, {
            "name": f"🔍 {analyst}分析",
            "description": f"进行{analyst}相关的专业分析"
        })
    
    def _estimate_total_duration(self) -> float:
        """Estimate total duration based on analyst count, research depth, and model type (seconds)"""
        # Base time (seconds) - environment preparation, configuration, etc.
        base_time = 60
        
        # Actual time for each analyst (based on real test data)
        analyst_base_time = {
            1: 120,  # Fast analysis: approximately 2 minutes per analyst
            2: 180,  # Basic analysis: approximately 3 minutes per analyst  
            3: 240   # Standard analysis: approximately 4 minutes per analyst
        }.get(self.research_depth, 180)
        
        analyst_time = len(self.analysts) * analyst_base_time
        
        # Model speed impact (based on actual tests)
        model_multiplier = {
            'dashscope': 1.0,  # Ali Baiyan speed is moderate
            'deepseek': 0.7,   # DeepSeek is faster
            'google': 1.3      # Google is slower
        }.get(self.llm_provider, 1.0)
        
        # Research depth additional impact (tool call complexity)
        depth_multiplier = {
            1: 0.8,  # Fast analysis, fewer tool calls
            2: 1.0,  # Basic analysis, standard tool calls
            3: 1.3   # Standard analysis, more tool calls and reasoning
        }.get(self.research_depth, 1.0)
        
        total_time = (base_time + analyst_time) * model_multiplier * depth_multiplier
        return total_time
    
    def update_progress(self, message: str, step: Optional[int] = None):
        """Update progress status"""
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        # Automatically detect step
        if step is None:
            step = self._detect_step_from_message(message)

        # Update step (prevent regression)
        if step is not None and step >= self.current_step:
            self.current_step = step
            logger.debug(f"📊 [异步进度] 步骤推进到 {self.current_step + 1}/{len(self.analysis_steps)}")

        # If it's a completion message, ensure progress is 100%
        if "分析完成" in message or "分析成功" in message or "✅ 分析完成" in message:
            self.current_step = len(self.analysis_steps) - 1
            logger.info(f"📊 [异步进度] 分析完成，设置为最终步骤")

        # Calculate progress
        progress_percentage = self._calculate_weighted_progress() * 100
        remaining_time = self._estimate_remaining_time(progress_percentage / 100, elapsed_time)

        # Update progress data
        current_step_info = self.analysis_steps[self.current_step] if self.current_step < len(self.analysis_steps) else self.analysis_steps[-1]

        # Special handling for tool call messages, update description but not step
        step_description = current_step_info['description']
        if "工具调用" in message:
            # Extract tool name and update description
            if "get_stock_market_data_unified" in message:
                step_description = "正在获取市场数据和技术指标..."
            elif "get_stock_fundamentals_unified" in message:
                step_description = "正在获取基本面数据和财务指标..."
            elif "get_china_stock_data" in message:
                step_description = "正在获取A股市场数据..."
            elif "get_china_fundamentals" in message:
                step_description = "正在获取A股基本面数据..."
            else:
                step_description = "正在调用分析工具..."
        elif "模块开始" in message:
            step_description = f"开始{current_step_info['name']}..."
        elif "模块完成" in message:
            step_description = f"{current_step_info['name']}已完成"

        self.progress_data.update({
            'current_step': self.current_step,
            'progress_percentage': progress_percentage,
            'current_step_name': current_step_info['name'],
            'current_step_description': step_description,
            'elapsed_time': elapsed_time,
            'remaining_time': remaining_time,
            'last_message': message,
            'last_update': current_time,
            'status': 'completed' if progress_percentage >= 100 else 'running'
        })

        # Save to storage
        self._save_progress()

        # Detailed update log
        step_name = current_step_info.get('name', 'Unknown')
        logger.info(f"📊 [进度更新] {self.analysis_id}: {message[:50]}...")
        logger.debug(f"📊 [进度详情] 步骤{self.current_step + 1}/{len(self.analysis_steps)} ({step_name}), 进度{progress_percentage:.1f}%, 耗时{elapsed_time:.1f}s")
    
    def _detect_step_from_message(self, message: str) -> Optional[int]:
        """Intelligently detect current step based on message content"""
        message_lower = message.lower()

        # Start analysis phase - only match initial start message
        if "🚀 开始股票分析" in message:
            return 0
        # Data validation phase
        elif "验证" in message or "预获取" in message or "数据准备" in message:
            return 0
        # Environment preparation phase
        elif "环境" in message or "api" in message_lower or "密钥" in message:
            return 1
        # Cost estimation phase
        elif "成本" in message or "预估" in message:
            return 2
        # Parameter configuration phase
        elif "配置" in message or "参数" in message:
            return 3
        # Engine initialization phase
        elif "初始化" in message or "引擎" in message:
            return 4
        # Module start log - only advance step when first started
        elif "模块开始" in message:
            # Extract analyst type from log, match new step names
            if "market_analyst" in message or "market" in message:
                return self._find_step_by_keyword(["市场分析", "市场"])
            elif "fundamentals_analyst" in message or "fundamentals" in message:
                return self._find_step_by_keyword(["基本面分析", "基本面"])
            elif "technical_analyst" in message or "technical" in message:
                return self._find_step_by_keyword(["技术分析", "技术"])
            elif "sentiment_analyst" in message or "sentiment" in message:
                return self._find_step_by_keyword(["情绪分析", "情绪"])
            elif "news_analyst" in message or "news" in message:
                return self._find_step_by_keyword(["新闻分析", "新闻"])
            elif "social_media_analyst" in message or "social" in message:
                return self._find_step_by_keyword(["社交媒体", "社交"])
            elif "risk_analyst" in message or "risk" in message:
                return self._find_step_by_keyword(["风险分析", "风险"])
            elif "bull_researcher" in message or "bull" in message:
                return self._find_step_by_keyword(["多头观点", "多头", "看涨"])
            elif "bear_researcher" in message or "bear" in message:
                return self._find_step_by_keyword(["空头观点", "空头", "看跌"])
            elif "research_manager" in message:
                return self._find_step_by_keyword(["观点整合", "整合"])
            elif "trader" in message:
                return self._find_step_by_keyword(["投资建议", "建议"])
            elif "risk_manager" in message:
                return self._find_step_by_keyword(["风险控制", "控制"])
            elif "graph_signal_processing" in message or "signal" in message:
                return self._find_step_by_keyword(["生成报告", "报告"])
        # Tool call log - do not advance step, only update description
        elif "工具调用" in message:
            # Stay on current step, do not advance
            return None
        # Module completion log - advance to next step
        elif "模块完成" in message:
            # When module completes, advance from current step to next step
            # No longer rely on module name, but advance based on current progress
            next_step = min(self.current_step + 1, len(self.analysis_steps) - 1)
            logger.debug(f"📊 [步骤推进] 模块完成，从步骤{self.current_step}推进到步骤{next_step}")
            return next_step

        return None

    def _find_step_by_keyword(self, keywords) -> Optional[int]:
        """Find step index by keyword"""
        if isinstance(keywords, str):
            keywords = [keywords]

        for i, step in enumerate(self.analysis_steps):
            for keyword in keywords:
                if keyword in step["name"]:
                    return i
        return None

    def _get_next_step(self, keyword: str) -> Optional[int]:
        """Get the next step for a specified keyword"""
        current_step_index = self._find_step_by_keyword(keyword)
        if current_step_index is not None:
            return min(current_step_index + 1, len(self.analysis_steps) - 1)
        return None

    def _calculate_weighted_progress(self) -> float:
        """Calculate progress based on step weights"""
        if self.current_step >= len(self.analysis_steps):
            return 1.0

        # If it's the last step, return 100%
        if self.current_step == len(self.analysis_steps) - 1:
            return 1.0

        completed_weight = sum(step["weight"] for step in self.analysis_steps[:self.current_step])
        total_weight = sum(step["weight"] for step in self.analysis_steps)

        return min(completed_weight / total_weight, 1.0)
    
    def _estimate_remaining_time(self, progress: float, elapsed_time: float) -> float:
        """Estimate remaining time based on total estimated time"""
        # If progress is completed, remaining time is 0
        if progress >= 1.0:
            return 0.0

        # Use a simple and accurate method: total estimated time - elapsed time
        remaining = max(self.estimated_duration - elapsed_time, 0)

        # If already exceeded estimated time, dynamically adjust based on current progress
        if remaining <= 0 and progress > 0:
            # Re-estimate total time based on current progress, then calculate remaining
            estimated_total = elapsed_time / progress
            remaining = max(estimated_total - elapsed_time, 0)

        return remaining
    
    def _save_progress(self):
        """Save progress to storage"""
        try:
            current_step_name = self.progress_data.get('current_step_name', 'Unknown')
            progress_pct = self.progress_data.get('progress_percentage', 0)
            status = self.progress_data.get('status', 'running')

            if self.use_redis:
                # Save to Redis (safely serialize)
                key = f"progress:{self.analysis_id}"
                safe_data = safe_serialize(self.progress_data)
                data_json = json.dumps(safe_data, ensure_ascii=False)
                self.redis_client.setex(key, 3600, data_json)  # 1 hour expiration

                logger.info(f"📊 [Redis写入] {self.analysis_id} -> {status} | {current_step_name} | {progress_pct:.1f}%")
                logger.debug(f"📊 [Redis详情] 键: {key}, 数据大小: {len(data_json)} 字节")
            else:
                # Save to file (safely serialize)
                safe_data = safe_serialize(self.progress_data)
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(safe_data, f, ensure_ascii=False, indent=2)

                logger.info(f"📊 [文件写入] {self.analysis_id} -> {status} | {current_step_name} | {progress_pct:.1f}%")
                logger.debug(f"📊 [文件详情] 路径: {self.progress_file}")

        except Exception as e:
            logger.error(f"📊 [异步进度] 保存失败: {e}")
            # Try fallback storage method
            try:
                if self.use_redis:
                    # Redis failed, try file storage
                    logger.warning(f"📊 [异步进度] Redis保存失败，尝试文件存储")
                    backup_file = f"./data/progress_{self.analysis_id}.json"
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    safe_data = safe_serialize(self.progress_data)
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        json.dump(safe_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"📊 [备用存储] 文件保存成功: {backup_file}")
                else:
                    # File storage failed, try simplified data
                    logger.warning(f"�� [异步进度] 文件保存失败，尝试简化数据")
                    simplified_data = {
                        'analysis_id': self.analysis_id,
                        'status': self.progress_data.get('status', 'unknown'),
                        'progress_percentage': self.progress_data.get('progress_percentage', 0),
                        'last_message': str(self.progress_data.get('last_message', '')),
                        'last_update': self.progress_data.get('last_update', time.time())
                    }
                    backup_file = f"./data/progress_{self.analysis_id}.json"
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        json.dump(simplified_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"📊 [备用存储] 简化数据保存成功: {backup_file}")
            except Exception as backup_e:
                logger.error(f"📊 [异步进度] 备用存储也失败: {backup_e}")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress"""
        return self.progress_data.copy()
    
    def mark_completed(self, message: str = "分析完成", results: Any = None):
        """Mark analysis as completed"""
        self.update_progress(message)
        self.progress_data['status'] = 'completed'
        self.progress_data['progress_percentage'] = 100.0
        self.progress_data['remaining_time'] = 0.0

        # Save analysis results (safely serialize)
        if results is not None:
            try:
                self.progress_data['raw_results'] = safe_serialize(results)
                logger.info(f"📊 [异步进度] 保存分析结果: {self.analysis_id}")
            except Exception as e:
                logger.warning(f"📊 [异步进度] 结果序列化失败: {e}")
                self.progress_data['raw_results'] = str(results)  # Final fallback

        self._save_progress()
        logger.info(f"📊 [异步进度] 分析完成: {self.analysis_id}")

        # Unregister from logging system
        try:
            from .progress_log_handler import unregister_analysis_tracker
            unregister_analysis_tracker(self.analysis_id)
        except ImportError:
            pass
    
    def mark_failed(self, error_message: str):
        """Mark analysis as failed"""
        self.progress_data['status'] = 'failed'
        self.progress_data['last_message'] = f"分析失败: {error_message}"
        self.progress_data['last_update'] = time.time()
        self._save_progress()
        logger.error(f"📊 [异步进度] 分析失败: {self.analysis_id}, 错误: {error_message}")

        # Unregister from logging system
        try:
            from .progress_log_handler import unregister_analysis_tracker
            unregister_analysis_tracker(self.analysis_id)
        except ImportError:
            pass

def get_progress_by_id(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Get progress by analysis ID"""
    try:
        # Check REDIS_ENABLED environment variable
        redis_enabled = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'

        # If Redis is enabled, try Redis first
        if redis_enabled:
            try:
                import redis

                # Get Redis configuration from environment variables
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', 6379))
                redis_password = os.getenv('REDIS_PASSWORD', None)
                redis_db = int(os.getenv('REDIS_DB', 0))

                # Create Redis connection
                if redis_password:
                    redis_client = redis.Redis(
                        host=redis_host,
                        port=redis_port,
                        password=redis_password,
                        db=redis_db,
                        decode_responses=True
                    )
                else:
                    redis_client = redis.Redis(
                        host=redis_host,
                        port=redis_port,
                        db=redis_db,
                        decode_responses=True
                    )

                key = f"progress:{analysis_id}"
                data = redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug(f"📊 [异步进度] Redis读取失败: {e}")

        # Try file
        progress_file = f"./data/progress_{analysis_id}.json"
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        return None
    except Exception as e:
        logger.error(f"📊 [异步进度] 获取进度失败: {analysis_id}, 错误: {e}")
        return None

def format_time(seconds: float) -> str:
    """Format time for display"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def get_latest_analysis_id() -> Optional[str]:
    """Get the latest analysis ID"""
    try:
        # Check REDIS_ENABLED environment variable
        redis_enabled = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'

        # If Redis is enabled, try to get from Redis first
        if redis_enabled:
            try:
                import redis

                # Get Redis configuration from environment variables
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', 6379))
                redis_password = os.getenv('REDIS_PASSWORD', None)
                redis_db = int(os.getenv('REDIS_DB', 0))

                # Create Redis connection
                if redis_password:
                    redis_client = redis.Redis(
                        host=redis_host,
                        port=redis_port,
                        password=redis_password,
                        db=redis_db,
                        decode_responses=True
                    )
                else:
                    redis_client = redis.Redis(
                        host=redis_host,
                        port=redis_port,
                        db=redis_db,
                        decode_responses=True
                    )

                # Get all progress keys
                keys = redis_client.keys("progress:*")
                if not keys:
                    return None

                # Get data for each key, find the latest
                latest_time = 0
                latest_id = None

                for key in keys:
                    try:
                        data = redis_client.get(key)
                        if data:
                            progress_data = json.loads(data)
                            last_update = progress_data.get('last_update', 0)
                            if last_update > latest_time:
                                latest_time = last_update
                                # Extract analysis_id from key (remove "progress:" prefix)
                                latest_id = key.replace('progress:', '')
                    except Exception:
                        continue

                if latest_id:
                    logger.info(f"📊 [恢复分析] 找到最新分析ID: {latest_id}")
                    return latest_id

            except Exception as e:
                logger.debug(f"📊 [恢复分析] Redis查找失败: {e}")

        # If Redis fails or is not enabled, try to find from file
        data_dir = Path("data")
        if data_dir.exists():
            progress_files = list(data_dir.glob("progress_*.json"))
            if progress_files:
                # Sort by modification time, get the latest
                latest_file = max(progress_files, key=lambda f: f.stat().st_mtime)
                # Extract analysis_id from filename
                filename = latest_file.name
                if filename.startswith("progress_") and filename.endswith(".json"):
                    analysis_id = filename[9:-5]  # Remove prefix and suffix
                    logger.debug(f"📊 [恢复分析] 从文件找到最新分析ID: {analysis_id}")
                    return analysis_id

        return None
    except Exception as e:
        logger.error(f"�� [恢复分析] 获取最新分析ID失败: {e}")
        return None
