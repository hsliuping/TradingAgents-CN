<template>
  <div class="ta-debug">
    <div class="ta-toolbar">
      <el-button link @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>
    <el-card>
      <el-form :model="form" label-width="120px">
        <!-- 🆕 调试模式选择 -->
        <el-form-item label="调试模式">
          <el-radio-group v-model="debugMode">
            <el-radio label="agent">单个 Agent 调试</el-radio>
            <el-radio label="workflow">完整工作流调试</el-radio>
            <el-radio label="invocations">调用记录</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 单个 Agent 调试：Agent 类型 -->
        <el-form-item label="Agent 类型" v-if="debugMode === 'agent'">
          <div class="agent-select-block">
            <el-select v-model="form.analyst_type" style="width: 420px" placeholder="选择 Agent">
              <el-option-group v-for="group in groupedAgents" :key="group.key" :label="group.label">
                <el-option
                  v-for="agent in group.agents"
                  :key="agent.id"
                  :label="agent.name"
                  :value="agent.id"
                >
                  <div class="agent-option-row">
                    <div class="agent-option-main">
                      <span class="agent-option-name">{{ agent.name }}</span>
                      <div class="agent-option-tags">
                        <el-tag
                          size="small"
                          effect="plain"
                          :type="getAgentCategoryTagType(agent.category)"
                        >
                          {{ formatAgentCategory(agent.category) }}
                        </el-tag>
                        <el-tag
                          v-if="agent.input_mode === 'upstream-dependent' || agent.input_mode === 'mixed'"
                          size="small"
                          :type="getAgentInputModeTagType(agent.input_mode)"
                        >
                          {{ formatAgentInputMode(agent.input_mode) }}
                        </el-tag>
                        <el-tag
                          v-if="agent.debug_replay_mode === 'requires_chain_prefill'"
                          size="small"
                          :type="getAgentReplayModeTagType(agent.debug_replay_mode)"
                        >
                          {{ formatAgentDebugReplayMode(agent.debug_replay_mode) }}
                        </el-tag>
                        <el-tag
                          v-if="agent.maintenance_status === 'unmaintained'"
                          size="small"
                          :type="getAgentMaintenanceTagType(agent.maintenance_status)"
                        >
                          {{ formatAgentMaintenanceStatus(agent.maintenance_status) }}
                        </el-tag>
                      </div>
                    </div>
                    <span class="agent-option-version">{{ agent.version }}</span>
                  </div>
                </el-option>
              </el-option-group>
            </el-select>
            <el-switch
              v-model="showUnmaintainedAgents"
              inline-prompt
              active-text="显示停止维护 Agent"
              inactive-text="隐藏停止维护 Agent"
            />
          </div>
        </el-form-item>

        <el-form-item label="治理信息" v-if="debugMode === 'agent' && selectedAgent">
          <div class="agent-governance-card">
            <div class="agent-governance-tags">
              <el-tag size="small" :type="getAgentMaturityTagType(selectedAgent.maturity_level)">
                成熟度 {{ formatAgentMaturityLevel(selectedAgent.maturity_level) }}
              </el-tag>
              <el-tag size="small" :type="getAgentInputModeTagType(selectedAgent.input_mode)">
                输入 {{ formatAgentInputMode(selectedAgent.input_mode) }}
              </el-tag>
              <el-tag size="small" :type="getAgentReplayModeTagType(selectedAgent.debug_replay_mode)">
                调试 {{ formatAgentDebugReplayMode(selectedAgent.debug_replay_mode) }}
              </el-tag>
              <el-tag size="small" :type="getAgentMaintenanceTagType(selectedAgent.maintenance_status)">
                维护 {{ formatAgentMaintenanceStatus(selectedAgent.maintenance_status) }}
              </el-tag>
            </div>
            <div class="agent-governance-surfaces">
              <span class="agent-governance-label">可调用入口</span>
              <el-tag
                v-for="surface in selectedAgent.callable_surfaces || []"
                :key="surface"
                size="small"
                effect="plain"
              >
                {{ formatCallableSurface(surface) }}
              </el-tag>
            </div>
            <div class="agent-governance-hint">{{ buildAgentGovernanceHint(selectedAgent) }}</div>
          </div>
        </el-form-item>

        <!-- 🆕 完整工作流调试：工作流选择 -->
        <el-form-item label="工作流" v-if="debugMode === 'workflow'">
          <el-select v-model="form.workflow_id" style="width: 400px" placeholder="选择工作流" filterable>
            <el-option-group v-for="group in groupedWorkflows" :key="group.type" :label="group.label">
              <el-option
                v-for="wf in group.workflows"
                :key="wf.id"
                :label="wf.name"
                :value="wf.id"
              >
                <span>{{ wf.name }}</span>
                <el-tag v-if="wf.is_system" size="small" type="info" style="margin-left: 8px">系统</el-tag>
              </el-option>
            </el-option-group>
          </el-select>
          <span style="font-size:12px;color:#909399;margin-left:10px;">{{ selectedWorkflowDesc }}</span>
        </el-form-item>

        <template v-if="debugMode === 'invocations'">
          <el-form-item v-if="form.invocation_locked_root_id" label="链路锁定">
            <div class="invocation-lock-banner">
              <el-tag type="warning" effect="dark">已锁定当前 root 链</el-tag>
              <span class="invocation-lock-root">{{ form.invocation_locked_root_id }}</span>
              <el-button link type="primary" @click="clearInvocationChainLock">解除锁定</el-button>
            </div>
          </el-form-item>
          <el-form-item label="来源类型">
            <el-select v-model="form.invocation_source_type" style="width: 220px" placeholder="全部来源" clearable>
              <el-option label="全部来源" value="" />
              <el-option label="Assistant -> Agent" value="assistant" />
              <el-option label="Workflow -> Agent" value="workflow" />
              <el-option label="Agent -> Agent" value="agent" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标 Agent">
            <el-input v-model="form.invocation_target_id" placeholder="如 research_manager_v2" style="width: 320px" clearable />
          </el-form-item>
          <el-form-item label="工作流 / 线程">
            <el-input v-model="form.invocation_workflow_id" placeholder="工作流 ID，可选" style="width: 260px" clearable />
            <el-input v-model="form.invocation_thread_id" placeholder="线程 ID，可选" style="width: 260px; margin-left: 12px" clearable />
          </el-form-item>
          <el-form-item label="执行状态">
            <el-select v-model="form.invocation_status" style="width: 220px" placeholder="全部状态" clearable>
              <el-option label="全部状态" value="" />
              <el-option label="成功" value="succeeded" />
              <el-option label="失败" value="failed" />
              <el-option label="运行中" value="running" />
            </el-select>
            <el-input v-model="form.invocation_symbol" placeholder="股票代码，可选" style="width: 220px; margin-left: 12px" clearable />
          </el-form-item>
        </template>

        <!-- 单个 Agent 调试：流程专属提示词（可选） -->
        <el-form-item label="流程专属提示词" v-if="debugMode === 'agent'">
          <el-select v-model="form.workflow_id" style="width: 300px" placeholder="可选：选择流程以使用流程专属提示词" clearable filterable>
            <el-option label="使用默认提示词" value="" />
            <el-option-group v-for="group in groupedWorkflows" :key="group.type" :label="group.label">
              <el-option
                v-for="wf in group.workflows"
                :key="wf.id"
                :label="wf.name"
                :value="wf.id"
              />
            </el-option-group>
          </el-select>
          <span style="font-size:12px;color:#909399;margin-left:10px;">指定后将加载该流程的专属提示词</span>
        </el-form-item>

        <el-form-item label="研究深度" v-if="debugMode === 'agent'">
          <el-select v-model="researchDepth" style="width: 200px">
            <el-option label="快速" value="快速" />
            <el-option label="基础" value="基础" />
            <el-option label="标准" value="标准" />
            <el-option label="深度" value="深度" />
            <el-option label="全面" value="全面" />
          </el-select>
        </el-form-item>
        <template v-if="debugMode === 'agent' && selectedAgentRequiresExtraState && selectedAgentDebugInputs.length > 0">
          <el-alert
            :title="selectedAgentExtraStateAlertTitle"
            type="info"
            :closable="false"
            style="margin-bottom: 18px;"
          />
          <el-form-item
            v-for="input in selectedAgentDebugInputs"
            :key="input.name"
            :label="input.description || input.name"
          >
            <div class="debug-contract-field">
              <div class="debug-contract-meta">
                <el-tag size="small" type="info" effect="plain">
                  来源 {{ formatInputContractSource((input as any).source) }}
                </el-tag>
                <el-tag size="small" effect="plain">
                  注入 state.{{ input.name }}
                </el-tag>
                <el-tag v-if="(input as any).state_field" size="small" effect="plain">
                  来源字段 {{ buildInputSourceFieldLabel(input) }}
                </el-tag>
                <el-tag v-if="(input as any).producer_hint" size="small" type="warning" effect="plain">
                  上游 {{ (input as any).producer_hint }}
                </el-tag>
                <el-tag v-if="(input as any).required === false" size="small" type="success" effect="plain">
                  可选
                </el-tag>
              </div>
              <el-input
                v-model="form.extra_state[input.name]"
                type="textarea"
                :rows="6"
                :placeholder="buildDebugInputPlaceholder(input)"
              />
            </div>
          </el-form-item>
        </template>
        <el-form-item label="模板来源" v-if="debugMode === 'agent'">
          <el-radio-group v-model="form.use_current">
            <el-radio :label="true">当前激活</el-radio>
            <el-radio :label="false">指定模板ID</el-radio>
          </el-radio-group>
          <el-input v-model="form.template_id" placeholder="模板ID" style="width: 300px; margin-left: 12px" :disabled="form.use_current" />
        </el-form-item>
        <el-form-item label="模型名称">
          <DeepModelSelector v-model="form.llm.model" :available-models="availableModels" type="deep" width="320px" />
        </el-form-item>
        <el-form-item label="生成参数">
          <div style="display:flex;align-items:center;gap:16px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:64px;color:#606266;">温度</span>
              <el-input-number v-model="form.llm.temperature" :min="0" :max="1" :step="0.1" />
              <span style="font-size:12px;color:#909399;">控制输出随机性，0更稳定，1更发散</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:88px;color:#606266;">最大Token</span>
              <el-input-number v-model="form.llm.max_tokens" :min="256" :max="8192" :step="256" />
              <span style="font-size:12px;color:#909399;">限制每次输出的最大Token数量</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="股票代码" v-if="needsStockSymbol">
          <el-input v-model="form.stock.symbol" placeholder="如 600519" style="width: 200px" />
          <el-date-picker
            v-model="form.stock.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="分析日期"
            style="width: 180px; margin-left:12px"
          />
        </el-form-item>
        <el-form-item label="分析日期" v-if="!needsStockSymbol">
          <el-date-picker
            v-model="form.stock.analysis_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="分析日期"
            style="width: 200px"
          />
          <span style="font-size:12px;color:#909399;margin-left:10px;">大盘分析不需要指定具体股票</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runDebug" :loading="loading">
            {{ debugMode === 'workflow' ? '运行工作流调试' : debugMode === 'invocations' ? '查询调用记录' : '运行调试' }}
          </el-button>
          <span v-if="workflowDebugTaskId && debugMode === 'workflow'" class="debug-task-tip">
            任务 {{ workflowDebugTaskId }} · {{ workflowDebugMessage || '正在执行...' }}
          </span>
        </el-form-item>
        <el-form-item v-if="workflowDebugTaskId && debugMode === 'workflow'" label="调试进度">
          <el-progress :percentage="workflowDebugProgress" style="width: 420px" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 单个 Agent 结果 -->
    <el-card class="ta-result" v-if="result && debugMode === 'agent'">
      <template #header>
        <div class="card-header">
          <span>📊 分析结果</span>
          <span class="meta-info">{{ result.analyst_type }} · {{ result.symbol }} · {{ result.report_length }} 字符</span>
        </div>
      </template>
      <el-scrollbar height="600px">
        <div class="markdown-body" v-html="renderMarkdown(result.report)"></div>
      </el-scrollbar>
    </el-card>

    <!-- 🆕 工作流调试结果 -->
    <el-card class="ta-result" v-if="workflowResult && debugMode === 'workflow'">
      <template #header>
        <div class="card-header">
          <span>📊 工作流执行结果</span>
          <span class="meta-info">{{ workflowResult.workflow_name }} · {{ workflowResult.symbol }} · {{ workflowResult.report_length }} 字符</span>
        </div>
      </template>
      <el-tabs v-model="activeReportTab">
        <el-tab-pane label="汇总报告" name="summary">
          <el-scrollbar height="550px">
            <div class="markdown-body" v-html="renderMarkdown(workflowResult.report)"></div>
          </el-scrollbar>
        </el-tab-pane>
        <el-tab-pane
          v-for="(report, key) in workflowResult.agent_reports"
          :key="key"
          :label="formatAgentReportLabel(key)"
          :name="key"
        >
          <el-scrollbar height="550px">
            <div class="markdown-body" v-html="renderMarkdown(report)"></div>
          </el-scrollbar>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card class="ta-result" v-if="invocationResult && debugMode === 'invocations'">
      <template #header>
        <div class="card-header">
          <span>调用记录</span>
          <span class="meta-info">共 {{ invocationResult.total }} {{ form.invocation_view_mode === 'chain' ? '条链路' : '条记录' }}</span>
        </div>
      </template>

      <div class="invocation-view-switch">
        <el-radio-group v-model="form.invocation_view_mode" @change="handleInvocationViewModeChange">
          <el-radio-button label="flat">平铺</el-radio-button>
          <el-radio-button label="chain">按调用链</el-radio-button>
        </el-radio-group>
      </div>

      <el-table
        v-if="form.invocation_view_mode === 'flat'"
        :data="invocationResult.items"
        stripe
        highlight-current-row
        style="width: 100%"
        @row-click="handleInvocationRowClick"
      >
        <el-table-column prop="source_type" label="来源" width="140">
          <template #default="scope">
            {{ formatInvocationSource(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="目标 Agent" min-width="260" show-overflow-tooltip>
          <template #default="scope">
            <div class="invocation-agent-cell">
              <span class="invocation-agent-name">{{ scope.row.target_id || '-' }}</span>
              <div class="invocation-agent-tags" v-if="getInvocationTargetAgent(scope.row)">
                <el-tag
                  v-if="getInvocationTargetAgent(scope.row)?.input_mode === 'upstream-dependent' || getInvocationTargetAgent(scope.row)?.input_mode === 'mixed'"
                  size="small"
                  :type="getAgentInputModeTagType(getInvocationTargetAgent(scope.row)?.input_mode)"
                >
                  {{ formatAgentInputMode(getInvocationTargetAgent(scope.row)?.input_mode) }}
                </el-tag>
                <el-tag
                  v-if="getInvocationTargetAgent(scope.row)?.debug_replay_mode === 'requires_chain_prefill'"
                  size="small"
                  :type="getAgentReplayModeTagType(getInvocationTargetAgent(scope.row)?.debug_replay_mode)"
                >
                  {{ formatAgentDebugReplayMode(getInvocationTargetAgent(scope.row)?.debug_replay_mode) }}
                </el-tag>
                <el-tag
                  v-if="getInvocationTargetAgent(scope.row)?.maintenance_status === 'unmaintained'"
                  size="small"
                  :type="getAgentMaintenanceTagType(getInvocationTargetAgent(scope.row)?.maintenance_status)"
                >
                  {{ formatAgentMaintenanceStatus(getInvocationTargetAgent(scope.row)?.maintenance_status) }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getInvocationStatusTagType(scope.row.status)">{{ scope.row.status || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="workflow_id" label="工作流" min-width="180" show-overflow-tooltip />
        <el-table-column prop="thread_id" label="线程" min-width="180" show-overflow-tooltip />
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="200" />
      </el-table>

      <div v-else class="invocation-chain-list">
        <el-collapse>
          <el-collapse-item
            v-for="chain in invocationResult.chains || []"
            :key="chain.root_invocation_id"
            :name="chain.root_invocation_id"
          >
            <template #title>
              <div class="invocation-chain-header">
                <div class="invocation-chain-main">
                  <span class="invocation-chain-root">{{ chain.root_invocation_id }}</span>
                  <span class="invocation-chain-meta">{{ chain.count }} 个节点</span>
                  <span class="invocation-chain-meta" v-if="chain.symbol">{{ chain.symbol }}</span>
                  <span class="invocation-chain-meta" v-if="chain.latest_created_at">{{ chain.latest_created_at }}</span>
                </div>
                <div class="invocation-chain-statuses">
                  <el-tag
                    v-for="(count, status) in chain.status_counts"
                    :key="status"
                    size="small"
                    :type="getInvocationStatusTagType(status)"
                  >
                    {{ status }} {{ count }}
                  </el-tag>
                </div>
              </div>
            </template>

            <div
              v-for="item in chain.items"
              :key="item.invocation_id"
              class="invocation-chain-item"
              :class="{ 'is-selected': selectedInvocation?.invocation_id === item.invocation_id }"
              @click="handleInvocationRowClick(item)"
            >
              <div class="invocation-chain-item-top">
                <div>
                  <span class="invocation-chain-item-title">{{ formatInvocationSource(item) }}</span>
                  <span class="invocation-chain-item-agent">{{ item.target_id || '-' }}</span>
                  <div class="invocation-agent-tags invocation-agent-tags-inline" v-if="getInvocationTargetAgent(item)">
                    <el-tag
                      v-if="getInvocationTargetAgent(item)?.input_mode === 'upstream-dependent' || getInvocationTargetAgent(item)?.input_mode === 'mixed'"
                      size="small"
                      :type="getAgentInputModeTagType(getInvocationTargetAgent(item)?.input_mode)"
                    >
                      {{ formatAgentInputMode(getInvocationTargetAgent(item)?.input_mode) }}
                    </el-tag>
                    <el-tag
                      v-if="getInvocationTargetAgent(item)?.debug_replay_mode === 'requires_chain_prefill'"
                      size="small"
                      :type="getAgentReplayModeTagType(getInvocationTargetAgent(item)?.debug_replay_mode)"
                    >
                      {{ formatAgentDebugReplayMode(getInvocationTargetAgent(item)?.debug_replay_mode) }}
                    </el-tag>
                    <el-tag
                      v-if="getInvocationTargetAgent(item)?.maintenance_status === 'unmaintained'"
                      size="small"
                      :type="getAgentMaintenanceTagType(getInvocationTargetAgent(item)?.maintenance_status)"
                    >
                      {{ formatAgentMaintenanceStatus(getInvocationTargetAgent(item)?.maintenance_status) }}
                    </el-tag>
                  </div>
                </div>
                <el-tag :type="getInvocationStatusTagType(item.status)">{{ item.status || '-' }}</el-tag>
              </div>
              <div class="invocation-chain-item-meta">
                <span>{{ item.invocation_id }}</span>
                <span v-if="item.parent_invocation_id">Parent: {{ item.parent_invocation_id }}</span>
                <span v-if="item.created_at">{{ item.created_at }}</span>
              </div>
              <div class="invocation-chain-item-summary">{{ item.summary || '无摘要' }}</div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div style="display:flex;justify-content:flex-end;margin-top:12px;">
        <el-pagination
          layout="total, prev, pager, next"
          :total="invocationResult.total"
          :page-size="invocationResult.page_size"
          :current-page="invocationResult.page"
          @current-change="handleInvocationPageChange"
        />
      </div>

      <div v-if="selectedInvocation" ref="invocationDetailRef" class="invocation-detail">
        <div class="invocation-actions">
          <el-button @click="handleLockCurrentInvocationChain">
            {{ isCurrentInvocationChainLocked ? '当前链已锁定' : '锁定当前链' }}
          </el-button>
          <el-button type="primary" @click="handleJumpToDebugFromInvocation">
            {{ selectedInvocationJumpActionLabel }}
          </el-button>
        </div>
        <el-alert
          v-if="selectedInvocationJumpActionHint"
          :title="selectedInvocationJumpActionHint"
          type="info"
          :closable="false"
          class="invocation-action-alert"
        />
        <el-descriptions :column="2" border>
          <el-descriptions-item label="调用 ID">{{ selectedInvocation.invocation_id }}</el-descriptions-item>
          <el-descriptions-item label="Root 调用 ID">{{ selectedInvocation.root_invocation_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ formatInvocationSource(selectedInvocation) }}</el-descriptions-item>
          <el-descriptions-item label="Parent 调用 ID">{{ selectedInvocation.parent_invocation_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源 ID">{{ selectedInvocation.source_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标 Agent">{{ selectedInvocation.target_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="工作流 ID">{{ selectedInvocation.workflow_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行 ID">{{ selectedInvocation.execution_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="线程 ID">{{ selectedInvocation.thread_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="输出字段">{{ selectedInvocation.output_field || '-' }}</el-descriptions-item>
          <el-descriptions-item label="股票代码">{{ selectedInvocation.symbol || '-' }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ selectedInvocation.error_message || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="selectedInvocationTargetAgent" class="agent-governance-card invocation-governance-card">
          <div class="invocation-json-title">目标 Agent 治理信息</div>
          <div class="agent-governance-tags">
            <el-tag size="small" :type="getAgentMaturityTagType(selectedInvocationTargetAgent.maturity_level)">
              成熟度 {{ formatAgentMaturityLevel(selectedInvocationTargetAgent.maturity_level) }}
            </el-tag>
            <el-tag size="small" :type="getAgentInputModeTagType(selectedInvocationTargetAgent.input_mode)">
              输入 {{ formatAgentInputMode(selectedInvocationTargetAgent.input_mode) }}
            </el-tag>
            <el-tag size="small" :type="getAgentReplayModeTagType(selectedInvocationTargetAgent.debug_replay_mode)">
              调试 {{ formatAgentDebugReplayMode(selectedInvocationTargetAgent.debug_replay_mode) }}
            </el-tag>
            <el-tag size="small" :type="getAgentMaintenanceTagType(selectedInvocationTargetAgent.maintenance_status)">
              维护 {{ formatAgentMaintenanceStatus(selectedInvocationTargetAgent.maintenance_status) }}
            </el-tag>
          </div>
          <div class="agent-governance-surfaces" v-if="(selectedInvocationTargetAgent.callable_surfaces || []).length > 0">
            <span class="agent-governance-label">可调用入口</span>
            <el-tag
              v-for="surface in selectedInvocationTargetAgent.callable_surfaces || []"
              :key="surface"
              size="small"
              effect="plain"
            >
              {{ formatCallableSurface(surface) }}
            </el-tag>
          </div>
          <div class="agent-governance-hint">{{ buildAgentGovernanceHint(selectedInvocationTargetAgent) }}</div>
        </div>

        <div v-if="selectedInvocationInputSources.length > 0" class="invocation-input-sources">
          <div class="invocation-json-title">前置输入来源</div>
          <el-table :data="selectedInvocationInputSources" stripe>
            <el-table-column label="输入字段" min-width="220" show-overflow-tooltip>
              <template #default="scope">
                <div class="invocation-input-label-cell">
                  <span>{{ scope.row.label }}</span>
                  <div class="invocation-input-label-tags">
                    <el-tag v-if="scope.row.targetField" size="small" effect="plain">注入 state.{{ scope.row.targetField }}</el-tag>
                    <el-tag v-if="scope.row.sourceFieldLabel" size="small" effect="plain">来源字段 {{ scope.row.sourceFieldLabel }}</el-tag>
                    <el-tag v-if="scope.row.producerHint" size="small" type="warning" effect="plain">上游 {{ scope.row.producerHint }}</el-tag>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="来源节点" min-width="240" show-overflow-tooltip>
              <template #default="scope">
                <span v-if="scope.row.sourceInvocationId">
                  <el-button link type="primary" @click.stop="handleSelectSourceInvocation(scope.row.sourceInvocationId)">
                    {{ scope.row.sourceTargetId || '-' }}
                  </el-button>
                  <span class="invocation-source-meta">{{ scope.row.sourceInvocationId }}</span>
                </span>
                <span v-else class="invocation-source-missing">未解析</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button
                  v-if="scope.row.sourceInvocationId"
                  link
                  type="primary"
                  @click.stop="handleCompareSourceInvocation(scope.row.sourceInvocationId)"
                >
                  对比
                </el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="scope">
                <el-tag v-if="scope.row.sourceStatus" size="small" :type="getInvocationStatusTagType(scope.row.sourceStatus)">
                  {{ scope.row.sourceStatus }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="preview" label="回填预览" min-width="360" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="invocation-json-grid">
          <div>
            <div class="invocation-json-title">Request</div>
            <pre class="ta-pre">{{ formatInvocationJson(selectedInvocation.request) }}</pre>
          </div>
          <div>
            <div class="invocation-json-title">Result</div>
            <pre class="ta-pre">{{ formatInvocationJson(selectedInvocation.result) }}</pre>
          </div>
        </div>

        <div v-if="compareSourceInvocation && compareAnchorInvocation" class="invocation-compare-panel">
          <div class="invocation-compare-header">
            <div class="invocation-json-title">来源节点对比</div>
            <el-button link @click="clearInvocationCompare">关闭对比</el-button>
          </div>
          <div class="invocation-compare-grid">
            <div>
              <div class="invocation-compare-card-title">
                当前节点
                <span class="invocation-source-meta">{{ compareAnchorInvocation.target_id || compareAnchorInvocation.invocation_id }}</span>
              </div>
              <div class="invocation-json-grid compare-inner-grid">
                <div>
                  <div class="invocation-json-title">Request</div>
                  <pre class="ta-pre">{{ formatInvocationJson(compareAnchorInvocation.request) }}</pre>
                </div>
                <div>
                  <div class="invocation-json-title">Result</div>
                  <pre class="ta-pre">{{ formatInvocationJson(compareAnchorInvocation.result) }}</pre>
                </div>
              </div>
            </div>
            <div>
              <div class="invocation-compare-card-title">
                来源节点
                <span class="invocation-source-meta">{{ compareSourceInvocation.target_id || compareSourceInvocation.invocation_id }}</span>
              </div>
              <div class="invocation-json-grid compare-inner-grid">
                <div>
                  <div class="invocation-json-title">Request</div>
                  <pre class="ta-pre">{{ formatInvocationJson(compareSourceInvocation.request) }}</pre>
                </div>
                <div>
                  <div class="invocation-json-title">Result</div>
                  <pre class="ta-pre">{{ formatInvocationJson(compareSourceInvocation.result) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TemplatesDebugApi, type WorkflowInfo, type TemplateDebugInvocationListResult, type TemplateDebugInvocationRecord, type DebugAgentInfo, type DebugAgentInputField, type DebugAgentInputContractField } from '@/api/templates_debug'
import { analysisApi } from '@/api/analysis'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configApi } from '@/api/config'
import { fetchTaskResultWithRetry } from '@/utils/taskResult'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import { ArrowLeft } from '@element-plus/icons-vue'

const DEBUG_PREFILL_STORAGE_PREFIX = 'template-debug-prefill:'

// 配置 marked 选项
// marked 配置已由 @/utils/markdown 统一管理
// Markdown 渲染函数
const renderMarkdown = (content: string): string => {
  if (!content) return '<p>暂无内容</p>'
  try {
    return safeMarkdown(content)
  } catch (e) {
    console.error('Markdown 渲染失败:', e)
    return `<pre style="white-space: pre-wrap; font-family: inherit;">${content}</pre>`
  }
}

// 🆕 调试模式：agent 或 workflow
const debugMode = ref<'agent' | 'workflow' | 'invocations'>('agent')

const form = ref({
  analyst_type: 'fundamentals',
  template_id: '',
  use_current: true,
  workflow_id: '',  // 🆕 工作流ID（用于流程专属提示词或完整工作流调试）
  invocation_source_type: '',
  invocation_target_id: '',
  invocation_workflow_id: '',
  invocation_thread_id: '',
  invocation_status: '',
  invocation_symbol: '',
  invocation_view_mode: 'flat' as 'flat' | 'chain',
  invocation_locked_root_id: '',
  extra_state: {} as Record<string, string>,
  llm: { provider: 'custom_openai', model: '', temperature: 0.2, max_tokens: 4000, backend_url: '' },
  stock: { symbol: '', analysis_date: '' }
})

const loading = ref(false)
const result = ref<any>(null)
const workflowResult = ref<any>(null)  // 🆕 工作流调试结果
const workflowDebugTaskId = ref<string | null>(null)
const workflowDebugPollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
const workflowDebugProgress = ref(0)
const workflowDebugMessage = ref('')
const invocationResult = ref<TemplateDebugInvocationListResult | null>(null)
const selectedInvocation = ref<TemplateDebugInvocationRecord | null>(null)
const invocationChainCache = ref<Record<string, TemplateDebugInvocationRecord[]>>({})
const invocationDetailRef = ref<HTMLElement | null>(null)
const compareAnchorInvocation = ref<TemplateDebugInvocationRecord | null>(null)
const compareSourceInvocation = ref<TemplateDebugInvocationRecord | null>(null)
const activeReportTab = ref('summary')  // 🆕 当前激活的报告标签页
const researchDepth = ref('标准')
const availableModels = ref<any[]>([])
const availableAgents = ref<DebugAgentInfo[]>([])
const availableWorkflows = ref<WorkflowInfo[]>([])  // 🆕 可用工作流列表
const showUnmaintainedAgents = ref(false)

const route = useRoute()
const router = useRouter()

// 🆕 按类型分组的工作流
const groupedWorkflows = computed(() => {
  const groups = [
    { type: 'template', label: '系统模板', workflows: [] as WorkflowInfo[] },
    { type: 'custom', label: '自定义工作流', workflows: [] as WorkflowInfo[] }
  ]

  availableWorkflows.value.forEach(wf => {
    if (wf.type === 'template' || wf.is_system) {
      groups[0].workflows.push(wf)
    } else {
      groups[1].workflows.push(wf)
    }
  })

  return groups.filter(group => group.workflows.length > 0)
})

// 🆕 选中工作流的描述
const selectedWorkflowDesc = computed(() => {
  const wf = availableWorkflows.value.find(w => w.id === form.value.workflow_id)
  return wf?.description || ''
})

const selectedAgent = computed(() => {
  return availableAgents.value.find(agent => agent.id === form.value.analyst_type) || null
})

const isUnmaintainedAgent = (agent?: DebugAgentInfo | null): boolean => {
  return agent?.maintenance_status === 'unmaintained'
}

const visibleAgents = computed(() => {
  if (showUnmaintainedAgents.value) {
    return availableAgents.value
  }
  return availableAgents.value.filter(agent => !isUnmaintainedAgent(agent))
})

const getAgentDebugInputs = (agent?: DebugAgentInfo | null): Array<DebugAgentInputField | DebugAgentInputContractField> => {
  const inputContract = agent?.input_contract || []
  const stateInputs = inputContract.filter(input => input.source === 'state')
  if (stateInputs.length > 0) {
    return stateInputs
  }
  return agent?.debug_inputs || []
}

const selectedAgentDebugInputs = computed(() => {
  return getAgentDebugInputs(selectedAgent.value)
})

const selectedAgentRequiresExtraState = computed(() => {
  const inputMode = selectedAgent.value?.input_mode
  const replayMode = selectedAgent.value?.debug_replay_mode
  if (inputMode === 'upstream-dependent' || inputMode === 'mixed') {
    return true
  }
  if (replayMode === 'requires_extra_state' || replayMode === 'requires_chain_prefill') {
    return true
  }
  return selectedAgentDebugInputs.value.length > 0
})

const selectedAgentExtraStateAlertTitle = computed(() => {
  if (selectedAgent.value?.debug_replay_mode === 'requires_chain_prefill') {
    return '当前 Agent 依赖上游链路输入，建议先从调用记录跳转回填；也可以手动补齐这些字段。'
  }
  return '当前 Agent 依赖上游 state，单独调试时需要手动补齐这些输入。'
})

const selectedInvocationTargetAgent = computed(() => {
  if (!selectedInvocation.value?.target_id) {
    return null
  }
  return availableAgents.value.find(agent => agent.id === selectedInvocation.value?.target_id) || null
})

const getInvocationTargetAgent = (record?: TemplateDebugInvocationRecord | null) => {
  if (!record?.target_id) {
    return null
  }
  return availableAgents.value.find(agent => agent.id === record.target_id) || null
}

const parseInvocationTime = (value?: string): number => {
  if (!value) return 0
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const extractInvocationOutputMap = (record: TemplateDebugInvocationRecord): Record<string, string> => {
  const outputMap: Record<string, string> = {}
  const result = record.result || {}
  const structuredOutput = result.structured_output
  if (structuredOutput && typeof structuredOutput === 'object' && !Array.isArray(structuredOutput)) {
    Object.entries(structuredOutput as Record<string, unknown>).forEach(([key, value]) => {
      if (typeof value === 'string' && value.trim()) {
        outputMap[key] = value.trim()
      }
    })
  }

  const outputField = record.output_field || (typeof result.output_field === 'string' ? result.output_field : '')
  const outputText = typeof result.output_text === 'string' ? result.output_text.trim() : ''
  if (outputField && outputText) {
    outputMap[outputField] = outputText
  }

  return outputMap
}

const getInputStateField = (input: DebugAgentInputField | DebugAgentInputContractField): string => {
  if ('state_field' in input && input.state_field) {
    return input.state_field
  }
  return input.name
}

const getInputSourceFields = (input: DebugAgentInputField | DebugAgentInputContractField): string[] => {
  const fields = [getInputStateField(input)]
  if ('source_state_fields' in input && Array.isArray(input.source_state_fields)) {
    input.source_state_fields.forEach(field => {
      if (field && !fields.includes(field)) {
        fields.push(field)
      }
    })
  }
  return fields
}

const getInputProducerHint = (input: DebugAgentInputField | DebugAgentInputContractField): string => {
  if ('producer_hint' in input && input.producer_hint) {
    return input.producer_hint
  }
  return ''
}

const buildInputSourceFieldLabel = (input: DebugAgentInputField | DebugAgentInputContractField): string => {
  return getInputSourceFields(input).join(' / ')
}

const findInvocationSourceForInput = (
  records: TemplateDebugInvocationRecord[],
  input: DebugAgentInputField | DebugAgentInputContractField
) => {
  const sourceFields = getInputSourceFields(input)
  const producerHint = getInputProducerHint(input)
  const matches = records
    .flatMap(record => {
      const outputMap = extractInvocationOutputMap(record)
      return sourceFields.map((field, index) => {
        const value = outputMap[field]
        if (typeof value !== 'string' || !value.trim()) {
          return null
        }
        return {
          record,
          value: value.trim(),
          matchedField: field,
          score: (producerHint && record.target_id === producerHint ? 10 : 0) + (sourceFields.length - index),
        }
      }).filter((item): item is { record: TemplateDebugInvocationRecord; value: string; matchedField: string; score: number } => !!item)
    })

  if (!matches.length) {
    return null
  }

  matches.sort((left, right) => {
    if (right.score !== left.score) {
      return right.score - left.score
    }
    const delta = parseInvocationTime(right.record.created_at) - parseInvocationTime(left.record.created_at)
    if (delta !== 0) {
      return delta
    }
    return (right.record.invocation_id || '').localeCompare(left.record.invocation_id || '')
  })

  return matches[0]
}

const buildExtraStateFromChain = (
  records: TemplateDebugInvocationRecord[],
  targetInvocation: TemplateDebugInvocationRecord,
  debugInputs: Array<DebugAgentInputField | DebugAgentInputContractField>
): Record<string, string> => {
  const extraState: Record<string, string> = {}

  const candidateRecords = records
    .filter(record => record.invocation_id !== targetInvocation.invocation_id)
    .sort((left, right) => {
      const delta = parseInvocationTime(right.created_at) - parseInvocationTime(left.created_at)
      if (delta !== 0) {
        return delta
      }
      return (right.invocation_id || '').localeCompare(left.invocation_id || '')
    })

  debugInputs.forEach(input => {
    const matched = findInvocationSourceForInput(candidateRecords, input)
    if (!matched || extraState[input.name]) {
      return
    }
    extraState[input.name] = matched.value
  })

  return extraState
}

const buildInputSourceRows = (
  records: TemplateDebugInvocationRecord[],
  targetInvocation: TemplateDebugInvocationRecord,
  debugInputs: Array<DebugAgentInputField | DebugAgentInputContractField>
) => {
  const candidateRecords = records
    .filter(record => record.invocation_id !== targetInvocation.invocation_id)
    .sort((left, right) => {
      const delta = parseInvocationTime(right.created_at) - parseInvocationTime(left.created_at)
      if (delta !== 0) {
        return delta
      }
      return (right.invocation_id || '').localeCompare(left.invocation_id || '')
    })

  return debugInputs.map(input => {
    const matched = findInvocationSourceForInput(candidateRecords, input)
    const sourceField = matched?.matchedField || getInputStateField(input)
    const producerHint = getInputProducerHint(input)
    if (matched) {
      return {
        inputName: input.name,
        label: input.description || input.name,
        targetField: input.name,
        sourceField,
        sourceFieldLabel: buildInputSourceFieldLabel(input),
        producerHint,
        sourceInvocationId: matched.record.invocation_id,
        sourceTargetId: matched.record.target_id,
        sourceStatus: matched.record.status,
        preview: matched.value.length > 120 ? `${matched.value.slice(0, 120)}...` : matched.value,
      }
    }

    return {
      inputName: input.name,
      label: input.description || input.name,
      targetField: input.name,
      sourceField,
      sourceFieldLabel: buildInputSourceFieldLabel(input),
      producerHint,
      sourceInvocationId: '',
      sourceTargetId: '',
      sourceStatus: '',
      preview: '未在当前调用链中找到可回填内容',
    }
  })
}

const buildDebugInputPlaceholder = (input: DebugAgentInputField | DebugAgentInputContractField): string => {
  const description = input.description ? `${input.description}，` : ''
  const sourceFieldLabel = buildInputSourceFieldLabel(input)
  if (sourceFieldLabel !== input.name) {
    return `填写 ${description}将注入 state.${input.name}，建议参考来源字段 ${sourceFieldLabel}`
  }
  return `填写 ${description}将写入 state.${input.name}`
}

const formatInputContractSource = (value?: DebugAgentInputContractField['source']): string => {
  const labels: Record<string, string> = {
    request: '请求参数',
    state: '工作流状态',
    context: '运行上下文'
  }
  return labels[value || 'request'] || (value || 'request')
}

const formatAgentMaturityLevel = (value?: DebugAgentInfo['maturity_level']): string => {
  const labels: Record<string, string> = {
    experimental: '实验中',
    internal: '内部可用',
    stable: '稳定'
  }
  return labels[value || 'stable'] || (value || 'stable')
}

const formatAgentInputMode = (value?: DebugAgentInfo['input_mode']): string => {
  const labels: Record<string, string> = {
    standalone: '独立输入',
    'upstream-dependent': '依赖上游',
    mixed: '混合输入'
  }
  return labels[value || 'standalone'] || (value || 'standalone')
}

const formatAgentDebugReplayMode = (value?: DebugAgentInfo['debug_replay_mode']): string => {
  const labels: Record<string, string> = {
    direct: '直接调试',
    requires_extra_state: '需补充状态',
    requires_chain_prefill: '建议链路回填'
  }
  return labels[value || 'direct'] || (value || 'direct')
}

const formatAgentMaintenanceStatus = (value?: DebugAgentInfo['maintenance_status']): string => {
  const labels: Record<string, string> = {
    maintained: '维护中',
    unmaintained: '停止维护'
  }
  return labels[value || 'maintained'] || (value || 'maintained')
}

const formatAgentCategory = (value?: DebugAgentInfo['category']): string => {
  const labels: Record<string, string> = {
    analyst: '分析师',
    researcher: '研究员',
    risk: '风险',
    manager: '管理',
    trader: '研究整合员',
    post_processor: '后处理'
  }
  return labels[value || 'analyst'] || (value || 'analyst')
}

const formatCallableSurface = (value: string): string => {
  const labels: Record<string, string> = {
    assistant: 'Assistant',
    workflow: 'Workflow',
    agent: 'Agent'
  }
  return labels[value] || value
}

const getAgentMaturityTagType = (value?: DebugAgentInfo['maturity_level']) => {
  if (value === 'experimental') return 'warning'
  if (value === 'internal') return 'info'
  return 'success'
}

const getAgentInputModeTagType = (value?: DebugAgentInfo['input_mode']) => {
  if (value === 'upstream-dependent') return 'warning'
  if (value === 'mixed') return 'info'
  return 'success'
}

const getAgentReplayModeTagType = (value?: DebugAgentInfo['debug_replay_mode']) => {
  if (value === 'requires_chain_prefill') return 'warning'
  if (value === 'requires_extra_state') return 'info'
  return 'success'
}

const getAgentMaintenanceTagType = (value?: DebugAgentInfo['maintenance_status']) => {
  if (value === 'unmaintained') return 'danger'
  return 'success'
}

const getAgentCategoryTagType = (value?: DebugAgentInfo['category']): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  if (value === 'researcher') return 'success'
  if (value === 'risk') return 'danger'
  if (value === 'manager') return 'warning'
  if (value === 'trader') return 'info'
  return 'primary'
}

const buildAgentGovernanceHint = (agent: DebugAgentInfo): string => {
  if (agent.maintenance_status === 'unmaintained') {
    return '该 Agent 属于 v1.0 遗留实现，当前已停止维护，仅保留兼容与历史调试能力。'
  }
  if (agent.debug_replay_mode === 'requires_chain_prefill') {
    return '该 Agent 更适合从调用记录中选择同一 root 链路后跳转回填，再进行单点调试。'
  }
  if (agent.debug_replay_mode === 'requires_extra_state') {
    return '该 Agent 支持单点调试，但需要先补齐依赖字段。'
  }
  if (agent.input_mode === 'mixed') {
    return '该 Agent 同时接受基础输入和部分上游输入，调试时请确认依赖字段是否完整。'
  }
  return '该 Agent 可直接独立调试，不依赖额外链路回填。'
}

const normalizeExtraState = () => {
  const normalized: Record<string, string> = {}
  selectedAgentDebugInputs.value.forEach(input => {
    normalized[input.name] = form.value.extra_state[input.name] || ''
  })
  form.value.extra_state = normalized
}

const buildPrefillStorageKey = (prefillId: string) => `${DEBUG_PREFILL_STORAGE_PREFIX}${prefillId}`

const savePrefillExtraState = (prefillId: string, extraState: Record<string, string>) => {
  if (!prefillId) return
  try {
    window.sessionStorage.setItem(buildPrefillStorageKey(prefillId), JSON.stringify(extraState))
  } catch (error) {
    console.warn('[模板调试] 保存预填充数据失败:', error)
  }
}

const loadPrefillExtraState = (prefillId?: string): Record<string, string> => {
  if (!prefillId) return {}
  try {
    const raw = window.sessionStorage.getItem(buildPrefillStorageKey(prefillId))
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).map(([key, value]) => [key, String(value ?? '')])
    )
  } catch (error) {
    console.warn('[模板调试] 读取预填充数据失败:', error)
    return {}
  }
}

const scrollToDebugTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const scrollToInvocationDetail = async () => {
  await nextTick()
  invocationDetailRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const selectedInvocationInputSources = computed(() => {
  const invocation = selectedInvocation.value
  const targetAgent = selectedInvocationTargetAgent.value
  const targetDebugInputs = getAgentDebugInputs(targetAgent)
  if (!invocation || !targetDebugInputs.length) {
    return []
  }
  const rootInvocationId = invocation.root_invocation_id || invocation.invocation_id
  const chainRecords = invocationChainCache.value[rootInvocationId] || []
  if (!chainRecords.length) {
    return []
  }
  return buildInputSourceRows(chainRecords, invocation, targetDebugInputs)
})

const currentRootInvocationId = computed(() => {
  if (!selectedInvocation.value) {
    return ''
  }
  return selectedInvocation.value.root_invocation_id || selectedInvocation.value.invocation_id || ''
})

const isCurrentInvocationChainLocked = computed(() => {
  return !!currentRootInvocationId.value && currentRootInvocationId.value === form.value.invocation_locked_root_id
})

const selectedInvocationJumpActionLabel = computed(() => {
  const agent = selectedInvocationTargetAgent.value
  if (!agent) {
    return '跳转并回填调试'
  }
  if (agent.debug_replay_mode === 'requires_chain_prefill') {
    return '跳转到单点调试并链路回填'
  }
  if (agent.debug_replay_mode === 'requires_extra_state') {
    return '跳转到单点调试并补充状态'
  }
  return '跳转到单点调试'
})

const selectedInvocationJumpActionHint = computed(() => {
  const agent = selectedInvocationTargetAgent.value
  if (!agent) {
    return ''
  }
  if (agent.debug_replay_mode === 'requires_chain_prefill') {
    return '该 Agent 标记为“建议链路回填”，此操作会带上当前 root 链中的可解析前置输入并切换到单点调试。'
  }
  if (agent.debug_replay_mode === 'requires_extra_state') {
    return '此操作会尽量补齐当前记录可解析的前置 state，然后切换到单点调试。'
  }
  return '此操作会保留当前上下文并切换到该 Agent 的单点调试界面。'
})

// 🆕 格式化 Agent 报告标签
const formatAgentReportLabel = (key: string | number): string => {
  const normalizedKey = String(key)
  const labels: Record<string, string> = {
    'market_report': '市场分析',
    'fundamentals_report': '基本面分析',
    'news_report': '新闻分析',
    'sentiment_report': '情绪分析',
    'index_report': '大盘分析',
    'sector_report': '板块分析',
    'risk_report': '风险分析',
    'trading_decision': '交易决策',
    'final_report': '最终报告'
  }
  return labels[normalizedKey] || normalizedKey
}

const formatInvocationSource = (record: TemplateDebugInvocationRecord): string => {
  const labels: Record<string, string> = {
    assistant: 'Assistant -> Agent',
    workflow: 'Workflow -> Agent',
    agent: 'Agent -> Agent'
  }
  return labels[record.source_type || ''] || record.source_collection || '-'
}

const getInvocationStatusTagType = (status?: string) => {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

const formatInvocationJson = (value: unknown): string => {
  if (!value) return '{}'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const handleInvocationRowClick = (row: TemplateDebugInvocationRecord) => {
  selectedInvocation.value = row
}

const clearInvocationChainLock = async () => {
  if (!form.value.invocation_locked_root_id) {
    return
  }
  form.value.invocation_locked_root_id = ''
  loading.value = true
  try {
    await loadInvocations(1)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '调用记录查询失败')
  } finally {
    loading.value = false
  }
}

const handleLockCurrentInvocationChain = async () => {
  const rootInvocationId = currentRootInvocationId.value
  if (!rootInvocationId) {
    ElMessage.warning('当前没有可锁定的调用链')
    return
  }
  if (form.value.invocation_locked_root_id === rootInvocationId) {
    ElMessage.info('当前链已经处于锁定状态')
    return
  }

  form.value.invocation_locked_root_id = rootInvocationId
  form.value.invocation_view_mode = 'chain'
  loading.value = true
  try {
    await loadInvocations(1, selectedInvocation.value?.invocation_id)
    ElMessage.success('已锁定当前 root 调用链')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '调用记录查询失败')
  } finally {
    loading.value = false
  }
}

const clearInvocationCompare = () => {
  compareAnchorInvocation.value = null
  compareSourceInvocation.value = null
}

const handleSelectSourceInvocation = async (sourceInvocationId?: string) => {
  if (!sourceInvocationId || !selectedInvocation.value) {
    return
  }
  const rootInvocationId = selectedInvocation.value.root_invocation_id || selectedInvocation.value.invocation_id
  await ensureInvocationChainLoaded(selectedInvocation.value)
  const chainRecords = invocationChainCache.value[rootInvocationId] || []
  const matchedInvocation = chainRecords.find(record => record.invocation_id === sourceInvocationId)
  if (!matchedInvocation) {
    ElMessage.warning('未在当前调用链中找到来源节点')
    return
  }
  selectedInvocation.value = matchedInvocation
  await scrollToInvocationDetail()
}

const handleCompareSourceInvocation = async (sourceInvocationId?: string) => {
  if (!sourceInvocationId || !selectedInvocation.value) {
    return
  }
  const rootInvocationId = selectedInvocation.value.root_invocation_id || selectedInvocation.value.invocation_id
  await ensureInvocationChainLoaded(selectedInvocation.value)
  const chainRecords = invocationChainCache.value[rootInvocationId] || []
  const matchedInvocation = chainRecords.find(record => record.invocation_id === sourceInvocationId)
  if (!matchedInvocation) {
    ElMessage.warning('未在当前调用链中找到来源节点')
    return
  }
  compareAnchorInvocation.value = selectedInvocation.value
  compareSourceInvocation.value = matchedInvocation
  await scrollToInvocationDetail()
}

const ensureInvocationChainLoaded = async (invocation?: TemplateDebugInvocationRecord | null) => {
  if (!invocation) {
    return
  }
  const rootInvocationId = invocation.root_invocation_id || invocation.invocation_id
  if (invocationChainCache.value[rootInvocationId]?.length) {
    return
  }

  const res = await TemplatesDebugApi.listInvocations({
    root_invocation_id: rootInvocationId,
    page: 1,
    page_size: 100
  })

  if (res.success) {
    invocationChainCache.value = {
      ...invocationChainCache.value,
      [rootInvocationId]: res.data.items,
    }
  }
}

const handleJumpToDebugFromInvocation = async () => {
  const invocation = selectedInvocation.value
  if (!invocation?.target_id) {
    ElMessage.error('当前记录缺少目标 Agent，无法回填')
    return
  }

  const targetAgent = availableAgents.value.find(agent => agent.id === invocation.target_id)
  if (!targetAgent) {
    ElMessage.error(`未找到目标 Agent：${invocation.target_id}`)
    return
  }

  loading.value = true
  try {
    const rootInvocationId = invocation.root_invocation_id || invocation.invocation_id
    await ensureInvocationChainLoaded(invocation)
    const chainRecords = invocationChainCache.value[rootInvocationId] || []

    if (!chainRecords.length) {
      ElMessage.error('获取调用链失败')
      return
    }

    form.value.analyst_type = targetAgent.id
    form.value.workflow_id = invocation.workflow_id || form.value.workflow_id || ''
    form.value.stock.symbol = invocation.symbol || form.value.stock.symbol || ''

    const requestPayload = invocation.request?.payload
    const requestAnalysisDate = requestPayload && typeof requestPayload.analysis_date === 'string'
      ? requestPayload.analysis_date
      : requestPayload && typeof requestPayload.trade_date === 'string'
        ? requestPayload.trade_date
        : ''
    form.value.stock.analysis_date = requestAnalysisDate || form.value.stock.analysis_date || ''

    normalizeExtraState()
    const targetDebugInputs = getAgentDebugInputs(targetAgent)
    const autoFilledState = buildExtraStateFromChain(chainRecords, invocation, targetDebugInputs)
    form.value.extra_state = {
      ...form.value.extra_state,
      ...autoFilledState
    }

    const prefillId = invocation.invocation_id
    savePrefillExtraState(prefillId, form.value.extra_state)

    await router.push({
      name: 'TemplateDebug',
      query: {
        ...route.query,
        mode: 'agent',
        analyst_type: targetAgent.id,
        symbol: form.value.stock.symbol || undefined,
        analysis_date: form.value.stock.analysis_date || undefined,
        workflow_id: form.value.workflow_id || undefined,
        prefill_invocation_id: prefillId,
      }
    })

    debugMode.value = 'agent'
    scrollToDebugTop()

    const missingInputs = targetDebugInputs.filter(input => !String(form.value.extra_state[input.name] || '').trim())
    if (missingInputs.length > 0) {
      ElMessage.warning(`已切换到单点调试并回填部分前置输入，仍缺少：${missingInputs.map(item => item.description || item.name).join('、')}`)
    } else {
      if (targetAgent.debug_replay_mode === 'requires_chain_prefill') {
        ElMessage.success('已切换到单点调试，并完成链路回填')
      } else if (targetAgent.debug_replay_mode === 'requires_extra_state') {
        ElMessage.success('已切换到单点调试，并补齐可解析状态')
      } else {
        ElMessage.success('已切换到单点调试')
      }
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '自动回填失败')
  } finally {
    loading.value = false
  }
}

const loadInvocations = async (page = 1, preferredInvocationId?: string) => {
  const res = await TemplatesDebugApi.listInvocations({
    source_type: (form.value.invocation_source_type || undefined) as 'assistant' | 'workflow' | 'agent' | undefined,
    target_id: form.value.invocation_target_id || undefined,
    root_invocation_id: form.value.invocation_locked_root_id || undefined,
    workflow_id: form.value.invocation_workflow_id || undefined,
    thread_id: form.value.invocation_thread_id || undefined,
    symbol: form.value.invocation_symbol || undefined,
    status: form.value.invocation_status || undefined,
    group_by_root: form.value.invocation_view_mode === 'chain',
    page,
    page_size: 20
  })

  if (res.success) {
    invocationResult.value = res.data
    const flatItems = res.data.items.length > 0
      ? res.data.items
      : (res.data.chains || []).flatMap(chain => chain.items || [])
    selectedInvocation.value = flatItems.find(item => item.invocation_id === preferredInvocationId)
      || flatItems[0]
      || null
  } else {
    ElMessage.error(res.message || '调用记录查询失败')
  }
}

const handleInvocationViewModeChange = async () => {
  loading.value = true
  try {
    await loadInvocations(1)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '调用记录查询失败')
  } finally {
    loading.value = false
  }
}

const handleInvocationPageChange = async (page: number) => {
  loading.value = true
  try {
    await loadInvocations(page)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '调用记录查询失败')
  } finally {
    loading.value = false
  }
}

// 🆕 加载可用的工作流
const loadAvailableWorkflows = async () => {
  try {
    const res = await TemplatesDebugApi.listDebugWorkflows()
    if (res.success && res.data) {
      availableWorkflows.value = res.data
      // 默认选择第一个工作流
      if (!form.value.workflow_id && availableWorkflows.value.length > 0) {
        form.value.workflow_id = availableWorkflows.value[0].id
      }
    }
  } catch (error) {
    console.error('加载工作流失败:', error)
  }
}

// 按版本和类别组合分组的 agents
const groupedAgents = computed(() => {
  const versionLabels: Record<string, string> = {
    v1: 'v1.0 (停止维护)',
    v2: 'v2.0 (新版)'
  }
  const categoryOrder = ['analyst', 'researcher', 'risk', 'manager', 'trader', 'post_processor']
  const grouped = new Map<string, { key: string; label: string; versionOrder: number; categoryOrder: number; agents: DebugAgentInfo[] }>()

  visibleAgents.value.forEach(agent => {
    const v = agent.version || ''
    const versionKey = (v === 'v1.0' || v === '1.0' || v === '1.0.0') ? 'v1' : 'v2'
    const categoryKey = agent.category || 'analyst'
    const groupKey = `${versionKey}:${categoryKey}`
    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, {
        key: groupKey,
        label: `${versionLabels[versionKey]} / ${formatAgentCategory(categoryKey)}`,
        versionOrder: versionKey === 'v1' ? 0 : 1,
        categoryOrder: categoryOrder.indexOf(categoryKey),
        agents: []
      })
    }
    grouped.get(groupKey)?.agents.push(agent)
  })

  return Array.from(grouped.values())
    .filter(group => group.agents.length > 0)
    .sort((left, right) => {
      if (left.versionOrder !== right.versionOrder) {
        return left.versionOrder - right.versionOrder
      }
      return left.categoryOrder - right.categoryOrder
    })
})

// 加载可用的agents
const loadAvailableAgents = async (targetAgentType?: string) => {
  try {
    const res = await TemplatesDebugApi.listDebugAgents()
    if (res.success && res.data) {
      availableAgents.value = res.data

      // 如果指定了目标agent类型，尝试设置它
      if (targetAgentType) {
        const targetAgent = availableAgents.value.find(a => a.id === targetAgentType)
        if (targetAgent) {
          if (isUnmaintainedAgent(targetAgent)) {
            showUnmaintainedAgents.value = true
          }
          form.value.analyst_type = targetAgentType
          return
        }
      }

      // 如果当前选择的agent不在列表中，选择第一个
      if (!visibleAgents.value.find(a => a.id === form.value.analyst_type)) {
        if (visibleAgents.value.length > 0) {
          form.value.analyst_type = visibleAgents.value[0].id
        } else if (availableAgents.value.length > 0) {
          showUnmaintainedAgents.value = true
          form.value.analyst_type = availableAgents.value[0].id
        }
      }
    }
  } catch (error) {
    console.error('加载agents失败:', error)
    ElMessage.error('加载分析师列表失败')
  }
}

// 判断是否需要股票代码输入
const needsStockSymbol = computed(() => {
  if (debugMode.value === 'invocations') {
    return false
  }
  // 工作流模式通常需要股票代码
  if (debugMode.value === 'workflow') {
    return true
  }
  // 单个 Agent 模式：只有大盘分析师不需要具体的股票代码
  // 板块分析师需要股票代码来分析该股票所属的行业/板块
  return form.value.analyst_type !== 'index_analyst'
})

const clearWorkflowDebugPolling = () => {
  if (workflowDebugPollingTimer.value) {
    clearInterval(workflowDebugPollingTimer.value)
    workflowDebugPollingTimer.value = null
  }
}

const buildWorkflowDebugResult = (rawResult: any, fallback: any = {}) => {
  const resultData = rawResult || {}
  const reportFields = [
    'final_report',
    'market_report',
    'fundamentals_report',
    'news_report',
    'sentiment_report',
    'index_report',
    'sector_report',
    'risk_report',
    'risk_assessment',
    'trading_decision',
    'final_trade_decision',
    'recommendation',
    'summary'
  ]
  const agentReports: Record<string, string> = {}

  for (const field of reportFields) {
    const value = resultData[field]
    if (typeof value === 'string' && value.trim()) {
      agentReports[field] = value
    } else if (value && typeof value === 'object') {
      const text = value.content || value.markdown || value.text || value.report || value.summary || value.reasoning
      if (typeof text === 'string' && text.trim()) {
        agentReports[field] = text
      }
    }
  }

  const finalReport = agentReports.final_report || agentReports.recommendation || agentReports.summary || Object.entries(agentReports)
    .filter(([, value]) => value)
    .map(([key, value]) => `## ${formatAgentReportLabel(key)}\n${value}`)
    .join('\n\n---\n\n')

  return {
    workflow_id: fallback.workflow_id || form.value.workflow_id,
    workflow_name: fallback.workflow_name || availableWorkflows.value.find(w => w.id === form.value.workflow_id)?.name || form.value.workflow_id,
    symbol: fallback.symbol || form.value.stock.symbol,
    analysis_date: fallback.analysis_date || form.value.stock.analysis_date,
    report: finalReport,
    agent_reports: agentReports,
    report_length: finalReport.length
  }
}

const startWorkflowDebugPolling = (taskId: string, fallback: any = {}) => {
  clearWorkflowDebugPolling()
  workflowDebugTaskId.value = taskId
  workflowDebugProgress.value = 0
  workflowDebugMessage.value = fallback.message || '工作流调试任务已提交'

  workflowDebugPollingTimer.value = setInterval(async () => {
    try {
      const response = await analysisApi.getTaskStatus(taskId)
      const status = response.data || response
      workflowDebugProgress.value = Number(status.progress || 0)
      workflowDebugMessage.value = status.current_step_description || status.message || workflowDebugMessage.value

      if (status.status === 'completed') {
        clearWorkflowDebugPolling()
        const rawResult = await fetchTaskResultWithRetry(taskId, { seedData: status.result_data })
        workflowResult.value = buildWorkflowDebugResult(rawResult, fallback)
        activeReportTab.value = 'summary'
        loading.value = false
        ElMessage.success('工作流调试完成')
      } else if (status.status === 'failed' || status.status === 'cancelled') {
        clearWorkflowDebugPolling()
        loading.value = false
        ElMessage.error(status.error_message || status.message || '工作流调试失败')
      }
    } catch (error: any) {
      console.error('轮询工作流调试状态失败:', error)
    }
  }, 2000)
}

const runDebug = async () => {
  loading.value = true
  // 清空之前的结果
  clearWorkflowDebugPolling()
  result.value = null
  workflowResult.value = null
  workflowDebugTaskId.value = null
  workflowDebugProgress.value = 0
  workflowDebugMessage.value = ''
  invocationResult.value = null
  selectedInvocation.value = null

  try {
    if (debugMode.value === 'invocations') {
      await loadInvocations(1)
      return
    }

    const symbol = String(form.value.stock.symbol || '').trim()

    // 只有需要股票代码的分析师才验证股票代码
    if (needsStockSymbol.value && !symbol) {
      ElMessage.error('请填写股票代码')
      loading.value = false
      return
    }

    // 🆕 工作流调试模式
    if (debugMode.value === 'workflow') {
      if (!form.value.workflow_id) {
        ElMessage.error('请选择要调试的工作流')
        loading.value = false
        return
      }

      const res = await TemplatesDebugApi.debugWorkflow({
        workflow_id: form.value.workflow_id,
        llm: form.value.llm,
        stock: { ...form.value.stock, symbol }
      })

      if (res.success && res.data?.task_id) {
        startWorkflowDebugPolling(res.data.task_id, res.data)
        ElMessage.success('工作流调试任务已提交，正在后台执行')
      } else if (res.success && res.data?.report) {
        workflowResult.value = buildWorkflowDebugResult(res.data, res.data)
        activeReportTab.value = 'summary'
        loading.value = false
        ElMessage.success('工作流调试完成')
      } else {
        loading.value = false
        ElMessage.error(res.message || '工作流调试失败')
      }
      return
    }

    // 单个 Agent 调试模式
    const agentVersion = selectedAgent.value?.version
    const extraState = Object.fromEntries(
      Object.entries(form.value.extra_state).filter(([, value]) => String(value || '').trim())
    )

    const missingDebugInputs = selectedAgentDebugInputs.value.filter(input => !String(form.value.extra_state[input.name] || '').trim())
    if (missingDebugInputs.length > 0) {
      ElMessage.error(`请先填写前置输入：${missingDebugInputs.map(item => item.description || item.name).join('、')}`)
      return
    }

    const res = await TemplatesDebugApi.debugAnalyst({
      analyst_type: form.value.analyst_type as any,
      agent_version: agentVersion,
      template_id: form.value.use_current ? undefined : form.value.template_id,
      use_current: form.value.use_current,
      workflow_id: form.value.workflow_id || undefined,  // 🆕 传递 workflow_id 用于流程专属提示词
      llm: form.value.llm,
      stock: { ...form.value.stock, symbol },
      extra_state: extraState
    })
    if (res.success) {
      result.value = res.data
    } else {
      ElMessage.error(res.message || '调试失败')
    }
  } catch (e: any) {
    // 处理权限错误
    if (e?.response?.status === 403) {
      const detail = e?.response?.data?.detail
      if (detail?.code === 'ADVANCED_REQUIRED') {
        ElMessageBox.confirm(
          '提示词调试功能为高级学员专属，请前往授权管理完成认证后使用。',
          '权限不足',
          {
            confirmButtonText: '前往授权管理',
            cancelButtonText: '返回',
            type: 'warning'
          }
        ).then(() => {
          router.push('/settings/license')
        }).catch(() => {
          // 用户点击取消，返回上一页
          router.back()
        })
        return
      }
    }
    ElMessage.error(e?.response?.data?.detail || e?.message || '调试失败')
  } finally {
    if (!workflowDebugPollingTimer.value) {
      loading.value = false
    }
  }
}

onUnmounted(() => {
  clearWorkflowDebugPolling()
})

onMounted(async () => {
  try {
    // 先解析URL参数
    const q = route.query || {}

    console.log('🔍 [模板调试] URL参数:', q)

    // 🆕 并行加载 agents 和 workflows
    const targetAgentType = typeof q.analyst_type === 'string' ? q.analyst_type : undefined
    await Promise.all([
      loadAvailableAgents(targetAgentType),
      loadAvailableWorkflows()
    ])

    // 应用其他URL参数
    if (q.mode === 'workflow' || q.mode === 'invocations' || q.mode === 'agent') {
      debugMode.value = q.mode
    }
    if (typeof q.template_id === 'string' && q.template_id) {
      form.value.use_current = false
      form.value.template_id = q.template_id as string
    }
    if (typeof q.symbol === 'string') form.value.stock.symbol = q.symbol as string
    if (typeof q.analysis_date === 'string' && q.analysis_date) form.value.stock.analysis_date = q.analysis_date as string
    if (typeof q.workflow_id === 'string' && q.workflow_id) form.value.workflow_id = q.workflow_id as string

    // 🔥 处理agent_type参数，用于区分v1.0和v2.0
    if (typeof q.agent_type === 'string' && q.agent_type) {
      const agentType = q.agent_type as string
      console.log('🔍 [模板调试] 检测到agent_type参数:', agentType)

      // 判断是否为v2.0版本
      const isV2 = agentType.endsWith('_v2')
      const targetVersion = isV2 ? 'v2.0' : 'v1.0'

      console.log('🔍 [模板调试] 目标版本:', targetVersion, '目标分析师类型:', targetAgentType)

      if (targetAgentType) {
        // 查找对应版本的分析师
        const targetAgent = availableAgents.value.find(agent => {
          const v = agent.version || ''
          const isAgentV2 = v === 'v2.0' || v === '2.0' || v.startsWith('2.')
          const isAgentV1 = v === 'v1.0' || v === '1.0' || v === '1.0.0'
          
          if (isV2 && !isAgentV2) return false
          if (!isV2 && !isAgentV1) return false

          if (isV2) {
            // v2.0版本：检查agent.id是否包含targetAgentType
            return agent.id.includes(targetAgentType)
          } else {
            // v1.0版本：直接匹配agent.id
            return agent.id === targetAgentType
          }
        })

        if (targetAgent) {
          if (isUnmaintainedAgent(targetAgent)) {
            showUnmaintainedAgents.value = true
          }
          form.value.analyst_type = targetAgent.id
          console.log('🔍 [模板调试] 自动选择分析师:', targetAgent.id, '版本:', targetVersion)
        } else {
          console.warn('🔍 [模板调试] 未找到匹配的分析师:', { agentType, targetAgentType, targetVersion })
        }
      }
    }

    if (!form.value.stock.analysis_date) {
      // 默认使用今天的日期，后端会自动查找最近的有效交易日
      const d = new Date()
      const yyyy = d.getFullYear()
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      form.value.stock.analysis_date = `${yyyy}-${mm}-${dd}`
    }

    if (typeof q.prefill_invocation_id === 'string' && q.prefill_invocation_id) {
      const savedExtraState = loadPrefillExtraState(q.prefill_invocation_id as string)
      if (Object.keys(savedExtraState).length > 0) {
        form.value.extra_state = {
          ...form.value.extra_state,
          ...savedExtraState
        }
        normalizeExtraState()
      }
    }

    try {
      const defaults = await configApi.getDefaultModels()
      console.log('🔍 [模板调试] 获取到的默认模型配置:', defaults)
      // 模板调试使用快速分析模型，因为是单个agent的快速测试
      form.value.llm.model = defaults.quick_analysis_model || form.value.llm.model
      console.log('🔍 [模板调试] 设置的模型名称:', form.value.llm.model)
    } catch (e) {
      console.error('❌ [模板调试] 获取默认模型失败:', e)
      // ignore, 保持默认值
    }

    try {
      const llmConfigs = await configApi.getLLMConfigs()
      availableModels.value = (llmConfigs as any[]).filter((c: any) => c.enabled)
      console.log('🔍 [模板调试] 可用模型列表:', availableModels.value.map(m => m.model_name))

      // 如果模型名称为空，使用第一个可用模型
      if (!form.value.llm.model && availableModels.value.length > 0) {
        form.value.llm.model = availableModels.value[0].model_name
        console.log('🔍 [模板调试] 模型名称为空，使用第一个可用模型:', form.value.llm.model)
      }

      const info = availableModels.value.find((m: any) => m.model_name === form.value.llm.model)
      if (info) {
        form.value.llm.provider = info.provider
        console.log('🔍 [模板调试] 找到模型信息:', { model: form.value.llm.model, provider: info.provider })
      } else {
        console.warn('⚠️ [模板调试] 未找到模型信息:', form.value.llm.model)
      }
    } catch (e) {
      console.error('❌ [模板调试] 获取LLM配置失败:', e)
      availableModels.value = []
    }
  } catch (error) {
    console.debug('[模板调试] 初始化可用模型失败，保留默认 provider:', error)
  }
})

watch(() => form.value.llm.model, (newModel) => {
  const info = availableModels.value.find((m: any) => m.model_name === newModel)
  form.value.llm.provider = info?.provider || 'custom_openai'
})

watch(() => form.value.analyst_type, () => {
  if (isUnmaintainedAgent(selectedAgent.value)) {
    showUnmaintainedAgents.value = true
  }
  normalizeExtraState()
})

watch(showUnmaintainedAgents, (visible) => {
  if (visible) {
    return
  }
  if (!isUnmaintainedAgent(selectedAgent.value)) {
    return
  }
  const nextMaintainedAgent = visibleAgents.value[0]
  if (nextMaintainedAgent) {
    form.value.analyst_type = nextMaintainedAgent.id
  }
})

watch(selectedInvocation, async (invocation) => {
  try {
    await ensureInvocationChainLoaded(invocation)
  } catch (error) {
    console.error('[模板调试] 加载调用链失败:', error)
  }
})

watch(() => route.query, (query) => {
  const nextMode = query.mode
  if (nextMode === 'agent' || nextMode === 'workflow' || nextMode === 'invocations') {
    debugMode.value = nextMode
  }
  if (typeof query.analyst_type === 'string' && query.analyst_type) {
    form.value.analyst_type = query.analyst_type
    if (isUnmaintainedAgent(availableAgents.value.find(agent => agent.id === query.analyst_type))) {
      showUnmaintainedAgents.value = true
    }
  }
  if (typeof query.symbol === 'string') {
    form.value.stock.symbol = query.symbol
  }
  if (typeof query.analysis_date === 'string') {
    form.value.stock.analysis_date = query.analysis_date
  }
  if (typeof query.workflow_id === 'string') {
    form.value.workflow_id = query.workflow_id
  }
  if (typeof query.prefill_invocation_id === 'string' && query.prefill_invocation_id) {
    const savedExtraState = loadPrefillExtraState(query.prefill_invocation_id)
    if (Object.keys(savedExtraState).length > 0) {
      form.value.extra_state = {
        ...form.value.extra_state,
        ...savedExtraState
      }
      normalizeExtraState()
    }
  }
}, { deep: true })

watch(debugMode, () => {
  result.value = null
  workflowResult.value = null
  invocationResult.value = null
  selectedInvocation.value = null
  clearInvocationCompare()
})

watch(selectedInvocation, () => {
  clearInvocationCompare()
})

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.ta-debug { padding: 16px }
.ta-toolbar { margin: 4px 0 8px 0 }
.ta-result { margin-top: 12px }
.ta-pre { white-space: pre-wrap; background: var(--el-fill-color); color: var(--el-text-color-primary); padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px }
.ta-meta { color: var(--el-text-color-secondary); margin-bottom: 6px }
.debug-task-tip { margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px }

.invocation-detail {
  margin-top: 16px;
}

.agent-governance-card {
  width: 100%;
  max-width: 760px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.agent-governance-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-governance-surfaces {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.agent-governance-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.agent-governance-hint {
  margin-top: 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.agent-select-block {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.agent-option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.agent-option-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.agent-option-name {
  color: var(--el-text-color-primary);
}

.agent-option-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.agent-option-version {
  color: #8492a6;
  font-size: 12px;
  flex-shrink: 0;
}

.debug-contract-field {
  width: 100%;
}

.debug-contract-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.invocation-governance-card {
  margin-top: 16px;
}

.invocation-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}

.invocation-action-alert {
  margin-bottom: 12px;
}

.invocation-lock-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.invocation-lock-root {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.invocation-input-sources {
  margin-top: 16px;
}

.invocation-source-meta {
  display: inline-block;
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.invocation-input-label-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.invocation-input-label-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.invocation-source-missing {
  color: var(--el-text-color-secondary);
}

.invocation-view-switch {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.invocation-chain-list {
  margin-top: 8px;
}

.invocation-chain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding-right: 12px;
}

.invocation-chain-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.invocation-chain-root {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.invocation-chain-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.invocation-chain-statuses {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.invocation-chain-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  margin-bottom: 10px;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.invocation-chain-item:hover,
.invocation-chain-item.is-selected {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.invocation-chain-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.invocation-chain-item-title {
  font-weight: 600;
  margin-right: 8px;
}

.invocation-chain-item-agent {
  color: var(--el-text-color-secondary);
}

.invocation-agent-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.invocation-agent-name {
  color: var(--el-text-color-primary);
}

.invocation-agent-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.invocation-agent-tags-inline {
  margin-top: 6px;
}

.invocation-chain-item-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 8px;
}

.invocation-chain-item-summary {
  margin-top: 8px;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

.invocation-json-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.invocation-compare-panel {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.invocation-compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.invocation-compare-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.invocation-compare-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.compare-inner-grid {
  margin-top: 0;
}

.invocation-json-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.meta-info {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 12px;
}

@media (max-width: 960px) {
  .invocation-json-grid {
    grid-template-columns: 1fr;
  }

  .invocation-compare-grid {
    grid-template-columns: 1fr;
  }
}

/* Markdown 样式 */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

:deep(.markdown-body h1) {
  font-size: 28px;
  font-weight: 600;
  margin: 24px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}

:deep(.markdown-body h2) {
  font-size: 24px;
  font-weight: 600;
  margin: 20px 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

:deep(.markdown-body h3) {
  font-size: 20px;
  font-weight: 600;
  margin: 16px 0 8px 0;
}

:deep(.markdown-body h4) {
  font-size: 16px;
  font-weight: 600;
  margin: 12px 0 6px 0;
}

:deep(.markdown-body p) {
  margin: 8px 0;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin: 8px 0;
  padding-left: 24px;
}

:deep(.markdown-body li) {
  margin: 4px 0;
}

:deep(.markdown-body table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

:deep(.markdown-body table th),
:deep(.markdown-body table td) {
  border: 1px solid var(--el-border-color-light);
  padding: 8px 12px;
  text-align: left;
}

:deep(.markdown-body table th) {
  background-color: var(--el-fill-color);
  font-weight: 600;
}

:deep(.markdown-body code) {
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

:deep(.markdown-body pre) {
  background-color: var(--el-fill-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 12px 0;
}

:deep(.markdown-body pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
}

:deep(.markdown-body blockquote) {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--el-text-color-secondary);
}

:deep(.markdown-body strong) {
  font-weight: 600;
}

:deep(.markdown-body em) {
  font-style: italic;
}

:deep(.markdown-body a) {
  color: var(--el-color-primary);
  text-decoration: none;
}

:deep(.markdown-body a:hover) {
  text-decoration: underline;
}

:deep(.markdown-body hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-light);
  margin: 16px 0;
}
</style>