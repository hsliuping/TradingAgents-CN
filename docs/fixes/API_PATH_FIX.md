# 大模型厂家管理API路径修复

## 🐛 问题描述

大模型厂家管理页面加载失败，API请求返回HTML页面而不是JSON数据。

## 🔍 问题分析

### 根本原因
前端API调用路径与后端API路径不一致：

- **后端API路径**: `/api/config/llm/providers`
- **前端调用路径**: `/config/llm/providers` ❌

### 路径构成分析
1. **后端路由定义**:
   ```python
   # app/routers/config.py
   router = APIRouter(prefix="/config", tags=["配置管理"])
   
   # app/main.py  
   app.include_router(config.router, prefix="/api", tags=["config"])
   ```
   最终路径: `/api` + `/config` = `/api/config`

2. **前端API调用**:
   ```typescript
   // 错误的调用
   ApiClient.get('/config/llm/providers')
   
   // 正确的调用
   ApiClient.get('/api/config/llm/providers')
   ```

### 问题表现
- API请求被前端路由处理，返回HTML页面
- 控制台错误: `providers.filter is not a function`
- 页面显示加载失败

## 🔧 修复方案

### 修复文件
- `frontend/src/api/config.ts`

### 修复内容
将所有配置API路径添加 `/api` 前缀：

```typescript
// 大模型厂家管理
getLLMProviders(): Promise<LLMProvider[]> {
  return ApiClient.get('/api/config/llm/providers')  // ✅ 修复后
},

// 大模型配置管理  
getLLMConfigs(): Promise<LLMConfig[]> {
  return ApiClient.get('/api/config/llm')  // ✅ 修复后
},

// 数据源配置管理
getDataSourceConfigs(): Promise<DataSourceConfig[]> {
  return ApiClient.get('/api/config/datasource')  // ✅ 修复后
},

// 系统设置
getSystemSettings(): Promise<Record<string, any>> {
  return ApiClient.get('/api/config/settings')  // ✅ 修复后
},
```

## 📊 修复统计

### 修复的API端点
- ✅ 大模型厂家管理: 6个端点
- ✅ 大模型配置管理: 4个端点  
- ✅ 数据源配置管理: 6个端点
- ✅ 市场分类管理: 4个端点
- ✅ 数据源分组管理: 4个端点
- ✅ 数据库配置管理: 1个端点
- ✅ 系统设置管理: 3个端点
- ✅ 配置导入导出: 4个端点

**总计**: 32个API端点全部修复

## ✅ 验证结果

修复后，大模型厂家管理页面应该能够：
1. 正确加载厂家列表
2. 显示厂家状态和API密钥状态
3. 支持添加、编辑、删除厂家
4. 支持测试厂家API连接

## 🔄 预防措施

### 开发规范
1. **API路径一致性检查**: 确保前后端API路径定义一致
2. **自动化测试**: 添加API路径正确性测试
3. **文档同步**: API变更时同步更新前端调用

### 代码审查要点
- 检查新增API的路径前缀
- 验证前端API调用路径的正确性
- 确保路由变更时前后端同步更新

## 📝 相关文件

### 修改的文件
- `frontend/src/api/config.ts` - 修复所有配置API路径

### 相关文件
- `app/routers/config.py` - 后端配置API路由定义
- `app/main.py` - API路由注册
- `frontend/src/views/Settings/ConfigManagement.vue` - 配置管理页面

---

**修复完成时间**: 2025-01-09  
**影响范围**: 配置管理相关功能  
**修复状态**: ✅ 已完成
