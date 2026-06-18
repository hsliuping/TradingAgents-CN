const { contextBridge, ipcRenderer } = require('electron')

// ---------------------------------------------------------------------------
// 通过 contextBridge 向渲染进程安全地暴露有限 API
// 原则：只暴露必要的、可控的功能，绝不暴露 Node.js 全量 API
// ---------------------------------------------------------------------------

contextBridge.exposeInMainWorld('electronAPI', {
  // ---- 平台信息 ----
  platform: process.platform,
  arch: process.arch,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  },

  // ---- 窗口控制 ----
  minimizeWindow: () => ipcRenderer.send('window:minimize'),
  maximizeWindow: () => ipcRenderer.send('window:maximize'),
  closeWindow: () => ipcRenderer.send('window:close'),

  // ---- 外部链接 ----
  openExternal: (url) => ipcRenderer.send('shell:openExternal', url),

  // ---- 应用信息 ----
  getAppVersion: () => ipcRenderer.invoke('app:getVersion'),
  getAppPath: () => ipcRenderer.invoke('app:getPath'),

  // ---- 平台检测 ----
  isWindows: process.platform === 'win32',
  isMac: process.platform === 'darwin',
  isLinux: process.platform === 'linux',

  // ---- IPC 通用通信（按需扩展）----
  send: (channel, ...args) => {
    const allowedChannels = ['window:minimize', 'window:maximize', 'window:close', 'shell:openExternal']
    if (allowedChannels.includes(channel)) {
      ipcRenderer.send(channel, ...args)
    }
  },
  invoke: (channel, ...args) => {
    const allowedChannels = ['app:getVersion', 'app:getPath']
    if (allowedChannels.includes(channel)) {
      return ipcRenderer.invoke(channel, ...args)
    }
    return Promise.reject(new Error(不允许的 IPC 通道: ))
  },
  on: (channel, callback) => {
    const allowedChannels = ['app:updateAvailable', 'app:downloadProgress']
    if (allowedChannels.includes(channel)) {
      const subscription = (_event, ...args) => callback(...args)
      ipcRenderer.on(channel, subscription)
      // 返回取消订阅函数
      return () => ipcRenderer.removeListener(channel, subscription)
    }
  }
})

console.log('[preload] 预加载脚本已执行，electronAPI 已暴露到 window.electronAPI')
