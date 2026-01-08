# API Key 配置优先级说明

## 📋 概述

本文档说明 TradingAgents-CN 系统中 API Key 的配置优先级和验证逻辑。

## 🎯 配置来源

系统支持两种 API Key 配置来源：

1. **MongoDB 数据库**（`llm_providers` 集合）
   - ✅ **通过 Web 界面配置**（推荐）
   - 存储在厂家配置中
   - 所有用户共享
   - 支持在线编辑和更新

2. **环境变量**（`.env` 文件）
   - 系统启动时加载
   - CLI 客户端使用
   - 作为兜底配置
   - 适合开发环境

## 🔄 优先级规则

```
有效的数据库配置 > 环境变量配置 > 无配置（报错）
```

### 什么是"有效的配置"？

系统会验证数据库中的 API Key 是否有效，判断标准：

1. ✅ Key 不为空
2. ✅ Key 不是占位符（不以 `your_` 或 `your-` 开头）
3. ✅ Key 长度 > 10 个字符

### 配置选择逻辑

```python
if 数据库中的 Key 有效:
    使用数据库中的 Key
    来源标记为 "database"
else:
    if 环境变量中有有效的 Key:
        使用环境变量中的 Key
        来源标记为 "environment"
    else:
        报错：未配置有效的 API Key
```

## 📊 使用场景

### 场景 1：只配置环境变量

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-real-key-from-env-12345678
```

**结果**：使用环境变量的 Key

### 场景 2：只配置数据库

```javascript
// MongoDB llm_providers 集合
{
  "name": "deepseek",
  "api_key": "sk-real-key-from-db-87654321"
}
```

**结果**：使用数据库的 Key

### 场景 3：两者都配置（数据库有效）

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-env-key-12345678
```

```javascript
// MongoDB
{
  "name": "deepseek",
  "api_key": "sk-db-key-87654321"  // 有效的 Key
}
```

**结果**：使用数据库的 Key（优先级更高）

### 场景 4：两者都配置（数据库无效）

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-env-key-12345678
```

```javascript
// MongoDB
{
  "name": "deepseek",
  "api_key": "your_deepseek_api_key_here"  // 占位符，无效
}
```

**结果**：使用环境变量的 Key（数据库配置无效，降级到环境变量）

### 场景 5：两者都未配置

```bash
# .env 文件
DEEPSEEK_API_KEY=  # 空
```

```javascript
// MongoDB
{
  "name": "deepseek",
  "api_key": ""  // 空
}
```

**结果**：报错，提示未配置有效的 API Key

## 🔍 验证逻辑

### 无效的 API Key 示例

```python
# ❌ 空字符串
api_key = ""

# ❌ None
api_key = None

# ❌ 占位符（以 your_ 开头）
api_key = "your_api_key_here"
api_key = "your_deepseek_api_key"

# ❌ 占位符（以 your- 开头）
api_key = "your-api-key-here"

# ❌ 长度不够（≤ 10 个字符）
api_key = "short"
api_key = "1234567890"
```

### 有效的 API Key 示例

```python
# ✅ 标准格式
api_key = "sk-1234567890abcdef"

# ✅ 长格式
api_key = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"

# ✅ 其他格式（只要长度 > 10）
api_key = "AIzaSyD1234567890"
```

## 🛠️ 实现细节

### 核心方法

#### 1. `_is_valid_api_key(api_key: str) -> bool`

验证 API Key 是否有效。

```python
def _is_valid_api_key(self, api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    
    api_key = api_key.strip()
    
    if not api_key:
        return False
    
    if api_key.startswith('your_') or api_key.startswith('your-'):
        return False
    
    if len(api_key) <= 10:
        return False
    
    return True
```

#### 2. `_get_env_api_key(provider_name: str) -> Optional[str]`

从环境变量获取 API Key，并验证有效性。

```python
def _get_env_api_key(self, provider_name: str) -> Optional[str]:
    env_key_mapping = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
        # ...
    }
    
    env_var = env_key_mapping.get(provider_name)
    if env_var:
        api_key = os.getenv(env_var)
        if self._is_valid_api_key(api_key):
            return api_key
    
    return None
```

#### 3. `get_llm_providers() -> List[LLMProvider]`

获取所有厂家配置，应用优先级逻辑。

```python
async def get_llm_providers(self) -> List[LLMProvider]:
    providers_data = await providers_collection.find().to_list(length=None)
    providers = []
    
    for provider_data in providers_data:
        provider = LLMProvider(**provider_data)
        
        # 判断数据库中的 Key 是否有效
        db_key_valid = self._is_valid_api_key(provider.api_key)
        
        if not db_key_valid:
            # 尝试从环境变量获取
            env_key = self._get_env_api_key(provider.name)
            if env_key:
                provider.api_key = env_key
                provider.extra_config["source"] = "environment"
        else:
            provider.extra_config["source"] = "database"
        
        providers.append(provider)
    
    return providers
```

## 🧪 测试

运行测试脚本验证配置优先级：

```bash
python scripts/test_api_key_priority.py
```

测试内容：
1. API Key 验证逻辑测试
2. 厂家配置优先级测试
3. 配置来源标识测试

## 📝 最佳实践

### 推荐配置方式

1. **开发环境**：使用 `.env` 文件配置
   - 方便快速切换
   - 不需要数据库操作

2. **生产环境**：✅ **使用 Web 界面配置到数据库**（推荐）
   - 集中管理
   - 可以在线修改
   - 支持审计日志
   - 无需重启服务

3. **混合模式**：数据库配置 + 环境变量兜底
   - 数据库配置主要的 Key
   - 环境变量作为备用
   - 系统自动选择有效的配置

### 如何在 Web 界面配置 API Key

1. **登录系统** → **设置** → **厂家管理**
2. **点击"编辑"按钮**，打开厂家信息编辑对话框
3. **在"API Key"输入框中输入你的 API Key**
4. **点击"更新"按钮**保存

**注意事项**：
- API Key 会被加密存储在数据库中
- 如果留空，系统会自动使用 `.env` 文件中的配置
- 如果输入无效的 Key（占位符或长度不够），系统会忽略并使用环境变量

### 如何添加新的厂家

如果你要使用的大模型厂家不在预设列表中：

1. **登录系统** → **设置** → **厂家管理**
2. **点击"添加厂家"按钮**
3. **填写厂家信息**：
   - **厂家ID**：小写英文标识符（如 `custom_provider`）
   - **显示名称**：中文名称（如 `自定义厂家`）
   - **API Key**：你的 API Key
   - **默认API地址**：厂家的 API 基础地址
4. **点击"添加"按钮**保存

**示例**：添加一个自定义的 OpenAI 兼容 API

```
厂家ID: custom_openai
显示名称: 自定义 OpenAI
描述: 自定义的 OpenAI 兼容 API
官网: https://custom.com
API文档: https://custom.com/docs
默认API地址: https://api.custom.com/v1
API Key: sk-custom-key-1234567890abcdef
```

### 配置检查

在系统启动时，会自动检查所有厂家的配置状态：

```
✅ 使用数据库配置的 DeepSeek API密钥
✅ 数据库配置无效，从环境变量为厂家 OpenAI 获取API密钥
⚠️ 厂家 Anthropic 的数据库配置和环境变量都未配置有效的API密钥
```

## 🔒 安全建议

1. **不要在代码中硬编码 API Key**
2. **生产环境使用环境变量或加密存储**
3. **定期轮换 API Key**
4. **监控 API Key 使用情况**
5. **限制 API Key 的权限范围**

## 📚 相关文档

- [配置管理系统](./CONFIG_MIGRATION_PLAN.md)
- [厂家配置管理](../fixes/data-source/PROVIDER_ID_FIX.md)
- [环境变量配置](.env.example)

