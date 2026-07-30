/* ==========================================================================
 * TradingAgents v4.0 Prototype-v2 共享 Vue 组件
 * 提供：AppShell（左侧导航 + 顶栏 + 内容容器）+ AssistantDrawer（全局智能助手抽屉）
 * 通过 window.registerPrototypeComponents(app) 注册到 Vue 应用。
 * ========================================================================== */
(function (global) {
  const NAV_GROUPS = [
    {
      title: "研究",
      items: [
        { key: "workspace", label: "今日工作台", icon: "Sunrise", href: "./workspace.html" },
        { key: "discover", label: "候选发现", icon: "Search", href: "./discover.html" },
        { key: "objects", label: "研究对象", icon: "DataAnalysis", href: "./object.html" },
      ],
    },
    {
      title: "执行与沉淀",
      items: [
        { key: "tasks", label: "任务中心", icon: "Operation", href: "./task.html" },
        { key: "library", label: "研究库", icon: "Reading", href: "./library.html" },
      ],
    },
    {
      title: "方法与系统",
      items: [
        { key: "learning", label: "学习中心", icon: "Notebook", href: "./learning.html" },
        { key: "studio", label: "方法工坊", icon: "MagicStick", href: "./studio.html" },
        { key: "control", label: "系统控制台", icon: "Setting", href: "./control.html" },
      ],
    },
  ];

  const AppShell = {
    name: "AppShell",
    props: {
      active: { type: String, required: true },
      pageTitle: { type: String, default: "" },
      breadcrumb: { type: Array, default: () => [] }, // [{label, href?}]
      user: { type: Object, default: () => ({ name: "研究员", initials: "Y" }) },
    },
    data() {
      return {
        navGroups: NAV_GROUPS,
        searchValue: "",
        assistantOpen: false,
      };
    },
    methods: {
      openAssistant() { this.assistantOpen = true; },
      closeAssistant() { this.assistantOpen = false; },
      onQuickNew() {
        ElementPlus.ElMessage.info("快速新建：发起分析 / 创建跟踪 / 记录观点（演示）");
      },
      handleUserCommand(command) {
        const targetMap = {
          profile: "./settings.html?tab=general",
          appearance: "./settings.html?tab=appearance",
          security: "./settings.html?tab=security",
          notifications: "./settings.html?tab=notifications",
          assistant: "./settings.html?tab=assistant",
        };
        if (targetMap[command]) {
          window.location.href = targetMap[command];
          return;
        }
        if (command === "logout") {
          ElementPlus.ElMessage.info("退出登录（原型演示）");
        }
      },
    },
    template: `
      <div class="shell">
        <aside class="shell-aside">
          <div class="brand">
            <div class="brand-mark">TA</div>
            <div class="brand-text">
              TradingAgents
              <small>v4.0 · 本地工作台</small>
            </div>
          </div>
          <div class="nav-section">
            <template v-for="group in navGroups" :key="group.title">
              <div class="nav-group-title">{{ group.title }}</div>
              <a
                v-for="item in group.items"
                :key="item.key"
                :href="item.href"
                class="nav-item"
                :class="{ 'is-active': item.key === active }"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </a>
            </template>
          </div>
          <div class="aside-footer">
            <div class="system-status">
              <span class="dot"></span>
              <span>系统正常</span>
            </div>
            <span>v4.0.0-α</span>
          </div>
        </aside>

        <div class="shell-main">
          <header class="shell-header">
            <div class="left">
              <div class="breadcrumb">
                <template v-if="breadcrumb.length">
                  <template v-for="(crumb, i) in breadcrumb" :key="i">
                    <a v-if="crumb.href" :href="crumb.href">{{ crumb.label }}</a>
                    <span v-else>{{ crumb.label }}</span>
                    <span v-if="i < breadcrumb.length - 1"> / </span>
                  </template>
                  <span v-if="pageTitle"> / <b>{{ pageTitle }}</b></span>
                </template>
                <b v-else>{{ pageTitle }}</b>
              </div>
            </div>
            <div class="center">
              <el-input
                v-model="searchValue"
                placeholder="搜索股票、主题、报告、研究卡片…（按 / 聚焦）"
                size="default"
                clearable
              >
                <template #prefix><el-icon><Search /></el-icon></template>
                <template #suffix><span class="text-xs muted">⌘ K</span></template>
              </el-input>
            </div>
            <div class="right">
              <el-button type="primary" plain size="default" @click="onQuickNew">
                <el-icon><Plus /></el-icon>&nbsp;快速新建
              </el-button>
              <span class="icon-btn" title="通知"><el-icon><Bell /></el-icon></span>
              <span class="icon-btn" title="帮助"><el-icon><QuestionFilled /></el-icon></span>
              <el-dropdown trigger="click" @command="handleUserCommand">
                <div class="user-chip">
                  <div class="avatar">{{ user.initials }}</div>
                  <span class="name">{{ user.name }}</span>
                  <el-icon><CaretBottom /></el-icon>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile"><el-icon><User /></el-icon>&nbsp;个人设置</el-dropdown-item>
                    <el-dropdown-item command="appearance"><el-icon><Brush /></el-icon>&nbsp;个性化设置</el-dropdown-item>
                    <el-dropdown-item command="security"><el-icon><Lock /></el-icon>&nbsp;安全设置</el-dropdown-item>
                    <el-dropdown-item command="notifications"><el-icon><Bell /></el-icon>&nbsp;通知偏好</el-dropdown-item>
                    <el-dropdown-item command="assistant"><el-icon><ChatDotRound /></el-icon>&nbsp;助理设置</el-dropdown-item>
                    <el-dropdown-item command="logout" :divided="true"><el-icon><SwitchButton /></el-icon>&nbsp;退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </header>

          <main class="shell-content">
            <slot />
          </main>
        </div>

        <div class="assistant-fab" @click="openAssistant" title="智能助手">
          <el-icon><ChatDotRound /></el-icon>
        </div>

        <assistant-drawer
          v-model:visible="assistantOpen"
          :context-label="pageTitle || '当前页面'"
        />
      </div>
    `,
  };

  const AssistantDrawer = {
    name: "AssistantDrawer",
    props: {
      visible: Boolean,
      contextLabel: { type: String, default: "" },
    },
    emits: ["update:visible"],
    data() {
      return {
        input: "",
        thread: [
          {
            role: "ai",
            text: "你好，我是研究助手。我可以基于当前页面的上下文协作 —— 例如帮你整理时间线、生成观点草稿、把分析结论沉淀为规则。",
            meta: "11:08 · 上下文：" + (this.contextLabel || "工作台"),
          },
          {
            role: "user",
            text: "把上一次招行分析的结论改写成一条投资规则草稿",
            meta: "11:09",
          },
          {
            role: "ai",
            text: "我基于上次分析整理了一条规则草稿，需要你确认后才会写入「我的规则」。",
            meta: "11:09 · 草稿不会自动入库",
            draft: {
              type: "规则草稿",
              title: "银行股配置：核心一级资本充足率底线",
              content: "当跟踪银行股核心一级资本充足率连续两个季度低于 9% 时，自动加入「重点观察」并降低配置权重至原仓位的 50%。",
              source: "来源：招行 2026Q1 分析任务 #4823 复盘结论",
            },
          },
        ],
        suggestions: [
          "整理今日变化",
          "生成观点草稿",
          "对比历史复盘",
          "解释这条数据",
        ],
      };
    },
    computed: {
      drawerVisible: {
        get() { return this.visible; },
        set(v) { this.$emit("update:visible", v); },
      },
    },
    methods: {
      send() {
        if (!this.input.trim()) return;
        this.thread.push({ role: "user", text: this.input, meta: "刚刚" });
        this.input = "";
        this.$nextTick(() => {
          this.thread.push({
            role: "ai",
            text: '（演示）助手会基于当前上下文给出回答，并把任何"对象 / 规则 / 观点"的修改包装成需要用户确认的草稿，不会直接写入研究库。',
            meta: "刚刚 · 演示数据",
          });
        });
      },
      pickSug(s) { this.input = s; },
      acceptDraft(msg) {
        ElementPlus.ElMessage.success("已写入「我的规则」（演示）");
        msg.draft = null;
      },
      discardDraft(msg) {
        ElementPlus.ElMessage.info("已丢弃草稿");
        msg.draft = null;
      },
    },
    template: `
      <el-drawer
        v-model="drawerVisible"
        title="研究助手"
        direction="rtl"
        size="420px"
        class="assistant-drawer"
        :with-header="true"
      >
        <div class="assistant-context">
          <el-icon><Link /></el-icon>
          上下文已绑定：{{ contextLabel }}
        </div>
        <div class="assistant-thread">
          <div
            v-for="(msg, i) in thread"
            :key="i"
            class="assistant-msg"
            :class="msg.role === 'user' ? 'is-user' : 'is-ai'"
          >
            <div class="a-avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
            <div style="flex:1; min-width:0;">
              <div class="a-bubble">{{ msg.text }}</div>
              <div class="a-meta">{{ msg.meta }}</div>
              <div v-if="msg.draft" class="assistant-draft">
                <div class="draft-label">
                  <el-icon><EditPen /></el-icon>{{ msg.draft.type }}（待确认）
                </div>
                <div class="fw-600 mb-2">{{ msg.draft.title }}</div>
                <div class="text-sm muted" style="line-height:1.6;">{{ msg.draft.content }}</div>
                <div class="source-line">{{ msg.draft.source }}</div>
                <div class="draft-actions">
                  <el-button type="primary" size="small" @click="acceptDraft(msg)">
                    确认写入研究库
                  </el-button>
                  <el-button size="small" text @click="discardDraft(msg)">丢弃</el-button>
                  <el-button size="small" text>修改后再确认</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="assistant-input">
          <div class="assistant-suggestions">
            <span
              v-for="s in suggestions"
              :key="s"
              class="sug-chip"
              @click="pickSug(s)"
            >{{ s }}</span>
          </div>
          <div class="input-row">
            <el-input
              v-model="input"
              placeholder="提问、或让助手做一件事…"
              type="textarea"
              :rows="2"
              resize="none"
              @keydown.enter.exact.prevent="send"
            />
            <el-button type="primary" @click="send">
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="text-xs muted mt-3" style="line-height:1.5;">
            助手生成的观点 / 规则 / 计划默认为草稿，必须经你确认才会进入研究库或修改对象状态。
          </div>
        </div>
      </el-drawer>
    `,
  };

  global.registerPrototypeComponents = function (app) {
    app.component("AppShell", AppShell);
    app.component("AssistantDrawer", AssistantDrawer);
  };
})(window);
