/**
 * 系统更新 API
 */
import request from '@/api/request'

/** 构建信息 */
export interface BuildInfo {
  build_type?: string
  version?: string
  build_date?: string
  git_commit?: string
  full_version?: string
}

/** 版本信息 */
export interface VersionInfo {
  current_version: string
  build_info: BuildInfo
  /** Docker 环境 */
  is_docker?: boolean
  /** 是否支持应用内更新（Windows 便携版/安装版） */
  supports_in_app_update?: boolean
}

/** 更新信息 */
export interface UpdateInfo {
  has_update: boolean
  latest_version: string
  download_url: string
  file_size: number
  sha256: string
  release_notes: string
  release_date: string
  is_mandatory: boolean
  min_version: string
  /** 检查失败（如服务器连接不上） */
  check_failed?: boolean
  /** 错误提示信息 */
  error_message?: string
}

/** 下载进度 */
export interface DownloadProgress {
  status: string       // idle | downloading | completed | failed | verify_failed
  version?: string
  total?: number
  downloaded?: number
  percent?: number
}

/** 获取当前版本信息 */
export function getVersionInfo() {
  return request<VersionInfo>({
    url: '/api/system/update/info',
    method: 'get'
  })
}

/** 检查更新 */
export function checkUpdate() {
  return request<UpdateInfo>({
    url: '/api/system/update/check',
    method: 'get'
  })
}

/** 获取下载进度 */
export function getDownloadProgress() {
  return request<DownloadProgress>({
    url: '/api/system/update/progress',
    method: 'get'
  })
}

/** 开始下载更新包 */
export function downloadUpdate() {
  return request({
    url: '/api/system/update/download',
    method: 'post'
  })
}

/** 应用更新（服务将重启） */
export function applyUpdate() {
  return request({
    url: '/api/system/update/apply',
    method: 'post'
  })
}

