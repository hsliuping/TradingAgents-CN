# TradingAgents 设计文档目录

本目录包含 TradingAgents 项目的核心设计文档，涵盖系统架构、数据模型、API规范等重要设计内容。

## 📋 文档索引

### 🏗️ 系统架构设计

| 文档 | 描述 | 状态 |
|------|------|------|
| [stock_analysis_system_design.md](stock_analysis_system_design.md) | 股票分析系统整体架构设计 | ✅ 完成 |
| [api_specification.md](api_specification.md) | API接口规范和设计 | ✅ 完成 |
| [configuration_management.md](configuration_management.md) | 配置管理系统设计 | ✅ 完成 |
| [timezone-strategy.md](timezone-strategy.md) | 时区处理策略设计 | ✅ 完成 |

### 📊 数据模型设计

| 文档 | 描述 | 状态 |
|------|------|------|
| [stock_data_model_design.md](stock_data_model_design.md) | **股票数据模型设计方案** | ✅ 最新 |
| [stock_data_methods_analysis.md](stock_data_methods_analysis.md) | 股票数据获取方法整理分析 | ✅ 完成 |
| [stock_data_quick_reference.md](stock_data_quick_reference.md) | 股票数据方法快速参考手册 | ✅ 完成 |

### 🎤 提示词模版系统设计

| 文档 | 描述 | 状态 |
|------|------|------|
| [PROMPT_TEMPLATE_SYSTEM_SUMMARY.md](PROMPT_TEMPLATE_SYSTEM_SUMMARY.md) | 提示词模版系统完整设计总结 | ✅ 完成 |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 提示词模版系统快速参考指南 | ✅ 完成 |
| [prompt_template_system_design.md](prompt_template_system_design.md) | 系统设计概览和架构 | ✅ 完成 |
| [prompt_template_architecture_comparison.md](prompt_template_architecture_comparison.md) | 现有系统与新系统对比 | ✅ 完成 |
| [prompt_template_architecture_diagram.md](prompt_template_architecture_diagram.md) | 架构图和数据流 | ✅ 完成 |
| [prompt_template_implementation_guide.md](prompt_template_implementation_guide.md) | 分步实现指南 | ✅ 完成 |
| [prompt_template_technical_spec.md](prompt_template_technical_spec.md) | 详细技术规范 | ✅ 完成 |
| [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) | 实现任务检查清单 | ✅ 完成 |
| [prompt_template_usage_examples.md](prompt_template_usage_examples.md) | 10个使用场景示例 | ✅ 完成 |

### 📚 版本化设计

| 目录 | 描述 | 状态 |
|------|------|------|
| [v1.0.1/](v1.0.1/) | 提示词模版系统v1.0.1 - 支持所有13个Agent | ✅ 设计完成 |
| [v0.1.16/](v0.1.16/) | v0.1.16 版本的设计文档 | ✅ 完成 |

## 🎯 重点设计文档

### 0. 提示词模版系统设计 (v1.0.1 - 最新)

**文档**: [v1.0.1/README.md](v1.0.1/README.md)

**核心内容**:
- 🎯 **为所有13个Agent提供可配置的提示词模版系统**
- 📋 **模版管理**: 预设模版、用户自定义、版本控制
- 🌐 **Web集成**: API接口、前端编辑、模版预览
- 🔄 **灵活切换**: 支持A/B测试、热更新、快速切换

**关键特性**:
- ✅ 支持13个Agent (4分析师 + 2研究员 + 3辩手 + 2管理者 + 1交易员)
- ✅ 31个预设模版 (每个Agent 2-3个)
- ✅ 用户自定义模版
- ✅ 完整的版本管理和回滚
- ✅ Web API和前端集成
- ✅ 模版预览和渲染

**v1.0.1新增文档**:
- [版本更新总结](v1.0.1/VERSION_UPDATE_SUMMARY.md) - v1.0.1的主要变化
- [扩展Agent支持](v1.0.1/EXTENDED_AGENTS_SUPPORT.md) - 13个Agent体系
- [Agent模版规范](v1.0.1/AGENT_TEMPLATE_SPECIFICATIONS.md) - 每个Agent的规范
- [实现路线图](v1.0.1/IMPLEMENTATION_ROADMAP.md) - 8阶段实现计划

**v1.0原有文档**:
- [快速参考](QUICK_REFERENCE.md) - 快速查找常用信息
- [系统设计](prompt_template_system_design.md) - 详细设计
- [实现指南](prompt_template_implementation_guide.md) - 分步实现
- [使用示例](prompt_template_usage_examples.md) - 10个使用场景

### 1. 股票数据模型设计 (最新)

**文档**: [stock_data_model_design.md](stock_data_model_design.md)

**核心内容**:
- 📊 **8个核心数据表设计**: 基础信息、历史行情、实时数据、财务数据、新闻、技术指标等
- 🌍 **多市场支持**: CN(A股)/HK(港股)/US(美股) 统一架构
- 🚀 **技术指标扩展**: 分类扩展机制，支持无限扩展新指标
- 💾 **索引优化**: 针对查询性能优化的复合索引设计
- 🔧 **数据标准化**: 统一的数据格式和字段命名规范

**设计亮点**:
```javascript
// 市场区分设计
"market_info": {
  "market": "CN",               // 市场标识
  "exchange": "SZSE",           // 交易所
  "currency": "CNY",            // 货币
  "timezone": "Asia/Shanghai"   // 时区
}

// 技术指标分类扩展
"indicators": {
  "trend": {...},      // 趋势指标
  "oscillator": {...}, // 震荡指标  
  "channel": {...},    // 通道指标
  "volume": {...},     // 成交量指标
  "custom": {...}      // 自定义指标
}
```

### 2. 股票数据方法分析

**文档**: [stock_data_methods_analysis.md](stock_data_methods_analysis.md)

**核心内容**:
- 🏗️ **5层架构分析**: 用户接口层 → 统一接口层 → 优化提供器层 → 数据源适配器层 → 缓存层
- 📊 **数据类型分类**: 基础信息、历史数据、财务数据、实时数据、新闻情绪
- 🔄 **数据流向设计**: 缓存优先级和数据源降级策略
- ⚡ **性能优化**: API限制、缓存策略、批量处理建议

### 3. 快速参考手册

**文档**: [stock_data_quick_reference.md](stock_data_quick_reference.md)

**核心内容**:
- 🚀 **推荐接口**: 最佳实践和推荐使用的统一接口
- 📋 **按场景分类**: 基本面分析、量化交易、新闻分析、风险管理
- 🎯 **数据源选择**: 质量排序、成本对比、使用建议
- 🔧 **性能优化**: 缓存配置、批量处理、常见问题解决

## 🔄 设计演进

### 最新更新 (2025-01-15)

**提示词模版系统设计 v1.0** (新增):
- ✅ 完整的系统设计方案
- ✅ 9份详细设计文档
- ✅ 4个分析师的模版规划
- ✅ 分步实现指南和检查清单
- ✅ 10个使用场景示例

**股票数据模型设计 v2.0**:
- ✅ 新增多市场支持 (CN/HK/US)
- ✅ 技术指标分类扩展机制
- ✅ 索引优化和查询性能提升
- ✅ 数据标准化和版本管理

**架构优化**:
- 🔧 数据获取与使用服务解耦
- 📊 MongoDB标准化数据模型
- 🚀 支持动态扩展新数据源SDK

## 📞 使用指南

### 提示词模版系统 - 快速开始

```bash
# 1. 查看快速参考
cat docs/design/QUICK_REFERENCE.md

# 2. 查看完整总结
cat docs/design/PROMPT_TEMPLATE_SYSTEM_SUMMARY.md

# 3. 查看实现指南
cat docs/design/prompt_template_implementation_guide.md

# 4. 查看使用示例
cat docs/design/prompt_template_usage_examples.md
```

### 提示词模版系统 - 实现参考顺序
1. **快速了解** → `QUICK_REFERENCE.md`
2. **系统总结** → `PROMPT_TEMPLATE_SYSTEM_SUMMARY.md`
3. **系统设计** → `prompt_template_system_design.md`
4. **架构设计** → `prompt_template_architecture_diagram.md`
5. **实现指南** → `prompt_template_implementation_guide.md`
6. **技术规范** → `prompt_template_technical_spec.md`
7. **检查清单** → `IMPLEMENTATION_CHECKLIST.md`
8. **使用示例** → `prompt_template_usage_examples.md`

### 股票数据系统 - 查看设计文档
```bash
# 查看股票数据模型设计
cat docs/design/stock_data_model_design.md

# 查看数据方法分析
cat docs/design/stock_data_methods_analysis.md

# 查看快速参考
cat docs/design/stock_data_quick_reference.md
```

### 股票数据系统 - 实现参考顺序
1. **系统架构** → `stock_analysis_system_design.md`
2. **数据模型** → `stock_data_model_design.md`
3. **API设计** → `api_specification.md`
4. **数据获取** → `stock_data_methods_analysis.md`
5. **快速参考** → `stock_data_quick_reference.md`

## 🤝 贡献指南

### 更新设计文档
1. 在对应的设计文档中进行修改
2. 更新本 README.md 中的状态和描述
3. 如有重大变更，创建新的版本目录

### 新增设计文档
1. 在 `docs/design/` 目录下创建新文档
2. 在本 README.md 中添加索引条目
3. 遵循现有的文档格式和命名规范

---

*设计文档目录 - 最后更新: 2025-01-15*

## 📊 设计文档统计

| 类别 | 文档数 | 总行数 | 状态 |
|------|--------|--------|------|
| 提示词模版系统 v1.0 | 9 | ~1200 | ✅ 完成 |
| 提示词模版系统 v1.0.1 | 4 | ~800 | ✅ 完成 |
| 股票数据系统 | 3 | ~800 | ✅ 完成 |
| 系统架构 | 4 | ~600 | ✅ 完成 |
| **总计** | **20** | **~3400** | **✅ 完成** |

### v1.0.1新增文档
- VERSION_UPDATE_SUMMARY.md - 版本更新总结
- EXTENDED_AGENTS_SUPPORT.md - 13个Agent体系
- AGENT_TEMPLATE_SPECIFICATIONS.md - Agent模版规范
- IMPLEMENTATION_ROADMAP.md - 实现路线图
- README.md (v1.0.1) - v1.0.1文档索引
