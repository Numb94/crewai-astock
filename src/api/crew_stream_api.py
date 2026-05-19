#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI流式推送API - CrewAI A-Stock V2.0

描述: SSE（Server-Sent Events）流式推送CrewAI执行过程
实时推送Agent输出到前端聊天窗

特性:
- SSE流式推送
- 实时Agent输出
- 心跳保持连接
- 多用户隔离

作者: AI Architect
版本: v2.0.0
日期: 2025-11-07
"""

import json
import time
import logging
from datetime import datetime
from flask import Blueprint, Response, stream_with_context, jsonify
from typing import Generator, Dict, Any

# 配置日志
logger = logging.getLogger(__name__)

# 创建蓝图
crew_stream_api = Blueprint('crew_stream', __name__, url_prefix='/api/crew')


class CrewStreamAPI:
    """CrewAI流式推送API"""
    
    def __init__(self):
        """初始化"""
        # 存储每个session的消息队列
        self.message_queues: Dict[str, list] = {}
    
    def add_message(self, session_id: str, agent: str, message: str, level: str = 'info'):
        """
        添加消息到队列
        
        Args:
            session_id: 用户会话ID
            agent: Agent名称
            message: 消息内容
            level: 日志级别（info/warning/error）
        """
        if session_id not in self.message_queues:
            self.message_queues[session_id] = []
        
        self.message_queues[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'agent': agent,
            'message': message,
            'level': level
        })

        # logger.debug(f"添加消息到队列: session_id={session_id[:8]}..., agent={agent}")  # 🔴 注释掉DEBUG日志
    
    def stream_messages(self, session_id: str) -> Generator[str, None, None]:
        """
        流式推送消息
        
        Args:
            session_id: 用户会话ID
            
        Yields:
            SSE格式的消息
        """
        # 初始化消息队列
        if session_id not in self.message_queues:
            self.message_queues[session_id] = []
        
        last_index = 0
        
        try:
            while True:
                # 获取新消息
                messages = self.message_queues[session_id][last_index:]
                
                if messages:
                    for msg in messages:
                        # SSE格式：data: {json}\n\n
                        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                        last_index += 1
                else:
                    # 发送心跳（每5秒）
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
                
                # 等待1秒
                time.sleep(1)
                
        except GeneratorExit:
            logger.info(f"SSE连接关闭: session_id={session_id[:8]}...")
    
    def create_sse_response(self, session_id: str) -> Response:
        """
        创建SSE响应
        
        Args:
            session_id: 用户会话ID
            
        Returns:
            Flask Response对象
        """
        return Response(
            stream_with_context(self.stream_messages(session_id)),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    def clear_messages(self, session_id: str):
        """
        清空消息队列
        
        Args:
            session_id: 用户会话ID
        """
        if session_id in self.message_queues:
            self.message_queues[session_id] = []
            logger.info(f"清空消息队列: session_id={session_id[:8]}...")


# 全局实例
_crew_stream_manager = CrewStreamAPI()


# API路由
@crew_stream_api.route('/stream/<session_id>')
def stream(session_id: str):
    """
    SSE流式推送CrewAI执行过程

    Args:
        session_id: 用户会话ID

    Returns:
        SSE响应
    """
    logger.info(f"SSE连接建立: session_id={session_id[:8]}...")
    return _crew_stream_manager.create_sse_response(session_id)


@crew_stream_api.route('/clear/<session_id>', methods=['POST'])
def clear(session_id: str):
    """
    清空消息队列

    Args:
        session_id: 用户会话ID

    Returns:
        JSON响应
    """
    _crew_stream_manager.clear_messages(session_id)
    return jsonify({'success': True, 'message': '消息队列已清空'})


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # 创建API实例
    api = CrewStreamAPI()
    
    # 添加测试消息
    api.add_message(
        session_id="test_session",
        agent="复盘分析师",
        message="开始分析昨日推荐表现...",
        level="info"
    )
    
    api.add_message(
        session_id="test_session",
        agent="复盘分析师",
        message="推荐数量：5只，盈利数量：3只，亏损数量：2只",
        level="info"
    )
    
    # 流式推送（测试）
    print("开始流式推送：")
    for i, msg in enumerate(api.stream_messages("test_session")):
        print(msg)
        if i >= 5:  # 只测试5条消息
            break

