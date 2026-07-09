# 定时分析配置 - 测试执行功能

## 📋 功能概述

**测试执行** 功能允许用户立即执行定时分析配置，而不需要等待到指定的 CRON 时间。这对于验证配置是否正确、调试分析参数非常有用。

---

## 🎯 功能特性

### 1. 立即执行
- ✅ 无需等待 CRON 时间
- ✅ 立即触发分析任务
- ✅ 异步执行，不阻塞界面

### 2. 智能验证
- ✅ 自动检查是否有启用的时间段
- ✅ 自动检查时间段是否配置了分组
- ✅ 提示用户将要执行的时间段名称

### 3. 执行第一个启用的时间段
- ✅ 自动选择第一个启用的时间段
- ✅ 使用该时间段配置的分组和参数
- ✅ 执行完成后记录到执行历史

---

## 🚀 使用方法

### 第 1 步：创建并配置定时分析

1. 前往 **设置 → 定时分析配置**
2. 创建新配置或编辑现有配置
3. 添加至少一个时间段并配置分组

### 第 2 步：点击"测试执行"按钮

1. 在配置列表中找到要测试的配置
2. 点击该配置行的 **"测试执行"** 按钮（绿色按钮）
3. 系统会显示确认对话框，告知将要执行的时间段

### 第 3 步：确认执行

1. 确认对话框会显示：
   ```
   将立即执行时间段"开盘前"的分析任务，确定继续吗？
   ```
2. 点击"确定"开始执行
3. 系统显示成功消息：
   ```
   测试任务已启动，正在执行时间段: 开盘前
   ```

### 第 4 步：查看执行结果

**方法 1: 查看执行历史**
1. 点击配置行的"历史"按钮
2. 查看最新的执行记录
3. 查看成功/失败数量和任务 ID

**方法 2: 查看分析报告**
1. 前往"分析报告"页面
2. 查看刚刚生成的分析报告

**方法 3: 查看最后运行时间**
1. 配置列表中的"最后运行"列会更新
2. 显示刚刚执行的时间

---

## 📊 执行流程

```
1. 用户点击"测试执行"按钮
   ↓
2. 前端验证配置
   - 检查是否有启用的时间段
   - 检查时间段是否配置了分组
   ↓
3. 显示确认对话框
   ↓
4. 用户确认后，调用后端 API
   POST /api/scheduled-analysis/configs/{config_id}/test
   ↓
5. 后端查找第一个启用的时间段
   ↓
6. 异步执行 run_scheduled_analysis_slot()
   ↓
7. 立即返回响应（不等待执行完成）
   ↓
8. 后台执行分析任务
   - 获取分组中的股票
   - 批量创建分析任务
   - 并发执行分析
   - 记录执行历史
   ↓
9. 用户可以查看执行历史和分析报告
```

---

## 🔧 技术实现

### 后端 API

**端点**: `POST /api/scheduled-analysis/configs/{config_id}/test`

**实现**:
```python
@router.post("/configs/{config_id}/test")
async def test_config(config_id: str, user: dict = Depends(get_current_user)):
    """测试执行定时分析配置"""
    
    # 1. 获取配置
    config = await db.scheduled_analysis_configs.find_one(...)
    
    # 2. 查找第一个启用的时间段
    enabled_slot_index = None
    for idx, slot in enumerate(time_slots):
        if slot.get("enabled", True):
            enabled_slot_index = idx
            break
    
    # 3. 异步执行测试任务（不阻塞响应）
    asyncio.create_task(
        run_scheduled_analysis_slot(
            config_id=config_id,
            user_id=user_id,
            slot_index=enabled_slot_index
        )
    )
    
    # 4. 立即返回响应
    return ok({"message": f"测试任务已启动，正在执行时间段: {slot_name}"})
```

### 前端实现

**文件**: `frontend/src/views/Settings/ScheduledAnalysis.vue`

**关键代码**:
```typescript
// 测试执行配置
const testConfig = async (config: ScheduledAnalysisConfig) => {
  // 1. 验证配置
  const enabledSlots = config.time_slots?.filter(slot => slot.enabled) || []
  if (enabledSlots.length === 0) {
    ElMessage.warning('该配置没有启用的时间段，无法测试')
    return
  }
  
  // 2. 确认执行
  await ElMessageBox.confirm(
    `将立即执行时间段"${firstSlot.name}"的分析任务，确定继续吗？`,
    '测试执行'
  )
  
  // 3. 调用 API
  testingConfigId.value = config.id
  const res = await testScheduledAnalysisConfig(config.id)
  
  // 4. 显示结果
  if (res?.success) {
    ElMessage.success('测试任务已启动，请稍后查看执行历史')
    setTimeout(() => loadConfigs(), 3000)
  }
}
```

---

## ⚠️ 注意事项

### 1. 执行时间
- 测试执行是异步的，不会立即返回结果
- 分析任务在后台执行，可能需要几分钟到几十分钟
- 可以通过"执行历史"查看进度

### 2. 资源消耗
- 测试执行会消耗 LLM Token
- 如果分组中股票较多，可能需要较长时间
- 建议先用小分组测试

### 3. 并发限制
- 同一配置不能同时执行多次
- 如果上一次测试还在执行，建议等待完成后再测试

### 4. 执行顺序
- 只执行第一个启用的时间段
- 如果要测试其他时间段，可以临时禁用前面的时间段

---

## 🐛 故障排查

### 问题 1: 点击"测试执行"没有反应

**原因**:
- 配置没有启用的时间段
- 时间段没有配置分组

**解决**:
1. 检查配置中是否有启用的时间段
2. 检查时间段是否配置了分组
3. 查看浏览器控制台是否有错误

### 问题 2: 测试执行后没有生成报告

**原因**:
- 分组中的股票代码无效
- LLM 服务异常
- 网络问题

**解决**:
1. 查看执行历史中的失败原因
2. 检查后端日志
3. 验证 LLM 配置是否正确

### 问题 3: 测试执行一直显示"加载中"

**原因**:
- 后端服务异常
- 网络超时

**解决**:
1. 刷新页面
2. 检查后端服务是否正常
3. 查看浏览器网络请求

---

## 📚 相关文档

- 定时分析快速开始: `docs/features/SCHEDULED_ANALYSIS_QUICK_START.md`
- 定时分析详细指南: `docs/features/scheduled_analysis_guide.md`
- API 文档: `app/routers/scheduled_analysis.py`

---

**最后更新**: 2026-01-07  
**功能版本**: v1.0.1  
**新增功能**: 测试执行按钮

