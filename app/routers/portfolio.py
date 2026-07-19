"""
持仓研究 API 路由
提供持仓管理和 AI 研究接口
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel, Field
import logging
import io

from app.routers.auth_db import get_current_user
from app.services.portfolio_service import get_portfolio_service
from app.models.portfolio import (
    PositionCreate, PositionUpdate, PositionImport, PositionOperationRequest,
    PositionChangeUpdate,
    PortfolioAnalysisRequest, PositionResponse,
    PortfolioStatsResponse, PortfolioAnalysisResponse,
    PositionAnalysisRequest, PositionAnalysisByCodeRequest,
    AccountInitRequest, AccountTransactionRequest,
    AccountSettingsRequest, CapitalTransactionType, PositionChangeType,
    QMTPositionImportRequest,
    PortfolioAnalysisStatus
)
from app.core.response import ok

logger = logging.getLogger("webapi")

router = APIRouter(
    prefix="/portfolio",
    tags=["持仓研究"]
)


# ==================== 持仓管理接口 ====================

@router.get("/positions", response_model=dict)
async def get_positions(
    source: str = Query("all", description="数据来源: all/real/paper"),
    current_user: dict = Depends(get_current_user)
):
    """获取持仓列表"""
    try:
        service = get_portfolio_service()
        positions = await service.get_positions(
            user_id=current_user["id"],
            source=source
        )

        # 转换为字典列表
        items = [pos.model_dump() for pos in positions]

        return ok(data={
            "items": items,
            "total": len(items)
        })
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/history", response_model=dict)
async def get_history_positions(
    source: str = Query("real", description="数据来源: real/paper"),
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取历史持仓（已清仓的记录）"""
    try:
        service = get_portfolio_service()
        result = await service.get_history_positions(
            user_id=current_user["id"],
            source=source,
            limit=limit,
            skip=skip
        )
        return ok(data=result)
    except Exception as e:
        logger.error(f"获取历史持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions", response_model=dict)
async def add_position(
    data: PositionCreate,
    current_user: dict = Depends(get_current_user)
):
    """添加持仓"""
    try:
        service = get_portfolio_service()
        position = await service.add_position(
            user_id=current_user["id"],
            data=data
        )
        return ok(data=position.model_dump(), message="添加成功")
    except Exception as e:
        logger.error(f"添加持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/positions/{position_id}", response_model=dict)
async def update_position(
    position_id: str,
    data: PositionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新持仓"""
    try:
        service = get_portfolio_service()
        position = await service.update_position(
            user_id=current_user["id"],
            position_id=position_id,
            data=data
        )
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(data=position.model_dump(), message="更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/positions/{position_id}", response_model=dict)
async def delete_position(
    position_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除持仓"""
    try:
        service = get_portfolio_service()
        success = await service.delete_position(
            user_id=current_user["id"],
            position_id=position_id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(message="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/import", response_model=dict)
async def import_positions(
    data: PositionImport,
    current_user: dict = Depends(get_current_user)
):
    """批量导入持仓"""
    try:
        service = get_portfolio_service()
        result = await service.import_positions(
            user_id=current_user["id"],
            positions=data.positions
        )
        return ok(data=result, message=f"导入完成: 成功 {result['success_count']}, 失败 {result['failed_count']}")
    except Exception as e:
        logger.error(f"导入持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class FileImportMapping(BaseModel):
    """文件列名映射"""
    code: str = Field("股票代码", description="股票代码列名")
    name: str = Field("股票名称", description="股票名称列名")
    quantity: str = Field("持仓数量", description="数量列名")
    cost_price: str = Field("成本价", description="成本价列名")
    buy_date: str = Field("买入日期", description="买入日期列名")


@router.post("/positions/import/file", response_model=dict)
async def import_positions_from_file(
    file: UploadFile = File(...),
    market: str = Query("CN", description="市场: CN/HK/US"),
    current_user: dict = Depends(get_current_user)
):
    """从 Excel/CSV 文件导入持仓

    支持 .xlsx / .xls / .csv 格式。
    自动识别常见券商导出格式（同花顺、东方财富、华泰等），
    也支持自定义列名映射。
    """
    try:
        import pandas as pd

        # 读取文件
        content = await file.read()
        filename = file.filename or ""

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {filename}，请上传 .xlsx / .xls / .csv 文件"
            )

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空"
            )

        logger.info(f"📁 文件解析成功: {filename}, {len(df)} 行, 列: {list(df.columns)}")

        # 自动识别列名映射
        col_map = _auto_detect_columns(df.columns.tolist())
        logger.info(f"🔍 自动识别列映射: {col_map}")

        # 解析为 PositionCreate 列表
        positions = []
        errors = []
        for idx, row in df.iterrows():
            try:
                code = str(row.get(col_map["code"], "")).strip()
                if not code or code == "nan":
                    continue
                # 确保代码为6位
                code = code.zfill(6)

                quantity = int(float(row.get(col_map["quantity"], 0)))
                cost_price = float(row.get(col_map["cost_price"], 0))

                if quantity <= 0 or cost_price <= 0:
                    errors.append({"row": idx + 1, "code": code, "error": "数量或成本价无效"})
                    continue

                name = str(row.get(col_map["name"], "")).strip()
                if name == "nan":
                    name = ""

                buy_date = None
                if col_map["buy_date"]:
                    raw_date = row.get(col_map["buy_date"], "")
                    if raw_date and str(raw_date) != "nan":
                        try:
                            from datetime import datetime as dt
                            if isinstance(raw_date, dt):
                                buy_date = raw_date
                            else:
                                # 尝试多种日期格式
                                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y"]:
                                    try:
                                        buy_date = dt.strptime(str(raw_date).strip(), fmt)
                                        break
                                    except ValueError:
                                        continue
                        except Exception:
                            pass

                pos = PositionCreate(
                    code=code,
                    name=name or None,
                    quantity=quantity,
                    cost_price=cost_price,
                    market=market,
                    buy_date=buy_date,
                )
                positions.append(pos)
            except Exception as e:
                errors.append({"row": idx + 1, "error": str(e)})

        if not positions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未能从文件中解析出有效持仓。列映射: {col_map}，解析错误: {errors[:5]}"
            )

        # 批量导入
        service = get_portfolio_service()
        result = await service.import_positions(
            user_id=current_user["id"],
            positions=positions,
            validate_input=True,
        )
        result["file_info"] = {
            "filename": filename,
            "total_rows": len(df),
            "parsed_rows": len(positions),
            "parse_errors": errors[:10],
            "column_mapping": col_map,
        }

        return ok(data=result, message=f"导入完成: 成功 {result['success_count']}, 失败 {result['failed_count']}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件导入持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _auto_detect_columns(columns: List[str]) -> Dict[str, Any]:
    """自动识别 Excel/CSV 列名到系统字段的映射

    支持同花顺、东方财富、华泰等常见券商导出格式
    """
    col_map = {
        "code": None,
        "name": None,
        "quantity": None,
        "cost_price": None,
        "buy_date": None,
    }

    # 股票代码候选列名
    code_candidates = [
        "股票代码", "证券代码", "代码", "code", "symbol",
        "stock_code", "证券号", "证券",
    ]
    # 股票名称候选列名
    name_candidates = [
        "股票名称", "证券名称", "名称", "name", "证券简称",
        "stock_name", "证券名",
    ]
    # 数量候选列名
    quantity_candidates = [
        "持仓数量", "证券数量", "持有数量", "数量", "quantity", "股数",
        "持仓股数", "可用数量", "持仓", "持仓量",
    ]
    # 成本价候选列名
    cost_price_candidates = [
        "成本价", "摊薄成本", "持仓成本", "成本", "cost_price",
        "成本价格", "均价", "买入均价", "买入价格",
    ]
    # 买入日期候选列名
    date_candidates = [
        "买入日期", "建仓日期", "购入日期", "买入时间",
        "buy_date", "首次买入日期", "买入日",
    ]

    def _find_column(candidates: List[str], cols: List[str]) -> Any:
        for c in candidates:
            for col in cols:
                if c in col or col in c:
                    return col
        return None

    col_map["code"] = _find_column(code_candidates, columns)
    col_map["name"] = _find_column(name_candidates, columns)
    col_map["quantity"] = _find_column(quantity_candidates, columns)
    col_map["cost_price"] = _find_column(cost_price_candidates, columns)
    col_map["buy_date"] = _find_column(date_candidates, columns)

    return col_map


@router.post("/positions/import/file/preview", response_model=dict)
async def preview_import_file(
    file: UploadFile = File(...),
    market: str = Query("CN", description="市场: CN/HK/US"),
    current_user: dict = Depends(get_current_user)
):
    """预览文件导入：解析文件并返回前10行和列映射结果，不执行导入"""
    try:
        import pandas as pd

        content = await file.read()
        filename = file.filename or ""

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {filename}"
            )

        col_map = _auto_detect_columns(df.columns.tolist())

        # 返回预览数据
        preview_rows = df.head(10).fillna("").to_dict("records")

        return ok(data={
            "filename": filename,
            "total_rows": len(df),
            "columns": list(df.columns),
            "column_mapping": col_map,
            "preview": preview_rows,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/import/screenshot", response_model=dict)
async def import_positions_from_screenshot(
    file: UploadFile = File(...),
    market: str = Query("CN", description="市场: CN/HK/US"),
    current_user: dict = Depends(get_current_user)
):
    """从券商截图识别持仓信息

    上传券商界面的截图（如持仓列表页面），使用 VLM（视觉语言模型）解析图片，
    自动提取股票代码、名称、数量、成本价等信息。
    返回识别结果供用户确认，不自动导入。

    注意：需要对话模型支持 Vision 能力（如 Qwen-VL、GPT-4o 等），
    GLM-5/GLM-5.1 等纯文本模型不支持此功能。
    """
    try:
        import base64
        import os
        from app.services.model_capability_service import get_model_capability_service
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        from tradingagents.graph.trading_graph import create_llm_by_provider

        # 京东云模式下禁用（GLM-5/5.1 不支持 Vision）
        if os.getenv("JDYUN_MODE", "").lower() == "true":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="京东云版当前对话模型不支持图片识别功能。请使用文件导入（Excel/CSV）方式批量添加持仓。"
            )

        # 读取图片
        content = await file.read()
        filename = file.filename or ""

        # 检查文件类型
        if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的图片格式: {filename}，请上传 PNG/JPG/BMP/WebP 格式"
            )

        # Base64 编码
        img_b64 = base64.b64encode(content).decode("utf-8")
        mime_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

        # 获取对话模型（Vision 能力）
        capability_service = get_model_capability_service()
        chat_model, _ = capability_service._get_default_models()
        model_name = chat_model

        # 检测模型是否支持 Vision（多模态输入）
        # 已知支持 Vision 的模型：Qwen-VL, Qwen2-VL, GPT-4o, GPT-4V, Claude-3, gemini
        # 已知不支持 Vision 的模型：GLM-5, GLM-5.1, GLM-5.2, DeepSeek-V4, DeepSeek-V3
        VISION_UNSUPPORTED_PATTERNS = ["glm-5", "glm-4", "deepseek", "qwen2.5-72b-instruct", "llama"]
        model_lower = model_name.lower()
        is_vision_supported = not any(p in model_lower for p in VISION_UNSUPPORTED_PATTERNS)

        if not is_vision_supported:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"当前对话模型 {model_name} 不支持图片识别功能。截图识别需要支持 Vision 的模型（如 Qwen2-VL、GPT-4o 等）。请改用文件导入（Excel/CSV）方式。"
            )

        provider_info = get_provider_and_url_by_model_sync(model_name)
        backend_url = provider_info.get("backend_url")
        api_key = provider_info.get("api_key")
        provider_name = provider_info.get("provider", "dashscope")

        if not backend_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="对话模型未配置，无法使用截图识别功能"
            )

        # 构造 Vision LLM 请求
        llm = create_llm_by_provider(
            provider=provider_name,
            model=model_name,
            backend_url=backend_url,
            temperature=0.1,
            max_tokens=4000,
        )

        # 构造多模态消息
        system_prompt = """你是一个专业的券商持仓截图识别助手。请识别这张券商持仓截图，提取每只股票的持仓信息。

请严格按照以下 JSON 格式返回结果，不要包含任何其他文字：
```json
[
  {
    "code": "000001",
    "name": "平安银行",
    "quantity": 1000,
    "cost_price": 12.34,
    "buy_date": "2024-01-15"
  }
]
```

注意事项：
1. 股票代码必须是6位数字
2. 数量必须是整数（股数）
3. 成本价保留2位小数
4. 买入日期格式为 YYYY-MM-DD，如果无法识别则设为 null
5. 如果某些字段无法识别，设为 null
6. 只返回 JSON 数组，不要有其他内容"""

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{img_b64}"
                    }
                },
                {
                    "type": "text",
                    "text": "请识别这张券商持仓截图中的所有股票持仓信息。"
                }
            ])
        ]

        response = await llm.ainvoke(messages)
        result_text = response.content if hasattr(response, 'content') else str(response)

        # 解析 JSON 结果
        import json
        import re

        # 提取 JSON 数组（可能被包裹在 ```json ... ``` 中）
        json_match = re.search(r'\[[\s\S]*?\]', result_text)
        if not json_match:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM 返回的内容无法解析为 JSON: {result_text[:200]}"
            )

        try:
            positions_data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"JSON 解析失败: {e}"
            )

        # 转换为 PositionCreate 列表
        positions = []
        parse_errors = []
        for idx, item in enumerate(positions_data):
            try:
                code = str(item.get("code", "")).zfill(6)
                quantity = int(item.get("quantity", 0))
                cost_price = float(item.get("cost_price", 0))

                if not code or quantity <= 0 or cost_price <= 0:
                    parse_errors.append({"index": idx, "data": item, "error": "必填字段缺失或无效"})
                    continue

                buy_date = None
                raw_date = item.get("buy_date")
                if raw_date and str(raw_date) != "null":
                    try:
                        from datetime import datetime as dt
                        buy_date = dt.strptime(str(raw_date), "%Y-%m-%d")
                    except ValueError:
                        pass

                pos = PositionCreate(
                    code=code,
                    name=item.get("name") or None,
                    quantity=quantity,
                    cost_price=cost_price,
                    market=market,
                    buy_date=buy_date,
                )
                positions.append(pos)
            except Exception as e:
                parse_errors.append({"index": idx, "data": item, "error": str(e)})

        logger.info(f"📸 截图识别完成: 识别 {len(positions_data)} 条，有效 {len(positions)} 条，错误 {len(parse_errors)} 条")

        return ok(data={
            "filename": filename,
            "model": model_name,
            "recognized_count": len(positions_data),
            "valid_count": len(positions),
            "positions": [p.model_dump() for p in positions],
            "parse_errors": parse_errors[:10],
            "raw_response": result_text[:500],
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"截图识别失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/import/qmt/preview", response_model=dict)
async def preview_positions_from_qmt(
    data: QMTPositionImportRequest,
    current_user: dict = Depends(get_current_user)
):
    """预览从 QMT 覆盖同步当前账户持仓的影响。"""
    try:
        service = get_portfolio_service()
        result = await service.preview_qmt_position_import(
            user_id=current_user["id"],
            account_id=data.account_id,
            account_type=data.account_type,
        )
        return ok(data=result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"QMT 持仓同步预览失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/import/qmt", response_model=dict)
async def import_positions_from_qmt(
    data: QMTPositionImportRequest,
    current_user: dict = Depends(get_current_user)
):
    """从 QMT 只读查询当前账户持仓并覆盖同步到系统持仓。"""
    try:
        service = get_portfolio_service()
        result = await service.import_positions_from_qmt(
            user_id=current_user["id"],
            account_id=data.account_id,
            account_type=data.account_type,
        )
        return ok(
            data=result,
            message=(
                f"QMT 持仓同步完成: 已覆盖 {result.get('deleted_positions', 0)} 个旧持仓, "
                f"成功 {result['success_count']}, 失败 {result['failed_count']}"
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"QMT 持仓导入失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/operate", response_model=dict)
async def operate_position(
    data: PositionOperationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    执行持仓操作（加仓、减仓、分红、拆股、合股、调整成本）

    操作类型:
    - add: 加仓（需要 quantity, price）
    - reduce: 减仓（需要 quantity, price）
    - dividend: 分红（需要 dividend_amount）
    - split: 拆股（需要 ratio，如 "2:1"）
    - merge: 合股（需要 ratio，如 "1:10"）
    - adjust: 调整成本价（需要 new_cost_price）
    """
    try:
        service = get_portfolio_service()
        result = await service.operate_position(
            user_id=current_user["id"],
            data=data
        )
        return ok(data=result, message=result.get("message", "操作成功"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"持仓操作失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓统计接口 ====================

@router.get("/statistics", response_model=dict)
async def get_portfolio_statistics(
    current_user: dict = Depends(get_current_user)
):
    """获取持仓统计"""
    try:
        service = get_portfolio_service()
        stats = await service.get_portfolio_statistics(current_user["id"])
        return ok(data=stats.model_dump())
    except Exception as e:
        logger.error(f"获取持仓统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓研究接口 ====================

@router.post("/analysis", response_model=dict)
async def analyze_portfolio(
    data: PortfolioAnalysisRequest = PortfolioAnalysisRequest(),
    current_user: dict = Depends(get_current_user)
):
    """发起持仓研究"""
    try:
        service = get_portfolio_service()
        report = await service.analyze_portfolio(
            user_id=current_user["id"],
            include_paper=data.include_paper,
            research_depth=data.research_depth
        )

        # 转换为响应格式
        response_data = {
            "analysis_id": report.analysis_id,
            "status": report.status.value,
            "health_score": report.health_score,
            "risk_level": report.risk_level,
            "portfolio_snapshot": report.portfolio_snapshot.model_dump(),
            "industry_distribution": [d.model_dump() for d in report.industry_distribution],
            "concentration_analysis": report.concentration_analysis.model_dump(),
            "ai_analysis": report.ai_analysis.model_dump(),
            "execution_time": report.execution_time,
            "error_message": report.error_message,
            "created_at": report.created_at.isoformat()
        }

        return ok(data=response_data)
    except Exception as e:
        logger.error(f"持仓研究失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/analysis/history", response_model=dict)
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """获取分析历史"""
    try:
        service = get_portfolio_service()
        result = await service.get_analysis_history(
            user_id=current_user["id"],
            page=page,
            page_size=page_size
        )

        # 转换ObjectId
        items = []
        for item in result["items"]:
            item["_id"] = str(item["_id"]) if "_id" in item else None
            items.append(item)

        return ok(data={
            "items": items,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"]
        })
    except Exception as e:
        logger.error(f"获取分析历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/analysis/{analysis_id}", response_model=dict)
async def get_analysis_detail(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取研究报告详情"""
    try:
        service = get_portfolio_service()
        report = await service.get_analysis_detail(analysis_id)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="研究报告不存在"
            )

        # 验证用户权限
        if report.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该报告"
            )

        # 如果报告包含ai_analysis，检查并转换action_reason
        if report.get("ai_analysis") and report["ai_analysis"].get("action_reason"):
            action_reason_raw = report["ai_analysis"]["action_reason"]
            logger.info(f"📊 [分析详情接口] 原始action_reason类型: {type(action_reason_raw)}, 长度: {len(str(action_reason_raw)) if action_reason_raw else 0}")
            
            import json
            advice_json = None
            
            if isinstance(action_reason_raw, str):
                action_reason_str = action_reason_raw.strip()
                if "```json" in action_reason_str or (action_reason_str.startswith("{") and ("analysis_summary" in action_reason_str or "neutral_operation" in action_reason_str)):
                    try:
                        if "```json" in action_reason_str:
                            json_start = action_reason_str.find("```json") + 7
                            json_end = action_reason_str.find("```", json_start)
                            if json_end > json_start:
                                json_str = action_reason_str[json_start:json_end].strip()
                                advice_json = json.loads(json_str)
                        elif action_reason_str.strip().startswith("{"):
                            advice_json = json.loads(action_reason_str)
                        
                        if advice_json:
                            logger.info(f"📊 [分析详情接口] JSON解析成功，转换为Markdown")
                            report["ai_analysis"]["action_reason"] = service._convert_action_advice_json_to_markdown(advice_json)
                    except Exception as e:
                        logger.warning(f"⚠️ [分析详情接口] JSON解析失败: {e}")
            elif isinstance(action_reason_raw, dict):
                logger.info(f"📊 [分析详情接口] action_reason是字典格式，转换为Markdown")
                report["ai_analysis"]["action_reason"] = service._convert_action_advice_json_to_markdown(action_reason_raw)

        # 转换ObjectId
        report["_id"] = str(report["_id"]) if "_id" in report else None

        return ok(data=report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 单股持仓研究接口 ====================

@router.get("/positions/{position_id}", response_model=dict)
async def get_position_detail(
    position_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取单个持仓详情"""
    try:
        service = get_portfolio_service()
        position = await service.get_position_by_id(current_user["id"], position_id)
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(data=position.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取持仓详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/{position_id}/analysis", response_model=dict)
async def analyze_position(
    position_id: str,
    data: PositionAnalysisRequest = PositionAnalysisRequest(),
    current_user: dict = Depends(get_current_user)
):
    """发起单股持仓研究"""
    try:
        service = get_portfolio_service()
        report = await service.analyze_position(
            user_id=current_user["id"],
            position_id=position_id,
            params=data
        )

        # 检查分析是否失败
        if report.status == PortfolioAnalysisStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=report.error_message or "研究失败"
            )

        snapshot_dict = report.position_snapshot.model_dump() if report.position_snapshot and hasattr(report.position_snapshot, "model_dump") else {}
        ai_analysis_data = report.ai_analysis.model_dump() if report.ai_analysis and hasattr(report.ai_analysis, "model_dump") else {}
        sanitized_ai_analysis = service._sanitize_position_analysis_dict(ai_analysis_data, position_snapshot=snapshot_dict)

        # 转换为响应格式
        response_data = {
            "analysis_id": report.analysis_id,
            "position_id": report.position_id,
            "code": report.position_snapshot.code if report.position_snapshot else None,
            "name": report.position_snapshot.name if report.position_snapshot else None,
            "status": report.status.value,
            "action": sanitized_ai_analysis.get("action"),
            "action_reason": sanitized_ai_analysis.get("action_reason"),
            "confidence": sanitized_ai_analysis.get("confidence"),
            "price_targets": sanitized_ai_analysis.get("price_targets"),
            "risk_assessment": sanitized_ai_analysis.get("risk_assessment"),
            "opportunity_assessment": sanitized_ai_analysis.get("opportunity_assessment"),
            "detailed_analysis": sanitized_ai_analysis.get("detailed_analysis"),
            "user_view": sanitized_ai_analysis.get("user_view", {}),
            "appendix_sections": sanitized_ai_analysis.get("appendix_sections", []),
            "execution_time": report.execution_time,
            "error_message": report.error_message,
            "created_at": report.created_at.isoformat()
        }

        return ok(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"单股持仓研究失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class CheckCacheRequest(BaseModel):
    """检查缓存请求"""
    code: str = Field(..., description="股票代码")
    market: str = Field("CN", description="市场类型（CN/HK/US）")


@router.post("/positions/check-cache", response_model=dict)
async def check_stock_analysis_cache(
    data: CheckCacheRequest,
    current_user: dict = Depends(get_current_user)
):
    """检查单股研究报告缓存状态
    
    在开始持仓研究前，先检查是否有可用的单股研究报告缓存。
    如果没有缓存，前端可以提示用户选择：
    1. 继续研究（不使用单股研究报告）
    2. 先去单股研究页面进行研究
    
    Args:
        data: 检查缓存请求，包含股票代码和市场类型
        
    Returns:
        缓存状态信息，包含：
        - has_cache: 是否有缓存
        - cache_age_hours: 缓存时间（小时）
        - cache_age_minutes: 缓存时间（分钟）
        - source: 缓存来源
        - task_id: 任务ID（如果有）
        - created_at: 缓存创建时间
    """
    try:
        from app.services.portfolio_service import get_portfolio_service, convert_market_code_to_name
        
        portfolio_service = get_portfolio_service()
        
        # 将市场代码转换为中文名称（A股/港股/美股）
        market_name = convert_market_code_to_name(data.market, data.code)
        
        logger.info(f"🔍 [检查缓存] 检查单股研究报告缓存: code={data.code}, market={data.market} -> {market_name}")
        
        cache_status = await portfolio_service.check_stock_analysis_cache(
            stock_code=data.code,
            market=market_name
        )
        
        logger.info(f"✅ [检查缓存] 缓存状态: has_cache={cache_status.get('has_cache')}, "
                   f"age={cache_status.get('cache_age_minutes')}分钟")
        
        return ok(data=cache_status, message="缓存状态查询成功")
        
    except Exception as e:
        logger.error(f"❌ [检查缓存] 查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询缓存状态失败: {str(e)}"
        )


@router.post("/positions/analyze-by-code", response_model=dict)
async def analyze_position_by_code(
    data: PositionAnalysisByCodeRequest,
    current_user: dict = Depends(get_current_user)
):
    """按股票代码分析持仓（异步模式）

    立即返回任务ID，后台执行分析。
    前端可通过 GET /api/analysis/tasks/{task_id}/status 查询分析状态和结果。

    使用新的统一任务中心进行管理。
    """
    import asyncio

    try:
        logger.info(f"📥 [持仓研究路由] 收到请求: code={data.code}, market={data.market}, user_id={current_user['id']}")
        
        from app.services.unified_analysis_service import get_unified_analysis_service

        unified_service = get_unified_analysis_service()
        logger.info(f"✅ [持仓研究路由] 获取到 UnifiedAnalysisService 实例")

        # 准备任务参数
        task_params = {
            "research_depth": data.research_depth,
            "include_add_position": data.include_add_position,
            "target_profit_pct": data.target_profit_pct,
            "total_capital": data.total_capital,
            "max_position_pct": data.max_position_pct,
            "max_loss_pct": data.max_loss_pct,
            "risk_tolerance": data.risk_tolerance,
            "investment_horizon": data.investment_horizon,
            "analysis_focus": data.analysis_focus,
            "position_type": data.position_type,
        }
        logger.info(f"📋 [持仓研究路由] 任务参数准备完成: {list(task_params.keys())}")

        # 创建统一研究任务
        logger.info(f"🔄 [持仓研究路由] 开始创建任务...")
        result = await unified_service.create_position_analysis_task(
            user_id=current_user["id"],
            code=data.code,
            market=data.market,
            task_params=task_params
        )
        logger.info(f"✅ [持仓研究路由] 任务创建成功: task_id={result['task_id']}")
        
        # 为了兼容前端，同时返回analysis_id字段（等于task_id）
        result["analysis_id"] = result["task_id"]

        # 后台执行研究
        logger.info(f"🚀 [持仓研究路由] 启动后台任务执行...")
        asyncio.create_task(
            unified_service.execute_position_analysis(
                task_id=result["task_id"],
                user_id=current_user["id"],
                code=data.code,
                market=data.market,
                task_params=task_params
            )
        )
        logger.info(f"✅ [持仓研究路由] 后台任务已启动")

        return ok(data=result, message="持仓研究任务已提交，预计需要2-5分钟完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [持仓研究路由] 创建任务失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/analysis/{task_id}", response_model=dict)
async def get_position_analysis_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取持仓研究任务状态和结果

    注意：此接口已改为使用统一任务中心，task_id 即为任务ID。
    也可以使用 GET /api/analysis/tasks/{task_id}/status 接口查询。
    """
    try:
        from app.core.database import get_mongo_db
        from bson import ObjectId

        db = get_mongo_db()

        # 从统一任务中心获取任务
        task = await db.unified_analysis_tasks.find_one({
            "task_id": task_id,
            "user_id": ObjectId(current_user["id"])
        })

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="研究任务不存在"
            )

        # 格式化返回数据
        task_status = task["status"]
        if hasattr(task_status, "value"):
            task_status = task_status.value
        elif isinstance(task_status, str):
            task_status = task_status
        else:
            task_status = str(task_status)
        
        # 辅助函数：将datetime或字符串转换为ISO格式字符串
        def to_iso_string(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)
        
        result_data = {
            "task_id": task["task_id"],
            "code": task["task_params"].get("code"),
            "market": task["task_params"].get("market"),
            "status": task_status,
            "message": task.get("message"),
            "progress": task.get("progress", 0),
            "created_at": to_iso_string(task.get("created_at")),
            "started_at": to_iso_string(task.get("started_at")),
            "completed_at": to_iso_string(task.get("completed_at")),
            "error_message": task.get("error_message"),
        }
        
        # 如果任务已完成且有结果，将result中的字段展平到顶层，以匹配前端期望的数据结构
        task_result = task.get("result")
        if task_result and isinstance(task_result, dict):
            # 提取analysis_id（如果有）
            if "analysis_id" in task_result:
                result_data["analysis_id"] = task_result["analysis_id"]
            
            # 提取position_snapshot中的字段
            position_snapshot = task_result.get("position_snapshot")
            if position_snapshot:
                result_data["code"] = position_snapshot.get("code") or result_data.get("code")
                result_data["name"] = position_snapshot.get("name")
                # 构建position_id
                if position_snapshot.get("code") and position_snapshot.get("market"):
                    result_data["position_id"] = f"{position_snapshot['code']}_{position_snapshot['market']}"
            elif result_data.get("code") and result_data.get("market"):
                # 如果没有snapshot，使用code和market构建position_id
                result_data["position_id"] = f"{result_data['code']}_{result_data['market']}"
            
            # 提取ai_analysis中的字段并展平到顶层
            ai_analysis = task_result.get("ai_analysis")
            if ai_analysis:
                service = get_portfolio_service()
                sanitized_ai_analysis = service._sanitize_position_analysis_dict(ai_analysis, position_snapshot=position_snapshot or {})
                # action可能是枚举类型，需要转换为字符串
                action_value = sanitized_ai_analysis.get("action")
                if hasattr(action_value, "value"):
                    action_value = action_value.value
                result_data["action"] = action_value
                result_data["action_reason"] = sanitized_ai_analysis.get("action_reason", "")
                result_data["recommendation"] = sanitized_ai_analysis.get("recommendation", "")
                result_data["confidence"] = sanitized_ai_analysis.get("confidence")
                result_data["price_targets"] = sanitized_ai_analysis.get("price_targets")
                result_data["risk_assessment"] = sanitized_ai_analysis.get("risk_assessment")
                result_data["opportunity_assessment"] = sanitized_ai_analysis.get("opportunity_assessment")
                result_data["detailed_analysis"] = sanitized_ai_analysis.get("detailed_analysis")
                result_data["user_view"] = sanitized_ai_analysis.get("user_view", {})
                result_data["appendix_sections"] = sanitized_ai_analysis.get("appendix_sections", [])
                result_data["suggested_quantity"] = sanitized_ai_analysis.get("suggested_quantity")
                result_data["suggested_amount"] = sanitized_ai_analysis.get("suggested_amount")
                result_data["risk_metrics"] = sanitized_ai_analysis.get("risk_metrics")
            
            # 保留result字段，但需要确保内部的recommendation也被转换
            # 创建一个副本，避免修改原始数据
            result_copy = task_result.copy() if isinstance(task_result, dict) else task_result
            if isinstance(result_copy, dict) and "ai_analysis" in result_copy:
                ai_analysis_copy = result_copy["ai_analysis"].copy() if isinstance(result_copy["ai_analysis"], dict) else result_copy["ai_analysis"]
                if isinstance(ai_analysis_copy, dict):
                    # 如果顶层的recommendation已经转换，同步到result内部
                    if "recommendation" in result_data:
                        ai_analysis_copy["recommendation"] = result_data["recommendation"]
                        logger.info(f"📊 [持仓研究接口] 同步转换后的recommendation到result.ai_analysis")
                    # 如果顶层的action_reason已经转换，也同步到result内部
                    if "action_reason" in result_data:
                        ai_analysis_copy["action_reason"] = result_data["action_reason"]
                        logger.info(f"📊 [持仓研究接口] 同步转换后的action_reason到result.ai_analysis")
                    if "detailed_analysis" in result_data:
                        ai_analysis_copy["detailed_analysis"] = result_data["detailed_analysis"]
                    if "user_view" in result_data:
                        ai_analysis_copy["user_view"] = result_data["user_view"]
                    if "appendix_sections" in result_data:
                        ai_analysis_copy["appendix_sections"] = result_data["appendix_sections"]
                    result_copy["ai_analysis"] = ai_analysis_copy
            result_data["result"] = result_copy
            
            # 提取execution_time
            if "execution_time" in task_result:
                result_data["execution_time"] = task_result["execution_time"]
        else:
            # 如果没有result，保持原样
            result_data["result"] = task_result

        return ok(data=result_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/analysis-by-code/{code}", response_model=dict)
async def get_position_analysis_by_code(
    code: str,
    market: str = Query("CN", description="市场: CN/HK/US"),
    source: str = Query("real", description="数据来源: real(用户持仓)/paper(模拟持仓)"),
    current_user: dict = Depends(get_current_user)
):
    """按股票代码获取最新的研究报告"""
    try:
        service = get_portfolio_service()
        # 🔥 将 source 转换为 position_type
        position_type = "simulated" if source == "paper" else "real"
        report = await service.get_latest_position_analysis(
            user_id=current_user["id"],
            code=code,
            market=market,
            position_type=position_type
        )

        if not report:
            return ok(data=None, message="暂无研究报告")

        return ok(data=report)
    except Exception as e:
        logger.error(f"获取持仓研究报告失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/{position_id}/analysis/history", response_model=dict)
async def get_position_analysis_history(
    position_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    source: str = Query("real", description="数据来源: real(用户持仓)/paper(模拟持仓)"),
    current_user: dict = Depends(get_current_user)
):
    """获取单股研究历史"""
    try:
        service = get_portfolio_service()
        # 🔥 将 source 转换为 position_type
        position_type = "simulated" if source == "paper" else "real"
        result = await service.get_position_analysis_history(
            user_id=current_user["id"],
            position_id=position_id,
            page=page,
            page_size=page_size,
            position_type=position_type
        )

        # 转换ObjectId
        items = []
        for item in result["items"]:
            item["_id"] = str(item["_id"]) if "_id" in item else None
            items.append(item)

        return ok(data={
            "items": items,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"]
        })
    except Exception as e:
        logger.error(f"获取单股研究历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/positions/analysis/{analysis_id}", response_model=dict)
async def delete_position_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除持仓研究报告"""
    try:
        from app.core.database import get_mongo_db
        from bson import ObjectId
        
        db = get_mongo_db()
        
        # 查找研究报告
        report = await db["position_analysis_reports"].find_one({
            "analysis_id": analysis_id,
            "user_id": current_user["id"]
        })
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="研究报告不存在"
            )
        
        # 删除研究报告
        result = await db["position_analysis_reports"].delete_one({
            "analysis_id": analysis_id,
            "user_id": current_user["id"]
        })
        
        if result.deleted_count > 0:
            logger.info(f"✅ 删除持仓研究报告成功: {analysis_id}")
            return ok(message="删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除持仓研究报告失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 资金账户接口 ====================

@router.get("/account", response_model=dict)
async def get_account(current_user: dict = Depends(get_current_user)):
    """获取资金账户信息"""
    try:
        service = get_portfolio_service()
        acc = await service.get_or_create_account(current_user["id"])
        # 移除 _id
        acc.pop("_id", None)
        return ok(data=acc)
    except Exception as e:
        logger.error(f"获取资金账户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/account/summary", response_model=dict)
async def get_account_summary(current_user: dict = Depends(get_current_user)):
    """获取账户摘要（含持仓市值和收益计算）"""
    try:
        service = get_portfolio_service()
        summary = await service.get_account_summary(current_user["id"])
        return ok(data=summary.model_dump())
    except Exception as e:
        logger.error(f"获取账户摘要失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/initialize", response_model=dict)
async def initialize_account(
    request: AccountInitRequest,
    current_user: dict = Depends(get_current_user)
):
    """初始化资金账户（设置初始资金）"""
    try:
        service = get_portfolio_service()
        acc = await service.initialize_account(
            user_id=current_user["id"],
            initial_capital=request.initial_capital,
            currency=request.currency
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"已设置初始资金 {request.initial_capital:,.2f} {request.currency}")
    except Exception as e:
        logger.error(f"初始化资金账户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/deposit", response_model=dict)
async def deposit(
    request: AccountTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """入金"""
    if request.transaction_type != CapitalTransactionType.DEPOSIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="交易类型必须为 deposit"
        )
    try:
        service = get_portfolio_service()
        acc = await service.deposit(
            user_id=current_user["id"],
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"入金成功 {request.amount:,.2f} {request.currency}")
    except Exception as e:
        logger.error(f"入金失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/withdraw", response_model=dict)
async def withdraw(
    request: AccountTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """出金"""
    if request.transaction_type != CapitalTransactionType.WITHDRAW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="交易类型必须为 withdraw"
        )
    try:
        service = get_portfolio_service()
        acc = await service.withdraw(
            user_id=current_user["id"],
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"出金成功 {request.amount:,.2f} {request.currency}")
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"出金失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/account/settings", response_model=dict)
async def update_account_settings(
    request: AccountSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新账户设置"""
    try:
        service = get_portfolio_service()
        acc = await service.update_account_settings(
            user_id=current_user["id"],
            settings=request
        )
        acc.pop("_id", None)
        return ok(data=acc, message="账户设置已更新")
    except Exception as e:
        logger.error(f"更新账户设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/account/transactions", response_model=dict)
async def get_transactions(
    currency: str = Query(None, description="货币类型过滤"),
    limit: int = Query(50, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """获取资金交易记录"""
    try:
        service = get_portfolio_service()
        transactions = await service.get_transactions(
            user_id=current_user["id"],
            currency=currency,
            limit=limit
        )
        return ok(data={"items": transactions, "total": len(transactions)})
    except Exception as e:
        logger.error(f"获取资金交易记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓变动记录接口 ====================

@router.get("/position-changes", response_model=dict)
async def get_position_changes(
    code: str = Query(None, description="股票代码过滤"),
    market: str = Query(None, description="市场过滤: CN/HK/US"),
    change_type: str = Query(None, description="变动类型: buy/add/reduce/sell/adjust"),
    limit: int = Query(100, description="返回数量限制"),
    skip: int = Query(0, description="跳过数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取持仓变动记录"""
    try:
        service = get_portfolio_service()
        changes = await service.get_position_changes(
            user_id=current_user["id"],
            code=code,
            market=market,
            change_type=change_type,
            limit=limit,
            skip=skip
        )
        total = await service.get_position_changes_count(
            user_id=current_user["id"],
            code=code,
            market=market,
            change_type=change_type
        )
        return ok(data={
            "items": [c.model_dump() for c in changes],
            "total": total,
            "limit": limit,
            "skip": skip
        })
    except Exception as e:
        logger.error(f"获取持仓变动记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/position-changes/{change_id}", response_model=dict)
async def update_position_change(
    change_id: str,
    data: PositionChangeUpdate,
    current_user: dict = Depends(get_current_user)
):
    """修改单笔交易记录（用于修正录入错误：数量、单价，支持买入/加仓/减仓/卖出）"""
    try:
        service = get_portfolio_service()
        result = await service.update_position_change(
            user_id=current_user["id"],
            change_id=change_id,
            quantity=data.quantity,
            price=data.price,
            trade_time=data.trade_time
        )
        return ok(data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"修改单笔成本失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/position-changes/{change_id}", response_model=dict)
async def delete_position_change(
    change_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除单笔变动记录，级联重算后续记录"""
    try:
        service = get_portfolio_service()
        result = await service.delete_position_change(
            user_id=current_user["id"],
            change_id=change_id
        )
        return ok(data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"删除变动记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/reset", response_model=dict)
async def reset_position(
    code: str = Query(..., description="股票代码"),
    market: str = Query("CN", description="市场: CN/HK/US"),
    current_user: dict = Depends(get_current_user)
):
    """重置整个持仓：删除该股票的所有变动记录和持仓"""
    try:
        service = get_portfolio_service()
        result = await service.reset_position(
            user_id=current_user["id"],
            code=code,
            market=market
        )
        return ok(data=result)
    except Exception as e:
        logger.error(f"重置持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/reset-all", response_model=dict)
async def reset_all_positions(
    current_user: dict = Depends(get_current_user)
):
    """清零全部持仓：删除该用户所有持仓和变动记录"""
    try:
        service = get_portfolio_service()
        result = await service.reset_all_positions(user_id=current_user["id"])
        return ok(data=result)
    except Exception as e:
        logger.error(f"清零全部持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
