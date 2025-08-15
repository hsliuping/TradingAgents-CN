"""
帝国AI角色模块
Imperial Agents Roles Module
"""

from .base_role import BaseImperialRole
from .wyckoff_ai import WyckoffAI
from .marenhui_ai import MarenhuiAI
from .crocodile_mentor_ai import CrocodileMentorAI

__all__ = [
    'BaseImperialRole',
    'WyckoffAI', 
    'MarenhuiAI',
    'CrocodileMentorAI'
]
