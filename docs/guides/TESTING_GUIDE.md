# 🧪 DeepSeek V3 预览版测试指南

## 📋 测试目标

帮助用户系统性地测试DeepSeek V3集成功能，发现问题并提供反馈，共同完善这个高性价比的AI金融分析工具。

## 🚀 快速测试流程

### 第一步：环境准备

```bash
# 1. 克隆预览分支
git clone -b feature/deepseek-v3-integration https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env
env\Scripts\activate  # Windows
# source env/bin/activate  # Linux/macOS

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
```

### 第二步：获取DeepSeek API密钥

1. 访问 [DeepSeek平台](https://platform.deepseek.com/)
2. 注册账号（支持手机号注册）
3. 进入控制台 → API Keys
4. 创建新的API Key
5. 复制API Key到.env文件：
   ```bash
   DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   DEEPSEEK_ENABLED=true
   ```

### 第三步：基础功能测试

```bash
# 测试DeepSeek连接
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DeepSeek API Key:', '✅ 已配置' if os.getenv('DEEPSEEK_API_KEY') else '❌ 未配置')
"

# 测试基本面分析
python tests/test_fundamentals_analysis.py

# 测试DeepSeek Token统计
python tests/test_deepseek_token_tracking.py
```

## 📊 详细测试项目

### 1. DeepSeek模型集成测试

#### 1.1 API连接测试
```bash
# 测试基本连接
python -c "
from tradingagents.llm_adapters.deepseek_adapter import ChatDeepSeek
llm = ChatDeepSeek(model='deepseek-chat', temperature=0.1)
response = llm.invoke('你好，请简单介绍一下股票投资')
print('响应:', response.content[:100] + '...')
"
```

**测试要点**：
- [ ] API密钥是否正确配置
- [ ] 网络连接是否正常
- [ ] 响应时间是否合理（通常5-15秒）
- [ ] 返回内容是否为中文

#### 1.2 Token统计测试
```bash
# 测试Token使用统计
python examples/demo_deepseek_analysis.py
```

**测试要点**：
- [ ] Token使用量是否正确统计
- [ ] 成本计算是否准确（输入¥0.001/1K，输出¥0.002/1K）
- [ ] 统计信息是否实时更新
- [ ] 会话级别的成本跟踪是否正常

### 2. 基本面分析功能测试

#### 2.1 A股分析测试
```bash
# 测试A股基本面分析
python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config.update({
    'llm_provider': 'deepseek',
    'llm_model': 'deepseek-chat',
    'quick_think_llm': 'deepseek-chat',
    'deep_think_llm': 'deepseek-chat',
})

ta = TradingAgentsGraph(
    selected_analysts=['fundamentals'],
    config=config
)

# 测试招商银行
result = ta.run_analysis('000001', '2025-01-08')
print('分析结果:', result)
"
```

**测试股票建议**：
- `000001` - 平安银行
- `600519` - 贵州茅台  
- `000858` - 五粮液
- `002594` - 比亚迪
- `300750` - 宁德时代

**测试要点**：
- [ ] 是否包含真实财务指标（PE、PB、ROE等）
- [ ] 投资建议是否使用中文（买入/持有/卖出）
- [ ] 行业识别是否准确
- [ ] 评分系统是否合理（0-10分）
- [ ] 风险评估是否完整

#### 2.2 美股分析测试
```bash
# 测试美股基本面分析
python -c "
# 同上配置，测试美股
result = ta.run_analysis('AAPL', '2025-01-08')
print('苹果公司分析:', result)
"
```

**测试股票建议**：
- `AAPL` - 苹果公司
- `MSFT` - 微软
- `GOOGL` - 谷歌
- `TSLA` - 特斯拉

### 3. Web界面测试

```bash
# 启动Web界面
streamlit run web/app.py
```

访问 http://localhost:8501 进行测试：

#### 3.1 配置页面测试
- [ ] DeepSeek模型是否出现在选择列表中
- [ ] API密钥状态显示是否正确
- [ ] 模型切换是否正常工作

#### 3.2 分析页面测试
- [ ] 股票代码输入是否正常
- [ ] 分析师选择是否包含基本面分析师
- [ ] 分析过程是否显示进度
- [ ] 结果展示是否完整清晰

#### 3.3 Token统计页面测试
- [ ] DeepSeek使用统计是否显示
- [ ] 成本计算是否准确
- [ ] 历史记录是否正确保存

### 4. CLI界面测试

```bash
# 启动CLI界面
python -m cli.main
```

**测试流程**：
1. 选择"DeepSeek V3"作为LLM提供商
2. 选择"deepseek-chat"模型
3. 输入股票代码进行分析
4. 检查分析结果质量

**测试要点**：
- [ ] DeepSeek选项是否可用
- [ ] 模型选择是否正常
- [ ] 分析流程是否顺畅
- [ ] 结果输出是否完整

## 🐛 常见问题排查

### 问题1：API密钥错误
```
错误：Authentication failed
```
**解决方案**：
1. 检查API密钥格式（应以sk-开头）
2. 确认API密钥有效且有余额
3. 检查网络连接

### 问题2：Token统计显示¥0.0000
**可能原因**：
1. API响应中缺少usage信息
2. Token提取逻辑问题

**排查方法**：
```bash
# 启用调试模式
export TRADINGAGENTS_LOG_LEVEL=DEBUG
python tests/test_deepseek_token_tracking.py
```

### 问题3：基本面分析显示模板内容
**可能原因**：
1. 数据获取失败
2. 分析逻辑问题

**排查方法**：
```bash
# 测试数据获取
python -c "
from tradingagents.dataflows.tdx_utils import get_china_stock_data
data = get_china_stock_data('000001', '2025-01-01', '2025-01-08')
print('数据获取结果:', data[:200] if data else '获取失败')
"
```

## 📝 反馈模板

### 成功测试反馈
```markdown
## ✅ 测试成功

**测试环境**：
- 操作系统：Windows 11 / macOS / Ubuntu
- Python版本：3.10.x
- 测试时间：2025-01-08

**测试项目**：
- [x] DeepSeek API连接
- [x] Token统计功能
- [x] 基本面分析
- [x] Web界面
- [x] CLI界面

**测试体验**：
- 响应速度：快/中等/慢
- 分析质量：优秀/良好/一般
- 成本控制：满意/一般/不满意
- 整体评价：推荐/可用/需改进

**建议改进**：
（可选）提出改进建议
```

### 问题反馈
```markdown
## 🐛 问题反馈

**问题描述**：
简要描述遇到的问题

**复现步骤**：
1. 执行的命令或操作
2. 预期结果
3. 实际结果

**环境信息**：
- 操作系统：
- Python版本：
- DeepSeek API密钥状态：
- 错误日志：

**截图**：
（如果有界面问题，请提供截图）
```

## 🎯 测试重点关注

### 高优先级测试
1. **DeepSeek API集成稳定性**
2. **Token统计准确性**
3. **基本面分析质量**
4. **中文输出正确性**

### 中优先级测试
1. **Web界面用户体验**
2. **CLI界面流畅性**
3. **错误处理机制**
4. **性能表现**

### 低优先级测试
1. **边界情况处理**
2. **并发使用测试**
3. **长时间运行稳定性**

## 📞 获取帮助

- **GitHub Issues**：https://github.com/hsliuping/TradingAgents-CN/issues
- **测试讨论**：GitHub Discussions
- **实时反馈**：在Issue中@hsliuping

---

**感谢您参与测试！您的反馈将帮助我们打造更好的AI金融分析工具。** 🙏
