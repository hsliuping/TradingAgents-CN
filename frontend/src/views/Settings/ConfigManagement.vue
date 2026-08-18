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
          管理系统配置、大模型、数据源等设置
        </p>
      </div>
      <div class="header-right">
        <el-button v-if="!isJdyunMode()" type="success" @click="handleReloadConfig" :loading="reloadLoading">
          <el-icon><Refresh /></el-icon>
          重载配置
        </el-button>
      </div>
    </div>

    <el-row :gutter="24">
      <!-- 左侧：配置菜单 -->
      <el-col :span="4">
        <el-card class="config-menu" shadow="never">
          <el-menu
            :default-active="activeTab"
            @select="handleMenuSelect"
            class="config-nav"
          >
            <!-- 京东云模式：只显示数据源配置 -->
            <template v-if="isJdyunMode()">
              <el-menu-item index="datasource">
                <el-icon><DataBoard /></el-icon>
                <span>数据源配置</span>
              </el-menu-item>
            </template>
            <!-- 非京东云模式：显示全部菜单 -->
            <template v-else>
              <el-menu-item index="providers">
                <el-icon><OfficeBuilding /></el-icon>
                <span>厂家管理</span>
              </el-menu-item>
              <el-menu-item index="model-catalog">
                <el-icon><Collection /></el-icon>
                <span>模型目录</span>
              </el-menu-item>
              <el-menu-item index="llm">
                <el-icon><Cpu /></el-icon>
                <span>大模型配置</span>
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
              <el-menu-item index="gateway">
                <el-icon><Connection /></el-icon>
                <span>Gateway 配置</span>
              </el-menu-item>
              <el-menu-item index="validation">
                <el-icon><CircleCheck /></el-icon>
                <span>配置验证</span>
              </el-menu-item>
              <!-- 隐藏的菜单项 -->
              <!-- <el-menu-item index="api-keys">
                <el-icon><Key /></el-icon>
                <span>API密钥状态</span>
              </el-menu-item> -->
              <!-- <el-menu-item index="import-export">
                <el-icon><Download /></el-icon>
                <span>导入导出</span>
              </el-menu-item> -->
            </template>
          </el-menu>
        </el-card>
      </el-col>

      <!-- 右侧：配置内容 -->
      <el-col :span="20">
        <!-- Gateway 配置（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'gateway'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>Gateway IM 平台配置</h3>
            </div>
          </template>

          <div v-loading="gatewayLoading">
            <el-alert
              title="说明"
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 20px"
            >
              配置 IM 平台（QQ Bot / 飞书 / 钉钉）的接入凭据。配置保存后适配器将自动热重载，无需重启服务。
            </el-alert>

            <!-- QQ Bot 配置 -->
            <h4 style="margin-bottom: 16px;">QQ Bot</h4>
            <el-form :model="gatewayQQConfig" label-width="140px" style="max-width: 600px">
              <el-form-item label="AppID" required>
                <el-input v-model="gatewayQQConfig.app_id" placeholder="在 QQ 机器人开发设置页获取" />
              </el-form-item>
              <el-form-item label="AppSecret" required>
                <el-input
                  v-model="gatewayQQConfig.app_secret"
                  placeholder="在 QQ 机器人开发设置页获取"
                  show-password
                />
              </el-form-item>
              <el-form-item label="连接模式" required>
                <el-radio-group v-model="gatewayQQConfig.connection_mode">
                  <el-radio value="websocket">WebSocket（推荐）</el-radio>
                  <el-radio value="webhook">Webhook</el-radio>
                </el-radio-group>
                <div class="form-tip">
                  <template v-if="gatewayQQConfig.connection_mode === 'websocket'">
                    主动连接 QQ 网关接收消息，<strong>无需公网 IP</strong>，适合本地开发和内网部署
                  </template>
                  <template v-else>
                    QQ 平台推送消息到你的服务器，<strong>需要公网可达的回调地址</strong>
                  </template>
                </div>
              </el-form-item>
              <el-form-item v-if="gatewayQQConfig.connection_mode === 'webhook'" label="Bot Secret（签名密钥）">
                <el-input
                  v-model="gatewayQQConfig.bot_secret"
                  placeholder="用于 Webhook 签名验证（Ed25519），可选"
                  show-password
                />
                <div class="form-tip">用于 Webhook 回调地址验证，不填则跳过签名校验</div>
              </el-form-item>
              <el-form-item label="启用">
                <el-switch v-model="gatewayQQConfig.enabled" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleSaveGatewayConfig('qq')" :loading="gatewaySaving">
                  保存配置
                </el-button>
                <el-button
                  @click="handleTestGatewayConnection('qq')"
                  :loading="gatewayTesting"
                  :disabled="!gatewayQQConfig.configured"
                >
                  测试连接
                </el-button>
                <el-tag v-if="gatewayQQConfig.configured" type="success" style="margin-left: 12px">已配置</el-tag>
                <el-tag v-else type="info" style="margin-left: 12px">未配置</el-tag>
              </el-form-item>
            </el-form>

            <el-divider />

            <!-- 飞书 Bot 配置 -->
            <h4 style="margin-bottom: 16px;">飞书 Bot</h4>
            <el-form :model="gatewayFeishuConfig" label-width="160px" style="max-width: 600px">
              <el-form-item label="App ID" required>
                <el-input v-model="gatewayFeishuConfig.app_id" placeholder="飞书开放平台应用的 App ID" />
              </el-form-item>
              <el-form-item label="App Secret" required>
                <el-input
                  v-model="gatewayFeishuConfig.app_secret"
                  placeholder="飞书开放平台应用的 App Secret"
                  show-password
                />
              </el-form-item>
              <el-form-item label="Verification Token">
                <el-input v-model="gatewayFeishuConfig.verification_token" placeholder="事件订阅验证 Token（可选）" />
                <div class="form-tip">飞书开放平台 → 应用 → 事件订阅 → Verification Token</div>
              </el-form-item>
              <el-form-item label="Encrypt Key">
                <el-input
                  v-model="gatewayFeishuConfig.encrypt_key"
                  placeholder="事件加密密钥（可选）"
                  show-password
                />
                <div class="form-tip">启用后飞书事件推送会加密，需要在飞书后台同时配置</div>
              </el-form-item>
              <el-form-item label="启用">
                <el-switch v-model="gatewayFeishuConfig.enabled" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleSaveGatewayConfig('feishu')" :loading="gatewaySaving">
                  保存配置
                </el-button>
                <el-button
                  @click="handleTestGatewayConnection('feishu')"
                  :loading="gatewayTesting"
                  :disabled="!gatewayFeishuConfig.configured"
                >
                  测试连接
                </el-button>
                <el-tag v-if="gatewayFeishuConfig.configured" type="success" style="margin-left: 12px">已配置</el-tag>
                <el-tag v-else type="info" style="margin-left: 12px">未配置</el-tag>
              </el-form-item>
            </el-form>

            <el-divider />

            <!-- 钉钉 Bot 配置 -->
            <h4 style="margin-bottom: 16px;">钉钉 Bot</h4>
            <el-form :model="gatewayDingtalkConfig" label-width="160px" style="max-width: 600px">
              <el-form-item label="AppKey" required>
                <el-input v-model="gatewayDingtalkConfig.app_key" placeholder="钉钉开放平台应用的 AppKey" />
              </el-form-item>
              <el-form-item label="AppSecret" required>
                <el-input
                  v-model="gatewayDingtalkConfig.app_secret"
                  placeholder="钉钉开放平台应用的 AppSecret"
                  show-password
                />
              </el-form-item>
              <el-form-item label="机器人编码 (Robot Code)">
                <el-input v-model="gatewayDingtalkConfig.robot_code" placeholder="用于主动发消息（可选）" />
                <div class="form-tip">钉钉开放平台 → 应用 → 机器人 → 机器人编码，主动发消息时必填</div>
              </el-form-item>
              <el-form-item label="启用">
                <el-switch v-model="gatewayDingtalkConfig.enabled" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleSaveGatewayConfig('dingtalk')" :loading="gatewaySaving">
                  保存配置
                </el-button>
                <el-button
                  @click="handleTestGatewayConnection('dingtalk')"
                  :loading="gatewayTesting"
                  :disabled="!gatewayDingtalkConfig.configured"
                >
                  测试连接
                </el-button>
                <el-tag v-if="gatewayDingtalkConfig.configured" type="success" style="margin-left: 12px">已配置</el-tag>
                <el-tag v-else type="info" style="margin-left: 12px">未配置</el-tag>
              </el-form-item>
            </el-form>
          </div>
        </el-card>

        <!-- 配置验证（京东云模式下隐藏） -->
        <div v-if="!isJdyunMode()" v-show="activeTab === 'validation'">
          <ConfigValidator />
        </div>

        <!-- 模型目录管理（京东云模式下隐藏） -->
        <div v-if="!isJdyunMode()" v-show="activeTab === 'model-catalog'">
          <ModelCatalogManagement />
        </div>

        <!-- 厂家管理（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'providers'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>大模型厂家管理</h3>
              <el-button type="primary" @click="showAddProviderDialog">
                <el-icon><Plus /></el-icon>
                添加厂家
              </el-button>
            </div>
          </template>

          <div v-loading="providersLoading">
            <el-table :data="sortedProviders" style="width: 100%">
              <el-table-column label="厂家信息" width="200">
                <template #default="{ row }">
                  <div class="provider-info">
                    <div class="provider-name">{{ row.display_name }}</div>
                    <div class="provider-id">{{ row.name }}</div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="API密钥" width="120">
                <template #default="{ row }">
                  <div class="api-key-status">
                    <el-tag
                      :type="row.extra_config?.has_api_key ? 'success' : 'danger'"
                      size="small"
                    >
                      {{ row.extra_config?.has_api_key ? '已配置' : '未配置' }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" />
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <div class="status-column">
                    <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                      {{ row.is_active ? '启用' : '禁用' }}
                    </el-tag>
                    <el-tag
                      v-if="row.extra_config?.has_api_key"
                      :type="row.extra_config?.source === 'environment' ? 'warning' : 'success'"
                      size="small"
                      class="key-source-tag"
                    >
                      {{ row.extra_config?.source === 'environment' ? 'ENV' : 'DB' }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="支持功能" width="200">
                <template #default="{ row }">
                  <div class="features">
                    <el-tag
                      v-for="feature in row.supported_features"
                      :key="feature"
                      size="small"
                      class="feature-tag"
                    >
                      {{ feature }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="280" fixed="right">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    @click.stop="editProvider(row)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    v-if="row.extra_config?.has_api_key"
                    size="small"
                    type="info"
                    @click.stop="testProviderAPI(row)"
                    :loading="testingProviders[row.id]"
                  >
                    测试
                  </el-button>
                  <el-button
                    size="small"
                    :type="row.is_active ? 'warning' : 'success'"
                    @click.stop="toggleProvider(row)"
                  >
                    {{ row.is_active ? '禁用' : '启用' }}
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    @click.stop="deleteProvider(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- 大模型配置（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'llm'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>大模型配置</h3>
              <div>
                <el-button type="success" plain @click="handleBatchImport" :loading="batchImporting">
                  <el-icon><Download /></el-icon>
                  一键导入
                </el-button>
                <el-button type="primary" @click="showAddLLMDialog">
                  <el-icon><Plus /></el-icon>
                  添加模型
                </el-button>
              </div>
            </div>
          </template>

          <div v-loading="llmLoading">
            <!-- 按厂家分组的卡片式布局 -->
            <div v-if="llmConfigGroups.length === 0" class="empty-state">
              <el-empty description="暂无大模型配置">
                <el-button type="primary" @click="showAddLLMDialog">
                  <el-icon><Plus /></el-icon>
                  添加第一个模型
                </el-button>
              </el-empty>
            </div>

            <div v-else class="provider-groups">
              <div
                v-for="group in llmConfigGroups"
                :key="group.provider"
                class="provider-group"
              >
                <!-- 厂家头部 -->
                <div class="provider-header">
                  <div class="provider-info">
                    <el-tag :type="getProviderTagType(group.provider)" size="large" class="provider-tag">
                      <el-icon><OfficeBuilding /></el-icon>
                      {{ group.display_name }}
                    </el-tag>
                    <span class="model-count">{{ group.models.length }} 个模型</span>
                    <el-tag
                      :type="group.is_active ? 'success' : 'danger'"
                      size="small"
                      class="status-tag"
                    >
                      {{ group.is_active ? '已启用' : '已禁用' }}
                    </el-tag>
                  </div>
                  <div class="provider-actions">
                    <el-button
                      size="small"
                      type="primary"
                      @click="addModelToProvider(group)"
                    >
                      <el-icon><Plus /></el-icon>
                      添加模型
                    </el-button>
                    <el-button
                      size="small"
                      :type="group.is_active ? 'warning' : 'success'"
                      @click="toggleProviderStatus(group)"
                    >
                      {{ group.is_active ? '禁用' : '启用' }}
                    </el-button>
                  </div>
                </div>

                <!-- 模型列表 - 表格式布局 -->
                <el-table :data="group.models" style="width: 100%" stripe>
                  <!-- 模型名称 -->
                  <el-table-column label="模型名称" width="200">
                    <template #default="{ row }">
                      <div class="model-name-cell">
                        <div class="model-display-name">
                          {{ row.model_display_name || row.model_name }}
                        </div>
                        <div v-if="row.model_display_name" class="model-code-text">{{ row.model_name }}</div>
                      </div>
                    </template>
                  </el-table-column>

                  <!-- 状态 -->
                  <el-table-column label="状态" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">
                        {{ row.enabled ? '启用' : '禁用' }}
                      </el-tag>
                    </template>
                  </el-table-column>

                  <!-- 基础配置 -->
                  <el-table-column label="基础配置" width="200">
                    <template #default="{ row }">
                      <div class="config-cell">
                        <div>Token: {{ row.max_tokens }}</div>
                        <div>温度: {{ row.temperature }} | 超时: {{ row.timeout }}s</div>
                      </div>
                    </template>
                  </el-table-column>

                  <!-- 定价 -->
                  <el-table-column label="定价" width="180">
                    <template #default="{ row }">
                      <div v-if="row.input_price_per_1k || row.output_price_per_1k" class="pricing-cell">
                        <div>输入: {{ formatPrice(row.input_price_per_1k) }} {{ row.currency || 'CNY' }}/1K</div>
                        <div>输出: {{ formatPrice(row.output_price_per_1k) }} {{ row.currency || 'CNY' }}/1K</div>
                      </div>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>

                  <!-- 模型能力 -->
                  <el-table-column label="模型能力" width="280">
                    <template #default="{ row }">
                      <div class="capability-cell">
                        <div v-if="row.capability_level" class="capability-row-item">
                          <span class="label">等级:</span>
                          <el-tag :type="getCapabilityLevelType(row.capability_level)" size="small">
                            {{ getCapabilityLevelText(row.capability_level) }}
                          </el-tag>
                        </div>
                        <div v-if="row.suitable_roles && row.suitable_roles.length > 0" class="capability-row-item">
                          <span class="label">角色:</span>
                          <el-tag
                            v-for="role in row.suitable_roles"
                            :key="role"
                            type="info"
                            size="small"
                            style="margin-right: 4px;"
                          >
                            {{ getRoleText(role) }}
                          </el-tag>
                        </div>
                        <div v-if="row.recommended_depths && row.recommended_depths.length > 0" class="capability-row-item">
                          <span class="label">深度:</span>
                          <el-tag
                            v-for="depth in row.recommended_depths"
                            :key="depth"
                            type="success"
                            size="small"
                            style="margin-right: 4px;"
                          >
                            {{ depth }}
                          </el-tag>
                        </div>
                      </div>
                    </template>
                  </el-table-column>

                  <!-- 操作 -->
                  <el-table-column label="操作" width="260" fixed="right">
                    <template #default="{ row }">
                      <el-button size="small" @click="editLLMConfig(row)">
                        编辑
                      </el-button>
                      <el-button
                        size="small"
                        type="primary"
                        @click="testLLMConfig(row)"
                      >
                        测试
                      </el-button>
                      <el-button
                        size="small"
                        :type="row.enabled ? 'warning' : 'success'"
                        @click="toggleLLMConfig(row)"
                      >
                        {{ row.enabled ? '禁用' : '启用' }}
                      </el-button>
                      <el-button
                        size="small"
                        type="danger"
                        @click="deleteLLMConfig(row)"
                      >
                        删除
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 数据源配置 -->
        <el-card v-show="activeTab === 'datasource'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>数据源配置</h3>
              <!-- 京东云模式下隐藏添加和管理分类按钮 -->
              <div class="header-actions">
                <el-button v-if="!isJdyunMode()" @click="showMarketCategoryManagement">
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

        <!-- 数据库配置（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'database'" class="config-content" shadow="never">
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
                  <el-button size="small" @click="editDatabaseConfig(row)">编辑</el-button>
                  <el-button size="small" type="primary" @click="testDatabase(row)">
                    测试连接
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>

        <!-- 系统设置（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'system'" class="config-content" shadow="never">
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

            <el-form-item label="快速分析模型">
              <el-select
                v-model="systemSettings.quick_analysis_model_config_id"
                :disabled="!isEditable('quick_analysis_model')"
                placeholder="选择快速分析模型"
                filterable
              >
                <el-option-group
                  v-for="group in groupedAvailableModels"
                  :key="group.provider"
                  :label="group.providerLabel"
                >
                  <el-option
                    v-for="model in group.models"
                    :key="model.config_id || `${model.provider}/${model.model_name}`"
                    :label="formatModelSelectionLabel(model)"
                    :value="model.config_id"
                  >
                    <div style="display: flex; flex-direction: column;">
                      <span>{{ formatModelSelectionLabel(model) }}</span>
                      <span style="font-size: 12px; color: #909399;">{{ formatModelSelectionMeta(model) }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <div class="setting-description">用于市场分析、新闻分析、基本面分析、研究员等，响应速度快。可从所有已启用供应商的模型中选择</div>
            </el-form-item>

            <el-form-item label="深度决策模型">
              <el-select
                v-model="systemSettings.deep_analysis_model_config_id"
                :disabled="!isEditable('deep_analysis_model')"
                placeholder="选择深度决策模型"
                filterable
              >
                <el-option-group
                  v-for="group in groupedAvailableModels"
                  :key="group.provider"
                  :label="group.providerLabel"
                >
                  <el-option
                    v-for="model in group.models"
                    :key="model.config_id || `${model.provider}/${model.model_name}`"
                    :label="formatModelSelectionLabel(model)"
                    :value="model.config_id"
                  >
                    <div style="display: flex; flex-direction: column;">
                      <span>{{ formatModelSelectionLabel(model) }}</span>
                      <span style="font-size: 12px; color: #909399;">{{ formatModelSelectionMeta(model) }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <div class="setting-description">用于研究整合员综合决策、风险评估师最终评估，推理能力强。可从所有已启用供应商的模型中选择</div>
            </el-form-item>

            <el-form-item label="深度推理模型">
              <el-select
                v-model="systemSettings.deep_reasoning_model_config_id"
                :disabled="!isEditable('deep_reasoning_model')"
                placeholder="可选，用于强推理场景"
                filterable
                clearable
              >
                <el-option-group
                  v-for="group in groupedAvailableModels"
                  :key="group.provider"
                  :label="group.providerLabel"
                >
                  <el-option
                    v-for="model in group.models"
                    :key="model.config_id || `${model.provider}/${model.model_name}`"
                    :label="formatModelSelectionLabel(model)"
                    :value="model.config_id"
                  >
                    <div style="display: flex; flex-direction: column;">
                      <span>{{ formatModelSelectionLabel(model) }}</span>
                      <span style="font-size: 12px; color: #909399;">{{ formatModelSelectionMeta(model) }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <div class="setting-description">用于智能助手规划、策略生成等强推理场景。未配置时使用深度决策模型，可从所有已启用供应商的模型中选择</div>
            </el-form-item>

            <el-form-item label="编程模型">
              <el-select
                v-model="systemSettings.coding_model_config_id"
                :disabled="!isEditable('coding_model')"
                placeholder="可选，用于策略 DSL 生成"
                filterable
                clearable
              >
                <el-option-group
                  v-for="group in groupedAvailableModels"
                  :key="group.provider"
                  :label="group.providerLabel"
                >
                  <el-option
                    v-for="model in group.models"
                    :key="model.config_id || `${model.provider}/${model.model_name}`"
                    :label="formatModelSelectionLabel(model)"
                    :value="model.config_id"
                  >
                    <div style="display: flex; flex-direction: column;">
                      <span>{{ formatModelSelectionLabel(model) }}</span>
                      <span style="font-size: 12px; color: #909399;">{{ formatModelSelectionMeta(model) }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <div class="setting-description">用于策略 DSL 生成，擅长 JSON 输出。未配置时使用深度推理/深度决策模型，可从所有已启用供应商的模型中选择</div>
            </el-form-item>

            <!-- 🔥 新增：默认 Embedding 模型配置 -->
            <el-form-item label="默认 Embedding 模型">
              <el-select
                v-model="systemSettings.default_embedding_model"
                :disabled="!isEditable('default_embedding_model')"
                placeholder="选择默认 Embedding 模型"
                filterable
                clearable
              >
                <el-option-group
                  v-for="provider in embeddingProviders"
                  :key="provider.name"
                  :label="provider.display_name"
                >
                  <el-option
                    v-for="model in getEmbeddingModelsForProvider(provider.name)"
                    :key="`${provider.name}/${model}`"
                    :label="formatEmbeddingSelectionLabel(provider, model)"
                    :value="`${provider.name}:${model}`"
                  >
                    <div style="display: flex; flex-direction: column;">
                      <span>{{ formatEmbeddingSelectionLabel(provider, model) }}</span>
                      <span style="font-size: 12px; color: #909399;">{{ formatEmbeddingSelectionMeta(provider, model) }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <div class="setting-description">
                用于文本向量化和记忆功能，从所有支持 embedding 的厂商中选择（格式：厂商:模型名，如：dashscope:text-embedding-v3）
                <!-- 向量迁移功能已废弃：向量存储已从 Qdrant 迁移到 MongoDB，不再需要 Qdrant 迁移 -->
                <!--
                <el-button
                  type="warning"
                  size="small"
                  @click="openMigrationDialog"
                  style="margin-left: 12px;"
                >
                  迁移向量数据
                </el-button>
                -->
              </div>
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

            <!-- 回测 DSL 生成 -->
            <el-divider content-position="left">回测策略生成</el-divider>
            <el-form-item label="生成时校验 DSL">
              <el-switch v-model="systemSettings.dsl_validate_on_generate" :disabled="!isEditable('dsl_validate_on_generate')" />
              <span class="setting-description">启用 L2 语义校验，失败时自动让 LLM 修正</span>
            </el-form-item>
            <el-form-item label="执行校验">
              <el-switch v-model="systemSettings.dsl_run_execution_check" :disabled="!isEditable('dsl_run_execution_check')" />
              <span class="setting-description">启用 L3 轻量回测校验（需回测服务已启动）</span>
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

            <!-- 代理配置 -->
            <el-divider content-position="left">网络代理</el-divider>

            <el-alert
              type="info"
              show-icon
              :closable="false"
              style="margin-bottom: 16px;"
            >
              <template #title>
                <span>代理用于访问需要翻墙的数据源（如 Yahoo Finance、Google News 等）</span>
              </template>
              <template #default>
                <div style="font-size: 12px; color: #909399;">
                  国内数据源（东方财富、新浪、腾讯等）已自动加入 NO_PROXY 列表，无需代理。
                  修改后需要<strong>重启后端服务</strong>才能生效。
                </div>
              </template>
            </el-alert>

            <el-form-item label="启用代理">
              <el-switch
                v-model="systemSettings.proxy_enabled"
                :disabled="!isEditable('proxy_enabled')"
                active-text="开启"
                inactive-text="关闭"
              />
              <div class="setting-description">
                控制是否使用代理访问国外数据源。关闭后，所有请求将直连（可能无法访问 Yahoo Finance、Google News 等）
              </div>
            </el-form-item>

            <el-form-item label="HTTP 代理">
              <el-input
                v-model="systemSettings.http_proxy"
                :disabled="!isEditable('http_proxy')"
                placeholder="例如: 127.0.0.1:7890 或 http://127.0.0.1:7890"
                clearable
              />
              <div class="setting-description">用于 HTTP 请求的代理服务器地址，可省略 http:// 前缀</div>
            </el-form-item>

            <el-form-item label="HTTPS 代理">
              <el-input
                v-model="systemSettings.https_proxy"
                :disabled="!isEditable('https_proxy')"
                placeholder="例如: 127.0.0.1:7890 或 http://127.0.0.1:7890"
                clearable
              />
              <div class="setting-description">用于 HTTPS 请求的代理服务器地址（通常与 HTTP 代理相同），可省略 http:// 前缀</div>
            </el-form-item>

            <el-form-item label="不使用代理">
              <el-input
                v-model="systemSettings.no_proxy"
                type="textarea"
                :rows="3"
                :disabled="!isEditable('no_proxy')"
                placeholder="localhost,127.0.0.1,eastmoney.com,..."
              />
              <div class="setting-description">
                不使用代理的域名列表，用逗号分隔。国内数据源已预设，可根据需要添加其他域名。
              </div>
            </el-form-item>

            <el-form-item label="代理测试">
              <div style="display: flex; gap: 12px; align-items: center;">
                <el-button
                  type="info"
                  @click="testProxyConnection"
                  :loading="proxyTesting"
                  :disabled="!systemSettings.http_proxy && !systemSettings.https_proxy"
                >
                  <el-icon><Connection /></el-icon>
                  测试代理连接
                </el-button>
                <span v-if="proxyTestResult" :class="['proxy-test-result', proxyTestResult.success ? 'success' : 'error']">
                  {{ proxyTestResult.message }}
                </span>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveSystemSettings" :loading="systemSaving">
                保存设置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- API密钥状态（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'api-keys'" class="config-content" shadow="never">
          <template #header>
            <div class="card-header">
              <h3>API密钥状态</h3>
              <el-button @click="loadProviders" :loading="providersLoading">
                <el-icon><Refresh /></el-icon>
                刷新状态
              </el-button>
            </div>
          </template>

          <div class="api-keys-content" v-loading="providersLoading">
            <el-row :gutter="24">
              <el-col :span="12">
                <h4>🔑 AI厂家密钥状态</h4>
                <div
                  v-for="provider in providers"
                  :key="provider.id"
                  class="api-key-item"
                >
                  <el-icon><Key /></el-icon>
                  <span class="key-name">{{ provider.display_name }}</span>
                  <el-tag
                    :type="getKeyStatusType(provider)"
                    size="small"
                  >
                    {{ getKeyStatusText(provider) }}
                  </el-tag>
                  <el-button
                    v-if="!provider.extra_config?.has_api_key"
                    size="small"
                    type="primary"
                    link
                    @click="editProvider(provider)"
                  >
                    配置
                  </el-button>
                </div>

                <div v-if="providers.length === 0" class="empty-state">
                  <el-empty description="暂无厂家配置">
                    <el-button type="primary" @click="activeTab = 'providers'">
                      添加厂家
                    </el-button>
                  </el-empty>
                </div>
              </el-col>

              <el-col :span="12">
                <h4>📊 配置统计</h4>
                <div class="stats-grid">
                  <div class="stat-item">
                    <div class="stat-number">{{ providers.length }}</div>
                    <div class="stat-label">总厂家数</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ configuredProvidersCount }}</div>
                    <div class="stat-label">已配置密钥</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ activeProvidersCount }}</div>
                    <div class="stat-label">启用厂家</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-number">{{ llmConfigs.length }}</div>
                    <div class="stat-label">配置模型</div>
                  </div>
                </div>
              </el-col>
            </el-row>

            <el-divider />

            <div class="api-key-help">
              <h4>💡 配置说明</h4>
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-card shadow="never" class="help-card">
                    <h5>如何配置API密钥？</h5>
                    <ol>
                      <li>在"厂家管理"中添加AI厂家</li>
                      <li>编辑厂家信息，填入API密钥</li>
                      <li>在"大模型配置"中选择厂家和模型</li>
                      <li>系统自动使用厂家的API密钥</li>
                    </ol>
                  </el-card>
                </el-col>
                <el-col :span="8">
                  <el-card shadow="never" class="help-card">
                    <h5>🔄 从环境变量迁移</h5>
                    <p>如果你之前在 .env 文件中配置了API密钥，可以一键迁移到厂家管理：</p>
                    <el-button
                      type="primary"
                      @click="migrateFromEnv"
                      :loading="migrateLoading"
                      size="small"
                    >
                      迁移环境变量
                    </el-button>
                  </el-card>
                </el-col>
                <el-col :span="8">
                  <el-alert
                    title="🔒 安全提示"
                    type="warning"
                    description="敏感密钥通过环境变量/运维配置注入，后端响应已统一脱敏；请勿在界面或导出文件中保存真实密钥。"
                    show-icon
                    :closable="false"
                  />
                </el-col>
              </el-row>
            </div>
          </div>
        </el-card>

        <!-- 导入导出（京东云模式下隐藏） -->
        <el-card v-if="!isJdyunMode()" v-show="activeTab === 'import-export'" class="config-content" shadow="never">
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

    <!-- 厂家管理对话框（京东云模式下隐藏） -->
    <ProviderDialog
      v-if="!isJdyunMode()"
      v-model:visible="providerDialogVisible"
      :provider="currentProvider"
      @success="handleProviderSuccess"
    />

    <!-- 大模型配置对话框（京东云模式下隐藏） -->
    <LLMConfigDialog
      v-if="!isJdyunMode()"
      v-model:visible="llmDialogVisible"
      :config="currentLLMConfig"
      @success="handleLLMConfigSuccess"
    />

    <!-- 一键导入对话框 -->
    <el-dialog v-model="batchImportDialogVisible" title="一键导入大模型配置" width="480px">
      <p style="margin-bottom: 16px; color: var(--el-text-color-regular); font-size: 14px;">
        选择要导入的厂家，系统将自动从模型目录中导入该厂家下所有模型配置。
      </p>
      <el-checkbox-group v-model="selectedImportProviders">
        <div v-for="p in importableProviders" :key="p.name" style="margin-bottom: 8px;">
          <el-checkbox :label="p.name" :value="p.name">
            {{ p.display_name }}
            <el-tag v-if="p.extra_config?.has_api_key" size="small" type="success" style="margin-left: 4px;">已配置密钥</el-tag>
            <el-tag v-else size="small" type="info" style="margin-left: 4px;">未配置密钥</el-tag>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <div v-if="importableProviders.length === 0" style="text-align: center; padding: 20px; color: var(--el-text-color-secondary);">
        暂无已启用的厂家
      </div>
      <template #footer>
        <el-button @click="batchImportDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchImporting" :disabled="selectedImportProviders.length === 0" @click="confirmBatchImport">
          导入选中厂家
        </el-button>
      </template>
    </el-dialog>

    <!-- 数据源配置对话框 -->
    <DataSourceConfigDialog
      v-model:visible="dataSourceDialogVisible"
      :config="currentDataSourceConfig"
      @success="handleDataSourceConfigSuccess"
    />

    <!-- 市场分类管理对话框（京东云模式下隐藏） -->
    <el-dialog
      v-if="!isJdyunMode()"
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

    <!-- 数据库配置对话框（京东云模式下隐藏） -->
    <el-dialog
      v-if="!isJdyunMode()"
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

    <!-- 向量迁移对话框已废弃：向量存储已从 Qdrant 迁移到 MongoDB -->
    <!--
    <el-dialog
      v-if="!isJdyunMode()"
      v-model="migrationDialogVisible"
      title="迁移向量数据"
      width="780px"
      :close-on-click-modal="false"
      @opened="loadMigrationData"
    >
      <el-alert
        title="说明"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <template #default>
          <div>
            更换 Embedding 模型（当前：<strong>{{ migrationCurrentModel }}</strong>）后，旧的向量数据需要用新模型重新生成。
            状态标记：<el-tag type="warning" size="small">待迁移</el-tag> 从未迁移，
            <el-tag type="success" size="small">已迁移</el-tag> 与当前模型一致，
            <el-tag type="danger" size="small">已过期</el-tag> 迁移过但模型已变。
          </div>
        </template>
      </el-alert>

      <div style="margin-bottom: 12px;">
        <el-button
          type="primary"
          :disabled="pendingMigrations.length === 0"
          :loading="migrationLoading"
          @click="migrateAllPending"
        >
          一键迁移全部（{{ pendingMigrations.length }} 个待迁移）
        </el-button>
      </div>

      <el-table :data="allCollections" v-loading="migrationLoading" max-height="400px" size="small">
        <el-table-column prop="name" label="Collection" min-width="240" show-overflow-tooltip />
        <el-table-column label="来源" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.source === 'main' ? 'primary' : 'info'" size="small">
              {{ row.source === 'main' ? '主存储' : 'mem0' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据" width="90" align="center">
          <template #default="{ row }">
            {{ row.point_count }} 条
          </template>
        </el-table-column>
        <el-table-column prop="dimensions" label="维度" width="70" align="center" />
        <el-table-column label="迁移状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.migration_status === 'pending'" type="warning" size="small">待迁移</el-tag>
            <el-tag v-else-if="row.migration_status === 'migrated'" type="success" size="small">已迁移</el-tag>
            <el-tag v-else-if="row.migration_status === 'outdated'" type="danger" size="small">已过期</el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.point_count > 0 && row.migration_status !== 'migrated'"
              size="small"
              type="warning"
              :loading="migratingCollections[row.name]"
              @click="migrateOne(row)"
            >
              迁移
            </el-button>
            <template v-else-if="row.point_count === 0">
              <span style="color: #909399; font-size: 12px;">空数据</span>
              <el-button
                size="small"
                type="danger"
                text
                :loading="migratingCollections[row.name]"
                @click="deleteCollection(row)"
              >
                删除
              </el-button>
            </template>
            <el-tag v-else type="success" size="small">已完成</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="migrationResults.length > 0" style="margin-top: 16px;">
        <el-descriptions
          v-for="(r, i) in migrationResults"
          :key="i"
          :column="2"
          border
          size="small"
          style="margin-bottom: 8px;"
        >
          <el-descriptions-item label="Collection">{{ r.collection_name || r.source_collection }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="r.success ? 'success' : 'danger'" size="small">
              {{ r.success ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="处理">{{ r.total_seen }}</el-descriptions-item>
          <el-descriptions-item label="迁移">{{ r.migrated }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <template #footer>
        <el-button @click="migrationDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isJdyunMode } from '@/utils/config'
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
  Key,
  OfficeBuilding,
  CircleCheck,
  Collection,
  Connection
} from '@element-plus/icons-vue'

import {
  configApi,
  type LLMProvider,
  type LLMConfig,
  type DataSourceConfig,
  type DatabaseConfig,
  type MarketCategory,
  type DataSourceGrouping,
  type SettingMeta,
  type GatewayConfig,
  type GatewayConfigRequest
} from '@/api/config'
import ConfigValidator from '@/components/ConfigValidator.vue'
import LLMConfigDialog from './components/LLMConfigDialog.vue'
import ProviderDialog from './components/ProviderDialog.vue'
import ModelCatalogManagement from './components/ModelCatalogManagement.vue'
import DataSourceConfigDialog from './components/DataSourceConfigDialog.vue'
import MarketCategoryManagement from './components/MarketCategoryManagement.vue'
import DataSourceGroupingDialog from './components/DataSourceGroupingDialog.vue'
import SortableDataSourceList from './components/SortableDataSourceList.vue'

// 响应式数据
const router = useRouter()
const activeTab = ref('providers')
const providers = ref<LLMProvider[]>([])
const llmConfigs = ref<LLMConfig[]>([])
const llmConfigGroups = ref<any[]>([])
const dataSourceConfigs = ref<DataSourceConfig[]>([])
const databaseConfigs = ref<DatabaseConfig[]>([])
const systemSettings = ref<Record<string, any>>({})
const systemSettingsMeta = ref<Record<string, SettingMeta>>({})
const defaultLLM = ref<string>('')

// 🔥 新增：用于 Embedding 模型切换提醒
const originalEmbeddingModel = ref<string>('')

// 厂家信息映射
const providerInfoMap = ref<Record<string, any>>({})
const defaultDataSource = ref<string>('')

// 新增：数据源分组相关
const marketCategories = ref<MarketCategory[]>([])
const dataSourceGroupings = ref<DataSourceGrouping[]>([])
const dataSourceGroups = ref<any[]>([])
const ungroupedDataSources = ref<DataSourceConfig[]>([])

// 加载状态
const providersLoading = ref(false)
const llmLoading = ref(false)
const dataSourceLoading = ref(false)
const databaseLoading = ref(false)
const systemLoading = ref(false)
const systemSaving = ref(false)
const exportLoading = ref(false)
const importLoading = ref(false)
const migrateLoading = ref(false)
const reloadLoading = ref(false)
const proxyTesting = ref(false)
const proxyTestResult = ref<{ success: boolean; message: string } | null>(null)

// 对话框状态
const providerDialogVisible = ref(false)
const currentProvider = ref<Partial<LLMProvider>>({})

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

// Gateway 配置
const gatewayLoading = ref(false)
const gatewaySaving = ref(false)
const gatewayTesting = ref(false)
const gatewayQQConfig = ref<GatewayConfig>({
  platform: 'qq',
  app_id: '',
  app_secret: '',
  bot_secret: '',
  connection_mode: 'websocket',
  enabled: false,
  configured: false,
})
const gatewayFeishuConfig = ref<GatewayConfig>({
  platform: 'feishu',
  app_id: '',
  app_secret: '',
  bot_secret: '',
  connection_mode: 'webhook',
  enabled: false,
  configured: false,
  verification_token: '',
  encrypt_key: '',
})
const gatewayDingtalkConfig = ref<GatewayConfig>({
  platform: 'dingtalk',
  app_id: '',
  app_secret: '',
  bot_secret: '',
  connection_mode: 'webhook',
  enabled: false,
  configured: false,
  app_key: '',
  robot_code: '',
})

// 测试状态
const testingProviders = ref<Record<string, boolean>>({})

// 方法
const handleMenuSelect = (index: string) => {
  activeTab.value = index
  loadTabData(index)
}

const loadTabData = async (tab: string) => {
  switch (tab) {
    case 'providers':
      await loadProviders()
      break
    case 'llm':
      await loadLLMConfigs()
      break
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
      await loadEmbeddingProviders()  // 🔥 新增：加载 Embedding 厂家列表
      break
    case 'gateway':
      await Promise.all([
        fetchGatewayConfig('qq'),
        fetchGatewayConfig('feishu'),
        fetchGatewayConfig('dingtalk'),
      ])
      break
    case 'api-keys':
      await loadProviders()
      await loadLLMConfigs()
      break
  }
}

// 🔥 计算属性：按启用状态排序的厂家列表（启用的在上面，禁用的在下面）
const sortedProviders = computed(() => {
  return [...providers.value].sort((a, b) => {
    // 启用的排在前面（is_active=true 返回 -1）
    if (a.is_active && !b.is_active) return -1
    if (!a.is_active && b.is_active) return 1
    // 如果状态相同，按名称排序
    return (a.display_name || a.name).localeCompare(b.display_name || b.name)
  })
})

const allEnabledModels = computed(() => {
  return llmConfigs.value.filter(config => config.enabled)
})

const selectableEnabledModels = computed(() => {
  return allEnabledModels.value.filter(
    (config): config is LLMConfig & { config_id: string } => typeof config.config_id === 'string' && config.config_id.trim().length > 0
  )
})

const groupedAvailableModels = computed(() => {
  const groups = new Map<string, { provider: string; providerLabel: string; models: Array<LLMConfig & { config_id: string }> }>()

  for (const model of selectableEnabledModels.value) {
    const providerLabel = providerInfoMap.value[model.provider]?.display_name || model.provider_name || model.provider
    const existingGroup = groups.get(model.provider)

    if (existingGroup) {
      existingGroup.models.push(model)
      continue
    }

    groups.set(model.provider, {
      provider: model.provider,
      providerLabel,
      models: [model]
    })
  }

  return Array.from(groups.values()).map(group => ({
    ...group,
    models: [...group.models].sort((left, right) => {
      const leftName = left.model_display_name || left.model_name
      const rightName = right.model_display_name || right.model_name
      return leftName.localeCompare(rightName)
    })
  }))
})

const getProviderDisplayLabel = (providerName?: string, fallbackName?: string) => {
  const normalizedProvider = String(providerName || '').trim()
  if (!normalizedProvider) {
    return String(fallbackName || '').trim()
  }

  return providerInfoMap.value[normalizedProvider]?.display_name || fallbackName || normalizedProvider
}

const formatModelSelectionLabel = (model: Pick<LLMConfig, 'provider' | 'provider_name' | 'model_display_name' | 'model_name'>) => {
  const providerLabel = getProviderDisplayLabel(model.provider, model.provider_name)
  const modelLabel = model.model_display_name || model.model_name
  return providerLabel ? `${providerLabel} / ${modelLabel}` : modelLabel
}

const formatModelSelectionMeta = (model: Pick<LLMConfig, 'provider' | 'model_name'>) => {
  const providerName = String(model.provider || '').trim()
  return providerName ? `${providerName} / ${model.model_name}` : model.model_name
}

const formatEmbeddingSelectionLabel = (provider: { name: string; display_name: string }, model: string) => {
  const providerLabel = provider.display_name || provider.name
  return `${providerLabel} / ${model}`
}

const formatEmbeddingSelectionMeta = (provider: { name: string }, model: string) => {
  return `${provider.name}:${model}`
}

const modelSettingPairs = [
  { modelKey: 'quick_analysis_model', configIdKey: 'quick_analysis_model_config_id' },
  { modelKey: 'deep_analysis_model', configIdKey: 'deep_analysis_model_config_id' },
  { modelKey: 'deep_reasoning_model', configIdKey: 'deep_reasoning_model_config_id' },
  { modelKey: 'coding_model', configIdKey: 'coding_model_config_id' }
] as const

const findLLMConfigBySelection = (modelName?: string, configId?: string) => {
  const normalizedConfigId = String(configId || '').trim()
  if (normalizedConfigId) {
    const exactConfig = allEnabledModels.value.find(model => model.config_id === normalizedConfigId)
    if (exactConfig) {
      return exactConfig
    }
  }

  const normalizedModelName = String(modelName || '').trim()
  if (!normalizedModelName) {
    return null
  }

  const matchingConfigs = allEnabledModels.value.filter(model => model.model_name === normalizedModelName)
  if (!matchingConfigs.length) {
    return null
  }

  const preferredProvider = String(systemSettings.value.default_provider || '').trim().toLowerCase()
  if (preferredProvider) {
    const preferredConfig = matchingConfigs.find(model => String(model.provider || '').trim().toLowerCase() === preferredProvider)
    if (preferredConfig) {
      return preferredConfig
    }
  }

  return matchingConfigs[0]
}

const syncModelSelectionSettings = () => {
  for (const { modelKey, configIdKey } of modelSettingPairs) {
    const matchedConfig = findLLMConfigBySelection(
      systemSettings.value[modelKey],
      systemSettings.value[configIdKey]
    )

    systemSettings.value[configIdKey] = matchedConfig?.config_id || ''
    systemSettings.value[modelKey] = matchedConfig?.model_name || ''
  }
}

// 🔥 新增：支持 embedding 的厂家和模型列表（从后端获取）
const embeddingProviders = ref<Array<{
  name: string
  display_name: string
  models: string[]
}>>([])

// 🔥 新增：加载支持 embedding 的厂家和模型列表
const loadEmbeddingProviders = async () => {
  try {
    const data = await configApi.getEmbeddingProviders()
    embeddingProviders.value = data
    console.log('✅ 加载 Embedding 厂家列表成功:', data)
  } catch (error) {
    console.error('❌ 加载 Embedding 厂家列表失败:', error)
    ElMessage.error('加载 Embedding 厂家列表失败')
    // 失败时使用空数组
    embeddingProviders.value = []
  }
}

// 🔥 新增：获取指定厂商的 Embedding 模型列表
const getEmbeddingModelsForProvider = (providerName: string) => {
  const provider = embeddingProviders.value.find(p => p.name === providerName)
  return provider ? provider.models : []
}

// 加载厂家列表
const loadProviders = async () => {
  providersLoading.value = true
  try {
    console.log('🔄 开始加载厂家列表...')
    const providerList = await configApi.getLLMProviders()
    console.log('📊 厂家列表响应:', providerList)
    providers.value = providerList
    console.log('✅ 厂家列表加载成功，数量:', providerList.length)
  } catch (error) {
    console.error('❌ 加载厂家列表失败:', error)
    ElMessage.error('加载厂家列表失败')
  } finally {
    providersLoading.value = false
  }
}

const loadLLMConfigs = async () => {
  llmLoading.value = true
  try {
    console.log('🔄 开始加载大模型配置...')
    const configs = await configApi.getLLMConfigs()
    console.log('📊 大模型配置响应:', configs)
    llmConfigs.value = configs
    console.log('✅ 大模型配置加载成功，数量:', configs.length)

    // 获取默认LLM
    const systemConfig = await configApi.getSystemConfig()
    console.log('📊 系统配置响应:', systemConfig)
    defaultLLM.value = systemConfig.default_llm || ''

    // 构建分组数据
    buildLLMConfigGroups()
  } catch (error) {
    console.error('❌ 加载大模型配置失败:', error)
    ElMessage.error('加载大模型配置失败')
  } finally {
    llmLoading.value = false
  }
}

// 构建大模型配置分组数据
const buildLLMConfigGroups = () => {
  // 按厂家分组
  const providerGroups: Record<string, LLMConfig[]> = {}

  llmConfigs.value.forEach(config => {
    const provider = config.provider
    if (!providerGroups[provider]) {
      providerGroups[provider] = []
    }
    providerGroups[provider].push(config)
  })

  // 构建分组数据
  const groups: any[] = []

  Object.entries(providerGroups).forEach(([provider, models]) => {
    // 获取厂家信息
    const providerInfo = providerInfoMap.value[provider] || {
      display_name: getProviderDisplayName(provider),
      description: `${getProviderDisplayName(provider)} 大模型服务`,
      is_active: true
    }

    // 创建厂家分组
    const group = {
      provider: provider,
      display_name: providerInfo.display_name,
      description: providerInfo.description,
      is_active: providerInfo.is_active,
      models: models.sort((a, b) => {
        // 默认模型排在前面
        if (a.model_name === defaultLLM.value) return -1
        if (b.model_name === defaultLLM.value) return 1
        // 启用的模型排在前面
        if (a.enabled && !b.enabled) return -1
        if (!a.enabled && b.enabled) return 1
        // 按名称排序
        return a.model_name.localeCompare(b.model_name)
      })
    }

    groups.push(group)
  })

  // 按厂家名称排序
  groups.sort((a, b) => a.display_name.localeCompare(b.display_name))

  llmConfigGroups.value = groups
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

  // 京东云模式下：只显示 tushare 和 akshare 类型的数据源
  const filteredConfigs = isJdyunMode()
    ? dataSourceConfigs.value.filter(ds => ['tushare', 'akshare'].includes(ds.type?.toLowerCase() || ''))
    : dataSourceConfigs.value

  // 按分类分组
  marketCategories.value.forEach(category => {
    const categoryGroupings = dataSourceGroupings.value.filter(
      g => g.market_category_id === category.id
    )

    if (categoryGroupings.length > 0) {
      const dataSources = categoryGroupings
        .map(grouping => {
          const dataSource = filteredConfigs.find(
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
        .filter((item): item is DataSourceConfig & { priority: number; enabled: boolean } => item !== null)
        .sort((a, b) => b.priority - a.priority) // 按优先级降序排列

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

  filteredConfigs.forEach(dataSource => {
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
      quick_analysis_model_config_id: '',
      deep_analysis_model: 'qwen-max',
      deep_analysis_model_config_id: '',
      deep_reasoning_model: '',
      deep_reasoning_model_config_id: '',
      coding_model: '',
      coding_model_config_id: '',
      default_embedding_model: '',  // 🔥 新增：默认 Embedding 模型
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
      // 回测 DSL 生成校验
      dsl_validate_on_generate: true,
      dsl_run_execution_check: true,
      // 代理配置
      proxy_enabled: false,  // 默认关闭代理
      http_proxy: '',
      https_proxy: '',
      no_proxy: 'localhost,127.0.0.1,eastmoney.com,push2.eastmoney.com,82.push2.eastmoney.com,82.push2delay.eastmoney.com,gtimg.cn,sinaimg.cn,api.tushare.pro,baostock.com',

      ...settings
    }
    // 🔥 修复：后端返回的数值字段可能是字符串，el-input-number 要求 Number 类型
    const numericKeys = [
      'cost_alert_threshold', 'default_analysis_timeout', 'cache_ttl',
      'worker_heartbeat_interval_seconds', 'queue_poll_interval_seconds',
      'queue_cleanup_interval_seconds', 'sse_poll_timeout_seconds',
      'sse_heartbeat_interval_seconds', 'sse_task_max_idle_seconds',
      'sse_batch_poll_interval_seconds', 'sse_batch_max_idle_seconds',
      'ta_hk_min_request_interval_seconds', 'ta_hk_timeout_seconds',
      'ta_hk_max_retries', 'ta_hk_rate_limit_wait_seconds', 'ta_hk_cache_ttl_seconds',
      'ta_china_min_api_interval_seconds', 'ta_us_min_api_interval_seconds',
      'ta_google_news_sleep_min_seconds', 'ta_google_news_sleep_max_seconds',
      'max_usage_records',
    ]
    for (const k of numericKeys) {
      const v = systemSettings.value[k]
      if (v != null && typeof v !== 'number') {
        systemSettings.value[k] = Number(v)
      }
    }
    syncModelSelectionSettings()
    // 🔥 保存原始 Embedding 模型值（用于切换提醒）
    originalEmbeddingModel.value = systemSettings.value.default_embedding_model || ''
    // 规整元数据为map
    const metaList = meta?.items || []
    systemSettingsMeta.value = Object.fromEntries(metaList.map((m: SettingMeta) => [m.key, m]))
    // 清空代理测试结果
    proxyTestResult.value = null
  } catch (error) {
    ElMessage.error('加载系统设置失败')
  } finally {
    systemLoading.value = false
  }
}

// 🔥 新增：监听 Embedding 模型变化，供应商切换时提醒
watch(() => systemSettings.value.default_embedding_model, (newValue, oldValue) => {
  const getProvider = (val: string | undefined) => {
    if (!val) return ''
    const parts = val.split(':')
    return parts[0] || ''
  }
  const oldProvider = getProvider(oldValue)
  const newProvider = getProvider(newValue)
  if (oldProvider && newProvider && oldProvider !== newProvider) {
    ElMessageBox.alert(
      `<p>您正在从 <strong>${oldProvider}</strong> 切换到 <strong>${newProvider}</strong> 作为默认 Embedding 供应商。</p>
       <p style="margin-top:10px; color:#f56c6c;"><strong>重要提示：</strong>不同 Embedding 模型生成的向量语义空间不同，即使维度相同，相似度搜索结果也会完全错误。</p>
       <p style="margin-top:10px;">建议重新生成所有向量数据（如记忆功能、知识库等），以确保准确性。</p>`,
      '切换 Embedding 供应商提醒',
      {
        confirmButtonText: '我知道了',
        dangerouslyUseHTMLString: true,
        type: 'warning'
      }
    )
  }
})

// ========== 厂家管理操作 ==========

// 显示添加厂家对话框
const showAddProviderDialog = () => {
  currentProvider.value = {}
  providerDialogVisible.value = true
}

// 编辑厂家
const editProvider = (provider: LLMProvider) => {
  currentProvider.value = { ...provider }
  providerDialogVisible.value = true
}

// 切换厂家状态
const toggleProvider = async (provider: LLMProvider) => {
  try {
    await configApi.toggleLLMProvider(provider.id, !provider.is_active)
    await loadProviders()
    ElMessage.success(`厂家已${provider.is_active ? '禁用' : '启用'}`)
  } catch (error) {
    ElMessage.error('切换厂家状态失败')
  }
}

// 删除厂家
const deleteProvider = async (provider: LLMProvider) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除厂家 ${provider.display_name} 吗？删除后该厂家下的所有模型配置也将被删除。`,
      '确认删除',
      { type: 'warning' }
    )

    await configApi.deleteLLMProvider(provider.id)
    await loadProviders()
    ElMessage.success('厂家删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除厂家失败')
    }
  }
}

// 厂家操作成功回调
const handleProviderSuccess = () => {
  loadProviders()
  // 重新加载厂家信息到映射表
  loadProviderInfoMap()
}

// 加载厂家信息到映射表
const loadProviderInfoMap = async () => {
  try {
    const providerList = await configApi.getLLMProviders()
    const map: Record<string, any> = {}

    providerList.forEach(provider => {
      map[provider.name] = {
        display_name: provider.display_name,
        description: provider.description,
        is_active: provider.is_active
      }
    })

    providerInfoMap.value = map
  } catch (error) {
    console.error('加载厂家信息映射失败:', error)
  }
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

// 获取厂家标签类型
const getProviderTagType = (provider: string): TagType => {
  const typeMap: Record<string, TagType> = {
    'openai': 'primary',
    'google': 'success',
    'anthropic': 'warning',
    'dashscope': 'info',
    'qwen': 'info',
    'zhipu': 'danger',
    'deepseek': 'primary',
    'qianfan': 'success'
  }
  return typeMap[provider.toLowerCase()] || 'info'
}

// 🆕 获取能力等级文本
const getCapabilityLevelText = (level: number) => {
  const levelMap: Record<number, string> = {
    1: '1级-基础',
    2: '2级-标准',
    3: '3级-高级',
    4: '4级-专业',
    5: '5级-旗舰'
  }
  return levelMap[level] || `${level}级`
}

// 🆕 获取能力等级标签类型
const getCapabilityLevelType = (level: number): TagType => {
  const typeMap: Record<number, TagType> = {
    1: 'info',
    2: 'primary',
    3: 'success',
    4: 'warning',
    5: 'danger'
  }
  return typeMap[level] || 'info'
}

// 🆕 获取角色文本
const getRoleText = (role: string) => {
  const roleMap: Record<string, string> = {
    'quick_analysis': '快速分析',
    'deep_analysis': '深度分析',
    'both': '全能型'
  }
  return roleMap[role] || role
}

// 🆕 格式化价格显示（去除尾部多余的零）
const formatPrice = (price: number | undefined | null) => {
  if (price === undefined || price === null) {
    return '0'
  }
  // 转换为字符串并去除尾部多余的零
  return parseFloat(price.toFixed(6)).toString()
}

// 为厂家添加模型
const addModelToProvider = (providerRow: any) => {
  // 预设厂家信息
  currentLLMConfig.value = {
    provider: providerRow.provider,
    model_name: '',
    model_display_name: '',
    description: '',
    enabled: true,
    max_tokens: 4000,
    temperature: 0.2,  // 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
    timeout: 60,
    retry_times: 3,
    priority: 0,
    api_base: '',
    model_category: '',
    enable_memory: false,
    enable_debug: false
  }

  llmDialogVisible.value = true
  isEditingLLM.value = false
}

// 切换厂家状态
const toggleProviderStatus = async (providerRow: any) => {
  try {
    const newStatus = !providerRow.is_active
    const action = newStatus ? '启用' : '禁用'

    // 获取厂家ID
    const provider = providers.value.find(p => p.name === providerRow.provider)
    if (!provider) {
      ElMessage.error('找不到厂家信息')
      return
    }

    // 调用后端API切换厂家状态
    await configApi.toggleLLMProvider(provider.id, newStatus)

    // 重新加载数据
    await loadProviders()
    await loadLLMConfigs()

    // 重新构建厂家信息映射和分组数据
    await loadProviderInfoMap()
    buildLLMConfigGroups()

    ElMessage.success(`厂家已${action}`)
  } catch (error) {
    console.error('切换厂家状态失败:', error)
    ElMessage.error('切换厂家状态失败')
  }
}

// 测试厂家API
const testProviderAPI = async (provider: LLMProvider) => {
  try {
    console.log('🔍 测试厂家API:', provider)
    console.log('📋 厂家ID:', provider.id)
    console.log('📋 厂家名称:', provider.display_name)

    testingProviders.value[provider.id] = true

    // 调用测试API
    const result = await configApi.testProviderAPI(provider.id)

    if (result.success) {
      ElMessage.success(`${provider.display_name} API测试成功`)
    } else {
      ElMessage.error(`${provider.display_name} API测试失败: ${result.message}`)
    }
  } catch (error) {
    console.error('API测试失败:', error)
    ElMessage.error(`${provider.display_name} API测试失败`)
  } finally {
    testingProviders.value[provider.id] = false
  }
}

// 获取厂家显示名称
const getProviderDisplayName = (providerId: string) => {
  const provider = providers.value.find(p => p.name === providerId)
  return provider?.display_name || providerId
}

// API密钥状态相关计算属性
const configuredProvidersCount = computed(() => {
  return providers.value.filter(p => p.extra_config?.has_api_key === true).length
})

const activeProvidersCount = computed(() => {
  return providers.value.filter(p => p.is_active).length
})

// 获取密钥状态类型
const getKeyStatusType = (provider: LLMProvider) => {
  if (!provider.extra_config?.has_api_key) {
    return 'info'
  }
  return provider.is_active ? 'success' : 'warning'
}

// 获取密钥状态文本
const getKeyStatusText = (provider: LLMProvider) => {
  if (!provider.extra_config?.has_api_key) {
    return '未配置'
  }
  if (!provider.is_active) {
    return '已配置(禁用)'
  }

  if (provider.extra_config?.source === 'environment') {
    return '已配置(环境变量)'
  }

  return '已配置'
}

// 从环境变量迁移
const migrateFromEnv = async () => {
  try {
    await ElMessageBox.confirm(
      '此操作将从 .env 文件中读取API密钥并创建对应的厂家配置。已存在的厂家配置不会被覆盖。',
      '确认迁移',
      { type: 'info' }
    )

    migrateLoading.value = true
    const result = await configApi.migrateEnvToProviders()

    ElMessage.success(result.message)

    // 重新加载厂家列表
    await loadProviders()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('迁移失败:', error)
      ElMessage.error('迁移失败，请检查控制台错误信息')
    }
  } finally {
    migrateLoading.value = false
  }
}

// ========== 大模型配置操作 ==========

// 大模型配置对话框
const llmDialogVisible = ref(false)
const currentLLMConfig = ref<LLMConfig | null>(null)
const isEditingLLM = ref(false)
const batchImporting = ref(false)
const batchImportDialogVisible = ref(false)
const selectedImportProviders = ref<string[]>([])
const importableProviders = ref<LLMProvider[]>([])

const handleBatchImport = async () => {
  // 加载厂家列表
  try {
    const providers = await configApi.getLLMProviders()
    importableProviders.value = providers.filter((p: LLMProvider) => p.is_active)
  } catch {
    ElMessage.error('加载厂家列表失败')
    return
  }
  selectedImportProviders.value = []
  batchImportDialogVisible.value = true
}

const confirmBatchImport = async () => {
  if (selectedImportProviders.value.length === 0) return

  batchImporting.value = true
  try {
    const result = await configApi.batchImportLLMConfigs(selectedImportProviders.value)
    if (result.success) {
      ElMessage.success(result.message)
      batchImportDialogVisible.value = false
      await loadLLMConfigs()
    } else {
      ElMessage.warning(result.message)
    }
  } catch (error) {
    console.error('批量导入失败:', error)
    ElMessage.error('批量导入失败')
  } finally {
    batchImporting.value = false
  }
}

const showAddLLMDialog = () => {
  currentLLMConfig.value = null
  isEditingLLM.value = false
  llmDialogVisible.value = true
}

const editLLMConfig = (config: LLMConfig) => {
  currentLLMConfig.value = config
  isEditingLLM.value = true
  llmDialogVisible.value = true
}

const handleLLMConfigSuccess = () => {
  loadLLMConfigs()
}

// 测试LLM配置
const testLLMConfig = async (config: LLMConfig) => {
  try {
    console.log('🧪 测试LLM配置:', config)
    console.log('📋 厂家:', config.provider)
    console.log('📋 模型名称:', config.model_name)
    console.log('📋 显示名称:', config.model_display_name)
    console.log('📋 API基础URL:', config.api_base)

    const result = await configApi.testConfig({
      config_type: 'llm',
      config_data: config
    })

    console.log('✅ 测试结果:', result)

    if (result.success) {
      ElMessage.success(`测试成功: ${result.message}`)
    } else {
      ElMessage.error(`测试失败: ${result.message}`)
    }
  } catch (error: any) {
    console.error('❌ 测试配置失败:', error)
    console.error('❌ 错误详情:', error.response?.data)
    ElMessage.error(error.response?.data?.detail || error.message || '测试配置失败')
  }
}

// 切换LLM配置启用状态
const toggleLLMConfig = async (config: LLMConfig) => {
  try {
    const newStatus = !config.enabled
    const action = newStatus ? '启用' : '禁用'

    // 更新配置
    const updateData = {
      ...config,
      enabled: newStatus
    }

    await configApi.updateLLMConfig(updateData)
    await loadLLMConfigs()
    ElMessage.success(`模型已${action}`)
  } catch (error) {
    ElMessage.error('切换模型状态失败')
  }
}

// 删除LLM配置
const deleteLLMConfig = async (config: LLMConfig) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除大模型配置 ${config.provider}/${config.model_name} 吗？`,
      '确认删除',
      { type: 'warning' }
    )

    await configApi.deleteLLMConfig(config.provider, config.model_name)
    await loadLLMConfigs()
    ElMessage.success('大模型配置删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除大模型配置失败')
    }
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
const handleDataSourceConfigSuccess = async () => {
  await loadDataSourceConfigs()

  // 🔥 数据源配置成功后，引导用户去同步数据
  try {
    await ElMessageBox.confirm(
      '数据源已配置完成，建议立即同步股票基础数据，以便开始分析。',
      '数据源配置成功',
      {
        confirmButtonText: '立即同步数据',
        cancelButtonText: '稍后再说',
        type: 'success',
        showClose: true,
      }
    )
    // 用户点击"立即同步数据"，跳转到同步页面
    router.push('/settings/sync')
  } catch (action) {
    // 用户点击"稍后再说"或关闭，不做任何操作
  }
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
      ElMessage.success('数据库连接测试成功')
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
// ========== Gateway 配置相关 ==========

const fetchGatewayConfig = async (platform: string) => {
  try {
    gatewayLoading.value = true
    const data = await configApi.getGatewayConfig(platform)
    if (platform === 'qq') {
      gatewayQQConfig.value = data
    } else if (platform === 'feishu') {
      gatewayFeishuConfig.value = data
    } else if (platform === 'dingtalk') {
      gatewayDingtalkConfig.value = data
    }
  } catch (error: any) {
    console.error(`获取 Gateway ${platform} 配置失败:`, error)
    ElMessage.error(`获取 Gateway ${platform} 配置失败`)
  } finally {
    gatewayLoading.value = false
  }
}

const handleSaveGatewayConfig = async (platform: string) => {
  let req: GatewayConfigRequest

  if (platform === 'qq') {
    const cfg = gatewayQQConfig.value
    if (!cfg.app_id || !cfg.app_secret) {
      ElMessage.warning('AppID 和 AppSecret 不能为空')
      return
    }
    req = {
      app_id: cfg.app_id,
      app_secret: cfg.app_secret,
      bot_secret: cfg.bot_secret || undefined,
      connection_mode: cfg.connection_mode || 'websocket',
      enabled: cfg.enabled,
    }
  } else if (platform === 'feishu') {
    const cfg = gatewayFeishuConfig.value
    if (!cfg.app_id || !cfg.app_secret) {
      ElMessage.warning('App ID 和 App Secret 不能为空')
      return
    }
    req = {
      app_id: cfg.app_id,
      app_secret: cfg.app_secret,
      verification_token: cfg.verification_token || undefined,
      encrypt_key: cfg.encrypt_key || undefined,
      enabled: cfg.enabled,
    }
  } else if (platform === 'dingtalk') {
    const cfg = gatewayDingtalkConfig.value
    if (!cfg.app_key || !cfg.app_secret) {
      ElMessage.warning('AppKey 和 AppSecret 不能为空')
      return
    }
    req = {
      app_key: cfg.app_key,
      app_secret: cfg.app_secret,
      robot_code: cfg.robot_code || undefined,
      enabled: cfg.enabled,
    }
  } else {
    return
  }

  try {
    gatewaySaving.value = true
    await configApi.updateGatewayConfig(platform, req)
    const labels: Record<string, string> = { qq: 'QQ', feishu: '飞书', dingtalk: '钉钉' }
    ElMessage.success(`${labels[platform] || platform} Gateway 配置已保存`)
    await fetchGatewayConfig(platform)
  } catch (error: any) {
    console.error(`保存 Gateway ${platform} 配置失败:`, error)
    ElMessage.error(error.response?.data?.detail || `保存失败`)
  } finally {
    gatewaySaving.value = false
  }
}

const handleTestGatewayConnection = async (platform: string) => {
  try {
    gatewayTesting.value = true
    const res = await configApi.testGatewayConnection(platform)
    if (res.success) {
      ElMessage.success(res.message || `Gateway ${platform.toUpperCase()} 连接成功`)
    } else {
      ElMessage.error(res.message || `Gateway ${platform.toUpperCase()} 连接失败`)
    }
  } catch (error: any) {
    console.error(`测试 Gateway ${platform} 连接失败:`, error)
    ElMessage.error(error.response?.data?.message || error.response?.data?.detail || '测试连接失败')
  } finally {
    gatewayTesting.value = false
  }
}

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
    syncModelSelectionSettings()
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
    // 如果修改了代理配置，提醒用户重启服务
    if ('http_proxy' in payload || 'https_proxy' in payload || 'no_proxy' in payload) {
      ElMessage.warning('代理配置已保存，请重启后端服务使配置生效')
    }
  } catch (error) {
    ElMessage.error('系统设置保存失败')
  } finally {
    systemSaving.value = false
  }
}

// 代理连接测试
const testProxyConnection = async () => {
  proxyTesting.value = true
  proxyTestResult.value = null

  try {
    const result = await configApi.testProxyConnection({
      http_proxy: systemSettings.value.http_proxy,
      https_proxy: systemSettings.value.https_proxy
    })

    const responseTime = result.data?.response_time
    proxyTestResult.value = {
      success: result.success,
      message: result.success
        ? `连接成功 (${responseTime?.toFixed(2)}s)`
        : (result.message || '连接失败')
    }
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '测试失败'
    proxyTestResult.value = {
      success: false,
      message: errMsg
    }
  } finally {
    proxyTesting.value = false
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

// 仅当模型本身不再可用时清空，默认供应商变化不应限制模型选择范围
watch(
  allEnabledModels,
  (availableModels) => {
    for (const { modelKey, configIdKey } of modelSettingPairs) {
      const configId = String(systemSettings.value[configIdKey] || '').trim()
      const modelName = String(systemSettings.value[modelKey] || '').trim()
      const matchedConfig = availableModels.find(model => {
        if (configId) {
          return model.config_id === configId
        }
        return model.model_name === modelName
      })

      if (!matchedConfig) {
        systemSettings.value[configIdKey] = ''
        systemSettings.value[modelKey] = ''
        continue
      }

      systemSettings.value[configIdKey] = matchedConfig.config_id || ''
      systemSettings.value[modelKey] = matchedConfig.model_name || ''
    }
  }
)

// 生命周期
onMounted(async () => {
  // 京东云模式下：只显示数据源配置标签页
  if (isJdyunMode()) {
    activeTab.value = 'datasource'
    await loadDataSourceConfigs()
    return
  }
  // 先加载厂家信息，再加载其他数据
  await loadProviders()
  await loadProviderInfoMap()
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

    .api-keys-content {
      h4 {
        margin: 0 0 16px 0;
        color: var(--el-text-color-primary);
      }

      .api-key-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        margin-bottom: 8px;
        border-radius: 6px;
        background: var(--el-fill-color-lighter);
        border: 1px solid var(--el-border-color-light);

        .key-name {
          flex: 1;
          font-size: 14px;
          font-weight: 500;
          color: var(--el-text-color-primary);
        }
      }

      .empty-state {
        text-align: center;
        padding: 40px 20px;
      }

      .stats-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
      }

      .stat-item {
        text-align: center;
        padding: 16px;
        background: var(--el-fill-color-lighter);
        border-radius: 8px;
        border: 1px solid var(--el-border-color-light);

        .stat-number {
          font-size: 24px;
          font-weight: bold;
          color: var(--el-color-primary);
          margin-bottom: 4px;
        }

        .stat-label {
          font-size: 12px;
          color: var(--el-text-color-regular);
        }
      }

      .api-key-help {
        margin-top: 24px;

        h4 {
          margin-bottom: 12px;
        }

        h5 {
          margin: 0 0 8px 0;
          color: var(--el-text-color-primary);
        }

        ol {
          margin: 0;
          padding-left: 20px;

          li {
            margin-bottom: 4px;
            color: var(--el-text-color-regular);
          }
        }

        .help-card {
          background: var(--el-fill-color-lighter);
        }
      }
    }

    .flex {
      display: flex;
    }

    .gap-1 {
      gap: 4px;
    }
  }

  // 厂家管理样式
  .provider-info {
    .provider-name {
      font-weight: 500;
      color: var(--el-text-color-primary);
    }

    .provider-id {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      margin-top: 2px;
    }
  }

  .features {
    .feature-tag {
      margin-right: 4px;
      margin-bottom: 4px;
    }
  }

  .status-column {
    display: flex;
    flex-direction: column;
    gap: 4px;

    .key-source-tag {
      font-size: 10px;
    }
  }

  .api-key-status {
    .key-preview {
      font-size: 11px;
      color: var(--el-text-color-placeholder);
      margin-top: 2px;
      font-family: monospace;
    }
  }

  // 卡片式布局样式
  .empty-state {
    padding: 60px 20px;
    text-align: center;
  }

  .provider-groups {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .provider-group {
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    overflow: hidden;
    background: var(--el-bg-color);
  }

  .provider-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: var(--el-fill-color-lighter);
    border-bottom: 1px solid var(--el-border-color-light);

    .provider-info {
      display: flex;
      align-items: center;
      gap: 12px;

      .provider-tag {
        font-weight: 600;
      }

      .model-count {
        font-size: 14px;
        color: var(--el-text-color-regular);
      }

      .status-tag {
        margin-left: 8px;
      }
    }

    .provider-actions {
      display: flex;
      gap: 8px;
    }
  }

  // 表格式布局样式
  .model-name-cell {
    .model-display-name {
      font-weight: 500;
      color: var(--el-text-color-primary);
      display: flex;
      align-items: center;
    }

    .model-code-text {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      font-family: 'Courier New', monospace;
      margin-top: 4px;
    }
  }

  .config-cell {
    font-size: 13px;
    color: var(--el-text-color-regular);
    line-height: 1.6;
  }

  .pricing-cell {
    font-size: 13px;
    color: var(--el-text-color-regular);
    line-height: 1.6;
  }

  .capability-cell {
    .capability-row-item {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;

      &:last-child {
        margin-bottom: 0;
      }

      .label {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        min-width: 40px;
      }
    }
  }

  .text-muted {
    color: var(--el-text-color-placeholder);
  }

  // 保留旧的卡片样式（如果其他地方还在使用）
  .model-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .model-title {
      display: flex;
      align-items: center;
      gap: 8px;

      .model-icon {
        color: var(--el-color-primary);
      }

      .model-name-wrapper {
        display: flex;
        flex-direction: column;
        gap: 2px;

        .model-name {
          font-weight: 600;
          font-size: 16px;
        }

        .model-code {
          font-size: 12px;
          color: #909399;
          font-family: 'Courier New', monospace;
        }
      }

      .default-tag {
        margin-left: 8px;
      }
    }
  }

  .model-config {
    margin-bottom: 12px;

    .config-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 4px;
      font-size: 13px;

      .config-label {
        color: var(--el-text-color-regular);
      }

      .config-value {
        font-weight: 500;
        color: var(--el-text-color-primary);
      }
    }
  }

  .model-pricing {
    margin-bottom: 12px;
    padding: 8px;
    background: var(--el-fill-color-lighter);
    border-radius: 4px;

    .pricing-row {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--el-color-warning);
      font-weight: 600;
    }

    .pricing-details {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding-left: 20px;

      .pricing-item {
        display: flex;
        justify-content: space-between;
        font-size: 12px;

        .pricing-type {
          color: var(--el-text-color-regular);
        }

        .pricing-value {
          font-weight: 500;
          color: var(--el-color-warning);
        }
      }
    }
  }

  // 🆕 模型能力信息样式
  .model-capability {
    margin-bottom: 12px;
    padding: 8px;
    background: var(--el-fill-color-lighter);
    border-radius: 4px;

    .capability-row {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--el-color-primary);
      font-weight: 600;
    }

    .capability-details {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding-left: 20px;

      .capability-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;

        .capability-type {
          color: var(--el-text-color-regular);
          min-width: 60px;
        }
      }
    }
  }

  .model-features {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    min-height: 20px;
  }

  .model-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;

    .el-button {
      flex: 1;
      min-width: 60px;
    }
  }

  // 代理测试结果样式
  .proxy-test-result {
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 4px;

    &.success {
      color: var(--el-color-success);
      background: var(--el-color-success-light-9);
    }

    &.error {
      color: var(--el-color-danger);
      background: var(--el-color-danger-light-9);
    }
  }

  .form-tip {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.4;
    margin-top: 4px;
  }
}
</style>
