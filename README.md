# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-cn--0.1.15-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

> 🚀 **最新版本 cn-0.1.15**: 开发者体验与LLM生态系统大升级！新增千帆大模型支持、完整开发工具链、学术研究资料、企业级工作流规范！
>
> 🎯 **核心功能**: 原生OpenAI支持 | Google AI全面集成 | 自定义端点配置 | 智能模型选择 | 多LLM提供商支持 | 模型选择持久化 | Docker容器化部署 | 专业报告导出 | 完整A股支持 | 中文本地化

基于多智能体大语言模型的**中文金融交易决策框架**。专为中文用户优化，提供完整的A股/港股/美股分析能力。

## 🙏 致敬源项目

感谢 [Tauric Research](https://github.com/TauricResearch) 团队创造的革命性多智能体交易框架 [TradingAgents](https://github.com/TauricResearch/TradingAgents)！

**🎯 我们的使命**: 为中国用户提供完整的中文化体验，支持A股/港股市场，集成国产大模型，推动AI金融技术在中文社区的普及应用。

## 🆕 v0.1.15 重大更新

### 🤖 LLM生态系统大升级

- **千帆大模型支持**: 新增百度千帆(ERNIE)大模型完整集成
- **LLM适配器重构**: 统一的OpenAI兼容适配器架构
- **多厂商支持**: 支持更多国产大模型提供商
- **集成指南**: 完整的LLM集成开发文档和测试工具

### 📚 学术研究支持

- **TradingAgents论文**: 完整的中文翻译版本和深度解读
- **技术博客**: 详细的技术分析和实现原理解读
- **学术资料**: PDF论文和相关研究资料
- **引用支持**: 标准的学术引用格式和参考文献

### 🛠️ 开发者体验升级

- **开发工作流**: 标准化的开发流程和分支管理规范
- **安装验证**: 完整的安装测试和验证脚本
- **文档重构**: 结构化的文档系统和快速开始指南
- **PR模板**: 标准化的Pull Request模板和代码审查流程

### 🔧 企业级工具链

- **分支保护**: GitHub分支保护策略和安全规则
- **紧急程序**: 完整的紧急处理和故障恢复程序
- **测试框架**: 增强的测试覆盖和验证工具
- **部署指南**: 企业级部署和配置管理

## 📋 v0.1.14 功能回顾

### 👥 用户权限管理系统

- **完整用户管理**: 新增用户注册、登录、权限控制功能
- **角色权限**: 支持多级用户角色和权限管理
- **会话管理**: 安全的用户会话和状态管理
- **用户活动日志**: 完整的用户操作记录和审计功能

### 🔐 Web用户认证系统

- **登录组件**: 现代化的用户登录界面
- **认证管理器**: 统一的用户认证和授权管理
- **安全增强**: 密码加密、会话安全等安全机制
- **用户仪表板**: 个性化的用户活动仪表板

### 🗄️ 数据管理优化

- **MongoDB集成增强**: 改进的MongoDB连接和数据管理
- **数据目录重组**: 优化的数据存储结构和管理
- **数据迁移脚本**: 完整的数据迁移和备份工具
- **缓存优化**: 提升数据加载和分析结果缓存性能

### 🧪 测试覆盖增强

- **功能测试脚本**: 新增6个专项功能测试脚本
- **工具处理器测试**: Google工具处理器修复验证
- **引导自动隐藏测试**: UI交互功能测试
- **在线工具配置测试**: 工具配置和选择逻辑测试
- **真实场景测试**: 实际使用场景的端到端测试
- **美股独立性测试**: 美股分析功能独立性验证

---

## 🆕 v0.1.13 重大更新

### 🤖 原生OpenAI端点支持

- **自定义OpenAI端点**: 支持配置任意OpenAI兼容的API端点
- **灵活模型选择**: 可以使用任何OpenAI格式的模型，不限于官方模型
- **智能适配器**: 新增原生OpenAI适配器，提供更好的兼容性和性能
- **配置管理**: 统一的端点和模型配置管理系统

### 🧠 Google AI生态系统全面集成

- **三大Google AI包支持**: langchain-google-genai、google-generativeai、google-genai
- **9个验证模型**: gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash等最新模型
- **Google工具处理器**: 专门的Google AI工具调用处理器
- **智能降级机制**: 高级功能失败时自动降级到基础功能

### 🔧 LLM适配器架构优化

- **GoogleOpenAIAdapter**: 新增Google AI的OpenAI兼容适配器
- **统一接口**: 所有LLM提供商使用统一的调用接口
- **错误处理增强**: 改进的异常处理和自动重试机制
- **性能监控**: 添加LLM调用性能监控和统计

### 🎨 Web界面智能优化

- **智能模型选择**: 根据可用性自动选择最佳模型
- **KeyError修复**: 彻底解决模型选择中的KeyError问题
- **UI响应优化**: 改进模型切换的响应速度和用户体验
- **错误提示**: 更友好的错误提示和解决建议

## 🆕 v0.1.12 重大更新

### 🧠 智能新闻分析模块

- **智能新闻过滤器**: 基于AI的新闻相关性评分和质量评估
- **多层次过滤机制**: 基础过滤、增强过滤、集成过滤三级处理
- **新闻质量评估**: 自动识别和过滤低质量、重复、无关新闻
- **统一新闻工具**: 整合多个新闻源，提供统一的新闻获取接口

### 🔧 技术修复和优化

- **DashScope适配器修复**: 解决工具调用兼容性问题
- **DeepSeek死循环修复**: 修复新闻分析师的无限循环问题
- **LLM工具调用增强**: 提升工具调用的可靠性和稳定性
- **新闻检索器优化**: 增强新闻数据获取和处理能力

### 📚 完善测试和文档

- **全面测试覆盖**: 新增15+个测试文件，覆盖所有新功能
- **详细技术文档**: 新增8个技术分析报告和修复文档
- **用户指南完善**: 新增新闻过滤使用指南和最佳实践
- **演示脚本**: 提供完整的新闻过滤功能演示

### 🗂️ 项目结构优化

- **文档分类整理**: 按功能将文档分类到docs子目录
- **示例代码归位**: 演示脚本统一到examples目录
- **根目录整洁**: 保持根目录简洁，提升项目专业度

## 🎯 核心特性

### 🤖 多智能体协作架构

- **专业分工**: 基本面、技术面、新闻面、社交媒体四大分析师
- **结构化辩论**: 看涨/看跌研究员进行深度分析
- **智能决策**: 交易员基于所有输入做出最终投资建议
- **风险管理**: 多层次风险评估和管理机制

## 🖥️ Web界面展示

### 📸 界面截图

> 🎨 **现代化Web界面**: 基于Streamlit构建的响应式Web应用，提供直观的股票分析体验

#### 🏠 主界面 - 分析配置

![1755003162925](images/README/1755003162925.png)

![1755002619976](images/README/1755002619976.png)

*智能配置面板，支持多市场股票分析，5级研究深度选择*

#### 📊 实时分析进度

![1755002731483](images/README/1755002731483.png)

*实时进度跟踪，可视化分析过程，智能时间预估*

#### 📈 分析结果展示

![1755002901204](images/README/1755002901204.png)

![1755002924844](images/README/1755002924844.png)

![1755002939905](images/README/1755002939905.png)

![1755002968608](images/README/1755002968608.png)

![1755002985903](images/README/1755002985903.png)

![1755003004403](images/README/1755003004403.png)

![1755003019759](images/README/1755003019759.png)

![1755003033939](images/README/1755003033939.png)

![1755003048242](images/README/1755003048242.png)

![1755003064598](images/README/1755003064598.png)

![1755003090603](images/README/1755003090603.png)

*专业投资报告，多维度分析结果，一键导出功能*

### 🎯 核心功能特色

#### 📋 **智能分析配置**

- **🌍 多市场支持**: 美股、A股、港股一站式分析
- **🎯 5级研究深度**: 从2分钟快速分析到25分钟全面研究
- **🤖 智能体选择**: 市场技术、基本面、新闻、社交媒体分析师
- **📅 灵活时间设置**: 支持历史任意时间点分析

#### 🚀 **实时进度跟踪**

- **📊 可视化进度**: 实时显示分析进展和剩余时间
- **🔄 智能步骤识别**: 自动识别当前分析阶段
- **⏱️ 准确时间预估**: 基于历史数据的智能时间计算
- **💾 状态持久化**: 页面刷新不丢失分析进度

#### 📈 **专业结果展示**

- **🎯 投资决策**: 明确的买入/持有/卖出建议
- **📊 多维分析**: 技术面、基本面、新闻面综合评估
- **🔢 量化指标**: 置信度、风险评分、目标价位
- **📄 专业报告**: 支持Markdown/Word/PDF格式导出

#### 🤖 **多LLM模型管理**

- **🌐 4大提供商**: DashScope、DeepSeek、Google AI、OpenRouter
- **🎯 60+模型选择**: 从经济型到旗舰级模型全覆盖
- **💾 配置持久化**: URL参数存储，刷新保持设置
- **⚡ 快速切换**: 5个热门模型一键选择按钮

### 🎮 Web界面操作指南

#### 🚀 **快速开始流程**

1. **启动应用**: `python start_web.py` 或 `docker-compose up -d`
2. **访问界面**: 浏览器打开 `http://localhost:8501`
3. **配置模型**: 侧边栏选择LLM提供商和模型
4. **输入股票**: 输入股票代码（如 AAPL、000001、0700.HK）
5. **选择深度**: 根据需求选择1-5级研究深度
6. **开始分析**: 点击"🚀 开始分析"按钮
7. **查看结果**: 实时跟踪进度，查看分析报告
8. **导出报告**: 一键导出专业格式报告

#### 📊 **支持的股票代码格式**

- **🇺🇸 美股**: `AAPL`, `TSLA`, `MSFT`, `NVDA`, `GOOGL`
- **🇨🇳 A股**: `000001`, `600519`, `300750`, `002415`
- **🇭🇰 港股**: `0700.HK`, `9988.HK`, `3690.HK`, `1810.HK`

#### 🎯 **研究深度说明**

- **1级 (2-4分钟)**: 快速概览，基础技术指标
- **2级 (4-6分钟)**: 标准分析，技术+基本面
- **3级 (6-10分钟)**: 深度分析，加入新闻情绪 ⭐ **推荐**
- **4级 (10-15分钟)**: 全面分析，多轮智能体辩论
- **5级 (15-25分钟)**: 最深度分析，完整研究报告

#### 💡 **使用技巧**

- **🔄 实时刷新**: 分析过程中可随时刷新页面，进度不丢失
- **📱 移动适配**: 支持手机和平板设备访问
- **🎨 深色模式**: 自动适配系统主题设置
- **⌨️ 快捷键**: 支持Enter键快速提交分析
- **📋 历史记录**: 自动保存最近的分析配置

> 📖 **详细指南**: 完整的Web界面使用说明请参考 [🖥️ Web界面详细使用指南](docs/usage/web-interface-detailed-guide.md)

## 🎯 功能特性

### 🚀  智能新闻分析✨ **v0.1.12重大升级**


| 功能特性               | 状态        | 详细说明                                 |
| ---------------------- | ----------- | ---------------------------------------- |
| **🧠 智能新闻分析**    | 🆕 v0.1.12  | AI新闻过滤，质量评估，相关性分析         |
| **🔧 新闻过滤器**      | 🆕 v0.1.12  | 多层次过滤，基础/增强/集成三级处理       |
| **📰 统一新闻工具**    | 🆕 v0.1.12  | 整合多源新闻，统一接口，智能检索         |
| **🤖 多LLM提供商**     | 🆕 v0.1.11  | 4大提供商，60+模型，智能分类管理         |
| **💾 模型选择持久化**  | 🆕 v0.1.11  | URL参数存储，刷新保持，配置分享          |
| **🎯 快速选择按钮**    | 🆕 v0.1.11  | 一键切换热门模型，提升操作效率           |
| **📊 实时进度显示**    | ✅ v0.1.10  | 异步进度跟踪，智能步骤识别，准确时间计算 |
| **💾 智能会话管理**    | ✅ v0.1.10  | 状态持久化，自动降级，跨页面恢复         |
| **🎯 一键查看报告**    | ✅ v0.1.10  | 分析完成后一键查看，智能结果恢复         |
| **🖥️ Streamlit界面** | ✅ 完整支持 | 现代化响应式界面，实时交互和数据可视化   |
| **⚙️ 配置管理**      | ✅ 完整支持 | Web端API密钥管理，模型选择，参数配置     |

### 🎨 CLI用户体验 ✨ **v0.1.9优化**


| 功能特性                | 状态        | 详细说明                             |
| ----------------------- | ----------- | ------------------------------------ |
| **🖥️ 界面与日志分离** | ✅ 完整支持 | 用户界面清爽美观，技术日志独立管理   |
| **🔄 智能进度显示**     | ✅ 完整支持 | 多阶段进度跟踪，防止重复提示         |
| **⏱️ 时间预估功能**   | ✅ 完整支持 | 智能分析阶段显示预计耗时             |
| **🌈 Rich彩色输出**     | ✅ 完整支持 | 彩色进度指示，状态图标，视觉效果提升 |

### 🧠 LLM模型支持 ✨ **v0.1.13全面升级**


| 模型提供商        | 支持模型                     | 特色功能                | 新增功能 |
| ----------------- | ---------------------------- | ----------------------- | -------- |
| **🇨🇳 阿里百炼** | qwen-turbo/plus/max          | 中文优化，成本效益高    | ✅ 集成  |
| **🇨🇳 DeepSeek** | deepseek-chat                | 工具调用，性价比极高    | ✅ 集成  |
| **🌍 Google AI**  | **9个验证模型**              | 最新Gemini 2.5系列      | 🆕 升级  |
| ├─**最新旗舰**  | gemini-2.5-pro/flash         | 最新旗舰，超快响应      | 🆕 新增  |
| ├─**稳定推荐**  | gemini-2.0-flash             | 推荐使用，平衡性能      | 🆕 新增  |
| ├─**经典强大**  | gemini-1.5-pro/flash         | 经典稳定，高质量分析    | ✅ 集成  |
| └─**轻量快速**  | gemini-2.5-flash-lite        | 轻量级任务，快速响应    | 🆕 新增  |
| **🌐 原生OpenAI** | **自定义端点支持**           | 任意OpenAI兼容端点      | 🆕 新增  |
| **🌐 OpenRouter** | **60+模型聚合平台**          | 一个API访问所有主流模型 | ✅ 集成  |
| ├─**OpenAI**    | o4-mini-high, o3-pro, GPT-4o | 最新o系列，推理专业版   | ✅ 集成  |
| ├─**Anthropic** | Claude 4 Opus/Sonnet/Haiku   | 顶级性能，平衡版本      | ✅ 集成  |
| ├─**Meta**      | Llama 4 Maverick/Scout       | 最新Llama 4系列         | ✅ 集成  |
| └─**自定义**    | 任意OpenRouter模型ID         | 无限扩展，个性化选择    | ✅ 集成  |

**🎯 快速选择**: 5个热门模型快速按钮 | **💾 持久化**: URL参数存储，刷新保持 | **🔄 智能切换**: 一键切换不同提供商

### 📊 数据源与市场


| 市场类型      | 数据源                   | 覆盖范围                     |
| ------------- | ------------------------ | ---------------------------- |
| **🇨🇳 A股**  | Tushare, AkShare, 通达信 | 沪深两市，实时行情，财报数据 |
| **🇭🇰 港股** | AkShare, Yahoo Finance   | 港交所，实时行情，基本面     |
| **🇺🇸 美股** | FinnHub, Yahoo Finance   | NYSE, NASDAQ，实时数据       |
| **📰 新闻**   | Google News              | 实时新闻，多语言支持         |

### 🤖 智能体团队

**分析师团队**: 📈市场分析 | 💰基本面分析 | 📰新闻分析 | 💬情绪分析
**研究团队**: 🐂看涨研究员 | 🐻看跌研究员 | 🎯交易决策员
**管理层**: 🛡️风险管理员 | 👔研究主管

## 🚀 快速开始

### 🐳 Docker部署 (推荐)

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入API密钥

# 3. 启动服务
# 首次启动或代码变更时（需要构建镜像）
docker-compose up -d --build

# 日常启动（镜像已存在，无代码变更）
docker-compose up -d

# 智能启动（自动判断是否需要构建）
# Windows环境
powershell -ExecutionPolicy Bypass -File scripts\smart_start.ps1

# Linux/Mac环境
chmod +x scripts/smart_start.sh && ./scripts/smart_start.sh

# 4. 访问应用
# Web界面: http://localhost:8501
```

### 💻 本地部署

```bash
# 1. 升级pip (重要！避免安装错误)
python -m pip install --upgrade pip

# 2. 安装依赖
pip install -e .

# 3. 启动应用
python start_web.py

# 4. 访问 http://localhost:8501
```

### 📊 开始分析

1. **选择模型**: DeepSeek V3 / 通义千问 / Gemini
2. **输入股票**: `000001` (A股) / `AAPL` (美股) / `0700.HK` (港股)
3. **开始分析**: 点击"🚀 开始分析"按钮
4. **实时跟踪**: 观察实时进度和分析步骤
5. **查看报告**: 点击"📊 查看分析报告"按钮
6. **导出报告**: 支持Word/PDF/Markdown格式

## 🔐 用户权限管理

### 🔑 默认账号信息

系统提供以下默认账号，首次启动时自动创建：

| 用户名 | 密码 | 角色 | 权限说明 |
|--------|------|------|----------|
| **admin** | **admin123** | 管理员 | 完整系统权限，用户管理，系统配置 |
| **user** | **user123** | 普通用户 | 股票分析，报告查看，基础功能 |

> ⚠️ **安全提醒**: 首次登录后请立即修改默认密码！

### 🛡️ 权限控制体系

- **🔐 登录认证**: 基于用户名密码的安全认证
- **👥 角色管理**: 管理员、普通用户等多级权限
- **⏰ 会话管理**: 自动超时保护，安全登出
- **📊 操作日志**: 完整的用户活动记录

### 🛠️ 用户管理工具

系统提供完整的命令行用户管理工具：

#### Windows 用户
```powershell
# 使用 PowerShell 脚本
.\scripts\user_manager.ps1 list                    # 列出所有用户
.\scripts\user_manager.ps1 change-password admin   # 修改密码
.\scripts\user_manager.ps1 create newuser trader  # 创建新用户
.\scripts\user_manager.ps1 delete olduser         # 删除用户

# 或使用批处理文件
.\scripts\user_manager.bat list
```

#### Python 脚本（跨平台）
```bash
# 直接使用 Python 脚本
python scripts/user_password_manager.py list
python scripts/user_password_manager.py change-password admin
python scripts/user_password_manager.py create newuser --role trader
python scripts/user_password_manager.py delete olduser
python scripts/user_password_manager.py reset  # 重置为默认配置
```

### 📋 支持的用户操作

- **📝 列出用户**: 查看所有用户及其角色权限
- **🔑 修改密码**: 安全的密码更新机制
- **👤 创建用户**: 支持自定义角色和权限
- **🗑️ 删除用户**: 安全的用户删除功能
- **🔄 重置配置**: 恢复默认用户设置

### 📁 配置文件位置

用户配置存储在：`web/config/users.json`

> 📚 **详细文档**: 完整的用户管理指南请参考 [scripts/USER_MANAGEMENT.md](scripts/USER_MANAGEMENT.md)

### 🚧 当前版本限制

- ❌ 暂不支持在线用户注册
- ❌ 暂不支持Web界面的角色管理
- ✅ 支持完整的命令行用户管理
- ✅ 支持完整的权限控制框架

---

## 🎯 核心优势

- **🧠 智能新闻分析**: v0.1.12新增AI驱动的新闻过滤和质量评估系统
- **🔧 多层次过滤**: 基础、增强、集成三级新闻过滤机制
- **📰 统一新闻工具**: 整合多源新闻，提供统一的智能检索接口
- **🆕 多LLM集成**: v0.1.11新增4大提供商，60+模型，一站式AI体验
- **💾 配置持久化**: 模型选择真正持久化，URL参数存储，刷新保持
- **🎯 快速切换**: 5个热门模型快速按钮，一键切换不同AI
- **🆕 实时进度**: v0.1.10异步进度跟踪，告别黑盒等待
- **💾 智能会话**: 状态持久化，页面刷新不丢失分析结果
- **🔐 用户权限**: v0.1.14新增完整的用户认证和权限管理体系
- **🇨🇳 中国优化**: A股/港股数据 + 国产LLM + 中文界面
- **🐳 容器化**: Docker一键部署，环境隔离，快速扩展
- **📄 专业报告**: 多格式导出，自动生成投资建议
- **🛡️ 稳定可靠**: 多层数据源，智能降级，错误恢复

## 🔧 技术架构

**核心技术**: Python 3.10+ | LangChain | Streamlit | MongoDB | Redis
**AI模型**: DeepSeek V3 | 阿里百炼 | Google AI | OpenRouter(60+模型) | OpenAI
**数据源**: Tushare | AkShare | FinnHub | Yahoo Finance
**部署**: Docker | Docker Compose | 本地部署

## 📚 文档和支持

- **📖 完整文档**: [docs/](./docs/) - 安装指南、使用教程、API文档
- **🚨 故障排除**: [troubleshooting/](./docs/troubleshooting/) - 常见问题解决方案
- **🔄 更新日志**: [CHANGELOG.md](./docs/releases/CHANGELOG.md) - 详细版本历史
- **🚀 快速开始**: [QUICKSTART.md](./QUICKSTART.md) - 5分钟快速部署指南

## 🆚 中文增强特色

**相比原版新增**: 智能新闻分析 | 多层次新闻过滤 | 新闻质量评估 | 统一新闻工具 | 多LLM提供商集成 | 模型选择持久化 | 快速切换按钮 | | 实时进度显示 | 智能会话管理 | 中文界面 | A股数据 | 国产LLM | Docker部署 | 专业报告导出 | 统一日志管理 | Web配置界面 | 成本优化

**Docker部署包含的服务**:

- 🌐 **Web应用**: TradingAgents-CN主程序
- 🗄️ **MongoDB**: 数据持久化存储
- ⚡ **Redis**: 高速缓存
- 📊 **MongoDB Express**: 数据库管理界面
- 🎛️ **Redis Commander**: 缓存管理界面

#### 💻 方式二：本地部署

**适用场景**: 开发环境、自定义配置、离线使用

### 环境要求

- Python 3.10+ (推荐 3.11)
- 4GB+ RAM (推荐 8GB+)
- 稳定的网络连接

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 3. 升级pip
python -m pip install --upgrade pip

# 4. 安装所有依赖
pip install -r requirements.txt
#或者使用pip install -e .
pip install -e .

# 注意：requirements.txt已包含所有必需依赖：
# - 数据库支持 (MongoDB + Redis)
# - 多市场数据源 (Tushare, AKShare, FinnHub等)
# - Web界面和报告导出功能
```

### 配置API密钥

#### 🇨🇳 推荐：使用阿里百炼（国产大模型）

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，配置以下必需的API密钥：
DASHSCOPE_API_KEY=your_dashscope_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here

# 推荐：Tushare API（专业A股数据）
TUSHARE_TOKEN=your_tushare_token_here
TUSHARE_ENABLED=true

# 可选：其他AI模型API
GOOGLE_API_KEY=your_google_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 数据库配置（可选，提升性能）
# 本地部署使用标准端口
MONGODB_ENABLED=false  # 设为true启用MongoDB
REDIS_ENABLED=false    # 设为true启用Redis
MONGODB_HOST=localhost
MONGODB_PORT=27017     # 标准MongoDB端口
REDIS_HOST=localhost
REDIS_PORT=6379        # 标准Redis端口

# Docker部署时需要修改主机名
# MONGODB_HOST=mongodb
# REDIS_HOST=redis
```

#### 📋 部署模式配置说明

**本地部署模式**：

```bash
# 数据库配置（本地部署）
MONGODB_ENABLED=true
REDIS_ENABLED=true
MONGODB_HOST=localhost      # 本地主机
MONGODB_PORT=27017         # 标准端口
REDIS_HOST=localhost       # 本地主机
REDIS_PORT=6379           # 标准端口
```

**Docker部署模式**：

```bash
# 数据库配置（Docker部署）
MONGODB_ENABLED=true
REDIS_ENABLED=true
MONGODB_HOST=mongodb       # Docker容器服务名
MONGODB_PORT=27017        # 标准端口
REDIS_HOST=redis          # Docker容器服务名
REDIS_PORT=6379          # 标准端口
```

> 💡 **配置提示**：
>
> - 本地部署：需要手动启动MongoDB和Redis服务
> - Docker部署：数据库服务通过docker-compose自动启动
> - 端口冲突：如果本地已有数据库服务，可修改docker-compose.yml中的端口映射

#### 🌍 可选：使用国外模型

```bash
# OpenAI (需要科学上网)
OPENAI_API_KEY=your_openai_api_key

# Anthropic (需要科学上网)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 🗄️ 数据库配置（MongoDB + Redis）

#### 高性能数据存储支持

本项目支持 **MongoDB** 和 **Redis** 数据库，提供：

- **📊 股票数据缓存**: 减少API调用，提升响应速度
- **🔄 智能降级机制**: MongoDB → API → 本地缓存的多层数据源
- **⚡ 高性能缓存**: Redis缓存热点数据，毫秒级响应
- **🛡️ 数据持久化**: MongoDB存储历史数据，支持离线分析

#### 数据库部署方式

**🐳 Docker部署（推荐）**

如果您使用Docker部署，数据库已自动包含在内：

```bash
# Docker部署会自动启动所有服务，包括：
docker-compose up -d --build
# - Web应用 (端口8501)
# - MongoDB (端口27017)
# - Redis (端口6379)
# - 数据库管理界面 (端口8081, 8082)
```

**💻 本地部署 - 数据库配置**

如果您使用本地部署，可以选择以下方式：

**方式一：仅启动数据库服务**

```bash
# 仅启动 MongoDB + Redis 服务（不启动Web应用）
docker-compose up -d mongodb redis mongo-express redis-commander

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

**方式二：完全本地安装**

```bash
# 数据库依赖已包含在requirements.txt中，无需额外安装

# 启动 MongoDB (默认端口 27017)
mongod --dbpath ./data/mongodb

# 启动 Redis (默认端口 6379)
redis-server
```

> ⚠️ **重要说明**:
>
> - **🐳 Docker部署**: 数据库自动包含，无需额外配置
> - **💻 本地部署**: 可选择仅启动数据库服务或完全本地安装
> - **📋 推荐**: 使用Docker部署以获得最佳体验和一致性

#### 数据库配置选项

**环境变量配置**（推荐）：

```bash
# MongoDB 配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=trading_agents
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
```

**配置文件方式**：

```python
# config/database_config.py
DATABASE_CONFIG = {
    'mongodb': {
        'host': 'localhost',
        'port': 27017,
        'database': 'trading_agents',
        'username': 'admin',
        'password': 'your_password'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'password': 'your_redis_password',
        'db': 0
    }
}
```

#### 数据库功能特性

**MongoDB 功能**：

- ✅ 股票基础信息存储
- ✅ 历史价格数据缓存
- ✅ 分析结果持久化
- ✅ 用户配置管理
- ✅ 自动数据同步

**Redis 功能**：

- ⚡ 实时价格数据缓存
- ⚡ API响应结果缓存
- ⚡ 会话状态管理
- ⚡ 热点数据预加载
- ⚡ 分布式锁支持

#### 智能降级机制

系统采用多层数据源降级策略，确保高可用性：

```
📊 数据获取流程：
1. 🔍 检查 Redis 缓存 (毫秒级)
2. 📚 查询 MongoDB 存储 (秒级)
3. 🌐 调用通达信API (秒级)
4. 💾 本地文件缓存 (备用)
5. ❌ 返回错误信息
```

**配置降级策略**：

```python
# 在 .env 文件中配置
ENABLE_MONGODB=true
ENABLE_REDIS=true
ENABLE_FALLBACK=true

# 缓存过期时间（秒）
REDIS_CACHE_TTL=300
MONGODB_CACHE_TTL=3600
```

#### 性能优化建议

**生产环境配置**：

```bash
# MongoDB 优化
MONGODB_MAX_POOL_SIZE=50
MONGODB_MIN_POOL_SIZE=5
MONGODB_MAX_IDLE_TIME=30000

# Redis 优化
REDIS_MAX_CONNECTIONS=20
REDIS_CONNECTION_POOL_SIZE=10
REDIS_SOCKET_TIMEOUT=5
```

#### 数据库管理工具

```bash
# 初始化数据库
python scripts/setup/init_database.py

# 系统状态检查
python scripts/validation/check_system_status.py

# 清理缓存工具
python scripts/maintenance/cleanup_cache.py --days 7
```

#### 故障排除

**常见问题解决**：

1. **🪟 Windows 10 ChromaDB兼容性问题**

   **问题现象**：在Windows 10上出现 `Configuration error: An instance of Chroma already exists for ephemeral with different settings` 错误，而Windows 11正常。

   **快速解决方案**：

   ```bash
   # 方案1：禁用内存功能（推荐）
   # 在 .env 文件中添加：
   MEMORY_ENABLED=false

   # 方案2：使用专用修复脚本
   powershell -ExecutionPolicy Bypass -File scripts\fix_chromadb_win10.ps1

   # 方案3：管理员权限运行
   # 右键PowerShell -> "以管理员身份运行"
   ```

   **详细解决方案**：参考 [Windows 10兼容性指南](docs/troubleshooting/windows10-chromadb-fix.md)
2. **MongoDB连接失败**

   **Docker部署**：

   ```bash
   # 检查服务状态
   docker-compose logs mongodb

   # 重启服务
   docker-compose restart mongodb
   ```

   **本地部署**：

   ```bash
   # 检查MongoDB进程
   ps aux | grep mongod

   # 重启MongoDB
   sudo systemctl restart mongod  # Linux
   brew services restart mongodb  # macOS
   ```
3. **Redis连接超时**

   ```bash
   # 检查Redis状态
   redis-cli ping

   # 清理Redis缓存
   redis-cli flushdb
   ```
4. **缓存问题**

   ```bash
   # 检查系统状态和缓存
   python scripts/validation/check_system_status.py

   # 清理过期缓存
   python scripts/maintenance/cleanup_cache.py --days 7
   ```

> 💡 **提示**: 即使不配置数据库，系统仍可正常运行，会自动降级到API直接调用模式。数据库配置是可选的性能优化功能。

> 📚 **详细文档**: 更多数据库配置信息请参考 [数据库架构文档](docs/architecture/database-architecture.md)

### 📤 报告导出功能

#### 新增功能：专业分析报告导出

本项目现已支持将股票分析结果导出为多种专业格式：

**支持的导出格式**：

- **📄 Markdown (.md)** - 轻量级标记语言，适合技术用户和版本控制
- **📝 Word (.docx)** - Microsoft Word文档，适合商务报告和进一步编辑
- **📊 PDF (.pdf)** - 便携式文档格式，适合正式分享和打印

**报告内容结构**：

- 🎯 **投资决策摘要** - 买入/持有/卖出建议，置信度，风险评分
- 📊 **详细分析报告** - 技术分析，基本面分析，市场情绪，新闻事件
- ⚠️ **风险提示** - 完整的投资风险声明和免责条款
- 📋 **配置信息** - 分析参数，模型信息，生成时间

**使用方法**：

1. 完成股票分析后，在结果页面底部找到"📤 导出报告"部分
2. 选择需要的格式：Markdown、Word或PDF
3. 点击导出按钮，系统自动生成并提供下载

**安装导出依赖**：

```bash
# 安装Python依赖
pip install markdown pypandoc

# 安装系统工具（用于PDF导出）
# Windows: choco install pandoc wkhtmltopdf
# macOS: brew install pandoc wkhtmltopdf
# Linux: sudo apt-get install pandoc wkhtmltopdf
```

> 📚 **详细文档**: 完整的导出功能使用指南请参考 [导出功能指南](docs/EXPORT_GUIDE.md)

### 🚀 启动应用

#### 🐳 Docker启动（推荐）

如果您使用Docker部署，应用已经自动启动：

```bash
# 应用已在Docker中运行，直接访问：
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f web
```

#### 💻 本地启动

如果您使用本地部署：

```bash
# 1. 激活虚拟环境
# Windows
.\env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 2. 安装项目到虚拟环境（重要！）
pip install -e .

# 3. 启动Web管理界面
# 方法1：使用项目启动脚本（推荐）
python start_web.py

# 方法2：使用原始启动脚本
python web/run_web.py

# 方法3：直接使用streamlit（需要先安装项目）
streamlit run web/app.py
```

然后在浏览器中访问 `http://localhost:8501`

**Web界面特色功能**:

- 🇺🇸 **美股分析**: 支持 AAPL, TSLA, NVDA 等美股代码
- 🇨🇳 **A股分析**: 支持 000001, 600519, 300750 等A股代码
- 📊 **实时数据**: 通达信API提供A股实时行情数据
- 🤖 **智能体选择**: 可选择不同的分析师组合
- 📤 **报告导出**: 一键导出Markdown/Word/PDF格式专业分析报告
- 🎯 **5级研究深度**: 从快速分析(2-4分钟)到全面分析(15-25分钟)
- 📊 **智能分析师选择**: 市场技术、基本面、新闻、社交媒体分析师
- 🔄 **实时进度显示**: 可视化分析过程，避免等待焦虑
- 📈 **结构化结果**: 投资建议、目标价位、置信度、风险评估
- 🇨🇳 **完全中文化**: 界面和分析结果全中文显示

**研究深度级别说明**:

- **1级 - 快速分析** (2-4分钟): 日常监控，基础决策
- **2级 - 基础分析** (4-6分钟): 常规投资，平衡速度
- **3级 - 标准分析** (6-10分钟): 重要决策，推荐默认
- **4级 - 深度分析** (10-15分钟): 重大投资，详细研究
- **5级 - 全面分析** (15-25分钟): 最重要决策，最全面分析

#### 💻 代码调用（适合开发者）

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 配置阿里百炼
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "qwen-plus"      # 深度分析
config["quick_think_llm"] = "qwen-turbo"    # 快速任务

# 创建交易智能体
ta = TradingAgentsGraph(debug=True, config=config)

# 分析股票 (以苹果公司为例)
state, decision = ta.propagate("AAPL", "2024-01-15")

# 输出分析结果
print(f"推荐动作: {decision['action']}")
print(f"置信度: {decision['confidence']:.1%}")
print(f"风险评分: {decision['risk_score']:.1%}")
print(f"推理过程: {decision['reasoning']}")
```

#### 快速启动脚本

```bash
# 阿里百炼演示（推荐中文用户）
python examples/dashscope/demo_dashscope_chinese.py

# 阿里百炼完整演示
python examples/dashscope/demo_dashscope.py

# 阿里百炼简化测试
python examples/dashscope/demo_dashscope_simple.py

# OpenAI演示（需要国外API）
python examples/openai/demo_openai.py

# 集成测试
python tests/integration/test_dashscope_integration.py
```

#### 📁 数据目录配置

**新功能**: 灵活配置数据存储路径，支持多种配置方式：

```bash
# 查看当前数据目录配置
python -m cli.main data-config --show

# 设置自定义数据目录
python -m cli.main data-config --set /path/to/your/data

# 重置为默认配置
python -m cli.main data-config --reset
```

**环境变量配置**:

```bash
# Windows
set TRADING_AGENTS_DATA_DIR=C:\MyTradingData

# Linux/macOS
export TRADING_AGENTS_DATA_DIR=/home/user/trading_data
```

**程序化配置**:

```python
from tradingagents.config_manager import ConfigManager

# 设置数据目录
config_manager = ConfigManager()
config_manager.set_data_directory("/path/to/data")

# 获取配置
data_dir = config_manager.get_data_directory()
print(f"数据目录: {data_dir}")
```

**配置优先级**: 程序设置 > 环境变量 > 配置文件 > 默认值

详细说明请参考: [📁 数据目录配置指南](docs/configuration/data-directory-configuration.md)

### 交互式分析

```bash
# 启动交互式命令行界面
python -m cli.main
```

## 🎯 **快速导航** - 找到您需要的内容


| 🎯**我想要...** | 📖**推荐文档**                                            | ⏱️**阅读时间** |
| --------------- | --------------------------------------------------------- | ---------------- |
| **快速上手**    | [🚀 快速开始](docs/overview/quick-start.md)               | 10分钟           |
| **了解架构**    | [🏛️ 系统架构](docs/architecture/system-architecture.md) | 15分钟           |
| **看代码示例**  | [📚 基础示例](docs/examples/basic-examples.md)            | 20分钟           |
| **解决问题**    | [🆘 常见问题](docs/faq/faq.md)                            | 5分钟            |
| **深度学习**  | [📁 完整文档目录](#-详细文档目录)                         | 2小时+           |

> 💡 **提示**: 我们的 `docs/` 目录包含了 **50,000+字** 的详细中文文档，这是与原版最大的区别！

## 📚 完整文档体系 - 核心亮点

> **🌟 这是本项目与原版最大的区别！** 我们构建了业界最完整的中文金融AI框架文档体系，包含超过 **50,000字** 的详细技术文档，**20+** 个专业文档文件，**100+** 个代码示例。

### 🎯 为什么选择我们的文档？


| 对比维度     | 原版 TradingAgents | 🚀**中文增强版**           |
| ------------ | ------------------ | -------------------------- |
| **文档语言** | 英文基础说明       | **完整中文体系**           |
| **文档深度** | 简单介绍           | **深度技术剖析**           |
| **架构说明** | 概念性描述         | **详细设计文档 + 架构图**  |
| **使用指南** | 基础示例           | **从入门到专家的完整路径** |
| **故障排除** | 无                 | **详细FAQ + 解决方案**     |
| **代码示例** | 少量示例           | **100+ 实用示例**          |

### 📖 文档导航 - 按学习路径组织

#### 🚀 **新手入门路径** (推荐从这里开始)

1. [📋 项目概述](docs/overview/project-overview.md) - **了解项目背景和核心价值**
2. [⚙️ 详细安装](docs/overview/installation.md) - **各平台详细安装指南**
3. [🚀 快速开始](docs/overview/quick-start.md) - **10分钟上手指南**
4. [📚 基础示例](docs/examples/basic-examples.md) - **8个实用的入门示例**

#### 🏗️ **架构理解路径** (深入了解系统设计)

1. [🏛️ 系统架构](docs/architecture/system-architecture.md) - **完整的系统架构设计**
2. [🤖 智能体架构](docs/architecture/agent-architecture.md) - **多智能体协作机制**
3. [📊 数据流架构](docs/architecture/data-flow-architecture.md) - **数据处理全流程**
4. [🔄 图结构设计](docs/architecture/graph-structure.md) - **LangGraph工作流程**

#### 🤖 **智能体深度解析** (了解每个智能体的设计)

1. [📈 分析师团队](docs/agents/analysts.md) - **四类专业分析师详解**
2. [🔬 研究员团队](docs/agents/researchers.md) - **看涨/看跌辩论机制**
3. [💼 交易员智能体](docs/agents/trader.md) - **交易决策制定流程**
4. [🛡️ 风险管理](docs/agents/risk-management.md) - **多层次风险评估**
5. [👔 管理层智能体](docs/agents/managers.md) - **协调和决策管理**

#### 📊 **数据处理专题** (掌握数据处理技术)

1. [🔌 数据源集成](docs/data/data-sources.md) - **多数据源API集成**
2. [⚙️ 数据处理流程](docs/data/data-processing.md) - **数据清洗和转换**
3. [💾 缓存策略](docs/data/caching.md) - **多层缓存优化性能**

#### ⚙️ **配置和优化** (性能调优和定制)

1. [📝 配置指南](docs/configuration/config-guide.md) - **详细配置选项说明**
2. [🧠 LLM配置](docs/configuration/llm-config.md) - **大语言模型优化**

#### 💡 **高级应用** (扩展开发和实战)

1. [📚 基础示例](docs/examples/basic-examples.md) - **8个实用基础示例**
2. [🚀 高级示例](docs/examples/advanced-examples.md) - **复杂场景和扩展开发**

#### ❓ **问题解决** (遇到问题时查看)

1. [🆘 常见问题](docs/faq/faq.md) - **详细FAQ和解决方案**

### 📊 文档统计数据

- 📄 **文档文件数**: 20+ 个专业文档
- 📝 **总字数**: 50,000+ 字详细内容
- 💻 **代码示例**: 100+ 个实用示例
- 📈 **架构图表**: 10+ 个专业图表
- 🎯 **覆盖范围**: 从入门到专家的完整路径

### 🎨 文档特色

- **🇨🇳 完全中文化**: 专为中文用户优化的表达方式
- **📊 图文并茂**: 丰富的架构图和流程图
- **💻 代码丰富**: 每个概念都有对应的代码示例
- **🔍 深度剖析**: 不仅告诉你怎么做，还告诉你为什么这样做
- **🛠️ 实用导向**: 所有文档都面向实际应用场景

---

## 📚 详细文档目录

### 📁 **docs/ 目录结构** - 完整的知识体系

```
docs/
├── 📖 overview/              # 项目概览 - 新手必读
│   ├── project-overview.md   # 📋 项目详细介绍
│   ├── quick-start.md        # 🚀 10分钟快速上手
│   └── installation.md       # ⚙️ 详细安装指南
│
├── 🏗️ architecture/          # 系统架构 - 深度理解
│   ├── system-architecture.md    # 🏛️ 整体架构设计
│   ├── agent-architecture.md     # 🤖 智能体协作机制
│   ├── data-flow-architecture.md # 📊 数据流处理架构
│   └── graph-structure.md        # 🔄 LangGraph工作流
│
├── 🤖 agents/               # 智能体详解 - 核心组件
│   ├── analysts.md          # 📈 四类专业分析师
│   ├── researchers.md       # 🔬 看涨/看跌辩论机制
│   ├── trader.md           # 💼 交易决策制定
│   ├── risk-management.md  # 🛡️ 多层风险评估
│   └── managers.md         # 👔 管理层协调
│
├── 📊 data/                 # 数据处理 - 技术核心
│   ├── data-sources.md      # 🔌 多数据源集成
│   ├── data-processing.md   # ⚙️ 数据处理流程
│   └── caching.md          # 💾 缓存优化策略
│
├── ⚙️ configuration/        # 配置优化 - 性能调优
│   ├── config-guide.md      # 📝 详细配置说明
│   └── llm-config.md       # 🧠 LLM模型优化
│
├── 💡 examples/             # 示例教程 - 实战应用
│   ├── basic-examples.md    # 📚 8个基础示例
│   └── advanced-examples.md # 🚀 高级开发示例
│
└── ❓ faq/                  # 问题解决 - 疑难解答
    └── faq.md              # 🆘 常见问题FAQ
```

### 🎯 **重点推荐文档** (必读精选)

#### 🔥 **最受欢迎的文档**

1. **[📋 项目概述](docs/overview/project-overview.md)** - ⭐⭐⭐⭐⭐

   > 了解项目的核心价值和技术特色，5分钟读懂整个框架
   >
2. **[🏛️ 系统架构](docs/architecture/system-architecture.md)** - ⭐⭐⭐⭐⭐

   > 深度解析多智能体协作机制，包含详细架构图
   >
3. **[📚 基础示例](docs/examples/basic-examples.md)** - ⭐⭐⭐⭐⭐

   > 8个实用示例，从股票分析到投资组合优化
   >

#### 🚀 **技术深度文档**

1. **[🤖 智能体架构](docs/architecture/agent-architecture.md)**

   > 多智能体设计模式和协作机制详解
   >
2. **[📊 数据流架构](docs/architecture/data-flow-architecture.md)**

   > 数据获取、处理、缓存的完整流程
   >
3. **[🔬 研究员团队](docs/agents/researchers.md)**

   > 看涨/看跌研究员辩论机制的创新设计
   >

#### 💼 **实用工具文档**

1. **[🌐 Web界面指南](docs/usage/web-interface-guide.md)** - ⭐⭐⭐⭐⭐

   > 完整的Web界面使用教程，包含5级研究深度详细说明
   >
2. **[💰 投资分析指南](docs/usage/investment_analysis_guide.md)**

   > 从基础到高级的完整投资分析教程
   >
3. **[🧠 LLM配置](docs/configuration/llm-config.md)**

   > 多LLM模型配置和成本优化策略
   >
4. **[💾 缓存策略](docs/data/caching.md)**

   > 多层缓存设计，显著降低API调用成本
   >
5. **[🆘 常见问题](docs/faq/faq.md)**

   > 详细的FAQ和故障排除指南
   >

### 📖 **按模块浏览文档**

<details>
<summary><strong>📖 概览文档</strong> - 项目入门必读</summary>

- [📋 项目概述](docs/overview/project-overview.md) - 详细的项目背景和特性介绍
- [🚀 快速开始](docs/overview/quick-start.md) - 从安装到第一次运行的完整指南
- [⚙️ 详细安装](docs/overview/installation.md) - 各平台详细安装说明

</details>

<details>
<summary><strong>🏗️ 架构文档</strong> - 深度理解系统设计</summary>

- [🏛️ 系统架构](docs/architecture/system-architecture.md) - 完整的系统架构设计
- [🤖 智能体架构](docs/architecture/agent-architecture.md) - 智能体设计模式和协作机制
- [📊 数据流架构](docs/architecture/data-flow-architecture.md) - 数据获取、处理和分发流程
- [🔄 图结构设计](docs/architecture/graph-structure.md) - LangGraph工作流程设计

</details>

<details>
<summary><strong>🤖 智能体文档</strong> - 核心组件详解</summary>

- [📈 分析师团队](docs/agents/analysts.md) - 四类专业分析师详解
- [🔬 研究员团队](docs/agents/researchers.md) - 看涨/看跌研究员和辩论机制
- [💼 交易员智能体](docs/agents/trader.md) - 交易决策制定流程
- [🛡️ 风险管理](docs/agents/risk-management.md) - 多层次风险评估体系
- [👔 管理层智能体](docs/agents/managers.md) - 协调和决策管理

</details>

<details>
<summary><strong>📊 数据处理</strong> - 技术核心实现</summary>

- [🔌 数据源集成](docs/data/data-sources.md) - 支持的数据源和API集成
- [⚙️ 数据处理流程](docs/data/data-processing.md) - 数据清洗、转换和验证
- [💾 缓存策略](docs/data/caching.md) - 多层缓存优化性能

</details>

<details>
<summary><strong>⚙️ 配置与部署</strong> - 性能调优指南</summary>

- [📝 配置指南](docs/configuration/config-guide.md) - 详细的配置选项说明
- [🧠 LLM配置](docs/configuration/llm-config.md) - 大语言模型配置优化

</details>

<details>
<summary><strong>💡 示例和教程</strong> - 实战应用指南</summary>

- [📚 基础示例](docs/examples/basic-examples.md) - 8个实用的基础示例
- [🚀 高级示例](docs/examples/advanced-examples.md) - 复杂场景和扩展开发

</details>

<details>
<summary><strong>❓ 帮助文档</strong> - 问题解决方案</summary>

- [🆘 常见问题](docs/faq/faq.md) - 详细的FAQ和解决方案

</details>

## 💰 成本控制

### 典型使用成本

- **经济模式**: $0.01-0.05/次分析 (使用 gpt-4o-mini)
- **标准模式**: $0.05-0.15/次分析 (使用 gpt-4o)
- **高精度模式**: $0.10-0.30/次分析 (使用 gpt-4o + 多轮辩论)

### 成本优化建议

```python
# 低成本配置示例
cost_optimized_config = {
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini", 
    "max_debate_rounds": 1,
    "online_tools": False  # 使用缓存数据
}
```

## 🤝 贡献指南

我们欢迎各种形式的贡献：

### 贡献类型

- 🐛 **Bug修复** - 发现并修复问题
- ✨ **新功能** - 添加新的功能特性
- 📚 **文档改进** - 完善文档和教程
- 🌐 **本地化** - 翻译和本地化工作
- 🎨 **代码优化** - 性能优化和代码重构

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 📋 查看贡献者

查看所有贡献者和详细贡献内容：**[🤝 贡献者名单](CONTRIBUTORS.md)**

## 📄 许可证

本项目基于 Apache 2.0 许可证开源。详见 [LICENSE](LICENSE) 文件。

### 许可证说明

- ✅ 商业使用
- ✅ 修改和分发
- ✅ 私人使用
- ✅ 专利使用
- ❗ 需要保留版权声明
- ❗ 需要包含许可证副本

## 🙏 致谢与感恩

### 🌟 向源项目开发者致敬

我们向 [Tauric Research](https://github.com/TauricResearch) 团队表达最深的敬意和感谢：

- **🎯 愿景领导者**: 感谢您们在AI金融领域的前瞻性思考和创新实践
- **💎 珍贵源码**: 感谢您们开源的每一行代码，它们凝聚着无数的智慧和心血
- **🏗️ 架构大师**: 感谢您们设计了如此优雅、可扩展的多智能体框架
- **💡 技术先驱**: 感谢您们将前沿AI技术与金融实务完美结合
- **🔄 持续贡献**: 感谢您们持续的维护、更新和改进工作

### 🤝 社区贡献者致谢

感谢所有为TradingAgents-CN项目做出贡献的开发者和用户！

详细的贡献者名单和贡献内容请查看：**[📋 贡献者名单](CONTRIBUTORS.md)**

包括但不限于：

- 🐳 **Docker容器化** - 部署方案优化
- 📄 **报告导出功能** - 多格式输出支持
- 🐛 **Bug修复** - 系统稳定性提升
- 🔧 **代码优化** - 用户体验改进
- 📝 **文档完善** - 使用指南和教程
- 🌍 **社区建设** - 问题反馈和推广
- **🌍 开源贡献**: 感谢您们选择Apache 2.0协议，给予开发者最大的自由
- **📚 知识分享**: 感谢您们提供的详细文档和最佳实践指导

**特别感谢**：[TradingAgents](https://github.com/TauricResearch/TradingAgents) 项目为我们提供了坚实的技术基础。虽然Apache 2.0协议赋予了我们使用源码的权利，但我们深知每一行代码的珍贵价值，将永远铭记并感谢您们的无私贡献。

### 🇨🇳 推广使命的初心

创建这个中文增强版本，我们怀着以下初心：

- **🌉 技术传播**: 让优秀的TradingAgents技术在中国得到更广泛的应用
- **🎓 教育普及**: 为中国的AI金融教育提供更好的工具和资源
- **🤝 文化桥梁**: 在中西方技术社区之间搭建交流合作的桥梁
- **🚀 创新推动**: 推动中国金融科技领域的AI技术创新和应用

### 🌍 开源社区

感谢所有为本项目贡献代码、文档、建议和反馈的开发者和用户。正是因为有了大家的支持，我们才能更好地服务中文用户社区。

### 🤝 合作共赢

我们承诺：

- **尊重原创**: 始终尊重源项目的知识产权和开源协议
- **反馈贡献**: 将有价值的改进和创新反馈给源项目和开源社区
- **持续改进**: 不断完善中文增强版本，提供更好的用户体验
- **开放合作**: 欢迎与源项目团队和全球开发者进行技术交流与合作

## 📈 版本历史

- **v0.1.13** (2025-08-02): 🤖 原生OpenAI支持与Google AI生态系统全面集成 ✨ **最新版本**
- **v0.1.12** (2025-07-29): 🧠 智能新闻分析模块与项目结构优化
- **v0.1.11** (2025-07-27): 🤖 多LLM提供商集成与模型选择持久化
- **v0.1.10** (2025-07-18): 🚀 Web界面实时进度显示与智能会话管理
- **v0.1.9** (2025-07-16): 🎯 CLI用户体验重大优化与统一日志管理
- **v0.1.8** (2025-07-15): 🎨 Web界面全面优化与用户体验提升
- **v0.1.7** (2025-07-13): 🐳 容器化部署与专业报告导出
- **v0.1.6** (2025-07-11): 🔧 阿里百炼修复与数据源升级
- **v0.1.5** (2025-07-08): 📊 添加Deepseek模型支持
- **v0.1.4** (2025-07-05): 🏗️ 架构优化与配置管理重构
- **v0.1.3** (2025-06-28): 🇨🇳 A股市场完整支持
- **v0.1.2** (2025-06-15): 🌐 Web界面和配置管理
- **v0.1.1** (2025-06-01): 🧠 国产LLM集成

📋 **详细更新日志**: [CHANGELOG.md](./docs/releases/CHANGELOG.md)

## 📞 联系方式

- **GitHub Issues**: [提交问题和建议](https://github.com/hsliuping/TradingAgents-CN/issues)
- **邮箱**: hsliup@163.com
- 项目ＱＱ群：782124367
- **原项目**: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **文档**: [完整文档目录](docs/)

## ⚠️ 风险提示

**重要声明**: 本框架仅用于研究和教育目的，不构成投资建议。

- 📊 交易表现可能因多种因素而异
- 🤖 AI模型的预测存在不确定性
- 💰 投资有风险，决策需谨慎
- 👨‍💼 建议咨询专业财务顾问

---

<div align="center">

**🌟 如果这个项目对您有帮助，请给我们一个 Star！**

[⭐ Star this repo](https://github.com/hsliuping/TradingAgents-CN) | [🍴 Fork this repo](https://github.com/hsliuping/TradingAgents-CN/fork) | [📖 Read the docs](./docs/)

</div>
