# 🧠 DeepSeek V3 使用指南

## 📋 概述

DeepSeek V3 是TradingAgents-CN v0.1.7新集成的成本优化AI模型，专为中文金融场景设计。相比GPT-4，DeepSeek V3在保持优秀分析质量的同时，成本降低90%以上，是进行股票分析的理想选择。

## 🎯 DeepSeek V3 特色

### 核心优势

| 特性 | DeepSeek V3 | GPT-4 | 优势说明 |
|------|-------------|-------|----------|
| **💰 成本** | $0.14/1M tokens | $15/1M tokens | 便宜90%+ |
| **🇨🇳 中文理解** | 优秀 | 良好 | 专门优化 |
| **🔧 工具调用** | 强大 | 强大 | 数学计算优势 |
| **⚡ 响应速度** | 快速 | 中等 | 更快响应 |
| **📊 金融分析** | 专业 | 通用 | 领域优化 |

### 技术特性

- ✅ **64K上下文长度**: 支持长文档分析
- ✅ **Function Calling**: 强大的工具调用能力
- ✅ **数学推理**: 优秀的数值计算和逻辑推理
- ✅ **中文优化**: 专为中文场景训练
- ✅ **实时响应**: 平均响应时间<3秒

## 🚀 快速开始

### 获取API密钥

#### 1. 注册DeepSeek账号
```bash
# 访问DeepSeek平台
https://platform.deepseek.com/

# 注册流程:
1. 点击"注册"按钮
2. 填写邮箱和密码
3. 验证邮箱
4. 完成实名认证 (可选)
```

#### 2. 创建API密钥
```bash
# 登录后操作:
1. 进入控制台
2. 点击"API Keys"
3. 点击"创建新密钥"
4. 设置密钥名称
5. 复制API密钥 (sk-开头)
```

#### 3. 充值账户
```bash
# 充值建议:
- 新用户: ¥50-100 (可用很久)
- 重度用户: ¥200-500
- 企业用户: ¥1000+

# 成本参考:
- 单次分析: ¥0.01-0.05
- 日常使用: ¥5-20/月
- 重度使用: ¥50-100/月
```

### 配置DeepSeek

#### 环境变量配置
```bash
# 编辑.env文件
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_ENABLED=true
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

#### Docker环境配置
```bash
# docker-compose.yml 已自动配置
# 只需在.env文件中设置API密钥即可

# 重启服务应用配置
docker-compose restart web
```

#### 本地环境配置
```bash
# 确保已安装最新依赖
pip install -r requirements.txt

# 重启应用
streamlit run web/app.py
```

## 📊 使用指南

### 基础使用

#### 1. 选择DeepSeek模型
```bash
# 在Web界面中:
1. 访问 http://localhost:8501
2. 在左侧边栏选择"LLM模型"
3. 选择"DeepSeek V3"
4. 确认模型状态为"可用"
```

#### 2. 进行股票分析
```bash
# 分析流程:
1. 输入股票代码 (如: 000001, AAPL)
2. 选择分析深度:
   - 快速分析 (2-3分钟)
   - 标准分析 (5-8分钟)  
   - 深度分析 (10-15分钟)
3. 选择分析师类型:
   - 技术分析师
   - 基本面分析师
   - 新闻分析师
   - 综合分析
4. 点击"开始分析"
```

#### 3. 查看分析结果
```bash
# 分析结果包含:
📈 技术指标分析
💰 基本面评估
📰 新闻情绪分析
🎯 投资建议
⚠️ 风险提示
📊 价格预测
```

### 高级功能

#### 智能模型路由
```bash
# 配置智能路由
LLM_SMART_ROUTING=true
LLM_PRIORITY_ORDER=deepseek,qwen,gemini,openai

# 路由策略:
- 常规分析 → DeepSeek V3 (成本优化)
- 复杂推理 → Gemini (推理能力)
- 中文内容 → 通义千问 (中文理解)
- 通用任务 → GPT-4 (综合能力)
```

#### 成本控制
```bash
# 成本监控配置
LLM_DAILY_COST_LIMIT=10.0          # 日成本限制 (美元)
LLM_COST_ALERT_THRESHOLD=8.0       # 告警阈值
LLM_AUTO_SWITCH_ON_LIMIT=true      # 超限自动切换

# 成本优化策略:
✅ 优先使用DeepSeek V3
✅ 启用智能缓存
✅ 避免重复分析
✅ 合理选择分析深度
```

## 💰 成本分析

### 成本对比

#### 单次分析成本
| 分析类型 | DeepSeek V3 | GPT-4 | 节省 |
|---------|-------------|-------|------|
| **快速分析** | ¥0.01-0.02 | ¥0.15-0.30 | 90%+ |
| **标准分析** | ¥0.02-0.05 | ¥0.30-0.60 | 90%+ |
| **深度分析** | ¥0.05-0.10 | ¥0.60-1.20 | 90%+ |

#### 月度使用成本
| 使用频率 | DeepSeek V3 | GPT-4 | 节省 |
|---------|-------------|-------|------|
| **轻度使用** (10次/天) | ¥5-10 | ¥50-100 | 90%+ |
| **中度使用** (50次/天) | ¥20-40 | ¥200-400 | 90%+ |
| **重度使用** (100次/天) | ¥40-80 | ¥400-800 | 90%+ |

### 成本优化建议

#### 1. 合理选择分析深度
```bash
# 建议策略:
✅ 日常监控 → 快速分析
✅ 投资决策 → 标准分析
✅ 重要决策 → 深度分析
✅ 学习研究 → 深度分析
```

#### 2. 启用缓存机制
```bash
# 缓存配置
LLM_ENABLE_CACHE=true
LLM_CACHE_TTL=3600  # 1小时缓存

# 缓存效果:
- 重复查询成本为0
- 相似股票分析成本降低50%
- 历史数据查询免费
```

#### 3. 批量分析优化
```bash
# 批量分析策略:
✅ 同时分析多只相关股票
✅ 使用行业对比分析
✅ 利用历史分析结果
✅ 合并相似查询
```

## 🔧 最佳实践

### 1. 提示词优化

#### 针对中文股票
```bash
# 优化的提示词示例:
"请分析A股股票{股票代码}的投资价值，重点关注：
1. 技术指标趋势
2. 基本面财务状况  
3. 行业地位和竞争优势
4. 近期新闻和政策影响
5. 风险因素和投资建议

请用专业的中文金融术语，提供具体的数据支撑。"
```

#### 针对美股
```bash
# 美股分析提示词:
"Please analyze the US stock {symbol} focusing on:
1. Technical indicators and trends
2. Fundamental analysis and financials
3. Market position and competitive advantages  
4. Recent news and market sentiment
5. Risk assessment and investment recommendations

Please provide data-driven insights with specific metrics."
```

### 2. 参数调优

#### 模型参数配置
```bash
# 推荐参数设置
DEEPSEEK_TEMPERATURE=0.3        # 降低随机性，提高一致性
DEEPSEEK_MAX_TOKENS=4000        # 适中的输出长度
DEEPSEEK_TOP_P=0.8             # 平衡创造性和准确性
DEEPSEEK_FREQUENCY_PENALTY=0.1  # 减少重复内容
```

#### 请求优化
```bash
# 性能优化配置
DEEPSEEK_REQUEST_TIMEOUT=30     # 请求超时时间
DEEPSEEK_MAX_RETRIES=3         # 最大重试次数
DEEPSEEK_RETRY_DELAY=1         # 重试延迟
DEEPSEEK_CONCURRENT_REQUESTS=3  # 并发请求数
```

### 3. 质量控制

#### 结果验证
```bash
# 分析质量检查:
✅ 数据准确性验证
✅ 逻辑一致性检查
✅ 中文表达质量
✅ 专业术语使用
✅ 投资建议合理性
```

#### 错误处理
```bash
# 常见问题处理:
- API限流 → 自动重试
- 网络超时 → 降级处理
- 余额不足 → 切换模型
- 内容过滤 → 调整提示词
```

## 🚨 故障排除

### 常见问题

#### 1. API密钥无效
```bash
# 检查步骤:
1. 确认API密钥格式 (sk-开头)
2. 检查密钥是否过期
3. 验证账户余额
4. 确认API权限

# 解决方案:
- 重新生成API密钥
- 充值账户余额
- 联系DeepSeek客服
```

#### 2. 请求失败
```bash
# 常见错误:
- 429: 请求频率过高 → 降低并发数
- 401: 认证失败 → 检查API密钥
- 500: 服务器错误 → 稍后重试
- 超时: 网络问题 → 检查网络连接

# 调试方法:
docker logs TradingAgents-web | grep deepseek
```

#### 3. 分析质量问题
```bash
# 质量优化:
- 调整temperature参数
- 优化提示词内容
- 增加上下文信息
- 使用更具体的指令
```

### 性能监控

```bash
# 监控指标:
📊 API调用成功率
⏱️ 平均响应时间
💰 成本使用情况
🔄 缓存命中率
⚠️ 错误率统计

# 监控命令:
# 查看使用统计
curl http://localhost:8501/api/stats

# 查看成本统计
curl http://localhost:8501/api/costs
```

## 📈 进阶技巧

### 1. 自定义分析模板
```python
# 创建专门的DeepSeek分析模板
deepseek_template = """
作为专业的中国股市分析师，请对{symbol}进行全面分析：

## 技术分析
- K线形态和趋势
- 主要技术指标 (MA, RSI, MACD)
- 支撑位和阻力位
- 成交量分析

## 基本面分析  
- 财务指标评估
- 行业地位分析
- 竞争优势评估
- 成长性分析

## 风险评估
- 市场风险
- 行业风险  
- 公司特定风险
- 政策风险

请提供具体的投资建议和目标价位。
"""
```

### 2. 批量分析脚本
```python
# 批量分析多只股票
import asyncio
from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek

async def batch_analysis(symbols):
    llm = ChatDeepSeek()
    results = {}
    
    for symbol in symbols:
        try:
            result = await llm.analyze_stock(symbol)
            results[symbol] = result
            print(f"✅ {symbol} 分析完成")
        except Exception as e:
            print(f"❌ {symbol} 分析失败: {e}")
    
    return results

# 使用示例
symbols = ['000001', '600519', '000858', '002415']
results = asyncio.run(batch_analysis(symbols))
```

---

## 📞 获取帮助

### DeepSeek支持
- 🌐 [DeepSeek官网](https://platform.deepseek.com/)
- 📚 [DeepSeek文档](https://platform.deepseek.com/docs)
- 💬 [DeepSeek社区](https://github.com/deepseek-ai)

### TradingAgents-CN支持
- 🐛 [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)
- 💬 [GitHub Discussions](https://github.com/hsliuping/TradingAgents-CN/discussions)
- 📚 [完整文档](https://github.com/hsliuping/TradingAgents-CN/tree/main/docs)

---

*最后更新: 2025-07-13*  
*版本: cn-0.1.7*  
*模型版本: DeepSeek V3*
