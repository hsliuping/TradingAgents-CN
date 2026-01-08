# 📈 升级指南: v0.1.12 → v0.1.13

## 🎯 升级概述

本指南将帮助您从 TradingAgents-CN v0.1.12 升级到 v0.1.13，享受原生OpenAI支持和Google AI全面集成的新功能。

## ⏰ 预计升级时间

- **简单升级**: 5-10分钟 (仅更新代码和依赖)
- **完整配置**: 15-20分钟 (包含Google AI配置和测试)
- **深度定制**: 30-45分钟 (包含自定义端点配置)

## 📋 升级前检查

### 1. 环境要求
```bash
# 检查Python版本 (需要 >= 3.10)
python --version

# 检查当前版本
cat VERSION
# 应该显示: cn-0.1.12
```

### 2. 备份重要数据
```bash
# 备份配置文件
cp .env .env.backup
cp -r reports reports_backup

# 备份自定义配置 (如果有)
cp -r config config_backup
```

### 3. 检查当前分支
```bash
git branch
# 确认当前在合适的分支
```

## 🚀 升级步骤

### 步骤 1: 切换到预览版分支
```bash
# 切换到预览版分支
git checkout feature/native-openai-support

# 拉取最新代码
git pull origin feature/native-openai-support

# 确认版本
cat VERSION
# 应该显示: cn-0.1.13-preview
```

### 步骤 2: 更新依赖包
```bash
# 方法1: 使用requirements.txt
pip install -r requirements.txt

# 方法2: 使用pyproject.toml (推荐)
pip install -e .

# 验证Google AI相关包（统一 LangChain）
pip list | grep -E "(google-genai|langchain-google-genai)"
```

### 步骤 3: 配置Google AI (可选但推荐)
```bash
# 在 .env 文件中添加Google API密钥
echo "GOOGLE_API_KEY=your_google_api_key_here" >> .env

# 如果没有Google API密钥，可以从以下地址获取:
# https://makersuite.google.com/app/apikey
```

### 步骤 4: 验证安装
```bash
# 测试Google AI包导入
python -c "
import langchain_google_genai
import google.genai
print('✅ Google AI packages imported successfully (LangChain unified)')
"

# 运行简单测试
python tests/test_gemini_simple.py
```

### 步骤 5: 启动和测试
```bash
# 启动Web界面
streamlit run web/app.py

# 在浏览器中访问 http://localhost:8501
# 测试新的模型选择功能
```

## 🔧 配置新功能

### 1. Google AI 配置

#### 获取API密钥
1. 访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 创建新的API密钥
3. 复制密钥到 `.env` 文件

#### 配置示例
```bash
# .env 文件
GOOGLE_API_KEY=AIzaSyC...your_key_here
```

#### 测试配置
```python
# 测试脚本
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# 检查API密钥
api_key = os.getenv('GOOGLE_API_KEY')
if api_key:
    print("✅ Google API密钥已配置")
    
    # 测试模型
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key
    )
    print("✅ Google AI模型创建成功")
else:
    print("⚠️ 请配置GOOGLE_API_KEY环境变量")
```

### 2. 原生OpenAI端点配置

#### 配置自定义端点
```bash
# .env 文件中添加
OPENAI_API_BASE=https://your-custom-endpoint.com/v1
OPENAI_API_KEY=your_custom_api_key
```

#### 支持的端点格式
- OpenAI官方: `https://api.openai.com/v1`
- 自建服务: `https://your-domain.com/v1`
- 代理服务: `https://proxy.example.com/v1`

### 3. Web界面新功能

#### 智能模型选择
- 🎯 自动检测可用模型
- 🔄 智能降级机制
- ⚡ 快速模型切换
- 🛡️ 错误恢复

#### 使用方法
1. 打开Web界面
2. 在侧边栏选择"Google AI"提供商
3. 选择具体的Google AI模型
4. 开始分析任务

## 🧪 功能测试

### 1. 基础功能测试
```bash
# 测试CLI功能
python cli/main.py --help

# 测试Web界面
streamlit run web/app.py
```

### 2. Google AI功能测试
```bash
# 运行Google AI测试套件
python tests/test_gemini_simple.py
python tests/test_gemini_final.py
python tests/test_google_memory_fix.py
```

### 3. 集成测试
```bash
# 运行完整的股票分析测试
python tests/test_analysis.py

# 测试新闻分析功能
python tests/test_web_fix.py
```

## ⚠️ 常见问题和解决方案

### 问题 1: 依赖冲突
```bash
# 症状: pip安装时出现依赖冲突
# 解决方案:
pip install --upgrade pip
pip install --force-reinstall -r requirements.txt
```

### 问题 2: Google AI包导入失败
```bash
# 症状: 依赖冲突或旧SDK导入失败
# 解决方案（统一为LangChain，移除旧SDK）:
# 1) 移除 google-generativeai 依赖
# 2) 保留/安装 langchain-google-genai 与 google-genai
pip install langchain-google-genai>=2.1.5 google-genai>=0.1.0
```

### 问题 3: API密钥配置问题
```bash
# 症状: Google API密钥无效
# 解决方案:
# 1. 检查密钥格式 (应以AIzaSy开头)
# 2. 确认密钥权限
# 3. 检查API配额
```

### 问题 4: Web界面模型选择错误
```bash
# 症状: KeyError in model selection
# 解决方案:
# 1. 清除浏览器缓存
# 2. 重启Streamlit应用
# 3. 检查模型配置文件
```

## 📊 升级验证清单

### ✅ 基础验证
- [ ] 版本号显示为 `cn-0.1.13-preview`
- [ ] 所有依赖包安装成功
- [ ] Web界面正常启动
- [ ] CLI功能正常工作

### ✅ Google AI验证
- [ ] Google AI包导入成功
- [ ] API密钥配置正确
- [ ] 模型创建和调用成功
- [ ] Web界面显示Google AI选项

### ✅ 功能验证
- [ ] 股票分析功能正常
- [ ] 新闻分析功能正常
- [ ] 模型切换功能正常
- [ ] 错误处理机制正常

### ✅ 性能验证
- [ ] 响应速度正常或更快
- [ ] 内存使用稳定
- [ ] 错误恢复正常
- [ ] 日志记录清晰

## 🔄 回滚方案

如果升级过程中遇到问题，可以回滚到v0.1.12：

```bash
# 回滚到v0.1.12
git checkout main  # 或之前的稳定分支
git pull origin main

# 恢复依赖
pip install -r requirements.txt

# 恢复配置文件
cp .env.backup .env
cp -r reports_backup reports
```

## 📞 获取帮助

### 🐛 问题报告
- **GitHub Issues**: 创建详细的问题报告
- **错误日志**: 提供完整的错误信息和日志
- **环境信息**: 包含Python版本、操作系统等信息

### 💡 功能建议
- **功能描述**: 详细描述期望的功能
- **使用场景**: 说明具体的使用需求
- **优先级**: 标明功能的重要性

### 📚 文档资源
- **配置指南**: `docs/configuration/google-ai-setup.md`
- **模型指南**: `docs/google_models_guide.md`
- **故障排除**: `docs/troubleshooting/`

## 🎉 升级完成

恭喜！您已成功升级到 TradingAgents-CN v0.1.13。

现在您可以：
- 🤖 使用原生OpenAI端点支持
- 🧠 体验Google AI模型的强大功能
- 🔧 享受优化的LLM适配器架构
- 🎨 使用改进的Web界面

感谢您选择 TradingAgents-CN，祝您使用愉快！