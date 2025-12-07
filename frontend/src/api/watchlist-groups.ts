/**
 * 自选股分组管理 API
 */

import request from './request'

export interface WatchlistGroup {
  id: string
  user_id: string
  name: string
  description: string
  color: string
  icon: string
  stock_codes: string[]
  analysis_depth?: number
  quick_analysis_model?: string
  deep_analysis_model?: string
  prompt_template_id?: string
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WatchlistGroupCreate {
  name: string
  description?: string
  color?: string
  icon?: string
  analysis_depth?: number
  quick_analysis_model?: string
  deep_analysis_model?: string
  prompt_template_id?: string
}

export interface WatchlistGroupUpdate {
  name?: string
  description?: string
  color?: string
  icon?: string
  analysis_depth?: number
  quick_analysis_model?: string
  deep_analysis_model?: string
  prompt_template_id?: string
  is_active?: boolean
}

/**
 * 获取所有分组
 */
export function getWatchlistGroups() {
  return request({
    url: '/api/watchlist-groups',
    method: 'get'
  })
}

/**
 * 创建分组
 */
export function createWatchlistGroup(data: WatchlistGroupCreate) {
  return request({
    url: '/api/watchlist-groups',
    method: 'post',
    data
  })
}

/**
 * 获取分组详情
 */
export function getWatchlistGroup(groupId: string) {
  return request({
    url: `/api/watchlist-groups/${groupId}`,
    method: 'get'
  })
}

/**
 * 更新分组
 */
export function updateWatchlistGroup(groupId: string, data: WatchlistGroupUpdate) {
  return request({
    url: `/api/watchlist-groups/${groupId}`,
    method: 'put',
    data
  })
}

/**
 * 删除分组
 */
export function deleteWatchlistGroup(groupId: string) {
  return request({
    url: `/api/watchlist-groups/${groupId}`,
    method: 'delete'
  })
}

/**
 * 添加股票到分组
 */
export function addStocksToGroup(groupId: string, stockCodes: string[]) {
  return request({
    url: `/api/watchlist-groups/${groupId}/stocks`,
    method: 'post',
    data: { stock_codes: stockCodes }
  })
}

/**
 * 从分组移除股票
 */
export function removeStocksFromGroup(groupId: string, stockCodes: string[]) {
  return request({
    url: `/api/watchlist-groups/${groupId}/stocks`,
    method: 'delete',
    data: { stock_codes: stockCodes }
  })
}

/**
 * 移动股票到其他分组
 */
export function moveStocksToGroup(sourceGroupId: string, targetGroupId: string, stockCodes: string[]) {
  return request({
    url: `/api/watchlist-groups/${sourceGroupId}/stocks/move`,
    method: 'post',
    data: {
      target_group_id: targetGroupId,
      stock_codes: stockCodes
    }
  })
}

