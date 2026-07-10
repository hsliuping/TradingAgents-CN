'use strict';

const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const IMGS = path.resolve(__dirname, '../../docs/07-courses/advanced/expanded/images');
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const mkd = (p) => fs.mkdirSync(p, { recursive: true });
let done = 0, failed = 0;

// Navigate to URL and wait for page to settle
async function nav(page, url, timeout = 10000) {
  await page.goto(BASE + url);
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch (_) {}
  await page.waitForTimeout(1200);
}

// Take screenshot – element-level if selector visible, else full viewport
async function shot(page, dir, file, opts = {}) {
  const { sel = null, full = false, t = 0 } = opts;
  if (t > 0) await page.waitForTimeout(t);
  mkd(path.join(IMGS, dir));
  const out = path.join(IMGS, dir, file);
  try {
    if (sel) {
      const loc = page.locator(sel).first();
      const ok = await loc.isVisible({ timeout: 3000 }).catch(() => false);
      if (ok) {
        await loc.screenshot({ path: out });
        console.log(`  ✓ [elem] ${dir}/${file}`);
        done++;
        return;
      }
    }
    await page.screenshot({ path: out, fullPage: full });
    console.log(`  ✓ [page] ${dir}/${file}`);
    done++;
  } catch (e) {
    console.log(`  ✗ [fail] ${dir}/${file}: ${e.message.split('\n')[0]}`);
    failed++;
  }
}

async function main() {
  console.log(`Edge path: ${EDGE_PATH}`);
  console.log(`Images dir: ${IMGS}\n`);

  const browser = await chromium.launch({
    executablePath: EDGE_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai'
  });

  const page = await ctx.newPage();

  // Suppress console noise from app
  page.on('console', () => {});
  page.on('pageerror', () => {});

  try {
    // ────────────────────────────────────────────────────────────────────────
    //  COMMON
    // ────────────────────────────────────────────────────────────────────────
    console.log('=== [common] ===');

    await nav(page, '/login');
    await shot(page, 'common', 'common-01-login-page.png');

    // ── Login ──
    await page.evaluate(() => localStorage.setItem('terms-accepted', 'true'));
    await nav(page, '/login');
    await page.locator('input[placeholder="请输入用户名"]').fill('admin');
    await page.locator('input[placeholder="请输入密码"]').fill('admin123');
    await page.locator('button:has-text("登录")').click();
    await page.waitForURL(BASE + '/dashboard', { timeout: 18000 }).catch(() => page.waitForTimeout(5000));
    console.log('  ✓ Logged in');

    await nav(page, '/dashboard');
    await shot(page, 'common', 'common-02-main-dashboard.png');

    // Ensure sidebar is NOT collapsed for the sidebar screenshot
    const isCollapsed = await page.locator('.sidebar.collapsed').isVisible({ timeout: 1000 }).catch(() => false);
    if (isCollapsed) {
      await page.locator('.sidebar-toggle').click().catch(() => {});
      await page.waitForTimeout(600);
    }
    await shot(page, 'common', 'common-03-left-menu.png', { sel: '.sidebar' });

    await nav(page, '/settings');
    await shot(page, 'common', 'common-04-user-settings.png');

    await nav(page, '/settings/config');
    await shot(page, 'common', 'common-05-system-config.png');

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 02: Workflow / 分析流
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-02] ===');

    await nav(page, '/workflow');
    await shot(page, 'lesson-02', '02-workflow-01-editor-overview.png');
    await shot(page, 'lesson-02', '02-workflow-03-analyst-selection.png', { sel: '.el-card:first-child, .workflow-card' });

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 03: Single stock analysis
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-03] ===');

    await nav(page, '/analysis/single');
    await shot(page, 'lesson-03', '03-single-01-page-overview.png');
    // Stock input area (top of the form)
    await shot(page, 'lesson-03', '03-single-02-stock-input.png', { sel: '.el-form-item:first-child, .stock-input-row' });
    await shot(page, 'lesson-03', '03-single-03-depth-selection.png', { sel: '.depth-selector' });
    await shot(page, 'lesson-03', '03-single-04-analyst-checkboxes.png', { sel: '.analysts-grid' });

    // Check for existing reports (analysis results)
    await nav(page, '/reports');
    const firstReport = page.locator('.el-table__row, .el-table-row, .report-row').first();
    const hasReport = await firstReport.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasReport) {
      console.log('  → Found existing reports, opening first...');
      await firstReport.click().catch(() => {});
      await page.waitForTimeout(2500);

      await shot(page, 'lesson-03', '03-single-06-report-overview.png');
      await shot(page, 'lesson-03', '03-single-07-key-metrics.png', { sel: '.key-metrics, .metrics-cards, .summary-cards' });
      await shot(page, 'lesson-03', '03-single-08-investment-advice.png', { sel: '.research-conclusion, .investment-advice, .conclusion-card, .el-card:last-child' });
      await shot(page, 'lesson-03', '03-single-10-bull-bear-debate.png', { sel: '.bull-bear, .debate-section, [class*="bull"], [class*="debate"]' });
      // Scroll down to capture more detail sections
      await page.evaluate(() => window.scrollTo(0, window.innerHeight));
      await page.waitForTimeout(800);
      await shot(page, 'lesson-03', '03-single-09-detailed-reports.png');
      // Scroll back up
      await page.evaluate(() => window.scrollTo(0, 0));
      await shot(page, 'lesson-09', '09-position-01-advice-display.png', { sel: '.position-advice, .recommendation, [class*="position"]' });
      await shot(page, 'lesson-13', '13-risk-04-risk-manager.png', { sel: '.risk-section, [class*="risk"]' });
      await shot(page, 'lesson-14', '14-stoploss-01-price-display.png', { sel: '.price-levels, [class*="price"], [class*="stop"]' });
      await shot(page, 'lesson-08', '08-debate-05-final-decision.png', { sel: '.final-decision, .research-manager, [class*="final"]' });
    } else {
      console.log('  → No reports found, taking empty-state screenshots');
      await shot(page, 'lesson-03', '03-single-06-report-overview.png');
      await shot(page, 'lesson-08', '08-debate-05-final-decision.png');
      await shot(page, 'lesson-09', '09-position-01-advice-display.png');
      await shot(page, 'lesson-13', '13-risk-04-risk-manager.png');
      await shot(page, 'lesson-14', '14-stoploss-01-price-display.png');
    }

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 04: Batch analysis
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-04] ===');

    await nav(page, '/analysis/batch');
    await shot(page, 'lesson-04', '04-batch-01-page-overview.png');
    await shot(page, 'lesson-04', '04-batch-02-stock-list-input.png', { sel: '.el-form, .batch-form, .input-section' });

    await nav(page, '/tasks/unified');
    await shot(page, 'lesson-04', '04-batch-05-task-center.png');
    await shot(page, 'lesson-04', '04-batch-04-result-table.png', { sel: '.el-table, .task-list' });

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 05: Analyst config
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-05] ===');

    await nav(page, '/analysis/single');
    await page.waitForTimeout(1500);
    await shot(page, 'lesson-05', '05-config-01-short-term-analysts.png', { sel: '.analysts-grid' });
    await shot(page, 'lesson-05', '05-config-02-long-term-analysts.png', { sel: '.analysts-grid' });

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 06-08: Market / debate analysis (from reports or empty state)
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-06-08] ===');

    await nav(page, '/reports');
    await shot(page, 'lesson-06', '06-market-01-index-analysis.png');
    await shot(page, 'lesson-07', '07-sector-01-industry-analysis.png');
    await shot(page, 'lesson-08', '08-debate-01-bull-arguments.png');
    await shot(page, 'lesson-08', '08-debate-02-bear-arguments.png');
    await shot(page, 'lesson-08', '08-debate-03-manager-conclusion.png');

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 10: Paper / mock trading
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-10] ===');

    await nav(page, '/paper');
    await shot(page, 'lesson-10', '10-mock-01-page-overview.png');

    // Try buy dialog
    const buyBtn = page.locator('button:has-text("买入")').first();
    if (await buyBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await buyBtn.click();
      await page.waitForTimeout(1200);
      await shot(page, 'lesson-10', '10-mock-02-buy-form.png', { sel: '.el-dialog, .el-dialog__body' });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    } else {
      await shot(page, 'lesson-10', '10-mock-02-buy-form.png');
    }

    // Try sell dialog
    const sellBtn = page.locator('button:has-text("卖出")').first();
    if (await sellBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await sellBtn.click();
      await page.waitForTimeout(1200);
      await shot(page, 'lesson-10', '10-mock-03-sell-form.png', { sel: '.el-dialog, .el-dialog__body' });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    } else {
      await shot(page, 'lesson-10', '10-mock-03-sell-form.png');
    }

    await shot(page, 'lesson-10', '10-mock-04-position-list.png', { sel: '.el-table, .positions-table' });

    // Trade history tab
    const tradeHistTab = page.locator('.el-tabs__item:has-text("交易记录"), .el-tabs__item:has-text("成交")').first();
    if (await tradeHistTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await tradeHistTab.click();
      await page.waitForTimeout(1000);
      await shot(page, 'lesson-10', '10-mock-05-trade-history.png', { sel: '.el-table' });
    } else {
      await shot(page, 'lesson-10', '10-mock-05-trade-history.png');
    }

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 11-12: Portfolio / holding research
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-11-12] ===');

    await nav(page, '/portfolio');
    await shot(page, 'lesson-11', '11-holding-01-page-overview.png');
    await shot(page, 'lesson-11', '11-holding-02-stock-detail.png', { sel: '.stats-row, .portfolio-stats, .summary-cards' });
    await shot(page, 'lesson-11', '11-holding-03-ai-analysis.png', { sel: '.el-table, .holdings-table' });
    await shot(page, 'lesson-12', '12-decision-01-add-position.png', { sel: '.el-table, .holdings-table' });

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 13-14: Risk management
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-13-14] ===');

    await nav(page, '/reports');
    await shot(page, 'lesson-13', '13-risk-01-aggressive-view.png');
    await shot(page, 'lesson-13', '13-risk-02-conservative-view.png');
    await shot(page, 'lesson-14', '14-stoploss-02-profit-target.png');
    await shot(page, 'lesson-14', '14-stoploss-03-risk-reward.png');

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 15-16: Trade review
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-15-16] ===');

    await nav(page, '/review');
    await shot(page, 'lesson-15', '15-review-01-page-overview.png');

    // Try opening a new review / review form
    const newRevBtn = page.locator('button:has-text("新建复盘"), button:has-text("开始复盘"), button:has-text("添加"), button:has-text("新建"), button:has-text("创建")').first();
    if (await newRevBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await newRevBtn.click();
      await page.waitForTimeout(1500);
      await shot(page, 'lesson-15', '15-review-02-review-form.png');
      // Import from holdings button inside form
      const importBtn = page.locator('button:has-text("导入持仓"), button:has-text("从持仓导入"), button:has-text("导入")').first();
      if (await importBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await shot(page, 'lesson-15', '15-review-03-holding-import.png', { sel: '.el-dialog, .import-section, .el-form' });
        await importBtn.click().catch(() => {});
        await page.waitForTimeout(1000);
        await shot(page, 'lesson-15', '15-review-03-holding-import.png');
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      } else {
        await shot(page, 'lesson-15', '15-review-03-holding-import.png');
      }
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
    } else {
      await shot(page, 'lesson-15', '15-review-02-review-form.png', { sel: '.el-form, .review-form' });
      await shot(page, 'lesson-15', '15-review-03-holding-import.png', { sel: '.el-form' });
    }

    // History tab
    const revHistTab = page.locator('.el-tabs__item:has-text("复盘历史"), .el-tabs__item:has-text("历史记录")').first();
    if (await revHistTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await revHistTab.click();
      await page.waitForTimeout(1000);
      await shot(page, 'lesson-15', '15-review-08-history-list.png', { sel: '.el-table, .history-list' });
      await shot(page, 'lesson-16', '16-iteration-04-strategy-adjust.png');
    } else {
      await shot(page, 'lesson-15', '15-review-08-history-list.png');
    }

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 17, 20: Workflow config
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-17/20] ===');

    await nav(page, '/workflow');
    await shot(page, 'lesson-17', '17-short-01-workflow-config.png');
    await shot(page, 'lesson-20', '20-long-01-workflow-config.png');

    // ────────────────────────────────────────────────────────────────────────
    //  LESSON 23-24: Trading system / plan
    // ────────────────────────────────────────────────────────────────────────
    console.log('\n=== [lesson-23-24] ===');

    await nav(page, '/trading-system');
    await shot(page, 'lesson-23', '23-system-01-trade-plan-template.png');
    await shot(page, 'lesson-24', '24-growth-01-performance-tracking.png');

    await nav(page, '/trading-system/create');
    await shot(page, 'lesson-23', '23-system-02-checklist-config.png');

    // Fill in a plan name to enable "Next" button
    const nameInput = page.locator('input[placeholder*="名称"], input[placeholder*="计划"], input[type="text"]').first();
    if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await nameInput.fill('我的短线交易体系');
      await page.waitForTimeout(500);
    }

    // Step through wizard only if button is enabled
    const wizNext = page.locator('button:has-text("下一步"), button:has-text("继续")').first();
    if (await wizNext.isVisible({ timeout: 2000 }).catch(() => false)) {
      const isEnabled = await wizNext.isEnabled({ timeout: 500 }).catch(() => false);
      if (isEnabled) {
        await wizNext.click();
        await page.waitForTimeout(1200);
        await shot(page, 'lesson-23', '23-system-03-rule-setting.png');
      } else {
        await shot(page, 'lesson-23', '23-system-03-rule-setting.png');
      }
    } else {
      await shot(page, 'lesson-23', '23-system-03-rule-setting.png');
    }
    await shot(page, 'lesson-23', '23-system-04-daily-routine.png', { sel: '.el-steps, .step-indicator, .wizard-steps, .form-section' });

    // ────────────────────────────────────────────────────────────────────────
    console.log(`\n✅ Done! ${done} screenshots saved, ${failed} failed.`);
    console.log(`   Output: ${IMGS}`);

  } catch (err) {
    console.error('\n❌ Fatal error:', err.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
