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
    name: '🐂 乐观情景研究员',
    description: '看好标的的看多研究',
  },
  'bear_researcher': {
    name: '🐻 审慎情景研究员',
    description: '看空标的的看跌研究',
  },
  'research_team_decision': {
    name: '🔬 研究经理',
    description: '多空研究的综合判断与关键数据支撑',
  },
  // v2.0 直出字段
  'bull_report': {
    name: '🐂 乐观情景研究',
    description: '看好标的的理由与证据',
  },
  'bear_report': {
    name: '🐻 审慎情景研究',
    description: '看空标的的风险与隐忧',
  },
  // 交易团队 (1个)
  'trader_investment_plan': {
    name: '🧩 研究整合员',
    description: '具体的交易计划与仓位建议',
  },
  // 风险管理团队 (4个)
  'risky_analyst': {
    name: '⚡ 高弹性情景分析师',
    description: '激进视角的分析与建议',
  },
  'safe_analyst': {
    name: '🛡️ 防御情景分析师',
    description: '保守视角的风险评估与建议',
  },
  'neutral_analyst': {
    name: '⚖️ 基准情景分析师',
    description: '中性视角的客观分析',
  },
  'risk_management_decision': {
    name: '👔 风险经理',
    description: '整体风险评估与控制意见',
  },
  // v2.0 风险观点与评估直出字段
  'risky_opinion': {
    name: '⚡ 高弹性情景分析观点',
    description: '激进风格的风险与机会',
  },
  'safe_opinion': {
    name: '🛡️ 防御情景分析观点',
    description: '保守风格的风险控制意见',
  },
  'neutral_opinion': {
    name: '⚖️ 基准情景分析观点',
    description: '中性视角的风险与机会',
  },
  'risk_assessment': {
    name: '⚠️ 风险审阅',
    description: '标的整体风险评定',
  },
  // 最终决策 (1个)
  'final_trade_decision': {
    name: '🧾 综合研究结论',
    description: '综合各团队的最终分析结论',
  },
  // 兼容旧字段
  'investment_plan': {
    name: '🧾 研究简报',
    description: '完整的投资建议与计划',
  },
  'investment_debate_state': {
    name: '🔬 研究团队分析（旧）',
    description: '研究团队多空讨论',
  },
  'risk_debate_state': {
    name: '⚖️ 风险团队分析（旧）',
    description: '风险管理团队讨论',
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
