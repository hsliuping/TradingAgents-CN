"""
修复看多和看空研究员的提示词模板，添加必须基于报告分析的约束

采用整体分析方式：
1. 读取完整的模板内容
2. 分析整个结构
3. 统一生成新的模板结构
4. 避免重复的约束文本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_mongo_db_sync
from dotenv import load_dotenv
import os
import re
import logging

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 约束文本（只在system_prompt中使用）
CONSTRAINTS_TEXT = """**⚠️ 重要约束**：
- **必须严格基于用户提示词中提供的实时分析报告进行分析**（包括市场分析、基本面分析、新闻分析、板块分析、大盘分析等）
- **禁止使用LLM内部知识或历史数据进行分析**（如2023年、2024年的数据）
- **如果报告中缺少某些数据，请明确说明"报告中未提供此数据"，不要编造或使用内部知识**
- **所有分析结论必须基于提供的报告内容，不得自行补充或假设数据**"""

# 可用报告列表说明（在user_prompt中使用）
AVAILABLE_REPORTS_INFO = """**📊 可用分析报告**：
以下报告已提供，请基于这些报告进行分析：
- **市场分析报告** (`market_report`): 技术分析、价格走势、成交量等
- **基本面分析报告** (`fundamentals_report`): 财务数据、估值指标、盈利能力等
- **新闻分析报告** (`news_report`): 最新新闻事件、市场动态等
- **社媒分析报告** (`sentiment_report`): 市场情绪、社交媒体讨论等
- **板块分析报告** (`sector_report`): 行业分析、板块表现等
- **大盘分析报告** (`index_report`): 大盘走势、市场环境等

**📈 当前股价**: {current_price} {currency_symbol}（系统实时获取）

**注意**：如果某个报告为空或未提供，请明确说明"该报告未提供"，不要使用内部知识补充。"""


def analyze_template_structure(template_content: dict) -> dict:
    """
    分析模板结构，识别需要调整的部分
    
    Returns:
        {
            'system_prompt': {
                'has_constraints': bool,
                'needs_constraints': bool,
                'content': str
            },
            'user_prompt': {
                'has_constraints': bool,
                'has_reports_info': bool,
                'content': str
            },
            'constraints': {
                'has_duplicate_constraints': bool,
                'content': str
            }
        }
    """
    content = template_content.get("content", {})
    
    analysis = {
        'system_prompt': {
            'has_constraints': False,
            'needs_constraints': False,
            'content': content.get("system_prompt", "")
        },
        'user_prompt': {
            'has_constraints': False,
            'has_reports_info': False,
            'content': content.get("user_prompt", "")
        },
        'constraints': {
            'has_duplicate_constraints': False,
            'content': content.get("constraints", "")
        }
    }
    
    # 分析 system_prompt
    system_prompt = analysis['system_prompt']['content']
    if "必须严格基于用户提示词中提供的实时分析报告" in system_prompt:
        analysis['system_prompt']['has_constraints'] = True
    else:
        analysis['system_prompt']['needs_constraints'] = True
    
    # 分析 user_prompt
    user_prompt = analysis['user_prompt']['content']
    if "必须严格基于" in user_prompt and ("重要要求" in user_prompt or "重要约束" in user_prompt):
        analysis['user_prompt']['has_constraints'] = True
    
    if "可用分析报告" in user_prompt or "📊 可用分析报告" in user_prompt:
        analysis['user_prompt']['has_reports_info'] = True
    
    # 分析 constraints 字段
    constraints = analysis['constraints']['content']
    if "必须严格基于用户提示词中提供的实时分析报告" in constraints:
        analysis['constraints']['has_duplicate_constraints'] = True
    
    return analysis


def rebuild_system_prompt(original: str, needs_constraints: bool) -> str:
    """
    重建 system_prompt，确保包含约束（如果缺失）
    """
    if not needs_constraints:
        return original
    
    # 如果已经有约束，直接返回
    if "必须严格基于用户提示词中提供的实时分析报告" in original:
        return original
    
    # 在合适的位置插入约束
    lines = original.split("\n")
    new_lines = []
    inserted = False
    
    # 查找插入位置：在角色描述之后，职责之前
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # 在角色描述之后插入约束
        if not inserted and (
            line.strip().startswith("你是一位") or 
            line.strip().startswith("您是一位") or
            line.strip().startswith("你是") or
            line.strip().startswith("您是")
        ):
            # 找到下一个空行或段落结束
            j = i + 1
            while j < len(lines) and lines[j].strip() != "":
                j += 1
            
            if j < len(lines):
                new_lines.append("")
                new_lines.append(CONSTRAINTS_TEXT)
                new_lines.append("")
                inserted = True
    
    if not inserted:
        # 如果没找到合适位置，在开头添加
        new_lines.insert(1, "")
        new_lines.insert(2, CONSTRAINTS_TEXT)
        new_lines.insert(3, "")
    
    return "\n".join(new_lines)


def rebuild_user_prompt(original: str, has_constraints: bool, has_reports_info: bool) -> str:
    """
    重建 user_prompt：
    1. 移除约束（如果存在）
    2. 替换或添加可用报告列表
    """
    result = original

    # 1. 移除约束块
    if has_constraints:
        # 使用正则表达式移除约束块
        pattern = r'\n?\*\*⚠️ 重要(要求|约束)\*\*：?\n(- \*\*[^\n]+\*\*[^\n]*\n?)+'
        result = re.sub(pattern, '', result)
        # 清理多余的空行
        result = re.sub(r'\n{3,}', '\n\n', result).rstrip()

    # 2. 移除旧的报告列表（如果存在）
    if has_reports_info:
        # 移除旧的报告列表块（从 "**📊 可用分析报告**" 到下一个空行或段落）
        pattern = r'\*\*📊 可用分析报告\*\*：?[\s\S]*?(?=\n\n|\n\*\*|$)'
        result = re.sub(pattern, '', result)
        # 清理多余的空行
        result = re.sub(r'\n{3,}', '\n\n', result).rstrip()

    # 3. 添加新的报告列表
    if True:  # 总是添加（无论之前是否存在）
        lines = result.split("\n")
        new_lines = []
        inserted = False
        
        # 在"请从"、"请分析"等指令之后插入
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            if not inserted and (
                line.strip().startswith("请从") or 
                line.strip().startswith("请分析") or
                line.strip().startswith("请撰写")
            ):
                # 找到下一个空行
                j = i + 1
                while j < len(lines) and lines[j].strip() != "":
                    j += 1
                
                if j < len(lines):
                    new_lines.append("")
                    new_lines.append(AVAILABLE_REPORTS_INFO)
                    new_lines.append("")
                    inserted = True
        
        if not inserted:
            # 如果没找到合适位置，在开头添加
            if len(lines) > 1:
                new_lines.insert(1, "")
                new_lines.insert(2, AVAILABLE_REPORTS_INFO)
                new_lines.insert(3, "")
            else:
                new_lines.append("")
                new_lines.append(AVAILABLE_REPORTS_INFO)
        
        result = "\n".join(new_lines)
    
    return result.rstrip()


def rebuild_constraints_field(original: str, has_duplicate: bool) -> str:
    """
    重建 constraints 字段：
    1. 移除重复的约束（如果存在）
    2. 如果为空，设置为简单说明
    """
    if not has_duplicate:
        return original
    
    # 移除约束块
    pattern = r'\*\*⚠️ 重要约束\*\*：?\n(- \*\*[^\n]+\*\*[^\n]*\n?)+'
    result = re.sub(pattern, '', original)
    result = re.sub(r'\n{3,}', '\n\n', result).strip()
    
    # 如果清理后为空，设置为简单说明
    if not result or result == "":
        result = "约束要求已在系统提示词中说明。"
    
    return result


def rebuild_template(template_content: dict) -> dict:
    """
    整体重建模板，统一处理所有字段
    """
    # 分析模板结构
    analysis = analyze_template_structure(template_content)
    
    # 重建各个字段
    content = template_content.get("content", {})
    new_content = content.copy()
    
    # 重建 system_prompt
    new_content["system_prompt"] = rebuild_system_prompt(
        analysis['system_prompt']['content'],
        analysis['system_prompt']['needs_constraints']
    )
    
    # 重建 user_prompt
    new_content["user_prompt"] = rebuild_user_prompt(
        analysis['user_prompt']['content'],
        analysis['user_prompt']['has_constraints'],
        analysis['user_prompt']['has_reports_info']
    )
    
    # 重建 constraints 字段
    if "constraints" in content:
        new_content["constraints"] = rebuild_constraints_field(
            analysis['constraints']['content'],
            analysis['constraints']['has_duplicate_constraints']
        )
    else:
        # 如果没有 constraints 字段，创建一个简单说明
        new_content["constraints"] = "约束要求已在系统提示词中说明。"
    
    return new_content


def update_researcher_templates():
    """更新看多和看空研究员的提示词模板"""
    # 连接 MongoDB
    db = get_mongo_db_sync()
    collection = db["prompt_templates"]
    
    # 查找所有看多和看空研究员的模板
    agent_names = ["bull_researcher_v2", "bear_researcher_v2"]
    
    updated_count = 0
    
    for agent_name in agent_names:
        logger.info(f"\n{'='*60}")
        logger.info(f"处理 {agent_name} 的模板...")
        logger.info(f"{'='*60}")
        
        templates = list(collection.find({"agent_name": agent_name}))
        logger.info(f"找到 {len(templates)} 个模板")
        
        for template in templates:
            template_id = template["_id"]
            template_name = template.get("template_name", "未知")
            preference_type = template.get("preference_type", "unknown")
            
            logger.info(f"\n处理模板: {template_name} (偏好: {preference_type})")
            
            # 分析当前模板结构
            analysis = analyze_template_structure(template)
            
            logger.info(f"  分析结果:")
            logger.info(f"    system_prompt: 有约束={analysis['system_prompt']['has_constraints']}, 需要添加={analysis['system_prompt']['needs_constraints']}")
            logger.info(f"    user_prompt: 有约束={analysis['user_prompt']['has_constraints']}, 有报告列表={analysis['user_prompt']['has_reports_info']}")
            logger.info(f"    constraints: 有重复约束={analysis['constraints']['has_duplicate_constraints']}")
            
            # 重建模板
            new_content = rebuild_template(template)
            
            # 检查是否有变化
            old_content = template.get("content", {})
            has_changes = False
            
            if old_content.get("system_prompt") != new_content.get("system_prompt"):
                has_changes = True
                logger.info(f"  ✓ system_prompt 需要更新")
            
            if old_content.get("user_prompt") != new_content.get("user_prompt"):
                has_changes = True
                logger.info(f"  ✓ user_prompt 需要更新")
            
            if old_content.get("constraints") != new_content.get("constraints"):
                has_changes = True
                logger.info(f"  ✓ constraints 需要更新")
            
            if has_changes:
                # 更新模板
                result = collection.update_one(
                    {"_id": template_id},
                    {"$set": {
                        "content.system_prompt": new_content["system_prompt"],
                        "content.user_prompt": new_content["user_prompt"],
                        "content.constraints": new_content["constraints"]
                    }}
                )
                
                if result.modified_count > 0:
                    logger.info(f"  ✅ 模板更新成功")
                    updated_count += 1
                else:
                    logger.warning(f"  ⚠️ 模板更新失败")
            else:
                logger.info(f"  ℹ️ 模板无需更新")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"更新完成！共更新 {updated_count} 个模板")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    update_researcher_templates()
