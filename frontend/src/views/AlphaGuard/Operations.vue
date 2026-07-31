<template>
  <div v-loading="loading" class="page-grid">
    <el-result v-if="loadError" icon="warning" title="运维状态加载失败" :sub-title="loadError"><template #extra><el-button @click="load">重试</el-button></template></el-result>
    <template v-else>
    <section v-if="!modelsOnly" class="safety-strip">
      <div><span>SYSTEM_MODE</span><strong>{{ readiness?.system_mode || 'UNKNOWN' }}</strong></div>
      <div><span>LIVE_TRADING_ENABLED</span><el-tag type="danger">{{ readiness?.live_trading_enabled ?? false }}</el-tag></div>
      <div><span>LIVE_EXECUTION_ALLOWED</span><el-tag type="danger">{{ readiness?.live_execution_allowed ?? false }}</el-tag></div>
    </section>
    <el-card v-if="!modelsOnly" shadow="never">
      <template #header><div class="header-row"><strong>系统准备度</strong><el-button @click="load">刷新</el-button></div></template>
      <div class="status-line">
        <el-tag :type="statusType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
        <span>Report {{ short(readiness?.report_hash) }}</span>
        <span>Config {{ short(readiness?.config_hash) }}</span>
        <el-tag type="danger">LIVE_READY = false</el-tag>
      </div>
      <el-alert v-if="readiness?.blocking_items.length" type="warning" :closable="false" :title="readiness.blocking_items.join('；')" />
    </el-card>

    <el-tabs
      v-model="activeOperationTab"
      type="border-card"
      :class="{ 'operations-tabs--embedded': props.embedded }"
    >
      <el-tab-pane v-if="!modelsOnly" label="服务" name="services">
        <el-table :data="services" size="small">
          <el-table-column prop="service_name" label="服务" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="latency_ms" label="延迟(ms)" />
          <el-table-column prop="error_code" label="错误代码" min-width="190" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="260" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="!modelsOnly" label="数据准备" name="data-readiness">
        <el-table :data="dataStatuses" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录" width="90" />
          <el-table-column label="覆盖" min-width="190"><template #default="{ row }">{{ row.coverage_start || '—' }} ～ {{ row.coverage_end || '—' }}</template></el-table-column>
          <el-table-column label="阻断" min-width="300"><template #default="{ row }">{{ row.blocking_reasons.join('；') }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="!modelsOnly" label="任务" name="jobs">
        <el-table :data="jobs" size="small">
          <el-table-column prop="job_name" label="任务" min-width="190" />
          <el-table-column prop="worker_name" label="Worker" min-width="130" />
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column prop="next_scheduled_at" label="下次执行" min-width="180" />
          <el-table-column prop="backlog_count" label="积压" width="80" />
          <el-table-column prop="error_code" label="错误" min-width="170" />
        </el-table>
        <div v-if="authStore.isAdmin && !isDemo && !isCredentialHost" class="admin-actions">
          <span>管理员受控任务：</span>
          <el-button v-for="name in manualJobs" :key="name" size="small" @click="runJob(name)">{{ name }}</el-button>
        </div>
      </el-tab-pane>
      <el-tab-pane v-if="!modelsOnly" label="告警" name="alerts">
        <el-table :data="alerts" size="small">
          <el-table-column prop="severity" label="级别" width="100" />
          <el-table-column prop="code" label="代码" min-width="220" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="280" />
          <el-table-column prop="occurrence_count" label="次数" width="80" />
          <el-table-column prop="status" label="状态" width="130" />
          <el-table-column v-if="authStore.isAdmin && !isDemo && !isCredentialHost" label="操作" width="150">
            <template #default="{ row }">
              <el-button link :disabled="row.status !== 'OPEN'" @click="ack(row)">确认</el-button>
              <el-button link type="success" :disabled="row.status === 'RESOLVED'" @click="resolve(row)">解决</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!alerts.length" description="暂无持久化告警" />
      </el-tab-pane>
      <el-tab-pane label="模型与 API" name="models">
        <div class="status-line">
          <el-tag :type="modelStatus?.status === 'READY' ? 'success' : modelStatus?.status === 'DEGRADED' ? 'warning' : 'danger'">
            {{ statusLabel(modelStatus?.status || 'NOT_CONFIGURED') }}
          </el-tag>
          <span>按步骤完成服务商、API 密钥、普通决策模型和风险终审模型配置。</span>
        </div>
        <el-alert
          v-if="lastConfigurationError"
          class="configuration-feedback"
          type="error"
          :closable="false"
          :title="lastConfigurationError"
        />
        <el-collapse v-if="lastConfigurationTechnicalError" class="advanced-information">
          <el-collapse-item title="高级信息（技术错误）" name="error-technical">
            <code>{{ lastConfigurationTechnicalError }}</code>
          </el-collapse-item>
        </el-collapse>
        <section class="configuration-guide">
          <el-steps :active="setupActiveStep" finish-status="success" simple>
            <el-step v-for="step in setupSteps" :key="step.key" :title="step.title" />
          </el-steps>
          <div class="next-action-card">
            <div>
              <strong>{{ configurationNextAction.complete ? '配置已完成' : `当前缺少：${configurationNextAction.missing}` }}</strong>
              <span>{{ configurationNextAction.complete ? '所有配置门禁均已通过。' : `下一步：点击“${configurationNextAction.actionLabel}”` }}</span>
            </div>
            <el-button
              v-if="!configurationNextAction.complete"
              type="primary"
              @click="goToNextConfigurationStep"
            >{{ configurationNextAction.actionLabel }}</el-button>
          </div>
        </section>
        <section v-if="configurationStatus" class="configuration-completeness">
          <div class="configuration-completeness__header">
            <div>
              <strong>配置完整性</strong>
              <span>{{ selectedEndpoint?.display_name || '当前服务商' }}</span>
            </div>
            <div>
              <el-tag :type="configurationStatus.production_allowed ? 'success' : 'warning'">
                {{ statusLabel(configurationStatus.stage) }}
              </el-tag>
              <el-button text @click="loadSelectedEndpointConfiguration">刷新状态</el-button>
            </div>
          </div>
          <div class="configuration-completeness__grid">
            <div
              v-for="item in configurationStatus.components"
              :key="item.key"
              class="configuration-component"
            >
              <span>{{ configurationComponentLabel(item.key) }}</span>
              <el-tag :type="item.complete ? 'success' : 'warning'" size="small">
                {{ statusLabel(item.status) }}
              </el-tag>
              <small v-if="item.reason_code">{{ reasonLabel(item.reason_code) }}</small>
            </div>
          </div>
          <el-collapse class="advanced-information">
            <el-collapse-item title="高级信息（技术状态与版本）" name="configuration-technical">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="接口标识">{{ configurationStatus.endpoint_profile_id }}</el-descriptions-item>
                <el-descriptions-item label="技术版本">{{ configurationStatus.endpoint_profile_version }}</el-descriptions-item>
                <el-descriptions-item label="显示状态">{{ statusLabel(configurationStatus.stage) }}</el-descriptions-item>
                <el-descriptions-item label="技术状态">{{ configurationStatus.stage }}</el-descriptions-item>
              </el-descriptions>
              <el-table :data="configurationStatus.components" size="small">
                <el-table-column label="项目"><template #default="{ row }">{{ configurationComponentLabel(row.key) }}</template></el-table-column>
                <el-table-column label="显示状态"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
                <el-table-column prop="status" label="技术状态" />
                <el-table-column prop="reason_code" label="技术原因" />
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </section>
        <el-tabs
          v-model="activeModelTab"
          class="model-tabs"
          :class="{ 'model-tabs--embedded': props.embedded }"
        >
          <el-tab-pane label="服务商配置" name="providers">
            <div class="provider-toolbar">
              <div>
                <strong>模型服务商</strong>
                <span>选择已有服务商继续配置，或创建一个新的第三方服务商。</span>
              </div>
              <el-button
                v-if="authStore.isAdmin && !isDemo"
                type="primary"
                @click="openCreateProviderEndpoint"
              >添加服务商</el-button>
            </div>
            <el-table
              :data="providerEndpoints"
              size="small"
              highlight-current-row
              @row-click="continueProviderEndpoint"
            >
              <el-table-column prop="display_name" label="服务商" min-width="170" />
              <el-table-column label="服务类型" min-width="150"><template #default="{ row }">{{ providerTypeLabel(row.provider_type) }}</template></el-table-column>
              <el-table-column label="接口状态" min-width="150"><template #default="{ row }">{{ statusLabel(row.state) }}</template></el-table-column>
              <el-table-column label="地址验证" min-width="140"><template #default="{ row }">{{ statusLabel(row.url_validation_status) }}</template></el-table-column>
              <el-table-column label="生产使用" width="120">
                <template #default="{ row }">{{ row.production_allowed ? '已启用' : '未启用' }}</template>
              </el-table-column>
              <el-table-column label="操作" width="160" fixed="right">
                <template #default="{ row }">
                  <el-button
                    link
                    @click.stop="continueProviderEndpoint(row)"
                  >{{ row.state === 'DRAFT' ? '继续配置' : '查看' }}</el-button>
                  <el-button
                    v-if="authStore.isAdmin && !isDemo && row.provider_type === 'OPENAI_COMPATIBLE'"
                    link
                    @click.stop="openNewEndpointVersion(row)"
                  >新版本</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!providerEndpoints.length" description="尚未登记模型服务商" />

            <section v-if="selectedEndpoint && endpointEditorMode === 'closed'" class="provider-detail">
              <div class="provider-detail__header">
                <div>
                  <strong>{{ selectedEndpoint.display_name }}</strong>
                  <span>当前版本</span>
                </div>
                <div class="provider-detail__actions">
                  <el-button
                    v-if="authStore.isAdmin && !isDemo && selectedEndpoint.provider_type === 'OPENAI_COMPATIBLE'"
                    @click="openNewEndpointVersion(selectedEndpoint)"
                  >创建新版本</el-button>
                  <el-button
                    v-if="selectedEndpoint.url_validation_status === 'PASS'"
                    type="primary"
                    @click="goToCredentialSettings(selectedEndpoint)"
                  >添加 API 密钥</el-button>
                </div>
              </div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="接口状态">
                  <el-tag :type="endpointStateType(selectedEndpoint.state)">{{ statusLabel(selectedEndpoint.state) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="地址验证">
                  <el-tag :type="selectedEndpoint.url_validation_status === 'PASS' ? 'success' : 'warning'">
                    {{ statusLabel(selectedEndpoint.url_validation_status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="接口地址">{{ selectedEndpoint.base_url || '系统固定' }}</el-descriptions-item>
                <el-descriptions-item label="模型获取方式">{{ selectedEndpoint.models_endpoint_enabled ? '自动读取' : '手工添加' }}</el-descriptions-item>
              </el-descriptions>
              <el-collapse class="advanced-information">
                <el-collapse-item title="高级信息" name="provider-technical">
                  <el-descriptions :column="2" border size="small">
                    <el-descriptions-item label="接口版本">{{ selectedEndpoint.profile_version }}</el-descriptions-item>
                    <el-descriptions-item label="服务类型">{{ selectedEndpoint.provider_type }}</el-descriptions-item>
                    <el-descriptions-item label="认证方式">{{ selectedEndpoint.auth_scheme || 'BEARER' }}</el-descriptions-item>
                    <el-descriptions-item label="API 模式">{{ selectedEndpoint.api_mode || '系统固定' }}</el-descriptions-item>
                    <el-descriptions-item label="结构化输出">{{ selectedEndpoint.structured_output_mode }}</el-descriptions-item>
                    <el-descriptions-item label="技术状态">{{ selectedEndpoint.state }}</el-descriptions-item>
                  </el-descriptions>
                </el-collapse-item>
              </el-collapse>

              <div
                v-if="authStore.isAdmin && !isDemo && selectedEndpoint.provider_type === 'OPENAI_COMPATIBLE' && selectedEndpoint.state === 'DRAFT'"
                class="endpoint-validation"
              >
                <el-alert
                  type="warning"
                  :closable="false"
                  title="该接口版本尚未验证地址，验证通过后才能添加 API 密钥。"
                />
                <el-checkbox v-model="endpointTransmissionConfirmed">
                  我确认将研究数据发送到该第三方服务，并已评估其隐私、数据保留和安全政策
                </el-checkbox>
                <el-button
                  type="primary"
                  :loading="providerSubmitting"
                  :disabled="!endpointTransmissionConfirmed"
                  @click="validateProviderEndpoint(selectedEndpoint)"
                >确认并验证地址</el-button>
              </div>
            </section>

            <el-form
              v-if="authStore.isAdmin && !isDemo && endpointEditorMode !== 'closed'"
              class="credential-form endpoint-editor"
              label-position="top"
              autocomplete="off"
              @submit.prevent
            >
              <div class="endpoint-editor__header">
                <div>
                  <strong>{{ endpointEditorMode === 'create' ? '添加服务商' : '创建接口新版本' }}</strong>
                  <span v-if="endpointEditorMode === 'new-version'">旧版本保持不可变，新配置保存为下一版本。</span>
                </div>
                <el-button text @click="cancelEndpointEdit">取消</el-button>
              </div>
              <div class="credential-grid">
                <el-form-item label="服务商名称">
                  <el-input v-model="endpointDisplayName" maxlength="120" autocomplete="off" />
                </el-form-item>
                <el-form-item label="服务类型">
                  <el-input model-value="OPENAI_COMPATIBLE" disabled />
                </el-form-item>
                <el-form-item label="接口地址（HTTPS）">
                  <el-input v-model="endpointBaseUrl" placeholder="https://provider.example/v1" autocomplete="off" />
                  <div v-if="endpointEditorMode === 'new-version'" class="field-note">新版本必须保持相同来源域名。</div>
                </el-form-item>
                <el-form-item label="接口模式">
                  <el-select v-model="endpointApiMode">
                    <el-option label="聊天补全（Chat Completions）" value="OPENAI_CHAT_COMPLETIONS" />
                    <el-option label="响应接口（Responses）" value="OPENAI_RESPONSES" />
                    <el-option label="自动检测" value="AUTO_DETECT" />
                  </el-select>
                </el-form-item>
                <el-form-item label="认证方式">
                  <el-select v-model="endpointAuthScheme">
                    <el-option label="Bearer" value="BEARER" />
                    <el-option label="X-API-Key" value="X_API_KEY" />
                  </el-select>
                </el-form-item>
                <el-form-item label="结构化输出模式">
                  <el-select v-model="endpointStructuredMode">
                    <el-option label="原生 JSON Schema" value="NATIVE_JSON_SCHEMA" />
                    <el-option label="工具调用（Tool Call）" value="TOOL_CALL" />
                    <el-option label="仅 JSON" value="JSON_ONLY" />
                    <el-option label="未知" value="UNKNOWN" />
                  </el-select>
                </el-form-item>
                <el-form-item label="模型发现">
                  <el-switch v-model="endpointModelsEnabled" active-text="支持 /models" inactive-text="手工登记" />
                </el-form-item>
                <el-form-item label="备注">
                  <el-input v-model="endpointNotes" maxlength="500" autocomplete="off" />
                </el-form-item>
              </div>
              <div class="credential-actions">
                <el-button type="primary" :loading="providerSubmitting" @click="createProviderEndpoint">
                  {{ endpointEditorMode === 'create' ? '保存服务商草稿' : '保存为新版本' }}
                </el-button>
                <el-button @click="cancelEndpointEdit">取消</el-button>
              </div>
              <p class="security-note">
                保存草稿不会发送 API 密钥。保存后再单独确认第三方数据传输并验证接口地址。
              </p>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="API 密钥" name="credentials">
            <el-table :data="credentials" size="small">
              <el-table-column label="绑定服务商" min-width="180">
                <template #default="{ row }">{{ credentialProviderLabel(row) }}</template>
              </el-table-column>
              <el-table-column label="接口版本" width="120">
                <template #default="{ row }">{{ credentialVersionLabel(row) }}</template>
              </el-table-column>
              <el-table-column prop="credential_id" label="密钥名称" min-width="180" />
              <el-table-column label="已保存密钥" width="130">
                <template #default="{ row }">{{ row.configured ? '••••••••' : '未配置' }}</template>
              </el-table-column>
              <el-table-column label="状态" width="130"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
              <el-table-column label="安全存储" width="140"><template #default="{ row }">{{ statusLabel(row.secret_store_status) }}</template></el-table-column>
              <el-table-column prop="last_verified_at" label="最后验证" min-width="190" />
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button link @click="verifyCredential(row)">验证</el-button>
                  <el-button link type="danger" @click="revokeCredential(row)">撤销</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!credentials.length" description="尚未添加 API 密钥" />

            <el-form
              v-if="authStore.isAdmin && !isDemo"
              class="credential-form"
              label-position="top"
              autocomplete="off"
              @submit.prevent
            >
              <el-alert
                v-if="credentialSecretStoreUnavailable"
                type="error"
                :closable="false"
                title="当前后端无法访问 macOS 钥匙串，因此无法安全保存 API 密钥。解决办法：使用本机安全入口重新打开此页面。"
              />
              <el-alert
                v-else-if="credentialProviderType === 'OPENAI_COMPATIBLE' && !validatedCompatibleEndpoints.length"
                type="warning"
                :closable="false"
                title="当前没有地址验证通过的服务商。解决办法：先到“服务商配置”添加并验证接口地址。"
              />
              <div class="credential-grid">
                <el-form-item label="服务类型">
                  <el-select
                    v-model="credentialProviderType"
                    @change="handleCredentialProviderChange"
                  >
                    <el-option label="OpenAI 官方服务" value="OPENAI_OFFICIAL" />
                    <el-option label="第三方兼容服务" value="OPENAI_COMPATIBLE" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="credentialProviderType === 'OPENAI_COMPATIBLE'" label="绑定服务商">
                  <el-input :model-value="selectedCredentialEndpoint?.display_name || '请先选择并验证服务商'" disabled />
                  <div class="field-note">接口版本：当前版本（由系统自动选择）</div>
                </el-form-item>
                <el-form-item label="密钥名称">
                  <el-input
                    v-model="credentialName"
                    :disabled="Boolean(activeCredential)"
                    maxlength="100"
                    autocomplete="off"
                  />
                </el-form-item>
                <el-form-item v-if="credentialProviderType === 'OPENAI_OFFICIAL'" label="固定接口地址">
                  <el-input
                    v-model="credentialBaseUrl"
                    disabled
                    autocomplete="off"
                  />
                </el-form-item>
                <el-form-item label="API 密钥">
                  <el-input
                    v-model="credentialApiKey"
                    type="password"
                    autocomplete="new-password"
                    placeholder="仅本次请求使用，提交后立即清空"
                  />
                </el-form-item>
              </div>
              <div class="credential-actions">
                <el-button
                  type="primary"
                  :loading="credentialSubmitting"
                  :disabled="Boolean(activeCredential) || credentialSubmissionBlocked"
                  @click="saveCredential(false)"
                >
                  添加 API 密钥
                </el-button>
                <el-button
                  :loading="credentialSubmitting"
                  :disabled="!activeCredential || credentialSecretStoreUnavailable"
                  @click="saveCredential(true)"
                >
                  替换 API 密钥
                </el-button>
              </div>
              <div v-if="credentialSubmissionBlocked" class="action-hint">
                {{ credentialActionBlockedReason }}
              </div>
              <p class="security-note">
                API 密钥只由后端短暂接收并写入 macOS 钥匙串；不会进入数据库、日志或浏览器存储。
                已保存密钥永远不可回显，系统会自动绑定当前接口版本。
              </p>
            </el-form>
            <el-alert
              v-else-if="isDemo"
              type="info"
              :closable="false"
              title="隔离演示环境禁止保存、替换、验证或撤销真实 API 密钥。"
            />
            <el-alert
              v-else
              type="info"
              :closable="false"
              title="普通用户只能查看配置状态；API 密钥管理仅限管理员。"
            />

            <el-descriptions v-if="lastCredentialResult" class="capability-result" :column="2" border>
              <el-descriptions-item label="身份认证">{{ statusLabel(lastCredentialResult.capability.authentication_status) }}</el-descriptions-item>
              <el-descriptions-item label="服务商访问">{{ statusLabel(lastCredentialResult.capability.provider_access_status) }}</el-descriptions-item>
              <el-descriptions-item label="普通决策模型">{{ statusLabel(lastCredentialResult.capability.normal_model_status) }}</el-descriptions-item>
              <el-descriptions-item label="风险终审模型">{{ statusLabel(lastCredentialResult.capability.top_model_status) }}</el-descriptions-item>
              <el-descriptions-item label="结构化输出">{{ statusLabel(lastCredentialResult.capability.structured_output_status) }}</el-descriptions-item>
              <el-descriptions-item label="调用价格">{{ statusLabel(lastCredentialResult.capability.price_status) }}</el-descriptions-item>
              <el-descriptions-item label="调用限制">{{ statusLabel(lastCredentialResult.capability.budget_status) }}</el-descriptions-item>
              <el-descriptions-item label="检查时间">{{ lastCredentialResult.capability.checked_at }}</el-descriptions-item>
            </el-descriptions>
            <el-collapse class="advanced-information">
              <el-collapse-item title="高级信息（密钥标识与技术版本）" name="credential-technical">
                <el-table :data="credentials" size="small">
                  <el-table-column prop="credential_id" label="密钥标识" />
                  <el-table-column prop="endpoint_profile_version" label="技术版本" />
                  <el-table-column prop="status" label="技术状态" />
                  <el-table-column prop="last_error_code" label="技术错误码" />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane label="模型管理" name="models">
            <div class="status-line">
              <el-select v-model="selectedEndpointIdentity" placeholder="选择服务商" @change="handleSelectedEndpointChange">
                <el-option
                  v-for="item in validatedCompatibleEndpoints"
                  :key="`${item.endpoint_profile_id}@${item.profile_version}`"
                  :label="`${item.display_name}（当前版本）`"
                  :value="`${item.endpoint_profile_id}@${item.profile_version}`"
                />
              </el-select>
              <span>分别添加普通决策模型和风险终审模型；模型能力不会从其他服务商继承。</span>
              <el-button v-if="authStore.isAdmin && !isDemo" :loading="modelSubmitting" :disabled="!selectedEndpoint" @click="discoverEndpointModelCatalog">自动读取模型列表</el-button>
            </div>
            <el-table :data="endpointModels" size="small">
              <el-table-column prop="display_name" label="模型名称" min-width="180" />
              <el-table-column label="用途" min-width="230">
                <template #default="{ row }">{{ roleCapabilitiesLabel(row.role_capabilities) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="120"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
            </el-table>
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="服务商模型名称"><el-input v-model="modelRemoteName" autocomplete="off" /></el-form-item>
                <el-form-item label="显示名称"><el-input v-model="modelDisplayName" autocomplete="off" /></el-form-item>
                <el-form-item label="模型用途">
                  <el-checkbox-group v-model="modelRoles">
                    <el-checkbox value="NORMAL_TRADER">普通决策模型</el-checkbox>
                    <el-checkbox value="TOP_RISK_REVIEWER">风险终审模型</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="结构化能力">
                  <el-checkbox v-model="modelSupportsJsonSchema">JSON Schema</el-checkbox>
                  <el-checkbox v-model="modelSupportsToolCall">Tool Call</el-checkbox>
                </el-form-item>
                <el-form-item label="最大上下文 Token 数"><el-input-number v-model="modelMaxContext" :min="1" controls-position="right" /></el-form-item>
                <el-form-item label="最大输出 Token 数"><el-input-number v-model="modelMaxOutput" :min="1" controls-position="right" /></el-form-item>
              </div>
              <el-button type="primary" :loading="modelSubmitting" :disabled="Boolean(modelActionBlockedReason)" @click="createEndpointModelDefinition">添加模型</el-button>
              <div v-if="modelActionBlockedReason" class="action-hint">{{ modelActionBlockedReason }}</div>
            </el-form>
            <el-collapse class="advanced-information">
              <el-collapse-item title="调用价格" name="model-pricing">
                <el-table :data="endpointPrices" size="small">
                  <el-table-column prop="endpoint_model_id" label="模型标识" min-width="180" />
                  <el-table-column label="价格类型" min-width="155">
                    <template #default="{ row }">
                      <el-tag :type="row.pricing_source === 'SELF_HOSTED' ? 'success' : 'info'">
                        {{ row.pricing_source === 'SELF_HOSTED' ? '自建服务 / 价格0' : '外部服务真实价格' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="输入 / 1M"><template #default="{ row }">{{ row.input_price_per_million }} {{ row.currency }}</template></el-table-column>
                  <el-table-column label="输出 / 1M"><template #default="{ row }">{{ row.output_price_per_million }} {{ row.currency }}</template></el-table-column>
                </el-table>
                <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
                  <div class="credential-grid">
                    <el-form-item label="模型"><el-select v-model="priceModelIdentity"><el-option v-for="item in endpointModels" :key="`${item.endpoint_model_id}@${item.model_version}`" :label="item.display_name" :value="`${item.endpoint_model_id}@${item.model_version}`" /></el-select></el-form-item>
                    <el-form-item label="价格类型"><el-select v-model="pricePricingSource"><el-option label="外部付费服务 / 真实价格" value="PROVIDER_PUBLISHED" /><el-option label="自建服务 / 价格0" value="SELF_HOSTED" /></el-select></el-form-item>
                    <el-form-item label="货币"><el-input v-model="priceCurrency" maxlength="8" /></el-form-item>
                    <el-form-item label="输入价格 / 1M Token"><el-input v-model="priceInput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                    <el-form-item label="缓存输入价格 / 1M Token"><el-input v-model="priceCachedInput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                    <el-form-item label="输出价格 / 1M Token"><el-input v-model="priceOutput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                    <el-form-item label="生效时间"><el-input v-model="priceEffectiveAt" /></el-form-item>
                    <el-form-item label="价格来源说明"><el-input v-model="priceSource" maxlength="500" /></el-form-item>
                    <el-form-item label="确认"><el-checkbox v-model="priceVerified">{{ pricePricingSource === 'SELF_HOSTED' ? '确认该服务为自建服务且不按 Token 计费' : '已对照服务商真实价格来源' }}</el-checkbox></el-form-item>
                  </div>
                  <el-button type="primary" :loading="priceSubmitting" @click="createEndpointPriceVersion">保存调用价格</el-button>
                </el-form>
              </el-collapse-item>
              <el-collapse-item title="高级信息（技术模型、Prompt 与版本）" name="model-technical">
                <el-table :data="endpointModels" size="small">
                  <el-table-column prop="remote_model_name" label="远端模型名" />
                  <el-table-column prop="model_version" label="模型版本" />
                  <el-table-column prop="status" label="技术状态" />
                  <el-table-column prop="supports_json_schema" label="JSON Schema" />
                  <el-table-column prop="supports_tool_call" label="Tool Call" />
                </el-table>
                <el-table :data="promptProfiles" size="small">
                  <el-table-column prop="prompt_id" label="Prompt 标识" />
                  <el-table-column prop="prompt_version" label="版本" />
                  <el-table-column prop="role" label="技术角色" />
                  <el-table-column prop="schema_target" label="Schema" />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane label="模型角色" name="profiles">
            <el-table :data="modelStatus?.profiles || []" size="small">
              <el-table-column label="角色" min-width="180"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
              <el-table-column label="模型角色配置" min-width="230">
                <template #default="{ row }">{{ row.model_name }}</template>
              </el-table-column>
              <el-table-column label="状态" width="135">
                <template #default="{ row }"><el-tag :type="row.configured ? 'success' : 'warning'">{{ row.configured ? '已配置' : '未配置' }}</el-tag></template>
              </el-table-column>
            </el-table>
            <div v-if="authStore.isAdmin && !isDemo" class="primary-role-actions">
              <div>
                <el-button type="primary" :loading="assignmentSubmitting" :disabled="Boolean(roleActionBlockedReason('NORMAL_TRADER'))" @click="createRoleAssignment('NORMAL_TRADER')">创建普通模型角色</el-button>
                <small v-if="roleActionBlockedReason('NORMAL_TRADER')">{{ roleActionBlockedReason('NORMAL_TRADER') }}</small>
              </div>
              <div>
                <el-button type="primary" :loading="assignmentSubmitting" :disabled="Boolean(roleActionBlockedReason('TOP_RISK_REVIEWER'))" @click="createRoleAssignment('TOP_RISK_REVIEWER')">创建终审模型角色</el-button>
                <small v-if="roleActionBlockedReason('TOP_RISK_REVIEWER')">{{ roleActionBlockedReason('TOP_RISK_REVIEWER') }}</small>
              </div>
            </div>
            <el-collapse class="advanced-information">
              <el-collapse-item title="高级信息（精确角色绑定）" name="role-technical">
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="角色">
                  <el-radio-group v-model="assignmentRole" @change="handleAssignmentRoleChange">
                    <el-radio-button label="NORMAL_TRADER">普通决策</el-radio-button>
                    <el-radio-button label="TOP_RISK_REVIEWER">风险终审</el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="角色配置标识"><el-input v-model="assignmentProfileId" autocomplete="off" /></el-form-item>
                <el-form-item label="技术版本"><el-input v-model="assignmentProfileVersion" autocomplete="off" /></el-form-item>
                <el-form-item label="模型">
                  <el-select v-model="assignmentModelIdentity">
                    <el-option v-for="item in endpointModels" :key="`${item.endpoint_model_id}@${item.model_version}`" :label="item.remote_model_name" :value="`${item.endpoint_model_id}@${item.model_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="价格版本">
                  <el-select v-model="assignmentPriceIdentity">
                    <el-option v-for="item in endpointPrices.filter(price => price.endpoint_profile_id === selectedEndpoint?.endpoint_profile_id && price.endpoint_profile_version === selectedEndpoint?.profile_version && price.endpoint_model_id === selectedAssignmentModel?.endpoint_model_id)" :key="`${item.price_version_id}@${item.price_version}`" :label="`${item.currency} ${item.input_price_per_million}/${item.output_price_per_million}`" :value="`${item.price_version_id}@${item.price_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="API 密钥">
                  <el-select v-model="assignmentCredentialId">
                    <el-option v-for="item in compatibleCredentials" :key="item.credential_id" :label="item.credential_id" :value="item.credential_id" />
                  </el-select>
                </el-form-item>
              </div>
              <el-checkbox v-model="assignmentSameModelConfirmed">我明确确认普通决策和风险终审可使用同一模型</el-checkbox>
              <div class="credential-actions">
                <el-button type="primary" :loading="assignmentSubmitting" @click="assignCompatibleProfile">保存精确角色绑定</el-button>
              </div>
            </el-form>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="Prompt版本" name="prompts">
            <el-table :data="promptProfiles" size="small">
              <el-table-column prop="prompt_id" label="Prompt" min-width="230" />
              <el-table-column prop="prompt_version" label="版本" min-width="210" />
              <el-table-column prop="role" label="角色" min-width="170" />
              <el-table-column prop="schema_target" label="Schema" min-width="180" />
              <el-table-column label="Hash" min-width="150">
                <template #default="{ row }">{{ short(row.template_hash) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="价格" name="prices">
            <el-table :data="endpointPrices" size="small">
              <el-table-column prop="endpoint_model_id" label="模型ID" min-width="180" />
              <el-table-column label="价格类型" min-width="155">
                <template #default="{ row }">
                  <el-tag :type="row.pricing_source === 'SELF_HOSTED' ? 'success' : 'info'">
                    {{ row.pricing_source === 'SELF_HOSTED' ? '自建服务 / 价格0' : '服务商价格' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="输入 / 1M" min-width="130"><template #default="{ row }">{{ row.input_price_per_million }} {{ row.currency }}</template></el-table-column>
              <el-table-column label="缓存输入 / 1M" min-width="150"><template #default="{ row }">{{ row.cached_input_price_per_million ?? '—' }}</template></el-table-column>
              <el-table-column label="输出 / 1M" min-width="130"><template #default="{ row }">{{ row.output_price_per_million }} {{ row.currency }}</template></el-table-column>
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  {{ row.pricing_source === 'SELF_HOSTED' ? '自建声明已确认' : (row.verified ? '真实价格已核验' : '未核验') }}
                </template>
              </el-table-column>
              <el-table-column prop="effective_at" label="生效时间" min-width="190" />
            </el-table>
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="Endpoint模型">
                  <el-select v-model="priceModelIdentity">
                    <el-option v-for="item in endpointModels" :key="`${item.endpoint_model_id}@${item.model_version}`" :label="item.remote_model_name" :value="`${item.endpoint_model_id}@${item.model_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="价格类型">
                  <el-select v-model="pricePricingSource">
                    <el-option label="外部付费服务 / 真实价格" value="PROVIDER_PUBLISHED" />
                    <el-option label="自建服务 / 价格0" value="SELF_HOSTED" />
                  </el-select>
                </el-form-item>
                <el-form-item label="货币"><el-input v-model="priceCurrency" maxlength="8" /></el-form-item>
                <el-form-item label="输入价格 / 1M Token"><el-input v-model="priceInput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                <el-form-item label="缓存输入价格 / 1M Token"><el-input v-model="priceCachedInput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                <el-form-item label="输出价格 / 1M Token"><el-input v-model="priceOutput" inputmode="decimal" :disabled="pricePricingSource === 'SELF_HOSTED'" /></el-form-item>
                <el-form-item label="生效时间"><el-input v-model="priceEffectiveAt" /></el-form-item>
                <el-form-item label="价格来源说明"><el-input v-model="priceSource" maxlength="500" /></el-form-item>
                <el-form-item label="核验">
                  <el-checkbox v-model="priceVerified">
                    {{ pricePricingSource === 'SELF_HOSTED' ? '确认该Endpoint为自建服务且不按Token计费' : '已对照服务商真实价格来源' }}
                  </el-checkbox>
                </el-form-item>
              </div>
              <el-button type="primary" :loading="priceSubmitting" @click="createEndpointPriceVersion">登记价格版本</el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="能力检测" name="capabilities">
            <div class="capability-primary-action">
              <div>
                <strong>验证普通决策模型与风险终审模型</strong>
                <span>能力检测会使用最小请求验证认证、模型访问和结构化输出，不会创建订单。</span>
              </div>
              <el-button type="primary" :disabled="Boolean(capabilityActionBlockedReason)" @click="startCapabilityCheck">开始能力检测</el-button>
            </div>
            <div v-if="capabilityActionBlockedReason" class="action-hint">{{ capabilityActionBlockedReason }}</div>
            <el-table :data="modelStatus?.profiles || []" size="small">
              <el-table-column label="角色" min-width="180"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
              <el-table-column label="模型角色配置" min-width="230"><template #default="{ row }">{{ row.model_name }}</template></el-table-column>
              <el-table-column label="能力状态" width="180"><template #default="{ row }">{{ statusLabel(row.capability) }}</template></el-table-column>
              <el-table-column prop="last_check" label="最后检测" min-width="190" />
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="130" fixed="right">
                <template #default="{ row }"><el-button link @click="checkCapability(row)">检测此模型</el-button></template>
              </el-table-column>
            </el-table>
            <el-collapse class="advanced-information">
              <el-collapse-item title="高级信息（技术状态与版本）" name="capability-technical">
                <el-table :data="modelStatus?.profiles || []" size="small">
                  <el-table-column prop="profile_id" label="角色配置标识" />
                  <el-table-column prop="profile_version" label="技术版本" />
                  <el-table-column prop="role" label="技术角色" />
                  <el-table-column prop="capability" label="技术状态" />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane label="调用限制" name="budget">
            <el-descriptions v-if="modelStatus?.budget" class="budget-summary" :column="3" border>
              <el-descriptions-item label="今日调用次数">{{ modelStatus.budget.daily_calls }} / {{ modelStatus.budget.max_daily_calls }}</el-descriptions-item>
              <el-descriptions-item label="今日费用">{{ modelStatus.budget.daily_cost }} / {{ modelStatus.budget.max_daily_cost }} {{ modelStatus.budget.currency }}</el-descriptions-item>
              <el-descriptions-item label="剩余调用次数">{{ modelStatus.budget.remaining_calls }}</el-descriptions-item>
            </el-descriptions>
            <el-alert type="warning" :closable="false" title="外部付费服务必须登记真实价格；自建服务可以设置价格0，但 Token 数量、调用次数、并发、超时和重试限制继续有效。" />
            <el-collapse class="advanced-information">
              <el-collapse-item title="高级信息（限制策略与调用记录）" name="budget-technical">
                <el-descriptions v-if="modelStatus?.budget" :column="2" border size="small">
                  <el-descriptions-item label="策略标识">{{ modelStatus.budget.policy_id }}</el-descriptions-item>
                  <el-descriptions-item label="策略版本">{{ modelStatus.budget.policy_version }}</el-descriptions-item>
                  <el-descriptions-item label="技术币种">{{ modelStatus.budget.currency }}</el-descriptions-item>
                  <el-descriptions-item label="剩余费用">{{ modelStatus.budget.remaining_cost }}</el-descriptions-item>
                </el-descriptions>
                <el-table v-if="authStore.isAdmin && !isDemo" :data="modelRuns" size="small">
                  <el-table-column prop="created_at" label="时间" min-width="190" />
                  <el-table-column prop="run_mode" label="技术模式" min-width="190" />
                  <el-table-column label="角色"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
                  <el-table-column prop="model_name" label="模型" />
                  <el-table-column label="显示状态"><template #default="{ row }">{{ statusLabel(row.structured_output_status) }}</template></el-table-column>
                  <el-table-column prop="structured_output_status" label="技术状态" />
                  <el-table-column prop="total_tokens" label="Token 数" />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="能力检测" name="capabilities-hidden">
            <div class="capability-primary-action">
              <div>
                <strong>验证普通决策模型与风险终审模型</strong>
                <span>能力检测会使用最小请求验证认证、模型访问和结构化输出，不会创建订单。</span>
              </div>
              <el-button type="primary" :disabled="Boolean(capabilityActionBlockedReason)" @click="startCapabilityCheck">开始能力检测</el-button>
            </div>
            <div v-if="capabilityActionBlockedReason" class="action-hint">{{ capabilityActionBlockedReason }}</div>
            <el-table :data="modelStatus?.profiles || []" size="small">
              <el-table-column label="角色" min-width="180"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
              <el-table-column label="模型角色配置" min-width="230">
                <template #default="{ row }">{{ row.model_name }}</template>
              </el-table-column>
              <el-table-column label="能力状态" width="180"><template #default="{ row }">{{ statusLabel(row.capability) }}</template></el-table-column>
              <el-table-column prop="last_check" label="最后检测" min-width="190" />
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button link @click="checkCapability(row)">检测此模型</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-collapse class="advanced-information">
              <el-collapse-item title="高级信息（技术状态与版本）" name="capability-technical">
                <el-table :data="modelStatus?.profiles || []" size="small">
                  <el-table-column prop="profile_id" label="角色配置标识" />
                  <el-table-column prop="profile_version" label="技术版本" />
                  <el-table-column prop="role" label="技术角色" />
                  <el-table-column prop="capability" label="技术状态" />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="调用记录" name="runs">
            <el-table v-if="authStore.isAdmin && !isDemo" :data="modelRuns" size="small">
              <el-table-column prop="created_at" label="时间" min-width="190" />
              <el-table-column prop="run_mode" label="模式" min-width="190" />
              <el-table-column prop="role" label="角色" min-width="160" />
              <el-table-column prop="model_name" label="模型" min-width="150" />
              <el-table-column prop="structured_output_status" label="状态" min-width="170" />
              <el-table-column prop="total_tokens" label="Tokens" width="100" />
              <el-table-column prop="estimated_cost" label="成本" width="100" />
              <el-table-column prop="error_category" label="错误" min-width="170" />
            </el-table>
            <el-alert v-else type="info" :closable="false" title="模型调用审计仅管理员可见。" />
          </el-tab-pane>
        </el-tabs>
        <el-alert class="model-secret-notice" type="info" :closable="false" title="浏览器不会直接访问模型服务商，也不会显示已保存的 API 密钥。技术版本、Prompt 和调用审计仅在高级信息中展示。" />
      </el-tab-pane>
      <el-tab-pane v-if="!modelsOnly" label="完整性与版本" name="integrity">
        <h4>完整性</h4><pre>{{ pretty(integrity) }}</pre>
        <h4>版本（已脱敏）</h4><pre>{{ pretty(versions) }}</pre>
      </el-tab-pane>
    </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  alphaguardModelsApi,
  type EndpointModelDefinition,
  type EndpointPriceVersion,
  type ModelCredentialMutationResult,
  type ModelCredentialStatus,
  type ModelRunSummary,
  type ModelRuntimeStatus,
  type PromptProfileSummary,
  type ProviderConfigurationStatus,
  type ProviderEndpointProfile
} from '@/api/alphaguardModels'
import {
  alphaguardOperationsApi,
  type DataReadiness,
  type JobHealth,
  type OperationalAlert,
  type ServiceHealth,
  type SystemReadiness
} from '@/api/alphaguardOperations'

type ModelSettingsTab =
  | 'providers'
  | 'credentials'
  | 'models'
  | 'profiles'
  | 'prompts'
  | 'prices'
  | 'budget'
  | 'capabilities'
  | 'runs'

type EndpointEditorMode = 'closed' | 'create' | 'new-version'

const props = withDefaults(defineProps<{
  modelsOnly?: boolean
  embedded?: boolean
  initialModelTab?: ModelSettingsTab
}>(), {
  modelsOnly: false,
  embedded: false,
  initialModelTab: 'providers'
})
const emit = defineEmits<{
  (event: 'model-tab-change', tab: ModelSettingsTab): void
}>()

const authStore = useAuthStore()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const isCredentialHost =
  import.meta.env.VITE_ALPHAGUARD_CREDENTIAL_HOST === 'true'
const modelsOnly = computed(() => isCredentialHost || props.modelsOnly)
const activeOperationTab = ref(modelsOnly.value ? 'models' : 'services')
const activeModelTab = ref<ModelSettingsTab>(props.initialModelTab)
const loading = ref(false)
const loadError = ref('')
const readiness = ref<SystemReadiness | null>(null)
const services = ref<ServiceHealth[]>([])
const dataStatuses = ref<DataReadiness[]>([])
const jobs = ref<JobHealth[]>([])
const alerts = ref<OperationalAlert[]>([])
const manualJobs = ref<string[]>([])
const versions = ref<Record<string, unknown>>({})
const integrity = ref<Record<string, unknown>>({})
const modelStatus = ref<ModelRuntimeStatus | null>(null)
const credentials = ref<ModelCredentialStatus[]>([])
const promptProfiles = ref<PromptProfileSummary[]>([])
const modelRuns = ref<ModelRunSummary[]>([])
const providerEndpoints = ref<ProviderEndpointProfile[]>([])
const endpointModels = ref<EndpointModelDefinition[]>([])
const endpointPrices = ref<EndpointPriceVersion[]>([])
const configurationStatus = ref<ProviderConfigurationStatus | null>(null)
const lastConfigurationError = ref('')
const lastConfigurationTechnicalError = ref('')
const lastCredentialResult = ref<ModelCredentialMutationResult | null>(null)
const credentialProviderType = ref<'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'>('OPENAI_OFFICIAL')
const credentialName = ref('openai-primary')
const credentialBaseUrl = ref('https://api.openai.com/v1')
const selectedEndpointIdentity = ref('')
const credentialEndpointIdentity = ref('')
const credentialApiKey = ref('')
const credentialSubmitting = ref(false)
const credentialSecretStoreStatus = ref<'READY' | 'UNAVAILABLE'>('UNAVAILABLE')
const endpointDisplayName = ref('')
const endpointBaseUrl = ref('')
const endpointApiMode = ref<'OPENAI_CHAT_COMPLETIONS' | 'OPENAI_RESPONSES' | 'AUTO_DETECT'>('OPENAI_CHAT_COMPLETIONS')
const endpointAuthScheme = ref<'BEARER' | 'X_API_KEY'>('BEARER')
const endpointModelsEnabled = ref(true)
const endpointStructuredMode = ref<'NATIVE_JSON_SCHEMA' | 'TOOL_CALL' | 'JSON_ONLY' | 'UNKNOWN'>('UNKNOWN')
const endpointNotes = ref('')
const endpointTransmissionConfirmed = ref(false)
const endpointEditorMode = ref<EndpointEditorMode>('closed')
const providerSubmitting = ref(false)
const modelRemoteName = ref('')
const modelDisplayName = ref('')
const modelRoles = ref<Array<'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'>>([])
const modelSupportsJsonSchema = ref(false)
const modelSupportsToolCall = ref(false)
const modelMaxContext = ref<number | undefined>()
const modelMaxOutput = ref<number | undefined>()
const modelSubmitting = ref(false)
const priceModelIdentity = ref('')
const pricePricingSource = ref<'PROVIDER_PUBLISHED' | 'SELF_HOSTED'>('PROVIDER_PUBLISHED')
const priceInput = ref('')
const priceCachedInput = ref('')
const priceOutput = ref('')
const priceCurrency = ref('USD')
const priceEffectiveAt = ref(new Date().toISOString())
const priceSource = ref('服务商公开价格页面或账单说明')
const priceVerified = ref(false)
const priceSubmitting = ref(false)
const assignmentRole = ref<'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'>('NORMAL_TRADER')
const assignmentModelIdentity = ref('')
const assignmentPriceIdentity = ref('')
const assignmentCredentialId = ref('')
const assignmentProfileId = ref('alphaguard_normal_compatible')
const assignmentProfileVersion = ref('v1')
const assignmentSameModelConfirmed = ref(false)
const assignmentSubmitting = ref(false)
const selectedEndpoint = computed(() => providerEndpoints.value.find(
  item => `${item.endpoint_profile_id}@${item.profile_version}` === selectedEndpointIdentity.value
) || null)
const compatibleCredentials = computed(() => credentials.value.filter(
  item => item.provider_type === 'OPENAI_COMPATIBLE'
    && item.status !== 'REVOKED'
    && item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
))
const compatibleEndpoints = computed(() => providerEndpoints.value.filter(
  item => item.provider_type === 'OPENAI_COMPATIBLE'
))
const validatedCompatibleEndpoints = computed(() => compatibleEndpoints.value.filter(
  item => item.url_validation_status === 'PASS' && item.enabled
))
const selectedCredentialEndpoint = computed(() => validatedCompatibleEndpoints.value.find(
  item => `${item.endpoint_profile_id}@${item.profile_version}` === credentialEndpointIdentity.value
) || null)
const activeCredential = computed(() => credentials.value.find(item => {
  if (item.status === 'REVOKED') return false
  if (credentialProviderType.value === 'OPENAI_OFFICIAL') {
    return item.provider_type === 'OPENAI_OFFICIAL'
  }
  return item.provider_type === 'OPENAI_COMPATIBLE'
    && item.endpoint_profile_id === selectedCredentialEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedCredentialEndpoint.value?.profile_version
}) || null)
const selectedPriceModel = computed(() => endpointModels.value.find(
  item => `${item.endpoint_model_id}@${item.model_version}` === priceModelIdentity.value
) || null)
const selectedAssignmentModel = computed(() => endpointModels.value.find(
  item => `${item.endpoint_model_id}@${item.model_version}` === assignmentModelIdentity.value
) || null)
const selectedAssignmentPrice = computed(() => endpointPrices.value.find(
  item => `${item.price_version_id}@${item.price_version}` === assignmentPriceIdentity.value
) || null)
const credentialSecretStoreUnavailable = computed(
  () => credentialSecretStoreStatus.value !== 'READY'
)
const credentialSubmissionBlocked = computed(
  () => credentialSecretStoreUnavailable.value
    || (credentialProviderType.value === 'OPENAI_COMPATIBLE' && !selectedCredentialEndpoint.value)
)
const configurationComponents = computed(() => new Map(
  (configurationStatus.value?.components || []).map(item => [item.key, item])
))
const setupSteps = computed(() => [
  { key: 'provider', title: '① 添加服务商', complete: componentIsComplete('endpoint') },
  { key: 'credential', title: '② 添加 API 密钥', complete: componentIsComplete('credential') },
  {
    key: 'models',
    title: '③ 登记普通模型和终审模型',
    complete: ['normal_model', 'top_model', 'normal_price', 'top_price'].every(componentIsComplete)
  },
  {
    key: 'profiles',
    title: '④ 创建模型角色',
    complete: ['normal_profile', 'top_profile', 'assignments'].every(componentIsComplete)
  },
  { key: 'capability', title: '⑤ 执行能力检测', complete: componentIsComplete('capability') },
  { key: 'complete', title: '⑥ 完成配置', complete: Boolean(configurationStatus.value?.production_allowed) }
])
const setupActiveStep = computed(() => {
  const firstIncomplete = setupSteps.value.findIndex(step => !step.complete)
  return firstIncomplete < 0 ? setupSteps.value.length : firstIncomplete
})
const configurationNextAction = computed(() => {
  const firstIncomplete = setupSteps.value.find(step => !step.complete)
  if (!firstIncomplete) {
    return { complete: true, missing: '', actionLabel: '', tab: 'providers' as ModelSettingsTab }
  }
  const actions: Record<string, { missing: string; actionLabel: string; tab: ModelSettingsTab }> = {
    provider: { missing: '服务商', actionLabel: '添加服务商', tab: 'providers' },
    credential: { missing: 'API 密钥', actionLabel: '添加 API 密钥', tab: 'credentials' },
    models: { missing: '普通决策模型、风险终审模型或调用价格', actionLabel: '添加模型', tab: 'models' },
    profiles: { missing: '模型角色配置或角色绑定', actionLabel: '创建模型角色', tab: 'profiles' },
    capability: { missing: '能力检测', actionLabel: '开始能力检测', tab: 'capabilities' },
    complete: { missing: '调用限制确认', actionLabel: '查看调用限制', tab: 'budget' }
  }
  return { complete: false, ...actions[firstIncomplete.key] }
})
const credentialActionBlockedReason = computed(() => {
  if (credentialSecretStoreUnavailable.value) return '当前安全存储不可用，请使用本机安全入口。'
  if (credentialProviderType.value === 'OPENAI_COMPATIBLE' && !selectedCredentialEndpoint.value) {
    return '请先添加服务商并完成接口地址验证。'
  }
  if (activeCredential.value) return '当前服务商已经有 API 密钥；如需更换，请点击“替换 API 密钥”。'
  return ''
})
const modelActionBlockedReason = computed(() => {
  if (!selectedEndpoint.value) return '请先选择地址验证通过的服务商。'
  if (!modelRemoteName.value.trim()) return '请填写服务商模型名称。'
  if (!modelRoles.value.length) return '请选择“普通决策模型”或“风险终审模型”。'
  return ''
})
const capabilityActionBlockedReason = computed(() => {
  if (!componentIsComplete('normal_profile') || !componentIsComplete('top_profile')) {
    return '请先创建普通模型角色和终审模型角色。'
  }
  if (!componentIsComplete('assignments')) return '请先完成两个模型角色的绑定。'
  if (componentIsComplete('capability')) return '两个模型的能力检测均已通过。'
  return ''
})
const statusType = computed(() => readiness.value?.overall_status === 'READY_FOR_PAPER' ? 'success' : readiness.value?.overall_status === 'UNSAFE' ? 'danger' : 'warning')
const short = (value?: string) => value ? value.slice(0, 12) : '—'
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

const STATUS_LABELS: Record<string, string> = {
  READY: '可用',
  URL_VALIDATED: '地址验证通过',
  UNVERIFIED: '未验证',
  MISSING: '未配置',
  NOT_CONFIGURED: '未配置',
  DEGRADED: '异常',
  BLOCKED: '已阻止',
  BUDGET_BLOCKED: '已阻止',
  ACTIVE: '已启用',
  ENABLED: '已启用',
  REUSED: '已复用',
  CREATED: '已创建',
  CONFIGURED: '已配置',
  PASS: '验证通过',
  NOT_CHECKED: '未检测',
  CAPABILITY_CHECKED: '能力检测完成',
  CREDENTIAL_CONFIGURED: 'API 密钥已配置',
  AUTHENTICATED: '身份认证通过',
  MODELS_REGISTERED: '模型已登记',
  PRICES_CONFIGURED: '调用价格已配置',
  PROFILES_CONFIGURED: '模型角色已配置',
  SELF_HOSTED_ZERO: '自建服务 / 价格0',
  DISABLED: '已停用',
  REVOKED: '已撤销',
  REJECTED: '已拒绝',
  UNAVAILABLE: '不可用',
  FAILED: '失败',
  DRAFT: '待验证'
}
const COMPONENT_LABELS: Record<string, string> = {
  endpoint: '接口地址',
  credential: 'API 密钥',
  normal_model: '普通决策模型',
  top_model: '风险终审模型',
  normal_price: '普通模型调用价格',
  top_price: '终审模型调用价格',
  normal_profile: '普通模型角色配置',
  top_profile: '终审模型角色配置',
  assignments: '角色绑定',
  capability: '能力检测',
  budget: '调用限制'
}
const ERROR_GUIDANCE: Record<string, { summary: string; solution: string }> = {
  CREDENTIAL_BINDING_EXISTS: {
    summary: '该密钥绑定到了旧接口版本。',
    solution: '点击“添加 API 密钥”，系统会自动绑定当前服务商。'
  },
  UNAUTHORIZED: {
    summary: 'API 密钥未通过身份认证。',
    solution: '检查密钥是否有效，然后使用“替换 API 密钥”重新提交。'
  },
  PROJECT_ACCESS_DENIED: {
    summary: '当前密钥没有访问该服务项目的权限。',
    solution: '在服务商后台授权当前项目，或更换有权限的密钥。'
  },
  MODEL_NOT_FOUND: {
    summary: '服务商没有找到登记的模型。',
    solution: '在“模型管理”中核对服务商模型名称。'
  },
  BUDGET_PRICING_UNAVAILABLE: {
    summary: '模型尚未配置调用价格。',
    solution: '在“模型管理 → 调用价格”中登记真实价格或自建服务价格0。'
  },
  BUDGET_CURRENCY_MISMATCH: {
    summary: '调用价格币种与调用限制策略不一致。',
    solution: '登记与调用限制相同币种的价格版本。'
  },
  RATE_LIMITED: {
    summary: '服务商暂时限制了请求频率。',
    solution: '稍后重试，并检查“调用限制”。'
  },
  TIMEOUT: {
    summary: '服务商在限定时间内没有响应。',
    solution: '检查接口地址和网络状态后重试。'
  }
}

function statusLabel(status?: string | null): string {
  if (!status) return '未配置'
  return STATUS_LABELS[status] || status
}

function configurationComponentLabel(key: string): string {
  return COMPONENT_LABELS[key] || key
}

function reasonLabel(reason?: string | null): string {
  if (!reason) return ''
  return ERROR_GUIDANCE[reason]?.summary || statusLabel(reason)
}

function componentIsComplete(key: string): boolean {
  return Boolean(configurationComponents.value.get(key)?.complete)
}

function providerTypeLabel(type?: string): string {
  return type === 'OPENAI_OFFICIAL' ? 'OpenAI 官方服务' : '第三方兼容服务'
}

function roleLabel(role?: string): string {
  if (role === 'NORMAL_TRADER') return '普通决策模型'
  if (role === 'TOP_RISK_REVIEWER') return '风险终审模型'
  if (role === 'RESEARCH_AGENT') return '研究模型'
  return role || '未配置'
}

function roleCapabilitiesLabel(roles: string[]): string {
  return roles.length ? roles.map(roleLabel).join('、') : '未指定用途'
}

watch(
  () => props.initialModelTab,
  tab => {
    activeModelTab.value = tab
  }
)
watch(activeModelTab, tab => {
  emit('model-tab-change', tab)
  if (tab !== 'credentials') credentialApiKey.value = ''
  if (tab !== 'providers') endpointTransmissionConfirmed.value = false
})
watch(lastConfigurationError, value => {
  if (!value) lastConfigurationTechnicalError.value = ''
})
watch(pricePricingSource, source => {
  priceVerified.value = false
  if (source === 'SELF_HOSTED') {
    priceInput.value = '0'
    priceCachedInput.value = '0'
    priceOutput.value = '0'
    priceCurrency.value = 'USD'
    priceSource.value = '用户确认的自建服务，不按Token计费'
  } else {
    priceInput.value = ''
    priceCachedInput.value = ''
    priceOutput.value = ''
    priceSource.value = '服务商公开价格页面或账单说明'
  }
})

function endpointIdentity(endpoint: ProviderEndpointProfile): string {
  return `${endpoint.endpoint_profile_id}@${endpoint.profile_version}`
}

function compatibleCredentialDefaultName(endpoint: ProviderEndpointProfile | null): string {
  if (!endpoint) return 'compatible-primary'
  return `${endpoint.endpoint_profile_id}-${endpoint.profile_version}-primary`.slice(0, 100)
}

function configurationErrorMessage(action: string, error: unknown): string {
  const candidate = error as {
    message?: string
    response?: {
      status?: number
      data?: {
        detail?: string | {
          error_code?: string
          sanitized_message?: string
        }
      }
    }
  }
  const detail = candidate.response?.data?.detail
  const errorCode = typeof detail === 'object' && detail
    ? detail.error_code
    : undefined
  const sanitizedMessage = typeof detail === 'object' && detail
    ? detail.sanitized_message
    : typeof detail === 'string'
      ? detail
      : candidate.message
  const status = candidate.response?.status
  const guidance = errorCode ? ERROR_GUIDANCE[errorCode] : undefined
  lastConfigurationTechnicalError.value = [
    status ? `HTTP ${status}` : 'NETWORK_ERROR',
    errorCode || 'REQUEST_FAILED',
    sanitizedMessage || '请求失败且后端未返回可展示摘要'
  ].join(' · ')
  if (guidance) {
    return `${action}：${guidance.summary} 解决办法：${guidance.solution}`
  }
  return `${action}：请求未完成。解决办法：检查当前步骤的必填项和服务状态后重试；如仍失败，请展开“高级信息”查看技术详情。`
}

function showConfigurationFailure(action: string, error: unknown) {
  lastConfigurationError.value = configurationErrorMessage(action, error)
  ElMessage.error(lastConfigurationError.value)
}

function goToNextConfigurationStep() {
  activeModelTab.value = configurationNextAction.value.tab
  if (configurationNextAction.value.tab === 'providers' && !providerEndpoints.value.length) {
    openCreateProviderEndpoint()
  }
}

function roleActionBlockedReason(role: 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'): string {
  if (!selectedEndpoint.value) return '请先选择服务商。'
  if (!compatibleCredentials.value.length) return '请先添加当前服务商的 API 密钥。'
  const model = endpointModels.value.find(item => item.role_capabilities.includes(role))
  if (!model) return `请先添加${roleLabel(role)}。`
  const price = endpointPrices.value.find(item =>
    item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && item.endpoint_model_id === model.endpoint_model_id
  )
  if (!price) return `请先配置${roleLabel(role)}的调用价格。`
  return ''
}

function synchronizeEndpointSelections() {
  if (!providerEndpoints.value.some(item => endpointIdentity(item) === selectedEndpointIdentity.value)) {
    const preferred = validatedCompatibleEndpoints.value[0] || compatibleEndpoints.value[0] || providerEndpoints.value[0]
    selectedEndpointIdentity.value = preferred ? endpointIdentity(preferred) : ''
  }
  if (!validatedCompatibleEndpoints.value.some(item => endpointIdentity(item) === credentialEndpointIdentity.value)) {
    const preferred = validatedCompatibleEndpoints.value[0]
    credentialEndpointIdentity.value = preferred ? endpointIdentity(preferred) : ''
  }
  if (selectedEndpoint.value) {
    assignmentProfileVersion.value = selectedEndpoint.value.profile_version
  }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    if (modelsOnly.value) {
      const [m, c, p, runs, endpoints, prices] = await Promise.all([
        alphaguardModelsApi.status(),
        alphaguardModelsApi.credentials(),
        alphaguardModelsApi.prompts(),
        authStore.isAdmin && !isDemo
          ? alphaguardModelsApi.runs(100)
          : Promise.resolve({ data: { items: [] as ModelRunSummary[] } }),
        alphaguardModelsApi.endpoints(),
        alphaguardModelsApi.prices()
      ])
      modelStatus.value = m.data
      credentials.value = c.data.items
      credentialSecretStoreStatus.value = c.data.secret_store_status
      promptProfiles.value = p.data.items
      modelRuns.value = runs.data.items
      providerEndpoints.value = endpoints.data.items
      endpointPrices.value = prices.data.items
      synchronizeEndpointSelections()
      await Promise.all([
        loadEndpointModels(),
        loadSelectedEndpointConfiguration()
      ])
      if (activeCredential.value) {
        credentialName.value = activeCredential.value.credential_id
      }
      return
    }
    const [r, s, d, j, a, v, i, m, c, p, runs, endpoints, prices] = await Promise.all([
      alphaguardOperationsApi.readiness(),
      alphaguardOperationsApi.services(),
      alphaguardOperationsApi.dataReadiness(),
      alphaguardOperationsApi.jobs(),
      alphaguardOperationsApi.alerts(),
      alphaguardOperationsApi.versions(),
      alphaguardOperationsApi.integrity(),
      alphaguardModelsApi.status(),
      alphaguardModelsApi.credentials(),
      alphaguardModelsApi.prompts(),
      authStore.isAdmin && !isDemo
        ? alphaguardModelsApi.runs(100)
        : Promise.resolve({ data: { items: [] as ModelRunSummary[] } }),
      alphaguardModelsApi.endpoints(),
      alphaguardModelsApi.prices()
    ])
    readiness.value = r.data
    services.value = s.data.items
    dataStatuses.value = d.data.items
    jobs.value = j.data.items
    manualJobs.value = j.data.allowed_manual_jobs || []
    alerts.value = a.data.items
    versions.value = v.data
    integrity.value = i.data
    modelStatus.value = m.data
    credentials.value = c.data.items
    credentialSecretStoreStatus.value = c.data.secret_store_status
    promptProfiles.value = p.data.items
    modelRuns.value = runs.data.items
    providerEndpoints.value = endpoints.data.items
    endpointPrices.value = prices.data.items
    synchronizeEndpointSelections()
    await Promise.all([
      loadEndpointModels(),
      loadSelectedEndpointConfiguration()
    ])
    if (activeCredential.value) {
      credentialName.value = activeCredential.value.credential_id
    }
  } catch (error: any) {
    loadError.value = `${error?.message || '未知错误'}；页面不会用缓存状态伪装服务健康。`
  } finally {
    loading.value = false
  }
}
async function loadEndpointModels() {
  if (!selectedEndpoint.value) {
    endpointModels.value = []
    return
  }
  const response = await alphaguardModelsApi.endpointModels(
    selectedEndpoint.value.endpoint_profile_id,
    selectedEndpoint.value.profile_version
  )
  endpointModels.value = response.data.items
}

async function loadSelectedEndpointConfiguration() {
  if (!selectedEndpoint.value || selectedEndpoint.value.provider_type !== 'OPENAI_COMPATIBLE') {
    configurationStatus.value = null
    return
  }
  try {
    const response = await alphaguardModelsApi.endpointConfigurationStatus(
      selectedEndpoint.value.endpoint_profile_id,
      selectedEndpoint.value.profile_version
    )
    configurationStatus.value = response.data
  } catch (error) {
    configurationStatus.value = null
    showConfigurationFailure('刷新配置完整性失败', error)
  }
}

async function handleSelectedEndpointChange() {
  priceModelIdentity.value = ''
  assignmentModelIdentity.value = ''
  assignmentPriceIdentity.value = ''
  assignmentCredentialId.value = ''
  assignmentProfileVersion.value = selectedEndpoint.value?.profile_version || 'v1'
  await Promise.all([
    loadEndpointModels(),
    loadSelectedEndpointConfiguration()
  ])
}

function clearEndpointEditor() {
  endpointEditorMode.value = 'closed'
  endpointDisplayName.value = ''
  endpointBaseUrl.value = ''
  endpointApiMode.value = 'OPENAI_CHAT_COMPLETIONS'
  endpointAuthScheme.value = 'BEARER'
  endpointModelsEnabled.value = true
  endpointStructuredMode.value = 'UNKNOWN'
  endpointNotes.value = ''
  endpointTransmissionConfirmed.value = false
}

function openCreateProviderEndpoint() {
  clearEndpointEditor()
  endpointEditorMode.value = 'create'
}

type EndpointRow = Record<string, unknown> | ProviderEndpointProfile

function openNewEndpointVersion(row: EndpointRow) {
  const endpoint = 'endpoint_profile_id' in row && 'profile_version' in row
    ? endpointFromRow(row as Record<string, unknown>)
    : null
  if (!endpoint || endpoint.provider_type !== 'OPENAI_COMPATIBLE') {
    ElMessage.error('只有第三方兼容服务商可以创建新版本')
    return
  }
  selectedEndpointIdentity.value = endpointIdentity(endpoint)
  endpointEditorMode.value = 'new-version'
  endpointDisplayName.value = endpoint.display_name
  endpointBaseUrl.value = endpoint.base_url || ''
  endpointApiMode.value = endpoint.api_mode || 'OPENAI_CHAT_COMPLETIONS'
  endpointAuthScheme.value = endpoint.auth_scheme || 'BEARER'
  endpointModelsEnabled.value = endpoint.models_endpoint_enabled !== false
  endpointStructuredMode.value = endpoint.structured_output_mode || 'UNKNOWN'
  endpointNotes.value = endpoint.notes || ''
  endpointTransmissionConfirmed.value = false
}

function cancelEndpointEdit() {
  clearEndpointEditor()
}

async function continueProviderEndpoint(row: EndpointRow) {
  const endpoint = endpointFromRow(row)
  if (!endpoint) return
  selectedEndpointIdentity.value = endpointIdentity(endpoint)
  endpointTransmissionConfirmed.value = false
  endpointEditorMode.value = 'closed'
  await handleSelectedEndpointChange()
}

function goToCredentialSettings(endpoint: ProviderEndpointProfile) {
  selectedEndpointIdentity.value = endpointIdentity(endpoint)
  if (endpoint.provider_type === 'OPENAI_COMPATIBLE') {
    credentialProviderType.value = 'OPENAI_COMPATIBLE'
    credentialEndpointIdentity.value = endpointIdentity(endpoint)
    const existing = credentials.value.find(item => item.status !== 'REVOKED'
      && item.provider_type === 'OPENAI_COMPATIBLE'
      && item.endpoint_profile_id === endpoint.endpoint_profile_id
      && item.endpoint_profile_version === endpoint.profile_version)
    credentialName.value = existing?.credential_id || compatibleCredentialDefaultName(endpoint)
  }
  activeModelTab.value = 'credentials'
}

function handleCredentialProviderChange() {
  credentialApiKey.value = ''
  if (credentialProviderType.value === 'OPENAI_COMPATIBLE') {
    const preferred = validatedCompatibleEndpoints.value[0]
    credentialEndpointIdentity.value = preferred ? endpointIdentity(preferred) : ''
    selectedEndpointIdentity.value = credentialEndpointIdentity.value
    const existing = credentials.value.find(item => item.status !== 'REVOKED'
      && item.provider_type === 'OPENAI_COMPATIBLE'
      && item.endpoint_profile_id === preferred?.endpoint_profile_id
      && item.endpoint_profile_version === preferred?.profile_version)
    credentialName.value = existing?.credential_id || compatibleCredentialDefaultName(preferred || null)
    return
  }
  const official = credentials.value.find(item => item.status !== 'REVOKED' && item.provider_type === 'OPENAI_OFFICIAL')
  credentialName.value = official?.credential_id || 'openai-primary'
}

function handleCredentialEndpointChange() {
  credentialApiKey.value = ''
  if (selectedCredentialEndpoint.value) {
    selectedEndpointIdentity.value = endpointIdentity(selectedCredentialEndpoint.value)
    const existing = credentials.value.find(item => item.status !== 'REVOKED'
      && item.provider_type === 'OPENAI_COMPATIBLE'
      && item.endpoint_profile_id === selectedCredentialEndpoint.value?.endpoint_profile_id
      && item.endpoint_profile_version === selectedCredentialEndpoint.value?.profile_version)
    credentialName.value = existing?.credential_id || compatibleCredentialDefaultName(selectedCredentialEndpoint.value)
  }
}

function endpointStateType(state: ProviderEndpointProfile['state']): 'success' | 'warning' | 'danger' | 'info' {
  if (state === 'READY' || state === 'URL_VALIDATED' || state === 'CAPABILITY_CHECKED') return 'success'
  if (state === 'DRAFT' || state === 'DEGRADED') return 'warning'
  if (state === 'REJECTED' || state === 'DISABLED') return 'danger'
  return 'info'
}

async function createProviderEndpoint() {
  if (!endpointDisplayName.value.trim() || !endpointBaseUrl.value.trim()) {
    ElMessage.error('请填写服务商名称和 HTTPS 接口地址')
    return
  }
  if (endpointEditorMode.value === 'new-version' && selectedEndpoint.value?.provider_type !== 'OPENAI_COMPATIBLE') {
    ElMessage.error('请选择已有第三方服务商后再创建新版本')
    return
  }
  if (endpointEditorMode.value === 'create') {
    try {
      const requestedOrigin = new URL(endpointBaseUrl.value.trim()).origin
      const existing = compatibleEndpoints.value.find(item => {
        if (!item.base_url) return false
        return new URL(item.base_url).origin === requestedOrigin
      })
      if (existing) {
        clearEndpointEditor()
        selectedEndpointIdentity.value = endpointIdentity(existing)
        ElMessage.warning('该服务地址已经登记，请继续配置已有服务商或显式创建新版本')
        return
      }
    } catch {
      ElMessage.error('请输入合法的 HTTPS 接口地址')
      return
    }
  }
  providerSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const editorMode = endpointEditorMode.value
    const response = await alphaguardModelsApi.createEndpoint({
      display_name: endpointDisplayName.value.trim(),
      provider_type: 'OPENAI_COMPATIBLE',
      base_url: endpointBaseUrl.value.trim(),
      api_mode: endpointApiMode.value,
      auth_scheme: endpointAuthScheme.value,
      models_endpoint_enabled: endpointModelsEnabled.value,
      structured_output_mode: endpointStructuredMode.value,
      notes: endpointNotes.value.trim() || undefined,
      ...(endpointEditorMode.value === 'new-version'
        ? {
            endpoint_profile_id: selectedEndpoint.value?.endpoint_profile_id,
            create_new_version: true
          }
        : {})
    })
    const item = response.data.item
    const identity = endpointIdentity(item)
    selectedEndpointIdentity.value = identity
    clearEndpointEditor()
    ElMessage.success(
      editorMode === 'new-version'
        ? `接口新版本${statusLabel(response.data.result)}，请继续执行地址验证`
        : `服务商${statusLabel(response.data.result)}，请继续执行地址验证`
    )
    await load()
    selectedEndpointIdentity.value = identity
  } catch (error) {
    showConfigurationFailure('保存接口配置失败', error)
  } finally {
    providerSubmitting.value = false
  }
}
function endpointFromRow(row: EndpointRow): ProviderEndpointProfile | null {
  if (typeof row.endpoint_profile_id !== 'string' || typeof row.profile_version !== 'string') return null
  return providerEndpoints.value.find(item => item.endpoint_profile_id === row.endpoint_profile_id && item.profile_version === row.profile_version) || null
}
async function validateProviderEndpoint(row: EndpointRow) {
  const endpoint = endpointFromRow(row)
  if (!endpoint || endpoint.provider_type !== 'OPENAI_COMPATIBLE') return
  if (!endpointTransmissionConfirmed.value) {
    ElMessage.error('必须先确认将研究数据发送到该第三方服务')
    return
  }
  await ElMessageBox.confirm(
    'AlphaGuard 将验证接口地址、DNS 结果、实际连接 IP 和重定向。验证通过后，模型输入可能发送到该第三方服务。',
    '确认第三方数据传输与接口验证',
    { type: 'warning', confirmButtonText: '确认并验证' }
  )
  providerSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const response = await alphaguardModelsApi.validateEndpoint(endpoint.endpoint_profile_id, {
      profile_version: endpoint.profile_version,
      confirm_data_transmission: true
    })
    const validatedIdentity = `${response.data.endpoint_profile_id}@${response.data.profile_version}`
    selectedEndpointIdentity.value = validatedIdentity
    ElMessage.success(response.data.url_validation_status === 'PASS' ? '接口地址验证通过，可以添加 API 密钥' : '接口地址已安全拒绝')
    await load()
    if (response.data.url_validation_status === 'PASS') {
      credentialProviderType.value = 'OPENAI_COMPATIBLE'
      credentialEndpointIdentity.value = validatedIdentity
      handleCredentialEndpointChange()
      activeModelTab.value = 'credentials'
    }
  } catch (error) {
    showConfigurationFailure('验证接口地址失败', error)
  } finally {
    endpointTransmissionConfirmed.value = false
    providerSubmitting.value = false
  }
}
async function createEndpointModelDefinition() {
  if (!selectedEndpoint.value || !modelRemoteName.value.trim() || !modelRoles.value.length) {
    ElMessage.error('请选择地址验证通过的服务商，并填写模型名称和用途')
    return
  }
  modelSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const response = await alphaguardModelsApi.createEndpointModel(selectedEndpoint.value.endpoint_profile_id, {
      endpoint_profile_version: selectedEndpoint.value.profile_version,
      remote_model_name: modelRemoteName.value.trim(),
      display_name: modelDisplayName.value.trim() || modelRemoteName.value.trim(),
      role_capabilities: [...modelRoles.value],
      supports_json_schema: modelSupportsJsonSchema.value,
      supports_tool_call: modelSupportsToolCall.value,
      max_context_tokens: modelMaxContext.value,
      max_output_tokens: modelMaxOutput.value
    })
    modelRemoteName.value = ''
    modelDisplayName.value = ''
    modelRoles.value = []
    ElMessage.success(`模型${statusLabel(response.data.result)}`)
    await Promise.all([
      loadEndpointModels(),
      loadSelectedEndpointConfiguration()
    ])
  } catch (error) {
    showConfigurationFailure('登记模型失败', error)
  } finally {
    modelSubmitting.value = false
  }
}
async function discoverEndpointModelCatalog() {
  if (!selectedEndpoint.value) {
    ElMessage.error('请选择地址验证通过的服务商')
    return
  }
  modelSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const credential = compatibleCredentials.value[0]
    const response = await alphaguardModelsApi.discoverEndpointModels(
      selectedEndpoint.value.endpoint_profile_id,
      {
        endpoint_profile_version: selectedEndpoint.value.profile_version,
        credential_id: credential?.credential_id
      }
    )
    endpointModels.value = response.data.items
    ElMessage.success(response.data.items.length ? '模型列表已读取并保存' : '服务商没有返回模型，请使用“添加模型”手工登记')
    await loadSelectedEndpointConfiguration()
  } catch (error) {
    showConfigurationFailure('探测模型目录失败', error)
  } finally {
    modelSubmitting.value = false
  }
}
async function createEndpointPriceVersion() {
  if (!selectedEndpoint.value || !selectedPriceModel.value || !priceVerified.value) {
    ElMessage.error(pricePricingSource.value === 'SELF_HOSTED' ? '请选择模型并确认自建服务声明' : '请选择模型并确认真实价格来源已核验')
    return
  }
  priceSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const response = await alphaguardModelsApi.createPrice({
      endpoint_profile_id: selectedEndpoint.value.endpoint_profile_id,
      endpoint_profile_version: selectedEndpoint.value.profile_version,
      endpoint_model_id: selectedPriceModel.value.endpoint_model_id,
      endpoint_model_version: selectedPriceModel.value.model_version,
      pricing_source: pricePricingSource.value,
      input_price_per_million: priceInput.value,
      cached_input_price_per_million: priceCachedInput.value || undefined,
      output_price_per_million: priceOutput.value,
      currency: priceCurrency.value,
      effective_at: new Date(priceEffectiveAt.value).toISOString(),
      source_description: priceSource.value.trim(),
      verified: true
    })
    priceInput.value = ''
    priceCachedInput.value = ''
    priceOutput.value = ''
    priceVerified.value = false
    ElMessage.success(pricePricingSource.value === 'SELF_HOSTED' ? `自建服务价格0${statusLabel(response.data.result)}` : `调用价格${statusLabel(response.data.result)}`)
    const prices = await alphaguardModelsApi.prices()
    endpointPrices.value = prices.data.items
    await loadSelectedEndpointConfiguration()
  } catch (error) {
    showConfigurationFailure('登记价格失败', error)
  } finally {
    priceSubmitting.value = false
  }
}
async function assignCompatibleProfile() {
  if (!selectedEndpoint.value || !selectedAssignmentModel.value || !selectedAssignmentPrice.value || !assignmentCredentialId.value) {
    ElMessage.error('服务商、模型、调用价格和 API 密钥必须全部精确选择')
    return
  }
  assignmentSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    await alphaguardModelsApi.assignCompatibleProfile({
      role: assignmentRole.value,
      profile_id: assignmentProfileId.value.trim(),
      profile_version: assignmentProfileVersion.value.trim(),
      endpoint_profile_id: selectedEndpoint.value.endpoint_profile_id,
      endpoint_profile_version: selectedEndpoint.value.profile_version,
      endpoint_model_id: selectedAssignmentModel.value.endpoint_model_id,
      endpoint_model_version: selectedAssignmentModel.value.model_version,
      credential_id: assignmentCredentialId.value,
      price_version_id: selectedAssignmentPrice.value.price_version_id,
      price_version: selectedAssignmentPrice.value.price_version,
      prompt_profile_id: assignmentRole.value === 'NORMAL_TRADER' ? 'normal_trade_plan_prompt' : 'top_risk_review_prompt',
      explicit_same_model_confirmation: assignmentSameModelConfirmed.value
    })
    ElMessage.success(`${roleLabel(assignmentRole.value)}角色已创建并绑定`)
    await load()
  } catch (error) {
    showConfigurationFailure('创建模型角色与角色绑定失败', error)
  } finally {
    assignmentSubmitting.value = false
  }
}
async function createRoleAssignment(role: 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER') {
  const blockedReason = roleActionBlockedReason(role)
  if (blockedReason) {
    ElMessage.warning(blockedReason)
    return
  }
  const model = endpointModels.value.find(item => item.role_capabilities.includes(role))
  const price = endpointPrices.value.find(item =>
    item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && item.endpoint_model_id === model?.endpoint_model_id
  )
  const credential = compatibleCredentials.value[0]
  if (!model || !price || !credential) return
  assignmentRole.value = role
  assignmentProfileId.value = role === 'NORMAL_TRADER'
    ? 'alphaguard_normal_compatible'
    : 'alphaguard_top_compatible'
  assignmentProfileVersion.value = selectedEndpoint.value?.profile_version || 'v1'
  assignmentModelIdentity.value = `${model.endpoint_model_id}@${model.model_version}`
  assignmentPriceIdentity.value = `${price.price_version_id}@${price.price_version}`
  assignmentCredentialId.value = credential.credential_id
  await assignCompatibleProfile()
}
function handleAssignmentRoleChange() {
  assignmentProfileId.value = assignmentRole.value === 'NORMAL_TRADER'
    ? 'alphaguard_normal_compatible'
    : 'alphaguard_top_compatible'
  assignmentProfileVersion.value = selectedEndpoint.value?.profile_version || 'v1'
}
async function saveCredential(replace: boolean) {
  if (credentialProviderType.value === 'OPENAI_COMPATIBLE' && !selectedCredentialEndpoint.value) {
    ElMessage.error('请先验证服务商接口地址，再添加 API 密钥')
    return
  }
  if (!credentialApiKey.value) {
    ElMessage.error('请输入 API 密钥')
    return
  }
  const resolvedCredentialName = credentialProviderType.value === 'OPENAI_COMPATIBLE'
    && ['openai-primary', 'compatible-primary'].includes(credentialName.value.trim())
    ? compatibleCredentialDefaultName(selectedCredentialEndpoint.value)
    : credentialName.value.trim()
  const payload = {
    api_key: credentialApiKey.value,
    base_url: credentialProviderType.value === 'OPENAI_OFFICIAL' ? credentialBaseUrl.value.trim() || undefined : undefined
  }
  // Clear component state before the network operation. The request client
  // redacts api_key from all diagnostics and never writes it to browser storage.
  credentialApiKey.value = ''
  credentialSubmitting.value = true
  try {
    lastConfigurationError.value = ''
    const response = replace && activeCredential.value
      ? await alphaguardModelsApi.replaceCredential(
          activeCredential.value.credential_id,
          payload
        )
      : await alphaguardModelsApi.createCredential({
          provider: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? 'openai_compatible' : 'openai',
          provider_type: credentialProviderType.value,
          endpoint_profile_id: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? selectedCredentialEndpoint.value?.endpoint_profile_id : undefined,
          endpoint_profile_version: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? selectedCredentialEndpoint.value?.profile_version : undefined,
          credential_name: resolvedCredentialName,
          ...payload
        })
    lastCredentialResult.value = response.data
    if (!response.data.stored) {
      const errorCode = response.data.last_error_code || 'VALIDATION_FAILED'
      const guidance = ERROR_GUIDANCE[errorCode]
      lastConfigurationTechnicalError.value = [
        errorCode,
        response.data.sanitized_message || '后端已安全拒绝本次提交'
      ].join(' · ')
      lastConfigurationError.value = guidance
        ? `API 密钥未保存：${guidance.summary} 解决办法：${guidance.solution}`
        : 'API 密钥未保存：验证没有通过。解决办法：检查密钥和当前服务商是否匹配后重新提交。'
      ElMessage.error(lastConfigurationError.value)
    } else {
      ElMessage.success(
        replace ? '新 API 密钥已验证并安全替换' : 'API 密钥已写入安全存储'
      )
    }
    await load()
  } catch (error) {
    showConfigurationFailure(replace ? '替换凭证失败' : '保存凭证失败', error)
  } finally {
    payload.api_key = ''
    credentialApiKey.value = ''
    credentialSubmitting.value = false
  }
}
function credentialFromRow(
  row: Record<string, unknown>
): Pick<ModelCredentialStatus, 'credential_id' | 'provider'> | null {
  if (
    typeof row.credential_id !== 'string'
    || typeof row.provider !== 'string'
  ) return null
  return {
    credential_id: row.credential_id,
    provider: row.provider
  }
}
function credentialProviderLabel(row: Record<string, unknown>): string {
  if (typeof row.endpoint_profile_id !== 'string') return 'OpenAI 官方服务'
  const endpoint = providerEndpoints.value.find(item =>
    item.endpoint_profile_id === row.endpoint_profile_id
    && item.profile_version === row.endpoint_profile_version
  )
  return endpoint?.display_name || '第三方兼容服务'
}
function credentialVersionLabel(row: Record<string, unknown>): string {
  if (typeof row.endpoint_profile_id !== 'string') return '系统版本'
  return row.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && row.endpoint_profile_version === selectedEndpoint.value?.profile_version
    ? '当前版本'
    : '旧版本'
}
async function verifyCredential(row: Record<string, unknown>) {
  const credential = credentialFromRow(row)
  if (!credential) {
    ElMessage.error('凭证身份无效，验证已阻断')
    return
  }
  try {
    lastConfigurationError.value = ''
    const response = await alphaguardModelsApi.verifyCredential(credential.credential_id)
    lastCredentialResult.value = response.data
    ElMessage.success('凭证能力检查已完成')
    await load()
  } catch (error) {
    showConfigurationFailure('验证凭证失败', error)
  }
}
async function revokeCredential(row: Record<string, unknown>) {
  const credential = credentialFromRow(row)
  if (!credential) {
    ElMessage.error('凭证身份无效，撤销已阻断')
    return
  }
  await ElMessageBox.confirm(
    '撤销会从Keychain删除Secret并立即阻断后续模型调用；历史能力检查和审计不会删除。',
    '确认撤销模型凭证',
    { type: 'warning', confirmButtonText: '撤销凭证' }
  )
  try {
    lastConfigurationError.value = ''
    await alphaguardModelsApi.revokeCredential(credential.credential_id)
    lastCredentialResult.value = null
    ElMessage.success('凭证已撤销')
    await load()
  } catch (error) {
    showConfigurationFailure('撤销凭证失败', error)
  }
}
async function checkCapability(row: Record<string, unknown>) {
  if (typeof row.profile_id !== 'string' || typeof row.profile_version !== 'string') {
    ElMessage.error('模型角色配置无效，能力检测已阻断')
    return
  }
  await ElMessageBox.confirm(
    '将使用已登记的模型角色执行最小、不可交易的真实网络能力检测，并受调用限制约束。不会创建订单。',
    '确认模型能力检查',
    { type: 'warning', confirmButtonText: '执行检查' }
  )
  await alphaguardModelsApi.capabilityCheck({
    profile_id: row.profile_id,
    profile_version: row.profile_version,
    idempotency_key: `ui-${row.profile_id}-${Date.now()}`,
    network: true
  })
  ElMessage.success('能力检查已完成')
  await load()
}
async function startCapabilityCheck() {
  if (capabilityActionBlockedReason.value) {
    ElMessage.warning(capabilityActionBlockedReason.value)
    return
  }
  const target = (modelStatus.value?.profiles || []).find(item =>
    item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && item.capability !== 'READY'
  )
  if (!target) {
    ElMessage.success('两个模型的能力检测均已通过')
    return
  }
  await checkCapability(target as unknown as Record<string, unknown>)
}
async function runJob(name: string) {
  await alphaguardOperationsApi.runJob(name)
  ElMessage.success(`${name} 已进入幂等队列`)
}
async function ack(row: Record<string, unknown>) {
  const alert = row as unknown as OperationalAlert
  await alphaguardOperationsApi.acknowledgeAlert(alert.alert_id)
  await load()
}
async function resolve(row: Record<string, unknown>) {
  const alert = row as unknown as OperationalAlert
  const result = await ElMessageBox.prompt('输入解决说明；历史告警不会删除', '解决告警', { inputValidator: value => String(value || '').length >= 3 || '至少3个字符' })
  await alphaguardOperationsApi.resolveAlert(alert.alert_id, result.value)
  await load()
}
onMounted(load)
</script>

<style scoped>
.page-grid { display: grid; gap: 16px; }
.safety-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.safety-strip > div { min-height: 58px; padding: 10px 14px; border: 1px solid var(--el-border-color-light); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.safety-strip span { color: var(--el-text-color-secondary); font-size: 12px; }
.header-row, .status-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.status-line > span { min-width: 0; flex: 1 1 320px; overflow-wrap: anywhere; }
.provider-toolbar, .provider-detail__header, .endpoint-editor__header { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.provider-toolbar { margin-bottom: 14px; }
.provider-toolbar > div, .provider-detail__header > div:first-child, .endpoint-editor__header > div { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.provider-toolbar span, .provider-detail__header span, .endpoint-editor__header span, .field-note { color: var(--el-text-color-secondary); font-size: 12px; }
.provider-detail { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--el-border-color-light); }
.provider-detail__header { margin-bottom: 14px; }
.provider-detail__actions { display: flex; gap: 8px; }
.endpoint-validation { display: grid; gap: 14px; align-items: start; margin-top: 16px; }
.endpoint-validation .el-button { width: fit-content; }
.endpoint-editor__header { margin-bottom: 14px; }
.admin-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-light); }
.model-tabs, .budget-summary, .model-secret-notice, .capability-result { margin-top: 16px; }
.configuration-guide { display: grid; gap: 14px; margin-top: 16px; }
.next-action-card, .capability-primary-action { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px; border: 1px solid var(--el-color-primary-light-7); border-radius: 8px; background: var(--el-color-primary-light-9); }
.next-action-card > div, .capability-primary-action > div { display: grid; gap: 6px; }
.next-action-card span, .capability-primary-action span { color: var(--el-text-color-secondary); }
.configuration-feedback, .configuration-completeness { margin-top: 14px; }
.configuration-completeness { padding: 14px; border: 1px solid var(--el-border-color-light); border-radius: 6px; background: var(--el-fill-color-lighter); }
.configuration-completeness__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.configuration-completeness__header > div { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.configuration-completeness__header span { color: var(--el-text-color-secondary); font-size: 12px; }
.configuration-completeness__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 12px; }
.configuration-component { display: grid; gap: 6px; align-content: start; padding: 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 4px; background: var(--el-bg-color); }
.configuration-component small { color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
.advanced-information { margin-top: 14px; }
.action-hint { margin-top: 8px; color: var(--el-color-warning); font-size: 13px; line-height: 1.5; }
.primary-role-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.primary-role-actions > div { display: grid; gap: 7px; }
.primary-role-actions small { color: var(--el-text-color-secondary); }
.credential-form { margin-top: 18px; padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.credential-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.credential-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.security-note { margin: 12px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
pre { max-height: 420px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
:deep(.operations-tabs--embedded) { border: 0; box-shadow: none; }
:deep(.operations-tabs--embedded > .el-tabs__header),
:deep(.model-tabs--embedded > .el-tabs__header) { display: none; }
:deep(.operations-tabs--embedded > .el-tabs__content) { padding: 0; }
@media (max-width: 700px) {
  .safety-strip, .credential-grid, .primary-role-actions { grid-template-columns: 1fr; }
  .next-action-card, .capability-primary-action { align-items: stretch; flex-direction: column; }
}
</style>
