# Tushare API 限流处理方案

## 📋 问题描述

当 Tushare API 遇到限流错误时（"抱歉，您每分钟最多访问该接口800次"），系统会继续循环重试，生成大量错误日志，浪费资源。

## ✅ 解决方案

### 1. **限流错误检测**

在 `tradingagents/dataflows/providers/china/tushare.py` 中添加限流错误检测方法：

```python
def _is_rate_limit_error(self, error_msg: str) -> bool:
    """检测是否为 API 限流错误"""
    rate_limit_keywords = [
        "每分钟最多访问",
        "每分钟最多",
        "rate limit",
        "too many requests",
        "访问频率",
        "请求过于频繁"
    ]
    error_msg_lower = error_msg.lower()
    return any(keyword in error_msg_lower for keyword in rate_limit_keywords)
```

### 2. **在 Provider 层抛出限流异常**

修改 `get_stock_quotes()` 方法，检测到限流错误时抛出异常：

```python
async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
    """获取实时行情"""
    try:
        # ... 获取数据的代码 ...
    except Exception as e:
        # 检查是否为限流错误
        if self._is_rate_limit_error(str(e)):
            self.logger.error(f"❌ 获取实时行情失败 symbol={symbol}: {e}")
            raise  # 抛出限流错误，让上层处理
        
        self.logger.error(f"❌ 获取实时行情失败 symbol={symbol}: {e}")
        return None
```

### 3. **在 Worker 层传播限流异常**

修改 `app/worker/tushare_sync_service.py` 中的 `_get_and_save_quotes()` 方法：

```python
async def _get_and_save_quotes(self, symbol: str) -> bool:
    """获取并保存单个股票行情"""
    try:
        quotes = await self.provider.get_stock_quotes(symbol)
        # ... 保存数据的代码 ...
    except Exception as e:
        error_msg = str(e)
        # 检测限流错误，直接抛出让上层处理
        if self._is_rate_limit_error(error_msg):
            logger.error(f"❌ 获取 {symbol} 行情失败（限流）: {e}")
            raise  # 抛出限流错误
        logger.error(f"❌ 获取 {symbol} 行情失败: {e}")
        return False
```

### 4. **在批次处理中检测限流**

修改 `_process_quotes_batch()` 方法，检测批次中的限流错误：

```python
async def _process_quotes_batch(self, batch: List[str]) -> Dict[str, Any]:
    """处理行情批次"""
    batch_stats = {
        "success_count": 0,
        "error_count": 0,
        "errors": [],
        "rate_limit_hit": False  # 新增：限流标记
    }
    
    # 并发获取行情数据
    tasks = [self._get_and_save_quotes(symbol) for symbol in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            error_msg = str(result)
            batch_stats["error_count"] += 1
            batch_stats["errors"].append({
                "code": batch[i],
                "error": error_msg,
                "context": "_process_quotes_batch"
            })
            
            # 检测 API 限流错误
            if self._is_rate_limit_error(error_msg):
                batch_stats["rate_limit_hit"] = True
                logger.warning(f"⚠️ 检测到 API 限流错误: {error_msg}")
        # ... 其他处理 ...
    
    return batch_stats
```

### 5. **在主同步方法中停止任务**

修改 `sync_realtime_quotes()` 方法，检测到限流时立即停止：

```python
async def sync_realtime_quotes(self, symbols: List[str] = None) -> Dict[str, Any]:
    """同步实时行情数据"""
    stats = {
        "total_processed": 0,
        "success_count": 0,
        "error_count": 0,
        "start_time": datetime.utcnow(),
        "errors": [],
        "stopped_by_rate_limit": False  # 新增：限流停止标记
    }
    
    try:
        # ... 获取股票列表 ...
        
        # 批量处理
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batch_stats = await self._process_quotes_batch(batch)
            
            # 更新统计
            stats["success_count"] += batch_stats["success_count"]
            stats["error_count"] += batch_stats["error_count"]
            stats["errors"].extend(batch_stats["errors"])
            
            # 检查是否遇到 API 限流错误
            if batch_stats.get("rate_limit_hit"):
                stats["stopped_by_rate_limit"] = True
                logger.warning(f"⚠️ 检测到 API 限流，停止同步任务")
                logger.warning(f"📊 已处理: {min(i + self.batch_size, len(symbols))}/{len(symbols)} "
                             f"(成功: {stats['success_count']}, 错误: {stats['error_count']})")
                break  # 立即停止循环
            
            # ... 进度日志和延迟 ...
        
        # 完成统计
        stats["end_time"] = datetime.utcnow()
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
        
        if stats["stopped_by_rate_limit"]:
            logger.warning(f"⚠️ 实时行情同步因 API 限流而停止: "
                         f"总计 {stats['total_processed']} 只, "
                         f"成功 {stats['success_count']} 只, "
                         f"错误 {stats['error_count']} 只, "
                         f"耗时 {stats['duration']:.2f} 秒")
        else:
            logger.info(f"✅ 实时行情同步完成: ...")
        
        return stats
    except Exception as e:
        logger.error(f"❌ 实时行情同步失败: {e}")
        return stats
```

## 📊 测试结果

### 修改前
```
2025-10-03 11:55:52 | ERROR | ❌ 获取实时行情失败 symbol=301307: 抱歉，您每分钟最多访问该接口800次
2025-10-03 11:55:52 | ERROR | ❌ 获取实时行情失败 symbol=301303: 抱歉，您每分钟最多访问该接口800次
... (继续处理剩余 4636 只股票，生成大量错误日志)
2025-10-03 11:55:52 | INFO | 📈 行情同步进度: 2600/5436 (成功: 0, 错误: 2600)
```

### 修改后
```
2025-10-03 12:10:27 | WARNING | ⚠️ 检测到 API 限流错误: 抱歉，您每分钟最多访问该接口800次
2025-10-03 12:10:27 | WARNING | ⚠️ 检测到 API 限流，停止同步任务
2025-10-03 12:10:27 | WARNING | 📊 已处理: 800/5436 (成功: 0, 错误: 800)
2025-10-03 12:10:27 | WARNING | ⚠️ 实时行情同步因 API 限流而停止: 总计 5436 只, 成功 0 只, 错误 800 只, 耗时 27.60秒
```

## ✅ 优势

1. **立即停止**：检测到限流错误后立即停止，不再浪费资源
2. **清晰日志**：明确标记任务因限流而停止
3. **统计准确**：记录实际处理的股票数量和耗时
4. **可扩展**：支持多种限流错误关键词检测

## 🔧 相关文件

- `tradingagents/dataflows/providers/china/tushare.py` - Provider 层限流检测
- `app/worker/tushare_sync_service.py` - Worker 层限流处理
- `docs/RATE_LIMIT_HANDLING.md` - 本文档

## 📝 注意事项

1. **限流关键词**：可以根据实际情况添加更多限流错误关键词
2. **重试策略**：可以考虑在下次定时任务中自动重试
3. **监控告警**：建议添加监控，当频繁遇到限流时发送告警

