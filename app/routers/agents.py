import json
import os
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.routers.auth_db import get_current_user
from uuid import uuid4

router = APIRouter(prefix="/api/agents", tags=["agents"])
AGENTS_CONFIG_FILE = "agents_config.json"

class AgentConfig(BaseModel):
    id: str
    name: str
    stage: str # analysis, research, risk, trading
    type: str # market, social, custom, etc.
    description: Optional[str] = ""
    prompt: Optional[str] = ""
    enabled: bool = True
    is_system: bool = False # If true, cannot be deleted

# Default System Agents
DEFAULT_AGENTS = [
    # Analysis Stage
    {
        "id": "market_analyst",
        "name": "Market Analyst",
        "stage": "analysis",
        "type": "market",
        "description": "Analyzes market trends and technical indicators.",
        "is_system": True,
        "enabled": True
    },
    {
        "id": "social_analyst",
        "name": "Social Media Analyst",
        "stage": "analysis",
        "type": "social",
        "description": "Analyzes social media sentiment and discussions.",
        "is_system": True,
        "enabled": True
    },
    {
        "id": "news_analyst",
        "name": "News Analyst",
        "stage": "analysis",
        "type": "news",
        "description": "Monitors and analyzes financial news.",
        "is_system": True,
        "enabled": True
    },
    {
        "id": "fundamentals_analyst",
        "name": "Fundamentals Analyst",
        "stage": "analysis",
        "type": "fundamentals",
        "description": "Analyzes company fundamentals and financial reports.",
        "is_system": True,
        "enabled": True
    },
    # Research Stage
    {
        "id": "bull_researcher",
        "name": "Bull Researcher",
        "stage": "research",
        "type": "bull",
        "description": "Researches bullish factors and opportunities.",
        "is_system": True,
        "enabled": True
    },
    {
        "id": "bear_researcher",
        "name": "Bear Researcher",
        "stage": "research",
        "type": "bear",
        "description": "Researches bearish risks and threats.",
        "is_system": True,
        "enabled": True
    },
    {
        "id": "research_manager",
        "name": "Research Manager",
        "stage": "research",
        "type": "manager",
        "description": "Synthesizes research from bull and bear perspectives.",
        "is_system": True,
        "enabled": True
    },
    # Risk Stage
    {
        "id": "risk_manager",
        "name": "Risk Manager",
        "stage": "risk",
        "type": "risk_manager",
        "description": "Evaluates overall trading risks.",
        "is_system": True,
        "enabled": True
    },
    # Trading Stage
    {
        "id": "trader",
        "name": "Trader",
        "stage": "trading",
        "type": "trader",
        "description": "Executes trades based on analysis and risk assessment.",
        "is_system": True,
        "enabled": True
    }
]

def _load_config() -> List[Dict[str, Any]]:
    if not os.path.exists(AGENTS_CONFIG_FILE):
        return []
    try:
        with open(AGENTS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading agents config: {e}")
        return []

def _save_config(config: List[Dict[str, Any]]):
    with open(AGENTS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

@router.get("/")
async def list_agents(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    custom_agents = _load_config()
    
    # Merge logic:
    # Start with default agents
    merged = {agent["id"]: agent.copy() for agent in DEFAULT_AGENTS}
    
    # Apply custom configs (overrides or new agents)
    for agent in custom_agents:
        if agent["id"] in merged:
            # Update existing (e.g. prompt, enabled)
            merged[agent["id"]].update(agent)
        else:
            # Add new custom agent
            merged[agent["id"]] = agent
            
    return {"success": True, "data": list(merged.values())}

@router.post("/")
async def save_agent(
    agent: AgentConfig,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    custom_agents = _load_config()
    
    # Check if updating an existing custom config
    found = False
    for i, item in enumerate(custom_agents):
        if item["id"] == agent.id:
            custom_agents[i] = agent.model_dump()
            found = True
            break
            
    if not found:
        custom_agents.append(agent.model_dump())
        
    _save_config(custom_agents)
    return {"success": True, "data": agent}

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    # Check if system agent
    is_system = any(a["id"] == agent_id for a in DEFAULT_AGENTS)
    
    custom_agents = _load_config()
    
    if is_system:
        # For system agents, "delete" means resetting to default (removing from custom config)
        original_len = len(custom_agents)
        custom_agents = [a for a in custom_agents if a["id"] != agent_id]
        if len(custom_agents) < original_len:
            _save_config(custom_agents)
            return {"success": True, "message": "Reset to default"}
        else:
            return {"success": True, "message": "Already default"}
    else:
        # For custom agents, actually delete
        custom_agents = [a for a in custom_agents if a["id"] != agent_id]
        _save_config(custom_agents)
        return {"success": True, "message": "Agent deleted"}
