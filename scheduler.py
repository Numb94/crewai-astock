"""
CrewAI A-Stock 调度器
自动化运行股票推荐和持仓监控

功能：
1. 每変14:30运行股票推荐（尾盘推荐，看全天走势）
2. 盘中监控持仓（每3秒更新价格）
   - 上午：9:30-11:30
   - 下午：13:00-15:00
3. AI深度分析（固定间隔，避免频繁运行）
   - 每60分钟分析一次
   - 🔴 已禁用关键阈值触发（因为ai_urgency会导致频繁触发）

作者: AI Architect
日期: 2025-11-06
"""

import schedule
import time
import threading
import os
from datetime import datetime, time as dt_time, date, timedelta
from typing import Dict, Any, Optional
from decimal import Decimal
from loguru import logger

# 导入新闻监控相关模块
from src.core.news_monitor_scheduler import NewsMonitorScheduler
from src.tools.news_source_manager import NewsSourceManager
from src.tools.news_summary_generator import NewsSummaryGenerator
from src.utils.pushplus_notifier import PushPlusNotifier
from src.utils.db_backup import DatabaseBackup


class StockScheduler:
    """
    股票交易调度器

    功能：
    1. 每天14:30运行股票推荐（尾盘推荐，看全天走势）
    2. 盘中监控持仓（价格更新 + AI分析）
       - 价格更新：每1分钟（快速、低成本，API限制3000次/分钟）
       - AI分析：智能触发（避免频繁运行）

    参数：
    - monitor_interval: 价格更新间隔（分钟），默认0.05分钟（3秒）
      * 0.05分钟（3秒）：推荐（实时监控，API限制足够）
      * 0.17分钟（10秒）：超短线（需要极高频监控）
      * 1分钟：低频监控（节省API调用）

    AI分析触发条件：
    - 正常情况：每30分钟分析一次
    - 关键阈值：达到止盈/止损线时，10分钟冷却后再次分析
    - 首次运行：启动后立即分析
    """

    def __init__(self, session_id: str = 'default', monitor_interval: float = 0.05):
        """
        初始化调度器

        Args:
            session_id: 用户session_id（支持多用户隔离）
            monitor_interval: 价格更新间隔（分钟），默认0.05分钟（3秒）
                - 0.05分钟（3秒）：推荐（实时监控）
                - 1分钟：低频监控

        注意：
        - 价格更新：每3秒（快速、低成本）
        - AI分析：智能触发（正常60分钟，关键阈值30分钟冷却）
        """
        self.session_id = session_id  # ✅ 用户session_id
        self.is_running = False
        self.thread = None
        self.monitor_interval = monitor_interval  # 价格更新间隔（分钟）
        self.ai_analysis_interval = 60  # 🔴 AI分析间隔（30分钟 → 60分钟）
        self.last_monitor_time = None  # 上次价格更新时间
        self.last_ai_analysis_time = None  # 上次AI分析时间
        self.task_lock = threading.RLock()  # ✅ 可重入锁，防止多个任务同时运行

        # 🔴 添加暂停标志，用于暂停定时任务
        self.is_paused = False

        # ✅ 创建独立的调度器实例（避免多用户共享全局调度器）
        self.scheduler = schedule.Scheduler()

        # 🔴 新闻监控相关
        self.news_scheduler = NewsMonitorScheduler(session_id=session_id)
        self.news_manager = NewsSourceManager()
        self.news_summary_generator = NewsSummaryGenerator()
        self.pushplus = PushPlusNotifier()

        # ✅ 新增：新闻数据库管理器（全局共享）
        from src.database.news_manager import NewsDBManager
        self.news_db = NewsDBManager()

        # 🔴 新增：推荐频率控制
        self.last_news_recommendation_date = None  # 上次新闻推荐日期（重大利好触发）
        self.last_morning_recommendation_date = None  # 上次早盘推荐日期

        # 🔴 新增：新闻去重机制（内存缓存，用于快速去重）
        self.processed_news_ids = set()  # 已处理的新闻ID集合
        self.processed_news_max_size = 1000  # 最大缓存数量

        # ✅ 新增：high级别新闻延迟推送队列
        self.high_news_queue = []  # 待推送的high级别新闻

        # ✅ 新增：数据库备份管理器
        self.db_backup = DatabaseBackup()
        self.high_news_push_delay = 300  # 5分钟延迟（秒）

        # ✅ 新增：新闻汇总推送
        self.last_news_summary_time = None  # 上次汇总推送时间
        self.news_summary_interval = 3600  # 1小时汇总一次（秒）


    def _log_with_prefix(self, level: str, task_type: str, message: str):
        """
        带前缀的日志输出（提高多用户场景下的日志可读性）

        Args:
            level: 日志级别 (debug/info/warning/error/success)
            task_type: 任务类型 (推荐/监控/新闻/绩效)
            message: 日志消息

        示例输出：
            [user123][推荐] 🤖 触发AI推荐系统...
            [user456][监控] 📊 持仓监控开始...
        """
        prefix = f"[{self.session_id[:8]}...][{task_type}]"
        full_message = f"{prefix} {message}"

        if level == 'debug':
            logger.debug(full_message)
        elif level == 'info':
            logger.info(full_message)
        elif level == 'warning':
            logger.warning(full_message)
        elif level == 'error':
            logger.error(full_message)
        elif level == 'success':
            logger.success(full_message)

    def pause(self):
        """暂停定时任务（手动推荐期间使用）"""
        self.is_paused = True

    def resume(self):
        """恢复定时任务"""
        self.is_paused = False

    def set_current_user(self, session_id: str):
        """设置当前服务的用户session_id（已废弃，使用构造函数传入）"""
        self.session_id = session_id
        logger.warning(f"⚠️ set_current_user已废弃，请在构造函数中传入session_id")

    def run_recommendation(self, session_id: str):
        """
        运行股票推荐（仅供手动触发使用）

        注意：此函数已不再用于定时任务，只能通过API手动触发

        Args:
            session_id: 用户session_id（必填）
        """
        logger.warning("⚠️ run_recommendation() 已废弃，请使用 API 手动触发推荐")
        logger.warning("⚠️ 定时推荐已移除，推荐应根据用户持仓情况和可用资金主动触发")
    
    def is_trading_time(self):
        """
        判断当前是否是交易时间

        交易时间：
        - 上午：9:30-11:30
        - 下午：13:00-15:00
        """
        now = datetime.now()
        current_time = now.time()

        # 上午交易时间：9:30-11:30
        morning_start = dt_time(9, 30)
        morning_end = dt_time(11, 30)

        # 下午交易时间：13:00-15:00
        afternoon_start = dt_time(13, 0)
        afternoon_end = dt_time(15, 0)

        # 判断是否在交易时间段内
        is_morning = morning_start <= current_time <= morning_end
        is_afternoon = afternoon_start <= current_time <= afternoon_end

        return is_morning or is_afternoon

    def has_critical_positions(self):
        """
        检查是否有持仓达到关键阈值（基于AI分析结果，而非硬编码）

        优化说明：
        - 不再使用硬编码的止盈止损阈值
        - 改为检查AI分析结果（ai_urgency字段）
        - AI分析由position_monitor_crew完成，更智能、更灵活

        触发条件：
        - AI紧急度为'high'（强烈建议卖出）
        - AI紧急度为'medium'（建议卖出）
        """
        try:
            from src.database.db_manager import get_db
            from src.database.models import Position

            db = get_db()

            with db.get_session() as session:
                # ✅ 使用用户session_id过滤
                positions = session.query(Position).filter(
                    Position.session_id == self.session_id,
                    Position.status == 'holding'
                ).all()

                if not positions:
                    return False

                # 检查是否有AI建议卖出的持仓
                for p in positions:
                    if p.ai_urgency in ['high', 'medium']:
                        # 🔴 改为DEBUG级别，减少控制台输出
                        logger.debug(f"⚠️ {p.stock_name}({p.stock_code}) AI建议: {p.ai_sell_reason}")
                        return True

                return False

        except Exception as e:
            logger.error(f"检查关键持仓失败: {e}")
            return False

    def should_run_ai_analysis(self, now):
        """
        判断是否需要运行AI分析

        触发条件：
        1. 首次运行
        2. 距离上次分析超过60分钟
        
        🔴 已禁用：关键阈值触发逻辑（因为ai_urgency会一直保留导致频繁触发）
        """
        # 首次运行
        if not self.last_ai_analysis_time:
            return True

        # 计算距离上次分析的时间
        time_diff = (now - self.last_ai_analysis_time).total_seconds() / 60

        # 距离上次分析超过60分钟
        if time_diff >= self.ai_analysis_interval:
            return True

        # 🔴 已禁用：关键阈值触发逻辑
        # 原因：ai_urgency字段会一直保留，导致has_critical_positions()持续返回True
        # if self.has_critical_positions() and time_diff >= 30:
        #     logger.info(f"🚨 检测到关键持仓，触发AI深度分析（距上次分析{time_diff:.1f}分钟）")
        #     return True

        return False

    def update_realtime_prices(self):
        """
        更新持仓的实时价格（每3秒执行）

        功能：
        - 所有用户：从智兔API更新价格（不查询同花顺，避免弹窗）
        - 更新current_price、profit_loss、profit_loss_pct

        注意：
        - 持仓数据只在首次启动和交易后从同花顺同步
        - 定时任务只更新价格，不同步持仓
        """
        try:
            # 🔴 所有用户：从智兔API更新价格（避免频繁查询同花顺）
            from src.database.db_manager import get_db
            from src.database.models import Position
            from src.tools.zhitu_api import ZhituAPI
            from decimal import Decimal

            db = get_db()
            zhitu = ZhituAPI()

            with db.get_session() as session:
                # ✅ 使用用户session_id过滤
                positions = session.query(Position).filter(
                    Position.session_id == self.session_id,
                    Position.status == 'holding'
                ).all()

                if not positions:
                    return

                # 获取实时价格
                stock_codes = [p.stock_code for p in positions]
                prices_data = zhitu.get_real_time_multi_broker(stock_codes)

                # 更新数据库
                updated_count = 0
                for position in positions:
                    price_info = prices_data.get(position.stock_code, {})
                    current_price = Decimal(str(price_info.get('current_price') or price_info.get('p', position.buy_price)))

                    position.current_price = current_price
                    position.profit_loss = (current_price - position.buy_price) * position.quantity
                    position.profit_loss_pct = ((current_price - position.buy_price) / position.buy_price) * 100
                    updated_count += 1

                session.commit()
                # 🟢 添加日志确认价格更新
                logger.debug(f"✅ 价格更新完成: {updated_count}只股票")

        except Exception as e:
            logger.error(f"更新实时价格失败: {e}")

    def run_monitor(self):
        """
        运行持仓监控（价格更新 + 智能AI分析 + 自动交易）

        自动交易状态机：
        - 状态1：无持仓 → 触发AI推荐 → 自动买入
        - 状态2：有持仓（今天买入，T+1不可卖）→ 停止监控
        - 状态3：有持仓（T+1可卖）→ AI分析 → 自动卖出 → 触发推荐 → 自动买入
        """
        # 🔴 检查是否暂停
        if self.is_paused:
            # logger.debug("⏸️ 定时任务已暂停，跳过持仓监控")  # 🔴 注释掉DEBUG日志
            return

        # ✅ 尝试获取锁，如果获取失败说明有其他任务在运行
        if not self.task_lock.acquire(blocking=False):
            # logger.debug("⏸️ 有其他任务正在运行，跳过本次持仓监控")  # 🔴 注释掉DEBUG日志
            return

        try:
            # 🟢 无论是否交易时间，都先更新价格（供前端显示）
            now = datetime.now()
            if not self.last_monitor_time or (now - self.last_monitor_time).total_seconds() / 60 >= self.monitor_interval:
                # logger.info(f"💰 更新价格... [{self.session_id[:8]}]")
                self.update_realtime_prices()
                self.last_monitor_time = now

            # 检查是否在交易时间（AI分析只在交易时间运行）
            if not self.is_trading_time():
                return

            # ✅ 设置当前session_id（使用contextvars）
            from src.agents.tools.database_tools import set_current_session_id
            set_current_session_id(self.session_id)

            # ✅ 查询持仓状态
            from src.database.db_manager import get_db
            from src.database.models import Position

            db = get_db()
            position_count = 0
            can_sell_count = 0
            
            with db.get_session() as session:
                # ✅ 使用用户session_id过滤
                positions = session.query(Position).filter(
                    Position.session_id == self.session_id,
                    Position.status == 'holding'
                ).all()
                
                position_count = len(positions)
                # ✅ 在session内提取can_sell_date判断
                can_sell_count = len([p for p in positions if p.can_sell_date <= date.today()])

            # ========================================
            # 状态1：无持仓 → 跳过AI分析
            # ========================================
            if position_count == 0:
                return

            # ========================================
            # 状态2：有持仓（今天买入，T+1不可卖）→ 跳过AI分析
            # ========================================
            if can_sell_count == 0:
                return

            # ========================================
            # 状态3：有持仓（T+1可卖）→ AI分析 → 自动卖出
            # ========================================

            # 🔴 改为DEBUG级别，减少控制台输出
            self._log_with_prefix('debug', '监控', "=" * 60)
            self._log_with_prefix('debug', '监控', "📊 开始运行持仓监控...")
            self._log_with_prefix('debug', '监控', f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._log_with_prefix('debug', '监控', "=" * 60)

            # 判断是否需要运行AI分析
            if self.should_run_ai_analysis(now):
                logger.info("🤖 触发AI深度分析...")

                # 导入持仓监控crew
                from src.crews.position_monitor_crew import run_position_monitor

                # 🔴 运行AI分析（传入session_id）
                result = run_position_monitor(session_id=self.session_id)

                # 更新上次AI分析时间
                self.last_ai_analysis_time = now

                logger.success("✅ AI分析完成！")
                logger.info(f"分析结果:\n{result}")


        except Exception as e:
            logger.error(f"❌ 持仓监控运行异常: {e}")
            logger.exception("详细错误:")
        finally:
            # ✅ 释放锁
            self.task_lock.release()
    
    def setup_schedule(self):
        """设置定时任务"""
        # 清空现有任务
        self.scheduler.clear()

        # 🔴 移除定时推荐（改为手动触发）
        # 🔴 移除新闻监控（改为全局共享，避免多用户重复监控）

        # ✅ 保留盘中实时监控（每1分钟）
        self.scheduler.every(self.monitor_interval).minutes.do(self.run_monitor)

        # ✅ 每日绩效更新（每天17:00执行）
        self.scheduler.every().day.at("17:00").do(self.run_performance_update)
    
    def run_scheduler(self):
        """运行调度器（后台线程）"""
        while self.is_running:
            self.scheduler.run_pending()
            time.sleep(1)
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            return

        # 设置定时任务
        self.setup_schedule()

        # 启动后台线程
        self.is_running = True
        self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.thread.start()

        # 🔴 启动时立即执行一次持仓监控（同步持仓数据）
        try:
            self.run_monitor()
        except Exception as e:
            logger.error(f"❌ 启动时同步持仓失败: {e}")
    
    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return

        self.is_running = False

        if self.thread:
            self.thread.join(timeout=5)
    
    def get_next_run_times(self):
        """获取下次运行时间"""
        jobs = self.scheduler.get_jobs()
        result = []

        for job in jobs:
            # 解析任务名称
            func_str = str(job.job_func)
            if 'run_recommendation' in func_str:
                task_name = "🔍 股票推荐（尾盘推荐）"
            elif 'run_monitor' in func_str:
                task_name = "📊 持仓监控（实时）"
            else:
                task_name = "未知任务"

            result.append({
                "task": task_name,
                "next_run": job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else "未知"
            })

        return result

    def run_news_monitor(self):
        """
        运行新闻监控（优化版）

        根据交易时间动态调整监控频率：
        - 休盘期间：每1小时
        - 开盘前：每5分钟
        - 盘中：每5分钟
        - 盘后：每30分钟

        新增功能：
        - 保存新闻到数据库
        - 实现high级别新闻延迟推送
        - 增强日志输出
        """
        # 判断是否需要监控
        if not self.news_scheduler.should_monitor():
            return

        try:
            self._log_with_prefix('info', '新闻', "=" * 60)
            self._log_with_prefix('info', '新闻', "📰 开始新闻监控...")
            self._log_with_prefix('info', '新闻', f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 获取突发新闻
            # ⚠️ 移除"降准"、"降息"关键词（已过时，避免误导AI）
            news = self.news_manager.get_breaking_news(
                keywords=["股票", "A股", "重大政策", "行业利好"],
                urgency='normal'
            )

            if not news:
                logger.info("📰 暂无新闻数据")
                self.news_scheduler.update_monitor_time()
                return

            logger.info(f"📥 获取到{len(news)}条新闻")

            # 判断紧急程度并分类
            critical_news = []
            high_news = []
            medium_news = []
            low_news = []

            # 统计信息
            saved_count = 0
            duplicate_count = 0

            for item in news:
                urgency = self.news_manager.judge_news_urgency(item)
                item['urgency'] = urgency  # 保存紧急程度到字典

                # ✅ 保存到数据库
                news_id = self.news_db.save_news(item)
                if news_id:
                    saved_count += 1
                    # ✅ 保存数据库ID到字典（用于后续标记已推送）
                    item['db_id'] = news_id
                else:
                    duplicate_count += 1
                    # ✅ 如果是重复新闻，跳过（不添加到分类列表）
                    continue

                # 分类
                if urgency == 'critical':
                    critical_news.append(item)
                elif urgency == 'high':
                    high_news.append(item)
                elif urgency == 'medium':
                    medium_news.append(item)
                else:
                    low_news.append(item)

            # 🔴 只在有critical新闻时输出统计信息
            if len(critical_news) > 0:
                logger.info(f"📊 新闻统计: 🔴critical={len(critical_news)}条, 🟠high={len(high_news)}条, 新保存={saved_count}条")

            # ✅ 过滤已推送的新闻（使用数据库is_pushed字段）
            critical_news_filtered = []
            for item in critical_news:
                # 检查数据库中是否已推送
                if 'db_id' in item:
                    news_obj = self.news_db.get_news_by_id(item['db_id'])
                    if news_obj and not news_obj.is_pushed:
                        critical_news_filtered.append(item)
                    # elif news_obj and news_obj.is_pushed:
                    #     logger.debug(f"⏭️ 跳过已推送新闻: {item['title'][:30]}...")  # 🔴 注释掉DEBUG日志
                else:
                    # 如果没有db_id（不应该发生），使用内存缓存
                    if not self._is_news_processed(item):
                        critical_news_filtered.append(item)

            high_news_filtered = []
            for item in high_news:
                # 检查数据库中是否已推送
                if 'db_id' in item:
                    news_obj = self.news_db.get_news_by_id(item['db_id'])
                    if news_obj and not news_obj.is_pushed:
                        high_news_filtered.append(item)
                    # elif news_obj and news_obj.is_pushed:
                    #     logger.debug(f"⏭️ 跳过已推送新闻: {item['title'][:30]}...")  # 🔴 注释掉DEBUG日志
                else:
                    # 如果没有db_id（不应该发生），使用内存缓存
                    if not self._is_news_processed(item):
                        high_news_filtered.append(item)

            # 🔴 立即推送critical级别新闻 + 自动触发推荐
            if critical_news_filtered:
                logger.warning(f"🔴 发现{len(critical_news_filtered)}条新的重大利好，立即推送并触发推荐")

                # 推送新闻摘要
                news_summary = "\n\n".join([
                    f"📰 {item['title']}\n{item['content']}\n来源：{item['source']}"
                    for item in critical_news_filtered
                ])

                self.pushplus.send_message(
                    title=f"🔴 重大利好（{len(critical_news_filtered)}条）",
                    content=news_summary
                )

                # ✅ 自动触发盘中推荐
                logger.info("🎯 自动触发盘中新闻推荐...")
                intraday_recommendation = self._generate_intraday_recommendation(critical_news_filtered)

                # 推送推荐结果
                self.pushplus.send_message(
                    title="🎯 盘中新闻推荐（重大利好）",
                    content=intraday_recommendation
                )

                # ✅ 标记新闻为已推送（写入数据库）
                for item in critical_news_filtered:
                    if 'db_id' in item:
                        self.news_db.mark_as_pushed(item['db_id'])
                        # logger.debug(f"✅ 标记新闻为已推送: {item['title'][:30]}...")  # 🔴 注释掉DEBUG日志

                logger.success("✅ 重大利好推送 + 盘中推荐完成")

            # ✅ 实现high级别新闻延迟推送（5分钟后）
            if high_news_filtered:
                logger.info(f"🟠 发现{len(high_news_filtered)}条新的高优先级新闻，将在5分钟后推送")

                # 添加到延迟推送队列
                for item in high_news_filtered:
                    self.high_news_queue.append({
                        'news': item,
                        'add_time': datetime.now()
                    })

                logger.info(f"📋 当前延迟推送队列: {len(self.high_news_queue)}条")

            # ✅ 处理延迟推送队列
            self._process_high_news_queue()

            # ✅ 输出过滤原因统计
            if medium_news or low_news:
                logger.info(f"📉 过滤掉的新闻:")
                logger.info(f"  - medium级别: {len(medium_news)}条（时效性或关键词权重不足）")
                logger.info(f"  - low级别: {len(low_news)}条（旧新闻或无关键词匹配）")

            # 更新监控时间
            self.news_scheduler.update_monitor_time()
            logger.info("=" * 60)
            logger.success("✅ 新闻监控完成")

        except Exception as e:
            logger.error(f"❌ 新闻监控失败: {e}")

    def _is_news_processed(self, news: Dict[str, Any]) -> bool:
        """
        判断新闻是否已处理（内存缓存快速去重）

        Args:
            news: 新闻字典

        Returns:
            True: 已处理
            False: 未处理
        """
        # 生成新闻唯一ID（标题+来源）
        news_id = f"{news.get('title', '')}_{news.get('source', '')}"

        if news_id in self.processed_news_ids:
            return True

        # 记录已处理
        self.processed_news_ids.add(news_id)

        # 限制缓存大小（FIFO）
        if len(self.processed_news_ids) > self.processed_news_max_size:
            # 移除最早的元素
            self.processed_news_ids.pop()

        return False

    def _process_high_news_queue(self):
        """
        处理high级别新闻延迟推送队列

        检查队列中的新闻，如果超过5分钟则推送 + 触发推荐
        """
        if not self.high_news_queue:
            return

        now = datetime.now()
        to_push = []
        remaining = []

        for item in self.high_news_queue:
            elapsed = (now - item['add_time']).total_seconds()
            if elapsed >= self.high_news_push_delay:
                to_push.append(item)
            else:
                remaining.append(item)

        # 推送到期的新闻 + 触发推荐
        if to_push:
            logger.info(f"🟠 推送{len(to_push)}条延迟的high级别新闻并触发推荐")

            # 提取新闻列表
            news_list = [item['news'] for item in to_push]

            # 推送新闻摘要
            news_summary = "\n\n".join([
                f"📰 {news['title']}\n{news['content']}\n来源：{news['source']}"
                for news in news_list
            ])

            self.pushplus.send_message(
                title=f"🟠 高优先级新闻（{len(news_list)}条）",
                content=news_summary
            )

            # ✅ 自动触发盘中推荐
            logger.info("🎯 自动触发盘中新闻推荐...")
            intraday_recommendation = self._generate_intraday_recommendation(news_list)

            # 推送推荐结果
            self.pushplus.send_message(
                title="🎯 盘中新闻推荐（高优先级）",
                content=intraday_recommendation
            )

            # ✅ 标记新闻为已推送（写入数据库）
            for news in news_list:
                if 'db_id' in news:
                    self.news_db.mark_as_pushed(news['db_id'])
                    # logger.debug(f"✅ 标记新闻为已推送: {news['title'][:30]}...")  # 🔴 注释掉DEBUG日志

            logger.success("✅ 高优先级新闻推送 + 盘中推荐完成")

        # 更新队列
        self.high_news_queue = remaining

        # if remaining:
        #     logger.debug(f"📋 剩余延迟推送队列: {len(remaining)}条")  # 🔴 注释掉DEBUG日志

    def run_news_summary(self):
        """
        运行新闻汇总推送

        每小时汇总medium/low级别的新闻并推送
        """
        try:
            # 检查是否需要推送汇总
            now = datetime.now()
            if self.last_news_summary_time:
                elapsed = (now - self.last_news_summary_time).total_seconds()
                if elapsed < self.news_summary_interval:
                    return

            logger.info("📊 开始生成新闻汇总...")

            # 获取最近1小时的新闻统计
            stats = self.news_db.get_news_stats(hours=1)

            # 如果没有medium/low级别的新闻，跳过
            medium_count = stats.get('medium', 0)
            low_count = stats.get('low', 0)

            if medium_count == 0 and low_count == 0:
                logger.info("📊 最近1小时无medium/low级别新闻，跳过汇总")
                self.last_news_summary_time = now
                return

            # 获取新闻摘要
            summary = self.news_db.get_recent_news_summary(hours=1, limit=20)

            # 推送汇总
            self.pushplus.send_message(
                title=f"📊 新闻汇总（最近1小时）",
                content=f"{summary}\n\n统计信息:\n"
                       f"- medium级别: {medium_count}条\n"
                       f"- low级别: {low_count}条\n"
                       f"- 总计: {stats.get('total', 0)}条"
            )

            self.last_news_summary_time = now
            logger.success("✅ 新闻汇总推送完成")

        except Exception as e:
            logger.error(f"❌ 新闻汇总推送失败: {e}")

    def run_morning_summary(self):
        """
        运行开盘前摘要生成 + 盘前新闻推荐

        每天9:00执行：
        1. 生成开盘前新闻摘要
        2. 如果有重大利好（critical/high级别），触发盘前推荐
        """
        # 判断是否需要生成摘要
        if not self.news_scheduler.should_generate_summary():
            return

        try:
            logger.info("📰 开始生成开盘前摘要...")

            # 获取最近12小时新闻（从数据库）
            critical_news = self.news_db.get_unpushed_news(urgency='critical', limit=10)
            high_news = self.news_db.get_unpushed_news(urgency='high', limit=10)

            important_news = list(critical_news) + list(high_news)

            if not important_news:
                logger.info("📰 暂无重大利好新闻，跳过盘前推荐")
                self.news_scheduler.update_summary_date()
                return

            logger.info(f"📰 发现{len(important_news)}条重大利好新闻（critical: {len(critical_news)}, high: {len(high_news)}）")

            # 生成新闻摘要
            news_list = [
                {
                    'title': news.title,
                    'content': news.content or '',
                    'source': news.source,
                    'urgency': news.urgency,
                    'publish_time': news.publish_time.strftime('%Y-%m-%d %H:%M') if news.publish_time else '未知'
                }
                for news in important_news
            ]

            summary = self.news_summary_generator.generate_summary(news_list)

            # 🔴 新增：盘前新闻推荐
            pre_market_recommendation = self._generate_pre_market_recommendation(news_list)

            # 推送通知
            full_content = f"{summary}\n\n{'='*60}\n\n{pre_market_recommendation}"

            logger.info("📰 推送开盘前摘要 + 盘前推荐")
            self.pushplus.send_message(
                title="📰 开盘前摘要 + 盘前推荐",
                content=full_content
            )

            # 标记新闻为已推送
            for news in important_news:
                self.news_db.mark_as_pushed(news.id)

            # 更新摘要日期
            self.news_scheduler.update_summary_date()
            logger.success("✅ 开盘前摘要 + 盘前推荐完成")

        except Exception as e:
            logger.error(f"❌ 开盘前摘要生成失败: {e}")
            logger.exception("详细错误:")

    def _generate_intraday_recommendation(self, news_list: list) -> str:
        """
        生成盘中新闻推荐（基于重大利好新闻）

        与盘前推荐的区别：
        - 盘中可以获取实时数据（价格、涨跌幅、盘口）
        - 推荐逻辑更激进（追涨停）
        - 操作建议更具体（立即买入 vs 等待回调）

        Args:
            news_list: 重大利好新闻列表

        Returns:
            盘中推荐文本
        """
        try:
            from src.agents.tools.pre_market_news_tools import (
                extract_sectors_from_news,
                screen_sector_leaders
            )

            logger.info("🎯 开始生成盘中新闻推荐...")

            # 步骤1：提取新闻相关板块
            sectors_result = extract_sectors_from_news.run(news_list=news_list)
            logger.info(f"板块提取结果:\n{sectors_result}")

            # 如果没有提取到板块，返回提示
            if "❌" in sectors_result or "未能" in sectors_result:
                return f"""
🎯 盘中新闻推荐

{sectors_result}

💡 建议：
- 人工分析新闻内容，判断相关板块
- 关注板块龙头股的实时表现
- 观察资金流向和涨停封单情况
"""

            # 步骤2：从板块中筛选龙头股
            import re
            # 修改正则：匹配 "✅ 板块名称" 或 "✅ 板块名称:"
            sector_names = re.findall(r'✅ ([^\n:：]+)', sectors_result)

            if not sector_names:
                return f"""
🎯 盘中新闻推荐

{sectors_result}

⚠️ 未能自动提取板块名称，请人工判断
"""

            # 对每个板块筛选候选股
            all_candidates = []
            screening_results = []

            for sector_name in sector_names[:2]:  # 最多处理2个板块
                leaders_result = screen_sector_leaders.run(
                    sector_name=sector_name,
                    min_change_pct=0.0,  # 盘中不限制昨日涨幅（关注实时表现）
                    min_volume=100000000,  # 成交额>1亿
                    max_market_cap=50000000000,  # ✅ 最大流通市值500亿（盘中追高，选择中盘股）
                    min_market_cap=5000000000,   # ✅ 最小流通市值50亿（扩大选股范围）
                    max_price=50.0,  # ✅ 最高价格50元（避免高价股）
                    min_price=5.0,   # ✅ 最低价格5元（避免低价股）
                    top_n=3  # 每个板块返回3只候选股
                )
                screening_results.append(leaders_result)

                # 提取候选股代码
                import re
                codes_match = re.search(r'📋 候选股代码：([0-9,]+)', leaders_result)
                if codes_match:
                    codes = codes_match.group(1).split(',')
                    all_candidates.extend(codes)

            # 如果没有候选股，返回筛选结果
            if not all_candidates:
                result_lines = [
                    "🎯 盘中新闻推荐（重大利好驱动）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🏆 候选股筛选：",
                ]
                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                return "\n".join(result_lines)

            # ✅ 调用stock_evaluation_crew进行深度分析
            logger.info(f"🤖 调用AI深度分析候选股: {all_candidates}")

            try:
                from src.crews.stock_evaluation_crew import create_stock_evaluation_crew

                # 取前3只候选股进行深度分析（避免分析时间过长）
                top_candidates = all_candidates[:3]
                stock_codes_str = ','.join(top_candidates)

                logger.info(f"🎯 开始深度分析: {stock_codes_str}")

                # 创建并运行评估Crew
                crew = create_stock_evaluation_crew(
                    stock_codes=stock_codes_str,
                    session_id=self.session_id
                )

                result = crew.kickoff()
                analysis_result = result.raw if hasattr(result, 'raw') else str(result)

                logger.success(f"✅ AI深度分析完成")

                # 格式化输出
                result_lines = [
                    "🎯 盘中新闻推荐（重大利好驱动 + AI深度分析）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🔍 候选股筛选：",
                ]

                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                result_lines.extend([
                    "=" * 60,
                    "🤖 AI深度分析（多维分析师 + 风险管理官 + 投资决策官）",
                    "=" * 60,
                    "",
                    analysis_result,
                    "",
                    "💡 操作建议（盘中）：",
                    "1. 立即查看推荐股票的实时走势和盘口",
                    "2. 如果正在拉升且封单强劲，可考虑追涨停",
                    "3. 如果已经涨停，观察封单情况，强封可排队",
                    "4. 如果涨幅<3%，等待回调至合理价位",
                    "5. 目标：涨停或高水位（>7%涨幅）",
                    "",
                    "⚠️ 风险提示：",
                    "- 盘中追高风险大，建议仓位控制在10-15%",
                    "- 设置止损位（-3%）",
                    "- 如果冲高回落，果断止损",
                    "- 避免在尾盘最后30分钟追高",
                ])

                return "\n".join(result_lines)

            except Exception as e:
                logger.error(f"❌ AI深度分析失败: {e}")
                logger.exception("详细错误:")

                # 降级：返回筛选结果
                result_lines = [
                    "🎯 盘中新闻推荐（重大利好驱动）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🏆 候选股筛选：",
                ]

                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                result_lines.extend([
                    "⚠️ AI深度分析失败，请手动分析以上候选股",
                    "",
                    "💡 操作建议（盘中）：",
                    "1. 立即查看推荐股票的实时走势和盘口",
                    "2. 如果正在拉升且封单强劲，可考虑追涨停",
                    "3. 如果已经涨停，观察封单情况，强封可排队",
                    "4. 如果涨幅<3%，等待回调至合理价位",
                    "5. 目标：涨停或高水位（>7%涨幅）",
                ])

                return "\n".join(result_lines)

        except Exception as e:
            logger.error(f"❌ 生成盘中推荐失败: {e}")
            logger.exception("详细错误:")
            return f"❌ 生成盘中推荐失败: {str(e)}"

    def _generate_pre_market_recommendation(self, news_list: list) -> str:
        """
        生成盘前新闻推荐（基于重大利好新闻）

        策略：
        1. 提取新闻相关板块
        2. 从板块中筛选昨日强势龙头股
        3. 推荐1-2只涨停潜力股

        Args:
            news_list: 重大利好新闻列表

        Returns:
            盘前推荐文本
        """
        try:
            from src.agents.tools.pre_market_news_tools import (
                extract_sectors_from_news,
                screen_sector_leaders
            )

            logger.info("🎯 开始生成盘前新闻推荐...")

            # 步骤1：提取新闻相关板块
            sectors_result = extract_sectors_from_news.run(news_list=news_list)
            logger.info(f"板块提取结果:\n{sectors_result}")

            # 如果没有提取到板块，返回提示
            if "❌" in sectors_result or "未能" in sectors_result:
                return f"""
🎯 盘前新闻推荐

{sectors_result}

💡 建议：
- 人工分析新闻内容，判断相关板块
- 关注板块龙头股的集合竞价表现
- 9:15-9:25集合竞价期间观察资金流向
"""

            # 步骤2：从板块中筛选龙头股
            # 简单解析板块名称（从sectors_result中提取）
            import re
            # 修改正则：匹配 "✅ 板块名称" 或 "✅ 板块名称:"
            sector_names = re.findall(r'✅ ([^\n:：]+)', sectors_result)

            if not sector_names:
                return f"""
🎯 盘前新闻推荐

{sectors_result}

⚠️ 未能自动提取板块名称，请人工判断
"""

            # 对每个板块筛选候选股
            all_candidates = []
            screening_results = []

            for sector_name in sector_names[:2]:  # 最多处理2个板块
                leaders_result = screen_sector_leaders.run(
                    sector_name=sector_name,
                    min_change_pct=3.0,  # 昨日涨幅>3%
                    min_volume=100000000,  # 成交额>1亿
                    max_market_cap=50000000000,  # ✅ 最大流通市值500亿（盘前埋伏，选择中盘股）
                    min_market_cap=5000000000,   # ✅ 最小流通市值50亿（扩大选股范围）
                    max_price=50.0,  # ✅ 最高价格50元（避免高价股）
                    min_price=5.0,   # ✅ 最低价格5元（避免低价股）
                    top_n=3  # 每个板块返回3只候选股
                )
                screening_results.append(leaders_result)

                # 提取候选股代码
                import re
                codes_match = re.search(r'📋 候选股代码：([0-9,]+)', leaders_result)
                if codes_match:
                    codes = codes_match.group(1).split(',')
                    all_candidates.extend(codes)

            # 如果没有候选股，返回筛选结果
            if not all_candidates:
                result_lines = [
                    "🎯 盘前新闻推荐（涨停潜力股）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🏆 候选股筛选：",
                ]
                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                return "\n".join(result_lines)

            # ✅ 调用stock_evaluation_crew进行深度分析
            logger.info(f"🤖 调用AI深度分析候选股: {all_candidates}")

            try:
                from src.crews.stock_evaluation_crew import create_stock_evaluation_crew

                # 取前3只候选股进行深度分析（避免分析时间过长）
                top_candidates = all_candidates[:3]
                stock_codes_str = ','.join(top_candidates)

                logger.info(f"🎯 开始深度分析: {stock_codes_str}")

                # 创建并运行评估Crew
                crew = create_stock_evaluation_crew(
                    stock_codes=stock_codes_str,
                    session_id=self.session_id
                )

                result = crew.kickoff()
                analysis_result = result.raw if hasattr(result, 'raw') else str(result)

                logger.success(f"✅ AI深度分析完成")

                # 格式化输出
                result_lines = [
                    "🎯 盘前新闻推荐（涨停潜力股 + AI深度分析）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🔍 候选股筛选：",
                ]

                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                result_lines.extend([
                    "=" * 60,
                    "🤖 AI深度分析（多维分析师 + 风险管理官 + 投资决策官）",
                    "=" * 60,
                    "",
                    analysis_result,
                    "",
                    "💡 操作建议：",
                    "1. 9:15-9:25集合竞价期间观察这些股票的资金流向",
                    "2. 如果集合竞价高开且封单强劲，可考虑挂涨停价买入",
                    "3. 如果开盘后快速拉升，不建议追高，等待回调",
                    "4. 目标：抓涨停或高水位（>5%涨幅）",
                    "",
                    "⚠️ 风险提示：",
                    "- 盘前推荐基于新闻驱动，波动较大",
                    "- 建议仓位控制在10-20%",
                    "- 设置止损位（-3%）",
                ])

                return "\n".join(result_lines)

            except Exception as e:
                logger.error(f"❌ AI深度分析失败: {e}")
                logger.exception("详细错误:")

                # 降级：返回筛选结果
                result_lines = [
                    "🎯 盘前新闻推荐（涨停潜力股）",
                    "",
                    "📊 相关板块：",
                    sectors_result,
                    "",
                    "🏆 候选股筛选：",
                ]

                for rec in screening_results:
                    result_lines.append(rec)
                    result_lines.append("")

                result_lines.extend([
                    "⚠️ AI深度分析失败，请手动分析以上候选股",
                    "",
                    "💡 操作建议：",
                    "1. 9:15-9:25集合竞价期间观察这些股票的资金流向",
                    "2. 如果集合竞价高开且封单强劲，可考虑挂涨停价买入",
                    "3. 如果开盘后快速拉升，不建议追高，等待回调",
                    "4. 目标：抓涨停或高水位（>5%涨幅）",
                ])

                return "\n".join(result_lines)

        except Exception as e:
            logger.error(f"❌ 生成盘前推荐失败: {e}")
            logger.exception("详细错误:")
            return f"❌ 生成盘前推荐失败: {str(e)}"

    def _trigger_morning_recommendation(self, news_summary: str) -> str:
        """
        触发早盘推荐

        Args:
            news_summary: 新闻摘要

        Returns:
            推荐结果
        """
        try:
            # 保存新闻上下文到AgentContext
            from src.agents.tools.context_tools import _save_context

            # 保存新闻上下文（使用辅助函数，不需要set_current_session_id）
            _save_context(
                session_id=self.session_id,
                context_type='news_context',
                context_data={
                    'source': '早盘汇总',
                    'content': news_summary,
                    'timestamp': datetime.now().isoformat()
                }
            )

            logger.info("✅ 新闻上下文已保存到AgentContext")

            # 触发推荐
            from src.crews.smart_recommendation_crew import create_smart_recommendation_crew
            crew = create_smart_recommendation_crew(session_id=self.session_id)
            result = crew.kickoff()

            return result.raw if hasattr(result, 'raw') else str(result)

        except Exception as e:
            logger.error(f"❌ 早盘推荐失败: {e}")
            return f"推荐失败: {e}"

    def _trigger_news_recommendation(self, critical_news: list) -> str:
        """
        触发重大利好推荐

        Args:
            critical_news: 重大利好新闻列表

        Returns:
            推荐结果
        """
        try:
            # 格式化新闻内容
            news_content = "\n\n".join([
                f"【{item['title']}】\n{item['content']}\n来源：{item['source']}"
                for item in critical_news
            ])

            # 保存新闻上下文到AgentContext
            from src.agents.tools.context_tools import _save_context

            # 保存新闻上下文（使用辅助函数，不需要set_current_session_id）
            _save_context(
                session_id=self.session_id,
                context_type='news_context',
                context_data={
                    'source': '重大利好',
                    'content': news_content,
                    'timestamp': datetime.now().isoformat()
                }
            )

            logger.info("✅ 新闻上下文已保存到AgentContext")

            # 触发推荐
            from src.crews.smart_recommendation_crew import create_smart_recommendation_crew
            crew = create_smart_recommendation_crew(session_id=self.session_id)
            result = crew.kickoff()

            return result.raw if hasattr(result, 'raw') else str(result)

        except Exception as e:
            logger.error(f"❌ 重大利好推荐失败: {e}")
            return f"推荐失败: {e}"

    def run_performance_update(self):
        """
        运行推荐绩效更新（每天17:00执行）

        功能：
        - 自动更新所有未更新绩效的推荐记录
        - 计算开盘/最高/收盘收益率
        - 判断是否冲高回落
        """
        try:
            self._log_with_prefix('info', '绩效', "=" * 60)
            self._log_with_prefix('info', '绩效', "📊 开始更新推荐绩效...")
            self._log_with_prefix('info', '绩效', f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._log_with_prefix('info', '绩效', f"👤 用户: {self.session_id}")
            self._log_with_prefix('info', '绩效', "=" * 60)

            # 导入绩效更新函数
            from src.utils.update_recommendation_performance import update_candidate_performance

            # 执行更新
            update_candidate_performance(session_id=self.session_id)

            self._log_with_prefix('success', '绩效', "✅ 推荐绩效更新完成！")

        except Exception as e:
            self._log_with_prefix('error', '绩效', f"❌ 推荐绩效更新失败: {e}")
            logger.exception("详细错误:")

    def run_database_backup(self):
        """
        运行数据库备份（每天凌晨2:00执行）

        功能：
        - 自动备份数据库
        - 清理30天前的旧备份
        """
        try:
            logger.info("=" * 60)
            logger.info("📦 开始数据库备份...")
            logger.info(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 60)

            # 创建备份
            backup_path = self.db_backup.create_backup()

            if backup_path:
                # 清理旧备份
                deleted_count = self.db_backup.cleanup_old_backups(keep_days=30)
                logger.success(f"✅ 数据库备份完成！备份路径: {backup_path}")

                if deleted_count > 0:
                    logger.info(f"🗑️ 已清理 {deleted_count} 个旧备份文件")
            else:
                logger.error("❌ 数据库备份失败！")

        except Exception as e:
            logger.error(f"❌ 数据库备份异常: {e}")
            logger.exception("详细错误:")


# 全局调度器实例
_scheduler = None


def get_scheduler(monitor_interval: float = 0.05):
    """
    获取调度器实例（单例）

    Args:
        monitor_interval: 监控间隔（分钟），默认0.05分钟（3秒）
                         只在第一次创建时生效

    Returns:
        StockScheduler实例
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = StockScheduler(monitor_interval=monitor_interval)
    return _scheduler

