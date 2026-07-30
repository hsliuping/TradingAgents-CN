<template>
  <div v-loading="loading" class="page-grid">
    <el-result v-if="loadError" icon="warning" title="运维状态加载失败" :sub-title="loadError"><template #extra><el-button @click="load">重试</el-button></template></el-result>
    <template v-else>
    <section class="safety-strip">
      <div><span>SYSTEM_MODE</span><strong>{{ readiness?.system_mode || 'UNKNOWN' }}</strong></div>
      <div><span>LIVE_TRADING_ENABLED</span><el-tag type="danger">{{ readiness?.live_trading_enabled ?? false }}</el-tag></div>
      <div><span>LIVE_EXECUTION_ALLOWED</span><el-tag type="danger">{{ readiness?.live_execution_allowed ?? false }}</el-tag></div>
    </section>
    <el-card shadow="never">
      <template #header><div class="header-row"><strong>系统准备度</strong><el-button @click="load">刷新</el-button></div></template>
      <div class="status-line">
        <el-tag :type="statusType" size="large">{{ readiness?.overall_status || 'UNKNOWN' }}</el-tag>
        <span>Report {{ short(readiness?.report_hash) }}</span>
        <span>Config {{ short(readiness?.config_hash) }}</span>
        <el-tag type="danger">LIVE_READY = false</el-tag>
      </div>
      <el-alert v-if="readiness?.blocking_items.length" type="warning" :closable="false" :title="readiness.blocking_items.join('；')" />
    </el-card>

    <el-tabs type="border-card">
      <el-tab-pane label="服务">
        <el-table :data="services" size="small">
          <el-table-column prop="service_name" label="服务" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="latency_ms" label="延迟(ms)" />
          <el-table-column prop="error_code" label="错误代码" min-width="190" />
          <el-table-column prop="sanitized_message" label="脱敏摘要" min-width="260" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="数据准备">
        <el-table :data="dataStatuses" size="small">
          <el-table-column prop="component" label="组件" min-width="190" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="record_count" label="记录" width="90" />
          <el-table-column label="覆盖" min-width="190"><template #default="{ row }">{{ row.coverage_start || '—' }} ～ {{ row.coverage_end || '—' }}</template></el-table-column>
          <el-table-column label="阻断" min-width="300"><template #default="{ row }">{{ row.blocking_reasons.join('；') }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="任务">
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
      <el-tab-pane label="告警">
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
      <el-tab-pane label="Models & API">
        <div class="status-line">
          <el-tag :type="modelStatus?.status === 'READY' ? 'success' : modelStatus?.status === 'DEGRADED' ? 'warning' : 'danger'">
            {{ modelStatus?.status || 'NOT_CONFIGURED' }}
          </el-tag>
          <span>只有精确登记并通过网络能力检查的 Normal / Top Profile 才能进入生产链。</span>
        </div>
        <el-tabs class="model-tabs">
          <el-tab-pane label="服务商">
            <el-table :data="providerEndpoints" size="small">
              <el-table-column prop="display_name" label="服务商" min-width="170" />
              <el-table-column prop="provider_type" label="类型" min-width="180" />
              <el-table-column label="版本" width="100">
                <template #default="{ row }">{{ row.profile_version }}</template>
              </el-table-column>
              <el-table-column prop="state" label="Endpoint状态" min-width="150" />
              <el-table-column prop="url_validation_status" label="URL安全" min-width="120" />
              <el-table-column prop="structured_output_mode" label="结构化输出" min-width="180" />
              <el-table-column label="生产使用" width="120">
                <template #default="{ row }">{{ row.production_allowed ? 'ENABLED' : 'DISABLED' }}</template>
              </el-table-column>
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="130">
                <template #default="{ row }">
                  <el-button
                    link
                    :disabled="row.provider_type !== 'OPENAI_COMPATIBLE' || row.state !== 'DRAFT'"
                    @click="validateProviderEndpoint(row)"
                  >验证URL</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-form
              v-if="authStore.isAdmin && !isDemo"
              class="credential-form"
              label-position="top"
              autocomplete="off"
              @submit.prevent
            >
              <div class="credential-grid">
                <el-form-item label="服务商名称">
                  <el-input v-model="endpointDisplayName" maxlength="120" autocomplete="off" />
                </el-form-item>
                <el-form-item label="Provider类型">
                  <el-input model-value="OPENAI_COMPATIBLE" disabled />
                </el-form-item>
                <el-form-item label="HTTPS Base URL">
                  <el-input v-model="endpointBaseUrl" placeholder="https://provider.example/v1" autocomplete="off" />
                </el-form-item>
                <el-form-item label="API模式">
                  <el-select v-model="endpointApiMode">
                    <el-option label="Chat Completions" value="OPENAI_CHAT_COMPLETIONS" />
                    <el-option label="Responses" value="OPENAI_RESPONSES" />
                    <el-option label="Auto Detect" value="AUTO_DETECT" />
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
                    <el-option label="Native JSON Schema" value="NATIVE_JSON_SCHEMA" />
                    <el-option label="Tool Call" value="TOOL_CALL" />
                    <el-option label="JSON Only" value="JSON_ONLY" />
                    <el-option label="Unknown" value="UNKNOWN" />
                  </el-select>
                </el-form-item>
                <el-form-item label="模型发现">
                  <el-switch v-model="endpointModelsEnabled" active-text="支持 /models" inactive-text="手工登记" />
                </el-form-item>
                <el-form-item label="备注">
                  <el-input v-model="endpointNotes" maxlength="500" autocomplete="off" />
                </el-form-item>
              </div>
              <el-checkbox v-model="endpointTransmissionConfirmed">
                我确认将研究数据发送到该第三方服务，并已评估其隐私、数据保留和安全政策
              </el-checkbox>
              <div class="credential-actions">
                <el-button type="primary" :loading="providerSubmitting" @click="createProviderEndpoint">保存Endpoint DRAFT</el-button>
              </div>
              <p class="security-note">
                保存DRAFT不会发送凭证。URL验证会检查HTTPS、DNS公网地址、实际连接目标和重定向；跨Origin跳转一律拒绝。
              </p>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="API凭证">
            <el-table :data="credentials" size="small">
              <el-table-column prop="provider" label="Provider" width="120" />
              <el-table-column prop="provider_type" label="类型" min-width="180" />
              <el-table-column label="Endpoint版本" min-width="190">
                <template #default="{ row }">{{ row.endpoint_profile_id ? `${row.endpoint_profile_id}@${row.endpoint_profile_version}` : '系统固定' }}</template>
              </el-table-column>
              <el-table-column prop="credential_id" label="凭证名称" min-width="180" />
              <el-table-column label="已保存Key" width="130">
                <template #default="{ row }">{{ row.configured ? '••••••••' : '未配置' }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="130" />
              <el-table-column prop="secret_store_status" label="Secret Store" width="140" />
              <el-table-column prop="last_verified_at" label="最后验证" min-width="190" />
              <el-table-column prop="last_error_code" label="错误代码" min-width="180" />
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="150">
                <template #default="{ row }">
                  <el-button link @click="verifyCredential(row)">验证</el-button>
                  <el-button link type="danger" @click="revokeCredential(row)">撤销</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!credentials.length" description="尚未配置模型API凭证" />

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
                title="当前后端无法访问macOS Keychain；凭证保存保持关闭。请使用本机安全后端入口。"
              />
              <div class="credential-grid">
                <el-form-item label="Provider类型">
                  <el-select v-model="credentialProviderType" :disabled="Boolean(activeCredential)">
                    <el-option label="OpenAI Official" value="OPENAI_OFFICIAL" />
                    <el-option label="OpenAI Compatible" value="OPENAI_COMPATIBLE" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="credentialProviderType === 'OPENAI_COMPATIBLE'" label="已验证Endpoint版本">
                  <el-select v-model="selectedEndpointIdentity" @change="loadEndpointModels">
                    <el-option
                      v-for="item in validatedCompatibleEndpoints"
                      :key="`${item.endpoint_profile_id}@${item.profile_version}`"
                      :label="`${item.display_name} @ ${item.profile_version}`"
                      :value="`${item.endpoint_profile_id}@${item.profile_version}`"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="凭证名称">
                  <el-input
                    v-model="credentialName"
                    :disabled="Boolean(activeCredential)"
                    maxlength="100"
                    autocomplete="off"
                  />
                </el-form-item>
                <el-form-item v-if="credentialProviderType === 'OPENAI_OFFICIAL'" label="固定 Base URL">
                  <el-input
                    v-model="credentialBaseUrl"
                    disabled
                    autocomplete="off"
                  />
                </el-form-item>
                <el-form-item label="API Key">
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
                  :disabled="Boolean(activeCredential) || credentialSecretStoreUnavailable"
                  @click="saveCredential(false)"
                >
                  保存并验证
                </el-button>
                <el-button
                  :loading="credentialSubmitting"
                  :disabled="!activeCredential || credentialSecretStoreUnavailable"
                  @click="saveCredential(true)"
                >
                  替换凭证
                </el-button>
              </div>
              <p class="security-note">
                Key只由后端请求接收并写入macOS Keychain；不会进入MongoDB、日志、
                localStorage、sessionStorage或Cookie。已保存Key永远不可回显，也不能跨Endpoint版本复用。
              </p>
            </el-form>
            <el-alert
              v-else-if="isDemo"
              type="info"
              :closable="false"
              title="隔离Demo禁止保存、替换、验证或撤销真实API凭证。"
            />
            <el-alert
              v-else
              type="info"
              :closable="false"
              title="普通用户只能查看凭证和能力状态；凭证管理仅限数据库管理员。"
            />

            <el-descriptions v-if="lastCredentialResult" class="capability-result" :column="2" border>
              <el-descriptions-item label="认证">{{ lastCredentialResult.capability.authentication_status }}</el-descriptions-item>
              <el-descriptions-item label="Provider">{{ lastCredentialResult.capability.provider_access_status }}</el-descriptions-item>
              <el-descriptions-item label="Normal">{{ lastCredentialResult.capability.normal_model_status }}</el-descriptions-item>
              <el-descriptions-item label="Top">{{ lastCredentialResult.capability.top_model_status }}</el-descriptions-item>
              <el-descriptions-item label="结构化输出">{{ lastCredentialResult.capability.structured_output_status }}</el-descriptions-item>
              <el-descriptions-item label="价格">{{ lastCredentialResult.capability.price_status }}</el-descriptions-item>
              <el-descriptions-item label="预算">{{ lastCredentialResult.capability.budget_status }}</el-descriptions-item>
              <el-descriptions-item label="检查时间">{{ lastCredentialResult.capability.checked_at }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="模型目录">
            <div class="status-line">
              <el-select v-model="selectedEndpointIdentity" placeholder="选择Endpoint版本" @change="loadEndpointModels">
                <el-option
                  v-for="item in validatedCompatibleEndpoints"
                  :key="`${item.endpoint_profile_id}@${item.profile_version}`"
                  :label="`${item.display_name} @ ${item.profile_version}`"
                  :value="`${item.endpoint_profile_id}@${item.profile_version}`"
                />
              </el-select>
              <span>模型名称和能力仅属于所选Endpoint，不继承官方OpenAI能力。</span>
              <el-button v-if="authStore.isAdmin && !isDemo" :loading="modelSubmitting" @click="discoverEndpointModelCatalog">探测 /models</el-button>
            </div>
            <el-table :data="endpointModels" size="small">
              <el-table-column prop="remote_model_name" label="远端模型" min-width="180" />
              <el-table-column prop="display_name" label="显示名称" min-width="160" />
              <el-table-column label="角色能力" min-width="230">
                <template #default="{ row }">{{ row.role_capabilities.join(', ') || '未分配' }}</template>
              </el-table-column>
              <el-table-column prop="supports_json_schema" label="JSON Schema" width="130" />
              <el-table-column prop="supports_tool_call" label="Tool Call" width="120" />
              <el-table-column prop="status" label="状态" width="120" />
            </el-table>
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="远端模型名称"><el-input v-model="modelRemoteName" autocomplete="off" /></el-form-item>
                <el-form-item label="显示名称"><el-input v-model="modelDisplayName" autocomplete="off" /></el-form-item>
                <el-form-item label="角色能力">
                  <el-checkbox-group v-model="modelRoles">
                    <el-checkbox value="NORMAL_TRADER">Normal</el-checkbox>
                    <el-checkbox value="TOP_RISK_REVIEWER">Top</el-checkbox>
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="结构化能力">
                  <el-checkbox v-model="modelSupportsJsonSchema">JSON Schema</el-checkbox>
                  <el-checkbox v-model="modelSupportsToolCall">Tool Call</el-checkbox>
                </el-form-item>
                <el-form-item label="最大上下文Tokens"><el-input-number v-model="modelMaxContext" :min="1" controls-position="right" /></el-form-item>
                <el-form-item label="最大输出Tokens"><el-input-number v-model="modelMaxOutput" :min="1" controls-position="right" /></el-form-item>
              </div>
              <el-button type="primary" :loading="modelSubmitting" @click="createEndpointModelDefinition">手工登记模型</el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="模型Profile">
            <el-table :data="modelStatus?.profiles || []" size="small">
              <el-table-column prop="role" label="角色" min-width="180" />
              <el-table-column label="Profile" min-width="230">
                <template #default="{ row }">{{ row.profile_id }}@{{ row.profile_version }}</template>
              </el-table-column>
              <el-table-column prop="provider" label="Provider" width="110" />
              <el-table-column prop="model_name" label="模型" min-width="150" />
              <el-table-column label="Prompt" min-width="220">
                <template #default="{ row }">{{ row.prompt_id || '—' }}@{{ row.prompt_version || '—' }}</template>
              </el-table-column>
              <el-table-column label="Configured" width="135">
                <template #default="{ row }"><el-tag :type="row.configured ? 'success' : 'danger'">{{ row.configured ? 'CONFIGURED' : 'NOT_CONFIGURED' }}</el-tag></template>
              </el-table-column>
            </el-table>
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="角色">
                  <el-radio-group v-model="assignmentRole" @change="handleAssignmentRoleChange">
                    <el-radio-button label="NORMAL_TRADER">Normal</el-radio-button>
                    <el-radio-button label="TOP_RISK_REVIEWER">Top</el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="Profile ID"><el-input v-model="assignmentProfileId" autocomplete="off" /></el-form-item>
                <el-form-item label="Profile版本"><el-input v-model="assignmentProfileVersion" autocomplete="off" /></el-form-item>
                <el-form-item label="Endpoint模型">
                  <el-select v-model="assignmentModelIdentity">
                    <el-option v-for="item in endpointModels" :key="`${item.endpoint_model_id}@${item.model_version}`" :label="item.remote_model_name" :value="`${item.endpoint_model_id}@${item.model_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="价格版本">
                  <el-select v-model="assignmentPriceIdentity">
                    <el-option v-for="item in endpointPrices.filter(price => price.endpoint_profile_id === selectedEndpoint?.endpoint_profile_id && price.endpoint_model_id === selectedAssignmentModel?.endpoint_model_id)" :key="`${item.price_version_id}@${item.price_version}`" :label="`${item.currency} ${item.input_price_per_million}/${item.output_price_per_million}`" :value="`${item.price_version_id}@${item.price_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="凭证">
                  <el-select v-model="assignmentCredentialId">
                    <el-option v-for="item in compatibleCredentials" :key="item.credential_id" :label="item.credential_id" :value="item.credential_id" />
                  </el-select>
                </el-form-item>
              </div>
              <el-checkbox v-model="assignmentSameModelConfirmed">我明确确认Normal和Top可使用同一Endpoint模型</el-checkbox>
              <div class="credential-actions">
                <el-button type="primary" :loading="assignmentSubmitting" @click="assignCompatibleProfile">显式分配Profile</el-button>
              </div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="Prompt版本">
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

          <el-tab-pane label="价格">
            <el-table :data="endpointPrices" size="small">
              <el-table-column prop="endpoint_model_id" label="模型ID" min-width="180" />
              <el-table-column label="输入 / 1M" min-width="130"><template #default="{ row }">{{ row.input_price_per_million }} {{ row.currency }}</template></el-table-column>
              <el-table-column label="缓存输入 / 1M" min-width="150"><template #default="{ row }">{{ row.cached_input_price_per_million ?? '—' }}</template></el-table-column>
              <el-table-column label="输出 / 1M" min-width="130"><template #default="{ row }">{{ row.output_price_per_million }} {{ row.currency }}</template></el-table-column>
              <el-table-column prop="verified" label="已核验" width="100" />
              <el-table-column prop="effective_at" label="生效时间" min-width="190" />
            </el-table>
            <el-form v-if="authStore.isAdmin && !isDemo" class="credential-form" label-position="top" @submit.prevent>
              <div class="credential-grid">
                <el-form-item label="Endpoint模型">
                  <el-select v-model="priceModelIdentity">
                    <el-option v-for="item in endpointModels" :key="`${item.endpoint_model_id}@${item.model_version}`" :label="item.remote_model_name" :value="`${item.endpoint_model_id}@${item.model_version}`" />
                  </el-select>
                </el-form-item>
                <el-form-item label="货币"><el-input v-model="priceCurrency" maxlength="8" /></el-form-item>
                <el-form-item label="输入价格 / 1M Token"><el-input v-model="priceInput" inputmode="decimal" /></el-form-item>
                <el-form-item label="缓存输入价格 / 1M Token"><el-input v-model="priceCachedInput" inputmode="decimal" /></el-form-item>
                <el-form-item label="输出价格 / 1M Token"><el-input v-model="priceOutput" inputmode="decimal" /></el-form-item>
                <el-form-item label="生效时间"><el-input v-model="priceEffectiveAt" /></el-form-item>
                <el-form-item label="价格来源说明"><el-input v-model="priceSource" maxlength="500" /></el-form-item>
                <el-form-item label="核验">
                  <el-checkbox v-model="priceVerified">已对照服务商正式价格来源</el-checkbox>
                </el-form-item>
              </div>
              <el-button type="primary" :loading="priceSubmitting" @click="createEndpointPriceVersion">登记价格版本</el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="预算">
            <el-descriptions v-if="modelStatus?.budget" class="budget-summary" :column="3" border>
              <el-descriptions-item label="Daily Calls">{{ modelStatus.budget.daily_calls }} / {{ modelStatus.budget.max_daily_calls }}</el-descriptions-item>
              <el-descriptions-item label="Daily Cost">{{ modelStatus.budget.daily_cost }} / {{ modelStatus.budget.max_daily_cost }} {{ modelStatus.budget.currency }}</el-descriptions-item>
              <el-descriptions-item label="Budget Policy">{{ modelStatus.budget.policy_id }}@{{ modelStatus.budget.policy_version }}</el-descriptions-item>
            </el-descriptions>
            <el-alert type="warning" :closable="false" title="价格版本未核验时，预算状态必须保持BLOCKED，不能执行付费模型调用。" />
          </el-tab-pane>

          <el-tab-pane label="能力检查">
            <el-table :data="modelStatus?.profiles || []" size="small">
              <el-table-column prop="role" label="角色" min-width="180" />
              <el-table-column label="Profile" min-width="230">
                <template #default="{ row }">{{ row.profile_id }}@{{ row.profile_version }}</template>
              </el-table-column>
              <el-table-column prop="capability" label="Capability" width="180" />
              <el-table-column prop="last_check" label="Last Check" min-width="190" />
              <el-table-column v-if="authStore.isAdmin && !isDemo" label="操作" width="130">
                <template #default="{ row }">
                  <el-button link @click="checkCapability(row)">能力检查</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="调用记录">
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
        <el-alert class="model-secret-notice" type="info" :closable="false" title="浏览器不会直接访问OpenAI，也不提供显示已保存Key、任意Prompt或未登记模型调用入口。" />
      </el-tab-pane>
      <el-tab-pane label="完整性与版本">
        <h4>完整性</h4><pre>{{ pretty(integrity) }}</pre>
        <h4>版本（已脱敏）</h4><pre>{{ pretty(versions) }}</pre>
      </el-tab-pane>
    </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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

const authStore = useAuthStore()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const isCredentialHost =
  import.meta.env.VITE_ALPHAGUARD_CREDENTIAL_HOST === 'true'
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
const lastCredentialResult = ref<ModelCredentialMutationResult | null>(null)
const credentialProviderType = ref<'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'>('OPENAI_OFFICIAL')
const credentialName = ref('openai-primary')
const credentialBaseUrl = ref('https://api.openai.com/v1')
const selectedEndpointIdentity = ref('')
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
const activeCredential = computed(() => credentials.value.find(item => {
  if (item.status === 'REVOKED') return false
  if (credentialProviderType.value === 'OPENAI_OFFICIAL') {
    return item.provider_type === 'OPENAI_OFFICIAL'
  }
  return item.provider_type === 'OPENAI_COMPATIBLE'
    && item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
}) || null)
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
const statusType = computed(() => readiness.value?.overall_status === 'READY_FOR_PAPER' ? 'success' : readiness.value?.overall_status === 'UNSAFE' ? 'danger' : 'warning')
const short = (value?: string) => value ? value.slice(0, 12) : '—'
const pretty = (value: unknown) => JSON.stringify(value, null, 2)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
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
    if (!selectedEndpointIdentity.value) {
      const preferred = validatedCompatibleEndpoints.value[0] || compatibleEndpoints.value[0]
      if (preferred) selectedEndpointIdentity.value = `${preferred.endpoint_profile_id}@${preferred.profile_version}`
    }
    await loadEndpointModels()
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
async function createProviderEndpoint() {
  if (!endpointDisplayName.value.trim() || !endpointBaseUrl.value.trim()) {
    ElMessage.error('请填写服务商名称和HTTPS Base URL')
    return
  }
  providerSubmitting.value = true
  try {
    const response = await alphaguardModelsApi.createEndpoint({
      display_name: endpointDisplayName.value.trim(),
      provider_type: 'OPENAI_COMPATIBLE',
      base_url: endpointBaseUrl.value.trim(),
      api_mode: endpointApiMode.value,
      auth_scheme: endpointAuthScheme.value,
      models_endpoint_enabled: endpointModelsEnabled.value,
      structured_output_mode: endpointStructuredMode.value,
      notes: endpointNotes.value.trim() || undefined
    })
    const item = response.data.item
    selectedEndpointIdentity.value = `${item.endpoint_profile_id}@${item.profile_version}`
    endpointDisplayName.value = ''
    endpointBaseUrl.value = ''
    endpointNotes.value = ''
    endpointTransmissionConfirmed.value = false
    ElMessage.success('Endpoint Profile已保存为DRAFT，请继续执行安全验证')
    await load()
  } finally {
    providerSubmitting.value = false
  }
}
function endpointFromRow(row: Record<string, unknown>): ProviderEndpointProfile | null {
  if (typeof row.endpoint_profile_id !== 'string' || typeof row.profile_version !== 'string') return null
  return providerEndpoints.value.find(item => item.endpoint_profile_id === row.endpoint_profile_id && item.profile_version === row.profile_version) || null
}
async function validateProviderEndpoint(row: Record<string, unknown>) {
  const endpoint = endpointFromRow(row)
  if (!endpoint || endpoint.provider_type !== 'OPENAI_COMPATIBLE') return
  if (!endpointTransmissionConfirmed.value) {
    ElMessage.error('必须先确认将研究数据发送到该第三方服务')
    return
  }
  await ElMessageBox.confirm(
    'AlphaGuard将验证输入URL、DNS结果、实际连接IP和重定向。验证通过后，模型输入可能发送到该第三方服务。',
    '确认第三方数据传输与Endpoint验证',
    { type: 'warning', confirmButtonText: '确认并验证' }
  )
  providerSubmitting.value = true
  try {
    const response = await alphaguardModelsApi.validateEndpoint(endpoint.endpoint_profile_id, {
      profile_version: endpoint.profile_version,
      confirm_data_transmission: true
    })
    selectedEndpointIdentity.value = `${response.data.endpoint_profile_id}@${response.data.profile_version}`
    ElMessage.success(response.data.url_validation_status === 'PASS' ? 'Endpoint URL安全验证通过' : 'Endpoint已安全拒绝')
    await load()
  } finally {
    providerSubmitting.value = false
  }
}
async function createEndpointModelDefinition() {
  if (!selectedEndpoint.value || !modelRemoteName.value.trim() || !modelRoles.value.length) {
    ElMessage.error('请选择已验证Endpoint，并填写模型名称和角色能力')
    return
  }
  modelSubmitting.value = true
  try {
    await alphaguardModelsApi.createEndpointModel(selectedEndpoint.value.endpoint_profile_id, {
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
    ElMessage.success('Endpoint模型定义已create-only登记')
    await loadEndpointModels()
  } finally {
    modelSubmitting.value = false
  }
}
async function discoverEndpointModelCatalog() {
  if (!selectedEndpoint.value) {
    ElMessage.error('请选择已验证Endpoint')
    return
  }
  modelSubmitting.value = true
  try {
    const credential = compatibleCredentials.value[0]
    const response = await alphaguardModelsApi.discoverEndpointModels(
      selectedEndpoint.value.endpoint_profile_id,
      {
        endpoint_profile_version: selectedEndpoint.value.profile_version,
        credential_id: credential?.credential_id
      }
    )
    endpointModels.value = response.data.items
    ElMessage.success(response.data.items.length ? '模型目录快照已保存' : 'Provider未返回模型，请手工登记')
  } finally {
    modelSubmitting.value = false
  }
}
async function createEndpointPriceVersion() {
  if (!selectedEndpoint.value || !selectedPriceModel.value || !priceVerified.value) {
    ElMessage.error('请选择模型并确认价格来源已核验')
    return
  }
  priceSubmitting.value = true
  try {
    await alphaguardModelsApi.createPrice({
      endpoint_profile_id: selectedEndpoint.value.endpoint_profile_id,
      endpoint_profile_version: selectedEndpoint.value.profile_version,
      endpoint_model_id: selectedPriceModel.value.endpoint_model_id,
      endpoint_model_version: selectedPriceModel.value.model_version,
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
    ElMessage.success('Decimal价格版本已create-only登记')
    const prices = await alphaguardModelsApi.prices()
    endpointPrices.value = prices.data.items
  } finally {
    priceSubmitting.value = false
  }
}
async function assignCompatibleProfile() {
  if (!selectedEndpoint.value || !selectedAssignmentModel.value || !selectedAssignmentPrice.value || !assignmentCredentialId.value) {
    ElMessage.error('Endpoint、模型、价格和凭证必须全部精确选择')
    return
  }
  assignmentSubmitting.value = true
  try {
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
    ElMessage.success(`${assignmentRole.value} Profile已显式绑定`)
    await load()
  } finally {
    assignmentSubmitting.value = false
  }
}
function handleAssignmentRoleChange() {
  assignmentProfileId.value = assignmentRole.value === 'NORMAL_TRADER'
    ? 'alphaguard_normal_compatible'
    : 'alphaguard_top_compatible'
}
async function saveCredential(replace: boolean) {
  if (!credentialApiKey.value) {
    ElMessage.error('请输入API Key')
    return
  }
  const resolvedCredentialName = credentialProviderType.value === 'OPENAI_COMPATIBLE'
    && credentialName.value.trim() === 'openai-primary'
    ? `${selectedEndpoint.value?.endpoint_profile_id || 'compatible'}-primary`
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
    const response = replace && activeCredential.value
      ? await alphaguardModelsApi.replaceCredential(
          activeCredential.value.credential_id,
          payload
        )
      : await alphaguardModelsApi.createCredential({
          provider: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? 'openai_compatible' : 'openai',
          provider_type: credentialProviderType.value,
          endpoint_profile_id: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? selectedEndpoint.value?.endpoint_profile_id : undefined,
          endpoint_profile_version: credentialProviderType.value === 'OPENAI_COMPATIBLE' ? selectedEndpoint.value?.profile_version : undefined,
          credential_name: resolvedCredentialName,
          ...payload
        })
    lastCredentialResult.value = response.data
    ElMessage.success(
      response.data.stored
        ? replace ? '新凭证已验证并安全替换' : '凭证已写入安全Secret Store'
        : '凭证验证未通过，未保存'
    )
    await load()
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
async function verifyCredential(row: Record<string, unknown>) {
  const credential = credentialFromRow(row)
  if (!credential) {
    ElMessage.error('凭证身份无效，验证已阻断')
    return
  }
  const response = await alphaguardModelsApi.verifyCredential(credential.credential_id)
  lastCredentialResult.value = response.data
  ElMessage.success('凭证能力检查已完成')
  await load()
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
  await alphaguardModelsApi.revokeCredential(credential.credential_id)
  lastCredentialResult.value = null
  ElMessage.success('凭证已撤销')
  await load()
}
async function checkCapability(row: Record<string, unknown>) {
  if (typeof row.profile_id !== 'string' || typeof row.profile_version !== 'string') {
    ElMessage.error('模型Profile身份无效，能力检查已阻断')
    return
  }
  await ElMessageBox.confirm(
    '将使用已登记 Profile 执行最小、不可交易的真实网络能力检查，并受预算约束。不会创建订单。',
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
.admin-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--el-border-color-light); }
.model-tabs, .budget-summary, .model-secret-notice, .capability-result { margin-top: 16px; }
.credential-form { margin-top: 18px; padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.credential-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.credential-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.security-note { margin: 12px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
pre { max-height: 420px; overflow: auto; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px; white-space: pre-wrap; }
@media (max-width: 700px) {
  .safety-strip, .credential-grid { grid-template-columns: 1fr; }
}
</style>
