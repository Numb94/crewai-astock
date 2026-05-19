#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智兔API工具包 - CrewAI Stock V2.0

描述: 智兔API完整接口封装，包含股票数据获取、技术指标、财务数据等功能
API文档更新时间: 2025-10-21 15:07:28
套餐类型: 包年版 (每分钟3000次调用限制)
Base URL: https://api.zhituapi.cn

作者: AI Architect
版本: v1.0.0
日期: 2025-10-30
"""

import os
import time
import requests
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import logging
from urllib.parse import urljoin
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class APIEndpoint:
    """API端点配置"""
    name: str
    path: str
    method: str = "GET"
    description: str = ""
    update_frequency: str = ""
    rate_limit: str = ""
    last_update: str = "2025-10-21 15:07:28"

class ZhituAPI:
    """
    智兔API客户端

    功能特性:
    - 完整封装智兔API所有接口
    - 自动速率限制管理 (包年版: 3000次/分钟)
    - 字段映射到数据库结构
    - 错误处理和重试机制
    - 请求缓存优化
    """

    def __new__(cls, base_url: str = None, token: str = None):
        """
        若 ZHITU_API_TOKEN 未配置，自动降级到 AKShareAdapter（开源数据源，无需 token）。
        """
        actual_token = (token or os.getenv('ZHITU_API_TOKEN', '') or '').strip()
        if not actual_token or actual_token.startswith('your_'):
            from src.tools.akshare_adapter import AKShareAdapter
            logger.info("ZHITU_API_TOKEN 未配置，自动使用 AKShare 适配器（pip install akshare）")
            return AKShareAdapter()
        return super().__new__(cls)

    def __init__(self, base_url: str = None, token: str = None):
        """
        初始化智兔API客户端

        Args:
            base_url: API基础URL，默认从环境变量获取
            token: API Token，默认从环境变量获取
        """
        self.base_url = base_url or os.getenv('ZHITU_API_BASE_URL', 'https://api.zhituapi.cn')
        self.token = token or os.getenv('ZHITU_API_TOKEN')

        if not self.token:
            # 不会走到这里 — __new__ 已经做了降级
            raise ValueError("智兔API Token未配置，请设置ZHITU_API_TOKEN环境变量")

        # 速率限制管理 (包年版: 3000次/分钟)
        self.rate_limit_per_minute = 3000
        self.request_times = []

        # 请求会话（优化连接池配置）
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CrewAI-Stock/2.0.0',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })

        # 配置连接池适配器（优化连接性能）
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # 重试策略：连接错误重试3次
        retry_strategy = Retry(
            total=3,
            connect=3,
            read=2,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=0.5
        )

        adapter = HTTPAdapter(
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,      # 最大连接数
            max_retries=retry_strategy,
            pool_block=False
        )

        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # API端点配置
        self._setup_endpoints()

        logger.debug(f"智兔API客户端初始化完成 - Base URL: {self.base_url}, 套餐: 包年版(3000次/分钟)")

    def _setup_endpoints(self):
        """设置API端点配置"""
        self.endpoints = {
            # === 基础数据接口 ===
            'stock_list': APIEndpoint(
                name="股票列表",
                path="/hs/list/all",
                description="获取基础的股票代码和名称",
                update_frequency="每日16:20",
                rate_limit="包年版1分钟3千次"
            ),

            # === 股池数据接口 ===
            'limit_up_pool': APIEndpoint(
                name="涨停股池",
                path="/hs/pool/ztgc",
                description="获取每日涨停股票列表",
                update_frequency="交易时间段每10分钟",
                rate_limit="包年版1分钟3千次"
            ),

            'limit_down_pool': APIEndpoint(
                name="跌停股池",
                path="/hs/pool/dtgc",
                description="获取每日跌停股票列表",
                update_frequency="交易时间段每10分钟",
                rate_limit="包年版1分钟3千次"
            ),

            'strong_stock_pool': APIEndpoint(
                name="强势股池",
                path="/hs/pool/qsgc",
                description="获取每日强势股票列表",
                update_frequency="交易时间段每10分钟",
                rate_limit="包年版1分钟3千次"
            ),

            # === 实时交易数据接口 ===
            'real_time_public': APIEndpoint(
                name="实时交易(公开数据源)",
                path="/hs/real/ssjy",
                description="获取实时交易数据(公开数据源)",
                update_frequency="交易时间段每1分钟",
                rate_limit="包年版1分钟3千次"
            ),

            'tick_by_tick': APIEndpoint(
                name="当天逐笔交易",
                path="/hs/real/zbjy",
                description="获取当天逐笔交易数据",
                update_frequency="每日21:00",
                rate_limit="包年版1分钟3千次"
            ),

            'real_time_all_public': APIEndpoint(
                name="实时交易(全部|公开数据)",
                path="/hs/public/realall",
                description="一次性获取所有股票的实时交易数据",
                update_frequency="交易时间段每1分钟",
                rate_limit="包年版1分钟1次"
            ),

            'real_time_multi_public': APIEndpoint(
                name="实时交易(多选|公开数据)",
                path="/hs/public/ssjymore",
                description="获取指定不超过20支股票的实时交易数据",
                update_frequency="交易时间段每1分钟",
                rate_limit="包年版1分钟3千次"
            ),

            'real_time_broker': APIEndpoint(
                name="实时交易(券商数据源)",
                path="/hs/real/time",
                description="获取实时交易数据(券商数据源)",
                update_frequency="实时",
                rate_limit="包年版1分钟3千次"
            ),

            'five_level_quotes': APIEndpoint(
                name="买卖五档盘口",
                path="/hs/real/five",
                description="获取实时买卖五档盘口数据",
                update_frequency="实时",
                rate_limit="包年版1分钟3千次"
            ),

            'real_time_all_broker': APIEndpoint(
                name="实时交易(全部|券商数据)",
                path="/hs/custom/realall",
                description="一次性获取所有股票的实时交易数据(券商数据)",
                update_frequency="实时",
                rate_limit="每分钟1次"
            ),

            'real_time_multi_broker': APIEndpoint(
                name="实时交易(多选|券商数据)",
                path="/hs/custom/ssjymore",
                description="获取指定不超过20支股票的实时交易数据(券商数据)",
                update_frequency="实时",
                rate_limit="包年版1分钟3千次"
            ),

            # === 历史数据接口 ===
            'fund_flow': APIEndpoint(
                name="资金流向数据",
                path="/hs/history/transaction",
                description="获取资金流向数据",
                update_frequency="每日21:30更新",
                rate_limit="包年版1分钟3千次"
            ),

            'latest_timeframe': APIEndpoint(
                name="最新分时交易",
                path="/hs/latest",
                description="获取最新分时交易数据",
                update_frequency="实时",
                rate_limit="包年版1分钟3千次"
            ),

            'history_timeframe': APIEndpoint(
                name="历史分时交易",
                path="/hs/history",
                description="获取历史分时交易数据",
                update_frequency="分钟级别盘中更新",
                rate_limit="包年版1分钟3千次"
            ),

            'history_stop_price': APIEndpoint(
                name="历史涨跌停价格",
                path="/hs/stopprice/history",
                description="获取历史涨跌停价格",
                update_frequency="每日0点",
                rate_limit="包年版1分钟3千次"
            ),

            # === 基础信息接口 ===
            'stock_basic_info': APIEndpoint(
                name="股票基础信息",
                path="/hs/instrument",
                description="获取股票的基础信息",
                update_frequency="每日1点",
                rate_limit="包年版1分钟3千次"
            ),

            # === 技术指标接口 ===
            'history_macd': APIEndpoint(
                name="历史分时MACD",
                path="/hs/history/macd",
                description="获取历史MACD数据",
                update_frequency="分钟级别盘中更新",
                rate_limit="包年版1分钟3千次"
            ),

            'history_ma': APIEndpoint(
                name="历史分时MA",
                path="/hs/history/ma",
                description="获取历史MA数据",
                update_frequency="分钟级别盘中更新",
                rate_limit="包年版1分钟3千次"
            ),

            'history_boll': APIEndpoint(
                name="历史分时BOLL",
                path="/hs/history/boll",
                description="获取历史BOLL数据",
                update_frequency="分钟级别盘中更新",
                rate_limit="包年版1分钟3千次"
            ),

            'history_kdj': APIEndpoint(
                name="历史分时KDJ",
                path="/hs/history/kdj",
                description="获取历史KDJ数据",
                update_frequency="分钟级别盘中更新",
                rate_limit="包年版1分钟3千次"
            ),

            # === 财务数据接口 ===
            'balance_sheet': APIEndpoint(
                name="资产负债表",
                path="/hs/fin/balance",
                description="获取资产负债表",
                update_frequency="每日0点",
                rate_limit="包年版1分钟3千次"
            ),
            'financial_ratios': APIEndpoint(
                name="财务主要指标",
                path="/hs/fin/ratios",
                description="获取财务主要指标",
                update_frequency="每日0点",
                rate_limit="包年版1分钟3千次"
            ),
            'financial_indicators': APIEndpoint(
                name="财务指标",
                path="/hs/gs/cwzb",
                description="获取上市公司近四个季度的主要财务指标",
                update_frequency="每日03:30",
                rate_limit="包年版1分钟3千次"
            ),

            'stock_sectors': APIEndpoint(
                name="所属板块",
                path="/hs/gs/ssbk",
                description="获取股票所属板块（行业、概念、地域）",
                update_frequency="每日21:00",
                rate_limit="包年版1分钟3千次"
            )
        }

    def _check_rate_limit(self):
        """检查速率限制"""
        current_time = time.time()

        # 清理1分钟前的请求记录
        self.request_times = [t for t in self.request_times if current_time - t < 60]

        # 检查是否超过限制
        if len(self.request_times) >= self.rate_limit_per_minute:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                logger.warning(f"达到速率限制，等待 {wait_time:.1f} 秒")
                time.sleep(wait_time)
                # 清理过期记录
                self.request_times = []

        # 记录当前请求
        self.request_times.append(current_time)

    def _make_request(self, endpoint_key: str, path_param: str = None, query_param: str = None, **params) -> Dict[str, Any]:
        """
        发起API请求

        Args:
            endpoint_key: 端点键名
            path_param: 路径参数（用于涨停股池等接口）
            query_param: 查询参数（用于技术指标等接口）
            **params: 请求参数

        Returns:
            API响应数据
        """
        if endpoint_key not in self.endpoints:
            raise ValueError(f"未知的API端点: {endpoint_key}")

        endpoint = self.endpoints[endpoint_key]

        # 检查速率限制
        self._check_rate_limit()

        # 构建请求URL
        if path_param:
            # 对于需要路径参数的接口，如涨停股池
            url = f"{self.base_url}{endpoint.path}/{path_param}"
        elif query_param:
            # 对于需要查询参数的接口，如技术指标、历史分时交易
            url = f"{self.base_url}{endpoint.path}/{query_param}"
        else:
            # 对于普通接口
            url = urljoin(self.base_url, endpoint.path)

        # 添加token参数
        params['token'] = self.token

        try:
            logger.debug(f"请求API: {endpoint.name} - {url}")

            # 分离连接超时和读取超时：(连接超时, 读取超时)
            # 连接超时5秒，读取超时30秒
            response = self.session.get(url, params=params, timeout=(5, 30))
            response.raise_for_status()

            data = response.json()

            logger.debug(f"API响应成功: {endpoint.name} - 数据量: {len(data) if isinstance(data, list) else 'object'}")
            return data

        except requests.exceptions.ConnectTimeout as e:
            logger.error(f"API连接超时: {endpoint.name} - {str(e)}")
            raise
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"API读取超时: {endpoint.name} - {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {endpoint.name} - {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API处理失败: {endpoint.name} - {str(e)}")
            raise

    def _make_request_with_url(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        使用自定义URL发起API请求

        Args:
            url: 完整的API URL
            params: 请求参数（已包含token）

        Returns:
            API响应数据
        """
        # 检查速率限制
        self._check_rate_limit()

        try:
            logger.debug(f"请求API: {url}")

            # 分离连接超时和读取超时：(连接超时, 读取超时)
            # 连接超时5秒，读取超时30秒
            response = self.session.get(url, params=params, timeout=(5, 30))
            response.raise_for_status()

            data = response.json()

            logger.debug(f"API响应成功 - 数据量: {len(data) if isinstance(data, list) else 'object'}")
            return data

        except requests.exceptions.ConnectTimeout as e:
            logger.error(f"API连接超时: {url} - {str(e)}")
            raise
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"API读取超时: {url} - {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API处理失败: {url} - {str(e)}")
            raise

    def _map_to_database_fields(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """
        将API数据映射到数据库字段

        Args:
            data: API原始数据
            data_type: 数据类型

        Returns:
            映射后的数据
        """
        mapped_data = {}

        if data_type == 'stock_basic':
            # 股票基础信息映射
            field_mapping = {
                'dm': 'stock_code',
                'mc': 'stock_name',
                'jys': 'exchange'
            }

        elif data_type == 'real_time_data':
            # 实时交易数据映射 - 根据实际API返回结构调整
            field_mapping = {
                'p': 'current_price',
                'pc': 'change_pct',  # 涨跌幅百分比
                'cje': 'turnover_amount',
                'lt': 'float_market_cap',
                'zsz': 'total_market_cap',
                'hs': 'turnover_rate',
                'pe': 'pe_ratio',
                'v': 'volume',
                'h': 'high_price',
                'l': 'low_price',
                'o': 'open_price',
                'yc': 'pre_close_price',
                'zf': 'change_percent',  # 涨跌幅
                't': 'update_time'
            }

        elif data_type == 'limit_up':
            # 涨停股池数据映射
            field_mapping = {
                'dm': 'stock_code',
                'mc': 'stock_name',
                'p': 'price',
                'zf': 'change_pct',
                'cje': 'turnover_amount',
                'lt': 'float_market_cap',
                'zsz': 'total_market_cap',
                'hs': 'turnover_rate',
                'lbc': 'consecutive_limit_up',
                'fbt': 'first_limit_time',
                'lbt': 'last_limit_time',
                'zj': 'limit_up_funds',
                'tj': 'limit_up_stats'
            }

        else:
            # 默认不进行映射
            return data

        # 执行字段映射
        for api_field, db_field in field_mapping.items():
            if api_field in data:
                mapped_data[db_field] = data[api_field]

        # 添加未映射的字段
        for field, value in data.items():
            if field not in field_mapping:
                mapped_data[field] = value

        return mapped_data

    # === 基础数据接口 ===

    def get_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表

        Returns:
            股票代码和名称列表
            字段: dm(股票代码), mc(股票名称), jys(交易所)
        """
        data = self._make_request('stock_list')
        return [self._map_to_database_fields(item, 'stock_basic') for item in data]

    # === 股池数据接口 ===

    def get_limit_up_pool(self, trade_date: str) -> List[Dict[str, Any]]:
        """
        获取涨停股池

        Args:
            trade_date: 交易日期，格式yyyy-MM-dd

        Returns:
            涨停股票列表，按封板时间升序
        """
        data = self._make_request('limit_up_pool', trade_date)
        return [self._map_to_database_fields(item, 'limit_up') for item in data]

    def get_limit_down_pool(self, trade_date: str) -> List[Dict[str, Any]]:
        """
        获取跌停股池

        Args:
            trade_date: 交易日期，格式yyyy-MM-dd

        Returns:
            跌停股票列表，按封单资金升序
        """
        data = self._make_request('limit_down_pool', trade_date)
        return data

    def get_strong_stock_pool(self, trade_date: str) -> List[Dict[str, Any]]:
        """
        获取强势股池

        Args:
            trade_date: 交易日期，格式yyyy-MM-dd

        Returns:
            强势股票列表，按涨幅倒序
        """
        data = self._make_request('strong_stock_pool', trade_date)
        return data

    # === 实时交易数据接口 ===

    def get_real_time_public(self, stock_code: str) -> Dict[str, Any]:
        """
        获取实时交易数据(公开数据源)

        Args:
            stock_code: 股票代码

        Returns:
            实时交易数据
        """
        data = self._make_request('real_time_public', stock_code)
        return self._map_to_database_fields(data, 'real_time_data')

    def get_tick_by_tick(self, stock_code: str) -> List[Dict[str, Any]]:
        """
        获取当天逐笔交易数据

        Args:
            stock_code: 股票代码

        Returns:
            逐笔交易数据，按时间倒序
            字段: d(日期), t(时间), v(成交量), p(成交价), ts(交易方向)
        """
        data = self._make_request('tick_by_tick', stock_code)
        return data

    def get_real_time_all_public(self) -> List[Dict[str, Any]]:
        """
        获取所有股票的实时交易数据(公开数据)

        注意: 此接口仅限至尊版和包年版，每分钟限制1次

        Returns:
            所有股票的实时交易数据
        """
        data = self._make_request('real_time_all_public')
        return [self._map_to_database_fields(item, 'real_time_data') for item in data]

    def get_real_time_multi_public(self, stock_codes: List[str]) -> List[Dict[str, Any]]:
        """
        获取指定股票的实时交易数据(公开数据)

        Args:
            stock_codes: 股票代码列表，不超过20支

        Returns:
            指定股票的实时交易数据
        """
        if len(stock_codes) > 20:
            raise ValueError("股票代码数量不能超过20支")

        codes_str = ','.join(stock_codes)
        data = self._make_request('real_time_multi_public', stock_codes=codes_str)
        return [self._map_to_database_fields(item, 'real_time_data') for item in data]

    def get_real_time_broker(self, stock_code: str) -> Dict[str, Any]:
        """
        获取实时交易数据(券商数据源)

        Args:
            stock_code: 股票代码

        Returns:
            实时交易数据(券商数据源)
        """
        data = self._make_request('real_time_broker', stock_code)
        return self._map_to_database_fields(data, 'real_time_data')

    def get_five_level_quotes(self, stock_code: str) -> Dict[str, Any]:
        """
        获取买卖五档盘口数据

        Args:
            stock_code: 股票代码

        Returns:
            五档盘口数据
            字段: ps(委卖价), pb(委买价), vs(委卖量), vb(委买量), t(更新时间)
        """
        data = self._make_request('five_level_quotes', stock_code)
        return data

    def get_real_time_all_broker(self) -> List[Dict[str, Any]]:
        """
        获取所有股票的实时交易数据(券商数据)

        注意: 此接口每分钟限制1次

        Returns:
            所有股票的实时交易数据(券商数据)
        """
        data = self._make_request('real_time_all_broker')
        return [self._map_to_database_fields(item, 'real_time_data') for item in data]

    def get_real_time_multi_broker(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        获取指定股票的实时交易数据(券商数据)

        Args:
            stock_codes: 股票代码列表，不超过20支

        Returns:
            字典，key为股票代码，value为实时数据
            例如: {'000892': {'p': 7.85, 'zd': 0.05, ...}, ...}
        """
        if len(stock_codes) > 20:
            raise ValueError("股票代码数量不能超过20支")

        codes_str = ','.join(stock_codes)
        data = self._make_request('real_time_multi_broker', stock_codes=codes_str)

        # 转换为字典格式，方便查询
        result = {}
        for item in data:
            mapped_item = self._map_to_database_fields(item, 'real_time_data')
            stock_code = mapped_item.get('dm')  # 股票代码
            if stock_code:
                result[stock_code] = mapped_item

        return result

    # === 历史数据接口 ===

    def get_fund_flow(self, stock_code: str, start_time: str = None,
                     end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        """
        获取资金流向数据

        Args:
            stock_code: 股票代码
            start_time: 开始时间，格式YYYYMMDD
            end_time: 结束时间，格式YYYYMMDD
            latest_count: 最新条数

        Returns:
            资金流向数据
        """
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time
        if latest_count:
            params['lt'] = latest_count

        data = self._make_request('fund_flow', stock_code, **params)
        return data

    def get_latest_timeframe(self, stock_symbol: str, timeframe: str = 'd',
                           adjust_type: str = 'n', limit: int = None) -> List[Dict[str, Any]]:
        """
        获取最新分时交易数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            limit: 最新条数

        Returns:
            最新分时交易数据，交易时间升序
            字段: t(时间), o/h/l/c(开高低收), v(成交量), a(成交额), pc(前收盘价), sf(停牌)
        """
        query_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if limit:
            params['lt'] = limit  # 参数名是lt，不是limit

        data = self._make_request('latest_timeframe', query_param=query_param, **params)
        return data

    def get_history_timeframe(self, stock_symbol: str, timeframe: str = 'd',
                            adjust_type: str = 'n', start_time: str = None,
                            end_time: str = None) -> List[Dict[str, Any]]:
        """
        获取历史分时交易数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            start_time: 开始时间，格式YYYYMMDD或YYYYMMDDhhmmss
            end_time: 结束时间，格式YYYYMMDD或YYYYMMDDhhmmss

        Returns:
            历史分时交易数据，交易时间升序
        """
        query_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time

        data = self._make_request('history_timeframe', query_param=query_param, **params)
        return data

    def get_history_stop_price(self, stock_symbol: str, start_time: str = None,
                             end_time: str = None) -> List[Dict[str, Any]]:
        """
        获取历史涨跌停价格

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            start_time: 开始时间，格式YYYYMMDD
            end_time: 结束时间，格式YYYYMMDD

        Returns:
            历史涨跌停价格
            字段: t(交易日期), h(涨停价格), l(跌停价格)
        """
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time

        data = self._make_request('history_stop_price', query_param=stock_symbol, **params)
        return data

    # === 基础信息接口 ===

    def get_stock_basic_info(self, stock_symbol: str) -> Dict[str, Any]:
        """
        获取股票基础信息

        Args:
            stock_symbol: 股票符号，格式如000001.SZ

        Returns:
            股票基础信息
            字段: ei(市场代码), ii(股票代码), name(名称), od(上市日期),
                  pc(前收盘价), up(涨停价), dp(跌停价), fv(流通股本),
                  tv(总股本), pk(最小变动单位), is(停牌状态)
        """
        data = self._make_request('stock_basic_info', query_param=stock_symbol)
        return data

    # === 技术指标接口 ===

    def get_history_macd(self, stock_symbol: str, timeframe: str = 'd',
                        adjust_type: str = 'n', start_time: str = None,
                        end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        """
        获取历史MACD数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            start_time: 开始时间
            end_time: 结束时间
            latest_count: 最新条数

        Returns:
            MACD数据
            字段: t(时间), diff, dea, macd, ema12, ema26
        """
        # 直接将路径参数传递给 _make_request，避免URL编码问题
        path_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time
        if latest_count:
            params['lt'] = latest_count

        data = self._make_request('history_macd', path_param=path_param, **params)
        return data

    def get_history_ma(self, stock_symbol: str, timeframe: str = 'd',
                      adjust_type: str = 'n', start_time: str = None,
                      end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        """
        获取历史MA数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            start_time: 开始时间
            end_time: 结束时间
            latest_count: 最新条数

        Returns:
            MA数据
            字段: t(时间), ma3/5/10/15/20/30/60/120/200/250
        """
        # 直接将路径参数传递给 _make_request，避免URL编码问题
        path_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time
        if latest_count:
            params['lt'] = latest_count

        data = self._make_request('history_ma', path_param=path_param, **params)
        return data

    def get_history_boll(self, stock_symbol: str, timeframe: str = 'd',
                        adjust_type: str = 'n', start_time: str = None,
                        end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        """
        获取历史BOLL数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            start_time: 开始时间
            end_time: 结束时间
            latest_count: 最新条数

        Returns:
            BOLL数据
            字段: t(时间), u(上轨), d(下轨), m(中轨)
        """
        # 直接将路径参数传递给 _make_request，避免URL编码问题
        path_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time
        if latest_count:
            params['lt'] = latest_count

        data = self._make_request('history_boll', path_param=path_param, **params)
        return data

    def get_history_kdj(self, stock_symbol: str, timeframe: str = 'd',
                       adjust_type: str = 'n', start_time: str = None,
                       end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        """
        获取历史KDJ数据

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            timeframe: 分时级别，5/15/30/60/d/w/m/y
            adjust_type: 除权方式，n/f/b/fr/br
            start_time: 开始时间
            end_time: 结束时间
            latest_count: 最新条数

        Returns:
            KDJ数据
            字段: t(时间), k(K值), d(D值), j(J值)
        """
        # 直接将路径参数传递给 _make_request，避免URL编码问题
        path_param = f"{stock_symbol}/{timeframe}/{adjust_type}"
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time
        if latest_count:
            params['lt'] = latest_count

        data = self._make_request('history_kdj', path_param=path_param, **params)
        return data

    # === 财务数据接口 ===

    def get_balance_sheet(self, stock_symbol: str, start_time: str = None,
                         end_time: str = None) -> List[Dict[str, Any]]:
        """
        获取资产负债表

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            start_time: 开始时间，格式YYYYMMDD
            end_time: 结束时间，格式YYYYMMDD

        Returns:
            资产负债表数据
            字段: jzrq(截止日期), plrq(披露日期), 以及各项财务指标
        """
        # 直接将路径参数传递给 _make_request，避免URL编码问题
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time

        data = self._make_request('balance_sheet', path_param=stock_symbol, **params)
        return data

    def get_financial_ratios(self, stock_symbol: str, start_time: str = None,
                            end_time: str = None) -> List[Dict[str, Any]]:
        """
        获取财务主要指标

        Args:
            stock_symbol: 股票符号，格式如000001.SZ
            start_time: 开始时间，格式YYYYMMDD
            end_time: 结束时间，格式YYYYMMDD

        Returns:
            财务主要指标数据
        """
        params = {}
        if start_time:
            params['st'] = start_time
        if end_time:
            params['et'] = end_time

        data = self._make_request('financial_ratios', path_param=stock_symbol, **params)
        return data

    def get_financial_indicators(self, stock_code: str) -> List[Dict[str, Any]]:
        """
        获取财务指标（近四个季度）

        Args:
            stock_code: 股票代码，如000001

        Returns:
            财务指标数据
        """
        data = self._make_request('financial_indicators', path_param=stock_code)
        return data

    def get_stock_basic_info(self, stock_symbol: str) -> Dict[str, Any]:
        """
        获取股票基础信息

        Args:
            stock_symbol: 股票符号，格式如000001.SZ

        Returns:
            股票基础信息，包含行业、上市日期等
        """
        data = self._make_request('stock_basic_info', path_param=stock_symbol)
        return data

    # === 工具方法 ===

    def get_api_info(self) -> Dict[str, Any]:
        """
        获取API信息

        Returns:
            API配置和状态信息
        """
        return {
            'base_url': self.base_url,
            'plan_type': '包年版',
            'rate_limit_per_minute': self.rate_limit_per_minute,
            'total_endpoints': len(self.endpoints),
            'last_update': '2025-10-21 15:07:28',
            'endpoints': {
                key: {
                    'name': ep.name,
                    'description': ep.description,
                    'update_frequency': ep.update_frequency,
                    'rate_limit': ep.rate_limit
                }
                for key, ep in self.endpoints.items()
            }
        }

    def format_stock_symbol(self, stock_code: str, exchange: str = None) -> str:
        """
        格式化股票符号

        Args:
            stock_code: 股票代码
            exchange: 交易所，sh/sz

        Returns:
            格式化的股票符号，如000001.SZ
        """
        if '.' in stock_code:
            return stock_code

        if exchange is None:
            if stock_code.startswith(('000', '001', '002', '003', '300')):
                exchange = 'SZ'
            elif stock_code.startswith(('600', '601', '603', '605', '688')):
                exchange = 'SH'
            else:
                raise ValueError(f"无法确定股票代码 {stock_code} 的交易所")

        return f"{stock_code}.{exchange}"

    def validate_trade_date(self, trade_date: str) -> bool:
        """
        验证交易日期格式

        Args:
            trade_date: 交易日期，格式yyyy-MM-dd

        Returns:
            是否有效
        """
        try:
            datetime.strptime(trade_date, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    def validate_time_format(self, time_str: str, format_type: str = 'date') -> bool:
        """
        验证时间格式

        Args:
            time_str: 时间字符串
            format_type: 格式类型，date/datetime

        Returns:
            是否有效
        """
        try:
            if format_type == 'date':
                datetime.strptime(time_str, '%Y%m%d')
            elif format_type == 'datetime':
                datetime.strptime(time_str, '%Y%m%d%H%M%S')
            return True
        except ValueError:
            return False

    def get_stock_sectors(self, stock_code: str) -> List[Dict[str, Any]]:
        """
        获取股票所属板块（行业、概念、地域）

        Args:
            stock_code: 股票代码（如000001）

        Returns:
            板块信息列表
            [
                {"keyword": "行业", "content": "电子信息 半导体 芯片"},
                {"keyword": "概念", "content": "人工智能 ChatGPT 算力"},
                {"keyword": "地域", "content": "深圳 广东"}
            ]
        """
        data = self._make_request('stock_sectors', path_param=stock_code)
        return data

    # ==================== 指数数据接口 ====================

    def get_index_list(self) -> List[Dict[str, Any]]:
        """
        获取沪深主要指数列表

        API端点: /hz/list/hszs

        Returns:
            指数列表
            [
                {"dm": "000001.SH", "mc": "上证指数"},
                {"dm": "399001.SZ", "mc": "深证成指"},
                {"dm": "399006.SZ", "mc": "创业板指"}
            ]
        """
        endpoint = f"{self.base_url}/hz/list/hszs?token={self.token}"

        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data
            else:
                logger.warning(f"指数列表返回格式异常: {data}")
                return []

        except Exception as e:
            logger.error(f"获取指数列表失败: {e}")
            return []

    def get_index_realtime(self, index_code: str) -> Dict[str, Any]:
        """
        获取指数实时交易数据

        API端点: /hz/real/ssjy/{index_code}

        Args:
            index_code: 指数代码，如 000001.SH（上证指数）、399001.SZ（深证成指）、399006.SZ（创业板指）

        Returns:
            指数实时数据
            {
                "p": 3200.50,      # 当前价格
                "o": 3180.20,      # 开盘价
                "h": 3210.80,      # 最高价
                "l": 3175.30,      # 最低价
                "zs": 3190.40,     # 昨收价
                "cje": 350000000000,  # 成交额（元）
                "cjl": 280000000,     # 成交量（手）
                "zf": 0.32,        # 涨幅（%）
                "zd": 10.10,       # 涨跌（元）
                "amplitude": 1.12  # 振幅（%）
            }
        """
        endpoint = f"{self.base_url}/hz/real/ssjy/{index_code}?token={self.token}"

        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                return data
            else:
                logger.warning(f"指数实时数据返回格式异常: {data}")
                return {}

        except Exception as e:
            logger.error(f"获取指数实时数据失败 ({index_code}): {e}")
            return {}

    def get_index_kline(self, index_code: str, period: str = "d", limit: int = 60) -> List[Dict[str, Any]]:
        """
        获取指数历史K线数据

        API端点: /hz/history/fsjy/{index_code}/{period}

        Args:
            index_code: 指数代码，如 000001.SH（上证指数）
            period: K线周期
                - "5": 5分钟
                - "15": 15分钟
                - "30": 30分钟
                - "60": 60分钟
                - "d": 日线（默认）
                - "w": 周线
                - "m": 月线
            limit: 返回数据条数，默认60条

        Returns:
            K线数据列表（按时间倒序）
            [
                {
                    "t": "2025-11-18",  # 时间
                    "o": 3180.20,       # 开盘价
                    "h": 3210.80,       # 最高价
                    "l": 3175.30,       # 最低价
                    "c": 3200.50,       # 收盘价
                    "v": 280000000,     # 成交量（手）
                    "a": 350000000000,  # 成交额（元）
                    "zs": 3190.40       # 昨收价
                }
            ]
        """
        endpoint = f"{self.base_url}/hz/history/fsjy/{index_code}/{period}?token={self.token}&lt={limit}"

        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                # 智兔API可能忽略lt参数，返回所有历史数据
                # 在客户端手动截取前N条数据（按时间倒序，最新的在前面）
                return data[:limit] if len(data) > limit else data
            else:
                logger.warning(f"指数K线数据返回格式异常: {data}")
                return []

        except Exception as e:
            logger.error(f"获取指数K线数据失败 ({index_code}, {period}): {e}")
            return []

    def close(self):
        """关闭API客户端"""
        self.session.close()
        logger.info("智兔API客户端已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# === 便捷函数 ===

def create_zhitu_client() -> ZhituAPI:
    """
    创建智兔API客户端的便捷函数

    Returns:
        智兔API客户端实例
    """
    return ZhituAPI()

def get_stock_basic_data(stock_code: str) -> Dict[str, Any]:
    """
    获取股票基础数据的便捷函数

    Args:
        stock_code: 股票代码

    Returns:
        股票基础数据
    """
    with ZhituAPI() as client:
        return client.get_real_time_public(stock_code)

def get_limit_up_stocks(trade_date: str = None) -> List[Dict[str, Any]]:
    """
    获取涨停股票的便捷函数

    Args:
        trade_date: 交易日期，默认为今日

    Returns:
        涨停股票列表
    """
    if trade_date is None:
        trade_date = date.today().strftime('%Y-%m-%d')

    with ZhituAPI() as client:
        return client.get_limit_up_pool(trade_date)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    with ZhituAPI() as client:
        # 测试获取股票列表
        print("=== 获取股票列表 ===")
        stocks = client.get_stock_list()
        print(f"获取到 {len(stocks)} 支股票")
        if stocks:
            print(f"示例股票: {stocks[0]}")

        # 测试获取涨停股池
        today = date.today().strftime('%Y-%m-%d')
        print(f"\n=== 获取今日涨停股池 ({today}) ===")
        try:
            limit_up_stocks = client.get_limit_up_pool(today)
            print(f"今日涨停股票数量: {len(limit_up_stocks)}")
            if limit_up_stocks:
                print(f"示例涨停股票: {limit_up_stocks[0]}")
        except Exception as e:
            print(f"获取涨停股池失败: {e}")

        # 测试获取实时数据
        if stocks:
            test_stock = stocks[0]['stock_code']
            print(f"\n=== 获取 {test_stock} 实时数据 ===")
            try:
                real_time_data = client.get_real_time_public(test_stock)
                print(f"实时数据: {real_time_data}")
            except Exception as e:
                print(f"获取实时数据失败: {e}")

        # 显示API信息
        print(f"\n=== API信息 ===")
        api_info = client.get_api_info()
        print(f"套餐类型: {api_info['plan_type']}")
        print(f"速率限制: {api_info['rate_limit_per_minute']} 次/分钟")
        print(f"接口数量: {api_info['total_endpoints']}")