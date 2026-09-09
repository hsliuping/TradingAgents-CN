<template>
  <div class="skills-page">
    <div class="page-header">
      <div class="header-left">
        <h1>
          <el-icon class="header-icon"><MagicStick /></el-icon>
          Skill 管理
        </h1>
        <span class="subtitle">管理 Agent Skills：导入、配置和启用/禁用</span>
      </div>
      <div class="header-right">
        <el-button type="success" @click="showImportDialog">
          <el-icon><Upload /></el-icon>
          导入 SKILL.md
        </el-button>
        <el-button type="warning" @click="showImportUrlDialog">
          <el-icon><Link /></el-icon>
          从网络获取
        </el-button>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建 Skill
        </el-button>
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 筛选区 -->
    <div class="filter-section">
      <el-radio-group v-model="filterCategory" @change="handleFilterChange">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat.id" :label="cat.id">
          {{ cat.name }} ({{ cat.count }})
        </el-radio-button>
      </el-radio-group>
      <div class="filter-extra">
        <el-select v-model="filterType" placeholder="Skill 类型" clearable size="default" style="width: 140px; margin-right: 8px;">
          <el-option label="全部类型" value="" />
          <el-option label="知识型" value="knowledge" />
          <el-option label="Python" value="python" />
          <el-option label="HTTP" value="http" />
          <el-option label="MCP" value="mcp" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="状态" clearable size="default" style="width: 120px;">
          <el-option label="全部状态" value="" />
          <el-option label="已启用" value="true" />
          <el-option label="已禁用" value="false" />
        </el-select>
      </div>
    </div>

    <!-- Skill 列表 -->
    <el-table v-loading="loading" :data="filteredSkills" style="width: 100%" border stripe>
      <el-table-column prop="name" label="Skill 名称" min-width="180">
        <template #default="{ row }">
          <div class="skill-name">
            <span class="skill-icon">{{ row.icon || '🔧' }}</span>
            <span class="name-text">{{ row.name }}</span>
            <el-tag v-if="row.is_builtin" type="warning" size="small" style="margin-left: 5px">内置</el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />

      <el-table-column prop="category" label="分类" width="110">
        <template #default="{ row }">
          <el-tag>{{ row.category }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="skill_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="getSkillTypeTag(row.skill_type)">{{ getSkillTypeLabel(row.skill_type) }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="enabled" label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" :disabled="row.is_builtin" @change="(val) => handleToggle(row, Boolean(val))" size="small" />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="showDetail(row)">详情</el-button>
          <el-button type="primary" link @click="handleExport(row)">导出</el-button>
          <template v-if="!row.is_builtin">
            <el-button type="primary" link @click="showEditDialog(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" :title="'Skill 详情: ' + (detailSkill?.name || '')" width="700px" destroy-on-close>
      <div v-if="detailSkill" class="skill-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="名称">{{ detailSkill.name }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ detailSkill.version }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ detailSkill.category }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="getSkillTypeTag(detailSkill.skill_type)">{{ getSkillTypeLabel(detailSkill.skill_type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="作者">{{ detailSkill.author || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detailSkill.enabled ? 'success' : 'info'">{{ detailSkill.enabled ? '启用' : '禁用' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailSkill.description }}</el-descriptions-item>
          <el-descriptions-item label="何时使用" :span="2" v-if="detailSkill.when_to_use">{{ detailSkill.when_to_use }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailSkill.parameters?.length" class="detail-section">
          <h4>参数定义</h4>
          <el-table :data="detailSkill.parameters" size="small" border>
            <el-table-column prop="name" label="参数名" width="120" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="required" label="必填" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="row.required ? 'danger' : 'info'" size="small">{{ row.required ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="detailSkill.implementation" class="detail-section">
          <h4>执行实现</h4>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="协议">{{ detailSkill.implementation.type }}</el-descriptions-item>
            <el-descriptions-item v-if="detailSkill.implementation.url" label="URL">{{ detailSkill.implementation.url }}</el-descriptions-item>
            <el-descriptions-item v-if="detailSkill.implementation.method" label="Method">{{ detailSkill.implementation.method }}</el-descriptions-item>
            <el-descriptions-item v-if="detailSkill.implementation.module" label="Module">{{ detailSkill.implementation.module }}</el-descriptions-item>
            <el-descriptions-item v-if="detailSkill.implementation.function" label="Function">{{ detailSkill.implementation.function }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="detailSkill.instructions" class="detail-section">
          <h4>指令说明</h4>
          <div class="instructions-content">{{ detailSkill.instructions }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog
      v-model="importVisible"
      :title="importTab === 'url' ? '从网络获取 Skill' : '导入 SKILL.md'"
      :width="importTab === 'url' ? 720 : 650"
      destroy-on-close
    >
      <el-tabs v-model="importTab">
        <el-tab-pane label="粘贴内容" name="paste">
          <el-input v-model="importContent" type="textarea" :rows="14" placeholder="粘贴 SKILL.md 文件内容..." />
        </el-tab-pane>
        <el-tab-pane label="上传文件" name="upload">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".md"
            :on-change="handleFileChange"
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 .md 文件（SKILL.md 格式）</div>
            </template>
          </el-upload>
        </el-tab-pane>
        <el-tab-pane label="从网络获取" name="url">
          <div class="import-url-section">
            <div class="sources-header">
              <span class="sources-title">推荐 Skill 来源</span>
              <span class="sources-hint">访问下方网站，找到想要的 Skill 后复制其直链 URL 粘贴到输入框</span>
            </div>
            <div class="skill-sources">
              <div
                v-for="src in skillSources"
                :key="src.id"
                class="source-card"
              >
                <div class="source-main">
                  <span class="source-icon">{{ src.icon }}</span>
                  <div class="source-info">
                    <span class="source-name">{{ src.name }}</span>
                    <span class="source-desc">{{ src.desc }}</span>
                    <span class="source-hint">{{ src.hint }}</span>
                  </div>
                  <el-button
                    type="primary"
                    link
                    :icon="Link"
                    @click="openSource(src.url)"
                  >
                    访问
                  </el-button>
                </div>
              </div>
            </div>
            <el-divider>粘贴 URL 并导入</el-divider>
            <el-input
              v-model="importUrl"
              placeholder="从上述网站复制 SKILL.md 的直链 URL 粘贴到此，如：https://raw.githubusercontent.com/..."
              clearable
              @keyup.enter="handleImportFromUrl"
            />
            <div class="import-url-tip">
              支持 GitHub raw 链接；若为 GitHub 网页链接（含 /blob/），将自动转为 raw 地址。
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button
          v-if="importTab === 'url'"
          type="primary"
          :loading="importUrlLoading"
          :disabled="!importUrl.trim()"
          @click="handleImportFromUrl"
        >
          获取并导入
        </el-button>
        <el-button v-else type="primary" :loading="importLoading" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="formVisible" :title="formMode === 'create' ? '新建 Skill' : '编辑 Skill'" width="700px" destroy-on-close>
      <el-form :model="skillForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="skillForm.name" placeholder="skill-name（小写、连字符分隔）" :disabled="formMode === 'edit'" />
        </el-form-item>
        <el-form-item label="描述" required>
          <el-input v-model="skillForm.description" type="textarea" :rows="2" placeholder="描述 Skill 做什么以及何时使用" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="skillForm.category" placeholder="general" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="skillForm.version" placeholder="1.0.0" style="width: 200px" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="skillForm.author" placeholder="可选" />
        </el-form-item>
        <el-form-item label="何时使用">
          <el-input v-model="skillForm.when_to_use" type="textarea" :rows="2" placeholder="描述什么情况下应使用这个 Skill" />
        </el-form-item>
        <el-form-item label="指令说明">
          <el-input v-model="skillForm.instructions" type="textarea" :rows="4" placeholder="Markdown 格式的详细指令" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="skillForm.enabled" />
        </el-form-item>
        <el-form-item label="Function Call">
          <el-switch v-model="skillForm.fc_enabled" />
          <span style="margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px;">启用后可被智能助手自动调用</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSaveSkill">{{ formMode === 'create' ? '创建' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <!-- 导出对话框 -->
    <el-dialog v-model="exportVisible" title="导出 SKILL.md" width="650px">
      <el-input v-model="exportContent" type="textarea" :rows="16" readonly />
      <template #footer>
        <el-button @click="exportVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyExportContent">复制内容</el-button>
        <el-button type="success" @click="downloadExport">下载文件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Refresh, Upload, Plus, Link } from '@element-plus/icons-vue'
import { skillsApi, type SkillData, type SkillCategory } from '@/api/skills'

const loading = ref(false)
const skills = ref<SkillData[]>([])
const categories = ref<SkillCategory[]>([])

// 筛选
const filterCategory = ref('')
const filterType = ref('')
const filterEnabled = ref('')

// 详情
const detailVisible = ref(false)
const detailSkill = ref<SkillData | null>(null)

// 导入
const importVisible = ref(false)
const importTab = ref('paste')
const importContent = ref('')
const importFile = ref<File | null>(null)
const importLoading = ref(false)
const importUrl = ref('')
const importUrlLoading = ref(false)
const uploadRef = ref()

// 创建/编辑
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formLoading = ref(false)
const editingSkillName = ref('')
const skillForm = reactive({
  name: '',
  description: '',
  category: 'general',
  version: '1.0.0',
  author: '',
  when_to_use: '',
  instructions: '',
  enabled: true,
  fc_enabled: true,
})

// 导出
const exportVisible = ref(false)
const exportContent = ref('')
const exportFilename = ref('')

// 推荐 Skill 来源（从网络获取时展示）
const skillSources = [
  {
    id: 'agent-skills-md',
    name: 'Agent-Skills.md',
    desc: '最大的 Agent Skill 市场，18,000+ 技能，可按 React、TypeScript、UI 等分类搜索',
    hint: '进入 Skill 详情页，在页面中找到 raw 或 direct 链接，或从 GitHub 仓库获取 raw URL',
    url: 'https://agent-skills.md/',
    icon: '📦'
  },
  {
    id: 'anthropics-skills',
    name: 'Anthropic 官方示例',
    desc: 'Claude/Agent Skills 官方仓库，文档创建、MCP 生成、Web 测试等示例',
    hint: '打开 skills/ 下的 SKILL.md 文件，点击 Raw 获取直链，复制地址栏 URL',
    url: 'https://github.com/anthropics/skills/tree/main/skills',
    icon: '🏛️'
  },
  {
    id: 'agentskills-io',
    name: 'agentskills.io',
    desc: 'Agent Skills 开放格式规范与参考，包含示例和验证工具',
    hint: '查看文档与示例，从 GitHub 链接进入对应 SKILL.md 的 Raw 页面',
    url: 'https://agentskills.io/',
    icon: '📐'
  },
  {
    id: 'cursor-how',
    name: 'Cursor How - Agent Skills Hub',
    desc: '现成 Playbooks：PPT、Excel、Word、PDF 文档生成等',
    hint: '浏览 Playbooks，从关联的 GitHub 或示例链接获取 SKILL.md raw URL',
    url: 'https://www.cursorhow.com/agent-skills-hub',
    icon: '📋'
  }
]

const openSource = (url: string) => {
  window.open(url, '_blank', 'noopener')
}

// 计算：过滤后的 Skill 列表
const filteredSkills = computed(() => {
  let result = skills.value
  if (filterCategory.value) {
    result = result.filter(s => s.category === filterCategory.value)
  }
  if (filterType.value) {
    result = result.filter(s => s.skill_type === filterType.value)
  }
  if (filterEnabled.value !== '') {
    const enabled = filterEnabled.value === 'true'
    result = result.filter(s => s.enabled === enabled)
  }
  return result
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const [skillsData, categoriesData] = await Promise.all([
      skillsApi.listSkills(),
      skillsApi.listCategories()
    ])
    skills.value = skillsData
    categories.value = categoriesData
  } catch (error) {
    console.error('加载 Skills 失败:', error)
    ElMessage.error('加载 Skill 列表失败')
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => { /* radio-group triggers reactivity */ }

// 类型标签
const getSkillTypeTag = (type: string) => {
  const map: Record<string, string> = { knowledge: 'info', python: '', http: 'success', mcp: 'warning' }
  return (map[type] || 'info') as any
}
const getSkillTypeLabel = (type: string) => {
  const map: Record<string, string> = { knowledge: '知识型', python: 'Python', http: 'HTTP', mcp: 'MCP' }
  return map[type] || type
}

// 详情
const showDetail = (skill: SkillData) => {
  detailSkill.value = skill
  detailVisible.value = true
}

// 启用/禁用
const handleToggle = async (skill: SkillData, val: boolean) => {
  try {
    await skillsApi.toggleSkill(skill.name, val)
    ElMessage.success(`Skill '${skill.name}' 已${val ? '启用' : '禁用'}`)
  } catch (error) {
    skill.enabled = !val  // 回滚
    ElMessage.error('操作失败')
  }
}

// 导入
const showImportDialog = () => {
  importContent.value = ''
  importFile.value = null
  importUrl.value = ''
  importTab.value = 'paste'
  importVisible.value = true
}

const showImportUrlDialog = () => {
  importUrl.value = ''
  importTab.value = 'url'
  importVisible.value = true
}

const handleFileChange = (file: any) => {
  importFile.value = file.raw
}

const handleImport = async () => {
  importLoading.value = true
  try {
    if (importTab.value === 'paste') {
      if (!importContent.value.trim()) {
        ElMessage.warning('请粘贴 SKILL.md 内容')
        return
      }
      await skillsApi.importSkill(importContent.value)
    } else {
      if (!importFile.value) {
        ElMessage.warning('请选择文件')
        return
      }
      await skillsApi.importSkillFile(importFile.value)
    }
    ElMessage.success('导入成功')
    importVisible.value = false
    loadData()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导入失败')
  } finally {
    importLoading.value = false
  }
}

const handleImportFromUrl = async () => {
  if (!importUrl.value.trim()) {
    ElMessage.warning('请输入 SKILL.md 的 URL')
    return
  }
  importUrlLoading.value = true
  try {
    await skillsApi.importSkillFromUrl(importUrl.value.trim())
    ElMessage.success('从网络获取并导入成功')
    importVisible.value = false
    loadData()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取失败')
  } finally {
    importUrlLoading.value = false
  }
}


// 创建
const showCreateDialog = () => {
  formMode.value = 'create'
  skillForm.name = ''
  skillForm.description = ''
  skillForm.category = 'general'
  skillForm.version = '1.0.0'
  skillForm.author = ''
  skillForm.when_to_use = ''
  skillForm.instructions = ''
  skillForm.enabled = true
  skillForm.fc_enabled = true
  formVisible.value = true
}

// 编辑
const showEditDialog = (skill: SkillData) => {
  formMode.value = 'edit'
  editingSkillName.value = skill.name
  skillForm.name = skill.name
  skillForm.description = skill.description
  skillForm.category = skill.category
  skillForm.version = skill.version
  skillForm.author = skill.author
  skillForm.when_to_use = skill.when_to_use
  skillForm.instructions = skill.instructions
  skillForm.enabled = skill.enabled
  skillForm.fc_enabled = skill.fc_enabled
  formVisible.value = true
}

// 保存（创建/编辑）
const handleSaveSkill = async () => {
  if (!skillForm.name.trim() || !skillForm.description.trim()) {
    ElMessage.warning('名称和描述为必填项')
    return
  }
  formLoading.value = true
  try {
    if (formMode.value === 'create') {
      await skillsApi.createSkill({ ...skillForm })
      ElMessage.success('创建成功')
    } else {
      await skillsApi.updateSkill(editingSkillName.value, { ...skillForm })
      ElMessage.success('更新成功')
    }
    formVisible.value = false
    loadData()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '操作失败')
  } finally {
    formLoading.value = false
  }
}

// 删除
const handleDelete = async (skill: SkillData) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 Skill '${skill.name}' 吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
    await skillsApi.deleteSkill(skill.name)
    ElMessage.success('删除成功')
    loadData()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  }
}

// 导出
const handleExport = async (skill: SkillData) => {
  try {
    const result = await skillsApi.exportSkill(skill.name)
    exportContent.value = result.content
    exportFilename.value = result.filename
    exportVisible.value = true
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const copyExportContent = () => {
  navigator.clipboard.writeText(exportContent.value)
  ElMessage.success('已复制到剪贴板')
}

const downloadExport = () => {
  const blob = new Blob([exportContent.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = exportFilename.value || 'SKILL.md'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.skills-page {
  padding: 20px;
  background-color: var(--el-bg-color);
  min-height: calc(100vh - 60px);

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .header-left {
      h1 {
        display: flex;
        align-items: center;
        font-size: 24px;
        margin: 0 0 8px 0;

        .header-icon {
          margin-right: 12px;
          color: var(--el-color-primary);
        }
      }

      .subtitle {
        color: var(--el-text-color-secondary);
        font-size: 14px;
      }
    }
  }

  .filter-section {
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;

    .filter-extra {
      display: flex;
      align-items: center;
    }
  }

  .skill-name {
    display: flex;
    align-items: center;

    .skill-icon {
      font-size: 18px;
      margin-right: 8px;
    }

    .name-text {
      font-weight: 500;
    }
  }
}

.import-url-section {
  padding: 8px 0;

  .sources-header {
    margin-bottom: 16px;

    .sources-title {
      display: block;
      font-weight: 600;
      font-size: 15px;
      color: var(--el-text-color-primary);
      margin-bottom: 6px;
    }

    .sources-hint {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      line-height: 1.5;
    }
  }

  .skill-sources {
    max-height: 280px;
    overflow-y: auto;
    margin-bottom: 16px;
  }

  .source-card {
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    background: var(--el-fill-color-blank);
    transition: border-color 0.2s;

    &:hover {
      border-color: var(--el-color-primary-light-5);
    }

    .source-main {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }

    .source-icon {
      font-size: 24px;
      flex-shrink: 0;
    }

    .source-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;

      .source-name {
        font-weight: 600;
        font-size: 14px;
        color: var(--el-text-color-primary);
      }

      .source-desc {
        font-size: 13px;
        color: var(--el-text-color-regular);
        line-height: 1.5;
      }

      .source-hint {
        font-size: 12px;
        color: var(--el-text-color-secondary);
        margin-top: 4px;
      }
    }
  }

  .el-input {
    margin-bottom: 8px;
  }

  .import-url-tip {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
  }
}

.skill-detail {
  .detail-section {
    margin-top: 20px;

    h4 {
      font-size: 15px;
      margin-bottom: 10px;
      border-left: 3px solid var(--el-color-primary);
      padding-left: 8px;
    }
  }

  .instructions-content {
    background-color: var(--el-fill-color-light);
    border-radius: 6px;
    padding: 12px 16px;
    white-space: pre-wrap;
    font-size: 13px;
    line-height: 1.6;
    max-height: 300px;
    overflow-y: auto;
  }
}
</style>