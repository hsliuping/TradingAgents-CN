'use strict';
/**
 * 将课程文档中的 [待添加截图] 占位符替换为真实的 Markdown 图片引用。
 * 图片路径相对于文档所在目录（即 images/lesson-XX/...）。
 */

const fs = require('fs');
const path = require('path');

const DOCS = path.resolve(__dirname, '../../docs/07-courses/advanced/expanded');

// Mapping: { file, oldFilename, newFilename }
// oldFilename  = the filename in the placeholder
// newFilename  = actual file that exists (same unless screenshot was renamed)
// lessonDir    = subdirectory under images/
const MAP = [
  {
    file: 'lesson-02-basics-evolvable-investment-cycle.md',
    lessonDir: 'lesson-02',
    entries: [
      { old: '02-workflow-01-editor-overview.png', alt: '分析流管理页面概览，展示分析师选择区域' },
    ],
  },
  {
    file: 'lesson-03-stock-selection-single-analysis.md',
    lessonDir: 'lesson-03',
    entries: [
      { old: '03-single-01-page-overview.png',    alt: '单股研究页面全貌' },
      { old: '03-single-03-depth-selection.png',  alt: '分析深度选择' },
      { old: '03-single-04-analyst-checkboxes.png', alt: '分析师选择复选框' },
      { old: '03-single-06-report-overview.png',  alt: '分析报告页面概览' },
      { old: '03-single-07-key-metrics.png',      alt: '关键指标卡片' },
      { old: '03-single-10-bull-bear-debate.png', alt: '多空辩论内容展示' },
      // 03-single-08-research-summary.png doesn't exist → use investment-advice
      { old: '03-single-08-research-summary.png', actual: '03-single-08-investment-advice.png', alt: '研究结论卡片' },
    ],
  },
  {
    file: 'lesson-04-stock-selection-batch-analysis.md',
    lessonDir: 'lesson-04',
    entries: [
      { old: '04-batch-01-page-overview.png',  alt: '批量分析页面全貌' },
      { old: '04-batch-05-task-center.png',    alt: '任务中心页面' },
      { old: '04-batch-04-result-table.png',   alt: '批量分析结果列表' },
    ],
  },
  {
    file: 'lesson-08-timing-multi-agent-debate.md',
    lessonDir: 'lesson-08',
    entries: [
      { old: '08-debate-01-bull-arguments.png',    alt: '看涨研究员观点展示' },
      { old: '08-debate-02-bear-arguments.png',    alt: '看跌研究员观点展示' },
      { old: '08-debate-03-manager-conclusion.png', alt: '研究经理综合结论' },
    ],
  },
  {
    file: 'lesson-10-execution-strategy.md',
    lessonDir: 'lesson-10',
    entries: [
      { old: '10-mock-01-page-overview.png', alt: '模拟交易页面全貌' },
      { old: '10-mock-02-buy-form.png',      alt: '买入表单' },
    ],
  },
  {
    file: 'lesson-11-position-ai-analysis.md',
    lessonDir: 'lesson-11',
    entries: [
      { old: '11-holding-01-page-overview.png', alt: '持仓研究页面全貌' },
      { old: '11-holding-03-ai-analysis.png',   alt: 'AI持仓研究结果展示' },
    ],
  },
  {
    file: 'lesson-15-review-ai-trade-review.md',
    lessonDir: 'lesson-15',
    entries: [
      { old: '15-review-01-page-overview.png', alt: '操作复盘页面全貌' },
      // 15-review-04-score-cards.png doesn't exist → use review-form
      { old: '15-review-04-score-cards.png', actual: '15-review-02-review-form.png', alt: 'AI评分卡片展示' },
      // 15-review-05-timing-analysis.png doesn't exist → use overview
      { old: '15-review-05-timing-analysis.png', actual: '15-review-01-page-overview.png', alt: '时机评分详细分析' },
    ],
  },
];

let total = 0;

for (const { file, lessonDir, entries } of MAP) {
  const filePath = path.join(DOCS, file);
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = 0;

  for (const entry of entries) {
    const { old: oldFilename, actual, alt } = entry;
    const actualFilename = actual || oldFilename;
    const imgPath = `images/${lessonDir}/${actualFilename}`;

    // Files use CRLF (\r\n) line endings.
    // Block pattern:
    //   <!-- 📸 截图占位符 -->\r\n
    //   > **[待添加截图]** `filename.png`\r\n
    //   >\r\n
    //   > 截图说明：...
    const escaped = oldFilename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const NL = '\r\n';
    const re = new RegExp(
      `<!-- 📸 截图占位符 -->\r\n> \\*\\*\\[待添加截图\\]\\*\\* \`${escaped}\`\r\n>\r\n> 截图说明：[^\r\n]+`,
      'g'
    );

    const replacement = `![${alt}](${imgPath})`;
    const newContent = content.replace(re, replacement);
    if (newContent !== content) {
      content = newContent;
      changed++;
      total++;
      console.log(`  ✓ ${file}: ${oldFilename}${actual ? ' → ' + actualFilename : ''}`);
    } else {
      console.log(`  ✗ MISS ${file}: ${oldFilename} (no match)`);
    }
  }

  if (changed > 0) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`  → wrote ${file} (${changed} replacements)`);
  }
}

console.log(`\nDone. Total replacements: ${total}`);
