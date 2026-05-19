#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
逐笔数据获取工具 - 精简版（无数据库依赖）

功能：
1. 获取当天股票逐笔交易数据（东方财富实时数据）
2. 支持代理池管理（可选）
3. 提供基础的逐笔数据分析

注意：
- 本工具仅获取当天逐笔数据
- 历史逐笔数据请使用智兔API: zhitu_api.get_tick_by_tick()

作者: AI Architect
版本: v1.0.0
日期: 2025-11-14
"""

import os
import time
import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Any
from decimal import Decimal
from loguru import logger


@dataclass
class ProxyEntry:
    """代理条目"""
    proxy: Dict[str, str]
    raw: str
    expires_at: float
    failures: int = 0


class TickDataFetcher:
    """逐笔数据获取工具（无数据库依赖）"""

    def __init__(
        self,
        enable_proxy: bool = False,
        proxy_api_url: Optional[str] = None
    ):
        """
        初始化逐笔数据获取工具

        Args:
            enable_proxy: 是否启用代理
            proxy_api_url: 代理API地址
        """
        self.enable_proxy = enable_proxy
        self.proxy_api_url = proxy_api_url or os.getenv('GIANT_IP_API_URL')
        
        # 初始化HTTP会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'http://quote.eastmoney.com/',
            'Connection': 'keep-alive'
        })
        
        self.base_url = 'http://push2.eastmoney.com/api/qt'
        self.request_timeout = 10
        self.max_retries = 5  # 从3次增加到5次（因为有时会失败）

        # 代理池管理
        self.current_proxy = None
        self.proxy_expires_at = 0

        logger.info(f"逐笔数据获取工具初始化完成 - 代理: {'启用' if enable_proxy else '禁用'}")

    def _get_proxy(self) -> Optional[Dict[str, str]]:
        """获取代理（如果启用）"""
        if not self.enable_proxy or not self.proxy_api_url:
            return None

        # 检查当前代理是否过期
        now = time.time()
        if self.current_proxy and now < self.proxy_expires_at:
            return self.current_proxy

        # 获取新代理
        try:
            logger.info("正在从巨量IP获取新代理...")
            response = requests.get(self.proxy_api_url, timeout=5)
            proxy_ip = response.text.strip()

            if proxy_ip and '.' in proxy_ip:
                protocol = os.getenv('GIANT_IP_PROTOCOL', 'http')
                proxy_dict = {
                    'http': f'{protocol}://{proxy_ip}',
                    'https': f'{protocol}://{proxy_ip}'
                }

                # 代理有效期（从环境变量读取，默认59秒）
                ttl = int(os.getenv('GIANT_IP_CACHE_TTL', '59'))
                self.current_proxy = proxy_dict
                self.proxy_expires_at = now + ttl

                logger.success(f"✅ 获取代理成功: {proxy_ip} (有效期{ttl}秒)")
                return proxy_dict
        except Exception as e:
            logger.warning(f"获取代理失败: {e}，使用直连")

        return None

    def _http_get(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """HTTP GET请求（支持代理和重试）"""
        for attempt in range(1, self.max_retries + 1):
            try:
                # 获取代理（如果启用）
                proxies = self._get_proxy()

                response = self.session.get(
                    url,
                    params=params,
                    proxies=proxies,
                    timeout=self.request_timeout
                )
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt}/{self.max_retries}): {str(e)}")

                # 代理失败时清除当前代理，下次重新获取
                if self.enable_proxy and attempt < self.max_retries:
                    self.current_proxy = None
                    self.proxy_expires_at = 0
                    logger.info("代理可能失效，将在下次尝试时获取新代理")

                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                raise e



    def get_tick_data(self, stock_code: str, trade_date: str = None) -> Optional[List[Dict]]:
        """
        获取逐笔交易数据

        Args:
            stock_code: 股票代码
            trade_date: 交易日期（YYYY-MM-DD），默认为今天

        Returns:
            逐笔交易数据列表，每条包含：
            - stock_code: 股票代码
            - trade_date: 交易日期
            - trade_time: 交易时间
            - price: 成交价格
            - volume: 成交量（手）
            - amount: 成交额（元）
            - buy_sell_type: 买卖类型（0=中性盘, 1=买入, 2=卖出）
        """
        try:
            # 判断市场代码
            if stock_code.startswith(('6', '688')):
                sec_id = f'1.{stock_code}'
            else:
                sec_id = f'0.{stock_code}'

            url = f'{self.base_url}/stock/details/get'
            params = {
                'secid': sec_id,
                'fields1': 'f1,f2,f3,f4',
                'fields2': 'f51,f52,f53,f54,f55',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'pos': '-0'
            }

            response = self._http_get(url, params=params)
            data = response.json()

            if not data.get('data') or 'details' not in data['data']:
                logger.warning(f"未找到股票 {stock_code} 的逐笔数据")
                return None

            details = data['data']['details']

            # 获取实际交易日期
            if not trade_date:
                trade_date = self._get_actual_trade_date(sec_id)

            # 解析逐笔数据
            tick_list = []
            for detail in details:
                parts = detail.split(',')
                if len(parts) >= 5:
                    time_str = parts[0]

                    # 解析买卖类型（field_4）
                    # field_4: 2=买入, 1=卖出, 4=中性盘
                    field_4 = parts[4] if len(parts) > 4 else None
                    buy_sell_type = None
                    if field_4 == '2':
                        buy_sell_type = 1  # 买入
                    elif field_4 == '1':
                        buy_sell_type = 2  # 卖出
                    elif field_4 == '4':
                        buy_sell_type = 0  # 中性盘

                    # 解析数据
                    price = float(parts[1])
                    volume_in_hands = int(parts[2])  # API返回的是手

                    # 计算金额（使用手数×100股/手）
                    amount = float(Decimal(str(price)) * Decimal(str(volume_in_hands * 100)))

                    tick = {
                        'stock_code': stock_code,
                        'trade_date': trade_date,
                        'trade_time': time_str,
                        'price': price,
                        'volume': volume_in_hands,
                        'amount': amount,
                        'buy_sell_type': buy_sell_type
                    }
                    tick_list.append(tick)

            logger.info(f"✅ 获取股票 {stock_code} 逐笔数据成功: {len(tick_list)} 条")
            return tick_list

        except Exception as e:
            logger.error(f"获取股票 {stock_code} 逐笔数据失败: {str(e)}")
            return None

    def _get_actual_trade_date(self, sec_id: str) -> str:
        """获取实际交易日期"""
        try:
            quote_url = f'{self.base_url}/stock/get'
            quote_params = {
                'secid': sec_id,
                'fields': 'f86',  # f86是交易时间戳
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }
            quote_response = self._http_get(quote_url, params=quote_params)
            quote_data = quote_response.json()

            if quote_data.get('data') and quote_data['data'].get('f86'):
                timestamp = quote_data['data']['f86']
                return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        except Exception:
            pass

        return datetime.now().strftime('%Y-%m-%d')

    def get_today_tick_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取当天逐笔数据（东方财富实时数据）

        Args:
            stock_code: 股票代码

        Returns:
            {
                'stock_code': 股票代码,
                'trade_date': 交易日期,
                'tick_data': 逐笔数据列表,
                'data_count': 数据条数
            }

        注意：
            - 仅获取当天数据
            - 历史逐笔数据请使用智兔API: zhitu_api.get_tick_by_tick()
        """
        logger.info(f"开始获取股票 {stock_code} 的当天逐笔数据...")

        # 获取今日数据
        today = datetime.now().strftime('%Y-%m-%d')
        tick_data = self.get_tick_data(stock_code, today)

        if tick_data and len(tick_data) > 0:
            logger.success(f"✅ 获取到今日 ({today}) 逐笔数据: {len(tick_data)} 条")
            return {
                'stock_code': stock_code,
                'trade_date': today,
                'tick_data': tick_data,
                'data_count': len(tick_data)
            }

        logger.warning(f"⚠️ 未找到股票 {stock_code} 的当天逐笔数据（可能非交易时间或停牌）")
        logger.info(f"💡 提示：历史逐笔数据请使用智兔API: zhitu_api.get_tick_by_tick('{stock_code}')")
        return None

    def analyze_tick_data(self, tick_data: List[Dict]) -> Dict[str, Any]:
        """
        分析逐笔数据

        Args:
            tick_data: 逐笔数据列表

        Returns:
            分析结果字典
        """
        if not tick_data:
            return {}

        total_volume = sum(t['volume'] for t in tick_data)
        total_amount = sum(t['amount'] for t in tick_data)

        buy_volume = sum(t['volume'] for t in tick_data if t.get('buy_sell_type') == 1)
        sell_volume = sum(t['volume'] for t in tick_data if t.get('buy_sell_type') == 2)
        neutral_volume = sum(t['volume'] for t in tick_data if t.get('buy_sell_type') == 0)

        buy_amount = sum(t['amount'] for t in tick_data if t.get('buy_sell_type') == 1)
        sell_amount = sum(t['amount'] for t in tick_data if t.get('buy_sell_type') == 2)

        avg_price = total_amount / (total_volume * 100) if total_volume > 0 else 0

        return {
            'total_ticks': len(tick_data),
            'total_volume': total_volume,
            'total_amount': total_amount,
            'avg_price': round(avg_price, 2),
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'neutral_volume': neutral_volume,
            'buy_amount': buy_amount,
            'sell_amount': sell_amount,
            'buy_sell_ratio': round(buy_volume / sell_volume, 2) if sell_volume > 0 else 0,
            'net_inflow': buy_amount - sell_amount
        }


# === 便捷函数 ===

def create_tick_fetcher(enable_proxy: bool = False) -> TickDataFetcher:
    """创建逐笔数据获取工具实例"""
    return TickDataFetcher(enable_proxy=enable_proxy)


def get_today_tick(stock_code: str, enable_proxy: bool = False) -> Optional[Dict[str, Any]]:
    """
    快速获取当天逐笔数据

    注意：历史逐笔数据请使用智兔API
    """
    fetcher = TickDataFetcher(enable_proxy=enable_proxy)
    return fetcher.get_today_tick_data(stock_code)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("逐笔数据获取工具测试")
    print("=" * 60)

    fetcher = TickDataFetcher(enable_proxy=False)

    # 测试获取当天逐笔数据
    result = fetcher.get_today_tick_data('600000')

    if result:
        print(f"\n股票代码: {result['stock_code']}")
        print(f"交易日期: {result['trade_date']}")
        print(f"数据条数: {result['data_count']}")

        # 分析逐笔数据
        analysis = fetcher.analyze_tick_data(result['tick_data'])
        print(f"\n逐笔数据分析:")
        print(f"  总成交量: {analysis['total_volume']} 手")
        print(f"  总成交额: {analysis['total_amount']:.2f} 元")
        print(f"  平均价格: {analysis['avg_price']:.2f} 元")
        print(f"  买入量: {analysis['buy_volume']} 手")
        print(f"  卖出量: {analysis['sell_volume']} 手")
        print(f"  买卖比: {analysis['buy_sell_ratio']}")
        print(f"  净流入: {analysis['net_inflow']:.2f} 元")
    else:
        print("未获取到当天逐笔数据")
        print("提示：历史逐笔数据请使用智兔API")

