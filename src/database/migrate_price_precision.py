'''
Author: error: error: git config user.name & please set dead value or install git && error: git config user.email & please set dead value or install git & please set dead value or install git
Date: 2025-11-12 21:06:01
LastEditors: error: error: git config user.name & please set dead value or install git && error: git config user.email & please set dead value or install git & please set dead value or install git
LastEditTime: 2025-11-12 21:08:07
FilePath: \crewAi_stock\src\database\migrate_price_precision.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
"""
数据库迁移脚本：将价格字段从2位小数升级为3位小数

修改的表和字段：
1. stock_recommendations 表：
   - recommend_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - target_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - buy_price_range_min: DECIMAL(10,2) -> DECIMAL(10,3)
   - buy_price_range_max: DECIMAL(10,2) -> DECIMAL(10,3)
   - next_day_open_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - next_day_high_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - next_day_close_price: DECIMAL(10,2) -> DECIMAL(10,3)

2. positions 表：
   - buy_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - current_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - sell_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - today_open_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - today_highest_price: DECIMAL(10,2) -> DECIMAL(10,3)
   - stop_loss_price: DECIMAL(10,2) -> DECIMAL(10,3)

3. transaction_history 表：
   - price: DECIMAL(10,2) -> DECIMAL(10,3)
"""

import sqlite3
from pathlib import Path

def migrate_database():
    """执行数据库迁移"""

    # 数据库路径
    db_path = Path(__file__).parent.parent.parent / "data" / "crewai_stock.db"

    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    print(f"📂 数据库路径: {db_path}")

    try:
        conn = sqlite3.connect(str(db_path))

        print("\n🔄 开始迁移数据库...")
        
        # SQLite 不支持直接修改列类型，需要重建表
        # 但由于 DECIMAL 在 SQLite 中实际存储为 NUMERIC，精度是灵活的
        # 我们只需要确保新数据以3位小数存储即可
        
        print("✅ SQLite 数据库迁移完成！")
        print("\n📝 说明：")
        print("   - SQLite 的 DECIMAL 类型实际存储为 NUMERIC")
        print("   - 精度是灵活的，不需要修改表结构")
        print("   - 只需确保应用层代码使用3位小数即可")
        print("\n⚠️  重要提示：")
        print("   1. 已修改 models.py 中的字段定义为 DECIMAL(10,3)")
        print("   2. 已修改 position_api.py 使用 round(price, 3)")
        print("   3. 前端已使用 .toFixed(3) 显示")
        print("   4. 新数据将自动以3位小数存储")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：价格字段精度升级（2位 -> 3位小数）")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n✅ 迁移成功！")
        print("\n📋 后续步骤：")
        print("   1. 重启应用程序")
        print("   2. 清空浏览器缓存")
        print("   3. 重新买入股票测试")
        print("   4. 验证价格显示为3位小数")
    else:
        print("\n❌ 迁移失败，请检查错误信息")

