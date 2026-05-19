"""
添加AI分析字段到Position表

运行方式：
python -m src.database.add_ai_analysis_fields
"""

from sqlalchemy import text
from src.database.db_manager import get_db
from loguru import logger


def add_ai_analysis_fields():
    """添加AI分析字段"""
    db = get_db()
    
    try:
        with db.get_session() as session:
            # 检查字段是否已存在
            result = session.execute(text("PRAGMA table_info(positions)"))
            columns = [row[1] for row in result.fetchall()]
            
            fields_to_add = [
                ("ai_sell_suggestion", "VARCHAR(50)"),
                ("ai_sell_reason", "TEXT"),
                ("ai_urgency", "VARCHAR(20)"),
                ("ai_analysis_time", "DATETIME"),
                ("ai_bid_ask_ratio", "DECIMAL(5, 2)"),
                ("ai_bid_ask_analysis", "TEXT"),
                ("ai_fund_flow", "VARCHAR(50)"),
                ("ai_fund_flow_analysis", "TEXT"),
                ("ai_technical_analysis", "TEXT")
            ]
            
            for field_name, field_type in fields_to_add:
                if field_name not in columns:
                    logger.info(f"添加字段: {field_name} {field_type}")
                    session.execute(text(f"ALTER TABLE positions ADD COLUMN {field_name} {field_type}"))
                else:
                    logger.info(f"字段已存在: {field_name}")
            
            session.commit()
            logger.success("✅ AI分析字段添加完成！")
            
    except Exception as e:
        logger.error(f"❌ 添加字段失败: {e}")
        raise


if __name__ == "__main__":
    add_ai_analysis_fields()

