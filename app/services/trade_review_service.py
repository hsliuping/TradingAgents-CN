"""
交易复盘服务
提供交易复盘和阶段性复盘功能
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.core.database import get_mongo_db
from app.models.review import (
    ReviewType, ReviewStatus, PeriodType,
    TradeRecord, TradeInfo, MarketSnapshot,
    AITradeReview, TradeReviewReport,
    TradingStatistics, AIPeriodicReview, TradeSummaryItem, PeriodicReviewReport,
    CreateTradeReviewRequest, CreatePeriodicReviewRequest,
    TradeReviewResponse, PeriodicReviewResponse, ReviewListItem
)
from app.utils.timezone import now_tz

logger = logging.getLogger("app.services.trade_review")


class TradeReviewService:
    """交易复盘服务"""

    def __init__(self):
        self.db = get_mongo_db()
        self.trade_reviews_collection = "trade_reviews"
        self.periodic_reviews_collection = "periodic_reviews"
        self.paper_trades_collection = "paper_trades"

    # ==================== 交易复盘 ====================

    async def create_trade_review(
        self,
        user_id: str,
        request: CreateTradeReviewRequest
    ) -> TradeReviewResponse:
        """创建交易复盘"""
        review_id = str(uuid.uuid4())
        
        # 1. 获取交易记录
        trade_records = await self._get_trade_records(user_id, request.trade_ids)
        if not trade_records:
            raise ValueError("未找到指定的交易记录")
        
        # 2. 构建交易信息
        trade_info = self._build_trade_info(trade_records, request.code)
        
        # 3. 创建复盘报告
        report = TradeReviewReport(
            review_id=review_id,
            user_id=user_id,
            review_type=request.review_type,
            trade_info=trade_info,
            status=ReviewStatus.PROCESSING
        )
        
        # 4. 保存初始报告
        report_dict = report.model_dump(by_alias=True, exclude={"id"})
        await self.db[self.trade_reviews_collection].insert_one(report_dict)
        
        try:
            start_time = datetime.now()
            
            # 5. 获取市场数据快照
            market_snapshot = await self._get_market_snapshot(
                code=trade_info.code,
                market=trade_info.market,
                first_buy_date=trade_info.first_buy_date,
                last_sell_date=trade_info.last_sell_date
            )
            
            # 6. 调用AI分析
            ai_review = await self._call_ai_trade_review(trade_info, market_snapshot)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 7. 更新报告
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "market_snapshot": market_snapshot.model_dump(),
                    "ai_review": ai_review.model_dump(),
                    "status": ReviewStatus.COMPLETED.value,
                    "execution_time": execution_time
                }}
            )
            
            logger.info(f"✅ 交易复盘完成: {review_id}, 股票: {trade_info.code}")
            
            return TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.COMPLETED,
                trade_info=trade_info,
                ai_review=ai_review,
                market_snapshot=market_snapshot,
                execution_time=execution_time,
                created_at=report.created_at
            )
            
        except Exception as e:
            logger.error(f"❌ 交易复盘失败: {e}", exc_info=True)
            await self.db[self.trade_reviews_collection].update_one(
                {"review_id": review_id},
                {"$set": {
                    "status": ReviewStatus.FAILED.value,
                    "error_message": str(e)
                }}
            )
            return TradeReviewResponse(
                review_id=review_id,
                status=ReviewStatus.FAILED,
                trade_info=trade_info,
                created_at=report.created_at
            )

    async def _get_trade_records(
        self,
        user_id: str,
        trade_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """获取交易记录"""
        # 交易记录使用 ObjectId 作为 _id
        object_ids = []
        for tid in trade_ids:
            try:
                object_ids.append(ObjectId(tid))
            except Exception:
                logger.warning(f"无效的交易ID: {tid}")
        
        if not object_ids:
            return []
        
        cursor = self.db[self.paper_trades_collection].find({
            "user_id": user_id,
            "_id": {"$in": object_ids}
        })
        return await cursor.to_list(None)

    def _build_trade_info(
        self,
        trade_records: List[Dict[str, Any]],
        code: Optional[str] = None
    ) -> TradeInfo:
        """构建交易信息"""
        if not trade_records:
            return TradeInfo(code=code or "")
        
        # 使用第一条记录的股票信息
        first_trade = trade_records[0]
        stock_code = code or first_trade.get("code", "")
        market = first_trade.get("market", "CN")
        currency = first_trade.get("currency", "CNY")
        
        # 构建交易记录列表
        trades = []
        total_buy_qty = 0
        total_buy_amount = 0.0
        total_sell_qty = 0
        total_sell_amount = 0.0
        total_pnl = 0.0
        total_commission = 0.0
        
        timestamps = []

        for record in trade_records:
            trade = TradeRecord(
                trade_id=str(record.get("_id", "")),
                side=record.get("side", ""),
                quantity=record.get("quantity", 0),
                price=record.get("price", 0.0),
                amount=record.get("amount", 0.0),
                commission=record.get("commission", 0.0),
                timestamp=record.get("timestamp", ""),
                pnl=record.get("pnl", 0.0)
            )
            trades.append(trade)

            if trade.timestamp:
                timestamps.append(trade.timestamp)

            total_commission += trade.commission

            if trade.side == "buy":
                total_buy_qty += trade.quantity
                total_buy_amount += trade.amount
            else:
                total_sell_qty += trade.quantity
                total_sell_amount += trade.amount
                total_pnl += trade.pnl

        # 计算平均价格
        avg_buy_price = total_buy_amount / total_buy_qty if total_buy_qty > 0 else 0.0
        avg_sell_price = total_sell_amount / total_sell_qty if total_sell_qty > 0 else 0.0

        # 计算盈亏百分比
        pnl_pct = (total_pnl / total_buy_amount * 100) if total_buy_amount > 0 else 0.0

        # 计算持仓天数
        timestamps.sort()
        first_buy_date = timestamps[0] if timestamps else None
        last_sell_date = timestamps[-1] if timestamps else None
        holding_days = 0
        if first_buy_date and last_sell_date:
            try:
                first_dt = datetime.fromisoformat(first_buy_date.replace('Z', '+00:00').split('+')[0])
                last_dt = datetime.fromisoformat(last_sell_date.replace('Z', '+00:00').split('+')[0])
                holding_days = (last_dt - first_dt).days
            except Exception:
                pass

        return TradeInfo(
            code=stock_code,
            market=market,
            currency=currency,
            trades=trades,
            total_buy_quantity=total_buy_qty,
            total_buy_amount=round(total_buy_amount, 2),
            avg_buy_price=round(avg_buy_price, 4),
            total_sell_quantity=total_sell_qty,
            total_sell_amount=round(total_sell_amount, 2),
            avg_sell_price=round(avg_sell_price, 4),
            realized_pnl=round(total_pnl, 2),
            realized_pnl_pct=round(pnl_pct, 2),
            total_commission=round(total_commission, 2),
            first_buy_date=first_buy_date,
            last_sell_date=last_sell_date,
            holding_days=holding_days
        )

    async def _get_market_snapshot(
        self,
        code: str,
        market: str,
        first_buy_date: Optional[str],
        last_sell_date: Optional[str]
    ) -> MarketSnapshot:
        """获取市场数据快照"""
        snapshot = MarketSnapshot()

        if not first_buy_date:
            return snapshot

        try:
            # 解析日期
            start_date = datetime.fromisoformat(first_buy_date.replace('Z', '+00:00').split('+')[0])
            end_date = datetime.fromisoformat(last_sell_date.replace('Z', '+00:00').split('+')[0]) if last_sell_date else datetime.now()

            # 扩展日期范围（前后各10天）
            query_start = (start_date - timedelta(days=10)).strftime("%Y-%m-%d")
            query_end = (end_date + timedelta(days=10)).strftime("%Y-%m-%d")

            # 获取K线数据
            kline_data = await self._get_kline_data(code, market, query_start, query_end)

            if kline_data:
                snapshot.kline_data = kline_data

                # 查找持仓期间的最高最低价
                period_start = start_date.strftime("%Y-%m-%d")
                period_end = end_date.strftime("%Y-%m-%d")

                period_klines = [k for k in kline_data if period_start <= k.get("date", "") <= period_end]

                if period_klines:
                    # 找最高价
                    max_kline = max(period_klines, key=lambda x: x.get("high", 0))
                    snapshot.period_high = max_kline.get("high")
                    snapshot.period_high_date = max_kline.get("date")

                    # 找最低价
                    min_kline = min(period_klines, key=lambda x: x.get("low", float('inf')))
                    snapshot.period_low = min_kline.get("low")
                    snapshot.period_low_date = min_kline.get("date")

                    # 最优买卖点
                    snapshot.optimal_buy_price = snapshot.period_low
                    snapshot.optimal_sell_price = snapshot.period_high

                # 买入当日行情
                buy_date_str = start_date.strftime("%Y-%m-%d")
                buy_kline = next((k for k in kline_data if k.get("date") == buy_date_str), None)
                if buy_kline:
                    snapshot.buy_date_open = buy_kline.get("open")
                    snapshot.buy_date_high = buy_kline.get("high")
                    snapshot.buy_date_low = buy_kline.get("low")
                    snapshot.buy_date_close = buy_kline.get("close")

                # 卖出当日行情
                if last_sell_date:
                    sell_date_str = end_date.strftime("%Y-%m-%d")
                    sell_kline = next((k for k in kline_data if k.get("date") == sell_date_str), None)
                    if sell_kline:
                        snapshot.sell_date_open = sell_kline.get("open")
                        snapshot.sell_date_high = sell_kline.get("high")
                        snapshot.sell_date_low = sell_kline.get("low")
                        snapshot.sell_date_close = sell_kline.get("close")

        except Exception as e:
            logger.error(f"获取市场快照失败: {e}", exc_info=True)

        return snapshot

    async def _get_kline_data(
        self,
        code: str,
        market: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """获取K线数据"""
        try:
            # 从数据库获取历史K线
            cursor = self.db["stock_daily_history"].find({
                "code": code,
                "date": {"$gte": start_date, "$lte": end_date}
            }).sort("date", 1)

            klines = await cursor.to_list(None)

            if klines:
                return [
                    {
                        "date": k.get("date"),
                        "open": k.get("open"),
                        "high": k.get("high"),
                        "low": k.get("low"),
                        "close": k.get("close"),
                        "volume": k.get("volume")
                    }
                    for k in klines
                ]

            # 如果数据库没有，尝试使用 akshare 获取
            logger.info(f"数据库无K线数据，尝试从akshare获取: {code}")
            return await self._fetch_kline_from_akshare(code, start_date, end_date)

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []

    async def _fetch_kline_from_akshare(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """从akshare获取K线数据"""
        try:
            import akshare as ak
            import pandas as pd

            # 格式化日期
            start = start_date.replace("-", "")
            end = end_date.replace("-", "")

            # 获取日K线
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq"
            )

            if df is not None and not df.empty:
                klines = []
                for _, row in df.iterrows():
                    klines.append({
                        "date": str(row["日期"])[:10],
                        "open": float(row["开盘"]),
                        "high": float(row["最高"]),
                        "low": float(row["最低"]),
                        "close": float(row["收盘"]),
                        "volume": int(row["成交量"])
                    })
                return klines

        except Exception as e:
            logger.error(f"akshare获取K线失败: {e}")

        return []

    async def _call_ai_trade_review(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> AITradeReview:
        """调用AI进行交易复盘分析"""
        try:
            prompt = self._build_trade_review_prompt(trade_info, market_snapshot)

            from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
            import asyncio

            model_name = "qwen-plus"
            provider_info = get_provider_and_url_by_model_sync(model_name)

            # 使用同步 requests 调用，避免异步 httpx 的代理问题
            content = await asyncio.get_event_loop().run_in_executor(
                None,
                self._call_llm_sync,
                prompt,
                model_name,
                provider_info.get("backend_url"),
                provider_info.get("api_key")
            )

            return self._parse_ai_trade_review(content, trade_info, market_snapshot)

        except Exception as e:
            logger.error(f"AI复盘分析失败: {e}", exc_info=True)
            return AITradeReview(
                summary=f"AI分析暂时不可用: {str(e)}",
                overall_score=50
            )

    def _call_llm_sync(self, prompt: str, model_name: str, base_url: str, api_key: str) -> str:
        """同步调用LLM API（使用requests，兼容系统代理）"""
        import requests

        # 确保 URL 以 /chat/completions 结尾
        if base_url and not base_url.endswith("/chat/completions"):
            if not base_url.endswith("/"):
                base_url += "/"
            url = base_url + "chat/completions"
        else:
            url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        data = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        logger.info(f"🔍 [AI复盘] 调用模型: {model_name}, URL: {url}")

        response = requests.post(url, json=data, headers=headers, timeout=120)

        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                raise ValueError(f"API响应格式异常: {result}")
        else:
            raise ValueError(f"API调用失败: HTTP {response.status_code} - {response.text}")

    def _build_trade_review_prompt(
        self,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> str:
        """构建交易复盘提示词"""
        # 交易记录明细
        trades_detail = ""
        for t in trade_info.trades:
            trades_detail += f"- {t.timestamp[:10]} {t.side.upper()} {t.quantity}股 @ {t.price}元"
            if t.pnl != 0:
                trades_detail += f" (盈亏: {t.pnl}元)"
            trades_detail += "\n"

        # K线数据摘要（最近10条）
        kline_summary = ""
        if market_snapshot.kline_data:
            recent_klines = market_snapshot.kline_data[-20:]
            for k in recent_klines:
                kline_summary += f"  {k['date']}: 开{k['open']:.2f} 高{k['high']:.2f} 低{k['low']:.2f} 收{k['close']:.2f}\n"

        prompt = f"""# 交易复盘分析任务

你是一位专业的交易复盘分析师，请对以下交易进行深入分析。

## 交易信息

- **股票代码**: {trade_info.code}
- **市场**: {trade_info.market}
- **持仓周期**: {trade_info.first_buy_date[:10] if trade_info.first_buy_date else '未知'} 至 {trade_info.last_sell_date[:10] if trade_info.last_sell_date else '未知'}
- **持仓天数**: {trade_info.holding_days} 天

### 交易明细
{trades_detail}

### 交易汇总
- 买入: {trade_info.total_buy_quantity}股，均价 {trade_info.avg_buy_price:.2f}元，金额 {trade_info.total_buy_amount:.2f}元
- 卖出: {trade_info.total_sell_quantity}股，均价 {trade_info.avg_sell_price:.2f}元，金额 {trade_info.total_sell_amount:.2f}元
- **实现盈亏**: {trade_info.realized_pnl:.2f}元 ({trade_info.realized_pnl_pct:.2f}%)
- 手续费: {trade_info.total_commission:.2f}元

## 交易期间行情数据

### 关键价格
- 持仓期间最高价: {market_snapshot.period_high or '未知'}元 (日期: {market_snapshot.period_high_date or '未知'})
- 持仓期间最低价: {market_snapshot.period_low or '未知'}元 (日期: {market_snapshot.period_low_date or '未知'})
- 买入当日: 开{market_snapshot.buy_date_open or '-'} 高{market_snapshot.buy_date_high or '-'} 低{market_snapshot.buy_date_low or '-'} 收{market_snapshot.buy_date_close or '-'}
- 卖出当日: 开{market_snapshot.sell_date_open or '-'} 高{market_snapshot.sell_date_high or '-'} 低{market_snapshot.sell_date_low or '-'} 收{market_snapshot.sell_date_close or '-'}

### K线数据
{kline_summary if kline_summary else '暂无K线数据'}

## 分析要求

请从以下维度分析这笔交易，以JSON格式输出：

```json
{{
    "overall_score": 0-100的整数（综合评分）,
    "timing_score": 0-100的整数（时机评分）,
    "position_score": 0-100的整数（仓位评分）,
    "discipline_score": 0-100的整数（纪律评分）,

    "summary": "50字以内的总体评价",
    "strengths": ["做得好的地方1", "做得好的地方2"],
    "weaknesses": ["需要改进的地方1", "需要改进的地方2"],
    "suggestions": ["具体建议1", "具体建议2"],

    "timing_analysis": "买入卖出时机的详细分析（100字以内）",
    "position_analysis": "仓位控制分析（50字以内）",
    "emotion_analysis": "是否存在情绪化操作（50字以内）",

    "optimal_pnl": 理论最优收益金额（数字）,
    "missed_profit": 错失的收益金额（数字，如果亏损则为0）,
    "avoided_loss": 避免的亏损金额（数字，如果盈利则为0）
}}
```

**评分标准**：
- 90-100分：优秀，时机把握精准，纪律严明
- 70-89分：良好，整体操作合理，小有瑕疵
- 50-69分：一般，有明显改进空间
- 0-49分：较差，存在严重问题
"""
        return prompt

    def _parse_ai_trade_review(
        self,
        content: str,
        trade_info: TradeInfo,
        market_snapshot: MarketSnapshot
    ) -> AITradeReview:
        """解析AI复盘结果"""
        import re
        import json

        result = AITradeReview(actual_pnl=trade_info.realized_pnl)

        # 尝试提取JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))

                result.overall_score = int(data.get("overall_score", 50))
                result.timing_score = int(data.get("timing_score", 50))
                result.position_score = int(data.get("position_score", 50))
                result.discipline_score = int(data.get("discipline_score", 50))

                result.summary = data.get("summary", "")
                result.strengths = data.get("strengths", [])
                result.weaknesses = data.get("weaknesses", [])
                result.suggestions = data.get("suggestions", [])

                result.timing_analysis = data.get("timing_analysis", "")
                result.position_analysis = data.get("position_analysis", "")
                result.emotion_analysis = data.get("emotion_analysis", "")

                result.optimal_pnl = float(data.get("optimal_pnl", 0))
                result.missed_profit = float(data.get("missed_profit", 0))
                result.avoided_loss = float(data.get("avoided_loss", 0))

                return result

            except json.JSONDecodeError:
                logger.warning("JSON解析失败，使用默认值")

        # 备用：计算理论最优收益
        if market_snapshot.optimal_buy_price and market_snapshot.optimal_sell_price:
            qty = trade_info.total_buy_quantity
            optimal_pnl = (market_snapshot.optimal_sell_price - market_snapshot.optimal_buy_price) * qty
            result.optimal_pnl = round(optimal_pnl, 2)

            if trade_info.realized_pnl >= 0:
                result.missed_profit = max(0, round(optimal_pnl - trade_info.realized_pnl, 2))
            else:
                result.avoided_loss = max(0, round(optimal_pnl - trade_info.realized_pnl, 2))

        result.summary = content[:200] if content else "AI分析完成"
        return result

    # ==================== 复盘历史查询 ====================

    async def get_review_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        review_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取复盘历史列表，支持按股票代码、时间段、复盘类型筛选"""
        skip = (page - 1) * page_size

        # 构建查询条件
        query = {"user_id": user_id}

        # 股票代码筛选
        if code:
            query["trade_info.code"] = code

        # 复盘类型筛选
        if review_type:
            query["review_type"] = review_type

        # 时间段筛选
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                from datetime import datetime
                query["created_at"]["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                from datetime import datetime
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                query["created_at"]["$lte"] = end_dt

        # 查询交易复盘
        cursor = self.db[self.trade_reviews_collection].find(
            query
        ).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.trade_reviews_collection].count_documents(query)

        result = []
        for item in items:
            trade_info = item.get("trade_info", {})
            ai_review = item.get("ai_review", {})
            result.append(ReviewListItem(
                review_id=item.get("review_id", ""),
                review_type=item.get("review_type", "complete_trade"),
                code=trade_info.get("code"),
                name=trade_info.get("name"),
                realized_pnl=trade_info.get("realized_pnl", 0),
                overall_score=ai_review.get("overall_score", 0),
                status=item.get("status", "pending"),
                is_case_study=item.get("is_case_study", False),
                created_at=item.get("created_at")
            ))

        return {
            "items": [r.model_dump() for r in result],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_review_detail(
        self,
        user_id: str,
        review_id: str
    ) -> Optional[TradeReviewReport]:
        """获取复盘详情"""
        doc = await self.db[self.trade_reviews_collection].find_one({
            "user_id": user_id,
            "review_id": review_id
        })

        if not doc:
            return None

        return TradeReviewReport(**doc)

    # ==================== 案例库功能 ====================

    async def save_as_case(
        self,
        user_id: str,
        review_id: str,
        tags: List[str] = None
    ) -> bool:
        """保存为案例"""
        result = await self.db[self.trade_reviews_collection].update_one(
            {"user_id": user_id, "review_id": review_id},
            {"$set": {
                "is_case_study": True,
                "tags": tags or []
            }}
        )
        return result.modified_count > 0

    async def get_cases(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取案例库"""
        skip = (page - 1) * page_size

        cursor = self.db[self.trade_reviews_collection].find({
            "user_id": user_id,
            "is_case_study": True
        }).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.trade_reviews_collection].count_documents({
            "user_id": user_id,
            "is_case_study": True
        })

        result = []
        for item in items:
            trade_info = item.get("trade_info", {})
            ai_review = item.get("ai_review", {})
            result.append({
                "review_id": item.get("review_id", ""),
                "code": trade_info.get("code"),
                "name": trade_info.get("name"),
                "realized_pnl": trade_info.get("realized_pnl", 0),
                "overall_score": ai_review.get("overall_score", 0),
                "tags": item.get("tags", []),
                "created_at": item.get("created_at")
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def delete_case(
        self,
        user_id: str,
        review_id: str
    ) -> bool:
        """从案例库移除"""
        result = await self.db[self.trade_reviews_collection].update_one(
            {"user_id": user_id, "review_id": review_id},
            {"$set": {"is_case_study": False}}
        )
        return result.modified_count > 0

    # ==================== 交易统计 ====================

    async def get_trading_statistics(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> TradingStatistics:
        """获取交易统计"""
        query = {"user_id": user_id, "side": "sell"}

        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date

        # 获取所有卖出交易
        cursor = self.db[self.paper_trades_collection].find(query)
        trades = await cursor.to_list(None)

        if not trades:
            return TradingStatistics()

        stats = TradingStatistics()
        stats.total_trades = len(trades)

        profits = []
        losses = []
        total_commission = 0.0

        for trade in trades:
            pnl = trade.get("pnl", 0)
            commission = trade.get("commission", 0)
            total_commission += commission

            if pnl > 0:
                stats.winning_trades += 1
                profits.append(pnl)
            elif pnl < 0:
                stats.losing_trades += 1
                losses.append(abs(pnl))

            stats.total_pnl += pnl

        # 计算统计指标
        if stats.total_trades > 0:
            stats.win_rate = round(stats.winning_trades / stats.total_trades * 100, 2)

        if profits:
            stats.avg_profit = round(sum(profits) / len(profits), 2)
            stats.max_single_profit = round(max(profits), 2)

        if losses:
            stats.avg_loss = round(sum(losses) / len(losses), 2)
            stats.max_single_loss = round(max(losses), 2)

        if stats.avg_loss > 0:
            stats.profit_loss_ratio = round(stats.avg_profit / stats.avg_loss, 2)

        stats.total_pnl = round(stats.total_pnl, 2)
        stats.total_commission = round(total_commission, 2)

        return stats

    # ==================== 阶段性复盘 ====================

    async def create_periodic_review(
        self,
        user_id: str,
        request: CreatePeriodicReviewRequest
    ) -> PeriodicReviewResponse:
        """创建阶段性复盘"""
        import time
        start_time = time.time()

        review_id = str(uuid.uuid4())

        # 解析日期
        period_start = datetime.strptime(request.start_date, "%Y-%m-%d")
        period_end = datetime.strptime(request.end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )

        # 获取该时间段内的所有交易
        query = {
            "user_id": user_id,
            "timestamp": {
                "$gte": period_start,
                "$lte": period_end
            }
        }
        cursor = self.db[self.paper_trades_collection].find(query).sort("timestamp", 1)
        trades = await cursor.to_list(None)

        if not trades:
            raise ValueError(f"在 {request.start_date} 至 {request.end_date} 期间没有交易记录")

        # 计算交易统计
        statistics = await self._calculate_period_statistics(trades)

        # 构建交易摘要
        trades_summary = self._build_trades_summary(trades)

        # 调用AI进行阶段性分析
        ai_review = await self._call_ai_periodic_review(
            period_type=request.period_type.value,
            start_date=request.start_date,
            end_date=request.end_date,
            statistics=statistics,
            trades_summary=trades_summary
        )

        execution_time = time.time() - start_time

        # 保存复盘报告
        report = PeriodicReviewReport(
            review_id=review_id,
            user_id=user_id,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            statistics=statistics,
            trades_summary=trades_summary,
            ai_review=ai_review,
            status=ReviewStatus.COMPLETED,
            execution_time=execution_time,
            created_at=now_tz()
        )

        await self.db[self.periodic_reviews_collection].insert_one(
            report.model_dump(by_alias=True)
        )

        return PeriodicReviewResponse(
            review_id=review_id,
            status=ReviewStatus.COMPLETED,
            period_type=request.period_type,
            period_start=period_start,
            period_end=period_end,
            statistics=statistics,
            ai_review=ai_review,
            execution_time=execution_time,
            created_at=report.created_at
        )

    async def _calculate_period_statistics(
        self,
        trades: List[Dict[str, Any]]
    ) -> TradingStatistics:
        """计算阶段性交易统计"""
        stats = TradingStatistics()

        sell_trades = [t for t in trades if t.get("side") == "sell"]
        stats.total_trades = len(sell_trades)

        profits = []
        losses = []
        total_commission = 0.0

        for trade in sell_trades:
            pnl = trade.get("pnl", 0)
            commission = trade.get("commission", 0)
            total_commission += commission

            if pnl > 0:
                stats.winning_trades += 1
                profits.append(pnl)
            elif pnl < 0:
                stats.losing_trades += 1
                losses.append(abs(pnl))

            stats.total_pnl += pnl

        # 计算统计指标
        if stats.total_trades > 0:
            stats.win_rate = round(stats.winning_trades / stats.total_trades * 100, 2)

        if profits:
            stats.avg_profit = round(sum(profits) / len(profits), 2)
            stats.max_single_profit = round(max(profits), 2)

        if losses:
            stats.avg_loss = round(sum(losses) / len(losses), 2)
            stats.max_single_loss = round(max(losses), 2)

        if stats.avg_loss > 0:
            stats.profit_loss_ratio = round(stats.avg_profit / stats.avg_loss, 2)

        stats.total_pnl = round(stats.total_pnl, 2)
        stats.total_commission = round(total_commission, 2)

        return stats

    def _build_trades_summary(
        self,
        trades: List[Dict[str, Any]]
    ) -> List[TradeSummaryItem]:
        """构建交易摘要列表"""
        summary = []
        for trade in trades:
            if trade.get("side") == "sell":
                pnl = trade.get("pnl", 0)
                amount = trade.get("amount", 0)
                pnl_pct = (pnl / amount * 100) if amount > 0 else 0

                summary.append(TradeSummaryItem(
                    code=trade.get("code", ""),
                    name=trade.get("name", ""),
                    side=trade.get("side", ""),
                    quantity=trade.get("quantity", 0),
                    price=trade.get("price", 0),
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 2),
                    timestamp=trade.get("timestamp", "").isoformat() if isinstance(trade.get("timestamp"), datetime) else str(trade.get("timestamp", ""))
                ))

        return summary

    async def _call_ai_periodic_review(
        self,
        period_type: str,
        start_date: str,
        end_date: str,
        statistics: TradingStatistics,
        trades_summary: List[TradeSummaryItem]
    ) -> AIPeriodicReview:
        """调用AI进行阶段性复盘分析"""
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        import asyncio

        # 构建提示词
        period_names = {
            "week": "周度",
            "month": "月度",
            "quarter": "季度",
            "year": "年度"
        }
        period_name = period_names.get(period_type, "阶段性")

        # 构建交易明细
        trades_detail = "\n".join([
            f"- {t.code}: {t.side} {t.quantity}股 @ {t.price}, 盈亏: {t.pnl} ({t.pnl_pct}%)"
            for t in trades_summary[:20]  # 最多显示20条
        ])
        if len(trades_summary) > 20:
            trades_detail += f"\n... 还有 {len(trades_summary) - 20} 条交易记录"

        prompt = f"""# {period_name}交易复盘

## 复盘周期
{start_date} 至 {end_date}

## 交易统计
- 总交易次数: {statistics.total_trades}
- 盈利次数: {statistics.winning_trades} / 亏损次数: {statistics.losing_trades}
- 胜率: {statistics.win_rate}%
- 总盈亏: {statistics.total_pnl}
- 平均盈利: {statistics.avg_profit} / 平均亏损: {statistics.avg_loss}
- 盈亏比: {statistics.profit_loss_ratio}
- 最大单笔盈利: {statistics.max_single_profit}
- 最大单笔亏损: {statistics.max_single_loss}
- 总手续费: {statistics.total_commission}

## 交易明细
{trades_detail}

请对这段时间的交易进行全面复盘分析，包括：
1. 整体评分（0-100分）
2. 交易风格分析
3. 常见错误总结
4. 改进方向建议
5. 下阶段行动计划
6. 最佳交易分析
7. 最差交易分析

请以JSON格式输出，格式如下：
{{
    "overall_score": 75,
    "summary": "整体评价...",
    "trading_style": "交易风格分析...",
    "common_mistakes": ["错误1", "错误2"],
    "improvement_areas": ["改进方向1", "改进方向2"],
    "action_plan": ["行动计划1", "行动计划2"],
    "best_trade": "最佳交易分析...",
    "worst_trade": "最差交易分析..."
}}
"""

        try:
            model_name = "qwen-plus"
            provider_info = get_provider_and_url_by_model_sync(model_name)

            # 使用同步 requests 调用，避免异步 httpx 的代理问题
            content = await asyncio.get_event_loop().run_in_executor(
                None,
                self._call_llm_sync,
                prompt,
                model_name,
                provider_info.get("backend_url"),
                provider_info.get("api_key")
            )

            # 解析JSON响应
            import json
            import re

            # 尝试提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                return AIPeriodicReview(
                    overall_score=data.get("overall_score", 60),
                    summary=data.get("summary", ""),
                    trading_style=data.get("trading_style", ""),
                    common_mistakes=data.get("common_mistakes", []),
                    improvement_areas=data.get("improvement_areas", []),
                    action_plan=data.get("action_plan", []),
                    best_trade=data.get("best_trade"),
                    worst_trade=data.get("worst_trade")
                )
            else:
                # 如果无法解析JSON，返回默认结果
                return AIPeriodicReview(
                    overall_score=60,
                    summary=content[:500] if content else "AI分析完成"
                )

        except Exception as e:
            logger.error(f"AI阶段性复盘分析失败: {e}")
            return AIPeriodicReview(
                overall_score=0,
                summary=f"AI分析失败: {str(e)}"
            )

    async def get_periodic_review_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """获取阶段性复盘历史"""
        skip = (page - 1) * page_size

        cursor = self.db[self.periodic_reviews_collection].find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(page_size)

        items = await cursor.to_list(None)
        total = await self.db[self.periodic_reviews_collection].count_documents({"user_id": user_id})

        result = []
        for item in items:
            ai_review = item.get("ai_review", {})
            statistics = item.get("statistics", {})
            result.append({
                "review_id": item.get("review_id", ""),
                "period_type": item.get("period_type", "month"),
                "period_start": item.get("period_start"),
                "period_end": item.get("period_end"),
                "total_trades": statistics.get("total_trades", 0),
                "total_pnl": statistics.get("total_pnl", 0),
                "win_rate": statistics.get("win_rate", 0),
                "overall_score": ai_review.get("overall_score", 0),
                "status": item.get("status", "pending"),
                "created_at": item.get("created_at")
            })

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_periodic_review_detail(
        self,
        user_id: str,
        review_id: str
    ) -> Optional[PeriodicReviewReport]:
        """获取阶段性复盘详情"""
        doc = await self.db[self.periodic_reviews_collection].find_one({
            "user_id": user_id,
            "review_id": review_id
        })

        if not doc:
            return None

        return PeriodicReviewReport(**doc)


# 单例模式
_trade_review_service: Optional[TradeReviewService] = None


def get_trade_review_service() -> TradeReviewService:
    """获取交易复盘服务实例"""
    global _trade_review_service
    if _trade_review_service is None:
        _trade_review_service = TradeReviewService()
    return _trade_review_service

