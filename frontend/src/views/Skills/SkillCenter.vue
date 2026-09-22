<template>
  <div class="skill-center">
    <el-page-header title="Skill 中心" content="统一管理所有技能资产">
      <template #extra>
        <el-space>
          <el-button type="primary" icon="Plus" @click="handleCreateSkill">
            新建 Skill
          </el-button>
        </el-space>
      </template>
    </el-page-header>

    <el-tabs v-model="activeTab" type="card" class="skill-tabs">
      <el-tab-pane label="我的 Skill" name="my-skills">
        <div class="skill-stats">
          <el-statistic title="Skill 总数" :value="stats.total" suffix="个">
            <template #prefix>
              <el-icon class="icon" size="20"><Collection /></el-icon>
            </template>
          </el-statistic>
          <el-statistic title="已启用" :value="stats.active" suffix="个">
            <template #prefix>
              <el-icon class="icon success" size="20"><CircleCheck /></el-icon>
            </template>
          </el-statistic>
          <el-statistic title="AI 生成" :value="stats.external" suffix="个">
            <template #prefix>
              <el-icon class="icon" size="20"><MagicStick /></el-icon>
            </template>
          </el-statistic>
          <el-statistic title="绑定数" :value="stats.bindings" suffix="个">
            <template #prefix>
              <el-icon class="icon" size="20"><Link /></el-icon>
            </template>
          </el-statistic>
        </div>

        <el-card class="skill-list-card">
          <template #header>
            <el-space>
              <span>Skill 列表</span>
              <el-input
                v-model="searchQuery"
                placeholder="搜索 Skill 名称或描述"
                class="search-input"
                clearable
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-select v-model="filterStatus" placeholder="按状态筛选">
                <el-option label="全部" value="" />
                <el-option label="已启用" value="active" />
                <el-option label="已禁用" value="disabled" />
                <el-option label="草稿" value="draft" />
                <el-option label="已归档" value="archived" />
              </el-select>
              <el-select v-model="filterSource" placeholder="按来源筛选">
                <el-option label="全部" value="" />
                <el-option label="导入" value="imported" />
                <el-option label="AI 生成" value="ai_generated" />
              </el-select>
            </el-space>
          </template>

          <el-table :data="filteredSkills" stripe border>
            <el-table-column prop="display_name" label="名称" min-width="180">
              <template #default="scope">
                <el-space>
                  <component :is="getSourceIcon(scope.row.source)" class="source-icon" />
                  <span>{{ scope.row.display_name }}</span>
                </el-space>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" />
            <el-table-column prop="type" label="类型" width="75">
              <template #default="scope">
                <el-tag :type="getTypeTagType(scope.row.type)" size="small">
                  {{ getTypeLabel(scope.row.type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="source" label="来源" width="75">
              <template #default="scope">
                <el-tag size="small">{{ getSourceLabel(scope.row.source) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="65">
              <template #default="scope">
                <el-tag :type="getStatusTagType(scope.row.status)" size="small">
                  {{ getStatusLabel(scope.row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="bindings" label="绑定" width="110">
              <template #default="scope">
                <el-space v-if="scope.row.bindings?.agents?.length" wrap size="small">
                  <el-tag
                    v-for="aid in scope.row.bindings.agents.slice(0, 3)"
                    :key="aid"
                    size="small"
                    type="info"
                  >
                    {{ getAgentName(aid) }}
                  </el-tag>
                  <el-text v-if="scope.row.bindings.agents.length > 3" type="info" size="small">
                    +{{ scope.row.bindings.agents.length - 3 }}
                  </el-text>
                </el-space>
                <span v-else class="text-gray">未绑定</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" align="center">
              <template #default="scope">
                <el-space>
                  <el-button
                    size="small"
                    icon="Play"
                    @click="handleTest(scope.row)"
                    :disabled="scope.row.status !== 'active'"
                  >测试</el-button>
                  <el-button
                    size="small"
                    icon="Power"
                    type="warning"
                    @click="handleToggleStatus(scope.row)"
                    v-if="scope.row.status === 'active'"
                  >禁用</el-button>
                  <el-button
                    size="small"
                    icon="Check"
                    type="success"
                    @click="handleToggleStatus(scope.row)"
                    v-else
                  >启用</el-button>
                  <el-dropdown trigger="click" @command="(cmd: string) => handleMoreAction(cmd, scope.row)">
                    <el-button size="small" icon="MoreFilled" circle />
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="credentials">
                          <el-icon><Key /></el-icon> 凭证配置
                        </el-dropdown-item>
                        <el-dropdown-item command="bind">
                          <el-icon><Link /></el-icon> 绑定 Agent
                        </el-dropdown-item>
                        <el-dropdown-item command="install_deps">
                          <el-icon><Download /></el-icon> 安装依赖
                        </el-dropdown-item>
                        <el-dropdown-item command="uninstall" divided>
                          <el-icon style="color: var(--el-color-danger)"><Delete /></el-icon>
                          <span style="color: var(--el-color-danger)">卸载</span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="ClawHub 安装" name="clawhub">
        <el-card class="clawhub-card">
          <template #header>
            <el-space>
              <span>ClawHub 脚本型 Skill 安装</span>
              <el-tag type="info">仅支持包含 scripts/ 的 Python 脚本型 Skill</el-tag>
            </el-space>
          </template>

          <el-form :inline="true" @submit.prevent>
            <el-form-item label="Skill Slug">
              <el-input
                v-model="clawhubSlug"
                placeholder="如 ifind-repilot-finance-data-search"
                style="width: 360px"
                clearable
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="clawhubInstalling" @click="() => installClawHubSkill()">
                安装并导入
              </el-button>
              <el-button :loading="clawhubSearching" @click="searchClawHubSkills">
                搜索
              </el-button>
              <el-button @click="loadLocalSkills">刷新本地包</el-button>
            </el-form-item>
          </el-form>

          <el-table v-if="clawhubResults.length" :data="clawhubResults" border style="margin-top: 12px">
            <el-table-column prop="display_name" label="名称" min-width="180" />
            <el-table-column prop="summary" label="描述" min-width="260" show-overflow-tooltip />
            <el-table-column prop="slug" label="Slug" min-width="220" />
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button size="small" type="primary" @click="installClawHubSkill(scope.row.slug)">
                  安装
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-divider />
          <h4>本地已安装 Skill 包</h4>
          <el-table :data="localSkills" border>
            <el-table-column prop="name" label="名称" min-width="220" />
            <el-table-column prop="skill_dir" label="目录" min-width="320" show-overflow-tooltip />
            <el-table-column label="类型" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.has_scripts ? 'success' : 'info'">
                  {{ scope.row.has_scripts ? '脚本型' : '知识型' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数据库" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.imported_to_db ? 'success' : 'warning'">
                  {{ scope.row.imported_to_db ? '已导入' : '未导入' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="scope">
                <el-button size="small" :disabled="scope.row.imported_to_db" @click="importLocalSkill(scope.row.skill_dir)">
                  导入
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="安装 / 导入" name="skillhub">
        <el-card class="clawhub-card">
          <template #header>
            <el-space>
              <span>安装 / 导入</span>
              <el-tag type="info">支持 ZIP 文件上传或下载链接导入</el-tag>
            </el-space>
          </template>

          <el-row :gutter="24">
            <!-- 左侧：ZIP 上传 -->
            <el-col :span="12">
              <el-card shadow="never" style="height: 100%">
                <template #header>
                  <div style="display: flex; align-items: center;">
                    <el-icon style="margin-right: 8px;"><Upload /></el-icon>
                    <span>ZIP 文件上传</span>
                  </div>
                </template>
                <el-upload
                  ref="zipUploadRef"
                  drag
                  :auto-upload="false"
                  accept=".zip"
                  :limit="1"
                  :on-change="handleZipFileChange"
                  :on-remove="handleZipFileRemove"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">将 ZIP 文件拖到此处，或<em>点击上传</em></div>
                  <template #tip>
                    <div class="el-upload__tip">
                      支持 .zip 格式，最大 50MB。包内需包含 SKILL.md 文件。
                    </div>
                  </template>
                </el-upload>
                <div v-if="selectedZipFile" style="margin-top: 12px; text-align: right;">
                  <el-button type="primary" :loading="importingZip" @click="handleImportZip">
                    导入
                  </el-button>
                </div>
              </el-card>
            </el-col>

            <!-- 右侧：URL 导入 -->
            <el-col :span="12">
              <el-card shadow="never" style="height: 100%">
                <template #header>
                  <div style="display: flex; align-items: center;">
                    <el-icon style="margin-right: 8px;"><Link /></el-icon>
                    <span>下载链接导入</span>
                  </div>
                </template>
                <el-form label-position="top">
                  <el-form-item label="ZIP 下载链接">
                    <el-input
                      v-model="importUrl"
                      placeholder="https://example.com/skill-package.zip"
                      clearable
                      type="textarea"
                      :rows="2"
                    />
                  </el-form-item>
                  <el-form-item label="自定义名称（可选）">
                    <el-input
                      v-model="importCustomName"
                      placeholder="留空则从 ZIP 包中自动提取"
                      clearable
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="importingUrl"
                      :disabled="!importUrl.trim()"
                      @click="handleImportUrl"
                    >
                      下载并导入
                    </el-button>
                  </el-form-item>
                </el-form>
              </el-card>
            </el-col>
          </el-row>

          <el-divider />
          <h4>本地已安装 Skill 包</h4>
          <el-table :data="localSkills" border>
            <el-table-column prop="name" label="名称" min-width="220" />
            <el-table-column prop="skill_dir" label="目录" min-width="320" show-overflow-tooltip />
            <el-table-column label="类型" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.has_scripts ? 'success' : 'info'">
                  {{ scope.row.has_scripts ? '脚本型' : '知识型' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数据库" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.imported_to_db ? 'success' : 'warning'">
                  {{ scope.row.imported_to_db ? '已导入' : '未导入' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="scope">
                <el-button size="small" :disabled="scope.row.imported_to_db" @click="importLocalSkill(scope.row.skill_dir)">
                  导入
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="AI 生成" name="generate">
        <SkillGenerate @imported="handleSkillImported" />
      </el-tab-pane>

      <el-tab-pane label="执行日志" name="logs">
        <div class="logs-container">
          <!-- 统计卡片 -->
          <el-row :gutter="12" style="margin-bottom: 16px;">
            <el-col :span="6">
              <el-card shadow="never">
                <el-statistic title="总调用" :value="logStats.total" />
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never">
                <el-statistic title="成功" :value="logStats.success" />
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never">
                <el-statistic title="失败" :value="logStats.failed" />
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never">
                <div style="font-size: 12px; color: #909399; margin-bottom: 4px;">成功率</div>
                <div style="font-size: 24px; font-weight: 600;">
                  {{ logStats.total ? ((logStats.success / logStats.total) * 100).toFixed(1) : 0 }}%
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 过滤栏 -->
          <el-form :inline="true" style="margin-bottom: 12px;">
            <el-form-item label="工具">
              <el-input v-model="logFilter.tool_id" placeholder="工具 ID" clearable style="width: 180px;" />
            </el-form-item>
            <el-form-item label="Agent">
              <el-input v-model="logFilter.agent_id" placeholder="Agent ID" clearable style="width: 180px;" />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="logFilter.success" placeholder="全部" clearable style="width: 100px;">
                <el-option label="成功" :value="true" />
                <el-option label="失败" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadToolLogs">查询</el-button>
            </el-form-item>
          </el-form>

          <!-- 日志表格 -->
          <el-table :data="toolLogs" stripe style="width: 100%;" max-height="500">
            <el-table-column prop="tool_id" label="工具" width="180" show-overflow-tooltip />
            <el-table-column prop="agent_id" label="Agent" width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.success ? 'success' : 'danger'" size="small">
                  {{ scope.row.success ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="execution_time_ms" label="耗时" width="80">
              <template #default="scope">{{ scope.row.execution_time_ms }}ms</template>
            </el-table-column>
            <el-table-column prop="tool_args" label="参数" show-overflow-tooltip>
              <template #default="scope">
                <pre style="margin: 0; font-size: 11px;">{{ JSON.stringify(scope.row.tool_args, null, 0) }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" show-overflow-tooltip>
              <template #default="scope">
                <span v-if="scope.row.error" style="color: #f56c6c;">{{ scope.row.error }}</span>
                <pre v-else style="margin: 0; font-size: 11px;">{{ String(scope.row.result).substring(0, 200) }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="scope">
                {{ scope.row.created_at ? new Date(scope.row.created_at).toLocaleString('zh-CN') : '' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="bindDialogVisible" title="绑定到 Agent" width="600px">
      <div v-if="currentSkill" class="bind-dialog-content">
        <p class="bind-skill-name">{{ currentSkill.display_name }}</p>
        
        <!-- 已绑定的 Agent -->
        <div v-if="boundAgents.length" class="bound-section">
          <h4 style="margin: 0 0 8px;">已绑定 Agent</h4>
          <el-space wrap>
            <el-tag
              v-for="agent in boundAgents"
              :key="agent.agent_id"
              closable
              @close="unbindAgent(agent.agent_id)"
              style="margin: 4px;"
            >
              {{ agent.name }}
              <span v-if="agent.priority" style="color: #909399; font-size: 11px;"> (P{{ agent.priority }})</span>
            </el-tag>
          </el-space>
        </div>

        <el-divider v-if="boundAgents.length" />

        <!-- 添加新绑定（无可选 Agent 时隐藏，如社区版） -->
        <div v-if="availableAgents.length" class="bind-add-section">
          <h4 style="margin: 0 0 8px;">添加绑定</h4>
          <el-form :model="bindForm" label-width="80px">
            <el-form-item label="选择 Agent">
              <el-select
                v-model="bindForm.agentIds"
                multiple
                filterable
                placeholder="选择一个或多个 Agent"
                style="width: 100%;"
              >
                <el-option
                  v-for="agent in availableAgents"
                  :key="agent.id"
                  :label="agent.name"
                  :value="agent.id"
                  :disabled="boundAgents.some(b => b.agent_id === agent.id)"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="优先级">
              <el-input-number v-model="bindForm.priority" :min="0" :max="100" style="width: 120px;" />
              <el-text type="info" size="small" style="margin-left: 8px;">数字越大越优先调用</el-text>
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="bindDialogVisible = false">关闭</el-button>
        <el-button
          v-if="availableAgents.length"
          type="primary"
          :loading="bindLoading"
          :disabled="!bindForm.agentIds.length"
          @click="confirmBatchBind"
        >
          批量绑定 ({{ bindForm.agentIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="testDialogVisible" title="测试 Skill" width="720px">
      <div v-if="currentTestSkill" class="test-dialog-content">
        <p class="test-skill-name">{{ currentTestSkill.display_name }}</p>
        <p class="test-skill-desc">来源：{{ currentTestSkill.source }} | 类型：{{ currentTestSkill.type }}</p>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="测试方式与正式 Agent 调用一致"
          description="后端会使用与分析流程相同的 LLM + Function Calling 机制：把 SKILL.md 作为系统提示词，让 LLM 理解后自主调用工具，并返回完整调用链路。"
          style="margin-bottom: 12px"
        />

        <el-form label-width="100px" style="margin-bottom: 16px">
          <el-form-item label="测试问题">
            <el-input
              v-model="testQuestion"
              type="textarea"
              :rows="3"
              placeholder="例如：帮我查一下美联储利率政策最近的新闻；或：测试一下这个 Skill 能否正常工作"
              :disabled="testLoading"
            />
          </el-form-item>
        </el-form>

        <div v-if="testLoading" class="test-status">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在调用 LLM 执行工具，可能需要 10-60 秒...
        </div>

        <div v-else-if="testResult" class="test-result">
          <el-alert
            :title="testResult.success ? '测试完成' : '测试失败'"
            :type="testResult.success ? 'success' : 'error'"
            :closable="false"
          />
          <div v-if="testResult.error" class="result-error">
            <strong>错误信息：</strong>
            <pre>{{ testResult.error }}</pre>
          </div>

          <!-- Agent 调用结果展示 -->
          <template v-if="testResult.success && testResult.result">
            <div v-if="testResult.result.final_answer" class="result-section">
              <strong>LLM 最终回答：</strong>
              <pre>{{ testResult.result.final_answer }}</pre>
            </div>

            <div v-if="testResult.result.tool_calls && testResult.result.tool_calls.length" class="result-section">
              <strong>工具调用轨迹（{{ testResult.result.tool_calls_count || testResult.result.tool_calls.length }} 次）：</strong>
              <pre>{{ JSON.stringify(testResult.result.tool_calls, null, 2) }}</pre>
            </div>

            <div v-if="testResult.result.model" class="result-meta">
              模型: {{ testResult.result.provider }}/{{ testResult.result.model }}
            </div>

            <!-- 兼容 knowledge 等非 Agent 路径 -->
            <div v-if="!testResult.result.final_answer && !testResult.result.tool_calls" class="result-section">
              <strong>详细信息：</strong>
              <pre>{{ formatTestResult(testResult.result) }}</pre>
            </div>
          </template>

          <div v-if="testResult.execution_time_ms > 0" class="result-meta">
            执行耗时：{{ testResult.execution_time_ms }}ms
          </div>
        </div>

        <div v-else class="test-hint">
          <el-text type="info">输入测试问题后点击"运行测试"，LLM 将根据 SKILL.md 自动调用工具</el-text>
        </div>
      </div>
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testLoading" @click="confirmTest">运行测试</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="credentialDialogVisible" title="配置 Skill 凭证" width="640px">
      <div v-if="credentialSkill" class="credential-dialog-content">
        <p class="bind-skill-name">{{ credentialSkill.display_name }}</p>
        <el-alert
          v-if="credentialStatus?.missing_required?.length"
          type="warning"
          :closable="false"
          :title="`缺少必填凭证：${credentialStatus.missing_required.join(', ')}`"
          style="margin-bottom: 12px"
        />
        <el-empty v-if="credentialStatus && !credentialStatus.required.length && !credentialStatus.extra.length" description="此 Skill 未声明凭证要求" />
        <el-form v-else label-width="130px">
          <el-form-item
            v-for="item in credentialStatus?.required || []"
            :key="item.name"
            :label="item.name"
          >
            <el-input
              v-model="credentialForm[item.name]"
              :placeholder="item.configured ? item.masked_value : item.description || '请输入凭证值'"
              show-password
              style="width: 360px"
            />
            <el-tag v-if="item.required" type="danger" size="small" style="margin-left: 8px">必填</el-tag>
            <el-tag v-if="item.config_type === 'script_arg'" type="warning" size="small" style="margin-left: 8px">
              {{ item.config_command }}
            </el-tag>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="credentialDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="credentialSaving" @click="saveCredentialConfig">保存凭证</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Collection,
  CircleCheck,
  Link,
  Search,
  Download,
  MagicStick,
  WarningFilled,
  Loading,
  Key,
  Upload,
  UploadFilled
} from '@element-plus/icons-vue'
import SkillGenerate from './SkillCenter/SkillGenerate.vue'
import { skillCenterApi } from '@/api/skillCenter'
import { skillsApi } from '@/api/skills'
import { ApiClient } from '@/api/request'

interface SkillSummary {
  skill_id: string
  display_name: string
  description: string
  source: string
  type: string
  status: string
  bindable: boolean
  tool_id?: string
  test_status?: string
  last_tested_at?: string
  bindings: { agents: string[]; workflows: string[] }
  created_at?: string
  updated_at?: string
}

const activeTab = ref('my-skills')
const searchQuery = ref('')
const filterStatus = ref('')
const filterSource = ref('')
const skills = ref<SkillSummary[]>([])
const stats = ref({ total: 0, standard: 0, external: 0, active: 0, bindings: 0 })

// 执行日志
const toolLogs = ref<any[]>([])
interface LogStats {
  total: number
  success: number
  failed: number
  by_tool: Array<{ tool_id: string; count: number; avg_ms: number }>
  by_agent: Array<{ agent_id: string; count: number }>
}
const logStats = ref<LogStats>({ total: 0, success: 0, failed: 0, by_tool: [], by_agent: [] })
const logFilter = ref({ tool_id: '', agent_id: '', success: null as boolean | null })

const bindDialogVisible = ref(false)
const bindForm = ref({ agentIds: [] as string[], priority: 0 })
const bindLoading = ref(false)
const boundAgents = ref<Array<{ agent_id: string; name: string; category: string; priority: number }>>([])
const currentSkill = ref<SkillSummary | null>(null)
const availableAgents = ref<{ id: string; name: string }[]>([])
// Agent 列表是否已加载完成（成功或失败都算），用于绑定入口的懒加载守卫
const agentsLoaded = ref(false)

const testDialogVisible = ref(false)
const currentTestSkill = ref<SkillSummary | null>(null)
const testLoading = ref(false)
const testQuestion = ref('')
const testResult = ref<{ success: boolean; result?: any; error?: string; execution_time_ms: number } | null>(null)

const clawhubSlug = ref('')
const clawhubSearching = ref(false)
const clawhubInstalling = ref(false)
const clawhubResults = ref<any[]>([])
const localSkills = ref<any[]>([])

// ZIP / URL 导入相关
const zipUploadRef = ref<any>(null)
const selectedZipFile = ref<File | null>(null)
const importingZip = ref(false)
const importUrl = ref('')
const importCustomName = ref('')
const importingUrl = ref(false)

const credentialDialogVisible = ref(false)
const credentialSkill = ref<SkillSummary | null>(null)
const credentialStatus = ref<any | null>(null)
const credentialForm = ref<Record<string, string>>({})
const credentialSaving = ref(false)

const filteredSkills = computed(() => {
  return skills.value.filter(skill => {
    const matchSearch = !searchQuery.value ||
      skill.display_name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      skill.description.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchStatus = !filterStatus.value || skill.status === filterStatus.value
    const matchSource = !filterSource.value || skill.source === filterSource.value
    return matchSearch && matchStatus && matchSource
  })
})

type ElTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function getSourceIcon(source: string): Component {
  const icons: Record<string, Component> = {
    imported: Download,
    clawhub: Download,
    ai_generated: MagicStick,
    system: Collection,
    gap_generated: WarningFilled
  }
  return icons[source] || Collection
}

function getSourceLabel(source: string) {
  const labels: Record<string, string> = {
    imported: '导入',
    clawhub: 'ClawHub',
    ai_generated: 'AI 生成',
    system: '系统',
    gap_generated: '缺口生成'
  }
  return labels[source] || source
}

function getTypeLabel(type: string) {
  const labels: Record<string, string> = {
    executable: '可执行',
    knowledge: '知识型',
    api: 'API',
    mcp: 'MCP'
  }
  return labels[type] || type
}

function getTypeTagType(type: string): ElTagType {
  const types: Record<string, ElTagType> = {
    executable: 'primary',
    knowledge: 'info',
    api: 'success',
    mcp: 'warning'
  }
  return types[type] || 'info'
}

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    active: '已启用',
    disabled: '已禁用',
    draft: '草稿',
    testing: '测试中',
    archived: '已归档',
    failed: '失败'
  }
  return labels[status] || status
}

function getStatusTagType(status: string): ElTagType {
  const types: Record<string, ElTagType> = {
    active: 'success',
    disabled: 'warning',
    draft: 'info',
    testing: 'primary',
    archived: 'info',
    failed: 'danger'
  }
  return types[status] || 'info'
}

function getAgentName(agentId: string): string {
  const agent = availableAgents.value.find(a => a.id === agentId)
  return agent ? agent.name : agentId
}

async function loadSkills() {
  try {
    skills.value = await skillCenterApi.listSkills()
  } catch (error) {
    console.error('Failed to load skills:', error)
  }
}

async function loadStats() {
  try {
    stats.value = await skillCenterApi.getStats()
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

async function loadAgents() {
  try {
    // Agent 元数据来自 Pro 路由（app/pro/routers/agents.py），社区版无此路由：
    // 静默降级为空列表（关闭全局 404 弹窗），绑定下拉为空即"无 Agent 可绑"
    const res: any = await ApiClient.get('/api/agents', undefined, { skipErrorHandler: true })
    const agents = Array.isArray(res) ? res : (res?.data || [])
    availableAgents.value = agents.map((a: any) => ({ id: a.id, name: a.name }))
  } catch (error) {
    console.debug('Agent 列表不可用（社区版无 Agent 管理体系），绑定下拉置空')
  } finally {
    agentsLoaded.value = true
  }
}

function handleCreateSkill() {
  window.location.href = '/skills/generation/create'
}

async function searchClawHubSkills() {
  if (!clawhubSlug.value.trim()) {
    ElMessage.warning('请输入搜索关键词或 Skill slug')
    return
  }
  clawhubSearching.value = true
  try {
    const result = await skillsApi.searchClawHub({ q: clawhubSlug.value.trim(), limit: 20 })
    clawhubResults.value = result.results
    if (!result.results.length) ElMessage.info('未找到匹配的 ClawHub Skill')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '搜索 ClawHub 失败')
  } finally {
    clawhubSearching.value = false
  }
}

async function installClawHubSkill(slug?: string) {
  const targetSlug = typeof slug === 'string' ? slug : clawhubSlug.value.trim()
  if (!targetSlug) {
    ElMessage.warning('请输入 Skill slug')
    return
  }
  clawhubInstalling.value = true
  try {
    const result = await skillsApi.installClawHub({ slug: targetSlug })
    if (result.success) {
      ElMessage.success(result.message)
      await Promise.all([loadLocalSkills(), loadSkills(), loadStats()])
      activeTab.value = 'my-skills'
    } else {
      ElMessage.warning(result.message)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '安装 ClawHub Skill 失败')
  } finally {
    clawhubInstalling.value = false
  }
}

async function loadLocalSkills() {
  try {
    localSkills.value = await skillsApi.listLocalSkills()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载本地 Skill 包失败')
  }
}

async function importLocalSkill(skillDir: string) {
  try {
    await skillsApi.importLocalSkill({ skill_dir: skillDir })
    ElMessage.success('本地 Skill 导入成功')
    await Promise.all([loadLocalSkills(), loadSkills(), loadStats()])
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入本地 Skill 失败')
  }
}

// ==================== ZIP / URL 导入 ====================

function handleZipFileChange(file: any) {
  if (file && file.raw) {
    selectedZipFile.value = file.raw
  }
}

function handleZipFileRemove() {
  selectedZipFile.value = null
}

async function handleImportZip() {
  if (!selectedZipFile.value) return
  importingZip.value = true
  try {
    const result = await skillsApi.importZip(selectedZipFile.value)
    ElMessage.success(result.message || 'ZIP 导入成功')
    selectedZipFile.value = null
    if (zipUploadRef.value) zipUploadRef.value.clearFiles()
    await Promise.all([loadLocalSkills(), loadSkills(), loadStats()])
    activeTab.value = 'my-skills'
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'ZIP 导入失败')
  } finally {
    importingZip.value = false
  }
}

async function handleImportUrl() {
  if (!importUrl.value.trim()) return
  importingUrl.value = true
  try {
    const result = await skillsApi.importFromUrl({
      url: importUrl.value.trim(),
      name: importCustomName.value.trim() || undefined,
    })
    ElMessage.success(result.message || 'URL 导入成功')
    importUrl.value = ''
    importCustomName.value = ''
    await Promise.all([loadLocalSkills(), loadSkills(), loadStats()])
    activeTab.value = 'my-skills'
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || 'URL 导入失败')
  } finally {
    importingUrl.value = false
  }
}

async function handleSkillImported(skillName: string) {
  ElMessage.success(`已导入 Skill: ${skillName}`)
  activeTab.value = 'my-skills'
  await loadSkills()
  loadStats()
  // 自动弹出绑定对话框
  const skill = skills.value.find(s => s.skill_id === skillName || s.display_name === skillName)
  if (skill) {
    handleBindAgent(skill)
  }
}

function handleTest(skill: SkillSummary) {
  currentTestSkill.value = skill
  testResult.value = null
  testQuestion.value = ''
  testDialogVisible.value = true
}

function formatTestResult(result: any): string {
  if (typeof result === 'string') return result
  // 知识型 Skill 的友好展示
  if (result.skill_type === 'knowledge') {
    const lines = [
      `类型: ${result.skill_type}`,
      `名称: ${result.name || '-'}`,
      `描述: ${result.description || '-'}`,
      result.category ? `分类: ${result.category}` : '',
      result.parameters_count !== undefined ? `参数数量: ${result.parameters_count}` : '',
      `已注册到工具库: ${result.registered_in_registry ? '是' : '否'}`,
      result.note || ''
    ].filter(Boolean)
    return lines.join('\n')
  }
  return JSON.stringify(result, null, 2)
}

async function confirmTest() {
  if (!currentTestSkill.value) return
  testLoading.value = true
  testResult.value = null
  try {
    const result = await skillsApi.testSkill({
      skill_name: currentTestSkill.value.skill_id,
      args: {},
      question: testQuestion.value || '',
      timeout: 90,
    } as any)
    testResult.value = result
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.error || '测试执行失败')
  } finally {
    testLoading.value = false
  }
}

function handleToggleStatus(skill: SkillSummary) {
  if (skill.source === 'ai_generated') {
    import('@/api/skillGeneration').then(api => {
      api.skillGenerationApi.updateSkillStatus(skill.skill_id, skill.status === 'active' ? 'disabled' : 'active')
        .then(() => loadSkills())
    })
  } else {
    import('@/api/skills').then(api => {
      api.skillsApi.toggleSkill(skill.skill_id.replace(/_/g, '-'), skill.status !== 'active')
        .then(() => loadSkills())
    })
  }
}

async function handleBindAgent(skill: SkillSummary) {
  // 无可绑定的 Agent 时不打开绑定弹窗（社区版无 Agent 工坊，列表为空）
  if (!agentsLoaded.value) {
    await loadAgents()
  }
  if (!availableAgents.value.length) {
    ElMessage.warning('暂无可绑定的 Agent')
    return
  }
  currentSkill.value = skill
  bindForm.value = { agentIds: [], priority: 0 }
  bindDialogVisible.value = true
  // 加载已绑定的 Agent
  try {
    const result = await skillCenterApi.getSkillBindings(skill.skill_id)
    boundAgents.value = result.agents
  } catch {
    boundAgents.value = []
  }
}

async function handleUninstall(skill: SkillSummary) {
  try {
    await ElMessageBox.confirm(
      `确定要卸载 Skill "${skill.display_name}" 吗？\n\n卸载将删除：\n• Skill 记录\n• 本地脚本目录\n• 凭证配置\n• Agent 绑定关系\n\n此操作不可撤销。`,
      '卸载确认',
      { type: 'warning', confirmButtonText: '确认卸载', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  try {
    if (skill.source === 'ai_generated') {
      // AI 生成的 Skill 使用 skill-generation API
      const { skillGenerationApi } = await import('@/api/skillGeneration')
      const result = await skillGenerationApi.deleteSkill(skill.skill_id)
      ElMessage.success(result.message || result.data?.message || `Skill "${skill.display_name}" 已卸载`)
    } else {
      // 手动安装的 Skill 使用 skills API
      const skillName = skill.skill_id.replace(/_/g, '-')
      const result = await skillsApi.deleteSkill(skillName)
      ElMessage.success(result.message || `Skill "${skill.display_name}" 已卸载`)
    }
    await loadSkills()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '卸载失败')
  }
}

// 下拉菜单操作分发
function handleMoreAction(command: string, skill: any) {
  switch (command) {
    case 'credentials':
      handleCredentials(skill)
      break
    case 'bind':
      handleBindAgent(skill)
      break
    case 'install_deps':
      handleInstallDeps(skill)
      break
    case 'uninstall':
      handleUninstall(skill)
      break
  }
}

async function handleInstallDeps(skill: any) {
  const skillName = skill.skill_id ? skill.skill_id.replace(/_/g, '-') : skill.name
  const displayName = skill.display_name || skill.name || skill.skill_id || skillName
  const loadingMsg = ElMessage({
    message: `正在为 "${displayName}" 安装依赖...`,
    type: 'info',
    duration: 0,
  })
  try {
    const result = await skillsApi.installSkillDeps(skillName)
    loadingMsg.close()
    if (result.success && result.installed) {
      ElMessageBox.alert(
        `<pre style="max-height:400px;overflow:auto;font-size:12px;">${result.log}</pre>`,
        '依赖安装成功',
        { dangerouslyUseHTMLString: true, type: 'success' }
      )
    } else if (!result.installed) {
      ElMessage.info(result.message)
    } else {
      ElMessageBox.alert(
        `<pre style="max-height:400px;overflow:auto;font-size:12px;color:#f56c6c;">${result.log}</pre>`,
        '依赖安装失败',
        { dangerouslyUseHTMLString: true, type: 'error' }
      )
    }
  } catch (error: any) {
    loadingMsg.close()
    ElMessage.error(error?.response?.data?.detail || '安装依赖失败')
  }
}

async function confirmBatchBind() {
  if (!currentSkill.value || !bindForm.value.agentIds.length) return
  bindLoading.value = true
  try {
    const result = await skillCenterApi.batchBindSkill(
      currentSkill.value.skill_id,
      bindForm.value.agentIds,
      bindForm.value.priority
    )
    ElMessage.success(result.message)
    bindForm.value = { agentIds: [], priority: 0 }
    // 刷新绑定列表
    const bindings = await skillCenterApi.getSkillBindings(currentSkill.value.skill_id)
    boundAgents.value = bindings.agents
    loadSkills()
    loadStats()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '批量绑定失败')
  } finally {
    bindLoading.value = false
  }
}

async function unbindAgent(agentId: string) {
  if (!currentSkill.value) return
  try {
    await skillCenterApi.unbindSkillFromAgent(currentSkill.value.skill_id, agentId)
    ElMessage.success('已解绑')
    boundAgents.value = boundAgents.value.filter(a => a.agent_id !== agentId)
    loadSkills()
    loadStats()
  } catch {
    ElMessage.error('解绑失败')
  }
}

async function handleCredentials(skill: SkillSummary) {
  credentialSkill.value = skill
  credentialForm.value = {}
  credentialStatus.value = null
  credentialDialogVisible.value = true
  try {
    credentialStatus.value = await skillsApi.getCredentialStatus(skill.skill_id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载凭证状态失败')
  }
}

async function saveCredentialConfig() {
  if (!credentialSkill.value || !credentialStatus.value) return
  const filled = Object.fromEntries(
    Object.entries(credentialForm.value).filter(([, value]) => String(value || '').trim() !== '')
  ) as Record<string, string>
  if (!Object.keys(filled).length) {
    ElMessage.warning('请输入至少一个凭证值')
    return
  }
  credentialSaving.value = true
  try {
    const scriptItems = (credentialStatus.value.required || []).filter((item: any) =>
      item.config_type === 'script_arg' && item.config_command && filled[item.name]
    )
    for (const item of scriptItems) {
      await skillsApi.configureCredentialViaScript(credentialSkill.value.skill_id, {
        config_command: item.config_command,
        credential_value: filled[item.name]
      })
      delete filled[item.name]
    }
    if (Object.keys(filled).length) {
      await skillsApi.saveCredentials(credentialSkill.value.skill_id, filled)
    }
    ElMessage.success('凭证已保存')
    credentialStatus.value = await skillsApi.getCredentialStatus(credentialSkill.value.skill_id)
    credentialForm.value = {}
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.message || '保存凭证失败')
  } finally {
    credentialSaving.value = false
  }
}

// 执行日志
async function loadToolLogs() {
  try {
    const params: any = { limit: 50 }
    if (logFilter.value.tool_id) params.tool_id = logFilter.value.tool_id
    if (logFilter.value.agent_id) params.agent_id = logFilter.value.agent_id
    if (logFilter.value.success !== null) params.success = logFilter.value.success
    const result = await skillCenterApi.getToolLogs(params)
    toolLogs.value = result.logs
  } catch {
    ElMessage.error('加载执行日志失败')
  }
}

async function loadLogStats() {
  try {
    logStats.value = await skillCenterApi.getToolLogStats()
  } catch {
    // 忽略
  }
}

watch(activeTab, (val) => {
  if (val === 'logs') {
    loadToolLogs()
    loadLogStats()
  }
  if (val === 'clawhub') {
    loadLocalSkills()
  }
})

onMounted(() => {
  loadSkills()
  loadStats()
  loadAgents()
})
</script>

<style scoped>
.skill-center {
  padding: 20px;
}

.skill-tabs {
  margin-top: 20px;
}

.skill-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.skill-stats .el-statistic {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.skill-stats .icon {
  color: #666;
}

.skill-stats .icon.success {
  color: #67c23a;
}

.skill-list-card {
  margin-top: 20px;
}

.search-input {
  width: 300px;
}

.source-icon {
  color: #409eff;
}

.text-gray {
  color: #999;
}

.el-table {
  --el-table-header-text-color: #666;
  --el-table-row-hover-bg-color: #fafafa;
}

.test-dialog-content {
  max-height: 500px;
  overflow-y: auto;
}

.test-skill-name {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 16px;
}

.test-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
}

.test-result {
  margin-top: 16px;
}

.result-section {
  margin-top: 12px;
}

.result-section strong {
  display: block;
  margin-bottom: 4px;
  color: #303133;
}

.test-result pre {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  margin: 8px 0;
}

.result-error {
  margin-top: 12px;
  color: #f56c6c;
}

.result-meta {
  margin-top: 12px;
  color: #909399;
  font-size: 12px;
}

.bind-dialog-content {
  max-height: 500px;
  overflow-y: auto;
}

.bind-skill-name {
  font-weight: 600;
  font-size: 15px;
  margin: 0 0 16px;
  color: var(--el-color-primary);
}

.bound-section {
  margin-bottom: 12px;
}

.bind-add-section {
  margin-top: 12px;
}

.logs-container {
  padding: 8px 4px;
}

.logs-container .el-card {
  background: #fafbfc;
}

.logs-container pre {
  margin: 0;
  font-size: 11px;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
}

.logs-container .el-table {
  font-size: 12px;
}
</style>