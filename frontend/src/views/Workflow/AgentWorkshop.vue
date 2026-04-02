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
        <p>这里专门做需求讨论、版本生成和评估迭代。Agent 列表和草稿管理放在单独的管理页。</p>
      </div>
      <div class="header-actions">
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
          <div class="empty-stage-text">这个页面现在只负责当前 Agent 的讨论、生成和评估。已有草稿和历史 Agent 请回管理页查看。</div>
          <div class="empty-stage-steps">
            <div class="empty-step">1. 聊需求</div>
            <div class="empty-step">2. 看规格</div>
            <div class="empty-step">3. 生成版本</div>
            <div class="empty-step">4. 评估迭代</div>
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
                  <strong>{{ currentSession?.stage || activeStepLabel }}</strong>
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
                    <el-button size="small" @click="refreshSession" :loading="loadingCurrentSession">刷新会话</el-button>
                    <el-button size="small" type="success" @click="handlePreviewSpec" :loading="previewing" :disabled="!currentSession">进入规格确认</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!currentSession" class="empty-state compact">当前没有进行中的会话。</div>
              <template v-else>
                <div class="chat-panel">
                  <div v-for="(message, index) in currentSession.messages" :key="index" :class="['chat-row', message.role]">
                    <div class="bubble">
                      <div class="bubble-role">{{ message.role === 'assistant' ? '工坊助手' : '你' }}</div>
                      <div class="bubble-content">{{ message.content }}</div>
                    </div>
                  </div>
                </div>

                <div class="composer">
                  <el-input
                    v-model="replyMessage"
                    type="textarea"
                    :rows="3"
                    resize="none"
                    placeholder="直接补充你想要的效果，或者告诉我哪里理解错了。"
                    @keydown.enter.ctrl.prevent="handleRespond"
                  />
                  <div class="action-row between">
                    <div class="hint-text">按 Ctrl + Enter 也可以发送</div>
                    <div class="session-toolbar-actions">
                      <el-button type="primary" :disabled="!replyMessage.trim()" :loading="responding" @click="handleRespond">
                        继续讨论
                      </el-button>
                      <el-button type="success" plain :disabled="!currentSession || responding" :loading="previewing" @click="handlePreviewSpec">
                        下一步
                      </el-button>
                    </div>
                  </div>
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
                    <el-button size="small" type="primary" @click="goToGapStep" :disabled="!displaySpec">进入能力检查</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!displaySpec" class="empty-state compact">先完成一轮需求讨论，再生成规格快照。</div>
              <div v-else class="spec-panel">
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
                <div class="field-block spec-confirm-block" v-if="currentSession">
                  <div class="field-label">最后确认一下</div>
                  <div class="note-item">
                    这里不用把需求重新说一遍。现在只要做两件事：
                    如果当前草案没问题，直接继续；如果有不对的地方，补一句你想改什么。
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
                      <el-button type="success" plain :loading="confirmingSpec" @click="handleAcceptRecommendedSpec">按当前方案继续</el-button>
                      <el-button type="primary" :disabled="!specFeedbackMessage.trim()" :loading="confirmingSpec" @click="handleSubmitSpecFeedback">提交修改并刷新</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">进入下一步前</div>
                  <div class="note-item">
                    这一步只确认“这个 Agent 要做什么、产出什么”。下一步才会检查现有能力够不够、还缺什么工具。
                  </div>
                </div>
              </div>
            </el-card>

          </div>

          <div v-else-if="activeStep === 'gap'" class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>工具缺口与能力检查</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" @click="activeStep = 'spec'">返回规格确认</el-button>
                    <el-button size="small" type="warning" @click="handleAnalyzeGaps" :loading="analyzing" :disabled="!canAdvance">{{ gapReport ? '重新发现缺口' : '做缺口分析' }}</el-button>
                    <el-button size="small" type="warning" plain @click="handleGenerateToolingPlan" :loading="generatingToolPlan" :disabled="!currentSession">生成工具需求草案</el-button>
                    <el-button size="small" type="primary" @click="handleBuildVersion" :loading="buildingVersion" :disabled="!canAdvance">生成版本草案</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!gapReport" class="empty-state compact">规格确认后，在这里看可复用能力和还缺什么。</div>
              <div v-else class="gap-panel">
                <div class="runtime-meta-row">
                  <span v-if="gapReport.generated_by === 'llm'">生成方式：LLM 缺口分析</span>
                  <span v-else-if="gapReport.generated_by === 'llm_failed'">生成方式：LLM 失败，未做兜底</span>
                </div>
                <div class="gap-stage-summary">
                  <div class="gap-stage-card">
                    <div class="gap-stage-kicker">第一步</div>
                    <div class="gap-stage-title">先看现有可复用能力</div>
                    <div class="gap-stage-text">先确认系统已经有什么，避免把可复用能力误判成新缺口。</div>
                    <div class="gap-stage-metric">当前识别 {{ reusableCapabilityCount }} 项可复用能力</div>
                  </div>
                  <div class="gap-stage-card">
                    <div class="gap-stage-kicker">第二步</div>
                    <div class="gap-stage-title">再看真正缺什么</div>
                    <div class="gap-stage-text">只把现有能力覆盖不了的最小能力单元算作缺口，不做大而全联想。</div>
                    <div class="gap-stage-metric">当前识别 {{ missingCapabilityCount }} 项待补缺口/待实现项</div>
                  </div>
                  <div class="gap-stage-card">
                    <div class="gap-stage-kicker">第三步</div>
                    <div class="gap-stage-title">最后落成工具草案</div>
                    <div class="gap-stage-text">把真正缺的能力继续收敛成工具需求草案，再决定是否进入版本组装。</div>
                    <div class="gap-stage-metric">{{ toolingPlan ? '已生成工具草案' : '尚未生成工具草案' }}</div>
                  </div>
                </div>
                <div v-if="gapReport.error_message" class="field-block">
                  <div class="field-label">缺口分析失败原因</div>
                  <div class="note-item error-note">{{ gapReport.error_message }}</div>
                </div>
                <div v-if="gapReport.raw_response" class="field-block">
                  <div class="field-label">LLM 原始响应摘要</div>
                  <pre class="runtime-raw-response">{{ gapReport.raw_response }}</pre>
                </div>
                <div class="field-block">
                  <div class="field-label">第一步：现有可复用能力</div>
                  <div class="note-item">这一段只回答“现在已经能直接用什么”。如果这里已经能覆盖，就不应该再进入新增能力实现。</div>
                </div>
                <div class="field-block" v-if="gapReport.existing_tools.length">
                  <div class="field-label">已发现工具</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in gapReport.existing_tools" :key="item" class="tag-item" type="info">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">第二步：真正缺口</div>
                  <div class="note-item">这一段只回答“现有能力为什么还不够”。只有这里识别出来的项，才值得进入能力工坊或工具实现。</div>
                </div>
                <div class="field-block" v-if="gapReport.suggested_tools.length || gapReport.suggested_capabilities.length">
                  <div class="field-label">怎么理解这些缺口</div>
                  <div class="note-item">
                    这里展示的是 Agent 还缺的执行能力，不等于它们天然就是一个独立 Skill。<br>
                    当前点“去能力工坊”时，会把上游 Agent 的目标和缺口上下文一并带过去；但真正要补的，仍然是那些输入输出明确、能被 Agent 直接调用的最小能力单元。是否最终落成新的 Skill，要看现有工具能不能复用、是否真的缺实现。
                  </div>
                </div>
                <div class="field-block" v-if="pendingSuggestedTools.length">
                  <div class="field-label">建议优先补齐的执行能力</div>
                  <div v-for="item in pendingSuggestedTools" :key="item.tool_id" class="pending-item descriptive-item">
                    <div class="descriptive-title">{{ item.tool_id }}</div>
                    <div class="descriptive-text">{{ item.description || getSuggestedToolDescription(item.tool_id) }}</div>
                    <div v-if="item.why_needed" class="descriptive-text" style="color: var(--el-text-color-secondary); font-size: 12px;">缺口原因：{{ item.why_needed }}</div>
                    <div class="inline-actions breakdown-actions">
                      <el-button size="small" @click="goToSkillWorkshop(item.tool_id)">去能力工坊</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="resolvedSuggestedTools.length">
                  <div class="field-label">已在能力工坊生成的能力</div>
                  <div class="note-item">这些能力已经在当前系统能力快照里可见，当前缺口展示可能还是旧结果。建议重新发现缺口，刷新这一步的判断。</div>
                  <div class="action-row" style="margin-bottom: 12px;">
                    <el-button size="small" type="warning" plain @click="handleAnalyzeGaps" :loading="analyzing" :disabled="!currentSession">重新发现缺口</el-button>
                  </div>
                  <div v-for="item in resolvedSuggestedTools" :key="`resolved-${item.tool_id}`" class="pending-item descriptive-item">
                    <div class="descriptive-title">
                      {{ item.tool_id }}
                      <el-tag size="small" type="success" effect="plain" style="margin-left: 8px;">已在能力工坊生成</el-tag>
                    </div>
                    <div class="descriptive-text">{{ item.description || getSuggestedToolDescription(item.tool_id) }}</div>
                    <div v-if="item.why_needed" class="descriptive-text" style="color: var(--el-text-color-secondary); font-size: 12px;">原缺口原因：{{ item.why_needed }}</div>
                    <div class="inline-actions breakdown-actions">
                      <el-button size="small" @click="goToSkillWorkshop(item.tool_id)">去能力工坊</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="gapReport.blocking_gaps.length">
                  <div class="field-label">当前阻塞缺口</div>
                  <div v-for="item in gapReport.blocking_gaps" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="gapReport.fallback_strategy.length">
                  <div class="field-label">缺工具时怎么处理</div>
                  <div v-for="item in gapReport.fallback_strategy" :key="item" class="note-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="gapReport.build_recommendations.length">
                  <div class="field-label">下一步建议</div>
                  <div v-for="item in gapReport.build_recommendations" :key="item" class="note-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="gapReport.manual_dependencies.length">
                  <div class="field-label">需要人工补的依赖</div>
                  <div v-for="item in gapReport.manual_dependencies" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="gapReport.notes.length">
                  <div class="field-label">备注</div>
                  <div v-for="item in gapReport.notes" :key="item" class="note-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="toolingPlan">
                  <div class="field-label">第三步：工具需求草案</div>
                  <div class="note-item" v-if="toolingPlan.summary">{{ toolingPlan.summary }}</div>
                  <div class="runtime-meta-row">
                    <span v-if="toolingPlan.generated_by === 'llm'">生成方式：LLM 草案</span>
                    <span v-else-if="toolingPlan.generated_by === 'llm_failed'">生成方式：LLM 失败，未做兜底</span>
                  </div>
                  <div class="field-block" v-if="toolingPlan.error_message">
                    <div class="field-label">工具草案失败原因</div>
                    <div class="note-item error-note">{{ toolingPlan.error_message }}</div>
                  </div>
                  <div class="field-block" v-if="toolingPlan.raw_response">
                    <div class="field-label">LLM 原始响应摘要</div>
                    <pre class="runtime-raw-response">{{ toolingPlan.raw_response }}</pre>
                  </div>
                  <div class="field-block" v-if="toolingPlan.missing_capabilities?.length">
                    <div class="field-label">待补能力</div>
                    <div v-for="item in toolingPlan.missing_capabilities" :key="item" class="pending-item">{{ item }}</div>
                  </div>
                  <div class="field-block" v-if="toolingPlan.implementation_order?.length">
                    <div class="field-label">建议实现顺序</div>
                    <div v-for="item in toolingPlan.implementation_order" :key="item" class="note-item">{{ item }}</div>
                  </div>
                  <div class="breakdown-grid" v-if="toolingPlan.draft_tools?.length">
                    <div v-for="item in toolingPlan.draft_tools" :key="item.tool_id" class="breakdown-card">
                      <div class="breakdown-title">{{ item.tool_name }}</div>
                      <div class="runtime-meta-row">
                        <span>工具 ID：{{ item.tool_id }}</span>
                        <span>优先级：{{ item.priority }}</span>
                        <span v-if="isCapabilityAlreadyGenerated(item)">已在能力工坊生成</span>
                      </div>
                      <div class="inline-actions breakdown-actions">
                        <el-button size="small" @click="goToSkillWorkshop(item)">去能力工坊</el-button>
                      </div>
                      <div class="note-item compact-note">{{ item.why_needed }}</div>
                      <div class="breakdown-group" v-if="item.solves_gaps?.length">
                        <div class="breakdown-label warning">解决缺口</div>
                        <div v-for="entry in item.solves_gaps" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                      <div class="breakdown-group" v-if="item.inputs?.length">
                        <div class="breakdown-label">输入草案</div>
                        <div v-for="field in item.inputs" :key="`${item.tool_id}-in-${field.name}`" class="note-item compact-note">
                          {{ field.name }} / {{ field.type }} / {{ field.required ? '必填' : '可选' }}{{ field.description ? ` / ${field.description}` : '' }}
                        </div>
                      </div>
                      <div class="breakdown-group" v-if="item.outputs?.length">
                        <div class="breakdown-label">输出草案</div>
                        <div v-for="field in item.outputs" :key="`${item.tool_id}-out-${field.name}`" class="note-item compact-note">
                          {{ field.name }} / {{ field.type }}{{ field.description ? ` / ${field.description}` : '' }}
                        </div>
                      </div>
                      <div class="breakdown-group" v-if="item.dependencies?.length">
                        <div class="breakdown-label">依赖</div>
                        <div class="tag-wrap">
                          <el-tag v-for="entry in item.dependencies" :key="entry" class="tag-item" effect="plain">{{ entry }}</el-tag>
                        </div>
                      </div>
                      <div class="breakdown-group" v-if="item.acceptance_criteria?.length">
                        <div class="breakdown-label success">验收标准</div>
                        <div v-for="entry in item.acceptance_criteria" :key="entry" class="note-item compact-note">{{ entry }}</div>
                      </div>
                      <div class="breakdown-group" v-if="item.fallback_before_ready">
                        <div class="breakdown-label">未就绪前如何降级</div>
                        <div class="note-item compact-note">{{ item.fallback_before_ready }}</div>
                      </div>
                    </div>
                  </div>
                  <div class="field-block" v-if="toolingPlan.notes?.length">
                    <div class="field-label">补充说明</div>
                    <div v-for="item in toolingPlan.notes" :key="item" class="note-item">{{ item }}</div>
                  </div>
                </div>
              </div>
            </el-card>

          </div>

          <div v-else-if="activeStep === 'version'" class="step-layout single-column">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>版本草案</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" @click="activeStep = 'gap'">返回能力检查</el-button>
                    <el-button size="small" type="primary" @click="handleBuildVersion" :loading="buildingVersion" :disabled="!canAdvance">重新生成</el-button>
                    <el-button size="small" type="success" plain @click="openEvaluateDialog" :disabled="!latestVersion">调试运行与评估</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!latestVersion" class="empty-state compact">先完成规格确认和缺口分析，再生成第一版版本草案。</div>
              <div v-else class="version-panel">
                <div class="spec-title">{{ latestVersion.agent_metadata?.name || latestVersion.version_id }}</div>
                <div class="version-meta-row">
                  <el-tag effect="plain">{{ latestVersion.version_id }}</el-tag>
                  <el-tag type="warning" effect="plain">{{ latestVersion.status }}</el-tag>
                  <el-tag type="success" effect="plain">v{{ latestVersion.version }}</el-tag>
                  <el-tag v-if="workshopMaintenanceStatus === 'unmaintained'" type="danger" effect="plain">停止维护</el-tag>
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
                <div class="field-block" v-if="pendingVersionCapabilities.length">
                  <div class="field-label">待补执行能力</div>
                  <div class="note-item">这些是版本草案里已经识别出来、需要显式挂接的执行能力，不表示它们一定都要新建成独立 Skill；也可能是复用已有工具、补一个最小实现单元，或做成新的可注册能力。</div>
                  <div v-for="item in pendingVersionCapabilities" :key="item" class="pending-item descriptive-item">
                    <div class="descriptive-title">
                      {{ item }}
                    </div>
                    <div class="descriptive-text">版本草案已经把这项能力识别为需要补齐或显式挂接的执行能力，不再只停留在抽象需求层；后续应先判断复用，再决定是否新增实现。</div>
                    <div class="inline-actions breakdown-actions">
                      <el-button size="small" @click="goToSkillWorkshop(item)">去能力工坊</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block" v-if="resolvedVersionCapabilities.length">
                  <div class="field-label">已补齐但当前版本尚未刷新</div>
                  <div class="note-item">这些能力已经在能力工坊中生成成功，但当前版本草案仍是旧快照。重新生成版本后，这里会自动收敛。</div>
                  <div v-for="item in resolvedVersionCapabilities" :key="`resolved-version-${item}`" class="pending-item descriptive-item">
                    <div class="descriptive-title">
                      {{ item }}
                      <el-tag size="small" type="success" effect="plain" style="margin-left: 8px;">已在能力工坊生成</el-tag>
                    </div>
                    <div class="inline-actions breakdown-actions">
                      <el-button size="small" @click="goToSkillWorkshop(item)">去能力工坊</el-button>
                    </div>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">Prompt 草案</div>
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
                  <div class="field-label">执行验证计划</div>
                  <div class="note-item" v-if="latestExecutionPlan.rationale">{{ latestExecutionPlan.rationale }}</div>
                  <div class="runtime-meta-row">
                    <span>模式：{{ latestExecutionPlan.mode || 'tool-driven' }}</span>
                    <span>状态：{{ latestExecutionPlan.validation_status || 'not-run' }}</span>
                  </div>
                  <div class="field-block" v-if="executionPlanSampleInputText" style="margin-top: 12px;">
                    <div class="field-label">默认调试输入</div>
                    <pre class="runtime-raw-response">{{ executionPlanSampleInputText }}</pre>
                  </div>
                  <div class="field-block" v-if="executionPlanStepCards.length" style="margin-top: 12px;">
                    <div class="field-label">执行步骤</div>
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
                  <div class="note-item">当前评分以 LLM 评审为主，重点判断结果是否真的完成任务、分析过程是否合理、工具选择是否合适、提示词设计是否清晰。规则扫描只作为辅助证据，不再直接代表最终评语。</div>
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
                <div class="field-block" v-if="latestEvaluation.issues?.length">
                  <div class="field-label">主要问题</div>
                  <div v-for="item in latestEvaluation.issues" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="latestEvaluation.recommendations?.length">
                  <div class="field-label">优化建议</div>
                  <div v-for="item in latestEvaluation.recommendations" :key="item" class="note-item">{{ item }}</div>
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import { toolsApi, type ToolMetadata } from '@/api/tools'
import agentWorkshopApi, {
  type AgentEvaluationReport,
  type AgentSpec,
  type AgentSpecIOItem,
  type AgentWorkshopCapabilitySnapshot,
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
} from '@/api/agentWorkshop'
import { configApi, type LLMConfig } from '@/api/config'

type FlowStep = 'discuss' | 'spec' | 'gap' | 'version' | 'evaluate'

const description = ref('')
const replyMessage = ref('')
const specFeedbackMessage = ref('')

const route = useRoute()
const router = useRouter()

const specs = ref<AgentSpec[]>([])
const currentSession = ref<AgentWorkshopSessionDetail | null>(null)
const previewResult = ref<AgentWorkshopPreviewResult | null>(null)
const gapReport = ref<AgentWorkshopGapAnalysis | null>(null)
const capabilitySnapshot = ref<AgentWorkshopCapabilitySnapshot | null>(null)
const latestVersion = ref<AgentVersion | null>(null)
const latestVersionPrompt = ref<AgentWorkshopVersionPrompt | null>(null)
const latestEvaluation = ref<AgentEvaluationReport | null>(null)
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
    output_text: '',
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
  { key: 'spec', index: '02', title: '看规格', description: '先确认职责、输出和待确认项' },
  { key: 'gap', index: '03', title: '查缺口', description: '单独检查能力缺口和可复用能力' },
  { key: 'version', index: '04', title: '生成版本', description: '确认工具方案后再组装版本结构' },
  { key: 'evaluate', index: '05', title: '评估迭代', description: '看结果，再决定下一轮怎么改' },
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

const displaySpec = computed(() => previewResult.value?.spec || currentSession.value?.current_spec_snapshot || null)
const displaySpecOutputTags = computed(() => (displaySpec.value?.outputs || []).map(item => getSpecIoText(item)).filter(Boolean))
const canAdvance = computed(() => currentSession.value?.feasibility_status === 'feasible' && (currentSession.value?.completeness_score || 0) >= 0.75)
const hasWorkspaceContext = computed(() => Boolean(currentSession.value || displaySpec.value || latestVersion.value || latestEvaluation.value))
const selectedSpecId = computed(() => displaySpec.value?.spec_id || currentSession.value?.current_spec_snapshot?.spec_id || latestVersion.value?.spec_id || '')
const selectedSpecName = computed(() => displaySpec.value?.name || latestVersion.value?.agent_metadata?.name || '未命名 Agent')
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
const llmReview = computed(() => {
  const review = latestEvaluation.value?.details?.llm_review
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
    acceptanceResults: Array.isArray(review.acceptance_results) ? review.acceptance_results.map(item => ({
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
const focusSubtitle = computed(() => {
  if (currentSession.value?.feasibility_status === 'not-feasible') {
    return currentSession.value.refusal_reason || '当前目标超出支持范围，建议先缩小问题。'
  }
  if (currentSession.value?.feasibility_status === 'need-clarification') {
    return '先把需求聊清楚，再往规格和版本阶段走。'
  }
  if (latestEvaluation.value) {
    return '当前已经有评估结果，可以继续发起下一轮迭代。'
  }
  if (latestVersion.value) {
    return '版本草案已经生成，下一步建议先做一次评估。'
  }
  if (gapReport.value || previewResult.value) {
    return '规格已经有轮廓了，确认没有问题后就可以生成版本。'
  }
  return '先在对话里把这个 Agent 讲明白。'
})
const statusText = computed(() => {
  const status = currentSession.value?.feasibility_status
  if (status === 'feasible') return '可继续'
  if (status === 'not-feasible') return '做不到'
  if (previewResult.value?.readiness === 'ready') return '可继续'
  return '待澄清'
})
const statusTagType = computed(() => {
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
    return
  }

  if (latestEvaluation.value) {
    activeStep.value = 'evaluate'
    return
  }

  if (latestVersion.value) {
    activeStep.value = 'version'
    return
  }

  if (latestVersion.value) {
    activeStep.value = 'version'
    return
  }

  if (gapReport.value || toolingPlan.value) {
    activeStep.value = 'gap'
    return
  }

  if (previewResult.value || displaySpec.value) {
    activeStep.value = 'spec'
    return
  }

  activeStep.value = 'discuss'
}

const goToGapStep = () => {
  activeStep.value = 'gap'
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
      output_text: '',
    },
  }
}

const clearWorkspace = () => {
  currentSession.value = null
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
}

const buildDefaultSpecConfirmationMessage = () => {
  if (specPendingQuestions.value.length) {
    return '整体方向没问题。上面这些待确认项如果我没有单独说明，就先按你推荐的方案继续。'
  }
  return '整体方向没问题，请按当前方案继续。'
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
    syncActiveStep()
    return
  }
  try {
    const result = await agentWorkshopApi.listVersions({ spec_id: specId, page: 1, page_size: 1 })
    latestVersion.value = result.items?.[0] || null
    if (latestVersion.value?.version_id) {
      await Promise.all([
        loadLatestEvaluation(latestVersion.value.version_id),
        loadLatestVersionPrompt(latestVersion.value.version_id),
      ])
    } else {
      latestVersionPrompt.value = null
    }
  } catch {
    latestVersion.value = null
    latestVersionPrompt.value = null
    latestEvaluation.value = null
  } finally {
    syncActiveStep()
  }
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
    syncActiveStep()
    return
  }
  try {
    const result = await agentWorkshopApi.listEvaluations(versionId, { page: 1, page_size: 1 })
    latestEvaluation.value = result.items?.[0] || null
  } catch {
    latestEvaluation.value = null
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

  clearWorkspace()

  if (sessionId) {
    loadingSessionList.value = true
    try {
      currentSession.value = await agentWorkshopApi.getSession(sessionId)
      gapReport.value = currentSession.value.gap_report || null
      await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
      syncActiveStep(currentSession.value.gap_report ? 'gap' : 'discuss')
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
      } catch (error: any) {
        ElMessage.error(error?.message || '加载 Agent 规格失败')
      }
    }
  }
}

const refreshSession = async () => {
  if (!currentSession.value?.session_id) return
  loadingCurrentSession.value = true
  try {
    const [session] = await Promise.all([
      agentWorkshopApi.getSession(currentSession.value.session_id),
      loadCapabilitySnapshot(),
    ])
    currentSession.value = session
    gapReport.value = currentSession.value.gap_report || null
    await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
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
    const result = await agentWorkshopApi.startSession({ description: description.value.trim() })
    currentSession.value = await agentWorkshopApi.getSession(result.session_id)
    previewResult.value = null
    gapReport.value = null
    latestVersion.value = null
    latestEvaluation.value = null
    await loadSpecs()
    router.replace({ path: '/workflow/agent-workshop/create', query: { sessionId: result.session_id } })
    syncActiveStep('discuss')
    ElMessage.success('工坊会话已创建')
  } catch (error: any) {
    ElMessage.error(error?.message || '创建会话失败')
  } finally {
    starting.value = false
  }
}

const handleRespond = async () => {
  if (!currentSession.value?.session_id || !replyMessage.value.trim()) return
  responding.value = true
  try {
    await agentWorkshopApi.respondToSession(currentSession.value.session_id, replyMessage.value.trim())
    replyMessage.value = ''
    await refreshSession()
    await loadSpecs()
    syncActiveStep('discuss')
  } catch (error: any) {
    ElMessage.error(error?.message || '回复失败')
  } finally {
    responding.value = false
  }
}

const handlePreviewSpec = async () => {
  if (!currentSession.value?.session_id) return
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
  if (!currentSession.value?.session_id) return
  confirmingSpec.value = true
  try {
    await agentWorkshopApi.respondToSession(currentSession.value.session_id, message)
    currentSession.value = await agentWorkshopApi.getSession(currentSession.value.session_id)
    previewResult.value = await agentWorkshopApi.previewSpec(currentSession.value.session_id)
    gapReport.value = currentSession.value.gap_report || null
    specFeedbackMessage.value = ''
    await loadSpecs()
    const canMoveToGap = previewResult.value?.readiness === 'ready'
      && currentSession.value?.feasibility_status === 'feasible'
      && (currentSession.value?.completeness_score || 0) >= 0.75
    syncActiveStep(canMoveToGap ? 'gap' : 'spec')
    ElMessage.success('规格确认信息已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '更新规格确认失败')
  } finally {
    confirmingSpec.value = false
  }
}

const handleAcceptRecommendedSpec = async () => {
  await submitSpecFeedback(buildDefaultSpecConfirmationMessage())
}

const handleSubmitSpecFeedback = async () => {
  const message = specFeedbackMessage.value.trim()
  if (!message) return
  await submitSpecFeedback(message)
}

const handleAnalyzeGaps = async () => {
  if (!currentSession.value?.session_id) return
  analyzing.value = true
  try {
    const result = await agentWorkshopApi.analyzeGaps(currentSession.value.session_id)
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
  if (!currentSession.value?.session_id) return
  generatingToolPlan.value = true
  try {
    await agentWorkshopApi.generateToolingPlan(currentSession.value.session_id)
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
  if (!currentSession.value?.session_id) return
  buildingVersion.value = true
  try {
    const result = await agentWorkshopApi.buildVersion(currentSession.value.session_id)
    latestVersion.value = result.version
    await refreshSession()
    await loadSpecs()
    router.replace({ path: '/workflow/agent-workshop/create', query: { sessionId: currentSession.value.session_id } })
    syncActiveStep('version')
    ElMessage.success('版本草案已生成')
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
    evaluationForm.value.runtime_result.output_text = debugResult.debug_prompt?.llm_final_response || debugResult.report || ''
    evaluationForm.value.runtime_result.user_goal = evaluationForm.value.runtime_result.user_goal || displaySpec.value?.primary_goal || ''
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
        user_goal: evaluationForm.value.runtime_result.user_goal,
        output_text: evaluationForm.value.runtime_result.output_text,
        symbol: debugResult?.symbol || evaluationForm.value.stock.symbol.trim(),
        analysis_date: debugResult?.analysis_date || evaluationForm.value.stock.analysis_date,
        output_payload: debugResult?.raw_result || {},
        debug_prompt: debugResult?.debug_prompt || {},
        template: debugResult?.template || {},
        metadata: debugResult?.metadata || {},
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
    const detail = await agentWorkshopApi.getSpec(spec.spec_id)
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
      await loadLatestVersion(detail.spec_id)
      router.replace({ path: '/workflow/agent-workshop/create', query: { sessionId: detail.latest_session_id } })
    } else {
      currentSession.value = null
      gapReport.value = null
      latestVersion.value = null
      latestEvaluation.value = null
      router.replace({ path: '/workflow/agent-workshop/create', query: { specId: detail.spec_id } })
    }
    syncActiveStep('spec')
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

watch(
  () => `${route.query.sessionId || ''}|${route.query.specId || ''}`,
  async () => {
    await initFromRoute()
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
  white-space: pre-wrap;
  line-height: 1.65;
  color: inherit;
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

.score-desc {
  margin-top: 8px;
  min-height: 36px;
  color: #6f817c;
  font-size: 12px;
  line-height: 1.5;
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

@media (max-width: 1100px) {
  .workspace-shell,
  .step-layout.two-columns,
  .flow-switcher,
  .focus-metrics,
  .score-grid {
    grid-template-columns: 1fr;
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