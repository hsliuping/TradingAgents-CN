/**
 * 安全的 Markdown 渲染工具
 *
 * 使用 marked 解析 Markdown + DOMPurify 净化 HTML，防止 XSS 攻击。
 * 所有通过 v-html 渲染 LLM 输出/用户输入的地方都应使用此工具。
 *
 * 安全模型：
 * - marked 将 Markdown 转换为 HTML 字符串
 * - DOMPurify 移除所有危险标签（<script>、on* 事件属性、javascript: 协议等）
 * - 允许常规排版标签（h1-h6、p、a、code、pre、table、ul/ol/li、strong/em 等）
 *
 * 使用方式：
 *   import { renderMarkdown } from '@/utils/markdown'
 *   const html = renderMarkdown(llmOutput)
 *   // 在模板中： <div v-html="html"></div>
 */

import { marked, type MarkedOptions } from 'marked'
import DOMPurify from 'dompurify'
import type { Config as DOMPurifyConfig } from 'dompurify'

// marked 全局配置：启用 GFM 和换行符
const markedOptions: MarkedOptions = {
  gfm: true,
  breaks: true,
}

// DOMPurify 配置：允许 Markdown 常见排版标签，禁止所有危险内容
const purifyConfig: DOMPurifyConfig = {
  // 允许的标签白名单（涵盖 Markdown 输出的所有常规标签）
  ALLOWED_TAGS: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'a', 'img',
    'strong', 'em', 'del', 's', 'u', 'mark', 'small', 'sub', 'sup',
    'code', 'pre', 'kbd', 'samp', 'var',
    'blockquote', 'q', 'cite',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
    'div', 'span',
    'details', 'summary',
    'figure', 'figcaption',
    'abbr', 'address', 'time',
  ],
  // 允许的属性白名单
  ALLOWED_ATTR: [
    'href', 'title', 'target', 'rel',
    'src', 'alt', 'width', 'height',
    'class', 'id',
    'colspan', 'rowspan',
    'datetime',
    'open',
    'align',
    'start', 'type', 'value',
  ],
  // 强制 a 标签的 rel 属性，防止钓鱼和 tabnabbing
  FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick', 'onmouseover'],
  // 允许协议白名单（禁止 javascript:、data: 等危险协议）
  ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|ftp|tel):|#|\/)/i,
}

// 配置 DOMPurify 钩子：为所有外部链接添加 rel="noopener noreferrer" 和 target="_blank"
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.getAttribute('href')) {
    const href = node.getAttribute('href') || ''
    // 外部链接（http/https 协议）添加安全属性
    if (/^https?:\/\//i.test(href)) {
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noopener noreferrer')
    }
  }
})

// 初始化 marked（仅配置一次）
marked.setOptions(markedOptions)

/**
 * 安全渲染 Markdown 为 HTML 字符串
 *
 * @param markdown Markdown 源字符串（可能来自 LLM 输出或用户输入）
 * @returns 净化后的 HTML 字符串，可直接用于 v-html
 */
export function renderMarkdown(markdown: string): string {
  if (!markdown) {
    return ''
  }
  try {
    // 1. marked 解析 Markdown → HTML
    const rawHtml = marked.parse(markdown, { async: false }) as string
    // 2. DOMPurify 净化 HTML → 安全 HTML
    // 注意：DOMPurify.sanitize 返回 TrustedHTML，需要转为 string
    const cleanHtml = String(DOMPurify.sanitize(rawHtml, purifyConfig))
    return cleanHtml
  } catch (err) {
    // 渲染失败时返回转义后的纯文本，避免崩溃
    console.error('[markdown] 渲染失败，返回转义文本:', err)
    return escapeHtml(String(markdown))
  }
}

/**
 * 转义 HTML 特殊字符（用于安全显示纯文本）
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export default renderMarkdown
