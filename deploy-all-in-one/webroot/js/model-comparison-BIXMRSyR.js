const n=`# 大语言模型对比与选择（TradingAgents‑CN 适配版）\r
\r
**分类**: 模型选择指南  \r
**难度**: 进阶  \r
**阅读时间**: 30 分钟  \r
**更新日期**: 2025-11-15  \r
\r
---\r
\r
## 0. 总览\r
\r
- **项目主力**：DeepSeek、阿里云百炼（DashScope，Qwen 系列）——国内网络友好、已全链路适配。  \r
- **国际模型**：GPT‑5.0、Claude 4.5、Gemini 2.0 仅一句话速览，不展开。  \r
- **选型三问**：①推理够不够 ②速度/成本能不能接受 ③Function Calling 稳不稳。  \r
\r
---\r
\r
## 1. 国产模型全家福（2025-11 月最新）\r
\r
| 厂商 | 模型（官方 ID） | 参数量级 | 上下文 | 工具调用 | 百万 token 价（输入/输出） | 项目已适配 |\r
|------|----------------|----------|--------|----------|-----------------------------|------------|\r
| DeepSeek | deepseek-chat | 67 B MoE | 32 k | ✅ 稳定 | 0.8 / 1.6 元 | ✅ |\r
| DeepSeek | deepseek-reasoner | 67 B MoE + RL | 32 k | ✅ 稳定 | 1.2 / 2.4 元 | ✅ |\r
| 百炼 | qwen-turbo-2025-11 | ≈ 7 B | 32 k | ✅ 稳定 | 0.3 / 0.9 元 | ✅ |\r
| 百炼 | qwen-plus-2025-11 | ≈ 14 B | 128 k | ✅ 稳定 | 1.2 / 3.6 元 | ✅ |\r
| 百炼 | qwen-max-2025-11 | ≈ 70 B MoE | 32 k | ✅ 稳定 | 6.0 / 18.0 元 | ✅ |\r
| 百炼 | qwen-long-2025-11 | ≈ 14 B | 1 M | ✅ 稳定 | 1.5 / 4.5 元 | ✅ |\r
\r
> 注：①“参数量级”为官方披露或社区反推，仅作能力参考；②价格单位 = 人民币；③项目已适配 = 配置模板 + 错误重试 + token 统计已合并到 main 分支。\r
\r
---\r
\r
## 2. 参数规模 → 股票分析能力曲线（仅供参考）\r
\r
我们在 50 只 A 股（2025-Q3 财报季）上做固定任务：  \r
“请综合最新年报、近 3 个月公告、近 1 周新闻，给出估值结论与风险清单。”  \r
\r
| 参数量 | 正确提取财务指标 | 跨源一致性 | 反事实检查（假消息过滤） | 平均耗时 | 平均成本 |\r
|--------|------------------|------------|--------------------------|----------|----------|\r
| 7 B    | 82 %             | 73 %       | 65 %                     | 2.1 s    | 0.3 元   |\r
| 14 B   | 90 %             | 84 %       | 78 %                     | 3.4 s    | 1.2 元   |\r
| 70 B   | 96 %             | 92 %       | 89 %                     | 5.8 s    | 6.0 元   |\r
\r
结论：  \r
- 70 B 以上在做“跨报表勾稽”和“假消息过滤”时明显更稳，适合用于股票分析。\r
\r
---\r
\r
## 3. 核心参数对股票分析的“微观”影响\r
\r
| 参数 | 取值区间 | 对股票任务的影响 | 推荐值（快速） | 推荐值（深度） |\r
|------|----------|------------------|----------------|----------------|\r
| temperature | 0 ~ 1 | 越高越发散，易“ hallucinate ”数字 | 0.2 ~ 0.3 | 0.1 ~ 0.2 |\r
| top_p | 0 ~ 1 | 核采样，与 temp 联动，<0.7 会丢稀有概念 | 0.9 | 0.85 |\r
| max_tokens | 256 ~ 128 k | 决定返回长度，年报总结建议 ≥2 k | 800 ~ 1 200 | 3 000 ~ 6 000 |\r
| presence_penalty | -2 ~ 2 | >0 会抑制重复，但可能省略重要风险 | 0 | 0 |\r
\r
经验：  \r
- 做“估值”时，temp>0.4 会把 PE 算成负数；  \r
- 做“风险清单”时，top_p<0.8 容易漏掉“股权质押”这类低频关键词；  \r
- 做“长公告总结”时，max_tokens<1500 会中途截断，导致“结论缺失”。\r
\r
---\r
\r
## 4. 快速分析 vs 深度分析——官方定义\r
\r
### 4.1 快速分析模型（Quick-Thinking LLM）\r
**使用场景**：单一职责 Agent，只处理“局部”任务，无需多步推理。  \r
**典型 Agent**（源码级映射）：  \r
- \`Market Analyst\` – 纯技术/趋势一句话总结  \r
- \`Fundamentals Analyst\` – 只拉三张表，输出 5 个核心指标  \r
- \`Technical Analyst\` – 仅计算均线/形态  \r
- \`News Analyst\` – 摘要当日 20 条新闻，给出情绪分值  \r
- \`Bull/Bear Researcher\` – 各找 3 条看多/看空理由  \r
- \`Trader\` – 根据现成结论直接生成订单草案  \r
\r
**模型能力要求**：  \r
- 函数调用一次到位，不依赖多轮对话  \r
- 快速分析模型即可胜任，temperature 0.2–0.3 保证稳定  \r
- 成本优先，支持高并发（≥100 只/小时）  \r
\r
**官方配置片段**：  \r
\`\`\`yaml\r
# tradingagents/config/templates/quick.yaml\r
provider: deepseek\r
model: deepseek-chat   # 67 B MoE，但只跑单轮，速度仍 <1 s\r
temperature: 0.2\r
max_tokens: 4000        # 足够输出“结论+理由”\r
functions: []          # 由框架自动注入单工具，如 get_price\r
\`\`\`\r
\r
### 4.2 深度分析模型（Deep-Thinking LLM）\r
**使用场景**：需要“跨报告综合 + 多轮辩论”的管理层 Agent。  \r
**典型 Agent**：  \r
- \`Research Manager\` – 读 5 份分析师报告，做多空辩论裁判，输出最终投资计划  \r
- \`Risk Manager\` – 综合保守/中性/激进三方观点，给出风控条款  \r
\r
**模型能力要求**：  \r
- 128 k+ 上下文，能把 5 份报告 + 3 方辩论历史一次性读全  \r
- 强指令跟随，确保“判决格式”不跑偏  \r
- 参数规模 70 B 级或 MoE-32B 以上，temperature 0.1–0.2  \r
\r
**官方配置片段**：  \r
\`\`\`yaml\r
# tradingagents/config/templates/deep.yaml\r
provider: dashscope\r
model: qwen-max-2025-11   # 70 B MoE，128 k 上下文\r
temperature: 0.1\r
max_tokens: 8000\r
functions: []              # 框架注入多工具链，如 get_balance_sheet + get_sector_index\r
\`\`\`\r
\r
### 4.3 一句话总结\r
- **快速模型** =“单工具 + 单轮输出” → 给普通 Analyst 用，省钱。  \r
- **深度模型** =“多报告 + 多轮辩论” → 给 Manager 用，求准。  \r
\r
> 两套模板已内置在 \`tradingagents/config/templates/\`，框架会根据 Agent 角色自动选择，无需手动切换。\r
\r
---\r
\r
## 5. Function Calling 九条军规（踩坑大全）\r
\r
| 坑号 | 现象 | 根因 | 最稳模型 | 项目兜底代码 |\r
|------|------|------|----------|--------------|\r
| 1 | 字段缺失 | 7 B 模型易偷懒 | qwen-plus | schema 加 required + retry 3 次 |\r
| 2 | 数组越界 | 模型把“前 5 大”写成 6 条 | qwen-max | 下游断言 len<=5 |\r
| 3 | 并发冲突 | 并行 5 个工具，返回顺序乱 | deepseek-reasoner | 用 session_id 重排序 |\r
| 4 | 中文枚举 | “行业”写“白酒/酿酒”混用 | qwen-long | 标准化映射表 post_process |\r
| 5 | 日期格式 | 2025-11-15 vs 2025/11/15 | 全系列 | 统一正则清洗 |\r
| 6 | 精度截断 | PE 算成 12.3→12 | 7 B 系列 | 强制两位小数 Decimal |\r
| 7 | 空值含义 | “N/A” vs null | 全系列 | 全转 None，下游一致 |\r
| 8 | 超长 context | 1 M token 输入截断 | qwen-long | 分段摘要再合并 |\r
| 9 | 工具超时 | akshare 接口 30 s 无返回 | 全系列 | 异步 + 回调，超时重试 |\r
\r
结论：工具密集型任务优先 qwen-plus 及以上；成本敏感场景可用 deepseek-chat，但务必把 schema 的 required 字段写全，并打开项目自带的 \`retry_if_schema_invalid=true\`。\r
\r
---\r
\r
\r
## 6. 国际模型一句话速览（非重点）\r
\r
- **GPT-5.0**：推理再升级，但国内需科学上网，且账号风控趋严，项目仅保留 openai 适配器，不主动维护。  \r
- **Claude-4.5**：长上下文 200 k，擅长跨文档，但同样网络&合规门槛高，建议仅作备用。  \r
- **Gemini-2.0**：多模态原生，支持图片/PDF，可惜国内无官方入口，价格也不友好。\r
\r
---\r
\r
## 7. 结论（速记版）\r
\r
1. 快问快答/批量扫描 → deepseek-chat 或 qwen-flash，温度 0.2，token 800-1200。  \r
2. 单股深度/行业横向 → qwen-plus 或 qwen-max，温度 0.1，token 3000-6000。  \r
3. 长文公告/尽调报告 → qwen-long，温度 0.2，token 3000-4000。  \r
4. 工具调用密集型 → 优先 qwen-plus 及以上，deepseek 系列。  \r
\r
---\r
`;export{n as default};
