/**
 * 日期时间工具函数
 * 统一处理时间转换和显示
 *
 * 处理逻辑：
 * 1. 如果时间字符串包含时区信息（+08:00 或 Z），直接使用
 * 2. 🔥 如果时间字符串没有时区信息，假定为 UTC+8 时间（后端已经入库为 UTC+8）
 * 3. 最终统一显示为中国时区（Asia/Shanghai）
 *
 * 注意：后端要求所有入库数据都是 UTC+8 时间，但可能没有时区标志
 */

/**
 * 格式化时间字符串，自动处理时区转换
 * @param dateStr - 时间字符串或时间戳
 * @param options - 格式化选项
 * @returns 格式化后的时间字符串
 */
export function formatDateTime(
  dateStr: string | number | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!dateStr) return '-'

  try {
    let timeStr: string

    // 处理时间戳（秒或毫秒）
    if (typeof dateStr === 'number') {
      // 如果是秒级时间戳（小于 10000000000），转换为毫秒
      const timestamp = dateStr < 10000000000 ? dateStr * 1000 : dateStr
      timeStr = new Date(timestamp).toISOString()
    } else {
      timeStr = String(dateStr).trim()
    }

    // 检查时间字符串是否包含时区信息
    const hasTimezone = timeStr.endsWith('Z') ||
                       timeStr.includes('+') ||
                       timeStr.includes('-', 10) // 日期后面的 - 才是时区标识

    // 🔥 如果没有时区标识，假定为 UTC+8 时间（后端已经入库为 UTC+8），添加 +08:00 后缀
    // 注意：如果后端已经返回了带时区的时间（如 +08:00 或 Z），这里不会修改
    if (timeStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && !hasTimezone) {
      console.debug('[时间处理] 检测到不带时区的时间字符串，添加 +08:00:', timeStr)
      timeStr += '+08:00'
      console.debug('[时间处理] 转换后:', timeStr)
    } else {
      console.debug('[时间处理] 时间字符串已有时区或格式不匹配:', timeStr, 'hasTimezone:', hasTimezone)
    }

    // 解析时间字符串
    const date = new Date(timeStr)

    if (isNaN(date.getTime())) {
      console.warn('无效的时间格式:', dateStr)
      return String(dateStr)
    }

    // 默认格式化选项
    const defaultOptions: Intl.DateTimeFormatOptions = {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }

    // 合并用户提供的选项
    const finalOptions = { ...defaultOptions, ...options }

    // 格式化为中国本地时间（UTC+8）
    return date.toLocaleString('zh-CN', finalOptions)
  } catch (e) {
    console.error('时间格式化错误:', e, dateStr)
    return String(dateStr)
  }
}

/**
 * 格式化时间并添加相对时间描述
 * @param dateStr - 时间字符串或时间戳
 * @returns 格式化后的时间字符串 + 相对时间
 */
export function formatDateTimeWithRelative(dateStr: string | number | null | undefined): string {
  if (!dateStr) return '-'
  
  try {
    let timeStr: string
    
    // 处理时间戳
    if (typeof dateStr === 'number') {
      const timestamp = dateStr < 10000000000 ? dateStr * 1000 : dateStr
      timeStr = new Date(timestamp).toISOString()
    } else {
      timeStr = String(dateStr).trim()
    }
    
    // 🔥 如果时间字符串没有时区标识，假定为 UTC+8 时间（后端已经入库为 UTC+8），添加 +08:00 后缀
    if (timeStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && !timeStr.endsWith('Z') && !timeStr.includes('+') && !timeStr.includes('-', 10)) {
      timeStr += '+08:00'
    }
    
    const utcDate = new Date(timeStr)
    
    if (isNaN(utcDate.getTime())) {
      console.warn('无效的时间格式:', dateStr)
      return String(dateStr)
    }
    
    // 获取当前时间
    const now = new Date()
    
    // 计算时间差
    const diff = now.getTime() - utcDate.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor(diff / (1000 * 60))
    
    // 格式化为中国本地时间
    const formatted = utcDate.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
    
    // 添加相对时间
    let relative = ''
    if (days > 0) {
      relative = `（${days}天前）`
    } else if (hours > 0) {
      relative = `（${hours}小时前）`
    } else if (minutes > 0) {
      relative = `（${minutes}分钟前）`
    } else {
      relative = '（刚刚）'
    }
    
    return formatted + ' ' + relative
  } catch (e) {
    console.error('时间格式化错误:', e, dateStr)
    return String(dateStr)
  }
}

/**
 * 仅格式化日期部分（不含时间）
 * @param dateStr - 时间字符串或时间戳
 * @returns 格式化后的日期字符串
 */
export function formatDate(dateStr: string | number | null | undefined): string {
  return formatDateTime(dateStr, {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

/**
 * 将 Date 对象或日期字符串格式化为本地时区的 "YYYY-MM-DD" 字符串
 *
 * ⚠️ 替代 `new Date(d).toISOString().split('T')[0]`：
 * 后者会把本地时间转成 UTC，东八区用户选的 5月12日 00:00 会被错误地格式化为 "2026-05-11"。
 * 本函数使用本地时区字段值，保证日期与用户选择一致。
 *
 * @param date - Date 对象、日期字符串或时间戳
 * @returns "YYYY-MM-DD" 格式字符串，输入无效时返回空字符串
 */
export function formatLocalDate(date: Date | string | number | null | undefined): string {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return ''
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

/**
 * 仅格式化时间部分（不含日期）
 * @param dateStr - 时间字符串或时间戳
 * @returns 格式化后的时间字符串
 */
export function formatTime(dateStr: string | number | null | undefined): string {
  return formatDateTime(dateStr, {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

/**
 * 格式化相对时间（距离现在多久）
 * @param dateStr - 时间字符串或时间戳
 * @returns 相对时间描述
 */
export function formatRelativeTime(dateStr: string | number | null | undefined): string {
  if (!dateStr) return '-'

  try {
    let timeStr: string

    // 处理时间戳
    if (typeof dateStr === 'number') {
      const timestamp = dateStr < 10000000000 ? dateStr * 1000 : dateStr
      timeStr = new Date(timestamp).toISOString()
    } else {
      timeStr = String(dateStr).trim()
    }

    // 🔥 如果时间字符串没有时区标识，假定为 UTC+8 时间（后端已经入库为 UTC+8），添加 +08:00 后缀
    if (timeStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && !timeStr.endsWith('Z') && !timeStr.includes('+') && !timeStr.includes('-', 10)) {
      timeStr += '+08:00'
    }

    const targetDate = new Date(timeStr)

    if (isNaN(targetDate.getTime())) {
      console.warn('无效的时间格式:', dateStr)
      return String(dateStr)
    }

    // 获取当前时间
    const now = new Date()

    // 计算时间差（毫秒）
    const diff = targetDate.getTime() - now.getTime()
    const absDiff = Math.abs(diff)

    // 转换为各种时间单位
    const seconds = Math.floor(absDiff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    // 判断是过去还是将来
    const isPast = diff < 0

    // 格式化相对时间
    if (days > 0) {
      return isPast ? `${days}天前` : `${days}天后`
    } else if (hours > 0) {
      return isPast ? `${hours}小时前` : `${hours}小时后`
    } else if (minutes > 0) {
      return isPast ? `${minutes}分钟前` : `${minutes}分钟后`
    } else if (seconds > 10) {
      return isPast ? `${seconds}秒前` : `${seconds}秒后`
    } else {
      return isPast ? '刚刚' : '即将执行'
    }
  } catch (e) {
    console.error('相对时间格式化错误:', e, dateStr)
    return String(dateStr)
  }
}
