# 贡献指南

感谢您对TradingAgents-CN项目的关注！我们欢迎各种形式的贡献。

## 🤝 如何贡献

### 1. 报告问题
- 使用GitHub Issues报告Bug
- 提供详细的问题描述和复现步骤
- 包含系统环境信息

### 2. 功能建议
- 在GitHub Issues中提出功能请求
- 详细描述功能需求和使用场景
- 讨论实现方案

### 3. 代码贡献
1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

### 4. 文档贡献
- 改进现有文档
- 添加使用示例
- 翻译文档
- 修正错误

## 📋 开发规范

### 代码风格
- 遵循PEP 8 Python代码规范
- 使用有意义的变量和函数名
- 添加适当的注释和文档字符串
- 保持代码简洁和可读性

### 提交规范
- 使用清晰的提交信息
- 一个提交只做一件事
- 提交信息使用中文或英文

### 测试要求
- 为新功能添加测试用例
- 确保所有测试通过
- 保持测试覆盖率

## 🔧 开发环境设置

### 1. 克隆仓库
```bash
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN
```

### 2. 创建虚拟环境
```bash
python -m venv env
source env/bin/activate  # Linux/macOS
# 或
env\Scripts\activate  # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，添加必要的API密钥
```

### 5. 运行测试
```bash
python -m pytest tests/
```

## 📝 Pull Request指南

### 提交前检查
- [ ] 代码遵循项目规范
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] 所有测试通过
- [ ] 没有引入新的警告

### PR描述模板
```markdown
## 更改类型
- [ ] Bug修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 性能优化
- [ ] 其他

## 更改描述
简要描述此PR的更改内容

## 测试
描述如何测试这些更改

## 相关Issue
关联的Issue编号（如果有）
```

## 🎯 贡献重点

### 优先级高的贡献
1. **Bug修复**: 修复现有功能问题
2. **文档改进**: 完善使用文档和示例
3. **测试增强**: 增加测试覆盖率
4. **性能优化**: 提升系统性能

### 欢迎的贡献
1. **新数据源**: 集成更多金融数据源
2. **新LLM支持**: 支持更多大语言模型
3. **界面优化**: 改进Web界面用户体验
4. **国际化**: 支持更多语言

## 📞 联系我们

- **GitHub Issues**: 问题报告和讨论
- **GitHub Discussions**: 社区交流
- **项目文档**: 详细的开发指南

## 📄 许可证

通过贡献代码，您同意您的贡献将在Apache 2.0许可证下发布。

---

感谢您的贡献！🎉
