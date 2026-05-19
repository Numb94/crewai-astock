"""
全局新闻监控调度器 - CrewAI A-Stock

功能：
- 全局共享的新闻监控（所有用户共享）
- 避免多用户重复监控新闻
- 减少日志输出

作者: AI Architect
日期: 2025-11-20
"""

import schedule
import time
import threading
from datetime import datetime
from loguru import logger

from src.core.news_monitor_scheduler import NewsMonitorScheduler
from src.tools.news_source_manager import NewsSourceManager
from src.tools.news_summary_generator import NewsSummaryGenerator
from src.utils.pushplus_notifier import PushPlusNotifier
from src.database.news_manager import NewsDBManager


class GlobalNewsScheduler:
    """全局新闻监控调度器（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.is_running = False
        self.thread = None
        
        # 创建独立的调度器实例
        self.scheduler = schedule.Scheduler()
        
        # 新闻监控相关
        self.news_scheduler = NewsMonitorScheduler(session_id='global')
        self.news_manager = NewsSourceManager()
        self.news_summary_generator = NewsSummaryGenerator()
        self.pushplus = PushPlusNotifier()
        self.news_db = NewsDBManager()
        
        # 新闻去重机制
        self.processed_news_ids = set()
        self.processed_news_max_size = 1000
        
        # high级别新闻延迟推送队列
        self.high_news_queue = []
        self.high_news_push_delay = 300  # 5分钟延迟（秒）
        
        # 新闻汇总推送
        self.last_news_summary_time = None
        self.news_summary_interval = 3600  # 1小时汇总一次（秒）
    
    def setup_schedule(self):
        """设置定时任务"""
        self.scheduler.clear()
        
        # 新闻监控（每5分钟检查一次）
        self.scheduler.every(5).minutes.do(self._run_news_monitor)
        
        # 开盘前摘要（每1分钟检查一次）
        self.scheduler.every(1).minutes.do(self._run_morning_summary)
        
        # 新闻汇总推送（每小时检查一次）
        self.scheduler.every(1).hours.do(self._run_news_summary)
    
    def run_scheduler(self):
        """运行调度器（后台线程）"""
        while self.is_running:
            self.scheduler.run_pending()
            time.sleep(1)
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            return
        
        self.setup_schedule()
        self.is_running = True
        self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.thread.start()
        
        logger.success("✅ 全局新闻监控调度器启动成功")
    
    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run_news_monitor(self):
        """运行新闻监控（内部方法，减少日志）"""
        # 判断是否需要监控
        if not self.news_scheduler.should_monitor():
            return
        
        try:
            # 获取突发新闻
            news = self.news_manager.get_breaking_news(
                keywords=["股票", "A股", "重大政策", "行业利好"],
                urgency='normal'
            )
            
            if not news:
                self.news_scheduler.update_monitor_time()
                return
            
            # 判断紧急程度并分类
            critical_news = []
            high_news = []
            saved_count = 0
            
            for item in news:
                urgency = self.news_manager.judge_news_urgency(item)
                item['urgency'] = urgency
                
                # 保存到数据库
                news_id = self.news_db.save_news(item)
                if news_id:
                    saved_count += 1
                    item['db_id'] = news_id
                else:
                    continue
                
                # 分类
                if urgency == 'critical':
                    critical_news.append(item)
                elif urgency == 'high':
                    high_news.append(item)
            
            # 只在有critical新闻时输出日志
            if critical_news:
                logger.warning(f"🔴 发现{len(critical_news)}条重大利好")
                # TODO: 推送critical新闻
            
            # 更新监控时间
            self.news_scheduler.update_monitor_time()
            
        except Exception as e:
            logger.error(f"❌ 新闻监控失败: {e}")
    
    def _run_morning_summary(self):
        """运行开盘前摘要（内部方法）"""
        # TODO: 实现开盘前摘要逻辑
        pass
    
    def _run_news_summary(self):
        """运行新闻汇总（内部方法）"""
        # TODO: 实现新闻汇总逻辑
        pass


# 全局单例
_global_news_scheduler = None

def get_global_news_scheduler() -> GlobalNewsScheduler:
    """获取全局新闻监控调度器实例"""
    global _global_news_scheduler
    if _global_news_scheduler is None:
        _global_news_scheduler = GlobalNewsScheduler()
    return _global_news_scheduler

