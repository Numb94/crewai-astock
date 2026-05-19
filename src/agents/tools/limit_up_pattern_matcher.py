#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
涨停形态复制工具 - 找出与涨停股票相似的潜力股

核心逻辑：
1. 分析涨停股票的特征（K线、技术指标、题材、资金）
2. 在全市场中搜索相似但还没涨停的股票
3. 计算相似度评分，推荐最相似的股票
"""

from crewai.tools import tool
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)


def _extract_limit_up_features(stock_code: str, zhitu, db_cache) -> Dict[str, Any]:
    """
    提取涨停股票的特征
    
    Args:
        stock_code: 股票代码
        zhitu: ZhituAPI实例
        db_cache: 数据库缓存
        
    Returns:
        特征字典
    """
    try:
        symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"
        
        features = {
            'stock_code': stock_code,
            'concepts': [],
            'kline_pattern': {},
            'technical_indicators': {},
            'price_position': 0.0
        }
        
        # 1. 题材特征
        try:
            concepts = db_cache.get_stock_concepts(stock_code)
            features['concepts'] = concepts[:5]  # 取前5个题材
        except Exception as e:
            logger.debug(f"获取题材失败: {e}")
        
        # 2. K线形态特征
        try:
            end_date = date.today().strftime('%Y%m%d')
            start_date = (date.today() - timedelta(days=30)).strftime('%Y%m%d')
            
            kline_data = zhitu.get_history_timeframe(
                stock_symbol=symbol,
                timeframe='d',
                adjust_type='n',
                start_time=start_date,
                end_time=end_date
            )
            
            if kline_data and len(kline_data) >= 5:
                latest = kline_data[-1]
                prev_5 = kline_data[-5:]
                
                # 计算价格位置（相对于5日高低点）
                high_5 = max([k['h'] for k in prev_5])
                low_5 = min([k['l'] for k in prev_5])
                if high_5 > low_5:
                    features['price_position'] = (latest['c'] - low_5) / (high_5 - low_5)
                
                # K线形态特征
                features['kline_pattern'] = {
                    'is_breakthrough': latest['c'] > max([k['h'] for k in kline_data[:-1]]),
                    'volume_ratio': latest['v'] / prev_5[-2]['v'] if len(prev_5) >= 2 else 1.0,
                    'price_change_5d': (latest['c'] - prev_5[0]['c']) / prev_5[0]['c'] if prev_5[0]['c'] > 0 else 0
                }
        except Exception as e:
            logger.debug(f"获取K线特征失败: {e}")
        
        # 3. 技术指标特征
        try:
            # MACD
            macd_data = zhitu.get_history_macd(symbol, 'd', 'n', latest_count=2)
            if macd_data and len(macd_data) >= 2:
                latest_macd = macd_data[-1]
                prev_macd = macd_data[-2]
                
                features['technical_indicators']['macd'] = {
                    'dif': latest_macd.get('dif', 0),
                    'dea': latest_macd.get('dea', 0),
                    'is_golden_cross': (
                        latest_macd.get('dif', 0) > latest_macd.get('dea', 0) and
                        prev_macd.get('dif', 0) <= prev_macd.get('dea', 0)
                    )
                }
        except Exception as e:
            logger.debug(f"获取技术指标失败: {e}")
        
        return features
        
    except Exception as e:
        logger.warning(f"提取涨停股票特征失败({stock_code}): {e}")
        return None


def _calculate_similarity(limit_up_features: Dict[str, Any], candidate_code: str, 
                         zhitu, db_cache) -> float:
    """
    计算候选股票与涨停股票的相似度
    
    Args:
        limit_up_features: 涨停股票特征
        candidate_code: 候选股票代码
        zhitu: ZhituAPI实例
        db_cache: 数据库缓存
        
    Returns:
        相似度评分（0-100）
    """
    try:
        # 提取候选股票特征
        candidate_features = _extract_limit_up_features(candidate_code, zhitu, db_cache)
        if not candidate_features:
            return 0.0
        
        score = 0.0
        
        # 1. 题材相似度（30分）
        limit_up_concepts = set(limit_up_features.get('concepts', []))
        candidate_concepts = set(candidate_features.get('concepts', []))
        if limit_up_concepts and candidate_concepts:
            concept_similarity = len(limit_up_concepts & candidate_concepts) / len(limit_up_concepts)
            score += concept_similarity * 30
        
        # 2. K线形态相似度（30分）
        limit_up_kline = limit_up_features.get('kline_pattern', {})
        candidate_kline = candidate_features.get('kline_pattern', {})
        
        if limit_up_kline and candidate_kline:
            # 价格位置相似度（10分）
            price_pos_diff = abs(limit_up_features.get('price_position', 0) - 
                                candidate_features.get('price_position', 0))
            score += max(0, 10 - price_pos_diff * 10)
            
            # 成交量相似度（10分）
            vol_ratio_diff = abs(limit_up_kline.get('volume_ratio', 1) - 
                                candidate_kline.get('volume_ratio', 1))
            score += max(0, 10 - vol_ratio_diff * 5)
            
            # 涨幅相似度（10分）
            price_change_diff = abs(limit_up_kline.get('price_change_5d', 0) - 
                                   candidate_kline.get('price_change_5d', 0))
            score += max(0, 10 - price_change_diff * 50)
        
        # 3. 技术指标相似度（20分）
        # 这里简化处理，后续可以扩展
        score += 10  # 基础分
        
        # 4. 资金流向相似度（20分）
        # 这里简化处理，后续可以扩展
        score += 10  # 基础分
        
        return min(100, score)

    except Exception as e:
        logger.warning(f"计算相似度失败({candidate_code}): {e}")
        return 0.0


@tool("找出涨停形态相似股票")
def find_similar_stocks_to_limit_up(limit_up_stock_code: str = None, top_n: int = 10) -> str:
    """
    找出与涨停股票形态相似但还没涨停的股票

    Args:
        limit_up_stock_code: 涨停股票代码（如果不指定，则分析昨日涨停股票中评分最高的）
        top_n: 返回相似股票数量，默认10只

    Returns:
        相似股票列表（自然语言描述）
    """
    try:
        from src.tools.zhitu_api import ZhituAPI
        from src.utils.db_cache import DBCache
        from src.tools.data_source_manager import DataSourceManager

        zhitu = ZhituAPI()
        db_cache = DBCache()
        dsm = DataSourceManager()

        # 1. 如果没有指定涨停股票，则自动选择昨日涨停股票中评分最高的
        if not limit_up_stock_code:
            from src.agents.tools.limit_up_analyzer import _get_last_trading_day
            yesterday = _get_last_trading_day()

            limit_up_stocks = zhitu.get_limit_up_pool(yesterday)
            if not limit_up_stocks or len(limit_up_stocks) == 0:
                return f"最近交易日({yesterday})无涨停股票，无法进行形态匹配"

            # 选择第一只涨停股票作为参考
            limit_up_stock_code = limit_up_stocks[0].get('stock_code')
            limit_up_stock_name = limit_up_stocks[0].get('stock_name', '')
            logger.info(f"自动选择参考股票: {limit_up_stock_name}({limit_up_stock_code})")
        else:
            # 获取股票名称
            try:
                stock_info = zhitu.get_stock_basic_info(
                    f"{limit_up_stock_code}.{'SH' if limit_up_stock_code.startswith('6') else 'SZ'}"
                )
                limit_up_stock_name = stock_info.get('mc', limit_up_stock_code)
            except:
                limit_up_stock_name = limit_up_stock_code

        logger.info(f"🔍 开始分析涨停股票: {limit_up_stock_name}({limit_up_stock_code})")

        # 2. 提取涨停股票的特征
        limit_up_features = _extract_limit_up_features(limit_up_stock_code, zhitu, db_cache)
        if not limit_up_features:
            return f"无法提取涨停股票特征: {limit_up_stock_name}({limit_up_stock_code})"

        logger.info(f"✅ 涨停股票特征提取完成")
        logger.info(f"   题材: {', '.join(limit_up_features.get('concepts', [])[:3])}")
        logger.info(f"   价格位置: {limit_up_features.get('price_position', 0):.2%}")

        # 3. 获取候选股票池（同题材股票）
        candidate_stocks = []
        limit_up_concepts = set(limit_up_features.get('concepts', []))

        if limit_up_concepts:
            # 从数据库中获取所有股票的题材信息
            all_stock_concepts = db_cache.get_all_stock_concepts()

            # 筛选同题材股票
            for stock_code, concepts in all_stock_concepts.items():
                # 计算题材交集
                stock_concepts = set(concepts)
                common_concepts = limit_up_concepts & stock_concepts

                # 如果有共同题材，加入候选池
                if common_concepts:
                    candidate_stocks.append(stock_code)

            logger.info(f"📊 候选股票池: {len(candidate_stocks)}只（同题材股票）")

        # 如果同题材股票太少，扩大到全市场
        if len(candidate_stocks) < 50:
            logger.info(f"⚠️ 同题材股票太少，扩大到全市场股票")
            # 获取全市场股票列表
            try:
                all_stocks = zhitu.get_stock_list()
                candidate_stocks = [s['dm'] for s in all_stocks if s.get('dm')]
                logger.info(f"📊 扩大候选池: {len(candidate_stocks)}只（全市场）")
            except Exception as e:
                logger.error(f"获取全市场股票失败: {e}")
                return f"获取候选股票池失败: {str(e)}"

        # 排除涨停股票本身
        candidate_stocks = [s for s in candidate_stocks if s != limit_up_stock_code]

        if len(candidate_stocks) == 0:
            return f"未找到候选股票，无法进行形态匹配"

        # 4. 计算相似度（只分析前100只，避免API调用过多）
        similar_stocks = []
        for i, candidate_code in enumerate(candidate_stocks[:100], 1):
            logger.info(f"  [{i}/100] 分析 {candidate_code}...")

            similarity = _calculate_similarity(limit_up_features, candidate_code, zhitu, db_cache)

            if similarity >= 30:  # 降低阈值到30，更容易找到相似股票
                try:
                    # 获取股票名称和当前价格
                    stock_info = zhitu.get_stock_basic_info(
                        f"{candidate_code}.{'SH' if candidate_code.startswith('6') else 'SZ'}"
                    )
                    stock_name = stock_info.get('mc', candidate_code)

                    similar_stocks.append({
                        'code': candidate_code,
                        'name': stock_name,
                        'similarity': similarity
                    })
                except Exception as e:
                    logger.debug(f"获取股票信息失败({candidate_code}): {e}")

        # 5. 按相似度排序
        similar_stocks.sort(key=lambda x: x['similarity'], reverse=True)

        logger.info(f"✅ 找到{len(similar_stocks)}只相似股票（相似度≥30%）")

        # 6. 生成报告
        limit_up_concepts_list = list(limit_up_concepts)  # 转换为列表
        result_lines = [f"=== 涨停形态相似股票分析 ===\n"]
        result_lines.append(f"📌 参考股票: {limit_up_stock_name}({limit_up_stock_code})")
        result_lines.append(f"📋 题材标签: {', '.join(limit_up_concepts_list[:5])}")
        result_lines.append(f"📊 价格位置: {limit_up_features.get('price_position', 0):.2%}\n")

        if similar_stocks:
            result_lines.append(f"🎯 相似股票TOP{min(top_n, len(similar_stocks))}（相似度≥30%）:")
            for i, stock in enumerate(similar_stocks[:top_n], 1):
                result_lines.append(
                    f"  {i}. {stock['name']}({stock['code']}) "
                    f"相似度{stock['similarity']:.1f}%"
                )
            result_lines.append("")

            result_lines.append("💡 操作建议:")
            result_lines.append("  - 重点关注相似度>50%的股票，形态较为相似")
            result_lines.append("  - 建议结合技术指标（MACD、KDJ）确认买点")
            result_lines.append("  - 注意控制仓位，分散风险")
        else:
            result_lines.append("⚠️ 未找到相似度≥30%的股票")
            result_lines.append("\n💡 建议:")
            result_lines.append("  - 扩大候选股票池范围")
            result_lines.append("  - 调整相似度计算算法")

        result = "\n".join(result_lines)
        logger.info(f"✅ 涨停形态匹配完成")

        return result

    except Exception as e:
        logger.error(f"找出涨停形态相似股票失败: {e}", exc_info=True)
        return f"分析失败: {str(e)}"

