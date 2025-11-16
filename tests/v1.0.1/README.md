# 提示词模板系统v1.0.1测试

## 测试文件结构

```
tests/v1.0.1/
├── __init__.py                      # 包初始化
├── conftest.py                      # pytest配置和fixtures
├── test_prompt_template_system.py   # 单元测试
├── test_integration.py              # 集成测试
├── test_api_endpoints.py            # API端点测试
└── README.md                        # 本文档
```

## 运行测试

### 运行所有测试

```bash
pytest tests/v1.0.1/ -v
```

### 运行特定测试文件

```bash
# 单元测试
pytest tests/v1.0.1/test_prompt_template_system.py -v

# 集成测试
pytest tests/v1.0.1/test_integration.py -v

# API端点测试
pytest tests/v1.0.1/test_api_endpoints.py -v
```

### 运行特定测试

```bash
pytest tests/v1.0.1/test_integration.py::test_complete_workflow -v
```

## 测试覆盖范围

### test_prompt_template_system.py
- ✅ 创建模板
- ✅ 获取模板
- ✅ 更新模板
- ✅ 创建偏好
- ✅ 获取用户偏好

### test_integration.py
- ✅ 完整工作流（创建系统模板 -> 创建偏好 -> 创建配置 -> 获取活跃配置）
- ✅ 用户模板优先级（用户模板 > 系统模板）

### test_api_endpoints.py
- ✅ 创建模板API
- ✅ 获取模板API
- ✅ 创建偏好API
- ✅ 获取用户偏好API
- ✅ 获取Agent模板API

## 测试依赖

- pytest
- pytest-asyncio
- fastapi
- pymongo

## 环境配置

确保 `.env` 文件中配置了正确的MongoDB连接：

```
MONGO_URI=mongodb://localhost:27017
MONGO_DB=trading_agents
```

## 常见问题

**Q: 测试失败，提示MongoDB连接错误**
A: 确保MongoDB服务正在运行，并且MONGO_URI配置正确。

**Q: 异步测试失败**
A: 确保已安装pytest-asyncio：`pip install pytest-asyncio`

**Q: 测试数据污染**
A: 每个测试使用不同的user_id来避免数据污染。

