# 大语言模型配置 (v0.1.7)

## 概述

TradingAgents-CN 框架支持多种大语言模型提供商，包括 DeepSeek、阿里百炼、Google AI、OpenAI 和 Anthropic。本文档详细介绍了如何配置和优化不同的 LLM 以获得最佳性能和成本效益。

## 🎯 v0.1.7 LLM支持更新

- ✅ **DeepSeek V3**: 新增成本优化的中文模型
- ✅ **智能路由**: 根据任务自动选择最优模型
- ✅ **成本控制**: 详细的成本监控和限制
- ✅ **工具调用**: 完整的Function Calling支持

## 支持的 LLM 提供商

### 1. 🇨🇳 DeepSeek (v0.1.7新增，推荐)

#### 支持的模型
```python
deepseek_models = {
    "deepseek-chat": {
        "description": "DeepSeek V3 对话模型",
        "context_length": 64000,
        "cost_per_1k_tokens": {"input": 0.0014, "output": 0.0028},
        "recommended_for": ["中文分析", "工具调用", "成本敏感场景"],
        "features": ["工具调用", "中文优化", "数学计算"]
    },
    "deepseek-coder": {
        "description": "DeepSeek 代码生成模型",
        "context_length": 64000,
        "cost_per_1k_tokens": {"input": 0.0014, "output": 0.0028},
        "recommended_for": ["代码分析", "技术指标计算", "数据处理"],
        "features": ["代码生成", "逻辑推理", "数据分析"]
    }
}
```

#### 配置示例
```bash
# .env 配置
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_ENABLED=true
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

#### 特色功能
- **🔧 工具调用**: 强大的Function Calling能力
- **💰 成本优化**: 比GPT-4便宜90%以上
- **🇨🇳 中文优化**: 专为中文场景设计
- **📊 数据分析**: 优秀的数学和逻辑推理能力

### 2. 🇨🇳 阿里百炼 (推荐)

#### 支持的模型
```python
qwen_models = {
    "qwen-plus": {
        "description": "通义千问Plus模型",
        "context_length": 32000,
        "cost_per_1k_tokens": {"input": 0.004, "output": 0.012},
        "recommended_for": ["中文理解", "快速响应", "日常分析"],
        "features": ["中文优化", "响应快速", "理解准确"]
    },
    "qwen-max": {
        "description": "通义千问Max模型",
        "context_length": 8000,
        "cost_per_1k_tokens": {"input": 0.02, "output": 0.06},
        "recommended_for": ["复杂推理", "深度分析", "高质量输出"],
        "features": ["推理能力强", "输出质量高", "逻辑清晰"]
    }
}
```

### 3. 🌍 Google AI (推荐)

#### 支持的模型
```python
gemini_models = {
    "gemini-1.5-pro": {
        "description": "Gemini 1.5 Pro模型",
        "context_length": 1000000,
        "cost_per_1k_tokens": {"input": 0.0035, "output": 0.0105},
        "recommended_for": ["复杂推理", "长文本处理", "多模态分析"],
        "features": ["超长上下文", "推理能力强", "多模态支持"]
    },
    "gemini-1.5-flash": {
        "description": "Gemini 1.5 Flash模型",
        "context_length": 1000000,
        "cost_per_1k_tokens": {"input": 0.00035, "output": 0.00105},
        "recommended_for": ["快速任务", "批量处理", "成本敏感"],
        "features": ["响应快速", "成本低", "性能均衡"]
    }
}
```

### 4. OpenAI

#### 支持的模型
```python
openai_models = {
    "gpt-4o": {
        "description": "最新的 GPT-4 优化版本",
        "context_length": 128000,
        "cost_per_1k_tokens": {"input": 0.005, "output": 0.015},
        "recommended_for": ["深度分析", "复杂推理", "高质量输出"]
    },
    "gpt-4o-mini": {
        "description": "轻量级 GPT-4 版本",
        "context_length": 128000,
        "cost_per_1k_tokens": {"input": 0.00015, "output": 0.0006},
        "recommended_for": ["快速任务", "成本敏感场景", "大量API调用"]
    },
    "gpt-4-turbo": {
        "description": "GPT-4 Turbo 版本",
        "context_length": 128000,
        "cost_per_1k_tokens": {"input": 0.01, "output": 0.03},
        "recommended_for": ["平衡性能和成本", "标准分析任务"]
    },
    "gpt-3.5-turbo": {
        "description": "经济实用的选择",
        "context_length": 16385,
        "cost_per_1k_tokens": {"input": 0.0005, "output": 0.0015},
        "recommended_for": ["简单任务", "预算有限", "快速响应"]
    }
}
```

#### 配置示例
```python
# OpenAI 配置
openai_config = {
    "llm_provider": "openai",
    "backend_url": "https://api.openai.com/v1",
    "deep_think_llm": "gpt-4o",           # 用于复杂分析
    "quick_think_llm": "gpt-4o-mini",     # 用于简单任务
    "api_key": os.getenv("OPENAI_API_KEY"),
    
    # 模型参数
    "model_params": {
        "temperature": 0.1,               # 低温度保证一致性
        "max_tokens": 2000,               # 最大输出长度
        "top_p": 0.9,                     # 核采样参数
        "frequency_penalty": 0.0,         # 频率惩罚
        "presence_penalty": 0.0,          # 存在惩罚
    },
    
    # 速率限制
    "rate_limits": {
        "requests_per_minute": 3500,      # 每分钟请求数
        "tokens_per_minute": 90000,       # 每分钟token数
    },
    
    # 重试配置
    "retry_config": {
        "max_retries": 3,
        "backoff_factor": 2,
        "timeout": 60
    }
}
```

### 2. Anthropic Claude

#### 支持的模型
```python
anthropic_models = {
    "claude-3-opus-20240229": {
        "description": "最强大的 Claude 模型",
        "context_length": 200000,
        "cost_per_1k_tokens": {"input": 0.015, "output": 0.075},
        "recommended_for": ["最复杂的分析", "高质量推理", "创意任务"]
    },
    "claude-3-sonnet-20240229": {
        "description": "平衡性能和成本",
        "context_length": 200000,
        "cost_per_1k_tokens": {"input": 0.003, "output": 0.015},
        "recommended_for": ["标准分析任务", "平衡使用场景"]
    },
    "claude-3-haiku-20240307": {
        "description": "快速且经济的选择",
        "context_length": 200000,
        "cost_per_1k_tokens": {"input": 0.00025, "output": 0.00125},
        "recommended_for": ["快速任务", "大量调用", "成本优化"]
    }
}
```

#### 配置示例
```python
# Anthropic 配置
anthropic_config = {
    "llm_provider": "anthropic",
    "backend_url": "https://api.anthropic.com",
    "deep_think_llm": "claude-3-opus-20240229",
    "quick_think_llm": "claude-3-haiku-20240307",
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    
    # 模型参数
    "model_params": {
        "temperature": 0.1,
        "max_tokens": 2000,
        "top_p": 0.9,
        "top_k": 40,
    },
    
    # 速率限制
    "rate_limits": {
        "requests_per_minute": 1000,
        "tokens_per_minute": 40000,
    }
}
```

### 3. Google AI (Gemini)

#### 支持的模型
```python
google_models = {
    "gemini-pro": {
        "description": "Google 的主力模型",
        "context_length": 32768,
        "cost_per_1k_tokens": {"input": 0.0005, "output": 0.0015},
        "recommended_for": ["多模态任务", "代码分析", "推理任务"]
    },
    "gemini-pro-vision": {
        "description": "支持图像的 Gemini 版本",
        "context_length": 16384,
        "cost_per_1k_tokens": {"input": 0.0005, "output": 0.0015},
        "recommended_for": ["图表分析", "多模态输入"]
    },
    "gemini-2.0-flash": {
        "description": "最新的快速版本",
        "context_length": 32768,
        "cost_per_1k_tokens": {"input": 0.0002, "output": 0.0008},
        "recommended_for": ["快速响应", "实时分析"]
    }
}
```

#### 配置示例
```python
# Google AI 配置
google_config = {
    "llm_provider": "google",
    "backend_url": "https://generativelanguage.googleapis.com/v1",
    "deep_think_llm": "gemini-pro",
    "quick_think_llm": "gemini-2.0-flash",
    "api_key": os.getenv("GOOGLE_API_KEY"),
    
    # 模型参数
    "model_params": {
        "temperature": 0.1,
        "max_output_tokens": 2000,
        "top_p": 0.9,
        "top_k": 40,
    }
}
```

## LLM 选择策略

### 基于任务类型的选择
```python
class LLMSelector:
    """LLM 选择器 - 根据任务选择最适合的模型"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.task_model_mapping = self._initialize_task_mapping()
        
    def select_model(self, task_type: str, complexity: str = "medium") -> str:
        """根据任务类型和复杂度选择模型"""
        
        task_config = self.task_model_mapping.get(task_type, {})
        
        if complexity == "high":
            return task_config.get("high_complexity", self.config["deep_think_llm"])
        elif complexity == "low":
            return task_config.get("low_complexity", self.config["quick_think_llm"])
        else:
            return task_config.get("medium_complexity", self.config["deep_think_llm"])
    
    def _initialize_task_mapping(self) -> Dict:
        """初始化任务-模型映射"""
        return {
            "fundamental_analysis": {
                "high_complexity": "gpt-4o",
                "medium_complexity": "gpt-4o-mini",
                "low_complexity": "gpt-3.5-turbo"
            },
            "technical_analysis": {
                "high_complexity": "claude-3-opus-20240229",
                "medium_complexity": "claude-3-sonnet-20240229",
                "low_complexity": "claude-3-haiku-20240307"
            },
            "news_analysis": {
                "high_complexity": "gpt-4o",
                "medium_complexity": "gpt-4o-mini",
                "low_complexity": "gemini-pro"
            },
            "social_sentiment": {
                "high_complexity": "claude-3-sonnet-20240229",
                "medium_complexity": "gpt-4o-mini",
                "low_complexity": "gemini-2.0-flash"
            },
            "risk_assessment": {
                "high_complexity": "gpt-4o",
                "medium_complexity": "claude-3-sonnet-20240229",
                "low_complexity": "gpt-4o-mini"
            },
            "trading_decision": {
                "high_complexity": "gpt-4o",
                "medium_complexity": "gpt-4o",
                "low_complexity": "claude-3-sonnet-20240229"
            }
        }
```

### 成本优化策略
```python
class CostOptimizer:
    """成本优化器 - 在性能和成本间找到平衡"""
    
    def __init__(self, budget_config: Dict):
        self.daily_budget = budget_config.get("daily_budget", 100)  # 美元
        self.cost_tracking = {}
        self.model_costs = self._load_model_costs()
        
    def get_cost_optimized_config(self, current_usage: Dict) -> Dict:
        """获取成本优化的配置"""
        
        remaining_budget = self._calculate_remaining_budget(current_usage)
        
        if remaining_budget > 50:  # 预算充足
            return {
                "deep_think_llm": "gpt-4o",
                "quick_think_llm": "gpt-4o-mini",
                "max_debate_rounds": 3
            }
        elif remaining_budget > 20:  # 预算中等
            return {
                "deep_think_llm": "gpt-4o-mini",
                "quick_think_llm": "gpt-4o-mini",
                "max_debate_rounds": 2
            }
        else:  # 预算紧张
            return {
                "deep_think_llm": "gpt-3.5-turbo",
                "quick_think_llm": "gpt-3.5-turbo",
                "max_debate_rounds": 1
            }
    
    def estimate_request_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """估算请求成本"""
        
        model_cost = self.model_costs.get(model, {"input": 0.001, "output": 0.002})
        
        input_cost = (input_tokens / 1000) * model_cost["input"]
        output_cost = (output_tokens / 1000) * model_cost["output"]
        
        return input_cost + output_cost
```

## 性能优化

### 提示词优化
```python
class PromptOptimizer:
    """提示词优化器"""
    
    def __init__(self):
        self.prompt_templates = self._load_prompt_templates()
        
    def optimize_prompt(self, task_type: str, model: str, context: Dict) -> str:
        """优化提示词"""
        
        base_prompt = self.prompt_templates[task_type]["base"]
        
        # 根据模型特点调整提示词
        if "gpt" in model.lower():
            optimized_prompt = self._optimize_for_gpt(base_prompt, context)
        elif "claude" in model.lower():
            optimized_prompt = self._optimize_for_claude(base_prompt, context)
        elif "gemini" in model.lower():
            optimized_prompt = self._optimize_for_gemini(base_prompt, context)
        else:
            optimized_prompt = base_prompt
        
        return optimized_prompt
    
    def _optimize_for_gpt(self, prompt: str, context: Dict) -> str:
        """为 GPT 模型优化提示词"""
        
        # GPT 喜欢结构化的指令
        structured_prompt = f"""
任务: {context.get('task_description', '')}

指令:
1. 仔细分析提供的数据
2. 应用相关的金融分析方法
3. 提供清晰的结论和建议
4. 包含置信度评估

数据:
{context.get('data', '')}

请按照以下格式回答:
- 分析结果: [你的分析]
- 结论: [主要结论]
- 建议: [具体建议]
- 置信度: [0-1之间的数值]
"""
        return structured_prompt
    
    def _optimize_for_claude(self, prompt: str, context: Dict) -> str:
        """为 Claude 模型优化提示词"""
        
        # Claude 喜欢对话式的提示
        conversational_prompt = f"""
我需要你作为一个专业的金融分析师来帮助我分析以下数据。

{context.get('data', '')}

请你:
1. 深入分析这些数据的含义
2. 识别关键的趋势和模式
3. 评估潜在的风险和机会
4. 给出你的专业建议

请用专业但易懂的语言回答，并解释你的推理过程。
"""
        return conversational_prompt
```

### 并发控制
```python
class LLMConcurrencyManager:
    """LLM 并发管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.semaphores = self._initialize_semaphores()
        self.rate_limiters = self._initialize_rate_limiters()
        
    def _initialize_semaphores(self) -> Dict:
        """初始化信号量控制并发"""
        return {
            "openai": asyncio.Semaphore(10),      # OpenAI 最多10个并发
            "anthropic": asyncio.Semaphore(5),    # Anthropic 最多5个并发
            "google": asyncio.Semaphore(8)        # Google 最多8个并发
        }
    
    async def execute_with_concurrency_control(self, provider: str, llm_call: callable) -> Any:
        """在并发控制下执行LLM调用"""
        
        semaphore = self.semaphores.get(provider)
        rate_limiter = self.rate_limiters.get(provider)
        
        async with semaphore:
            await rate_limiter.acquire()
            try:
                result = await llm_call()
                return result
            except Exception as e:
                # 处理速率限制错误
                if "rate_limit" in str(e).lower():
                    await asyncio.sleep(60)  # 等待1分钟
                    return await llm_call()
                else:
                    raise e
```

## 监控和调试

### LLM 性能监控
```python
class LLMMonitor:
    """LLM 性能监控"""
    
    def __init__(self):
        self.metrics = {
            "request_count": defaultdict(int),
            "response_times": defaultdict(list),
            "token_usage": defaultdict(dict),
            "error_rates": defaultdict(float),
            "costs": defaultdict(float)
        }
    
    def record_request(self, model: str, response_time: float, 
                      input_tokens: int, output_tokens: int, cost: float):
        """记录请求指标"""
        
        self.metrics["request_count"][model] += 1
        self.metrics["response_times"][model].append(response_time)
        
        if model not in self.metrics["token_usage"]:
            self.metrics["token_usage"][model] = {"input": 0, "output": 0}
        
        self.metrics["token_usage"][model]["input"] += input_tokens
        self.metrics["token_usage"][model]["output"] += output_tokens
        self.metrics["costs"][model] += cost
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        
        report = {}
        
        for model in self.metrics["request_count"]:
            response_times = self.metrics["response_times"][model]
            
            report[model] = {
                "total_requests": self.metrics["request_count"][model],
                "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
                "total_input_tokens": self.metrics["token_usage"][model].get("input", 0),
                "total_output_tokens": self.metrics["token_usage"][model].get("output", 0),
                "total_cost": self.metrics["costs"][model],
                "avg_cost_per_request": self.metrics["costs"][model] / self.metrics["request_count"][model] if self.metrics["request_count"][model] > 0 else 0
            }
        
        return report
```

## 最佳实践

### 1. 模型选择建议
- **高精度任务**: 使用 GPT-4o 或 Claude-3-Opus
- **平衡场景**: 使用 GPT-4o-mini 或 Claude-3-Sonnet  
- **成本敏感**: 使用 GPT-3.5-turbo 或 Claude-3-Haiku
- **快速响应**: 使用 Gemini-2.0-flash

### 2. 成本控制策略
- 设置每日预算限制
- 使用较小模型处理简单任务
- 实施智能缓存减少重复调用
- 监控token使用量

### 3. 性能优化技巧
- 优化提示词长度和结构
- 使用适当的温度参数
- 实施并发控制避免速率限制
- 定期监控和调整配置

通过合理的LLM配置和优化，可以在保证分析质量的同时控制成本并提高系统性能。
