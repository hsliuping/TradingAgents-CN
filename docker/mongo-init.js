// MongoDB初始化脚本
// 创建TradingAgents数据库和初始集合

// 切换到tradingagents数据库
db = db.getSiblingDB('tradingagents');

// 创建股票数据集合
db.createCollection('stock_data');

// 创建股票数据索引
db.stock_data.createIndex({ "symbol": 1, "market_type": 1 });
db.stock_data.createIndex({ "created_at": -1 });
db.stock_data.createIndex({ "updated_at": -1 });

print('✅ 股票数据集合和索引创建完成');

// 创建分析结果集合
db.createCollection('analysis_results');

// 创建分析结果索引
db.analysis_results.createIndex({ "symbol": 1, "analysis_type": 1 });
db.analysis_results.createIndex({ "created_at": -1 });
db.analysis_results.createIndex({ "symbol": 1, "created_at": -1 });

print('✅ 分析结果集合和索引创建完成');

// 创建用户会话集合
db.createCollection('user_sessions');

// 创建用户会话索引
db.user_sessions.createIndex({ "session_id": 1 }, { unique: true });
db.user_sessions.createIndex({ "created_at": -1 });
db.user_sessions.createIndex({ "last_activity": -1 });

print('✅ 用户会话集合和索引创建完成');

// 创建配置集合
db.createCollection('configurations');

// 创建配置索引
db.configurations.createIndex({ "config_type": 1, "config_name": 1 }, { unique: true });
db.configurations.createIndex({ "updated_at": -1 });

print('✅ 配置集合和索引创建完成');

// 插入初始配置数据
var currentTime = new Date();

// 缓存TTL配置
db.configurations.insertOne({
    "config_type": "cache",
    "config_name": "ttl_settings",
    "config_value": {
        "us_stock_data": 7200,      // 美股数据2小时
        "china_stock_data": 3600,   // A股数据1小时
        "us_news": 21600,           // 美股新闻6小时
        "china_news": 14400,        // A股新闻4小时
        "us_fundamentals": 86400,   // 美股基本面24小时
        "china_fundamentals": 43200 // A股基本面12小时
    },
    "description": "缓存TTL配置",
    "created_at": currentTime,
    "updated_at": currentTime
});

// 默认LLM模型配置
db.configurations.insertOne({
    "config_type": "llm",
    "config_name": "default_models",
    "config_value": {
        "default_provider": "dashscope",
        "models": {
            "dashscope": "qwen-plus-latest",
            "openai": "gpt-4o-mini",
            "google": "gemini-pro"
        }
    },
    "description": "默认LLM模型配置",
    "created_at": currentTime,
    "updated_at": currentTime
});

// 系统设置配置
db.configurations.insertOne({
    "config_type": "system",
    "config_name": "general_settings",
    "config_value": {
        "version": "0.1.2",
        "initialized_at": currentTime,
        "features": {
            "cache_enabled": true,
            "mongodb_enabled": true,
            "redis_enabled": true,
            "web_interface": true
        }
    },
    "description": "系统通用设置",
    "created_at": currentTime,
    "updated_at": currentTime
});
