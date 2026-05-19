#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻数据库管理器 - CrewAI Stock V2.0

描述: 管理市场新闻的数据库操作
- 保存新闻到数据库
- 查询未推送的新闻
- 标记新闻为已推送
- 查询新闻统计信息

作者: AI Architect
版本: v1.0.0
日期: 2025-11-14
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import IntegrityError

from src.database.models import MarketNews
from src.database.connection import get_session

# 配置日志
logger = logging.getLogger(__name__)


class NewsDBManager:
    """新闻数据库管理器（全局共享，不区分用户）"""

    def __init__(self):
        """初始化新闻数据库管理器"""
        pass
    
    def save_news(self, news_data: Dict[str, Any]) -> Optional[int]:
        """
        保存新闻到数据库

        Args:
            news_data: 新闻数据字典

        Returns:
            新闻ID，如果已存在则返回None
        """
        session = get_session()
        try:
            # 检查是否已存在（根据标题+来源去重）
            existing = session.query(MarketNews).filter(
                and_(
                    MarketNews.title == news_data.get('title'),
                    MarketNews.source == news_data.get('source')
                )
            ).first()

            if existing:
                logger.debug(f"新闻已存在，跳过保存: {news_data.get('title')}")
                return None

            # ✅ 处理publish_time（可能是字符串或datetime对象）
            publish_time = news_data.get('publish_time')
            if publish_time and isinstance(publish_time, str):
                try:
                    from dateutil import parser as date_parser
                    publish_time = date_parser.parse(publish_time)
                except Exception as e:
                    logger.warning(f"解析发布时间失败: {e}, 使用None")
                    publish_time = None

            # 创建新闻记录
            news = MarketNews(
                title=news_data.get('title'),
                content=news_data.get('content'),
                source=news_data.get('source'),
                url=news_data.get('url'),
                publish_time=publish_time,
                urgency=news_data.get('urgency'),
                urgency_score=news_data.get('urgency_score'),
                time_weight=news_data.get('time_weight'),
                matched_keywords=news_data.get('matched_keywords', []),
                related_stocks=news_data.get('related_stocks', []),
                related_topics=news_data.get('related_topics', []),
            )

            session.add(news)
            session.commit()
            news_id = news.id  # ✅ 在session关闭前获取ID
            logger.debug(f"✅ 新闻已保存: {news_data.get('title')}")
            return news_id

        except IntegrityError as e:
            # 并发场景下的重复新闻，静默处理
            session.rollback()
            logger.debug(f"新闻已存在（并发插入），跳过保存: {news_data.get('title')}")
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 保存新闻失败: {e}")
            return None
        finally:
            session.close()
    
    def get_unpushed_news(self, urgency: Optional[str] = None, limit: int = 100) -> List[MarketNews]:
        """
        获取未推送的新闻
        
        Args:
            urgency: 紧急程度过滤（可选）
            limit: 返回数量限制
            
        Returns:
            新闻列表
        """
        session = get_session()
        try:
            query = session.query(MarketNews).filter(MarketNews.is_pushed == False)

            if urgency:
                query = query.filter(MarketNews.urgency == urgency)

            news_list = query.order_by(desc(MarketNews.monitor_time)).limit(limit).all()
            return news_list

        except Exception as e:
            logger.error(f"❌ 查询未推送新闻失败: {e}")
            return []
        finally:
            session.close()
    
    def get_news_by_id(self, news_id: int):
        """
        根据ID获取新闻

        Args:
            news_id: 新闻ID

        Returns:
            新闻对象或None
        """
        session = get_session()
        try:
            news = session.query(MarketNews).filter(MarketNews.id == news_id).first()
            return news
        except Exception as e:
            logger.error(f"❌ 获取新闻失败: {e}")
            return None
        finally:
            session.close()

    def mark_as_pushed(self, news_id: int) -> bool:
        """
        标记新闻为已推送

        Args:
            news_id: 新闻ID

        Returns:
            是否成功
        """
        session = get_session()
        try:
            news = session.query(MarketNews).filter(MarketNews.id == news_id).first()
            if news:
                news.is_pushed = True
                news.push_time = datetime.now()
                session.commit()
                logger.debug(f"✅ 标记新闻为已推送: ID={news_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"❌ 标记新闻为已推送失败: {e}")
            return False
        finally:
            session.close()

    def get_news_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取新闻统计信息

        Args:
            hours: 统计时间范围（小时）

        Returns:
            统计信息字典
        """
        session = get_session()
        try:
            since_time = datetime.now() - timedelta(hours=hours)

            # 查询指定时间范围内的新闻
            news_list = session.query(MarketNews).filter(
                MarketNews.monitor_time >= since_time
            ).all()

            # 统计各紧急程度的数量
            stats = {
                'total': len(news_list),
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'pushed': 0,
                'unpushed': 0,
            }

            for news in news_list:
                if news.urgency:
                    stats[news.urgency] = stats.get(news.urgency, 0) + 1
                if news.is_pushed:
                    stats['pushed'] += 1
                else:
                    stats['unpushed'] += 1

            return stats

        except Exception as e:
            logger.error(f"❌ 获取新闻统计失败: {e}")
            return {}
        finally:
            session.close()

    def get_recent_news_summary(self, hours: int = 24, limit: int = 10) -> str:
        """
        获取最近新闻摘要（用于日志输出）

        Args:
            hours: 时间范围（小时）
            limit: 返回数量

        Returns:
            新闻摘要文本
        """
        session = get_session()
        try:
            since_time = datetime.now() - timedelta(hours=hours)

            news_list = session.query(MarketNews).filter(
                MarketNews.monitor_time >= since_time
            ).order_by(desc(MarketNews.monitor_time)).limit(limit).all()

            if not news_list:
                return f"最近{hours}小时无新闻"

            summary_lines = [f"最近{hours}小时新闻摘要（共{len(news_list)}条）："]
            for i, news in enumerate(news_list, 1):
                time_str = news.monitor_time.strftime('%H:%M')
                summary_lines.append(
                    f"{i}. [{news.urgency}] {time_str} {news.title[:50]}..."
                )

            return "\n".join(summary_lines)

        except Exception as e:
            logger.error(f"❌ 获取新闻摘要失败: {e}")
            return ""
        finally:
            session.close()

