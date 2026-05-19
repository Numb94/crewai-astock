#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Memory预热脚本 - 将历史数据导入CrewAI Memory

从Candidate/Position/Transaction表提取经验，生成Memory记录：
1. 策略胜率经验 → Long-term Memory
2. 成功案例 → Entity Memory (股票实体)
3. 失败教训 → Long-term Memory

运行方式:
    python scripts/warmup_memory.py
"""

import os
import sys
from datetime import date, timedelta
from collections import defaultdict

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.database.db_manager import get_db
from src.database.models import Candidate, Position, Transaction
from sqlalchemy import func


def collect_strategy_performance():
    """收集策略表现数据（基于已卖出持仓）"""
    logger.info("📊 收集策略表现数据...")

    db = get_db()
    experiences = []

    with db.get_session() as session:
        # 按策略分组统计
        strategy_stats = defaultdict(lambda: {
            "total": 0, "win": 0, "total_return": 0, "stocks": []
        })

        # 直接从已卖出的持仓记录统计
        sold_positions = session.query(Position).filter(
            Position.status == 'sold',
            Position.sell_price.isnot(None),
            Position.buy_price.isnot(None)
        ).all()

        for pos in sold_positions:
            buy_price = float(pos.buy_price)
            sell_price = float(pos.sell_price)

            if buy_price <= 0:
                continue

            profit_pct = (sell_price - buy_price) / buy_price * 100

            # 查找对应的推荐记录获取策略名
            candidate = session.query(Candidate).filter(
                Candidate.stock_code == pos.stock_code
            ).order_by(Candidate.recommend_time.desc()).first()

            strategy = candidate.strategy_name if candidate else "未知策略"

            strategy_stats[strategy]["total"] += 1
            strategy_stats[strategy]["total_return"] += profit_pct

            if profit_pct > 0:
                strategy_stats[strategy]["win"] += 1

            strategy_stats[strategy]["stocks"].append({
                "code": pos.stock_code,
                "name": pos.stock_name,
                "return": round(profit_pct, 2),
                "result": "成功" if profit_pct > 0 else "失败"
            })

        # 生成策略经验
        for strategy, stats in strategy_stats.items():
            if stats["total"] == 0:
                continue

            win_rate = stats["win"] / stats["total"] * 100
            avg_return = stats["total_return"] / stats["total"]

            experience = {
                "type": "strategy_performance",
                "strategy": strategy,
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_return, 2),
                "sample_count": stats["total"],
                "text": f"【策略经验】{strategy}：历史胜率{win_rate:.1f}%，平均收益{avg_return:.2f}%，样本数{stats['total']}次",
                "stocks": stats["stocks"]
            }
            experiences.append(experience)
            logger.info(f"  ✅ {strategy}: 胜率{win_rate:.1f}%, 平均收益{avg_return:.2f}%")

    return experiences


def collect_trade_cases():
    """收集交易案例（基于已卖出持仓）"""
    logger.info("📈 收集交易案例...")

    db = get_db()
    cases = []

    with db.get_session() as session:
        # 从已卖出持仓收集案例
        sold_positions = session.query(Position).filter(
            Position.status == 'sold',
            Position.sell_price.isnot(None),
            Position.buy_price.isnot(None)
        ).all()

        for pos in sold_positions:
            buy_price = float(pos.buy_price)
            sell_price = float(pos.sell_price)

            if buy_price <= 0:
                continue

            profit_pct = (sell_price - buy_price) / buy_price * 100

            # 查找对应的推荐记录获取策略名
            candidate = session.query(Candidate).filter(
                Candidate.stock_code == pos.stock_code
            ).order_by(Candidate.recommend_time.desc()).first()

            strategy = candidate.strategy_name if candidate else "未知策略"

            if profit_pct > 3:
                # 成功案例
                case = {
                    "type": "success_case",
                    "stock_code": pos.stock_code,
                    "stock_name": pos.stock_name,
                    "strategy": strategy,
                    "return": round(profit_pct, 2),
                    "buy_date": str(pos.buy_date),
                    "sell_date": str(pos.sell_date),
                    "text": f"【成功案例】{pos.stock_code} {pos.stock_name}，策略:{strategy}，收益+{profit_pct:.1f}%，持仓{pos.buy_date}至{pos.sell_date}"
                }
                cases.append(case)

            elif profit_pct < -2:
                # 失败教训
                case = {
                    "type": "failure_lesson",
                    "stock_code": pos.stock_code,
                    "stock_name": pos.stock_name,
                    "strategy": strategy,
                    "return": round(profit_pct, 2),
                    "buy_date": str(pos.buy_date),
                    "sell_date": str(pos.sell_date),
                    "text": f"【失败教训】{pos.stock_code} {pos.stock_name}，策略:{strategy}，亏损{profit_pct:.1f}%，需要反思原因"
                }
                cases.append(case)
            else:
                # 普通案例（小盈小亏）
                case = {
                    "type": "normal_case",
                    "stock_code": pos.stock_code,
                    "stock_name": pos.stock_name,
                    "strategy": strategy,
                    "return": round(profit_pct, 2),
                    "buy_date": str(pos.buy_date),
                    "sell_date": str(pos.sell_date),
                    "text": f"【交易记录】{pos.stock_code} {pos.stock_name}，策略:{strategy}，收益{profit_pct:+.1f}%"
                }
                cases.append(case)

        success = len([c for c in cases if c['type'] == 'success_case'])
        failure = len([c for c in cases if c['type'] == 'failure_lesson'])
        normal = len([c for c in cases if c['type'] == 'normal_case'])
        logger.info(f"  ✅ 成功案例: {success}条")
        logger.info(f"  ⚠️ 失败教训: {failure}条")
        logger.info(f"  📝 普通记录: {normal}条")

    return cases


def warmup_crewai_memory(experiences: list, lessons: list):
    """将经验导入CrewAI Memory"""
    logger.info("🧠 导入CrewAI Memory...")

    from src.config.embeddings_config import get_siliconflow_embedder_config

    embedder_config = get_siliconflow_embedder_config()
    if not embedder_config:
        logger.error("❌ 未配置SILICONFLOW_API_KEY，无法预热Memory")
        return False

    # 设置存储路径
    storage_path = "./storage"
    os.makedirs(storage_path, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = storage_path

    # 直接使用Storage层（不经过LongTermMemory封装）
    from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage
    from datetime import datetime
    import json

    ltm_storage = LTMSQLiteStorage(db_path=f"{storage_path}/long_term_memory.db")

    success_count = 0

    # 导入策略经验
    logger.info("  📥 导入策略经验...")
    for exp in experiences:
        try:
            # 直接调用storage.save()
            ltm_storage.save(
                task_description=exp["text"],
                metadata=json.dumps({
                    "type": exp["type"],
                    "strategy": exp["strategy"],
                    "win_rate": exp["win_rate"],
                    "avg_return": exp["avg_return"],
                    "sample_count": exp["sample_count"],
                    "agent": "复盘分析师"
                }),
                datetime=datetime.now().isoformat(),
                score=exp["win_rate"] / 100  # 用胜率作为质量分
            )
            success_count += 1
            logger.info(f"    ✅ {exp['strategy']}")
        except Exception as e:
            logger.warning(f"    ⚠️ 导入失败: {e}")

    # 导入交易案例
    logger.info("  📥 导入交易案例...")
    for lesson in lessons:
        try:
            score = 0.8 if lesson["type"] == "success_case" else 0.3
            ltm_storage.save(
                task_description=lesson["text"],
                metadata=json.dumps({
                    "type": lesson["type"],
                    "stock_code": lesson["stock_code"],
                    "stock_name": lesson["stock_name"],
                    "strategy": lesson["strategy"],
                    "return": lesson["return"],
                    "agent": "复盘分析师"
                }),
                datetime=datetime.now().isoformat(),
                score=score
            )
            success_count += 1
            logger.info(f"    ✅ {lesson['stock_code']} {lesson['stock_name']}")
        except Exception as e:
            logger.warning(f"    ⚠️ 导入失败: {e}")

    logger.info(f"✅ Memory预热完成！成功导入 {success_count} 条经验")
    return True


def verify_memory():
    """验证Memory内容"""
    logger.info("🔍 验证Memory内容...")

    storage_path = "./storage"
    db_path = f"{storage_path}/long_term_memory.db"

    if not os.path.exists(db_path):
        logger.warning("⚠️ Memory数据库不存在")
        return

    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查询表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    logger.info(f"  📋 数据库表: {[t[0] for t in tables]}")

    # 查询记录数
    try:
        cursor.execute("SELECT COUNT(*) FROM long_term_memories")
        count = cursor.fetchone()[0]
        logger.info(f"  📊 Memory记录数: {count}")

        # 查看表结构
        cursor.execute("PRAGMA table_info(long_term_memories)")
        columns = cursor.fetchall()
        col_names = [c[1] for c in columns]
        logger.info(f"  📋 表字段: {col_names}")

        # 显示最近几条
        cursor.execute("SELECT datetime, task_description FROM long_term_memories ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()

        logger.info("  📝 最近导入的经验:")
        for row in rows:
            text = row[1][:60] if row[1] else "(空)"
            logger.info(f"    - {text}...")
    except Exception as e:
        logger.warning(f"  ⚠️ 查询失败: {e}")

    conn.close()


def main():
    """主函数"""
    print("\n" + "🚀" * 20)
    print("   CrewAI Memory 预热工具")
    print("🚀" * 20 + "\n")

    # 1. 收集数据
    experiences = collect_strategy_performance()
    cases = collect_trade_cases()

    if not experiences and not cases:
        logger.warning("⚠️ 没有找到历史数据，无需预热")
        return

    print(f"\n📊 数据汇总:")
    print(f"   策略经验: {len(experiences)} 条")
    print(f"   交易案例: {len(cases)} 条")

    # 2. 导入Memory
    print("\n")
    success = warmup_crewai_memory(experiences, cases)

    if success:
        # 3. 验证
        print("\n")
        verify_memory()

        print("\n" + "✅" * 20)
        print("   Memory预热完成！")
        print("   Agent现在拥有历史经验了")
        print("✅" * 20 + "\n")


if __name__ == "__main__":
    main()

