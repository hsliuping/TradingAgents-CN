# 分析师提示词模版系统 - 完整设计方案总结

## 🎯 项目概述

为TradingAgentsCN系统中的4个分析师智能体（基本面、市场、新闻、社媒）设计并实现一个完整的提示词模版管理系统，允许用户选择、编辑和自定义分析师的行为指导。

## 📊 核心设计要点

### 1. 系统架构
- **分离关注点**: 提示词与代码分离，便于管理和维护
- **模块化设计**: 每个分析师独立的模版目录
- **可扩展性**: 支持新增分析师和模版类型
- **版本控制**: 完整的模版版本管理和回滚机制

### 2. 关键特性
✅ **多模版支持**: 每个分析师支持多个预设模版
✅ **用户自定义**: 用户可创建和保存自定义模版
✅ **热更新**: 无需重启即可切换模版
✅ **A/B测试**: 支持不同模版的对比分析
✅ **Web编辑**: 前端界面支持模版编辑和预览
✅ **版本管理**: 完整的版本历史和回滚功能

### 3. 4个分析师的模版规划

| 分析师 | 模版1 | 模版2 | 模版3 |
|------|------|------|------|
| 基本面 | default | conservative | aggressive |
| 市场 | default | short_term | long_term |
| 新闻 | default | real_time | deep |
| 社媒 | default | sentiment_focus | trend_focus |

## 📁 文件结构

```
prompts/
├── templates/
│   ├── fundamentals/
│   │   ├── default.yaml
│   │   ├── conservative.yaml
│   │   └── aggressive.yaml
│   ├── market/
│   ├── news/
│   └── social/
├── schema/
│   └── prompt_template_schema.json
└── README.md

tradingagents/
├── config/
│   └── prompt_manager.py
└── agents/analysts/
    └── prompt_templates.py
```

## 🔧 核心模块

### PromptTemplateManager
- 加载和缓存模版
- 验证模版格式
- 渲染模版变量
- 管理模版版本

### 分析师集成
- 接收 `template_name` 参数
- 加载对应的模版
- 注入模版内容到提示词
- 执行分析

### Web API
- 模版列表查询
- 模版详情获取
- 模版创建/更新/删除
- 模版预览和渲染

## 📈 实现路线图

### Phase 1: 基础设施 (1-2周)
- [ ] 创建模版目录结构
- [ ] 实现PromptTemplateManager类
- [ ] 创建模版Schema和验证
- [ ] 编写单元测试

### Phase 2: 分析师集成 (1-2周)
- [ ] 提取现有硬编码提示词
- [ ] 创建预设模版文件
- [ ] 修改4个分析师代码
- [ ] 集成测试

### Phase 3: Web API (1周)
- [ ] 创建API路由
- [ ] 实现CRUD操作
- [ ] 添加模版预览功能
- [ ] API文档

### Phase 4: 前端集成 (1-2周)
- [ ] 模版选择UI
- [ ] 模版编辑器
- [ ] 模版预览
- [ ] 集成到分析流程

### Phase 5: 文档和优化 (1周)
- [ ] 完整文档
- [ ] 使用示例
- [ ] 性能优化
- [ ] 用户指南

## 💡 关键设计决策

1. **YAML格式**: 易于编辑、版本控制友好、支持注释
2. **文件存储**: 初期使用文件系统，后期可迁移到数据库
3. **缓存机制**: 提高性能，减少文件I/O
4. **变量注入**: 支持动态渲染，增加灵活性
5. **向后兼容**: 默认模版保持现有行为

## 🔌 集成点

### 分析师创建函数
```python
create_fundamentals_analyst(llm, toolkit, template_name="default")
```

### 分析API
```python
POST /api/analysis
{
  "ticker": "000001",
  "analyst_templates": {
    "fundamentals": "conservative",
    "market": "short_term"
  }
}
```

## 📚 文档清单

已生成的设计文档：
1. ✅ `prompt_template_system_design.md` - 系统设计概览
2. ✅ `prompt_template_implementation_guide.md` - 实现指南
3. ✅ `prompt_template_architecture_comparison.md` - 架构对比
4. ✅ `prompt_template_technical_spec.md` - 技术规范
5. ✅ `prompt_template_usage_examples.md` - 使用示例
6. ✅ `PROMPT_TEMPLATE_SYSTEM_SUMMARY.md` - 本文档

## 🎓 学习资源

### 模版示例
- 基本面分析师默认模版
- 市场分析师短期模版
- 新闻分析师实时模版
- 社媒分析师情绪模版

### API示例
- 列表查询
- 详情获取
- 创建/更新/删除
- 预览渲染

### 前端示例
- 模版选择组件
- 模版编辑器
- 模版预览
- 分析参数集成

## ✨ 预期收益

### 用户角度
- 🎯 灵活定制分析师行为
- 📊 对比不同分析风格
- 💾 保存个人偏好模版
- 🔄 快速切换分析策略

### 开发角度
- 🧹 代码更清晰（提示词与代码分离）
- 🔧 维护更容易（集中管理提示词）
- 🧪 测试更便利（模版独立测试）
- 📈 扩展更灵活（新增模版无需改代码）

### 业务角度
- 📈 提高用户满意度
- 🎯 支持个性化分析
- 🔬 便于A/B测试
- 💰 降低维护成本

## 🚀 下一步行动

1. **评审设计方案**: 确认架构和实现方向
2. **创建模版文件**: 提取现有提示词到YAML
3. **实现管理器**: 开发PromptTemplateManager类
4. **集成分析师**: 修改4个分析师代码
5. **开发API**: 创建Web接口
6. **前端集成**: 更新UI支持模版选择
7. **测试验证**: 单元测试和集成测试
8. **文档完善**: 用户指南和API文档

## 📞 相关文档

- 系统设计: `docs/design/prompt_template_system_design.md`
- 实现指南: `docs/design/prompt_template_implementation_guide.md`
- 架构对比: `docs/design/prompt_template_architecture_comparison.md`
- 技术规范: `docs/design/prompt_template_technical_spec.md`
- 使用示例: `docs/design/prompt_template_usage_examples.md`

---

**版本**: 1.0  
**日期**: 2024-01-15  
**状态**: 设计完成，待实现

