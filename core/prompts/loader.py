"""
提示词加载器

从文件系统加载提示词模板
"""

import os
from pathlib import Path
from typing import Dict, Optional

from .template import PromptTemplate


class PromptLoader:
    """
    提示词加载器
    
    从 prompts/ 目录加载提示词模板
    
    目录结构:
        prompts/
        ├── en/
        │   ├── analysts/
        │   │   ├── market_analyst.txt
        │   │   └── news_analyst.txt
        │   └── researchers/
        │       └── bull_researcher.txt
        └── zh/
            ├── analysts/
            │   ├── market_analyst.txt
            │   └── news_analyst.txt
            └── researchers/
                └── bull_researcher.txt
    """
    
    DEFAULT_PROMPTS_DIR = "prompts"
    
    def __init__(self, prompts_dir: Optional[str] = None):
        self.prompts_dir = Path(prompts_dir or self.DEFAULT_PROMPTS_DIR)
        self._cache: Dict[str, PromptTemplate] = {}
    
    def load(
        self,
        name: str,
        language: str = "zh",
        category: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """
        加载提示词模板
        
        Args:
            name: 模板名称 (不含扩展名)
            language: 语言 (zh/en)
            category: 类别 (analysts/researchers/traders)
            
        Returns:
            提示词模板，如果不存在返回 None
        """
        cache_key = f"{language}/{category}/{name}" if category else f"{language}/{name}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 构建文件路径
        if category:
            file_path = self.prompts_dir / language / category / f"{name}.txt"
        else:
            file_path = self.prompts_dir / language / f"{name}.txt"
        
        # 尝试加载
        if not file_path.exists():
            # 尝试 .md 扩展名
            file_path = file_path.with_suffix('.md')
            if not file_path.exists():
                return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            template = PromptTemplate(
                template=content,
                name=name,
                language=language
            )
            
            self._cache[cache_key] = template
            return template
            
        except Exception as e:
            print(f"加载提示词失败 {file_path}: {e}")
            return None
    
    def load_all(
        self,
        language: str = "zh",
        category: Optional[str] = None
    ) -> Dict[str, PromptTemplate]:
        """
        加载指定目录下的所有提示词
        
        Args:
            language: 语言
            category: 类别
            
        Returns:
            {name: template} 字典
        """
        templates = {}
        
        if category:
            dir_path = self.prompts_dir / language / category
        else:
            dir_path = self.prompts_dir / language
        
        if not dir_path.exists():
            return templates
        
        for file_path in dir_path.glob("*.txt"):
            name = file_path.stem
            template = self.load(name, language, category)
            if template:
                templates[name] = template
        
        for file_path in dir_path.glob("*.md"):
            name = file_path.stem
            if name not in templates:
                template = self.load(name, language, category)
                if template:
                    templates[name] = template
        
        return templates
    
    def exists(
        self,
        name: str,
        language: str = "zh",
        category: Optional[str] = None
    ) -> bool:
        """检查提示词是否存在"""
        if category:
            file_path = self.prompts_dir / language / category / f"{name}.txt"
        else:
            file_path = self.prompts_dir / language / f"{name}.txt"
        
        return file_path.exists() or file_path.with_suffix('.md').exists()
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()

