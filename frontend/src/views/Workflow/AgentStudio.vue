<template>
  <div class="agent-studio-page">
    <header class="topbar">
      <div class="topbar-left">
        <div class="brand-mark">A</div>
        <div class="brand-text">
          <div class="brand-title">Agent 工坊 · 助手模式</div>
          <div class="brand-subtitle">通过对话创建、测试并发布可用于工作流的 Agent</div>
        </div>
      </div>
      <div class="topbar-actions">
        <el-button class="btn btn-ghost" plain :class="{ active: showLeftSidebar }" @click="showLeftSidebar = !showLeftSidebar">Agent 列表</el-button>
        <el-button class="btn btn-ghost" plain :class="{ active: showStatusSidebar }" @click="showStatusSidebar = !showStatusSidebar">查看状态</el-button>
        <el-button class="btn btn-ghost" plain @click="router.push('/workflow')">返回分析流</el-button>
        <el-button class="btn btn-primary" type="primary" @click="resetStudio">新建 Agent</el-button>
      </div>
    </header>

    <div class="main" :style="mainGridStyle">
      <aside v-if="showLeftSidebar" class="sidebar">
        <div class="panel-head">
          <div class="panel-title-row">
            <span class="panel-title">我的 Agent</span>
            <div class="panel-title-actions">
              <span class="count-pill">{{ filteredAgentItems.length }} 个</span>
              <el-button size="small" text type="primary" @click="router.push('/workflow/agent-workshop/manage')">管理</el-button>
            </div>
          </div>
          <el-input
            v-model="agentSearchText"
            class="search-box"
            placeholder="搜索 Agent"
            clearable
            size="default"
          />
          <div class="filter-row">
            <button
              v-for="option in agentStatusFilterOptions"
              :key="option.value"
              type="button"
              :class="['filter-chip', { active: selectedAgentStatusFilter === option.value }]"
              @click="selectedAgentStatusFilter = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
        <div class="agent-list">
          <div
            v-for="item in filteredAgentItems"
            :key="item.spec_id"
            :class="['agent-card', { active: activeTreeKey.startsWith('spec:' + item.spec_id) || (latestVersion?.spec_id === item.spec_id) }]"
            @click="openAgentItem(item)"
          >
            <div class="agent-card-top">
              <div class="agent-name">{{ item.name || '未命名 Agent' }}</div>
              <el-tag size="small" effect="plain" :type="getSpecTagType(item)" class="status-tag">
                {{ getSpecStatusLabel(item) }}
              </el-tag>
            </div>
            <div class="agent-desc">{{ item.primary_goal || '等待补充目标描述' }}</div>
            <div class="agent-meta">
              <span>{{ (versionItemsBySpec[item.spec_id] || []).length ? `v${Math.max(...(versionItemsBySpec[item.spec_id] || []).map(v => v.version))}` : '暂无版本' }}</span>
              <span>{{ getSpecMetaText(item) }}</span>
            </div>
          </div>
        </div>
      </aside>

      <main class="content">
        <div class="chat-head">
          <div>
            <div class="chat-title" @dblclick="startRenameSpec" :title="displaySpec?.spec_id ? '双击可重命名' : ''">
              <template v-if="renamingSpecId && renamingSpecId === displaySpec?.spec_id">
                <el-input
                  ref="renameInputRef"
                  v-model="renameSpecName"
                  size="small"
                  class="rename-inline-input"
                  @blur="confirmRenameSpec"
                  @keydown.enter="confirmRenameSpec"
                  @keydown.escape="cancelRenameSpec"
                />
              </template>
              <template v-else>
                {{ displaySpec?.name || '新建 Agent' }}
              </template>
            </div>
            <div class="chat-subtitle">{{ focusSubtitle }}</div>
          </div>
          <div class="chat-head-actions">
            <el-button v-if="!showLeftSidebar" class="btn btn-ghost mobile-panel-btn" plain @click="showLeftSidebar = true">
              显示列表
            </el-button>
            <el-button v-if="!showStatusSidebar" class="btn btn-ghost mobile-panel-btn" plain @click="showStatusSidebar = true">
              显示状态
            </el-button>
            <el-tag size="small" effect="plain" :type="draftStatusTagType" class="status-tag">
              {{ latestVersion ? `v${latestVersion.version}` : '' }} {{ draftStatusText }}
            </el-tag>
          </div>
        </div>

        <div v-if="!displayedMessages.length" class="empty-preview">
          <div class="empty-preview-title">你想创建什么样的 Agent？</div>
          <div class="empty-preview-desc">
            描述你的目标后，助手会帮你设计职责、选择工具、生成测试版本并在发布前检查是否能接入工作流。
          </div>
          <div class="example-grid">
            <div
              v-for="example in exampleQuestions"
              :key="example"
              class="example-card"
              @click="composerText = example"
            >
              <strong>{{ example.split('，')[0] }}</strong>
              <span>{{ example.split('，').slice(1).join('，') }}</span>
            </div>
          </div>
        </div>

        <div ref="messagesContainer" class="messages">
          <div v-if="!displayedMessages.length" class="empty-spacer" />
          <div v-else class="messages-list">
            <div
              v-for="(message, index) in displayedMessages"
              :key="index"
              :class="['message-row', message.role === 'user' ? 'user' : 'assistant', (nanobotStreaming && index === displayedMessages.length - 1 && message.role === 'assistant') ? 'streaming-message' : '']"
            >
              <template v-if="message.role === 'user'">
                <div class="avatar user-avatar">你</div>
                <div class="bubble">
                  <div class="message-text markdown-content" v-html="renderMarkdown(message.content)"></div>
                </div>
              </template>
              <template v-else>
                <div class="avatar assistant-avatar">助</div>
                <div class="bubble">
                  <div v-if="message.progressSteps?.length" class="progress-timeline">
                    <div
                      v-for="(step, stepIdx) in message.progressSteps"
                      :key="stepIdx"
                      :class="['progress-item', step.tone, (nanobotStreaming && index === displayedMessages.length - 1 && stepIdx === message.progressSteps.length - 1) ? 'current' : '']"
                    >
                      <span class="step-no">{{ stepIdx + 1 }}</span>
                      <div class="step-copy">
                        <strong>{{ step.text }}</strong>
                        <span v-if="step.meta">{{ step.meta }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="message-text markdown-content" v-html="renderMarkdown(message.content || (nanobotStreaming && index === displayedMessages.length - 1 ? loadingHint : ''))"></div>
                </div>
              </template>
            </div>

            <div v-if="latestVersion" class="quick-actions">
              <div class="quick-actions-hint">测试运行完成，可以查看详细结果：</div>
              <div class="quick-actions-row">
                <el-button class="quick-action" type="primary" size="small" @click="openLatestVersionDetail">
                  查看测试结果
                </el-button>
                <el-button class="quick-action" plain size="small" @click="openLatestVersionDetail">
                  检查发布配置
                </el-button>
                <el-button class="quick-action" type="primary" plain size="small" :disabled="!canPublishLatestVersion" @click="openLatestPublishConfirm">
                  发布版本
                </el-button>
                <el-button class="quick-action" plain size="small" @click="composerText = '我想继续优化这个 Agent 的职责和输出效果。'">
                  继续优化职责
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-shell">
            <el-input
              v-model="composerText"
              class="chat-input"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              placeholder="继续描述你的需求，或直接说：发布版本、重新测试、修改报告展示名称..."
              :disabled="nanobotStreaming"
            />
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!composerText.trim() || nanobotStreaming"
              @click="handleSendMessage"
            >
              发送
            </el-button>
          </div>
          <div class="input-tip">
            <template v-if="nanobotStreaming">
              <el-button link type="danger" size="small" @click="cancelNanobotStreaming">停止本轮生成</el-button>
            </template>
            <template v-else>
              建议：用自然语言描述目标即可，具体字段和工具由助手生成并在发布前确认。
            </template>
          </div>
        </div>
      </main>

      <aside v-if="showStatusSidebar" class="inspector">
        <div class="inspector-scroll">
          <section class="status-card">
            <div class="status-eyebrow">{{ latestVersion ? `当前版本 v${latestVersion.version}` : '当前 Agent' }}</div>
            <div class="status-title">{{ rightPanelStatusTitle }}</div>
            <div class="status-desc">{{ rightPanelStatusDescription }}</div>
            <div v-if="latestVersion" class="score-row">
              <div class="score-value">{{ overallScoreText }}</div>
              <div class="score-copy">
                <strong>{{ rightPanelScoreTitle }}</strong>
                <span>{{ rightPanelScoreDescription }}</span>
              </div>
            </div>
            <div class="status-actions">
              <el-button type="primary" :disabled="!canPublishLatestVersion" @click="openLatestPublishConfirm">
                发布
              </el-button>
              <el-button :disabled="!latestVersion" @click="openLatestVersionDetail">
                详情
              </el-button>
            </div>
          </section>

          <section v-if="hasGapDeadLetters" class="right-section dead-letter-section">
            <div class="section-title section-title-with-action">
              <span>补齐异常</span>
              <el-tag size="small" type="danger" effect="plain">{{ activeGapDeadLetters.length }}</el-tag>
            </div>
            <div v-loading="loadingGapDeadLetters" class="plain-card dead-letter-card">
              <div class="dead-letter-alert">
                <strong>自动补齐 Skill 有失败项</strong>
                <span>{{ gapDeadLetterSummaryText }}</span>
                <span v-if="latestGapDeadLetter?.reason_message" class="dead-letter-message">{{ latestGapDeadLetter.reason_message }}</span>
              </div>
              <div v-if="activeGapDeadLetterGroups.length" class="dead-letter-groups">
                <div v-for="group in activeGapDeadLetterGroups.slice(0, 3)" :key="group.reason_code" class="dead-letter-group">
                  <div>
                    <strong>{{ group.reason_code }}</strong>
                    <span>{{ group.count }} 项 / {{ group.job_count }} 个任务</span>
                  </div>
                  <el-button link type="primary" size="small" :loading="recoveringGapDeadLetters" @click="recoverGapDeadLettersByReason(group)">
                    恢复同类
                  </el-button>
                </div>
              </div>
              <div class="dead-letter-items">
                <div v-for="item in activeGapDeadLetters.slice(0, 3)" :key="`${item.job_id}-${item.gap_id}`" class="dead-letter-item">
                  <div class="dead-letter-item-main">
                    <strong>{{ item.description || item.gap_id }}</strong>
                    <span>{{ item.reason_code }} · {{ item.failed_at || item.updated_at }}</span>
                  </div>
                  <el-button link type="primary" size="small" :loading="recoveringGapDeadLetters" @click="recoverSingleGapDeadLetter(item)">
                    重试
                  </el-button>
                </div>
              </div>
              <div class="dead-letter-actions">
                <el-button size="small" :loading="loadingGapDeadLetters" @click="loadGapDeadLetters()">刷新</el-button>
                <el-button type="primary" size="small" :loading="recoveringGapDeadLetters" @click="recoverGapDeadLetters({ recover_all: true })">批量恢复</el-button>
              </div>
            </div>
          </section>

          <section class="right-section">
            <div class="section-title">构建进度</div>
            <div class="progress-list">
              <div
                v-for="(item, index) in workflowStageItems"
                :key="item.key"
                :class="['progress-item', item.state]"
              >
                <span class="step-no">{{ index + 1 }}</span>
                <div class="step-copy">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.description }}</span>
                </div>
              </div>
            </div>
          </section>

          <section class="right-section">
            <div class="section-title">发布后展示</div>
            <div class="plain-card report-preview">
              <div class="report-row">
                <span>报告名称</span>
                <span class="report-label"><strong>{{ rightPanelReportLabel }}</strong></span>
              </div>
              <div class="report-row">
                <span>展示位置</span>
                <span class="report-stage"><strong>{{ rightPanelWorkflowStageText }}</strong></span>
              </div>
              <div class="report-row">
                <span>报告状态</span>
                <span class="report-show"><strong>{{ rightPanelReportVisibilityText }}</strong></span>
              </div>
            </div>
          </section>

          <details class="advanced">
            <summary>高级配置</summary>
            <div class="advanced-body">
              <div class="kv"><span>输出字段</span><span><strong>{{ rightPanelOutputField }}</strong></span></div>
              <div class="kv"><span>工作流阶段</span><span><strong>{{ rightPanelWorkflowStage }}</strong></span></div>
              <div class="kv"><span>执行顺序</span><span><strong>{{ rightPanelExecutionOrder }}</strong></span></div>
              <div class="kv"><span>提示词代理</span><span><strong>{{ rightPanelPromptAgentType }}</strong></span></div>
              <div class="kv"><span>模板状态</span><span><strong>{{ rightPanelPromptStatus }}</strong></span></div>
            </div>
          </details>

          <section v-if="callableAgents.length" class="right-section">
            <div class="section-title">可调用 Agent</div>
            <div class="plain-card callable-list">
              <div
                v-for="agent in callableAgents"
                :key="agent.spec_id"
                class="callable-item"
                @click="openAgentItem(agent)"
              >
                <div class="callable-name">{{ agent.name || '未命名' }}</div>
                <div class="callable-desc">{{ (agent.primary_goal || '').slice(0, 40) || '无描述' }}</div>
              </div>
            </div>
          </section>

          <section v-if="governanceReferences.length" class="right-section">
            <div class="section-title">治理参考</div>
            <div class="plain-card governance-refs">
              <div
                v-for="(ref, idx) in governanceReferences"
                :key="idx"
                :class="['governance-ref-item', ref.tone]"
              >
                <div class="governance-ref-label">{{ ref.label }}</div>
                <div class="governance-ref-text">{{ ref.text }}</div>
              </div>
            </div>
          </section>

          <details class="advanced debug-config-card">
            <summary>后台轨迹</summary>
            <div class="advanced-body">
              <el-card shadow="never">
                <div class="status-main-hint">{{ nanobotProgressHint || '等待新的助手动作。' }}</div>
                <div v-if="testProgress" class="test-progress-bar">
                  <el-progress :percentage="Math.max(5, Math.min(95, ['init','config','model','agent','analysis','report'].indexOf(testProgress.stage) * 15 + 10))" :stroke-width="6" :show-text="false" />
                  <span class="test-progress-label">{{ testProgress.message }}</span>
                </div>
                <div class="status-metrics">
                  <div class="status-metric-item">
                    <span>会话</span>
                    <strong>{{ currentNanobotSessionKey ? '已连接' : '未连接' }}</strong>
                  </div>
                  <div class="status-metric-item">
                    <span>草稿</span>
                    <strong>{{ displaySpec ? '已同步' : '未同步' }}</strong>
                  </div>
                  <div class="status-metric-item">
                    <span>版本</span>
                    <strong>{{ latestVersion ? `v${latestVersion.version}` : '无' }}</strong>
                  </div>
                </div>
              </el-card>

              <el-card class="status-card" shadow="never" style="margin-top: 12px;">
                <template #header>
                  <div class="card-header">
                    <span>工具轨迹</span>
                    <el-tag size="small" effect="plain">{{ nanobotToolEvents.length }}</el-tag>
                  </div>
                </template>
                <div v-if="!nanobotToolEvents.length" class="empty-note">开始对话后，这里会显示助手模式的后台处理轨迹。</div>
                <div v-else class="tool-event-list">
                  <div v-for="event in nanobotToolEvents" :key="event.key" :class="['tool-event-card', event.tone]">
                    <span class="tool-event-status">{{ event.statusLabel }}</span>
                    <strong>{{ event.title }}</strong>
                    <span v-if="event.detail">{{ event.detail }}</span>
                  </div>
                </div>
              </el-card>
            </div>
          </details>
        </div>
      </aside>
    </div>

    <el-dialog
      v-model="versionDetailDialogVisible"
      width="min(900px, 100vw - 48px)"
      destroy-on-close
      class="version-detail-dialog"
    >
      <template #header>
        <div class="dialog-head">
          <div>
            <div class="dialog-title">{{ versionDetailVersion?.agent_metadata?.name || versionDetailSpec?.name || 'Agent 详情' }}</div>
            <div class="dialog-subtitle">{{ versionDetailVersion?.version_id || versionDetailSpec?.spec_id || '' }}</div>
          </div>
          <el-button class="icon-btn" link @click="versionDetailDialogVisible = false">✕</el-button>
        </div>
      </template>

      <div class="dialog-body">
        <div v-loading="versionDetailLoading" class="dialog-content">
          <div v-if="versionDetailVersion" class="tab-container">
            <el-tabs v-model="versionDetailActiveTab" class="tab-bar">
              <el-tab-pane label="概览" name="overview">
                <div class="version-overview-hero">
                  <div class="score-value">{{ versionDetailScoreText }}</div>
                  <div class="version-overview-copy">
                    <h3>{{ versionDetailOverviewTitle }}</h3>
                    <p>{{ versionDetailOverviewDescription }}</p>
                  </div>
                </div>

                <div class="version-detail-card-grid">
                  <section class="detail-card">
                    <div class="detail-title">
                      基础信息
                      <el-button v-if="!editingVersionMetadata" link type="primary" @click="startEditingVersionMetadata">
                        编辑
                      </el-button>
                      <template v-else>
                        <el-button type="primary" size="small" :loading="savingVersionMetadata" @click="saveVersionMetadata">保存</el-button>
                        <el-button size="small" @click="cancelEditingVersionMetadata">取消</el-button>
                      </template>
                    </div>
                    <div class="detail-grid">
                      <div class="kv">
                        <span>版本号</span>
                        <span><strong>v{{ versionDetailVersion.version }}</strong></span>
                      </div>
                      <div class="kv">
                        <span>版本状态</span>
                        <span><strong>{{ getVersionStatusLabel(versionDetailVersion) }}</strong></span>
                      </div>
                      <div class="kv">
                        <span>规格</span>
                        <span><strong>{{ versionDetailSpec?.name || versionDetailVersion.spec_id }}</strong></span>
                      </div>
                      <div class="kv">
                        <span>输出字段</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailOutputFieldText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-input v-model="versionMetadataEditForm.output_field" size="small" placeholder="analysis" />
                        </template>
                      </div>
                      <div class="kv">
                        <span>工作流阶段</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailWorkflowStageText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-select v-model="versionMetadataEditForm.workflow_stage" size="small">
                            <el-option label="analyst" value="analyst" />
                            <el-option label="research" value="research" />
                            <el-option label="risk" value="risk" />
                            <el-option label="manager" value="manager" />
                            <el-option label="trader" value="trader" />
                          </el-select>
                        </template>
                      </div>
                      <div class="kv">
                        <span>报告标签</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailReportLabelText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-input v-model="versionMetadataEditForm.report_label" size="small" placeholder="【Agent名称】" />
                        </template>
                      </div>
                      <div class="kv">
                        <span>报告展示</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailShowInReportsText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-switch v-model="versionMetadataEditForm.show_in_reports" size="small" />
                        </template>
                      </div>
                      <div class="kv">
                        <span>执行顺序</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailExecutionOrderText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-input-number v-model="versionMetadataEditForm.execution_order" size="small" :min="0" :max="999" />
                        </template>
                      </div>
                      <div class="kv">
                        <span>节点名称</span>
                        <template v-if="!editingVersionMetadata">
                          <span><strong>{{ versionDetailNodeNameText }}</strong></span>
                        </template>
                        <template v-else>
                          <el-input v-model="versionMetadataEditForm.node_name" size="small" placeholder="Agent 节点名称" />
                        </template>
                      </div>
                    </div>
                  </section>

                  <section v-if="versionDetailPublishErrors.length || versionDetailPublishWarnings.length" class="detail-card">
                    <div class="detail-title">发布校验结果</div>
                    <div v-if="versionDetailPublishErrors.length" class="notice notice-amber">
                      <div class="notice-title">错误（必须修复才能发布）</div>
                      <ul style="padding-left: 18px; margin-top: 8px;">
                        <li v-for="err in versionDetailPublishErrors" :key="err">{{ err }}</li>
                      </ul>
                    </div>
                    <div v-if="versionDetailPublishWarnings.length" class="notice notice-amber" style="margin-top: 10px;">
                      <div class="notice-title">警告</div>
                      <ul style="padding-left: 18px; margin-top: 8px;">
                        <li v-for="warn in versionDetailPublishWarnings" :key="warn">{{ warn }}</li>
                      </ul>
                    </div>
                  </section>

                  <section class="detail-card">
                    <div class="detail-title">绑定工具</div>
                    <div v-if="versionDetailVersion.required_tools?.length" class="tool-tags">
                      <el-tag v-for="tool in versionDetailVersion.required_tools" :key="tool" class="tag-item" effect="plain">
                        {{ tool }}
                      </el-tag>
                    </div>
                    <div v-else class="empty-note">当前版本没有绑定工具。</div>
                    <div v-if="versionDetailAutoResolvedGaps.length" class="auto-resolved-list">
                      <div class="detail-subtitle">自动补齐 Skill</div>
                      <div v-for="item in versionDetailAutoResolvedGaps" :key="`${item.job_id || ''}-${item.gap_id || ''}-${item.skill_tool_id}`" class="auto-resolved-item">
                        <div class="auto-resolved-main">
                          <el-tag size="small" type="success" effect="plain">自动补齐</el-tag>
                          <strong>{{ item.skill_display_name || item.skill_tool_id }}</strong>
                          <el-button link type="primary" size="small" @click="openSkillTrace(item.skill_tool_id)">查看 Skill</el-button>
                        </div>
                        <div class="auto-resolved-meta">
                          <span v-if="item.gap">缺口：{{ item.gap }}</span>
                          <span v-if="item.resolution_stage">阶段：{{ item.resolution_stage }}</span>
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </el-tab-pane>

              <el-tab-pane label="Prompt 模板" name="prompt">
                <section class="detail-card">
                  <div class="detail-title">模板基本信息</div>
                  <div class="detail-grid">
                    <div class="kv">
                      <span>模板</span>
                      <span><strong>{{ versionDetailPrompt?.template_name || versionDetailVersion?.prompt_template_ref?.template_name || '未命名模板' }}</strong></span>
                    </div>
                    <div class="kv">
                      <span>状态</span>
                      <span><strong>{{ versionDetailPrompt?.status || versionDetailVersion?.prompt_template_ref?.status || '未知' }}</strong></span>
                    </div>
                    <div class="kv">
                      <span>Agent 类型</span>
                      <span><strong>{{ versionDetailPromptAgentTypeText }}</strong></span>
                    </div>
                    <div class="kv">
                      <span>Agent 名称</span>
                      <span><strong>{{ versionDetailPromptAgentNameText }}</strong></span>
                    </div>
                  </div>
                  <div class="detail-title" style="margin-top: 12px;">Prompt 内容</div>
                  <div v-if="versionDetailPromptSections.length" class="prompt-section-list">
                    <div v-for="section in versionDetailPromptSections" :key="section.key" class="prompt-section-card">
                      <div class="prompt-section-title">{{ section.label }}</div>
                      <pre class="prompt-section-content">{{ section.value }}</pre>
                    </div>
                  </div>
                  <div v-else class="empty-note">当前版本没有可展示的 Prompt 内容。</div>
                </section>
              </el-tab-pane>

              <el-tab-pane label="测试结果" name="test">
                <div v-if="versionDetailEvaluation" class="version-overview-hero">
                  <div class="score-value">{{ String(versionDetailEvaluation.scores?.overall ?? '-') }}</div>
                  <div class="version-overview-copy">
                    <h3>{{ getEvaluationDecisionLabel(versionDetailEvaluation.decision) }}</h3>
                    <p>点击“重新评估”可基于当前证据再次运行评估。</p>
                  </div>
                </div>

                <div class="version-detail-card-grid" style="margin-top: 12px;">
                  <section v-if="versionDetailPromptProjectMemorySummary" class="detail-card">
                    <div class="detail-title">项目记忆 - 模板绑定</div>
                    <div class="memory-summary-head">
                      <strong>{{ getProjectMemorySummaryStatusText(versionDetailPromptProjectMemorySummary.review_status) }}</strong>
                      <el-tag
                        size="small"
                        effect="plain"
                        :type="getProjectMemorySummaryTagType(versionDetailPromptProjectMemorySummary.review_status)"
                      >
                        {{ getProjectMemorySummaryStatusText(versionDetailPromptProjectMemorySummary.review_status) }}
                      </el-tag>
                    </div>
                    <div class="memory-summary-body">{{ versionDetailPromptProjectMemorySummary.summary }}</div>
                    <div class="memory-summary-meta" style="margin-top: 10px;">
                      <span>命中 {{ versionDetailPromptProjectMemorySummary.matched_items }}/{{ versionDetailPromptProjectMemorySummary.expected_items }}</span>
                      <span v-if="versionDetailPromptProjectMemorySummary.missing_item_count">缺口 {{ versionDetailPromptProjectMemorySummary.missing_item_count }}</span>
                    </div>
                  </section>

                  <section v-if="versionDetailEvaluationSummaryForDisplay" class="detail-card">
                    <div class="detail-title">
                      <span>最近评估摘要</span>
                      <el-button v-if="versionDetailEvaluation" size="small" link type="primary" @click="scrollToVersionDetailEvaluation">
                        查看完整评估
                      </el-button>
                    </div>
                    <div class="memory-summary-head">
                      <strong>{{ getEvaluationDecisionLabel(versionDetailEvaluationSummaryForDisplay.decision) }}</strong>
                      <el-tag size="small" effect="plain" :type="getEvaluationDecisionTagType(versionDetailEvaluationSummaryForDisplay.decision)">
                        {{ getEvaluationDecisionLabel(versionDetailEvaluationSummaryForDisplay.decision) }}
                      </el-tag>
                    </div>
                    <div class="memory-summary-body">{{ versionDetailEvaluationSummaryText }}</div>
                    <div v-if="versionDetailEvaluationSummaryItems.length" class="evaluation-summary-detail-list">
                      <div
                        v-for="(item, idx) in versionDetailEvaluationSummaryItems"
                        :key="`${item.type}-${idx}`"
                        class="evaluation-summary-detail-item"
                        :class="`evaluation-summary-detail-${item.type}`"
                      >
                        <span class="evaluation-summary-detail-label">{{ item.label }}</span>
                        <span class="evaluation-summary-detail-text">{{ item.text }}</span>
                      </div>
                    </div>
                    <div class="memory-summary-meta" style="margin-top: 10px;">
                      <span v-if="versionDetailEvaluationSummaryForDisplay.created_at">{{ formatDisplayTime(versionDetailEvaluationSummaryForDisplay.created_at) }}</span>
                      <span v-if="typeof versionDetailEvaluationSummaryForDisplay.overall_score === 'number'">综合分 {{ versionDetailEvaluationSummaryForDisplay.overall_score }}</span>
                    </div>
                  </section>

                  <section class="detail-card">
                    <div class="detail-title">最近测试报告</div>
                    <div v-if="versionDetailLatestRuntimeReportText || versionDetailLatestRuntimePayloadText || versionDetailLatestRuntimeMeta.length" class="version-detail-runtime-card">
                      <div v-if="versionDetailLatestRuntimeMeta.length" class="version-detail-meta-line">
                        <span v-for="item in versionDetailLatestRuntimeMeta" :key="item">{{ item }}</span>
                      </div>
                      <div v-if="versionDetailLatestRuntimeReportText" class="prompt-section-card runtime-report-card">
                        <div class="prompt-section-title">报告正文</div>
                        <div class="prompt-section-content runtime-report-content runtime-report-markdown" v-html="renderMarkdown(versionDetailLatestRuntimeReportText)"></div>
                      </div>
                      <div v-if="versionDetailLatestRuntimePayloadText" class="prompt-section-card runtime-report-card">
                        <div class="prompt-section-title runtime-json-title-row">
                          <span>结构化输出预览</span>
                          <el-button size="small" link @click="copyRuntimePayloadJson">复制 JSON</el-button>
                        </div>
                        <pre class="prompt-section-content runtime-report-content runtime-json-content">{{ versionDetailLatestRuntimePayloadText }}</pre>
                      </div>
                    </div>
                    <div v-else class="empty-note">最近一次测试没有保存可展示的报告正文。</div>
                  </section>

                  <section id="version-detail-evaluation-section" class="detail-card">
                    <div class="detail-title">
                      <span>最近评估</span>
                      <div class="detail-actions">
                        <el-button
                          size="small"
                          :loading="reEvaluatingVersionDetail"
                          :disabled="!canReEvaluateVersionDetail"
                          @click="reEvaluateVersionFromDetail"
                        >
                          重新评估
                        </el-button>
                        <el-button
                          size="small"
                          type="primary"
                          :loading="publishingVersionDetail"
                          :disabled="!canPublishVersionDetail"
                          @click="publishVersionFromDetail"
                        >
                          发布
                        </el-button>
                      </div>
                    </div>
                    <div v-if="versionDetailEvaluation" class="version-detail-runtime-card">
                      <div class="detail-grid">
                        <div class="kv">
                          <span>结论</span>
                          <span><strong>{{ getEvaluationDecisionLabel(versionDetailEvaluation.decision) }}</strong></span>
                        </div>
                        <div class="kv">
                          <span>总分</span>
                          <span><strong>{{ String(versionDetailEvaluation.scores?.overall ?? '-') }}</strong></span>
                        </div>
                        <div class="kv">
                          <span>评估类型</span>
                          <span><strong>{{ versionDetailEvaluation.evaluation_type || '-' }}</strong></span>
                        </div>
                        <div class="kv">
                          <span>更新时间</span>
                          <span><strong>{{ versionDetailEvaluation.updated_at || versionDetailEvaluation.created_at || '-' }}</strong></span>
                        </div>
                      </div>
                      <div v-if="versionDetailLayerCards.length" class="evaluation-layer-grid">
                        <div v-for="item in versionDetailLayerCards" :key="item.key" class="evaluation-layer-card">
                          <div class="evaluation-layer-title-row">
                            <strong>{{ item.label }}</strong>
                            <el-tag size="small" effect="plain" :type="(item.tagType as any)">{{ item.decisionLabel }}</el-tag>
                          </div>
                          <div class="evaluation-layer-meta">得分 {{ item.scoreText }}</div>
                        </div>
                      </div>
                      <div v-if="versionDetailBlockers.length" class="compact-list">
                        <div v-for="(item, idx) in versionDetailBlockers.slice(0, 4)" :key="idx" class="list-row list-row-danger">
                          阻断项 {{ idx + 1 }}：{{ item }}
                        </div>
                      </div>
                      <div v-if="versionDetailWarnings.length" class="compact-list">
                        <div v-for="(item, idx) in versionDetailWarnings.slice(0, 4)" :key="idx" class="list-row list-row-warning">
                          提示项 {{ idx + 1 }}：{{ item }}
                        </div>
                      </div>
                      <div v-if="versionDetailEvaluationIssues.length" class="compact-list">
                        <div v-for="(item, idx) in versionDetailEvaluationIssues" :key="idx" class="list-row list-row-danger">
                          问题 {{ idx + 1 }}：{{ item }}
                        </div>
                      </div>
                      <div v-if="versionDetailEvaluationRecommendations.length" class="compact-list">
                        <div v-for="(item, idx) in versionDetailEvaluationRecommendations" :key="idx" class="list-row list-row-info">
                          建议 {{ idx + 1 }}：{{ item }}
                        </div>
                      </div>
                    </div>
                    <div v-else class="empty-note">当前版本还没有评估记录。</div>
                  </section>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>

          <div v-else class="empty-note">当前没有可展示的版本详情。</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { useAuthStore } from '@/stores/auth'
import { isTokenValid } from '@/utils/auth'
import embeddedNanobotApi, {
  type EmbeddedNanobotChatResponse,
  type EmbeddedNanobotMessageItem,
  type EmbeddedNanobotThreadContext,
  type EmbeddedNanobotThreadItem,
} from '@/api/embeddedNanobot'
import agentWorkshopApi, {
  type AgentAutoResolvedGap,
  type AgentEvaluationReport,
  type AgentGapResolutionDeadLettersResult,
  type AgentGapResolutionDeadLetterGroup,
  type AgentGapResolutionDeadLetterItem,
  type AgentSpec,
  type AgentVersion,
  type AgentWorkshopMessage,
  type AgentWorkshopSessionDetail,
  type AgentWorkshopVersionPrompt,
} from '@/api/agentWorkshop'

type NanobotToolEventCard = {
  key: string
  title: string
  detail: string
  statusLabel: string
  tone: 'info' | 'success' | 'warning'
}

type NanobotStudioPersistedState = {
  nanobotSessionKey?: string
  sessionId?: string
  specId?: string
  specName?: string
  versionId?: string
  threadContext?: EmbeddedNanobotThreadContext | null
}

marked.setOptions({ breaks: true, gfm: true })

const AGENT_STUDIO_SESSION_PREFIX = 'embedded:agent-studio:'
const NANOBOT_SKILLS = ['nanobot-agent-design']
const AGENT_STUDIO_STATE_STORAGE_KEY = 'agent-studio:state'

const exampleQuestions = [
  '我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。',
  '帮我创建一个多维度估值助手，要能对比行业估值、历史估值、DCF模型估值。',
  '我需要一个新闻情绪助手，能抓取个股相关新闻并给出偏多/偏空/中性判断。',
]

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const routeQueryText = (value: unknown) => Array.isArray(value) ? String(value[0] || '') : String(value || '')
const isNewAgentRoute = () => {
  const mode = routeQueryText(route.query.mode).trim().toLowerCase()
  const action = routeQueryText(route.query.action).trim().toLowerCase()
  return mode === 'new' || action === 'new_agent'
}
const consumeNewAgentRouteParam = () => {
  const nextQuery = { ...route.query }
  delete nextQuery.mode
  delete nextQuery.action
  suppressNextRouteInit = true
  router.replace({ path: route.path, query: nextQuery }).catch(() => {})
}
let suppressNextRouteInit = false
let pendingRouteSync = false

const composerText = ref('')
const agentSearchText = ref('')
const selectedAgentStatusFilter = ref('all')
const agentStatusFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '草稿', value: 'draft' },
  { label: '测试中', value: 'testing' },
  { label: '已发布', value: 'published' },
]
const agentItems = ref<AgentSpec[]>([])
const versionItemsBySpec = ref<Record<string, AgentVersion[]>>({})
const loadingSpecVersions = ref<Record<string, boolean>>({})
const expandedSpecIds = ref<string[]>([])
const selectedVersionId = ref('')
const currentSession = ref<AgentWorkshopSessionDetail | null>(null)
const standaloneSpec = ref<AgentSpec | null>(null)
const currentNanobotSessionKey = ref('')
const currentNanobotThreadContext = ref<EmbeddedNanobotThreadContext | null>(null)
const nanobotMessages = ref<AgentWorkshopMessage[]>([])
// 按 spec_id 隔离聊天记录，切换 Agent 时自动保存/恢复
const specMessagesMap = ref<Record<string, AgentWorkshopMessage[]>>({})
const specSessionKeyMap = ref<Record<string, string>>({})
const nanobotDraftLink = ref<{ specId: string; specName: string; sessionId?: string } | null>(null)
const nanobotStreaming = ref(false)
const nanobotProgressHint = ref('')
const nanobotToolEvents = ref<NanobotToolEventCard[]>([])
const testProgress = ref<{ stage: string; message: string; status: string } | null>(null)
let testPollTimer: ReturnType<typeof setInterval> | null = null
const messagesContainer = ref<HTMLElement | null>(null)
const scrollToLatestMessage = () => {
  nextTick(() => {
    const el = messagesContainer.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}
const latestVersion = ref<AgentVersion | null>(null)
const latestVersionPrompt = ref<AgentWorkshopVersionPrompt | null>(null)
const latestEvaluation = ref<AgentEvaluationReport | null>(null)
const versionDetailDialogVisible = ref(false)
const versionDetailLoading = ref(false)
const publishingVersionDetail = ref(false)
const reEvaluatingVersionDetail = ref(false)
const versionDetailSpec = ref<AgentSpec | null>(null)
const versionDetailVersion = ref<AgentVersion | null>(null)
const versionDetailPrompt = ref<AgentWorkshopVersionPrompt | null>(null)
const versionDetailEvaluation = ref<AgentEvaluationReport | null>(null)
const versionDetailActiveTab = ref('overview')
const versionDetailPublishErrors = ref<string[]>([])
const versionDetailPublishWarnings = ref<string[]>([])
const editingVersionMetadata = ref(false)
const savingVersionMetadata = ref(false)
const versionMetadataEditForm = ref<Record<string, any>>({})
const renamingSpecId = ref('')
const renameSpecName = ref('')
const renameInputRef = ref<HTMLElement | null>(null)
const loadingNanobotThreads = ref(false)
const showLeftSidebar = ref(true)
const showStatusSidebar = ref(true)
const gapDeadLetters = ref<AgentGapResolutionDeadLettersResult | null>(null)
const loadingGapDeadLetters = ref(false)
const recoveringGapDeadLetters = ref(false)
const mainGridStyle = computed(() => {
  const l = showLeftSidebar.value
  const r = showStatusSidebar.value
  if (l && r) return { gridTemplateColumns: '280px minmax(0, 1fr) 340px' }
  if (!l && !r) return { gridTemplateColumns: 'minmax(0, 1fr)' }
  if (!l) return { gridTemplateColumns: 'minmax(0, 1fr) 340px' }
  return { gridTemplateColumns: '280px minmax(0, 1fr)' }
})
const recentNanobotThreads = ref<EmbeddedNanobotThreadItem[]>([])
const selectedThreadScope = ref('active')

const sending = ref(false)
const loadingSession = ref(false)

let activeNanobotStreamController: AbortController | null = null

/** 停止测试进度轮询 */
function stopTestProgressPolling() {
  if (testPollTimer) {
    clearInterval(testPollTimer)
    testPollTimer = null
  }
  testProgress.value = null
}

/** 启动测试进度轮询（每2秒获取一次进度） */
function startTestProgressPolling(versionId: string) {
  stopTestProgressPolling()
  const poll = async () => {
    try {
      const data = await agentWorkshopApi.getTestProgress(versionId)
      if (data.status === 'running') {
        testProgress.value = { stage: data.stage, message: data.message, status: 'running' }
      } else if (data.status === 'done' || data.status === 'idle' || !data.status) {
        stopTestProgressPolling()
      } else {
        testProgress.value = { stage: data.stage, message: data.message, status: data.status }
      }
    } catch {
      // 轮询失败不打断用户体验
    }
  }
  poll()
  testPollTimer = setInterval(poll, 2000)
}
const versionContextRequests = new Map<string, Promise<void>>()
const latestVersionContextRequests = new Map<string, Promise<void>>()
const sessionRequests = new Map<string, Promise<void>>()
const threadMessageRequests = new Map<string, Promise<boolean>>()

const readPersistedStudioState = (): NanobotStudioPersistedState | null => {
  try {
    const raw = localStorage.getItem(AGENT_STUDIO_STATE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed as NanobotStudioPersistedState : null
  } catch {
    return null
  }
}

const clearPersistedStudioState = () => {
  try {
    localStorage.removeItem(AGENT_STUDIO_STATE_STORAGE_KEY)
  } catch {}
}

const isNotFoundError = (error: any) => {
  return error?.response?.status === 404 || error?.status === 404 || String(error?.message || '').includes('404')
}

const clearInvalidPersistedSpec = (specId?: string) => {
  const invalidSpecId = String(specId || '').trim()
  const persisted = readPersistedStudioState()
  if (!persisted || (invalidSpecId && persisted.specId !== invalidSpecId)) {
    return
  }
  clearPersistedStudioState()
  nanobotDraftLink.value = null
  selectedVersionId.value = ''
  standaloneSpec.value = null
  resetVersionContext()
}

const persistState = () => {
  try {
    localStorage.setItem(
      AGENT_STUDIO_STATE_STORAGE_KEY,
      JSON.stringify({
        nanobotSessionKey: currentNanobotSessionKey.value,
        sessionId: currentSession.value?.session_id,
        specId: nanobotDraftLink.value?.specId || displaySpec.value?.spec_id,
        specName: nanobotDraftLink.value?.specName || displaySpec.value?.name,
        versionId: selectedVersionId.value || latestVersion.value?.version_id,
        threadContext: currentNanobotThreadContext.value,
      }),
    )
  } catch {}
}

const ensureNanobotContextAuth = async (): Promise<boolean> => {
  const accessToken = authStore.token || localStorage.getItem('auth-token')
  if (accessToken && isTokenValid(accessToken)) {
    return true
  }

  if (!authStore.refreshToken) {
    return false
  }

  try {
    return await authStore.refreshAccessToken()
  } catch {
    return false
  }
}

const renderMarkdown = (content: string) => {
  try {
    let text = content || ''
    if (!text) return ''
    // 流式渲染时，修复不完整的 GFM 表格：
    // 如果存在 | 但缺少闭合行（分隔行 |---|---| 后的行未完整），暂时隐藏不完整部分
    // 策略：找到最后一个未完成的表格块（以 | 开头的连续行），如果它没有分隔行就暂时移除
    const lines = text.split('\n')
    let lastTableStart = -1
    let hasSeparator = false
    for (let i = lines.length - 1; i >= 0; i--) {
      const trimmed = lines[i].trim()
      if (trimmed.startsWith('|') || trimmed === '') {
        if (trimmed.includes('|') && trimmed.replace(/[|\-\s:]/g, '') === '') {
          hasSeparator = true
        }
        if (lastTableStart === -1 && trimmed.startsWith('|')) {
          lastTableStart = i
        }
      } else {
        break
      }
    }
    // 如果尾部有表格行但没有分隔行，说明表格刚开始，暂不渲染表格部分
    if (lastTableStart >= 0 && !hasSeparator) {
      const beforeTable = lines.slice(0, lastTableStart).join('\n')
      const rendered = marked.parse(beforeTable) as string
      return rendered + `<div class="streaming-table-hint" style="color:var(--el-text-color-placeholder);font-size:12px;margin-top:4px;">正在生成表格...</div>`
    }
    return marked.parse(text) as string
  } catch {
    return String(content || '')
  }
}

const copyRuntimePayloadJson = async () => {
  const text = versionDetailLatestRuntimePayloadText.value
  if (!text) { ElMessage.warning('当前没有可复制的结构化输出'); return }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('JSON 已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}

const buildThreadContext = (): EmbeddedNanobotThreadContext => {
  const versionId = String(selectedVersionId.value || latestVersion.value?.version_id || '').trim() || undefined
  const workflowId = versionId ? `agent_workshop_debug_${versionId}` : undefined
  const debugTemplateId = String(
    latestVersionPrompt.value?.template_id || latestVersion.value?.prompt_template_ref?.template_id || ''
  ).trim() || undefined
  // 从上一轮 persisted context 继承工具写入的字段（intent, has_blocking_gaps, evaluation_status 等）
  const persisted = currentNanobotThreadContext.value || {}
  return {
    ...persisted as EmbeddedNanobotThreadContext,
    // UI 当前状态始终覆盖 persisted 值（spec_id / version_id 等）
    spec_id: String(displaySpec.value?.spec_id || '').trim() || undefined,
    spec_name: String(displaySpec.value?.name || nanobotDraftLink.value?.specName || '').trim() || undefined,
    workshop_session_id: String(currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim() || undefined,
    version_id: versionId,
    version_status: String(latestVersion.value?.status || '').trim() || undefined,
    workflow_id: workflowId,
    node_id: undefined,
    preference_id: 'neutral',
    debug_template_id: debugTemplateId,
  }
}

const applyThreadContext = async (threadContext?: EmbeddedNanobotThreadContext | null) => {
  const context = threadContext || {}
  const sessionId = String(context.workshop_session_id || '').trim()
  const specId = String(context.spec_id || '').trim()
  const versionId = String(context.version_id || '').trim()

  if (specId) {
    nanobotDraftLink.value = {
      specId,
      specName: String(context.spec_name || '').trim() || '当前 Draft',
      sessionId: sessionId || undefined,
    }
  }

  if (sessionId) {
    if (String(currentSession.value?.session_id || '').trim() !== sessionId) {
      await loadSession(sessionId, { syncNanobotThread: false, silent: true })
    }
  } else if (specId) {
    const currentSpecId = String(displaySpec.value?.spec_id || '').trim()
    if (currentSpecId !== specId || !latestVersion.value) {
      try {
        standaloneSpec.value = await agentWorkshopApi.getSpec(specId)
        selectedVersionId.value = ''
        expandAgentBranch(specId)
        await ensureSpecVersionsLoaded(specId)
        await loadLatestVersionContext(specId)
      } catch (error: any) {
        // 🔑 spec 还没创建（Agent Builder 流程中 spec 要到 generate_confirmed_candidate_agent
        // 才写库，但 thread_context 中可能已携带 spec_id）。此时静默忽略 404，
        // 并清除 nanobotDraftLink，避免前端持有无效的 specId。
        if (isNotFoundError(error)) {
          nanobotDraftLink.value = null
        }
      }
    }
  }

  if (versionId) {
    // 🔑 校验 version_id 是否属于当前 Agent，防止旧的线程上下文中的 version_id 污染
    // 版本 ID 格式: {spec_id}_v{N}，如 spec_nanobot_moat_analyst_v2_v1
    const currentSpecId = String(displaySpec.value?.spec_id || '').trim()
    if (currentSpecId && !versionId.startsWith(currentSpecId + '_v')) {
      // version_id 不属于当前 Agent，跳过加载
      return
    }
    selectedVersionId.value = versionId
    if (String(latestVersion.value?.version_id || '').trim() !== versionId || !latestVersionPrompt.value) {
      await loadVersionContext(versionId)
    }
  }

  // new_agent 意图由后端直接回复提示消息，不再自动重置会话
}

const getAgentStatusGroup = (item: AgentSpec) => {
  const versions = versionItemsBySpec.value[item.spec_id] || []
  if (versions.some(v => v.status === 'active')) return 'published'
  if (versions.some(v => v.status === 'testing')) return 'testing'
  return 'draft'
}

const filteredAgentItems = computed(() => {
  const keyword = agentSearchText.value.trim().toLowerCase()
  const status = selectedAgentStatusFilter.value
  return agentItems.value.filter(item => {
    const matchesKeyword = !keyword ||
      String(item.name || '').toLowerCase().includes(keyword) ||
      String(item.primary_goal || '').toLowerCase().includes(keyword) ||
      String(item.spec_id || '').toLowerCase().includes(keyword)
    const matchesStatus = status === 'all' || getAgentStatusGroup(item) === status
    return matchesKeyword && matchesStatus
  })
})

const displaySpec = computed(() => currentSession.value?.current_spec_snapshot || standaloneSpec.value || null)
type WorkspacePhase = 'requirement-intake' | 'confirmation' | 'generation' | 'governance' | 'testing' | 'evaluation' | 'publish-ready' | 'published' | 'blocked'

const generationReady = computed(() => Boolean(
  currentWorkshopSessionId.value
  && currentSession.value?.feasibility_status === 'feasible'
  && (currentSession.value?.completeness_score || 0) >= 0.75,
))
const workspacePhase = computed<WorkspacePhase>(() => {
  const feasibilityStatus = currentSession.value?.feasibility_status
  const versionStatus = latestVersion.value?.status

  if (feasibilityStatus === 'not-feasible') {
    return 'blocked'
  }
  if (versionStatus === 'active') {
    return 'published'
  }
  if (versionStatus === 'testing' && hasPassedLatestEvaluation.value) {
    return 'publish-ready'
  }
  if (latestEvaluation.value) {
    return 'evaluation'
  }
  if (versionStatus === 'testing') {
    return 'testing'
  }
  if (versionStatus === 'draft') {
    return 'governance'
  }
  if (currentSession.value?.gap_report || currentSession.value?.tooling_plan) {
    return 'governance'
  }
  if (latestVersion.value || generationReady.value) {
    return 'generation'
  }
  if (feasibilityStatus === 'need-clarification') {
    return 'confirmation'
  }
  return 'requirement-intake'
})
const workspacePhaseMeta = computed(() => {
  switch (workspacePhase.value) {
    case 'blocked':
      return {
        label: '不可继续',
        tagType: 'danger' as const,
        subtitle: currentSession.value?.refusal_reason || '当前目标超出可支持范围，请先缩小问题。',
        publishHint: '当前需求尚未进入可执行链路，不存在可发布版本。',
        nextAction: '先调整目标范围、输入边界或输出要求，再重新发起需求。',
        actionGuideItems: [
          '请在中间对话区告诉助手你要缩小的问题范围，或明确不再要求的内容。',
        ],
      }
    case 'confirmation':
      return {
        label: '待确认',
        tagType: 'warning' as const,
        subtitle: '助手已整理出初步 Draft，但还有关键决策待你确认。',
        publishHint: '当前还在确认阶段，尚未进入版本生成。',
        nextAction: '先回答待确认点，让需求进入可执行状态。',
        actionGuideItems: [
          '请直接回复待确认点，例如目标用户、输出格式、边界限制、默认工具偏好。',
        ],
      }
    case 'generation':
      return {
        label: latestVersion.value ? '待测试' : '可补建版本',
        tagType: generationReady.value || latestVersion.value ? 'success' as const : 'info' as const,
        subtitle: latestVersion.value
          ? '测试版本已生成。下一步直接用真实股票做真数据测试即可。'
          : '需求已经基本齐备，可以让助手补建测试版本。',
        publishHint: latestVersion.value?.status === 'draft'
          ? '当前还是 draft，需要先生成或补建测试版本。'
          : '当前还没有可发布的版本。',
        nextAction: latestVersion.value
          ? '直接发起真数据测试，验证这个测试版本。'
          : '先补建一个测试版本，再进入真数据测试。',
        actionGuideItems: latestVersion.value
          ? ['请直接在中间对话区告诉助手：开始真数据测试。']
          : ['请直接在中间对话区告诉助手：补建测试版本。'],
      }
    case 'governance':
      return {
        label: '资产治理中',
        tagType: 'warning' as const,
        subtitle: latestVersion.value
          ? `Draft 版本已存在（${latestVersion.value.version_id?.slice(-8) || ''}），可进行缺口分析、工具规划或构建测试版本。`
          : '需求已确认，Draft 已写入。接下来进行缺口分析、工具规划或版本构建。',
        publishHint: '当前还在治理阶段，版本尚未进入测试。',
        nextAction: '在对话中协作完成缺口分析和版本构建，准备进入真数据测试。',
        actionGuideItems: [
          '可在对话中要求分析缺口、生成工具规划，或直接让助手构建测试版本。',
        ],
      }
    case 'testing':
      return {
        label: '真数据测试中',
        tagType: 'success' as const,
        subtitle: '当前版本已进入 testing，可直接用真实股票做真数据测试；测试通过后才可发布。',
        publishHint: '当前版本已进入 testing，但还没有通过最新一次真数据测试评估，暂时不能发布。',
        nextAction: '继续完成真数据测试，并等待最新评估结论。',
        actionGuideItems: ['请直接在中间对话区告诉助手：对这个版本做真数据测试。'],
      }
    case 'evaluation':
      return {
        label: '待修正',
        tagType: 'warning' as const,
        subtitle: `最近一次真数据测试结论：${evaluationDecisionText.value}。`,
        publishHint: '当前已有真数据测试结论，但尚未满足正式发布条件。',
        nextAction: latestEvaluation.value?.decision === 'pass'
          ? '评估已通过，可进入待确认发布状态。'
          : '评估未通过，需要在对话中讨论修改方案，回到治理阶段重新迭代。',
        actionGuideItems: latestEvaluation.value?.decision === 'pass'
          ? ['评估已通过，请使用发布按钮确认发布。']
          : [
            '在中间对话区和小助手讨论修改方案。',
            '修改完成后，需要重新构建版本并运行真数据测试。',
          ],
      }
    case 'publish-ready':
      return {
        label: '待确认发布',
        tagType: 'success' as const,
        subtitle: '当前版本的最新一次真数据测试已通过，但不会自动发布；必须由你手动确认后才能发布为正式版本。',
        publishHint: '当前版本已进入 testing，且最新一次真数据测试评估通过；现处于待确认发布状态，不会自动发布。',
        nextAction: '确认无误后，手动执行发布。',
        actionGuideItems: ['如需发布，请使用版本详情区的发布按钮并手动确认，不再通过输入框自动触发。'],
      }
    case 'published':
      return {
        label: '已发布',
        tagType: 'success' as const,
        subtitle: '当前版本已经正式发布。后续如需修改，请基于下一轮迭代继续讨论。',
        publishHint: '当前版本已经是正式版本。',
        nextAction: '如果要继续优化，请开启下一轮迭代。',
        actionGuideItems: ['如需继续优化，请使用页面中的下一轮/迭代入口，不再通过输入框自动触发。'],
      }
    case 'requirement-intake':
    default:
      return {
        label: hasWorkspaceContext.value ? '需求收集中' : '讨论中',
        tagType: 'info' as const,
        subtitle: displaySpec.value
          ? '助手正在围绕当前 Draft 持续收敛目标、边界和输出。'
          : '先把这个 Agent 要做什么讲清楚。',
        publishHint: '当前还在需求收集阶段，尚未生成任何版本。',
        nextAction: '继续补充目标、边界、输入、输出和验收方式。',
        actionGuideItems: ['请直接在中间对话区继续描述你想创建的 Agent，直到需求足够完整。'],
      }
  }
})
const draftStatusText = computed(() => workspacePhaseMeta.value.label)
const focusSubtitle = computed(() => workspacePhaseMeta.value.subtitle)
const draftStatusTagType = computed(() => workspacePhaseMeta.value.tagType)
const callableAgents = computed(() => {
  return agentItems.value
    .filter(item => {
      const versions = versionItemsBySpec.value[item.spec_id] || []
      return versions.some(v => v.status === 'active')
    })
    .slice(0, 8)
})
const governanceReferences = computed(() => {
  const refs: { label: string; text: string; tone: string }[] = []
  const lr = getEvaluationLayeredReview(latestEvaluation.value)
  if (lr) {
    const blockers = getBlockers(latestEvaluation.value)
    const warnings = getWarnings(latestEvaluation.value)
    for (const b of blockers.slice(0, 2)) {
      refs.push({ label: '需修复', text: b.slice(0, 80), tone: 'danger' })
    }
    for (const w of warnings.slice(0, 2)) {
      refs.push({ label: '建议', text: w.slice(0, 80), tone: 'warning' })
    }
  }
  if (workspacePhase.value === 'governance' && !refs.length) {
    refs.push({ label: '当前阶段', text: '请完成缺口分析和版本构建后再进入测试。', tone: 'info' })
  }
  return refs
})
const activeAgentId = computed(() => String(displaySpec.value?.spec_id || '').trim())
const activeTreeKey = computed(() => selectedVersionId.value ? `version:${selectedVersionId.value}` : (activeAgentId.value ? `spec:${activeAgentId.value}` : ''))
const activeGapDeadLetters = computed<AgentGapResolutionDeadLetterItem[]>(() => gapDeadLetters.value?.items || [])
const activeGapDeadLetterGroups = computed<AgentGapResolutionDeadLetterGroup[]>(() => gapDeadLetters.value?.groups || [])
const hasGapDeadLetters = computed(() => activeGapDeadLetters.value.length > 0)
const latestGapDeadLetter = computed(() => activeGapDeadLetters.value[0] || null)
const gapDeadLetterSummaryText = computed(() => {
  if (!hasGapDeadLetters.value) return '暂无异常'
  const top = activeGapDeadLetterGroups.value[0]
  return top ? `${activeGapDeadLetters.value.length} 个失败项，主要原因：${top.reason_code}` : `${activeGapDeadLetters.value.length} 个失败项`
})
const latestVersionRuntimeContract = computed(() => latestVersion.value?.evaluation_policy?.runtime_contract || {})
const getLatestVersionMetadataValue = (key: string) => latestVersion.value?.agent_metadata?.[key] ?? latestVersionRuntimeContract.value?.[key]
const rightPanelOutputField = computed(() => String(getLatestVersionMetadataValue('output_field') || '分析').trim() || '分析')
const rightPanelWorkflowStage = computed(() => String(getLatestVersionMetadataValue('workflow_stage') || '研究').trim() || '研究')
const rightPanelWorkflowStageText = computed(() => {
  const stage = rightPanelWorkflowStage.value
  const labels: Record<string, string> = {
    analyst: '分析师部分',
    research: '研究分析部分',
    risk: '风险管理部分',
    manager: '组合决策部分',
    trader: '交易执行部分',
  }
  return labels[stage] || stage
})
const rightPanelReportLabel = computed(() => String(getLatestVersionMetadataValue('report_label') || latestVersion.value?.agent_metadata?.name || displaySpec.value?.name || '-').trim() || '-')
const rightPanelReportVisibilityText = computed(() => getLatestVersionMetadataValue('show_in_reports') === false ? '不展示在最终报告中' : '将展示在最终报告中')
const rightPanelExecutionOrder = computed(() => String(getLatestVersionMetadataValue('execution_order') ?? '-'))
const rightPanelPromptContract = computed(() => latestVersion.value?.evaluation_policy?.prompt_contract || {})
const rightPanelPromptAgentType = computed(() => String(rightPanelPromptContract.value?.agent_type || 'universal').trim() || 'universal')
const rightPanelPromptStatus = computed(() => String(latestVersionPrompt.value?.status || latestVersion.value?.prompt_template_ref?.status || '-').trim() || '-')
const rightPanelStatusTitle = computed(() => {
  if (workspacePhase.value === 'publish-ready') return '测试通过，可以发布'
  if (workspacePhase.value === 'published') return '已正式发布'
  if (workspacePhase.value === 'testing') return '测试中'
  if (workspacePhase.value === 'evaluation') return '等待修订或确认'
  if (workspacePhase.value === 'generation') return latestVersion.value ? '已生成版本，等待测试' : '需求已齐备，等待生成版本'
  return '开始创建 Agent'
})
const rightPanelStatusDescription = computed(() => {
  if (workspacePhase.value === 'publish-ready') return '当前版本已完成真数据测试，发布后将进入工作流报告。'
  if (workspacePhase.value === 'published') return '当前版本已经是工作流可用的正式版本。'
  if (latestVersion.value) return workspacePhaseMeta.value.subtitle
  return '描述你的目标后，助手会帮你设计职责、选择工具、生成测试版本。'
})
const rightPanelScoreTitle = computed(() => workspacePhase.value === 'publish-ready' ? '建议发布' : evaluationDecisionText.value)
const rightPanelScoreDescription = computed(() => latestEvaluation.value ? '内容质量、工具调用和输出格式会在这里汇总。' : '生成版本并完成评估后显示评分。')
const canPublishLatestVersion = computed(() => Boolean(latestVersion.value && latestEvaluation.value?.decision === 'pass' && latestVersion.value.status !== 'active'))

const latestVersionSpecFallback = computed<AgentSpec>(() => displaySpec.value || {
  spec_id: latestVersion.value?.spec_id || '',
  name: latestVersion.value?.agent_metadata?.name || latestVersion.value?.version_id || '智能体',
  primary_goal: latestVersion.value?.agent_metadata?.description || '',
  status: 'draft',
} as AgentSpec)

const hasWorkspaceContext = computed(() => Boolean(displaySpec.value || displayedMessages.value.length))
const currentWorkshopSessionId = computed(() => String(nanobotDraftLink.value?.sessionId || currentSession.value?.session_id || '').trim())
const displayedMessages = computed(() => {
  // 中间聊天区只展示用户与 Nanobot 的真实交互历史。
  // Agent Workshop session.messages 是内部治理状态（Draft 同步、gap 分析、版本构建等），
  // 不应回退展示在聊天区，否则会把内部提示词误认为用户对话历史。
  return nanobotMessages.value
})

const loadingHint = computed(() => {
  if (nanobotProgressHint.value.trim()) {
    return nanobotProgressHint.value.trim()
  }
  const latestEvent = nanobotToolEvents.value[nanobotToolEvents.value.length - 1]
  if (latestEvent) {
    return latestEvent.detail || latestEvent.title || '工坊助手正在整理方案'
  }
  return '工坊助手正在思考你的 Agent 方案'
})

const hasPassedLatestEvaluation = computed(() => latestEvaluation.value?.decision === 'pass')
const evaluationDecisionText = computed(() => latestEvaluation.value?.decision === 'pass' ? '通过' : '未评估')
const overallScoreText = computed(() => String(latestEvaluation.value?.scores?.overall ?? '-'))

const workflowStageItems = computed(() => {
  const hasVersion = Boolean(latestVersion.value)
  return [
    {
      key: 'requirement',
      title: '需求澄清',
      description: hasWorkspaceContext.value ? '已确认需求，正在整理 Draft' : '请先描述你的目标',
      state: hasWorkspaceContext.value ? 'done' : 'current',
    },
    {
      key: 'generated',
      title: '生成版本',
      description: hasVersion
        ? `已创建测试版本 v${latestVersion.value?.version}`
        : '需求已齐备，等待补建版本',
      state: hasVersion ? 'done' : 'current',
    },
    {
      key: 'verified',
      title: '真数据测试',
      description: workspacePhase.value === 'publish-ready' || workspacePhase.value === 'published'
        ? '最新一次真数据测试已通过'
        : latestEvaluation.value
          ? `最近评估结论：${evaluationDecisionText.value}`
          : '尚未开始真数据测试',
      state: workspacePhase.value === 'publish-ready' || workspacePhase.value === 'published'
        ? 'done'
        : latestEvaluation.value || workspacePhase.value === 'testing' || workspacePhase.value === 'evaluation'
          ? 'current'
          : hasVersion ? 'current' : 'pending',
    },
    {
      key: 'published',
      title: '确认发布',
      description: latestVersion.value?.status === 'active'
        ? '当前版本已经是正式版本'
        : '只有真数据测试评估通过后的 testing 版本才能正式发布',
      state: workspacePhase.value === 'published'
        ? 'done'
        : workspacePhase.value === 'publish-ready'
          ? 'current'
          : 'pending',
    },
  ]
})

const getSpecStatusLabel = (item: AgentSpec) => {
  // 优先使用 spec 自身的 status 字段
  const specStatus = String((item as any).status || '').trim().toLowerCase()
  if (specStatus === 'active') return '已发布'
  if (specStatus === 'testing') return '测试中'
  if (specStatus === 'draft') return '草稿'
  if (specStatus === 'archived') return '已归档'

  // 兜底：从已加载的版本数据推断
  const versions = versionItemsBySpec.value[item.spec_id] || []
  if (versions.some(v => v.status === 'active')) return '已发布'
  if (versions.some(v => v.status === 'testing')) return '测试中'
  return '草稿'
}

const getSpecTagType = (item: AgentSpec) => {
  const specStatus = String((item as any).status || '').trim().toLowerCase()
  if (specStatus === 'active') return 'primary'
  if (specStatus === 'testing') return 'warning'
  if (specStatus === 'archived') return 'info'
  return getSpecStatusLabel(item) === '草稿' ? 'info' : 'primary'
}

const getSpecMetaText = (item: AgentSpec) => {
  const versions = versionItemsBySpec.value[item.spec_id] || []
  if (!versions.length) return '暂无版本'
  const latestVersionItem = versions.sort((a, b) => b.version - a.version)[0]
  if (latestVersionItem.last_evaluation_summary) {
    const score = typeof latestVersionItem.last_evaluation_summary.overall_score === 'number'
      ? `评分 ${latestVersionItem.last_evaluation_summary.overall_score}`
      : ''
    const decision = getEvaluationDecisionLabel(latestVersionItem.last_evaluation_summary.decision)
    return [score, decision].filter(Boolean).join('，')
  }
  return '等待评估'
}

const getVersionStatusLabel = (version: AgentVersion) => {
  if (version.status === 'active') return '已发布'
  if (version.status === 'testing') return '测试中'
  return '草稿'
}

const getEvaluationDecisionLabel = (decision?: string) => {
  if (decision === 'pass') return '通过'
  if (decision === 'reject') return '拒绝'
  if (decision === 'revise') return '需要修订'
  return decision || '未评估'
}

const getEvaluationDecisionTagType = (decision?: string) => {
  const label = getEvaluationDecisionLabel(decision)
  if (label === '通过') return 'success'
  if (label === '拒绝') return 'danger'
  if (label === '需要修订') return 'warning'
  return 'info'
}

const getProjectMemorySummaryTagType = (status?: string) => {
  if (status === 'reviewed') return 'success'
  if (status === 'needs-review') return 'warning'
  return 'info'
}

const getProjectMemorySummaryStatusText = (status?: string) => {
  if (status === 'reviewed') return '已审核'
  if (status === 'needs-review') return '待审核'
  return '未审核'
}

const getEvaluationSummary = (evaluation?: AgentEvaluationReport | null) => evaluation?.evaluation_summary || null

const buildLayerCards = (evaluation?: AgentEvaluationReport | null) => {
  const lr = evaluation?.details?.layered_review
  if (!lr) return []
  const entries: Array<[string, any]> = []
  if (lr.content_quality) entries.push(['content_quality', lr.content_quality])
  if (lr.publish_readiness) entries.push(['publish_readiness', lr.publish_readiness])
  return entries.map(([key, layer]: [string, any]) => ({
    key,
    label: key === 'content_quality' ? '内容质量' : '发布就绪',
    decision: layer.decision,
    decisionLabel: getEvaluationDecisionLabel(layer.decision),
    tagType: getEvaluationDecisionTagType(layer.decision),
    scoreText: typeof layer.score === 'number' ? String(layer.score) : '-',
  }))
}

const versionDetailLayerCards = computed(() => buildLayerCards(versionDetailEvaluation.value))

const getEvaluationLayeredReview = (evaluation?: AgentEvaluationReport | null) => evaluation?.details?.layered_review || null
const getBlockers = (evaluation?: AgentEvaluationReport | null): string[] => {
  const lr = getEvaluationLayeredReview(evaluation)
  const raw = lr?.blockers
  return Array.isArray(raw) ? raw.filter((b): b is string => typeof b === 'string') : []
}
const getWarnings = (evaluation?: AgentEvaluationReport | null): string[] => {
  const lr = getEvaluationLayeredReview(evaluation)
  const raw = lr?.warnings
  return Array.isArray(raw) ? raw.filter((w): w is string => typeof w === 'string') : []
}
const versionDetailBlockers = computed(() => getBlockers(versionDetailEvaluation.value))
const versionDetailWarnings = computed(() => getWarnings(versionDetailEvaluation.value))

type EvaluationSummaryItem = {
  type: 'danger' | 'warning' | 'info'
  label: string
  text: string
}

const normalizeEvaluationText = (raw: any): string => {
  if (!raw) return ''
  if (typeof raw === 'string') return raw.trim()
  if (typeof raw !== 'object') return String(raw).trim()
  const severity = String(raw.severity || '').trim()
  const dimension = String(raw.dimension || raw.category || '').trim()
  const title = String(raw.title || '').trim()
  const description = String(raw.description || raw.issue || raw.message || '').trim()
  const evidence = Array.isArray(raw.evidence)
    ? raw.evidence.map((item: any) => String(item || '').trim()).filter(Boolean).join('；')
    : ''
  return [severity, dimension, title, description || evidence].filter(Boolean).join('｜').trim()
}

const getEvaluationIssues = (evaluation?: AgentEvaluationReport | null): string[] => {
  const raw = evaluation?.issues
  return Array.isArray(raw) ? raw.map(normalizeEvaluationText).filter(Boolean) : []
}

const getEvaluationRecommendations = (evaluation?: AgentEvaluationReport | null): string[] => {
  const raw = evaluation?.recommendations
  return Array.isArray(raw) ? raw.map(normalizeEvaluationText).filter(Boolean) : []
}

const versionDetailEvaluationIssues = computed(() => getEvaluationIssues(versionDetailEvaluation.value))
const versionDetailEvaluationRecommendations = computed(() => getEvaluationRecommendations(versionDetailEvaluation.value))
const versionDetailEvaluationSummaryItems = computed<EvaluationSummaryItem[]>(() => {
  const items: EvaluationSummaryItem[] = []
  versionDetailBlockers.value.slice(0, 3).forEach(text => items.push({ type: 'danger', label: '阻断项', text }))
  versionDetailWarnings.value.slice(0, 3).forEach(text => items.push({ type: 'warning', label: '提示项', text }))
  versionDetailEvaluationIssues.value.slice(0, 4).forEach(text => items.push({ type: 'danger', label: '问题', text }))
  versionDetailEvaluationRecommendations.value.slice(0, 3).forEach(text => items.push({ type: 'info', label: '建议', text }))
  return items.slice(0, 8)
})
const versionDetailEvaluationSummaryText = computed(() => {
  const summary = versionDetailEvaluationSummaryForDisplay.value
  const decisionLabel = getEvaluationDecisionLabel(summary?.decision)
  if (versionDetailEvaluationSummaryItems.value.length) {
    return `${decisionLabel}：请查看下方主要问题和修订建议。`
  }
  return versionDetailEvaluationProjectMemorySummary.value?.summary || '最近评估已运行。'
})
const scrollToVersionDetailEvaluation = () => {
  document.getElementById('version-detail-evaluation-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const versionDetailOutputFieldText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  return String(versionDetailVersion.value.agent_metadata?.output_field ?? '-').trim() || '-'
})
const versionDetailWorkflowStageText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  return String(versionDetailVersion.value.agent_metadata?.workflow_stage ?? '-').trim() || '-'
})
const versionDetailReportLabelText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  return String(versionDetailVersion.value.agent_metadata?.report_label ?? '-').trim() || '-'
})
const versionDetailShowInReportsText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  return versionDetailVersion.value.agent_metadata?.show_in_reports === false ? '不展示' : '展示'
})
const versionDetailExecutionOrderText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  const val = versionDetailVersion.value.agent_metadata?.execution_order
  return val == null ? '-' : String(val)
})
const versionDetailNodeNameText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  return String(versionDetailVersion.value.agent_metadata?.node_name ?? '-').trim() || '-'
})

const versionDetailPromptContract = computed(() => versionDetailVersion.value?.evaluation_policy?.prompt_contract || {})
const versionDetailAutoResolvedGaps = computed(() => {
  const metaGaps = versionDetailVersion.value?.agent_metadata?.auto_resolved_gaps
  const policyGaps = versionDetailVersion.value?.evaluation_policy?.auto_resolved_gaps
  const gaps: AgentAutoResolvedGap[] = Array.isArray(metaGaps) ? metaGaps : (Array.isArray(policyGaps) ? policyGaps : [])
  return gaps.filter(item => item && item.skill_tool_id)
})
const versionDetailPromptAgentTypeText = computed(() => String(versionDetailPromptContract.value?.agent_type ?? 'universal').trim() || 'universal')
const versionDetailPromptAgentNameText = computed(() => String(versionDetailPromptContract.value?.agent_name ?? versionDetailVersion.value?.version_id ?? '-').trim() || '-')

const versionDetailPromptProjectMemorySummary = computed(() => versionDetailVersion.value?.prompt_template_project_memory_binding_summary || null)
const versionDetailEvaluationSummaryForDisplay = computed(() => getEvaluationSummary(versionDetailEvaluation.value) || versionDetailVersion.value?.last_evaluation_summary || null)
const versionDetailEvaluationProjectMemorySummary = computed(() => versionDetailEvaluationSummaryForDisplay.value?.project_memory_binding || null)

const versionDetailPromptSections = computed(() => {
  const content = versionDetailPrompt.value?.content
  if (!content) return []
  return [
    { key: 'system_prompt', label: 'System Prompt', value: String(content.system_prompt || '').trim() },
    { key: 'user_prompt', label: 'User Prompt', value: String(content.user_prompt || '').trim() },
    { key: 'output_format', label: '输出格式', value: String(content.output_format || '').trim() },
  ].filter(item => item.value)
})
const versionDetailLatestRuntimeReportText = computed(() => {
  const runtime = versionDetailVersion.value?.runtime_result
  const debug = versionDetailVersion.value?.debug_result
  if (runtime && typeof runtime === 'object') {
    return String((runtime as any).output_text || (runtime as any).report || '').trim()
  }
  if (debug && typeof debug === 'object') {
    return String((debug as any).report || '').trim()
  }
  return ''
})
const versionDetailLatestRuntimePayloadText = computed(() => {
  const runtime = versionDetailVersion.value?.runtime_result
  if (runtime && typeof runtime === 'object') {
    const payload = (runtime as any).output_payload
    if (payload && typeof payload === 'object' && Object.keys(payload).length) {
      return JSON.stringify(payload, null, 2)
    }
    return ''
  }
  return ''
})
const versionDetailLatestRuntimeMeta = computed(() => {
  const runtime = versionDetailVersion.value?.runtime_result
  const debug = versionDetailVersion.value?.debug_result
  const data = (runtime && typeof runtime === 'object' ? runtime : debug && typeof debug === 'object' ? debug : {}) as Record<string, any>
  const result: string[] = []
  const symbol = String(data?.symbol || '').trim()
  const analysisDate = String(data?.analysis_date || '').trim()
  if (symbol) result.push(`标的: ${symbol}`)
  if (analysisDate) result.push(`分析日期: ${analysisDate}`)
  return result
})

const versionDetailScoreText = computed(() => {
  const score = versionDetailEvaluation.value?.scores?.overall ?? versionDetailVersion.value?.last_evaluation_summary?.overall_score
  return String(score ?? '-')
})
const versionDetailOverviewTitle = computed(() => {
  if (versionDetailVersion.value?.status === 'active') return '已正式发布'
  if (versionDetailEvaluation.value?.decision === 'pass') return '测试通过，建议发布'
  if (versionDetailEvaluation.value) return getEvaluationDecisionLabel(versionDetailEvaluation.value.decision)
  return '等待真数据测试'
})
const versionDetailOverviewDescription = computed(() => {
  if (versionDetailVersion.value?.status === 'active') return '当前版本已经接入工作流，可在分析报告中使用。'
  if (versionDetailEvaluation.value?.decision === 'pass') return `发布后将在最终分析报告中展示为 ${versionDetailReportLabelText.value}`
  if (versionDetailEvaluation.value) return '请根据评估结果继续修订后再发布。'
  return '生成版本并完成真数据测试后，才能进入发布确认。'
})
const canReEvaluateVersionDetail = computed(() => !!versionDetailVersion.value)
const canPublishVersionDetail = computed(() => !!versionDetailVersion.value && versionDetailEvaluation.value?.decision === 'pass' && versionDetailVersion.value.status !== 'active')

const openSkillTrace = (skillId?: string) => {
  const normalized = String(skillId || '').trim()
  if (!normalized) return
  router.push({ path: '/workflow/skill-generation', query: { skill_id: normalized, source: 'agent_studio_auto_gap_resolution' } })
}

const startEditingVersionMetadata = () => {
  const meta = versionDetailVersion.value?.agent_metadata || {}
  versionMetadataEditForm.value = {
    output_field: String(meta.output_field || 'analysis').trim() || 'analysis',
    workflow_stage: String(meta.workflow_stage || 'research').trim() || 'research',
    report_label: String(meta.report_label || '').trim(),
    show_in_reports: meta.show_in_reports !== false,
    execution_order: Number(meta.execution_order ?? 50),
    node_name: String(meta.node_name || '').trim(),
  }
  editingVersionMetadata.value = true
}

const cancelEditingVersionMetadata = () => {
  editingVersionMetadata.value = false
  versionMetadataEditForm.value = {}
}

const saveVersionMetadata = async () => {
  const versionId = String(versionDetailVersion.value?.version_id || '').trim()
  if (!versionId) return
  savingVersionMetadata.value = true
  try {
    const result = await agentWorkshopApi.updateVersionMetadata(versionId, versionMetadataEditForm.value)
    if (versionDetailVersion.value) {
      versionDetailVersion.value.agent_metadata = result.agent_metadata
    }
    if (latestVersion.value?.version_id === versionId) {
      latestVersion.value.agent_metadata = result.agent_metadata
    }
    editingVersionMetadata.value = false
    versionMetadataEditForm.value = {}
    ElMessage.success('运行时字段已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '更新失败')
  } finally {
    savingVersionMetadata.value = false
  }
}

const startRenameSpec = () => {
  const specId = String(displaySpec.value?.spec_id || '').trim()
  if (!specId) return
  renamingSpecId.value = specId
  renameSpecName.value = String(displaySpec.value?.name || '').trim()
  setTimeout(() => {
    const input = (renameInputRef.value as any)?.$el?.querySelector?.('input')
    if (input) {
      input.focus()
      input.select()
    }
  }, 50)
}

const cancelRenameSpec = () => {
  renamingSpecId.value = ''
  renameSpecName.value = ''
}

const confirmRenameSpec = async () => {
  const specId = String(renamingSpecId.value || '').trim()
  const newName = String(renameSpecName.value || '').trim()
  if (!specId || !newName) {
    cancelRenameSpec()
    return
  }
  renamingSpecId.value = ''
  renameSpecName.value = ''

  try {
    await agentWorkshopApi.updateSpec(specId, { name: newName })

    // 更新 standaloneSpec（displaySpec computed 会自动刷新）
    if (standaloneSpec.value?.spec_id === specId) {
      standaloneSpec.value = { ...standaloneSpec.value, name: newName }
    }
    // 更新 currentSession 中的 current_spec_snapshot
    if (currentSession.value?.current_spec_snapshot?.spec_id === specId) {
      currentSession.value.current_spec_snapshot.name = newName
    }
    // 更新 agentItems 列表
    const idx = agentItems.value.findIndex((it: any) => it.spec_id === specId)
    if (idx >= 0) {
      agentItems.value[idx] = { ...agentItems.value[idx], name: newName }
    }
    ElMessage.success('名称已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '重命名失败')
  }
}

const loadAgentItems = async () => {
  try {
    const result = await agentWorkshopApi.listSpecs({ page: 1, page_size: 100 })
    agentItems.value = [...(result.items || [])].sort((a, b) => {
      const leftTime = Date.parse(a.updated_at || a.created_at || '') || 0
      const rightTime = Date.parse(b.updated_at || b.created_at || '') || 0
      return rightTime - leftTime
    })
  } catch {
    agentItems.value = []
  }
}

const expandAgentBranch = (specId: string) => {
  if (!expandedSpecIds.value.includes(specId)) {
    expandedSpecIds.value.push(specId)
  }
}

const ensureSpecVersionsLoaded = async (specId: string, force?: boolean) => {
  const normalized = String(specId || '').trim()
  if (!normalized) return
  if (!force && versionItemsBySpec.value[normalized]) {
    return
  }
  if (loadingSpecVersions.value[normalized]) {
    return
  }
  loadingSpecVersions.value[normalized] = true
  try {
    const result = await agentWorkshopApi.listVersions({ spec_id: normalized, page: 1, page_size: 20 })
    versionItemsBySpec.value[normalized] = [...(result.items || [])].sort((a, b) => b.version - a.version)
  } catch {
    versionItemsBySpec.value[normalized] = []
  } finally {
    loadingSpecVersions.value[normalized] = false
  }
}

const loadVersionContext = async (versionId?: string) => {
  const normalized = String(versionId || '').trim()
  if (!normalized) {
    resetVersionContext()
    return
  }
  if (versionContextRequests.has(normalized)) {
    return versionContextRequests.get(normalized) as Promise<void>
  }
  const request = async () => {
    try {
      const [versionResult, versionPromptResult, evaluationResult] = await Promise.all([
        agentWorkshopApi.getVersion(normalized),
        agentWorkshopApi.getVersionPrompt(normalized).catch(() => null),
        agentWorkshopApi.listEvaluations(normalized, { page: 1, page_size: 1 }).catch(() => null),
      ])
      latestVersion.value = versionResult
      latestVersionPrompt.value = versionPromptResult
      latestEvaluation.value = evaluationResult?.items?.[0] || null
    } catch {
      resetVersionContext()
    }
  }
  versionContextRequests.set(normalized, request())
  try {
    await versionContextRequests.get(normalized)
  } finally {
    versionContextRequests.delete(normalized)
  }
}

const resetVersionContext = () => {
  latestVersion.value = null
  latestVersionPrompt.value = null
  latestEvaluation.value = null
}

const loadGapDeadLetters = async (options?: { silent?: boolean }) => {
  const sessionId = currentWorkshopSessionId.value
  const specId = activeAgentId.value
  if (!sessionId && !specId) {
    gapDeadLetters.value = null
    return
  }
  loadingGapDeadLetters.value = true
  try {
    gapDeadLetters.value = await agentWorkshopApi.listGapResolutionDeadLetters({
      session_id: sessionId || undefined,
      spec_id: sessionId ? undefined : specId,
      limit: 80,
    })
  } catch (error: any) {
    if (!options?.silent) {
      ElMessage.error(error?.message || '加载补齐异常失败')
    }
    gapDeadLetters.value = null
  } finally {
    loadingGapDeadLetters.value = false
  }
}

const recoverGapDeadLetters = async (payload?: { reason_code?: string; gap_ids?: string[]; job_id?: string; recover_all?: boolean }) => {
  const sessionId = currentWorkshopSessionId.value
  const specId = activeAgentId.value
  if (!sessionId && !specId && !payload?.job_id) return
  try {
    recoveringGapDeadLetters.value = true
    const result = await agentWorkshopApi.recoverGapResolutionDeadLetters({
      job_id: payload?.job_id,
      session_id: payload?.job_id ? undefined : (sessionId || undefined),
      spec_id: payload?.job_id || sessionId ? undefined : (specId || undefined),
      reason_code: payload?.reason_code,
      gap_ids: payload?.gap_ids,
      recover_all: payload?.recover_all ?? Boolean(!payload?.reason_code && !payload?.gap_ids?.length && !payload?.job_id),
      reason: 'Agent Studio 人工恢复 dead-letter',
    })
    ElMessage.success(result.recovered ? `已恢复 ${result.recovered} 个补齐失败项` : '没有可恢复的失败项')
    await loadGapDeadLetters({ silent: true })
  } catch (error: any) {
    ElMessage.error(error?.message || '恢复失败')
  } finally {
    recoveringGapDeadLetters.value = false
  }
}

const recoverGapDeadLettersByReason = async (group: AgentGapResolutionDeadLetterGroup) => {
  await recoverGapDeadLetters({ reason_code: group.reason_code })
}

const recoverSingleGapDeadLetter = async (item: AgentGapResolutionDeadLetterItem) => {
  await recoverGapDeadLetters({ job_id: item.job_id, gap_ids: [item.gap_id] })
}

const loadLatestVersionContext = async (specId?: string) => {
  const normalized = String(specId || '').trim()
  if (!normalized) {
    resetVersionContext()
    return
  }
  if (latestVersionContextRequests.has(normalized)) {
    return latestVersionContextRequests.get(normalized) as Promise<void>
  }
  const request = async () => {
    try {
      const result = await agentWorkshopApi.listVersions({ spec_id: normalized, page: 1, page_size: 1 })
      const latestVersionId = result.items?.[0]?.version_id
      if (!latestVersionId) {
        resetVersionContext()
        return
      }
      await loadVersionContext(latestVersionId)
    } catch {
      resetVersionContext()
    }
  }
  latestVersionContextRequests.set(normalized, request())
  try {
    await latestVersionContextRequests.get(normalized)
  } finally {
    latestVersionContextRequests.delete(normalized)
  }
}

const loadSession = async (sessionId?: string, options?: { syncNanobotThread?: boolean; silent?: boolean }) => {
  const normalized = String(sessionId || '').trim()
  if (!normalized) return
  if (sessionRequests.has(normalized)) {
    return sessionRequests.get(normalized) as Promise<void>
  }
  const request = async () => {
    loadingSession.value = true
    try {
      currentSession.value = await agentWorkshopApi.getSession(normalized)
      standaloneSpec.value = null
      nanobotDraftLink.value = {
        specId: currentSession.value.current_spec_snapshot?.spec_id || '',
        specName: currentSession.value.current_spec_snapshot?.name || '当前 Draft',
        sessionId: currentSession.value.session_id,
      }
      selectedVersionId.value = ''
      expandAgentBranch(currentSession.value.current_spec_snapshot?.spec_id || '')
      await ensureSpecVersionsLoaded(currentSession.value.current_spec_snapshot?.spec_id || '')
      await loadLatestVersionContext(currentSession.value.current_spec_snapshot?.spec_id || '')
      await loadGapDeadLetters({ silent: true })
      if (options?.syncNanobotThread && currentNanobotSessionKey.value) {
        await loadNanobotThreadMessages({ sessionKey: currentNanobotSessionKey.value, silent: true })
      }
    } catch (error: any) {
      if (!options?.silent) {
        ElMessage.error(error?.message || '加载会话失败')
      }
      throw error
    } finally {
      loadingSession.value = false
    }
  }
  sessionRequests.set(normalized, request())
  try {
    await sessionRequests.get(normalized)
  } finally {
    sessionRequests.delete(normalized)
  }
}

const findNanobotThreadForSpec = (specId: string, sourceThreadId?: string) => {
  const normalizedSpecId = String(specId || '').trim()
  const normalizedSourceThreadId = String(sourceThreadId || '').trim()
  return recentNanobotThreads.value.find(t => {
    const ctx = (t as any).thread_context || {}
    const channel = String((t as any).channel || '').trim()
    const threadId = String((t as any).thread_id || '').trim()
    const sessionKey = String((t as any).session_key || '').trim()
    if (
      channel === 'agent_workshop_evaluation'
      || threadId.startsWith('agent-workshop-eval:')
      || sessionKey.startsWith('embedded:agent-workshop-eval:')
      || threadId.startsWith('agent-workshop-worker:')
      || sessionKey.startsWith('embedded:agent-workshop-worker:')
    ) return false
    if (normalizedSourceThreadId && (threadId === normalizedSourceThreadId || sessionKey === normalizedSourceThreadId)) return true
    return normalizedSpecId && String(ctx.spec_id || '').trim() === normalizedSpecId
  }) || null
}

const openAgentItem = async (item: AgentSpec) => {
  // 保存当前 Agent 的聊天记录
  const currentSpecId = String(displaySpec.value?.spec_id || '').trim()
  if (currentSpecId && nanobotMessages.value.length) {
    specMessagesMap.value[currentSpecId] = [...nanobotMessages.value]
    specSessionKeyMap.value[currentSpecId] = currentNanobotSessionKey.value
  }

  // 切换到目标 Agent
  standaloneSpec.value = item
  expandAgentBranch(item.spec_id)
  await ensureSpecVersionsLoaded(item.spec_id)
  await loadLatestVersionContext(item.spec_id)

  // 🔥 优先加载并显示 Nanobot 聊天历史（用户真正的对话）
  // workshop session 只用于状态管理（gap report、tooling plan 等），不用于显示消息
  const savedMessages = specMessagesMap.value[item.spec_id]
  const savedSessionKey = specSessionKeyMap.value[item.spec_id]
  if (savedMessages && savedMessages.length) {
    nanobotMessages.value = [...savedMessages]
    currentNanobotSessionKey.value = savedSessionKey || ''
  } else {
    // 没有内存记录 → 从数据库查找该 Agent 的历史会话
    nanobotMessages.value = []
    currentNanobotSessionKey.value = ''

    await loadNanobotThreads()
    let sourceThreadId = ''
    if (item.latest_session_id) {
      try {
        const session = await agentWorkshopApi.getSession(item.latest_session_id)
        sourceThreadId = String((session.builder_contracts as any)?.nanobot_source?.thread_id || '').trim()
      } catch {}
    }
    const matchingThread = findNanobotThreadForSpec(item.spec_id, sourceThreadId)
    if (matchingThread) {
      await loadNanobotThreadMessages({ sessionKey: matchingThread.session_key || matchingThread.thread_id, silent: true })
    }
  }

  // 加载 workshop session（用于状态管理，不影响聊天显示）
  if (item.latest_session_id) {
    try {
      await loadSession(item.latest_session_id, { syncNanobotThread: false, silent: true })
      nanobotDraftLink.value = {
        specId: currentSession.value?.current_spec_snapshot?.spec_id || item.spec_id,
        specName: currentSession.value?.current_spec_snapshot?.name || item.name || '当前 Draft',
        sessionId: currentSession.value?.session_id,
      }
    } catch {
      currentSession.value = null
      nanobotDraftLink.value = {
        specId: item.spec_id,
        specName: item.name || '当前 Draft',
        sessionId: item.latest_session_id || undefined,
      }
    }
  } else {
    currentSession.value = null
    nanobotDraftLink.value = {
      specId: item.spec_id,
      specName: item.name || '当前 Draft',
      sessionId: undefined,
    }
  }

  await loadGapDeadLetters({ silent: true })

  nanobotStreaming.value = false
  nanobotProgressHint.value = ''
  nanobotToolEvents.value = []

  persistState()
  ElMessage.info('已选择该 Agent，继续对话可以创建/迭代版本')
}

const openLatestVersionDetail = async () => {
  if (!latestVersion.value) {
    ElMessage.warning('当前还没有版本')
    return
  }
  versionDetailDialogVisible.value = true
  versionDetailLoading.value = true
  versionDetailActiveTab.value = 'overview'
  versionDetailSpec.value = displaySpec.value || latestVersionSpecFallback.value
  try {
    await loadVersionDetail(latestVersion.value.version_id)
  } catch (error: any) {
    versionDetailDialogVisible.value = false
    ElMessage.error(error?.message || '加载版本详情失败')
  } finally {
    versionDetailLoading.value = false
  }
}

const openLatestPublishConfirm = async () => {
  if (!canPublishLatestVersion.value || !latestVersion.value) {
    ElMessage.warning('当前版本不满足发布条件')
    return
  }
  await openLatestVersionDetail()
  if (versionDetailDialogVisible.value && canPublishVersionDetail.value) {
    await publishVersionFromDetail()
  }
}

const loadVersionDetail = async (versionId: string) => {
  versionDetailVersion.value = null
  versionDetailPrompt.value = null
  versionDetailEvaluation.value = null
  versionDetailPublishErrors.value = []
  versionDetailPublishWarnings.value = []
  const [versionResult, versionPromptResult, evaluationResult] = await Promise.all([
    agentWorkshopApi.getVersion(versionId),
    agentWorkshopApi.getVersionPrompt(versionId).catch(() => null),
    agentWorkshopApi.listEvaluations(versionId, { page: 1, page_size: 1 }).catch(() => null),
  ])
  versionDetailVersion.value = versionResult
  versionDetailPrompt.value = versionPromptResult
  versionDetailEvaluation.value = evaluationResult?.items?.[0] || null
}

const publishVersionFromDetail = async () => {
  const versionId = String(versionDetailVersion.value?.version_id || '').trim()
  const specId = String(versionDetailSpec.value?.spec_id || versionDetailVersion.value?.spec_id || '').trim()
  if (!versionId) return
  if (!canPublishVersionDetail.value) {
    ElMessage.warning(versionDetailVersion.value?.status === 'active' ? '当前版本已经是正式版本' : '当前版本未满足发布条件')
    return
  }
  try {
    const agentName = versionDetailVersion.value?.agent_metadata?.name || versionDetailSpec.value?.name || specId
    const versionLabel = versionDetailVersion.value?.version != null ? `v${versionDetailVersion.value.version}` : versionId
    const autoResolvedSkills = versionDetailAutoResolvedGaps.value
      .map(item => item.skill_display_name || item.skill_tool_id)
      .filter(Boolean)
    const skillNote = autoResolvedSkills.length
      ? `\n\n本次版本包含 ${autoResolvedSkills.length} 个自动补齐的 Skill：${autoResolvedSkills.join('、')}`
      : ''
    await ElMessageBox.confirm(
      `确认将 Agent「${agentName}」(${versionLabel}) 发布为正式版本？${skillNote}`,
      '确认发布',
      { confirmButtonText: '确认发布', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  publishingVersionDetail.value = true
  versionDetailPublishErrors.value = []
  versionDetailPublishWarnings.value = []
  try {
    const result = await agentWorkshopApi.publishVersion(versionId)
    if (result.workflow_compatibility) {
      versionDetailPublishErrors.value = result.workflow_compatibility.errors || []
      versionDetailPublishWarnings.value = result.workflow_compatibility.warnings || []
    }
    await ensureSpecVersionsLoaded(specId, true)
    await loadVersionDetail(versionId)
    await loadAgentItems()
    if (latestVersion.value?.version_id === versionId) {
      await loadVersionContext(versionId)
    }
    ElMessage.success(result.previous_active_archived ? '版本已发布，上一正式版本已归档' : '版本已发布')
  } catch (error: any) {
    ElMessage.error(error?.message || '发布失败')
  } finally {
    publishingVersionDetail.value = false
  }
}

const reEvaluateVersionFromDetail = async () => {
  const versionId = String(versionDetailVersion.value?.version_id || '').trim()
  const specId = String(versionDetailSpec.value?.spec_id || versionDetailVersion.value?.spec_id || '').trim()
  if (!versionId) return
  reEvaluatingVersionDetail.value = true
  try {
    const result = await agentWorkshopApi.evaluateVersion(versionId)
    await loadVersionDetail(versionId)
    if (latestVersion.value?.version_id === versionId) {
      await loadVersionContext(versionId)
    }
    if (specId && displaySpec.value?.spec_id === specId) {
      await loadLatestVersionContext(specId)
    }
    await loadAgentItems()
    ElMessage.success(result.evaluation?.decision === 'pass' ? '重新评估完成，已满足发布条件' : '重新评估完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '重新评估失败')
  } finally {
    reEvaluatingVersionDetail.value = false
  }
}

const resetStudio = () => {
  // 保存当前 Agent 的聊天记录
  const specId = String(displaySpec.value?.spec_id || '').trim()
  if (specId && nanobotMessages.value.length) {
    specMessagesMap.value[specId] = [...nanobotMessages.value]
    specSessionKeyMap.value[specId] = currentNanobotSessionKey.value
  }
  clearStudioState()
  ElMessage.success('已重置，可以开始创建新 Agent')
}

const handleSendMessage = async () => {
  const text = composerText.value.trim()
  if (!text) return
  sending.value = true
  try {
    const hasAuth = await ensureNanobotContextAuth()
    if (!hasAuth) {
      ElMessage.warning('请先登录后再使用')
      return
    }

    if (!recentNanobotThreads.value.length) {
      await loadNanobotThreads()
    }

    const sessionKey = currentNanobotSessionKey.value || `${AGENT_STUDIO_SESSION_PREFIX}${Date.now()}`
    const now = new Date().toISOString()
    const nextMessages = [
      ...displayedMessages.value,
      { role: 'user', content: text, timestamp: now },
      { role: 'assistant', content: '', timestamp: now, progressSteps: [] },
    ]
    const assistantIndex = nextMessages.length - 1

    currentNanobotSessionKey.value = sessionKey
    nanobotMessages.value = nextMessages
    nanobotStreaming.value = true
    nanobotProgressHint.value = '正在发送给工坊助手'
    nanobotToolEvents.value = []
    composerText.value = ''
    persistState()

    const appendAssistantChunk = (chunk?: string) => {
      const t = String(chunk || '')
      if (!t) return
      nextMessages[assistantIndex].content = nextMessages[assistantIndex].content + t
      nanobotMessages.value = [...nextMessages]
    }

    try {
      await new Promise<EmbeddedNanobotChatResponse>((resolve, reject) => {
        activeNanobotStreamController = embeddedNanobotApi.chatStream({
          message: text,
          session_key: sessionKey,
          channel: 'agent_workshop',
          skill_names: NANOBOT_SKILLS,
          thread_context: buildThreadContext(),
        }, {
          onStarted(data) {
            currentNanobotSessionKey.value = data.session_key || sessionKey
            nanobotProgressHint.value = data.message || '工坊助手已开始处理'
            nextMessages[assistantIndex].progressSteps = nextMessages[assistantIndex].progressSteps || []
            nanobotMessages.value = [...nextMessages]
            persistState()
          },
          onProgress(data) {
            const msg = String(data.message || '').trim()
            if (!msg) return
            nanobotProgressHint.value = msg
            if (!nextMessages[assistantIndex].progressSteps) nextMessages[assistantIndex].progressSteps = []
            const steps = nextMessages[assistantIndex].progressSteps || []
            nextMessages[assistantIndex].progressSteps = [
              ...steps,
              { text: msg, tone: 'info' as const },
            ]
            nanobotMessages.value = [...nextMessages]
          },
          onToken(content) {
            appendAssistantChunk(content)
          },
          onToolEvent(event) {
            const toolName = String(event.title || event.name || '工具').trim() || '工具'
            const rawStatus = String(event.status || '').trim().toLowerCase()
            let statusLabel = '处理中'
            let tone: 'info' | 'success' | 'warning' = 'info'
            if (rawStatus.includes('complete') || rawStatus.includes('done')) { statusLabel = '已完成'; tone = 'success' }
            else if (rawStatus.includes('fail') || rawStatus.includes('error')) { statusLabel = '失败'; tone = 'warning' }
            nanobotToolEvents.value = [...nanobotToolEvents.value, { key: `${Date.now()}-${nanobotToolEvents.value.length}`, title: toolName, detail: String(event.detail || ''), statusLabel, tone }].slice(-8)
            nanobotProgressHint.value = event.status === 'started' ? `正在执行 ${toolName}` : `已处理 ${toolName}`

            // 🔥 测试工具开始 → 轮询进度
            const isTestTool = ['run_agent_workshop_real_data_test', 'debug_agent_workshop_version'].includes(String(event.name || ''))
            if (isTestTool && event.status === 'started') {
              const vid = latestVersion.value?.version_id
                || versionDetailVersion.value?.version_id
                || selectedVersionId.value
                || buildThreadContext().version_id
              if (vid) {
                startTestProgressPolling(vid)
              }
            }
            if (isTestTool && (rawStatus.includes('complete') || rawStatus.includes('done') || rawStatus.includes('fail') || rawStatus.includes('error'))) {
              stopTestProgressPolling()
            }

            if (!nextMessages[assistantIndex].progressSteps) nextMessages[assistantIndex].progressSteps = []
            const existingSteps = nextMessages[assistantIndex].progressSteps || []
            nextMessages[assistantIndex].progressSteps = [
              ...existingSteps,
              { text: event.status === 'started' ? `执行：${toolName}` : `完成：${toolName}`, tone, meta: String(event.detail || '') },
            ]
            nanobotMessages.value = [...nextMessages]
          },
          onStepEvent(event) {
            const title = String(event.title || '').trim()
            const detail = String(event.detail || '').trim()
            if (!title && !detail) return
            const status = String(event.status || '').trim().toLowerCase()
            const tone: 'info' | 'success' | 'warning' = status === 'completed' ? 'success' : status === 'error' ? 'warning' : 'info'
            if (!nextMessages[assistantIndex].progressSteps) nextMessages[assistantIndex].progressSteps = []
            const stepItems = nextMessages[assistantIndex].progressSteps || []
            nextMessages[assistantIndex].progressSteps = [
              ...stepItems,
              { text: title, tone, meta: detail },
            ]
            nanobotMessages.value = [...nextMessages]
          },
          onDone(data) {
            stopTestProgressPolling()
            currentNanobotSessionKey.value = data.session_key || sessionKey
            // 🔑 接收后端持久化后的完整 thread_context（含 intent），确保下次请求携带正确上下文
            if (data.thread_context) {
              currentNanobotThreadContext.value = data.thread_context
            }
            if (!nextMessages[assistantIndex].content.trim()) {
              nextMessages[assistantIndex].content = data.content || '工坊助手已处理当前需求。'
            }
            nanobotMessages.value = [...nextMessages]
            nanobotProgressHint.value = data.tools_used?.length ? `本轮已完成，调用了 ${data.tools_used.length} 个工具` : '本轮已完成'
            persistState()
            resolve(data)
          },
          onError(messageText) {
            stopTestProgressPolling()
            nextMessages[assistantIndex].content = `请求失败：${messageText || '未知错误'}`
            nanobotMessages.value = [...nextMessages]
            reject(new Error(messageText || '未知错误'))
          },
          onAbort() {
            stopTestProgressPolling()
            nextMessages[assistantIndex].content = '已停止本轮生成。'
            nanobotMessages.value = [...nextMessages]
            reject(new Error('已停止生成'))
          },
        })
      })

      await loadNanobotThreadMessages({ threadId: sessionKey, silent: true })
      await loadAgentItems()
      // 🔑 优先从后端返回的 thread_context 中获取 version_id（不依赖 displaySpec）
      const ctxVersionId = currentNanobotThreadContext.value?.version_id || ''
      if (ctxVersionId && (!latestVersion.value || String(latestVersion.value.version_id || '').trim() !== String(ctxVersionId).trim())) {
        await loadVersionContext(ctxVersionId)
      } else if (displaySpec.value?.spec_id) {
        await ensureSpecVersionsLoaded(displaySpec.value.spec_id)
        await loadLatestVersionContext(displaySpec.value.spec_id)
      }
      // 同步 Nanobot 线程上下文：确保 spec_id 写入线程，切换 Agent 后可恢复聊天记录
      if (displaySpec.value?.spec_id && currentNanobotSessionKey.value) {
        try {
          await embeddedNanobotApi.updateThreadContext(
            currentNanobotSessionKey.value,
            { thread_context: buildThreadContext() },
          )
        } catch {}
      }
      persistState()
      // 保存当前 Agent 的聊天记录到隔离 map
      const specId = String(displaySpec.value?.spec_id || '').trim()
      if (specId && nanobotMessages.value.length) {
        specMessagesMap.value[specId] = [...nanobotMessages.value]
        specSessionKeyMap.value[specId] = currentNanobotSessionKey.value
      }
    } finally {
      activeNanobotStreamController = null
      nanobotStreaming.value = false
    }
  } catch (error: any) {
    if (error?.name === 'AbortError' || error?.message === '已停止生成') {
      ElMessage.info('已停止')
    } else {
      ElMessage.error(error?.message || '发送失败')
    }
  } finally {
    sending.value = false
    nanobotStreaming.value = false
  }
}

const cancelNanobotStreaming = () => {
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
  }
}

const normalizeAssistantDisplayText = (value?: string | null) => {
  const text = String(value || '')
  if (!text) return ''
  return text
}

const loadInitialState = async () => {
  const newAgentMode = isNewAgentRoute()
  if (newAgentMode) {
    clearStudioState()
    consumeNewAgentRouteParam()
  }

  await loadAgentItems()
  await loadNanobotThreads()

  const routeSessionId = routeQueryText(route.query.sessionId).trim()
  const routeAgentId = routeQueryText(route.query.agent_id || route.query.agentId).trim()
  const routeSpecId = routeQueryText(route.query.specId || routeAgentId).trim()
  const routeNanobotSessionKey = routeQueryText(route.query.nanobotSessionKey).trim()

  const hasExplicitRouteTarget = Boolean(routeSessionId || routeSpecId || routeNanobotSessionKey || newAgentMode)

  // 🔑 如果有明确的 URL 目标（agent_id/specId/sessionId/nanobotSessionKey），或明确是新建模式，
  // 先清除旧状态，防止 localStorage 恢复的旧 Agent / selectedVersionId 污染当前页面
  if (hasExplicitRouteTarget) {
    selectedVersionId.value = ''
    resetVersionContext()
  }

  const restored = !hasExplicitRouteTarget ? restoreState() : false

  if (routeSessionId) {
    try {
      await loadSession(routeSessionId, { syncNanobotThread: false, silent: true })
    } catch (error: any) {
      if (isNotFoundError(error)) {
        clearInvalidPersistedSpec(routeSessionId)
      }
    }
  } else if (routeSpecId) {
    const matchedAgent = agentItems.value.find(item => item.spec_id === routeSpecId)
    if (matchedAgent) {
      await openAgentItem(matchedAgent)
    } else {
      try {
        standaloneSpec.value = await agentWorkshopApi.getSpec(routeSpecId)
        expandAgentBranch(routeSpecId)
        await ensureSpecVersionsLoaded(routeSpecId)
        await loadLatestVersionContext(routeSpecId)
        nanobotDraftLink.value = {
          specId: routeSpecId,
          specName: standaloneSpec.value.name || '当前 Draft',
          sessionId: standaloneSpec.value.latest_session_id || undefined,
        }
      } catch (error: any) {
        if (isNotFoundError(error)) {
          clearInvalidPersistedSpec(routeSpecId)
        }
      }
    }
  } else if (restored) {
    const persisted = readPersistedStudioState()
    if (persisted?.sessionId) {
      try {
        await loadSession(persisted.sessionId, { syncNanobotThread: false, silent: true })
      } catch (error: any) {
        if (isNotFoundError(error)) {
          clearInvalidPersistedSpec(persisted.specId)
        }
      }
    } else if (persisted?.specId) {
      const matchedByList = agentItems.value.find(item => item.spec_id === persisted.specId)
      if (matchedByList) {
        await openAgentItem(matchedByList)
      } else {
        try {
          standaloneSpec.value = await agentWorkshopApi.getSpec(persisted.specId)
          expandAgentBranch(persisted.specId)
          await ensureSpecVersionsLoaded(persisted.specId)
          await loadLatestVersionContext(persisted.specId)
        } catch (error: any) {
          if (isNotFoundError(error)) {
            clearInvalidPersistedSpec(persisted.specId)
          }
        }
      }
    }
    if (persisted?.nanobotSessionKey && !nanobotMessages.value.length) {
      await loadNanobotThreadMessages({ sessionKey: persisted.nanobotSessionKey, silent: true })
    }
  }

  if (routeNanobotSessionKey) {
    currentNanobotSessionKey.value = routeNanobotSessionKey
    if (!nanobotMessages.value.length) {
      await loadNanobotThreadMessages({ sessionKey: routeNanobotSessionKey, silent: true })
    }
  }

  if (displaySpec.value?.spec_id && !versionItemsBySpec.value[displaySpec.value.spec_id]) {
    await ensureSpecVersionsLoaded(displaySpec.value.spec_id)
    if (!latestVersion.value) {
      await loadLatestVersionContext(displaySpec.value.spec_id)
    }
  }
}

onMounted(() => {
  loadInitialState()
})

watch(() => route.fullPath, () => {
  if (suppressNextRouteInit) {
    suppressNextRouteInit = false
    return
  }
  if (!pendingRouteSync) {
    loadInitialState()
  }
})

/** 聊天消息变化时自动滚到底部 */
watch(() => displayedMessages.value.length, () => {
  scrollToLatestMessage()
})

const clearStudioState = (preserveStorage = false) => {
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
    activeNanobotStreamController = null
  }
  stopTestProgressPolling()
  currentSession.value = null
  standaloneSpec.value = null
  currentNanobotSessionKey.value = ''
  currentNanobotThreadContext.value = null
  nanobotMessages.value = []
  specMessagesMap.value = {}
  specSessionKeyMap.value = {}
  nanobotDraftLink.value = null
  nanobotStreaming.value = false
  nanobotProgressHint.value = ''
  nanobotToolEvents.value = []
  gapDeadLetters.value = null
  composerText.value = ''
  selectedVersionId.value = ''
  resetVersionContext()
  if (!preserveStorage) {
    clearPersistedStudioState()
  }
}

const restoreState = (sessionKey?: string) => {
  const persisted = readPersistedStudioState()
  if (!persisted) return false

  const restoredSessionKey = String(sessionKey || persisted.nanobotSessionKey || '').trim()
  if (restoredSessionKey) {
    currentNanobotSessionKey.value = restoredSessionKey
  }

  const restoredSpecId = String(persisted.specId || '').trim()
  const restoredSessionId = String(persisted.sessionId || '').trim()
  const restoredSpecName = String(persisted.specName || '').trim()
  if (restoredSpecId || restoredSessionId) {
    nanobotDraftLink.value = {
      specId: restoredSpecId,
      specName: restoredSpecName || '当前 Draft',
      sessionId: restoredSessionId || undefined,
    }
  }

  const restoredVersionId = String(persisted.versionId || '').trim()
  if (restoredVersionId) {
    selectedVersionId.value = restoredVersionId
  }

  if (persisted.threadContext) {
    currentNanobotThreadContext.value = persisted.threadContext as EmbeddedNanobotThreadContext
  }

  return Boolean(restoredSessionKey || restoredSpecId)
}

const loadNanobotThreads = async () => {
  loadingNanobotThreads.value = true
  try {
    const result = await embeddedNanobotApi.listThreads(80, selectedThreadScope.value === 'archived')
    recentNanobotThreads.value = result.items || []
  } catch {
    recentNanobotThreads.value = []
  } finally {
    loadingNanobotThreads.value = false
  }
}

const loadNanobotThreadMessages = async (options?: {
  threadId?: string
  sessionKey?: string
  silent?: boolean
}) => {
  const requestedThreadId = String(options?.threadId || options?.sessionKey || currentNanobotSessionKey.value || '').trim()
  if (!requestedThreadId) return false

  if (threadMessageRequests.has(requestedThreadId)) {
    return threadMessageRequests.get(requestedThreadId) as Promise<boolean>
  }

  const request = (async () => {
    let targetThread = recentNanobotThreads.value.find(item => item.thread_id === requestedThreadId || item.session_key === requestedThreadId) || null
    if (!targetThread) {
      await loadNanobotThreads()
      targetThread = recentNanobotThreads.value.find(item => item.thread_id === requestedThreadId || item.session_key === requestedThreadId) || null
    }
    if (!targetThread) return false
    const channel = String((targetThread as any).channel || '').trim()
    const threadId = String((targetThread as any).thread_id || '').trim()
    const sessionKey = String((targetThread as any).session_key || '').trim()
    if (
      channel === 'agent_workshop_evaluation'
      || threadId.startsWith('agent-workshop-eval:')
      || sessionKey.startsWith('embedded:agent-workshop-eval:')
      || threadId.startsWith('agent-workshop-worker:')
      || sessionKey.startsWith('embedded:agent-workshop-worker:')
    ) {
      return false
    }

    try {
      const result = await embeddedNanobotApi.getThreadMessages(targetThread.thread_id)
      currentNanobotSessionKey.value = result.thread?.session_key || targetThread.session_key || targetThread.thread_id
      nanobotMessages.value = mapDbMessagesToWorkshopMessages(result.messages || [])
      // 同步保存到隔离 map
      const specId = String(displaySpec.value?.spec_id || '').trim()
      if (specId && nanobotMessages.value.length) {
        specMessagesMap.value[specId] = [...nanobotMessages.value]
        specSessionKeyMap.value[specId] = currentNanobotSessionKey.value
      }
      await applyThreadContext(result.thread?.thread_context)
      persistState()
      return true
    } catch (error: any) {
      if (!options?.silent) {
        ElMessage.error(error?.message || '加载会话历史失败')
      }
      return false
    }
  })()

  threadMessageRequests.set(requestedThreadId, request)
  try {
    return await request
  } finally {
    threadMessageRequests.delete(requestedThreadId)
  }
}

const mapDbMessagesToWorkshopMessages = (items: EmbeddedNanobotMessageItem[]): AgentWorkshopMessage[] => {
  return items.map(item => ({
    role: item.role === 'user' ? 'user' : 'assistant',
    content: normalizeAssistantDisplayText(String(item.content || '')),
    timestamp: String(item.created_at || ''),
  }))
}

const formatDisplayTime = (value?: string | null) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('zh-CN', { hour12: false })
}

</script>
<style scoped>
.agent-studio-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(180deg, #f4f6fb 0%, #fafbfc 100%);
  color: #1e293b;
}

.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
  position: sticky;
  top: 0;
  z-index: 20;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.brand-mark {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  letter-spacing: -0.03em;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.24);
  flex-shrink: 0;
}

.brand-text {
  min-width: 0;
}

.brand-title {
  font-size: 16px;
  font-weight: 800;
  color: #1e293b;
  margin: 0;
}

.brand-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.btn-ghost.active {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #2563eb;
}

.btn {
  border: 0;
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.15s ease;
  cursor: pointer;
  background: #fff;
  color: #475569;
  border: 1px solid rgba(30, 58, 95, 0.14);
}

.btn:hover {
  background: #f8fafc;
}

.btn-primary {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
  border: 0;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.26);
}

.main {
  flex: 1;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 340px;
  overflow: hidden;
}

.sidebar, .inspector {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar {
  border-right: 1px solid rgba(30, 58, 95, 0.08);
}

.inspector {
  border-left: 1px solid rgba(30, 58, 95, 0.08);
}

.content {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.panel-head {
  padding: 16px;
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
}

.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
  margin: 0;
}

.panel-title-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.count-pill {
  font-size: 12px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid rgba(30, 58, 95, 0.08);
  padding: 2px 9px;
  border-radius: 999px;
}

.search-box {
  width: 100%;
  border: 1px solid rgba(30, 58, 95, 0.14);
  border-radius: 10px;
  padding: 9px 12px;
  outline: none;
  color: #1e293b;
  background: #fff;
  font-size: 13px;
  box-sizing: border-box;
}

.search-box:focus {
  border-color: rgba(37, 99, 235, 0.45);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

.filter-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.filter-chip {
  border: 1px solid rgba(30, 58, 95, 0.08);
  background: #fff;
  color: #64748b;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-chip:hover {
  background: #f8fafc;
}

.filter-chip.active {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #bfdbfe;
  font-weight: 700;
}

.agent-list {
  padding: 10px;
  overflow-y: auto;
  flex: 1;
}

.agent-card {
  padding: 13px;
  border: 1px solid transparent;
  border-radius: 14px;
  margin-bottom: 8px;
  transition: all 0.15s ease;
  background: transparent;
  cursor: pointer;
}

.agent-card:hover {
  background: rgba(37, 99, 235, 0.04);
  border-color: rgba(37, 99, 235, 0.1);
}

.agent-card.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(37, 99, 235, 0.02));
  border-color: rgba(37, 99, 235, 0.18);
}

.agent-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.agent-name {
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin: 0;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}

.agent-desc {
  margin-top: 7px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.agent-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #94a3b8;
  font-size: 11px;
}

.chat-head {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: rgba(255, 255, 255, 0.58);
}

.chat-head-left {
  min-width: 0;
}

.chat-title {
  font-size: 17px;
  font-weight: 850;
  color: #1e293b;
  margin: 0;
  cursor: default;
}

.chat-title:hover {
  color: #3b82f6;
}

.rename-inline-input {
  max-width: 260px;
}

.chat-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 3px;
}

.chat-head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mobile-panel-btn {
  display: none;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  padding-bottom: 120px;
}

.empty-spacer {
  display: none;
}

.empty-preview {
  margin: 18px 24px 0;
  border: 1px dashed #bfdbfe;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(255, 255, 255, 0.7));
  padding: 22px;
}

.empty-preview-title {
  font-size: 18px;
  font-weight: 900;
  color: #1e293b;
  margin: 0 0 8px;
}

.empty-preview-desc {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 16px;
}

.example-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 14px;
  background: #fff;
  padding: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.example-card:hover {
  border-color: rgba(37, 99, 235, 0.18);
  background: rgba(37, 99, 235, 0.02);
}

.example-card strong {
  display: block;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 6px;
}

.example-card span {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.message-row {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
  max-width: 84%;
}

.message-row.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.avatar {
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
}

.message-row.assistant .avatar {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
}

.message-row.user .avatar {
  background: #e2e8f0;
  color: #1e293b;
}

.bubble {
  background: #fff;
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 16px;
  padding: 14px 16px;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.035);
  flex: 1;
  min-width: 0;
}

.message-row.user .bubble {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  border-color: transparent;
  text-align: right;
}

.bubble-title {
  font-weight: 800;
  color: #1d4ed8;
  margin-bottom: 6px;
}

.message-row.user .bubble-title {
  color: #fff;
}

.bubble ul {
  padding-left: 18px;
  margin: 6px 0;
}

.bubble code {
  background: #f1f5f9;
  color: #1d4ed8;
  padding: 2px 5px;
  border-radius: 5px;
  font-size: 12px;
}

.bubble .markdown-content {
  :deep(table) {
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 13px;
    width: 100%;
    display: block;
    overflow-x: auto;
  }
  :deep(thead), :deep(tbody), :deep(tr) {
    display: table;
    width: 100%;
    table-layout: fixed;
  }
  :deep(th), :deep(td) {
    border: 1px solid rgba(30, 58, 95, 0.12);
    padding: 4px 10px;
    text-align: left;
    word-break: break-word;
  }
  :deep(th) {
    background: #f8fafc;
    font-weight: 600;
  }
  :deep(td:empty)::after {
    content: '—';
    color: #94a3b8;
  }
}

.quick-actions {
  margin: 0 0 20px 46px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-actions-hint {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
  line-height: 1.4;
}

.quick-actions-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-action {
  border: 1px solid #bfdbfe;
  background: #fff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}

.quick-action:hover {
  background: #eff6ff;
}

.input-area {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 14px 24px 18px;
  background: linear-gradient(to top, rgba(244, 246, 251, 0.98) 70%, rgba(244, 246, 251, 0.7) 95%, rgba(244, 246, 251, 0));
}

.input-shell {
  max-width: 960px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid rgba(30, 58, 95, 0.14);
  border-radius: 20px;
  padding: 8px 12px 10px;
  display: flex;
  gap: 10px;
  align-items: flex-end;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.chat-input {
  flex: 1;
  min-height: 42px;
  max-height: 140px;
  resize: none;
  border-radius: 14px;
  border: none;
  padding: 10px 12px;
  outline: none;
  background: transparent;
  color: #1e293b;
  font-size: 14px;
}

.input-tip {
  max-width: 960px;
  margin: 8px auto 0;
  color: #94a3b8;
  font-size: 11px;
  text-align: center;
}

.inspector-scroll {
  overflow-y: auto;
  padding: 10px 16px 16px 16px;
  flex: 1;
}

.status-card {
  border: 1px solid #bfdbfe;
  border-radius: 18px;
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  padding: 16px;
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.08);
}

.status-eyebrow {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 850;
  margin-bottom: 6px;
}

.status-title {
  color: #1e293b;
  font-size: 18px;
  font-weight: 900;
  margin-bottom: 6px;
}

.status-desc {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.score-row {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-value {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid #bfdbfe;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 900;
  color: #2563eb;
  flex-shrink: 0;
}

.score-copy {
  flex: 1;
  min-width: 0;
}

.score-copy strong {
  display: block;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 4px;
}

.score-copy span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.status-actions {
  margin-top: 14px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.right-section {
  margin-top: 18px;
}

.section-title {
  font-size: 13px;
  font-weight: 850;
  color: #1e293b;
  margin-bottom: 10px;
}

.section-title-with-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.dead-letter-card {
  border-color: rgba(239, 68, 68, 0.24);
  background: #fff7f7;
}

.dead-letter-alert {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #7f1d1d;
  font-size: 12px;
  line-height: 1.5;
}

.dead-letter-alert strong {
  color: #991b1b;
  font-size: 13px;
}

.dead-letter-message {
  color: #b45309;
}

.dead-letter-groups,
.dead-letter-items {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dead-letter-group,
.dead-letter-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  border: 1px solid rgba(239, 68, 68, 0.16);
  background: #fff;
  border-radius: 12px;
  padding: 8px 10px;
}

.dead-letter-group > div,
.dead-letter-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.dead-letter-group strong,
.dead-letter-item-main strong {
  color: #1e293b;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dead-letter-group span,
.dead-letter-item-main span {
  color: #64748b;
  font-size: 11px;
}

.dead-letter-actions {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border: 1px solid rgba(30, 58, 95, 0.08);
  background: #fff;
  border-radius: 13px;
  padding: 10px 12px;
}

.progress-item.current {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.progress-item.done .step-no {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.step-no {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 900;
  background: #f8fafc;
  color: #64748b;
  border: 1px solid rgba(30, 58, 95, 0.08);
}

.step-copy {
  flex: 1;
  min-width: 0;
}

.step-copy strong {
  display: block;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 2px;
}

.step-copy span {
  font-size: 12px;
  color: #64748b;
}

.plain-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 14px;
  background: #fff;
  padding: 14px;
}

.report-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.report-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.report-row span:first-child {
  color: #64748b;
}

.report-row span:last-child {
  color: #1e293b;
  font-weight: 750;
  text-align: right;
}

.callable-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.callable-item {
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}

.callable-item:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.callable-name {
  font-size: 13px;
  font-weight: 750;
  color: #1e293b;
}

.callable-desc {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.governance-refs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.governance-ref-item {
  border-radius: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(30, 58, 95, 0.08);
  background: #fff;
}

.governance-ref-item.danger {
  border-color: #fecaca;
  background: #fef2f2;
}

.governance-ref-item.warning {
  border-color: #fed7aa;
  background: #fff7ed;
}

.governance-ref-item.info {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.governance-ref-label {
  font-size: 11px;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 3px;
}

.governance-ref-item.danger .governance-ref-label { color: #dc2626; }
.governance-ref-item.warning .governance-ref-label { color: #ea580c; }
.governance-ref-item.info .governance-ref-label { color: #2563eb; }

.governance-ref-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.45;
}

details.advanced {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}

details.advanced summary {
  list-style: none;
  padding: 13px 14px;
  color: #1e293b;
  font-size: 13px;
  font-weight: 850;
  cursor: pointer;
}

details.advanced summary::-webkit-details-marker {
  display: none;
}

.advanced-body {
  border-top: 1px solid rgba(30, 58, 95, 0.08);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kv {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}

.kv span:first-child {
  color: #64748b;
}

.kv span:last-child {
  color: #1e293b;
  font-weight: 750;
  text-align: right;
}

.tool-event-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-event-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 13px;
  padding: 10px 12px;
  background: #fff;
}

.tool-event-card .tool-event-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  margin-bottom: 6px;
}

.tool-event-card.info .tool-event-status {
  background: #f8fafc;
  color: #64748b;
}

.tool-event-card.success .tool-event-status {
  background: #eff6ff;
  color: #1d4ed8;
}

.tool-event-card.warning .tool-event-status {
  background: #fffbeb;
  color: #d97706;
}

.tool-event-card strong {
  display: block;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 4px;
}

.tool-event-card span {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.status-main-hint {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.test-progress-bar {
  margin: 8px 0;
}
.test-progress-label {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #4b5563;
}

.status-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.status-metric-item {
  flex: 1;
  min-width: 0;
  background: #f8fafc;
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 13px;
  padding: 10px 12px;
  text-align: center;
}

.status-metric-item span {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}

.status-metric-item strong {
  display: block;
  font-size: 13px;
  font-weight: 800;
  color: #1e293b;
}

.dialog-head {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.dialog-title {
  font-size: 18px;
  font-weight: 900;
  color: #1e293b;
  margin: 0;
}

.dialog-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
}

.dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid rgba(30, 58, 95, 0.08);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.tab-container {
  width: 100%;
}

.tab-bar {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
  padding-bottom: 12px;
  margin-bottom: 16px;
  overflow-x: auto;
}

.tab-btn {
  border: 1px solid rgba(30, 58, 95, 0.08);
  background: #fff;
  color: #64748b;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  background: #f8fafc;
}

.tab-btn.active {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.version-detail-card-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.detail-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 16px;
  background: #f8fafc;
  padding: 16px;
}

.detail-title {
  font-size: 13px;
  font-weight: 850;
  color: #1e293b;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-overview-hero {
  display: flex;
  gap: 16px;
  align-items: center;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 14px;
}

.version-overview-copy {
  flex: 1;
  min-width: 0;
}

.version-overview-copy h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 850;
  color: #1e293b;
}

.version-overview-copy p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.version-detail-runtime-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 16px;
  background: #fff;
  padding: 14px;
}

.version-detail-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.version-detail-meta-line span {
  font-size: 11px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 999px;
  padding: 2px 9px;
}

.prompt-section-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-section-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 14px;
  background: #fff;
  padding: 14px;
}

.prompt-section-title {
  font-size: 13px;
  font-weight: 800;
  color: #1e293b;
  margin-bottom: 8px;
}

.prompt-section-content {
  background: #0f172a;
  color: #dbeafe;
  border-radius: 14px;
  padding: 14px;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  max-height: 260px;
  overflow-y: auto;
}

.runtime-json-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.runtime-json-title-row button {
  font-size: 12px;
}

.runtime-report-content.runtime-report-markdown {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #1e293b;
  font-family: "Noto Sans SC", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 14px;
  line-height: 1.8;
  max-height: 420px;
  padding: 16px 20px;
}

.runtime-report-content.runtime-report-markdown h1,
.runtime-report-content.runtime-report-markdown h2,
.runtime-report-content.runtime-report-markdown h3 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 800;
}

.runtime-report-content.runtime-report-markdown p {
  margin-bottom: 10px;
}

.runtime-report-content.runtime-report-markdown ul,
.runtime-report-content.runtime-report-markdown ol {
  padding-left: 20px;
  margin-bottom: 10px;
}

.notice {
  border-radius: 14px;
  padding: 14px;
  font-size: 13px;
  line-height: 1.6;
}

.notice-blue {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}

.notice-amber {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #d97706;
}

.tool-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-item {
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 12px;
  background: #f8fafc;
  color: #1e293b;
  border: 1px solid rgba(30, 58, 95, 0.08);
}

.auto-resolved-list {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.detail-subtitle {
  font-size: 12px;
  font-weight: 800;
  color: #475569;
}

.auto-resolved-item {
  border: 1px solid rgba(34, 197, 94, 0.18);
  border-radius: 12px;
  background: #f0fdf4;
  padding: 10px;
}

.auto-resolved-main {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #14532d;
}

.auto-resolved-meta {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.evaluation-layer-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.evaluation-layer-card {
  border: 1px solid rgba(30, 58, 95, 0.08);
  border-radius: 14px;
  background: #fff;
  padding: 14px;
}

.evaluation-layer-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.evaluation-layer-title-row strong {
  font-size: 13px;
  font-weight: 800;
  color: #1e293b;
}

.evaluation-layer-meta {
  font-size: 12px;
  color: #64748b;
}

.compact-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.evaluation-summary-detail-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.evaluation-summary-detail-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.55;
  background: #f8fafc;
}

.evaluation-summary-detail-label {
  flex: 0 0 auto;
  font-weight: 800;
}

.evaluation-summary-detail-text {
  color: #334155;
}

.evaluation-summary-detail-danger {
  background: #fef2f2;
}

.evaluation-summary-detail-danger .evaluation-summary-detail-label {
  color: #dc2626;
}

.evaluation-summary-detail-warning {
  background: #fffbeb;
}

.evaluation-summary-detail-warning .evaluation-summary-detail-label {
  color: #d97706;
}

.evaluation-summary-detail-info {
  background: #eff6ff;
}

.evaluation-summary-detail-info .evaluation-summary-detail-label {
  color: #2563eb;
}

.list-row {
  font-size: 13px;
  color: #475569;
}

.list-row-danger {
  color: #dc2626;
}

.list-row-warning {
  color: #d97706;
}

.list-row-info {
  color: #2563eb;
}

.evaluation-review-form {
  padding: 10px 0;
}

.evaluation-review-field {
  margin-bottom: 14px;
}

.evaluation-review-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 6px;
  display: block;
}

.empty-note {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

@media (max-width: 1280px) {
  .main {
    grid-template-columns: 260px minmax(0, 1fr);
  }
  .inspector {
    display: none;
  }
  .mobile-panel-btn {
    display: inline-flex;
  }
  .message-row {
    max-width: 90%;
  }
  .example-grid {
    grid-template-columns: 1fr;
  }
  .evaluation-layer-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .topbar {
    padding: 0 14px;
  }
  .brand-subtitle {
    display: none;
  }
  .main {
    grid-template-columns: minmax(0, 1fr);
  }
  .sidebar {
    display: none;
  }
  .chat-head {
    padding: 14px 16px;
  }
  .messages {
    padding: 18px 16px;
    padding-bottom: 120px;
  }
  .input-area {
    padding: 12px 16px 16px;
  }
  .topbar-actions .btn-ghost {
    display: none;
  }
}
</style>

