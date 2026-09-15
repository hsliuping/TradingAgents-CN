/**
 * 交付物文件下载拦截器（全局）
 *
 * 背景：智能助手回复中的下载链接（/api/assistant/deliverables/*.xlsx）是
 * <a> 标签，浏览器直接导航不带 Authorization 头（JWT 存 localStorage，仅
 * XHR/fetch 会携带），历史消息里的链接点击必然 401"未登录或登录已过期"。
 *
 * 方案：document 捕获阶段全局委托，拦截该类链接的点击，改用 fetch
 * （带 JWT 头）请求后以 blob 触发浏览器下载。
 *   - 历史消息中的旧链接（无签名）→ fetch 带 JWT → 可下载
 *   - 新签名链接（?exp=&sig=）→ 同样走此路径，行为一致
 *   - 未登录/过期 → 提示用户重新登录
 *
 * 全局一次性绑定，覆盖智能助手主页、悬浮助手、股票详情页等所有
 * 渲染 markdown 消息的位置，后续新增入口无需重复接线。
 */

// 匹配智能助手交付物下载链接（相对路径或绝对路径均可）
const DELIVERABLE_HREF_PATTERN = /\/api\/assistant\/deliverables\//

/** 从 Content-Disposition 提取文件名（支持 RFC 5987 filename* 与普通 filename） */
function extractFilename(
  contentDisposition: string | null,
  fallbackHref: string
): string {
  if (contentDisposition) {
    // filename*=UTF-8''%E8%B5%9B... 优先（FastAPI 对中文文件名用此格式）
    const starMatch = contentDisposition.match(/filename\*=(?:UTF-8''|utf-8'')([^;]+)/i)
    if (starMatch) {
      try {
        return decodeURIComponent(starMatch[1].replace(/["']/g, '').trim())
      } catch {
        /* fallthrough */
      }
    }
    const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
    if (plainMatch) {
      try {
        return decodeURIComponent(plainMatch[1].trim())
      } catch {
        return plainMatch[1].trim()
      }
    }
  }
  // fallback：URL path 末段
  try {
    const path = fallbackHref.split('?')[0]
    return decodeURIComponent(path.substring(path.lastIndexOf('/') + 1)) || 'download.xlsx'
  } catch {
    return 'download.xlsx'
  }
}

async function downloadDeliverable(href: string): Promise<void> {
  // 动态引入避免 utils 层硬依赖 pinia（token 过期刷新由 request.ts 体系负责，
  // 这里兜底 localStorage 直读，保持与 request.ts 相同的取值链）
  const { useAuthStore } = await import('@/stores/auth')
  const authStore = useAuthStore()
  const token = authStore.token || localStorage.getItem('auth-token')

  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  try {
    const resp = await fetch(href, { headers, credentials: 'include' })

    if (resp.status === 401) {
      const { ElMessage } = await import('element-plus')
      ElMessage.error('登录已过期，请重新登录后再次点击下载')
      return
    }
    if (!resp.ok) {
      const { ElMessage } = await import('element-plus')
      ElMessage.error(`下载失败（HTTP ${resp.status}），请重新导出后再试`)
      return
    }

    const blob = await resp.blob()
    const filename = extractFilename(resp.headers.get('content-disposition'), href)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('[deliverableDownload] 下载失败:', err)
    const { ElMessage } = await import('element-plus')
    ElMessage.error('下载失败，请检查网络后重试')
  }
}

let installed = false

/** 安装全局交付物下载拦截（幂等，在应用入口调用一次） */
export function setupDeliverableDownloadInterceptor(): void {
  if (installed) return
  installed = true

  document.addEventListener(
    'click',
    (event) => {
      // 捕获阶段拦截，抢在浏览器导航之前
      const target = event.target as HTMLElement | null
      const anchor = target?.closest?.('a[href]') as HTMLAnchorElement | null
      if (!anchor) return

      const href = anchor.getAttribute('href') || ''
      if (!DELIVERABLE_HREF_PATTERN.test(href)) return

      event.preventDefault()
      event.stopPropagation()
      void downloadDeliverable(href)
    },
    true
  )
}
