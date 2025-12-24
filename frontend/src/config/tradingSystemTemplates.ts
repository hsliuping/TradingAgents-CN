/**
 * 交易系统模板配置
 */

export interface TradingSystemTemplate {
  id: string
  name: string
  description: string
  style: 'short_term' | 'medium_term' | 'long_term'
  risk_profile: 'conservative' | 'balanced' | 'aggressive'
  data: {
    stock_selection: any
    timing: any
    position: any
    holding: any
    risk_management: any
    review: any
    discipline: any
  }
}

export const tradingSystemTemplates: TradingSystemTemplate[] = [
  {
    id: 'short_term_trend',
    name: '短线趋势追踪系统',
    description: '基于技术面分析，捕捉短期趋势机会，适合有时间盯盘的投资者',
    style: 'short_term',
    risk_profile: 'aggressive',
    data: {
      stock_selection: {
        must_have: [
          { rule: '市值 > 50亿', description: '避免小盘股流动性风险' },
          { rule: '流通盘 > 10亿', description: '确保足够的流动性' },
          { rule: '近3日平均成交额 > 1亿', description: '活跃度要求' },
          { rule: '股价在20日均线之上', description: '趋势向上' },
          { rule: '近5日涨幅 > 5%', description: '有上涨动能' }
        ],
        exclude: [
          { rule: 'ST股票', description: '风险过高' },
          { rule: '次新股（上市不足1年）', description: '波动过大' },
          { rule: '连续跌停', description: '避免接飞刀' },
          { rule: '近期有重大利空消息', description: '基本面恶化' }
        ]
      },
      timing: {
        entry_signals: [
          { signal: '大盘处于上升趋势（沪深300指数MA20 > MA60）', description: '市场环境良好' },
          { signal: '股价突破前期高点', description: '技术突破' },
          { signal: 'MACD金叉', description: '动能转强' },
          { signal: '成交量较前5日平均放大50%以上', description: '资金关注' },
          { signal: '连续3日收阳', description: '趋势确认' }
        ]
      },
      position: {
        max_per_stock: 0.15,
        max_holdings: 8,
        min_holdings: 3
      },
      holding: {
        review_frequency: 'daily',
        add_conditions: [
          { condition: '股价高于成本价5%以上', description: '盈利加仓' },
          { condition: '上涨趋势未破坏', description: '趋势完好' }
        ],
        reduce_conditions: [
          { condition: '跌破5日均线', description: '短期趋势转弱' },
          { condition: '成交量萎缩', description: '动能衰竭' }
        ]
      },
      risk_management: {
        stop_loss: {
          type: 'percentage',
          percentage: 0.07,
          description: '固定7%止损'
        },
        take_profit: {
          type: 'trailing',
          description: '跌破5日均线止盈'
        }
      },
      review: {
        frequency: 'weekly',
        checklist: [
          '检查持仓表现',
          '分析买卖决策',
          '评估系统执行',
          '总结经验教训'
        ]
      },
      discipline: {
        must_do: [
          { rule: '严格执行止损，不得有任何借口', description: '保护本金' },
          { rule: '每次交易前必须检查所有选股条件', description: '确保符合系统' },
          { rule: '盈利后及时复盘总结', description: '持续改进' },
          { rule: '每日收盘后更新交易日志', description: '记录完整' }
        ],
        must_not: [
          { rule: '追涨杀跌，情绪化交易', description: '保持理性' },
          { rule: '重仓单只股票超过15%', description: '控制风险' },
          { rule: '一天内频繁交易同一只股票', description: '避免过度交易' },
          { rule: '不设止损就入场', description: '必须有保护' }
        ]
      }
    }
  },
  {
    id: 'medium_term_value',
    name: '中线价值成长系统',
    description: '结合基本面和技术面，寻找价值被低估的成长股，适合上班族',
    style: 'medium_term',
    risk_profile: 'balanced',
    data: {
      stock_selection: {
        must_have: [
          { rule: '市值 > 100亿', description: '中大盘股' },
          { rule: 'ROE > 15%（最近3年平均）', description: '盈利能力强' },
          { rule: '营收增长率 > 20%（最近3年平均）', description: '成长性好' },
          { rule: '市盈率 < 行业平均', description: '估值合理' },
          { rule: '负债率 < 60%', description: '财务健康' }
        ],
        exclude: [
          { rule: 'ST股票', description: '风险过高' },
          { rule: '业绩连续下滑', description: '基本面恶化' },
          { rule: '有重大诉讼或处罚', description: '法律风险' },
          { rule: '大股东减持', description: '信心不足' }
        ]
      },
      timing: {
        entry_signals: [
          { signal: '大盘处于震荡或上升趋势', description: '市场环境' },
          { signal: '股价回调至60日均线附近', description: '技术位置' },
          { signal: 'MACD即将金叉或刚刚金叉', description: '动能转强' },
          { signal: '出现重大利好消息（如业绩超预期）', description: '催化剂' },
          { signal: '机构资金流入', description: '资金认可' }
        ]
      },
      position: {
        max_per_stock: 0.20,
        max_holdings: 6,
        min_holdings: 3
      },
      holding: {
        review_frequency: 'weekly',
        add_conditions: [],
        reduce_conditions: []
      },
      risk_management: {
        stop_loss: {
          type: 'percentage',
          percentage: 0.12,
          description: '固定12%止损'
        },
        take_profit: {
          type: 'scaled',
          description: '涨30%卖1/3，涨50%卖1/3，剩余持有'
        }
      },
      review: {
        frequency: 'monthly',
        checklist: [
          '每季度财报发布后重新评估持仓',
          '检查行业和公司基本面变化',
          '评估估值水平',
          '总结投资决策'
        ]
      },
      discipline: {
        must_do: [
          { rule: '每季度财报发布后重新评估持仓', description: '跟踪基本面' },
          { rule: '严格执行止损和止盈计划', description: '纪律执行' },
          { rule: '定期复盘，每月至少一次', description: '持续改进' },
          { rule: '保持仓位分散，不超过3个行业', description: '分散风险' }
        ],
        must_not: [
          { rule: '因短期波动而频繁交易', description: '保持耐心' },
          { rule: '不做基本面研究就买入', description: '必须研究' },
          { rule: '重仓单只股票', description: '控制风险' },
          { rule: '追高买入', description: '等待合理价位' }
        ]
      }
    }
  },
  {
    id: 'long_term_value',
    name: '长线价值投资系统',
    description: '专注于优质蓝筹股，长期持有，分享企业成长，适合价值投资者',
    style: 'long_term',
    risk_profile: 'conservative',
    data: {
      stock_selection: {
        must_have: [
          { rule: '市值 > 500亿', description: '大盘蓝筹' },
          { rule: 'ROE > 15%（最近5年平均）', description: '持续盈利能力' },
          { rule: '连续5年盈利增长', description: '稳定成长' },
          { rule: '行业龙头地位', description: '竞争优势' },
          { rule: '分红率 > 2%', description: '股东回报' }
        ],
        exclude: [
          { rule: '周期性行业（除非在底部）', description: '避免周期波动' },
          { rule: '高负债企业（负债率 > 70%）', description: '财务风险' },
          { rule: '管理层频繁变动', description: '稳定性差' },
          { rule: '主营业务不清晰', description: '商业模式不明' }
        ]
      },
      timing: {
        entry_signals: [
          { signal: '股价处于历史估值低位（PE < 历史平均）', description: '估值合理' },
          { signal: '出现系统性风险导致的非理性下跌', description: '市场恐慌' },
          { signal: '重大利好（如政策支持、行业拐点）', description: '长期利好' },
          { signal: '大股东或管理层增持', description: '内部信心' }
        ]
      },
      position: {
        max_per_stock: 0.30,
        max_holdings: 5,
        min_holdings: 2
      },
      holding: {
        review_frequency: 'monthly',
        add_conditions: [
          { condition: '估值进一步下降', description: '加仓机会' },
          { condition: '基本面持续改善', description: '增强信心' }
        ],
        reduce_conditions: [
          { condition: '估值过高', description: '获利了结' },
          { condition: '基本面恶化', description: '及时止损' }
        ]
      },
      risk_management: {
        stop_loss: {
          type: 'technical',
          description: '跌破年线且基本面恶化时止损'
        },
        take_profit: {
          type: 'percentage',
          description: '估值过高或基本面恶化时卖出'
        }
      },
      review: {
        frequency: 'quarterly',
        checklist: [
          '深度研究持仓公司年报/季报',
          '关注公司重大公告',
          '评估行业发展趋势',
          '检查投资逻辑是否改变'
        ]
      },
      discipline: {
        must_do: [
          { rule: '每年至少深度研究一次持仓公司', description: '了解投资标的' },
          { rule: '关注公司重大公告和财报', description: '跟踪变化' },
          { rule: '保持耐心，不因短期波动而动摇', description: '长期思维' },
          { rule: '定期再平衡，维持合理仓位', description: '风险控制' }
        ],
        must_not: [
          { rule: '因短期涨跌而频繁交易', description: '长期持有' },
          { rule: '追逐热点和概念股', description: '坚持价值' },
          { rule: '使用杠杆', description: '稳健投资' },
          { rule: '不做研究就买入', description: '必须深入研究' }
        ]
      }
    }
  }
]

