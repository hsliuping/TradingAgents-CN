# 版权侵权处理指南
# Copyright Infringement Handling Guide

## 📋 版权信息摘要

### 专有组件（受版权保护）
- **目录**: `app/` (后端), `frontend/` (前端)
- **版权所有者**: hsliuping
- **限制**: 
  - ❌ 禁止商业使用（需授权）
  - ❌ 禁止重新分发
  - ❌ 禁止修改
  - ✅ 仅允许个人评估和教育用途

### 开源组件
- **目录**: `tradingagents/`, `cli/`, `scripts/`, `docs/`, `examples/`, `tests/`
- **许可证**: Apache License 2.0
- **允许**: 自由使用、商业使用、修改和分发

## 🚨 发现侵权时的处理步骤

### 第一步：收集证据

1. **网页截图**
   - 侵权网站首页
   - 声称版权/所有权的页面
   - 使用我们代码的功能页面
   - 网站关于我们/联系我们页面

2. **代码对比证据**
   - 对比侵权网站使用的代码与我们的代码
   - 记录相似度（文件名、函数名、注释等）
   - 截图或保存源代码片段

3. **Whois 信息**
   - 查询域名注册信息：https://whois.net/
   - 记录域名注册商、注册人、注册日期

4. **网站技术栈分析**
   - 使用浏览器开发者工具检查
   - 查看网络请求，确认使用的 API 端点
   - 检查前端代码结构

5. **时间线证据**
   - 我们的代码发布时间（GitHub 提交记录）
   - 侵权网站上线时间
   - 证明对方在我们之后使用

### 第二步：准备法律文件

#### 1. 版权声明函（DMCA Takedown Notice）

**发送对象**: 
- 网站托管服务商
- 域名注册商
- 网站所有者（如果可联系）

**内容应包括**:
```
主题：版权侵权通知 - TradingAgents-CN 专有代码

尊敬的 [服务商名称]：

我是 TradingAgents-CN 项目的版权所有者 hsliuping。

我发现以下网站未经授权使用了我们的专有代码：
- 网站：tradingagents-ai.com
- 侵权内容：app/ 和 frontend/ 目录下的专有代码

根据中华人民共和国著作权法，该网站的行为构成版权侵权。

我们的版权声明：
- 版权所有者：hsliuping
- 版权年份：2025
- 受保护组件：app/（后端）、frontend/（前端）
- 许可证文件：https://github.com/hsliuping/TradingAgents-CN/blob/main/COPYRIGHT.md

要求：
1. 立即停止使用我们的专有代码
2. 删除所有侵权内容
3. 公开道歉并澄清版权归属

证据：
[附上截图和代码对比证据]

联系方式：
- 邮箱：hsliup@163.com
- GitHub：https://github.com/hsliuping/TradingAgents-CN

请于 [日期] 前回复，否则我们将采取进一步法律行动。

此致
敬礼

hsliuping
```

#### 2. 律师函（如果对方不配合）

如果 DMCA 通知无效，可以委托律师发送正式律师函。

### 第三步：联系侵权方

**优先尝试友好沟通**:

```
主题：关于 tradingagents-ai.com 使用 TradingAgents-CN 代码的版权问题

您好，

我是 TradingAgents-CN 项目的版权所有者 hsliuping。

我注意到您的网站 tradingagents-ai.com 使用了我们的代码，但未获得商业使用授权。

根据我们的版权声明（https://github.com/hsliuping/TradingAgents-CN/blob/main/COPYRIGHT.md），
app/ 和 frontend/ 目录下的代码为专有代码，禁止商业使用。

请选择以下方案之一：
1. 立即停止使用并删除侵权代码
2. 联系我们获得商业使用授权（hsliup@163.com）
3. 仅使用开源组件（tradingagents/ 目录，Apache 2.0 许可证）

请在 7 天内回复，否则我们将采取法律行动。

谢谢理解。

hsliuping
```

### 第四步：向服务商举报

#### 1. 向托管服务商举报

如果网站托管在：
- **Cloudflare**: https://www.cloudflare.com/abuse/form/
- **AWS**: https://aws.amazon.com/report-abuse/
- **阿里云**: https://report.aliyun.com/
- **腾讯云**: https://cloud.tencent.com/act/event/report-abuse

#### 2. 向域名注册商举报

查询域名注册商后，向注册商举报。

#### 3. GitHub（如果对方在 GitHub 上）

如果对方在 GitHub 上托管代码：
- 提交 DMCA Takedown: https://github.com/contact/dmca

### 第五步：法律途径

如果以上步骤无效，可以考虑：

1. **咨询专业律师**
   - 知识产权律师
   - 准备诉讼材料

2. **向法院起诉**
   - 收集所有证据
   - 准备起诉书
   - 申请财产保全（如需要）

3. **向监管部门举报**
   - 国家版权局
   - 当地知识产权局

## 📞 联系信息

**版权所有者**: hsliuping  
**邮箱**: hsliup@163.com  
**GitHub**: https://github.com/hsliuping/TradingAgents-CN  
**QQ群**: 782124367

## 📚 相关法律依据

### 中华人民共和国著作权法

- **第四十七条**: 未经著作权人许可，复制、发行、表演、放映、广播、汇编、通过信息网络向公众传播其作品的，应当承担民事责任。
- **第四十八条**: 侵犯著作权或者与著作权有关的权利的，侵权人应当按照权利人的实际损失给予赔偿；实际损失难以计算的，可以按照侵权人的违法所得给予赔偿。

### 信息网络传播权保护条例

- **第十四条**: 对提供信息存储空间或者提供搜索、链接服务的网络服务提供者，权利人认为其服务所涉及的作品、表演、录音录像制品，侵犯自己的信息网络传播权或者被删除、改变了自己的权利管理电子信息的，可以向该网络服务提供者提交书面通知。

## ⚠️ 注意事项

1. **保持冷静**: 先尝试友好沟通，避免不必要的法律纠纷
2. **保留证据**: 所有沟通记录、截图、时间戳都要保存
3. **专业建议**: 重大侵权建议咨询专业律师
4. **成本考虑**: 法律诉讼成本较高，评估是否值得

## 🔗 有用链接

- [GitHub DMCA 政策](https://docs.github.com/en/github/site-policy/dmca-takedown-policy)
- [Cloudflare 滥用举报](https://www.cloudflare.com/abuse/form/)
- [国家版权局](http://www.ncac.gov.cn/)
- [中国知识产权局](https://www.cnipa.gov.cn/)

---

**最后更新**: 2026-02-04  
**版本**: v1.0
