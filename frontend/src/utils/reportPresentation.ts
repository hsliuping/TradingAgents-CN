export type ReportInfo = {
  name: string
  icon?: string
  description?: string
}

export const REPORT_INFO_MAP: Record<string, ReportInfo> = {
  // 🆕 宏观分析师团队 (2个)
  'index_report': {
    name: '📊 大盘分析师',
    description: '基于技术面、资金面、基本面多维度分析大盘指数',
  },
  'sector_report': {
    name: '🏭 板块分析师',
    description: '热点板块轮动分析与板块估值定位',
  },
  // 分析师团队 (4个)
  'market_report': {
    name: '📈 市场分析师',
    description: '基于K线、均线、成交量的纯技术分析',
  },
  'sentiment_report': {
    name: '💬 社交媒体分析师',
    description: '基于新闻、舆情、资金流向的情绪判断',
  },
  'news_report': {
    name: '📰 新闻分析师',
    description: '近期重大新闻与公告对标的的影响',
  },
  'fundamentals_report': {
    name: '💰 基本面分析师',
    description: '估值、财务、增长性基本面分析',
  },
  'chip_report': {
    name: '🧮 筹码分布分析师',
    description: '获利比例、筹码集中度与成本分布分析',
  },
  // 研究团队 (3个)
  'bull_researcher': {
    name: '🐂 积极证据研究员',
    description: '基于积极证据的研究观察',
  },
  'bear_researcher': {
    name: '🐻 谨慎证据研究员',
    description: '基于谨慎证据的研究观察',
  },
  'research_team_decision': {
    name: '🔬 研究整合员',
    description: '多情景研究的综合观察与关键数据支撑',
  },
  // v2.0 直出字段
  'bull_report': {
    name: '🐂 积极证据研究',
    description: '基于积极证据的研究观察',
  },
  'bear_report': {
    name: '🐻 谨慎证据研究',
    description: '基于谨慎证据的研究观察',
  },
  // 交易团队 (1个)
  'trader_investment_plan': {
    name: '🧩 研究整合员',
    description: '研究简报与研究观察汇总',
  },
  // 风险管理团队 (4个)
  'risky_analyst': {
    name: '⚡ 高弹性情景分析师',
    description: '高弹性视角的分析与研究观察',
  },
  'safe_analyst': {
    name: '🛡️ 防御情景分析师',
    description: '防御视角的风险评估与研究观察',
  },
  'neutral_analyst': {
    name: '⚖️ 基准情景分析师',
    description: '中性视角的客观分析',
  },
  'risk_management_decision': {
    name: '👔 风险评估师',
    description: '整体风险评估与治理意见',
  },
  // v2.0 风险观点与评估直出字段
  'risky_opinion': {
    name: '⚡ 高弹性情景分析观点',
    description: '高弹性情景视角的风险与机会',
  },
  'safe_opinion': {
    name: '🛡️ 防御情景分析观点',
    description: '防御情景视角的风险控制意见',
  },
  'neutral_opinion': {
    name: '⚖️ 基准情景分析观点',
    description: '中性视角的风险与机会',
  },
  'risk_assessment': {
    name: '⚠️ 风险审阅',
    description: '标的整体风险评定',
  },
  // 最终研究结论 (1个)
  'final_trade_decision': {
    name: '🧾 综合研究结论',
    description: '综合各团队的最终研究结论',
  },
  // 兼容旧字段
  'investment_plan': {
    name: '🧾 研究简报',
    description: '完整的研究观察汇总',
  },
  'investment_debate_state': {
    name: '🔬 研究团队分析（旧）',
    description: '研究团队多情景研究讨论',
  },
  'risk_debate_state': {
    name: '⚖️ 风险团队分析（旧）',
    description: '风险团队多情景研究讨论',
  },
  'detailed_analysis': {
    name: '📄 详细分析',
    description: '详细原始分析',
  },
}

export interface ManifestEntry {
  field: string
  display_name: string
  icon?: string
  description?: string
  category?: string
  order?: number
  is_primary?: boolean
  agent_id?: string
  has_content?: boolean
}

export function getReportName(key: string, manifestOrIsEtf?: ManifestEntry[] | boolean): string {
  const isEtf = typeof manifestOrIsEtf === 'boolean' ? manifestOrIsEtf : false
  const manifest = Array.isArray(manifestOrIsEtf) ? manifestOrIsEtf : undefined

  if (isEtf && key === 'fundamentals_report') {
    return '📊 ETF 分析'
  }
  // 1. 优先从 manifest 获取 display_name
  if (manifest) {
    const entry = manifest.find((m) => m.field === key)
    if (entry?.display_name) {
      const icon = entry.icon || ''
      return icon ? `${icon} ${entry.display_name}` : entry.display_name
    }
  }
  // 2. 回退到硬编码 REPORT_INFO_MAP
  const info = REPORT_INFO_MAP[key]
  if (info?.name) {
    return info.name
  }
  // 3. 最终兜底：纯文本格式化
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

export function getReportIcon(key: string, manifest?: ManifestEntry[]): string {
  // 1. 优先从 manifest 获取 icon
  if (manifest) {
    const entry = manifest.find((m) => m.field === key)
    if (entry?.icon) {
      return entry.icon
    }
  }
  // 2. 回退到硬编码 REPORT_INFO_MAP
  const info = REPORT_INFO_MAP[key]
  if (!info?.name) {
    return ''
  }
  const match = info.name.match(/^(\S+)\s*/)
  return match?.[1] || ''
}

export function getReportDescription(key: string, manifest?: ManifestEntry[]): string {
  // 1. 优先从 manifest 获取 description
  if (manifest) {
    const entry = manifest.find((m) => m.field === key)
    if (entry?.description) {
      return entry.description
    }
  }
  // 2. 回退到硬编码 REPORT_INFO_MAP
  return REPORT_INFO_MAP[key]?.description || ''
}
