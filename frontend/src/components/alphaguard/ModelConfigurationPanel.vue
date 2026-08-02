<template>
  <div v-loading="loading" class="model-configuration">
    <el-result
      v-if="loadError"
      icon="warning"
      title="模型配置加载失败"
      :sub-title="loadError"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <template v-else>
      <header class="page-heading">
        <div>
          <h2>大模型配置</h2>
          <p>统一配置模型服务、密钥和两个决策角色。</p>
        </div>
        <div class="heading-actions">
          <el-tag :type="overallStatusType">{{ overallStatusLabel }}</el-tag>
          <el-tooltip content="刷新配置状态" placement="top">
            <el-button circle aria-label="刷新配置状态" @click="load">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </header>

      <el-alert
        v-if="actionError"
        class="action-feedback"
        type="error"
        :closable="false"
        :title="actionError"
      />

      <div :class="['next-action', { complete: nextAction.complete }]">
        <el-icon><CircleCheck v-if="nextAction.complete" /><Warning v-else /></el-icon>
        <div>
          <strong>{{ nextAction.title }}</strong>
          <span>{{ nextAction.description }}</span>
        </div>
      </div>

      <section class="settings-section">
        <div class="section-heading">
          <div class="section-icon"><Connection /></div>
          <div>
            <h3>模型服务</h3>
            <p>配置一个 OpenAI-Compatible 模型服务。</p>
          </div>
          <div v-if="canManage" class="section-actions">
            <el-button @click="openProviderDialog(false)">
              <el-icon><Plus /></el-icon>添加服务
            </el-button>
            <el-tooltip
              v-if="selectedEndpoint?.provider_type === 'OPENAI_COMPATIBLE'"
              content="编辑当前服务"
              placement="top"
            >
              <el-button circle aria-label="编辑当前服务" @click="openProviderDialog(true)">
                <el-icon><Edit /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip v-if="selectedEndpoint?.provider_type === 'OPENAI_COMPATIBLE'" content="停用当前服务" placement="top">
              <el-button
                circle
                type="danger"
                plain
                aria-label="停用当前服务"
                :loading="providerDisabling"
                @click="disableSelectedEndpoint"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <div class="setting-row">
          <span class="setting-label">当前服务</span>
          <el-select
            v-if="selectableEndpoints.length > 1"
            v-model="selectedEndpointIdentity"
            class="setting-control"
            placeholder="选择模型服务"
            @change="handleEndpointChange"
          >
            <el-option
              v-for="endpoint in selectableEndpoints"
              :key="endpointIdentity(endpoint)"
              :label="endpoint.display_name"
              :value="endpointIdentity(endpoint)"
            />
          </el-select>
          <div v-else class="setting-value">
            <strong>{{ selectedEndpoint?.display_name || '未配置' }}</strong>
            <span>{{ providerTypeLabel(selectedEndpoint?.provider_type) }}</span>
          </div>
          <el-tag :type="endpointStatusType" size="small">{{ endpointStatusLabel }}</el-tag>
        </div>
        <div class="setting-row setting-row--secondary">
          <span class="setting-label">接口地址</span>
          <div class="setting-value setting-value--mono">
            <span>{{ selectedEndpoint?.base_url || '未配置' }}</span>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <div class="section-icon"><Key /></div>
          <div>
            <h3>API 密钥</h3>
            <p>密钥只保存在后端安全存储中，页面不会回显。</p>
          </div>
          <div v-if="canManage" class="section-actions">
            <el-button
              type="primary"
              :title="credentialBlockedReason"
              @click="openCredentialDialog"
            >
              <el-icon><Key /></el-icon>{{ currentCredential ? '更换密钥' : '添加密钥' }}
            </el-button>
            <el-tooltip v-if="currentCredential" content="撤销当前密钥" placement="top">
              <el-button
                circle
                type="danger"
                plain
                aria-label="撤销当前密钥"
                :loading="credentialOperationId === currentCredential.credential_id"
                @click="revokeCurrentCredential"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <div class="setting-row">
          <span class="setting-label">保存状态</span>
          <div class="setting-value">
            <strong>{{ currentCredential ? '••••••••' : '未配置' }}</strong>
            <span>{{ credentialStatusDescription }}</span>
          </div>
          <el-tag :type="credentialStatusType" size="small">
            {{ credentialStatusLabel }}
          </el-tag>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <div class="section-icon"><Cpu /></div>
          <div>
            <h3>决策模型</h3>
            <p>为普通决策和风险终审各选择一个已登记模型。</p>
          </div>
          <div v-if="canManage" class="section-actions">
            <el-button
              :title="modelAddBlockedReason"
              @click="openModelDialog"
            >
              <el-icon><Plus /></el-icon>添加模型
            </el-button>
          </div>
        </div>

        <div class="role-grid">
          <div v-for="role in decisionRoles" :key="role" class="role-field">
            <div class="role-field__heading">
              <strong>{{ roleLabel(role) }}</strong>
              <el-tag :type="capabilityTagType(profileForRole(role))" size="small">
                {{ capabilityDisplayLabel(profileForRole(role)) }}
              </el-tag>
            </div>
            <el-select
              :model-value="modelIdentityForRole(role)"
              :disabled="!canManage || !credentialReady"
              :placeholder="`选择${roleLabel(role)}`"
              @change="value => updateModelIdentity(role, String(value))"
            >
              <el-option
                v-for="model in modelsForRole(role)"
                :key="modelIdentity(model)"
                :label="modelOptionLabel(model)"
                :value="modelIdentity(model)"
                :disabled="!modelHasUsablePrice(model)"
              />
            </el-select>
            <small>{{ capabilityGuidance(profileForRole(role)) }}</small>
          </div>
        </div>

        <el-checkbox v-if="modelsAreSame && canManage" v-model="sameModelConfirmed">
          我确认两个角色使用同一个模型
        </el-checkbox>

        <div v-if="canManage && !assignmentsMatchSelections" class="primary-actions">
          <el-button
            type="primary"
            :loading="modelsSaving"
            :title="modelSaveBlockedReason"
            @click="saveDecisionModels"
          >
            <el-icon><Check /></el-icon>保存模型设置
          </el-button>
          <span v-if="modelSaveBlockedReason" class="action-hint">{{ modelSaveBlockedReason }}</span>
        </div>
        <div v-else-if="canManage" class="saved-state" role="status">
          <el-icon><CircleCheck /></el-icon>
          <span>模型设置已保存</span>
        </div>
      </section>

      <section class="settings-section settings-section--last">
        <div class="section-heading">
          <div class="section-icon"><CircleCheck /></div>
          <div>
            <h3>连接检测</h3>
            <p>验证认证、模型访问和结构化输出，不会创建订单。</p>
          </div>
          <div v-if="canManage" class="section-actions">
            <el-button
              type="primary"
              plain
              :loading="capabilityChecking"
              :title="capabilityBlockedReason"
              @click="runCapabilityChecks"
            >
              <el-icon><Connection /></el-icon>{{ capabilityActionLabel }}
            </el-button>
          </div>
        </div>

        <div class="capability-summary">
          <div v-for="role in decisionRoles" :key="`capability-${role}`">
            <span>{{ roleLabel(role) }}</span>
            <el-tag :type="capabilityTagType(profileForRole(role))" size="small">
              {{ capabilityDisplayLabel(profileForRole(role)) }}
            </el-tag>
          </div>
          <div>
            <span>调用限制</span>
            <el-tag :type="budgetReady ? 'success' : 'warning'" size="small">
              {{ budgetReady ? '可用' : '已阻止' }}
            </el-tag>
          </div>
        </div>
        <el-alert
          v-if="capabilityFailureDetail"
          class="capability-result"
          type="warning"
          :closable="false"
          title="检测已执行，但当前模型未通过"
          :description="capabilityFailureDetail"
        />
        <p v-if="hasStaleCapability" class="capability-note">
          API 密钥已重新验证，旧检测结果仍保留在审计中；请重新检测当前模型。
        </p>
        <div v-if="capabilityBlockedReason" class="action-hint">{{ capabilityBlockedReason }}</div>
      </section>

      <el-collapse v-model="advancedSections" class="technical-records" @change="loadAuditData">
        <el-collapse-item title="高级信息与审计记录" name="technical">
          <el-alert
            v-if="technicalError"
            class="technical-error"
            type="error"
            :closable="false"
            :title="technicalError"
          />
          <el-descriptions v-if="selectedEndpoint" :column="2" border size="small">
            <el-descriptions-item label="服务标识">{{ selectedEndpoint.endpoint_profile_id }}</el-descriptions-item>
            <el-descriptions-item label="接口版本">{{ selectedEndpoint.profile_version }}</el-descriptions-item>
            <el-descriptions-item label="显示状态">{{ endpointStatusLabel }}</el-descriptions-item>
            <el-descriptions-item label="技术状态">{{ selectedEndpoint.state }}</el-descriptions-item>
            <el-descriptions-item label="认证方式">{{ selectedEndpoint.auth_scheme || 'BEARER' }}</el-descriptions-item>
            <el-descriptions-item label="接口模式">{{ selectedEndpoint.api_mode || '系统默认' }}</el-descriptions-item>
          </el-descriptions>

          <h4>模型服务版本</h4>
          <el-table :data="endpoints" size="small">
            <el-table-column prop="display_name" label="服务" min-width="180" />
            <el-table-column prop="profile_version" label="版本" />
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.state) }}</template></el-table-column>
            <el-table-column label="地址验证"><template #default="{ row }">{{ statusLabel(row.url_validation_status) }}</template></el-table-column>
          </el-table>

          <h4>配置门禁</h4>
          <el-table :data="configurationStatus?.components || []" size="small">
            <el-table-column label="项目"><template #default="{ row }">{{ componentLabel(row.key) }}</template></el-table-column>
            <el-table-column label="显示状态"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
            <el-table-column prop="status" label="技术状态" />
            <el-table-column prop="reason_code" label="原因" />
          </el-table>

          <h4>模型与价格</h4>
          <el-table :data="endpointModels" size="small">
            <el-table-column prop="display_name" label="模型" min-width="180" />
            <el-table-column label="用途" min-width="220"><template #default="{ row }">{{ row.role_capabilities.map(roleLabel).join('、') }}</template></el-table-column>
            <el-table-column label="价格"><template #default="{ row }">{{ priceLabelForRow(row) }}</template></el-table-column>
            <el-table-column prop="status" label="技术状态" />
          </el-table>

          <h4>模型角色绑定</h4>
          <el-table :data="endpointProfiles" size="small">
            <el-table-column label="角色"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
            <el-table-column prop="profile_id" label="角色配置标识" min-width="220" />
            <el-table-column prop="profile_version" label="版本" />
            <el-table-column prop="model_name" label="模型" />
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.capability) }}</template></el-table-column>
          </el-table>

          <h4>API 密钥记录</h4>
          <el-table :data="endpointCredentialRecords" size="small">
            <el-table-column prop="credential_id" label="密钥标识" min-width="220" />
            <el-table-column label="接口版本"><template #default="{ row }">{{ row.endpoint_profile_version || '系统版本' }}</template></el-table-column>
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
            <el-table-column prop="last_verified_at" label="最后验证" min-width="190" />
          </el-table>

          <h4>近期调用记录</h4>
          <el-table :data="endpointRuns" size="small">
            <el-table-column prop="created_at" label="时间" min-width="190" />
            <el-table-column label="角色"><template #default="{ row }">{{ roleLabel(row.role) }}</template></el-table-column>
            <el-table-column prop="model_name" label="模型" />
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.structured_output_status) }}</template></el-table-column>
            <el-table-column label="估算 / 实际输入" min-width="140"><template #default="{ row }">{{ row.estimated_input_tokens ?? '—' }} / {{ row.input_tokens ?? '—' }}</template></el-table-column>
            <el-table-column label="输出 Token"><template #default="{ row }">{{ row.output_tokens ?? '—' }}</template></el-table-column>
            <el-table-column label="上下文余量" min-width="130"><template #default="{ row }">{{ row.remaining_context_capacity ?? '—' }} / {{ row.model_context_window ?? '—' }}</template></el-table-column>
            <el-table-column label="上下文告警"><template #default="{ row }">{{ contextWarningLabel(row.context_warning_level) }}</template></el-table-column>
            <el-table-column label="延迟"><template #default="{ row }">{{ row.latency_ms }} ms</template></el-table-column>
            <el-table-column label="请求哈希" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.request_hash) }}</span></template></el-table-column>
            <el-table-column label="响应哈希" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.response_hash) }}</span></template></el-table-column>
          </el-table>

          <h4>真实双模型验证</h4>
          <el-empty v-if="!validationRuns.length" description="尚无验证记录" :image-size="56" />
          <el-table v-else :data="validationRuns" size="small">
            <el-table-column prop="created_at" label="时间" min-width="190" />
            <el-table-column label="样本" min-width="150"><template #default="{ row }">{{ row.symbol || '—' }} · {{ row.source_trade_date || '—' }}</template></el-table-column>
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
            <el-table-column label="验证契约" min-width="190"><template #default="{ row }">{{ row.validation_contract_version || '旧版契约' }}</template></el-table-column>
            <el-table-column label="决策证据" min-width="180"><template #default="{ row }">
              <span>{{ statusLabel(row.decision_evidence_status || 'MISSING') }}</span>
              <span v-if="row.decision_evidence_pack_manifest_id" class="hash-value"> · {{ shortHash(row.decision_evidence_pack_manifest_id) }}</span>
            </template></el-table-column>
            <el-table-column label="普通模型" min-width="150"><template #default="{ row }">{{ validationRoleStatus(row, 'NORMAL_TRADER') }}</template></el-table-column>
            <el-table-column label="终审模型" min-width="170"><template #default="{ row }">{{ validationRoleStatus(row, 'TOP_RISK_REVIEWER') }}</template></el-table-column>
            <el-table-column label="终审上下文" min-width="170"><template #default="{ row }">{{ validationTopContext(row) }}</template></el-table-column>
            <el-table-column label="证据复用" min-width="120"><template #default="{ row }">{{ row.reused_research_and_normal ? '研究与普通模型已复用' : '未复用' }}</template></el-table-column>
            <el-table-column label="共识"><template #default="{ row }">{{ statusLabel(row.consensus_status || 'NOT_REACHED') }}</template></el-table-column>
            <el-table-column label="硬风控"><template #default="{ row }">{{ statusLabel(row.hard_risk_status || 'NOT_REACHED') }}</template></el-table-column>
            <el-table-column label="执行安全门" min-width="150"><template #default="{ row }">{{ statusLabel(row.execution_gate_status) }}</template></el-table-column>
            <el-table-column label="Token 合计" min-width="110"><template #default="{ row }">{{ validationTokenTotal(row) }}</template></el-table-column>
            <el-table-column label="Snapshot" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.snapshot_id) }}</span></template></el-table-column>
            <el-table-column label="Context Hash" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.context_hash) }}</span></template></el-table-column>
            <el-table-column label="失败原因" min-width="220"><template #default="{ row }">{{ validationFailureLabel(row) }}</template></el-table-column>
          </el-table>

          <h4>研究经理结构契约</h4>
          <el-empty v-if="!contractChecks.length" description="尚无结构契约检查" :image-size="56" />
          <el-table v-else :data="contractChecks" size="small">
            <el-table-column prop="checked_at" label="时间" min-width="190" />
            <el-table-column label="契约"><template #default="{ row }">{{ row.contract_id }}@{{ row.contract_version }}</template></el-table-column>
            <el-table-column label="状态"><template #default="{ row }">{{ statusLabel(row.status) }}</template></el-table-column>
            <el-table-column label="Schema Hash" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.schema_hash) }}</span></template></el-table-column>
            <el-table-column label="Prompt Hash" min-width="150"><template #default="{ row }"><span class="hash-value">{{ shortHash(row.prompt_hash) }}</span></template></el-table-column>
            <el-table-column prop="total_tokens" label="Token 数" />
            <el-table-column label="延迟"><template #default="{ row }">{{ row.latency_ms }} ms</template></el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>

      <p class="security-note">
        浏览器不会直接访问模型服务，也不会显示已保存的 API 密钥。
      </p>
    </template>

    <el-dialog
      v-model="providerDialogVisible"
      :title="providerEditing ? '编辑模型服务' : '添加模型服务'"
      width="min(560px, calc(100vw - 32px))"
      destroy-on-close
      append-to-body
      @closed="resetProviderForm"
    >
      <el-form label-position="top" autocomplete="off" @submit.prevent>
        <el-form-item label="服务名称">
          <el-input v-model="providerForm.displayName" maxlength="120" autocomplete="off" placeholder="例如：公司自建模型服务" />
        </el-form-item>
        <el-form-item label="接口地址">
          <el-input v-model="providerForm.baseUrl" autocomplete="off" placeholder="https://example.com/v1" />
        </el-form-item>
        <el-checkbox v-model="providerForm.transmissionConfirmed">
          我确认模型请求会发送到该服务，并已评估其数据政策
        </el-checkbox>
        <el-collapse class="dialog-advanced">
          <el-collapse-item title="高级选项" name="provider-advanced">
            <el-form-item label="接口模式">
              <el-select v-model="providerForm.apiMode">
                <el-option label="Chat Completions" value="OPENAI_CHAT_COMPLETIONS" />
                <el-option label="Responses" value="OPENAI_RESPONSES" />
                <el-option label="自动识别" value="AUTO_DETECT" />
              </el-select>
            </el-form-item>
            <el-form-item label="认证方式">
              <el-select v-model="providerForm.authScheme">
                <el-option label="Bearer" value="BEARER" />
                <el-option label="X-API-Key" value="X_API_KEY" />
              </el-select>
            </el-form-item>
            <el-form-item label="结构化输出">
              <el-select v-model="providerForm.structuredMode">
                <el-option label="自动检测" value="UNKNOWN" />
                <el-option label="JSON Schema" value="NATIVE_JSON_SCHEMA" />
                <el-option label="工具调用" value="TOOL_CALL" />
                <el-option label="JSON" value="JSON_ONLY" />
              </el-select>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <el-alert
        v-if="providerEditing"
        type="info"
        :closable="false"
        title="修改会保存为新版本；当前版本在新地址验证通过前保持有效。"
      />
      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="providerSaving"
          :title="providerSaveBlockedReason"
          @click="saveProvider"
        >保存并验证地址</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="credentialDialogVisible"
      :title="currentCredential ? '更换 API 密钥' : '添加 API 密钥'"
      width="min(500px, calc(100vw - 32px))"
      destroy-on-close
      append-to-body
      @closed="clearCredentialInput"
    >
      <div class="dialog-summary">
        <span>绑定服务</span>
        <strong>{{ selectedEndpoint?.display_name || '未选择' }}</strong>
      </div>
      <el-form label-position="top" autocomplete="off" @submit.prevent>
        <el-form-item label="API 密钥">
          <el-input
            v-model="credentialApiKey"
            type="password"
            autocomplete="new-password"
            placeholder="仅本次提交使用"
          />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" title="提交后立即清空，只保存到后端安全存储。" />
      <template #footer>
        <el-button @click="credentialDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="credentialSaving"
          :title="!credentialApiKey ? '请输入 API 密钥。' : credentialBlockedReason"
          @click="saveCredential"
        >{{ currentCredential ? '验证并更换' : '验证并保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="modelDialogVisible"
      title="添加模型"
      width="min(600px, calc(100vw - 32px))"
      destroy-on-close
      append-to-body
      @closed="resetModelForm"
    >
      <div class="dialog-summary">
        <span>模型服务</span>
        <strong>{{ selectedEndpoint?.display_name || '未选择' }}</strong>
      </div>
      <el-form label-position="top" autocomplete="off" @submit.prevent>
        <el-form-item label="服务商模型名称">
          <div class="model-name-control">
            <el-select
              v-model="modelForm.remoteName"
              class="model-name-select"
              filterable
              allow-create
              default-first-option
              clearable
              autocomplete="off"
              placeholder="选择或输入模型名称"
              @change="applyLocalModelDefaults"
            >
              <el-option
                v-for="option in availableModelNameOptions"
                :key="option.remote_model_name"
                :label="option.remote_model_name"
                :value="option.remote_model_name"
              >
                <span class="model-option-name">{{ option.remote_model_name }}</span>
                <span class="model-option-source">{{ option.source === 'LOCAL' ? '已登记' : '服务商返回' }}</span>
              </el-option>
            </el-select>
            <el-tooltip content="从当前服务商读取模型列表，不执行模型推理" placement="top">
              <el-button
                circle
                aria-label="读取服务商模型"
                :loading="modelOptionsLoading"
                :title="modelOptionsBlockedReason"
                @click="refreshModelOptions"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
          <div v-if="modelOptionsStatus" class="model-options-status">
            {{ modelOptionsStatus }}
          </div>
          <el-alert
            v-if="modelOptionsError"
            class="model-options-error"
            type="warning"
            :closable="false"
            :title="modelOptionsError"
          />
        </el-form-item>
        <el-form-item label="用途">
          <el-checkbox-group v-model="modelForm.roles">
            <el-checkbox value="NORMAL_TRADER">普通决策</el-checkbox>
            <el-checkbox value="TOP_RISK_REVIEWER">风险终审</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="计费方式">
          <el-radio-group v-model="modelForm.pricingSource">
            <el-radio value="SELF_HOSTED">自建服务，价格为 0</el-radio>
            <el-radio value="PROVIDER_PUBLISHED">外部付费服务</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="modelForm.pricingSource === 'PROVIDER_PUBLISHED'">
          <div class="price-grid">
            <el-form-item label="输入价格 / 百万 Token">
              <el-input v-model="modelForm.inputPrice" inputmode="decimal" />
            </el-form-item>
            <el-form-item label="输出价格 / 百万 Token">
              <el-input v-model="modelForm.outputPrice" inputmode="decimal" />
            </el-form-item>
          </div>
          <el-form-item label="价格来源">
            <el-input v-model="modelForm.priceSource" maxlength="300" autocomplete="off" />
          </el-form-item>
          <el-checkbox v-model="modelForm.priceVerified">我已核对服务商真实价格</el-checkbox>
        </template>
        <el-collapse class="dialog-advanced">
          <el-collapse-item title="高级选项" name="model-advanced">
            <el-form-item label="显示名称">
              <el-input v-model="modelForm.displayName" autocomplete="off" placeholder="默认与模型名称相同" />
            </el-form-item>
            <el-checkbox v-model="modelForm.supportsJsonSchema">支持 JSON Schema</el-checkbox>
            <el-checkbox v-model="modelForm.supportsToolCall">支持工具调用</el-checkbox>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="modelSaving"
          :title="modelDialogBlockedReason"
          @click="saveModel"
        >添加模型</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  CircleCheck,
  Connection,
  Cpu,
  Delete,
  Edit,
  Key,
  Plus,
  Refresh,
  Warning
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  alphaguardModelsApi,
  type EndpointModelDefinition,
  type EndpointModelOption,
  type EndpointPriceVersion,
  type ModelCredentialStatus,
  type ModelProfileStatus,
  type RealModelValidationSummary,
  type ResearchManagerContractCheckSummary,
  type ModelRunSummary,
  type ModelRuntimeStatus,
  type ProviderConfigurationStatus,
  type ProviderEndpointProfile
} from '@/api/alphaguardModels'

type DecisionRole = 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'
type PricingSource = 'PROVIDER_PUBLISHED' | 'SELF_HOSTED'
type ModelNameOption = EndpointModelOption & { source: 'LOCAL' | 'PROVIDER' }

const authStore = useAuthStore()
const isDemo = import.meta.env.VITE_ALPHAGUARD_DEMO === 'true'
const canManage = computed(() => authStore.isAdmin && !isDemo)
const decisionRoles: DecisionRole[] = ['NORMAL_TRADER', 'TOP_RISK_REVIEWER']

const loading = ref(false)
const loadError = ref('')
const actionError = ref('')
const technicalError = ref('')
const endpoints = ref<ProviderEndpointProfile[]>([])
const credentials = ref<ModelCredentialStatus[]>([])
const endpointModels = ref<EndpointModelDefinition[]>([])
const providerModelOptions = ref<EndpointModelOption[]>([])
const providerModelOptionsEndpoint = ref('')
const modelOptionsLoading = ref(false)
const modelOptionsError = ref('')
const prices = ref<EndpointPriceVersion[]>([])
const modelStatus = ref<ModelRuntimeStatus | null>(null)
const configurationStatus = ref<ProviderConfigurationStatus | null>(null)
const modelRuns = ref<ModelRunSummary[]>([])
const validationRuns = ref<RealModelValidationSummary[]>([])
const contractChecks = ref<ResearchManagerContractCheckSummary[]>([])
const secretStoreStatus = ref<'READY' | 'UNAVAILABLE'>('UNAVAILABLE')
const selectedEndpointIdentity = ref('')
const normalModelIdentity = ref('')
const topModelIdentity = ref('')
const sameModelConfirmed = ref(false)
const advancedSections = ref<string[]>([])
const auditLoaded = ref(false)

const providerDialogVisible = ref(false)
const providerEditing = ref(false)
const providerSaving = ref(false)
const providerDisabling = ref(false)
const credentialDialogVisible = ref(false)
const credentialApiKey = ref('')
const credentialSaving = ref(false)
const credentialOperationId = ref('')
const modelDialogVisible = ref(false)
const modelSaving = ref(false)
const modelsSaving = ref(false)
const capabilityChecking = ref(false)

const providerForm = reactive({
  displayName: '',
  baseUrl: '',
  apiMode: 'OPENAI_CHAT_COMPLETIONS' as 'OPENAI_CHAT_COMPLETIONS' | 'OPENAI_RESPONSES' | 'AUTO_DETECT',
  authScheme: 'BEARER' as 'BEARER' | 'X_API_KEY',
  structuredMode: 'UNKNOWN' as 'NATIVE_JSON_SCHEMA' | 'TOOL_CALL' | 'JSON_ONLY' | 'UNKNOWN',
  transmissionConfirmed: false
})

const modelForm = reactive({
  remoteName: '',
  displayName: '',
  roles: [] as DecisionRole[],
  supportsJsonSchema: false,
  supportsToolCall: false,
  pricingSource: 'SELF_HOSTED' as PricingSource,
  inputPrice: '',
  outputPrice: '',
  priceSource: '',
  priceVerified: false
})

const selectableEndpoints = computed(() => {
  const byProvider = new Map<string, ProviderEndpointProfile>()
  for (const endpoint of endpoints.value.filter(item =>
    item.provider_type === 'OPENAI_COMPATIBLE'
    && item.enabled
    && item.state !== 'DISABLED'
  )) {
    const existing = byProvider.get(endpoint.endpoint_profile_id)
    if (!existing || endpointPriority(endpoint) > endpointPriority(existing)) {
      byProvider.set(endpoint.endpoint_profile_id, endpoint)
    }
  }
  return Array.from(byProvider.values()).sort((left, right) => {
    if (left.production_allowed !== right.production_allowed) return left.production_allowed ? -1 : 1
    return left.display_name.localeCompare(right.display_name, 'zh-CN')
  })
})

const selectedEndpoint = computed(() => endpoints.value.find(
  item => endpointIdentity(item) === selectedEndpointIdentity.value
) || null)

const currentCredential = computed(() => credentials.value.find(item =>
  item.status !== 'REVOKED'
  && (
    selectedEndpoint.value?.provider_type === 'OPENAI_OFFICIAL'
      ? item.provider_type === 'OPENAI_OFFICIAL'
      : item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
        && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
  )
) || null)

const credentialReady = computed(() => Boolean(
  currentCredential.value?.configured
))

const credentialNeedsModelSetup = computed(() => Boolean(
  credentialReady.value
  && currentCredential.value?.status === 'DEGRADED'
  && !decisionRoles.every(role => (modelStatus.value?.profiles || []).some(profile =>
    profile.configured
    && profile.role === role
    && profile.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && profile.endpoint_profile_version === selectedEndpoint.value?.profile_version
  ))
  && ['MODEL_NOT_FOUND', 'PRICE_NOT_VERIFIED', 'BUDGET_BLOCKED'].includes(
    currentCredential.value.last_error_code || ''
  )
))

const credentialStatusLabel = computed(() => {
  if (!currentCredential.value) return '未配置'
  if (credentialNeedsModelSetup.value) return '已保存，待配置'
  if (credentialReady.value) return '已配置'
  return statusLabel(currentCredential.value.status)
})

const credentialStatusType = computed<'success' | 'warning'>(() =>
  credentialReady.value ? 'success' : 'warning'
)

const credentialStatusDescription = computed(() => {
  if (!currentCredential.value) return credentialBlockedReason.value || '等待添加'
  if (credentialNeedsModelSetup.value) return '认证和服务访问已通过，请继续添加决策模型'
  if (credentialReady.value) return '已绑定当前模型服务'
  return currentCredential.value.sanitized_message
    || '密钥记录存在，但安全存储当前不可读；可以更换或撤销。'
})

const endpointProfiles = computed(() => (modelStatus.value?.profiles || []).filter(item =>
  item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
  && item.endpoint_profile_version === selectedEndpoint.value?.profile_version
  && decisionRoles.includes(item.role as DecisionRole)
))

const endpointCredentialRecords = computed(() => credentials.value.filter(item =>
  selectedEndpoint.value?.provider_type === 'OPENAI_OFFICIAL'
    ? item.provider_type === 'OPENAI_OFFICIAL'
    : item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
))

const endpointRuns = computed(() => {
  const profileIds = new Set(endpointProfiles.value.map(item => item.profile_id))
  return modelRuns.value.filter(item => profileIds.has(item.model_profile_id))
})

const modelsAreSame = computed(() => Boolean(
  normalModelIdentity.value && normalModelIdentity.value === topModelIdentity.value
))

const assignmentsMatchSelections = computed(() => decisionRoles.every(role => {
  const profile = profileForRole(role)
  const selectedModel = modelFromIdentity(modelIdentityForRole(role))
  return Boolean(
    profile?.configured
    && selectedModel
    && profile.endpoint_model_id === selectedModel.endpoint_model_id
    && profile.model_version === selectedModel.model_version
  )
}))

const budgetReady = computed(() => {
  const budget = modelStatus.value?.budget
  const gate = configurationStatus.value?.components.find(item => item.key === 'budget')
  return Boolean(
    budget
    && budget.remaining_calls > 0
    && Number(budget.remaining_cost) >= 0
    && (!gate || gate.status === 'READY')
  )
})

const endpointStatusLabel = computed(() => {
  if (!selectedEndpoint.value) return '未配置'
  if (selectedEndpoint.value.url_validation_status === 'PASS') return '地址验证通过'
  return statusLabel(selectedEndpoint.value.state)
})

const endpointStatusType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  if (!selectedEndpoint.value) return 'warning'
  if (selectedEndpoint.value.url_validation_status === 'PASS') return 'success'
  if (['REJECTED', 'DEGRADED', 'DISABLED'].includes(selectedEndpoint.value.state)) return 'danger'
  return 'warning'
})

const overallReady = computed(() =>
  decisionRoles.every(role => profileForRole(role)?.capability === 'READY') && budgetReady.value
)
const hasStaleCapability = computed(() =>
  decisionRoles.some(role => Boolean(profileForRole(role)?.capability_stale))
)
const hasPreviousCapabilityCheck = computed(() =>
  decisionRoles.some(role => Boolean(profileForRole(role)?.last_check))
)
const failedCapabilityProfiles = computed(() => endpointProfiles.value.filter(profile =>
  profile.configured && Boolean(profile.last_check) && profile.capability !== 'READY'
))
const capabilityFailureDetail = computed(() => {
  if (!failedCapabilityProfiles.value.length) return ''
  const failures = failedCapabilityProfiles.value.map(profile =>
    `${roleLabel(profile.role as DecisionRole)}：${capabilityGuidance(profile)}`
  )
  return `${failures.join(' ')} 请先更换对应模型或处理服务商额度并保存；配置不变时，重复检测通常会得到相同结果。`
})
const capabilityActionLabel = computed(() => {
  return hasStaleCapability.value || hasPreviousCapabilityCheck.value ? '重新检测' : '开始检测'
})
const overallStatusLabel = computed(() =>
  overallReady.value ? '配置可用' : hasStaleCapability.value ? '需重新检测' : '配置未完成'
)
const overallStatusType = computed<'success' | 'warning'>(() => overallReady.value ? 'success' : 'warning')

const nextAction = computed(() => {
  if (!selectedEndpoint.value || selectedEndpoint.value.url_validation_status !== 'PASS') {
    return { complete: false, title: '当前缺少：可用的模型服务', description: '添加或编辑模型服务，并完成接口地址验证。' }
  }
  if (!currentCredential.value) {
    return { complete: false, title: '当前缺少：API 密钥', description: '添加一把绑定当前模型服务的 API 密钥。' }
  }
  if (!credentialReady.value) {
    return {
      complete: false,
      title: '当前需要：修复 API 密钥',
      description: currentCredential.value.sanitized_message
        || '密钥记录存在，但安全存储当前不可读；请更换或撤销后重新添加。'
    }
  }
  if (!decisionRoles.every(role => modelsForRole(role).some(modelHasUsablePrice))) {
    return { complete: false, title: '当前缺少：决策模型', description: '添加普通决策模型和风险终审模型。' }
  }
  if (!decisionRoles.every(role => Boolean(profileForRole(role)?.configured))) {
    return { complete: false, title: '当前缺少：模型角色绑定', description: '选择两个模型并保存模型设置。' }
  }
  if (hasStaleCapability.value) {
    return { complete: false, title: '当前需要：重新检测模型', description: 'API 密钥已重新验证，请对当前两个模型重新执行连接检测。' }
  }
  if (!decisionRoles.every(role => profileForRole(role)?.capability === 'READY')) {
    return hasPreviousCapabilityCheck.value
      ? {
          complete: false,
          title: '当前需要：更换或修复失败模型',
          description: capabilityFailureDetail.value || '查看模型下方的具体原因，处理后再执行检测。'
        }
      : { complete: false, title: '当前缺少：连接检测', description: '配置确认无误后，由管理员手动开始检测。' }
  }
  if (!budgetReady.value) {
    return { complete: false, title: '当前阻断：调用限制', description: '调用次数或资源预算不可用。' }
  }
  return { complete: true, title: '配置完成', description: '模型服务、密钥、角色和调用限制均已就绪。' }
})

const credentialBlockedReason = computed(() => {
  if (secretStoreStatus.value !== 'READY') return '后端安全存储不可用，暂时不能保存密钥。'
  if (!selectedEndpoint.value) return '请先添加模型服务。'
  if (selectedEndpoint.value.url_validation_status !== 'PASS') return '请先完成接口地址验证。'
  return ''
})

const modelAddBlockedReason = computed(() => {
  if (!selectedEndpoint.value || selectedEndpoint.value.url_validation_status !== 'PASS') return '请先添加并验证模型服务。'
  if (!credentialReady.value) return '请先添加或修复 API 密钥。'
  return ''
})

const modelSaveBlockedReason = computed(() => {
  if (!credentialReady.value) return '请先添加或修复 API 密钥。'
  if (!normalModelIdentity.value) return '请选择普通决策模型。'
  if (!topModelIdentity.value) return '请选择风险终审模型。'
  const selectedModels = [normalModelIdentity.value, topModelIdentity.value].map(modelFromIdentity)
  if (selectedModels.some(model => !model || !modelHasUsablePrice(model))) return '所选模型缺少有效价格记录。'
  if (modelsAreSame.value && !sameModelConfirmed.value) return '两个角色选择了同一个模型，请先确认。'
  return ''
})

const capabilityBlockedReason = computed(() => {
  if (!credentialReady.value) return '请先添加或修复 API 密钥。'
  if (!decisionRoles.every(role => Boolean(profileForRole(role)?.configured))) return '请先保存两个模型角色。'
  if (!assignmentsMatchSelections.value) return '模型选择尚未保存，请先保存模型设置。'
  if (decisionRoles.every(role => profileForRole(role)?.capability === 'READY')) return '当前模型已经检测通过。'
  if (!budgetReady.value) return '调用次数或资源预算不可用。'
  return ''
})

const modelDialogBlockedReason = computed(() => {
  if (!modelForm.remoteName.trim()) return '请填写服务商模型名称。'
  if (!modelForm.roles.length) return '请至少选择一个用途。'
  if (modelForm.pricingSource === 'PROVIDER_PUBLISHED') {
    if (!validNonNegativeDecimal(modelForm.inputPrice) || !validNonNegativeDecimal(modelForm.outputPrice)) return '请填写有效的输入和输出价格。'
    if (!modelForm.priceSource.trim()) return '请填写价格来源。'
    if (!modelForm.priceVerified) return '请先确认已核对真实价格。'
  }
  return ''
})

const modelOptionsBlockedReason = computed(() => {
  if (!selectedEndpoint.value?.models_endpoint_enabled) return '当前服务商未启用模型列表接口，可直接输入模型名称。'
  if (!credentialReady.value) return '请先添加或修复 API 密钥。'
  return ''
})

const providerSaveBlockedReason = computed(() => {
  if (!providerForm.displayName.trim()) return '请填写服务名称。'
  if (!providerForm.baseUrl.trim()) return '请填写接口地址。'
  if (!providerForm.transmissionConfirmed) return '请先确认数据会发送到该服务。'
  return ''
})

const availableModelNameOptions = computed<ModelNameOption[]>(() => {
  const options = new Map<string, ModelNameOption>()
  for (const model of [...endpointModels.value].sort(
    (left, right) => versionRank(right.model_version) - versionRank(left.model_version)
  )) {
    if (!options.has(model.remote_model_name)) {
      options.set(model.remote_model_name, {
        remote_model_name: model.remote_model_name,
        display_name: model.display_name || model.remote_model_name,
        source: 'LOCAL'
      })
    }
  }
  if (providerModelOptionsEndpoint.value === selectedEndpointIdentity.value) {
    for (const option of providerModelOptions.value) {
      if (!options.has(option.remote_model_name)) {
        options.set(option.remote_model_name, { ...option, source: 'PROVIDER' })
      }
    }
  }
  return Array.from(options.values()).sort((left, right) =>
    left.remote_model_name.localeCompare(right.remote_model_name)
  )
})

const modelOptionsStatus = computed(() => {
  if (modelOptionsLoading.value) return ''
  if (providerModelOptionsEndpoint.value === selectedEndpointIdentity.value) {
    return providerModelOptions.value.length
      ? `服务商返回 ${providerModelOptions.value.length} 个模型`
      : '服务商未返回可选模型，可直接输入模型名称'
  }
  if (endpointModels.value.length) return '已显示当前服务中登记过的模型'
  return ''
})

const STATUS_LABELS: Record<string, string> = {
  READY: '可用',
  URL_VALIDATED: '地址验证通过',
  UNVERIFIED: '未验证',
  NOT_CONFIGURED: '未配置',
  MISSING: '未配置',
  DEGRADED: '异常',
  BLOCKED: '已阻止',
  ACTIVE: '已启用',
  CONFIGURED: '已配置',
  REUSED: '已复用',
  CREATED: '已创建',
  REVOKED: '已撤销',
  DRAFT: '待验证',
  PASS: '通过',
  SUCCESS: '成功',
  PROVIDER_ERROR: '服务异常',
  UNAUTHORIZED: '认证失败',
  PROJECT_ACCESS_DENIED: '项目无权限',
  PROVIDER_QUOTA_EXHAUSTED: '服务商额度不足',
  BUDGET_BLOCKED: '服务商额度不足',
  MODEL_NOT_FOUND: '模型不存在',
  RATE_LIMITED: '请求受限',
  TIMEOUT: '请求超时',
  MODEL_TIMEOUT: '响应超时',
  INVALID_OUTPUT: '输出格式无效',
  CREDENTIAL_REVERIFIED: '密钥已更新，需重新检测',
  SELF_HOSTED_ZERO: '自建服务 / 价格0',
  PROVIDER_PUBLISHED: '服务商价格',
  DISABLED: '已停用',
  REJECTED: '已拒绝',
  FAILED: '未完成',
  COMPLETED: '已完成',
  COMPLETE: '完整',
  PARTIAL: '部分完整',
  NOT_REACHED: '未到达',
  PROPOSE_TRADE: '交易计划已生成',
  MODEL_FAILED: '模型未执行',
  MODEL_CONTEXT_WINDOW_EXCEEDED: '超过模型上下文窗口',
  OVER_70: '已超过 70%',
  OVER_85: '已超过 85%',
  OVER_95: '已超过 95%'
}

const COMPONENT_LABELS: Record<string, string> = {
  endpoint: '接口地址',
  credential: 'API 密钥',
  normal_model: '普通决策模型',
  top_model: '风险终审模型',
  normal_price: '普通模型价格',
  top_price: '终审模型价格',
  normal_profile: '普通模型角色',
  top_profile: '终审模型角色',
  assignments: '角色绑定',
  capability: '能力检测',
  budget: '调用限制'
}

function endpointIdentity(endpoint: ProviderEndpointProfile): string {
  return `${endpoint.endpoint_profile_id}@${endpoint.profile_version}`
}

function modelIdentity(model: EndpointModelDefinition): string {
  return `${model.endpoint_model_id}@${model.model_version}`
}

function versionRank(version: string): number {
  const value = Number.parseInt(version.replace(/^v/i, ''), 10)
  return Number.isFinite(value) ? value : 0
}

function endpointPriority(endpoint: ProviderEndpointProfile): number {
  const readiness = endpoint.production_allowed ? 3 : endpoint.url_validation_status === 'PASS' ? 2 : 1
  return readiness * 100000 + versionRank(endpoint.profile_version)
}

function providerTypeLabel(type?: string): string {
  if (!type) return '等待添加'
  return type === 'OPENAI_OFFICIAL' ? 'OpenAI 官方服务' : 'OpenAI-Compatible 服务'
}

function roleLabel(role?: string): string {
  if (role === 'NORMAL_TRADER') return '普通决策模型'
  if (role === 'TOP_RISK_REVIEWER') return '风险终审模型'
  if (role === 'RESEARCH_AGENT') return '研究模型'
  return role || '未配置'
}

function statusLabel(status?: string | null): string {
  return status ? STATUS_LABELS[status] || status : '未配置'
}

function validationRoleStatus(
  row: Partial<RealModelValidationSummary>,
  role: 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'
): string {
  const result = role === 'NORMAL_TRADER' ? row.normal_result : row.top_result
  if (result?.model_meta?.error_type) return statusLabel(result.model_meta.error_type)
  if (result?.status) return statusLabel(result.status)
  const audit = [...(row.model_call_records || [])].reverse().find(item => item.role === role)
  if (audit?.error_category) return statusLabel(audit.error_category)
  return audit ? statusLabel(audit.structured_output_status) : statusLabel('NOT_REACHED')
}

function validationTokenTotal(row: Partial<RealModelValidationSummary>): number {
  return (row.model_call_records || []).reduce(
    (total, item) => total + Number(item.total_tokens || 0),
    0
  )
}

function validationTopContext(row: Partial<RealModelValidationSummary>): string {
  const audit = [...(row.model_call_records || [])].reverse().find(
    item => item.role === 'TOP_RISK_REVIEWER' && item.estimated_input_tokens != null
  )
  if (!audit) return '—'
  return `${audit.estimated_input_tokens} + ${audit.configured_max_output_tokens ?? '—'} / ${audit.model_context_window ?? '—'}`
}

function contextWarningLabel(value?: ModelRunSummary['context_warning_level']): string {
  if (!value || value === 'NONE') return '无'
  return statusLabel(value)
}

function validationFailureLabel(row: Partial<RealModelValidationSummary>): string {
  if (!row.failure_code) return '—'
  const topError = row.top_result?.model_meta?.error_type
  if (row.failure_code === 'TOP_MODEL_FAILED' && topError) {
    return `风险终审模型：${statusLabel(topError)}`
  }
  return statusLabel(row.failure_code)
}

function shortHash(value?: string | null): string {
  if (!value) return '—'
  return value.length <= 16 ? value : `${value.slice(0, 8)}…${value.slice(-6)}`
}

function componentLabel(key: string): string {
  return COMPONENT_LABELS[key] || key
}

function capabilityStatusType(status?: string | null): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'READY') return 'success'
  if (!status || ['UNVERIFIED', 'NOT_CONFIGURED'].includes(status)) return 'info'
  if (['RATE_LIMITED', 'TIMEOUT', 'MODEL_TIMEOUT', 'BUDGET_BLOCKED'].includes(status)) return 'warning'
  return 'danger'
}

function capabilityTagType(profile?: ModelProfileStatus): 'success' | 'warning' | 'danger' | 'info' {
  if (profile?.capability_stale) return 'warning'
  return capabilityStatusType(profile?.capability)
}

function capabilityDisplayLabel(profile?: ModelProfileStatus): string {
  return profile?.capability_stale
    ? '需重新检测'
    : statusLabel(profile?.capability || 'NOT_CONFIGURED')
}

function capabilityGuidance(profile?: ModelProfileStatus): string {
  if (!profile?.configured) return '保存模型设置后可执行连接检测。'
  if (profile.capability_stale) return 'API 密钥已更新，请重新检测当前模型。'
  if (profile.capability === 'READY') return '连接和结构化输出检测已通过。'
  return profile.failure_summary || '尚未通过连接检测。'
}

function profileForRole(role: DecisionRole): ModelProfileStatus | undefined {
  return endpointProfiles.value.find(item => item.role === role)
}

function modelsForRole(role: DecisionRole): EndpointModelDefinition[] {
  return endpointModels.value.filter(model => model.role_capabilities.includes(role))
}

function modelIdentityForRole(role: DecisionRole): string {
  return role === 'NORMAL_TRADER' ? normalModelIdentity.value : topModelIdentity.value
}

function updateModelIdentity(role: DecisionRole, identity: string) {
  if (role === 'NORMAL_TRADER') normalModelIdentity.value = identity
  else topModelIdentity.value = identity
  if (!modelsAreSame.value) sameModelConfirmed.value = false
}

function modelFromIdentity(identity: string): EndpointModelDefinition | null {
  return endpointModels.value.find(item => modelIdentity(item) === identity) || null
}

function priceForModel(model: EndpointModelDefinition): EndpointPriceVersion | undefined {
  return prices.value.find(price =>
    price.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && price.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && price.endpoint_model_id === model.endpoint_model_id
    && price.endpoint_model_version === model.model_version
    && price.verified
  )
}

function modelHasUsablePrice(model: EndpointModelDefinition): boolean {
  return Boolean(priceForModel(model))
}

function modelOptionLabel(model: EndpointModelDefinition): string {
  return `${model.display_name || model.remote_model_name}${modelHasUsablePrice(model) ? '' : '（价格未配置）'}`
}

function priceLabelForModel(model: EndpointModelDefinition): string {
  const price = priceForModel(model)
  if (!price) return '未配置'
  if (price.pricing_source === 'SELF_HOSTED') return '自建服务 / 价格0'
  return `${price.currency} ${price.input_price_per_million} / ${price.output_price_per_million}`
}

function priceLabelForRow(row: Record<string, unknown>): string {
  const model = endpointModels.value.find(item =>
    item.endpoint_model_id === row.endpoint_model_id
    && item.model_version === row.model_version
  )
  return model ? priceLabelForModel(model) : '身份无效'
}

function validNonNegativeDecimal(value: string): boolean {
  return /^\d+(?:\.\d+)?$/.test(value.trim()) && Number(value) >= 0
}

function sameDecimal(left: string | null | undefined, right: string): boolean {
  const leftNumber = Number(left)
  const rightNumber = Number(right)
  return Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber === rightNumber
}

function sameRoles(left: string[], right: DecisionRole[]): boolean {
  return [...left].sort().join('|') === [...right].sort().join('|')
}

function modelsWithRemoteName(remoteName: string): EndpointModelDefinition[] {
  return endpointModels.value
    .filter(model => model.remote_model_name === remoteName)
    .sort((left, right) => versionRank(right.model_version) - versionRank(left.model_version))
}

function modelMatchesForm(model: EndpointModelDefinition): boolean {
  const displayName = modelForm.displayName.trim() || modelForm.remoteName.trim()
  return model.display_name === displayName
    && sameRoles(model.role_capabilities, modelForm.roles)
    && model.supports_json_schema === modelForm.supportsJsonSchema
    && model.supports_tool_call === modelForm.supportsToolCall
}

function matchingPrice(model: EndpointModelDefinition): EndpointPriceVersion | undefined {
  const selfHosted = modelForm.pricingSource === 'SELF_HOSTED'
  return prices.value.find(price =>
    price.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && price.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && price.endpoint_model_id === model.endpoint_model_id
    && price.endpoint_model_version === model.model_version
    && price.verified
    && price.currency === 'USD'
    && price.pricing_source === modelForm.pricingSource
    && (selfHosted
      ? sameDecimal(price.input_price_per_million, '0')
        && sameDecimal(price.cached_input_price_per_million, '0')
        && sameDecimal(price.output_price_per_million, '0')
      : sameDecimal(price.input_price_per_million, modelForm.inputPrice.trim())
        && sameDecimal(price.cached_input_price_per_million, '0')
        && sameDecimal(price.output_price_per_million, modelForm.outputPrice.trim())
        && price.source_description === modelForm.priceSource.trim())
  )
}

function nextModelVersion(models: EndpointModelDefinition[]): string {
  return `v${Math.max(0, ...models.map(model => versionRank(model.model_version))) + 1}`
}

function applyLocalModelDefaults(remoteName: string) {
  const model = modelsWithRemoteName(remoteName)[0]
  if (!model) return
  modelForm.displayName = model.display_name
  modelForm.roles = model.role_capabilities.filter((role): role is DecisionRole =>
    decisionRoles.includes(role as DecisionRole)
  )
  modelForm.supportsJsonSchema = model.supports_json_schema
  modelForm.supportsToolCall = model.supports_tool_call
  const price = priceForModel(model)
  if (!price) return
  modelForm.pricingSource = price.pricing_source
  if (price.pricing_source === 'PROVIDER_PUBLISHED') {
    modelForm.inputPrice = price.input_price_per_million
    modelForm.outputPrice = price.output_price_per_million
    modelForm.priceSource = price.source_description
    modelForm.priceVerified = price.verified
  }
}

function selectPreferredEndpoint() {
  if (selectableEndpoints.value.some(item => endpointIdentity(item) === selectedEndpointIdentity.value)) return
  const available = new Map(selectableEndpoints.value.map(item => [endpointIdentity(item), item]))
  const assigned = (modelStatus.value?.profiles || []).find(profile =>
    decisionRoles.includes(profile.role as DecisionRole)
    && profile.endpoint_profile_id
    && profile.endpoint_profile_version
    && available.has(`${profile.endpoint_profile_id}@${profile.endpoint_profile_version}`)
  )
  const configuredCredential = credentials.value.find(credential =>
    credential.configured
    && credential.status !== 'REVOKED'
    && credential.endpoint_profile_id
    && credential.endpoint_profile_version
    && available.has(`${credential.endpoint_profile_id}@${credential.endpoint_profile_version}`)
  )
  const compatible = selectableEndpoints.value.find(endpoint =>
    endpoint.provider_type === 'OPENAI_COMPATIBLE'
    && endpoint.url_validation_status === 'PASS'
  )
  const preferredIdentity = assigned?.endpoint_profile_id && assigned.endpoint_profile_version
    ? `${assigned.endpoint_profile_id}@${assigned.endpoint_profile_version}`
    : configuredCredential?.endpoint_profile_id && configuredCredential.endpoint_profile_version
      ? `${configuredCredential.endpoint_profile_id}@${configuredCredential.endpoint_profile_version}`
      : compatible
        ? endpointIdentity(compatible)
        : selectableEndpoints.value[0]
          ? endpointIdentity(selectableEndpoints.value[0])
          : ''
  selectedEndpointIdentity.value = preferredIdentity
}

function syncModelSelections() {
  for (const role of decisionRoles) {
    const profile = profileForRole(role)
    const existingIdentity = profile?.endpoint_model_id && profile.model_version
      ? `${profile.endpoint_model_id}@${profile.model_version}`
      : ''
    const selected = modelFromIdentity(existingIdentity) && modelHasUsablePrice(modelFromIdentity(existingIdentity)!)
      ? existingIdentity
      : modelsForRole(role).find(modelHasUsablePrice)
        ? modelIdentity(modelsForRole(role).find(modelHasUsablePrice)!)
        : ''
    updateModelIdentity(role, selected)
  }
  sameModelConfirmed.value = false
}

function parseActionError(action: string, error: unknown): string {
  const candidate = error as {
    response?: { status?: number; data?: { detail?: string | { error_code?: string; sanitized_message?: string } } }
  }
  const detail = candidate.response?.data?.detail
  const code = typeof detail === 'object' && detail ? detail.error_code : undefined
  const guidance: Record<string, string> = {
    CREDENTIAL_ENDPOINT_VERSION_MISMATCH: '该密钥属于旧接口版本，请为当前模型服务添加新密钥。',
    CREDENTIAL_NOT_ACTIVE: '当前密钥已撤销，请添加新密钥。',
    ENDPOINT_NOT_VALIDATED: '接口地址尚未验证，请先编辑并验证模型服务。',
    CONFIGURATION_NOT_READY: '当前模型服务配置不完整。请编辑当前服务并检查高级选项。',
    STRUCTURED_OUTPUT_NOT_READY: '所选模型缺少结构化输出能力。请在“添加模型”的高级选项中启用 JSON Schema 或工具调用。',
    MODEL_NOT_REGISTERED: '所选模型登记记录不存在，请重新添加该模型。',
    MODEL_ROLE_NOT_SUPPORTED: '所选模型没有对应角色能力，请重新添加模型并勾选正确用途。',
    MODEL_PRICE_NOT_READY: '所选模型缺少有效价格记录；自建服务请选择“价格为 0”。',
    SAME_MODEL_CONFIRMATION_REQUIRED: '两个角色选择了同一模型，请勾选同模型确认后再保存。',
    UNAUTHORIZED: '密钥认证失败，请检查后重新提交。',
    PROJECT_ACCESS_DENIED: '服务商拒绝读取模型列表。请检查该密钥的模型目录权限，或直接输入已知模型名称。',
    PROVIDER_QUOTA_EXHAUSTED: '服务商额度不足，请充值或选择额度要求更低的模型。',
    BUDGET_BLOCKED: '服务商额度不足，请充值或选择额度要求更低的模型。',
    MODEL_NOT_FOUND: '服务商没有找到该模型名称，请核对后重试。',
    RATE_LIMITED: '服务商请求受限，请稍后重试。',
    TIMEOUT: '服务商响应超时，请检查网络和接口地址。',
    PROVIDER_ERROR: '模型服务返回异常，请检查接口模式和模型名称。',
    INTEGRITY_CONFLICT: '相同身份已有不同内容，系统已阻止覆盖。'
  }
  technicalError.value = [candidate.response?.status ? `HTTP ${candidate.response.status}` : '', code || 'REQUEST_FAILED']
    .filter(Boolean)
    .join(' · ')
  return `${action}：${code && guidance[code] ? guidance[code] : '请求未完成，请检查当前配置后重试。'}`
}

function showActionError(action: string, error: unknown) {
  actionError.value = parseActionError(action, error)
  ElMessage.error(actionError.value)
}

async function load() {
  loading.value = true
  loadError.value = ''
  actionError.value = ''
  const failures = (await Promise.all([
    loadPart('模型状态', async () => {
      const response = await alphaguardModelsApi.status()
      modelStatus.value = response.data
    }),
    loadPart('API 密钥状态', async () => {
      const response = await alphaguardModelsApi.credentials()
      credentials.value = response.data.items
      secretStoreStatus.value = response.data.secret_store_status
    }),
    loadPart('模型服务', async () => {
      const response = await alphaguardModelsApi.endpoints()
      endpoints.value = response.data.items
    }),
    loadPart('价格记录', async () => {
      const response = await alphaguardModelsApi.prices()
      prices.value = response.data.items
    })
  ])).filter((item): item is string => Boolean(item))
  try {
    if (failures.length === 4) {
      loadError.value = '无法读取后端配置状态；页面不会使用旧缓存伪装成功。'
      return
    }
    selectPreferredEndpoint()
    try {
      await loadSelectedEndpointData()
    } catch {
      failures.push('当前服务详情')
    }
    syncModelSelections()
    if (failures.length) {
      actionError.value = `部分状态未能读取：${failures.join('、')}。已显示其余实时结果。`
    }
  } finally {
    loading.value = false
  }
}

async function loadPart(label: string, loader: () => Promise<void>): Promise<string | null> {
  try {
    await loader()
    return null
  } catch {
    return label
  }
}

async function loadSelectedEndpointData() {
  const endpoint = selectedEndpoint.value
  endpointModels.value = []
  configurationStatus.value = null
  if (!endpoint) {
    return
  }
  const [modelsResult, configurationResult] = await Promise.allSettled([
    alphaguardModelsApi.endpointModels(endpoint.endpoint_profile_id, endpoint.profile_version),
    endpoint.provider_type === 'OPENAI_COMPATIBLE'
      ? alphaguardModelsApi.endpointConfigurationStatus(endpoint.endpoint_profile_id, endpoint.profile_version)
      : Promise.resolve({ data: null })
  ])
  const failures: string[] = []
  if (modelsResult.status === 'fulfilled') endpointModels.value = modelsResult.value.data.items
  else failures.push('模型列表')
  if (configurationResult.status === 'fulfilled') configurationStatus.value = configurationResult.value.data
  else failures.push('配置门禁')
  if (failures.length) throw new Error(failures.join('、'))
}

async function handleEndpointChange() {
  actionError.value = ''
  providerModelOptions.value = []
  providerModelOptionsEndpoint.value = ''
  modelOptionsError.value = ''
  try {
    await loadSelectedEndpointData()
    syncModelSelections()
  } catch (error) {
    showActionError('切换模型服务失败', error)
  }
}

function resetProviderForm() {
  providerEditing.value = false
  providerForm.displayName = ''
  providerForm.baseUrl = ''
  providerForm.apiMode = 'OPENAI_CHAT_COMPLETIONS'
  providerForm.authScheme = 'BEARER'
  providerForm.structuredMode = 'UNKNOWN'
  providerForm.transmissionConfirmed = false
}

function openProviderDialog(editing: boolean) {
  resetProviderForm()
  providerEditing.value = editing && Boolean(selectedEndpoint.value)
  if (providerEditing.value && selectedEndpoint.value) {
    providerForm.displayName = selectedEndpoint.value.display_name
    providerForm.baseUrl = selectedEndpoint.value.base_url || ''
    providerForm.apiMode = selectedEndpoint.value.api_mode || 'OPENAI_CHAT_COMPLETIONS'
    providerForm.authScheme = selectedEndpoint.value.auth_scheme || 'BEARER'
    providerForm.structuredMode = selectedEndpoint.value.structured_output_mode
  }
  providerDialogVisible.value = true
}

async function saveProvider() {
  if (providerSaveBlockedReason.value) {
    ElMessage.warning(providerSaveBlockedReason.value)
    return
  }
  providerSaving.value = true
  actionError.value = ''
  try {
    const response = await alphaguardModelsApi.createEndpoint({
      display_name: providerForm.displayName.trim(),
      provider_type: 'OPENAI_COMPATIBLE',
      base_url: providerForm.baseUrl.trim(),
      api_mode: providerForm.apiMode,
      auth_scheme: providerForm.authScheme,
      models_endpoint_enabled: true,
      structured_output_mode: providerForm.structuredMode,
      ...(providerEditing.value && selectedEndpoint.value
        ? { endpoint_profile_id: selectedEndpoint.value.endpoint_profile_id, create_new_version: true }
        : {})
    })
    const endpoint = response.data.item
    const validation = await alphaguardModelsApi.validateEndpoint(endpoint.endpoint_profile_id, {
      profile_version: endpoint.profile_version,
      confirm_data_transmission: true
    })
    if (validation.data.url_validation_status !== 'PASS') {
      selectedEndpointIdentity.value = endpointIdentity(validation.data)
      providerEditing.value = true
      ElMessage.warning('模型服务已保存，但接口地址验证未通过。请检查地址后重试。')
      await load()
      return
    }
    selectedEndpointIdentity.value = endpointIdentity(validation.data)
    providerDialogVisible.value = false
    ElMessage.success(providerEditing.value ? '模型服务新版本已验证并启用。' : '模型服务已添加。')
    await load()
  } catch (error) {
    showActionError('保存模型服务失败', error)
  } finally {
    providerSaving.value = false
  }
}

async function disableSelectedEndpoint() {
  const endpoint = selectedEndpoint.value
  if (!endpoint) return
  try {
    await ElMessageBox.confirm(
      `停用“${endpoint.display_name}”后，绑定的模型将不能继续调用。历史记录会保留。`,
      '停用模型服务',
      { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' }
    )
  } catch (error) {
    if (!isDialogCancellation(error)) {
      showActionError('打开停用确认失败', error)
    }
    return
  }
  providerDisabling.value = true
  try {
    await alphaguardModelsApi.disableEndpoint(endpoint.endpoint_profile_id, endpoint.profile_version)
    selectedEndpointIdentity.value = ''
    ElMessage.success('模型服务已停用，历史配置仍保留。')
    await load()
  } catch (error) {
    showActionError('停用模型服务失败', error)
  } finally {
    providerDisabling.value = false
  }
}

function openCredentialDialog() {
  if (credentialBlockedReason.value) {
    ElMessage.warning(credentialBlockedReason.value)
    return
  }
  clearCredentialInput()
  credentialDialogVisible.value = true
}

function clearCredentialInput() {
  credentialApiKey.value = ''
}

async function saveCredential() {
  const endpoint = selectedEndpoint.value
  if (!endpoint) {
    ElMessage.warning('请先添加模型服务。')
    return
  }
  if (!credentialApiKey.value) {
    ElMessage.warning('请输入 API 密钥。')
    return
  }
  const replacingCredential = Boolean(currentCredential.value)
  const payload = { api_key: credentialApiKey.value }
  credentialApiKey.value = ''
  credentialSaving.value = true
  try {
    const response = currentCredential.value
      ? await alphaguardModelsApi.replaceCredential(currentCredential.value.credential_id, payload)
      : await alphaguardModelsApi.createCredential({
          provider: endpoint.provider_type === 'OPENAI_OFFICIAL' ? 'openai' : 'openai_compatible',
          provider_type: endpoint.provider_type,
          endpoint_profile_id: endpoint.provider_type === 'OPENAI_COMPATIBLE' ? endpoint.endpoint_profile_id : undefined,
          endpoint_profile_version: endpoint.provider_type === 'OPENAI_COMPATIBLE' ? endpoint.profile_version : undefined,
          base_url: endpoint.provider_type === 'OPENAI_OFFICIAL' ? endpoint.base_url : undefined,
          credential_name: `${endpoint.endpoint_profile_id}-${endpoint.profile_version}-primary`.slice(0, 100),
          ...payload
        })
    payload.api_key = ''
    if (!response.data.stored) {
      ElMessage.error('API 密钥未保存：验证没有通过，请检查密钥和当前服务是否匹配。')
      return
    }
    if (replacingCredential && !response.data.replaced) {
      ElMessage.error('新 API 密钥验证未通过，原密钥已保留且仍可使用。')
      return
    }
    credentialDialogVisible.value = false
    ElMessage.success(replacingCredential ? 'API 密钥已安全更换。' : 'API 密钥已保存到安全存储。')
    await load()
  } catch (error) {
    showActionError(replacingCredential ? '更换 API 密钥失败' : '保存 API 密钥失败', error)
  } finally {
    payload.api_key = ''
    credentialApiKey.value = ''
    credentialSaving.value = false
  }
}

async function revokeCurrentCredential() {
  const credential = currentCredential.value
  if (!credential) return
  try {
    await ElMessageBox.confirm(
      '撤销后模型会立即停止使用这把密钥，历史审计记录仍会保留。',
      '撤销 API 密钥',
      { type: 'warning', confirmButtonText: '确认撤销', cancelButtonText: '取消' }
    )
  } catch (error) {
    if (!isDialogCancellation(error)) {
      showActionError('打开撤销确认失败', error)
    }
    return
  }
  credentialOperationId.value = credential.credential_id
  try {
    const response = await alphaguardModelsApi.revokeCredential(credential.credential_id)
    if (response.data.cleanup_status === 'PENDING') {
      ElMessage.warning('API 密钥已撤销；安全存储中的孤立项将在下次清理时重试。')
    } else {
      ElMessage.success('API 密钥已撤销。')
    }
    await load()
  } catch (error) {
    showActionError('撤销 API 密钥失败', error)
  } finally {
    credentialOperationId.value = ''
  }
}

function resetModelForm() {
  modelForm.remoteName = ''
  modelForm.displayName = ''
  modelForm.roles = []
  modelForm.supportsJsonSchema = false
  modelForm.supportsToolCall = false
  modelForm.pricingSource = prices.value.some(price =>
    price.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id
    && price.endpoint_profile_version === selectedEndpoint.value?.profile_version
    && price.pricing_source === 'SELF_HOSTED'
  ) ? 'SELF_HOSTED' : 'PROVIDER_PUBLISHED'
  modelForm.inputPrice = ''
  modelForm.outputPrice = ''
  modelForm.priceSource = ''
  modelForm.priceVerified = false
  modelOptionsError.value = ''
}

function openModelDialog() {
  if (modelAddBlockedReason.value) {
    ElMessage.warning(modelAddBlockedReason.value)
    return
  }
  resetModelForm()
  modelDialogVisible.value = true
}

async function refreshModelOptions() {
  const endpoint = selectedEndpoint.value
  const credential = currentCredential.value
  if (!endpoint || !credential || modelOptionsBlockedReason.value) {
    if (modelOptionsBlockedReason.value) ElMessage.warning(modelOptionsBlockedReason.value)
    return
  }
  modelOptionsLoading.value = true
  modelOptionsError.value = ''
  try {
    const response = await alphaguardModelsApi.endpointModelOptions(endpoint.endpoint_profile_id, {
      endpoint_profile_version: endpoint.profile_version,
      credential_id: credential.credential_id
    })
    providerModelOptions.value = response.data.items
    providerModelOptionsEndpoint.value = endpointIdentity(endpoint)
    if (response.data.items.length) {
      ElMessage.success(`已读取 ${response.data.items.length} 个服务商模型。`)
    } else {
      ElMessage.info('服务商未返回模型列表，仍可手动输入模型名称。')
    }
  } catch (error) {
    modelOptionsError.value = parseActionError('读取服务商模型失败', error)
  } finally {
    modelOptionsLoading.value = false
  }
}

async function saveModel() {
  const endpoint = selectedEndpoint.value
  if (!endpoint) {
    ElMessage.warning('请先添加模型服务。')
    return
  }
  if (modelDialogBlockedReason.value) {
    ElMessage.warning(modelDialogBlockedReason.value)
    return
  }
  modelSaving.value = true
  try {
    const sameNameModels = modelsWithRemoteName(modelForm.remoteName.trim())
    const reusableModel = sameNameModels.find(modelMatchesForm)
    let model = reusableModel
    let modelResult: 'CREATED' | 'REUSED' = 'REUSED'
    if (!model) {
      const latest = sameNameModels[0]
      const modelResponse = await alphaguardModelsApi.createEndpointModel(endpoint.endpoint_profile_id, {
        endpoint_profile_version: endpoint.profile_version,
        remote_model_name: modelForm.remoteName.trim(),
        display_name: modelForm.displayName.trim() || modelForm.remoteName.trim(),
        role_capabilities: modelForm.roles,
        supports_json_schema: modelForm.supportsJsonSchema,
        supports_tool_call: modelForm.supportsToolCall,
        ...(latest
          ? {
              endpoint_model_id: latest.endpoint_model_id,
              model_version: nextModelVersion(sameNameModels)
            }
          : {})
      })
      model = modelResponse.data.item
      modelResult = modelResponse.data.result
    }
    const selfHosted = modelForm.pricingSource === 'SELF_HOSTED'
    const existingPrice = matchingPrice(model)
    if (!existingPrice) {
      await alphaguardModelsApi.createPrice({
        endpoint_profile_id: endpoint.endpoint_profile_id,
        endpoint_profile_version: endpoint.profile_version,
        endpoint_model_id: model.endpoint_model_id,
        endpoint_model_version: model.model_version,
        pricing_source: modelForm.pricingSource,
        input_price_per_million: selfHosted ? '0' : modelForm.inputPrice.trim(),
        cached_input_price_per_million: '0',
        output_price_per_million: selfHosted ? '0' : modelForm.outputPrice.trim(),
        currency: 'USD',
        effective_at: new Date().toISOString(),
        source_description: selfHosted ? 'SELF_HOSTED' : modelForm.priceSource.trim(),
        verified: true
      })
    }
    modelDialogVisible.value = false
    ElMessage.success(`模型已${statusLabel(modelResult)}，价格记录已${existingPrice ? '复用' : '保存'}。`)
    await load()
  } catch (error) {
    showActionError('添加模型失败', error)
  } finally {
    modelSaving.value = false
  }
}

async function saveDecisionModels() {
  if (modelSaveBlockedReason.value) {
    ElMessage.warning(modelSaveBlockedReason.value)
    return
  }
  const endpoint = selectedEndpoint.value
  const credential = currentCredential.value
  const normal = modelFromIdentity(normalModelIdentity.value)
  const top = modelFromIdentity(topModelIdentity.value)
  if (!endpoint || !credential || !normal || !top) return
  modelsSaving.value = true
  try {
    await alphaguardModelsApi.configureDecisionModels({
      endpoint_profile_id: endpoint.endpoint_profile_id,
      endpoint_profile_version: endpoint.profile_version,
      credential_id: credential.credential_id,
      normal_endpoint_model_id: normal.endpoint_model_id,
      normal_endpoint_model_version: normal.model_version,
      top_endpoint_model_id: top.endpoint_model_id,
      top_endpoint_model_version: top.model_version,
      explicit_same_model_confirmation: sameModelConfirmed.value
    })
    ElMessage.success('两个决策模型已保存。')
    await load()
  } catch (error) {
    showActionError('保存模型设置失败', error)
  } finally {
    modelsSaving.value = false
  }
}

async function runCapabilityChecks() {
  if (capabilityBlockedReason.value) {
    ElMessage.warning(capabilityBlockedReason.value)
    return
  }
  try {
    await ElMessageBox.confirm(
      capabilityFailureDetail.value
        ? '当前模型上次检测未通过。如果没有更换模型或处理服务商额度，本次结果很可能相同。确认再次发送最小验证请求吗？不会创建订单。'
        : '将向两个模型发送最小验证请求，检查认证、访问权限和结构化输出。不会创建订单。',
      capabilityActionLabel.value,
      { type: 'warning', confirmButtonText: capabilityActionLabel.value, cancelButtonText: '取消' }
    )
  } catch (error) {
    if (!isDialogCancellation(error)) {
      showActionError('打开检测确认失败', error)
    }
    return
  }
  const targets = endpointProfiles.value.filter(item => item.capability !== 'READY')
  const results: Array<{ role: DecisionRole; status: string }> = []
  capabilityChecking.value = true
  try {
    for (const [index, profile] of targets.entries()) {
      const response = await alphaguardModelsApi.capabilityCheck({
        profile_id: profile.profile_id,
        profile_version: profile.profile_version,
        idempotency_key: `ui-${profile.profile_id}-${Date.now()}-${index}`,
        network: true
      })
      results.push({ role: profile.role as DecisionRole, status: response.data.status })
    }
    await load()
    const failed = results.filter(result => result.status !== 'READY')
    if (failed.length) {
      const summary = failed
        .map(result => `${roleLabel(result.role)}：${statusLabel(result.status)}`)
        .join('；')
      ElMessage.warning(`检测已执行，但未全部通过（${summary}）。请先处理对应模型，重复检测不会自动更换配置。`)
    } else {
      ElMessage.success('连接检测已完成，两个模型均可用。')
    }
  } catch (error) {
    showActionError('连接检测失败', error)
    await load()
  } finally {
    capabilityChecking.value = false
  }
}

function isDialogCancellation(error: unknown): boolean {
  if (error === 'cancel' || error === 'close') return true
  return error instanceof Error && ['cancel', 'close'].includes(error.message)
}

async function loadAuditData() {
  if (!advancedSections.value.includes('technical') || auditLoaded.value || !canManage.value) return
  try {
    const [runsResponse, validationResponse, contractResponse] = await Promise.all([
      alphaguardModelsApi.runs(100),
      alphaguardModelsApi.validationRuns(20),
      alphaguardModelsApi.contractChecks(20)
    ])
    modelRuns.value = runsResponse.data.items
    validationRuns.value = validationResponse.data.items
    contractChecks.value = contractResponse.data.items
    auditLoaded.value = true
  } catch (error) {
    showActionError('加载审计记录失败', error)
  }
}

onMounted(load)
</script>

<style scoped>
.model-configuration { min-height: 240px; }
.page-heading, .section-heading, .setting-row, .heading-actions, .section-actions, .primary-actions { display: flex; align-items: center; }
.page-heading, .section-heading, .setting-row { justify-content: space-between; }
.page-heading { gap: 20px; padding: 4px 0 18px; border-bottom: 1px solid var(--el-border-color-light); }
.page-heading h2, .section-heading h3 { margin: 0; letter-spacing: 0; }
.page-heading h2 { font-size: 20px; }
.page-heading p, .section-heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.heading-actions, .section-actions, .primary-actions { gap: 8px; flex-wrap: wrap; }
.next-action { display: flex; align-items: center; gap: 10px; margin: 16px 0 2px; padding: 11px 14px; border-left: 3px solid var(--el-color-warning); background: var(--el-color-warning-light-9); }
.next-action.complete { border-left-color: var(--el-color-success); background: var(--el-color-success-light-9); }
.next-action > div { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.next-action span { color: var(--el-text-color-secondary); font-size: 13px; }
.action-feedback { margin-top: 14px; }
.settings-section { padding: 22px 0; border-bottom: 1px solid var(--el-border-color-light); }
.settings-section--last { border-bottom: 0; }
.section-heading { align-items: flex-start; gap: 12px; }
.section-heading > div:nth-child(2) { flex: 1; min-width: 180px; }
.section-heading h3 { font-size: 15px; }
.section-icon { display: grid; place-items: center; width: 32px; height: 32px; flex: 0 0 32px; color: var(--el-color-primary); background: var(--el-color-primary-light-9); border-radius: 6px; }
.section-icon :deep(svg) { width: 17px; height: 17px; }
.setting-row { gap: 14px; min-height: 52px; margin-left: 44px; padding: 9px 0; }
.setting-row--secondary { min-height: 40px; padding-top: 0; }
.setting-label { width: 96px; flex: 0 0 96px; color: var(--el-text-color-secondary); font-size: 13px; }
.setting-value { display: grid; gap: 3px; min-width: 0; flex: 1; }
.setting-value span { color: var(--el-text-color-secondary); font-size: 12px; overflow-wrap: anywhere; }
.setting-value--mono span { font-family: var(--el-font-family); }
.hash-value { font-family: var(--el-font-family); white-space: nowrap; }
.setting-control { width: min(440px, 100%); margin-right: auto; }
.role-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin: 18px 0 14px 44px; }
.role-field { display: grid; gap: 9px; min-width: 0; }
.role-field__heading, .capability-summary > div { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.role-field small { min-height: 36px; color: var(--el-text-color-secondary); line-height: 1.5; }
.primary-actions { margin: 14px 0 0 44px; }
.action-hint { color: var(--el-color-warning); font-size: 13px; line-height: 1.5; }
.saved-state { display: flex; align-items: center; gap: 6px; margin: 14px 0 0 44px; color: var(--el-color-success); font-size: 13px; }
.capability-result { margin: 12px 0 0 44px; width: calc(100% - 44px); }
.capability-note { margin: 12px 0 0 44px; color: var(--el-color-warning-dark-2); font-size: 13px; line-height: 1.5; }
.capability-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 16px 0 8px 44px; }
.capability-summary > div { padding: 9px 11px; border: 1px solid var(--el-border-color-lighter); border-radius: 5px; }
.technical-records { margin-top: 8px; border-top: 1px solid var(--el-border-color-light); }
.technical-records h4 { margin: 20px 0 10px; font-size: 13px; letter-spacing: 0; }
.technical-error { margin-bottom: 14px; }
.security-note { margin: 12px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.dialog-summary { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; padding: 11px 13px; background: var(--el-fill-color-lighter); border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.dialog-summary span { color: var(--el-text-color-secondary); }
.dialog-summary strong { min-width: 0; overflow-wrap: anywhere; text-align: right; }
.dialog-advanced { margin-top: 16px; }
.model-name-control { display: flex; align-items: center; gap: 8px; width: 100%; }
.model-name-select { flex: 1; min-width: 0; }
.model-option-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.model-option-source { margin-left: 14px; color: var(--el-text-color-secondary); font-size: 12px; }
.model-options-status { margin-top: 7px; color: var(--el-text-color-secondary); font-size: 12px; }
.model-options-error { margin-top: 9px; }
.price-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
@media (max-width: 720px) {
  .page-heading { align-items: stretch; flex-direction: column; }
  .section-heading { display: grid; grid-template-columns: 32px minmax(0, 1fr); }
  .section-heading > div:nth-child(2) { min-width: 0; }
  .section-actions { grid-column: 1 / -1; margin-left: 44px; }
  .setting-row { margin-left: 0; display: grid; grid-template-columns: 1fr auto; }
  .setting-label { width: auto; grid-column: 1 / -1; }
  .setting-value, .setting-control { grid-column: 1; }
  .role-grid, .capability-summary, .price-grid { grid-template-columns: 1fr; margin-left: 0; }
  .primary-actions, .saved-state, .capability-result, .capability-note { margin-left: 0; width: 100%; }
}
</style>
