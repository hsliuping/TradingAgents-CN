/**
 * 为提示词模板添加股价信息
 * 
 * 使用方法:
 *   mongo tradingagents scripts/add_price_info_to_prompts.js
 */

// 连接到数据库
var db = db.getSiblingDB('tradingagents');

// 要添加的股价信息文本
var priceInfoText = `
📈 当前股价信息：
- 最新价: {{current_price}} {{currency_symbol}}
- 市场: {{market_name}}
- 行业: {{industry}}
`;

print("=" + "=".repeat(79));
print("为分析师提示词模板添加股价信息");
print("=" + "=".repeat(79));

// 查找所有分析师系统模板
var templates = db.prompt_templates.find({
    is_system: true,
    agent_type: "analysts"
});

var totalCount = 0;
var updatedCount = 0;
var skippedCount = 0;

templates.forEach(function(template) {
    totalCount++;
    
    var agentName = template.agent_name;
    var preference = template.preference_type || "neutral";
    var content = template.content || {};
    var userPrompt = content.user_prompt || "";
    
    print("\n" + "-".repeat(80));
    print("Agent: " + agentName + " (偏好: " + preference + ")");
    
    // 检查是否已包含股价信息
    var hasCurrentPrice = userPrompt.indexOf("current_price") >= 0;
    var hasPriceSection = userPrompt.indexOf("当前股价") >= 0 || userPrompt.indexOf("最新价") >= 0;
    
    if (hasCurrentPrice || hasPriceSection) {
        print("  ⏭️  跳过: 已包含股价信息");
        skippedCount++;
        return;
    }
    
    // 在用户提示词开头添加股价信息
    var newUserPrompt = priceInfoText.trim() + "\n\n" + userPrompt;
    
    print("  ✏️  更新中...");
    
    // 更新数据库
    var result = db.prompt_templates.updateOne(
        { _id: template._id },
        {
            $set: {
                "content.user_prompt": newUserPrompt,
                "updated_at": new Date()
            }
        }
    );
    
    if (result.modifiedCount > 0) {
        print("  ✅ 已更新");
        updatedCount++;
    } else {
        print("  ❌ 更新失败");
    }
});

print("\n" + "=" + "=".repeat(79));
print("统计:");
print("  - 总计: " + totalCount);
print("  - 已更新: " + updatedCount);
print("  - 已跳过: " + skippedCount);
print("=" + "=".repeat(79));

// 显示一个更新后的示例
print("\n示例 - 查看更新后的模板:");
print("-".repeat(80));

var sampleTemplate = db.prompt_templates.findOne({
    is_system: true,
    agent_type: "analysts",
    agent_name: "market_analyst_v2"
});

if (sampleTemplate) {
    var sampleUserPrompt = sampleTemplate.content.user_prompt || "";
    print("Agent: " + sampleTemplate.agent_name);
    print("\nuser_prompt 前300字符:");
    print(sampleUserPrompt.substring(0, 300) + "...");
} else {
    print("未找到示例模板");
}

print("\n✅ 完成!");

