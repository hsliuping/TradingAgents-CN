// MongoDB初始化脚本
// 创建TradingAgents数据库和用户

// 切换到admin数据库
db = db.getSiblingDB('admin');

// 创建应用用户
db.createUser({
  user: 'tradingagents',
  pwd: 'tradingagents123',
  roles: [
    {
      role: 'readWrite',
      db: 'tradingagents'
    }
  ]
});

// 切换到应用数据库
db = db.getSiblingDB('tradingagents');

// 创建集合和索引
db.createCollection('stock_data');
db.createCollection('analysis_reports');
db.createCollection('user_sessions');
db.createCollection('system_logs');

// 为股票数据创建索引
db.stock_data.createIndex({ "symbol": 1, "date": 1 });
db.stock_data.createIndex({ "market": 1 });
db.stock_data.createIndex({ "created_at": 1 });

// 为分析报告创建索引
db.analysis_reports.createIndex({ "symbol": 1, "analysis_type": 1 });
db.analysis_reports.createIndex({ "created_at": 1 });

// 为用户会话创建索引
db.user_sessions.createIndex({ "session_id": 1 });
db.user_sessions.createIndex({ "created_at": 1 }, { expireAfterSeconds: 86400 }); // 24小时过期

// 为系统日志创建索引
db.system_logs.createIndex({ "level": 1, "timestamp": 1 });
db.system_logs.createIndex({ "timestamp": 1 }, { expireAfterSeconds: 604800 }); // 7天过期

print('TradingAgents数据库初始化完成');
