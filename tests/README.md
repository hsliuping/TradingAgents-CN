# TradingAgents-CN 测试目录

这个目录包含 TradingAgents-CN 的标准测试套件、历史测试脚本和外部集成测试。

当前约定：

- 默认标准套件不依赖任何真实 API Key
- 需要真实 Key 的测试必须显式标记为 `integration`
- 未配置所需环境变量时，这类测试应显示为 `skipped`，而不是 `failed`
- 真实密钥绝不写入仓库，只能通过本地环境变量提供

## 目录结构

```
tests/
├── README.md                           # 本文件
├── __init__.py                         # Python包初始化
├── integration/                        # 集成测试
│   ├── __init__.py
│   └── test_dashscope_integration.py   # 阿里百炼集成测试
├── test_*.py                          # 各种功能测试
└── debug_*.py                         # 调试和诊断工具
```

## 测试分类

### 🔧 API和集成测试
- `test_all_apis.py` - 所有API密钥测试
- `test_correct_apis.py` - Google和Reddit API测试
- `test_analysis_with_apis.py` - API集成分析测试
- `test_toolkit_tools.py` - 工具包测试
- `integration/test_dashscope_integration.py` - 阿里百炼集成测试

### 📊 数据源测试
- `fast_tdx_test.py` - Tushare数据接口快速连接测试
- `test_tdx_integration.py` - Tushare数据接口完整集成测试

### ⚡ 性能测试
- `test_redis_performance.py` - Redis性能基准测试
- `quick_redis_test.py` - Redis快速连接测试

### 🤖 AI模型测试
- `test_chinese_output.py` - 中文输出测试
- `test_gemini*.py` - Google Gemini模型系列测试
- `test_embedding_models.py` - 嵌入模型测试
- `test_google_memory_fix.py` - Google AI内存功能测试

### 🌐 Web界面测试
- `test_web_interface.py` - Web界面功能测试

### 🔍 调试和诊断工具
- `debug_imports.py` - 导入问题诊断
- `diagnose_gemini_25.py` - Gemini 2.5模型诊断
- `check_gemini_models.py` - Gemini模型可用性检查

### 🧪 功能测试
- `test_analysis.py` - 基础分析功能测试
- `test_format_fix.py` - 格式化修复测试
- `test_progress_time_calculation.py` - 进度时间估算相关测试

## 运行测试

### 默认标准套件

从项目根目录运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

默认会执行当前维护中的标准测试集合：

- `tests/system/`
- `tests/unit/`
- `tests/test_recent_changes_unittest.py`
- `tests/test_progress_time_calculation.py`

这部分测试不需要任何真实 provider key，目标是保持稳定全绿。

### 前端校验现状

前端当前维护的是工程校验脚本，而不是正式测试套件：

- `pnpm lint`
- `pnpm type-check`
- `pnpm build`

目前仓库里没有接入统一的 `vitest/jest/playwright` 标准入口，因此不要把前端工程校验等同于“前端全量测试”。

### 运行外部集成测试

只有在你主动提供测试专用环境变量时，才建议运行外部集成测试：

```bash
export TEST_DASHSCOPE_API_KEY=your_real_test_key
export TEST_FINNHUB_API_KEY=your_real_test_key
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -m integration
```

如果没有配置这些变量，对应测试应自动 `skipped`。

如果你要单独运行带 `@pytest.mark.anyio` 的异步测试文件，请直接使用常规 `pytest` 入口，不要再额外设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，否则 `anyio` 插件不会被加载。

### 运行历史脚本式测试

历史目录中有大量脚本式文件，适合人工排查，不属于默认标准套件。需要时可以单独运行：

```bash
python tests/integration/test_dashscope_integration.py
python tests/test_all_apis.py
python tests/test_web_interface.py
```

### 诊断工具
```bash
# 诊断Gemini模型问题
python tests/diagnose_gemini_25.py

# 检查导入问题
python tests/debug_imports.py

# 检查所有可用的Gemini模型
python tests/check_gemini_models.py
```

## 测试环境要求

### 测试专用环境变量

优先使用 `.env.example` 里预留的 `TEST_*` 变量，而不是直接复用生产/开发环境密钥。

在没有真实 key 的情况下，外部测试应跳过。

```env
TEST_DASHSCOPE_API_KEY=
TEST_FINNHUB_API_KEY=
TEST_OPENAI_API_KEY=
TEST_TUSHARE_TOKEN=
TEST_GOOGLE_API_KEY=
TEST_REDDIT_CLIENT_ID=
TEST_REDDIT_CLIENT_SECRET=
TEST_REDDIT_USER_AGENT=
```

### Python依赖
```bash
pip install -r requirements.txt
```

### 测试结果解读
- **所有测试通过**：功能完全正常，可以使用完整功能
- **部分测试通过**：基本功能正常，可能需要检查配置
- **大部分测试失败**：存在问题，需要排查API密钥和环境配置

## 贡献指南

添加新测试时，请遵循以下规范：

1. **测试文件命名**: `test_功能名称.py`
2. **调试工具命名**: `debug_问题描述.py` 或 `diagnose_问题描述.py`
3. **测试函数命名**: `test_具体功能()`
4. **文档**: 在函数开头添加清晰的文档字符串
5. **分类**: 根据功能将测试放在适当的类别中

### 测试模板

```python
import pytest

pytestmark = pytest.mark.integration

def test_live_provider_call():
    """
    需要环境变量：
    - TEST_OPENAI_API_KEY
    未配置时应 skipped，不应 failed。
    """
    from tests.conftest import require_env

    api_key = require_env("TEST_OPENAI_API_KEY")
    assert api_key
```

## 编写要求

需要真实外部服务的测试请遵循：

1. 文件顶部注明需要哪些环境变量
2. 使用 `pytest.mark.integration`
3. 通过 `tests.conftest.require_env()` 读取环境变量
4. 未配置时自动跳过，不得直接报错
5. 不要在仓库里写入任何真实 key 或长得像真实 key 的样例

## 最近更新

- ✅ 添加了Google Gemini模型系列测试
- ✅ 添加了Web界面Google模型选择测试
- ✅ 添加了API集成测试（Google、Reddit）
- ✅ 添加了中文输出功能测试
- ✅ 添加了内存系统和嵌入模型测试
- ✅ 整理了所有测试文件到tests目录
- ✅ 添加了调试和诊断工具

## 测试最佳实践

1. **测试隔离**：每个测试应该独立运行
2. **清晰命名**：测试函数名应该清楚描述测试内容
3. **错误处理**：测试应该能够处理各种错误情况
4. **文档化**：为复杂的测试添加详细注释
5. **快速反馈**：测试应该尽快给出结果

## 故障排除

### 常见问题
1. **API密钥问题** - 检查.env文件配置
2. **网络连接问题** - 确认网络和防火墙设置
3. **依赖包问题** - 确保所有依赖已安装
4. **模型兼容性** - 检查模型名称和版本

### 调试技巧
1. 启用详细输出查看错误信息
2. 单独运行测试函数定位问题
3. 使用诊断工具检查配置
4. 查看Web应用日志了解运行状态

## 许可证

本项目遵循Apache 2.0许可证。


## 新增的测试文件

### 集成测试
- `quick_test.py` - 快速集成测试，验证基本功能
- `test_smart_system.py` - 智能系统完整测试
- `demo_fallback_system.py` - 降级系统演示和测试

### 运行方法
```bash
# 快速测试
python tests/quick_test.py

# 智能系统测试
python tests/test_smart_system.py

# 降级系统演示
python tests/demo_fallback_system.py
```
