#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - Agents模块

包含所有Agent定义和工具
"""

from .smart_agents import (
    create_performance_analyst,
    create_market_intelligence,
    create_smart_screener,
    create_multi_dimensional_analyst,
    create_risk_manager,
    create_investment_officer,
    create_all_smart_agents
)

__all__ = [
    'create_performance_analyst',
    'create_market_intelligence',
    'create_smart_screener',
    'create_multi_dimensional_analyst',
    'create_risk_manager',
    'create_investment_officer',
    'create_all_smart_agents'
]
