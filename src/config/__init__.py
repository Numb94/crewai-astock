#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI Stock - 配置模块初始化

确保config目录可以被import
"""

from .llm_config import (
    get_deepseek_llm,
    get_analysis_llm,
    get_decision_llm,
    get_creative_llm
)

from .embeddings_config import (
    SiliconFlowEmbedder,
    get_siliconflow_embedder_config,
    get_embedder_instance
)

__all__ = [
    # LLM配置
    'get_deepseek_llm',
    'get_analysis_llm',
    'get_decision_llm',
    'get_creative_llm',
    # Embeddings配置
    'SiliconFlowEmbedder',
    'get_siliconflow_embedder_config',
    'get_embedder_instance'
]
