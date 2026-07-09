# 工作流 API 实现总结

## ✅ 完成内容

为 TradingAgents-CN Pro 添加了完整的工作流 API 接口，允许外部服务调用自定义工作流。

---

## 📁 新增文件

### 1. `app/routers/workflow_api.py`

**用途**: 工作流 API 路由

**核心功能**:
- ✅ 执行工作流（同步/异步模式）
- ✅ 查询任务状态
- ✅ 获取任务结果
- ✅ 取消任务

**请求模型**:
- `WorkflowExecuteRequest` - 工作流执行请求
- `WorkflowExecuteResponse` - 工作流执行响应
- `TaskStatusResponse` - 任务状态响应

**API 端点**:
- `POST /api/v1/workflow/execute` - 执行工作流
- `GET /api/v1/workflow/task/{task_id}/status` - 查询任务状态
- `GET /api/v1/workflow/task/{task_id}/result` - 获取任务结果
- `POST /api/v1/workflow/task/{task_id}/cancel` - 取消任务

### 2. `docs/api/workflow_api_guide.md`

**用途**: API 使用文档

**包含内容**:
- 📋 API 概述和认证方式
- 🔌 详细的 API 端点说明
- 📝 Python、JavaScript、cURL 使用示例
- 🔧 高级用法（同步模式、自定义参数、回调 URL）
- ⚠️ 注意事项和错误处理

---

## 🔧 修改文件

### 1. `app/main.py`

**修改内容**:
- 添加了 `workflow_api_router` 的导入和注册
- 路由路径: `/api/v1/workflow`
- 标签: `workflow-api`

**修改位置**: 第 1085-1092 行

```python
from app.routers import workflow_api as workflow_api_router
register_router_with_log(app, workflow_api_router.router, "工作流API路由 (workflow-api)", tags=["workflow-api"])
```

---

## 🎯 核心特性

### 1. 双模式执行

**异步模式**（默认）:
- 立即返回 `task_id`
- 通过轮询查询任务状态
- 适合长时间运行的工作流

**同步模式**:
- 等待执行完成后返回结果
- 支持超时配置（默认 30 分钟）
- 适合快速工作流

### 2. 完整的任务管理

- ✅ 创建任务
- ✅ 查询状态和进度
- ✅ 获取结果
- ✅ 取消任务

### 3. 灵活的参数配置

**标准参数**:
- `workflow_id` - 工作流 ID
- `ticker` / `stock_code` - 股票代码
- `analysis_date` - 分析日期
- `market_type` - 市场类型
- `research_depth` - 研究深度
- `preference_type` - 风险偏好
- `quick_analysis_model` - 快速分析模型
- `deep_analysis_model` - 深度分析模型
- `lookback_days` - 回溯天数
- `max_debate_rounds` - 最大辩论轮数

**自定义参数**:
- `custom_params` - 任意自定义参数字典
- 会合并到任务参数中传递给工作流

### 4. 认证支持

- ✅ JWT Token 认证
- ✅ Session Cookie 认证
- ✅ 任务所有权验证

---

## 📊 使用流程

### 异步模式流程

```
1. POST /api/v1/workflow/execute (async_mode=true)
   ↓
2. 返回 task_id
   ↓
3. 轮询 GET /api/v1/workflow/task/{task_id}/status
   ↓
4. 状态变为 completed
   ↓
5. GET /api/v1/workflow/task/{task_id}/result
   ↓
6. 获取完整结果
```

### 同步模式流程

```
1. POST /api/v1/workflow/execute (async_mode=false)
   ↓
2. 等待执行完成（最多 timeout 秒）
   ↓
3. 直接返回结果或超时错误
```

---

## 🔌 集成示例

### Python 客户端

```python
import requests

class WorkflowAPIClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def execute_workflow(self, workflow_id, ticker, **kwargs):
        """执行工作流（异步）"""
        response = requests.post(
            f"{self.base_url}/api/v1/workflow/execute",
            headers=self.headers,
            json={
                "workflow_id": workflow_id,
                "ticker": ticker,
                "async_mode": True,
                **kwargs
            }
        )
        return response.json()["task_id"]
    
    def get_task_status(self, task_id):
        """查询任务状态"""
        response = requests.get(
            f"{self.base_url}/api/v1/workflow/task/{task_id}/status",
            headers=self.headers
        )
        return response.json()
    
    def get_task_result(self, task_id):
        """获取任务结果"""
        response = requests.get(
            f"{self.base_url}/api/v1/workflow/task/{task_id}/result",
            headers=self.headers
        )
        return response.json()["data"]["result"]
```

---

## 🚀 下一步

1. **测试 API**:
   - 重启后端服务
   - 使用 Postman 或 cURL 测试各个端点
   - 验证异步和同步模式

2. **文档完善**:
   - 添加更多使用示例
   - 补充错误处理说明
   - 添加性能优化建议

3. **功能扩展**:
   - 添加批量执行接口
   - 支持 Webhook 回调
   - 添加任务优先级

---

**创建时间**: 2026-02-19  
**版本**: v1.0.0  
**状态**: ✅ 已完成

