#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CrewAI A-Stock - 用户容器

实现多用户完全隔离：
- 每个用户有独立的CrewAI实例
- 每个用户有独立的Scheduler实例
- 每个用户有独立的上下文变量
- 每个用户有独立的任务锁

作者: AI Architect
日期: 2025-11-06
"""

from contextvars import ContextVar
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger

# ✅ 使用contextvars代替全局变量（支持异步和多线程）
current_session_id: ContextVar[str] = ContextVar('current_session_id', default='default')


class UserContainer:
    """
    用户容器：每个用户的独立运行环境
    
    包含：
    - session_id: 用户标识
    - crew_instance: CrewAI实例（智能推荐）
    - position_crew_instance: CrewAI实例（持仓监控）
    - scheduler_instance: Scheduler实例
    - task_lock: 任务锁（防止同一用户并发）
    - created_at: 创建时间
    - last_used_at: 最后使用时间
    - is_running: 是否正在运行
    """
    
    def __init__(self, session_id: str):
        """
        初始化用户容器
        
        Args:
            session_id: 用户session_id
        """
        self.session_id = session_id
        self.crew_instance = None  # 智能推荐Crew
        self.position_crew_instance = None  # 持仓监控Crew
        self.scheduler_instance = None  # Scheduler实例
        self.task_lock = threading.RLock()  # 用户级可重入锁
        self.lock = threading.RLock()  # ✅ 容器级锁（保护Scheduler创建）
        self.created_at = datetime.now()
        self.last_used_at = datetime.now()
        self.is_running = False

        logger.info(f"🆕 创建用户容器: session_id={session_id[:8]}...")
    
    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used_at = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """
        检查容器是否过期
        
        Args:
            timeout_minutes: 超时时间（分钟），默认30分钟
            
        Returns:
            是否过期
        """
        return datetime.now() - self.last_used_at > timedelta(minutes=timeout_minutes)
    
    def cleanup(self):
        """清理容器资源"""
        logger.info(f"🧹 清理用户容器: session_id={self.session_id[:8]}...")
        
        # 停止Scheduler
        if self.scheduler_instance and self.scheduler_instance.is_running:
            self.scheduler_instance.stop()
        
        # 清空实例
        self.crew_instance = None
        self.position_crew_instance = None
        self.scheduler_instance = None


class UserContainerManager:
    """
    用户容器管理器：管理所有用户的容器
    
    功能：
    - 创建/获取用户容器
    - 自动清理过期容器（30分钟未使用）
    - 线程安全
    - 统计信息
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化容器管理器"""
        if not hasattr(self, 'initialized'):
            self.containers: Dict[str, UserContainer] = {}
            self.lock = threading.RLock()
            self.cleanup_interval = 60  # 清理间隔（秒）
            self.timeout_minutes = 30  # 容器超时时间（分钟）
            self.cleanup_thread = None
            self.is_running = False
            self.initialized = True
            
            logger.info("🏗️ 用户容器管理器初始化完成")
            
            # 启动自动清理线程
            self._start_cleanup_thread()
    
    def get_or_create(self, session_id: str) -> UserContainer:
        """
        获取或创建用户容器
        
        Args:
            session_id: 用户session_id
            
        Returns:
            用户容器实例
        """
        with self.lock:
            if session_id not in self.containers:
                self.containers[session_id] = UserContainer(session_id)
                logger.info(f"✅ 创建新容器: session_id={session_id[:8]}..., 总数={len(self.containers)}")
            # else:
                # logger.debug(f"♻️ 复用容器: session_id={session_id[:8]}...")  # 🔴 注释掉频繁的DEBUG日志
            
            container = self.containers[session_id]
            container.update_last_used()
            return container

    def set_current_session(self, session_id: str):
        """
        设置当前session_id（使用contextvars）

        Args:
            session_id: 用户session_id
        """
        current_session_id.set(session_id)
        logger.debug(f"🔄 设置当前session: {session_id[:8]}...")

    def get_current_session(self) -> str:
        """
        获取当前session_id（从contextvars）

        Returns:
            当前session_id
        """
        return current_session_id.get()

    def mark_running(self, session_id: str, is_running: bool):
        """
        标记容器运行状态

        Args:
            session_id: 用户session_id
            is_running: 是否正在运行
        """
        with self.lock:
            if session_id in self.containers:
                self.containers[session_id].is_running = is_running

    def remove_container(self, session_id: str):
        """
        移除用户容器

        Args:
            session_id: 用户session_id
        """
        with self.lock:
            if session_id in self.containers:
                container = self.containers[session_id]
                container.cleanup()
                del self.containers[session_id]
                logger.info(f"🗑️ 移除容器: session_id={session_id[:8]}..., 剩余={len(self.containers)}")

    def _cleanup_expired_containers(self):
        """清理过期容器"""
        with self.lock:
            expired_sessions = [
                session_id for session_id, container in self.containers.items()
                if container.is_expired(self.timeout_minutes) and not container.is_running
            ]

            for session_id in expired_sessions:
                logger.info(f"⏰ 容器过期: session_id={session_id[:8]}...")
                self.remove_container(session_id)

    def _cleanup_loop(self):
        """清理循环（后台线程）"""
        import time
        logger.info(f"🔄 启动自动清理线程: 间隔={self.cleanup_interval}秒, 超时={self.timeout_minutes}分钟")

        while self.is_running:
            time.sleep(self.cleanup_interval)
            try:
                self._cleanup_expired_containers()
            except Exception as e:
                logger.error(f"❌ 清理容器失败: {e}")

    def _start_cleanup_thread(self):
        """启动自动清理线程"""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.is_running = True
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True,
                name="ContainerCleanup"
            )
            self.cleanup_thread.start()

    def stop(self):
        """停止容器管理器"""
        logger.info("🛑 停止用户容器管理器...")
        self.is_running = False

        # 清理所有容器
        with self.lock:
            for session_id in list(self.containers.keys()):
                self.remove_container(session_id)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            running_count = sum(1 for c in self.containers.values() if c.is_running)

            return {
                'total_containers': len(self.containers),
                'running_containers': running_count,
                'idle_containers': len(self.containers) - running_count,
                'sessions': list(self.containers.keys()),
                'timeout_minutes': self.timeout_minutes,
                'cleanup_interval': self.cleanup_interval
            }


# ========================================
# 全局单例
# ========================================

_container_manager: Optional[UserContainerManager] = None
_manager_lock = threading.Lock()


def get_container_manager() -> UserContainerManager:
    """
    获取用户容器管理器（单例）

    Returns:
        UserContainerManager实例
    """
    global _container_manager

    if _container_manager is None:
        with _manager_lock:
            if _container_manager is None:
                _container_manager = UserContainerManager()

    return _container_manager

