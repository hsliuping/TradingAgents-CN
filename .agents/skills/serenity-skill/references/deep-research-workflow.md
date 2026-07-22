# Deep Research Workflow

Use this file when the user asks for current opportunities, ranked candidates, "which is worth researching now", or a full theme scan.

## Goal

Turn a broad investment theme into a ranked set of research priorities backed by current sources.

The final answer should read like a clear research conversation. The internal workflow can be rigorous; the external answer should stay plain and useful.

## Minimum completion standard

For a current theme scan, aim to complete these checks before the final answer:

- cover at least three value-chain layers;
- rank the scarce layers before ranking companies;
- inspect at least 25 sources when tools and runtime allow;
- build a starting candidate universe of at least 20 companies when the market is broad enough;
- build a candidate universe across visible winners, upstream suppliers, equipment, materials, testing, infrastructure, and adjacent beneficiaries;
- identify the strongest scarce layers;
- select the top 3-7 priorities;
- explain what each final candidate constrains or sits closest to;
- support each top candidate with concrete evidence;
- state what could make the judgment wrong;
- name at least one obvious or popular area that ranked lower and explain why;
- give the next checks the user should run.

If tools or time prevent that standard, state the limitation and give a focused partial answer with an exact verification path.

## Workflow

### 1. Scope the request

Infer the missing parts when reasonable:

- market: US, Hong Kong, A-share, Taiwan, Japan, Korea, Europe, global;
- theme: AI infrastructure, semiconductors, CPO, advanced packaging, robotics, power, cooling, materials, equipment, healthcare manufacturing, defense electronics;
- time window: for "now" use 3-12 months as the default research window;
- output: priority research candidates, reasoning, and next checks.

Ask a clarification only when the missing scope would materially change the answer.

### 2. Convert the theme into a system change

Write the practical chain:

`demand wave -> system pressure -> required technical change -> constrained layer`

Examples:

- AI clusters -> bandwidth and power pressure -> optical interconnect and switching upgrades -> lasers, DSP/ASICs, testing, packaging, substrates.
- AI servers -> power density and uptime pressure -> power conversion, transformers, switchgear, liquid cooling -> qualified equipment and components.
- Humanoid robotics -> actuator and sensing density -> precision reducers, motors, encoders, tactile sensing, batteries -> manufacturing yield and supplier qualification.

### 3. Build the value-chain map

Use these layers as a checklist:

1. End customers and capex source.
2. System integrators and OEMs.
3. Modules and subsystems.
4. Chips, devices, and critical components.
5. Process, assembly, packaging, and testing.
6. Equipment and metrology.
7. Materials, consumables, and specialty inputs.
8. Physical infrastructure.

### 4. Search for scarce layers

A scarce layer becomes interesting when several signals stack:

- customers cannot scale without it;
- supplier count is low;
- qualification is slow;
- expansion requires specialized equipment, permits, know-how, or material purity;
- customers show urgency through prepayments, capacity reservations, long-term contracts, expedited orders, or price acceptance;
- the public market still classifies the company by an older business category.

After this step, write the layer ranking before moving to the final company list.

Example:

```text
I would rank the layers first: equipment platforms, process-specific equipment, compute chips, advanced packaging materials, then broad component suppliers.
Equipment platforms and process-specific tools sit closer to fab expansion and technology migration. Broad component suppliers usually need stronger order and margin evidence to rank higher.
```

Chinese:

```text
先排产业链层级：设备平台、关键工艺设备、国产算力芯片、先进封装材料、普通零部件。
前两层更接近晶圆厂扩产和工艺升级的硬约束，后面几层需要更强的订单和财务证据才能往前排。
```

### 5. Build the company universe

Include names across the chain before ranking. Avoid starting from popular tickers.

For broad market scans, start with at least 20 candidates when the market has enough listed companies. Cover:

- obvious leaders;
- compute chips and AI accelerators;
- EDA, IP, verification, and design infrastructure;
- memory, storage, and interconnect chips;
- upstream equipment;
- process-specific tools;
- materials and consumables;
- testing and metrology;
- advanced packaging and OSAT;
- PCB, CCL, optical links, and server infrastructure when the theme reaches AI servers;
- infrastructure and power;
- lower-priority or popular names that need explicit downgrading.

Keep categories clean. Split a broad bucket when companies have different economics, evidence paths, or bottleneck logic. For A-share AI semiconductors, avoid merging compute chips, EDA/IP, memory interconnect, equipment, materials, OSAT, optical links, and PCB/CCL into one candidate layer.

Classify each candidate in plain language:

- controls the scarce layer;
- supplies the scarce layer;
- benefits from demand but has limited control;
- has exposure with weak pricing power;
- has a good story with weak proof.

### 6. Gather current evidence

Prioritize:

- filings and exchange disclosures;
- company announcements and investor relations materials;
- earnings transcripts and presentations;
- official customer/order/project/regulatory documents;
- patents, standards, technical papers, and trade publications;
- reputable financial and industry media;
- specialist analysis as context;
- social posts as leads.

Use `references/evidence-ladder.md` for grading.

For deep current scans, aim for 25+ sources before the final ranking. A good mix:

- 10+ filings, exchange disclosures, annual reports, quarterly reports, or announcements;
- 5+ company IR/transcript/product/technical sources;
- 5+ credible media, trade publications, industry association, patents, standards, or project records;
- extra sources for cross-checking valuation, liquidity, financing, and customer evidence.

### 7. Rank candidates

Rank by:

- demand pressure;
- tightness of the scarce layer;
- supplier concentration;
- expansion difficulty;
- evidence strength;
- valuation gap or market misunderstanding;
- near-term events that could change investor perception;
- financing, governance, liquidity, accounting, and geopolitical risk.

Use `scripts/serenity_scorecard.py` when a repeatable numeric score helps.

Keep two rankings distinct:

1. **Layer ranking**: which parts of the system deserve attention first.
2. **Company ranking**: which companies best represent those layers with evidence.

This keeps the answer from becoming a generic list of popular stocks.

For each final company, answer:

- What exactly does it constrain?
- Where does it sit in the chain?
- Why does it rank here?
- What evidence supports that rank?
- What would make the rank weaker?

### 8. Explain the answer

The answer should start with the conclusion:

- the layers worth prioritizing;
- the top names to research first;
- the reason those names rank higher;
- the strongest proof;
- the popular areas that ranked lower;
- the main ways the view can be wrong;
- the next checks.

Prefer normal prose. Add a compact table only for rankings or evidence comparison.

## A-share deep scan pattern

For A-share prompts, verify through:

- 年报、半年报、季报、临时公告；
- 交易所问询函、互动易、上证 e 互动；
- 招投标、中标公告、客户认证；
- 环评/能评、地方项目备案、产能建设记录；
- 专利、标准、行业协会资料；
- 应收、存货、合同负债、现金流、毛利率；
- 关联交易、资产注入、定增、可转债、股权质押。

The final answer should avoid sounding like a broker report. Use direct investment language:

`先看带宽和工艺约束，再看纯算力芯片...`

`先排产业链层级，再排公司。我会优先看这几层...`

`我会优先看这几层...`

`这个公司排前面，是因为它更靠近真实扩产约束...`

`这个热门方向我会先降级，因为...`

`这个判断最容易错在...`

`下一步先查...`
