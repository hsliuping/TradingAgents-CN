// MongoDB 脚本：检查研究员模板中的当前股价信息

// 连接到数据库
db = db.getSiblingDB('tradingagents');

// 查找看多研究员模板
print("\n" + "=".repeat(80));
print("检查 bull_researcher_v2 模板");
print("=".repeat(80));

db.prompt_templates.find({agent_name: "bull_researcher_v2"}).forEach(function(template) {
    print("\n模板: " + template.template_name + " (偏好: " + template.preference_type + ")");
    
    var userPrompt = template.content.user_prompt || "";
    var hasCurrentPrice = userPrompt.includes("{current_price}");
    var hasCurrencySymbol = userPrompt.includes("{currency_symbol}");
    var hasPriceSection = userPrompt.includes("📈 当前股价");
    
    print("  包含 {current_price}: " + hasCurrentPrice);
    print("  包含 {currency_symbol}: " + hasCurrencySymbol);
    print("  包含 '📈 当前股价': " + hasPriceSection);
    
    if (hasPriceSection) {
        var lines = userPrompt.split("\n");
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].includes("📈 当前股价")) {
                print("\n  当前股价片段:");
                var start = Math.max(0, i - 1);
                var end = Math.min(lines.length, i + 2);
                for (var j = start; j < end; j++) {
                    print("    " + lines[j]);
                }
                break;
            }
        }
    }
});

// 查找看空研究员模板
print("\n" + "=".repeat(80));
print("检查 bear_researcher_v2 模板");
print("=".repeat(80));

db.prompt_templates.find({agent_name: "bear_researcher_v2"}).forEach(function(template) {
    print("\n模板: " + template.template_name + " (偏好: " + template.preference_type + ")");
    
    var userPrompt = template.content.user_prompt || "";
    var hasCurrentPrice = userPrompt.includes("{current_price}");
    var hasCurrencySymbol = userPrompt.includes("{currency_symbol}");
    var hasPriceSection = userPrompt.includes("📈 当前股价");
    
    print("  包含 {current_price}: " + hasCurrentPrice);
    print("  包含 {currency_symbol}: " + hasCurrencySymbol);
    print("  包含 '📈 当前股价': " + hasPriceSection);
    
    if (hasPriceSection) {
        var lines = userPrompt.split("\n");
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].includes("📈 当前股价")) {
                print("\n  当前股价片段:");
                var start = Math.max(0, i - 1);
                var end = Math.min(lines.length, i + 2);
                for (var j = start; j < end; j++) {
                    print("    " + lines[j]);
                }
                break;
            }
        }
    }
});

print("\n" + "=".repeat(80));
print("检查完成！");
print("=".repeat(80) + "\n");

