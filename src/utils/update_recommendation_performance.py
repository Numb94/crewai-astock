"""
自动化绩效更新脚本：每日盘后自动更新推荐记录的实际表现

执行方式：
    python src/utils/update_recommendation_performance.py
    
定时任务（每日17:00执行）：
    crontab -e
    0 17 * * 1-5 cd /path/to/crewAi_stock && python src/utils/update_recommendation_performance.py
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.db_manager import DatabaseManager
from src.database.models import Candidate
from src.tools.zhitu_api import ZhituAPI
from src.utils.trading_calendar import adjust_to_trading_day
from sqlalchemy import text


def update_candidate_performance(session_id: str = "default"):
    """
    更新推荐记录的实际表现

    Args:
        session_id: 用户ID，默认"default"
    """
    db = DatabaseManager()
    zhitu = ZhituAPI()
    
    print("=" * 80)
    print(f"开始更新推荐绩效 - 用户: {session_id}")
    print(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 获取所有未更新绩效的推荐记录（可卖日期 <= 今天）
    today = date.today()
    
    with db.get_session() as session:
        candidates = session.query(Candidate).filter(
            Candidate.session_id == session_id,
            Candidate.can_sell_date <= today,
            Candidate.performance_updated_at.is_(None)  # 未更新过
        ).all()
        
        if not candidates:
            print("✅ 没有需要更新的推荐记录")
            return
        
        print(f"\n找到 {len(candidates)} 条需要更新的推荐记录\n")
        
        updated_count = 0
        failed_count = 0
        
        for candidate in candidates:
            try:
                # ✅ 修复：调整可卖日期到交易日（如果是周末，向后调整到周一）
                sell_date = candidate.can_sell_date
                actual_sell_date = adjust_to_trading_day(sell_date, direction='forward')

                if actual_sell_date != sell_date:
                    print(f"📅 {candidate.stock_code} {candidate.stock_name} - "
                          f"可卖日期{sell_date}是非交易日，调整到{actual_sell_date}")

                # 获取调整后日期的K线数据
                start_date = actual_sell_date.strftime('%Y%m%d')
                end_date = (actual_sell_date + timedelta(days=5)).strftime('%Y%m%d')

                # 转换股票代码格式（600000 -> 600000.SH）
                stock_symbol = candidate.stock_code
                if stock_symbol.startswith('6'):
                    stock_symbol = f"{stock_symbol}.SH"
                elif stock_symbol.startswith(('0', '3')):
                    stock_symbol = f"{stock_symbol}.SZ"

                klines = zhitu.get_history_timeframe(
                    stock_symbol=stock_symbol,
                    timeframe='d',
                    adjust_type='n',
                    start_time=start_date,
                    end_time=end_date
                )
                
                if not klines:
                    print(f"⚠️  {candidate.stock_code} {candidate.stock_name} - 无K线数据")
                    failed_count += 1
                    continue
                
                # ✅ 修复：找到调整后交易日的数据
                day_data = None
                for kline in klines:
                    if isinstance(kline['t'], str):
                        try:
                            kline_date = datetime.strptime(kline['t'], '%Y-%m-%d %H:%M:%S').date()
                        except:
                            kline_date = datetime.strptime(kline['t'].split()[0], '%Y-%m-%d').date()
                    else:
                        kline_date = datetime.fromtimestamp(kline['t']).date()

                    # ✅ 使用调整后的交易日匹配
                    if kline_date == actual_sell_date:
                        day_data = kline
                        break

                if not day_data:
                    print(f"⚠️  {candidate.stock_code} {candidate.stock_name} - "
                          f"交易日{actual_sell_date}无数据（原可卖日期{sell_date}）")
                    failed_count += 1
                    continue
                
                # 计算收益率
                recommend_price = float(candidate.recommend_price)
                open_price = float(day_data['o'])
                high_price = float(day_data['h'])
                close_price = float(day_data['c'])
                
                open_profit_pct = ((open_price - recommend_price) / recommend_price) * 100
                high_profit_pct = ((high_price - recommend_price) / recommend_price) * 100
                close_profit_pct = ((close_price - recommend_price) / recommend_price) * 100
                
                # 判断是否冲高回落
                is_rush_high_pullback = (high_profit_pct > 0 and close_profit_pct < high_profit_pct * 0.5)
                
                # 更新数据库
                candidate.next_day_open_price = Decimal(str(round(open_price, 2)))
                candidate.next_day_high_price = Decimal(str(round(high_price, 2)))
                candidate.next_day_close_price = Decimal(str(round(close_price, 2)))
                candidate.actual_open_profit_pct = Decimal(str(round(open_profit_pct, 2)))
                candidate.actual_high_profit_pct = Decimal(str(round(high_profit_pct, 2)))
                candidate.actual_close_profit_pct = Decimal(str(round(close_profit_pct, 2)))
                candidate.is_rush_high_pullback = is_rush_high_pullback
                candidate.performance_updated_at = datetime.now()
                
                session.commit()
                
                print(f"✅ {candidate.stock_code} {candidate.stock_name} - "
                      f"开盘:{open_profit_pct:+.2f}% 最高:{high_profit_pct:+.2f}% "
                      f"收盘:{close_profit_pct:+.2f}% {'🔴冲高回落' if is_rush_high_pullback else '✅正常'}")
                
                updated_count += 1
                
            except Exception as e:
                print(f"❌ {candidate.stock_code} {candidate.stock_name} - 更新失败: {e}")
                failed_count += 1
                continue
    
    print("\n" + "=" * 80)
    print(f"✅ 更新完成！成功: {updated_count} 条，失败: {failed_count} 条")
    print("=" * 80)


if __name__ == "__main__":
    update_candidate_performance()

