#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
涨停板深度分析工具 - 增强版

功能：
1. K线形态分析（突破、回踩、加速等）
2. 技术指标分析（MACD、KDJ、成交量等）
3. 涨停逻辑分析（首板、连板、补涨、龙头等）
4. 封板强度分析（封单金额、开板次数、封板时间）
"""

from crewai.tools import tool
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _get_last_trading_day() -> str:
    """获取最近的交易日（简化版：跳过周末）"""
    from datetime import date
    today = date.today()
    days_back = 1

    # 最多回溯7天
    while days_back <= 7:
        check_date = today - timedelta(days=days_back)
        # 简化版：周一到周五是交易日
        if check_date.weekday() < 5:  # 0=周一, 4=周五
            return check_date.strftime('%Y-%m-%d')
        days_back += 1

    # 如果7天内都没有交易日，返回昨天（兜底）
    return (today - timedelta(days=1)).strftime('%Y-%m-%d')


def _analyze_kline_pattern(stock_code: str, zhitu) -> Dict[str, Any]:
    """
    分析K线形态

    Args:
        stock_code: 股票代码
        zhitu: ZhituAPI实例

    Returns:
        K线形态分析结果
    """
    try:
        # 转换股票代码格式
        symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"

        # 获取最近10天的日K线数据
        from datetime import date
        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=30)).strftime('%Y%m%d')

        kline_data = zhitu.get_history_timeframe(
            stock_symbol=symbol,
            timeframe='d',
            adjust_type='n',
            start_time=start_date,
            end_time=end_date
        )

        if not kline_data or len(kline_data) < 5:
            return {'pattern': '数据不足', 'score': 0}

        # 分析K线形态
        latest = kline_data[-1]  # 最新一天（涨停日）
        prev_1 = kline_data[-2] if len(kline_data) >= 2 else None
        prev_2 = kline_data[-3] if len(kline_data) >= 3 else None

        pattern = []
        score = 0

        # 1. 判断是否突破前高
        if prev_1 and latest['c'] > max([k['h'] for k in kline_data[:-1]]):
            pattern.append('突破前高')
            score += 3

        # 2. 判断是否缩量涨停（更强）
        if prev_1 and latest['v'] < prev_1['v'] * 0.8:
            pattern.append('缩量涨停')
            score += 2
        elif prev_1 and latest['v'] > prev_1['v'] * 1.5:
            pattern.append('放量涨停')
            score += 1

        # 3. 判断是否一字板（最强）
        if latest['o'] == latest['h'] == latest['l'] == latest['c']:
            pattern.append('一字板')
            score += 5

        # 4. 判断是否T字板（强）
        elif latest['o'] == latest['c'] and latest['l'] < latest['o']:
            pattern.append('T字板')
            score += 3

        # 5. 判断涨停前的形态
        if prev_1 and prev_2:
            # 连续上涨
            if prev_1['c'] > prev_2['c'] and latest['c'] > prev_1['c']:
                pattern.append('加速上涨')
                score += 2
            # 回踩后涨停
            elif prev_1['c'] < prev_2['c'] and latest['c'] > prev_1['c']:
                pattern.append('回踩涨停')
                score += 1

        return {
            'pattern': ' + '.join(pattern) if pattern else '普通涨停',
            'score': score,
            'close': latest['c'],
            'volume': latest['v']
        }

    except Exception as e:
        logger.warning(f"分析K线形态失败({stock_code}): {e}")
        return {'pattern': '分析失败', 'score': 0}


def _analyze_technical_indicators(stock_code: str, zhitu) -> Dict[str, Any]:
    """
    分析技术指标

    Args:
        stock_code: 股票代码
        zhitu: ZhituAPI实例

    Returns:
        技术指标分析结果
    """
    try:
        symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"

        indicators = {}
        score = 0

        # 1. MACD指标
        try:
            macd_data = zhitu.get_history_macd(symbol, 'd', 'n', latest_count=3)
            if macd_data and len(macd_data) >= 2:
                latest_macd = macd_data[-1]
                prev_macd = macd_data[-2]

                # ✅ 修复：智兔API返回的字段名是'diff'而不是'dif'
                dif = latest_macd.get('diff') or latest_macd.get('dif', 0)
                dea = latest_macd.get('dea', 0)
                macd = latest_macd.get('macd', 0)

                # 判断金叉
                prev_dif = prev_macd.get('diff') or prev_macd.get('dif', 0)
                prev_dea = prev_macd.get('dea', 0)

                if dif > dea and prev_dif <= prev_dea:
                    indicators['macd'] = 'MACD金叉'
                    score += 2
                elif dif > dea:
                    indicators['macd'] = 'MACD多头'
                    score += 1
                else:
                    indicators['macd'] = 'MACD空头'
        except Exception as e:
            logger.debug(f"获取MACD失败: {e}")
            indicators['macd'] = 'N/A'

        # 2. KDJ指标
        try:
            kdj_data = zhitu.get_history_kdj(symbol, 'd', 'n', latest_count=2)
            if kdj_data and len(kdj_data) >= 1:
                latest_kdj = kdj_data[-1]
                k = latest_kdj.get('k', 50)
                d = latest_kdj.get('d', 50)
                j = latest_kdj.get('j', 50)

                if j < 20:
                    indicators['kdj'] = 'KDJ超卖'
                    score += 2
                elif j > 80:
                    indicators['kdj'] = 'KDJ超买'
                    score -= 1
                else:
                    indicators['kdj'] = 'KDJ正常'
                    score += 1
        except Exception as e:
            logger.debug(f"获取KDJ失败: {e}")
            indicators['kdj'] = 'N/A'

        return {
            'indicators': indicators,
            'score': score
        }

    except Exception as e:
        logger.warning(f"分析技术指标失败({stock_code}): {e}")
        return {'indicators': {}, 'score': 0}


def _analyze_limit_up_logic(stock_info: Dict[str, Any], db_cache) -> Dict[str, Any]:
    """
    分析涨停逻辑

    Args:
        stock_info: 股票信息（包含连板数、封板时间等）
        db_cache: 数据库缓存

    Returns:
        涨停逻辑分析结果
    """
    try:
        stock_code = stock_info.get('stock_code')
        continuous_limit_up = stock_info.get('continuous_limit_up', 1)
        first_limit_up_time = stock_info.get('first_limit_up_time', '')
        open_count = stock_info.get('open_count', 0)

        logic = []
        score = 0

        # 1. 判断连板数
        if continuous_limit_up >= 3:
            logic.append(f'{continuous_limit_up}连板')
            score += continuous_limit_up * 2
        elif continuous_limit_up == 2:
            logic.append('2连板')
            score += 3
        else:
            logic.append('首板')
            score += 1

        # 2. 判断封板时间（越早越强）
        if first_limit_up_time:
            try:
                # 解析封板时间（格式：HH:MM:SS）
                hour = int(first_limit_up_time.split(':')[0])
                minute = int(first_limit_up_time.split(':')[1])

                if hour == 9 and minute <= 30:
                    logic.append('早盘封板')
                    score += 3
                elif hour < 11:
                    logic.append('上午封板')
                    score += 2
                elif hour < 14:
                    logic.append('午后封板')
                    score += 1
                else:
                    logic.append('尾盘封板')
                    score += 0
            except:
                pass

        # 3. 判断开板次数（越少越强）
        if open_count == 0:
            logic.append('未开板')
            score += 3
        elif open_count == 1:
            logic.append('开板1次')
            score += 1
        else:
            logic.append(f'开板{open_count}次')
            score -= 1

        # 4. 判断题材属性
        try:
            concepts = db_cache.get_stock_concepts(stock_code)
            if concepts:
                # 判断是否是热门题材
                hot_concepts = ['人工智能', '芯片', '新能源', '军工', '医药', '消费电子']
                for concept in concepts:
                    if any(hot in concept for hot in hot_concepts):
                        logic.append(f'热门题材({concept})')
                        score += 2
                        break
        except:
            pass

        return {
            'logic': ' + '.join(logic),
            'score': score,
            'continuous_limit_up': continuous_limit_up
        }

    except Exception as e:
        logger.warning(f"分析涨停逻辑失败: {e}")
        return {'logic': '分析失败', 'score': 0, 'continuous_limit_up': 1}


@tool("分析今日涨停板")
def analyze_yesterday_limit_up() -> str:
    """
    深度分析今日涨停股票（包含K线、技术指标、涨停逻辑）

    用于尾盘推荐场景（14:30-15:00）：
    - 分析今日涨停股的热点题材（哪些板块涨停多）
    - 识别强封板股票（封单资金大）
    - 分析连板股票（连板数越高越强）
    - 判断市场情绪（涨停家数多 = 情绪火热）

    Returns:
        今日涨停板深度分析结果
    """
    try:
        from src.tools.zhitu_api import ZhituAPI
        from src.utils.db_cache import DBCache
        from datetime import date

        zhitu = ZhituAPI()
        db_cache = DBCache()

        today = date.today().strftime('%Y-%m-%d')
        logger.info(f"🔍 开始深度分析今日涨停板: {today}")

        limit_up_stocks = zhitu.get_limit_up_pool(today)

        if not limit_up_stocks or len(limit_up_stocks) == 0:
            return f"今日({today})暂无涨停股票，市场情绪冷淡"

        # 统计数据
        concept_count = {}
        strong_limit_up = []
        detailed_analysis = []

        # 分析前20只涨停股票（避免API调用过多）
        for i, stock in enumerate(limit_up_stocks[:20], 1):
            stock_code = stock.get('stock_code')
            stock_name = stock.get('stock_name', '')
            seal_amount = stock.get('seal_amount', 0)

            logger.info(f"  [{i}/20] 分析 {stock_name}({stock_code})...")

            # 1. K线形态分析
            kline_result = _analyze_kline_pattern(stock_code, zhitu)

            # 2. 技术指标分析
            tech_result = _analyze_technical_indicators(stock_code, zhitu)

            # 3. 涨停逻辑分析
            logic_result = _analyze_limit_up_logic(stock, db_cache)

            # 计算综合评分
            total_score = kline_result['score'] + tech_result['score'] + logic_result['score']

            # 收集强封板股票
            if seal_amount > 100000000:
                strong_limit_up.append({
                    'code': stock_code,
                    'name': stock_name,
                    'seal_amount': seal_amount,
                    'score': total_score,
                    'kline_pattern': kline_result['pattern'],
                    'logic': logic_result['logic']
                })

            # 收集详细分析（只保留评分>5的）
            if total_score >= 5:
                detailed_analysis.append({
                    'rank': i,
                    'code': stock_code,
                    'name': stock_name,
                    'score': total_score,
                    'kline_pattern': kline_result['pattern'],
                    'macd': tech_result['indicators'].get('macd', 'N/A'),
                    'kdj': tech_result['indicators'].get('kdj', 'N/A'),
                    'logic': logic_result['logic'],
                    'continuous_limit_up': logic_result['continuous_limit_up']
                })

            # 统计题材
            try:
                concepts = db_cache.get_stock_concepts(stock_code)
                for concept in concepts:
                    if concept:
                        concept_count[concept] = concept_count.get(concept, 0) + 1
            except:
                continue

        # 排序：按综合评分降序
        detailed_analysis.sort(key=lambda x: x['score'], reverse=True)
        strong_limit_up.sort(key=lambda x: x['score'], reverse=True)

        # 生成报告
        hot_concepts = sorted(concept_count.items(), key=lambda x: x[1], reverse=True)[:5]

        result_lines = [f"=== 今日涨停板深度分析({today}) ===\n"]
        result_lines.append(f"📊 涨停股票总数: {len(limit_up_stocks)}只")
        result_lines.append(f"💪 强封板股票: {len(strong_limit_up)}只(封单>1亿)")
        result_lines.append(f"⭐ 高分股票: {len(detailed_analysis)}只(评分≥5分)\n")

        # 热点题材
        if hot_concepts:
            result_lines.append("🔥 热点题材排行:")
            for i, (concept, count) in enumerate(hot_concepts, 1):
                percentage = (count / len(limit_up_stocks[:20])) * 100
                result_lines.append(f"  {i}. {concept} ({count}只, 占比{percentage:.1f}%)")
            result_lines.append("")

        # 强封板股票（按评分排序）
        if strong_limit_up:
            result_lines.append("💎 强封板股票TOP5（按综合评分排序）:")
            for i, stock in enumerate(strong_limit_up[:5], 1):
                seal_amount_yi = stock['seal_amount'] / 100000000
                result_lines.append(
                    f"  {i}. {stock['name']}({stock['code']}) "
                    f"封单{seal_amount_yi:.2f}亿 | 评分{stock['score']}分"
                )
                result_lines.append(f"     形态: {stock['kline_pattern']}")
                result_lines.append(f"     逻辑: {stock['logic']}")
            result_lines.append("")

        # 详细技术分析TOP10
        if detailed_analysis:
            result_lines.append("📈 技术分析TOP10（综合评分≥5分）:")
            for stock in detailed_analysis[:10]:
                result_lines.append(
                    f"  {stock['rank']}. {stock['name']}({stock['code']}) "
                    f"评分{stock['score']}分"
                )
                result_lines.append(f"     K线: {stock['kline_pattern']}")
                result_lines.append(f"     指标: {stock['macd']} | {stock['kdj']}")
                result_lines.append(f"     逻辑: {stock['logic']}")
            result_lines.append("")

        # 策略建议
        result_lines.append("💡 策略建议:")
        if len(limit_up_stocks) > 50:
            result_lines.append("  - 市场情绪火热，可采用'涨停复盘战法'")
            if len(detailed_analysis) >= 5:
                result_lines.append("  - 重点关注高分股票（评分≥5分），技术形态良好")
        elif len(limit_up_stocks) > 20:
            result_lines.append("  - 市场情绪温和，可适度关注涨停题材")
            if strong_limit_up:
                result_lines.append("  - 优先关注强封板股票（封单>1亿）")
        else:
            result_lines.append("  - 市场情绪冷淡，不建议追涨停题材")
            result_lines.append("  - 建议等待市场情绪回暖")

        result = "\n".join(result_lines)
        logger.info(f"✅ 涨停板深度分析完成")

        return result

    except Exception as e:
        logger.error(f"分析最近交易日涨停板失败: {e}", exc_info=True)
        error_msg = str(e)

        if "404" in error_msg or "Not Found" in error_msg:
            return f"""
=== 涨停板分析失败 ===

⚠️ 无法获取涨停板数据（可能是周末/节假日，或API数据未更新）

建议：
- 继续使用其他市场数据（市场情绪、新闻热点）进行决策
- 策略选择优先参考复盘分析师的历史胜率
"""
        else:
            return f"分析失败: {error_msg}"


@tool("筛选涨停题材股")
def screen_limit_up_concept_stocks(concept: str) -> str:
    """
    筛选指定题材的股票

    Args:
        concept: 题材名称

    Returns:
        筛选结果
    """
    return f"'{concept}'题材筛选建议：请使用'动态筛选股票'工具进行筛选。"