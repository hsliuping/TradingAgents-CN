"""
社媒消息数据API路由
提供社媒消息的查询、搜索和统计接口
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field
import logging

from app.routers.auth_db import get_current_user
from app.services.social_media_service import (
    get_social_media_service,
    SocialMediaQueryParams,
    SocialMediaStats
)
from app.utils.social_media_parser import SocialMediaFileParser
from app.core.response import ok

router = APIRouter(prefix="/api/social-media", tags=["social-media"])
logger = logging.getLogger(__name__)


class SocialMediaMessage(BaseModel):
    """社媒消息模型"""
    message_id: str
    platform: str
    message_type: str = "post"
    content: str
    media_urls: Optional[List[str]] = []
    hashtags: Optional[List[str]] = []
    author: Dict[str, Any]
    engagement: Dict[str, Any]
    publish_time: datetime
    sentiment: Optional[str] = "neutral"
    sentiment_score: Optional[float] = 0.0
    keywords: Optional[List[str]] = []
    topics: Optional[List[str]] = []
    importance: Optional[str] = "low"
    credibility: Optional[str] = "medium"
    location: Optional[Dict[str, str]] = None
    language: str = "none"
    data_source: str
    crawler_version: str = "1.0"


class SocialMediaBatchRequest(BaseModel):
    """批量保存社媒消息请求"""
    symbol: str = Field(..., description="股票代码")
    messages: List[SocialMediaMessage] = Field(..., description="社媒消息列表")


class SocialMediaQueryRequest(BaseModel):
    """社媒消息查询请求"""
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    market: Optional[str] = Field(None, description="市场类型：A股/港股/美股")
    platform: Optional[str] = None
    message_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sentiment: Optional[str] = None
    importance: Optional[str] = None
    min_influence_score: Optional[float] = None
    min_engagement_rate: Optional[float] = None
    verified_only: bool = False
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    limit: int = Field(50, ge=1, le=1000)
    skip: int = Field(0, ge=0)


@router.post("/save", response_model=dict)
async def save_social_media_messages(
    request: SocialMediaBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """批量保存社媒消息"""
    try:
        service = await get_social_media_service()

        # 转换消息格式并添加股票代码
        messages = []
        for msg in request.messages:
            message_dict = msg.dict()
            message_dict["symbol"] = request.symbol
            messages.append(message_dict)

        # 保存消息
        result = await service.save_social_media_messages(messages)

        return ok(
            data=result,
            message=f"成功保存 {result['saved']} 条社媒消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存社媒消息失败: {str(e)}")


@router.post("/query", response_model=dict)
async def query_social_media_messages(
    request: SocialMediaQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """查询社媒消息"""
    try:
        service = await get_social_media_service()

        # 构建查询参数
        params = SocialMediaQueryParams(
            symbol=request.symbol,
            symbols=request.symbols,
            market=request.market,
            platform=request.platform,
            message_type=request.message_type,
            start_time=request.start_time,
            end_time=request.end_time,
            sentiment=request.sentiment,
            importance=request.importance,
            min_influence_score=request.min_influence_score,
            min_engagement_rate=request.min_engagement_rate,
            verified_only=request.verified_only,
            keywords=request.keywords,
            hashtags=request.hashtags,
            limit=request.limit,
            skip=request.skip
        )

        # 执行查询
        messages = await service.query_social_media_messages(params)

        return ok(
            data={
                "messages": messages,
                "count": len(messages),
                "params": request.dict()
            },
            message=f"查询到 {len(messages)} 条社媒消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询社媒消息失败: {str(e)}")


@router.get("/latest/{symbol}", response_model=dict)
async def get_latest_messages(
    symbol: str,
    platform: Optional[str] = Query(None, description="平台类型"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取最新社媒消息"""
    try:
        service = await get_social_media_service()
        messages = await service.get_latest_messages(symbol, platform, limit)
        
        return ok(data={
                "messages": messages,
                "count": len(messages),
                "symbol": symbol,
                "platform": platform
            },
            message=f"获取到 {len(messages)} 条最新消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最新消息失败: {str(e)}")


@router.get("/search", response_model=dict)
async def search_messages(
    query: str = Query(..., description="搜索关键词"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    platform: Optional[str] = Query(None, description="平台类型"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    current_user: dict = Depends(get_current_user)
):
    """全文搜索社媒消息"""
    try:
        service = await get_social_media_service()
        messages = await service.search_messages(query, symbol, platform, limit)

        return ok(
            data={
                "messages": messages,
                "count": len(messages),
                "query": query,
                "symbol": symbol,
                "platform": platform
            },
            message=f"搜索到 {len(messages)} 条相关消息"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索消息失败: {str(e)}")


@router.get("/statistics", response_model=dict)
async def get_statistics(
    symbol: Optional[str] = Query(None, description="股票代码"),
    market: Optional[str] = Query(None, description="市场类型"),
    platform: Optional[str] = Query(None, description="平台类型"),
    sentiment: Optional[str] = Query(None, description="情绪类型"),
    hours_back: Optional[int] = Query(None, ge=1, le=168, description="回溯小时数（可选，不传则统计所有数据）"),
    current_user: dict = Depends(get_current_user)
):
    """获取社媒消息统计信息"""
    try:
        service = await get_social_media_service()
        
        # 计算时间范围（如果指定了hours_back）
        start_time = None
        end_time = None
        if hours_back:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours_back)
        
        stats = await service.get_social_media_statistics(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            market=market,
            platform=platform,
            sentiment=sentiment
        )
        
        return ok(data={
                "statistics": stats.__dict__,
                "query_params": {
                    "symbol": symbol,
                    "market": market,
                    "platform": platform,
                    "sentiment": sentiment
                },
                "time_range": {
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None,
                    "hours_back": hours_back
                }
            },
            message="统计信息获取成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/platforms", response_model=dict)
async def get_supported_platforms(
    current_user: dict = Depends(get_current_user)
):
    """获取支持的社媒平台列表"""
    platforms = [
        {
            "code": "weibo",
            "name": "微博",
            "description": "新浪微博社交平台"
        },
        {
            "code": "wechat",
            "name": "微信",
            "description": "微信公众号和朋友圈"
        },
        {
            "code": "douyin",
            "name": "抖音",
            "description": "字节跳动短视频平台"
        },
        {
            "code": "xiaohongshu",
            "name": "小红书",
            "description": "生活方式分享平台"
        },
        {
            "code": "zhihu",
            "name": "知乎",
            "description": "知识问答社区"
        },
        {
            "code": "twitter",
            "name": "Twitter",
            "description": "国际社交媒体平台"
        },
        {
            "code": "reddit",
            "name": "Reddit",
            "description": "国际论坛社区"
        }
    ]
    
    return ok(data={
            "platforms": platforms,
            "count": len(platforms)
        },
        message="支持的平台列表获取成功"
    )


@router.get("/sentiment-analysis/{symbol}", response_model=dict)
async def get_sentiment_analysis(
    symbol: str,
    platform: Optional[str] = Query(None, description="平台类型"),
    hours_back: int = Query(24, ge=1, le=168, description="回溯小时数"),
    current_user: dict = Depends(get_current_user)
):
    """获取股票的社媒情绪分析"""
    try:
        service = await get_social_media_service()
        
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # 查询消息
        params = SocialMediaQueryParams(
            symbol=symbol,
            platform=platform,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
        
        messages = await service.query_social_media_messages(params)
        
        # 分析情绪分布
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        platform_sentiment = {}
        hourly_sentiment = {}
        
        for msg in messages:
            sentiment = msg.get("sentiment", "neutral")
            sentiment_counts[sentiment] += 1
            
            # 按平台统计
            msg_platform = msg.get("platform", "unknown")
            if msg_platform not in platform_sentiment:
                platform_sentiment[msg_platform] = {"positive": 0, "negative": 0, "neutral": 0}
            platform_sentiment[msg_platform][sentiment] += 1
            
            # 按小时统计
            publish_time = msg.get("publish_time")
            if publish_time:
                hour_key = publish_time.strftime("%Y-%m-%d %H:00")
                if hour_key not in hourly_sentiment:
                    hourly_sentiment[hour_key] = {"positive": 0, "negative": 0, "neutral": 0}
                hourly_sentiment[hour_key][sentiment] += 1
        
        # 计算情绪指数 (positive: +1, neutral: 0, negative: -1)
        total_messages = len(messages)
        sentiment_score = 0
        if total_messages > 0:
            sentiment_score = (sentiment_counts["positive"] - sentiment_counts["negative"]) / total_messages
        
        return ok(data={
                "symbol": symbol,
                "total_messages": total_messages,
                "sentiment_distribution": sentiment_counts,
                "sentiment_score": sentiment_score,
                "platform_sentiment": platform_sentiment,
                "hourly_sentiment": hourly_sentiment,
                "time_range": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "hours_back": hours_back
                }
            },
            message=f"情绪分析完成，共分析 {total_messages} 条消息"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"情绪分析失败: {str(e)}")


@router.post("/upload", response_model=dict)
async def upload_social_media_file(
    file: UploadFile = File(..., description="社媒消息文件（支持JSON、CSV、Excel）"),
    encoding: str = Form("utf-8", description="文件编码（CSV/JSON使用）"),
    overwrite: bool = Form(False, description="是否覆盖已存在的消息"),
    current_user: dict = Depends(get_current_user)
):
    """
    上传社媒消息文件
    
    支持格式：
    - JSON: .json（数组或包含messages字段的对象）
    - CSV: .csv（逗号分隔值）
    - Excel: .xlsx, .xls
    
    必需字段（文件中每条消息必须包含）：
    - message_id: 消息ID（唯一标识）
    - platform: 平台类型
    - symbol: 股票代码
    - content: 消息内容
    - publish_time: 发布时间
    
    可选字段：
    - author: 作者信息（author_id, author_name等）
    - engagement: 互动数据（views, likes, shares, comments）
    - sentiment: 情绪（positive/negative/neutral）
    - hashtags: 话题标签列表
    - keywords: 关键词列表
    - market: 市场类型（A股/港股/美股，如果不提供会根据symbol自动识别）
    """
    try:
        logger.info(f"📤 收到社媒文件上传请求: {file.filename}")
        
        # 读取文件内容
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件内容为空")
        
        logger.info(f"📊 文件大小: {len(content)} 字节")
        
        # 解析文件
        try:
            raw_messages = SocialMediaFileParser.parse_file(content, file.filename, encoding)
            logger.info(f"✅ 文件解析成功: {len(raw_messages)} 条消息")
        except Exception as e:
            logger.error(f"❌ 文件解析失败: {e}")
            raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
        
        if not raw_messages:
            raise HTTPException(status_code=400, detail="文件中没有消息数据")
        
        # 🔥 验证文件中是否包含必需的symbol和platform字段
        missing_fields = []
        for idx, msg in enumerate(raw_messages):
            if not msg.get('symbol'):
                missing_fields.append(f"第{idx+1}条消息缺少symbol字段")
            if not msg.get('platform'):
                missing_fields.append(f"第{idx+1}条消息缺少platform字段")
        
        if missing_fields:
            error_msg = "文件中存在缺少必需字段的消息：\n" + "\n".join(missing_fields[:10])
            if len(missing_fields) > 10:
                error_msg += f"\n...还有{len(missing_fields)-10}条消息有问题"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # 验证和规范化消息（不再传入symbol和platform，从文件中读取）
        normalized_messages = SocialMediaFileParser.validate_and_normalize_messages(raw_messages)
        
        if not normalized_messages:
            raise HTTPException(status_code=400, detail="文件中没有有效的消息数据")
        
        # 统计文件中的股票代码和平台（用于返回信息）
        symbols = set(msg.get('symbol') for msg in normalized_messages if msg.get('symbol'))
        platforms = set(msg.get('platform') for msg in normalized_messages if msg.get('platform'))
        
        # 保存到数据库
        service = await get_social_media_service()
        result = await service.save_social_media_messages(normalized_messages)
        
        logger.info(f"✅ 文件上传完成: {result['saved']}/{len(normalized_messages)} 条消息已保存")
        
        return ok(
            data={
                "filename": file.filename,
                "symbols": list(symbols),  # 文件中的所有股票代码
                "platforms": list(platforms),  # 文件中的所有平台
                "total_messages": len(normalized_messages),
                "saved": result['saved'],
                "failed": result.get('failed', 0),
                "upserted": result.get('upserted', 0),
                "modified": result.get('modified', 0)
            },
            message=f"成功上传并保存 {result['saved']} 条社媒消息"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 文件上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/download-template-file/{file_type}")
async def download_template_file(file_type: str):
    """
    下载模板文件到本地
    
    Args:
        file_type: 文件类型 (json/csv)
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "docs" / "examples"
        
        if file_type == "json":
            file_path = template_dir / "social_media_template.json"
            filename = "social_media_template.json"
            media_type = "application/json"
        elif file_type == "csv":
            file_path = template_dir / "social_media_template.csv"
            filename = "social_media_template.csv"
            media_type = "text/csv"
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_type}")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="模板文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载模板文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载模板文件失败: {str(e)}")


@router.get("/template-content/{file_type}")
async def get_template_content(file_type: str):
    """获取模板文件的原始内容（用于前端渲染）"""
    from fastapi.responses import Response
    from pathlib import Path
    import json
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "docs" / "examples"
        
        if file_type == "json":
            file_path = template_dir / "social_media_template.json"
        elif file_type == "csv":
            file_path = template_dir / "social_media_template.csv"
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_type}")
        
        logger.info(f"📄 尝试读取模板文件: {file_path}")
        logger.info(f"📄 文件是否存在: {file_path.exists()}")
        
        if not file_path.exists():
            logger.error(f"❌ 模板文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail=f"模板文件不存在: {file_path}")
        
        content = file_path.read_text(encoding='utf-8')
        
        # JSON文件格式化
        if file_type == "json":
            try:
                json_data = json.loads(content)
                content = json.dumps(json_data, ensure_ascii=False, indent=2)
            except:
                pass  # 如果解析失败，返回原始内容
        
        logger.info(f"✅ 成功读取模板文件，内容长度: {len(content)} 字符")
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取模板文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取模板文件失败: {str(e)}")


@router.get("/api-example-content")
async def get_api_example_content():
    """获取API示例代码的原始内容（用于前端渲染）"""
    from fastapi.responses import Response
    from pathlib import Path
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "docs" / "examples" / "social_media_api_example.py"
        
        logger.info(f"📄 尝试读取API示例文件: {file_path}")
        logger.info(f"📄 文件是否存在: {file_path.exists()}")
        
        if not file_path.exists():
            logger.error(f"❌ API示例文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail="API示例文件不存在")
        
        content = file_path.read_text(encoding='utf-8')
        logger.info(f"✅ 成功读取API示例文件，内容长度: {len(content)} 字符")
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取API示例文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取API示例文件失败: {str(e)}")


@router.get("/download-template/{file_type}")
async def download_template(file_type: str):
    """
    查看模板文件内容（在新页面中显示）
    
    Args:
        file_type: 文件类型 (json/csv)
    """
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    import json
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "docs" / "examples"
        
        if file_type == "json":
            file_path = template_dir / "social_media_template.json"
            # 读取并格式化JSON
            content = file_path.read_text(encoding='utf-8')
            try:
                json_data = json.loads(content)
                formatted_json = json.dumps(json_data, ensure_ascii=False, indent=2)
            except:
                formatted_json = content
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>JSON模板 - 社媒消息管理</title>
    <style>
        body {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #409EFF;
        }}
        h1 {{
            color: #409EFF;
            margin: 0;
            flex: 1;
        }}
        .download-btn {{
            background: #409EFF;
            color: white !important;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            white-space: nowrap;
            margin-left: 20px;
        }}
        .download-btn:hover {{
            background: #66b1ff;
            color: white !important;
        }}
        pre {{
            background: #f8f8f8;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #e4e7ed;
        }}
        code {{
            font-size: 14px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>JSON模板文件</h1>
            <a href="/api/social-media/download-template-file/json" class="download-btn" download>📥 下载文件</a>
        </div>
        <pre><code>{formatted_json}</code></pre>
    </div>
</body>
</html>"""
            
        elif file_type == "csv":
            file_path = template_dir / "social_media_template.csv"
            content = file_path.read_text(encoding='utf-8')
            
            # 将CSV转换为HTML表格
            lines = content.strip().split('\n')
            if lines:
                headers = lines[0].split(',')
                rows = [line.split(',') for line in lines[1:] if line.strip()]
                
                table_rows = ''.join([
                    f'<tr>{"".join([f"<td>{cell}</td>" for cell in row])}</tr>'
                    for row in rows
                ])
                
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CSV模板 - 社媒消息管理</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #409EFF;
        }}
        h1 {{
            color: #409EFF;
            margin: 0;
            flex: 1;
        }}
        .download-btn {{
            background: #409EFF;
            color: white !important;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            white-space: nowrap;
            margin-left: 20px;
        }}
        .download-btn:hover {{
            background: #66b1ff;
            color: white !important;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            border: 1px solid #e4e7ed;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #f5f7fa;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background: #fafafa;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CSV模板文件</h1>
            <a href="/api/social-media/download-template-file/csv" class="download-btn" download>📥 下载文件</a>
        </div>
        <table>
            <thead>
                <tr>{"".join([f"<th>{header}</th>" for header in headers])}</tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""
            else:
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CSV模板 - 社媒消息管理</title>
</head>
<body>
    <pre>{content}</pre>
</body>
</html>"""
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_type}")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="模板文件不存在")
        
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取模板文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取模板文件失败: {str(e)}")


@router.get("/api-guide-content")
async def get_api_guide_content():
    """获取API接入指南的Markdown原始内容（用于前端渲染）"""
    from fastapi.responses import Response
    from pathlib import Path
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "docs" / "examples" / "social_media_api_guide.md"
        
        logger.info(f"📄 尝试读取API指南文件: {file_path}")
        logger.info(f"📄 文件是否存在: {file_path.exists()}")
        
        if not file_path.exists():
            logger.error(f"❌ API指南文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail=f"API指南文件不存在: {file_path}")
        
        content = file_path.read_text(encoding='utf-8')
        logger.info(f"✅ 成功读取API指南文件，内容长度: {len(content)} 字符")
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取API指南内容失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取API指南内容失败: {str(e)}")


@router.get("/download-api-guide")
async def download_api_guide():
    """查看API接入指南（在新页面中显示）"""
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "docs" / "examples" / "social_media_api_guide.md"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="API指南文件不存在")
        
        # 读取文件内容
        content = file_path.read_text(encoding='utf-8')
        
        # 简单的Markdown转HTML（基本转换）
        html_content = content.replace('\n', '<br>\n')
        html_content = html_content.replace('# ', '<h1>').replace('\n# ', '</h1>\n')
        html_content = html_content.replace('## ', '<h2>').replace('\n## ', '</h2>\n')
        html_content = html_content.replace('### ', '<h3>').replace('\n### ', '</h3>\n')
        html_content = html_content.replace('**', '<strong>').replace('**', '</strong>')
        html_content = html_content.replace('`', '<code>').replace('`', '</code>')
        
        html_page = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>API接入指南 - 社媒消息管理</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #409EFF;
        }}
        h1 {{
            color: #409EFF;
            margin: 0;
            flex: 1;
        }}
        .download-btn {{
            background: #409EFF;
            color: white !important;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            white-space: nowrap;
            margin-left: 20px;
        }}
        .download-btn:hover {{
            background: #66b1ff;
            color: white !important;
        }}
        h2 {{
            color: #606266;
            margin-top: 30px;
            border-left: 4px solid #409EFF;
            padding-left: 10px;
        }}
        h3 {{
            color: #909399;
            margin-top: 20px;
        }}
        code {{
            background: #f5f7fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
        }}
        pre {{
            background: #f8f8f8;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #e4e7ed;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>API接入指南</h1>
            <a href="/api/social-media/download-api-guide-file" class="download-btn" download>📥 下载文件</a>
        </div>
        <div>{html_content}</div>
    </div>
</body>
</html>"""
        
        return HTMLResponse(content=html_page)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取API指南失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取API指南失败: {str(e)}")


@router.get("/download-api-example-file")
async def download_api_example_file():
    """下载API示例代码文件到本地"""
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "docs" / "examples" / "social_media_api_example.py"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="API示例文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename="social_media_api_example.py",
            media_type="text/x-python",
            headers={"Content-Disposition": 'attachment; filename="social_media_api_example.py"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载API示例文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载API示例文件失败: {str(e)}")


@router.get("/download-api-example")
async def download_api_example():
    """查看API示例代码（在新页面中显示）"""
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    import html
    
    try:
        # 获取项目根目录 (app/routers/social_media.py -> app/routers -> app -> 项目根目录)
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / "docs" / "examples" / "social_media_api_example.py"
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="API示例文件不存在")
        
        # 读取文件内容并转义HTML
        content = file_path.read_text(encoding='utf-8')
        escaped_content = html.escape(content)
        
        html_page = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Python示例代码 - 社媒消息管理</title>
    <style>
        body {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #409EFF;
        }}
        h1 {{
            color: #409EFF;
            margin: 0;
            flex: 1;
        }}
        .download-btn {{
            background: #409EFF;
            color: white !important;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            white-space: nowrap;
            margin-left: 20px;
        }}
        .download-btn:hover {{
            background: #66b1ff;
            color: white !important;
        }}
        pre {{
            background: #282c34;
            color: #abb2bf;
            padding: 20px;
            border-radius: 4px;
            overflow-x: auto;
            line-height: 1.5;
            font-size: 14px;
        }}
        code {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Python API示例代码</h1>
            <a href="/api/social-media/download-api-example-file" class="download-btn" download>📥 下载文件</a>
        </div>
        <pre><code>{escaped_content}</code></pre>
    </div>
</body>
</html>"""
        
        return HTMLResponse(content=html_page)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取API示例失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"读取API示例失败: {str(e)}")


@router.get("/health", response_model=dict)
async def health_check():
    """健康检查"""
    try:
        service = await get_social_media_service()
        
        # 简单的连接测试
        collection = await service._get_collection()
        count = await collection.estimated_document_count()
        
        return ok(data={
                "status": "healthy",
                "total_messages": count,
                "service": "social_media_service"
            },
            message="社媒消息服务运行正常"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")
