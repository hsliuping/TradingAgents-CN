<template>
  <div class="config-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <el-icon><Setting /></el-icon>
          配置管理
        </h1>
        <p class="page-description">
          统一管理模型服务商、API 密钥、模型角色和调用限制
        </p>
      </div>
      <div class="header-right">
        <el-button v-if="!isCredentialHost && activeTab !== 'models'" type="success" @click="handleReloadConfig" :loading="reloadLoading">
          <el-icon><Refresh /></el-icon>
          重载配置
        </el-button>
      </div>
    </div>

    <el-row :gutter="24">
      <!-- 左侧：配置菜单 -->
      <el-col v-if="!isCredentialHost" :xs="24" :sm="6" :md="4" class="config-nav-column">
        <el-card class="config-menu" shadow="never">
          <el-menu
            :default-active="activeTab"
            @select="handleMenuSelect"
            class="config-nav"
          >
            <el-menu-item-group title="模型接入">
              <el-menu-item index="models">
                <el-icon><Cpu /></el-icon>
                <span>大模型配置</span>
              </el-menu-item>
            </el-menu-item-group>
            <el-menu-item-group v-if="!isCredentialHost" title="系统配置">
              <el-menu-item index="validation">
                <el-icon><CircleCheck /></el-icon>
                <span>配置验证</span>
              </el-menu-item>
              <el-menu-item index="datasource">
                <el-icon><DataBoard /></el-icon>
                <span>数据源配置</span>
              </el-menu-item>
              <el-menu-item index="database">
                <el-icon><Coin /></el-icon>
                <span>数据库配置</span>
              </el-menu-item>
              <el-menu-item index="system">
                <el-icon><Tools /></el-icon>
                <span>系统设置</span>
              </el-menu-item>
              <el-menu-item index="import-export">
                <el-icon><Download /></el-icon>
                <span>导入导出</span>
              </el-menu-item>
            </el-menu-item-group>
          </el-menu>
        </el-card>
      </el-col>

      <!-- 右侧：配置内容 -->
      <el-col :xs="24" :sm="isCredentialHost ? 24 : 18" :md="isCredentialHost ? 24 : 20" class="config-content-column">
        <!-- 配置验证 -->
        <div v-if="activeTab === 'validation'">
          <ConfigValidator />
        </div>

        <div v-if="isSecureModelTab" class="secure-model-settings">
          <AlphaGuardOperations models-only embedded />
        </div>

        <!-- 数据源配置 -->
        <el-card v-show="activeTab === 'datasource'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>数据源配置</h3>
              <div class="header-actions">
                <el-button @click="showMarketCategoryManagement">
                  <el-icon><Setting /></el-icon>
                  管理分类
                </el-button>
                <el-button type="primary" @click="showAddDataSourceDialog">
                  <el-icon><Plus /></el-icon>
                  添加数据源
                </el-button>
              </div>
            </div>
          </template>

          <div v-loading="dataSourceLoading" class="datasource-content">
            <!-- 数据源分组展示 -->
            <div v-if="dataSourceGroups.length > 0" class="datasource-groups">
              <SortableDataSourceList
                v-for="group in dataSourceGroups"
                :key="group.categoryId"
                :category-id="group.categoryId"
                :category-display-name="group.categoryDisplayName"
                :data-sources="group.dataSources"
                @update-order="handleUpdateDataSourceOrder"
                @edit-datasource="editDataSourceConfig"
                @manage-grouping="showDataSourceGroupingDialog"
                @manage-category="showMarketCategoryManagement"
                @add-datasource="showAddDataSourceDialog"
                @delete-datasource="deleteDataSourceConfig"
              />
            </div>

            <!-- 未分组的数据源 -->
            <div v-if="ungroupedDataSources.length > 0" class="ungrouped-section">
              <el-card shadow="never">
                <template #header>
                  <div class="section-header">
                    <h4>未分组数据源</h4>
                    <el-tag type="warning" size="small">{{ ungroupedDataSources.length }} 个</el-tag>
                  </div>
                </template>

                <div class="ungrouped-list">
                  <div
                    v-for="dataSource in ungroupedDataSources"
                    :key="dataSource.name"
                    class="ungrouped-item"
                  >
                    <div class="item-info">
                      <span class="item-name">{{ dataSource.display_name || dataSource.name }}</span>
                      <el-tag :type="dataSource.enabled ? 'success' : 'danger'" size="small">
                        {{ dataSource.enabled ? '启用' : '禁用' }}
                      </el-tag>
                      <span class="item-type">{{ dataSource.type }}</span>
                    </div>
                    <div class="item-actions">
                      <el-button size="small" @click="editDataSourceConfig(dataSource)">
                        编辑
                      </el-button>
                      <el-button size="small" @click="showDataSourceGroupingDialog(dataSource.name)">
                        分组
                      </el-button>
                      <el-button size="small" type="primary" @click="testDataSource(dataSource)">
                        测试
                      </el-button>
                      <el-button size="small" type="danger" @click="deleteDataSourceConfig(dataSource)">
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-card>
            </div>

            <!-- 空状态 -->
            <div v-if="dataSourceConfigs.length === 0" class="empty-state">
              <el-empty description="暂无数据源配置">
                <el-button type="primary" @click="showAddDataSourceDialog">
                  添加第一个数据源
                </el-button>
              </el-empty>
            </div>
          </div>
        </el-card>

        <!-- 数据库配置 -->
        <el-card v-show="activeTab === 'database'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>数据库配置</h3>
              <el-text type="info" size="small">系统核心数据库配置，仅支持编辑和测试</el-text>
            </div>
          </template>

          <div v-loading="databaseLoading">
            <el-table :data="databaseConfigs" style="width: 100%">
              <el-table-column prop="name" label="名称" width="150" />
              <el-table-column prop="type" label="类型" width="120" />
              <el-table-column prop="host" label="主机" width="150" />
              <el-table-column prop="port" label="端口" width="100" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.enabled ? 'success' : 'danger'">
                    {{ row.enabled ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    @click="invokeTableRowAction(databaseConfigs, row, editDatabaseConfig)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    @click="invokeTableRowAction(databaseConfigs, row, testDatabase)"
                  >
                    测试连接
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- 系统设置 -->
        <el-card v-show="activeTab === 'system'" class="config-content" shadow="never">
          <template #header>
            <h3>系统设置</h3>
          </template>

          <el-alert type="info" show-icon :closable="false"
            title="敏感/ENV来源项已锁定"
            description="来自环境变量或标记为敏感的设置将以只读方式展示。保存时仅提交可编辑项。"
            style="margin-bottom: 12px;"
          />

          <el-form :model="systemSettings" label-width="150px" v-loading="systemLoading">
            <!-- 基础设置 -->
            <el-divider content-position="left">基础设置</el-divider>

            <el-form-item label="数据供应商">
              <el-select
                v-model="systemSettings.default_provider"
                :disabled="!isEditable('default_provider')"
                placeholder="选择已启用的厂家"
                filterable
              >
                <el-option
                  v-for="provider in enabledProviders"
                  :key="provider.id"
                  :label="provider.display_name"
                  :value="provider.name"
                >
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>{{ provider.display_name }}</span>
                    <el-tag v-if="provider.is_active" type="success" size="small">已启用</el-tag>
                  </div>
                </el-option>
              </el-select>
              <div class="setting-description">从已配置的厂家中选择默认供应商</div>
            </el-form-item>

            <el-form-item label="快速分析模型">
              <el-select
                v-model="systemSettings.quick_analysis_model"
                :disabled="!isEditable('quick_analysis_model')"
                placeholder="选择快速分析模型"
                filterable
              >
                <el-option
                  v-for="model in availableModelsForProvider(systemSettings.default_provider)"
                  :key="`${model.provider}/${model.model_name}`"
                  :label="model.model_display_name || model.model_name"
                  :value="model.model_name"
                >
                  <div style="display: flex; flex-direction: column;">
                    <span>{{ model.model_display_name || model.model_name }}</span>
                    <span style="font-size: 12px; color: #909399;">{{ model.model_name }}</span>
                  </div>
                </el-option>
              </el-select>
              <div class="setting-description">用于市场分析、新闻分析、基本面分析、研究员等，响应速度快（推荐：qwen-turbo）</div>
            </el-form-item>

            <el-form-item label="深度决策模型">
              <el-select
                v-model="systemSettings.deep_analysis_model"
                :disabled="!isEditable('deep_analysis_model')"
                placeholder="选择深度决策模型"
                filterable
              >
                <el-option
                  v-for="model in availableModelsForProvider(systemSettings.default_provider)"
                  :key="`${model.provider}/${model.model_name}`"
                  :label="model.model_display_name || model.model_name"
                  :value="model.model_name"
                >
                  <div style="display: flex; flex-direction: column;">
                    <span>{{ model.model_display_name || model.model_name }}</span>
                    <span style="font-size: 12px; color: #909399;">{{ model.model_name }}</span>
                  </div>
                </el-option>
              </el-select>
              <div class="setting-description">用于研究管理者综合决策、风险管理者最终评估，推理能力强（推荐：qwen-max）</div>
            </el-form-item>

            <el-form-item label="启用成本跟踪">
              <el-switch v-model="systemSettings.enable_cost_tracking" :disabled="!isEditable('enable_cost_tracking')" />
            </el-form-item>

            <el-form-item label="成本警告阈值">
              <el-input-number v-model="systemSettings.cost_alert_threshold" :min="0" :step="10" :disabled="!isEditable('cost_alert_threshold')" />
              <span class="setting-description">元</span>
            </el-form-item>

            <el-form-item label="货币偏好">
              <el-select v-model="systemSettings.currency_preference" :disabled="!isEditable('currency_preference')">
                <el-option label="人民币 (CNY)" value="CNY" />
                <el-option label="美元 (USD)" value="USD" />
                <el-option label="欧元 (EUR)" value="EUR" />
              </el-select>
            </el-form-item>

            <el-form-item label="系统时区">
              <el-select v-model="systemSettings.app_timezone" :disabled="!isEditable('app_timezone')" filterable>
                <el-option label="Asia/Shanghai (UTC+8)" value="Asia/Shanghai" />
                <el-option label="UTC (UTC+0)" value="UTC" />
              </el-select>
              <div class="setting-description">用于后端存储与展示的统一时区；修改后新写入的时间将按此时区保存与返回。</div>
            </el-form-item>


            <!-- 性能设置 -->
            <el-divider content-position="left">性能设置</el-divider>

            <el-form-item label="分析超时时间">
              <el-input-number v-model="systemSettings.default_analysis_timeout" :min="60" :max="1800" :disabled="!isEditable('default_analysis_timeout')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="启用缓存">
              <el-switch v-model="systemSettings.enable_cache" :disabled="!isEditable('enable_cache')" />
            </el-form-item>

            <el-form-item label="缓存TTL">
              <el-input-number v-model="systemSettings.cache_ttl" :min="300" :max="86400" :disabled="!isEditable('cache_ttl')" />
              <span class="setting-description">秒</span>
            </el-form-item>


            <!-- 队列与 Worker -->
            <el-divider content-position="left">队列与 Worker</el-divider>

            <el-form-item label="Worker 心跳间隔">
              <el-input-number v-model="systemSettings.worker_heartbeat_interval_seconds" :min="1" :step="1" :disabled="!isEditable('worker_heartbeat_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="Worker 心跳上报周期；过小会增加负载，过大可能影响健康检查" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <el-form-item label="队列轮询间隔">
              <el-input-number v-model="systemSettings.queue_poll_interval_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('queue_poll_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="队列拉取任务的频率；过小增加Redis压力，过大影响任务延迟" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <el-form-item label="队列清理间隔">
              <el-input-number v-model="systemSettings.queue_cleanup_interval_seconds" :min="1" :step="1" :disabled="!isEditable('queue_cleanup_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="清理超时/失败任务的频率；建议≥60秒" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <!-- SSE 设置 -->
            <el-divider content-position="left">SSE</el-divider>

            <el-form-item label="SSE 轮询超时">
              <el-input-number v-model="systemSettings.sse_poll_timeout_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('sse_poll_timeout_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="任务进度SSE每次等待超时时间；过小会产生更多请求" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <el-form-item label="SSE 心跳间隔">
              <el-input-number v-model="systemSettings.sse_heartbeat_interval_seconds" :min="1" :step="1" :disabled="!isEditable('sse_heartbeat_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="SSE维持长连接的心跳事件发送周期" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <!-- TradingAgents（可选） -->
            <el-divider content-position="left">TradingAgents（可选）</el-divider>
            <el-form-item label="使用 App 缓存优先">
              <el-switch v-model="systemSettings.ta_use_app_cache" :disabled="!isEditable('ta_use_app_cache')" />
              <div class="setting-description">优先使用 App 缓存（stock_basic_info / market_quotes），未命中自动回退直连数据源</div>
            </el-form-item>


            <el-form-item label="港股最小请求间隔">
              <el-input-number v-model="systemSettings.ta_hk_min_request_interval_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('ta_hk_min_request_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="港股数据请求的最小间隔，用于节流" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <el-form-item label="港股请求超时">
              <el-input-number v-model="systemSettings.ta_hk_timeout_seconds" :min="1" :step="1" :disabled="!isEditable('ta_hk_timeout_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="港股最大重试">
              <el-input-number v-model="systemSettings.ta_hk_max_retries" :min="0" :step="1" :disabled="!isEditable('ta_hk_max_retries')" />
            </el-form-item>

            <el-form-item label="港股限速等待">
              <el-input-number v-model="systemSettings.ta_hk_rate_limit_wait_seconds" :min="1" :step="1" :disabled="!isEditable('ta_hk_rate_limit_wait_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="港股缓存TTL">
              <el-input-number v-model="systemSettings.ta_hk_cache_ttl_seconds" :min="10" :step="10" :disabled="!isEditable('ta_hk_cache_ttl_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="A股最小调用间隔">
              <el-input-number v-model="systemSettings.ta_china_min_api_interval_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('ta_china_min_api_interval_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="美股最小调用间隔">
              <el-input-number v-model="systemSettings.ta_us_min_api_interval_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('ta_us_min_api_interval_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="GoogleNews最小延时">
              <el-input-number v-model="systemSettings.ta_google_news_sleep_min_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('ta_google_news_sleep_min_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="GoogleNews最大延时">
              <el-input-number v-model="systemSettings.ta_google_news_sleep_max_seconds" :min="0.1" :step="0.1" :disabled="!isEditable('ta_google_news_sleep_max_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>


            <el-form-item label="任务流最大空闲">
              <el-input-number v-model="systemSettings.sse_task_max_idle_seconds" :min="10" :step="10" :disabled="!isEditable('sse_task_max_idle_seconds')" />
              <span class="setting-description">秒</span>
            </el-form-item>

            <el-form-item label="批次流轮询间隔">
              <el-input-number v-model="systemSettings.sse_batch_poll_interval_seconds" :min="0.5" :step="0.5" :disabled="!isEditable('sse_batch_poll_interval_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="批次进度刷新频率；过小将增加服务器负载" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <el-form-item label="批次流最大空闲">
              <el-input-number v-model="systemSettings.sse_batch_max_idle_seconds" :min="10" :step="10" :disabled="!isEditable('sse_batch_max_idle_seconds')" />
              <span class="setting-description">秒</span>
              <el-tooltip effect="dark" content="批次流在无事件情况下允许的最长空闲时间，超时将关闭连接" placement="top">
                <i class="el-icon-info" style="margin-left:8px; color:#909399;" />
              </el-tooltip>
            </el-form-item>

            <!-- 日志和监控 -->
            <el-divider content-position="left">日志和监控</el-divider>

            <el-form-item label="日志级别">
              <el-select v-model="systemSettings.log_level" :disabled="!isEditable('log_level')">
                <el-option label="DEBUG" value="DEBUG" />
                <el-option label="INFO" value="INFO" />
                <el-option label="WARNING" value="WARNING" />
                <el-option label="ERROR" value="ERROR" />
              </el-select>
            </el-form-item>

            <el-form-item label="启用监控">
              <el-switch v-model="systemSettings.enable_monitoring" :disabled="!isEditable('enable_monitoring')" />
            </el-form-item>

            <!-- 数据管理 -->
            <el-divider content-position="left">数据管理</el-divider>

            <el-form-item label="自动保存使用记录">
              <el-switch v-model="systemSettings.auto_save_usage" :disabled="!isEditable('auto_save_usage')" />
            </el-form-item>

            <el-form-item label="最大使用记录数">
              <el-input-number v-model="systemSettings.max_usage_records" :min="1000" :max="100000" :step="1000" :disabled="!isEditable('max_usage_records')" />
            </el-form-item>

            <el-form-item label="自动创建目录">
              <el-switch v-model="systemSettings.auto_create_dirs" :disabled="!isEditable('auto_create_dirs')" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveSystemSettings" :loading="systemSaving">
                保存设置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 导入导出 -->
        <el-card v-show="activeTab === 'import-export'" class="config-content" shadow="never">
          <template #header>
            <h3>导入导出</h3>
          </template>

          <div class="import-export-content">
            <el-row :gutter="24">
              <el-col :span="12">
                <h4>导出配置</h4>
                <p>将当前系统配置导出为JSON文件</p>
                <el-button type="primary" @click="exportConfig" :loading="exportLoading">
                  <el-icon><Download /></el-icon>
                  导出配置
                </el-button>
              </el-col>

              <el-col :span="12">
                <h4>导入配置</h4>
                <p>从JSON文件导入配置（将覆盖现有配置）</p>
                <el-upload
                  :before-upload="handleImportConfig"
                  :show-file-list="false"
                  accept=".json"
                >
                  <el-button type="success" :loading="importLoading">
                    <el-icon><Upload /></el-icon>
                    导入配置
                  </el-button>
                </el-upload>
              </el-col>
            </el-row>

            <el-divider />

            <div class="legacy-migration">
              <h4>传统配置迁移</h4>
              <p>将旧版本的配置文件迁移到新系统</p>
              <el-button type="warning" @click="migrateLegacyConfig" :loading="migrateLoading">
                <el-icon><Refresh /></el-icon>
                迁移传统配置
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据源配置对话框 -->
    <DataSourceConfigDialog
      v-model:visible="dataSourceDialogVisible"
      :config="currentDataSourceConfig"
      @success="handleDataSourceConfigSuccess"
    />

    <!-- 市场分类管理对话框 -->
    <el-dialog
      v-model="marketCategoryManagementVisible"
      title="市场分类管理"
      width="80%"
      :close-on-click-modal="false"
    >
      <MarketCategoryManagement @success="handleMarketCategorySuccess" />
    </el-dialog>

    <!-- 数据源分组对话框 -->
    <DataSourceGroupingDialog
      v-model:visible="dataSourceGroupingDialogVisible"
      :data-source-name="currentDataSourceName"
      @success="handleDataSourceGroupingSuccess"
    />

    <!-- 数据库配置对话框 -->
    <el-dialog
      v-model="databaseDialogVisible"
      title="编辑数据库配置"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="提示"
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        数据库配置是系统核心配置，配置名称和类型不可修改。如果配置中未填写用户名密码，系统将使用环境变量（.env文件）中的配置。
      </el-alert>

      <el-form :model="currentDatabaseConfig" label-width="120px">
        <el-form-item label="配置名称" required>
          <el-input
            v-model="currentDatabaseConfig.name"
            placeholder="请输入配置名称"
            disabled
          />
        </el-form-item>

        <el-form-item label="数据库类型" required>
          <el-select v-model="currentDatabaseConfig.type" placeholder="请选择数据库类型" disabled>
            <el-option label="MongoDB" value="mongodb" />
            <el-option label="Redis" value="redis" />
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="SQLite" value="sqlite" />
          </el-select>
        </el-form-item>

        <el-form-item label="主机地址" required>
          <el-input v-model="currentDatabaseConfig.host" placeholder="例如: localhost" />
        </el-form-item>

        <el-form-item label="端口号" required>
          <el-input-number
            v-model="currentDatabaseConfig.port"
            :min="1"
            :max="65535"
            placeholder="例如: 27017"
          />
        </el-form-item>

        <el-form-item label="用户名">
          <el-input v-model="currentDatabaseConfig.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="currentDatabaseConfig.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item label="数据库名">
          <el-input v-model="currentDatabaseConfig.database" placeholder="请输入数据库名" />
        </el-form-item>

        <el-form-item label="连接池大小">
          <el-input-number v-model="currentDatabaseConfig.pool_size" :min="1" :max="100" />
        </el-form-item>

        <el-form-item label="最大溢出连接">
          <el-input-number v-model="currentDatabaseConfig.max_overflow" :min="0" :max="200" />
        </el-form-item>

        <el-form-item label="启用状态">
          <el-switch v-model="currentDatabaseConfig.enabled" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="currentDatabaseConfig.description"
            type="textarea"
            :rows="3"
            placeholder="请输入配置描述"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="databaseDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDatabaseConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Setting,
  Cpu,
  DataBoard,
  Coin,
  Tools,
  Download,
  Upload,
  Plus,
  Refresh,
  CircleCheck
} from '@element-plus/icons-vue'

import {
  configApi,
  type LLMProvider,
  type LLMConfig,
  type DataSourceConfig,
  type DatabaseConfig,
  type MarketCategory,
  type DataSourceGrouping,
  type SettingMeta
} from '@/api/config'
import ConfigValidator from '@/components/ConfigValidator.vue'
import AlphaGuardOperations from '@/views/AlphaGuard/Operations.vue'
import DataSourceConfigDialog from './components/DataSourceConfigDialog.vue'
import MarketCategoryManagement from './components/MarketCategoryManagement.vue'
import DataSourceGroupingDialog from './components/DataSourceGroupingDialog.vue'
import SortableDataSourceList from './components/SortableDataSourceList.vue'
import { invokeTableRowAction } from '@/utils/tableRows'

const isCredentialHost =
  import.meta.env.VITE_ALPHAGUARD_CREDENTIAL_HOST === 'true'

// 响应式数据
const activeTab = ref('models')
const isSecureModelTab = computed(
  () => activeTab.value === 'models'
)
const providers = ref<LLMProvider[]>([])
const llmConfigs = ref<LLMConfig[]>([])
const dataSourceConfigs = ref<DataSourceConfig[]>([])
const databaseConfigs = ref<DatabaseConfig[]>([])
const systemSettings = ref<Record<string, any>>({})
const systemSettingsMeta = ref<Record<string, SettingMeta>>({})
const defaultDataSource = ref<string>('')

// 新增：数据源分组相关
const marketCategories = ref<MarketCategory[]>([])
const dataSourceGroupings = ref<DataSourceGrouping[]>([])
const dataSourceGroups = ref<any[]>([])
const ungroupedDataSources = ref<DataSourceConfig[]>([])

// 加载状态
const dataSourceLoading = ref(false)
const databaseLoading = ref(false)
const systemLoading = ref(false)
const systemSaving = ref(false)
const exportLoading = ref(false)
const importLoading = ref(false)
const migrateLoading = ref(false)
const reloadLoading = ref(false)

// 新增：数据源相关对话框
const dataSourceDialogVisible = ref(false)
const currentDataSourceConfig = ref<DataSourceConfig | null>(null)
const marketCategoryManagementVisible = ref(false)
const dataSourceGroupingDialogVisible = ref(false)
const currentDataSourceName = ref<string>('')

// 新增：数据库配置对话框
const databaseDialogVisible = ref(false)
const databaseDialogMode = ref<'add' | 'edit'>('add')
const currentDatabaseConfig = ref<Partial<DatabaseConfig>>({
  name: '',
  type: 'mongodb',
  host: 'localhost',
  port: 27017,
  username: '',
  password: '',
  database: '',
  connection_params: {},
  pool_size: 10,
  max_overflow: 20,
  enabled: true,
  description: ''
})

// 方法
const handleMenuSelect = (index: string) => {
  activeTab.value = index
  loadTabData(index)
}

const loadTabData = async (tab: string) => {
  if (tab === 'models') return
  switch (tab) {
    case 'datasource':
      await loadDataSourceConfigs()
      break
    case 'database':
      await loadDatabaseConfigs()
      break
    case 'system':
      // 系统设置需要加载厂家和大模型配置，用于模型选择下拉框
      await loadProviders()
      await loadLLMConfigs()
      await loadSystemSettings()
      break
  }
}

// 计算属性：获取已启用的厂家
const enabledProviders = computed(() => {
  return providers.value.filter(p => p.is_active)
})

// 函数：根据厂家获取可用的模型
const availableModelsForProvider = (providerId: string) => {
  if (!providerId) return []
  return sortLLMConfigsByNewest(
    llmConfigs.value.filter(
      config => config.provider === providerId && config.enabled
    )
  )
}

// 加载厂家列表
const loadProviders = async () => {
  try {
    const providerList = await configApi.getLLMProviders()
    providers.value = sortProvidersByNewest(providerList)
  } catch {
    ElMessage.error('加载厂家列表失败')
  }
}

const sortProvidersByNewest = (providerList: LLMProvider[]) => {
  const getTimestamp = (provider: LLMProvider) => {
    const timeValue = provider.created_at || provider.updated_at
    const timestamp = timeValue ? new Date(timeValue).getTime() : 0
    return Number.isNaN(timestamp) ? 0 : timestamp
  }

  return [...providerList].sort((a, b) => getTimestamp(b) - getTimestamp(a))
}

const sortLLMConfigsByNewest = (configs: LLMConfig[]) => {
  const getTimestamp = (config: LLMConfig) => {
    const timeValue = config.created_at || config.updated_at
    const timestamp = timeValue ? new Date(timeValue).getTime() : 0
    return Number.isNaN(timestamp) ? 0 : timestamp
  }

  return [...configs].sort((a, b) => getTimestamp(b) - getTimestamp(a))
}

const loadLLMConfigs = async () => {
  try {
    const configs = await configApi.getLLMConfigs()
    llmConfigs.value = sortLLMConfigsByNewest(configs)
  } catch {
    ElMessage.error('加载大模型配置失败')
  }
}

const loadDataSourceConfigs = async () => {
  dataSourceLoading.value = true
  try {
    const configs = await configApi.getDataSourceConfigs()
    dataSourceConfigs.value = configs

    // 获取默认数据源
    const systemConfig = await configApi.getSystemConfig()
    defaultDataSource.value = systemConfig.default_data_source || ''

    // 加载分组相关数据
    await loadMarketCategories()
    await loadDataSourceGroupings()
    buildDataSourceGroups()
  } catch (error) {
    ElMessage.error('加载数据源配置失败')
  } finally {
    dataSourceLoading.value = false
  }
}

// 加载市场分类
const loadMarketCategories = async () => {
  try {
    marketCategories.value = await configApi.getMarketCategories()
  } catch (error) {
    console.error('加载市场分类失败:', error)
  }
}

// 加载数据源分组关系
const loadDataSourceGroupings = async () => {
  try {
    dataSourceGroupings.value = await configApi.getDataSourceGroupings()
  } catch (error) {
    console.error('加载数据源分组关系失败:', error)
  }
}

// 构建数据源分组
const buildDataSourceGroups = () => {
  const groups: any[] = []
  const ungrouped: DataSourceConfig[] = []

  // 按分类分组
  marketCategories.value.forEach(category => {
    const categoryGroupings = dataSourceGroupings.value.filter(
      g => g.market_category_id === category.id
    )

    if (categoryGroupings.length > 0) {
      const dataSources = categoryGroupings
        .map(grouping => {
          const dataSource = dataSourceConfigs.value.find(
            ds => ds.name === grouping.data_source_name
          )
          if (dataSource) {
            return {
              ...dataSource,
              priority: grouping.priority,
              enabled: grouping.enabled
            }
          }
          return null
        })
        .filter(Boolean)
        .sort((a, b) => (b?.priority ?? 0) - (a?.priority ?? 0)) // 按优先级降序排列

      groups.push({
        categoryId: category.id,
        categoryDisplayName: category.display_name,
        dataSources
      })
    }
  })

  // 找出未分组的数据源
  const groupedDataSourceNames = new Set(
    dataSourceGroupings.value.map(g => g.data_source_name)
  )

  dataSourceConfigs.value.forEach(dataSource => {
    if (!groupedDataSourceNames.has(dataSource.name)) {
      ungrouped.push(dataSource)
    }
  })

  dataSourceGroups.value = groups
  ungroupedDataSources.value = ungrouped
}

const loadDatabaseConfigs = async () => {
  databaseLoading.value = true
  try {
    databaseConfigs.value = await configApi.getDatabaseConfigs()
  } catch (error) {
    ElMessage.error('加载数据库配置失败')
  } finally {
    databaseLoading.value = false
  }
}

const loadSystemSettings = async () => {
  systemLoading.value = true
  try {
    const [settings, meta] = await Promise.all([
      configApi.getSystemSettings(),
      configApi.getSystemSettingsMeta()
    ])
    // 确保有默认值
    systemSettings.value = {
      quick_analysis_model: 'qwen-turbo',
      deep_analysis_model: 'qwen-max',
      default_analysis_timeout: 300,
      enable_cache: true,
      cache_ttl: 3600,
      log_level: 'INFO',
      enable_monitoring: true,
      // 队列与 Worker 默认
      worker_heartbeat_interval_seconds: 30,
      queue_poll_interval_seconds: 1.0,
      queue_cleanup_interval_seconds: 60.0,
      // SSE 默认
      sse_poll_timeout_seconds: 1.0,
      sse_heartbeat_interval_seconds: 10,
      sse_task_max_idle_seconds: 300,
      sse_batch_poll_interval_seconds: 2.0,
      sse_batch_max_idle_seconds: 600,
      // TradingAgents（可选）默认
      ta_use_app_cache: false,
      ta_hk_min_request_interval_seconds: 2.0,
      ta_hk_timeout_seconds: 60,
      ta_hk_max_retries: 3,
      ta_hk_rate_limit_wait_seconds: 60,
      ta_hk_cache_ttl_seconds: 86400,
      ta_china_min_api_interval_seconds: 0.5,
      ta_us_min_api_interval_seconds: 1.0,
      ta_google_news_sleep_min_seconds: 2.0,
      ta_google_news_sleep_max_seconds: 6.0,
      app_timezone: 'Asia/Shanghai',

      ...settings
    }
    // 规整元数据为map
    const metaList = meta?.items || []
    systemSettingsMeta.value = Object.fromEntries(metaList.map((m: SettingMeta) => [m.key, m]))
  } catch (error) {
    ElMessage.error('加载系统设置失败')
  } finally {
    systemLoading.value = false
  }
}

// 数据源相关操作
const showAddDataSourceDialog = () => {
  currentDataSourceConfig.value = null
  dataSourceDialogVisible.value = true
}

const editDataSourceConfig = (config: DataSourceConfig) => {
  currentDataSourceConfig.value = config
  dataSourceDialogVisible.value = true
}

// 显示市场分类管理
const showMarketCategoryManagement = () => {
  marketCategoryManagementVisible.value = true
}

// 显示数据源分组对话框
const showDataSourceGroupingDialog = (dataSourceName: string) => {
  currentDataSourceName.value = dataSourceName
  dataSourceGroupingDialogVisible.value = true
}

// 处理数据源排序更新
const handleUpdateDataSourceOrder = async (categoryId: string, orderedItems: Array<{name: string, priority: number}>) => {
  try {
    await configApi.updateCategoryDataSourceOrder(categoryId, orderedItems)
    ElMessage.success('排序更新成功')
    // 重新加载数据
    await loadDataSourceGroupings()
    buildDataSourceGroups()
  } catch (error) {
    console.error('更新排序失败:', error)
    ElMessage.error('更新排序失败')
  }
}

// 数据源配置成功回调
const handleDataSourceConfigSuccess = () => {
  loadDataSourceConfigs()
}

// 市场分类管理成功回调
const handleMarketCategorySuccess = () => {
  loadMarketCategories()
  buildDataSourceGroups()
}

// 数据源分组成功回调
const handleDataSourceGroupingSuccess = () => {
  loadDataSourceGroupings()
  buildDataSourceGroups()
}

const testDataSource = async (config: DataSourceConfig) => {
  try {
    const result = await configApi.testConfig({
      config_type: 'datasource',
      config_data: config
    })

    if (result.success) {
      ElMessage.success('数据源连接测试成功')
    } else {
      ElMessage.error(`数据源连接测试失败: ${result.message}`)
    }
  } catch (error) {
    ElMessage.error('数据源连接测试失败')
  }
}

// 删除数据源配置
const deleteDataSourceConfig = async (config: DataSourceConfig) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据源 "${config.display_name || config.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    await configApi.deleteDataSourceConfig(config.name)
    ElMessage.success('数据源删除成功')
    await loadDataSourceConfigs()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除数据源失败:', error)
      ElMessage.error(error.message || '删除数据源失败')
    }
  }
}

// 数据库相关操作
const editDatabaseConfig = (config: DatabaseConfig) => {
  databaseDialogMode.value = 'edit'
  currentDatabaseConfig.value = { ...config }
  databaseDialogVisible.value = true
}

const saveDatabaseConfig = async () => {
  try {
    await configApi.updateDatabaseConfig(
      currentDatabaseConfig.value.name!,
      currentDatabaseConfig.value
    )
    ElMessage.success('数据库配置更新成功')
    databaseDialogVisible.value = false
    await loadDatabaseConfigs()
  } catch (error: any) {
    ElMessage.error(error.message || '保存数据库配置失败')
  }
}

const testDatabase = async (config: DatabaseConfig) => {
  try {
    console.log('🧪 测试数据库配置:', config)
    console.log('📋 配置名称:', config.name)
    console.log('📋 配置类型:', config.type)
    console.log('📋 主机地址:', config.host)
    console.log('📋 端口:', config.port)

    const result = await configApi.testDatabaseConfig(config.name)

    if (result.success) {
      ElMessage.success(`数据库连接测试成功`)
    } else {
      ElMessage.error(`数据库连接测试失败: ${result.message}`)
    }
  } catch (error: any) {
    console.error('❌ 数据库测试失败:', error)
    console.error('❌ 错误详情:', error.response?.data)
    ElMessage.error(error.response?.data?.detail || error.message || '数据库连接测试失败')
  }
}

// 配置重载
const handleReloadConfig = async () => {
  try {
    reloadLoading.value = true
    const response = await configApi.reloadConfig()

    if (response.success) {
      ElMessage.success({
        message: '配置重载成功！新配置已生效',
        duration: 3000
      })
    } else {
      ElMessage.warning({
        message: response.message || '配置重载失败',
        duration: 3000
      })
    }
  } catch (error: any) {
    console.error('配置重载失败:', error)
    ElMessage.error({
      message: error.response?.data?.detail || '配置重载失败',
      duration: 3000
    })
  } finally {
    reloadLoading.value = false
  }
}

// 系统设置相关操作
const isEditable = (key: string): boolean => {
  const meta = systemSettingsMeta.value[key]
  if (!meta) return true
  return !!meta.editable
}

const saveSystemSettings = async () => {
  systemSaving.value = true
  try {
    // 基本校验：这些数值需 > 0
    const positiveKeys: Array<{key: string; min: number}> = [
      { key: 'worker_heartbeat_interval_seconds', min: 1 },
      { key: 'queue_poll_interval_seconds', min: 0.000001 },
      { key: 'queue_cleanup_interval_seconds', min: 1 },
      { key: 'sse_poll_timeout_seconds', min: 0.000001 },
      { key: 'sse_heartbeat_interval_seconds', min: 1 },
      { key: 'sse_task_max_idle_seconds', min: 1 },
      { key: 'sse_batch_poll_interval_seconds', min: 0.000001 },
      { key: 'sse_batch_max_idle_seconds', min: 1 },
      // TradingAgents（可选）
      { key: 'ta_hk_min_request_interval_seconds', min: 0.000001 },
      { key: 'ta_hk_timeout_seconds', min: 1 },
      { key: 'ta_hk_max_retries', min: 0 },
      { key: 'ta_hk_rate_limit_wait_seconds', min: 1 },
      { key: 'ta_hk_cache_ttl_seconds', min: 1 },
      { key: 'ta_china_min_api_interval_seconds', min: 0.000001 },
      { key: 'ta_us_min_api_interval_seconds', min: 0.000001 },
      { key: 'ta_google_news_sleep_min_seconds', min: 0.000001 },
      { key: 'ta_google_news_sleep_max_seconds', min: 0.000001 },
    ]
    for (const { key, min } of positiveKeys) {
      const v = (systemSettings.value as any)[key]
      if (v !== undefined && v !== null && Number(v) <= min - Number.EPSILON && isEditable(key)) {
        ElMessage.error(`${key} 必须大于 ${min}`)
        systemSaving.value = false
        return
      }
    }
    // 额外：Google News 最大延时应大于最小延时
    const gMin = Number((systemSettings.value as any)['ta_google_news_sleep_min_seconds'])
    const gMax = Number((systemSettings.value as any)['ta_google_news_sleep_max_seconds'])
    if (!Number.isNaN(gMin) && !Number.isNaN(gMax) && isEditable('ta_google_news_sleep_max_seconds')) {
      if (gMax <= gMin) {
        ElMessage.error('ta_google_news_sleep_max_seconds 必须大于 ta_google_news_sleep_min_seconds')
        systemSaving.value = false
        return
      }
    }

    // 仅提交可编辑项
    const entries = Object.entries(systemSettings.value).filter(([k]) => isEditable(k))
    const payload = Object.fromEntries(entries)
    await configApi.updateSystemSettings(payload)
    ElMessage.success('系统设置保存成功')
  } catch (error) {
    ElMessage.error('系统设置保存失败')
  } finally {
    systemSaving.value = false
  }
}

// 导入导出相关操作
const exportConfig = async () => {
  exportLoading.value = true
  try {
    const result = await configApi.exportConfig()

    // 创建下载链接
    const blob = new Blob([JSON.stringify(result.data, null, 2)], {
      type: 'application/json'
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `tradingagents-config-${new Date().toISOString().split('T')[0]}.json`
    link.click()
    URL.revokeObjectURL(url)

    ElMessage.success('配置导出成功')
  } catch (error) {
    ElMessage.error('配置导出失败')
  } finally {
    exportLoading.value = false
  }
}

const handleImportConfig = async (file: File) => {
  importLoading.value = true
  try {
    const text = await file.text()
    const configData = JSON.parse(text)

    await ElMessageBox.confirm(
      '导入配置将覆盖现有配置，确定要继续吗？',
      '确认导入',
      { type: 'warning' }
    )

    await configApi.importConfig(configData)
    ElMessage.success('配置导入成功')

    // 重新加载当前标签页数据
    await loadTabData(activeTab.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('配置导入失败')
    }
  } finally {
    importLoading.value = false
  }

  return false // 阻止自动上传
}

const migrateLegacyConfig = async () => {
  migrateLoading.value = true
  try {
    await ElMessageBox.confirm(
      '迁移传统配置可能会覆盖现有配置，确定要继续吗？',
      '确认迁移',
      { type: 'warning' }
    )

    await configApi.migrateLegacyConfig()
    ElMessage.success('传统配置迁移成功')

    // 重新加载所有数据
    await loadTabData(activeTab.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('传统配置迁移失败')
    }
  } finally {
    migrateLoading.value = false
  }
}

// 监听供应商变化，自动清空不匹配的模型选择
watch(
  () => systemSettings.value.default_provider,
  (newProvider, oldProvider) => {
    if (newProvider !== oldProvider && newProvider) {
      const availableModels = availableModelsForProvider(newProvider)
      const quickModel = systemSettings.value.quick_analysis_model
      const deepModel = systemSettings.value.deep_analysis_model

      // 如果当前选择的快速分析模型不属于新供应商，清空
      if (quickModel && !availableModels.find(m => m.model_name === quickModel)) {
        systemSettings.value.quick_analysis_model = ''
      }

      // 如果当前选择的深度决策模型不属于新供应商，清空
      if (deepModel && !availableModels.find(m => m.model_name === deepModel)) {
        systemSettings.value.deep_analysis_model = ''
      }
    }
  }
)

onMounted(() => {
  loadTabData(activeTab.value)
})
</script>

<style lang="scss" scoped>
.config-management {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      flex: 1;

      .page-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 24px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        margin: 0 0 8px 0;
      }

      .page-description {
        margin: 0;
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }

    .header-right {
      display: flex;
      gap: 12px;
    }
  }

  .config-menu {
    .config-nav {
      border: none;
    }
  }

  .config-content-column,
  .secure-model-settings {
    min-width: 0;
  }

  .secure-model-settings {
    max-width: 100%;
    overflow: hidden;

    :deep(.el-table),
    :deep(.el-tabs),
    :deep(.el-tab-pane) {
      max-width: 100%;
      min-width: 0;
    }
  }

  .config-content {
    min-height: 500px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h3 {
        margin: 0;
      }

      .header-actions {
        display: flex;
        gap: 8px;
      }
    }

    .datasource-content {
      .datasource-groups {
        margin-bottom: 24px;
      }

      .ungrouped-section {
        margin-bottom: 24px;

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;

          h4 {
            margin: 0;
            color: #303133;
            font-size: 14px;
          }
        }

        .ungrouped-list {
          .ungrouped-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;

            &:last-child {
              border-bottom: none;
            }

            .item-info {
              flex: 1;
              display: flex;
              align-items: center;
              gap: 12px;

              .item-name {
                font-weight: 500;
                color: #303133;
              }

              .item-type {
                color: #909399;
                font-size: 12px;
              }
            }

            .item-actions {
              display: flex;
              gap: 8px;
            }
          }
        }
      }

      .empty-state {
        text-align: center;
        padding: 60px 20px;
      }
    }

    .setting-description {
      margin-left: 8px;
      font-size: 12px;
      color: var(--el-text-color-placeholder);
    }

    .import-export-content {
      h4 {
        margin: 0 0 8px 0;
        color: var(--el-text-color-primary);
      }

      p {
        margin: 0 0 16px 0;
        color: var(--el-text-color-regular);
        font-size: 14px;
      }

      .legacy-migration {
        margin-top: 24px;
      }
    }

  }

}
</style>
