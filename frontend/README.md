# TradingAgents-CN 前端应用

现代化的Vue3前端界面，为TradingAgents-CN提供优秀的用户体验。

## 🚀 快速开始

### 环境要求

- Node.js >= 18.0.0
- npm >= 8.0.0

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## 📁 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── api/               # API接口
│   ├── components/        # 组件
│   │   ├── Global/       # 全局组件
│   │   └── Layout/       # 布局组件
│   ├── layouts/          # 页面布局
│   ├── router/           # 路由配置
│   ├── stores/           # 状态管理
│   ├── styles/           # 样式文件
│   ├── types/            # 类型定义
│   ├── utils/            # 工具函数
│   ├── views/            # 页面组件
│   ├── App.vue           # 根组件
│   └── main.ts           # 应用入口
├── index.html            # HTML模板
├── package.json          # 项目配置
├── tsconfig.json         # TypeScript配置
├── vite.config.ts        # Vite配置
└── README.md             # 说明文档
```

## 🎨 主要功能

### 📊 仪表板
- 数据概览和统计
- 快速操作入口
- 系统状态监控
- 最近分析记录

### 🔍 股票筛选
- 多维度筛选条件
- 实时结果展示
- 批量操作支持
- 筛选结果导出

### 📈 股票分析
- 单股深度分析
- 批量分析处理
- 分析历史查看
- 进度实时跟踪

### 📋 队列管理
- 任务队列监控
- 实时状态更新
- 任务优先级管理
- 批量操作支持

### 📄 分析报告
- 报告生成和管理
- 多格式导出支持
- 报告分享功能
- 历史报告查看

### ⚙️ 系统设置
- 个人偏好配置
- 主题和外观设置
- 分析参数配置
- 安全设置管理

## 🛠️ 技术栈

### 核心框架
- **Vue 3** - 渐进式JavaScript框架
- **TypeScript** - 类型安全的JavaScript
- **Vite** - 现代化构建工具

### UI组件库
- **Element Plus** - 企业级Vue组件库
- **@element-plus/icons-vue** - 图标组件

### 状态管理
- **Pinia** - Vue官方状态管理库
- **@vueuse/core** - Vue组合式API工具集

### 路由和网络
- **Vue Router 4** - 官方路由管理器
- **Axios** - HTTP客户端

### 开发工具
- **ESLint** - 代码质量检查
- **Prettier** - 代码格式化
- **unplugin-auto-import** - 自动导入
- **unplugin-vue-components** - 组件自动导入

## 🎯 特色功能

### 🌈 现代化设计
- 响应式布局设计
- 明暗主题切换
- 流畅的动画效果
- 移动端适配

### 🔧 开发体验
- TypeScript类型安全
- 组件自动导入
- 热模块替换
- 代码分割优化

### 🚀 性能优化
- 路由懒加载
- 组件按需加载
- 图片懒加载
- 缓存策略优化

### 🔒 安全特性
- JWT认证集成
- 权限路由守卫
- XSS防护
- CSRF保护

## 📱 响应式设计

支持多种设备尺寸：

- **桌面端**: >= 1200px
- **平板端**: 768px - 1199px  
- **手机端**: < 768px

## 🎨 主题定制

支持多种主题模式：

- **浅色主题**: 适合白天使用
- **深色主题**: 适合夜间使用
- **自动模式**: 跟随系统设置

## 🔧 配置说明

### 环境变量

创建 `.env.local` 文件：

```env
# API基础URL
VITE_API_BASE_URL=http://localhost:8000/api

# 应用标题
VITE_APP_TITLE=TradingAgents-CN
```

### 代理配置

开发环境自动代理API请求到后端服务：

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

## 🚀 部署指南

### 构建应用

```bash
npm run build
```

### 部署到Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🤝 开发指南

### 添加新页面

1. 在 `src/views/` 创建页面组件
2. 在 `src/router/index.ts` 添加路由
3. 在侧边栏菜单中添加导航

### 添加新API

1. 在 `src/types/` 定义类型
2. 在 `src/api/` 创建API模块
3. 在组件中使用API

### 状态管理

使用Pinia进行状态管理：

```typescript
// 定义store
export const useExampleStore = defineStore('example', {
  state: () => ({
    data: []
  }),
  actions: {
    async fetchData() {
      // 获取数据逻辑
    }
  }
})

// 在组件中使用
const exampleStore = useExampleStore()
```

## 📝 代码规范

### 命名规范
- 组件名：PascalCase
- 文件名：kebab-case
- 变量名：camelCase
- 常量名：UPPER_SNAKE_CASE

### 提交规范
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构
- test: 测试相关
- chore: 构建过程或辅助工具的变动

## 🐛 问题排查

### 常见问题

1. **依赖安装失败**
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **端口被占用**
   ```bash
   # 修改端口
   npm run dev -- --port 3001
   ```

3. **类型错误**
   ```bash
   # 重新生成类型文件
   npm run type-check
   ```

---

**TradingAgents-CN Frontend v1.0.0-preview** - 现代化的股票分析平台前端
