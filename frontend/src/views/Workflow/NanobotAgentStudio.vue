<template>
  <div class="nanobot-agent-studio-page">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">Agent 工坊助手</h1>
        <div class="page-subtitle">左侧管理 Agent，中央通过助手模式快速讨论、生成和迭代，右侧只保留后台状态。</div>
      </div>
      <div class="header-right">
        <div class="layout-toggle-group">
          <span class="layout-toggle-label">布局</span>
          <el-button size="small" :type="showAgentSidebar ? 'primary' : 'default'" plain @click="showAgentSidebar = !showAgentSidebar">
            {{ showAgentSidebar ? '隐藏左栏' : '显示左栏' }}
          </el-button>
          <el-button size="small" :type="showStatusSidebar ? 'primary' : 'default'" plain @click="showStatusSidebar = !showStatusSidebar">
            {{ showStatusSidebar ? '隐藏右栏' : '显示右栏' }}
          </el-button>
        </div>
        <el-button size="small" plain @click="router.push('/workflow/agent-workshop')">返回 Agent 工坊</el-button>
        <el-button size="small" plain @click="router.push('/workflow')">返回分析流</el-button>
        <el-button size="small" @click="refreshWorkspace" :loading="loadingSession">刷新</el-button>
        <el-button size="small" type="primary" @click="resetStudio">新建 Agent</el-button>
      </div>
    </div>

    <div :class="['workspace-body', { 'left-sidebar-hidden': !showAgentSidebar, 'right-sidebar-hidden': !showStatusSidebar }]">
      <aside v-if="showAgentSidebar" class="agent-sidebar">
        <div class="sidebar-header sidebar-header-compact">
          <div class="sidebar-header-actions">
            <el-button size="small" text @click="showNanobotThreadPanel = !showNanobotThreadPanel">
              {{ showNanobotThreadPanel ? '隐藏会话' : '最近会话' }}
            </el-button>
            <el-button size="small" text @click="resetStudio">新建</el-button>
          </div>
        </div>

        <div v-if="showNanobotThreadPanel" class="nanobot-thread-panel">
          <div class="thread-panel-header">
            <div>
              <div class="sidebar-title">最近助手会话</div>
              <div class="sidebar-subtitle">从数据库恢复后端已保存的对话</div>
            </div>
            <div class="thread-panel-actions">
              <el-button size="small" text @click="loadNanobotThreads" :loading="loadingNanobotThreads">刷新</el-button>
              <el-button size="small" text @click="showNanobotThreadPanel = false">收起</el-button>
            </div>
          </div>
          <div class="thread-filter-grid">
            <el-select v-model="selectedThreadScope" size="small" placeholder="活动会话" @change="loadNanobotThreads">
              <el-option label="活动会话" value="active" />
              <el-option label="已归档会话" value="archived" />
            </el-select>
            <el-input v-model="threadSearchText" size="small" clearable placeholder="搜索标题、摘要、最近问题" />
            <el-select v-model="selectedThreadAgentFilter" size="small" placeholder="全部 Agent">
              <el-option label="全部 Agent" value="all" />
              <el-option
                v-for="option in nanobotThreadAgentOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-select v-model="selectedThreadTimeFilter" size="small" placeholder="全部时间">
              <el-option label="全部时间" value="all" />
              <el-option label="最近 24 小时" value="24h" />
              <el-option label="最近 7 天" value="7d" />
              <el-option label="最近 30 天" value="30d" />
            </el-select>
          </div>
          <div v-if="loadingNanobotThreads" class="tree-inline-note">正在加载会话...</div>
          <div v-else-if="!filteredNanobotThreads.length" class="tree-inline-note">{{ selectedThreadScope === 'archived' ? '没有符合筛选条件的已归档会话' : '没有符合筛选条件的会话' }}</div>
          <div v-else class="nanobot-thread-list">
            <div
              v-for="thread in filteredNanobotThreads"
              :key="thread.thread_id"
              :class="['nanobot-thread-item', { active: activeNanobotThreadId === thread.thread_id }]"
            >
              <button type="button" class="nanobot-thread-main" @click="openNanobotThread(thread)">
                <div class="nanobot-thread-title-row">
                  <span class="nanobot-thread-title">{{ thread.title || '助手会话' }}</span>
                  <el-tag size="small" effect="plain">{{ thread.message_count }}</el-tag>
                </div>
                <div class="nanobot-thread-desc">{{ thread.last_user_message || thread.summary || '暂无摘要' }}</div>
                <div class="nanobot-thread-meta-row">
                  <span class="nanobot-thread-meta">{{ formatThreadMeta(thread) }}</span>
                  <span class="nanobot-thread-meta-badges">
                    <el-tag v-if="thread.archived" size="small" type="info" effect="plain">已归档</el-tag>
                    <span v-if="thread.thread_context?.spec_name" class="nanobot-thread-agent">{{ thread.thread_context.spec_name }}</span>
                  </span>
                </div>
              </button>
              <el-button
                v-if="thread.archived"
                type="primary"
                link
                class="thread-delete-btn"
                @click.stop="handleRestoreNanobotThread(thread)"
              >恢复</el-button>
              <el-button
                v-else
                type="danger"
                link
                class="thread-delete-btn"
                @click.stop="handleDeleteNanobotThread(thread)"
              >归档</el-button>
            </div>
          </div>
        </div>

        <button v-else type="button" class="nanobot-thread-panel-collapsed" @click="showNanobotThreadPanel = true">
          <span class="collapsed-panel-title">最近助手会话</span>
          <span class="collapsed-panel-desc">点击展开数据库会话列表、筛选和归档记录</span>
        </button>

        <div class="agent-tree">
          <el-empty v-if="!agentItems.length" description="暂无 Agent" :image-size="56" />
          <div v-else class="agent-tree-list">
            <div v-for="item in agentItems" :key="item.spec_id" class="agent-tree-branch">
              <div :class="['agent-tree-parent', { active: activeTreeKey === `spec:${item.spec_id}` }]">
                <button type="button" class="tree-toggle" @click.stop="toggleAgentBranch(item.spec_id)">
                  <span :class="['tree-chevron', { expanded: isAgentBranchExpanded(item.spec_id) }]"></span>
                </button>
                <button type="button" class="tree-main" @click="openAgentItem(item)">
                  <div class="agent-list-top">
                    <div class="agent-list-title">{{ item.name || '未命名 Agent' }}</div>
                    <el-tag size="small" :type="getSpecTagType(item)" effect="plain">{{ getSpecStatusLabel(item) }}</el-tag>
                  </div>
                  <div class="agent-list-desc">{{ item.primary_goal || '等待补充目标描述' }}</div>
                  <div class="agent-list-meta">
                    <span>版本 {{ (versionItemsBySpec[item.spec_id] || []).length || item.version_count || 0 }}</span>
                    <span>{{ getSpecMetaText(item) }}</span>
                  </div>
                </button>
                <el-button type="danger" link class="tree-delete-btn" @click.stop="handleDeleteSpec(item)">删除</el-button>
              </div>

              <div v-if="isAgentBranchExpanded(item.spec_id)" class="agent-tree-children">
                <div v-if="loadingSpecVersions[item.spec_id]" class="tree-inline-note">正在加载版本...</div>
                <div v-else-if="!(versionItemsBySpec[item.spec_id] || []).length" class="tree-inline-note">暂无版本</div>
                <div v-else class="agent-version-list">
                  <button
                    v-for="version in versionItemsBySpec[item.spec_id] || []"
                    :key="version.version_id"
                    type="button"
                    :class="['agent-version-item', { active: activeTreeKey === `version:${version.version_id}` }]"
                    @click="openAgentVersion(item, version)"
                  >
                    <div class="agent-version-main">
                      <div class="agent-version-title-row">
                        <span class="agent-version-title">v{{ version.version }}</span>
                        <el-tag size="small" effect="plain" :type="getVersionTagType(version)">{{ getVersionStatusLabel(version) }}</el-tag>
                        <el-tag
                          v-if="version.last_evaluation_summary"
                          size="small"
                          effect="plain"
                          :type="getEvaluationDecisionTagType(version.last_evaluation_summary.decision)"
                        >
                          {{ getEvaluationDecisionLabel(version.last_evaluation_summary.decision) }}
                        </el-tag>
                      </div>
                      <div class="agent-version-desc">
                        {{ version.prompt_template_project_memory_binding_summary?.summary || item.name || version.agent_metadata?.name || 'Agent 版本' }}
                      </div>
                      <div
                        v-if="getVersionProjectMemorySummary(version) || typeof version.last_evaluation_summary?.overall_score === 'number'"
                        class="agent-version-meta"
                      >
                        <el-tag
                          v-if="getVersionProjectMemorySummary(version)"
                          size="small"
                          effect="plain"
                          :type="getProjectMemorySummaryTagType(getVersionProjectMemorySummary(version)?.review_status)"
                        >
                          {{ getProjectMemorySummaryStatusText(getVersionProjectMemorySummary(version)?.review_status) }}
                        </el-tag>
                        <span v-if="typeof version.last_evaluation_summary?.overall_score === 'number'">
                          综合分 {{ version.last_evaluation_summary?.overall_score }}
                        </span>
                      </div>
                    </div>
                    <el-button type="danger" link class="tree-delete-btn" @click.stop="handleDeleteVersion(item, version)">删除</el-button>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <section class="chat-panel">
        <div class="chat-panel-header">
          <div>
            <div class="current-thread-title">{{ displaySpec?.name || '新建 Agent' }}</div>
            <div class="current-thread-subtitle">{{ focusSubtitle }}</div>
          </div>
          <div class="chat-panel-actions">
            <el-tag size="small" effect="plain">齐备度 {{ completenessPercent }}%</el-tag>
            <el-tag size="small" :type="draftStatusTagType" effect="plain">{{ draftStatusText }}</el-tag>
            <el-button size="small" @click="handleRefreshDraft" :loading="refreshingDraft">检查 Draft</el-button>
          </div>
        </div>

        <div ref="messagesContainer" class="messages-container">
          <el-empty
            v-if="displayedMessages.length === 0"
            description="先描述你要创建的 Agent，例如：做一个能跟踪财报变化并总结风险提示的助手。"
            :image-size="72"
          />
          <div v-else class="messages-list">
            <div
              v-for="(message, index) in displayedMessages"
              :key="index"
              :class="['message-item', message.role === 'user' ? 'message-user' : 'message-assistant', nanobotStreaming && index === displayedMessages.length - 1 && message.role === 'assistant' ? 'streaming-message' : '']"
            >
              <template v-if="message.role === 'user'">
                <div class="message-content">
                  <div class="message-text">{{ message.content }}</div>
                </div>
                <div class="message-avatar user-avatar">你</div>
              </template>
              <template v-else>
                <div class="message-avatar assistant-avatar">小助手</div>
                <div class="message-content">
                  <div v-if="message.progressSteps?.length" class="progress-timeline">
                    <div v-for="(step, stepIdx) in message.progressSteps" :key="`${index}-${stepIdx}`" class="timeline-step">
                      <span class="step-dot" :class="[{ success: step.tone === 'success' }, { warning: step.tone === 'warning' }, { active: nanobotStreaming && index === displayedMessages.length - 1 && stepIdx === message.progressSteps.length - 1 }] "></span>
                      <div class="step-content">
                        <span class="step-text">{{ step.text }}</span>
                        <span v-if="step.meta" class="step-meta">{{ step.meta }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="message-text markdown-content" v-html="renderMarkdown(message.content || (nanobotStreaming && index === displayedMessages.length - 1 ? loadingHint : ''))"></div>
                </div>
              </template>
            </div>

            <div v-if="nanobotStreaming && !displayedMessages.length" class="message-item message-assistant thinking-bubble">
              <div class="message-avatar assistant-avatar">小助手</div>
              <div class="message-content thinking-content">
                <div class="thinking-main-row">
                  <span class="thinking-text">{{ loadingHint }}</span>
                  <span class="thinking-dots">
                    <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
                  </span>
                </div>
                <div class="thinking-sub-row">已等待 {{ loadingSeconds }}s</div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-row">
            <el-input
              v-model="composerText"
              type="textarea"
              :rows="3"
              :autosize="{ minRows: 3, maxRows: 6 }"
              :placeholder="composerPlaceholder"
              :disabled="nanobotStreaming"
              @keydown.enter.ctrl.prevent="handleSendMessage"
            />
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!composerText.trim() || nanobotStreaming"
              class="send-btn"
              @click="handleSendMessage"
            >
              {{ sendButtonText }}
            </el-button>
          </div>
          <div class="input-tip-row">
            <span class="input-tip">Ctrl + Enter 发送</span>
            <el-button v-if="nanobotStreaming" type="danger" link @click="cancelNanobotStreaming">停止本轮生成</el-button>
          </div>
        </div>

      </section>

      <aside v-if="showStatusSidebar" class="status-sidebar">
        <div class="status-sidebar-header">
          <div>
            <div class="sidebar-title">助手状态</div>
            <div class="sidebar-subtitle">这里只看后台状态和工具轨迹</div>
          </div>
          <el-button v-if="nanobotStreaming" size="small" text @click="cancelNanobotStreaming">停止</el-button>
        </div>

        <div class="status-sidebar-scroll">
          <div class="result-panels">
            <el-collapse v-model="activeResultPanels" class="result-collapse">
              <el-collapse-item name="draft">
                <template #title>
                  <div class="result-collapse-title-row">
                    <span>Draft 结果</span>
                    <el-tag v-if="displaySpec" type="success" size="small" effect="plain">已同步</el-tag>
                  </div>
                </template>
                <div v-if="!displaySpec" class="empty-note">助手还没有同步出可用 Draft。</div>
                <div v-else class="result-section">
                  <div class="result-title">{{ displaySpec.name }}</div>
                  <div class="result-desc">{{ displaySpec.primary_goal }}</div>
                  <div v-if="displaySpec.responsibilities?.length" class="result-block">
                    <div class="result-label">职责</div>
                    <div class="tag-wrap">
                      <el-tag v-for="item in displaySpec.responsibilities" :key="item" class="tag-item">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="displaySpecOutputTags.length" class="result-block">
                    <div class="result-label">输出</div>
                    <div class="tag-wrap">
                      <el-tag v-for="item in displaySpecOutputTags" :key="item" class="tag-item" type="success">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="pendingQuestions.length" class="result-block">
                    <div class="result-label">待确认点</div>
                    <div class="compact-list">
                      <div v-for="(item, index) in pendingQuestions" :key="`${index}-${item}`" class="list-row">{{ index + 1 }}. {{ item }}</div>
                    </div>
                  </div>
                </div>
              </el-collapse-item>

              <el-collapse-item name="version">
                <template #title>
                  <div class="result-collapse-title-row">
                    <span>版本与评估</span>
                    <el-tag v-if="latestVersion" type="warning" size="small" effect="plain">v{{ latestVersion.version }}</el-tag>
                  </div>
                </template>
                <div v-if="!latestVersion" class="empty-note">还没有生成可测试版本。</div>
                <div v-else class="result-section">
                  <div class="result-title">{{ latestVersion.agent_metadata?.name || latestVersion.version_id }}</div>
                  <div class="meta-row">
                    <span>{{ latestVersion.version_id }}</span>
                    <span>{{ latestVersion.status }}</span>
                  </div>
                  <div v-if="versionOutputFields.length" class="result-block">
                    <div class="result-label">输出字段</div>
                    <div class="tag-wrap">
                      <el-tag v-for="item in versionOutputFields" :key="item" class="tag-item" type="success">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="versionPromptProjectMemorySummary || latestEvaluationSummaryForDisplay || latestEvaluationProjectMemorySummary" class="result-block">
                    <div class="result-label">L4 项目长期记忆</div>
                    <div class="memory-summary-grid">
                      <div v-if="versionPromptProjectMemorySummary" class="memory-summary-card">
                        <div class="memory-summary-head">
                          <strong class="memory-summary-title">模板绑定</strong>
                          <el-tag
                            size="small"
                            effect="plain"
                            :type="getProjectMemorySummaryTagType(versionPromptProjectMemorySummary.review_status)"
                          >
                            {{ getProjectMemorySummaryStatusText(versionPromptProjectMemorySummary.review_status) }}
                          </el-tag>
                        </div>
                        <div class="memory-summary-body">{{ versionPromptProjectMemorySummary.summary }}</div>
                        <div class="memory-summary-meta">
                          <span>命中 {{ versionPromptProjectMemorySummary.matched_items }}/{{ versionPromptProjectMemorySummary.expected_items }}</span>
                          <span v-if="versionPromptProjectMemorySummary.missing_item_count">缺口 {{ versionPromptProjectMemorySummary.missing_item_count }}</span>
                        </div>
                        <div v-if="versionPromptProjectMemorySummary.missing_items_preview?.length" class="memory-summary-missing">
                          <div
                            v-for="item in versionPromptProjectMemorySummary.missing_items_preview.slice(0, 2)"
                            :key="item"
                            class="memory-summary-missing-item"
                          >
                            {{ item }}
                          </div>
                        </div>
                      </div>
                      <div v-if="latestEvaluationSummaryForDisplay" class="memory-summary-card">
                        <div class="memory-summary-head">
                          <strong class="memory-summary-title">最近评估摘要</strong>
                          <el-tag size="small" effect="plain" :type="getEvaluationDecisionTagType(latestEvaluationSummaryForDisplay.decision)">
                            {{ getEvaluationDecisionLabel(latestEvaluationSummaryForDisplay.decision) }}
                          </el-tag>
                        </div>
                        <div class="memory-summary-body">
                          {{ latestEvaluationProjectMemorySummary?.summary || (latestEvaluationSummaryForDisplay.evaluation_valid ? '最近评估已产出可消费摘要。' : '最近评估仍有证据缺口，需要继续补齐。') }}
                        </div>
                        <div class="memory-summary-meta">
                          <span v-if="latestEvaluationSummaryForDisplay.created_at">{{ formatDisplayTime(latestEvaluationSummaryForDisplay.created_at) }}</span>
                          <span v-if="typeof latestEvaluationSummaryForDisplay.overall_score === 'number'">综合分 {{ latestEvaluationSummaryForDisplay.overall_score }}</span>
                          <span v-if="latestEvaluationSummaryForDisplay.worker_execution_mode">Worker {{ latestEvaluationSummaryForDisplay.worker_execution_mode }}</span>
                        </div>
                        <div v-if="latestEvaluationProjectMemorySummary" class="memory-summary-meta subtle">
                          <el-tag
                            size="small"
                            effect="plain"
                            :type="getProjectMemorySummaryTagType(latestEvaluationProjectMemorySummary.review_status)"
                          >
                            {{ getProjectMemorySummaryStatusText(latestEvaluationProjectMemorySummary.review_status) }}
                          </el-tag>
                          <span>命中 {{ latestEvaluationProjectMemorySummary.matched_items }}/{{ latestEvaluationProjectMemorySummary.expected_items }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="latestEvaluation" class="result-block">
                    <div class="result-label">最近评估</div>
                    <div class="meta-row">
                      <span>结论 {{ evaluationDecisionText }}</span>
                      <span>得分 {{ overallScoreText }}</span>
                    </div>
                    <div v-if="latestEvaluationLayerCards.length" class="evaluation-layer-grid compact-layer-grid">
                      <div v-for="item in latestEvaluationLayerCards" :key="item.key" class="evaluation-layer-card">
                        <div class="evaluation-layer-title-row">
                          <strong>{{ item.label }}</strong>
                          <el-tag size="small" effect="plain" :type="item.tagType">{{ item.decisionLabel }}</el-tag>
                        </div>
                        <div class="evaluation-layer-meta">得分 {{ item.scoreText }}</div>
                      </div>
                    </div>
                    <div v-if="latestEvaluationBlockers.length" class="compact-list">
                      <div v-for="(item, index) in latestEvaluationBlockers.slice(0, 4)" :key="`${index}-${item}`" class="list-row list-row-danger">阻断项 {{ index + 1 }}：{{ item }}</div>
                    </div>
                    <div v-if="latestEvaluationWarnings.length" class="compact-list">
                      <div v-for="(item, index) in latestEvaluationWarnings.slice(0, 4)" :key="`${index}-${item}`" class="list-row list-row-warning">提示项 {{ index + 1 }}：{{ item }}</div>
                    </div>
                    <div v-if="latestEvaluationEvidenceIncomplete || latestEvaluationInvalidReasons.length" class="compact-list">
                      <div v-if="latestEvaluationEvidenceIncomplete" class="list-row">当前评估未定案：存在关键证据缺口，不能直接作为正式发布依据。</div>
                      <div v-for="item in latestEvaluationInvalidReasons.slice(0, 3)" :key="item" class="list-row">证据缺口：{{ item }}</div>
                    </div>
                    <div v-if="latestEvaluationConfirmedIssues.length" class="compact-list">
                      <div v-for="(item, index) in latestEvaluationConfirmedIssues.slice(0, 4)" :key="`${index}-${item}`" class="list-row">已证实问题 {{ index + 1 }}：{{ item }}</div>
                    </div>
                    <div v-else-if="latestEvaluationInsufficientTitles.length" class="compact-list">
                      <div v-for="(item, index) in latestEvaluationInsufficientTitles.slice(0, 3)" :key="`${index}-${item}`" class="list-row">证据不足 {{ index + 1 }}：{{ item }}</div>
                    </div>
                    <div v-if="latestEvaluationWorkerCards.length" class="result-worker-list">
                      <div v-for="item in latestEvaluationWorkerCards.slice(0, 2)" :key="item.key" class="result-worker-card">
                        <div class="result-worker-title-row">
                          <strong>{{ item.workerName }}</strong>
                          <span>{{ item.statusText }} / {{ item.sourceText }}</span>
                        </div>
                        <div v-if="item.summary" class="result-worker-summary">{{ item.summary }}</div>
                        <div v-for="group in item.artifactGroups" :key="`${item.key}-${group.key}`" class="result-worker-group">
                          <div class="result-worker-group-title">{{ group.label }}</div>
                          <div v-for="artifact in group.items" :key="`${item.key}-${group.key}-${artifact.title}`" class="result-worker-artifact">
                            <div class="result-worker-artifact-title">{{ artifact.title }}</div>
                            <div v-for="entry in artifact.detailLines" :key="entry" class="result-worker-artifact-content">{{ entry }}</div>
                            <div v-if="artifact.tagEntries.length" class="tag-wrap worker-artifact-tags">
                              <el-tag v-for="entry in artifact.tagEntries" :key="entry" class="tag-item" effect="plain">{{ entry }}</el-tag>
                            </div>
                            <div class="result-worker-artifact-actions">
                              <el-tag v-if="artifact.manualReview" size="small" effect="plain" :type="getManualReviewTagType(artifact.manualReview)">
                                {{ getManualReviewStatusLabel(artifact.manualReview) }}
                              </el-tag>
                              <el-button size="small" text @click="openEvaluationArtifactReviewDialog(artifact)">人工审核</el-button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="result-block">
                    <div class="result-label">发布状态</div>
                    <div class="meta-row">
                      <span>{{ publishStatusHint }}</span>
                    </div>
                  </div>
                  <div class="result-block">
                    <div class="result-label">真实流程状态</div>
                    <div class="meta-row">
                      <span>当前阶段 {{ workspacePhaseLabel }}</span>
                    </div>
                    <div class="workflow-stage-list">
                      <div v-for="item in workflowStageItems" :key="item.key" :class="['workflow-stage-item', item.state]">
                        <span class="workflow-stage-dot"></span>
                        <div class="workflow-stage-body">
                          <div class="workflow-stage-name">{{ item.title }}</div>
                          <div class="workflow-stage-desc">{{ item.description }}</div>
                        </div>
                      </div>
                    </div>
                    <div class="workflow-next-action">下一步：{{ nextRequiredAction }}</div>
                  </div>
                  <div class="result-block nanobot-action-guide">
                    <div class="result-label">执行入口</div>
                    <div class="compact-list">
                      <div class="list-row">当前页面已移除前端直连的版本操作。</div>
                      <div v-for="item in phaseActionGuideItems" :key="item" class="list-row">{{ item }}</div>
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <el-card class="status-card" shadow="never">
            <div class="status-main-hint">{{ nanobotProgressHint || '等待新的助手动作。' }}</div>
            <div class="status-metrics">
              <div class="status-metric-item">
                <span>会话</span>
                <strong>{{ currentNanobotSessionKey ? '已连接' : '未连接' }}</strong>
              </div>
              <div class="status-metric-item">
                <span>Draft</span>
                <strong>{{ displaySpec ? '已同步' : '未同步' }}</strong>
              </div>
              <div class="status-metric-item">
                <span>版本</span>
                <strong>{{ latestVersion ? `v${latestVersion.version}` : '无' }}</strong>
              </div>
            </div>
          </el-card>

          <el-card class="status-card" shadow="never">
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

          <el-card v-if="hasIterationContext" class="status-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span>本轮重点</span>
              </div>
            </template>
            <div class="compact-list">
              <div v-for="(item, index) in iterationImprovementItems" :key="`${index}-${item}`" class="list-row">{{ index + 1 }}. {{ item }}</div>
            </div>
          </el-card>
          </div>
      </aside>
    </div>

    <el-dialog
      v-model="versionDetailDialogVisible"
      width="min(960px, calc(100vw - 32px))"
      destroy-on-close
      class="version-detail-dialog"
    >
      <template #header>
        <div class="version-detail-header">
          <div>
            <div class="version-detail-title">{{ versionDetailVersion?.agent_metadata?.name || versionDetailSpec?.name || 'Agent 详情' }}</div>
            <div class="version-detail-subtitle">{{ versionDetailVersion?.version_id || versionDetailSpec?.spec_id || '' }}</div>
          </div>
          <div class="version-detail-header-actions">
            <div class="version-detail-header-tags">
              <el-tag v-if="versionDetailVersion" size="small" effect="plain" :type="getVersionTagType(versionDetailVersion)">
                {{ getVersionStatusLabel(versionDetailVersion) }}
              </el-tag>
              <el-tag v-if="versionDetailSpec" size="small" effect="plain" :type="getSpecTagType(versionDetailSpec)">
                {{ getSpecStatusLabel(versionDetailSpec) }}
              </el-tag>
            </div>
            <el-button
              v-if="versionDetailVersion"
              type="primary"
              size="small"
              :loading="publishingVersionDetail"
              :disabled="!canPublishVersionDetail"
              @click="publishVersionFromDetail"
            >
              {{ versionDetailPublishButtonText }}
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="versionDetailLoading" class="version-detail-body">
        <div v-if="versionDetailVersion" class="version-detail-grid">
          <section class="version-detail-section summary-section">
            <div class="version-detail-section-title">基础信息</div>
            <div class="version-detail-summary-grid">
              <div class="version-detail-summary-item">
                <span>版本号</span>
                <strong>v{{ versionDetailVersion.version }}</strong>
              </div>
              <div class="version-detail-summary-item">
                <span>版本状态</span>
                <strong>{{ getVersionStatusLabel(versionDetailVersion) }}</strong>
              </div>
              <div class="version-detail-summary-item">
                <span>Spec</span>
                <strong>{{ versionDetailSpec?.name || versionDetailVersion.spec_id }}</strong>
              </div>
              <div class="version-detail-summary-item">
                <span>输出字段</span>
                <strong>{{ versionDetailOutputFieldText }}</strong>
              </div>
            </div>
            <div class="version-detail-description">
              {{ versionDetailVersion.agent_metadata?.description || versionDetailSpec?.primary_goal || '暂无描述' }}
            </div>
          </section>

          <section class="version-detail-section">
            <div class="version-detail-section-title">绑定工具</div>
            <div v-if="versionDetailVersion.required_tools?.length" class="tag-wrap detail-tag-wrap">
              <el-tag v-for="tool in versionDetailVersion.required_tools" :key="tool" class="tag-item" type="success">
                {{ tool }}
              </el-tag>
            </div>
            <div v-else class="empty-note">当前版本没有绑定工具。</div>
          </section>

          <section class="version-detail-section">
            <div class="version-detail-section-title">能力声明</div>
            <div v-if="versionDetailVersion.required_capabilities?.length" class="tag-wrap detail-tag-wrap">
              <el-tag v-for="capability in versionDetailVersion.required_capabilities" :key="capability" class="tag-item" effect="plain">
                {{ capability }}
              </el-tag>
            </div>
            <div v-else class="empty-note">当前版本没有额外的能力声明。</div>
          </section>

          <section class="version-detail-section">
            <div class="version-detail-section-title">Prompt 模板</div>
            <div class="version-detail-meta-line">
              <span>模板：{{ versionDetailPrompt?.template_name || versionDetailVersion.prompt_template_ref?.template_name || '未命名模板' }}</span>
              <span>状态：{{ versionDetailPrompt?.status || versionDetailVersion.prompt_template_ref?.status || 'unknown' }}</span>
            </div>
            <div v-if="versionDetailPromptSections.length" class="prompt-section-list">
              <div v-for="section in versionDetailPromptSections" :key="section.key" class="prompt-section-card">
                <div class="prompt-section-title">{{ section.label }}</div>
                <pre class="prompt-section-content">{{ section.value }}</pre>
              </div>
            </div>
            <div v-else class="empty-note">当前版本没有可展示的 Prompt 内容。</div>
          </section>

          <section v-if="versionDetailPromptProjectMemorySummary || versionDetailEvaluationSummaryForDisplay || versionDetailEvaluationProjectMemorySummary" class="version-detail-section">
            <div class="version-detail-section-title">L4 项目长期记忆</div>
            <div class="memory-summary-grid">
              <div v-if="versionDetailPromptProjectMemorySummary" class="memory-summary-card">
                <div class="memory-summary-head">
                  <strong class="memory-summary-title">模板绑定</strong>
                  <el-tag
                    size="small"
                    effect="plain"
                    :type="getProjectMemorySummaryTagType(versionDetailPromptProjectMemorySummary.review_status)"
                  >
                    {{ getProjectMemorySummaryStatusText(versionDetailPromptProjectMemorySummary.review_status) }}
                  </el-tag>
                </div>
                <div class="memory-summary-body">{{ versionDetailPromptProjectMemorySummary.summary }}</div>
                <div class="memory-summary-meta">
                  <span>命中 {{ versionDetailPromptProjectMemorySummary.matched_items }}/{{ versionDetailPromptProjectMemorySummary.expected_items }}</span>
                  <span v-if="versionDetailPromptProjectMemorySummary.missing_item_count">缺口 {{ versionDetailPromptProjectMemorySummary.missing_item_count }}</span>
                </div>
                <div v-if="versionDetailPromptProjectMemorySummary.missing_items_preview?.length" class="memory-summary-missing">
                  <div
                    v-for="item in versionDetailPromptProjectMemorySummary.missing_items_preview.slice(0, 3)"
                    :key="item"
                    class="memory-summary-missing-item"
                  >
                    {{ item }}
                  </div>
                </div>
              </div>
              <div v-if="versionDetailEvaluationSummaryForDisplay" class="memory-summary-card">
                <div class="memory-summary-head">
                  <strong class="memory-summary-title">最近评估摘要</strong>
                  <el-tag size="small" effect="plain" :type="getEvaluationDecisionTagType(versionDetailEvaluationSummaryForDisplay.decision)">
                    {{ getEvaluationDecisionLabel(versionDetailEvaluationSummaryForDisplay.decision) }}
                  </el-tag>
                </div>
                <div class="memory-summary-body">
                  {{ versionDetailEvaluationProjectMemorySummary?.summary || (versionDetailEvaluationSummaryForDisplay.evaluation_valid ? '最近评估已产出可消费摘要。' : '最近评估仍有证据缺口，需要继续补齐。') }}
                </div>
                <div class="memory-summary-meta">
                  <span v-if="versionDetailEvaluationSummaryForDisplay.created_at">{{ formatDisplayTime(versionDetailEvaluationSummaryForDisplay.created_at) }}</span>
                  <span v-if="typeof versionDetailEvaluationSummaryForDisplay.overall_score === 'number'">综合分 {{ versionDetailEvaluationSummaryForDisplay.overall_score }}</span>
                  <span v-if="versionDetailEvaluationSummaryForDisplay.evaluation_status">状态 {{ versionDetailEvaluationSummaryForDisplay.evaluation_status }}</span>
                </div>
                <div v-if="versionDetailEvaluationProjectMemorySummary" class="memory-summary-meta subtle">
                  <el-tag
                    size="small"
                    effect="plain"
                    :type="getProjectMemorySummaryTagType(versionDetailEvaluationProjectMemorySummary.review_status)"
                  >
                    {{ getProjectMemorySummaryStatusText(versionDetailEvaluationProjectMemorySummary.review_status) }}
                  </el-tag>
                  <span>命中 {{ versionDetailEvaluationProjectMemorySummary.matched_items }}/{{ versionDetailEvaluationProjectMemorySummary.expected_items }}</span>
                </div>
              </div>
            </div>
          </section>

          <section class="version-detail-section">
            <div class="version-detail-section-title">最近测试报告</div>
            <div v-if="versionDetailLatestRuntimeReportText || versionDetailLatestRuntimePayloadText || versionDetailLatestRuntimeMeta.length" class="version-detail-runtime-card">
              <div v-if="versionDetailLatestRuntimeMeta.length" class="version-detail-meta-line">
                <span v-for="item in versionDetailLatestRuntimeMeta" :key="item">{{ item }}</span>
              </div>
              <div v-if="versionDetailLatestRuntimeReportText" class="prompt-section-card runtime-report-card">
                <div class="prompt-section-title">报告正文</div>
                <div
                  class="prompt-section-content runtime-report-content runtime-report-markdown"
                  v-html="renderMarkdown(versionDetailLatestRuntimeReportText)"
                ></div>
              </div>
              <div v-if="versionDetailLatestRuntimePayloadText" class="prompt-section-card runtime-report-card">
                <div class="prompt-section-title runtime-json-title-row">
                  <span>结构化输出预览</span>
                  <el-button size="small" text @click="copyRuntimePayloadJson">复制 JSON</el-button>
                </div>
                <pre class="prompt-section-content runtime-report-content runtime-json-content">{{ versionDetailLatestRuntimePayloadText }}</pre>
              </div>
            </div>
            <div v-else class="empty-note">最近一次测试没有保存可展示的报告正文。</div>
          </section>

          <section class="version-detail-section">
            <div class="version-detail-section-head">
              <div class="version-detail-section-title">最近评估</div>
              <div class="version-detail-section-actions">
                <el-button
                  v-if="versionDetailVersion"
                  size="small"
                  :loading="reEvaluatingVersionDetail"
                  :disabled="!canReEvaluateVersionDetail"
                  @click="reEvaluateVersionFromDetail"
                >
                  {{ versionDetailReEvaluateButtonText }}
                </el-button>
                <el-button
                  v-if="versionDetailVersion"
                  type="primary"
                  size="small"
                  :loading="publishingVersionDetail"
                  :disabled="!canPublishVersionDetail"
                  @click="publishVersionFromDetail"
                >
                  {{ versionDetailPublishButtonText }}
                </el-button>
              </div>
            </div>
            <div v-if="versionDetailEvaluation" class="version-detail-evaluation-card">
              <div class="version-detail-summary-grid">
                <div class="version-detail-summary-item">
                  <span>结论</span>
                  <strong>{{ getEvaluationDecisionLabel(versionDetailEvaluation.decision) }}</strong>
                </div>
                <div class="version-detail-summary-item">
                  <span>总分</span>
                  <strong>{{ String(versionDetailEvaluation.scores?.overall ?? '-') }}</strong>
                </div>
                <div class="version-detail-summary-item">
                  <span>评估类型</span>
                  <strong>{{ versionDetailEvaluation.evaluation_type || '-' }}</strong>
                </div>
                <div class="version-detail-summary-item">
                  <span>更新时间</span>
                  <strong>{{ versionDetailEvaluation.updated_at || versionDetailEvaluation.created_at || '-' }}</strong>
                </div>
              </div>
              <div v-if="versionDetailLayerCards.length" class="evaluation-layer-grid">
                <div v-for="item in versionDetailLayerCards" :key="item.key" class="evaluation-layer-card">
                  <div class="evaluation-layer-title-row">
                    <strong>{{ item.label }}</strong>
                    <el-tag size="small" effect="plain" :type="item.tagType">{{ item.decisionLabel }}</el-tag>
                  </div>
                  <div class="evaluation-layer-meta">得分 {{ item.scoreText }}</div>
                  <div v-if="item.summaryItems.length" class="compact-list layer-summary-list">
                    <div v-for="entry in item.summaryItems" :key="`${item.key}-${entry}`" class="list-row">{{ entry }}</div>
                  </div>
                </div>
              </div>
              <div v-if="versionDetailBlockers.length" class="compact-list">
                <div v-for="(issue, index) in versionDetailBlockers" :key="`${index}-${issue}`" class="list-row list-row-danger">
                  阻断项 {{ index + 1 }}：{{ issue }}
                </div>
              </div>
              <div v-if="versionDetailWarnings.length" class="compact-list">
                <div v-for="(issue, index) in versionDetailWarnings" :key="`${index}-${issue}`" class="list-row list-row-warning">
                  提示项 {{ index + 1 }}：{{ issue }}
                </div>
              </div>
              <div v-if="versionDetailConfirmedIssues.length" class="compact-list">
                <div v-for="(issue, index) in versionDetailConfirmedIssues" :key="`${index}-${issue}`" class="list-row">
                  已证实问题 {{ index + 1 }}：{{ issue }}
                </div>
              </div>
              <div v-else-if="versionDetailInsufficientTitles.length" class="compact-list">
                <div v-for="(item, index) in versionDetailInsufficientTitles" :key="`${index}-${item}`" class="list-row">
                  证据不足 {{ index + 1 }}：{{ item }}
                </div>
              </div>
              <div v-if="versionDetailEvidenceIncomplete || versionDetailInvalidReasons.length" class="compact-list" style="margin-top: 10px;">
                <div v-if="versionDetailEvidenceIncomplete" class="list-row">当前评估未定案：存在关键证据缺口。</div>
                <div v-for="item in versionDetailInvalidReasons" :key="item" class="list-row">证据缺口：{{ item }}</div>
              </div>
              <div v-if="versionDetailWorkerCards.length" class="result-worker-list">
                <div v-for="item in versionDetailWorkerCards.slice(0, 4)" :key="item.key" class="result-worker-card">
                  <div class="result-worker-title-row">
                    <strong>{{ item.workerName }}</strong>
                    <span>{{ item.statusText }} / {{ item.sourceText }}</span>
                  </div>
                  <div v-if="item.summary" class="result-worker-summary">{{ item.summary }}</div>
                  <div v-for="group in item.artifactGroups" :key="`${item.key}-${group.key}`" class="result-worker-group">
                    <div class="result-worker-group-title">{{ group.label }}</div>
                    <div v-for="artifact in group.items" :key="`${item.key}-${group.key}-${artifact.title}`" class="result-worker-artifact">
                      <div class="result-worker-artifact-title">{{ artifact.title }}</div>
                      <div v-for="entry in artifact.detailLines" :key="entry" class="result-worker-artifact-content">{{ entry }}</div>
                      <div v-if="artifact.tagEntries.length" class="tag-wrap worker-artifact-tags">
                        <el-tag v-for="entry in artifact.tagEntries" :key="entry" class="tag-item" effect="plain">{{ entry }}</el-tag>
                      </div>
                      <div class="result-worker-artifact-actions">
                        <el-tag v-if="artifact.manualReview" size="small" effect="plain" :type="getManualReviewTagType(artifact.manualReview)">
                          {{ getManualReviewStatusLabel(artifact.manualReview) }}
                        </el-tag>
                        <el-button size="small" text @click="openEvaluationArtifactReviewDialog(artifact)">人工审核</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="!versionDetailConfirmedIssues.length && !versionDetailInsufficientTitles.length && !versionDetailEvidenceIncomplete && !versionDetailInvalidReasons.length" class="empty-note">最近评估没有记录问题项。</div>
            </div>
            <div v-else class="empty-note">当前版本还没有评估记录。</div>
          </section>
        </div>

        <div v-else class="empty-note">当前没有可展示的版本详情。</div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="evaluationArtifactReviewDialogVisible"
      width="min(560px, calc(100vw - 32px))"
      destroy-on-close
      title="人工审核证据项"
    >
      <div class="evaluation-review-form">
        <div class="compact-list">
          <div class="list-row">路径：{{ evaluationArtifactReviewForm.targetPath || '-' }}</div>
          <div class="list-row">标题：{{ evaluationArtifactReviewForm.targetTitle || '-' }}</div>
        </div>
        <div class="evaluation-review-field">
          <div class="evaluation-review-label">审核结果</div>
          <el-radio-group v-model="evaluationArtifactReviewForm.approved">
            <el-radio :label="true">误报，忽略该项</el-radio>
            <el-radio :label="false">保留问题项</el-radio>
          </el-radio-group>
        </div>
        <div class="evaluation-review-field">
          <div class="evaluation-review-label">审核原因</div>
          <el-input v-model="evaluationArtifactReviewForm.reason" type="textarea" :rows="3" placeholder="例如：该数值可由同报告内已标注来源的表格直接复核，属于误报。" />
        </div>
        <div class="evaluation-review-field">
          <div class="evaluation-review-label">补充说明</div>
          <el-input v-model="evaluationArtifactReviewForm.comment" type="textarea" :rows="2" placeholder="可选，补充人工判断依据。" />
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="evaluationArtifactReviewDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingEvaluationArtifactReview" @click="submitEvaluationArtifactReview">保存审核</el-button>
        </div>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
  type AgentEvaluationReport,
  type AgentEvaluationEvidenceArtifact,
  type AgentEvaluationEvidenceBundle,
  type AgentEvaluationSummary,
  type AgentEvaluationLayeredReview,
  type AgentEvaluationManualReview,
  type AgentProjectMemoryBindingSummary,
  type AgentEvaluationWorkerResult,
  type AgentSpec,
  type AgentSpecIOItem,
  type AgentVersion,
  type AgentWorkshopMessage,
  type AgentWorkshopSessionDetail,
  type AgentWorkshopVersionPrompt,
  getAgentEvaluationEvidenceBundle,
} from '@/api/agentWorkshop'

type NanobotToolEventCard = {
  key: string
  title: string
  detail: string
  statusLabel: string
  tone: 'info' | 'success' | 'warning'
}

type EvaluationArtifactView = {
  type: string
  title: string
  path: string
  detailLines: string[]
  tagEntries: string[]
  manualReview: AgentEvaluationManualReview | null
  artifactType: string
  findingId: string
  workerName: string
}

type NanobotStudioPersistedState = {
  nanobotSessionKey?: string
  sessionId?: string
  specId?: string
  specName?: string
  versionId?: string
  showNanobotThreadPanel?: boolean
  selectedThreadScope?: string
}

marked.setOptions({ breaks: true, gfm: true })

const NANOBOT_WORKSHOP_SESSION_PREFIX = 'embedded:nanobot-agent-studio:'
const NANOBOT_SKILLS = ['nanobot-agent-design']
const NANOBOT_STUDIO_STATE_STORAGE_KEY = 'nanobot-agent-studio:state'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
let suppressNextRouteInit = false
let pendingRouteSync = false

const composerText = ref('')
const agentItems = ref<AgentSpec[]>([])
const versionItemsBySpec = ref<Record<string, AgentVersion[]>>({})
const loadingSpecVersions = ref<Record<string, boolean>>({})
const expandedSpecIds = ref<string[]>([])
const selectedVersionId = ref('')
const currentSession = ref<AgentWorkshopSessionDetail | null>(null)
const standaloneSpec = ref<AgentSpec | null>(null)
const currentNanobotSessionKey = ref('')
const nanobotMessages = ref<AgentWorkshopMessage[]>([])
const nanobotDraftLink = ref<{ specId: string; specName: string; sessionId?: string } | null>(null)
const nanobotIterationBootstrapPending = ref(false)
const nanobotStreaming = ref(false)
const nanobotProgressHint = ref('')
const nanobotToolEvents = ref<NanobotToolEventCard[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
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
const evaluationArtifactReviewDialogVisible = ref(false)
const submittingEvaluationArtifactReview = ref(false)
const evaluationArtifactReviewForm = ref({
  evaluationId: '',
  targetPath: '',
  targetTitle: '',
  artifactType: '',
  findingId: '',
  workerName: '',
  approved: true,
  reason: '',
  comment: '',
})
const activeResultPanels = ref<string[]>(['draft'])
const loadingSeconds = ref(0)
const recentNanobotThreads = ref<EmbeddedNanobotThreadItem[]>([])
const loadingNanobotThreads = ref(false)
const showNanobotThreadPanel = ref(false)
const showAgentSidebar = ref(true)
const showStatusSidebar = ref(true)
const selectedThreadScope = ref('active')
const threadSearchText = ref('')
const selectedThreadAgentFilter = ref('all')
const selectedThreadTimeFilter = ref('all')

const sending = ref(false)
const refreshingDraft = ref(false)
const buildingVersion = ref(false)
const iteratingVersion = ref(false)
const loadingSession = ref(false)

let activeNanobotStreamController: AbortController | null = null
let loadingTimer: number | null = null
let persistThreadContextPromise: Promise<void> | null = null
let queuedThreadContextSignature: string | null = null
let lastPersistedThreadContextSignature = ''
let initFromRoutePromise: Promise<void> | null = null
const versionContextRequests = new Map<string, Promise<void>>()
const latestVersionContextRequests = new Map<string, Promise<void>>()
const sessionRequests = new Map<string, Promise<void>>()
const threadMessageRequests = new Map<string, Promise<boolean>>()
const THREAD_CONTEXT_PERSIST_DEBOUNCE_MS = 180

const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

const getThreadTimestamp = (thread?: EmbeddedNanobotThreadItem | null) => {
  const raw = String(thread?.updated_at || thread?.created_at || '').trim()
  if (!raw) return 0
  const timestamp = Date.parse(raw)
  return Number.isFinite(timestamp) ? timestamp : 0
}

const readPersistedStudioState = (): NanobotStudioPersistedState | null => {
  try {
    const raw = localStorage.getItem(NANOBOT_STUDIO_STATE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed as NanobotStudioPersistedState : null
  } catch {
    return null
  }
}

const clearPersistedStudioState = () => {
  try {
    localStorage.removeItem(NANOBOT_STUDIO_STATE_STORAGE_KEY)
  } catch {
    // Ignore storage failures and keep the page usable.
  }
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
    return marked.parse(content || '') as string
  } catch {
    return String(content || '')
  }
}

const copyRuntimePayloadJson = async () => {
  const text = versionDetailLatestRuntimePayloadText.value
  if (!text) {
    ElMessage.warning('当前没有可复制的结构化输出')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('结构化输出 JSON 已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

const openEvaluationArtifactReviewDialog = (artifact: any) => {
  if (!versionDetailEvaluation.value?.evaluation_id || !artifact?.path) {
    ElMessage.warning('当前证据项缺少可审核的路径信息')
    return
  }
  evaluationArtifactReviewForm.value = {
    evaluationId: versionDetailEvaluation.value.evaluation_id,
    targetPath: String(artifact.path || '').trim(),
    targetTitle: String(artifact.title || '').trim(),
    artifactType: String(artifact.artifactType || artifact.type || '').trim(),
    findingId: String(artifact.findingId || '').trim(),
    workerName: String(artifact.workerName || '').trim(),
    approved: artifact.manualReview ? Boolean(artifact.manualReview.approved) : true,
    reason: artifact.manualReview?.reason || '',
    comment: artifact.manualReview?.comment || '',
  }
  evaluationArtifactReviewDialogVisible.value = true
}

const submitEvaluationArtifactReview = async () => {
  const form = evaluationArtifactReviewForm.value
  if (!form.evaluationId || !form.targetPath) {
    ElMessage.warning('缺少待审核的证据项信息')
    return
  }
  if (!String(form.reason || '').trim()) {
    ElMessage.warning('请填写审核原因')
    return
  }

  submittingEvaluationArtifactReview.value = true
  try {
    const result = await agentWorkshopApi.reviewEvaluationArtifact(form.evaluationId, {
      target_path: form.targetPath,
      target_title: form.targetTitle,
      artifact_type: form.artifactType,
      finding_id: form.findingId,
      worker_name: form.workerName,
      approved: form.approved,
      reason: form.reason,
      comment: form.comment,
    })
    versionDetailEvaluation.value = result.evaluation
    if (latestVersion.value?.version_id && latestVersion.value.version_id === result.version_id) {
      latestEvaluation.value = result.evaluation
    }
    evaluationArtifactReviewDialogVisible.value = false
    ElMessage.success(result.publish_ready ? '人工审核已保存，误报已生效，当前可以直接发布' : '人工审核已保存')
  } catch (error: any) {
    ElMessage.error(error?.message || '保存人工审核失败')
  } finally {
    submittingEvaluationArtifactReview.value = false
  }
}

const getSpecIoText = (item: AgentSpecIOItem) => {
  if (typeof item === 'string') return item
  const name = String(item.name || '').trim()
  const descriptionText = String(item.description || '').trim()
  if (name && descriptionText && name !== descriptionText) {
    return `${name}：${descriptionText}`
  }
  return name || descriptionText
}

const buildThreadContext = (): EmbeddedNanobotThreadContext => {
  const versionId = String(selectedVersionId.value || latestVersion.value?.version_id || '').trim() || undefined
  const workflowId = versionId ? `agent_workshop_debug_${versionId}` : undefined
  const debugTemplateId = String(
    latestVersionPrompt.value?.template_id
    || latestVersion.value?.prompt_template_ref?.template_id
    || ''
  ).trim() || undefined
  return {
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
      await loadSession(sessionId, { syncNanobotThread: false })
    }
  } else if (specId) {
    const currentSpecId = String(displaySpec.value?.spec_id || '').trim()
    if (currentSpecId !== specId || !latestVersion.value) {
      try {
        standaloneSpec.value = await agentWorkshopApi.getSpec(specId)
        currentSession.value = null
        expandAgentBranch(specId)
        await ensureSpecVersionsLoaded(specId)
        await loadLatestVersionContext(specId)
      } catch {
        // Ignore stale draft references when restoring old context.
      }
    }
  }

  if (versionId) {
    selectedVersionId.value = versionId
    if (String(latestVersion.value?.version_id || '').trim() !== versionId || !latestVersionPrompt.value) {
      await loadVersionContext(versionId)
    }
  }
}

const persistThreadContext = async () => {
  const threadId = String(currentNanobotSessionKey.value || '').trim()
  if (!threadId || nanobotStreaming.value) return
  const signature = JSON.stringify({
    threadId,
    payload: {
      session_key: currentNanobotSessionKey.value,
      channel: 'agent_workshop' as const,
      thread_context: buildThreadContext(),
    },
  })

  if (signature === lastPersistedThreadContextSignature) {
    return
  }

  if (persistThreadContextPromise) {
    queuedThreadContextSignature = signature
    return persistThreadContextPromise
  }

  try {
    persistThreadContextPromise = (async () => {
      await sleep(THREAD_CONTEXT_PERSIST_DEBOUNCE_MS)

      const latestThreadId = String(currentNanobotSessionKey.value || '').trim()
      if (!latestThreadId || nanobotStreaming.value) {
        return
      }

      const latestPayload = {
        session_key: currentNanobotSessionKey.value,
        channel: 'agent_workshop' as const,
        thread_context: buildThreadContext(),
      }
      const latestSignature = JSON.stringify({ threadId: latestThreadId, payload: latestPayload })

      if (latestSignature === lastPersistedThreadContextSignature) {
        return
      }

      const authReady = await ensureNanobotContextAuth()
      if (!authReady) {
        return
      }

      await embeddedNanobotApi.updateThreadContext(latestThreadId, latestPayload)
      lastPersistedThreadContextSignature = latestSignature
      await loadNanobotThreads()
    })()
    await persistThreadContextPromise
  } catch {
    // Keep UI usable even if context persistence is temporarily unavailable.
  } finally {
    persistThreadContextPromise = null
    if (queuedThreadContextSignature && queuedThreadContextSignature !== lastPersistedThreadContextSignature) {
      const nextSignature = queuedThreadContextSignature
      queuedThreadContextSignature = null
      await persistThreadContext()
      if (nextSignature === lastPersistedThreadContextSignature) {
        queuedThreadContextSignature = null
      }
    } else {
      queuedThreadContextSignature = null
    }
  }
}

const mapDbMessagesToWorkshopMessages = (items: EmbeddedNanobotMessageItem[]): AgentWorkshopMessage[] => {
  return items.map(item => ({
    role: item.role === 'user' ? 'user' : 'assistant',
    content: normalizeAssistantDisplayText(String(item.content || '')),
    timestamp: String(item.created_at || ''),
  }))
}

const resetVersionContext = () => {
  latestVersion.value = null
  latestVersionPrompt.value = null
  latestEvaluation.value = null
}

const normalizeAssistantDisplayText = (value?: string | null) => {
  const text = String(value || '')
  if (!text) return ''
  return text
    .replace(/Nanobot Agent 工作台/g, 'Agent 工坊助手')
    .replace(/Nanobot 会话/g, '助手会话')
    .replace(/Embedded Nanobot/g, '工坊助手')
    .replace(/\bNanobot\b/g, '工坊助手')
}

const clearStudioState = (preserveStorage = false) => {
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
    activeNanobotStreamController = null
  }
  currentSession.value = null
  standaloneSpec.value = null
  currentNanobotSessionKey.value = ''
  nanobotMessages.value = []
  nanobotDraftLink.value = null
  nanobotIterationBootstrapPending.value = false
  nanobotStreaming.value = false
  nanobotProgressHint.value = ''
  nanobotToolEvents.value = []
  composerText.value = ''
  selectedVersionId.value = ''
  resetVersionContext()
  lastPersistedThreadContextSignature = ''
  queuedThreadContextSignature = null
  if (!preserveStorage) {
    clearPersistedStudioState()
  }
}

const persistState = () => {
  try {
    const payload: NanobotStudioPersistedState = {
      nanobotSessionKey: String(currentNanobotSessionKey.value || '').trim() || undefined,
      sessionId: String(currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim() || undefined,
      specId: String(displaySpec.value?.spec_id || nanobotDraftLink.value?.specId || '').trim() || undefined,
      specName: String(displaySpec.value?.name || nanobotDraftLink.value?.specName || '').trim() || undefined,
      versionId: String(selectedVersionId.value || latestVersion.value?.version_id || '').trim() || undefined,
      showNanobotThreadPanel: showNanobotThreadPanel.value,
      selectedThreadScope: selectedThreadScope.value,
    }
    localStorage.setItem(NANOBOT_STUDIO_STATE_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore storage failures and keep the page usable.
  }
}

const restoreState = (sessionKey?: string) => {
  const persisted = readPersistedStudioState()
  if (!persisted) return false

  showNanobotThreadPanel.value = Boolean(persisted.showNanobotThreadPanel)
  if (persisted.selectedThreadScope === 'active' || persisted.selectedThreadScope === 'archived') {
    selectedThreadScope.value = persisted.selectedThreadScope
  }

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

  return Boolean(restoredSessionKey || restoredSessionId || restoredSpecId)
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

const formatThreadMeta = (thread: EmbeddedNanobotThreadItem) => {
  const raw = String(thread.updated_at || thread.created_at || '').trim()
  if (!raw) return '未知时间'
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('zh-CN', { hour12: false })
}

const doesThreadMatchWorkspace = (
  thread?: EmbeddedNanobotThreadItem | null,
  options?: {
    sessionId?: string
    specId?: string
    versionId?: string
  },
) => {
  if (!thread) return false

  const sessionId = String(options?.sessionId || currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim()
  const specId = String(options?.specId || displaySpec.value?.spec_id || nanobotDraftLink.value?.specId || '').trim()
  const versionId = String(options?.versionId || selectedVersionId.value || latestVersion.value?.version_id || '').trim()

  const threadSessionId = String(thread.thread_context?.workshop_session_id || '').trim()
  const threadSpecId = String(thread.thread_context?.spec_id || '').trim()
  const threadVersionId = String(thread.thread_context?.version_id || '').trim()

  if (sessionId && threadSessionId && threadSessionId !== sessionId) return false
  if (specId && threadSpecId && threadSpecId !== specId) return false
  if (versionId && threadVersionId && threadVersionId !== versionId) return false

  if (sessionId && threadSessionId === sessionId) return true
  if (versionId && threadVersionId === versionId) return true
  if (specId && threadSpecId === specId) return true

  return !sessionId && !specId && !versionId
}

const findBestMatchingNanobotThread = (options?: {
  sessionId?: string
  specId?: string
  versionId?: string
  sessionKey?: string
}) => {
  const sessionId = String(options?.sessionId || '').trim()
  const specId = String(options?.specId || '').trim()
  const versionId = String(options?.versionId || '').trim()
  const sessionKey = String(options?.sessionKey || '').trim()
  const hasWorkspaceIdentity = Boolean(sessionId || specId || versionId)

  const ranked = recentNanobotThreads.value
    .map(thread => {
      const threadSessionId = String(thread.thread_context?.workshop_session_id || '').trim()
      const threadSpecId = String(thread.thread_context?.spec_id || '').trim()
      const threadVersionId = String(thread.thread_context?.version_id || '').trim()
      const threadSessionKey = String(thread.session_key || thread.thread_id || '').trim()
      let score = 0

      if (hasWorkspaceIdentity && !doesThreadMatchWorkspace(thread, { sessionId, specId, versionId })) {
        return null
      }

      if (!hasWorkspaceIdentity && sessionKey && threadSessionKey === sessionKey) score += 1000
      if (sessionId && threadSessionId === sessionId) score += 400
      if (specId && threadSpecId === specId) score += 120
      if (versionId && threadVersionId === versionId) score += 80

      if (!score) return null
      return {
        thread,
        score,
        timestamp: getThreadTimestamp(thread),
      }
    })
    .filter((item): item is { thread: EmbeddedNanobotThreadItem; score: number; timestamp: number } => Boolean(item))
    .sort((left, right) => right.score - left.score || right.timestamp - left.timestamp)

  return ranked[0]?.thread || null
}

const alignNanobotThreadWithWorkspace = async (options?: {
  silent?: boolean
  forceReload?: boolean
}) => {
  const sessionId = String(currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim()
  const specId = String(displaySpec.value?.spec_id || nanobotDraftLink.value?.specId || '').trim()
  const versionId = String(selectedVersionId.value || latestVersion.value?.version_id || '').trim()
  const currentSessionKey = String(currentNanobotSessionKey.value || '').trim()

  const matchedThread = findBestMatchingNanobotThread({
    sessionId,
    specId,
    versionId,
    sessionKey: currentSessionKey,
  })

  if (matchedThread) {
    const matchedSessionKey = String(matchedThread.session_key || matchedThread.thread_id || '').trim()
    if (options?.forceReload || matchedSessionKey !== currentSessionKey || !nanobotMessages.value.length) {
      return await loadNanobotThreadMessages({ threadId: matchedThread.thread_id, silent: options?.silent })
    }
    return true
  }

  if (currentSessionKey || nanobotMessages.value.length) {
    currentNanobotSessionKey.value = ''
    nanobotMessages.value = []
    nanobotToolEvents.value = []
    nanobotProgressHint.value = ''
    persistState()
  }
  return false
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

    try {
      const result = await embeddedNanobotApi.getThreadMessages(targetThread.thread_id)
      currentNanobotSessionKey.value = result.thread?.session_key || targetThread.session_key || targetThread.thread_id
      nanobotMessages.value = mapDbMessagesToWorkshopMessages(result.messages || [])
      await applyThreadContext(result.thread?.thread_context)
      persistState()
      return true
    } catch (error: any) {
      if (!options?.silent) {
        ElMessage.error(error?.message || '加载数据库会话历史失败')
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

const syncRoute = () => {
  if (nanobotStreaming.value) {
    pendingRouteSync = true
    return
  }

  const nextQuery: Record<string, string> = {}
  const sessionId = String(currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim()
  const specId = String(displaySpec.value?.spec_id || '').trim()
  if (sessionId) nextQuery.sessionId = sessionId
  else if (specId) nextQuery.specId = specId
  if (currentNanobotSessionKey.value) nextQuery.nanobotSessionKey = currentNanobotSessionKey.value

  if (
    String(route.query.sessionId || '') === String(nextQuery.sessionId || '')
    && String(route.query.specId || '') === String(nextQuery.specId || '')
    && String(route.query.nanobotSessionKey || '') === String(nextQuery.nanobotSessionKey || '')
  ) {
    return
  }

  suppressNextRouteInit = true
  pendingRouteSync = false
  router.replace({ path: '/workflow/nanobot-agent-studio', query: nextQuery })
}

const displaySpec = computed(() => currentSession.value?.current_spec_snapshot || standaloneSpec.value || null)
const activeNanobotThread = computed(() => {
  const sessionKey = String(currentNanobotSessionKey.value || '').trim()
  if (!sessionKey) return null
  return recentNanobotThreads.value.find(item => item.session_key === sessionKey || item.thread_id === sessionKey) || null
})
const activeNanobotThreadMatchesWorkspace = computed(() => {
  if (!nanobotMessages.value.length) return false
  return doesThreadMatchWorkspace(activeNanobotThread.value)
})
const displayedMessages = computed(() => {
  const workspaceSessionId = String(currentSession.value?.session_id || nanobotDraftLink.value?.sessionId || '').trim()
  const workspaceSpecId = String(displaySpec.value?.spec_id || nanobotDraftLink.value?.specId || '').trim()
  const workspaceVersionId = String(selectedVersionId.value || latestVersion.value?.version_id || '').trim()
  const hasWorkspaceIdentity = Boolean(workspaceSessionId || workspaceSpecId || workspaceVersionId)

  if (nanobotMessages.value.length && (!hasWorkspaceIdentity || activeNanobotThreadMatchesWorkspace.value)) {
    return nanobotMessages.value
  }
  return currentSession.value?.messages || []
})
const activeNanobotThreadId = computed(() => {
  const sessionKey = String(currentNanobotSessionKey.value || '').trim()
  if (!sessionKey) return ''
  const matched = recentNanobotThreads.value.find(item => item.session_key === sessionKey || item.thread_id === sessionKey)
  return matched?.thread_id || sessionKey
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
const hasWorkspaceContext = computed(() => Boolean(displaySpec.value || displayedMessages.value.length || latestVersion.value || latestEvaluation.value))
const currentWorkshopSessionId = computed(() => String(nanobotDraftLink.value?.sessionId || currentSession.value?.session_id || '').trim())
const activeAgentId = computed(() => String(displaySpec.value?.spec_id || '').trim())
const activeTreeKey = computed(() => selectedVersionId.value ? `version:${selectedVersionId.value}` : (activeAgentId.value ? `spec:${activeAgentId.value}` : ''))
const displaySpecOutputTags = computed(() => (displaySpec.value?.outputs || []).map(item => getSpecIoText(item)).filter(Boolean))
const pendingQuestions = computed(() => (currentSession.value?.pending_questions || []).filter(Boolean))
const completenessPercent = computed(() => Math.round((currentSession.value?.completeness_score || 0) * 100))
type WorkspacePhase = 'requirement-intake' | 'confirmation' | 'generation' | 'testing' | 'evaluation' | 'publish-ready' | 'published' | 'blocked'

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
        subtitle: `最近一次真数据测试结论：${evaluationDecisionText.value}。请根据结果决定是否继续修改或重新测试。`,
        publishHint: '当前已有真数据测试结论，但尚未满足正式发布条件。',
        nextAction: '根据最新评估问题继续修改，必要时重新发起测试。',
        actionGuideItems: ['在中间对话区继续和小助手讨论修改方案；版本类操作请使用页面按钮。'],
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
        actionGuideItems: ['如需继续优化，请使用页面中的下一轮/迭代入口，不再通过输入框触发。'],
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
const workspacePhaseLabel = computed(() => workspacePhaseMeta.value.label)
const draftStatusText = computed(() => workspacePhaseMeta.value.label)
const focusSubtitle = computed(() => workspacePhaseMeta.value.subtitle)
const versionOutputFields = computed(() => Object.keys(latestVersion.value?.output_schema?.properties || {}))
const promptSections = computed(() => {
  const content = latestVersionPrompt.value?.content
  if (!content) return []
  return [
    { key: 'system_prompt', label: 'System Prompt', value: String(content.system_prompt || '').trim() },
    { key: 'user_prompt', label: 'User Prompt', value: String(content.user_prompt || '').trim() },
    { key: 'output_format', label: '输出格式', value: String(content.output_format || '').trim() },
  ].filter(item => item.value)
})
const versionDetailPromptSections = computed(() => {
  const content = versionDetailPrompt.value?.content
  if (!content) return []
  return [
    { key: 'system_prompt', label: 'System Prompt', value: String(content.system_prompt || '').trim() },
    { key: 'user_prompt', label: 'User Prompt', value: String(content.user_prompt || '').trim() },
    { key: 'tool_guidance', label: '工具使用约束', value: String(content.tool_guidance || '').trim() },
    { key: 'analysis_requirements', label: '分析要求', value: String(content.analysis_requirements || '').trim() },
    { key: 'output_format', label: '输出格式', value: String(content.output_format || '').trim() },
    { key: 'constraints', label: '额外约束', value: String(content.constraints || '').trim() },
  ].filter(item => item.value)
})
const versionDetailOutputFieldText = computed(() => {
  if (!versionDetailVersion.value) return '-'
  const outputFields = Object.keys(versionDetailVersion.value.output_schema?.properties || {})
  if (outputFields.length) return outputFields.join(' / ')
  return String(versionDetailVersion.value.agent_metadata?.output_field || '-').trim() || '-'
})
const iterationReminderMessage = computed(() => {
  const messages = currentSession.value?.messages || []
  const matched = [...messages].reverse().find(item => item.role === 'assistant' && String(item.content || '').includes('上一轮评估摘要'))
  return matched?.content || ''
})
const iterationImprovementItems = computed(() => pendingQuestions.value.slice(0, 4))
const hasIterationContext = computed(() => Boolean(iterationReminderMessage.value || iterationImprovementItems.value.length))
const getEvaluationEvidenceBundle = (evaluation?: AgentEvaluationReport | null): AgentEvaluationEvidenceBundle | null => {
  return getAgentEvaluationEvidenceBundle(evaluation)
}
const getEvaluationLayeredReview = (evaluation?: AgentEvaluationReport | null): AgentEvaluationLayeredReview | null => {
  const layeredReview = evaluation?.details?.layered_review
  if (layeredReview && typeof layeredReview === 'object') {
    return layeredReview as AgentEvaluationLayeredReview
  }
  return null
}
const getConfirmedIssues = (evaluation?: AgentEvaluationReport | null) => {
  const bundle = getEvaluationEvidenceBundle(evaluation)
  const officialIssues = Array.isArray(bundle?.official_issues) ? bundle.official_issues.filter(Boolean) : []
  if (officialIssues.length) return officialIssues
  return Array.isArray(evaluation?.issues) ? evaluation.issues.filter(Boolean) : []
}
const getBlockerIssues = (evaluation?: AgentEvaluationReport | null) => {
  const layeredReview = getEvaluationLayeredReview(evaluation)
  const blockers = Array.isArray(layeredReview?.blockers) ? layeredReview.blockers.filter(Boolean) : []
  if (blockers.length) return blockers
  const detailBlockers = evaluation?.details?.blocker_issues
  if (Array.isArray(detailBlockers) && detailBlockers.length) return detailBlockers.filter(Boolean)
  return getConfirmedIssues(evaluation)
}
const getWarningIssues = (evaluation?: AgentEvaluationReport | null) => {
  const layeredReview = getEvaluationLayeredReview(evaluation)
  const warnings = Array.isArray(layeredReview?.warnings) ? layeredReview.warnings.filter(Boolean) : []
  if (warnings.length) return warnings
  const detailWarnings = evaluation?.details?.warning_issues
  return Array.isArray(detailWarnings) ? detailWarnings.filter(Boolean) : []
}
const getLayerDecisionLabel = (decision?: string) => {
  if (decision === 'pass') return '通过'
  if (decision === 'pass_with_warnings') return '通过但有提示'
  if (decision === 'revise') return '需修订'
  if (decision === 'reject') return '拒绝'
  return decision || '未评估'
}
const getLayerDecisionTagType = (decision?: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (decision === 'pass') return 'success'
  if (decision === 'pass_with_warnings' || decision === 'revise') return 'warning'
  if (decision === 'reject') return 'danger'
  return 'info'
}
const buildLayerCards = (evaluation?: AgentEvaluationReport | null) => {
  const layeredReview = getEvaluationLayeredReview(evaluation)
  if (!layeredReview) return []
  const layers = [
    {
      key: 'content_quality',
      label: '内容质量',
      layer: layeredReview.content_quality,
    },
    {
      key: 'publish_readiness',
      label: '发布就绪',
      layer: layeredReview.publish_readiness,
    },
  ]
  return layers
    .filter(item => item.layer)
    .map(item => ({
      key: item.key,
      label: item.label,
      decisionLabel: getLayerDecisionLabel(item.layer?.decision),
      tagType: getLayerDecisionTagType(item.layer?.decision),
      scoreText: typeof item.layer?.score === 'number' ? item.layer.score.toFixed(2) : '-',
      summaryItems: [
        ...(Array.isArray(item.layer?.blockers) ? item.layer?.blockers.slice(0, 2).map(entry => `阻断：${entry}`) : []),
        ...(Array.isArray(item.layer?.warnings) ? item.layer?.warnings.slice(0, 2).map(entry => `提示：${entry}`) : []),
      ],
    }))
}
const getInsufficientEvidenceTitles = (evaluation?: AgentEvaluationReport | null) => {
  const bundle = getEvaluationEvidenceBundle(evaluation)
  if (!Array.isArray(bundle?.insufficient_evidence)) return []
  return bundle.insufficient_evidence.map(item => item.title || '未命名项').filter(Boolean)
}
const getWorkerStatusText = (status?: string) => {
  if (status === 'confirmed') return '已证实'
  if (status === 'disproved') return '已排除'
  if (status === 'insufficient_evidence') return '证据不足'
  return status || '未知'
}
const getWorkerSourceText = (source?: string) => {
  if (source === 'nanobot') return '工坊助手'
  if (source === 'nanobot-fallback') return '工坊助手回退'
  if (source === 'rules') return '规则'
  return source || '未知来源'
}
const truncateArtifactContent = (value?: string, limit = 160) => {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}
const getArtifactTypeLabel = (type?: string) => {
  const normalized = String(type || '').trim()
  if (normalized === 'tool_trace') return '工具轨迹'
  if (normalized === 'tool_trace_gap') return '工具轨迹缺口'
  if (normalized === 'output_payload') return '输出载荷'
  if (normalized === 'rule_breakdown') return '规则评估明细'
  if (normalized === 'traceability_gap') return '可追溯性缺口'
  if (normalized === 'execution_plan_review') return '执行计划验收'
  if (normalized === 'prompt_gap') return 'Prompt 证据缺口'
  return normalized || '其他证据'
}
const normalizeArtifactMetadataEntries = (metadata?: Record<string, any>) => {
  if (!metadata || typeof metadata !== 'object') return []
  return Object.entries(metadata)
    .filter(([key]) => key !== 'manual_review')
    .flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.slice(0, 3).map(entry => `${key}: ${typeof entry === 'string' ? entry : JSON.stringify(entry)}`)
      }
      return [`${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`]
    })
    .filter(Boolean)
    .slice(0, 4)
}
const getArtifactManualReview = (metadata?: Record<string, any>): AgentEvaluationManualReview | null => {
  const review = metadata?.manual_review
  return review && typeof review === 'object' ? review as AgentEvaluationManualReview : null
}
const getManualReviewStatusLabel = (review?: AgentEvaluationManualReview | null) => {
  if (!review) return ''
  return review.approved ? '已标记误报' : '保留问题项'
}
const getManualReviewTagType = (review?: AgentEvaluationManualReview | null): 'success' | 'danger' | 'info' => {
  if (!review) return 'info'
  return review.approved ? 'success' : 'danger'
}
const buildArtifactView = (
  item?: AgentEvaluationEvidenceArtifact | null,
  context?: { findingId?: string; workerName?: string },
): EvaluationArtifactView => {
  const type = String(item?.artifact_type || 'evidence_artifact').trim() || 'evidence_artifact'
  const title = String(item?.title || item?.artifact_type || '未命名证据').trim() || '未命名证据'
  const path = String(item?.path || '').trim()
  const content = truncateArtifactContent(String(item?.content || ''))
  const metadata = item?.metadata && typeof item.metadata === 'object' ? item.metadata as Record<string, any> : {}
  const metadataEntries = normalizeArtifactMetadataEntries(metadata)
  const manualReview = getArtifactManualReview(metadata)
  const detailLines: string[] = []

  if (type === 'tool_trace') {
    const toolName = String(metadata.tool_name || '').trim()
    const success = typeof metadata.success === 'boolean' ? (metadata.success ? 'success=true' : 'success=false') : ''
    if (toolName || success) detailLines.push([toolName, success].filter(Boolean).join(' / '))
  } else if (type === 'traceability_gap') {
    if (metadata.value) detailLines.push(`数值：${metadata.value}`)
    if (metadata.source_type) detailLines.push(`来源类型：${metadata.source_type}`)
    if (metadata.line_number) {
      detailLines.push(`报告位置：第 ${metadata.line_number} 行${metadata.column_number ? `，第 ${metadata.column_number} 列` : ''}`)
    }
    if (metadata.line_excerpt) {
      detailLines.push(`行内容：${metadata.line_excerpt}`)
    }
  } else if (type === 'execution_plan_review' && typeof metadata.issues_count !== 'undefined') {
    detailLines.push(`问题数：${metadata.issues_count}`)
  }

  if (path) detailLines.push(`路径：${path}`)
  if (content) detailLines.push(content)

  return {
    type,
    title,
    path,
    detailLines: detailLines.filter(Boolean),
    tagEntries: metadataEntries.filter(Boolean),
    manualReview,
    artifactType: type,
    findingId: String(context?.findingId || '').trim(),
    workerName: String(context?.workerName || '').trim(),
  }
}
const normalizeWorkerArtifacts = (artifacts?: AgentEvaluationEvidenceArtifact[] | null, context?: { findingId?: string; workerName?: string }) => {
  if (!Array.isArray(artifacts)) return []
  return artifacts
    .map(item => buildArtifactView(item, context))
    .filter(item => item.title || item.detailLines.length || item.tagEntries.length)
}
const getWorkerResultCards = (evaluation?: AgentEvaluationReport | null) => {
  const bundle = getEvaluationEvidenceBundle(evaluation)
  if (!Array.isArray(bundle?.worker_results)) return []
  return bundle.worker_results.map((item: AgentEvaluationWorkerResult) => ({
    key: `${item.task_id}-${item.worker_name}`,
    workerName: item.worker_name || '未命名 worker',
    statusText: getWorkerStatusText(item.status),
    sourceText: getWorkerSourceText(item.source),
    summary: String(item.summary || '').trim(),
    artifactGroups: Object.values(normalizeWorkerArtifacts(item.artifacts, { findingId: item.finding_id, workerName: item.worker_name }).reduce((groups, artifact) => {
      const key = artifact.type
      if (!groups[key]) {
        groups[key] = {
          key,
          label: getArtifactTypeLabel(key),
          items: [],
        }
      }
      groups[key].items.push(artifact)
      return groups
    }, {} as Record<string, { key: string; label: string; items: EvaluationArtifactView[] }>)).map(group => ({
      ...group,
      items: group.items.slice(0, 2),
    })),
  }))
}
const getInvalidReasons = (evaluation?: AgentEvaluationReport | null) => {
  const bundle = getEvaluationEvidenceBundle(evaluation)
  return Array.isArray(bundle?.invalid_reasons) ? bundle.invalid_reasons.filter(Boolean) : []
}
const isEvaluationEvidenceIncomplete = (evaluation?: AgentEvaluationReport | null) => {
  const bundle = getEvaluationEvidenceBundle(evaluation)
  const status = String(bundle?.evaluation_status || evaluation?.details?.evaluation_status || '').trim()
  return status === 'evidence_incomplete'
}
const getEvaluationRuntimeResult = (evaluation?: AgentEvaluationReport | null) => {
  const runtimeResult = evaluation?.details?.runtime_result
  if (runtimeResult && typeof runtimeResult === 'object') {
    return runtimeResult as Record<string, any>
  }
  return null
}
const getVersionRuntimeResult = (version?: AgentVersion | null) => {
  const runtimeResult = version?.runtime_result
  if (runtimeResult && typeof runtimeResult === 'object') {
    return runtimeResult as Record<string, any>
  }

  const debugResult = version?.debug_result
  if (debugResult && typeof debugResult === 'object') {
    const rawResult = debugResult.raw_result && typeof debugResult.raw_result === 'object'
      ? debugResult.raw_result as Record<string, any>
      : {}
    const debugPrompt = debugResult.debug_prompt && typeof debugResult.debug_prompt === 'object'
      ? debugResult.debug_prompt as Record<string, any>
      : {}
    return {
      output_text: String(debugResult.report || '').trim(),
      output_payload: rawResult,
      debug_prompt: debugPrompt,
      tool_trace: debugPrompt.tool_trace || rawResult.tool_trace || [],
      symbol: debugResult.symbol,
      analysis_date: debugResult.analysis_date,
      user_goal: debugResult.metadata?.user_goal,
    }
  }

  return null
}
const stringifyRuntimePayload = (payload: unknown) => {
  if (payload == null) return ''
  if (typeof payload === 'string') return payload.trim()
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}
const deriveRuntimeReportText = (evaluation?: AgentEvaluationReport | null, version?: AgentVersion | null) => {
  const runtimeResult = getEvaluationRuntimeResult(evaluation) || getVersionRuntimeResult(version)
  const outputText = String(runtimeResult?.output_text || '').trim()
  if (outputText) return outputText

  const outputPayload = runtimeResult?.output_payload
  if (outputPayload && typeof outputPayload === 'object') {
    const preferredText = [
      outputPayload.llm_final_response,
      outputPayload.analysis_report,
      outputPayload.report,
    ].find(item => typeof item === 'string' && String(item).trim())
    if (typeof preferredText === 'string') {
      return preferredText.trim()
    }
    const firstStringValue = Object.values(outputPayload).find(item => typeof item === 'string' && String(item).trim())
    if (typeof firstStringValue === 'string') {
      return firstStringValue.trim()
    }
  }

  if (evaluation) {
    return String(evaluation.details?.parsed_output_excerpt || '').trim()
  }

  return ''
}
const deriveRuntimePayloadText = (evaluation?: AgentEvaluationReport | null, version?: AgentVersion | null) => {
  const runtimeResult = getEvaluationRuntimeResult(evaluation) || getVersionRuntimeResult(version)
  return stringifyRuntimePayload(runtimeResult?.output_payload).trim()
}
const deriveRuntimeMeta = (evaluation?: AgentEvaluationReport | null, version?: AgentVersion | null) => {
  const runtimeResult = getEvaluationRuntimeResult(evaluation) || getVersionRuntimeResult(version)
  return [
    runtimeResult?.symbol ? `标的：${String(runtimeResult.symbol).trim()}` : '',
    runtimeResult?.analysis_date ? `分析日期：${String(runtimeResult.analysis_date).trim()}` : '',
    runtimeResult?.user_goal ? `测试目标：${String(runtimeResult.user_goal).trim()}` : '',
  ].filter(Boolean)
}
const evaluationDecisionText = computed(() => {
  if (latestEvaluation.value?.decision === 'pass') return '通过'
  if (latestEvaluation.value?.decision === 'reject') return '拒绝'
  if (latestEvaluation.value?.decision === 'revise') return '需要修改'
  return latestEvaluation.value?.decision || '未评估'
})
const overallScoreText = computed(() => String(latestEvaluation.value?.scores?.overall ?? '-'))
const latestEvaluationConfirmedIssues = computed(() => getConfirmedIssues(latestEvaluation.value))
const latestEvaluationBlockers = computed(() => getBlockerIssues(latestEvaluation.value))
const latestEvaluationWarnings = computed(() => getWarningIssues(latestEvaluation.value))
const latestEvaluationLayerCards = computed(() => buildLayerCards(latestEvaluation.value))
const latestEvaluationInsufficientTitles = computed(() => getInsufficientEvidenceTitles(latestEvaluation.value))
const latestEvaluationWorkerCards = computed(() => getWorkerResultCards(latestEvaluation.value))
const latestEvaluationInvalidReasons = computed(() => getInvalidReasons(latestEvaluation.value))
const latestEvaluationEvidenceIncomplete = computed(() => isEvaluationEvidenceIncomplete(latestEvaluation.value))
const versionDetailConfirmedIssues = computed(() => getConfirmedIssues(versionDetailEvaluation.value))
const versionDetailBlockers = computed(() => getBlockerIssues(versionDetailEvaluation.value))
const versionDetailWarnings = computed(() => getWarningIssues(versionDetailEvaluation.value))
const versionDetailLayerCards = computed(() => buildLayerCards(versionDetailEvaluation.value))
const versionDetailInsufficientTitles = computed(() => getInsufficientEvidenceTitles(versionDetailEvaluation.value))
const versionDetailWorkerCards = computed(() => getWorkerResultCards(versionDetailEvaluation.value))
const versionDetailInvalidReasons = computed(() => getInvalidReasons(versionDetailEvaluation.value))
const versionDetailEvidenceIncomplete = computed(() => isEvaluationEvidenceIncomplete(versionDetailEvaluation.value))
const versionDetailLatestRuntimeReportText = computed(() => deriveRuntimeReportText(versionDetailEvaluation.value, versionDetailVersion.value))
const versionDetailLatestRuntimePayloadText = computed(() => deriveRuntimePayloadText(versionDetailEvaluation.value, versionDetailVersion.value))
const versionDetailLatestRuntimeMeta = computed(() => deriveRuntimeMeta(versionDetailEvaluation.value, versionDetailVersion.value))
const canReEvaluateVersionDetail = computed(() => {
  if (!versionDetailVersion.value) return false
  return !versionDetailLoading.value && !reEvaluatingVersionDetail.value && !publishingVersionDetail.value
})
const versionDetailReEvaluateButtonText = computed(() => reEvaluatingVersionDetail.value ? '基于当前证据重新评估中...' : '基于当前证据重新评估')
const canPublishVersionDetail = computed(() => {
  if (!versionDetailVersion.value) return false
  if (publishingVersionDetail.value || versionDetailLoading.value || reEvaluatingVersionDetail.value) return false
  if (versionDetailVersion.value.status === 'active') return false
  return versionDetailEvaluation.value?.decision === 'pass'
})
const versionDetailPublishButtonText = computed(() => {
  if (publishingVersionDetail.value) return '发布中...'
  if (versionDetailVersion.value?.status === 'active') return '已正式发布'
  if (versionDetailEvaluation.value?.decision === 'pass') return '手动确认发布'
  return '等待评估通过'
})
const versionPromptProjectMemorySummary = computed(() => latestVersion.value?.prompt_template_project_memory_binding_summary || null)
const latestEvaluationSummaryForDisplay = computed(() => getEvaluationSummary(latestEvaluation.value) || latestVersion.value?.last_evaluation_summary || null)
const latestEvaluationProjectMemorySummary = computed(() => getProjectMemoryBindingSummary(latestEvaluation.value) || latestEvaluationSummaryForDisplay.value?.project_memory_binding || null)
const versionDetailPromptProjectMemorySummary = computed(() => versionDetailVersion.value?.prompt_template_project_memory_binding_summary || null)
const versionDetailEvaluationSummaryForDisplay = computed(() => getEvaluationSummary(versionDetailEvaluation.value) || versionDetailVersion.value?.last_evaluation_summary || null)
const versionDetailEvaluationProjectMemorySummary = computed(() => getProjectMemoryBindingSummary(versionDetailEvaluation.value) || versionDetailEvaluationSummaryForDisplay.value?.project_memory_binding || null)
const hasPassedLatestEvaluation = computed(() => latestEvaluation.value?.decision === 'pass')
const draftStatusTagType = computed(() => workspacePhaseMeta.value.tagType)
const publishStatusHint = computed(() => workspacePhaseMeta.value.publishHint)
const workflowStageItems = computed(() => {
  const phase = workspacePhase.value
  const hasVersion = Boolean(latestVersion.value)
  const versionStatus = latestVersion.value?.status
  return [
    {
      key: 'generated',
      title: '1. 测试版本',
      description: hasVersion
        ? `已创建测试版本 v${latestVersion.value?.version}。`
        : generationReady.value
          ? '需求已齐备，等待补建测试版本。'
          : '尚无测试版本。',
      state: hasVersion
        ? 'done'
        : phase === 'generation'
          ? 'current'
          : phase === 'testing' || phase === 'evaluation' || phase === 'publish-ready' || phase === 'published'
            ? 'done'
            : 'pending',
    },
    {
      key: 'verified',
      title: '2. 真数据测试',
      description: phase === 'publish-ready' || phase === 'published'
        ? '最新一次真数据测试已通过。'
        : latestEvaluation.value
          ? `最近评估结论：${evaluationDecisionText.value}。`
          : versionStatus === 'testing'
            ? '已进入 testing，可直接发起真数据测试。'
            : '尚未开始真数据测试。',
      state: phase === 'publish-ready' || phase === 'published'
        ? 'done'
        : phase === 'testing' || phase === 'evaluation'
          ? 'current'
          : hasVersion
            ? 'current'
            : 'pending',
    },
    {
      key: 'published',
      title: '3. 正式发布',
      description: versionStatus === 'active' ? '当前版本已经是 active。' : '只有真数据测试评估通过后的 testing 版本才能正式发布。',
      state: phase === 'published'
        ? 'done'
        : phase === 'publish-ready'
          ? 'current'
          : 'pending',
    },
  ]
})
const nextRequiredAction = computed(() => workspacePhaseMeta.value.nextAction)
const phaseActionGuideItems = computed(() => workspacePhaseMeta.value.actionGuideItems)
const realStateGuardText = computed(() => {
  const specStatus = displaySpec.value?.status || 'draft'
  const versionStatus = latestVersion.value?.status || 'none'
  const evaluationStatus = latestEvaluation.value ? evaluationDecisionText.value : '未评估'
  return [
    `真实状态：spec=${specStatus}；version=${versionStatus}；evaluation=${evaluationStatus}。`,
    '状态约束：进入 testing 只代表已进入真数据测试阶段，不代表已经通过；只有最新一次真数据测试评估为 pass 的 testing 版本，才能声称“可正式发布”。',
    '如果当前仍是 draft，只能说“待补建测试版本”；如果当前是 testing 但评估未通过，只能说“测试中/待修正”，不能说“已通过”。',
    '测试验收约束：默认直接用真实股票做真数据测试；测试通过就是通过，测试不通过就是失败或待修正，不能把临时脚本、MongoDB 直查、stdout/file 探测当作正式结论。',
    '失败处理约束：如果真数据测试失败，只能把它表述为 Agent Workshop 测试链路问题、运行时问题或系统默认模型配置问题；不要把失败改写成“去直接调用已注册 Agent”或“改走蓝图复用路径”。',
  ].join('\n')
})
const composerPlaceholder = computed(() => {
  if (!hasWorkspaceContext.value) {
    return '直接描述你想创建的 Agent，例如：做一个能跟踪财报变化并总结风险提示的助手。'
  }
  return '继续补充你的要求，或告诉 Nanobot 哪些地方需要修改。'
})
const sendButtonText = computed(() => hasWorkspaceContext.value ? '发送' : '开始创建')
const nanobotThreadAgentOptions = computed(() => {
  const seen = new Map<string, string>()
  for (const item of recentNanobotThreads.value) {
    const specId = String(item.thread_context?.spec_id || '').trim()
    const specName = String(item.thread_context?.spec_name || '').trim()
    if (!specId || seen.has(specId)) continue
    seen.set(specId, specName || specId)
  }
  return Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
})
const filteredNanobotThreads = computed(() => {
  const keyword = String(threadSearchText.value || '').trim().toLowerCase()
  const now = Date.now()
  const windowMap: Record<string, number> = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
  }
  return recentNanobotThreads.value.filter(item => {
    if (selectedThreadAgentFilter.value !== 'all') {
      if (String(item.thread_context?.spec_id || '').trim() !== selectedThreadAgentFilter.value) {
        return false
      }
    }

    if (selectedThreadTimeFilter.value !== 'all') {
      const timestamp = Date.parse(String(item.updated_at || item.created_at || ''))
      const range = windowMap[selectedThreadTimeFilter.value]
      if (!Number.isFinite(timestamp) || !range || now - timestamp > range) {
        return false
      }
    }

    if (!keyword) return true
    const haystack = [
      item.title,
      item.last_user_message,
      item.summary,
      item.thread_context?.spec_name,
    ].join(' ').toLowerCase()
    return haystack.includes(keyword)
  })
})

type ContextChoiceOption = {
  order: number
  label: string
  text: string
}

type ContextualReplyIntent = {
  selectionIndex: number
  selectedOption: string
  optionsText: string
}

const CHINESE_NUMERAL_INDEX_MAP: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
}

const getLatestAssistantMessageContent = () => {
  const matched = [...displayedMessages.value].reverse().find(item => item.role === 'assistant' && String(item.content || '').trim())
  return String(matched?.content || '').trim()
}

const normalizeContextLines = (content: string) => {
  return String(content || '')
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
}

const isChoiceCueLine = (line: string) => /(你想要|你是指|请选择|请确认.*意图|下一步操作|可选操作|请告诉我下一步|请确认你的选择)/.test(line)

const isChoiceTerminatorLine = (line: string) => /^(请告诉我|请确认|告诉我|请回复|回复我|说明你的选择|请说明下一步)/.test(line)

const stripChoicePrefix = (line: string) => {
  return line
    .replace(/^[-*•]+\s*/, '')
    .replace(/^([A-Za-z]|\d+|第[一二三四五六七八九十]+(?:项|个)?|[一二三四五六七八九十])[\)\.、：:．]\s*/, '')
    .trim()
}

const extractContextChoiceOptions = (content: string): ContextChoiceOption[] => {
  const lines = normalizeContextLines(content)
  if (!lines.length) return []

  let startIndex = -1
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    if (isChoiceCueLine(lines[index])) {
      startIndex = index + 1
      break
    }
  }

  const candidateLines = (startIndex >= 0 ? lines.slice(startIndex) : lines.slice(-6))
  const options: ContextChoiceOption[] = []

  for (const line of candidateLines) {
    if (isChoiceTerminatorLine(line)) break
    if (/^(当前状态|Spec ID|Session ID|Version|项目\s*状态|状态说明|📊|✅|⚠️|❌)/.test(line)) continue

    const explicitLabelMatch = line.match(/^([A-Za-z]|\d+|第[一二三四五六七八九十]+(?:项|个)?|[一二三四五六七八九十])[\)\.、：:．]\s*(.+)$/)
    if (explicitLabelMatch) {
      options.push({
        order: options.length + 1,
        label: explicitLabelMatch[1],
        text: explicitLabelMatch[2].trim(),
      })
      continue
    }

    if (line.includes(' - ') || line.includes('：') || line.includes(':')) {
      options.push({
        order: options.length + 1,
        label: String(options.length + 1),
        text: stripChoicePrefix(line),
      })
      continue
    }

    if (candidateLines.length <= 5 && line.length <= 48) {
      options.push({
        order: options.length + 1,
        label: String(options.length + 1),
        text: stripChoicePrefix(line),
      })
    }
  }

  return options.filter(item => item.text)
}

const resolveSelectionIndex = (message: string) => {
  const normalized = String(message || '')
    .trim()
    .replace(/[\s\u3000'"“”‘’。！？!?,，；;：:]/g, '')
    .toLowerCase()

  if (!normalized || normalized.length > 12) return null
  if (/^\d+$/.test(normalized)) {
    const value = Number(normalized)
    return Number.isFinite(value) && value > 0 ? value : null
  }
  if (/^[a-z]$/.test(normalized)) {
    return normalized.charCodeAt(0) - 96
  }

  const ordinalMatch = normalized.match(/^第([一二三四五六七八九十]+)(项|个)?$/)
  if (ordinalMatch) {
    return CHINESE_NUMERAL_INDEX_MAP[ordinalMatch[1]] || null
  }

  if (CHINESE_NUMERAL_INDEX_MAP[normalized]) {
    return CHINESE_NUMERAL_INDEX_MAP[normalized]
  }

  return null
}

const resolveContextualReplyIntent = (message: string): ContextualReplyIntent | null => {
  const selectionIndex = resolveSelectionIndex(message)
  if (!selectionIndex) return null

  const latestAssistantMessage = getLatestAssistantMessageContent()
  if (!latestAssistantMessage) return null

  const options = extractContextChoiceOptions(latestAssistantMessage)
  if (options.length < selectionIndex) return null

  const selectedOption = options[selectionIndex - 1]
  return {
    selectionIndex,
    selectedOption: selectedOption.text,
    optionsText: options.map(item => `${item.order}. ${item.text}`).join('\n'),
  }
}

const getSpecStatusLabel = (spec?: AgentSpec | null) => {
  const status = String(spec?.status || '').trim()
  const specId = String(spec?.spec_id || '').trim()

  if (status === 'archived') return '已归档'
  if (status === 'active') return '已发布'
  if (specId && specId === activeAgentId.value) {
    return workspacePhaseMeta.value.label
  }
  if (spec?.current_version_id) return '待测试'
  return '需求中'
}

const getSpecTagType = (spec?: AgentSpec | null) => {
  const status = String(spec?.status || '').trim()
  const specId = String(spec?.spec_id || '').trim()

  if (status === 'archived') return 'info'
  if (status === 'active') return 'success'
  if (specId && specId === activeAgentId.value) {
    return workspacePhaseMeta.value.tagType
  }
  if (spec?.current_version_id) return 'success'
  return 'primary'
}

const getSpecMetaText = (spec?: AgentSpec | null) => {
  const status = String(spec?.status || '').trim()
  const specId = String(spec?.spec_id || '').trim()

  if (status === 'archived') return '当前已归档'
  if (status === 'active') return '当前已有正式版本'
  if (spec?.current_version_id) return '当前已有测试版本'
  if (specId && specId === activeAgentId.value) {
    if (workspacePhase.value === 'confirmation') return '仍有待确认点'
    if (workspacePhase.value === 'blocked') return '当前不可继续'
    if (workspacePhase.value === 'generation') return '等待补建测试版本'
  }
  return '暂无测试版本'
}

const getVersionStatusLabel = (version?: AgentVersion | null) => {
  const status = String(version?.status || '').trim()
  const versionId = String(version?.version_id || '').trim()

  if (status === 'active') return '已发布'
  if (status === 'archived') return '已归档'
  if (status === 'testing') {
    if (versionId && versionId === latestVersion.value?.version_id && hasPassedLatestEvaluation.value) {
      return '待确认发布'
    }
    return '真数据测试中'
  }
  if (status === 'draft') return '草稿'
  return status || '草稿'
}

const getVersionTagType = (version?: AgentVersion | null) => {
  const status = String(version?.status || '').trim()
  const versionId = String(version?.version_id || '').trim()

  if (status === 'active') return 'success'
  if (status === 'archived') return 'info'
  if (status === 'testing') {
    if (versionId && versionId === latestVersion.value?.version_id && hasPassedLatestEvaluation.value) {
      return 'success'
    }
    return 'warning'
  }
  return 'primary'
}

const formatDisplayTime = (value?: string | null) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('zh-CN', { hour12: false })
}

const getProjectMemorySummaryTagType = (status?: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'pass') return 'success'
  if (status === 'evidence_incomplete') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getProjectMemorySummaryStatusText = (status?: string) => {
  if (status === 'pass') return '已绑定'
  if (status === 'failed') return '缺失'
  if (status === 'evidence_incomplete') return '证据不足'
  if (status === 'not_enabled') return '未启用'
  return status || '未知'
}

const getEvaluationDecisionTagType = (decision?: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (decision === 'pass') return 'success'
  if (decision === 'reject') return 'danger'
  if (decision === 'revise') return 'warning'
  return 'info'
}

const getEvaluationSummary = (evaluation?: AgentEvaluationReport | null): AgentEvaluationSummary | null => {
  const explicitSummary = evaluation?.evaluation_summary
  if (explicitSummary && typeof explicitSummary === 'object') {
    return explicitSummary
  }
  const nestedSummary = evaluation?.details?.evaluation_summary
  if (nestedSummary && typeof nestedSummary === 'object') {
    return nestedSummary as AgentEvaluationSummary
  }
  return null
}

const getProjectMemoryBindingSummary = (evaluation?: AgentEvaluationReport | null): AgentProjectMemoryBindingSummary | null => {
  const explicitSummary = evaluation?.project_memory_binding_summary
  if (explicitSummary && typeof explicitSummary === 'object') {
    return explicitSummary
  }
  const nestedSummary = evaluation?.details?.project_memory_binding_summary
  if (nestedSummary && typeof nestedSummary === 'object') {
    return nestedSummary as AgentProjectMemoryBindingSummary
  }
  const evaluationSummary = getEvaluationSummary(evaluation)
  return evaluationSummary?.project_memory_binding || null
}

const getVersionProjectMemorySummary = (version?: AgentVersion | null): AgentProjectMemoryBindingSummary | null => {
  if (!version) return null
  return version.last_evaluation_summary?.project_memory_binding || version.prompt_template_project_memory_binding_summary || null
}

const getEvaluationDecisionLabel = (decision?: string) => {
  if (decision === 'pass') return '通过'
  if (decision === 'reject') return '拒绝'
  if (decision === 'revise') return '需修订'
  return decision || '未评估'
}

const fillExample = (type: 'valuation' | 'industry' | 'watcher') => {
  if (type === 'valuation') {
    composerText.value = '我要做一个股票估值分析师，负责根据行情、财务数据和行业背景给出估值区间，解释关键假设，说明失效条件，但不要直接给交易建议。'
    return
  }
  if (type === 'industry') {
    composerText.value = '我想做一个行业比较研究员，负责横向比较行业格局、盈利质量、估值水平和景气位置，输出结构化对比结论。'
    return
  }
  composerText.value = '我想做一个财报跟踪助手，负责跟踪重点公司的季报变化、提炼异常指标、总结风险提示，但不做独立投资建议。'
}

const isAgentBranchExpanded = (specId: string) => expandedSpecIds.value.includes(specId)

const expandAgentBranch = (specId?: string) => {
  const normalized = String(specId || '').trim()
  if (!normalized || expandedSpecIds.value.includes(normalized)) return
  expandedSpecIds.value = [...expandedSpecIds.value, normalized]
}

const ensureSpecVersionsLoaded = async (specId?: string, force = false) => {
  const normalized = String(specId || '').trim()
  if (!normalized) return
  if (!force && versionItemsBySpec.value[normalized]) return
  loadingSpecVersions.value = { ...loadingSpecVersions.value, [normalized]: true }
  try {
    const result = await agentWorkshopApi.listVersions({ spec_id: normalized, page: 1, page_size: 100 })
    versionItemsBySpec.value = {
      ...versionItemsBySpec.value,
      [normalized]: [...(result.items || [])].sort((left, right) => right.version - left.version),
    }
  } catch {
    versionItemsBySpec.value = { ...versionItemsBySpec.value, [normalized]: [] }
  } finally {
    loadingSpecVersions.value = { ...loadingSpecVersions.value, [normalized]: false }
  }
}

const toggleAgentBranch = async (specId: string) => {
  if (isAgentBranchExpanded(specId)) {
    expandedSpecIds.value = expandedSpecIds.value.filter(item => item !== specId)
    return
  }
  expandAgentBranch(specId)
  await ensureSpecVersionsLoaded(specId)
}

const scrollMessagesToBottom = (behavior: ScrollBehavior = 'smooth') => {
  nextTick(() => {
    const container = messagesContainer.value
    if (!container) return
    container.scrollTo({ top: container.scrollHeight, behavior })
  })
}

const startLoadingTimer = () => {
  if (loadingTimer !== null) {
    window.clearInterval(loadingTimer)
  }
  loadingSeconds.value = 0
  loadingTimer = window.setInterval(() => {
    loadingSeconds.value += 1
  }, 1000)
}

const stopLoadingTimer = () => {
  if (loadingTimer !== null) {
    window.clearInterval(loadingTimer)
    loadingTimer = null
  }
}

const loadAgentItems = async () => {
  try {
    const result = await agentWorkshopApi.listSpecs({ page: 1, page_size: 100 })
    agentItems.value = [...(result.items || [])].sort((left, right) => {
      const leftTime = Date.parse(left.updated_at || left.created_at || '') || 0
      const rightTime = Date.parse(right.updated_at || right.created_at || '') || 0
      return rightTime - leftTime
    })
  } catch {
    agentItems.value = []
  }
}

const reconcileDeletedWorkspaceState = () => {
  const currentSpecId = String(displaySpec.value?.spec_id || nanobotDraftLink.value?.specId || '').trim()
  if (!currentSpecId) {
    return false
  }
  const stillExists = agentItems.value.some(item => item.spec_id === currentSpecId)
  if (stillExists) {
    return false
  }
  resetStudio()
  ElMessage.info('当前 Agent 已不存在，已同步清空对话与缓存状态')
  return true
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
  const request = (async () => {
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
  })()
  versionContextRequests.set(normalized, request)
  try {
    await request
  } finally {
    versionContextRequests.delete(normalized)
  }
}

const openVersionDetailDialog = async (item: AgentSpec, version: AgentVersion) => {
  versionDetailDialogVisible.value = true
  versionDetailLoading.value = true
  versionDetailSpec.value = item
  try {
    await loadVersionDetail(version.version_id)
  } catch (error: any) {
    versionDetailDialogVisible.value = false
    ElMessage.error(error?.message || '加载版本详情失败')
  } finally {
    versionDetailLoading.value = false
  }
}

const loadVersionDetail = async (versionId: string) => {
  versionDetailVersion.value = null
  versionDetailPrompt.value = null
  versionDetailEvaluation.value = null
  const [versionResult, versionPromptResult, evaluationResult] = await Promise.all([
    agentWorkshopApi.getVersion(versionId),
    agentWorkshopApi.getVersionPrompt(versionId).catch(() => null),
    agentWorkshopApi.listEvaluations(versionId, { page: 1, page_size: 1 }).catch(() => null),
  ])
  versionDetailVersion.value = versionResult
  versionDetailPrompt.value = versionPromptResult
  versionDetailEvaluation.value = evaluationResult?.items?.[0] || null
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
  const request = (async () => {
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
  })()
  latestVersionContextRequests.set(normalized, request)
  try {
    await request
  } finally {
    latestVersionContextRequests.delete(normalized)
  }
}

const publishVersionFromDetail = async () => {
  const versionId = String(versionDetailVersion.value?.version_id || '').trim()
  const specId = String(versionDetailSpec.value?.spec_id || versionDetailVersion.value?.spec_id || '').trim()
  if (!versionId) return
  if (!canPublishVersionDetail.value) {
    ElMessage.warning(versionDetailVersion.value?.status === 'active' ? '当前版本已经是正式版本' : '当前版本尚未满足发布条件')
    return
  }

  try {
    await ElMessageBox.confirm(
      `版本 v${versionDetailVersion.value?.version || ''} 已通过最新真数据测试，但不会自动发布。确认现在手动发布为正式版本吗？`,
      '确认发布',
      {
        confirmButtonText: '确认发布',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  publishingVersionDetail.value = true
  try {
    const result = await agentWorkshopApi.publishVersion(versionId)
    await Promise.all([
      loadVersionDetail(result.version_id),
      ensureSpecVersionsLoaded(specId, true),
      loadAgentItems(),
      selectedVersionId.value === result.version_id || latestVersion.value?.version_id === result.version_id
        ? loadVersionContext(result.version_id)
        : Promise.resolve(),
      specId && displaySpec.value?.spec_id === specId
        ? loadLatestVersionContext(specId)
        : Promise.resolve(),
    ])
    await persistThreadContext()
    ElMessage.success(result.previous_active_archived ? '版本已手动发布，上一正式版本已自动归档' : '版本已手动发布')
  } catch (error: any) {
    ElMessage.error(error?.message || '发布失败')
  } finally {
    publishingVersionDetail.value = false
  }
}

const reEvaluateVersionFromDetail = async () => {
  const versionId = String(versionDetailVersion.value?.version_id || '').trim()
  const specId = String(versionDetailSpec.value?.spec_id || versionDetailVersion.value?.spec_id || '').trim()
  const evaluationType = String(versionDetailEvaluation.value?.evaluation_type || 'production-review').trim() || 'production-review'
  if (!versionId) return

  reEvaluatingVersionDetail.value = true
  try {
    const result = await agentWorkshopApi.evaluateVersion(versionId, {
      evaluation_type: evaluationType,
    })
    await Promise.all([
      loadVersionDetail(result.version_id),
      selectedVersionId.value === result.version_id || latestVersion.value?.version_id === result.version_id
        ? loadVersionContext(result.version_id)
        : Promise.resolve(),
      specId && displaySpec.value?.spec_id === specId
        ? loadLatestVersionContext(specId)
        : Promise.resolve(),
      loadAgentItems(),
    ])
    await persistThreadContext()
    ElMessage.success(result.evaluation.decision === 'pass' ? '重新评估完成，当前已满足发布条件' : '重新评估完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '重新评估失败')
  } finally {
    reEvaluatingVersionDetail.value = false
  }
}

const loadSession = async (sessionId?: string, options?: {
  syncNanobotThread?: boolean
}) => {
  const normalized = String(sessionId || '').trim()
  if (!normalized) return
  if (sessionRequests.has(normalized)) {
    return sessionRequests.get(normalized) as Promise<void>
  }
  const request = (async () => {
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
      expandAgentBranch(currentSession.value.current_spec_snapshot?.spec_id)
      await ensureSpecVersionsLoaded(currentSession.value.current_spec_snapshot?.spec_id)
      await loadLatestVersionContext(currentSession.value.current_spec_snapshot?.spec_id)
      if (options?.syncNanobotThread && currentNanobotSessionKey.value) {
        await loadNanobotThreadMessages({ sessionKey: currentNanobotSessionKey.value, silent: true })
      } else {
        await alignNanobotThreadWithWorkspace({ silent: true })
      }
    } catch (error: any) {
      ElMessage.error(error?.message || '加载会话失败')
    } finally {
      loadingSession.value = false
    }
  })()
  sessionRequests.set(normalized, request)
  try {
    await request
  } finally {
    sessionRequests.delete(normalized)
  }
}

const findLatestNanobotSpec = async (requestedAtMs?: number) => {
  const result = await agentWorkshopApi.listSpecs({ page: 1, page_size: 50 })
  const sortedSpecs = [...(result.items || [])].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at || left.created_at || '') || 0
    const rightTime = Date.parse(right.updated_at || right.created_at || '') || 0
    return rightTime - leftTime
  })
  return sortedSpecs.find(item => {
    if (item.source !== 'nanobot') return false
    if (!requestedAtMs) return true
    const updatedAt = Date.parse(item.updated_at || item.created_at || '') || 0
    return updatedAt >= requestedAtMs - 5000
  }) || null
}

const syncDraftAfterNanobot = async (options?: {
  response?: EmbeddedNanobotChatResponse
  requestedAtMs?: number
  force?: boolean
  silent?: boolean
}) => {
  const toolsUsed = options?.response?.tools_used || []
  const shouldCheckDraft = Boolean(options?.force || toolsUsed.some(toolId => (
    toolId === 'create_or_update_agent_workshop_draft' || toolId === 'generate_confirmed_candidate_agent'
  )))
  if (!shouldCheckDraft) return false

  const matchedSpec = await findLatestNanobotSpec(options?.requestedAtMs)
  if (!matchedSpec) {
    if (options?.force && !options?.silent) {
      ElMessage.warning('助手还没有同步出可用 Draft，请继续补充。')
    }
    return false
  }

  standaloneSpec.value = matchedSpec
  nanobotDraftLink.value = {
    specId: matchedSpec.spec_id,
    specName: matchedSpec.name,
    sessionId: matchedSpec.latest_session_id,
  }
  expandAgentBranch(matchedSpec.spec_id)
  await ensureSpecVersionsLoaded(matchedSpec.spec_id, true)
  if (matchedSpec.latest_session_id) {
    await loadSession(matchedSpec.latest_session_id)
  } else {
    currentSession.value = null
    selectedVersionId.value = ''
    await loadLatestVersionContext(matchedSpec.spec_id)
  }
  await loadAgentItems()
  await loadNanobotThreads()
  persistState()
  syncRoute()
  return true
}

const pushNanobotToolEvent = (event: Record<string, any>) => {
  const toolName = normalizeAssistantDisplayText(String(event.title || event.name || event.tool || event.tool_id || event.step || '未命名步骤').trim()) || '未命名步骤'
  const rawStatus = String(event.status || event.event || '').trim().toLowerCase()
  const detail = normalizeAssistantDisplayText(String(event.detail || event.message || event.summary || '').trim())
  let statusLabel = '处理中'
  let tone: 'info' | 'success' | 'warning' = 'info'

  if (rawStatus.includes('complete') || rawStatus.includes('done') || rawStatus.includes('success')) {
    statusLabel = '已完成'
    tone = 'success'
  } else if (rawStatus.includes('fail') || rawStatus.includes('error')) {
    statusLabel = '失败'
    tone = 'warning'
  } else if (rawStatus.includes('start') || rawStatus.includes('progress')) {
    statusLabel = '执行中'
  }

  nanobotToolEvents.value = [
    ...nanobotToolEvents.value,
    {
      key: `${Date.now()}-${nanobotToolEvents.value.length}`,
      title: toolName,
      detail,
      statusLabel,
      tone,
    },
  ].slice(-8)
}

const appendAssistantProgressStep = (
  messages: AgentWorkshopMessage[],
  assistantIndex: number,
  step: { text: string; tone?: 'info' | 'success' | 'warning'; meta?: string },
) => {
  const normalizedText = normalizeAssistantDisplayText(step.text).trim()
  const normalizedMeta = normalizeAssistantDisplayText(step.meta || '').trim()
  if (!messages[assistantIndex] || !normalizedText) return
  const currentSteps = [...(messages[assistantIndex].progressSteps || [])]
  const previous = currentSteps[currentSteps.length - 1]
  if (previous?.text === normalizedText && previous?.meta === normalizedMeta && previous?.tone === step.tone) {
    return
  }
  currentSteps.push({
    ...step,
    text: normalizedText,
    meta: normalizedMeta || undefined,
  })
  messages[assistantIndex] = {
    ...messages[assistantIndex],
    progressSteps: currentSteps,
  }
  nanobotMessages.value = [...messages]
  persistState()
}

const buildNanobotPayload = (message: string) => {
  const normalized = message.trim()
  if (!normalized) return ''
  const contextualIntent = resolveContextualReplyIntent(normalized)
  if (!currentWorkshopSessionId.value) {
    if (!contextualIntent) return normalized
    return [
      normalized,
      '补充上下文：这是一个基于上一轮助手选项的简短选择。',
      `上一轮可选项：\n${contextualIntent.optionsText}`,
      `本次短回复更可能表示：选择第 ${contextualIntent.selectionIndex} 项「${contextualIntent.selectedOption}」。如果无冲突，请直接按该意图执行，不要重复追问编号含义。`,
    ].join('\n\n')
  }

  const blocks = [
    '继续当前 Agent Workshop Draft 讨论，不要重新新建一个 Agent。',
    `session_id='${currentWorkshopSessionId.value}'。`,
    displaySpec.value?.spec_id ? `spec_id='${displaySpec.value.spec_id}'。` : '',
    realStateGuardText.value,
    '当前任务是沿着现有 Workshop 版本继续执行或诊断测试链路，不要切换到内置 Agent 蓝图侦察、已注册 Agent 直调或重新设计路径，除非用户明确要求重做。',
    contextualIntent ? `上一轮可选项：\n${contextualIntent.optionsText}` : '',
    contextualIntent ? `本次短回复更可能表示：选择第 ${contextualIntent.selectionIndex} 项「${contextualIntent.selectedOption}」。如果无冲突，请直接按该意图执行，不要重复追问编号含义。` : '',
    nanobotIterationBootstrapPending.value && iterationReminderMessage.value ? `上一轮评估摘要如下：\n${iterationReminderMessage.value}` : '',
    nanobotIterationBootstrapPending.value && iterationImprovementItems.value.length
      ? `本轮优先处理的问题：\n${iterationImprovementItems.value.map((item, index) => `${index + 1}. ${item}`).join('\n')}`
      : '',
    `用户本次补充：${normalized}`,
  ].filter(Boolean)

  return blocks.join('\n\n')
}

const sendNanobotMessage = async (message: string) => {
  const normalized = message.trim()
  if (!normalized) return null

  const payloadMessage = buildNanobotPayload(normalized)
  const requestedAtMs = Date.now()
  const sessionKey = currentNanobotSessionKey.value || `${NANOBOT_WORKSHOP_SESSION_PREFIX}${requestedAtMs}`
  const now = new Date().toISOString()
  const nextMessages = [
    ...displayedMessages.value,
    { role: 'user', content: normalized, timestamp: now },
    { role: 'assistant', content: '', timestamp: now, progressSteps: [] },
  ]
  const assistantIndex = nextMessages.length - 1

  currentNanobotSessionKey.value = sessionKey
  nanobotMessages.value = nextMessages
  nanobotStreaming.value = true
  nanobotProgressHint.value = '正在发送给工坊助手'
  nanobotToolEvents.value = []
  startLoadingTimer()
  persistState()
  syncRoute()
  scrollMessagesToBottom('auto')

  const appendAssistantChunk = (chunk?: string) => {
    const text = normalizeAssistantDisplayText(String(chunk || ''))
    if (!text.trim()) return
    nextMessages[assistantIndex].content = nextMessages[assistantIndex].content
      ? `${nextMessages[assistantIndex].content}\n${text}`
      : text
    nanobotMessages.value = [...nextMessages]
    persistState()
  }

  try {
    const response = await new Promise<EmbeddedNanobotChatResponse>((resolve, reject) => {
      activeNanobotStreamController = embeddedNanobotApi.chatStream({
        message: payloadMessage,
        display_message: normalized,
        session_key: sessionKey,
        chat_id: sessionKey,
        channel: 'agent_workshop',
        skill_names: NANOBOT_SKILLS,
        thread_context: buildThreadContext(),
      }, {
        onStarted(data) {
          currentNanobotSessionKey.value = data.session_key || sessionKey
          nanobotProgressHint.value = normalizeAssistantDisplayText(data.message) || '工坊助手已开始处理当前需求'
          appendAssistantProgressStep(nextMessages, assistantIndex, {
            text: normalizeAssistantDisplayText(data.message) || '工坊助手已开始处理当前需求',
            tone: 'info',
          })
          persistState()
          syncRoute()
          scrollMessagesToBottom('auto')
        },
        onProgress(data) {
          currentNanobotSessionKey.value = data.session_key || currentNanobotSessionKey.value || sessionKey
          nanobotProgressHint.value = normalizeAssistantDisplayText(data.message) || '工坊助手正在处理中'
          appendAssistantProgressStep(nextMessages, assistantIndex, {
            text: normalizeAssistantDisplayText(data.message) || '工坊助手正在处理中',
            tone: 'info',
          })
          persistState()
          scrollMessagesToBottom('auto')
        },
        onToken(content) {
          appendAssistantChunk(content)
          scrollMessagesToBottom('auto')
        },
        onToolEvent(event) {
          pushNanobotToolEvent(event)
          const toolName = String(event.name || event.tool || event.tool_id || '工具').trim() || '工具'
          nanobotProgressHint.value = event.status === 'started'
            ? `正在执行 ${toolName}`
            : `已处理 ${toolName} 的最新动作`
          scrollMessagesToBottom('auto')
        },
        onStepEvent(event) {
          pushNanobotToolEvent(event)
          const stepTitle = normalizeAssistantDisplayText(String(event.title || event.step || '步骤').trim()) || '步骤'
          const detail = normalizeAssistantDisplayText(String(event.detail || '').trim())
          const isCompleted = String(event.status || '').trim().toLowerCase() === 'completed'
          nanobotProgressHint.value = event.status === 'started'
            ? (detail || `正在执行 ${stepTitle}`)
            : (detail || `${stepTitle} 已完成`)
          appendAssistantProgressStep(nextMessages, assistantIndex, {
            text: `${stepTitle}${isCompleted ? ' 已完成' : ' 开始'}`,
            tone: isCompleted ? 'success' : 'info',
            meta: detail || undefined,
          })
          persistState()
          scrollMessagesToBottom('auto')
        },
        onDone(data) {
          currentNanobotSessionKey.value = data.session_key || currentNanobotSessionKey.value || sessionKey
          if (!nextMessages[assistantIndex].content.trim()) {
            nextMessages[assistantIndex].content = normalizeAssistantDisplayText(data.content) || '工坊助手已处理当前需求。'
          }
          nanobotMessages.value = [...nextMessages]
          nanobotProgressHint.value = data.tools_used?.length
            ? `本轮已完成，调用了 ${data.tools_used.length} 个工具`
            : '本轮已完成'
          stopLoadingTimer()
          persistState()
          syncRoute()
          resolve(data)
        },
        onError(messageText) {
          nextMessages[assistantIndex].content = nextMessages[assistantIndex].content || `请求失败：${messageText || '未知错误'}`
          nanobotMessages.value = [...nextMessages]
          stopLoadingTimer()
          persistState()
          reject(new Error(messageText || '未知错误'))
        },
        onAbort() {
          nextMessages[assistantIndex].content = nextMessages[assistantIndex].content || '已停止本轮生成。'
          nanobotMessages.value = [...nextMessages]
          stopLoadingTimer()
          persistState()
          reject(new Error('已停止生成'))
        },
      })
    })

    await syncDraftAfterNanobot({ response, requestedAtMs, silent: true })
    await loadNanobotThreadMessages({ threadId: response.thread_id || sessionKey, silent: true })
    nanobotIterationBootstrapPending.value = false
    return response
  } finally {
    activeNanobotStreamController = null
    nanobotStreaming.value = false
    stopLoadingTimer()
  }
}

const refreshWorkspace = async () => {
  await loadAgentItems()
  await loadNanobotThreads()
  if (reconcileDeletedWorkspaceState()) {
    return
  }
  if (currentWorkshopSessionId.value) {
    await loadSession(currentWorkshopSessionId.value)
  } else if (displaySpec.value?.spec_id) {
    await loadLatestVersionContext(displaySpec.value.spec_id)
  } else if (currentNanobotSessionKey.value) {
    await loadNanobotThreadMessages({ sessionKey: currentNanobotSessionKey.value, silent: true })
  }
  await alignNanobotThreadWithWorkspace({ silent: true })
}

const openNanobotThread = async (thread: EmbeddedNanobotThreadItem) => {
  clearStudioState(true)
  currentNanobotSessionKey.value = thread.session_key || thread.thread_id
  await loadNanobotThreadMessages({ threadId: thread.thread_id })
  syncRoute()
}

const handleDeleteNanobotThread = async (thread: EmbeddedNanobotThreadItem) => {
  try {
    await ElMessageBox.confirm(`归档会话「${thread.title || thread.thread_id}」后，它会从活动列表隐藏，但历史消息仍会保留。是否继续？`, '归档会话', {
      type: 'warning',
      confirmButtonText: '归档',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    await embeddedNanobotApi.deleteThread(thread.thread_id)
    if (activeNanobotThreadId.value === thread.thread_id) {
      resetStudio()
    } else {
      await loadNanobotThreads()
    }
    ElMessage.success('会话已归档')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close' || error?.action === 'cancel' || error?.action === 'close') return
    ElMessage.error(error?.message || '归档会话失败')
  }
}

const handleRestoreNanobotThread = async (thread: EmbeddedNanobotThreadItem) => {
  try {
    await embeddedNanobotApi.restoreThread(thread.thread_id)
    await loadNanobotThreads()
    ElMessage.success('会话已恢复到活动列表')
  } catch (error: any) {
    ElMessage.error(error?.message || '恢复会话失败')
  }
}

const openAgentItem = async (item: AgentSpec) => {
  selectedVersionId.value = ''
  expandAgentBranch(item.spec_id)
  await ensureSpecVersionsLoaded(item.spec_id)
  standaloneSpec.value = item
  nanobotDraftLink.value = {
    specId: item.spec_id,
    specName: item.name,
    sessionId: item.latest_session_id,
  }
  if (item.latest_session_id) {
    await loadSession(item.latest_session_id)
  } else {
    currentSession.value = null
    await alignNanobotThreadWithWorkspace({ silent: true, forceReload: true })
    await loadLatestVersionContext(item.spec_id)
    syncRoute()
  }
  await persistThreadContext()
}

const openAgentVersion = async (item: AgentSpec, version: AgentVersion) => {
  selectedVersionId.value = version.version_id
  expandAgentBranch(item.spec_id)
  await ensureSpecVersionsLoaded(item.spec_id)
  standaloneSpec.value = item
  nanobotDraftLink.value = {
    specId: item.spec_id,
    specName: item.name,
    sessionId: item.latest_session_id,
  }
  if (item.latest_session_id) {
    await loadSession(item.latest_session_id)
  } else {
    currentSession.value = null
    await alignNanobotThreadWithWorkspace({ silent: true, forceReload: true })
    syncRoute()
  }
  selectedVersionId.value = version.version_id
  await loadVersionContext(version.version_id)
  await alignNanobotThreadWithWorkspace({ silent: true, forceReload: true })
  await persistThreadContext()
  await openVersionDetailDialog(item, version)
}

const handleDeleteSpec = async (item: AgentSpec) => {
  try {
    await ElMessageBox.confirm(`删除 Agent「${item.name || item.spec_id}」后，其所有版本、评估和运行配置都会一起删除。是否继续？`, '删除 Agent', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    await agentWorkshopApi.deleteSpec(item.spec_id)
    if (activeAgentId.value === item.spec_id) {
      resetStudio()
    }
    delete versionItemsBySpec.value[item.spec_id]
    expandedSpecIds.value = expandedSpecIds.value.filter(specId => specId !== item.spec_id)
    await loadAgentItems()
    reconcileDeletedWorkspaceState()
    ElMessage.success('Agent 已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close' || error?.action === 'cancel' || error?.action === 'close') return
    ElMessage.error(error?.message || '删除 Agent 失败')
  }
}

const handleDeleteVersion = async (item: AgentSpec, version: AgentVersion) => {
  try {
    await ElMessageBox.confirm(`删除版本 v${version.version} 后，关联评估和运行配置也会一起删除。是否继续？`, '删除版本', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    await agentWorkshopApi.deleteVersion(version.version_id)
    await ensureSpecVersionsLoaded(item.spec_id, true)
    await loadAgentItems()
    if (selectedVersionId.value === version.version_id) {
      selectedVersionId.value = ''
      if (activeAgentId.value === item.spec_id) {
        if (currentWorkshopSessionId.value) {
          await loadSession(currentWorkshopSessionId.value)
        } else {
          await loadLatestVersionContext(item.spec_id)
        }
      }
    } else if (activeAgentId.value === item.spec_id && latestVersion.value?.version_id === version.version_id) {
      await loadLatestVersionContext(item.spec_id)
    }
    ElMessage.success('版本已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close' || error?.action === 'cancel' || error?.action === 'close') return
    ElMessage.error(error?.message || '删除版本失败')
  }
}

const handleSendMessage = async () => {
  if (!composerText.value.trim()) return
  sending.value = true
  try {
    const shouldStartFresh = !hasWorkspaceContext.value && !currentNanobotSessionKey.value
    await sendNanobotMessage(composerText.value.trim())
    if (shouldStartFresh) {
      await loadAgentItems()
      ElMessage.success('已接入 Nanobot，开始创建 Agent')
    }
    composerText.value = ''
  } catch (error: any) {
    ElMessage.error(error?.message || '发送失败')
  } finally {
    sending.value = false
  }
}

const handleRefreshDraft = async () => {
  refreshingDraft.value = true
  try {
    const synced = await syncDraftAfterNanobot({ force: true })
    if (!synced) {
      ElMessage.warning('还没有可打开的 Draft，请继续补充需求。')
      return
    }
    ElMessage.success('Draft 已刷新')
  } catch (error: any) {
    ElMessage.error(error?.message || '刷新 Draft 失败')
  } finally {
    refreshingDraft.value = false
  }
}

const handleBuildVersion = async () => {
  if (!currentWorkshopSessionId.value) return
  buildingVersion.value = true
  try {
    const result = await agentWorkshopApi.buildVersion(currentWorkshopSessionId.value)
    latestVersion.value = result.version
    await loadSession(currentWorkshopSessionId.value)
    await loadLatestVersionContext(result.spec_id)
    await loadAgentItems()
    await persistThreadContext()
    ElMessage.success('测试版本已补建')
  } catch (error: any) {
    ElMessage.error(error?.message || '补建测试版本失败')
  } finally {
    buildingVersion.value = false
  }
}

const handleIterateVersion = async () => {
  if (!latestVersion.value?.version_id) return
  iteratingVersion.value = true
  try {
    const result = await agentWorkshopApi.iterateVersion(latestVersion.value.version_id)
    await loadSession(result.session_id)
    nanobotDraftLink.value = {
      specId: currentSession.value?.current_spec_snapshot?.spec_id || result.spec_id,
      specName: currentSession.value?.current_spec_snapshot?.name || '当前 Draft',
      sessionId: result.session_id,
    }
    if (!currentNanobotSessionKey.value) {
      currentNanobotSessionKey.value = `${NANOBOT_WORKSHOP_SESSION_PREFIX}${Date.now()}`
    }
    nanobotMessages.value = [...(currentSession.value?.messages || [])]
    nanobotIterationBootstrapPending.value = true
    await loadAgentItems()
    await persistThreadContext()
    persistState()
    syncRoute()
    ElMessage.success('已基于当前 Agent 创建下一轮迭代，会继续由工坊助手接手讨论')
  } catch (error: any) {
    ElMessage.error(error?.message || '发起下一轮失败')
  } finally {
    iteratingVersion.value = false
  }
}

void [restoreState, promptSections, fillExample, handleBuildVersion, handleIterateVersion]

const cancelNanobotStreaming = () => {
  if (!activeNanobotStreamController) return
  activeNanobotStreamController.abort()
}

const resetStudio = () => {
  clearStudioState()
  router.push('/workflow/nanobot-agent-studio')
}

const initFromRoute = async () => {
  if (initFromRoutePromise) {
    return initFromRoutePromise
  }

  initFromRoutePromise = (async () => {
    clearStudioState(true)
    const routeNanobotSessionKey = typeof route.query.nanobotSessionKey === 'string' ? route.query.nanobotSessionKey : ''
    const routeSessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : ''
    const routeSpecId = typeof route.query.specId === 'string' ? route.query.specId : ''
    const restoredFromStorage = !routeNanobotSessionKey && !routeSessionId && !routeSpecId ? restoreState() : false
    const nanobotSessionKey = routeNanobotSessionKey || String(currentNanobotSessionKey.value || '').trim()
    const sessionId = routeSessionId || String(nanobotDraftLink.value?.sessionId || '').trim()
    const specId = routeSpecId || String(nanobotDraftLink.value?.specId || '').trim()
    let restoredFromNanobotThread = false

    await loadNanobotThreads()

    if (nanobotSessionKey) {
      restoredFromNanobotThread = await loadNanobotThreadMessages({ sessionKey: nanobotSessionKey, silent: true })
    }

    if (sessionId) {
      if (!restoredFromNanobotThread || String(currentSession.value?.session_id || '').trim() !== sessionId) {
        await loadSession(sessionId, { syncNanobotThread: false })
      }
    } else if (specId) {
      if (!restoredFromNanobotThread || String(displaySpec.value?.spec_id || '').trim() !== specId) {
        try {
          standaloneSpec.value = await agentWorkshopApi.getSpec(specId)
          selectedVersionId.value = ''
          expandAgentBranch(specId)
          await ensureSpecVersionsLoaded(specId)
          await loadLatestVersionContext(specId)
        } catch (error: any) {
          ElMessage.error(error?.message || '加载 Draft 失败')
        }
      }
    } else if (nanobotDraftLink.value?.sessionId && !restoredFromNanobotThread) {
      await loadSession(nanobotDraftLink.value.sessionId, { syncNanobotThread: false })
    }

    if (!restoredFromNanobotThread && (sessionId || specId || restoredFromStorage)) {
      await alignNanobotThreadWithWorkspace({ silent: true, forceReload: true })
    }

    await loadAgentItems()
    reconcileDeletedWorkspaceState()
    persistState()
    syncRoute()
  })()

  try {
    await initFromRoutePromise
  } finally {
    initFromRoutePromise = null
  }
}

watch(
  () => [
    currentNanobotSessionKey.value,
    displaySpec.value?.spec_id || '',
    displaySpec.value?.name || '',
    currentSession.value?.session_id || '',
    selectedVersionId.value || '',
    latestVersion.value?.version_id || '',
    latestVersion.value?.status || '',
  ].join('|'),
  async (value, previousValue) => {
    if (!value || value === previousValue) return
    await persistThreadContext()
  },
)

watch(
  () => `${route.query.sessionId || ''}|${route.query.specId || ''}|${route.query.nanobotSessionKey || ''}`,
  async (value, previousValue) => {
    if (value === previousValue) return
    if (suppressNextRouteInit) {
      suppressNextRouteInit = false
      return
    }
    await initFromRoute()
  },
)

watch(
  () => displayedMessages.value.length,
  () => {
    scrollMessagesToBottom('smooth')
  },
)

watch(
  () => nanobotStreaming.value,
  (streaming) => {
    if (streaming) {
      scrollMessagesToBottom('smooth')
      return
    }
    stopLoadingTimer()
    if (pendingRouteSync) {
      syncRoute()
    }
  },
)

onMounted(async () => {
  await initFromRoute()
  scrollMessagesToBottom('auto')
})

onUnmounted(() => {
  stopLoadingTimer()
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
    activeNanobotStreamController = null
  }
})
</script>

<style scoped lang="scss">
.nanobot-agent-studio-page {
  min-height: calc(100vh - 108px);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background:
    radial-gradient(circle at top left, rgba(6, 95, 70, 0.08), transparent 28%),
    linear-gradient(180deg, #f6fbfa 0%, #ffffff 100%);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  margin: 0;
  font-size: 28px;
  color: #123f39;
}

.page-subtitle {
  color: #5a726c;
  line-height: 1.6;
}

.header-right,
.chat-panel-actions,
.meta-row,
.tag-wrap,
.result-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.layout-toggle-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(15, 61, 54, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
}

.layout-toggle-label {
  font-size: 12px;
  font-weight: 700;
  color: #5a726c;
}

.workspace-body {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
  gap: 16px;
  min-height: 0;
  flex: 1;
}

.workspace-body.left-sidebar-hidden {
  grid-template-columns: minmax(0, 1fr) 320px;
}

.workspace-body.right-sidebar-hidden {
  grid-template-columns: 280px minmax(0, 1fr);
}

.workspace-body.left-sidebar-hidden.right-sidebar-hidden {
  grid-template-columns: minmax(0, 1fr);
}

.agent-sidebar,
.chat-panel,
.status-sidebar {
  min-width: 0;
  min-height: 0;
  border: 1px solid rgba(15, 61, 54, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
}

.agent-sidebar,
.status-sidebar {
  display: flex;
  flex-direction: column;
  padding: 14px;
  gap: 14px;
  overflow: hidden;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.status-sidebar-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.sidebar-header,
.status-sidebar-header,
.chat-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px 0;
}

.sidebar-header-compact {
  justify-content: flex-end;
  align-items: center;
  padding: 4px 4px 0;
}

.sidebar-header-actions,
.thread-panel-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sidebar-title,
.current-thread-title {
  font-size: 16px;
  font-weight: 700;
  color: #123f39;
}

.sidebar-subtitle,
.current-thread-subtitle,
.input-tip,
.page-subtitle {
  font-size: 12px;
  color: #6b7f79;
  line-height: 1.6;
}

.agent-tree {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
  min-height: 0;
}

.nanobot-thread-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #dce8e3;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.nanobot-thread-panel-collapsed {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 14px 16px;
  border: 1px dashed rgba(15, 138, 125, 0.24);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(251, 254, 253, 0.92) 0%, rgba(244, 250, 247, 0.96) 100%);
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    border-color: rgba(15, 138, 125, 0.42);
    background: linear-gradient(180deg, rgba(244, 253, 250, 0.96) 0%, rgba(255, 255, 255, 1) 100%);
  }
}

.collapsed-panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #123f39;
}

.collapsed-panel-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #6b7f79;
}

.thread-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.thread-filter-grid {
  display: grid;
  gap: 8px;
}

.nanobot-thread-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nanobot-thread-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: 14px;
  background: #fff;
  box-shadow: inset 0 0 0 1px rgba(15, 61, 54, 0.05);

  &.active {
    background: linear-gradient(180deg, rgba(240, 253, 250, 0.96) 0%, rgba(255, 255, 255, 1) 100%);
    box-shadow:
      inset 0 0 0 1px rgba(15, 138, 125, 0.14),
      0 8px 18px rgba(15, 138, 125, 0.08);
  }
}

.nanobot-thread-main {
  border: 0;
  background: transparent;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.nanobot-thread-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.nanobot-thread-title {
  font-size: 13px;
  font-weight: 700;
  color: #123f39;
}

.nanobot-thread-desc {
  margin-top: 6px;
  font-size: 12px;
  color: #5a726c;
  line-height: 1.6;
}

.nanobot-thread-meta {
  font-size: 11px;
  color: #6b7f79;
}

.nanobot-thread-meta-row {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.nanobot-thread-meta-badges {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.nanobot-thread-agent {
  font-size: 11px;
  color: #0f8a7d;
  white-space: nowrap;
}

.thread-delete-btn {
  align-self: center;
}

.agent-tree-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-tree-branch {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-tree-parent {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: stretch;
  border: 1px solid #dce8e3;
  border-radius: 16px;
  padding: 10px;
  background: #fff;
  transition: all 0.18s ease;

  &:hover {
    border-color: rgba(15, 138, 125, 0.32);
    background: #f7fbfa;
  }

  &.active {
    border-color: rgba(15, 138, 125, 0.42);
    background: linear-gradient(180deg, rgba(240, 253, 250, 0.96) 0%, rgba(255, 255, 255, 1) 100%);
    box-shadow: 0 10px 24px rgba(15, 138, 125, 0.08);
  }
}

.tree-toggle,
.tree-main,
.agent-version-item {
  border: 0;
  background: transparent;
}

.tree-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.tree-chevron {
  width: 8px;
  height: 8px;
  border-right: 1.5px solid #5a726c;
  border-bottom: 1.5px solid #5a726c;
  transform: rotate(-45deg);
  transition: transform 0.18s ease;

  &.expanded {
    transform: rotate(45deg);
  }
}

.tree-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  text-align: left;
  cursor: pointer;
}

.tree-delete-btn {
  align-self: center;
}

.agent-tree-children {
  margin-left: 18px;
  padding-left: 14px;
  border-left: 1px dashed rgba(15, 138, 125, 0.22);
}

.agent-version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-version-item {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f7fbfa;
  box-shadow: inset 0 0 0 1px rgba(15, 61, 54, 0.05);
  cursor: pointer;
  text-align: left;

  &.active {
    background: linear-gradient(180deg, rgba(240, 253, 250, 0.96) 0%, rgba(255, 255, 255, 1) 100%);
    box-shadow:
      inset 0 0 0 1px rgba(15, 138, 125, 0.14),
      0 8px 18px rgba(15, 138, 125, 0.08);
  }
}

.agent-version-main {
  min-width: 0;
}

.agent-version-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-version-title {
  font-size: 13px;
  font-weight: 700;
  color: #123f39;
}

.agent-version-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7f79;
  display: -webkit-box;
  overflow: hidden;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
}

.agent-version-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #6b7f79;
}

.tree-inline-note {
  padding: 8px 12px;
  font-size: 12px;
  color: #6b7f79;
}

.agent-list-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.agent-list-title {
  font-size: 14px;
  font-weight: 700;
  color: #123f39;
}

.agent-list-desc,
.agent-list-meta,
.status-main-hint,
.empty-note,
.result-desc,
.result-label,
.tool-event-card span {
  color: #5a726c;
  line-height: 1.6;
}

.agent-list-desc {
  margin-top: 8px;
  font-size: 13px;
}

.agent-list-meta {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.messages-container {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px;
  padding-bottom: 28px;
  scroll-behavior: smooth;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.message-item {
  display: flex;
  gap: 12px;

  &.message-user {
    justify-content: flex-end;

    .message-content {
      background: linear-gradient(135deg, #0f8a7d, #145d55);
      color: #fff;
    }

    .message-text {
      color: #fff;
    }
  }
}

.streaming-message {
  .message-content {
    box-shadow:
      inset 0 0 0 1px rgba(15, 138, 125, 0.1),
      0 10px 24px rgba(15, 138, 125, 0.08);
  }
}

.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 13px;
  font-weight: 700;
}

.assistant-avatar {
  background: rgba(15, 138, 125, 0.12);
  color: #0f5a4e;
  width: auto;
  min-width: 52px;
  padding: 0 10px;
  font-size: 11px;
}

.thinking-bubble {
  align-items: center;
}

.thinking-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.thinking-main-row {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #123f39;
  font-weight: 600;
}

.thinking-sub-row {
  font-size: 12px;
  color: #6b7f79;
}

.thinking-dots {
  display: inline-flex;
  gap: 2px;
  color: #0f8a7d;
}

.thinking-dots .dot {
  animation: thinkingBlink 1.2s infinite ease-in-out;
}

.thinking-dots .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking-dots .dot:nth-child(3) {
  animation-delay: 0.4s;
}

.user-avatar {
  background: rgba(15, 61, 54, 0.08);
  color: #123f39;
}

.message-content {
  max-width: min(880px, 88%);
  padding: 14px 16px;
  border-radius: 18px;
  background: #f3f8f6;
  box-shadow: inset 0 0 0 1px rgba(15, 61, 54, 0.05);
}

.progress-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(15, 61, 54, 0.08);
}

.timeline-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.step-dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.25);
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.08);
  flex: none;
}

.step-dot.active {
  background: #14b8a6;
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.14);
}

.step-dot.success {
  background: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.12);
}

.step-dot.warning {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.step-text {
  font-size: 13px;
  font-weight: 600;
  color: #123f39;
}

.step-meta {
  font-size: 12px;
  color: #6b7f79;
  line-height: 1.5;
}

.message-text {
  line-height: 1.65;
  color: inherit;
}

.message-text:deep(p),
.message-text:deep(ul),
.message-text:deep(ol),
.message-text:deep(table),
.message-text:deep(blockquote),
.message-text:deep(pre) {
  margin: 0 0 12px;
}

.message-text:deep(*:last-child) {
  margin-bottom: 0;
}

.message-text:deep(ul),
.message-text:deep(ol) {
  padding-left: 20px;
}

.message-text:deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 61, 54, 0.08);
  font-size: 12px;
}

.message-user .message-text:deep(code) {
  background: rgba(255, 255, 255, 0.16);
}

.input-area {
  padding: 0 18px 18px;
  position: sticky;
  bottom: 0;
  z-index: 2;
  border-top: 1px solid rgba(15, 61, 54, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(255, 255, 255, 0.98) 24%, #ffffff 100%);
  box-shadow: 0 -10px 24px rgba(15, 61, 54, 0.06);
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  margin-top: 18px;
}

.send-btn {
  height: 42px;
}

.input-tip-row {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.result-panels {
  display: block;
  min-height: 0;
}

.result-collapse {
  border-top: 1px solid rgba(15, 61, 54, 0.08);
  border-bottom: 1px solid rgba(15, 61, 54, 0.08);
}

.result-collapse :deep(.el-collapse-item__header) {
  min-height: 56px;
  padding: 0 18px;
  background: rgba(247, 251, 250, 0.92);
  color: #123f39;
  font-weight: 700;
}

.result-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
}

.result-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.result-collapse-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.result-card,
.status-card {
  border-radius: 18px;
  border: 1px solid rgba(15, 61, 54, 0.08);
  background: #fff;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
}

.result-title {
  font-size: 16px;
  font-weight: 700;
  color: #123f39;
}

.result-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.memory-summary-card {
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(18, 63, 57, 0.08);
  background: linear-gradient(180deg, rgba(251, 254, 253, 0.94) 0%, rgba(244, 250, 247, 0.98) 100%);
  display: grid;
  gap: 8px;
}

.memory-summary-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.memory-summary-title {
  font-size: 13px;
  color: #123f39;
}

.memory-summary-body {
  font-size: 12px;
  line-height: 1.7;
  color: #35524c;
}

.memory-summary-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 12px;
  color: #6b7f79;
}

.memory-summary-meta.subtle {
  margin-top: -2px;
}

.memory-summary-missing {
  display: grid;
  gap: 6px;
}

.memory-summary-missing-item {
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(18, 63, 57, 0.05);
  color: #4f6660;
  font-size: 12px;
  line-height: 1.5;
}

.workflow-stage-list {
  display: grid;
  gap: 10px;
}

.workflow-stage-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(18, 63, 57, 0.04);

  &.done {
    background: rgba(22, 163, 74, 0.08);
  }

  &.current {
    background: rgba(59, 130, 246, 0.08);
  }
}

.workflow-stage-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 999px;
  background: #cbd5e1;
}

.workflow-stage-item.done .workflow-stage-dot {
  background: #16a34a;
}

.workflow-stage-item.current .workflow-stage-dot {
  background: #2563eb;
}

.workflow-stage-name {
  font-size: 13px;
  font-weight: 700;
  color: #123f39;
}

.workflow-stage-desc,
.workflow-next-action {
  font-size: 12px;
  line-height: 1.6;
  color: #5a726c;
}

.compact-list {
  display: grid;
  gap: 8px;
}

.list-row {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(18, 63, 57, 0.04);
  color: #35524c;
  line-height: 1.6;
}

.result-worker-list {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.result-worker-card {
  padding: 12px;
  border-radius: 14px;
  background: rgba(18, 63, 57, 0.04);
  border: 1px solid rgba(18, 63, 57, 0.08);
}

.result-worker-group {
  margin-top: 8px;
}

.result-worker-group-title {
  font-size: 11px;
  font-weight: 700;
  color: #1d7b52;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.result-worker-title-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #6b7f79;

  strong {
    color: #123f39;
    font-size: 13px;
  }
}

.result-worker-summary {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: #35524c;
}

.result-worker-artifact {
  margin-top: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(18, 63, 57, 0.08);
}

.result-worker-artifact-title {
  font-size: 12px;
  font-weight: 700;
  color: #123f39;
}

.result-worker-artifact-path {
  margin-top: 4px;
  font-size: 11px;
  color: #6b7f79;
  word-break: break-all;
}

.result-worker-artifact-content {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #35524c;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-worker-artifact-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.evaluation-review-form {
  display: grid;
  gap: 14px;
}

.evaluation-review-field {
  display: grid;
  gap: 8px;
}

.evaluation-review-label {
  font-size: 13px;
  font-weight: 700;
  color: #123f39;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.status-main-hint {
  font-size: 14px;
}

.status-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.status-metric-item {
  padding: 12px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f6fbf9 0%, #edf6f2 100%);
  display: flex;
  flex-direction: column;
  gap: 6px;

  span {
    font-size: 12px;
    color: #6b7f79;
  }

  strong {
    color: #123f39;
    font-size: 15px;
  }
}

.tool-event-list {
  display: grid;
  gap: 10px;
}

.tool-event-card {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(255, 255, 255, 0.86);
  color: #35524c;
  border-radius: 14px;
}

.tool-event-card.info {
  border: 1px solid rgba(15, 90, 78, 0.1);
}

.tool-event-card.success {
  border: 1px solid rgba(29, 122, 74, 0.16);
}

.tool-event-card.warning {
  border: 1px solid rgba(196, 98, 49, 0.18);
}

.tool-event-status {
  width: auto;
  min-width: 56px;
  padding: 2px 8px;
  background: rgba(15, 90, 78, 0.08);
  color: #0f5a4e;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.version-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.version-detail-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.version-detail-title {
  font-size: 18px;
  font-weight: 700;
  color: #123f39;
}

.version-detail-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7f79;
  word-break: break-all;
}

.version-detail-header-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.version-detail-body {
  min-height: 160px;
}

.version-detail-grid {
  display: grid;
  gap: 16px;
}

.version-detail-section {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(15, 61, 54, 0.08);
  background: linear-gradient(180deg, #fbfefd 0%, #f6fbf9 100%);
}

.summary-section {
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.92) 0%, #ffffff 100%);
}

.version-detail-section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: #123f39;
}

.version-detail-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.version-detail-section-head .version-detail-section-title {
  margin-bottom: 0;
}

.version-detail-section-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.version-detail-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.version-detail-summary-item {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  display: flex;
  flex-direction: column;
  gap: 6px;

  span {
    font-size: 12px;
    color: #6b7f79;
  }

  strong {
    color: #123f39;
    word-break: break-word;
  }
}

.version-detail-description {
  margin-top: 14px;
  line-height: 1.7;
  color: #35524c;
}

.detail-tag-wrap {
  gap: 8px;
}

.version-detail-meta-line {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  color: #5a726c;
  font-size: 13px;
}

.prompt-section-list {
  display: grid;
  gap: 12px;
}

.prompt-section-card {
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(15, 61, 54, 0.06);
  overflow: hidden;
}

.prompt-section-title {
  padding: 12px 14px;
  font-size: 13px;
  font-weight: 700;
  color: #123f39;
  border-bottom: 1px solid rgba(15, 61, 54, 0.06);
}

.prompt-section-content {
  margin: 0;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: #35524c;
  background: transparent;
  font-family: "Cascadia Code", "Consolas", monospace;
  font-size: 12px;
}

.version-detail-evaluation-card {
  display: grid;
  gap: 12px;
}

.evaluation-layer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.compact-layer-grid {
  margin-top: 10px;
}

.evaluation-layer-card {
  border: 1px solid rgba(71, 118, 110, 0.16);
  border-radius: 14px;
  background: rgba(250, 248, 242, 0.86);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}

.evaluation-layer-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.evaluation-layer-meta {
  font-size: 12px;
  color: #6b7d78;
}

.layer-summary-list {
  margin-top: 0;
}

.list-row-danger {
  color: #9f2f2f;
}

.list-row-warning {
  color: #8a5d12;
}

.version-detail-runtime-card {
  display: grid;
  gap: 12px;
}

.runtime-report-card {
  background: rgba(255, 255, 255, 0.92);
}

.runtime-report-content {
  max-height: 420px;
  overflow: auto;
}

.runtime-report-markdown {
  white-space: normal;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
}

.runtime-report-markdown:deep(h1),
.runtime-report-markdown:deep(h2),
.runtime-report-markdown:deep(h3),
.runtime-report-markdown:deep(h4),
.runtime-report-markdown:deep(h5),
.runtime-report-markdown:deep(h6) {
  margin: 0 0 12px;
  color: #123f39;
  line-height: 1.45;
}

.runtime-report-markdown:deep(p),
.runtime-report-markdown:deep(ul),
.runtime-report-markdown:deep(ol),
.runtime-report-markdown:deep(table),
.runtime-report-markdown:deep(blockquote),
.runtime-report-markdown:deep(pre) {
  margin: 0 0 12px;
}

.runtime-report-markdown:deep(*:last-child) {
  margin-bottom: 0;
}

.runtime-report-markdown:deep(ul),
.runtime-report-markdown:deep(ol) {
  padding-left: 20px;
}

.runtime-report-markdown:deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.runtime-report-markdown:deep(th),
.runtime-report-markdown:deep(td) {
  padding: 8px 10px;
  border: 1px solid rgba(15, 61, 54, 0.12);
  text-align: left;
  vertical-align: top;
}

.runtime-report-markdown:deep(thead th) {
  background: rgba(15, 61, 54, 0.05);
}

.runtime-report-markdown:deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 61, 54, 0.08);
  font-size: 12px;
  font-family: "Cascadia Code", "Consolas", monospace;
}

.runtime-report-markdown:deep(pre) {
  padding: 12px;
  border-radius: 10px;
  background: rgba(15, 61, 54, 0.04);
  overflow: auto;
}

.runtime-report-markdown:deep(pre code) {
  padding: 0;
  background: transparent;
}

.runtime-report-markdown:deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid rgba(15, 61, 54, 0.18);
  color: #4f6762;
}

.runtime-json-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.runtime-json-content {
  white-space: pre;
  font-family: "Cascadia Code", "Consolas", monospace;
  font-size: 12px;
}

.evaluation-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .workspace-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .status-sidebar-scroll {
    overflow: visible;
    padding-right: 0;
  }
}

@media (max-width: 768px) {
  .nanobot-agent-studio-page {
    min-height: auto;
    padding: 16px;
  }

  .page-header,
  .input-row,
  .input-tip-row {
    flex-direction: column;
    align-items: stretch;
  }

  .status-metrics {
    grid-template-columns: minmax(0, 1fr);
  }

  .memory-summary-grid,
  .version-detail-summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .evaluation-layer-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .version-detail-header {
    flex-direction: column;
  }

  .version-detail-header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .version-detail-section-actions {
    width: 100%;
  }
}

@keyframes thinkingBlink {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-1px);
  }
}
</style>