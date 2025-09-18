#!/usr/bin/env python3
"""
DeepSeek直接适配器，不依赖langchain_openai，避免DefaultHttpxClient兼容性问题
"""

import os
import json
from typing import Any, Dict, List, Optional, Union
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

import logging
logger = logging.getLogger(__name__)

class DeepSeekDirectAdapter:
    """DeepSeek直接适配器，使用OpenAI库直接调用DeepSeek API"""
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 1000,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com"
    ):
        """
        初始化DeepSeek直接适配器
        
        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            api_key: API密钥，如果不提供则从环境变量获取
            base_url: API基础URL
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 获取API密钥
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("未找到DEEPSEEK_API_KEY，请在.env文件中配置或通过参数传入")
        
        # 创建OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )
        
        logger.info(f"✅ DeepSeek直接适配器初始化成功，模型: {model}")
    
    def invoke(self, messages: Union[str, List[Dict[str, str]]]) -> str:
        """
        调用DeepSeek API
        
        Args:
            messages: 消息内容，可以是字符串或消息列表
            
        Returns:
            str: 模型响应
        """
        try:
            # 处理输入消息格式
            if isinstance(messages, str):
                formatted_messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, list):
                formatted_messages = messages
            else:
                raise ValueError(f"不支持的消息格式: {type(messages)}")
            
            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = response.choices[0].message.content
            logger.debug(f"DeepSeek API调用成功，响应长度: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            raise
    
    def chat(self, message: str) -> str:
        """
        简单聊天接口
        
        Args:
            message: 用户消息
            
        Returns:
            str: 模型响应
        """
        return self.invoke(message)
    
    def analyze_with_tools(self, query: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        使用工具进行分析
        
        Args:
            query: 查询内容
            tools: 可用工具列表
            
        Returns:
            Dict: 分析结果
        """
        try:
            # 构建包含工具信息的提示
            tools_description = "\n".join([
                f"- {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}"
                for tool in tools
            ])
            
            prompt = f"""
你是一个专业的股票分析师。请根据以下查询进行分析：

查询：{query}

可用工具：
{tools_description}

请提供详细的分析结果，包括：
1. 分析思路
2. 关键发现
3. 投资建议
4. 风险提示

请用中文回答。
"""
            
            response = self.invoke(prompt)
            
            return {
                "query": query,
                "analysis": response,
                "tools_used": [tool.get('name') for tool in tools],
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"工具分析失败: {e}")
            return {
                "query": query,
                "analysis": f"分析失败: {str(e)}",
                "tools_used": [],
                "status": "error"
            }

def create_deepseek_direct_adapter(
    model: str = "deepseek-chat",
    temperature: float = 0.1,
    max_tokens: int = 1000,
    **kwargs
) -> DeepSeekDirectAdapter:
    """
    创建DeepSeek直接适配器的便捷函数
    
    Args:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        **kwargs: 其他参数
        
    Returns:
        DeepSeekDirectAdapter: 适配器实例
    """
    return DeepSeekDirectAdapter(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )