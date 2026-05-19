"""
数据库迁移脚本：为Candidate、Position、Transaction表添加绩效跟踪字段

执行方式：
    python src/database/add_performance_fields.py
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

def add_candidate_performance_fields():
    """为Candidate表添加绩效跟踪字段"""
    from src.database.connection import engine as db_engine
    
    fields_to_add = [
        ("next_day_open_price", "DECIMAL(10, 2)", "次日开盘价"),
        ("next_day_high_price", "DECIMAL(10, 2)", "次日最高价"),
        ("next_day_close_price", "DECIMAL(10, 2)", "次日收盘价"),
        ("actual_open_profit_pct", "DECIMAL(10, 2)", "开盘价收益率"),
        ("actual_high_profit_pct", "DECIMAL(10, 2)", "最高价收益率"),
        ("actual_close_profit_pct", "DECIMAL(10, 2)", "收盘价收益率"),
        ("is_rush_high_pullback", "BOOLEAN DEFAULT 0", "是否冲高回落"),
        ("performance_updated_at", "DATETIME", "绩效更新时间"),
    ]
    
    print("=" * 80)
    print("开始为Candidate表添加绩效跟踪字段...")
    print("=" * 80)
    
    with db_engine.connect() as conn:
        for field_name, field_type, description in fields_to_add:
            try:
                # 检查字段是否已存在
                result = conn.execute(text(f"PRAGMA table_info(candidates)"))
                existing_fields = [row[1] for row in result]
                
                if field_name in existing_fields:
                    print(f"✅ 字段 {field_name} 已存在，跳过")
                    continue
                
                # 添加字段
                sql = f"ALTER TABLE candidates ADD COLUMN {field_name} {field_type}"
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ 成功添加字段: {field_name} ({description})")
                
            except Exception as e:
                print(f"❌ 添加字段 {field_name} 失败: {e}")
    
    print("\n✅ Candidate表字段添加完成！\n")


def add_position_lifecycle_fields():
    """为Position表添加生命周期跟踪字段"""
    from src.database.connection import engine as db_engine
    
    fields_to_add = [
        ("stop_loss_triggered", "BOOLEAN DEFAULT 0", "止损是否触发"),
        ("stop_loss_price", "DECIMAL(10, 2)", "止损触发价格"),
        ("stop_loss_time", "DATETIME", "止损触发时间"),
        ("sell_reason", "VARCHAR(50)", "卖出原因"),
        ("max_profit_pct", "DECIMAL(10, 2)", "持仓期间最大盈利百分比"),
        ("max_loss_pct", "DECIMAL(10, 2)", "持仓期间最大亏损百分比"),
    ]
    
    print("=" * 80)
    print("开始为Position表添加生命周期跟踪字段...")
    print("=" * 80)
    
    with db_engine.connect() as conn:
        for field_name, field_type, description in fields_to_add:
            try:
                # 检查字段是否已存在
                result = conn.execute(text(f"PRAGMA table_info(positions)"))
                existing_fields = [row[1] for row in result]
                
                if field_name in existing_fields:
                    print(f"✅ 字段 {field_name} 已存在，跳过")
                    continue
                
                # 添加字段
                sql = f"ALTER TABLE positions ADD COLUMN {field_name} {field_type}"
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ 成功添加字段: {field_name} ({description})")
                
            except Exception as e:
                print(f"❌ 添加字段 {field_name} 失败: {e}")
    
    print("\n✅ Position表字段添加完成！\n")


def add_transaction_decision_fields():
    """为Transaction表添加决策依据字段"""
    from src.database.connection import engine as db_engine
    
    fields_to_add = [
        ("decision_reason", "VARCHAR(200)", "交易决策依据"),
        ("decision_agent", "VARCHAR(50)", "决策Agent名称"),
        ("related_recommendation_id", "INTEGER", "关联推荐ID"),
    ]
    
    print("=" * 80)
    print("开始为Transaction表添加决策依据字段...")
    print("=" * 80)
    
    with db_engine.connect() as conn:
        for field_name, field_type, description in fields_to_add:
            try:
                # 检查字段是否已存在
                result = conn.execute(text(f"PRAGMA table_info(transactions)"))
                existing_fields = [row[1] for row in result]
                
                if field_name in existing_fields:
                    print(f"✅ 字段 {field_name} 已存在，跳过")
                    continue
                
                # 添加字段
                sql = f"ALTER TABLE transactions ADD COLUMN {field_name} {field_type}"
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ 成功添加字段: {field_name} ({description})")
                
            except Exception as e:
                print(f"❌ 添加字段 {field_name} 失败: {e}")
    
    print("\n✅ Transaction表字段添加完成！\n")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("数据库迁移：添加绩效跟踪字段")
    print("=" * 80 + "\n")
    
    # 1. 为Candidate表添加绩效字段
    add_candidate_performance_fields()
    
    # 2. 为Position表添加生命周期字段
    add_position_lifecycle_fields()
    
    # 3. 为Transaction表添加决策依据字段
    add_transaction_decision_fields()
    
    print("=" * 80)
    print("✅ 所有字段添加完成！")
    print("=" * 80)
    print("\n下一步：")
    print("1. 运行 python src/database/init_db.py --check 检查表结构")
    print("2. 创建自动化绩效更新脚本")
    print("3. 更新models.py中的ORM模型定义")

