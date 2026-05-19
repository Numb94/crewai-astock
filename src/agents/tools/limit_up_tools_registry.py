#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
涨停板分析工具注册器

功能：
1. 根据环境变量控制是否启用涨停板分析工具
2. 提供工具列表给Agent使用

作者: AI Architect
日期: 2025-11-09
"""

import os
from typing import List
from crewai.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


def get_limit_up_tools() -> List[BaseTool]:
    """
    获取涨停板分析工具列表
    
    根据环境变量 ENABLE_LIMIT_UP_ANALYSIS 决定是否启用
    - true: 返回涨停板分析工具列表
    - false: 返回空列表（默认）
    
    Returns:
        工具列表（如果启用）或空列表（如果未启用）
    """
    # 读取环境变量（默认为false）
    enabled = os.getenv('ENABLE_LIMIT_UP_ANALYSIS', 'false').lower() == 'true'
    
    if not enabled:
        logger.info("⚠️ 涨停板分析工具未启用（ENABLE_LIMIT_UP_ANALYSIS=false）")
        return []  # 返回空列表，不影响现有功能
    
    # 启用时，导入并返回工具
    try:
        from .limit_up_analyzer import (
            analyze_yesterday_limit_up,
            screen_limit_up_concept_stocks
        )
        from .limit_up_pattern_matcher import (
            find_similar_stocks_to_limit_up
        )

        logger.info("✅ 涨停板分析工具已启用（ENABLE_LIMIT_UP_ANALYSIS=true）")

        return [
            analyze_yesterday_limit_up,
            screen_limit_up_concept_stocks,
            find_similar_stocks_to_limit_up  # 新增：涨停形态匹配工具
        ]

    except Exception as e:
        logger.error(f"❌ 加载涨停板分析工具失败: {e}")
        return []  # 加载失败时返回空列表，不影响现有功能


def is_limit_up_analysis_enabled() -> bool:
    """
    检查涨停板分析功能是否启用
    
    Returns:
        True: 已启用
        False: 未启用
    """
    return os.getenv('ENABLE_LIMIT_UP_ANALYSIS', 'false').lower() == 'true'

