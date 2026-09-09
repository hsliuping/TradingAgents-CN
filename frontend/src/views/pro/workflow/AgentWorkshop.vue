<template>
  <div class="agent-workshop-page">
    <div class="page-header">
      <div class="page-title-block">
        <div class="back-row">
          <el-button text @click="goBackToManager">
            返回管理页
          </el-button>
        </div>
        <h1>Agent 工坊</h1>
        <p>这里是标准工作页：先聊需求，再直接生成可测试版本，最后做验证和迭代。若你更偏好对话式操作，可以切到助手模式。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="router.push('/workflow/agent-studio')">
          助手模式
        </el-button>
        <el-button type="primary" plain @click="startNewDraft">
          新建 Agent
        </el-button>
        <el-button @click="refreshAll" :loading="loadingSpecs || loadingCurrentSession">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="workspace-shell single-pane">
      <section class="flow-stage">
        <div v-if="!hasWorkspaceContext" class="empty-stage-card with-create-card">
          <div class="empty-stage-title">从这里开始一个新 Agent</div>
          <div class="empty-stage-text">这个页面现在只负责当前 Agent 的讨论、生成、测试和迭代。已有草稿和历史 Agent 请回管理页查看。</div>
          <div class="empty-stage-steps">
            <div class="empty-step">1. 聊需求</div>
            <div class="empty-step">2. 确认并生成</div>
            <div class="empty-step">3. 测试验证</div>
            <div class="empty-step">4. 提意见迭代</div>
          </div>

          <el-card class="inline-create-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span>新建 Agent</span>
              </div>
            </template>

            <el-input
              v-model="description"
              type="textarea"
              :rows="6"
              resize="none"
              placeholder="例如：我要做一个新的股票估值分析师，它要能给出估值区间、解释假设、说明失效条件，但不要直接给交易建议。"
            />

            <div class="action-row">
              <el-button type="primary" :loading="starting" :disabled="!description.trim()" @click="handleStartSession">
                开始讨论
              </el-button>
            </div>

            <div class="examples">
              <div class="examples-title">快速填充</div>
              <el-button text @click="fillExample('valuation')">股票估值分析师</el-button>
              <el-button text @click="fillExample('industry')">行业比较研究员</el-button>
              <el-button text @click="fillExample('watcher')">财报跟踪助手</el-button>
            </div>
          </el-card>
        </div>

        <template v-else>
          <el-card class="focus-card" shadow="never">
            <div class="focus-card-inner">
              <div>
                <div class="focus-label">当前 Agent</div>
                <div class="focus-title-row">
                  <div class="focus-title">{{ selectedSpecName }}</div>
                  <el-tag v-if="workshopMaintenanceStatus === 'unmaintained'" type="danger" effect="plain">停止维护</el-tag>
                </div>
                <div class="focus-subtitle">{{ focusSubtitle }}</div>
              </div>
              <div class="focus-metrics">
                <div class="metric-item">
                  <span>阶段</span>
                  <strong>{{ summaryStageText }}</strong>
                </div>
                <div class="metric-item">
                  <span>信息齐备度</span>
                  <strong>{{ Math.round((currentSession?.completeness_score || previewResult?.completeness_score || 0) * 100) }}%</strong>
                </div>
                <div class="metric-item">
                  <span>状态</span>
                  <el-tag :type="statusTagType" effect="plain">{{ statusText }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>

          <div class="flow-switcher">
            <button
              v-for="step in flowSteps"
              :key="step.key"
              type="button"
              :class="['flow-switch', { active: activeStep === step.key }]"
              @click="activeStep = step.key"
            >
              <span class="flow-switch-index">{{ step.index }}</span>
              <span class="flow-switch-text">
                <strong>{{ step.title }}</strong>
                <small>{{ step.description }}</small>
              </span>
            </button>
          </div>

          <el-alert
            v-if="currentSession?.feasibility_status === 'not-feasible'"
            class="status-alert"
            type="error"
            :closable="false"
            :title="currentSession.refusal_reason || '当前需求超出 Agent 工坊可支持范围，先调整目标再继续。'"
          />
          <el-alert
            v-else-if="workshopMaintenanceStatus === 'unmaintained'"
            class="status-alert"
            type="warning"
            :closable="false"
            title="当前识别到的运行 Agent 属于 v1.0 遗留实现，已停止维护；如继续演进，建议迁移到 v2.0 Agent 标识和运行时。"
          />
          <el-alert
            v-else-if="currentSession?.feasibility_status === 'need-clarification'"
            class="status-alert"
            type="warning"
            :closable="false"
            title="需求还没澄清清楚，先把目标、边界和输出说完整，再继续往后走。"
          />

          <div v-if="activeStep === 'discuss'" class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>讨论需求</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" @click="refreshSession" :loading="loadingCurrentSession">{{ isNanobotDiscussionSession ? '检查 Draft' : '刷新会话' }}</el-button>
                    <el-button size="small" type="success" @click="handlePreviewSpec" :loading="previewing" :disabled="!currentSession">{{ isNanobotDiscussionSession ? (replyMessage.trim() ? '发送并打开 Draft' : '打开已生成 Draft') : '进入规格确认' }}</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!currentSession" class="empty-state compact">当前没有进行中的会话。</div>
              <template v-else>
                <div class="discuss-workbench">
                  <section class="discuss-pane discuss-main-pane">
                    <el-alert
                      v-if="nanobotDraftLink && isNanobotDiscussionSession"
                      class="status-alert"
                      type="success"
                      :closable="false"
                      :title="`Nanobot 已同步 Draft：${nanobotDraftLink.specName}。你可以继续在这里讨论，确认后再进入规格确认。`"
                    />
                    <div class="chat-panel">
                      <div v-for="(message, index) in displayedDiscussionMessages" :key="index" :class="['chat-row', message.role]">
                        <div class="bubble">
                          <div class="bubble-role">{{ message.role === 'assistant' ? (isNanobotDiscussionSession ? 'Nanobot' : '工坊助手') : '你' }}</div>
                          <div class="bubble-content markdown-body" v-html="renderMarkdown(message.content)"></div>
                        </div>
                      </div>
                    </div>

                    <div class="compose-panel-header">
                      <div>
                        <div class="compose-panel-title">继续补充</div>
                        <div class="compose-panel-hint">把你想补充、修正或强调的点直接写在这里。</div>
                      </div>
                    </div>
                    <div class="composer composer-embedded">
                      <el-input
                        v-model="replyMessage"
                        type="textarea"
                        :rows="4"
                        resize="none"
                        placeholder="直接补充你想要的效果，或者告诉我哪里理解错了。"
                        @keydown.enter.ctrl.prevent="handleRespond"
                      />
                      <div class="action-row between">
                        <div class="hint-text">按 Ctrl + Enter 也可以发送</div>
                        <div class="session-toolbar-actions">
                          <el-button type="primary" :disabled="!replyMessage.trim() || nanobotStreaming" :loading="responding" @click="handleRespond">
                            继续讨论
                          </el-button>
                          <el-button type="success" plain :disabled="!currentSession || responding || nanobotStreaming" :loading="previewing" @click="handlePreviewSpec">
                            {{ isNanobotDiscussionSession ? (replyMessage.trim() ? '发送并下一步' : '检查并下一步') : '下一步' }}
                          </el-button>
                        </div>
                      </div>
                    </div>
                  </section>

                  <aside class="discuss-pane discuss-progress-pane">
                    <div class="progress-sidebar-header">
                      <div>
                        <div class="progress-sidebar-title">Nanobot 最近动作</div>
                        <div class="progress-sidebar-hint">这里显示后台处理进度和工具执行轨迹。</div>
                      </div>
                      <el-button v-if="nanobotStreaming" text @click="cancelNanobotStreaming">停止</el-button>
                    </div>

                    <div v-if="shouldShowNanobotStreamPanel" class="nanobot-stream-panel sidebar-mode">
                      <div class="nanobot-stream-hint sidebar-hint">{{ nanobotProgressHint || '当前会话已连接到 Nanobot。' }}</div>
                      <div v-if="nanobotToolEvents.length" class="nanobot-tool-event-list compact-list">
                        <div v-for="event in nanobotToolEvents" :key="event.key" :class="['nanobot-tool-event', event.tone, 'sidebar-event']">
                          <span class="nanobot-tool-status">{{ event.statusLabel }}</span>
                          <strong>{{ event.title }}</strong>
                          <span v-if="event.detail">{{ event.detail }}</span>
                        </div>
                      </div>
                    </div>

                    <div v-else class="progress-placeholder">
                      <div class="progress-placeholder-title">等待下一步动作</div>
                      <div class="progress-placeholder-text">开始讨论或补充需求后，这里会实时显示 Nanobot 的处理进度。</div>
                    </div>
                  </aside>
                </div>
              </template>
            </el-card>
          </div>

          <div v-else-if="activeStep === 'spec'" class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>确认规格</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" type="success" @click="handlePreviewSpec" :loading="previewing" :disabled="!currentSession">刷新规格</el-button>
                    <el-button size="small" type="primary" @click="handleConfirmAndBuildVersion" :loading="confirmingSpec || buildingVersion" :disabled="!canAdvance">直接生成可测试版本</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!displaySpec" class="empty-state compact">先完成一轮需求讨论，再生成规格快照。</div>
              <div v-else class="spec-panel">
                <div v-if="latestVersion" class="field-block">
                  <div class="field-label">已生成可测试版本</div>
                  <div class="note-item">
                    当前草案已经生成完成，下一步直接去“测试验证”做调试运行即可。如果结果不对，再根据测试结果发起下一轮迭代。
                  </div>
                  <div class="action-row between">
                    <div class="hint-text">这里不再重复展示前面的需求对话，避免和测试页面信息混在一起。</div>
                    <div class="session-toolbar-actions">
                      <el-button @click="activeStep = 'discuss'">回讨论区补充</el-button>
                      <el-button type="primary" @click="activeStep = 'version'">去测试验证</el-button>
                    </div>
                  </div>
                </div>
                <div class="spec-title">{{ displaySpec.name }}</div>
                <div class="spec-goal">{{ displaySpec.primary_goal }}</div>

                <div class="field-block">
                  <div class="field-label">职责</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in displaySpec.responsibilities" :key="item" class="tag-item">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">输出</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in displaySpecOutputTags" :key="item" class="tag-item" type="success">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">非目标</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in displaySpec.non_goals" :key="item" class="tag-item" type="warning">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block spec-confirm-block" v-if="currentSession && !latestVersion">
                  <div class="field-label">最后确认一下</div>
                  <div class="note-item">
                    这里不用把需求重新说一遍。现在只要做两件事：
                    如果当前草案没问题，直接生成一个可测试版本；如果有不对的地方，补一句你想改什么。
                  </div>
                  <div v-if="specPendingQuestions.length" class="confirm-question-list">
                    <div v-for="(question, index) in specPendingQuestions" :key="`confirm-${question}`" class="confirm-question-item">
                      <span class="confirm-question-index">{{ index + 1 }}</span>
                      <span>{{ question }}</span>
                    </div>
                  </div>
                  <el-input
                    v-model="specFeedbackMessage"
                    type="textarea"
                    :rows="4"
                    resize="none"
                    placeholder="例如：整体没问题，继续。或者：输出里请单列三种估值方法结果，不要只给一个综合结论。"
                  />
                  <div class="action-row between">
                    <el-button text @click="fillSpecDefaultReply">帮我填入默认回复</el-button>
                    <div class="session-toolbar-actions">
                      <el-button @click="activeStep = 'discuss'">回讨论区详细补充</el-button>
                      <el-button type="success" plain :loading="confirmingSpec || buildingVersion" :disabled="!canAdvance" @click="handleAcceptRecommendedSpec">按当前方案直接生成</el-button>
                      <el-button type="primary" :disabled="!specFeedbackMessage.trim()" :loading="confirmingSpec" @click="handleSubmitSpecFeedback">先保存修改</el-button>
                      <el-button type="primary" :disabled="!canAdvance" :loading="confirmingSpec || buildingVersion" @click="handleConfirmAndBuildVersion">保存修改后生成</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">进入下一步前</div>
                  <div class="note-item">
                    这一步只确认“这个 Agent 要做什么、产出什么”。确认后会直接生成一个可测试版本，你可以马上调试、评估，再根据结果继续提修改意见。
                  </div>
                </div>
              </div>
            </el-card>

          </div>

          <div v-else-if="activeStep === 'gap'" class="step-layout single-column">
            <!-- 缺口分析报告 -->
            <el-card v-if="gapReport" class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>缺口分析报告</span>
                  <div class="session-toolbar-actions">
                    <el-tag v-if="gapReport.blocking_gaps?.length" type="danger" size="small">{{ gapReport.blocking_gaps.length }} 个阻断性缺口</el-tag>
                    <el-tag v-else type="success" size="small">无阻断性缺口</el-tag>
                    <el-button size="small" type="primary" :loading="analyzing" @click="handleAnalyzeGaps">重新分析</el-button>
                    <el-button size="small" @click="activeStep = latestVersion ? 'version' : 'spec'">返回</el-button>
                  </div>
                </div>
              </template>

              <!-- 错误消息 -->
              <el-alert v-if="gapReport.error_message" type="error" :closable="false" show-icon style="margin-bottom:16px">
                <template #title>分析过程中出现错误</template>
                {{ gapReport.error_message }}
              </el-alert>

              <!-- 现有工具 -->
              <div class="gap-section" v-if="gapReport.existing_tools?.length">
                <h4>现有工具（{{ gapReport.existing_tools.length }} 个）</h4>
                <div class="gap-tool-chips">
                  <el-tag v-for="tool in gapReport.existing_tools" :key="tool" type="info" size="small" effect="plain" style="margin:2px 4px 2px 0">
                    {{ gapExistingToolLabelMap.get(tool) || tool }}
                  </el-tag>
                </div>
              </div>

              <!-- 阻断性缺口 -->
              <div class="gap-section" v-if="gapReport.blocking_gaps?.length">
                <h4 style="color:#f56c6c">阻断性缺口（{{ gapReport.blocking_gaps.length }} 个）</h4>
                <ul class="gap-list danger">
                  <li v-for="(gap, idx) in gapReport.blocking_gaps" :key="idx">{{ gap }}</li>
                </ul>
              </div>

              <!-- 建议工具 -->
              <div class="gap-section" v-if="gapReport.suggested_tools?.length">
                <h4>建议补齐工具（{{ gapReport.suggested_tools.length }} 个）</h4>
                <el-table :data="gapReport.suggested_tools" size="small" border stripe max-height="300">
                  <el-table-column prop="tool_id" label="工具 ID" width="220" />
                  <el-table-column prop="name" label="名称" width="160" />
                  <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
                  <el-table-column prop="rationale" label="推荐理由" min-width="180" show-overflow-tooltip />
                </el-table>
              </div>

              <!-- 可推断缺口 -->
              <div class="gap-section" v-if="gapReport.inferable_gaps?.length">
                <h4>可推断覆盖（{{ gapReport.inferable_gaps.length }} 个）</h4>
                <el-table :data="gapReport.inferable_gaps" size="small" border stripe max-height="300">
                  <el-table-column prop="gap" label="缺口" min-width="200" show-overflow-tooltip />
                  <el-table-column label="可从以下工具推断" min-width="250">
                    <template #default="{ row }">
                      <el-tag v-for="t in row.inferable_from" :key="t" size="small" effect="plain" style="margin:1px 3px 1px 0">{{ t }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="inference_approach" label="推断方式" width="160" show-overflow-tooltip />
                </el-table>
              </div>

              <!-- 降级策略 -->
              <div class="gap-section" v-if="gapReport.fallback_strategy?.length">
                <h4>降级策略</h4>
                <ul class="gap-list">
                  <li v-for="(s, idx) in gapReport.fallback_strategy" :key="idx">{{ s }}</li>
                </ul>
              </div>

              <!-- 构建建议 -->
              <div class="gap-section" v-if="gapReport.build_recommendations?.length">
                <h4>构建建议</h4>
                <ul class="gap-list">
                  <li v-for="(r, idx) in gapReport.build_recommendations" :key="idx">{{ r }}</li>
                </ul>
              </div>

              <!-- 手动依赖 -->
              <div class="gap-section" v-if="gapReport.manual_dependencies?.length">
                <h4>手动依赖</h4>
                <ul class="gap-list">
                  <li v-for="(d, idx) in gapReport.manual_dependencies" :key="idx">{{ d }}</li>
                </ul>
              </div>

              <!-- 备注 -->
              <div class="gap-section" v-if="gapReport.notes?.length">
                <h4>备注</h4>
                <ul class="gap-list">
                  <li v-for="(n, idx) in gapReport.notes" :key="idx">{{ n }}</li>
                </ul>
              </div>

              <!-- 原始 LLM 输出（调试用） -->
              <el-collapse v-if="gapReport.raw_response" style="margin-top:16px">
                <el-collapse-item title="原始 LLM 输出（调试用）">
                  <el-input type="textarea" :model-value="gapReport.raw_response" readonly :rows="10" />
                </el-collapse-item>
              </el-collapse>
            </el-card>

            <!-- 未分析状态 -->
            <el-card v-else class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>缺口分析</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" type="primary" :loading="analyzing" @click="handleAnalyzeGaps">开始分析</el-button>
                    <el-button size="small" @click="activeStep = 'spec'">返回</el-button>
                  </div>
                </div>
              </template>
              <div class="empty-state compact">
                <p>尚未执行能力缺口分析。点击"开始分析"扫描平台现有工具能力，对比 Agent 需求，生成缺口报告。</p>
              </div>
            </el-card>
          </div>

          <div v-else-if="activeStep === 'version'" class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>测试验证</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" @click="activeStep = 'spec'">返回确认页</el-button>
                    <el-button size="small" type="primary" @click="handleBuildVersion" :loading="buildingVersion" :disabled="!canAdvance">重新生成</el-button>
                    <el-button size="small" type="success" plain @click="openEvaluateDialog" :disabled="!latestVersion">开始测试</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!latestVersion" class="empty-state compact">先确认规格并生成一个可测试版本。</div>
              <div v-else class="version-panel">
                <div class="spec-title">{{ latestVersion.agent_metadata?.name || latestVersion.version_id }}</div>
                <div class="version-meta-row">
                  <el-tag effect="plain">{{ latestVersion.version_id }}</el-tag>
                  <el-tag type="warning" effect="plain">{{ latestVersion.status }}</el-tag>
                  <el-tag type="success" effect="plain">v{{ latestVersion.version }}</el-tag>
                  <el-tag v-if="workshopMaintenanceStatus === 'unmaintained'" type="danger" effect="plain">停止维护</el-tag>
                </div>

                <div class="field-block">
                  <div class="field-label">现在做什么</div>
                  <div class="note-item">版本已经生成完成。下一步直接点“开始测试”，先跑一遍默认样本，确认输出是否符合预期；不满意再进入下一轮迭代。</div>
                </div>

                <div class="field-block">
                  <div class="field-label">默认工具</div>
                  <div v-if="versionDefaultToolCards.length" class="default-tool-list">
                    <div v-for="item in versionDefaultToolCards" :key="item.id" class="default-tool-card">
                      <div class="default-tool-header">
                        <div class="default-tool-name-row">
                          <span class="default-tool-name">{{ item.name }}</span>
                          <span class="default-tool-id">{{ item.id }}</span>
                        </div>
                      </div>
                      <div class="default-tool-description">{{ item.description }}</div>
                    </div>
                  </div>
                  <div v-else class="note-item compact-note">
                    当前版本尚未绑定默认工具。
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">Prompt 摘要</div>
                  <div class="note-item">
                    模板：{{ latestVersion.prompt_template_ref?.template_name || '未生成' }}
                    <br>
                    模板 ID：{{ latestVersion.prompt_template_ref?.template_id || '无' }}
                  </div>
                  <div v-if="latestVersionPrompt?.message && !promptSections.length" class="note-item compact-note">{{ latestVersionPrompt.message }}</div>
                  <div v-for="section in promptSections" :key="section.key" class="field-block" style="margin-top: 12px;">
                    <div class="field-label">{{ section.label }}</div>
                    <pre class="runtime-raw-response">{{ section.value }}</pre>
                  </div>
                </div>
                <div class="field-block" v-if="versionPromptProjectMemorySummary || latestVersion.last_evaluation_summary">
                  <div class="field-label">L4 项目长期记忆</div>
                  <div class="breakdown-grid project-memory-summary-grid">
                    <div v-if="versionPromptProjectMemorySummary" class="breakdown-card project-memory-summary-card">
                      <div class="breakdown-title">模板绑定状态</div>
                      <div class="project-memory-summary-meta">
                        <el-tag :type="getProjectMemorySummaryTagType(versionPromptProjectMemorySummary.review_status)" effect="plain">
                          {{ getProjectMemorySummaryStatusText(versionPromptProjectMemorySummary.review_status) }}
                        </el-tag>
                        <span>命中 {{ versionPromptProjectMemorySummary.matched_items }}/{{ versionPromptProjectMemorySummary.expected_items }}</span>
                      </div>
                      <div class="note-item compact-note">{{ versionPromptProjectMemorySummary.summary }}</div>
                      <div v-if="versionPromptProjectMemorySummary.missing_items_preview?.length" class="breakdown-group">
                        <div class="breakdown-label warning">缺失预览</div>
                        <div v-for="item in versionPromptProjectMemorySummary.missing_items_preview" :key="item" class="note-item compact-note warning-note">{{ item }}</div>
                      </div>
                    </div>
                    <div v-if="latestVersion.last_evaluation_summary" class="breakdown-card project-memory-summary-card">
                      <div class="breakdown-title">最近一次评估</div>
                      <div class="project-memory-summary-meta">
                        <el-tag :type="latestVersion.last_evaluation_summary.decision === 'pass' ? 'success' : latestVersion.last_evaluation_summary.decision === 'reject' ? 'danger' : 'warning'" effect="plain">
                          {{ latestVersion.last_evaluation_summary.decision === 'pass' ? '通过' : latestVersion.last_evaluation_summary.decision === 'reject' ? '拒绝' : '需要修改' }}
                        </el-tag>
                        <span>{{ formatDisplayTime(latestVersion.last_evaluation_summary.created_at) }}</span>
                      </div>
                      <div class="note-item compact-note">{{ latestVersion.last_evaluation_summary.project_memory_binding.summary }}</div>
                      <div class="project-memory-summary-meta subtle" v-if="latestVersion.last_evaluation_summary.worker_execution_mode || latestVersion.last_evaluation_summary.evaluation_status">
                        <span v-if="latestVersion.last_evaluation_summary.worker_execution_mode">执行器：{{ latestVersion.last_evaluation_summary.worker_execution_mode }}</span>
                        <span v-if="latestVersion.last_evaluation_summary.evaluation_status">评估状态：{{ latestVersion.last_evaluation_summary.evaluation_status }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">输出字段</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in Object.keys(latestVersion.output_schema?.properties || {})" :key="item" class="tag-item" type="success">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">评估维度</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in latestVersion.evaluation_policy?.dimensions || []" :key="item" class="tag-item">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block" v-if="latestExecutionPlan">
                  <div class="field-label">默认测试计划</div>
                  <div class="note-item" v-if="latestExecutionPlan.rationale">{{ latestExecutionPlan.rationale }}</div>
                  <div class="runtime-meta-row">
                    <span>模式：{{ latestExecutionPlan.mode || '工具驱动' }}</span>
                    <span>状态：{{ latestExecutionPlan.validation_status || '未运行' }}</span>
                  </div>
                  <div class="field-block" v-if="executionPlanSampleInputText" style="margin-top: 12px;">
                    <div class="field-label">默认调试输入</div>
                    <pre class="runtime-raw-response">{{ executionPlanSampleInputText }}</pre>
                  </div>
                  <div class="field-block" v-if="executionPlanStepCards.length" style="margin-top: 12px;">
                    <div class="field-label">测试步骤</div>
                    <div class="breakdown-grid">
                      <div v-for="item in executionPlanStepCards" :key="item.stepId" class="breakdown-card">
                        <div class="breakdown-title">{{ item.title }}</div>
                        <div class="note-item compact-note">{{ item.objective }}</div>
                        <div v-if="item.tools.length" class="breakdown-group">
                          <div class="breakdown-label">建议工具</div>
                          <div class="tag-wrap">
                            <el-tag v-for="tool in item.tools" :key="tool" class="tag-item" effect="plain">{{ tool }}</el-tag>
                          </div>
                        </div>
                        <div v-if="item.expectedEvidence.length" class="breakdown-group">
                          <div class="breakdown-label success">期望证据</div>
                          <div v-for="entry in item.expectedEvidence" :key="entry" class="note-item compact-note">{{ entry }}</div>
                        </div>
                        <div v-if="item.failureSignals.length" class="breakdown-group">
                          <div class="breakdown-label warning">失败信号</div>
                          <div v-for="entry in item.failureSignals" :key="entry" class="note-item compact-note">{{ entry }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="field-block" v-if="executionPlanAcceptanceChecks.length" style="margin-top: 12px;">
                    <div class="field-label">验收清单</div>
                    <div v-for="item in executionPlanAcceptanceChecks" :key="item" class="note-item compact-note">{{ item }}</div>
                  </div>
                  <div class="field-block" v-if="executionPlanFallbackRules.length" style="margin-top: 12px;">
                    <div class="field-label">降级规则</div>
                    <div v-for="item in executionPlanFallbackRules" :key="item" class="note-item compact-note">{{ item }}</div>
                  </div>
                </div>
                <div class="action-row right">
                  <el-button type="success" @click="openEvaluateDialog">开始测试</el-button>
                  <el-button type="primary" plain @click="handleIterateVersion" :loading="iteratingVersion">基于当前结果发起下一轮迭代</el-button>
                </div>
              </div>
            </el-card>
          </div>

          <div v-else class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>评估与迭代</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" type="success" plain @click="openEvaluateDialog" :disabled="!latestVersion">调试运行与评估</el-button>
                    <el-button size="small" type="primary" plain @click="handleIterateVersion" :loading="iteratingVersion" :disabled="!latestVersion">开始下一轮</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!latestEvaluation" class="empty-state compact">评估一次版本后，这里会显示得分、问题和建议。</div>
              <div v-else class="version-panel">
                <div class="version-meta-row">
                  <el-tag :type="latestEvaluation.decision === 'pass' ? 'success' : latestEvaluation.decision === 'reject' ? 'danger' : 'warning'" effect="plain">
                    {{ evaluationDecisionText }}
                  </el-tag>
                  <el-tag effect="plain">{{ evaluationTypeText }}</el-tag>
                </div>
                <div class="field-block" v-if="latestEvaluationProjectMemorySummary || latestEvaluationSummary">
                  <div class="field-label">L4 项目长期记忆</div>
                  <div class="breakdown-grid project-memory-summary-grid">
                    <div v-if="latestEvaluationProjectMemorySummary" class="breakdown-card project-memory-summary-card">
                      <div class="breakdown-title">当前评估绑定状态</div>
                      <div class="project-memory-summary-meta">
                        <el-tag :type="getProjectMemorySummaryTagType(latestEvaluationProjectMemorySummary.review_status)" effect="plain">
                          {{ getProjectMemorySummaryStatusText(latestEvaluationProjectMemorySummary.review_status) }}
                        </el-tag>
                        <span>命中 {{ latestEvaluationProjectMemorySummary.matched_items }}/{{ latestEvaluationProjectMemorySummary.expected_items }}</span>
                      </div>
                      <div class="note-item compact-note">{{ latestEvaluationProjectMemorySummary.summary }}</div>
                      <div class="project-memory-summary-meta subtle" v-if="latestEvaluationProjectMemorySummary.evaluation_status || latestEvaluationProjectMemorySummary.decision">
                        <span v-if="latestEvaluationProjectMemorySummary.evaluation_status">评估状态：{{ latestEvaluationProjectMemorySummary.evaluation_status }}</span>
                        <span v-if="latestEvaluationProjectMemorySummary.decision">结论：{{ latestEvaluationProjectMemorySummary.decision }}</span>
                      </div>
                      <div v-if="latestEvaluationProjectMemorySummary.missing_items_preview?.length" class="breakdown-group">
                        <div class="breakdown-label warning">缺失预览</div>
                        <div v-for="item in latestEvaluationProjectMemorySummary.missing_items_preview" :key="item" class="note-item compact-note warning-note">{{ item }}</div>
                      </div>
                    </div>
                    <div v-if="latestEvaluationSummary" class="breakdown-card project-memory-summary-card">
                      <div class="breakdown-title">评估摘要</div>
                      <div class="project-memory-summary-meta">
                        <el-tag :type="latestEvaluationSummary.decision === 'pass' ? 'success' : latestEvaluationSummary.decision === 'reject' ? 'danger' : 'warning'" effect="plain">
                          {{ latestEvaluationSummary.decision === 'pass' ? '通过' : latestEvaluationSummary.decision === 'reject' ? '拒绝' : '需要修改' }}
                        </el-tag>
                        <span>{{ formatDisplayTime(latestEvaluationSummary.created_at) }}</span>
                      </div>
                      <div class="note-item compact-note">{{ latestEvaluationSummary.project_memory_binding.summary }}</div>
                      <div class="project-memory-summary-meta subtle">
                        <span v-if="latestEvaluationSummary.worker_execution_mode">执行器：{{ latestEvaluationSummary.worker_execution_mode }}</span>
                        <span v-if="latestEvaluationSummary.review_mode">模式：{{ latestEvaluationSummary.review_mode }}</span>
                        <span v-if="latestEvaluationSummary.overall_score !== null && typeof latestEvaluationSummary.overall_score !== 'undefined'">综合分：{{ latestEvaluationSummary.overall_score }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="displayedRawBackendResult">
                  <div class="field-label">后端原始返回</div>
                  <div class="runtime-meta-row">
                    <span v-if="displayedRuntimeSymbol">标的：{{ displayedRuntimeSymbol }}</span>
                    <span v-if="displayedRuntimeDate">日期：{{ displayedRuntimeDate }}</span>
                    <span v-if="latestDebugResult?.output_field">输出字段：{{ latestDebugResult.output_field }}</span>
                  </div>
                  <div class="raw-result-box">{{ displayedRawBackendResult }}</div>
                </div>
                <div class="field-block" v-if="displayedRuntimeOutput">
                  <div class="field-label">本次调试输出</div>
                  <div class="runtime-meta-row">
                    <span v-if="displayedRuntimeSymbol">标的：{{ displayedRuntimeSymbol }}</span>
                    <span v-if="displayedRuntimeDate">日期：{{ displayedRuntimeDate }}</span>
                    <span v-if="displayedRuntimeGoal">目标：{{ displayedRuntimeGoal }}</span>
                  </div>
                  <div class="runtime-report-box">{{ displayedRuntimeOutput }}</div>
                </div>
                <div class="field-block evaluation-note-block">
                  <div class="field-label">评估依据</div>
                  <div class="note-item">当前正式评估采用 evidence-first：正式问题只来自结构化证据包。LLM 评审仅作为 advisory 展示，不再直接决定正式问题列表或发布结论。</div>
                </div>
                <div class="field-block" v-if="evaluationValiditySummary || evidenceInvalidReasons.length">
                  <div class="field-label">评估状态</div>
                  <div v-if="evaluationValiditySummary" class="note-item" :class="{ 'warning-note': evaluationEvidenceIncomplete }">{{ evaluationValiditySummary }}</div>
                  <div v-for="item in evidenceInvalidReasons" :key="item" class="note-item compact-note warning-note">{{ item }}</div>
                </div>
                <div class="field-block" v-if="latestEvaluation.details?.llm_review_error">
                  <div class="field-label">LLM 评审失败原因</div>
                  <div class="note-item error-note">{{ latestEvaluation.details.llm_review_error }}</div>
                </div>
                <div class="field-block" v-if="llmReviewSummary">
                  <div class="field-label">LLM 评审结论</div>
                  <div class="runtime-meta-row">
                    <span v-if="judgeModelText">评审模型：{{ judgeModelText }}</span>
                  </div>
                  <div class="note-item">{{ llmReviewSummary }}</div>
                </div>
                <div class="field-block" v-if="valuationTraceabilitySummary || valuationTraceabilityItems.length">
                  <div class="field-label">估值数字来源</div>
                  <div v-if="valuationTraceabilitySummary" class="note-item">{{ valuationTraceabilitySummary }}</div>
                  <div class="breakdown-grid" v-if="valuationTraceabilityItems.length">
                    <div v-for="item in valuationTraceabilityItems" :key="`${item.label}-${item.value}`" class="breakdown-card">
                      <div class="breakdown-title">{{ item.label }}</div>
                      <div class="note-item compact-note">{{ item.value }}</div>
                      <div class="breakdown-group">
                        <div class="breakdown-label" :class="item.tagClass">{{ item.judgement }}</div>
                        <div class="tag-wrap" v-if="item.evidenceTools.length">
                          <el-tag v-for="tool in item.evidenceTools" :key="tool" class="tag-item" effect="plain">{{ tool }}</el-tag>
                        </div>
                      </div>
                      <div v-if="item.notes.length" class="breakdown-group">
                        <div class="breakdown-label">说明</div>
                        <div v-for="entry in item.notes" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">得分</div>
                  <div class="score-grid">
                    <div v-for="item in evaluationScoreCards" :key="item.key" class="score-card">
                      <div class="score-key">{{ item.label }}</div>
                      <div class="score-desc">{{ item.description }}</div>
                      <div class="score-value">{{ item.value }}</div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="llmDimensionCards.length">
                  <div class="field-label">LLM 逐项判断</div>
                  <div class="breakdown-grid">
                    <div v-for="item in llmDimensionCards" :key="item.key" class="breakdown-card">
                      <div class="breakdown-title">{{ item.label }}</div>
                      <div class="score-desc" style="margin-bottom: 8px;">{{ item.description }}</div>
                      <div class="score-value" style="margin-bottom: 12px;">{{ item.score }}</div>
                      <div v-if="item.judgement" class="note-item compact-note">{{ item.judgement }}</div>
                      <div v-if="item.evidence.length" class="breakdown-group">
                        <div class="breakdown-label success">证据</div>
                        <div class="tag-wrap">
                          <el-tag v-for="entry in item.evidence" :key="entry" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
                        </div>
                      </div>
                      <div v-if="item.problems.length" class="breakdown-group">
                        <div class="breakdown-label warning">问题</div>
                        <div class="tag-wrap">
                          <el-tag v-for="entry in item.problems" :key="entry" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
                        </div>
                      </div>
                      <div v-if="item.suggestions.length" class="breakdown-group">
                        <div class="breakdown-label">建议</div>
                        <div v-for="entry in item.suggestions" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                      <div v-if="item.notes.length" class="breakdown-group">
                        <div class="breakdown-label">备注</div>
                        <div v-for="entry in item.notes" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="ruleBreakdownCards.length">
                  <div class="field-label">规则辅助检查</div>
                  <div class="breakdown-grid">
                    <div v-for="item in ruleBreakdownCards" :key="item.key" class="breakdown-card">
                      <div class="breakdown-title">{{ item.label }}</div>
                      <div v-if="item.matched.length" class="breakdown-group">
                        <div class="breakdown-label success">{{ item.matchedLabel }}</div>
                        <div class="tag-wrap">
                          <el-tag v-for="entry in item.matched" :key="entry" class="tag-item" type="success" effect="plain">{{ entry }}</el-tag>
                        </div>
                      </div>
                      <div v-if="item.missing.length" class="breakdown-group">
                        <div class="breakdown-label warning">{{ item.missingLabel }}</div>
                        <div class="tag-wrap">
                          <el-tag v-for="entry in item.missing" :key="entry" class="tag-item" type="warning" effect="plain">{{ entry }}</el-tag>
                        </div>
                      </div>
                      <div v-if="item.notes.length" class="breakdown-group">
                        <div class="breakdown-label">说明</div>
                        <div v-for="entry in item.notes" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="executionPlanReview">
                  <div class="field-label">执行计划验收</div>
                  <div class="runtime-meta-row">
                    <span>状态：{{ executionPlanReview.statusText }}</span>
                    <span>得分：{{ executionPlanReview.score }}</span>
                  </div>
                  <div v-if="executionPlanReview.sampleInputText" class="note-item compact-note">推荐样本：{{ executionPlanReview.sampleInputText }}</div>
                  <div class="breakdown-grid" v-if="executionPlanReview.acceptanceResults.length">
                    <div v-for="item in executionPlanReview.acceptanceResults" :key="item.label" class="breakdown-card">
                      <div class="breakdown-title">{{ item.label }}</div>
                      <div class="breakdown-group">
                        <div class="breakdown-label" :class="item.passed ? 'success' : 'warning'">{{ item.passed ? '通过' : '未通过' }}</div>
                        <div class="note-item compact-note">{{ item.detail }}</div>
                      </div>
                    </div>
                  </div>
                  <div class="breakdown-grid" v-if="executionPlanReview.matched.length || executionPlanReview.missing.length">
                    <div class="breakdown-card" v-if="executionPlanReview.matched.length">
                      <div class="breakdown-title">已满足</div>
                      <div v-for="item in executionPlanReview.matched" :key="item" class="note-item compact-note">{{ item }}</div>
                    </div>
                    <div class="breakdown-card" v-if="executionPlanReview.missing.length">
                      <div class="breakdown-title">待补齐</div>
                      <div v-for="item in executionPlanReview.missing" :key="item" class="note-item compact-note">{{ item }}</div>
                    </div>
                  </div>
                  <div class="field-block" v-if="executionPlanReview.notes.length" style="margin-top: 12px;">
                    <div class="field-label">说明</div>
                    <div v-for="item in executionPlanReview.notes" :key="item" class="note-item compact-note">{{ item }}</div>
                  </div>
                </div>
                <div class="field-block" v-if="latestEvaluation.details?.parsed_output_excerpt && !displayedRuntimeOutput">
                  <div class="field-label">评估使用的结果摘录</div>
                  <div class="runtime-report-box">{{ latestEvaluation.details.parsed_output_excerpt }}</div>
                </div>
                <div class="field-block" v-if="confirmedEvaluationIssues.length">
                  <div class="field-label">已证实问题</div>
                  <div v-for="item in confirmedEvaluationIssues" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="insufficientEvidenceCards.length">
                  <div class="field-label">证据不足项</div>
                  <div class="breakdown-grid">
                    <div v-for="item in insufficientEvidenceCards" :key="`${item.title}-${item.category}`" class="breakdown-card evidence-card">
                      <div class="breakdown-title">{{ item.title }}</div>
                      <div class="breakdown-label warning">证据不足</div>
                      <div v-if="item.evidence.length" class="breakdown-group">
                        <div class="breakdown-label">当前证据</div>
                        <div v-for="entry in item.evidence" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="evidenceWorkerCards.length">
                  <div class="field-label">证据 Worker 产物</div>
                  <div class="breakdown-grid">
                    <div v-for="item in evidenceWorkerCards" :key="item.key" class="breakdown-card">
                      <div class="breakdown-title">{{ item.workerName }}</div>
                      <div class="runtime-meta-row worker-meta-row">
                        <span>{{ item.statusText }}</span>
                        <span>{{ item.sourceText }}</span>
                      </div>
                      <div v-if="item.summary" class="note-item compact-note">{{ item.summary }}</div>
                      <div v-if="item.evidence.length" class="breakdown-group">
                        <div class="breakdown-label">证据摘要</div>
                        <div v-for="entry in item.evidence" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                      <div v-if="item.artifactGroups.length" class="breakdown-group">
                        <div class="breakdown-label success">结构化证据</div>
                        <div class="worker-artifact-group-list">
                          <div v-for="group in item.artifactGroups" :key="`${item.key}-${group.key}`" class="worker-artifact-group">
                            <div class="worker-artifact-group-title">{{ group.label }}</div>
                            <div class="worker-artifact-list">
                              <div v-for="artifact in group.items" :key="`${item.key}-${group.key}-${artifact.title}`" class="worker-artifact-item">
                                <div class="worker-artifact-title">{{ artifact.title }}</div>
                                <div v-for="entry in artifact.detailLines" :key="entry" class="worker-artifact-content">{{ entry }}</div>
                                <div v-if="artifact.tagEntries.length" class="tag-wrap worker-artifact-tags">
                                  <el-tag v-for="entry in artifact.tagEntries" :key="entry" class="tag-item" effect="plain">{{ entry }}</el-tag>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="latestEvaluation.recommendations?.length">
                  <div class="field-label">优化建议</div>
                  <div v-for="item in latestEvaluation.recommendations" :key="item" class="note-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="evaluationHistoryCards.length">
                  <div class="field-label">最近评估历史</div>
                  <div class="breakdown-grid project-memory-history-grid">
                    <div v-for="item in evaluationHistoryCards" :key="item.key" class="breakdown-card history-card">
                      <div class="breakdown-title history-card-title-row">
                        <span>{{ item.evaluationTypeText }}</span>
                        <el-tag :type="item.decisionType" effect="plain">{{ item.decisionText }}</el-tag>
                      </div>
                      <div class="project-memory-summary-meta subtle">
                        <span>{{ item.createdAt }}</span>
                        <span v-if="item.overallScore !== null && typeof item.overallScore !== 'undefined'">综合分：{{ item.overallScore }}</span>
                      </div>
                      <div v-if="item.projectMemorySummary" class="note-item compact-note">{{ item.projectMemorySummary.summary }}</div>
                      <div class="project-memory-summary-meta" v-if="item.projectMemorySummary">
                        <el-tag :type="getProjectMemorySummaryTagType(item.projectMemorySummary.review_status)" effect="plain">
                          {{ getProjectMemorySummaryStatusText(item.projectMemorySummary.review_status) }}
                        </el-tag>
                        <span>命中 {{ item.projectMemorySummary.matched_items }}/{{ item.projectMemorySummary.expected_items }}</span>
                      </div>
                      <div class="project-memory-summary-meta subtle" v-if="item.workerExecutionMode || item.evaluationStatus">
                        <span v-if="item.workerExecutionMode">执行器：{{ item.workerExecutionMode }}</span>
                        <span v-if="item.evaluationStatus">评估状态：{{ item.evaluationStatus }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
          </div>
        </template>
      </section>
    </div>

    <el-dialog v-model="evaluateDialogVisible" title="调试运行与结果评估" width="860px" destroy-on-close>
      <div class="evaluation-dialog">
        <el-form label-width="120px">
          <el-alert
            type="info"
            :closable="false"
            title="先做一次调试运行，确认输出没问题后，再发起结果评估。当前 Agent 工坊暂不提供样本基准评估入口。"
          />
          <el-form-item label="模型名称" style="margin-top: 16px;">
            <DeepModelSelector
              v-model="evaluationForm.llm.model"
              :available-models="availableModels"
              type="deep"
              width="320px"
            />
          </el-form-item>

          <el-form-item label="股票代码">
            <el-input v-model="evaluationForm.stock.symbol" placeholder="如 600519" style="max-width: 220px;" />
            <el-date-picker
              v-model="evaluationForm.stock.analysis_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="分析日期"
              style="width: 180px; margin-left: 12px"
            />
          </el-form-item>

          <el-form-item label="用户目标">
            <el-input v-model="evaluationForm.runtime_result.user_goal" placeholder="例如：希望得到可解释的估值区间与失效条件" />
          </el-form-item>

          <el-form-item label="运行结果">
            <el-input
              v-model="evaluationForm.runtime_result.output_text"
              type="textarea"
              :rows="10"
              resize="vertical"
              readonly
              placeholder="点击下方按钮后，这里会自动显示本次调试运行输出。"
            />
          </el-form-item>

          <el-form-item v-if="latestDebugResult?.debug_prompt?.user_prompt" label="提交 Prompt">
            <el-input
              :model-value="displayedDebugPrompt"
              type="textarea"
              :rows="10"
              resize="vertical"
              readonly
            />
          </el-form-item>

          <el-form-item v-if="latestDebugResult?.debug_prompt?.llm_final_response" label="LLM 返回原文">
            <el-input
              :model-value="latestDebugResult?.debug_prompt?.llm_final_response || ''"
              type="textarea"
              :rows="10"
              resize="vertical"
              readonly
            />
          </el-form-item>

          <el-form-item label="补充反馈">
            <el-input
              v-model="evaluationForm.user_feedback"
              type="textarea"
              :rows="3"
              resize="vertical"
              placeholder="可选，填写你对这次调试结果的主观评价。"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="evaluateDialogVisible = false">取消</el-button>
        <el-button type="primary" plain :loading="debuggingVersion" @click="handleDebugVersion">调试运行</el-button>
        <el-button type="primary" :loading="evaluatingVersion" :disabled="!canSubmitEvaluation" @click="handleEvaluateVersion">结果评估</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { renderMarkdown as safeMarkdown } from '@/utils/markdown'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import { toolsApi, type ToolMetadata } from '@/api/tools'
import agentWorkshopApi, {
  type AgentEvaluationReport,
  type AgentEvaluationEvidenceArtifact,
  type AgentEvaluationEvidenceBundle,
  type AgentEvaluationSummary,
  type AgentEvaluationWorkerResult,
  type AgentProjectMemoryBindingSummary,
  type AgentSpec,
  type AgentSpecIOItem,
  type AgentWorkshopCapabilitySnapshot,
  type AgentWorkshopMessage,
  type AgentWorkshopDebugVersionResult,
  type AgentWorkshopGapAnalysis,
  type AgentWorkshopPreviewResult,
  type AgentWorkshopSessionDetail,
  type AgentWorkshopVersionPrompt,
  type SuggestedToolItem,
  type AgentWorkshopToolingPlanItem,
  type AgentWorkshopToolingPlan,
  type AgentWorkshopValuationTraceabilityItem,
  type AgentVersion,
  getAgentEvaluationEvidenceBundle,
} from '@/api/agentWorkshop'
import embeddedNanobotApi, { type EmbeddedNanobotChatResponse } from '@/api/embeddedNanobot'
import { configApi, type LLMConfig } from '@/api/config'

type FlowStep = 'discuss' | 'spec' | 'gap' | 'version' | 'evaluate'
type SessionMode = 'workshop' | 'nanobot'
type NanobotToolEventCard = {
  key: string
  title: string
  detail: string
  statusLabel: string
  tone: 'info' | 'success' | 'warning'
}

// marked 配置已由 @/utils/markdown 统一管理
const description = ref('')
const replyMessage = ref('')
const specFeedbackMessage = ref('')

const route = useRoute()
const router = useRouter()

const specs = ref<AgentSpec[]>([])
const currentSession = ref<AgentWorkshopSessionDetail | null>(null)
const currentSessionMode = ref<SessionMode>('workshop')
const currentNanobotSessionKey = ref('')
const nanobotDiscussionMessages = ref<AgentWorkshopMessage[]>([])
const nanobotDraftLink = ref<{ specId: string; specName: string; sessionId?: string } | null>(null)
const nanobotStreaming = ref(false)
const nanobotProgressHint = ref('')
const nanobotToolEvents = ref<NanobotToolEventCard[]>([])
const previewResult = ref<AgentWorkshopPreviewResult | null>(null)
const gapReport = ref<AgentWorkshopGapAnalysis | null>(null)
const capabilitySnapshot = ref<AgentWorkshopCapabilitySnapshot | null>(null)
const latestVersion = ref<AgentVersion | null>(null)
const latestVersionPrompt = ref<AgentWorkshopVersionPrompt | null>(null)
const latestEvaluation = ref<AgentEvaluationReport | null>(null)
const evaluationHistory = ref<AgentEvaluationReport[]>([])
const latestDebugResult = ref<AgentWorkshopDebugVersionResult | null>(null)
const availableModels = ref<LLMConfig[]>([])
const toolCatalog = ref<ToolMetadata[]>([])

const evaluateDialogVisible = ref(false)
const evaluationForm = ref({
  user_feedback: '',
  llm: {
    provider: 'custom_openai',
    model: '',
    temperature: 0.2,
    max_tokens: 4000,
    backend_url: '',
  },
  stock: {
    symbol: '',
    market_type: 'A股',
    analysis_date: '',
  },
  runtime_result: {
    user_goal: '',
    report: '',
    raw_result: {},
    output_text: '',
    output_payload: {},
    debug_prompt: {},
    tool_trace: [],
    template: {},
    metadata: {},
    symbol: '',
    analysis_date: '',
  },
})

const starting = ref(false)
const responding = ref(false)
const previewing = ref(false)
const analyzing = ref(false)
const buildingVersion = ref(false)
const generatingToolPlan = ref(false)
const confirmingSpec = ref(false)
const debuggingVersion = ref(false)
const evaluatingVersion = ref(false)
const iteratingVersion = ref(false)
const loadingSpecs = ref(false)
const loadingSessionList = ref(false)
const loadingCurrentSession = ref(false)
const activeStep = ref<FlowStep>('discuss')

const flowSteps: Array<{ key: FlowStep; index: string; title: string; description: string }> = [
  { key: 'discuss', index: '01', title: '聊需求', description: '先把目标、边界和输出讲清楚' },
  { key: 'spec', index: '02', title: '确认并生成', description: '确认草案后直接生成可测试版本' },
  { key: 'version', index: '03', title: '测试验证', description: '先调试运行，再看版本输出是否对路' },
  { key: 'evaluate', index: '04', title: '继续迭代', description: '根据结果提修改意见，发起下一轮' },
]

const getSpecIoText = (item?: AgentSpecIOItem | null) => {
  if (!item) return ''
  if (typeof item === 'string') return item.trim()
  const name = String(item.name || '').trim()
  const description = String(item.description || '').trim()
  if (name && description && description !== name) {
    return `${name}：${description}`
  }
  return name || description
}

const renderMarkdown = (content: string): string => {
  try {
    return safeMarkdown(content || '')
  } catch {
    return String(content || '')
  }
}

const AGENT_WORKSHOP_DEBUG = true

const getSpecTimestamp = (spec?: AgentSpec | null) => {
  const rawValue = String(spec?.updated_at || spec?.created_at || '').trim()
  if (!rawValue) return 0
  const parsed = Date.parse(rawValue)
  return Number.isFinite(parsed) ? parsed : 0
}

const debugAgentWorkshopState = (label: string, extra: Record<string, unknown> = {}) => {
  if (!AGENT_WORKSHOP_DEBUG || typeof window === 'undefined') return
  console.debug('[AgentWorkshop]', label, {
    routeSessionId: String(route.query.sessionId || ''),
    routeSpecId: String(route.query.specId || ''),
    routeNanobotSessionKey: String(route.query.nanobotSessionKey || ''),
    activeStep: activeStep.value,
    sessionMode: currentSessionMode.value,
    currentSessionId: currentSession.value?.session_id || '',
    currentSessionSpecId: currentSession.value?.current_spec_snapshot?.spec_id || '',
    currentSessionSpecUpdatedAt: currentSession.value?.current_spec_snapshot?.updated_at || '',
    previewSpecId: previewResult.value?.spec?.spec_id || '',
    previewSpecUpdatedAt: previewResult.value?.spec?.updated_at || '',
    latestVersionId: latestVersion.value?.version_id || '',
    latestVersionSpecId: latestVersion.value?.spec_id || '',
    nanobotSessionKey: currentNanobotSessionKey.value || '',
    ...extra,
  })
}

const displaySpec = computed(() => {
  const previewSpec = previewResult.value?.spec || null
  const sessionSpec = currentSession.value?.current_spec_snapshot || null
  if (!previewSpec) return sessionSpec
  if (!sessionSpec) return previewSpec
  if (previewSpec.spec_id && sessionSpec.spec_id && previewSpec.spec_id !== sessionSpec.spec_id) {
    return sessionSpec
  }
  return getSpecTimestamp(sessionSpec) >= getSpecTimestamp(previewSpec) ? sessionSpec : previewSpec
})
const displaySpecOutputTags = computed(() => (displaySpec.value?.outputs || []).map(item => getSpecIoText(item)).filter(Boolean))
const canAdvance = computed(() => currentSession.value?.feasibility_status === 'feasible' && (currentSession.value?.completeness_score || 0) >= 0.75)
const hasNanobotDiscussionContext = computed(() => Boolean(currentNanobotSessionKey.value || nanobotDiscussionMessages.value.length))
const hasWorkspaceContext = computed(() => Boolean(currentSession.value || displaySpec.value || latestVersion.value || latestEvaluation.value || hasNanobotDiscussionContext.value))
const isNanobotDiscussionSession = computed(() => hasNanobotDiscussionContext.value && activeStep.value === 'discuss')
const shouldShowNanobotStreamPanel = computed(() => isNanobotDiscussionSession.value && (nanobotStreaming.value || Boolean(nanobotProgressHint.value) || nanobotToolEvents.value.length > 0))
const displayedDiscussionMessages = computed(() => {
  if (hasNanobotDiscussionContext.value) {
    return nanobotDiscussionMessages.value
  }
  return currentSession.value?.messages || []
})
const nanobotDiscussionLeadMessage = computed(() => {
  const firstUserMessage = nanobotDiscussionMessages.value.find(item => item.role === 'user')
  return firstUserMessage?.content || ''
})
const nanobotDiscussionLatestAssistantMessage = computed(() => {
  const messages = [...nanobotDiscussionMessages.value].reverse()
  const latestAssistantMessage = messages.find(item => item.role === 'assistant')
  return latestAssistantMessage?.content || ''
})
const nanobotDiscussionRecentMessages = computed(() => {
  return nanobotDiscussionMessages.value.slice(-4)
})
const selectedSpecId = computed(() => displaySpec.value?.spec_id || currentSession.value?.current_spec_snapshot?.spec_id || latestVersion.value?.spec_id || '')
const selectedSpecName = computed(() => displaySpec.value?.name || latestVersion.value?.agent_metadata?.name || '未命名 Agent')

const syncPreviewSpecFromSession = (reason: string) => {
  const sessionSpec = currentSession.value?.current_spec_snapshot || null
  if (!previewResult.value || !sessionSpec) return
  const previewSpec = previewResult.value.spec
  if (previewSpec?.spec_id && sessionSpec.spec_id && previewSpec.spec_id !== sessionSpec.spec_id) return
  previewResult.value = {
    ...previewResult.value,
    spec: sessionSpec,
  }
  debugAgentWorkshopState('sync-preview-spec-from-session', { reason })
}
const normalizeCapabilityId = (value?: string) => String(value || '').trim().toLowerCase().split('|')[0].trim().replace(/-/g, '_')
const parseToolLabel = (value?: string) => {
  const raw = String(value || '').trim()
  if (!raw) {
    return { id: '', name: '' }
  }
  if (!raw.includes('|')) {
    return { id: raw, name: '' }
  }
  const [toolId, toolName] = raw.split('|', 2)
  return {
    id: String(toolId || '').trim(),
    name: String(toolName || '').trim(),
  }
}
const toolCatalogMap = computed(() => {
  const entries = toolCatalog.value.map(item => [item.id, item] as const)
  return new Map(entries)
})
const gapExistingToolLabelMap = computed(() => {
  const entries = (gapReport.value?.existing_tools || [])
    .map(item => parseToolLabel(item))
    .filter(item => item.id)
    .map(item => [item.id, item.name] as const)
  return new Map(entries)
})
const versionDefaultToolCards = computed(() => {
  return (latestVersion.value?.required_tools || []).map(toolId => {
    const metadata = toolCatalogMap.value.get(toolId)
    const fallbackName = gapExistingToolLabelMap.value.get(toolId) || toolId
    return {
      id: toolId,
      name: metadata?.name || fallbackName,
      description: metadata?.description || '当前版本已绑定该工具，但工具注册表中暂未返回更详细的使用说明。',
    }
  })
})
const existingCapabilityIds = computed(() => {
  const snapshot = capabilitySnapshot.value
  if (!snapshot) return new Set<string>()
  const ids = [
    ...(snapshot.external_skill_tool_ids || []),
    ...(snapshot.external_data_skills || []),
    ...(snapshot.external_analysis_skills || []),
  ].map(item => normalizeCapabilityId(item)).filter(Boolean)
  return new Set(ids)
})
const dedupeSuggestedItems = (items: SuggestedToolItem[]) => {
  const seen = new Set<string>()
  return items.filter(item => {
    const key = normalizeCapabilityId(item.tool_id)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}
const isCapabilityAlreadyGenerated = (target?: string | AgentWorkshopToolingPlanItem) => {
  const value = typeof target === 'string' ? target : (target?.tool_id || target?.tool_name || '')
  return existingCapabilityIds.value.has(normalizeCapabilityId(value))
}
const pendingSuggestedTools = computed(() => dedupeSuggestedItems((gapReport.value?.suggested_tools || []).filter(item => !isCapabilityAlreadyGenerated(item.tool_id))))
const resolvedSuggestedTools = computed(() => dedupeSuggestedItems((gapReport.value?.suggested_tools || []).filter(item => isCapabilityAlreadyGenerated(item.tool_id))))
const normalizeCapabilityLabel = (value?: string) => normalizeCapabilityId(String(value || '').replace(/\s+可调用能力$/, '').trim())
const pendingVersionCapabilities = computed(() => {
  return (latestVersion.value?.required_capabilities || []).filter(item => !existingCapabilityIds.value.has(normalizeCapabilityLabel(item)))
})
const resolvedVersionCapabilities = computed(() => {
  return (latestVersion.value?.required_capabilities || []).filter(item => existingCapabilityIds.value.has(normalizeCapabilityLabel(item)))
})
const latestExecutionPlan = computed(() => latestVersion.value?.execution_plan || null)
const executionPlanSampleInputText = computed(() => {
  const payload = latestExecutionPlan.value?.sample_input
  if (!payload || typeof payload !== 'object' || !Object.keys(payload).length) return ''
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
})
const executionPlanStepCards = computed(() => {
  return (latestExecutionPlan.value?.execution_steps || []).map(item => ({
    stepId: item.step_id,
    title: item.title,
    objective: item.objective,
    tools: Array.isArray(item.suggested_tools) ? item.suggested_tools.filter(Boolean) : [],
    expectedEvidence: Array.isArray(item.expected_evidence) ? item.expected_evidence.filter(Boolean) : [],
    failureSignals: Array.isArray(item.failure_signals) ? item.failure_signals.filter(Boolean) : [],
  }))
})
const executionPlanAcceptanceChecks = computed(() => {
  return Array.isArray(latestExecutionPlan.value?.acceptance_checks) ? latestExecutionPlan.value?.acceptance_checks.filter(Boolean) : []
})
const executionPlanFallbackRules = computed(() => {
  return Array.isArray(latestExecutionPlan.value?.fallback_rules) ? latestExecutionPlan.value?.fallback_rules.filter(Boolean) : []
})
const promptSections = computed(() => {
  const content = latestVersionPrompt.value?.content
  if (!content) return []
  return [
    { key: 'system_prompt', label: 'System Prompt', value: content.system_prompt || '' },
    { key: 'user_prompt', label: 'User Prompt', value: content.user_prompt || '' },
    { key: 'tool_guidance', label: '工具指引', value: content.tool_guidance || '' },
    { key: 'analysis_requirements', label: '分析要求', value: content.analysis_requirements || '' },
    { key: 'output_format', label: '输出格式', value: content.output_format || '' },
    { key: 'constraints', label: '约束', value: content.constraints || '' },
  ].filter(item => item.value)
})
const isV2AgentId = (agentId?: string) => {
  const normalized = String(agentId || '').toLowerCase()
  return normalized.includes('_v2') || normalized.startsWith('v2_')
}
const explicitWorkshopMaintenanceStatus = computed(() => {
  const versionStatus = latestVersion.value?.agent_metadata?.maintenance_status
  if (versionStatus === 'maintained' || versionStatus === 'unmaintained') {
    return versionStatus
  }
  const debugStatus = latestDebugResult.value?.metadata?.maintenance_status
  if (debugStatus === 'maintained' || debugStatus === 'unmaintained') {
    return debugStatus
  }
  return ''
})
const workshopRuntimeAgentId = computed(() => {
  const metadataId = latestVersion.value?.agent_metadata?.id
  if (typeof metadataId === 'string' && metadataId.trim()) {
    return metadataId.trim()
  }
  const debugMetadataId = latestDebugResult.value?.metadata?.agent_id
  if (typeof debugMetadataId === 'string' && debugMetadataId.trim()) {
    return debugMetadataId.trim()
  }
  const debugRuntimeId = latestDebugResult.value?.runtime_agent_id
  if (typeof debugRuntimeId === 'string' && debugRuntimeId.trim()) {
    return debugRuntimeId.trim()
  }
  return ''
})
const workshopMaintenanceStatus = computed(() => {
  if (explicitWorkshopMaintenanceStatus.value === 'maintained' || explicitWorkshopMaintenanceStatus.value === 'unmaintained') {
    return explicitWorkshopMaintenanceStatus.value
  }
  const runtimeVersion = String(latestVersion.value?.agent_metadata?.version || '').toLowerCase()
  if (runtimeVersion.startsWith('1') || runtimeVersion.startsWith('v1')) {
    return 'unmaintained'
  }
  if (runtimeVersion.startsWith('2') || runtimeVersion.startsWith('v2')) {
    return 'maintained'
  }
  if (!workshopRuntimeAgentId.value) {
    return 'maintained'
  }
  return isV2AgentId(workshopRuntimeAgentId.value) ? 'maintained' : 'unmaintained'
})
const displayedRuntimeResult = computed(() => {
  const detailRuntime = latestEvaluation.value?.details?.runtime_result
  if (detailRuntime && typeof detailRuntime === 'object') {
    return detailRuntime as Record<string, any>
  }
  if (latestDebugResult.value) {
    return {
      user_goal: latestDebugResult.value.metadata?.user_goal,
      output_text: latestDebugResult.value.report,
      symbol: latestDebugResult.value.symbol,
      analysis_date: latestDebugResult.value.analysis_date,
    }
  }
  return null
})
const displayedRuntimeOutput = computed(() => {
  const outputText = displayedRuntimeResult.value?.output_text
  if (typeof outputText === 'string' && outputText.trim()) {
    return outputText.trim()
  }
  return latestEvaluation.value?.details?.parsed_output_excerpt || ''
})
const displayedRawBackendResult = computed(() => {
  const rawResult = latestDebugResult.value?.raw_result
  if (rawResult && typeof rawResult === 'object') {
    try {
      return JSON.stringify(rawResult, null, 2)
    } catch {
      return String(rawResult)
    }
  }

  const payload = latestEvaluation.value?.details?.runtime_result?.output_payload
  if (payload && typeof payload === 'object') {
    try {
      return JSON.stringify(payload, null, 2)
    } catch {
      return String(payload)
    }
  }

  return ''
})
const displayedDebugPrompt = computed(() => {
  const debugPrompt = latestDebugResult.value?.debug_prompt
  if (!debugPrompt) return ''

  const parts = []
  if (debugPrompt.system_prompt?.trim()) {
    parts.push(`【System Prompt】\n${debugPrompt.system_prompt}`)
  }
  if (debugPrompt.user_prompt?.trim()) {
    parts.push(`【User Prompt】\n${debugPrompt.user_prompt}`)
  }
  return parts.join('\n\n')
})
const displayedRuntimeGoal = computed(() => {
  const goal = displayedRuntimeResult.value?.user_goal
  return typeof goal === 'string' && goal.trim() ? goal.trim() : ''
})
const displayedRuntimeSymbol = computed(() => {
  const symbol = displayedRuntimeResult.value?.symbol || latestDebugResult.value?.symbol
  return typeof symbol === 'string' && symbol.trim() ? symbol.trim() : ''
})
const displayedRuntimeDate = computed(() => {
  const value = displayedRuntimeResult.value?.analysis_date || latestDebugResult.value?.analysis_date
  return typeof value === 'string' && value.trim() ? value.trim() : ''
})
const formatDisplayTime = (value?: string | null) => {
  const normalized = String(value || '').trim()
  return normalized ? normalized.replace('T', ' ').slice(0, 19) : '-'
}
const evaluationDecisionText = computed(() => {
  const decision = latestEvaluation.value?.decision
  if (decision === 'pass') return '通过'
  if (decision === 'reject') return '拒绝'
  if (decision === 'revise') return '需要修改'
  return decision || ''
})
const evaluationTypeText = computed(() => {
  const type = latestEvaluation.value?.evaluation_type
  if (type === 'production-review') return '结果评估'
  return type || '结果评估'
})
const evaluationEvidenceBundle = computed<AgentEvaluationEvidenceBundle | null>(() => getAgentEvaluationEvidenceBundle(latestEvaluation.value))
const versionPromptProjectMemorySummary = computed<AgentProjectMemoryBindingSummary | null>(() => {
  return latestVersion.value?.prompt_template_project_memory_binding_summary || null
})
const latestEvaluationSummary = computed<AgentEvaluationSummary | null>(() => {
  if (latestEvaluation.value?.evaluation_summary) return latestEvaluation.value.evaluation_summary
  const details = latestEvaluation.value?.details || {}
  if (details && typeof details.evaluation_summary === 'object') {
    return details.evaluation_summary as AgentEvaluationSummary
  }
  return latestVersion.value?.last_evaluation_summary || null
})
const latestEvaluationProjectMemorySummary = computed<AgentProjectMemoryBindingSummary | null>(() => {
  if (latestEvaluation.value?.project_memory_binding_summary) return latestEvaluation.value.project_memory_binding_summary
  const details = latestEvaluation.value?.details || {}
  if (details && typeof details.project_memory_binding_summary === 'object') {
    return details.project_memory_binding_summary as AgentProjectMemoryBindingSummary
  }
  return latestEvaluationSummary.value?.project_memory_binding || null
})
const getProjectMemorySummaryTagType = (status?: string) => {
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
const evaluationHistoryCards = computed(() => {
  return evaluationHistory.value.map((item) => {
    const details = item.details || {}
    const evaluationSummary = item.evaluation_summary || (typeof details.evaluation_summary === 'object' ? details.evaluation_summary as AgentEvaluationSummary : null)
    const projectMemorySummary = item.project_memory_binding_summary
      || (typeof details.project_memory_binding_summary === 'object' ? details.project_memory_binding_summary as AgentProjectMemoryBindingSummary : null)
      || evaluationSummary?.project_memory_binding
      || null
    return {
      key: item.evaluation_id,
      evaluationId: item.evaluation_id,
      createdAt: formatDisplayTime(item.created_at),
      decision: item.decision,
      decisionText: item.decision === 'pass' ? '通过' : item.decision === 'reject' ? '拒绝' : '需要修改',
      decisionType: item.decision === 'pass'
        ? ('success' as const)
        : item.decision === 'reject'
          ? ('danger' as const)
          : ('warning' as const),
      evaluationTypeText: item.evaluation_type === 'production-review' ? '结果评估' : (item.evaluation_type || '结果评估'),
      overallScore: typeof item.scores?.overall === 'number' ? item.scores.overall : evaluationSummary?.overall_score,
      evaluationStatus: evaluationSummary?.evaluation_status || String(details.evaluation_status || '').trim(),
      workerExecutionMode: evaluationSummary?.worker_execution_mode || '',
      projectMemorySummary,
    }
  })
})
const getWorkerStatusText = (status?: string) => {
  if (status === 'confirmed') return '已证实'
  if (status === 'disproved') return '已排除'
  if (status === 'insufficient_evidence') return '证据不足'
  return status || '未知'
}
const getWorkerSourceText = (source?: string) => {
  if (source === 'nanobot') return 'Nanobot'
  if (source === 'nanobot-fallback') return 'Nanobot 回退'
  if (source === 'rules') return '规则'
  return source || '未知来源'
}
const truncateWorkerArtifactContent = (value?: string, limit = 220) => {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}
const getWorkerArtifactTypeLabel = (type?: string) => {
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
const normalizeMetadataEntries = (metadata?: Record<string, any>) => {
  if (!metadata || typeof metadata !== 'object') return []
  return Object.entries(metadata)
    .flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.slice(0, 3).map(entry => `${key}: ${typeof entry === 'string' ? entry : JSON.stringify(entry)}`)
      }
      return [`${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`]
    })
    .filter(Boolean)
    .slice(0, 4)
}
const buildWorkerArtifactView = (item?: AgentEvaluationEvidenceArtifact | null) => {
  const type = String(item?.artifact_type || 'evidence_artifact').trim() || 'evidence_artifact'
  const title = String(item?.title || item?.artifact_type || '未命名证据').trim() || '未命名证据'
  const path = String(item?.path || '').trim()
  const content = truncateWorkerArtifactContent(String(item?.content || ''))
  const metadata = item?.metadata && typeof item.metadata === 'object' ? item.metadata as Record<string, any> : {}
  const metadataEntries = normalizeMetadataEntries(metadata)
  const detailLines: string[] = []
  const tagEntries: string[] = []

  if (type === 'tool_trace') {
    const toolName = String(metadata.tool_name || '').trim()
    const success = typeof metadata.success === 'boolean' ? (metadata.success ? 'success=true' : 'success=false') : ''
    if (toolName || success) {
      detailLines.push([toolName, success].filter(Boolean).join(' / '))
    }
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
  } else if (type === 'traceability_gap') {
    if (metadata.value) detailLines.push(`数值：${metadata.value}`)
    if (metadata.source_type) detailLines.push(`来源类型：${metadata.source_type}`)
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
  } else if (type === 'execution_plan_review') {
    if (typeof metadata.issues_count !== 'undefined') detailLines.push(`问题数：${metadata.issues_count}`)
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
    tagEntries.push(...metadataEntries.filter(entry => entry.startsWith('missing_required_tools:')))
  } else if (type === 'tool_trace_gap' || type === 'prompt_gap') {
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
    tagEntries.push(...metadataEntries)
  } else if (type === 'output_payload' || type === 'rule_breakdown') {
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
    tagEntries.push(...metadataEntries)
  } else {
    if (path) detailLines.push(`路径：${path}`)
    if (content) detailLines.push(content)
    tagEntries.push(...metadataEntries)
  }

  return {
    type,
    title,
    detailLines: detailLines.filter(Boolean),
    tagEntries: tagEntries.filter(Boolean),
  }
}
const normalizeWorkerArtifactCards = (artifacts?: AgentEvaluationEvidenceArtifact[] | null) => {
  if (!Array.isArray(artifacts)) return []
  return artifacts
    .map(item => buildWorkerArtifactView(item))
    .filter(item => item.title || item.detailLines.length || item.tagEntries.length)
}
const evaluationEvidenceIncomplete = computed(() => {
  const status = String(evaluationEvidenceBundle.value?.evaluation_status || latestEvaluation.value?.details?.evaluation_status || '').trim()
  return status === 'evidence_incomplete'
})
const evaluationValiditySummary = computed(() => {
  if (!latestEvaluation.value) return ''
  if (evaluationEvidenceIncomplete.value) return '当前评估未定案：存在关键证据缺口，本次结果不能作为正式发布依据。'
  if (evaluationEvidenceBundle.value) return '当前评估已完成 evidence-first 定案，正式问题列表仅包含已证实问题。'
  return ''
})
const evidenceInvalidReasons = computed(() => {
  return Array.isArray(evaluationEvidenceBundle.value?.invalid_reasons)
    ? evaluationEvidenceBundle.value.invalid_reasons.filter(Boolean)
    : []
})
const confirmedEvaluationIssues = computed(() => {
  const officialIssues = Array.isArray(evaluationEvidenceBundle.value?.official_issues)
    ? evaluationEvidenceBundle.value.official_issues.filter(Boolean)
    : []
  if (officialIssues.length) return officialIssues
  return Array.isArray(latestEvaluation.value?.issues) ? latestEvaluation.value.issues.filter(Boolean) : []
})
const insufficientEvidenceCards = computed(() => {
  const items = evaluationEvidenceBundle.value?.insufficient_evidence
  if (!Array.isArray(items)) return []
  return items.map(item => ({
    category: item.category || '',
    title: item.title || '未命名项',
    evidence: Array.isArray(item.evidence) ? item.evidence.filter(Boolean) : [],
  }))
})
const evidenceWorkerCards = computed(() => {
  const items = evaluationEvidenceBundle.value?.worker_results
  if (!Array.isArray(items)) return []
  return items.map((item: AgentEvaluationWorkerResult) => ({
    key: `${item.task_id}-${item.worker_name}`,
    workerName: item.worker_name || '未命名 worker',
    statusText: getWorkerStatusText(item.status),
    sourceText: getWorkerSourceText(item.source),
    summary: String(item.summary || '').trim(),
    evidence: Array.isArray(item.evidence) ? item.evidence.filter(Boolean).slice(0, 3) : [],
    artifactGroups: Object.values(normalizeWorkerArtifactCards(item.artifacts).reduce((groups, artifact) => {
      const key = artifact.type
      if (!groups[key]) {
        groups[key] = {
          key,
          label: getWorkerArtifactTypeLabel(key),
          items: [],
        }
      }
      groups[key].items.push(artifact)
      return groups
    }, {} as Record<string, { key: string; label: string; items: Array<{ type: string; title: string; detailLines: string[]; tagEntries: string[] }> }>)),
  }))
})
const llmReview = computed(() => {
  const review = latestEvaluation.value?.details?.llm_advisory || latestEvaluation.value?.details?.llm_review
  return review && typeof review === 'object' ? review as Record<string, any> : null
})
const llmReviewSummary = computed(() => {
  const value = llmReview.value?.summary
  return typeof value === 'string' && value.trim() ? value.trim() : ''
})
const judgeModelText = computed(() => {
  const judgeModel = latestEvaluation.value?.details?.judge_model
  if (!judgeModel || typeof judgeModel !== 'object') return ''
  const provider = typeof judgeModel.provider === 'string' ? judgeModel.provider : ''
  const model = typeof judgeModel.model === 'string' ? judgeModel.model : ''
  return [provider, model].filter(Boolean).join(' / ')
})
const valuationTraceability = computed(() => {
  const trace = latestEvaluation.value?.details?.valuation_traceability
  return trace && typeof trace === 'object' ? trace as Record<string, any> : null
})
const valuationTraceabilitySummary = computed(() => {
  const value = valuationTraceability.value?.summary
  return typeof value === 'string' && value.trim() ? value.trim() : ''
})
const valuationTraceabilityItems = computed(() => {
  const items = valuationTraceability.value?.items
  if (!Array.isArray(items)) return []
  return items.map((item: AgentWorkshopValuationTraceabilityItem) => {
    const sourceType = item?.source_type || ''
    let tagClass = ''
    if (sourceType === 'tool_calculated') tagClass = 'success'
    else if (sourceType === 'llm_inferred_from_tool_data') tagClass = 'warning'
    else tagClass = 'danger'
    return {
      label: item?.label || '估值区间',
      value: item?.value || '',
      judgement: item?.judgement || '未知',
      evidenceTools: Array.isArray(item?.evidence_tools) ? item.evidence_tools.filter(Boolean) : [],
      notes: Array.isArray(item?.notes) ? item.notes.filter(Boolean) : [],
      tagClass,
    }
  })
})
const executionPlanReview = computed(() => {
  const review = latestEvaluation.value?.details?.execution_plan_review
  if (!review || typeof review !== 'object') return null
  const sampleInput = review.sample_input && typeof review.sample_input === 'object' ? review.sample_input : null
  let sampleInputText = ''
  if (sampleInput) {
    try {
      sampleInputText = JSON.stringify(sampleInput, null, 2)
    } catch {
      sampleInputText = String(sampleInput)
    }
  }
  const status = typeof review.status === 'string' ? review.status : ''
  const statusMap: Record<string, string> = {
    pass: '通过',
    revise: '需补齐',
    fail: '失败',
  }
  return {
    status,
    statusText: statusMap[status] || status || '未知',
    score: typeof review.score === 'number' ? review.score : '-',
    sampleInputText,
    acceptanceResults: Array.isArray(review.acceptance_results) ? review.acceptance_results.map((item: Record<string, any>) => ({
      label: item?.label || '未命名检查项',
      passed: Boolean(item?.passed),
      detail: item?.detail || '',
    })) : [],
    matched: Array.isArray(review.matched) ? review.matched.filter(Boolean) : [],
    missing: Array.isArray(review.missing) ? review.missing.filter(Boolean) : [],
    notes: Array.isArray(review.notes) ? review.notes.filter(Boolean) : [],
  }
})
const evaluationScoreCards = computed(() => {
  const scoreMap: Record<string, { label: string; description: string }> = {
    runtime_goal_alignment: { label: '目标对齐', description: '输出有没有真正回应这次任务目标' },
    runtime_output_quality: { label: '结果质量', description: '输出是否完整、专业、可直接用于判断，而不是只看字段命中' },
    runtime_reasoning_quality: { label: '分析过程', description: '推理过程、假设与结论之间是否自洽合理' },
    runtime_tool_usage: { label: '工具使用', description: '工具选择和调用过程是否适合这个任务' },
    runtime_prompt_quality: { label: '提示词质量', description: 'Prompt 是否把任务、约束和输出要求讲清楚了' },
    runtime_execution_readiness: { label: '执行验收', description: '是否按 execution_plan 完成了样本、工具、输出和降级约束' },
    runtime_constraint_control: { label: '边界控制', description: '有没有越界说到不该说的内容' },
    overall: { label: '综合得分', description: '以上几项评审分的平均值' },
  }

  return Object.entries(latestEvaluation.value?.scores || {}).map(([key, value]) => ({
    key,
    label: scoreMap[key]?.label || key,
    description: scoreMap[key]?.description || '当前规则项评分',
    value,
  }))
})
const llmDimensionCards = computed(() => {
  const scoreMap: Record<string, { label: string; description: string }> = {
    runtime_goal_alignment: { label: '目标对齐', description: '输出有没有真正回应这次任务目标' },
    runtime_output_quality: { label: '结果质量', description: '输出是否完整、专业、可直接用于判断' },
    runtime_reasoning_quality: { label: '分析过程', description: '推理过程是否清晰、自洽且有依据' },
    runtime_tool_usage: { label: '工具使用', description: '工具选择和调用轨迹是否合理' },
    runtime_prompt_quality: { label: '提示词质量', description: 'Prompt 是否明确、充分、可执行' },
    runtime_execution_readiness: { label: '执行验收', description: '是否真的按版本执行计划完成关键检查项' },
    runtime_constraint_control: { label: '边界控制', description: '是否存在越界、幻觉或违反限制的内容' },
  }

  const dimensions = llmReview.value?.dimensions
  if (!dimensions || typeof dimensions !== 'object') return []

  return Object.entries(dimensions).map(([key, value]) => {
    const detail = value && typeof value === 'object' ? value as Record<string, any> : {}
    return {
      key,
      label: scoreMap[key]?.label || key,
      description: scoreMap[key]?.description || 'LLM 评审维度',
      score: typeof detail.score === 'number' ? detail.score : '-',
      judgement: typeof detail.judgement === 'string' ? detail.judgement : '',
      evidence: Array.isArray(detail.evidence) ? detail.evidence.filter(Boolean) : [],
      problems: Array.isArray(detail.problems) ? detail.problems.filter(Boolean) : [],
      suggestions: Array.isArray(detail.suggestions) ? detail.suggestions.filter(Boolean) : [],
      notes: Array.isArray(detail.notes) ? detail.notes.filter(Boolean) : [],
    }
  })
})
const ruleBreakdownMap = computed(() => {
  const breakdown = latestEvaluation.value?.details?.rule_review?.score_breakdown || latestEvaluation.value?.details?.score_breakdown
  return breakdown && typeof breakdown === 'object' ? breakdown as Record<string, any> : {}
})
const ruleBreakdownCards = computed(() => {
  return evaluationScoreCards.value
    .filter(item => item.key !== 'overall' && ['runtime_goal_alignment', 'runtime_constraint_control'].includes(item.key) === false)
    .map(item => {
      const legacyKeyMap: Record<string, string> = {
        runtime_output_quality: 'runtime_output_coverage',
        runtime_reasoning_quality: 'runtime_explainability',
      }
      const detail = ruleBreakdownMap.value[item.key] || ruleBreakdownMap.value[legacyKeyMap[item.key]] || {}
      const matched = Array.isArray(detail.matched) ? detail.matched.filter(Boolean) : []
      const missing = Array.isArray(detail.missing) ? detail.missing.filter(Boolean) : []
      const notes = Array.isArray(detail.notes) ? detail.notes.filter(Boolean) : []
      return {
        key: item.key,
        label: item.label,
        matched,
        missing,
        notes,
        matchedLabel: item.key === 'runtime_constraint_control' ? '触发' : '命中',
        missingLabel: item.key === 'runtime_constraint_control' ? '未触发' : '缺失',
      }
    })
    .filter(item => item.matched.length || item.missing.length || item.notes.length)
})
const canSubmitEvaluation = computed(() => {
  return Boolean(evaluationForm.value.runtime_result.output_text?.trim())
})
const activeStepLabel = computed(() => flowSteps.find(item => item.key === activeStep.value)?.title || '聊需求')
const summaryStageText = computed(() => {
  if (latestEvaluation.value) return '继续迭代'
  if (latestVersion.value) return '测试验证'
  if (displaySpec.value) return '确认并生成'
  return '聊需求'
})
const focusSubtitle = computed(() => {
  if (currentSession.value?.feasibility_status === 'not-feasible') {
    return currentSession.value.refusal_reason || '当前目标超出支持范围，建议先缩小问题。'
  }
  if (currentSession.value?.feasibility_status === 'need-clarification') {
    return '先把需求聊清楚，再确认草案并生成可测试版本。'
  }
  if (latestEvaluation.value) {
    return '当前已经有评估结果，可以继续发起下一轮迭代。'
  }
  if (latestVersion.value) {
    return '可测试版本已经生成，下一步建议先调试运行并做评估。'
  }
  if (gapReport.value || previewResult.value) {
    return '规格已经有轮廓了，确认没有问题后就可以直接生成可测试版本。'
  }
  return '先在对话里把这个 Agent 讲明白。'
})
const statusText = computed(() => {
  if (latestEvaluation.value) return '可迭代'
  if (latestVersion.value) return '待测试'
  const status = currentSession.value?.feasibility_status
  if (status === 'feasible') return '可继续'
  if (status === 'not-feasible') return '做不到'
  if (previewResult.value?.readiness === 'ready') return '可继续'
  return '待澄清'
})
const statusTagType = computed(() => {
  if (latestEvaluation.value) return 'primary'
  if (latestVersion.value) return 'success'
  const status = currentSession.value?.feasibility_status
  if (status === 'feasible') return 'success'
  if (status === 'not-feasible') return 'danger'
  if (previewResult.value?.readiness === 'ready') return 'success'
  return 'warning'
})
const toolingPlan = computed<AgentWorkshopToolingPlan | null>(() => currentSession.value?.tooling_plan || null)
const specPendingQuestions = computed(() => {
  if (previewResult.value?.pending_questions?.length) {
    return previewResult.value.pending_questions
  }
  return currentSession.value?.pending_questions || []
})
const reusableCapabilityCount = computed(() => {
  if (!gapReport.value) return 0
  return gapReport.value.existing_tools?.length || 0
})
const missingCapabilityCount = computed(() => {
  if (!gapReport.value) return 0
  return pendingSuggestedTools.value.length
    + (gapReport.value.blocking_gaps?.length || 0)
    + (toolingPlan.value?.missing_capabilities?.length || 0)
})

const syncActiveStep = (preferred?: FlowStep) => {
  if (preferred) {
    activeStep.value = preferred
    debugAgentWorkshopState('sync-active-step', { preferred, resolvedStep: activeStep.value })
    return
  }

  if (latestEvaluation.value) {
    activeStep.value = 'evaluate'
    debugAgentWorkshopState('sync-active-step', { resolvedStep: activeStep.value, reason: 'latestEvaluation' })
    return
  }

  if (latestVersion.value) {
    activeStep.value = 'version'
    debugAgentWorkshopState('sync-active-step', { resolvedStep: activeStep.value, reason: 'latestVersion' })
    return
  }

  if (latestVersion.value) {
    activeStep.value = 'version'
    debugAgentWorkshopState('sync-active-step', { resolvedStep: activeStep.value, reason: 'latestVersion-duplicate-branch' })
    return
  }

  if (previewResult.value || displaySpec.value) {
    activeStep.value = 'spec'
    debugAgentWorkshopState('sync-active-step', { resolvedStep: activeStep.value, reason: 'preview-or-display-spec' })
    return
  }

  activeStep.value = 'discuss'
  debugAgentWorkshopState('sync-active-step', { resolvedStep: activeStep.value, reason: 'fallback-discuss' })
}

// const formatTime = (value?: string) => {
//   if (!value) return '-'
//   return value.replace('T', ' ').slice(0, 19)
// }

const resetEvaluationForm = () => {
  const sampleInput = latestVersion.value?.execution_plan?.sample_input || {}
  evaluationForm.value = {
    user_feedback: '',
    llm: {
      provider: 'custom_openai',
      model: availableModels.value[0]?.model_name || '',
      temperature: 0.2,
      max_tokens: 4000,
      backend_url: '',
    },
    stock: {
      symbol: String(sampleInput.symbol || displaySpec.value?.sample_symbols?.[0] || ''),
      market_type: String(sampleInput.market_type || 'A股'),
      analysis_date: String(sampleInput.analysis_date || ''),
    },
    runtime_result: {
      user_goal: String(sampleInput.task_description || ''),
      report: '',
      raw_result: {},
      output_text: '',
      output_payload: {},
      debug_prompt: {},
      tool_trace: [],
      template: {},
      metadata: {},
      symbol: String(sampleInput.symbol || displaySpec.value?.sample_symbols?.[0] || ''),
      analysis_date: String(sampleInput.analysis_date || ''),
    },
  }
}

const clearWorkspace = (preserveNanobotState = false) => {
  const previousNanobotSessionKey = currentNanobotSessionKey.value
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
    activeNanobotStreamController = null
  }
  currentSession.value = null
  currentSessionMode.value = 'workshop'
  currentNanobotSessionKey.value = ''
  nanobotDiscussionMessages.value = []
  nanobotDraftLink.value = null
  nanobotStreaming.value = false
  nanobotProgressHint.value = ''
  nanobotToolEvents.value = []
  previewResult.value = null
  gapReport.value = null
  latestVersion.value = null
  latestVersionPrompt.value = null
  latestEvaluation.value = null
  latestDebugResult.value = null
  replyMessage.value = ''
  specFeedbackMessage.value = ''
  resetEvaluationForm()
  syncActiveStep('discuss')
  if (!preserveNanobotState && previousNanobotSessionKey) {
    removeNanobotDiscussionState(previousNanobotSessionKey)
  }
  debugAgentWorkshopState('clear-workspace', { preserveNanobotState })
}

const buildDefaultSpecConfirmationMessage = () => {
  if (specPendingQuestions.value.length) {
    return '整体方向没问题。上面这些待确认项如果我没有单独说明，就先按你推荐的方案更新 Draft，然后直接生成一个可测试版本。'
  }
  return '整体方向没问题，请按当前草案直接生成一个可测试版本。'
}

const buildNanobotDraftUpdateMessage = (message: string) => {
  return [
    '继续当前 Agent Workshop 会话，仅更新当前 Draft 规格内容。',
    '这一步只允许更新/刷新 Agent Workshop Draft，不要创建或更新运行时 Agent，不要调用 generate_confirmed_candidate_agent。',
    '请把下面这段用户反馈合并进当前草案，并保持在 Agent Workshop 规格流里：',
    message,
  ].join('\n')
}

const fillSpecDefaultReply = () => {
  specFeedbackMessage.value = buildDefaultSpecConfirmationMessage()
}

const syncEvaluationModelConfig = () => {
  const selectedModel = availableModels.value.find(item => item.model_name === evaluationForm.value.llm.model)
  if (!selectedModel) return

  evaluationForm.value.llm.provider = selectedModel.provider || evaluationForm.value.llm.provider
  evaluationForm.value.llm.backend_url = selectedModel.api_base || ''
  evaluationForm.value.llm.max_tokens = selectedModel.max_tokens || evaluationForm.value.llm.max_tokens
  if (typeof selectedModel.temperature === 'number') {
    evaluationForm.value.llm.temperature = selectedModel.temperature
  }
}

const loadAvailableModels = async () => {
  try {
    const llmConfigs = await configApi.getLLMConfigs()
    availableModels.value = (llmConfigs || []).filter(item => item.enabled)
    if (!evaluationForm.value.llm.model && availableModels.value.length > 0) {
      evaluationForm.value.llm.model = availableModels.value[0].model_name
      syncEvaluationModelConfig()
    }
  } catch (error: any) {
    availableModels.value = []
    ElMessage.error(error?.message || '加载模型列表失败')
  }
}

const goBackToManager = () => {
  router.push('/workflow/agent-workshop')
}

const startNewDraft = () => {
  clearWorkspace()
  description.value = ''
  replyMessage.value = ''
  activeStep.value = 'discuss'
  router.push('/workflow/agent-workshop/create')
}

const loadLatestVersion = async (specId?: string) => {
  if (!specId) {
    latestVersion.value = null
    latestVersionPrompt.value = null
    latestEvaluation.value = null
    evaluationHistory.value = []
    debugAgentWorkshopState('load-latest-version:empty-spec', { specId: specId || '' })
    syncActiveStep()
    return
  }
  try {
    const result = await agentWorkshopApi.listVersions({ spec_id: specId, page: 1, page_size: 1 })
    const latestVersionStub = result.items?.[0] || null
    latestVersion.value = latestVersionStub?.version_id ? await agentWorkshopApi.getVersion(latestVersionStub.version_id) : null
    if (latestVersion.value?.version_id) {
      await Promise.all([
        loadLatestEvaluation(latestVersion.value.version_id),
        loadLatestVersionPrompt(latestVersion.value.version_id),
      ])
    } else {
      latestVersionPrompt.value = null
    }
    debugAgentWorkshopState('load-latest-version:success', {
      specId,
      latestVersionId: latestVersion.value?.version_id || '',
      latestVersionNumber: latestVersion.value?.version || 0,
    })
  } catch {
    latestVersion.value = null
    latestVersionPrompt.value = null
    latestEvaluation.value = null
    evaluationHistory.value = []
    debugAgentWorkshopState('load-latest-version:failed', { specId })
  } finally {
    syncActiveStep()
  }
}

const NANOBOT_WORKSHOP_SESSION_PREFIX = 'embedded:agent-workshop:'
const NANOBOT_WORKSHOP_SKILLS = ['nanobot-agent-design']
const NANOBOT_DISCUSSION_STORAGE_PREFIX = 'agent-workshop:nanobot:'
let activeNanobotStreamController: AbortController | null = null

const getNanobotDiscussionStorageKey = (sessionKey?: string) => {
  const normalized = String(sessionKey || '').trim()
  return normalized ? `${NANOBOT_DISCUSSION_STORAGE_PREFIX}${normalized}` : ''
}

const persistNanobotDiscussionState = () => {
  if (typeof window === 'undefined') return
  const storageKey = getNanobotDiscussionStorageKey(currentNanobotSessionKey.value)
  if (!storageKey) return
  window.sessionStorage.setItem(storageKey, JSON.stringify({
    sessionKey: currentNanobotSessionKey.value,
    messages: nanobotDiscussionMessages.value,
    draftLink: nanobotDraftLink.value,
  }))
}

const syncNanobotSessionShell = (sessionKey: string, messages: AgentWorkshopMessage[]) => {
  const now = new Date().toISOString()
  currentNanobotSessionKey.value = sessionKey
  nanobotDiscussionMessages.value = messages
  const baseSpecSnapshot = currentSession.value?.current_spec_snapshot || createEmptySpecSnapshot()
  const nextSpecSnapshot: AgentSpec = {
    ...baseSpecSnapshot,
    spec_id: nanobotDraftLink.value?.specId || baseSpecSnapshot.spec_id,
    name: nanobotDraftLink.value?.specName || baseSpecSnapshot.name,
    latest_session_id: nanobotDraftLink.value?.sessionId || baseSpecSnapshot.latest_session_id,
    updated_at: now,
  }

  if (!currentSession.value || currentSessionMode.value === 'nanobot') {
    currentSession.value = {
      session_id: sessionKey,
      spec_id: currentSession.value?.spec_id || '',
      user_id: currentSession.value?.user_id || '',
      stage: currentSession.value?.stage || 'planning',
      current_round: Math.max(1, Math.ceil(messages.length / 2)),
      messages,
      current_spec_snapshot: nextSpecSnapshot,
      pending_questions: currentSession.value?.pending_questions || [],
      completeness_score: currentSession.value?.completeness_score || 0,
      feasibility_status: currentSession.value?.feasibility_status || 'need-clarification',
      refusal_reason: currentSession.value?.refusal_reason || '',
      gap_report: currentSession.value?.gap_report || null,
      tooling_plan: currentSession.value?.tooling_plan || null,
      created_at: currentSession.value?.created_at || now,
      updated_at: now,
    }
    currentSessionMode.value = 'nanobot'
  }

  persistNanobotDiscussionState()
}

const updateNanobotSessionKey = (sessionKey?: string) => {
  const normalized = String(sessionKey || '').trim()
  if (!normalized || normalized === currentNanobotSessionKey.value) return

  const previousKey = currentNanobotSessionKey.value
  currentNanobotSessionKey.value = normalized
  if (currentSessionMode.value === 'nanobot' && currentSession.value) {
    currentSession.value = {
      ...currentSession.value,
      session_id: normalized,
      updated_at: new Date().toISOString(),
    }
  }
  persistNanobotDiscussionState()
  if (previousKey && previousKey !== normalized) {
    removeNanobotDiscussionState(previousKey)
  }
}

const pushNanobotToolEvent = (event: Record<string, any>) => {
  const toolName = String(event.name || event.tool || event.tool_id || '未命名工具').trim() || '未命名工具'
  const rawStatus = String(event.status || event.event || '').trim().toLowerCase()
  const detail = String(event.detail || event.message || event.summary || '').trim()
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
  ].slice(-6)
}

const getCurrentWorkshopSessionId = () => {
  if (currentSessionMode.value === 'workshop' && currentSession.value?.session_id) {
    return currentSession.value.session_id
  }
  return String(nanobotDraftLink.value?.sessionId || '').trim()
}

const cancelNanobotStreaming = () => {
  if (!activeNanobotStreamController) return
  activeNanobotStreamController.abort()
}

const removeNanobotDiscussionState = (sessionKey?: string) => {
  if (typeof window === 'undefined') return
  const storageKey = getNanobotDiscussionStorageKey(sessionKey)
  if (!storageKey) return
  window.sessionStorage.removeItem(storageKey)
}

const restoreNanobotDiscussionState = (sessionKey?: string) => {
  if (typeof window === 'undefined') return false
  const storageKey = getNanobotDiscussionStorageKey(sessionKey)
  if (!storageKey) return false
  const raw = window.sessionStorage.getItem(storageKey)
  if (!raw) return false
  try {
    const parsed = JSON.parse(raw) as {
      sessionKey?: string
      messages?: AgentWorkshopMessage[]
      draftLink?: { specId: string; specName: string; sessionId?: string } | null
    }
    const restoredSessionKey = String(parsed.sessionKey || sessionKey || '').trim()
    const restoredMessages = Array.isArray(parsed.messages) ? parsed.messages : []
    nanobotDraftLink.value = parsed.draftLink || null
    if (restoredSessionKey) {
      syncNanobotSessionShell(restoredSessionKey, restoredMessages)
      currentSessionMode.value = 'nanobot'
      return true
    }
    currentSessionMode.value = 'workshop'
    return false
  } catch {
    return false
  }
}

const syncNanobotDiscussionRoute = () => {
  const nextQuery: Record<string, any> = { ...route.query }
  if (currentNanobotSessionKey.value) {
    nextQuery.nanobotSessionKey = currentNanobotSessionKey.value
  } else {
    delete nextQuery.nanobotSessionKey
  }
  const currentSessionId = String(route.query.sessionId || '')
  const currentSpecId = String(route.query.specId || '')
  const currentNanobotKey = String(route.query.nanobotSessionKey || '')
  const nextSessionId = String(nextQuery.sessionId || '')
  const nextSpecId = String(nextQuery.specId || '')
  const nextNanobotKey = String(nextQuery.nanobotSessionKey || '')
  if (
    currentSessionId === nextSessionId
    && currentSpecId === nextSpecId
    && currentNanobotKey === nextNanobotKey
  ) {
    return
  }
  router.replace({ path: '/workflow/agent-workshop/create', query: nextQuery })
}

const createEmptySpecSnapshot = (): AgentSpec => ({
  spec_id: '',
  name: 'Nanobot 需求讨论中',
  domain: 'general',
  target_users: [],
  primary_goal: '',
  responsibilities: [],
  non_goals: [],
  inputs: [],
  outputs: [],
  success_criteria: [],
  constraints: [],
  preferred_methods: [],
  sample_symbols: [],
  status: 'draft',
  source: 'nanobot',
  owner_user_id: '',
  latest_session_id: '',
  current_version_id: null,
  version_count: 0,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
})

const findLatestNanobotSpec = (afterMs?: number) => {
  const sortedSpecs = [...specs.value].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at || left.created_at || '') || 0
    const rightTime = Date.parse(right.updated_at || right.created_at || '') || 0
    return rightTime - leftTime
  })

  return sortedSpecs.find(item => {
    if (item.source !== 'nanobot') return false
    if (!afterMs) return true
    const updatedAt = Date.parse(item.updated_at || item.created_at || '') || 0
    return updatedAt >= afterMs - 5000
  }) || null
}

const syncWorkshopDraftAfterNanobot = async (options?: {
  response?: EmbeddedNanobotChatResponse
  requestedAtMs?: number
  force?: boolean
  silent?: boolean
  openIfFound?: boolean
}) => {
  const toolsUsed = options?.response?.tools_used || []
  const shouldCheckDraft = Boolean(options?.force || toolsUsed.some(toolId => (
    toolId === 'create_or_update_agent_workshop_draft' || toolId === 'generate_confirmed_candidate_agent'
  )))

  if (!shouldCheckDraft) {
    return false
  }

  await loadSpecs()
  const matchedSpec = findLatestNanobotSpec(options?.requestedAtMs)
  if (!matchedSpec) {
    if (options?.force && !options?.silent) {
      ElMessage.warning('Nanobot 还没有同步出可打开的 Draft，请继续补充需求后再试。')
    }
    return false
  }

  nanobotDraftLink.value = {
    specId: matchedSpec.spec_id,
    specName: matchedSpec.name,
    sessionId: matchedSpec.latest_session_id,
  }
  persistNanobotDiscussionState()

  if (options?.openIfFound) {
    await openSpec(matchedSpec)
    currentSessionMode.value = 'workshop'
    syncActiveStep('spec')
  }

  if (!options?.silent) {
    ElMessage.success(options?.openIfFound ? '已进入 Agent Workshop 规格确认' : 'Nanobot 已同步 Draft，可继续讨论或进入规格确认')
  }
  return true
}

const sendWorkshopMessageToNanobot = async (message: string) => {
  const normalizedMessage = message.trim()
  if (!normalizedMessage) return null

  const requestedAtMs = Date.now()
  const sessionKey = currentNanobotSessionKey.value || `${NANOBOT_WORKSHOP_SESSION_PREFIX}${requestedAtMs}`
  const now = new Date().toISOString()
  const nextMessages = [
    ...nanobotDiscussionMessages.value,
    { role: 'user', content: normalizedMessage, timestamp: now },
    { role: 'assistant', content: '', timestamp: now },
  ]
  const assistantIndex = nextMessages.length - 1

  syncNanobotSessionShell(sessionKey, nextMessages)
  nanobotStreaming.value = true
  nanobotProgressHint.value = '正在发送给 Nanobot'
  nanobotToolEvents.value = []

  const appendAssistantChunk = (chunk?: string) => {
    const text = String(chunk || '')
    if (!text.trim()) return
    nextMessages[assistantIndex].content = nextMessages[assistantIndex].content
      ? `${nextMessages[assistantIndex].content}\n${text}`
      : text
  }

  try {
    const response = await new Promise<EmbeddedNanobotChatResponse>((resolve, reject) => {
      activeNanobotStreamController = embeddedNanobotApi.chatStream({
        message: normalizedMessage,
        session_key: sessionKey,
        channel: 'agent_workshop',
        chat_id: sessionKey,
        skill_names: NANOBOT_WORKSHOP_SKILLS,
      }, {
        onStarted(data) {
          updateNanobotSessionKey(data.session_key || sessionKey)
          nanobotProgressHint.value = data.message || 'Nanobot 已开始处理当前需求'
        },
        onProgress(data) {
          updateNanobotSessionKey(data.session_key || currentNanobotSessionKey.value)
          nanobotProgressHint.value = data.message || 'Nanobot 正在处理中'
        },
        onToken(content) {
          appendAssistantChunk(content)
          syncNanobotSessionShell(currentNanobotSessionKey.value || sessionKey, [...nextMessages])
        },
        onToolEvent(event) {
          pushNanobotToolEvent(event)
          const toolName = String(event.name || event.tool || event.tool_id || '工具').trim() || '工具'
          nanobotProgressHint.value = event.status === 'started'
            ? `正在执行 ${toolName}`
            : `已处理 ${toolName} 的最新动作`
        },
        onDone(data) {
          updateNanobotSessionKey(data.session_key || currentNanobotSessionKey.value || sessionKey)
          if (!nextMessages[assistantIndex].content.trim()) {
            nextMessages[assistantIndex].content = data.content || 'Nanobot 已处理当前需求。'
          }
          syncNanobotSessionShell(currentNanobotSessionKey.value || sessionKey, [...nextMessages])
          nanobotProgressHint.value = data.tools_used?.length
            ? `本轮已完成，调用了 ${data.tools_used.length} 个工具`
            : '本轮已完成'
          resolve(data)
        },
        onError(messageText) {
          nextMessages[assistantIndex].content = nextMessages[assistantIndex].content || `请求失败：${messageText || '未知错误'}`
          syncNanobotSessionShell(currentNanobotSessionKey.value || sessionKey, [...nextMessages])
          reject(new Error(messageText || '未知错误'))
        },
        onAbort() {
          nextMessages[assistantIndex].content = nextMessages[assistantIndex].content || '已停止本轮生成。'
          syncNanobotSessionShell(currentNanobotSessionKey.value || sessionKey, [...nextMessages])
          reject(new Error('已停止生成'))
        },
      })
    })

    const switchedToDraft = await syncWorkshopDraftAfterNanobot({
      response,
      requestedAtMs,
      silent: true,
      openIfFound: false,
    })

    syncNanobotDiscussionRoute()

    return {
      response,
      switchedToDraft,
    }
  } finally {
    activeNanobotStreamController = null
    nanobotStreaming.value = false
  }
}

const sendWorkshopStageCommandToNanobot = async (options: {
  expectedToolId: string
  message: string
  successMessage: string
  refreshVersion?: boolean
  nextStep?: FlowStep
  routeToSession?: boolean
}) => {
  const workshopSessionId = getCurrentWorkshopSessionId()
  if (!workshopSessionId) return false

  const result = await sendWorkshopMessageToNanobot(options.message)
  const toolsUsed = result?.response?.tools_used || []
  if (!toolsUsed.includes(options.expectedToolId)) {
    throw new Error('Nanobot 这次没有真正执行对应阶段工具，请稍后重试。')
  }

  await refreshSession()
  await loadSpecs()
  if (options.refreshVersion) {
    await loadLatestVersion(currentSession.value?.current_spec_snapshot?.spec_id)
  }
  if (options.routeToSession && workshopSessionId) {
    router.replace({
      path: '/workflow/agent-workshop/create',
      query: {
        sessionId: workshopSessionId,
        ...(currentNanobotSessionKey.value ? { nanobotSessionKey: currentNanobotSessionKey.value } : {}),
      },
    })
  }
  syncActiveStep(options.nextStep)
  ElMessage.success(options.successMessage)
  return true
}

const loadLatestVersionPrompt = async (versionId?: string) => {
  if (!versionId) {
    latestVersionPrompt.value = null
    return
  }
  try {
    latestVersionPrompt.value = await agentWorkshopApi.getVersionPrompt(versionId)
  } catch {
    latestVersionPrompt.value = null
  }
}

const loadLatestEvaluation = async (versionId?: string) => {
  if (!versionId) {
    latestEvaluation.value = null
    evaluationHistory.value = []
    syncActiveStep()
    return
  }
  try {
    const result = await agentWorkshopApi.listEvaluations(versionId, { page: 1, page_size: 5 })
    evaluationHistory.value = result.items || []
    latestEvaluation.value = evaluationHistory.value[0] || null
  } catch {
    latestEvaluation.value = null
    evaluationHistory.value = []
  } finally {
    syncActiveStep()
  }
}

const loadSpecs = async () => {
  loadingSpecs.value = true
  try {
    const result = await agentWorkshopApi.listSpecs({ page: 1, page_size: 20 })
    specs.value = result.items || []
  } catch (error: any) {
    ElMessage.error(error?.message || '加载规格失败')
  } finally {
    loadingSpecs.value = false
  }
}

const loadCapabilitySnapshot = async () => {
  try {
    capabilitySnapshot.value = await agentWorkshopApi.getCapabilitySnapshot()
  } catch {
    capabilitySnapshot.value = null
  }
}

const loadToolCatalog = async () => {
  try {
    toolCatalog.value = await toolsApi.listTools()
  } catch {
    toolCatalog.value = []
  }
}

const initFromRoute = async () => {
  await Promise.all([loadSpecs(), loadCapabilitySnapshot(), loadToolCatalog()])

  const sessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : ''
  const specId = typeof route.query.specId === 'string' ? route.query.specId : ''
  const nanobotSessionKey = typeof route.query.nanobotSessionKey === 'string' ? route.query.nanobotSessionKey : ''

  debugAgentWorkshopState('init-from-route:start', { sessionId, specId, nanobotSessionKey })

  clearWorkspace(true)

  if (nanobotSessionKey) {
    restoreNanobotDiscussionState(nanobotSessionKey)
  }

  if (sessionId) {
    loadingSessionList.value = true
    try {
      currentSession.value = await agentWorkshopApi.getSession(sessionId)
      currentSessionMode.value = 'workshop'
      gapReport.value = currentSession.value.gap_report || null
      syncPreviewSpecFromSession('init-from-route-session')
      await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
      syncActiveStep()
      debugAgentWorkshopState('init-from-route:loaded-session', { sessionId })
    } catch (error: any) {
      ElMessage.error(error?.message || '加载工坊会话失败')
    } finally {
      loadingSessionList.value = false
    }
    return
  }

  if (specId) {
    const matched = specs.value.find(item => item.spec_id === specId)
    if (matched) {
      await openSpec(matched)
    } else {
      try {
        const detail = await agentWorkshopApi.getSpec(specId)
        previewResult.value = {
          spec: detail,
          completeness_score: 0,
          pending_questions: [],
          feasibility_status: 'need-clarification',
          refusal_reason: '',
          readiness: 'needs-clarification',
        }
        await loadLatestVersion(detail.spec_id)
        syncActiveStep('spec')
        debugAgentWorkshopState('init-from-route:loaded-spec', { specId: detail.spec_id })
      } catch (error: any) {
        ElMessage.error(error?.message || '加载 Agent 规格失败')
      }
    }
  }
}

const refreshSession = async () => {
  if (!currentSession.value?.session_id) return
  if (isNanobotDiscussionSession.value) {
    await syncWorkshopDraftAfterNanobot({ force: true })
    return
  }
  loadingCurrentSession.value = true
  try {
    const [session] = await Promise.all([
      agentWorkshopApi.getSession(currentSession.value.session_id),
      loadCapabilitySnapshot(),
    ])
    currentSession.value = session
    gapReport.value = currentSession.value.gap_report || null
    syncPreviewSpecFromSession('refresh-session')
    await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
    debugAgentWorkshopState('refresh-session:success')
  } catch (error: any) {
    ElMessage.error(error?.message || '刷新会话失败')
  } finally {
    loadingCurrentSession.value = false
    syncActiveStep()
  }
}

const refreshAll = async () => {
  if (currentSession.value?.session_id) {
    await Promise.all([loadSpecs(), refreshSession()])
    return
  }

  if (displaySpec.value?.spec_id) {
    await Promise.all([loadSpecs(), loadLatestVersion(displaySpec.value.spec_id)])
    return
  }

  await loadSpecs()
}

const handleStartSession = async () => {
  if (!description.value.trim()) return
  starting.value = true
  try {
    clearWorkspace()
    const result = await sendWorkshopMessageToNanobot(description.value.trim())
    if (!result) return
    await loadSpecs()
    router.replace({
      path: '/workflow/agent-workshop/create',
      query: currentNanobotSessionKey.value ? { nanobotSessionKey: currentNanobotSessionKey.value } : {},
    })
    syncActiveStep('discuss')
    ElMessage.success(result.switchedToDraft ? '已同步 Nanobot Draft，可继续讨论' : '已接入 Nanobot 开始讨论')
  } catch (error: any) {
    ElMessage.error(error?.message || '创建会话失败')
  } finally {
    starting.value = false
  }
}

const handleRespond = async () => {
  const sessionId = currentSession.value?.session_id || ''
  if ((!sessionId && !currentNanobotSessionKey.value) || !replyMessage.value.trim()) return
  responding.value = true
  try {
    if (isNanobotDiscussionSession.value) {
      const result = await sendWorkshopMessageToNanobot(replyMessage.value.trim())
      if (!result) return
      await loadSpecs()
    } else {
      await agentWorkshopApi.respondToSession(sessionId, replyMessage.value.trim())
      await refreshSession()
      await loadSpecs()
    }
    replyMessage.value = ''
    syncActiveStep('discuss')
  } catch (error: any) {
    ElMessage.error(error?.message || '回复失败')
  } finally {
    responding.value = false
  }
}

const handlePreviewSpec = async () => {
  if (!currentSession.value?.session_id) return
  if (isNanobotDiscussionSession.value) {
    previewing.value = true
    try {
      if (replyMessage.value.trim()) {
        await sendWorkshopMessageToNanobot(replyMessage.value.trim())
        replyMessage.value = ''
      }
      const switched = await syncWorkshopDraftAfterNanobot({ force: true, openIfFound: true })
      if (!switched) {
        ElMessage.warning('还没有可打开的 Draft。请先按 Nanobot 的提示补充或确认需求。')
      }
    } catch (error: any) {
      ElMessage.error(error?.message || '打开 Draft 失败')
    } finally {
      previewing.value = false
    }
    return
  }
  previewing.value = true
  try {
    previewResult.value = await agentWorkshopApi.previewSpec(currentSession.value.session_id)
    await refreshSession()
    await loadSpecs()
    syncActiveStep('spec')
    ElMessage.success('规格预览已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '规格预览失败')
  } finally {
    previewing.value = false
  }
}

const submitSpecFeedback = async (message: string) => {
  const workshopSessionId = getCurrentWorkshopSessionId()
  if (!workshopSessionId && !currentNanobotSessionKey.value) return
  confirmingSpec.value = true
  try {
    if (workshopSessionId) {
      await agentWorkshopApi.respondToSession(workshopSessionId, message)
      currentSession.value = await agentWorkshopApi.getSession(workshopSessionId)
      currentSessionMode.value = 'workshop'
      previewResult.value = await agentWorkshopApi.previewSpec(workshopSessionId)
      gapReport.value = currentSession.value.gap_report || null
      specFeedbackMessage.value = ''
      await loadSpecs()
    } else if (currentNanobotSessionKey.value) {
      const result = await sendWorkshopMessageToNanobot(buildNanobotDraftUpdateMessage(message))
      const switched = await syncWorkshopDraftAfterNanobot({
        response: result?.response,
        force: true,
        openIfFound: true,
        silent: true,
      })
      specFeedbackMessage.value = ''
      await loadSpecs()
      if (!switched) {
        ElMessage.warning('Nanobot 已收到修改意见，但还没有同步出新的规格草案。请继续补充或稍后重试。')
        syncActiveStep('spec')
        return
      }
    }
    syncActiveStep('spec')
    ElMessage.success('规格确认信息已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '更新规格确认失败')
  } finally {
    confirmingSpec.value = false
  }
}

const handleConfirmAndBuildVersion = async () => {
  const message = specFeedbackMessage.value.trim()
  if (message) {
    await submitSpecFeedback(message)
  }
  await handleBuildVersion()
}

const handleAcceptRecommendedSpec = async () => {
  await handleConfirmAndBuildVersion()
}

const handleSubmitSpecFeedback = async () => {
  const message = specFeedbackMessage.value.trim()
  if (!message) return
  await submitSpecFeedback(message)
}

const handleAnalyzeGaps = async () => {
  const workshopSessionId = getCurrentWorkshopSessionId()
  if (!workshopSessionId) return
  analyzing.value = true
  try {
    if (currentNanobotSessionKey.value) {
      await sendWorkshopStageCommandToNanobot({
        expectedToolId: 'analyze_agent_workshop_gaps',
        message: [
          '继续当前 Agent Workshop 会话，直接执行缺口分析。',
          `请调用 analyze_agent_workshop_gaps(session_id='${workshopSessionId}')。`,
          '执行后请用中文总结：现有可复用能力、主要阻塞缺口、建议补齐方向。不要反问。',
        ].join('\n'),
        successMessage: '缺口分析完成',
        nextStep: 'gap',
      })
      gapReport.value = currentSession.value?.gap_report || null
      return
    }

    const result = await agentWorkshopApi.analyzeGaps(workshopSessionId)
    gapReport.value = result.gap_report
    await refreshSession()
    syncActiveStep('gap')
    ElMessage.success('缺口分析完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '缺口分析失败')
  } finally {
    analyzing.value = false
  }
}

const handleGenerateToolingPlan = async () => {
  const workshopSessionId = getCurrentWorkshopSessionId()
  if (!workshopSessionId) return
  generatingToolPlan.value = true
  try {
    if (currentNanobotSessionKey.value) {
      await sendWorkshopStageCommandToNanobot({
        expectedToolId: 'generate_agent_workshop_tooling_plan',
        message: [
          '继续当前 Agent Workshop 会话，直接生成工具需求草案。',
          `请调用 generate_agent_workshop_tooling_plan(session_id='${workshopSessionId}')。`,
          '执行后请用中文总结：缺哪些能力、优先补哪些工具、哪些可以先复用。不要反问。',
        ].join('\n'),
        successMessage: '工具需求草案已生成',
        nextStep: 'gap',
      })
      return
    }

    await agentWorkshopApi.generateToolingPlan(workshopSessionId)
    await refreshSession()
    syncActiveStep('gap')
    ElMessage.success('工具需求草案已生成')
  } catch (error: any) {
    ElMessage.error(error?.message || '生成工具需求草案失败')
  } finally {
    generatingToolPlan.value = false
  }
}

const handleBuildVersion = async () => {
  const workshopSessionId = getCurrentWorkshopSessionId()
  if (!workshopSessionId) return
  buildingVersion.value = true
  try {
    debugAgentWorkshopState('build-version:start', { workshopSessionId })
    const result = await agentWorkshopApi.buildVersion(workshopSessionId)
    latestVersion.value = result.version
    await refreshSession()
    await loadSpecs()
    await loadLatestVersion(currentSession.value?.current_spec_snapshot?.spec_id || result.spec_id)
    syncPreviewSpecFromSession('build-version')
    router.replace({
      path: '/workflow/agent-workshop/create',
      query: {
        sessionId: workshopSessionId,
        ...(currentNanobotSessionKey.value ? { nanobotSessionKey: currentNanobotSessionKey.value } : {}),
      },
    })
    currentSessionMode.value = 'workshop'
    syncActiveStep('version')
    debugAgentWorkshopState('build-version:success', {
      workshopSessionId,
      resultSpecId: result.spec_id,
      resultVersionId: result.version?.version_id || '',
    })
    ElMessage.success('可测试版本已生成，下一步可以直接开始测试')
  } catch (error: any) {
    ElMessage.error(error?.message || '生成版本草案失败')
  } finally {
    buildingVersion.value = false
  }
}

// const handleDeleteSpec = async (spec: AgentSpec) => {
//   try {
//     await ElMessageBox.confirm(
//       `确定删除“${spec.name}”吗？这会同时删除它的会话、版本和评估记录。`,
//       '删除 Agent 草案',
//       {
//         type: 'warning',
//         confirmButtonText: '删除',
//         cancelButtonText: '取消',
//         confirmButtonClass: 'el-button--danger',
//       }
//     )
//
//     await agentWorkshopApi.deleteSpec(spec.spec_id)
//
//     if (currentSession.value?.spec_id === spec.spec_id) {
//       currentSession.value = null
//       previewResult.value = null
//       gapReport.value = null
//       latestVersion.value = null
//       latestEvaluation.value = null
//       replyMessage.value = ''
//     }
//
//     await refreshAll()
//     syncActiveStep()
//     ElMessage.success('测试 Agent 已删除')
//   } catch (error: any) {
//     if (error === 'cancel' || error?.message === 'cancel') {
//       return
//     }
//     ElMessage.error(error?.message || '删除规格失败')
//   }
// }

const openEvaluateDialog = async () => {
  if (!latestVersion.value?.spec_id) return
  resetEvaluationForm()
  latestDebugResult.value = null
  evaluateDialogVisible.value = true
  syncActiveStep('evaluate')
}

const handleDebugVersion = async () => {
  if (!latestVersion.value?.version_id) return
  debuggingVersion.value = true
  try {
    if (!evaluationForm.value.llm.model?.trim()) {
      ElMessage.warning('请先选择模型')
      return
    }

    if (!evaluationForm.value.stock.symbol?.trim()) {
      ElMessage.warning('请先填写股票代码')
      return
    }

    const debugResult = await agentWorkshopApi.debugVersion(latestVersion.value.version_id, {
      llm: {
        provider: evaluationForm.value.llm.provider,
        model: evaluationForm.value.llm.model,
        temperature: evaluationForm.value.llm.temperature,
        max_tokens: evaluationForm.value.llm.max_tokens,
        backend_url: evaluationForm.value.llm.backend_url || undefined,
      },
      stock: {
        symbol: evaluationForm.value.stock.symbol.trim(),
        market_type: evaluationForm.value.stock.market_type,
        analysis_date: evaluationForm.value.stock.analysis_date || undefined,
      },
      user_goal: evaluationForm.value.runtime_result.user_goal || displaySpec.value?.primary_goal || '',
    })

    latestDebugResult.value = debugResult
  evaluationForm.value.runtime_result.report = debugResult.report || ''
  evaluationForm.value.runtime_result.raw_result = debugResult.raw_result || {}
    evaluationForm.value.runtime_result.output_text = debugResult.debug_prompt?.llm_final_response || debugResult.report || ''
    evaluationForm.value.runtime_result.user_goal = evaluationForm.value.runtime_result.user_goal || displaySpec.value?.primary_goal || ''
    evaluationForm.value.runtime_result.output_payload = debugResult.raw_result || {}
    evaluationForm.value.runtime_result.debug_prompt = debugResult.debug_prompt || {}
  evaluationForm.value.runtime_result.tool_trace = debugResult.debug_prompt?.tool_trace || debugResult.raw_result?.tool_trace || []
    evaluationForm.value.runtime_result.template = debugResult.template || {}
    evaluationForm.value.runtime_result.metadata = debugResult.metadata || {}
    evaluationForm.value.runtime_result.symbol = debugResult.symbol || evaluationForm.value.stock.symbol.trim()
    evaluationForm.value.runtime_result.analysis_date = debugResult.analysis_date || evaluationForm.value.stock.analysis_date || ''
    ElMessage.success('调试运行完成，可以继续做结果评估')
  } catch (error: any) {
    ElMessage.error(error?.message || '调试运行失败')
  } finally {
    debuggingVersion.value = false
  }
}

const handleEvaluateVersion = async () => {
  if (!latestVersion.value?.version_id) return
  evaluatingVersion.value = true
  try {
    if (!evaluationForm.value.runtime_result.output_text?.trim()) {
      ElMessage.warning('请先完成调试运行并生成结果')
      return
    }

    const debugResult = latestDebugResult.value

    const payload: any = {
      evaluation_type: 'production-review',
      user_feedback: evaluationForm.value.user_feedback || '',
      runtime_result: {
        review_worker_mode: 'nanobot-assisted',
        nanobot_evidence_workers: true,
        user_goal: evaluationForm.value.runtime_result.user_goal,
        report: evaluationForm.value.runtime_result.report || debugResult?.report || '',
        raw_result: evaluationForm.value.runtime_result.raw_result || debugResult?.raw_result || {},
        output_text: evaluationForm.value.runtime_result.output_text,
        symbol: evaluationForm.value.runtime_result.symbol || debugResult?.symbol || evaluationForm.value.stock.symbol.trim(),
        analysis_date: evaluationForm.value.runtime_result.analysis_date || debugResult?.analysis_date || evaluationForm.value.stock.analysis_date,
        output_payload: evaluationForm.value.runtime_result.output_payload || debugResult?.raw_result || {},
        debug_prompt: evaluationForm.value.runtime_result.debug_prompt || debugResult?.debug_prompt || {},
        tool_trace: evaluationForm.value.runtime_result.tool_trace || debugResult?.debug_prompt?.tool_trace || debugResult?.raw_result?.tool_trace || [],
        template: evaluationForm.value.runtime_result.template || debugResult?.template || {},
        metadata: evaluationForm.value.runtime_result.metadata || debugResult?.metadata || {},
        llm: {
          provider: evaluationForm.value.llm.provider,
          model: evaluationForm.value.llm.model,
          temperature: evaluationForm.value.llm.temperature,
          max_tokens: evaluationForm.value.llm.max_tokens,
          backend_url: evaluationForm.value.llm.backend_url || undefined,
        },
      }
    }

    const result = await agentWorkshopApi.evaluateVersion(latestVersion.value.version_id, payload)
    latestEvaluation.value = result.evaluation
    latestVersion.value = await agentWorkshopApi.getVersion(latestVersion.value.version_id)
    syncActiveStep('evaluate')
    ElMessage.success('版本评估完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '版本评估失败')
  } finally {
    evaluatingVersion.value = false
  }
}

const handleIterateVersion = async () => {
  if (!latestVersion.value?.version_id) return
  iteratingVersion.value = true
  try {
    const result = await agentWorkshopApi.iterateVersion(latestVersion.value.version_id)
    currentSession.value = await agentWorkshopApi.getSession(result.session_id)
    previewResult.value = null
    gapReport.value = currentSession.value.gap_report || null
    await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
    await loadSpecs()
    router.replace({ path: '/workflow/agent-workshop/create', query: { sessionId: result.session_id } })
    syncActiveStep('discuss')
    ElMessage.success('已基于评估创建下一轮工坊会话')
  } catch (error: any) {
    ElMessage.error(error?.message || '发起迭代失败')
  } finally {
    iteratingVersion.value = false
  }
}

const openSpec = async (spec: AgentSpec) => {
  try {
    debugAgentWorkshopState('open-spec:start', { specId: spec.spec_id, specName: spec.name })
    const detail = await agentWorkshopApi.getSpec(spec.spec_id)
    currentSessionMode.value = 'workshop'
    previewResult.value = {
      spec: detail,
      completeness_score: currentSession.value?.current_spec_snapshot?.spec_id === spec.spec_id
        ? currentSession.value.completeness_score
        : 0,
      pending_questions: currentSession.value?.current_spec_snapshot?.spec_id === spec.spec_id
        ? currentSession.value.pending_questions
        : [],
      feasibility_status: currentSession.value?.current_spec_snapshot?.spec_id === spec.spec_id
        ? currentSession.value.feasibility_status
        : 'need-clarification',
      refusal_reason: currentSession.value?.current_spec_snapshot?.spec_id === spec.spec_id
        ? currentSession.value.refusal_reason
        : '',
      readiness: currentSession.value?.current_spec_snapshot?.spec_id === spec.spec_id && currentSession.value.completeness_score >= 0.75
        ? 'ready'
        : (currentSession.value?.feasibility_status === 'not-feasible' ? 'blocked' : 'needs-clarification'),
    }
    if (detail.latest_session_id) {
      currentSession.value = await agentWorkshopApi.getSession(detail.latest_session_id)
      gapReport.value = currentSession.value.gap_report || null
      syncPreviewSpecFromSession('open-spec-latest-session')
      await loadLatestVersion(detail.spec_id)
      router.replace({ path: '/workflow/agent-workshop/create', query: { sessionId: detail.latest_session_id, ...(currentNanobotSessionKey.value ? { nanobotSessionKey: currentNanobotSessionKey.value } : {}) } })
    } else {
      currentSession.value = null
      gapReport.value = null
      latestVersion.value = null
      latestEvaluation.value = null
      router.replace({ path: '/workflow/agent-workshop/create', query: { specId: detail.spec_id, ...(currentNanobotSessionKey.value ? { nanobotSessionKey: currentNanobotSessionKey.value } : {}) } })
    }
    syncActiveStep('spec')
    debugAgentWorkshopState('open-spec:success', { specId: detail.spec_id, latestSessionId: detail.latest_session_id || '' })
  } catch (error: any) {
    ElMessage.error(error?.message || '打开规格失败')
  }
}

const fillExample = (type: 'valuation' | 'industry' | 'watcher') => {
  if (type === 'valuation') {
    description.value = '我要做一个新的股票估值分析师，它要能根据行情、财务数据和行业背景给出估值区间，解释关键假设，说明失效条件，但不要直接给买卖建议。'
    return
  }
  if (type === 'industry') {
    description.value = '我想做一个行业比较研究员，负责横向比较行业格局、盈利质量、估值水平和景气位置，输出结构化对比结论。'
    return
  }
  description.value = '我想做一个财报跟踪助手，负责跟踪重点公司的季报变化、提炼异常指标、总结风险提示，但不做独立投资建议。'
}

const humanizeToolId = (toolId: string) => {
  const normalized = String(toolId || '').trim().toLowerCase()
  if (!normalized) return '待澄清能力'

  const aliases: Record<string, string> = {
    stock_valuation_calculator: '股票估值计算',
    get_analyst_forecast: '分析师预测获取',
    get_market_quotes: '行情获取',
    get_stock_fundamentals: '基本面数据获取',
    peer_comparison: '可比公司对比',
  }
  if (aliases[normalized]) return aliases[normalized]

  return normalized
    .replace(/^(get_|fetch_|query_|load_|calculate_|build_)/, '')
    .split('_')
    .filter(Boolean)
    .map(part => {
      const tokenMap: Record<string, string> = {
        stock: '股票',
        valuation: '估值',
        calculator: '计算',
        analyst: '分析师',
        forecast: '预测',
        market: '行情',
        quote: '报价',
        quotes: '报价',
        fundamentals: '基本面',
        fundamental: '基本面',
        peer: '可比对象',
        comparison: '对比',
        risk: '风险',
        score: '评分',
        ranking: '排序',
      }
      return tokenMap[part] || part.toUpperCase()
    })
    .join('')
}

const getSuggestedToolDescription = (toolId: string) => {
  const toolDraft = toolingPlan.value?.draft_tools?.find(item => item.tool_id === toolId)
  if (toolDraft?.capability_description) {
    return toolDraft.capability_description
  }
  if (toolDraft?.why_needed) {
    return toolDraft.why_needed
  }

  if (toolDraft?.solves_gaps?.length) {
    return `这是一个面向“${humanizeToolId(toolId)}”的候选执行能力，主要用于解决：${toolDraft.solves_gaps.slice(0, 2).join('；')}。具体输入、输出、数据来源和调用边界还需要在能力工坊里继续澄清。`
  }

  const blockingGaps = gapReport.value?.blocking_gaps || []
  if (blockingGaps.length) {
    return `这是一个面向“${humanizeToolId(toolId)}”的候选执行能力，目的是补齐 Agent 当前缺少的一段可直接调用的执行链路。它应被收敛成输入输出明确、结果可复核的最小能力单元；具体功能边界会结合当前缺口继续澄清。`
  }

  return `这是一个面向“${humanizeToolId(toolId)}”的候选执行能力，用来给 Agent 提供可直接调用的结构化结果。当前名称只是能力草案，还需要在能力工坊里进一步明确它的输入参数、输出结构、依赖数据和调用边界。`
}

const getSortedToolDrafts = () => {
  const priorityOrder: Record<string, number> = { P0: 0, P1: 1, P2: 2 }
  return [...(toolingPlan.value?.draft_tools || [])].sort((left, right) => {
    const leftPriority = priorityOrder[left.priority] ?? 99
    const rightPriority = priorityOrder[right.priority] ?? 99
    if (leftPriority !== rightPriority) return leftPriority - rightPriority
    return (left.tool_id || '').localeCompare(right.tool_id || '')
  })
}

const findConcreteToolDraft = (target: string | AgentWorkshopToolingPlanItem) => {
  if (typeof target !== 'string') return target

  const normalizedTarget = target.trim().toLowerCase()
  const drafts = getSortedToolDrafts()
  const exact = drafts.find(item =>
    item.tool_id?.toLowerCase() === normalizedTarget ||
    item.tool_name?.toLowerCase() === normalizedTarget,
  )
  if (exact) return exact

  if (normalizedTarget.includes('skill')) {
    return drafts[0] || null
  }

  return null
}

const collectKeywordTokens = (value: string) => {
  return value
    .toLowerCase()
    .split(/[^a-z0-9\u4e00-\u9fa5]+/)
    .map(item => item.trim())
    .filter(item => item.length >= 2)
}

const getToolScopeHints = (toolDraft: AgentWorkshopToolingPlanItem) => {
  const toolKey = `${toolDraft.tool_id || ''} ${toolDraft.tool_name || ''}`.toLowerCase()

  if (toolKey.includes('pe_relative') || (toolKey.includes('pe') && toolKey.includes('relative'))) {
    return {
      keywords: ['pe', '相对估值', '市盈率', '同行', '同业', '可比公司', 'peer'],
      scopeLines: [
        '只实现 PE 相对估值这一段执行链路，不扩展为 DCF、PEG 或三种方法综合结论。',
        '围绕可比公司/同行对比完成估值，输出 PE 估值数值与估值区间。',
        '需要说明可比对象选择依据、核心参数/倍数选择依据，以及方法失效边界。',
      ],
      nonGoalLines: [
        '不负责 DCF 估值计算。',
        '不负责 PEG 估值计算。',
        '不负责三种估值结果的综合汇总。',
        '不输出直接买卖建议。',
      ],
    }
  }

  if (toolKey.includes('dcf')) {
    return {
      keywords: ['dcf', '折现', '现金流', '自由现金流', 'discount'],
      scopeLines: [
        '只实现 DCF 估值这一段执行链路，不扩展为 PE、PEG 或三种方法综合结论。',
        '围绕现金流折现法完成估值，输出 DCF 估值数值与估值区间。',
        '需要说明现金流预测、折现率、终值等关键假设及方法失效边界。',
      ],
      nonGoalLines: [
        '不负责 PE 相对估值计算。',
        '不负责 PEG 估值计算。',
        '不负责三种估值结果的综合汇总。',
        '不输出直接买卖建议。',
      ],
    }
  }

  if (toolKey.includes('peg')) {
    return {
      keywords: ['peg', '增长', 'growth'],
      scopeLines: [
        '只实现 PEG 估值这一段执行链路，不扩展为 DCF、PE 或三种方法综合结论。',
        '围绕 PEG 估值法完成估值，输出 PEG 估值数值与估值区间。',
        '需要说明增长率假设、PE 与增长匹配关系，以及方法失效边界。',
      ],
      nonGoalLines: [
        '不负责 DCF 估值计算。',
        '不负责 PE 相对估值计算。',
        '不负责三种估值结果的综合汇总。',
        '不输出直接买卖建议。',
      ],
    }
  }

  return {
    keywords: [],
    scopeLines: [
      '这次只补齐当前点选的单一执行能力，不要扩展成整个 Agent 的完整能力集合。',
    ],
    nonGoalLines: [
      '不把当前子能力泛化成覆盖整个 Agent 的大而全方案。',
    ],
  }
}

const pickRelevantSpecLines = (lines: Array<string | AgentSpecIOItem>, toolDraft: AgentWorkshopToolingPlanItem, fallbackCount = 2) => {
  const normalizedLines = lines.map(item => getSpecIoText(item as AgentSpecIOItem)).filter(Boolean)
  if (!normalizedLines.length) return []

  const scopeHints = getToolScopeHints(toolDraft)
  const keywordSet = new Set<string>(scopeHints.keywords)
  ;[
    toolDraft.tool_id,
    toolDraft.tool_name,
    toolDraft.capability_description,
    toolDraft.why_needed,
    ...(toolDraft.solves_gaps || []),
    ...(toolDraft.acceptance_criteria || []),
    ...(toolDraft.outputs || []).map(field => `${field.name} ${field.description || ''}`),
  ].filter(Boolean).forEach(item => {
    for (const token of collectKeywordTokens(String(item))) {
      keywordSet.add(token)
    }
  })

  const keywords = Array.from(keywordSet)
  if (!keywords.length) return normalizedLines.slice(0, fallbackCount)

  const matched = normalizedLines.filter(line => {
    const normalizedLine = line.toLowerCase()
    return keywords.some(keyword => normalizedLine.includes(keyword.toLowerCase()))
  })

  return matched.length ? matched : normalizedLines.slice(0, fallbackCount)
}

const buildToolDraftSkillDescription = (toolDraft: AgentWorkshopToolingPlanItem) => {
  const spec = displaySpec.value
  const version = latestVersion.value
  const gapNotes = gapReport.value?.blocking_gaps || []
  const recommendations = gapReport.value?.build_recommendations || []
  const toolHints = version?.required_tools || []
  const scopeHints = getToolScopeHints(toolDraft)
  const responsibilityLines = pickRelevantSpecLines(spec?.responsibilities || [], toolDraft, 3).map(item => `- ${item}`)
  const specOutputLines = pickRelevantSpecLines(spec?.outputs || [], toolDraft, 3).map(item => `- ${item}`)
  const nonGoalLines = [
    ...(pickRelevantSpecLines(spec?.non_goals || [], toolDraft, 2)),
    ...scopeHints.nonGoalLines,
  ].filter((item, index, array) => array.indexOf(item) === index).map(item => `- ${item}`)
  const inputLines = (toolDraft.inputs || []).map(field => `- ${field.name}: ${field.type}${field.required ? '，必填' : '，可选'}${field.description ? `，${field.description}` : ''}`)
  const outputLines = (toolDraft.outputs || []).map(field => `- ${field.name}: ${field.type}${field.description ? `，${field.description}` : ''}`)

  return [
    `我要补齐一个 Agent 可直接调用的执行能力：${toolDraft.tool_id}。`,
    spec?.name ? `它服务于 Agent：${spec.name}。` : '',
    spec?.primary_goal ? `Agent 目标：${spec.primary_goal}` : '',
    spec?.domain ? `业务领域：${spec.domain}` : '',
    '注意：当前只是从这个 Agent 中拆出一个要补齐的子能力，不是重新定义整个 Agent。下面会同时给你上游 Agent 背景和这个子能力自己的明确范围。',
    responsibilityLines.length ? `上游 Agent 背景中，与当前子能力直接相关的职责：\n${responsibilityLines.join('\n')}` : '',
    specOutputLines.length ? `上游 Agent 背景中，与当前子能力直接相关的输出：\n${specOutputLines.join('\n')}` : '',
    nonGoalLines.length ? `当前子能力必须继承的边界与非目标：\n${nonGoalLines.join('\n')}` : '',
    toolHints.length ? `当前 Agent 已绑定工具：${toolHints.join('、')}` : '',
    gapNotes.length ? `当前识别到的关键缺口：${gapNotes.slice(0, 3).join('；')}` : '',
    recommendations.length ? `实现建议：${recommendations.slice(0, 3).join('；')}` : '',
    `这项子能力的名称说明：${toolDraft.tool_name || toolDraft.tool_id}`,
    toolDraft.capability_description ? `这项子能力的功能说明：${toolDraft.capability_description}` : '',
    `这项能力的目标是：${toolDraft.why_needed}`,
    toolDraft.solves_gaps?.length ? `它要解决的问题：${toolDraft.solves_gaps.join('；')}` : '',
    scopeHints.scopeLines.length ? `这项子能力本次必须收敛到的职责范围：\n${scopeHints.scopeLines.map(item => `- ${item}`).join('\n')}` : '',
    toolDraft.dependencies?.length ? `依赖数据或前置条件：${toolDraft.dependencies.join('、')}` : '',
    inputLines.length ? `建议输入参数：\n${inputLines.join('\n')}` : '',
    outputLines.length ? `建议输出结构：\n${outputLines.join('\n')}` : '',
    toolDraft.acceptance_criteria?.length ? `验收标准：${toolDraft.acceptance_criteria.join('；')}` : '',
    toolDraft.fallback_before_ready ? `未完成前的降级策略：${toolDraft.fallback_before_ready}` : '',
    `本次不要偏题：你要补的是“${toolDraft.tool_id}”这一段最小执行能力，不是整个股票估值分析 Agent，也不是三种估值方法的总控流程。`,
    '请先判断这项能力能否直接复用现有工具或已有 Skill；如果不能，再把它收敛成一个新增的最小实现单元。不要泛化成大而全的综合能力。重点只描述这个单一能力的输入参数、输出结构、依赖数据、调用边界和计算职责。',
  ].filter(Boolean).join('\n')
}

const buildSkillGenerationDescription = (target: string | AgentWorkshopToolingPlanItem) => {
  const concreteTool = findConcreteToolDraft(target)
  if (concreteTool) {
    return buildToolDraftSkillDescription(concreteTool)
  }

  const skillName = (typeof target === 'string' ? target : (target.tool_name || target.tool_id || '')).trim()
  const spec = displaySpec.value

  // Build keyword set from skill name for filtering relevant spec lines
  const skillKeywords = new Set<string>()
  for (const token of collectKeywordTokens(skillName)) {
    skillKeywords.add(token)
  }
  // Also add human-readable alias tokens
  const humanized = humanizeToolId(skillName)
  for (const token of collectKeywordTokens(humanized)) {
    skillKeywords.add(token)
  }
  const keywords = Array.from(skillKeywords)

  const filterLines = (lines: string[], fallbackCount = 2) => {
    if (!lines.length || !keywords.length) return lines.slice(0, fallbackCount)
    const matched = lines.filter(line =>
      keywords.some(kw => line.toLowerCase().includes(kw.toLowerCase())),
    )
    return matched.length ? matched : lines.slice(0, fallbackCount)
  }

  const responsibilityLines = filterLines(spec?.responsibilities || [], 2).map(item => `- ${item}`)
  const nonGoalLines = filterLines(spec?.non_goals || [], 2).map(item => `- ${item}`)

  // Prefer structured description from gap report, fallback to heuristic
  const suggestedItem = (gapReport.value?.suggested_tools || []).find(t => t.tool_id === skillName)
  const toolDescription = suggestedItem?.description || getSuggestedToolDescription(skillName)
  const whyNeeded = suggestedItem?.why_needed || ''

  return [
    `我要补齐一个 Agent 可直接调用的执行能力：${skillName}。`,
    toolDescription ? `功能说明：${toolDescription}` : '',
    whyNeeded ? `缺口原因：${whyNeeded}` : '',
    spec?.name ? `它服务于 Agent：${spec.name}。` : '',
    spec?.primary_goal ? `Agent 目标：${spec.primary_goal}` : '',
    responsibilityLines.length ? `与该能力相关的 Agent 职责：\n${responsibilityLines.join('\n')}` : '',
    nonGoalLines.length ? `边界约束：\n${nonGoalLines.join('\n')}` : '',
    '请把它澄清成一个最小实现单元，收敛职责边界，不要泛化。',
  ].filter(Boolean).join('\n')
}

const goToSkillWorkshop = (target?: string | AgentWorkshopToolingPlanItem) => {
  const description = target ? buildSkillGenerationDescription(target) : ''
  if (!description) {
    router.push('/workflow/skill-generation/create')
    return
  }

  router.push({
    path: '/workflow/skill-generation/create',
    query: {
      description,
      from_agent_workshop: selectedSpecId.value || '',
      source_name: selectedSpecName.value || '',
      skill_name: typeof target === 'string' ? target : (target?.tool_id || target?.tool_name || ''),
      target_capability: typeof target === 'string' ? target : (target?.tool_id || target?.tool_name || ''),
      handoff_intent: '当前是从 Agent 创建流程里补能力缺口，不是普通 Skill 脑暴。必须优先保留上游目标能力；若需要拆成 Skill，只能定义成该 Agent 能力里的最小确定性子能力。',
    }
  })
}

void [
  nanobotDiscussionLeadMessage,
  nanobotDiscussionLatestAssistantMessage,
  nanobotDiscussionRecentMessages,
  resolvedSuggestedTools,
  pendingVersionCapabilities,
  resolvedVersionCapabilities,
  activeStepLabel,
  reusableCapabilityCount,
  missingCapabilityCount,
  handleAnalyzeGaps,
  handleGenerateToolingPlan,
  goToSkillWorkshop,
]

watch(
  () => `${route.query.sessionId || ''}|${route.query.specId || ''}`,
  async (value, previousValue) => {
    if (value === previousValue) return
    debugAgentWorkshopState('watch-route-session-or-spec', { value, previousValue })
    await initFromRoute()
  }
)

watch(
  () => String(route.query.nanobotSessionKey || ''),
  async (value, previousValue) => {
    if (!value || value === previousValue) return
    if (value === currentNanobotSessionKey.value) return
    if (hasNanobotDiscussionContext.value || currentSession.value) return
    debugAgentWorkshopState('watch-route-nanobot-session-key', { value, previousValue })
    await initFromRoute()
  }
)

watch(
  () => ({
    activeStep: activeStep.value,
    sessionMode: currentSessionMode.value,
    currentSessionId: currentSession.value?.session_id || '',
    currentSessionSpecId: currentSession.value?.current_spec_snapshot?.spec_id || '',
    currentSessionSpecUpdatedAt: currentSession.value?.current_spec_snapshot?.updated_at || '',
    previewSpecId: previewResult.value?.spec?.spec_id || '',
    previewSpecUpdatedAt: previewResult.value?.spec?.updated_at || '',
    latestVersionId: latestVersion.value?.version_id || '',
    latestVersionSpecId: latestVersion.value?.spec_id || '',
    nanobotSessionKey: currentNanobotSessionKey.value || '',
  }),
  (value) => {
    debugAgentWorkshopState('watch-state-snapshot', value)
  }
)

watch(
  () => specPendingQuestions.value.join('|'),
  (value) => {
    if (!value || specFeedbackMessage.value.trim()) return
    specFeedbackMessage.value = buildDefaultSpecConfirmationMessage()
  },
  { immediate: true }
)

watch(
  () => evaluationForm.value.llm.model,
  () => {
    syncEvaluationModelConfig()
  }
)

onMounted(async () => {
  await loadAvailableModels()
  await initFromRoute()
})

onUnmounted(() => {
  if (activeNanobotStreamController) {
    activeNanobotStreamController.abort()
    activeNanobotStreamController = null
  }
})
</script>

<style scoped lang="scss">
.agent-workshop-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background:
    radial-gradient(circle at top left, rgba(17, 139, 122, 0.08), transparent 30%),
    linear-gradient(180deg, #f7fbfa 0%, #ffffff 100%);
  min-height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;

  .page-title-block {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .back-row {
    display: flex;
    align-items: center;
  }

  h1 {
    margin: 0;
    font-size: 28px;
    color: #0f3d36;
  }

  p {
    margin: 8px 0 0;
    color: #55726b;
  }
}

.workspace-shell {
  display: grid;
  gap: 20px;
  align-items: start;
}

.workspace-shell.single-pane {
  grid-template-columns: minmax(0, 1fr);
}

.flow-stage {
  min-width: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

.action-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-start;

  &.between {
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  &.right {
    justify-content: flex-end;
  }
}

.default-tool-list {
  display: grid;
  gap: 12px;
}

.default-tool-card {
  padding: 14px 16px;
  border: 1px solid #dce8e3;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.default-tool-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.default-tool-name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
}

.default-tool-name {
  font-size: 15px;
  font-weight: 700;
  color: #123f39;
}

.default-tool-id {
  font-size: 12px;
  color: #6b7f79;
}

.default-tool-description {
  margin-top: 8px;
  line-height: 1.7;
  color: #4f6761;
}

.examples {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.examples-title,
.field-label,
.bubble-role {
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #6b7f79;
}

.focus-card-inner,
.session-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.focus-card-inner {
  gap: 24px;
}

.focus-label,
.hint-text {
  font-size: 12px;
  color: #6b7f79;
}

.focus-title {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 700;
  color: #123f39;
}

.focus-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.focus-subtitle {
  margin-top: 8px;
  max-width: 680px;
  line-height: 1.7;
  color: #58706a;
}

.focus-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 12px;
  flex: 1;
}

.metric-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f6fbf9 0%, #eef6f3 100%);
  display: flex;
  flex-direction: column;
  gap: 8px;

  span {
    font-size: 12px;
    color: #6b7f79;
  }

  strong {
    font-size: 18px;
    color: #123f39;
  }
}

.flow-switcher {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.flow-switch {
  border: 0;
  border-radius: 18px;
  padding: 16px;
  background: #f4f8f7;
  color: #33514b;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    background: #eaf4f1;
  }

  &.active {
    background: linear-gradient(135deg, #0f8a7d, #145d55);
    color: #fff;
    box-shadow: 0 14px 28px rgba(15, 138, 125, 0.16);

    small,
    .flow-switch-index {
      color: rgba(255, 255, 255, 0.76);
    }
  }
}

.flow-switch-index {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: #6b7f79;
}

.flow-switch-text {
  display: flex;
  flex-direction: column;
  gap: 6px;

  strong {
    font-size: 15px;
    font-weight: 700;
  }

  small {
    font-size: 12px;
    line-height: 1.5;
    color: #6b7f79;
  }
}

.status-alert {
  margin-top: 16px;
}

.session-meta,
.session-toolbar-actions,
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.spec-confirm-block {
  padding: 16px;
  border: 1px solid #dbe7e2;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.discussion-summary-block {
  padding: 16px;
  border: 1px solid #dbe7e2;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.discussion-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.discussion-summary-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(15, 61, 54, 0.08);
}

.discussion-summary-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #0f5a4e;
}

.discussion-timeline {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.discussion-timeline-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(15, 61, 54, 0.04);
}

.discussion-timeline-role {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #0f5a4e;
}

.discussion-timeline-content {
  line-height: 1.65;
  color: #35524c;
}

.nanobot-stream-panel {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 90, 78, 0.12);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(245, 251, 248, 0.96) 0%, rgba(239, 248, 244, 0.92) 100%);
}

.discuss-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 16px;
  align-items: start;
}

.discuss-pane {
  min-width: 0;
}

.discuss-main-pane,
.discuss-progress-pane {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #dbe7e2;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.discuss-main-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 640px;
}

.discuss-progress-pane {
  min-height: 640px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compose-panel-header,
.progress-sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.compose-panel-title,
.progress-sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f5a4e;
}

.compose-panel-hint,
.progress-sidebar-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #5a726c;
}

.composer-embedded {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
}

.composer-embedded :deep(.el-textarea__inner) {
  min-height: 140px;
}

.sidebar-mode {
  margin-bottom: 0;
  height: 100%;
}

.sidebar-hint {
  margin-top: 0;
}

.compact-list {
  margin-top: 10px;
}

.sidebar-event {
  align-items: flex-start;
}

.sidebar-event strong,
.sidebar-event span {
  word-break: break-word;
}

.progress-placeholder {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px dashed rgba(15, 90, 78, 0.18);
}

.progress-placeholder-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f5a4e;
}

.progress-placeholder-text {
  font-size: 12px;
  line-height: 1.7;
  color: #5a726c;
}

.nanobot-stream-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.nanobot-stream-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f5a4e;
}

.nanobot-stream-hint {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #35524c;
}

.nanobot-tool-event-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.nanobot-tool-event {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  color: #35524c;
}

.nanobot-tool-event.info {
  border: 1px solid rgba(15, 90, 78, 0.1);
}

.nanobot-tool-event.success {
  border: 1px solid rgba(29, 122, 74, 0.16);
}

.nanobot-tool-event.warning {
  border: 1px solid rgba(196, 98, 49, 0.18);
}

.nanobot-tool-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 90, 78, 0.08);
  font-size: 12px;
  font-weight: 700;
  color: #0f5a4e;
}

.gap-stage-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.gap-stage-card {
  padding: 14px 16px;
  border: 1px solid #dbe7e2;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfefd 0%, #f4faf7 100%);
}

.gap-stage-kicker {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b7f79;
}

.gap-stage-title {
  margin-top: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #123f39;
}

.gap-stage-text {
  margin-top: 8px;
  line-height: 1.7;
  color: #55726b;
}

.gap-stage-metric {
  margin-top: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #0f5a4e;
}
.confirm-question-list {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
}
.confirm-question-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(18, 63, 57, 0.04);
  color: #35524c;
  line-height: 1.7;
}
.confirm-question-index {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #dbeee8;
  color: #0f5a4e;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  margin-top: 2px;
}

.step-layout {
  margin-top: 16px;
  display: grid;
  gap: 16px;
}

.step-layout.two-columns {
  grid-template-columns: 1.1fr 0.9fr;
}

.step-layout.single-column {
  grid-template-columns: minmax(0, 1fr);
}

.step-card {
  min-width: 0;
}

.inline-create-card {
  width: min(760px, 100%);
}

.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  max-height: 560px;
  overflow: auto;
  padding-right: 6px;
}

.chat-row {
  display: flex;

  &.assistant {
    justify-content: flex-start;
  }

  &.user {
    justify-content: flex-end;

    .bubble {
      background: linear-gradient(135deg, #0f8a7d, #145d55);
      color: #fff;
    }

    .bubble-role {
      color: rgba(255, 255, 255, 0.75);
    }
  }
}

.bubble {
  max-width: 88%;
  padding: 14px 16px;
  border-radius: 18px;
  background: #f3f8f6;
  box-shadow: inset 0 0 0 1px rgba(15, 61, 54, 0.05);
}

.bubble-content {
  white-space: normal;
  line-height: 1.65;
  color: inherit;
}

.bubble-content:deep(p),
.bubble-content:deep(ul),
.bubble-content:deep(ol),
.bubble-content:deep(table),
.bubble-content:deep(blockquote),
.bubble-content:deep(pre) {
  margin: 0 0 12px;
}

.bubble-content:deep(*:last-child) {
  margin-bottom: 0;
}

.bubble-content:deep(h1),
.bubble-content:deep(h2),
.bubble-content:deep(h3),
.bubble-content:deep(h4) {
  margin: 0 0 10px;
  line-height: 1.4;
  color: inherit;
}

.bubble-content:deep(ul),
.bubble-content:deep(ol) {
  padding-left: 20px;
}

.bubble-content:deep(li) {
  margin-bottom: 6px;
}

.bubble-content:deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 61, 54, 0.08);
  font-size: 12px;
}

.chat-row.user .bubble-content:deep(code) {
  background: rgba(255, 255, 255, 0.16);
}

.bubble-content:deep(pre) {
  overflow: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(15, 61, 54, 0.08);
}

.chat-row.user .bubble-content:deep(pre) {
  background: rgba(255, 255, 255, 0.12);
}

.bubble-content:deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.bubble-content:deep(th),
.bubble-content:deep(td) {
  padding: 8px 10px;
  border: 1px solid rgba(15, 61, 54, 0.12);
  text-align: left;
  vertical-align: top;
}

.bubble-content:deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid rgba(15, 61, 54, 0.2);
  color: inherit;
  opacity: 0.88;
}

.composer {
  margin-top: 16px;
}

.tag-wrap {
  display: flex;
  flex-wrap: wrap;
}

.spec-panel,
.gap-panel,
.version-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.version-meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.project-memory-summary-grid,
.project-memory-history-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.score-desc {
  margin-top: 8px;
  min-height: 36px;
  color: #6f817c;
  font-size: 12px;
  line-height: 1.5;
}

.project-memory-summary-card,
.history-card {
  background: linear-gradient(180deg, #fbfefd 0%, #f3faf7 100%);
}

.project-memory-summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 10px 0 12px;
  color: #47655e;
  font-size: 13px;
}

.project-memory-summary-meta.subtle {
  color: #6b7f79;
  margin-top: 12px;
  margin-bottom: 0;
}

.history-card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.evaluation-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}


.runtime-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
  color: #5d746e;
  font-size: 13px;
}

.runtime-raw-response {
  margin: 0;
  padding: 16px;
  border-radius: 14px;
  background: #0f1720;
  border: 1px solid #243341;
  color: #d8e4ec;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  max-height: 280px;
  overflow: auto;
}

.error-note {
  color: #b42318;
}

.runtime-report-box {
  padding: 16px;
  border-radius: 14px;
  background: #f8fbfa;
  border: 1px solid #e4efeb;
  color: #1e3733;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-result-box {
  padding: 16px;
  border-radius: 14px;
  background: #0f1720;
  border: 1px solid #243341;
  color: #d8e4ec;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  max-height: 320px;
  overflow: auto;
}

.evaluation-note-block .note-item {
  line-height: 1.7;
}

.warning-note {
  color: #9a3412;
}

.breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.breakdown-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fbfa;
  border: 1px solid #e4efeb;
}

.evidence-card {
  background: #fffaf2;
  border-color: #f4d9a6;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 700;
  color: #143f39;
}

.breakdown-group + .breakdown-group {
  margin-top: 12px;
}

.breakdown-label {
  margin-bottom: 8px;
  font-size: 12px;
  color: #6b7f79;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.breakdown-label.success {
  color: #1d7b52;
}

.breakdown-label.warning {
  color: #b26a12;
}

.compact-note {
  padding: 10px 12px;
}

.worker-meta-row {
  margin: 8px 0 10px;
}

.worker-artifact-list {
  display: grid;
  gap: 10px;
}

.worker-artifact-group-list {
  display: grid;
  gap: 12px;
}

.worker-artifact-group {
  display: grid;
  gap: 8px;
}

.worker-artifact-group-title {
  font-size: 12px;
  font-weight: 700;
  color: #1d7b52;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.worker-artifact-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #d9e7e2;
}

.worker-artifact-title {
  font-size: 13px;
  font-weight: 700;
  color: #143f39;
}

.worker-artifact-path {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7f79;
  word-break: break-all;
}

.worker-artifact-content {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #35524c;
  white-space: pre-wrap;
  word-break: break-word;
}

.worker-artifact-tags {
  margin-top: 8px;
}

.score-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f1f7f5;
}

.score-key {
  font-size: 12px;
  color: #6b7f79;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.score-value {
  font-size: 22px;
  font-weight: 700;
  color: #123f39;
}

.spec-title {
  font-size: 20px;
  font-weight: 700;
  color: #123f39;
}

.spec-goal {
  line-height: 1.7;
  color: #415d57;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tag-item {
  margin-right: 8px;
  margin-bottom: 8px;
}

.empty-stage-steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.pending-item,
.note-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f6f7f2;
  color: #4e5b57;
  line-height: 1.6;
}

.actionable-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.descriptive-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.descriptive-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 240px;
}

.descriptive-title {
  font-weight: 600;
  color: #1f2937;
}

.descriptive-text {
  color: #6b7280;
  line-height: 1.6;
  font-size: 13px;
}

.inline-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.breakdown-actions {
  margin: 10px 0 12px;
}

.empty-stage-card {
  border-radius: 18px;
  background: #fff;
  border: 1px dashed rgba(15, 61, 54, 0.14);
}

.empty-stage-card {
  min-height: 460px;
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  background:
    radial-gradient(circle at top left, rgba(15, 138, 125, 0.08), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f7fbfa 100%);
}

.empty-stage-card.with-create-card {
  align-items: flex-start;
}

.empty-stage-title {
  font-size: 28px;
  font-weight: 700;
  color: #123f39;
}

.empty-stage-text {
  max-width: 640px;
  line-height: 1.75;
  color: #5a726c;
}

.empty-stage-steps {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.empty-step {
  padding: 12px 16px;
  border-radius: 999px;
  background: #eff7f4;
  color: #35524c;
  font-weight: 600;
}

.empty-state {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #7c8c87;
  background: repeating-linear-gradient(
    -45deg,
    rgba(15, 138, 125, 0.04),
    rgba(15, 138, 125, 0.04) 10px,
    rgba(15, 138, 125, 0.02) 10px,
    rgba(15, 138, 125, 0.02) 20px
  );
  border-radius: 14px;
}

.empty-state.compact {
  min-height: 220px;
}

/* 缺口分析面板 */
.gap-section {
  margin-bottom: 16px;
}
.gap-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
}
.gap-list {
  margin: 0;
  padding-left: 20px;
}
.gap-list li {
  margin-bottom: 4px;
  font-size: 13px;
  line-height: 1.5;
}
.gap-list.danger li {
  color: #f56c6c;
}
.gap-tool-chips {
  line-height: 2;
}

@media (max-width: 1100px) {
  .workspace-shell,
  .step-layout.two-columns,
  .flow-switcher,
  .focus-metrics,
  .score-grid {
    grid-template-columns: 1fr;
  }

  .discuss-workbench {
    grid-template-columns: 1fr;
  }

  .discuss-main-pane,
  .discuss-progress-pane {
    min-height: auto;
  }

  .breakdown-grid {
    grid-template-columns: 1fr;
  }

  .focus-card-inner {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 760px) {
  .agent-workshop-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .header-actions,
  .action-row.between {
    flex-wrap: wrap;
  }

  .flow-switch {
    padding: 14px;
  }
}
</style>