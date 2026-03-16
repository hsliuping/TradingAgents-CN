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
                <div class="focus-title">{{ selectedSpecName }}</div>
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
                    <el-button type="primary" :disabled="!replyMessage.trim()" :loading="responding" @click="handleRespond">
                      继续讨论
                    </el-button>
                  </div>
                </div>
              </template>
            </el-card>
          </div>

          <div v-else-if="activeStep === 'spec'" class="step-layout two-columns">
            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>确认规格</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" type="success" @click="handlePreviewSpec" :loading="previewing" :disabled="!currentSession">刷新规格</el-button>
                    <el-button size="small" type="warning" @click="handleAnalyzeGaps" :loading="analyzing" :disabled="!canAdvance">做缺口分析</el-button>
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
                    <el-tag v-for="item in displaySpec.outputs" :key="item" class="tag-item" type="success">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block">
                  <div class="field-label">非目标</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in displaySpec.non_goals" :key="item" class="tag-item" type="warning">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block" v-if="previewResult?.pending_questions?.length">
                  <div class="field-label">还要确认</div>
                  <div v-for="question in previewResult.pending_questions" :key="question" class="pending-item">{{ question }}</div>
                </div>
              </div>
            </el-card>

            <el-card class="step-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>缺口分析</span>
                  <div class="session-toolbar-actions">
                    <el-button size="small" type="warning" plain @click="handleGenerateToolingPlan" :loading="generatingToolPlan" :disabled="!currentSession">生成工具需求草案</el-button>
                    <el-button size="small" type="primary" @click="handleBuildVersion" :loading="buildingVersion" :disabled="!canAdvance">生成版本草案</el-button>
                  </div>
                </div>
              </template>

              <div v-if="!gapReport" class="empty-state compact">规格确认后，在这里看可复用能力和还缺什么。</div>
              <div v-else class="gap-panel">
                <div class="field-block">
                  <div class="field-label">可复用模块</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in gapReport.reusable_modules" :key="item" class="tag-item">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block" v-if="gapReport.existing_tools.length">
                  <div class="field-label">已发现工具</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in gapReport.existing_tools" :key="item" class="tag-item" type="info">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block" v-if="gapReport.suggested_tools.length">
                  <div class="field-label">建议补齐的工具</div>
                  <div v-for="item in gapReport.suggested_tools" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block" v-if="gapReport.suggested_skills.length">
                  <div class="field-label">建议补齐的 Skill</div>
                  <div v-for="item in gapReport.suggested_skills" :key="item" class="pending-item">{{ item }}</div>
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
                  <div class="field-label">工具需求草案</div>
                  <div class="note-item" v-if="toolingPlan.summary">{{ toolingPlan.summary }}</div>
                  <div class="runtime-meta-row">
                    <span v-if="toolingPlan.generated_by === 'llm'">生成方式：LLM 草案</span>
                    <span v-else-if="toolingPlan.generated_by">生成方式：规则兜底</span>
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
                    <el-button size="small" type="primary" @click="handleBuildVersion" :loading="buildingVersion" :disabled="!canAdvance">重新生成</el-button>
                    <el-button size="small" type="success" plain @click="openEvaluateDialog" :disabled="!latestVersion">真实结果调试</el-button>
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
                </div>

                <div class="field-block">
                  <div class="field-label">默认工具</div>
                  <div class="tag-wrap">
                    <el-tag v-for="item in latestVersion.required_tools" :key="item" class="tag-item" type="info">{{ item }}</el-tag>
                  </div>
                </div>
                <div class="field-block" v-if="latestVersion.required_skills?.length">
                  <div class="field-label">待补 Skill</div>
                  <div v-for="item in latestVersion.required_skills" :key="item" class="pending-item">{{ item }}</div>
                </div>
                <div class="field-block">
                  <div class="field-label">Prompt 草案</div>
                  <div class="note-item">
                    模板：{{ latestVersion.prompt_template_ref?.template_name || '未生成' }}
                    <br>
                    模板 ID：{{ latestVersion.prompt_template_ref?.template_id || '无' }}
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
                    <el-button size="small" type="success" plain @click="openEvaluateDialog" :disabled="!latestVersion">真实结果调试</el-button>
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
                  <el-tag effect="plain">真实结果调试</el-tag>
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
                  <div class="field-label">本次真实输出</div>
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

    <el-dialog v-model="evaluateDialogVisible" title="真实结果调试" width="860px" destroy-on-close>
      <div class="evaluation-dialog">
        <el-form label-width="120px">
          <el-alert
            type="info"
            :closable="false"
            title="先做一次真实调试运行，确认输出没问题后，再单独发起结果评估。"
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
              placeholder="点击下方按钮后，这里会自动显示本次真实调试输出。"
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
              placeholder="可选，填写你对这次样本或运行结果的主观评价。"
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import DeepModelSelector from '@/components/DeepModelSelector.vue'
import agentWorkshopApi, {
  type AgentEvaluationReport,
  type AgentSpec,
  type AgentWorkshopDebugVersionResult,
  type AgentWorkshopGapAnalysis,
  type AgentWorkshopPreviewResult,
  type AgentWorkshopSessionDetail,
  type AgentWorkshopToolingPlan,
  type AgentWorkshopValuationTraceabilityItem,
  type AgentVersion,
} from '@/api/agentWorkshop'
import { configApi, type LLMConfig } from '@/api/config'

type FlowStep = 'discuss' | 'spec' | 'version' | 'evaluate'

const description = ref('')
const replyMessage = ref('')

const route = useRoute()
const router = useRouter()

const specs = ref<AgentSpec[]>([])
const currentSession = ref<AgentWorkshopSessionDetail | null>(null)
const previewResult = ref<AgentWorkshopPreviewResult | null>(null)
const gapReport = ref<AgentWorkshopGapAnalysis | null>(null)
const latestVersion = ref<AgentVersion | null>(null)
const latestEvaluation = ref<AgentEvaluationReport | null>(null)
const latestDebugResult = ref<AgentWorkshopDebugVersionResult | null>(null)
const availableModels = ref<LLMConfig[]>([])

const evaluateDialogVisible = ref(false)
const evaluationForm = ref({
  evaluation_type: 'production-review',
  sample_set_id: '',
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
const debuggingVersion = ref(false)
const evaluatingVersion = ref(false)
const iteratingVersion = ref(false)
const loadingSpecs = ref(false)
const loadingSessionList = ref(false)
const loadingCurrentSession = ref(false)
const activeStep = ref<FlowStep>('discuss')

const flowSteps: Array<{ key: FlowStep; index: string; title: string; description: string }> = [
  { key: 'discuss', index: '01', title: '聊需求', description: '先把目标、边界和输出讲清楚' },
  { key: 'spec', index: '02', title: '看规格', description: '确认职责、输出和待补能力' },
  { key: 'version', index: '03', title: '生成版本', description: '组装工具、Prompt 和输出结构' },
  { key: 'evaluate', index: '04', title: '评估迭代', description: '看结果，再决定下一轮怎么改' },
]

const displaySpec = computed(() => previewResult.value?.spec || currentSession.value?.current_spec_snapshot || null)
const canAdvance = computed(() => currentSession.value?.feasibility_status === 'feasible' && (currentSession.value?.completeness_score || 0) >= 0.75)
const hasWorkspaceContext = computed(() => Boolean(currentSession.value || displaySpec.value || latestVersion.value || latestEvaluation.value))
const selectedSpecId = computed(() => displaySpec.value?.spec_id || currentSession.value?.current_spec_snapshot?.spec_id || latestVersion.value?.spec_id || '')
const selectedSpecName = computed(() => displaySpec.value?.name || latestVersion.value?.agent_metadata?.name || '未命名 Agent')
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
const evaluationScoreCards = computed(() => {
  const scoreMap: Record<string, { label: string; description: string }> = {
    runtime_goal_alignment: { label: '目标对齐', description: '输出有没有真正回应这次任务目标' },
    runtime_output_quality: { label: '结果质量', description: '输出是否完整、专业、可直接用于判断，而不是只看字段命中' },
    runtime_reasoning_quality: { label: '分析过程', description: '推理过程、假设与结论之间是否自洽合理' },
    runtime_tool_usage: { label: '工具使用', description: '工具选择和调用过程是否适合这个任务' },
    runtime_prompt_quality: { label: '提示词质量', description: 'Prompt 是否把任务、约束和输出要求讲清楚了' },
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
  const canSubmitEvaluation = computed(() => Boolean(evaluationForm.value.runtime_result.output_text?.trim()))
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

  if (previewResult.value || gapReport.value || displaySpec.value) {
    activeStep.value = 'spec'
    return
  }

  activeStep.value = 'discuss'
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

const resetEvaluationForm = () => {
  evaluationForm.value = {
    evaluation_type: 'production-review',
    sample_set_id: '',
    user_feedback: '',
    llm: {
      provider: 'custom_openai',
      model: availableModels.value[0]?.model_name || '',
      temperature: 0.2,
      max_tokens: 4000,
      backend_url: '',
    },
    stock: {
      symbol: displaySpec.value?.sample_symbols?.[0] || '',
      market_type: 'A股',
      analysis_date: '',
    },
    runtime_result: {
      user_goal: '',
      output_text: '',
    },
  }
}

const clearWorkspace = () => {
  currentSession.value = null
  previewResult.value = null
  gapReport.value = null
  latestVersion.value = null
  latestEvaluation.value = null
  latestDebugResult.value = null
  replyMessage.value = ''
  resetEvaluationForm()
  syncActiveStep('discuss')
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
    latestEvaluation.value = null
    syncActiveStep()
    return
  }
  try {
    const result = await agentWorkshopApi.listVersions({ spec_id: specId, page: 1, page_size: 1 })
    latestVersion.value = result.items?.[0] || null
    if (latestVersion.value?.version_id) {
      await loadLatestEvaluation(latestVersion.value.version_id)
    }
  } catch {
    latestVersion.value = null
    latestEvaluation.value = null
  } finally {
    syncActiveStep()
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

const initFromRoute = async () => {
  await loadSpecs()

  const sessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : ''
  const specId = typeof route.query.specId === 'string' ? route.query.specId : ''

  clearWorkspace()

  if (sessionId) {
    loadingSessionList.value = true
    try {
      currentSession.value = await agentWorkshopApi.getSession(sessionId)
      gapReport.value = currentSession.value.gap_report || null
      await loadLatestVersion(currentSession.value.current_spec_snapshot?.spec_id)
      syncActiveStep(currentSession.value.gap_report ? 'spec' : 'discuss')
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
    currentSession.value = await agentWorkshopApi.getSession(currentSession.value.session_id)
    gapReport.value = currentSession.value.gap_report || gapReport.value
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

const handleAnalyzeGaps = async () => {
  if (!currentSession.value?.session_id) return
  analyzing.value = true
  try {
    const result = await agentWorkshopApi.analyzeGaps(currentSession.value.session_id)
    gapReport.value = result.gap_report
    await refreshSession()
    syncActiveStep('spec')
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
    syncActiveStep('spec')
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

const handleDeleteSpec = async (spec: AgentSpec) => {
  try {
    await ElMessageBox.confirm(
      `确定删除“${spec.name}”吗？这会同时删除它的会话、版本和评估记录。`,
      '删除 Agent 草案',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      }
    )

    await agentWorkshopApi.deleteSpec(spec.spec_id)

    if (currentSession.value?.spec_id === spec.spec_id) {
      currentSession.value = null
      previewResult.value = null
      gapReport.value = null
      latestVersion.value = null
      latestEvaluation.value = null
      replyMessage.value = ''
    }

    await refreshAll()
    syncActiveStep()
    ElMessage.success('测试 Agent 已删除')
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    ElMessage.error(error?.message || '删除规格失败')
  }
}

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

watch(
  () => `${route.query.sessionId || ''}|${route.query.specId || ''}`,
  async () => {
    await initFromRoute()
  }
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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