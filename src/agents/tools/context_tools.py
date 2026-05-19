#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Agent上下文管理工具 - 用于Agent间传递结构化数据

作者: AI Architect
版本: v1.0.0
日期: 2025-11-06
"""

from src.database.models import AgentContext
from src.database.db_manager import get_db
from src.agents.tools.database_tools import get_current_session_id
from crewai.tools import tool
from loguru import logger
import json


# ========================================
# 辅助函数（不带@tool装饰器，供scheduler等非Agent代码使用）
# ========================================

def _save_context(session_id: str, context_type: str, context_data: dict) -> str:
    """
    保存Agent上下文数据到数据库（辅助函数，不带@tool装饰器）

    Args:
        session_id: 会话ID
        context_type: 上下文类型
        context_data: 上下文数据

    Returns:
        保存结果
    """
    db = get_db()

    try:
        with db.get_session() as db_session:
            # 删除旧的同类型上下文
            deleted_count = db_session.query(AgentContext).filter_by(
                session_id=session_id,
                context_type=context_type
            ).delete()

            if deleted_count > 0:
                logger.debug(f"🗑️ 删除旧上下文 [session={session_id[:8]}...]: {context_type} ({deleted_count}条)")

            # 保存新上下文
            context = AgentContext(
                session_id=session_id,
                context_type=context_type,
                context_data=context_data
            )
            db_session.add(context)
            db_session.commit()

            logger.info(f"✅ 保存上下文 [session={session_id[:8]}...]: {context_type} = {json.dumps(context_data, ensure_ascii=False)}")
            return f"✅ 成功保存{context_type}上下文"

    except Exception as e:
        logger.error(f"❌ 保存上下文失败 [session={session_id[:8]}...]: {e}")
        return f"❌ 保存失败: {e}"


def _load_context(session_id: str, context_type: str) -> dict:
    """
    从数据库读取Agent上下文数据（辅助函数，不带@tool装饰器）

    Args:
        session_id: 会话ID
        context_type: 上下文类型

    Returns:
        上下文数据（字典格式）
    """
    db = get_db()

    try:
        with db.get_session() as db_session:
            context = db_session.query(AgentContext).filter_by(
                session_id=session_id,
                context_type=context_type
            ).order_by(AgentContext.created_at.desc()).first()

            if context:
                logger.info(f"✅ 读取上下文 [session={session_id[:8]}...]: {context_type} = {json.dumps(context.context_data, ensure_ascii=False)}")
                return context.context_data
            else:
                logger.warning(f"⚠️ 未找到{context_type}上下文 [session={session_id[:8]}...]")
                return {"error": f"未找到{context_type}上下文"}

    except Exception as e:
        logger.error(f"❌ 读取上下文失败 [session={session_id[:8]}...]: {e}")
        return {"error": str(e)}


# ========================================
# CrewAI Tool装饰器版本（供Agent使用）
# ========================================


@tool("保存Agent上下文")
def save_agent_context(context_type: str, context_data: dict) -> str:
    """
    保存Agent上下文数据到数据库

    Args:
        context_type: 上下文类型（recommended_count/strategy_name/screening_params/candidate_stocks等）
        context_data: 上下文数据（字典格式）

    Returns:
        保存结果

    示例1：保存推荐数量
        save_agent_context(
            context_type='recommended_count',
            context_data={'count': 2, 'reason': '总资产15万，推荐2只'}
        )

    示例2：保存策略名称
        save_agent_context(
            context_type='strategy_name',
            context_data={'name': '龙头战法', 'reason': '市场HOT，历史胜率75%'}
        )

    示例3：保存筛选参数
        save_agent_context(
            context_type='screening_params',
            context_data={
                'price_change_min': 5,
                'price_change_max': 9,
                'turnover_min': 8,
                'volume_min': 5,
                'sort_by': 'turnover'
            }
        )

    示例4：保存候选股列表（🔴 新增）
        save_agent_context(
            context_type='candidate_stocks',
            context_data={
                'stocks': [
                    {
                        'code': '600000',
                        'name': '浦发银行',
                        'current_price': 10.5,
                        'price_change': 5.2,
                        'turnover_rate': 8.5,
                        'volume': 15.3,
                        'amplitude': 6.8
                    },
                    {
                        'code': '000001',
                        'name': '平安银行',
                        'current_price': 12.3,
                        'price_change': 6.1,
                        'turnover_rate': 9.2,
                        'volume': 18.7,
                        'amplitude': 7.2
                    }
                ],
                'count': 15,
                'screening_time': '2025-11-07 10:30:00'
            }
        )
    """
    session_id = get_current_session_id()
    db = get_db()
    
    try:
        with db.get_session() as db_session:
            # 删除旧的同类型上下文
            deleted_count = db_session.query(AgentContext).filter_by(
                session_id=session_id,
                context_type=context_type
            ).delete()

            if deleted_count > 0:
                logger.debug(f"🗑️ 删除旧上下文 [session={session_id[:8]}...]: {context_type} ({deleted_count}条)")

            # 保存新上下文
            context = AgentContext(
                session_id=session_id,
                context_type=context_type,
                context_data=context_data
            )
            db_session.add(context)
            db_session.commit()

            logger.info(f"✅ 保存上下文 [session={session_id[:8]}...]: {context_type} = {json.dumps(context_data, ensure_ascii=False)}")
            return f"✅ 成功保存{context_type}上下文"

    except Exception as e:
        logger.error(f"❌ 保存上下文失败 [session={session_id[:8]}...]: {e}")
        return f"❌ 保存失败: {e}"


@tool("读取Agent上下文")
def load_agent_context(context_type: str) -> str:
    """
    从数据库读取Agent上下文数据

    Args:
        context_type: 上下文类型

    Returns:
        上下文数据（JSON字符串）

    示例1：读取推荐数量
        load_agent_context('recommended_count')
        # 返回: '{"count": 2, "reason": "总资产15万，推荐2只"}'

    示例2：读取策略名称
        load_agent_context('strategy_name')
        # 返回: '{"name": "龙头战法", "reason": "市场HOT，历史胜率75%"}'

    示例3：读取筛选参数
        load_agent_context('screening_params')
        # 返回: '{"price_change_min": 5, "price_change_max": 9, ...}'

    示例4：读取候选股列表（🔴 新增）
        load_agent_context('candidate_stocks')
        # 返回: '{"stocks": [{"code": "600000", "name": "浦发银行", ...}], "count": 15}'
    """
    session_id = get_current_session_id()
    db = get_db()
    
    try:
        with db.get_session() as db_session:
            context = db_session.query(AgentContext).filter_by(
                session_id=session_id,
                context_type=context_type
            ).order_by(AgentContext.created_at.desc()).first()

            if context:
                logger.info(f"✅ 读取上下文 [session={session_id[:8]}...]: {context_type} = {json.dumps(context.context_data, ensure_ascii=False)}")
                return json.dumps(context.context_data, ensure_ascii=False)
            else:
                # 🔴 降级为 DEBUG，避免首次运行时大量警告
                logger.debug(f"⚠️ 未找到{context_type}上下文 [session={session_id[:8]}...]")
                return f'{{"error": "未找到{context_type}上下文"}}'

    except Exception as e:
        logger.error(f"❌ 读取上下文失败 [session={session_id[:8]}...]: {e}")
        return f'{{"error": "{e}"}}'


@tool("清理Agent上下文")
def clear_agent_context(context_type: str = None) -> str:
    """
    清理Agent上下文数据
    
    Args:
        context_type: 上下文类型（如果为None，清理所有上下文）
    
    Returns:
        清理结果
    
    示例：
        clear_agent_context('recommended_count')  # 清理推荐数量上下文
        clear_agent_context()  # 清理所有上下文
    """
    session_id = get_current_session_id()
    db = get_db()
    
    try:
        with db.get_session() as db_session:
            if context_type:
                # 清理指定类型
                deleted_count = db_session.query(AgentContext).filter_by(
                    session_id=session_id,
                    context_type=context_type
                ).delete()
                logger.info(f"✅ 清理上下文: {context_type} ({deleted_count}条)")
                return f"✅ 成功清理{context_type}上下文（{deleted_count}条）"
            else:
                # 清理所有上下文
                deleted_count = db_session.query(AgentContext).filter_by(
                    session_id=session_id
                ).delete()
                logger.info(f"✅ 清理所有上下文 ({deleted_count}条)")
                return f"✅ 成功清理所有上下文（{deleted_count}条）"
    
    except Exception as e:
        logger.error(f"❌ 清理上下文失败: {e}")
        return f"❌ 清理失败: {e}"

