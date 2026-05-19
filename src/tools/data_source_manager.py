#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据源管理器 - CrewAI A-Stock V2.0

描述: 统一管理智兔API、MCP Aktools、东方财富爬虫三个数据源
实现智能数据源选择、容错机制和负载均衡策略

数据源特性:
- 智兔API: 稳定可靠，接口丰富，速率限制3000次/分钟
- MCP Aktools: 专业分析，技术指标强，异步调用
- 东方财富爬虫: 实时性好，补充数据，代理池保护

作者: AI Architect
版本: v1.0.0
日期: 2025-10-30
"""

import os
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum
import json
from functools import wraps

# 导入数据源（MCP Aktools 客户端在开源版本中已移除，下面的代码会自动跳过 MCP 分支）
from .zhitu_api import ZhituAPI, create_zhitu_client
from .eastmoney_crawler import EastMoneyCrawler, create_eastmoney_crawler
create_mcp_client = None  # MCP 已移除，保留变量名以兼容下面的判断

# 配置日志
logger = logging.getLogger(__name__)

class DataSource(Enum):
    """数据源枚举"""
    ZHITU = "zhitu"
    MCP = "mcp"
    EASTMONEY = "eastmoney"

@dataclass
class DataSourceStatus:
    """数据源状态"""
    name: DataSource
    available: bool = True
    last_error: Optional[str] = None
    last_success_time: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    avg_response_time: float = 0.0
    rate_limit_remaining: int = 0
    last_check: datetime = field(default_factory=datetime.now)

@dataclass
class DataRequest:
    """数据请求"""
    method: str
    params: Dict[str, Any]
    priority: int = 1  # 1=高, 2=中, 3=低
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class DataResponse:
    """数据响应"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    source: DataSource = None
    response_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    cached: bool = False

class DataSourceManager:
    """数据源管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化数据源管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), 'data_source_config.json')
        self.config = self._load_config()

        # 初始化数据源
        self.zhitu_client: Optional[ZhituAPI] = None
        self.mcp_client = None  # MCPRouterSolutionClient类型
        self.eastmoney_crawler: Optional[EastMoneyCrawler] = None

        # 数据源状态跟踪
        self.status: Dict[DataSource, DataSourceStatus] = {
            source: DataSourceStatus(name=source) for source in DataSource
        }

        # 请求统计
        self.request_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0
        }

        # 缓存
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = self.config.get('cache_ttl', 300)  # 5分钟缓存

        # 初始化数据源客户端
        self._initialize_data_sources()

        # 配置数据源策略
        self._setup_source_strategies()

        logger.info("数据源管理器初始化完成")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            'sources': {
                'zhitu': {
                    'enabled': True,
                    'priority': 1,
                    'timeout': 30,
                    'max_retries': 3,
                    'rate_limit': 3000
                },
                'mcp': {
                    'enabled': True,
                    'priority': 2,
                    'timeout': 45,
                    'max_retries': 2,
                    'async_capable': True
                },
                'eastmoney': {
                    'enabled': True,
                    'priority': 3,
                    'timeout': 60,
                    'max_retries': 5,
                    'proxy_enabled': True
                }
            },
            'fallback_enabled': True,
            'cache_enabled': True,
            'cache_ttl': 300,
            'load_balancing': 'round_robin',
            'health_check_interval': 300
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return {**default_config, **config}
            except Exception as e:
                logger.error(f"加载数据源配置失败: {e}")

        return default_config

    def _initialize_data_sources(self):
        """初始化数据源客户端"""
        # 初始化智兔API
        if self.config['sources']['zhitu']['enabled']:
            try:
                self.zhitu_client = create_zhitu_client()
                self.status[DataSource.ZHITU].available = True
                logger.info("智兔API客户端初始化成功")
            except Exception as e:
                self.status[DataSource.ZHITU].available = False
                self.status[DataSource.ZHITU].last_error = str(e)
                logger.error(f"智兔API客户端初始化失败: {e}")

        # MCP 客户端在开源版本中已移除，此分支恒为禁用
        self.mcp_client = None
        self.status[DataSource.MCP].available = False

        # 初始化东方财富爬虫
        if self.config['sources']['eastmoney']['enabled']:
            try:
                enable_proxy = self.config['sources']['eastmoney']['proxy_enabled']
                self.eastmoney_crawler = create_eastmoney_crawler(enable_proxy=enable_proxy)
                self.status[DataSource.EASTMONEY].available = True
                logger.info("东方财富爬虫客户端初始化成功")
            except Exception as e:
                self.status[DataSource.EASTMONEY].available = False
                self.status[DataSource.EASTMONEY].last_error = str(e)
                logger.error(f"东方财富爬虫客户端初始化失败: {e}")

    def _setup_source_strategies(self):
        """设置数据源策略"""
        self.strategies = {
            'stock_info': {
                'primary': DataSource.ZHITU,
                'fallback': [DataSource.MCP, DataSource.EASTMONEY],
                'cache_key': lambda params: f"stock_info_{params.get('stock_code')}"
            },
            'realtime_quote': {
                'primary': DataSource.ZHITU,
                'fallback': [DataSource.EASTMONEY, DataSource.MCP],
                'cache_key': lambda params: f"quote_{params.get('stock_code')}_{datetime.now().strftime('%Y%m%d%H%M')}"
            },
            'historical_data': {
                'primary': DataSource.ZHITU,
                'fallback': [DataSource.MCP, DataSource.EASTMONEY],
                'cache_key': lambda params: f"hist_{params.get('stock_code')}_{params.get('start_date')}_{params.get('end_date')}"
            },
            'technical_indicators': {
                'primary': DataSource.MCP,
                'fallback': [DataSource.ZHITU, DataSource.EASTMONEY],
                'cache_key': lambda params: f"tech_{params.get('stock_code')}_{hash(str(params.get('indicators', [])))}"
            },
            'limit_up_stocks': {
                'primary': DataSource.ZHITU,
                'fallback': [DataSource.EASTMONEY],
                'cache_key': lambda params: f"limit_up_{params.get('trade_date', date.today().strftime('%Y-%m-%d'))}"
            },
            'market_overview': {
                'primary': DataSource.EASTMONEY,
                'fallback': [DataSource.ZHITU],
                'cache_key': lambda params: f"market_{datetime.now().strftime('%Y%m%d%H%M')}"
            }
        }

    def _get_cache_key(self, method: str, params: Dict[str, Any]) -> Optional[str]:
        """生成缓存键"""
        if not self.config.get('cache_enabled', True):
            return None

        strategy = self.strategies.get(method)
        if strategy and 'cache_key' in strategy:
            return strategy['cache_key'](params)
        return f"{method}_{hash(json.dumps(params, sort_keys=True))}"

    def _get_from_cache(self, cache_key: str) -> Optional[DataResponse]:
        """从缓存获取数据"""
        if cache_key and cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                self.request_stats['cache_hits'] += 1
                return DataResponse(
                    success=True,
                    data=cached_data['data'],
                    source=cached_data['source'],
                    cached=True
                )
            else:
                del self.cache[cache_key]
        return None

    def _store_in_cache(self, cache_key: str, response: DataResponse):
        """存储数据到缓存"""
        if cache_key and response.success:
            self.cache[cache_key] = {
                'data': response.data,
                'source': response.source,
                'timestamp': time.time()
            }

    def _update_source_status(self, source: DataSource, success: bool, error: str = None, response_time: float = 0):
        """更新数据源状态"""
        status = self.status[source]
        status.last_check = datetime.now()

        if success:
            status.success_count += 1
            status.last_success_time = datetime.now()
            status.failure_count = 0

            # 更新平均响应时间
            if response_time > 0:
                if status.avg_response_time == 0:
                    status.avg_response_time = response_time
                else:
                    status.avg_response_time = (status.avg_response_time + response_time) / 2
        else:
            status.failure_count += 1
            status.last_error = error

            # 连续失败过多则标记为不可用
            if status.failure_count >= 3:
                status.available = False
                logger.warning(f"数据源 {source.value} 连续失败 {status.failure_count} 次，标记为不可用")

    def _select_best_source(self, method: str, params: Dict[str, Any]) -> List[DataSource]:
        """选择最佳数据源"""
        strategy = self.strategies.get(method, {})
        primary = strategy.get('primary')
        fallback = strategy.get('fallback', [])

        # 按优先级排序可用数据源
        candidates = []
        if primary and self.status[primary].available:
            candidates.append(primary)

        for source in fallback:
            if self.status[source].available:
                candidates.append(source)

        return candidates

    async def _execute_request(self, source: DataSource, method: str, params: Dict[str, Any]) -> DataResponse:
        """执行数据请求"""
        start_time = time.time()

        try:
            if source == DataSource.ZHITU and self.zhitu_client:
                data = await self._execute_zhitu_request(method, params)
            elif source == DataSource.MCP and self.mcp_client:
                data = await self._execute_mcp_request(method, params)
            elif source == DataSource.EASTMONEY and self.eastmoney_crawler:
                data = await self._execute_eastmoney_request(method, params)
            else:
                raise ValueError(f"数据源 {source.value} 不可用")

            response_time = time.time() - start_time

            return DataResponse(
                success=True,
                data=data,
                source=source,
                response_time=response_time
            )

        except Exception as e:
            response_time = time.time() - start_time
            return DataResponse(
                success=False,
                error=str(e),
                source=source,
                response_time=response_time
            )

    async def _execute_zhitu_request(self, method: str, params: Dict[str, Any]) -> Any:
        """执行智兔API请求"""
        if method == 'stock_info':
            stock_code = params.get('stock_code')
            # 从股票列表中找到对应股票的信息
            stock_list = await asyncio.get_event_loop().run_in_executor(
                None, self.zhitu_client.get_stock_list
            )

            # 查找匹配的股票
            for stock in stock_list:
                stock_dm = stock.get('dm', '')
                stock_code_formatted = stock_code.split('.')[0]  # 去掉交易所后缀
                if stock_dm == stock_code_formatted:
                    # 转换为统一格式
                    return {
                        'stock_code': stock_dm,
                        'stock_name': stock.get('mc', stock.get('stock_name')),
                        'exchange': stock.get('jys', stock.get('exchange')),
                        'market': 'SH' if stock_dm.startswith('6') else 'SZ',
                        'data_source': 'zhitu_api'
                    }

            # 如果没找到，返回基本信息
            return {
                'stock_code': stock_code,
                'stock_name': f'股票{stock_code}',
                'market': 'SH' if stock_code.startswith('6') else 'SZ',
                'data_source': 'zhitu_api'
            }
        elif method == 'realtime_quote':
            stock_code = params.get('stock_code')

            # 并行获取两个数据源
            broker_task = asyncio.get_event_loop().run_in_executor(
                None, self.zhitu_client.get_real_time_broker, stock_code
            )
            public_task = asyncio.get_event_loop().run_in_executor(
                None, self.zhitu_client.get_real_time_public, stock_code
            )

            # 等待两个数据源都返回
            broker_data, public_data = await asyncio.gather(broker_task, public_task, return_exceptions=True)

            # 处理异常情况
            if isinstance(broker_data, Exception):
                broker_data = None
            if isinstance(public_data, Exception):
                public_data = None

            # 智能融合两个数据源
            merged_data = {}

            # 券商数据源的数据（更准确的核心字段）
            if broker_data and isinstance(broker_data, dict):
                # 券商数据源的准确字段作为主数据
                merged_data.update(broker_data)

            # 公开数据源的数据（补充字段）
            if public_data and isinstance(public_data, dict):
                # 添加公开数据源独有的字段
                for key, value in public_data.items():
                    if key not in merged_data:
                        merged_data[key] = value
                    # 如果两个数据源都有相同字段，优先使用券商数据（已在上面的update中覆盖）
                    # 这里不需要额外处理，因为券商数据已经覆盖���

            return merged_data if merged_data else (broker_data or public_data)

        elif method == 'limit_up_stocks':
            trade_date = params.get('trade_date', date.today().strftime('%Y-%m-%d'))
            return await asyncio.get_event_loop().run_in_executor(
                None, self.zhitu_client.get_limit_up_pool, trade_date
            )
        elif method == 'historical_data':
            stock_symbol = params.get('stock_code', '').replace('SH', '.SH').replace('SZ', '.SZ')
            timeframe = params.get('period', 'd')
            start_time = params.get('start_date', '').replace('-', '')
            end_time = params.get('end_date', '').replace('-', '')
            return await asyncio.get_event_loop().run_in_executor(
                None, self.zhitu_client.get_history_timeframe,
                stock_symbol, timeframe, 'n', start_time, end_time
            )
        elif method == 'technical_indicators':
            stock_symbol = params.get('stock_code', '').replace('SH', '.SH').replace('SZ', '.SZ')
            indicators = params.get('indicators', [])
            if 'MACD' in indicators:
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.zhitu_client.get_history_macd, stock_symbol, 'd', 'n', None, None, None
                )
        else:
            raise ValueError(f"不支持的智兔API方法: {method}")

    async def _execute_mcp_request(self, method: str, params: Dict[str, Any]) -> Any:
        """执行MCP请求"""
        if method == 'stock_info':
            return await self.mcp_client.get_stock_info_async(
                params.get('stock_code'), params.get('market')
            )
        elif method == 'realtime_quote':
            return await self.mcp_client.get_realtime_quote_async(
                params.get('stock_code'), params.get('fields')
            )
        elif method == 'historical_data':
            return await self.mcp_client.get_historical_data_async(
                params.get('stock_code'), params.get('start_date'), params.get('end_date'), params.get('period', 'd')
            )
        elif method == 'technical_indicators':
            return await self.mcp_client.get_technical_indicators_async(
                params.get('stock_code'), params.get('indicators', []), params.get('period', 'd')
            )
        elif method == 'stock_screening':
            return await self.mcp_client.screen_stocks_async(
                params.get('criteria', {}), params.get('market'), params.get('limit', 50)
            )
        else:
            raise ValueError(f"不支持的MCP方法: {method}")

    async def _execute_eastmoney_request(self, method: str, params: Dict[str, Any]) -> Any:
        """执行东方财富请求"""
        if method == 'realtime_quote':
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.eastmoney_crawler.crawl_single_stock, params.get('stock_code'), False
            )
            return result.data if result.success else None
        elif method == 'market_overview':
            return await asyncio.get_event_loop().run_in_executor(
                None, self.eastmoney_crawler.get_market_overview, params.get('market', 'all')
            )
        elif method == 'batch_quotes':
            stock_codes = params.get('stock_codes', [])
            results = await asyncio.get_event_loop().run_in_executor(
                None, self.eastmoney_crawler.crawl_multiple_stocks, stock_codes, False
            )
            return [r.data for r in results if r.success]
        else:
            raise ValueError(f"不支持的东方财富方法: {method}")

    async def get_data(self, method: str, params: Dict[str, Any], use_cache: bool = True) -> DataResponse:
        """
        获取数据 - 统一入口

        Args:
            method: 数据获取方法
            params: 请求参数
            use_cache: 是否使用缓存

        Returns:
            数据响应
        """
        self.request_stats['total_requests'] += 1

        # 检查缓存
        cache_key = self._get_cache_key(method, params) if use_cache else None
        if cache_key:
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                return cached_response

        # 选择数据源
        sources = self._select_best_source(method, params)
        if not sources:
            error_msg = f"没有可用的数据源获取 {method} 数据"
            logger.error(error_msg)
            self.request_stats['failed_requests'] += 1
            return DataResponse(success=False, error=error_msg)

        # 尝试各个数据源
        last_error = None
        for source in sources:
            try:
                response = await self._execute_request(source, method, params)

                if response.success:
                    self._update_source_status(source, True, response_time=response.response_time)
                    self.request_stats['successful_requests'] += 1

                    # 存储到缓存
                    if cache_key:
                        self._store_in_cache(cache_key, response)

                    return response
                else:
                    last_error = response.error
                    self._update_source_status(source, False, error=last_error, response_time=response.response_time)
                    logger.warning(f"数据源 {source.value} 获取数据失败: {last_error}")

            except Exception as e:
                last_error = str(e)
                self._update_source_status(source, False, error=last_error)
                logger.error(f"数据源 {source.value} 执行失败: {e}")

        # 所有数据源都失败
        self.request_stats['failed_requests'] += 1
        return DataResponse(success=False, error=f"所有数据源都失败，最后错误: {last_error}")

    # === 便捷方法 ===

    async def get_stock_info(self, stock_code: str) -> DataResponse:
        """获取股票基础信息"""
        return await self.get_data('stock_info', {'stock_code': stock_code})

    async def get_realtime_quote(self, stock_code: str) -> DataResponse:
        """获取实时行情"""
        return await self.get_data('realtime_quote', {'stock_code': stock_code})

    async def get_historical_data(self, stock_code: str, start_date: str, end_date: str, period: str = 'd') -> DataResponse:
        """获取历史数据"""
        return await self.get_data('historical_data', {
            'stock_code': stock_code,
            'start_date': start_date,
            'end_date': end_date,
            'period': period
        })

    async def get_technical_indicators(self, stock_code: str, indicators: List[str], period: str = 'd') -> DataResponse:
        """获取技术指标"""
        return await self.get_data('technical_indicators', {
            'stock_code': stock_code,
            'indicators': indicators,
            'period': period
        })

    async def get_limit_up_stocks(self, trade_date: str = None) -> DataResponse:
        """获取涨停股票"""
        if not trade_date:
            trade_date = date.today().strftime('%Y-%m-%d')
        return await self.get_data('limit_up_stocks', {'trade_date': trade_date})

    async def get_market_overview(self, market: str = 'all') -> DataResponse:
        """获取市场概览"""
        return await self.get_data('market_overview', {'market': market})

    async def screen_stocks(self, criteria: Dict[str, Any], market: str = None, limit: int = 50) -> DataResponse:
        """股票筛选"""
        return await self.get_data('stock_screening', {
            'criteria': criteria,
            'market': market,
            'limit': limit
        })

    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        return {
            'sources': {
                source.value: {
                    'available': status.available,
                    'success_count': status.success_count,
                    'failure_count': status.failure_count,
                    'avg_response_time': round(status.avg_response_time, 3),
                    'last_success': status.last_success_time.isoformat() if status.last_success_time else None,
                    'last_error': status.last_error
                }
                for source, status in self.status.items()
            },
            'statistics': {
                **self.request_stats,
                'success_rate': round(self.request_stats['successful_requests'] / max(self.request_stats['total_requests'], 1) * 100, 2),
                'cache_hit_rate': round(self.request_stats['cache_hits'] / max(self.request_stats['total_requests'], 1) * 100, 2)
            },
            'cache': {
                'enabled': self.config.get('cache_enabled', True),
                'ttl': self.cache_ttl,
                'size': len(self.cache)
            },
            'config': self.config
        }


# === 便捷函数 ===

def create_data_manager(config_path: str = None) -> DataSourceManager:
    """创建数据源管理器"""
    return DataSourceManager(config_path)

# 同步包装函数
def get_stock_info(stock_code: str) -> Optional[Dict[str, Any]]:
    """同步获取股票信息"""
    manager = create_data_manager()
    response = asyncio.run(manager.get_stock_info(stock_code))
    return response.data if response.success else None

def get_realtime_quote(stock_code: str) -> Optional[Dict[str, Any]]:
    """同步获取实时行情"""
    manager = create_data_manager()
    response = asyncio.run(manager.get_realtime_quote(stock_code))
    return response.data if response.success else None

def get_limit_up_stocks(trade_date: str = None) -> List[Dict[str, Any]]:
    """同步获取涨停股票"""
    manager = create_data_manager()
    response = asyncio.run(manager.get_limit_up_stocks(trade_date))
    return response.data if response.success else []


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    async def test_data_manager():
        print("=" * 60)
        print("数据源管理器测试")
        print("=" * 60)

        manager = create_data_manager()

        # 显示状态
        status = manager.get_status()
        print("数据源状态:")
        for source, info in status['sources'].items():
            print(f"  {source}: {'✓' if info['available'] else '✗'} (成功: {info['success_count']}, 失败: {info['failure_count']})")

        print(f"\n统计信息: {status['statistics']}")

        # 测试获取股票信息
        print("\n【测试1】获取股票信息")
        response = await manager.get_stock_info('600000')
        if response.success:
            print(f"数据源: {response.source.value}")
            print(f"响应时间: {response.response_time:.3f}s")
            print(f"缓存: {'是' if response.cached else '否'}")
            print(f"数据: {response.data}")
        else:
            print(f"失败: {response.error}")

        # 测试获取实时行情
        print("\n【测试2】获取实时行情")
        response = await manager.get_realtime_quote('600000')
        if response.success:
            print(f"数据源: {response.source.value}")
            print(f"响应时间: {response.response_time:.3f}s")
            print(f"数据: {response.data}")
        else:
            print(f"失败: {response.error}")

        # 测试获取涨停股票
        print("\n【测试3】获取涨停股票")
        response = await manager.get_limit_up_stocks()
        if response.success:
            print(f"数据源: {response.source.value}")
            print(f"涨停股票数量: {len(response.data) if response.data else 0}")
        else:
            print(f"失败: {response.error}")

        # 再次测试相同请求（应该使用缓存）
        print("\n【测试4】缓存测试")
        response = await manager.get_realtime_quote('600000')
        if response.success:
            print(f"数据源: {response.source.value}")
            print(f"缓存: {'是' if response.cached else '否'}")

        # 显示最终状态
        final_status = manager.get_status()
        print(f"\n最终统计: {final_status['statistics']}")

    # 运行测试
    asyncio.run(test_data_manager())