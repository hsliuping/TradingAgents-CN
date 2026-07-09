# 迁移计划

## 📋 概述

本文档描述从 v1.x 到 v2.0 的迁移策略，确保平滑过渡。

---

## 🎯 迁移原则

1. **向后兼容** - 现有功能不受影响
2. **渐进式** - 分阶段迁移，降低风险
3. **可回滚** - 每个阶段都可以回滚
4. **并行运行** - 新旧系统可以并行运行

---

## 📊 迁移阶段

### 阶段 1: 基础设施准备

**目标**: 创建 `core/` 目录，建立基础框架

**任务**:
- [ ] 创建 `core/` 目录结构
- [ ] 添加专有许可证文件
- [ ] 创建基础模块骨架
- [ ] 配置 Python 包结构

**风险**: 低
**回滚**: 删除 `core/` 目录

---

### 阶段 2: 统一 LLM 客户端

**目标**: 实现 UnifiedLLMClient，与现有适配器并存

**任务**:
- [ ] 实现 UnifiedLLMClient 基础类
- [ ] 实现 OpenAI 兼容适配器
- [ ] 实现 Google 特殊处理
- [ ] 实现工具调用标准化
- [ ] 编写单元测试

**迁移策略**:
```python
# 阶段 2: 新旧并存
class MarketAnalyst:
    def __init__(self, llm=None, unified_client=None):
        if unified_client:
            self.llm = unified_client  # 新方式
        else:
            self.llm = llm  # 旧方式 (兼容)
```

**风险**: 中
**回滚**: 移除 UnifiedLLMClient 引用，恢复原有适配器

---

### 阶段 3: 智能体基类

**目标**: 实现 BaseAgent，逐步迁移现有智能体

**任务**:
- [ ] 实现 BaseAgent 基类
- [ ] 实现 AgentRegistry
- [ ] 迁移 MarketAnalyst (试点)
- [ ] 验证功能等价性
- [ ] 迁移其他分析师

**迁移策略**:
```python
# 阶段 3: 继承迁移
# 旧代码 (tradingagents/)
class MarketAnalyst:
    def create_market_analyst(self, llm, toolkit):
        # 500 行代码...

# 新代码 (core/)
class MarketAnalystV2(BaseAgent):
    @classmethod
    def get_metadata(cls):
        return AgentMetadata(
            id="market_analyst",
            name="市场分析师",
            ...
        )
    
    def _prepare_context(self, state):
        # 简化的实现
        pass
```

**风险**: 中
**回滚**: 恢复使用原有智能体类

---

### 阶段 4: 工作流引擎

**目标**: 实现动态工作流引擎

**任务**:
- [ ] 实现 WorkflowDefinition 模型
- [ ] 实现 WorkflowBuilder
- [ ] 实现 WorkflowEngine
- [ ] 创建默认工作流模板
- [ ] 实现工作流 API

**迁移策略**:
```python
# 阶段 4: 双轨运行
class GraphSetup:
    def setup_graph(self, workflow_id=None, selected_analysts=None):
        if workflow_id:
            # 新方式: 从数据库加载工作流定义
            return self.workflow_engine.build(workflow_id)
        else:
            # 旧方式: 硬编码图结构
            return self._legacy_setup(selected_analysts)
```

**风险**: 高
**回滚**: 禁用工作流引擎，恢复硬编码图

---

### 阶段 5: 前端工作流编辑器

**目标**: 实现可视化工作流编辑器

**任务**:
- [ ] 安装 Vue Flow 依赖
- [ ] 实现 FlowCanvas 组件
- [ ] 实现自定义节点
- [ ] 实现属性面板
- [ ] 实现工作流保存/加载
- [ ] 集成到主应用

**风险**: 中
**回滚**: 隐藏工作流编辑器入口

---

### 阶段 6: 授权系统

**目标**: 实现许可证管理和功能分级

**任务**:
- [ ] 实现 LicenseManager
- [ ] 实现功能开关
- [ ] 实现用量跟踪
- [ ] 集成到 API 层
- [ ] 实现许可证验证

**风险**: 中
**回滚**: 禁用授权检查，所有功能开放

---

## 📅 时间线

```
阶段 1: 基础设施准备     [第 1 周]
阶段 2: 统一 LLM 客户端  [第 2-3 周]
阶段 3: 智能体基类       [第 4-5 周]
阶段 4: 工作流引擎       [第 6-8 周]
阶段 5: 前端编辑器       [第 9-11 周]
阶段 6: 授权系统         [第 12 周]
─────────────────────────────────────
总计: 约 12 周 (3 个月)
```

---

## ⚠️ 风险管理

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| LLM 适配器兼容性问题 | 高 | 中 | 充分测试，保留旧适配器 |
| 工作流执行结果不一致 | 高 | 中 | A/B 测试，对比验证 |
| 前端性能问题 | 中 | 低 | 虚拟化大型工作流 |
| 授权绕过 | 高 | 低 | 服务端验证，代码混淆 |

---

## ✅ 验收标准

每个阶段完成后需满足：
1. 所有现有测试通过
2. 新功能测试覆盖率 > 80%
3. 性能不低于原有系统
4. 文档更新完成
5. 代码审查通过

