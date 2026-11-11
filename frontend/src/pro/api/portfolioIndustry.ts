/**
 * 持仓行业周期 API（社区版空壳）
 *
 * 本文件由发布管道（scripts/publish_community.py）整文件替换：
 * 社区版无行业周期数据，接口返回空 industries，共享页面自动降级。
 */
export type CyclePosition = Record<string, any>

export interface PortfolioIndustryCycleResponse {
  industries: Record<string, CyclePosition>
  as_of?: string
  note?: string
}

export async function getPortfolioIndustryCycle(
  _params?: any,
): Promise<{ data: PortfolioIndustryCycleResponse }> {
  return { data: { industries: {} } }
}
