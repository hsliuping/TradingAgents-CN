"""
SKILL.md 解析器

解析 Agent Skills 标准格式的 SKILL.md 文件：
- YAML frontmatter（--- 分隔的元数据）
- Markdown body（自然语言指令）

支持：
1. 标准 Agent Skills 格式（仅 name + description）
2. 扩展格式（增加 parameters, returns, implementation 等）
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .models import (
    HttpImplementation,
    ImplementationType,
    McpImplementation,
    PythonImplementation,
    SkillImplementation,
    SkillMetadata,
    SkillParameter,
    SkillReturns,
)

logger = logging.getLogger(__name__)


class SkillParser:
    """SKILL.md 文件解析器"""

    @staticmethod
    def parse_file(file_path: str) -> SkillMetadata:
        """
        解析 SKILL.md 文件
        
        Args:
            file_path: SKILL.md 文件路径
            
        Returns:
            SkillMetadata 对象
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"SKILL.md 文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")
        skill = SkillParser.parse_content(content)
        skill.source_file = str(path.resolve())
        return skill

    @staticmethod
    def parse_content(content: str) -> SkillMetadata:
        """
        解析 SKILL.md 内容字符串
        
        Args:
            content: SKILL.md 文件内容
            
        Returns:
            SkillMetadata 对象
        """
        frontmatter, body = SkillParser._split_frontmatter(content)

        if not frontmatter:
            raise ValueError("SKILL.md 必须包含 YAML frontmatter（用 --- 分隔）")

        # 解析 YAML frontmatter
        try:
            metadata = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML frontmatter 解析失败: {e}")

        if not isinstance(metadata, dict):
            raise ValueError("YAML frontmatter 必须是一个字典")

        # 必填字段校验
        if "name" not in metadata:
            raise ValueError("SKILL.md 必须包含 'name' 字段")
        if "description" not in metadata:
            raise ValueError("SKILL.md 必须包含 'description' 字段")

        # 构建 SkillMetadata
        return SkillParser._build_skill_metadata(metadata, body.strip())

    @staticmethod
    def _split_frontmatter(content: str) -> Tuple[Optional[str], str]:
        """分离 YAML frontmatter 和 Markdown body"""
        # 匹配 --- 开头和结尾的 frontmatter
        pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)"
        match = re.match(pattern, content.strip(), re.DOTALL)

        if match:
            return match.group(1), match.group(2)

        return None, content

    @staticmethod
    def _build_skill_metadata(metadata: Dict[str, Any], body: str) -> SkillMetadata:
        """从解析结果构建 SkillMetadata"""
        # 基本字段
        skill_data = {
            "name": metadata["name"],
            "description": metadata["description"],
            "instructions": body,
        }

        # Agent Skills 可选字段
        if "allowed-tools" in metadata or "allowed_tools" in metadata:
            skill_data["allowed_tools"] = metadata.get("allowed-tools") or metadata.get("allowed_tools")

        # 扩展元数据字段
        for field in ("version", "author", "category", "tags", "icon", "color"):
            if field in metadata:
                skill_data[field] = metadata[field]

        # Function Calling 扩展字段
        if "when_to_use" in metadata:
            skill_data["when_to_use"] = metadata["when_to_use"]

        if "examples" in metadata:
            skill_data["examples"] = metadata["examples"]

        # 参数定义
        if "parameters" in metadata and isinstance(metadata["parameters"], list):
            skill_data["parameters"] = [
                SkillParameter(**p) if isinstance(p, dict) else p
                for p in metadata["parameters"]
            ]

        # 返回值定义
        if "returns" in metadata and isinstance(metadata["returns"], dict):
            skill_data["returns"] = SkillReturns(**metadata["returns"])

        # 执行实现
        if "implementation" in metadata and isinstance(metadata["implementation"], dict):
            skill_data["implementation"] = SkillParser._parse_implementation(
                metadata["implementation"]
            )

        # 状态字段
        for field in ("enabled", "fc_enabled"):
            if field in metadata:
                skill_data[field] = metadata[field]

        return SkillMetadata(**skill_data)

    @staticmethod
    def _parse_implementation(impl_data: Dict[str, Any]) -> Optional[SkillImplementation]:
        """解析执行实现配置"""
        impl_type = impl_data.get("type", "").lower()

        if impl_type == "python":
            return PythonImplementation(**impl_data)
        elif impl_type == "http":
            return HttpImplementation(**impl_data)
        elif impl_type == "mcp":
            return McpImplementation(**impl_data)
        else:
            logger.warning(f"未知的执行协议类型: {impl_type}，跳过 implementation")
            return None

