#!/usr/bin/env node
/**
 * mock-jdyun-gateway.mjs — 京东云网关本地模拟器（含登录页）
 *
 * 完整模拟京东云登录链路:
 *   1. 用户打开 http://localhost:3100 → 未登录，重定向到 /login
 *   2. /login 显示登录页面（模拟京东云平台登录）
 *   3. 用户输入用户名密码 → 网关验证凭据
 *   4. 验证通过 → 设置 session cookie，重定向到首页
 *   5. 后续所有请求自动携带 cookie → 网关从 cookie 提取凭据注入 Basic Auth
 *   6. 用户无需二次登录，直接使用系统
 *
 * 真实京东云链路对照:
 *   京东云登录页        → 本网关 /login 页面
 *   京东云平台认证       → 本网关验证用户名密码
 *   京东云网关注入Header → 本网关从 cookie 提取凭据注入 Authorization: Basic
 *   我们的容器          → 前端 3003 / 后端 8002
 *
 * 启动方式:
 *   $env:JDYUN_AUTH_USER = "testuser"
 *   $env:JDYUN_AUTH_PASS = "Test@123456"
 *   node frontend/mock-jdyun-gateway.mjs
 *   浏览器打开 http://localhost:3100
 *
 * 环境变量:
 *   JDYUN_GATEWAY_PORT      网关监听端口（默认 3100）
 *   JDYUN_TARGET            目标地址（默认 http://127.0.0.1:8082）
 *   JDYUN_AUTH_USER         登录用户名（默认 testuser）
 *   JDYUN_AUTH_PASS         登录密码（必填）
 */

import http from 'node:http'
import { URL } from 'node:url'

// ===== 配置 =====
// 单容器镜像：前端+后端+Nginx 统一在 8082 端口
// 模拟网关只需把所有请求转发到 8082，Nginx 内部自动区分前端/后端
const GATEWAY_PORT = parseInt(process.env.JDYUN_GATEWAY_PORT || '3100', 10)
const TARGET = process.env.JDYUN_TARGET || 'http://127.0.0.1:8082'

// 登录页凭据（模拟京东云平台账号，用户在登录页输入）
// 开发测试用，直接写死，无需配置环境变量
const AUTH_USER = 'testuser'
const AUTH_PASS = 'Test@123456'

// 注入后端的 Basic Auth 凭据（对应后端 JDYUN_BASIC_AUTH_USERS 配置）
// 默认用 .env.docker.jdyun 中的 jcloud-ugidvcp 凭据
const INJECT_AUTH = process.env.JDYUN_INJECT_AUTH || 'jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7'

// Cookie 中存储的凭据（就是注入后端的 Basic Auth 的 base64 值）
const CREDENTIAL_B64 = Buffer.from(INJECT_AUTH, 'utf-8').toString('base64')
const SESSION_COOKIE_NAME = 'jdyun_session'

// 后端路径前缀
const BACKEND_PREFIXES = ['/api', '/docs', '/openapi.json', '/redoc']

// 不需要登录即可访问的路径（静态资源等）
const PUBLIC_PATHS = ['/login', '/favicon.ico', '/logo.svg', '/manifest.json']
const PUBLIC_EXTENSIONS = ['.js', '.css', '.ico', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.woff', '.woff2', '.ttf', '.map']

function isBackendPath(pathname) {
  return BACKEND_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + '/'))
}

function isPublicPath(pathname) {
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'))) return true
  const ext = pathname.substring(pathname.lastIndexOf('.'))
  return PUBLIC_EXTENSIONS.includes(ext)
}

function parseTarget(target) {
  const t = new URL(target)
  return { protocol: t.protocol, hostname: t.hostname, port: t.port || (t.protocol === 'https:' ? 443 : 80), host: t.host }
}

// ===== Cookie / Session =====
function parseCookies(cookieHeader) {
  const cookies = {}
  if (!cookieHeader) return cookies
  for (const part of cookieHeader.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k) cookies[k] = v.join('=').trim()
  }
  return cookies
}

function isValidSession(cookieHeader) {
  const cookies = parseCookies(cookieHeader)
  return cookies[SESSION_COOKIE_NAME] === CREDENTIAL_B64
}

// ===== 登录页面 HTML =====
function renderLoginPage(errorMsg) {
  const errorBlock = errorMsg
    ? `<div class="error">${errorMsg}</div>`
    : `<div class="hint">京东云合作版 — 请输入您的京东云账号密码</div>`
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>京东云 - 登录</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
      background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
    }
    .login-card {
      background: #fff; border-radius: 12px; padding: 40px 36px; width: 380px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    }
    .logo {
      text-align: center; margin-bottom: 28px;
    }
    .logo-text {
      font-size: 24px; font-weight: 700; color: #1a73e8;
    }
    .logo-sub {
      font-size: 13px; color: #999; margin-top: 4px;
    }
    .form-group { margin-bottom: 20px; }
    .form-group label {
      display: block; font-size: 14px; color: #333; margin-bottom: 8px; font-weight: 500;
    }
    .form-group input {
      width: 100%; padding: 12px 14px; border: 1px solid #ddd; border-radius: 8px;
      font-size: 15px; transition: border-color 0.2s; outline: none;
    }
    .form-group input:focus { border-color: #1a73e8; }
    .btn-login {
      width: 100%; padding: 13px; background: #1a73e8; color: #fff; border: none;
      border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
      transition: background 0.2s; margin-top: 8px;
    }
    .btn-login:hover { background: #1557b0; }
    .btn-login:active { background: #0d47a1; }
    .error {
      background: #fff0f0; color: #e53935; padding: 10px 14px; border-radius: 8px;
      font-size: 14px; margin-bottom: 20px; border: 1px solid #ffcdd2;
    }
    .hint {
      color: #999; font-size: 13px; margin-bottom: 20px; text-align: center;
    }
    .footer {
      text-align: center; margin-top: 24px; font-size: 12px; color: #bbb;
    }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="logo">
      <div class="logo-text">☁️ 京东云</div>
      <div class="logo-sub">TradingAgents-CN 合作版</div>
    </div>
    ${errorBlock}
    <form method="POST" action="/login">
      <div class="form-group">
        <label>用户名</label>
        <input type="text" name="username" placeholder="请输入用户名" autocomplete="username" required />
      </div>
      <div class="form-group">
        <label>密码</label>
        <input type="password" name="password" placeholder="请输入密码" autocomplete="current-password" required />
      </div>
      <button type="submit" class="btn-login">登 录</button>
    </form>
    <div class="footer">© 京东云合作版 · 本地模拟网关</div>
  </div>
</body>
</html>`
}

// ===== 请求体解析 =====
function readBody(req) {
  return new Promise((resolve) => {
    let data = ''
    req.on('data', (chunk) => { data += chunk })
    req.on('end', () => resolve(data))
  })
}

function parseUrlEncoded(body) {
  const params = {}
  for (const pair of body.split('&')) {
    const [k, ...v] = pair.split('=')
    if (k) params[decodeURIComponent(k)] = decodeURIComponent(v.join('='))
  }
  return params
}

// ===== HTTP 转发 =====
function forward(req, res, target, injectAuth) {
  const t = parseTarget(target)
  const headers = { ...req.headers, host: t.host }
  if (injectAuth) headers.authorization = `Basic ${CREDENTIAL_B64}`

  const proxyReq = http.request(
    { protocol: t.protocol, hostname: t.hostname, port: t.port, method: req.method, path: req.url, headers },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers)
      proxyRes.pipe(res)
    }
  )
  proxyReq.on('error', (err) => {
    console.error(`❌ 转发失败 ${req.method} ${req.url} → ${err.message}`)
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end(`网关转发失败: ${err.message}`)
  })
  req.pipe(proxyReq)
}

// ===== WebSocket 转发 =====
function forwardUpgrade(req, socket, head) {
  const pathname = (req.url || '/').split('?')[0]
  const isBackend = isBackendPath(pathname)
  const target = TARGET
  const t = parseTarget(target)
  // 复制原始头，覆盖 host，显式设置升级头（避免 Node.js http 客户端覆盖 Connection）
  const headers = { ...req.headers, host: t.host }
  if (isBackend) headers.authorization = `Basic ${CREDENTIAL_B64}`
  headers.connection = 'Upgrade'
  headers.upgrade = 'websocket'

  console.log(`🔌 [WS] ${req.url} → ${target}`)

  const proxyReq = http.request({
    protocol: t.protocol, hostname: t.hostname, port: t.port,
    method: req.method || 'GET', path: req.url, headers,
  })

  // 后端返回 101 Switching Protocols → 转发升级响应
  proxyReq.on('upgrade', (proxyRes, proxySocket, proxyHead) => {
    const rawHeaders = Object.entries(proxyRes.headers)
      .map(([k, v]) => (Array.isArray(v) ? v.map((x) => `${k}: ${x}`).join('\r\n') : `${k}: ${v}`))
      .join('\r\n')
    // 注意：头结束后需要 \r\n\r\n（空行表示头结束）
    socket.write('HTTP/1.1 101 Switching Protocols\r\n' + rawHeaders + '\r\n\r\n')
    if (proxyHead && proxyHead.length) socket.write(proxyHead)
    if (head && head.length) proxySocket.write(head)
    proxySocket.pipe(socket)
    socket.pipe(proxySocket)
    console.log(`✅ [WS] 升级成功: ${req.url}`)
  })

  // 后端返回普通 HTTP 响应（如 403/401 拒绝升级）→ 转发给客户端
  proxyReq.on('response', (proxyRes) => {
    const chunks = []
    proxyRes.on('data', (chunk) => chunks.push(chunk))
    proxyRes.on('end', () => {
      const body = Buffer.concat(chunks)
      const statusLine = `HTTP/1.1 ${proxyRes.statusCode} ${proxyRes.statusMessage || ''}\r\n`
      const rawHeaders = Object.entries(proxyRes.headers)
        .map(([k, v]) => (Array.isArray(v) ? v.map((x) => `${k}: ${x}`).join('\r\n') : `${k}: ${v}`))
        .join('\r\n')
      socket.write(statusLine + rawHeaders + '\r\n\r\n')
      if (body.length) socket.write(body)
      socket.end()
      console.log(`⚠️ [WS] 后端拒绝升级 (HTTP ${proxyRes.statusCode}): ${req.url}`)
    })
  })

  proxyReq.on('error', (err) => {
    console.error(`❌ WS 转发失败 ${req.url} → ${err.message}`)
    socket.destroy()
  })

  proxyReq.end()
}

// ===== HTTP 请求处理 =====
async function handleHttp(req, res) {
  const pathname = (req.url || '/').split('?')[0]

  // --- 登录页 ---
  if (pathname === '/login') {
    if (req.method === 'GET') {
      return res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(renderLoginPage())
    }
    if (req.method === 'POST') {
      const body = await readBody(req)
      const { username, password } = parseUrlEncoded(body)
      if (username === AUTH_USER && password === AUTH_PASS) {
        console.log(`✅ 登录成功: ${username}`)
        res.writeHead(302, {
          'Set-Cookie': `${SESSION_COOKIE_NAME}=${CREDENTIAL_B64}; HttpOnly; Path=/; Max-Age=86400; SameSite=Lax`,
          'Location': '/',
        })
        return res.end()
      }
      console.log(`❌ 登录失败: ${username}`)
      return res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(renderLoginPage('用户名或密码错误'))
    }
  }

  // --- 登出 ---
  if (pathname === '/logout') {
    res.writeHead(302, {
      'Set-Cookie': `${SESSION_COOKIE_NAME}=; HttpOnly; Path=/; Max-Age=0`,
      'Location': '/login',
    })
    return res.end()
  }

  // --- 检查登录状态 ---
  const loggedIn = isValidSession(req.headers.cookie)

  // API 请求：未登录返回 401
  if (isBackendPath(pathname)) {
    if (!loggedIn) {
      return res.writeHead(401, { 'Content-Type': 'application/json' }).end(JSON.stringify({ success: false, message: '未登录' }))
    }
    console.log(`🔐 [API] ${req.method} ${pathname} -> 后端`)
    return forward(req, res, TARGET, true)
  }

  // 公开资源（静态文件等）：直接转发到前端
  if (isPublicPath(pathname)) {
    return forward(req, res, TARGET, false)
  }

  // 页面请求：未登录重定向到登录页
  if (!loggedIn) {
    res.writeHead(302, { 'Location': '/login' })
    return res.end()
  }

  // 已登录：转发到前端
  console.log(`🌐 [页面] ${req.method} ${pathname} -> 前端`)
  return forward(req, res, TARGET, false)
}

// ===== 启动 =====
const server = http.createServer((req, res) => {
  handleHttp(req, res).catch((err) => {
    console.error('❌ 处理请求异常:', err)
    if (!res.headersSent) res.writeHead(500).end('Internal Server Error')
  })
})
server.on('upgrade', forwardUpgrade)

server.listen(GATEWAY_PORT, '0.0.0.0', () => {
  console.log('==========================================================')
  console.log('  京东云网关本地模拟器（含登录页）')
  console.log('==========================================================')
  console.log(`  网关地址:  http://localhost:${GATEWAY_PORT}`)
  console.log(`  登录页:    http://localhost:${GATEWAY_PORT}/login`)
  console.log(`  目标地址:  ${TARGET}`)
  console.log(`  登录凭据:  ${AUTH_USER} / ${AUTH_PASS}`)
  console.log('==========================================================')
  console.log('  流程: 打开网关地址 → 登录页 → 输入凭据 → 跳转系统')
  console.log('==========================================================')
})
