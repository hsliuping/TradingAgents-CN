# 应用升级功能设计

## 1. 现状分析

### 1.1 当前版本管理

| 组件 | 版本来源 | 说明 |
|------|----------|------|
| **后端** | `VERSION` 文件 | `v1.0.0-preview` |
| **前端** | `stores/app.ts` | 硬编码 `0.1.16` |
| **数据库** | `system_config` 集合 | `v1.0.0-preview` |

### 1.2 本地数据存储

| 存储位置 | 数据类型 | 迁移风险 |
|----------|----------|----------|
| **MongoDB** | 用户、分析报告、配置等 | 🔴 高 |
| **localStorage** | 主题、偏好、认证Token | 🟡 中 |
| **文件系统** | 缓存、日志、临时文件 | 🟢 低 |

### 1.3 MongoDB集合清单

```
用户相关：users, user_sessions, user_activities
股票数据：stock_basic_info, stock_financial_data, market_quotes, stock_news
分析相关：analysis_tasks, analysis_reports, analysis_progress
筛选收藏：screening_results, favorites, tags
配置系统：system_config, system_configs, prompt_templates
模拟交易：paper_trades, paper_positions, paper_portfolios
其他：operation_logs, token_usage
```

---

## 2. 升级架构设计

### 2.1 升级检测流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      应用启动                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  检查云端最新版本                                 │
│   GET https://auth-server/api/v1/app/version                    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       版本相同                          有新版本
         │                                   │
         ▼                                   ▼
       正常启动                        显示升级提示
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                           立即升级      稍后提醒      跳过此版本
```

### 2.2 版本号规范

```
格式: v{major}.{minor}.{patch}[-{stage}]
示例: v1.0.0-preview, v1.1.0, v2.0.0-beta

major: 重大更新，可能有破坏性变更
minor: 功能更新，向后兼容
patch: Bug修复，向后兼容
stage: preview/alpha/beta/rc（可选）
```

### 2.3 升级类型

| 类型 | 说明 | 是否强制 | 数据迁移 |
|------|------|----------|----------|
| **强制升级** | 安全漏洞、严重Bug | ✅ 必须 | 自动 |
| **推荐升级** | 新功能、性能优化 | ❌ 可选 | 自动 |
| **静默升级** | 小Bug修复 | ❌ 可选 | 无需 |

---

## 3. 版本检测API设计

### 3.1 检查最新版本

```
GET /api/v1/app/version
X-App-Version: v1.0.0-preview
X-Platform: windows

Response:
{
  "code": 0,
  "data": {
    "latest_version": "v1.1.0",
    "current_version": "v1.0.0-preview",
    "has_update": true,
    "update_type": "recommended",  // forced/recommended/silent
    "release_date": "2024-01-20",
    "release_notes": "### 新功能\n- 持仓分析\n- 操作复盘",
    "download_url": "https://github.com/.../releases/download/v1.1.0/...",
    "min_supported_version": "v0.9.0",
    "migration_required": true,
    "migration_scripts": ["v1.0.0_to_v1.1.0"]
  }
}
```

### 3.2 获取迁移脚本

```
GET /api/v1/app/migration/{from_version}/{to_version}

Response:
{
  "code": 0,
  "data": {
    "from_version": "v1.0.0-preview",
    "to_version": "v1.1.0",
    "steps": [
      {
        "order": 1,
        "type": "mongodb",
        "collection": "users",
        "action": "add_field",
        "field": "license_key",
        "default": null
      },
      {
        "order": 2,
        "type": "mongodb", 
        "collection": "system_configs",
        "action": "update_schema",
        "changes": [...]
      }
    ],
    "backup_required": true,
    "estimated_time": 30  // 秒
  }
}
```

---

## 4. 数据迁移设计

### 4.1 迁移框架

```python
# app/migrations/migration_manager.py

class MigrationManager:
    """数据迁移管理器"""
    
    def __init__(self, db):
        self.db = db
        self.migrations_collection = db.migrations
        
    async def get_current_db_version(self) -> str:
        """获取数据库当前版本"""
        record = await self.migrations_collection.find_one(
            {"type": "db_version"},
            sort=[("applied_at", -1)]
        )
        return record["version"] if record else "v0.0.0"
    
    async def migrate(self, target_version: str) -> MigrationResult:
        """执行迁移到目标版本"""
        current = await self.get_current_db_version()
        
        # 获取需要执行的迁移
        pending = self.get_pending_migrations(current, target_version)
        
        # 备份数据
        backup_id = await self.backup_database()
        
        try:
            for migration in pending:
                await self.run_migration(migration)
                
            return MigrationResult(success=True)
        except Exception as e:
            # 回滚
            await self.restore_backup(backup_id)
            return MigrationResult(success=False, error=str(e))
```

### 4.2 迁移脚本结构

```python
# app/migrations/versions/v1_0_0_to_v1_1_0.py

class Migration_v1_0_0_to_v1_1_0:
    """v1.0.0 → v1.1.0 迁移脚本"""
    
    version_from = "v1.0.0-preview"
    version_to = "v1.1.0"
    description = "添加License字段，新增持仓分析表"
    
    async def up(self, db):
        """升级迁移"""
        # 1. users集合添加license_key字段
        await db.users.update_many(
            {"license_key": {"$exists": False}},
            {"$set": {"license_key": None, "license_expires": None}}
        )
        
        # 2. 创建持仓分析集合
        await db.create_collection("portfolio_positions")
        await db.create_collection("portfolio_analysis_reports")
        
        # 3. 创建操作复盘集合
        await db.create_collection("trade_reviews")
        
        # 4. 更新索引
        await db.portfolio_positions.create_index([
            ("user_id", 1), ("stock_code", 1)
        ])
        
    async def down(self, db):
        """回滚迁移"""
        # 移除新增字段
        await db.users.update_many(
            {},
            {"$unset": {"license_key": "", "license_expires": ""}}
        )
        
        # 删除新集合（谨慎操作）
        # await db.drop_collection("portfolio_positions")
```

### 4.3 备份策略

```python
# app/migrations/backup_manager.py

class BackupManager:
    """备份管理器"""
    
    async def create_backup(self, reason: str = "migration") -> str:
        """创建完整备份"""
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = Path(f"data/backups/{backup_id}")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 1. 导出MongoDB数据
        collections = await self.db.list_collection_names()
        for coll_name in collections:
            data = await self.db[coll_name].find().to_list(None)
            with open(backup_path / f"{coll_name}.json", "w") as f:
                json.dump(data, f, default=str)
        
        # 2. 备份localStorage（前端处理）
        # 3. 备份配置文件
        
        # 记录备份信息
        await self.db.backups.insert_one({
            "backup_id": backup_id,
            "reason": reason,
            "created_at": datetime.now(),
            "collections": collections,
            "path": str(backup_path)
        })
        
        return backup_id
```

---

## 5. 前端升级UI设计

### 5.1 升级提示组件

```vue
<!-- components/UpgradeNotification.vue -->
<template>
  <el-dialog
    v-model="visible"
    :title="isForced ? '🚨 重要更新' : '🎉 发现新版本'"
    :close-on-click-modal="!isForced"
    :show-close="!isForced"
  >
    <div class="upgrade-content">
      <div class="version-info">
        <span class="current">当前版本: {{ currentVersion }}</span>
        <el-icon><ArrowRight /></el-icon>
        <span class="latest">最新版本: {{ latestVersion }}</span>
      </div>

      <el-divider />

      <div class="release-notes">
        <h4>更新内容</h4>
        <div v-html="releaseNotes"></div>
      </div>

      <el-alert
        v-if="migrationRequired"
        type="warning"
        :closable="false"
        show-icon
      >
        此版本需要数据迁移，请确保已备份重要数据
      </el-alert>
    </div>

    <template #footer>
      <el-button v-if="!isForced" @click="remindLater">稍后提醒</el-button>
      <el-button v-if="!isForced" @click="skipVersion">跳过此版本</el-button>
      <el-button type="primary" @click="startUpgrade" :loading="upgrading">
        {{ isForced ? '立即升级' : '开始升级' }}
      </el-button>
    </template>
  </el-dialog>
</template>
```

### 5.2 升级进度组件

```vue
<!-- components/UpgradeProgress.vue -->
<template>
  <el-dialog v-model="visible" title="正在升级..." :close-on-click-modal="false" :show-close="false">
    <div class="upgrade-progress">
      <el-steps :active="currentStep" finish-status="success">
        <el-step title="备份数据" />
        <el-step title="下载更新" />
        <el-step title="数据迁移" />
        <el-step title="完成" />
      </el-steps>

      <el-progress
        :percentage="progress"
        :status="status"
        :stroke-width="20"
        class="main-progress"
      />

      <div class="step-detail">{{ stepDetail }}</div>

      <el-alert v-if="error" type="error" :title="error" :closable="false" />
    </div>
  </el-dialog>
</template>
```

### 5.3 设置页面版本信息

```vue
<!-- views/Settings/About.vue -->
<template>
  <el-card>
    <template #header>
      <span>关于应用</span>
    </template>

    <el-descriptions :column="1" border>
      <el-descriptions-item label="当前版本">
        {{ appVersion }}
        <el-tag v-if="hasUpdate" type="warning" size="small" class="ml-2">
          有新版本
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="最新版本">
        {{ latestVersion || '检查中...' }}
      </el-descriptions-item>
      <el-descriptions-item label="更新时间">
        {{ lastCheckTime }}
      </el-descriptions-item>
    </el-descriptions>

    <div class="actions">
      <el-button @click="checkUpdate" :loading="checking">检查更新</el-button>
      <el-button v-if="hasUpdate" type="primary" @click="showUpgrade">查看更新</el-button>
    </div>
  </el-card>
</template>
```

---

## 6. localStorage迁移

### 6.1 localStorage数据清单

| Key | 数据类型 | 迁移策略 |
|-----|----------|----------|
| `auth-token` | 认证Token | 保留，可能需重新登录 |
| `refresh-token` | 刷新Token | 保留 |
| `user-info` | 用户信息JSON | 检查schema变更 |
| `app-theme` | 主题设置 | 保留 |
| `app-language` | 语言设置 | 保留 |
| `sidebar-collapsed` | 侧边栏状态 | 保留 |
| `user-preferences` | 用户偏好JSON | 检查schema变更 |
| `learning-progress` | 学习进度 | 新增，需初始化 |

### 6.2 前端迁移逻辑

```typescript
// utils/storageMigration.ts

interface StorageMigration {
  fromVersion: string
  toVersion: string
  migrate: () => void
}

const migrations: StorageMigration[] = [
  {
    fromVersion: 'v1.0.0',
    toVersion: 'v1.1.0',
    migrate: () => {
      // 1. 迁移用户偏好
      const prefs = localStorage.getItem('user-preferences')
      if (prefs) {
        const data = JSON.parse(prefs)
        // 添加新字段
        data.enableLicenseFeatures = false
        data.learningProgressSync = true
        localStorage.setItem('user-preferences', JSON.stringify(data))
      }

      // 2. 初始化学习进度存储
      if (!localStorage.getItem('learning-progress')) {
        localStorage.setItem('learning-progress', JSON.stringify({
          articles: {},
          lastSync: null
        }))
      }

      // 3. 记录迁移版本
      localStorage.setItem('storage-version', 'v1.1.0')
    }
  }
]

export function runStorageMigrations(currentVersion: string, targetVersion: string) {
  const storedVersion = localStorage.getItem('storage-version') || 'v0.0.0'

  for (const migration of migrations) {
    if (compareVersions(storedVersion, migration.fromVersion) <= 0 &&
        compareVersions(targetVersion, migration.toVersion) >= 0) {
      console.log(`Running storage migration: ${migration.fromVersion} -> ${migration.toVersion}`)
      migration.migrate()
    }
  }
}
```

---

## 7. 升级流程实现

### 7.1 完整升级流程

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: 用户确认升级                                            │
│  • 显示版本信息和更新内容                                         │
│  • 强制更新不可跳过                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 2: 创建备份                                                │
│  • MongoDB数据导出                                               │
│  • localStorage快照                                              │
│  • 配置文件复制                                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 3: 下载新版本                                              │
│  • 从GitHub Releases下载                                         │
│  • 校验文件完整性(SHA256)                                        │
│  • 解压到临时目录                                                 │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 4: 数据迁移                                                │
│  • 执行MongoDB迁移脚本                                           │
│  • 执行localStorage迁移                                          │
│  • 更新配置文件                                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 5: 替换文件                                                │
│  • 停止后端服务                                                   │
│  • 替换应用文件                                                   │
│  • 重启应用                                                       │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 6: 验证升级                                                │
│  • 检查服务状态                                                   │
│  • 验证数据完整性                                                 │
│  • 升级成功提示                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 升级状态管理

```typescript
// stores/upgrade.ts

export const useUpgradeStore = defineStore('upgrade', {
  state: () => ({
    // 版本信息
    currentVersion: '',
    latestVersion: '',
    hasUpdate: false,
    updateType: '' as 'forced' | 'recommended' | 'silent',
    releaseNotes: '',
    downloadUrl: '',

    // 升级状态
    upgrading: false,
    currentStep: 0,  // 0-5
    progress: 0,
    stepDetail: '',
    error: null as string | null,

    // 备份信息
    backupId: null as string | null,

    // 用户选择
    skippedVersions: [] as string[]
  }),

  actions: {
    async checkForUpdate() {
      try {
        const res = await api.checkVersion(this.currentVersion)
        this.latestVersion = res.latest_version
        this.hasUpdate = res.has_update
        this.updateType = res.update_type
        this.releaseNotes = res.release_notes
        this.downloadUrl = res.download_url

        // 检查是否是跳过的版本
        if (this.skippedVersions.includes(this.latestVersion)) {
          this.hasUpdate = false
        }

        return this.hasUpdate
      } catch (e) {
        console.error('检查更新失败:', e)
        return false
      }
    },

    async startUpgrade() {
      this.upgrading = true
      this.error = null

      try {
        // Step 1: 备份
        this.currentStep = 0
        this.stepDetail = '正在备份数据...'
        this.backupId = await this.createBackup()
        this.progress = 25

        // Step 2: 下载
        this.currentStep = 1
        this.stepDetail = '正在下载更新包...'
        await this.downloadUpdate()
        this.progress = 50

        // Step 3: 迁移
        this.currentStep = 2
        this.stepDetail = '正在迁移数据...'
        await this.runMigrations()
        this.progress = 75

        // Step 4: 完成
        this.currentStep = 3
        this.stepDetail = '正在重启应用...'
        await this.restartApp()
        this.progress = 100

      } catch (e: any) {
        this.error = e.message
        // 尝试回滚
        if (this.backupId) {
          await this.rollback(this.backupId)
        }
      } finally {
        this.upgrading = false
      }
    }
  }
})
```

---

## 8. 后端升级服务

### 8.1 升级控制器

```python
# app/routers/upgrade.py

router = APIRouter(prefix="/api/v1/upgrade", tags=["upgrade"])

@router.get("/check")
async def check_update(
    current_version: str = Header(..., alias="X-App-Version"),
    platform: str = Header("windows", alias="X-Platform")
):
    """检查更新"""
    # 从云端获取最新版本信息
    latest = await get_latest_release(platform)

    has_update = compare_versions(current_version, latest.version) < 0
    update_type = determine_update_type(current_version, latest)

    return {
        "latest_version": latest.version,
        "current_version": current_version,
        "has_update": has_update,
        "update_type": update_type,
        "release_date": latest.release_date,
        "release_notes": latest.release_notes,
        "download_url": latest.download_url,
        "migration_required": latest.migration_required
    }

@router.post("/backup")
async def create_backup():
    """创建升级前备份"""
    backup_manager = BackupManager()
    backup_id = await backup_manager.create_backup(reason="upgrade")
    return {"backup_id": backup_id}

@router.post("/migrate")
async def run_migration(
    from_version: str,
    to_version: str,
    backup_id: str
):
    """执行数据迁移"""
    migration_manager = MigrationManager()
    result = await migration_manager.migrate(from_version, to_version)

    if not result.success:
        # 自动回滚
        await BackupManager().restore_backup(backup_id)
        raise HTTPException(500, f"迁移失败: {result.error}")

    return {"success": True, "migrated_collections": result.collections}

@router.post("/rollback/{backup_id}")
async def rollback(backup_id: str):
    """回滚到备份"""
    backup_manager = BackupManager()
    await backup_manager.restore_backup(backup_id)
    return {"success": True}
```

---

## 9. 实现计划

### Phase 1: 版本检测 (Week 1)

- [ ] 云端版本API
- [ ] 前端版本检查
- [ ] 升级提示UI

### Phase 2: 备份系统 (Week 2)

- [ ] MongoDB备份导出
- [ ] localStorage快照
- [ ] 备份恢复功能

### Phase 3: 迁移框架 (Week 3)

- [ ] 迁移管理器
- [ ] 迁移脚本模板
- [ ] 版本比较工具

### Phase 4: 升级流程 (Week 4)

- [ ] 下载更新包
- [ ] 文件替换逻辑
- [ ] 应用重启机制

### Phase 5: 测试优化 (Week 5)

- [ ] 升级流程测试
- [ ] 回滚测试
- [ ] 边界情况处理

---

## 10. 注意事项

### 10.1 数据安全

| 风险 | 应对措施 |
|------|----------|
| 备份失败 | 升级前必须成功创建备份，否则不继续 |
| 迁移失败 | 自动回滚到备份状态 |
| 下载中断 | 支持断点续传 |
| 文件损坏 | SHA256校验，失败则重新下载 |

### 10.2 用户体验

| 场景 | 处理 |
|------|------|
| 升级过程中关闭应用 | 下次启动检测并恢复 |
| 网络不稳定 | 提示用户确保网络稳定 |
| 磁盘空间不足 | 升级前检查，提前警告 |
| 升级时间过长 | 显示详细进度，避免用户焦虑 |

### 10.3 向后兼容

- 新版本必须能读取旧版本数据
- 迁移脚本必须幂等（可重复执行）
- 保留至少2个大版本的向后兼容


