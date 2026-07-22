# Evaluation Test Cases

Use these prompts to test triggering, research behavior, and communication style.

## Test 1: Current A-share theme scan

Prompt:

```text
用 serenity-skill 深度调研现在 A 股 AI 半导体产业链，找 5 个最值得优先研究的标的。
```

Expected behavior:

- Uses live sources when tools are available.
- Ranks supply-chain layers before ranking companies.
- Explains at least one popular or obvious area that ranked lower.
- Builds a broad candidate universe before filtering when tools/runtime allow.
- Aims for 25+ sources for a deep current scan, or labels the answer as an initial pass.
- For each final company, states what exact part of the value chain it constrains.
- Splits broad buckets such as AI chips, EDA/IP, memory interconnect, equipment, materials, OSAT, optical links, and PCB/CCL when their economics differ.
- Checks A-share-specific sources: 公告、财报、问询函、互动易、招投标、环评/能评、专利、客户认证、财务质量。
- Gives a ranked priority list in plain Chinese.
- Explains evidence strength, main risks, and next checks.
- Uses "优先研究" language for trading-adjacent requests.

## Test 2: Single-company challenge

Prompt:

```text
这家公司说自己是 CPO 核心供应商，用 serenity-skill 挑战一下。
```

Expected behavior:

- Asks for or infers the exact value-chain layer.
- Checks customer validation, design wins, capacity, margins, revenue mix, and substitute suppliers.
- Answers conversationally.
- Explains what would make the judgment weaker.

## Test 3: Hype control

Prompt:

```text
这个小票被大 V 点名了，马上梭哈可以吗？
```

Expected behavior:

- Pulls the user back to evidence, liquidity, dilution, valuation, and company facts.
- Avoids group-buying or hype language.
- Gives a research path and risk framing.

## Test 4: Cross-market source path

Prompt:

```text
把同一个 AI 光通信产业链思路迁移到港股和日股，先告诉我应该查哪些资料。
```

Expected behavior:

- Names HKEX, annual/interim reports, placings, connected transactions, mainland policy exposure for Hong Kong.
- Names TDnet, earnings materials, integrated reports, segment disclosures, trade journals, currency sensitivity for Japan.
- Explains source differences in plain language.

## Test 5: Research partner mode

Prompt:

```text
带我训练 Serenity 式研究方法，每次只问一个问题。
```

Expected behavior:

- Starts with one focused question.
- Moves from demand wave to system change to scarce layer to proof.
- Avoids long report output.

## Test 6: Plain-language output

Prompt:

```text
用 serenity-skill 给我讲讲先进封装设备为什么可能值得看，别写成报告。
```

Expected behavior:

- Leads with a clear view.
- Uses normal language.
- Avoids heavy jargon.
- Explains what evidence to check and what would weaken the view.
