# TradingAgents/graph/signal_processing.py

from langchain_openai import ChatOpenAI

# 导入统一日志系统和图处理模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_graph_module
logger = get_logger("graph.signal_processing")


class SignalProcessor:
    """Processes trading signals to extract actionable decisions."""

    def __init__(self, quick_thinking_llm: ChatOpenAI):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    @log_graph_module("signal_processing")
    def process_signal(self, full_signal: str, stock_symbol: str = None) -> dict:
        """
        Process a full trading signal to extract structured decision information.

        Args:
            full_signal: Complete trading signal text
            stock_symbol: Stock symbol to determine currency type

        Returns:
            Dictionary containing extracted decision information
        """

        # 检测股票类型和货币
        from tradingagents.utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(stock_symbol)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

        logger.info(f"🔍 [SignalProcessor] 处理信号: 股票={stock_symbol}, 市场={market_info['market_name']}, 货币={currency}",
                   extra={'stock_symbol': stock_symbol, 'market': market_info['market_name'], 'currency': currency})

        messages = [
            (
                "system",
                f"""You are a professional financial analysis assistant responsible for extracting structured investment decision information from a trader's analysis report.

Please extract the following information from the provided analysis report and return it in JSON format:

{{
    "action": "Buy/Hold/Sell",
    "target_price": Number({currency} price, **must provide a specific value, cannot be null**),
    "confidence": Number(0-1, if not explicitly mentioned then 0.7),
    "risk_score": Number(0-1, if not explicitly mentioned then 0.5),
    "reasoning": "Summary of the main reasoning for the decision"
}}

Please ensure:
1. The action field must be one of "Buy", "Hold", or "Sell" (absolutely not allowed to use English buy/hold/sell)
2. target_price must be a specific number, target_price should be a reasonable {currency} price number (using {currency_symbol} symbol)
3. confidence and risk_score should be between 0-1
4. reasoning should be a concise English summary
5. All content must be in English, no English investment advice is allowed

Special note:
- The stock code {stock_symbol or 'Unknown'} is {market_info['market_name']}, priced in {currency}
- The target price must be consistent with the stock's trading currency ({currency_symbol})

If some information is not explicitly mentioned in the report, please use reasonable default values. Please write all analysis in English.""",
            ),
            ("human", full_signal),
        ]

        try:
            response = self.quick_thinking_llm.invoke(messages).content
            logger.debug(f"🔍 [SignalProcessor] LLM响应: {response[:200]}...")

            # 尝试解析JSON响应
            import json
            import re

            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                logger.debug(f"🔍 [SignalProcessor] 提取的JSON: {json_text}")
                decision_data = json.loads(json_text)

                # 验证和标准化数据
                action = decision_data.get('action', 'Hold')
                if action not in ['Buy', 'Hold', 'Sell']:
                    # 尝试映射英文和其他变体
                    action_map = {
                        'buy': 'Buy', 'hold': 'Hold', 'sell': 'Sell',
                        'BUY': 'Buy', 'HOLD': 'Hold', 'SELL': 'Sell',
                        'Purchase': 'Buy', 'Keep': 'Hold', 'Dispose': 'Sell',
                        'purchase': 'Buy', 'keep': 'Hold', 'dispose': 'Sell'
                    }
                    action = action_map.get(action, 'Hold')
                    if action != decision_data.get('action', 'Hold'):
                        logger.debug(f"🔍 [SignalProcessor] 投资建议映射: {decision_data.get('action')} -> {action}")

                # 处理目标价格，确保正确提取
                target_price = decision_data.get('target_price')
                if target_price is None or target_price == "null" or target_price == "":
                    # 如果JSON中没有目标价格，尝试从reasoning和完整文本中提取
                    reasoning = decision_data.get('reasoning', '')
                    full_text = f"{reasoning} {full_signal}"  # 扩大搜索范围
                    
                    # 增强的价格匹配模式
                    price_patterns = [
                        r'Target Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',  # Target Price: 45.50
                        r'Target[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Target: 45.50
                        r'Price[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Price: 45.50
                        r'Price[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Price: 45.50
                        r'Reasonable Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)', # Reasonable Price: 45.50
                        r'Valuation[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Valuation: 45.50
                        r'[¥\$](\d+(?:\.\d+)?)',                      # ¥45.50 或 $190
                        r'(\d+(?:\.\d+)?) Yuan',                         # 45.50 Yuan
                        r'(\d+(?:\.\d+)?) Dollar',                       # 190 Dollar
                        r'Suggestion[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',        # Suggestion: 45.50
                        r'Expectation[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',        # Expectation: 45.50
                        r'See[s]?\s*[¥\$]?(\d+(?:\.\d+)?)',          # See 45.50
                        r'Rise[s]?\s*[¥\$]?(\d+(?:\.\d+)?)',        # Rise to 45.50
                        r'(\d+(?:\.\d+)?)\s*[¥\$]',                  # 45.50¥
                    ]
                    
                    for pattern in price_patterns:
                        price_match = re.search(pattern, full_text, re.IGNORECASE)
                        if price_match:
                            try:
                                target_price = float(price_match.group(1))
                                logger.debug(f"🔍 [SignalProcessor] 从文本中提取到目标价格: {target_price} (模式: {pattern})")
                                break
                            except (ValueError, IndexError):
                                continue

                    # 如果仍然没有找到价格，尝试智能推算
                    if target_price is None or target_price == "null" or target_price == "":
                        target_price = self._smart_price_estimation(full_text, action, is_china)
                        if target_price:
                            logger.debug(f"🔍 [SignalProcessor] 智能推算目标价格: {target_price}")
                        else:
                            target_price = None
                            logger.warning(f"🔍 [SignalProcessor] 未能提取到目标价格，设置为None")
                else:
                    # 确保价格是数值类型
                    try:
                        if isinstance(target_price, str):
                            # 清理字符串格式的价格
                            clean_price = target_price.replace('$', '').replace('¥', '').replace('￥', '').replace('元', '').replace('美元', '').strip()
                            target_price = float(clean_price) if clean_price and clean_price.lower() not in ['none', 'null', ''] else None
                        elif isinstance(target_price, (int, float)):
                            target_price = float(target_price)
                        logger.debug(f"🔍 [SignalProcessor] 处理后的目标价格: {target_price}")
                    except (ValueError, TypeError):
                        target_price = None
                        logger.warning(f"🔍 [SignalProcessor] 价格转换失败，设置为None")

                result = {
                    'action': action,
                    'target_price': target_price,
                    'confidence': float(decision_data.get('confidence', 0.7)),
                    'risk_score': float(decision_data.get('risk_score', 0.5)),
                    'reasoning': decision_data.get('reasoning', '基于综合分析的投资建议')
                }
                logger.info(f"🔍 [SignalProcessor] 处理结果: {result}",
                           extra={'action': result['action'], 'target_price': result['target_price'],
                                 'confidence': result['confidence'], 'stock_symbol': stock_symbol})
                return result
            else:
                # 如果无法解析JSON，使用简单的文本提取
                return self._extract_simple_decision(response)

        except Exception as e:
            logger.error(f"信号处理错误: {e}", exc_info=True, extra={'stock_symbol': stock_symbol})
            # 回退到简单提取
            return self._extract_simple_decision(full_signal)

    def _smart_price_estimation(self, text: str, action: str, is_china: bool) -> float:
        """智能价格推算方法"""
        import re
        
        # 尝试从文本中提取当前价格和涨跌幅信息
        current_price = None
        percentage_change = None
        
        # 提取当前价格
        current_price_patterns = [
            r'Current Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',
            r'Current Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',
            r'Current Stock Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',
            r'Price[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',
        ]
        
        for pattern in current_price_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    current_price = float(match.group(1))
                    break
                except ValueError:
                    continue
        
        # 提取涨跌幅信息
        percentage_patterns = [
            r'Rise\s*(\d+(?:\.\d+)?)%',
            r'Increase\s*(\d+(?:\.\d+)?)%',
            r'Growth\s*(\d+(?:\.\d+)?)%',
            r'(\d+(?:\.\d+)?)%\s*of? Rise',
        ]
        
        for pattern in percentage_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    percentage_change = float(match.group(1)) / 100
                    break
                except ValueError:
                    continue
        
        # 基于动作和信息推算目标价
        if current_price and percentage_change:
            if action == 'Buy':
                return round(current_price * (1 + percentage_change), 2)
            elif action == 'Sell':
                return round(current_price * (1 - percentage_change), 2)
        
        # 如果有当前价格但没有涨跌幅，使用默认估算
        if current_price:
            if action == 'Buy':
                # 买入建议默认10-20%涨幅
                multiplier = 1.15 if is_china else 1.12
                return round(current_price * multiplier, 2)
            elif action == 'Sell':
                # 卖出建议默认5-10%跌幅
                multiplier = 0.95 if is_china else 0.92
                return round(current_price * multiplier, 2)
            else:  # 持有
                # 持有建议使用当前价格
                return current_price
        
        return None

    def _extract_simple_decision(self, text: str) -> dict:
        """简单的决策提取方法作为备用"""
        import re

        # 提取动作
        action = 'Hold'  # 默认
        if re.search(r'Buy|BUY', text, re.IGNORECASE):
            action = 'Buy'
        elif re.search(r'Sell|SELL', text, re.IGNORECASE):
            action = 'Sell'
        elif re.search(r'Hold|HOLD', text, re.IGNORECASE):
            action = 'Hold'

        # 尝试提取目标价格（使用增强的模式）
        target_price = None
        price_patterns = [
            r'Target Price[s]?[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',  # Target Price: 45.50
            r'\*\*Target Price[s]?\*\*[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',  # **Target Price**: 45.50
            r'Target[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Target: 45.50
            r'Price[：:]?\s*[¥\$]?(\d+(?:\.\d+)?)',         # Price: 45.50
            r'[¥\$](\d+(?:\.\d+)?)',                      # ¥45.50 或 $190
            r'(\d+(?:\.\d+)?) Yuan',                         # 45.50 Yuan
        ]

        for pattern in price_patterns:
            price_match = re.search(pattern, text)
            if price_match:
                try:
                    target_price = float(price_match.group(1))
                    break
                except ValueError:
                    continue

        # 如果没有找到价格，尝试智能推算
        if target_price is None:
            # 检测股票类型
            is_china = True  # 默认假设是A股，实际应该从上下文获取
            target_price = self._smart_price_estimation(text, action, is_china)

        return {
            'action': action,
            'target_price': target_price,
            'confidence': 0.7,
            'risk_score': 0.5,
            'reasoning': '基于综合分析的投资建议'
        }
