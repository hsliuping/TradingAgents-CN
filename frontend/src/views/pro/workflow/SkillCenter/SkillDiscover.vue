<template>
  <div class="skill-discover">
    <el-card class="discover-card">
      <template #header>
        <div class="card-header">
          <span>发现 & 导入 Skill</span>
          <el-text type="info">从 SkillHub、GitHub、MCP Hub、AgentHub 或直接上传导入可验证的 Skill</el-text>
        </div>
      </template>

      <el-tabs v-model="activeTab" type="border-card" class="import-tabs">
        <!-- 腾讯 SkillHub（第一位） -->
        <el-tab-pane label="腾讯 SkillHub" name="skillhub">
          <div class="skillhub-header">
            <el-input
              v-model="skillhubKeyword"
              placeholder="搜索技能..."
              style="width: 300px;"
              clearable
              @keyup.enter="loadSkillHubSkills"
            />
            <el-button type="primary" :loading="skillhubLoading" @click="loadSkillHubSkills">
              搜索
            </el-button>
            <el-text type="info">skillhub.cloud.tencent.com — 7.1 万个 AI Skills，腾讯官方出品</el-text>
          </div>

          <!-- 精选推荐 -->
          <div v-if="skillhubFeatured.length && !skillhubKeyword" class="skillhub-section">
            <h4 style="margin: 12px 0 8px; color: var(--el-color-primary);">精选推荐</h4>
            <el-space wrap>
              <el-card
                v-for="skill in skillhubFeatured"
                :key="skill.skill_id"
                class="skillhub-featured-card"
                shadow="hover"
              >
                <div class="featured-name">{{ skill.display_name }}</div>
                <div class="featured-desc">{{ skill.description }}</div>
                <div class="featured-meta">
                  <el-tag v-if="skill.category" size="small" type="info">{{ skill.category }}</el-tag>
                  <span v-if="skill.downloads" class="meta-stat">📥 {{ skill.downloads }}</span>
                  <span v-if="skill.ai_score" class="meta-stat">⭐ {{ skill.ai_score }}</span>
                  <el-tag v-if="skill.needs_api_key" size="small" type="warning">需 API Key</el-tag>
                </div>
              </el-card>
            </el-space>
          </div>

          <!-- 全部技能 -->
          <div class="skillhub-section">
            <h4 v-if="!skillhubKeyword" style="margin: 16px 0 8px;">热门技能</h4>
            <el-space wrap>
              <el-card
                v-for="skill in skillhubSkills"
                :key="skill.skill_id"
                class="skillhub-skill-card"
                shadow="hover"
              >
                <template #header>
                  <div class="skillhub-skill-header">
                    <span class="skill-name">{{ skill.display_name }}</span>
                    <el-space>
                      <el-tag v-if="skill.needs_api_key" type="warning" size="small">需 Key</el-tag>
                      <el-tag v-if="skill.category" size="small">{{ skill.category }}</el-tag>
                    </el-space>
                  </div>
                </template>
                <p class="skillhub-desc">{{ skill.description }}</p>
                <div class="skillhub-meta">
                  <span v-if="skill.author" class="meta-stat">👤 {{ skill.author }}</span>
                  <span v-if="skill.downloads" class="meta-stat">📥 {{ skill.downloads }}</span>
                  <span v-if="skill.ai_score" class="meta-stat">⭐ {{ skill.ai_score }}</span>
                  <span v-if="skill.version" class="meta-stat">v{{ skill.version }}</span>
                </div>
                <template #footer>
                  <el-space>
                    <el-button size="small" @click="openSkillHubSkill(skill)">查看详情</el-button>
                    <el-button
                      size="small"
                      type="primary"
                      :loading="importingId === skill.skill_id"
                      @click="importFromSkillHub(skill)"
                    >
                      导入
                    </el-button>
                  </el-space>
                </template>
              </el-card>
            </el-space>
          </div>

          <div style="margin-top: 16px; text-align: center;">
            <el-text type="info">
              共 {{ skillhubTotal }} 个技能 · 更多技能请访问
              <el-link type="primary" href="https://skillhub.cloud.tencent.com/skills" target="_blank">
                skillhub.cloud.tencent.com
              </el-link>
            </el-text>
          </div>
        </el-tab-pane>

        <!-- GitHub 仓库浏览 -->
        <el-tab-pane label="GitHub 仓库" name="github">
          <el-form :model="githubForm" label-width="120px">
            <el-row :gutter="12">
              <el-col :span="10">
                <el-form-item label="仓库所有者">
                  <el-input v-model="githubForm.owner" placeholder="例如：trading-agents" />
                </el-form-item>
              </el-col>
              <el-col :span="10">
                <el-form-item label="仓库名">
                  <el-input v-model="githubForm.repo" placeholder="例如：skill-market" />
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-button type="primary" :loading="githubLoading" @click="loadGitHubRepo">
                  浏览
                </el-button>
              </el-col>
            </el-row>
          </el-form>

          <div v-if="githubRepo" class="repo-section">
            <div class="repo-title">
              <el-link :href="`https://github.com/${githubRepo.owner}/${githubRepo.repo}`" target="_blank" type="primary">
                {{ githubRepo.owner }}/{{ githubRepo.repo }}
              </el-link>
              <el-tag v-if="githubRepo.skills.length" type="success" size="small">
                {{ githubRepo.skills.length }} 个 Skill
              </el-tag>
            </div>

            <el-empty v-if="!githubRepo.skills.length" description="该仓库暂未发现 SKILL.md 文件" />

            <el-space v-else wrap>
              <el-card
                v-for="skill in githubRepo.skills"
                :key="skill.path"
                class="skill-item-card"
                shadow="hover"
              >
                <template #header>
                  <div class="skill-item-header">
                    <span class="skill-name">{{ skill.name }}</span>
                    <el-tag size="small">{{ formatFileSize(skill.size) }}</el-tag>
                  </div>
                </template>
                <div class="skill-path">{{ skill.path }}</div>
                <template #footer>
                  <el-space direction="vertical" alignment="start" style="width: 100%;">
                    <el-input
                      v-model="skillTestArgs[skill.path]"
                      type="textarea"
                      :rows="2"
                      size="small"
                      placeholder='测试参数 JSON，如 {"symbol": "000001.SZ"}'
                    />
                    <el-space>
                      <el-button size="small" @click="previewGitHubSkill(skill)">预览</el-button>
                      <el-button size="small" type="primary" :loading="importingId === skill.path" @click="importFromGitHub(skill)">
                        导入并测试
                      </el-button>
                    </el-space>
                  </el-space>
                </template>
              </el-card>
            </el-space>
          </div>
        </el-tab-pane>

        <!-- Smithery MCP Server -->
        <el-tab-pane label="Smithery MCP" name="smithery">
          <div class="smithery-header">
            <el-button type="primary" :loading="smitheryLoading" @click="loadSmitheryServers">
              刷新 MCP Server 列表
            </el-button>
            <el-text type="info">Smithery 是 MCP Server 的分发平台，安装后可在系统中作为外部工具使用</el-text>
          </div>

          <el-empty v-if="!smitheryServers.length && !smitheryLoading" description="点击上方按钮获取 Smithery 上的 MCP Server" />

          <el-space v-else wrap>
            <el-card
              v-for="server in smitheryServers"
              :key="server.id"
              class="skill-item-card smithery-card"
              shadow="hover"
            >
              <template #header>
                <div class="skill-item-header">
                  <span class="skill-name">{{ server.name }}</span>
                  <el-tag type="warning" size="small">MCP</el-tag>
                </div>
              </template>
              <p class="server-description">{{ server.description || '暂无描述' }}</p>
              <div class="tool-count">工具数：{{ server.tools.length }}</div>
              <template #footer>
                <el-button size="small" type="primary" @click="installSmitheryServer(server)">
                  查看安装命令
                </el-button>
              </template>
            </el-card>
          </el-space>
        </el-tab-pane>

        <!-- MCP Hub 中国 -->
        <el-tab-pane label="MCP Hub 中国" name="mcphub">
          <div class="mcphub-header">
            <el-input
              v-model="mcphubKeyword"
              placeholder="搜索 MCP Server..."
              style="width: 300px;"
              clearable
              @keyup.enter="loadMCPHubServers"
            />
            <el-button type="primary" :loading="mcphubLoading" @click="loadMCPHubServers">
              搜索
            </el-button>
            <el-text type="info">mcp-cn.com — 国内精选 MCP Server 市场</el-text>
          </div>

          <el-empty v-if="!mcphubServers.length && !mcphubLoading" description="输入关键词搜索 MCP Server" />

          <el-table v-else :data="mcphubServers" stripe style="width: 100%">
            <el-table-column prop="display_name" label="名称" width="180" />
            <el-table-column prop="description" label="描述" show-overflow-tooltip />
            <el-table-column prop="creator" label="作者" width="120" />
            <el-table-column prop="use_count" label="使用次数" width="100">
              <template #default="{ row }">
                {{ row.use_count?.toLocaleString() || 0 }}
              </template>
            </el-table-column>
            <el-table-column prop="tag" label="标签" width="160">
              <template #default="{ row }">
                <el-tag v-for="t in (row.tag || '').split(',').slice(0, 3)" :key="t" size="small" style="margin: 2px;">
                  {{ t }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="installMCPHubServer(row)">
                  安装
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="mcphubTotal > mcphubPageSize"
            style="margin-top: 16px;"
            :current-page="mcphubPage"
            :page-size="mcphubPageSize"
            :total="mcphubTotal"
            layout="prev, pager, next"
            @current-change="(p: number) => { mcphubPage = p; loadMCPHubServers() }"
          />
        </el-tab-pane>

        <!-- AgentHub / ClawHub -->
        <el-tab-pane label="AgentHub" name="agenthub">
          <div class="agenthub-header">
            <el-input
              v-model="agenthubQuery"
              placeholder="搜索 Skill 或 MCP Server..."
              style="width: 300px;"
              clearable
              @keyup.enter="searchAgentHub"
            />
            <el-select v-model="agenthubTypeFilter" style="width: 140px;" placeholder="类型" clearable>
              <el-option label="全部" value="" />
              <el-option label="Skill" value="skill" />
              <el-option label="MCP Server" value="mcp-server" />
            </el-select>
            <el-button type="primary" :loading="agenthubLoading" @click="searchAgentHub">
              搜索
            </el-button>
            <el-text type="info">agent.xjtool.top — 聚合 ClawHub、MCP Hub 等多源市场</el-text>
          </div>

          <el-empty v-if="!agenthubItems.length && !agenthubLoading" description="输入关键词搜索，如 stock、finance、A股" />

          <el-space v-else wrap>
            <el-card
              v-for="item in agenthubItems"
              :key="item.id"
              class="skill-item-card agenthub-card"
              shadow="hover"
            >
              <template #header>
                <div class="skill-item-header">
                  <span class="skill-name">{{ item.display_name }}</span>
                  <el-space>
                    <el-tag :type="item.type === 'skill' ? 'success' : 'warning'" size="small">
                      {{ item.type === 'skill' ? 'Skill' : 'MCP' }}
                    </el-tag>
                    <el-tag v-if="item.origin === 'clawhub'" type="info" size="small">ClawHub</el-tag>
                  </el-space>
                </div>
              </template>
              <p class="item-description">{{ item.description }}</p>
              <div class="item-meta">
                <span v-if="item.stars">⭐ {{ item.stars }}</span>
                <span v-if="item.downloads">📥 {{ item.downloads?.toLocaleString() }}</span>
                <span v-if="item.installs">🔧 {{ item.installs }}</span>
              </div>
              <template #footer>
                <el-space>
                  <el-button size="small" @click="openAgentHubItem(item)">查看详情</el-button>
                  <el-button
                    v-if="item.type === 'skill'"
                    size="small"
                    type="primary"
                    :loading="importingId === item.pkg_id"
                    @click="importFromAgentHub(item)"
                  >
                    导入
                  </el-button>
                </el-space>
              </template>
            </el-card>
          </el-space>
        </el-tab-pane>

        <!-- URL 导入 -->
        <el-tab-pane label="URL 导入" name="url">
          <el-form :model="urlForm" label-width="120px">
            <el-form-item label="Skill URL">
              <el-input v-model="urlForm.url" placeholder="请输入 SKILL.md 的 URL，支持 GitHub raw 链接" />
            </el-form-item>
            <el-form-item label="测试参数 (JSON)">
              <el-input
                v-model="urlForm.testArgs"
                type="textarea"
                :rows="4"
                placeholder='{"symbol": "000001.SZ"}'
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="urlLoading" @click="importFromUrl">导入并测试</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 上传文件 -->
        <el-tab-pane label="上传文件" name="file">
          <el-upload
            class="upload-demo"
            drag
            action="/api/skills/import"
            :auto-upload="false"
            :on-change="handleFileChange"
          >
            <el-icon class="el-icon-upload"><Upload /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处，或<em>点击上传</em>
            </div>
            <div class="el-upload__tip">支持 .md 或 .json 格式的 Skill 文件</div>
          </el-upload>

          <el-form v-if="uploadFile" label-width="120px" style="margin-top: 16px;">
            <el-form-item label="测试参数 (JSON)">
              <el-input
                v-model="fileForm.testArgs"
                type="textarea"
                :rows="4"
                placeholder='{"symbol": "000001.SZ"}'
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="uploadAndTestFile">导入并测试</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 粘贴内容 -->
        <el-tab-pane label="粘贴内容" name="paste">
          <el-form :model="pasteForm">
            <el-form-item>
              <el-input
                v-model="pasteForm.content"
                type="textarea"
                :rows="12"
                placeholder="粘贴完整的 SKILL.md 内容..."
              />
            </el-form-item>
            <el-form-item label="测试参数 (JSON)" label-width="120px">
              <el-input
                v-model="pasteForm.testArgs"
                type="textarea"
                :rows="4"
                placeholder='{"symbol": "000001.SZ"}'
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pasteLoading" @click="importFromContent">导入并测试</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 推荐 Skill -->
    <el-card class="discover-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>推荐 Skill 来源</span>
          <el-text type="info">常用的 Skill 仓库和 MCP Server 集合</el-text>
        </div>
      </template>
      <el-space wrap>
        <el-card
          v-for="source in recommendedSources"
          :key="source.id"
          class="recommend-card"
          shadow="hover"
        >
          <template #header>
            <el-space>
              <component :is="getSourceIcon(source.type)" />
              <span>{{ source.name }}</span>
            </el-space>
          </template>
          <p>{{ source.description }}</p>
          <template #footer>
            <el-space>
              <el-tag size="small">{{ source.category }}</el-tag>
              <el-button size="small" type="primary" @click="openRecommendedSource(source)">前往</el-button>
            </el-space>
          </template>
        </el-card>
      </el-space>
    </el-card>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewVisible" title="Skill 内容预览" width="700px">
      <el-input v-model="previewContent" type="textarea" :rows="20" readonly />
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 安装命令对话框 -->
    <el-dialog v-model="installVisible" title="MCP Server 安装命令" width="600px">
      <p>{{ installServer?.description }}</p>
      <el-input v-model="installCommand" type="textarea" :rows="3" readonly />
      <template #footer>
        <el-button @click="copyInstallCommand">复制命令</el-button>
        <el-button type="primary" @click="installVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Upload, Collection, MagicStick, Cpu, Link } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { skillsApi, type GitHubRepoSkill, type SmitheryServer, type SkillHubSkill } from '@/api/skills'

const emit = defineEmits<{
  imported: [skillName: string]
}>()

const activeTab = ref('skillhub')

// URL 导入
const urlForm = ref({ url: '', testArgs: '' })
const urlLoading = ref(false)

// 文件导入
const uploadFile = ref<any>(null)
const fileForm = ref({ testArgs: '' })

// 粘贴导入
const pasteForm = ref({ content: '', testArgs: '' })
const pasteLoading = ref(false)

// SkillHub
const skillhubLoading = ref(false)
const skillhubSkills = ref<SkillHubSkill[]>([])
const skillhubFeatured = ref<SkillHubSkill[]>([])
const skillhubKeyword = ref('')
const skillhubTotal = ref('7.1 万')

// GitHub
const githubForm = ref({ owner: '', repo: '' })
const githubLoading = ref(false)
const githubRepo = ref<{ owner: string; repo: string; skills: GitHubRepoSkill[]; readme?: string } | null>(null)
const importingId = ref<string | null>(null)
const skillTestArgs = reactive<Record<string, string>>({})

// Smithery
const smitheryLoading = ref(false)
const smitheryServers = ref<SmitheryServer[]>([])
const installVisible = ref(false)
const installServer = ref<SmitheryServer | null>(null)
const installCommand = ref('')

// MCP Hub 中国
const mcphubLoading = ref(false)
const mcphubServers = ref<any[]>([])
const mcphubKeyword = ref('')
const mcphubPage = ref(1)
const mcphubPageSize = ref(20)
const mcphubTotal = ref(0)

// AgentHub
const agenthubLoading = ref(false)
const agenthubItems = ref<any[]>([])
const agenthubQuery = ref('stock')
const agenthubTypeFilter = ref('')

// 预览
const previewVisible = ref(false)
const previewContent = ref('')

// 推荐来源
const recommendedSources = ref([
  { id: 'skillhub', name: '腾讯 SkillHub', description: '7.1 万个 AI Skills，腾讯官方出品，国内高速下载', category: 'Skill 市场', type: 'mcp', url: 'https://skillhub.cloud.tencent.com/' },
  { id: 'github-skills', name: 'GitHub Skill 仓库', description: '搜索公开的 SKILL.md 仓库并直接导入', category: '代码托管', type: 'github', url: 'https://github.com/search?q=SKILL.md&type=repositories' },
  { id: 'mcphub', name: 'MCP Hub 中国', description: '国内精选 MCP Server 市场，74+ 服务', category: 'MCP 市场', type: 'mcp', url: 'https://www.mcp-cn.com/' },
  { id: 'agenthub', name: 'AgentHub', description: '聚合 ClawHub、MCP Hub 等多源市场，5800+ Skill', category: 'Skill 市场', type: 'mcp', url: 'https://agent.xjtool.top/' },
  { id: 'smithery', name: 'Smithery MCP', description: '国际 MCP Server 分发平台', category: 'MCP 市场', type: 'mcp', url: 'https://smithery.ai/' },
  { id: 'coze', name: '扣子技能商店', description: '字节跳动旗下 Agent 技能市场，含 A 股投资分析技能包', category: 'Skill 市场', type: 'mcp', url: 'https://www.coze.cn/skills' },
  { id: 'modelscope', name: '魔搭 MCP 广场', description: '阿里云旗下，4000+ MCP 服务', category: 'MCP 市场', type: 'mcp', url: 'https://modelscope.cn/stores/mcp' },
  { id: 'local-template', name: '本地模板', description: '从本地上传或粘贴 SKILL.md 内容', category: '本地导入', type: 'local' }
])

function getSourceIcon(type: string) {
  const icons: Record<string, any> = {
    github: Collection,
    mcp: Cpu,
    local: MagicStick
  }
  return icons[type] || Link
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function parseTestArgs(jsonStr: string): Record<string, any> {
  if (!jsonStr.trim()) return {}
  try {
    return JSON.parse(jsonStr)
  } catch {
    ElMessage.warning('测试参数 JSON 格式不正确，将使用空参数测试')
    return {}
  }
}

async function loadGitHubRepo() {
  const { owner, repo } = githubForm.value
  if (!owner || !repo) {
    ElMessage.warning('请输入仓库所有者和仓库名')
    return
  }
  githubLoading.value = true
  try {
    githubRepo.value = await skillsApi.listGitHubRepoSkills(owner, repo)
    if (!githubRepo.value.skills.length) {
      ElMessage.info('该仓库暂未发现 SKILL.md 文件')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取仓库失败')
  } finally {
    githubLoading.value = false
  }
}

async function previewGitHubSkill(skill: GitHubRepoSkill) {
  try {
    const resp = await fetch(skill.raw_url)
    previewContent.value = await resp.text()
    previewVisible.value = true
  } catch {
    ElMessage.error('预览失败')
  }
}

async function importFromGitHub(skill: GitHubRepoSkill) {
  if (!githubRepo.value) return
  importingId.value = skill.path
  try {
    const result = await skillsApi.importFromGitHub({
      owner: githubRepo.value.owner,
      repo: githubRepo.value.repo,
      path: skill.path,
      test_args: parseTestArgs(skillTestArgs[skill.path] || '')
    })
    ElMessage.success(result.message || '导入成功')
    if (result.test_result) {
      showTestResult(result.test_result, result.skill.name)
    }
    emit('imported', result.skill.name)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    importingId.value = null
  }
}

// SkillHub 函数
async function loadSkillHubSkills() {
  skillhubLoading.value = true
  try {
    const result = await skillsApi.listSkillHubSkills({
      keyword: skillhubKeyword.value,
    })
    skillhubSkills.value = result.skills
    skillhubFeatured.value = result.featured
    skillhubTotal.value = result.total
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取 SkillHub 列表失败')
  } finally {
    skillhubLoading.value = false
  }
}

function openSkillHubSkill(skill: SkillHubSkill) {
  window.open(skill.url, '_blank')
}

async function importFromSkillHub(skill: SkillHubSkill) {
  importingId.value = skill.skill_id
  try {
    const result = await skillsApi.importFromSkillHub({
      skill_id: skill.skill_id,
    })
    ElMessage.success(result.message || '导入成功')
    if (result.test_result) {
      showTestResult(result.test_result, result.skill.name)
    }
    emit('imported', result.skill.name)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    importingId.value = null
  }
}

// 初始化加载 SkillHub
loadSkillHubSkills()

async function loadSmitheryServers() {
  smitheryLoading.value = true
  try {
    smitheryServers.value = await skillsApi.listSmitheryServers()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取 Smithery 列表失败')
  } finally {
    smitheryLoading.value = false
  }
}

function installSmitheryServer(server: SmitheryServer) {
  installServer.value = server
  installCommand.value = server.install_command
  installVisible.value = true
}

function copyInstallCommand() {
  navigator.clipboard.writeText(installCommand.value).then(() => {
    ElMessage.success('命令已复制')
  })
}

async function loadMCPHubServers() {
  mcphubLoading.value = true
  try {
    const result = await skillsApi.listMCPHubServers({
      page: mcphubPage.value,
      page_size: mcphubPageSize.value,
      keyword: mcphubKeyword.value,
    })
    mcphubServers.value = result.servers
    mcphubTotal.value = result.total
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取 MCP Hub 列表失败')
  } finally {
    mcphubLoading.value = false
  }
}

function installMCPHubServer(server: any) {
  installServer.value = server
  // 解析 connections 字段生成安装命令
  let cmd = server.connections || ''
  try {
    const conns = JSON.parse(cmd.replace(/'/g, '"'))
    if (conns.length > 0) {
      const c = conns[0]
      if (c.type === 'stdio' && c.config) {
        const parts = [c.config.command, ...(c.config.args || [])]
        cmd = parts.join(' ')
        if (c.config.env) {
          const envVars = Object.entries(c.config.env).map(([k, v]) => `${k}=${v}`)
          cmd = envVars.join(' ') + ' ' + cmd
        }
      }
    }
  } catch {
    // keep original
  }
  installCommand.value = cmd
  installVisible.value = true
}

async function searchAgentHub() {
  agenthubLoading.value = true
  try {
    const result = await skillsApi.searchAgentHub({
      q: agenthubQuery.value,
      type_filter: agenthubTypeFilter.value,
    })
    agenthubItems.value = result.items
    if (!result.items.length) {
      ElMessage.info('未找到相关资源')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '搜索 AgentHub 失败')
  } finally {
    agenthubLoading.value = false
  }
}

function openAgentHubItem(item: any) {
  if (item.source_url) {
    window.open(item.source_url, '_blank')
  }
}

async function importFromAgentHub(item: any) {
  importingId.value = item.pkg_id
  try {
    const result = await skillsApi.importFromAgentHub({
      pkg_id: item.pkg_id,
    })
    ElMessage.success(result.message || '导入成功')
    if (result.test_result) {
      showTestResult(result.test_result, result.skill.name)
    }
    emit('imported', result.skill.name)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    importingId.value = null
  }
}

async function importFromUrl() {
  if (!urlForm.value.url) return
  urlLoading.value = true
  try {
    const imported = await skillsApi.importSkillFromUrl(urlForm.value.url)
    ElMessage.success(`导入成功: ${imported.name}`)
    await testImportedSkill(imported.name, urlForm.value.testArgs)
    emit('imported', imported.name)
    urlForm.value.url = ''
    urlForm.value.testArgs = ''
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    urlLoading.value = false
  }
}

async function handleFileChange(file: any) {
  uploadFile.value = file
}

async function uploadAndTestFile() {
  if (!uploadFile.value?.raw) {
    ElMessage.warning('请先选择文件')
    return
  }
  try {
    const imported = await skillsApi.importSkillFile(uploadFile.value.raw)
    ElMessage.success(`导入成功: ${imported.name}`)
    await testImportedSkill(imported.name, fileForm.value.testArgs)
    emit('imported', imported.name)
    uploadFile.value = null
    fileForm.value.testArgs = ''
  } catch (error: any) {
    console.error('Import failed:', error)
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  }
}

async function importFromContent() {
  if (!pasteForm.value.content) return
  pasteLoading.value = true
  try {
    const imported = await skillsApi.importSkill(pasteForm.value.content)
    ElMessage.success(`导入成功: ${imported.name}`)
    await testImportedSkill(imported.name, pasteForm.value.testArgs)
    emit('imported', imported.name)
    pasteForm.value.content = ''
    pasteForm.value.testArgs = ''
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    pasteLoading.value = false
  }
}

async function testImportedSkill(skillName: string, testArgsJson: string) {
  try {
    const args = parseTestArgs(testArgsJson)
    const result = await skillsApi.testSkill({ skill_name: skillName, args })
    showTestResult(result, skillName)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '测试失败')
  }
}

function showTestResult(result: { success: boolean; result?: any; error?: string; execution_time_ms: number }, skillName: string) {
  if (result.success) {
    ElMessage.success(`Skill「${skillName}」测试通过`)
  } else {
    ElMessage.error(`Skill「${skillName}」测试失败：${result.error || '未知错误'}`)
  }
}

function openRecommendedSource(source: any) {
  if (source.type === 'local') {
    activeTab.value = 'paste'
  } else if (source.url) {
    window.open(source.url, '_blank')
  }
}
</script>

<style scoped>
.skill-discover {
  padding: 20px;
}

.discover-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-tabs {
  margin-top: 20px;
}

.repo-section {
  margin-top: 20px;
}

.repo-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 500;
}

.skill-item-card {
  width: 320px;
}

.skill-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.skill-path {
  color: #909399;
  font-size: 12px;
  word-break: break-all;
  margin-bottom: 8px;
}

.smithery-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.smithery-card .server-description {
  min-height: 40px;
  color: #606266;
  font-size: 14px;
}

.tool-count {
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}

.recommend-card {
  width: 300px;
}

.el-upload {
  border: 2px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.el-upload:hover {
  border-color: #409eff;
}

.skillhub-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.skillhub-section {
  margin-top: 12px;
}

.skillhub-featured-card {
  width: 260px;
  cursor: pointer;
  transition: transform 0.2s;
}
.skillhub-featured-card:hover {
  transform: translateY(-2px);
}
.skillhub-featured-card .featured-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
}
.skillhub-featured-card .featured-desc {
  color: #606266;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  min-height: 36px;
}
.skillhub-featured-card .featured-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}

.skillhub-skill-card {
  width: 320px;
}
.skillhub-skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.skillhub-desc {
  color: #606266;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  min-height: 54px;
}
.skillhub-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}

.meta-stat {
  color: #909399;
  font-size: 12px;
}

.mcphub-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.agenthub-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.agenthub-card .item-description {
  min-height: 40px;
  color: #606266;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.agenthub-card .item-meta {
  display: flex;
  gap: 12px;
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}
</style>
