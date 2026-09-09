/**
 * 交易计划 API（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）生成：
 * 交易计划为 Pro 能力（trading_plan_check 门控），社区版接口返回空数据，
 * 引用组件（持仓复盘/操作历史弹窗的"关联交易计划"下拉）自然降级为空列表。
 */

/** 交易计划最小类型（仅声明社区版引用组件使用的字段；style 必填与 Pro 原版类型一致） */
export interface TradingSystem {
  id?: string
  name: string
  style: string
  is_active?: boolean
}

export interface TradingSystemsResponse {
  data: { systems: TradingSystem[] }
}

/** 获取交易计划列表（社区版：恒为空） */
export const getTradingSystems = async (): Promise<TradingSystemsResponse> => ({
  data: { systems: [] }
})
