#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
盘前新闻推荐工具 - CrewAI A-Stock V2.0

描述: 基于重大利好新闻，在盘前推荐涨停潜力股
核心策略：
1. 只处理critical/high级别新闻（重大利好）
2. 提取新闻相关板块
3. 从板块中筛选昨日强势龙头股
4. 推荐1-2只涨停潜力股

作者: AI Architect
版本: v1.0.0
日期: 2025-11-14
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from crewai.tools import tool

logger = logging.getLogger(__name__)


@tool("提取新闻相关板块")
def extract_sectors_from_news(news_list: List[Dict[str, Any]]) -> str:
    """
    从重大利好新闻中提取相关板块（使用AI智能识别）

    Args:
        news_list: 新闻列表，每条新闻包含title、content、urgency等字段

    Returns:
        相关板块列表（自然语言描述）
    """
    import os
    from langchain_openai import ChatOpenAI

    try:
        # 只处理critical/high级别新闻
        important_news = [
            news for news in news_list
            if news.get('urgency') in ['critical', 'high']
        ]

        if not important_news:
            return "❌ 没有重大利好新闻，无法提取板块"

        logger.info(f"📰 发现{len(important_news)}条重大利好新闻，使用AI智能识别板块...")

        # 构建新闻摘要
        news_summary = []
        for i, news in enumerate(important_news, 1):
            title = news.get('title', '')
            content = news.get('content', '')
            news_summary.append(f"{i}. {title}\n   {content[:200]}...")

        news_text = "\n\n".join(news_summary)

        # ✅ 创建独立的LLM实例（不使用全局配置，避免影响CrewAI）
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        llm = ChatOpenAI(
            model="deepseek-chat",  # ✅ 直接使用deepseek-chat，不加openai/前缀
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
            max_tokens=500,  # 板块识别不需要太多token
            timeout=30
        )

        prompt = f"""你是一个专业的股票市场分析师，请分析以下重大利好新闻，识别出相关的A股板块。

## 新闻内容
{news_text}

## 可选板块列表（仅供参考，如果新闻涉及其他板块，也可以输出）
- 新能源车（新能源汽车、电动车、充电桩、动力电池、锂电池）
- 半导体（芯片、集成电路、晶圆、光刻机、存储芯片、GPU、CPU）
- 人工智能（AI、大模型、算力、深度学习、机器学习）
- 医药（生物医药、创新药、疫苗、医疗器械、CXO）
- 军工（国防、航空航天、导弹、战斗机、战机、军售、军备、武器、军事装备、航母、舰艇）
- 光伏（太阳能、硅片、组件、逆变器）
- 风电（风力发电、海上风电、风机）
- 5G（通信、基站、光模块、6G）
- 消费电子（手机、苹果产业链、VR、AR、可穿戴设备）
- 房地产（地产、楼市、住房、房价）
- 有色金属（铜、铝、锂、钴、镍、稀土）
- 煤炭（动力煤、焦煤、焦炭）
- 石油石化（原油、天然气、化工）
- 银行（商业银行、存款、贷款、利率）
- 证券（券商、投行、资管）
- 保险（寿险、财险、保费）
- 白酒（茅台、五粮液、白酒股）
- 食品饮料（乳制品、调味品、休闲食品）
- 汽车（整车、汽车零部件）
- 家电（白色家电、黑色家电）

## 输出要求
1. 只输出板块名称，每行一个，格式：✅ 板块名称
2. 如果新闻涉及多个板块，全部输出
3. 如果新闻涉及的板块不在上述列表中，也可以输出（如：航空、旅游、教育等）
4. 板块名称要简洁明确（2-5个字）
5. 不要输出任何解释说明，只输出板块名称

## 示例输出
✅ 军工
✅ 航空航天
✅ 国防"""

        response = llm.invoke(prompt)
        ai_result = response.content.strip()

        logger.info(f"🤖 AI识别结果:\n{ai_result}")

        # 解析AI输出，提取板块名称
        matched_sectors = set()
        for line in ai_result.split('\n'):
            line = line.strip()
            if line.startswith('✅'):
                sector = line.replace('✅', '').strip()
                if sector:
                    matched_sectors.add(sector)

        if not matched_sectors:
            logger.warning("⚠️ AI未能识别出板块，尝试从原始输出中提取...")
            # 如果AI没有按格式输出，尝试直接使用输出内容
            for line in ai_result.split('\n'):
                line = line.strip()
                if line and len(line) <= 10:  # 板块名称通常不超过10个字
                    matched_sectors.add(line)

        if not matched_sectors:
            return f"❌ AI未能从新闻中识别出明确板块\n\nAI分析结果:\n{ai_result}"

        # ✅ 输出识别结果
        result_lines = [f"📊 从{len(important_news)}条重大利好新闻中识别到{len(matched_sectors)}个相关板块：\n"]

        for sector_name in matched_sectors:
            result_lines.append(f"✅ {sector_name}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"❌ 提取板块失败: {e}")
        return f"❌ 提取板块失败: {str(e)}"


@tool("筛选板块候选股")
def screen_sector_leaders(sector_name: str, min_change_pct: float = 3.0,
                          min_volume: float = 100000000,
                          max_market_cap: float = 100000000000,
                          min_market_cap: float = 5000000000,
                          max_price: float = 100.0,
                          min_price: float = 5.0,
                          top_n: int = 5) -> str:
    """
    从指定板块中筛选候选股票（返回多只，供后续深度分析）

    策略：从板块中筛选昨日强势股票，返回TOP N只候选股

    Args:
        sector_name: 板块名称（如"新能源汽车"、"半导体"）
        min_change_pct: 最小涨幅要求（默认3%）
        min_volume: 最小成交额要求（默认1亿元）
        max_market_cap: 最大流通市值（默认1000亿，过滤超大盘股）
        min_market_cap: 最小流通市值（默认50亿，过滤微盘股）
        max_price: 最高价格（默认100元，过滤高价股）
        min_price: 最低价格（默认5元，过滤低价股）
        top_n: 返回候选股数量（默认5只）

    Returns:
        候选股列表（股票代码，供后续深度分析）
    """
    from src.tools.data_source_manager import DataSourceManager
    from src.database.db_manager import get_db
    from src.database.models import StockConcepts
    from datetime import datetime, timedelta

    try:
        dsm = DataSourceManager()
        db = get_db()

        logger.info(f"📊 开始筛选板块 '{sector_name}' 的龙头股...")

        # 步骤1：从数据库查询板块相关股票
        with db.get_session() as session:
            # 使用LIKE查询，支持模糊匹配
            concept_records = session.query(StockConcepts).filter(
                StockConcepts.tag.like(f"%{sector_name}%")
            ).limit(50).all()

            if not concept_records:
                return f"❌ 数据库中未找到板块 '{sector_name}' 的相关股票"

            stock_codes = [c.stock_code for c in concept_records]
            logger.info(f"📊 板块 '{sector_name}' 找到{len(stock_codes)}只股票")

        # 步骤2：获取这些股票的昨日K线数据，筛选出强势股票
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        candidate_stocks = []  # 存储所有符合条件的股票
        filtered_by_market_cap = 0
        filtered_by_price = 0
        filtered_by_change = 0

        for stock_code in stock_codes[:50]:  # 扩大范围到50只
            try:
                stock_symbol = f"{stock_code}.{'SH' if stock_code.startswith('6') else 'SZ'}"

                # 获取昨日K线数据
                kline = dsm.zhitu_client.get_history_timeframe(
                    stock_symbol=stock_symbol,
                    timeframe='d',
                    adjust_type='n',
                    start_time=yesterday,
                    end_time=yesterday
                )

                if kline and len(kline) > 0:
                    latest = kline[-1]
                    change_pct = float(latest.get('pc', 0))
                    amount = float(latest.get('a', 0))
                    close_price = float(latest.get('c', 0))

                    # ✅ 第一步：价格过滤
                    if not (min_price <= close_price <= max_price):
                        filtered_by_price += 1
                        logger.debug(f"过滤 {stock_code}：价格{close_price:.2f}元不在范围[{min_price}, {max_price}]")
                        continue

                    # ✅ 第二步：获取流通市值
                    try:
                        import sqlite3
                        conn = sqlite3.connect('data/stock_trading.db')
                        cursor = conn.cursor()
                        cursor.execute("SELECT float_shares FROM stock_basic_info WHERE stock_code = ?", (stock_code,))
                        result = cursor.fetchone()
                        conn.close()

                        if result and result[0]:
                            float_shares = float(result[0])  # 流通股本（股）
                            market_cap = float_shares * close_price  # 流通市值（元）

                            # ✅ 市值过滤
                            if not (min_market_cap <= market_cap <= max_market_cap):
                                filtered_by_market_cap += 1
                                logger.debug(f"过滤 {stock_code}：流通市值{market_cap/100000000:.2f}亿不在范围[{min_market_cap/100000000:.0f}亿, {max_market_cap/100000000:.0f}亿]")
                                continue
                        else:
                            logger.debug(f"跳过 {stock_code}：无流通股本数据")
                            continue

                    except Exception as e:
                        logger.debug(f"获取 {stock_code} 流通股本失败: {e}")
                        continue

                    # ✅ 第三步：涨幅和成交额过滤
                    if change_pct >= min_change_pct and amount >= min_volume:
                        # ✅ 过滤异常涨幅（>20%可能是ST股票或数据错误）
                        if change_pct > 20:
                            logger.debug(f"过滤 {stock_code}：涨幅{change_pct:.2f}%异常（>20%）")
                            filtered_by_change += 1
                            continue

                        candidate_stocks.append({
                            'code': stock_code,
                            'change_pct': change_pct,
                            'amount': amount,
                            'close_price': close_price,
                            'market_cap': market_cap
                        })

            except Exception as e:
                logger.debug(f"获取 {stock_code} 数据失败: {e}")
                continue

        if not candidate_stocks:
            filter_msg = f"（昨日涨幅{min_change_pct}-20%，成交额>{min_volume/100000000}亿，价格{min_price}-{max_price}元，市值{min_market_cap/100000000:.0f}-{max_market_cap/100000000:.0f}亿）"
            logger.warning(f"⚠️ 板块 '{sector_name}' 未找到符合条件的股票，过滤统计：价格{filtered_by_price}只，市值{filtered_by_market_cap}只，异常涨幅{filtered_by_change}只")
            # ✅ 不返回错误，而是返回空列表，让调用者决定如何处理
            return f"⚠️ 板块 '{sector_name}' 中未找到符合条件的股票{filter_msg}\n📋 候选股代码："

        # 按涨幅排序，取TOP N（如果候选股不足top_n，就返回全部）
        candidate_stocks.sort(key=lambda x: x['change_pct'], reverse=True)
        actual_count = min(len(candidate_stocks), top_n)
        top_stocks = candidate_stocks[:actual_count]

        logger.info(f"📊 板块 '{sector_name}' 筛选出{len(top_stocks)}只候选股（共{len(candidate_stocks)}只符合条件，目标{top_n}只）")

        # 获取股票名称
        import sqlite3
        conn = sqlite3.connect('data/stock_trading.db')
        cursor = conn.cursor()

        result_lines = [f"📊 板块 '{sector_name}' 候选股（共{len(top_stocks)}只）\n"]
        stock_codes_list = []

        for i, stock in enumerate(top_stocks, 1):
            stock_code = stock['code']
            stock_codes_list.append(stock_code)

            # 获取股票名称
            cursor.execute("SELECT stock_name FROM stock_basic_info WHERE stock_code = ?", (stock_code,))
            result = cursor.fetchone()
            stock_name = result[0] if result else "未知"

            result_lines.append(
                f"{i}. {stock_code} {stock_name}\n"
                f"   昨日涨幅: {stock['change_pct']:.2f}% | "
                f"成交额: {stock['amount']/100000000:.2f}亿 | "
                f"收盘价: {stock['close_price']:.2f}元 | "
                f"流通市值: {stock['market_cap']/100000000:.2f}亿"
            )

        conn.close()

        result_lines.append(f"\n⚠️ 筛选条件：涨幅{min_change_pct}-20%，成交额>{min_volume/100000000}亿，价格{min_price}-{max_price}元，市值{min_market_cap/100000000:.0f}-{max_market_cap/100000000:.0f}亿")
        result_lines.append(f"📉 过滤统计：价格{filtered_by_price}只，市值{filtered_by_market_cap}只，异常涨幅{filtered_by_change}只")
        result_lines.append(f"\n💡 建议：将以上候选股交给多维分析师进行深度分析")
        result_lines.append(f"📋 候选股代码：{','.join(stock_codes_list)}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"❌ 筛选龙头股失败: {e}")
        return f"❌ 筛选龙头股失败: {str(e)}"

