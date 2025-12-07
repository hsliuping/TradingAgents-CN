/**
 * 邮件通知 API
 */
import request from './request'

export interface EmailSettings {
  enabled: boolean
  email_address: string
  single_analysis: boolean
  batch_analysis: boolean
  scheduled_analysis: boolean
  important_signals: boolean
  system_notifications: boolean
  quiet_hours_enabled: boolean
  quiet_hours_start: string
  quiet_hours_end: string
  format: string
  language: string
}

export interface EmailRecord {
  id: string
  user_id: string
  to_email: string
  subject: string
  template_name: string
  email_type: string
  status: string
  created_at: string
  sent_at: string | null
  error_message: string | null
}

export interface SMTPConfig {
  enabled: boolean
  host: string
  port: number
  username: string
  password?: string
  from_email: string
  from_name: string
  use_tls: boolean
  use_ssl: boolean
}

/**
 * 获取SMTP配置状态
 */
export function getSMTPConfig() {
  return request.get('/api/email/config')
}

/**
 * 更新SMTP配置
 */
export function updateSMTPConfig(config: SMTPConfig) {
  return request.put('/api/email/config', config)
}

/**
 * 测试SMTP连接
 */
export function testSMTPConnection(config: SMTPConfig) {
  return request.post('/api/email/config/test', config)
}

/**
 * 获取用户邮件设置
 */
export function getEmailSettings(userId: string) {
  return request.get(`/api/email/settings/${userId}`)
}

/**
 * 更新用户邮件设置
 */
export function updateEmailSettings(userId: string, settings: Partial<EmailSettings>) {
  return request.put(`/api/email/settings/${userId}`, settings)
}

/**
 * 发送测试邮件
 */
export function sendTestEmail(userId: string) {
  return request.post(`/api/email/test/${userId}`)
}

/**
 * 获取邮件发送历史
 */
export function getEmailHistory(userId: string, page: number = 1, pageSize: number = 20) {
  return request.get(`/api/email/history/${userId}`, {
    params: { page, page_size: pageSize }
  })
}

