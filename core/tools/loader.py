"""
工具加载器

动态加载工具模块
"""

import logging
import importlib
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ToolLoader:
    """
    工具加载器
    
    自动发现和加载工具模块
    
    用法:
        loader = ToolLoader()
        
        # 加载所有工具
        loader.load_all()
        
        # 加载特定类别
        loader.load_category("market")
        
        # 加载特定工具
        loader.load_tool("get_stock_market_data_unified")
    """
    
    def __init__(self, tools_dir: Optional[str] = None):
        """
        初始化工具加载器
        
        Args:
            tools_dir: 工具目录路径，默认为 core/tools/implementations
        """
        if tools_dir is None:
            # 默认工具目录
            current_dir = Path(__file__).parent
            tools_dir = current_dir / "implementations"
        
        self.tools_dir = Path(tools_dir)
        self._loaded_modules = set()
    
    def load_all(self) -> int:
        """
        加载所有工具模块
        
        Returns:
            加载的模块数量
        """
        if not self.tools_dir.exists():
            logger.warning(f"工具目录不存在: {self.tools_dir}")
            return 0
        
        count = 0
        
        # 遍历所有 Python 文件
        for py_file in self.tools_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                self._load_module_from_file(py_file)
                count += 1
            except Exception as e:
                logger.error(f"加载工具模块失败 {py_file}: {e}")
        
        logger.info(f"✅ 加载了 {count} 个工具模块")
        return count
    
    def load_category(self, category: str) -> int:
        """
        加载特定类别的工具
        
        Args:
            category: 工具类别（对应子目录名）
            
        Returns:
            加载的模块数量
        """
        category_dir = self.tools_dir / category
        
        if not category_dir.exists():
            logger.warning(f"类别目录不存在: {category_dir}")
            return 0
        
        count = 0
        
        for py_file in category_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                self._load_module_from_file(py_file)
                count += 1
            except Exception as e:
                logger.error(f"加载工具模块失败 {py_file}: {e}")
        
        logger.info(f"✅ 加载了 {count} 个 {category} 类别的工具")
        return count
    
    def load_tool(self, tool_id: str) -> bool:
        """
        加载特定工具
        
        Args:
            tool_id: 工具ID
            
        Returns:
            是否加载成功
        """
        # 尝试从各个类别目录查找
        for category_dir in self.tools_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            # 尝试 tool_id.py
            tool_file = category_dir / f"{tool_id}.py"
            if tool_file.exists():
                try:
                    self._load_module_from_file(tool_file)
                    logger.info(f"✅ 加载工具: {tool_id}")
                    return True
                except Exception as e:
                    logger.error(f"加载工具失败 {tool_id}: {e}")
                    return False
        
        logger.warning(f"找不到工具: {tool_id}")
        return False
    
    def _load_module_from_file(self, file_path: Path) -> None:
        """
        从文件加载模块

        Args:
            file_path: Python 文件路径
        """
        # 计算模块名：从项目根目录开始
        # 例如：C:\TradingAgentsCN\core\tools\implementations\market\stock_market_data.py
        # 应该变成：core.tools.implementations.market.stock_market_data

        # 获取项目根目录（假设是当前工作目录或者向上查找）
        current_dir = Path.cwd()

        try:
            rel_path = file_path.relative_to(current_dir)
        except ValueError:
            # 如果文件不在当前目录下，尝试使用绝对路径的后几段
            # 从 core 开始
            parts = file_path.parts
            if 'core' in parts:
                core_index = parts.index('core')
                rel_path = Path(*parts[core_index:])
            else:
                raise ValueError(f"无法计算模块路径: {file_path}")

        module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")

        # 避免重复加载
        if module_name in self._loaded_modules:
            return

        # 导入模块
        importlib.import_module(module_name)
        self._loaded_modules.add(module_name)

        logger.debug(f"加载模块: {module_name}")
    
    def get_loaded_modules(self) -> List[str]:
        """获取已加载的模块列表"""
        return list(self._loaded_modules)


# 全局加载器实例
_global_loader: Optional[ToolLoader] = None


def get_tool_loader() -> ToolLoader:
    """获取全局工具加载器"""
    global _global_loader
    if _global_loader is None:
        _global_loader = ToolLoader()
    return _global_loader

