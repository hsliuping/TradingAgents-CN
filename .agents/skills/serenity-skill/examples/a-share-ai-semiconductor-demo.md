# Demo: A-Share AI Semiconductor Scan

This is a dated example output shape for a tool-using run. Current facts, valuation, and ranking should be refreshed with live sources before use.

## Prompt

```text
用 serenity-skill 深度调研现在 A 股 AI 半导体产业链，找 5 个最值得优先研究的标的。
```

## Example answer shape

先看带宽和工艺约束，再看纯算力芯片。AI 需求继续扩张时，先紧起来的往往是内存互连、CMP/减薄、刻蚀和耗材这些决定供给能不能爬坡的环节。

先排产业链层级，再排公司。我会把优先级放在：内存互连芯片、CMP/减薄、关键刻蚀设备、CMP/电镀耗材、先进封测。纯 AI 芯片和光模块业绩弹性强，但估值和拥挤度更高，适合作为景气度温度计。

| 标的 | 卡住的环节 | 为什么排这里 | 关键证据 | 主要风险 |
|---|---|---|---|---|
| 澜起科技 | AI 服务器 DDR5、MRDIMM、PCIe/CXL 互连 | 带宽升级绕不开，报表能看到互连产品变化 | 季报、年报、IR 中的产品线收入和毛利率 | 新子代迭代放缓，互连收入占比停滞 |
| 华海清科 | CMP、减薄、边抛、划切 | 贴近 HBM、先进封装、3D IC 的工艺瓶颈 | 年报中的 CMP 出机、客户验证、减薄设备进展 | 客户重复订单放缓，扩产摊薄收益 |
| 中微公司 | 高深宽比刻蚀、先进逻辑/存储关键刻蚀 | 先进制程和高端存储扩产落到设备验证 | 反应台量产、客户产线、刻蚀收入增长 | 验证周期延长，研发投入转订单速度变慢 |
| 安集科技 | CMP 抛光液、湿电子化学品、电镀添加剂 | 耗材是复购型卡点，先进制程步骤增加会抬升需求 | 年报中的 CMP、湿电子、电镀产品进展 | 客户二供压价，新品认证转量产慢 |
| 通富微电 | AI/HPC 封测和先进封装产能 | Chiplet、Bumping、FCBGA、3nm 相关验证带来弹性 | 年报、募集说明书、问询回复中的客户和扩产信息 | 客户集中、再融资摊薄、毛利率兑现慢 |

我的跟踪顺序会很明确：先看澜起互连产品收入占比和毛利率，再看华海清科 HBM/CMP 重复订单，其次看中微高深宽比刻蚀的客户扩展，最后用安集和通富验证先进封装扩张是否真的进入耗材和封测报表。

## Why this is a good Skill output

- It starts from physical and process constraints.
- It ranks layers before companies.
- It downgrades popular crowded areas with a reason.
- It explains what each company constrains.
- It uses normal research-partner language.
