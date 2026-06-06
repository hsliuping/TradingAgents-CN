export const meta = {
  name: 'tradingagents',
  description: 'TradingAgents 原生化:四分析师+多空辩论+风控终裁,只读预取JSON出结构化决策',
  phases: [
    { title: '分析师' },
    { title: '多空辩论' },
    { title: '决策' },
    { title: '风控' },
  ],
}

const D = args || {}
const meta_ = D.meta || {}
const tag = `${meta_.code || '?'} ${meta_.name || ''}`.trim()
const rounds = D.debate_rounds || 1

const ANALYST_SCHEMA = {
  type: 'object',
  required: ['dimension', 'stance', 'score', 'key_points', 'risks'],
  properties: {
    dimension: { type: 'string' },
    stance: { type: 'string', enum: ['看多', '看空', '中性'] },
    score: { type: 'number' },
    key_points: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'array', items: { type: 'string' } },
  },
}
const DEBATE_SCHEMA = {
  type: 'object',
  required: ['side', 'argument'],
  properties: {
    side: { type: 'string', enum: ['bull', 'bear'] },
    argument: { type: 'string' },
    rebuttal_to_prev: { type: 'string' },
  },
}
const FINAL_SCHEMA = {
  type: 'object',
  required: ['signal_lights', 'action', 'position_pct', 'one_liner', 'key_catalysts', 'key_risks'],
  properties: {
    signal_lights: {
      type: 'object', required: ['综合', '估值', '资金'],
      properties: {
        综合: { type: 'string', enum: ['🟢', '🟡', '🔴'] },
        估值: { type: 'string', enum: ['🟢', '🟡', '🔴'] },
        资金: { type: 'string', enum: ['🟢', '🟡', '🔴'] },
      },
    },
    action: { type: 'string', enum: ['BUY', 'HOLD', 'SELL'] },
    position_pct: { type: 'number' },
    target_price_range: { type: 'array', items: { type: 'number' } },
    key_catalysts: { type: 'array', items: { type: 'string' } },
    key_risks: { type: 'array', items: { type: 'string' } },
    one_liner: { type: 'string' },
  },
}

const J = (x) => JSON.stringify(x, null, 2)
const DISCLAIMER = '仅研究学习用途,不构成投资建议。数据可能滞后,结论为模型判断未经回测。'

// Phase 1 — 四分析师(barrier:辩论需全到齐)
phase('分析师')
const ANALYSTS = [
  { dim: '技术面', slice: { tech: D.tech }, ask: '从均线排列/MACD/RSI/BOLL/量价判断趋势与位置' },
  { dim: '基本面', slice: { funda: D.funda }, ask: '从 PE/PB 分位、ROE、利润趋势判断估值是否合理' },
  { dim: '新闻面', slice: { news: D.news }, ask: '从研报评级共识与题材催化判断预期' },
  { dim: '资金情绪面', slice: { senti: D.senti }, ask: '从主力/资金流、龙虎榜、融资、筹码集中度判断资金态度' },
]
const analyses = await parallel(ANALYSTS.map((a) => () =>
  agent(
    `你是${a.dim}分析师,分析 ${tag}。${a.ask}。${DISCLAIMER}\n` +
    `只依据以下数据(缺失项不臆造):\n${J(a.slice)}`,
    { label: `分析:${a.dim}`, phase: '分析师', schema: ANALYST_SCHEMA },
  ).then((r) => (r ? { ...r, dimension: r.dimension || a.dim } : null))
))
const analysesOk = analyses.filter(Boolean)

// Phase 2 — 多空辩论(loop,上一轮发言喂下一轮)
phase('多空辩论')
const transcript = []
for (let r = 1; r <= rounds; r++) {
  const prev = transcript.length ? `\n对方上一轮观点:\n${J(transcript[transcript.length - 1])}` : ''
  const bull = await agent(
    `你是看多研究员,为 ${tag} 构建多头论点。基于四分析师结论:\n${J(analysesOk)}${prev}\n` +
    `给出最强多头理由并反驳空头。${DISCLAIMER}`,
    { label: `辩论:多R${r}`, phase: '多空辩论', schema: DEBATE_SCHEMA },
  )
  const bear = await agent(
    `你是看空研究员,为 ${tag} 构建空头论点。基于四分析师结论:\n${J(analysesOk)}\n` +
    `多头本轮观点:\n${J(bull)}\n给出最强空头理由并反驳多头。${DISCLAIMER}`,
    { label: `辩论:空R${r}`, phase: '多空辩论', schema: DEBATE_SCHEMA },
  )
  transcript.push({ round: r, bull, bear })
}

// Phase 3 — 研究经理综合 → 交易员决策
phase('决策')
const manager = await agent(
  `你是研究经理,综合四分析师与多空辩论,给出中立结论。\n分析:${J(analysesOk)}\n辩论:${J(transcript)}\n` +
  `输出:倾向(看多/看空/中性)、多空强度、核心论点。${DISCLAIMER}`,
  { label: '研究经理', phase: '决策' },
)
const trader = await agent(
  `你是交易员,基于研究经理结论为 ${tag} 出交易决策。\n${manager}\n` +
  `给出 BUY/HOLD/SELL、信心、建议仓位%、进场逻辑、止损逻辑。${DISCLAIMER}`,
  { label: '交易员', phase: '决策' },
)

// Phase 4 — 风控三方(parallel)→ 终裁
phase('风控')
const RISK = ['激进', '保守', '中性']
const riskViews = await parallel(RISK.map((p) => () =>
  agent(
    `你是${p}风控,审视交易员对 ${tag} 的决策:\n${trader}\n` +
    `从${p}视角给出支持/反对/有条件 及调整建议。${DISCLAIMER}`,
    { label: `风控:${p}`, phase: '风控' },
  )
))
const final = await agent(
  `你是风控经理,做最终裁决。\n交易员决策:\n${trader}\n风控三方:\n${J(riskViews.filter(Boolean))}\n` +
  `估值面参考:${J(D.funda)}\n资金面参考:${J(D.senti)}\n` +
  `给出信号灯(综合/估值/资金 各 🟢🟡🔴)、action、仓位%、目标价区间、关键催化与风险、一句话结论。${DISCLAIMER}`,
  { label: '风控终裁', phase: '风控', schema: FINAL_SCHEMA },
)

return {
  meta: meta_,
  analyses: analysesOk,
  debate: transcript,
  trader,
  risk_views: riskViews.filter(Boolean),
  final,
}
