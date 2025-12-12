// 用户信息接口
export interface User {
  id: string
  username: string
  email: string
  avatar?: string
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  created_at: string
  updated_at: string
  last_login?: string
  
  // 用户偏好
  preferences: UserPreferences
  
  // 配额和限制
  daily_quota: number
  concurrent_limit: number
  
  // 统计信息
  total_analyses: number
  successful_analyses: number
  failed_analyses: number
}

// 用户偏好设置
export interface UserPreferences {
  // 分析偏好
  default_market: 'A股' | '美股' | '港股'
  default_depth: '1' | '2' | '3' | '4' | '5'  // 1-5级分析深度
  default_analysts?: string[]  // 默认分析师列表：市场分析师、基本面分析师、新闻分析师、社媒分析师
  auto_refresh?: boolean
  refresh_interval?: number

  // 外观设置
  ui_theme: 'light' | 'dark' | 'auto'
  sidebar_width?: number

  // 语言和地区
  language: 'zh-CN' | 'en-US'

  // 通知设置
  notifications_enabled: boolean
  email_notifications: boolean
  desktop_notifications?: boolean
  analysis_complete_notification?: boolean
  system_maintenance_notification?: boolean
}

// 登录表单
export interface LoginForm {
  username: string
  password: string
  remember_me?: boolean
  captcha?: string
}

// 注册表单
export interface RegisterForm {
  username: string
  email: string
  password: string
  confirm_password: string
  agreement: boolean
  captcha?: string
  invitation_code?: string
}

// 修改密码表单
export interface ChangePasswordForm {
  old_password: string
  new_password: string
  confirm_password: string
}

// 重置密码表单
export interface ResetPasswordForm {
  email: string
  captcha?: string
}

// 用户权限信息
export interface UserPermissions {
  permissions: string[]
  roles: string[]
}

// 登录响应
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

// Token刷新响应
export interface RefreshTokenResponse {
  access_token: string
  refresh_token?: string
  expires_in: number
}

// 用户会话信息
export interface UserSession {
  session_id: string
  user_id: string
  created_at: string
  expires_at: string
  last_activity: string
  ip_address?: string
  user_agent?: string
}

// 用户统计信息
export interface UserStats {
  total_analyses: number
  successful_analyses: number
  failed_analyses: number
  success_rate: number
  daily_quota: number
  daily_used: number
  concurrent_limit: number
  current_concurrent: number
}

// 用户活动日志
export interface UserActivity {
  id: string
  user_id: string
  action: string
  resource: string
  details?: Record<string, any>
  ip_address?: string
  user_agent?: string
  created_at: string
}

// 用户配置更新
export interface UserConfigUpdate {
  preferences?: Partial<UserPreferences>
  daily_quota?: number
  concurrent_limit?: number
}

// 验证码信息
export interface CaptchaInfo {
  captcha_id: string
  captcha_image: string
  expires_in: number
}

// 邀请码信息
export interface InvitationCode {
  code: string
  created_by: string
  used_by?: string
  used_at?: string
  expires_at: string
  is_used: boolean
  max_uses: number
  current_uses: number
}
