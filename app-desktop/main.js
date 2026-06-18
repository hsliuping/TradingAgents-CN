const { app, BrowserWindow, shell, Menu, ipcMain } = require('electron')
const path = require('path')

// ---------------------------------------------------------------------------
// 常量 & 全局状态
// ---------------------------------------------------------------------------
const IS_DEV = !app.isPackaged
const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL || 'http://localhost:3000'

let mainWindow = null

// ---------------------------------------------------------------------------
// 创建主窗口
// ---------------------------------------------------------------------------
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'AITrading - 多智能体股票分析学习平台',
    show: false,          // 先隐藏，ready-to-show 后再显示，避免白屏闪烁
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,   // 启用上下文隔离（安全）
      nodeIntegration: false,   // 禁用 Node 集成（安全）
      sandbox: false            // 关闭沙盒以允许 preload 使用 Node API
    }
  })

  // ---------- 加载页面 ----------
  if (IS_DEV) {
    // 开发环境：加载 Vite 开发服务器
    console.log('[main] 开发模式，连接 Vite 开发服务器:', VITE_DEV_SERVER_URL)
    mainWindow.loadURL(VITE_DEV_SERVER_URL)
    // 开发环境下自动打开 DevTools
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    // 生产环境：加载打包后的 Vue 静态文件（在 app.asar 内的 dist/ 目录）
    const indexPath = path.join(__dirname, 'dist', 'index.html')
    console.log('[main] 生产模式，__dirname:', __dirname)
    console.log('[main] 生产模式，加载文件:', indexPath)

    // 添加文件加载失败监听（帮助诊断白屏问题）
    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
      console.error('[main] 页面加载失败:', errorCode, errorDescription, validatedURL)
    })

    mainWindow.loadFile(indexPath).catch(err => {
      console.error('[main] loadFile 失败:', err.message)
    })
  }

  // ---------- 窗口事件 ----------
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // ---------- 拦截外部链接，在默认浏览器中打开 ----------
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  // 处理页面内 navigated 到外部链接的情况
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!IS_DEV && !url.startsWith('file://')) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })
}

// ---------------------------------------------------------------------------
// IPC 处理器（配合 preload.js 的 contextBridge）
// ---------------------------------------------------------------------------
function registerIpcHandlers() {
  ipcMain.on('window:minimize', () => {
    mainWindow?.minimize()
  })
  ipcMain.on('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.on('window:close', () => {
    mainWindow?.close()
  })
  ipcMain.on('shell:openExternal', (_event, url) => {
    if (typeof url === 'string' && (url.startsWith('http:') || url.startsWith('https:'))) {
      shell.openExternal(url)
    }
  })
  ipcMain.handle('app:getVersion', () => app.getVersion())
  ipcMain.handle('app:getPath', () => app.getAppPath())
}

// ---------------------------------------------------------------------------
// 应用生命周期
// ---------------------------------------------------------------------------
app.whenReady().then(() => {
  registerIpcHandlers()
  Menu.setApplicationMenu(null)
  createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 防止多实例
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}