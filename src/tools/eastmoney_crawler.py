#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
东方财富爬虫工具包 - CrewAI Stock V2.0

描述: 东方财富股票数据爬虫，集成巨量代理池机制
作为三个数据源之一，主要提供实时行情和补充数据

特性:
- 集成巨量IP代理池防止封禁
- 智能并发控制和速率限制
- 数据库自动存储和索引
- 异常处理和自动重试
- 数据标准化和字段映射

作者: AI Architect
版本: v2.0.0
日期: 2025-10-30
"""

import os
import json
import time
import sqlite3
import threading
import asyncio
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple, Any, Set, Union
import requests
import logging

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class ProxyEntry:
    """代理条目"""
    proxy: Dict[str, str]
    raw: str
    expires_at: float
    failures: int = 0

@dataclass
class CrawlResult:
    """爬取结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    stock_code: str = ""
    duration: float = 0.0
    proxy_used: str = ""

class GiantIPProxyManager:
    """巨量IP代理池管理器"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        protocol: str = 'http',
        cache_ttl: float = 15.0,
        max_failures: int = 2,
        static_proxies: Optional[List[str]] = None,
        fetch_timeout: int = 8,
        max_pool_size: int = 5,
    ) -> None:
        self.api_url = api_url or os.getenv('GIANT_IP_API_URL')
        self.protocol = protocol
        self.cache_ttl = cache_ttl
        self.max_failures = max_failures
        self.fetch_timeout = fetch_timeout
        self.max_pool_size = max(1, max_pool_size)
        self._pool: deque[ProxyEntry] = deque()
        self._static_pool: deque[str] = deque(static_proxies or [])
        self._lock = threading.Lock()

    @staticmethod
    def _normalize_proxy(raw: str, protocol: str) -> Dict[str, str]:
        """标准化代理格式"""
        if raw.startswith('http://') or raw.startswith('https://'):
            proxy_url = raw
        else:
            proxy_url = f'{protocol}://{raw}'

        if 'https://' in proxy_url or protocol == 'https':
            https_proxy = proxy_url.replace('http://', 'https://')
        else:
            https_proxy = proxy_url

        return {'http': proxy_url, 'https': https_proxy}

    @staticmethod
    def _parse_expire_time(expire_str: Optional[str]) -> Optional[float]:
        """解析过期时间"""
        if not expire_str:
            return None
        patterns = [
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
        ]
        for pattern in patterns:
            try:
                dt = datetime.strptime(expire_str, pattern)
                return dt.timestamp()
            except ValueError:
                continue
        return None

    def _parse_json_payload(self, payload: Any) -> List[Tuple[str, float]]:
        """解析JSON载荷"""
        items: List[Any] = []
        if isinstance(payload, dict):
            for key in ('data', 'rows', 'proxies', 'list'):
                value = payload.get(key)
                if value:
                    if isinstance(value, list):
                        items.extend(value)
                    elif isinstance(value, dict):
                        items.append(value)
            if not items:
                items.append(payload)
        elif isinstance(payload, list):
            items = payload

        proxies: List[Tuple[str, float]] = []
        now = time.time()
        for item in items:
            if not isinstance(item, dict):
                continue
            ip = item.get('ip') or item.get('IP') or item.get('host')
            port = item.get('port') or item.get('Port') or item.get('port_value')
            if not ip or not port:
                continue
            raw = f'{ip}:{port}'
            expire_str = (
                item.get('expire_time')
                or item.get('expire')
                or item.get('expireAt')
                or item.get('expire_at')
            )
            expire_at = self._parse_expire_time(expire_str)
            if not expire_at:
                expire_at = now + self.cache_ttl
            proxies.append((raw, expire_at))
        return proxies

    def _parse_plain_payload(self, text: str) -> List[Tuple[str, float]]:
        """解析文本载荷"""
        now = time.time()
        proxies: List[Tuple[str, float]] = []
        for line in text.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if '://' in raw and raw.split('://', 1)[0] not in ('http', 'https'):
                continue
            if raw.startswith('#'):
                continue
            proxies.append((raw, now + self.cache_ttl))
        return proxies

    def _fetch_one_locked(self, reason: str = '') -> int:
        """获取一个代理"""
        if not self.api_url:
            return 0
        try:
            response = requests.get(self.api_url, timeout=self.fetch_timeout)
            response.raise_for_status()
            content = response.text.strip()
            try:
                payload = response.json()
                proxies = self._parse_json_payload(payload)
            except ValueError:
                proxies = self._parse_plain_payload(content)

            existing = {entry.raw for entry in self._pool}
            added = 0
            for raw, expire_at in proxies:
                if raw in existing:
                    continue
                entry = ProxyEntry(
                    proxy=self._normalize_proxy(raw, self.protocol),
                    raw=raw,
                    expires_at=expire_at,
                )
                self._pool.append(entry)
                logger.info(f"从巨量IP获取代理: {raw}（原因: {reason}）")
                added += 1
                break
            if added == 0:
                logger.warning(f"巨量IP接口未返回新代理（{reason}）")
            return added
        except Exception as exc:
            logger.error(f"获取巨量IP代理失败：{exc}（{reason}）")
            return 0

    def _ensure_pool_locked(self, reason: str = '') -> None:
        """确保代理池不为空"""
        while len(self._pool) < self.max_pool_size:
            added = self._fetch_one_locked(reason)
            if added == 0:
                break

    def _prune_expired_locked(self) -> None:
        """清理过期代理"""
        now = time.time()
        refreshed = deque()
        removed = False
        while self._pool:
            entry = self._pool.popleft()
            if entry.expires_at and entry.expires_at < now:
                logger.info(f"代理 {entry.raw} 已过期，移除")
                removed = True
                continue
            refreshed.append(entry)
        self._pool = refreshed
        if removed:
            self._ensure_pool_locked('expired replacement')

    def acquire(self) -> Optional[ProxyEntry]:
        """获取一个代理"""
        with self._lock:
            self._prune_expired_locked()
            if not self._pool:
                self._ensure_pool_locked('pool empty')
            if not self._pool and self._static_pool:
                raw = self._static_pool[0]
                self._static_pool.rotate(-1)
                expires_at = time.time() + (self.cache_ttl * 10)
                return ProxyEntry(
                    proxy=self._normalize_proxy(raw, self.protocol),
                    raw=raw,
                    expires_at=expires_at,
                )
            if not self._pool:
                return None

            entry = self._pool[0]
            self._pool.rotate(-1)
            return entry

    def report_failure(self, entry: ProxyEntry, reason: str = '') -> None:
        """报告代理失败"""
        with self._lock:
            logger.warning(f"代理 {entry.raw} 请求失败：{reason}")
            try:
                self._pool.remove(entry)
            except ValueError:
                pass
            self._ensure_pool_locked('failure replacement')

    def report_success(self, entry: ProxyEntry) -> None:
        """报告代理成功"""
        entry.failures = 0

    @property
    def enabled(self) -> bool:
        """是否启用代理"""
        return bool(self.api_url or self._static_pool)

class EastMoneyCrawler:
    """东方财富爬虫工具"""

    def __init__(
        self,
        db_path: str = None,
        enable_proxy: bool = None,
        config_path: str = None,
    ):
        """
        初始化爬虫

        Args:
            db_path: 数据库路径
            enable_proxy: 是否启用代理
            config_path: 配置文件路径
        """
        self.db_path = db_path or os.getenv('DATABASE_PATH', 'data/stock_trading.db')
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), 'crawler_config.json')

        # 加载配置
        self.settings = self._load_settings()

        # 初始化请求会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'http://quote.eastmoney.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })

        # 基础配置
        self.base_url = 'http://push2.eastmoney.com/api/qt'
        self.request_timeout = float(self.settings.get('REQUEST_TIMEOUT', 10))
        self.max_retries = int(self.settings.get('CRAWLER_MAX_RETRIES', 3))
        self.retry_delay = float(self.settings.get('CRAWLER_RETRY_DELAY', 0.5))
        self.retry_backoff = float(self.settings.get('CRAWLER_RETRY_BACKOFF', 1.5))
        self.default_delay = float(self.settings.get('CRAWLER_DELAY_SECONDS', 0.5))
        self.proxy_delay = float(self.settings.get('CRAWLER_PROXY_DELAY', 0.05))

        # 代理配置 - 默认禁用代理，因为代理池连接有问题
        config_proxy_flag = self._to_bool(self.settings.get('CRAWLER_USE_PROXY', False), default=False)
        self.proxy_enabled = config_proxy_flag if enable_proxy is None else enable_proxy

        # 检查代理配置有效性，如果代理服务不可用则自动禁用
        if self.proxy_enabled:
            if not self._test_proxy_availability():
                logger.warning("代理服务不可用，自动禁用代理模式")
                self.proxy_enabled = False
            else:
                self.proxy_manager = self._build_proxy_manager()
        else:
            self.proxy_manager = None

        # 并发配置
        self.batch_size = int(self.settings.get('CRAWLER_BATCH_SIZE', 100))
        self.worker_count = int(self.settings.get('CRAWLER_WORKERS', 5))
        self.fail_threshold = int(self.settings.get('CRAWLER_FAIL_THRESHOLD', 5))
        self.item_retry_limit = int(self.settings.get('CRAWLER_ITEM_RETRIES', 3))

        # 数据库配置
        self.db_timeout = float(self.settings.get('CRAWLER_DB_TIMEOUT', 30))

        # 状态管理
        self.consecutive_failures = 0
        self._thread_local = threading.local()

        # 初始化数据库
        self._init_database()

        logger.info(f"东方财富爬虫初始化完成 - 代理: {'启用' if self.proxy_enabled else '禁用'}")

    def _load_settings(self) -> Dict[str, Any]:
        """加载配置设置"""
        settings: Dict[str, Any] = {}

        # 加载配置文件
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(key, str) and not key.startswith('_'):
                            settings[key.upper()] = value
            except Exception as exc:
                logger.error(f"加载配置文件 {self.config_path} 失败: {exc}")

        # 环境变量覆盖
        setting_keys = {
            'REQUEST_TIMEOUT', 'CRAWLER_MAX_RETRIES', 'CRAWLER_RETRY_DELAY',
            'CRAWLER_RETRY_BACKOFF', 'CRAWLER_DELAY_SECONDS', 'CRAWLER_PROXY_DELAY',
            'CRAWLER_PROXY_POOL_SIZE', 'CRAWLER_PROXY_EXPIRY_SECONDS',
            'CRAWLER_FAIL_THRESHOLD', 'CRAWLER_DB_TIMEOUT', 'CRAWLER_BATCH_SIZE',
            'CRAWLER_WORKERS', 'CRAWLER_ITEM_RETRIES', 'GIANT_IP_API_URL',
            'GIANT_IP_STATIC_PROXIES', 'GIANT_IP_PROTOCOL', 'GIANT_IP_CACHE_TTL',
            'GIANT_IP_MAX_FAILURES', 'GIANT_IP_FETCH_TIMEOUT', 'CRAWLER_USE_PROXY'
        }

        for key in setting_keys:
            env_value = os.getenv(key)
            if env_value is not None:
                settings[key] = env_value

        return settings

    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        """转换为布尔值"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if not text:
                return default
            if text in {'1', 'true', 'yes', 'y', 'on'}:
                return True
            if text in {'0', 'false', 'no', 'n', 'off'}:
                return False
            try:
                return bool(int(text))
            except ValueError:
                return default
        return default

    def _test_proxy_availability(self) -> bool:
        """测试代理服务可用性"""
        api_url = self.settings.get('GIANT_IP_API_URL')
        if not api_url:
            logger.info("未配置代理API URL，跳过代理测试")
            return False

        try:
            # 快速测试代理API是否可访问
            test_url = api_url.split('?')[0] if '?' in api_url else api_url
            response = requests.get(test_url, timeout=3)
            if response.status_code == 200:
                logger.info("代理服务可用")
                return True
            else:
                logger.warning(f"代理服务返回状态码: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"代理服务不可用: {e}")
            return False

    def _build_proxy_manager(self) -> Optional[GiantIPProxyManager]:
        """构建代理管理器"""
        api_url = self.settings.get('GIANT_IP_API_URL')
        static_proxies = self.settings.get('GIANT_IP_STATIC_PROXIES', [])

        if isinstance(static_proxies, str):
            static_list = [item.strip() for item in static_proxies.split(',') if item.strip()]
        elif isinstance(static_proxies, (list, tuple, set)):
            static_list = [str(item).strip() for item in static_proxies if str(item).strip()]
        else:
            static_list = []

        if not api_url and not static_list:
            return None

        protocol = str(self.settings.get('GIANT_IP_PROTOCOL', 'http')).lower() or 'http'
        cache_ttl = float(self.settings.get('GIANT_IP_CACHE_TTL', 59))
        max_failures = int(self.settings.get('GIANT_IP_MAX_FAILURES', 2))
        fetch_timeout = int(self.settings.get('GIANT_IP_FETCH_TIMEOUT', 8))
        max_pool_size = int(self.settings.get('CRAWLER_PROXY_POOL_SIZE', 5))

        manager = GiantIPProxyManager(
            api_url=api_url,
            protocol=protocol,
            cache_ttl=cache_ttl,
            max_failures=max_failures,
            static_proxies=static_list,
            fetch_timeout=fetch_timeout,
            max_pool_size=max_pool_size,
        )

        return manager if manager.enabled else None

    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path, timeout=self.db_timeout) as conn:
            conn.execute('PRAGMA busy_timeout = 30000')
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()

            # 创建股票行情表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS eastmoney_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    trade_date DATE NOT NULL,
                    current_price REAL,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    prev_close REAL,
                    change_amount REAL,
                    change_percent REAL,
                    volume REAL,
                    turnover REAL,
                    amplitude REAL,
                    turnover_rate REAL,
                    pe_ratio REAL,
                    pb_ratio REAL,
                    market_value REAL,
                    circulating_market_value REAL,
                    volume_ratio REAL,
                    data_source TEXT DEFAULT 'eastmoney',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(stock_code, trade_date, data_source)
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_em_quotes_code ON eastmoney_quotes(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_em_quotes_date ON eastmoney_quotes(trade_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_em_quotes_source ON eastmoney_quotes(data_source)')

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=self.db_timeout)
        conn.execute(f'PRAGMA busy_timeout = {int(self.db_timeout * 1000)}')
        return conn

    def _http_get(self, url: str, params: Optional[Dict[str, Any]] = None,
                  use_proxy: bool = True, timeout: Optional[float] = None) -> requests.Response:
        """HTTP GET请求"""
        last_error: Optional[Exception] = None
        require_proxy = use_proxy and self.proxy_enabled

        if require_proxy and not self.proxy_manager:
            raise RuntimeError('启用了代理模式，但代理池未初始化')

        for attempt in range(1, self.max_retries + 1):
            entry: Optional[ProxyEntry] = None
            proxies: Optional[Dict[str, str]] = None

            try:
                if require_proxy:
                    entry = self.proxy_manager.acquire()
                    if not entry:
                        raise RuntimeError('无法获取代理IP')
                    proxies = entry.proxy

                response = self.session.get(
                    url,
                    params=params,
                    timeout=timeout or self.request_timeout,
                    proxies=proxies,
                )
                response.raise_for_status()

                if entry and self.proxy_manager:
                    self.proxy_manager.report_success(entry)

                return response

            except Exception as exc:
                last_error = exc
                if entry and self.proxy_manager:
                    self.proxy_manager.report_failure(entry, str(exc))

                if attempt < self.max_retries:
                    sleep_seconds = self.retry_delay * (self.retry_backoff ** (attempt - 1))
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                    continue

        raise last_error or RuntimeError('HTTP请求失败')

    def get_stock_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票行情数据

        Args:
            stock_code: 股票代码

        Returns:
            行情数据字典
        """
        try:
            # 确定市场代码
            if stock_code.startswith(('6', '68')):
                sec_id = f'1.{stock_code}'
            else:
                sec_id = f'0.{stock_code}'

            url = f'{self.base_url}/stock/get'
            params = {
                'secid': sec_id,
                'fields': 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f86,f107,f116,f117,f162,f167,f168,f169,f170,f171',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }

            response = self._http_get(url, params=params)
            data = response.json()

            if not data.get('data'):
                logger.warning(f"未找到股票 {stock_code} 的数据")
                return None

            stock_data = data['data']

            # 解析数据
            trade_timestamp = stock_data.get('f86')
            if trade_timestamp:
                trade_date = datetime.fromtimestamp(trade_timestamp).strftime('%Y-%m-%d')
            else:
                trade_date = datetime.now().strftime('%Y-%m-%d')

            current_price = stock_data.get('f43', 0) / 100 if stock_data.get('f43') else None
            prev_close = stock_data.get('f60', 0) / 100 if stock_data.get('f60') else None

            change_amount = stock_data.get('f169', 0) / 100 if stock_data.get('f169') else None
            change_percent = stock_data.get('f170', 0) / 100 if stock_data.get('f170') else None

            if change_amount is None and current_price is not None and prev_close is not None and prev_close != 0:
                change_amount = round(current_price - prev_close, 2)
            if change_percent is None and current_price is not None and prev_close is not None and prev_close != 0:
                change_percent = round((current_price - prev_close) / prev_close * 100, 2)

            return {
                'stock_code': stock_code,
                'stock_name': stock_data.get('f58', ''),
                'trade_date': trade_date,
                'current_price': current_price,
                'open_price': stock_data.get('f46', 0) / 100 if stock_data.get('f46') else None,
                'high_price': stock_data.get('f44', 0) / 100 if stock_data.get('f44') else None,
                'low_price': stock_data.get('f45', 0) / 100 if stock_data.get('f45') else None,
                'prev_close': prev_close,
                'change_amount': change_amount,
                'change_percent': change_percent,
                'volume': stock_data.get('f47', 0) if stock_data.get('f47') else None,
                'turnover': stock_data.get('f48', 0) if stock_data.get('f48') else None,
                'amplitude': stock_data.get('f171', 0) / 100 if stock_data.get('f171') else None,
                'turnover_rate': stock_data.get('f168', 0) / 100 if stock_data.get('f168') else None,
                'volume_ratio': stock_data.get('f50', 0) / 100 if stock_data.get('f50') else None,
                'pe_ratio': stock_data.get('f162', 0) / 100 if stock_data.get('f162') else None,
                'pb_ratio': stock_data.get('f167', 0) / 100 if stock_data.get('f167') else None,
                'market_value': stock_data.get('f116', 0) if stock_data.get('f116') else None,
                'circulating_market_value': stock_data.get('f117', 0) if stock_data.get('f117') else None,
                'data_source': 'eastmoney'
            }

        except Exception as e:
            logger.error(f"获取股票 {stock_code} 行情失败: {str(e)}")
            return None

    def save_quote_to_db(self, quote: Dict[str, Any]) -> bool:
        """
        保存行情数据到数据库

        Args:
            quote: 行情数据

        Returns:
            是否成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO eastmoney_quotes (
                        stock_code, stock_name, trade_date, current_price, open_price,
                        high_price, low_price, prev_close, change_amount, change_percent,
                        volume, turnover, amplitude, turnover_rate, volume_ratio,
                        pe_ratio, pb_ratio, market_value, circulating_market_value,
                        data_source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                ''', (
                    quote['stock_code'], quote['stock_name'], quote['trade_date'],
                    quote['current_price'], quote['open_price'], quote['high_price'],
                    quote['low_price'], quote['prev_close'], quote['change_amount'],
                    quote['change_percent'], quote['volume'], quote['turnover'],
                    quote['amplitude'], quote['turnover_rate'], quote['volume_ratio'],
                    quote['pe_ratio'], quote['pb_ratio'], quote['market_value'],
                    quote['circulating_market_value'], quote['data_source']
                ))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"保存行情数据失败: {str(e)}")
            return False

    def crawl_single_stock(self, stock_code: str, save_to_db: bool = True) -> CrawlResult:
        """
        爬取单只股票数据

        Args:
            stock_code: 股票代码
            save_to_db: 是否保存到数据库

        Returns:
            爬取结果
        """
        start_time = time.time()

        try:
            quote = self.get_stock_quote(stock_code)

            if quote and save_to_db:
                self.save_quote_to_db(quote)

            duration = time.time() - start_time

            return CrawlResult(
                success=True,
                data=quote,
                stock_code=stock_code,
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            return CrawlResult(
                success=False,
                error=str(e),
                stock_code=stock_code,
                duration=duration
            )

    def crawl_multiple_stocks(self, stock_codes: List[str], save_to_db: bool = True,
                             delay: Optional[float] = None) -> List[CrawlResult]:
        """
        批量爬取股票数据

        Args:
            stock_codes: 股票代码列表
            save_to_db: 是否保存到数据库
            delay: 请求间隔

        Returns:
            爬取结果列表
        """
        if not stock_codes:
            return []

        total = len(stock_codes)
        logger.info(f"开始批量爬取 {total} 只股票数据")

        effective_delay = self.default_delay if delay is None else delay
        if delay is None and self.proxy_manager:
            effective_delay = self.proxy_delay

        results: List[CrawlResult] = []
        success_count = 0
        fail_count = 0
        consecutive_failures = 0

        def fetch_quote(stock_code: str) -> CrawlResult:
            return self.crawl_single_stock(stock_code, save_to_db=False)

        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            # 分批处理
            for batch_start in range(0, total, self.batch_size):
                batch = stock_codes[batch_start:batch_start + self.batch_size]

                futures = {executor.submit(fetch_quote, code): code for code in batch}

                for future in as_completed(futures):
                    result = future.result()

                    if result.success:
                        success_count += 1
                        consecutive_failures = 0
                        if save_to_db and result.data:
                            self.save_quote_to_db(result.data)
                        logger.info(f"成功: {result.stock_code}")
                    else:
                        fail_count += 1
                        consecutive_failures += 1
                        logger.error(f"失败: {result.stock_code} - {result.error}")

                        if consecutive_failures >= self.fail_threshold:
                            logger.error(f"连续失败 {consecutive_failures} 次，停止爬取")
                            # 取消剩余任务
                            for f in futures:
                                f.cancel()
                            break

                    results.append(result)

                    # 控制请求频率
                    if effective_delay > 0:
                        time.sleep(effective_delay)

                # 检查是否需要停止
                if consecutive_failures >= self.fail_threshold:
                    break

        logger.info(f"批量爬取完成 - 成功: {success_count}, 失败: {fail_count}")
        return results

    def get_all_stocks_realtime(self, market: str = 'all') -> Optional[List[Dict[str, Any]]]:
        """
        获取所有股票的实时行情数据（包括换手率）

        Args:
            market: 市场类型 (sh/sz/all)

        Returns:
            所有股票的实时行情列表，每只股票包含：
            - f12: 股票代码
            - f14: 股票名称
            - f2: 最新价
            - f3: 涨跌幅(%)
            - f4: 涨跌额
            - f5: 成交量(手)
            - f6: 成交额(元)
            - f8: 换手率(%)
            - f7: 振幅(%)
            - f15: 最高价
            - f16: 最低价
            - f17: 今开
            - f18: 昨收
        """
        try:
            # 使用正确的API端点 - 沪深指数行情
            url = 'http://push2.eastmoney.com/api/qt/ulist.np/get'

            # 根据市场类型构造不同的股票过滤器
            if market == 'sh':
                # 上海A股
                fs = 'm:1 t:2,m:1 t:23'
            elif market == 'sz':
                # 深圳A股
                fs = 'm:0 t:6,m:0 t:80'
            else:
                # 全部A股 (默认)
                fs = 'm:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048'

            params = {
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'pn': '1',
                'pz': '5000',
                'po': '1',
                'np': '1',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'fs': fs,
                'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152'
            }

            response = self._http_get(url, params=params)

            if response.status_code == 404:
                logger.error("市场概览API端点不存在(404)")
                return None

            data = response.json()

            if not data.get('data') or not data['data'].get('diff'):
                logger.warning(f"市场概览数据为空: {data}")
                return None

            stocks = data['data']['diff']

            if not stocks:
                return None

            # ✅ 返回所有股票的详细数据
            logger.success(f"✅ 成功获取{len(stocks)}只股票的实时行情（包括换手率）")
            return stocks

        except Exception as e:
            logger.error(f"获取所有股票实时行情失败: {str(e)}")
            return None

    def get_market_overview(self, market: str = 'all') -> Optional[Dict[str, Any]]:
        """
        获取市场概览统计数据

        Args:
            market: 市场类型 (sh/sz/all)

        Returns:
            市场概览统计数据
        """
        try:
            # ✅ 复用get_all_stocks_realtime方法
            stocks = self.get_all_stocks_realtime(market)

            if not stocks:
                return None

            # 统计市场数据
            total_stocks = len(stocks)
            up_count = sum(1 for s in stocks if s.get('f3', 0) > 0)
            down_count = sum(1 for s in stocks if s.get('f3', 0) < 0)
            flat_count = total_stocks - up_count - down_count

            limit_up_count = sum(1 for s in stocks if s.get('f3', 0) >= 9.8)
            limit_down_count = sum(1 for s in stocks if s.get('f3', 0) <= -9.8)

            # 计算平均涨跌幅
            avg_change_percent = sum(s.get('f3', 0) for s in stocks) / total_stocks if total_stocks > 0 else 0

            return {
                'market': market,
                'total_stocks': total_stocks,
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'limit_up_count': limit_up_count,
                'limit_down_count': limit_down_count,
                'up_ratio': round(up_count / total_stocks * 100, 2) if total_stocks > 0 else 0,
                'down_ratio': round(down_count / total_stocks * 100, 2) if total_stocks > 0 else 0,
                'avg_change_percent': round(avg_change_percent, 2),
                'timestamp': datetime.now().isoformat(),
                'data_source': 'eastmoney'
            }

        except Exception as e:
            logger.error(f"获取市场概览失败: {str(e)}")
            # 如果主API失败，尝试备用方案
            try:
                return self._get_market_overview_fallback(market)
            except Exception as fallback_error:
                logger.error(f"备用市场概览API也失败: {str(fallback_error)}")
                return None

    def _get_market_overview_fallback(self, market: str = 'all') -> Optional[Dict[str, Any]]:
        """
        获取市场概览的备用方案 - 使用新浪财经公开API

        Args:
            market: 市场类型 (sh/sz/all)

        Returns:
            市场概览数据
        """
        try:
            # 使用新浪财经的公开指数API
            index_urls = {
                'sh': 'https://hq.sinajs.cn/list=s_sh000001',  # 上证指数
                'sz': 'https://hq.sinajs.cn/list=s_sz399001',  # 深证成指
                'all': 'https://hq.sinajs.cn/list=s_sh000001,s_sz399001'  # 两个指数
            }

            url = index_urls.get(market, index_urls['all'])

            # 使用简单的requests请求，不使用代理
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # 解析新浪财经返回的数据
            content = response.text
            index_data = {}

            if 's_sh000001' in content:
                # 解析上证指数数据
                import re
                sh_match = re.search(r'var hq_str_s_sh000001="([^"]+)"', content)
                if sh_match:
                    sh_data = sh_match.group(1).split(',')
                    if len(sh_data) > 3:
                        index_data['sh'] = {
                            'name': '上证指数',
                            'current': float(sh_data[1]) if sh_data[1] else 0,
                            'change': float(sh_data[2]) if sh_data[2] else 0,
                            'change_percent': float(sh_data[3]) if sh_data[3] else 0
                        }

            if 's_sz399001' in content:
                # 解析深证成指数据
                sz_match = re.search(r'var hq_str_s_sz399001="([^"]+)"', content)
                if sz_match:
                    sz_data = sz_match.group(1).split(',')
                    if len(sz_data) > 3:
                        index_data['sz'] = {
                            'name': '深证成指',
                            'current': float(sz_data[1]) if sz_data[1] else 0,
                            'change': float(sz_data[2]) if sz_data[2] else 0,
                            'change_percent': float(sz_data[3]) if sz_data[3] else 0
                        }

            if not index_data:
                return None

            # 计算综合市场状态
            all_changes = [data['change_percent'] for data in index_data.values()]
            avg_change = sum(all_changes) / len(all_changes) if all_changes else 0

            market_state = "上涨" if avg_change > 1 else "下跌" if avg_change < -1 else "震荡"

            result = {
                'market': market,
                'market_state': market_state,
                'avg_change_percent': round(avg_change, 2),
                'timestamp': datetime.now().isoformat(),
                'data_source': 'sina_fallback',
                'note': '使用新浪财经指数数据作为备用方案',
                'indices': index_data
            }

            # 如果只查询单个市场，只返回对应指数信息
            if market in ['sh', 'sz'] and market in index_data:
                idx = index_data[market]
                result.update({
                    'index_name': idx['name'],
                    'index_change_percent': round(idx['change_percent'], 2),
                    'index_current': idx['current']
                })
            elif market == 'all':
                # 全部市场时返回主要指数
                if 'sh' in index_data:
                    result['sh_index'] = {
                        'name': index_data['sh']['name'],
                        'change_percent': round(index_data['sh']['change_percent'], 2)
                    }
                if 'sz' in index_data:
                    result['sz_index'] = {
                        'name': index_data['sz']['name'],
                        'change_percent': round(index_data['sz']['change_percent'], 2)
                    }

            # 为了保持接口兼容性，设置默认值
            result.update({
                'total_stocks': 0,
                'up_count': 0,
                'down_count': 0,
                'flat_count': 0,
                'limit_up_count': 0,
                'limit_down_count': 0,
                'up_ratio': 0,
                'down_ratio': 0
            })

            return result

        except Exception as e:
            logger.error(f"获取备用市场概览失败: {str(e)}")
            # 最后的备用方案：返回模拟的市场状态
            return {
                'market': market,
                'market_state': '数据获取失败',
                'avg_change_percent': 0,
                'timestamp': datetime.now().isoformat(),
                'data_source': 'mock_fallback',
                'note': '所有数据源都失败，返回模拟状态',
                'total_stocks': 0,
                'up_count': 0,
                'down_count': 0,
                'flat_count': 0,
                'limit_up_count': 0,
                'limit_down_count': 0,
                'up_ratio': 0,
                'down_ratio': 0
            }

    def query_quotes(self, stock_code: Optional[str] = None, start_date: Optional[str] = None,
                    end_date: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询历史行情数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量

        Returns:
            行情数据列表
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                sql = 'SELECT * FROM eastmoney_quotes WHERE 1=1'
                params: List[Any] = []

                if stock_code:
                    sql += ' AND stock_code = ?'
                    params.append(stock_code)

                if start_date:
                    sql += ' AND trade_date >= ?'
                    params.append(start_date)

                if end_date:
                    sql += ' AND trade_date <= ?'
                    params.append(end_date)

                sql += ' ORDER BY trade_date DESC, stock_code ASC LIMIT ?'
                params.append(limit)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"查询行情数据失败: {str(e)}")
            return []

    def check_proxy_health(self) -> Dict[str, Any]:
        """
        检查代理池健康状态

        Returns:
            {
                'status': 'healthy/warning/disabled',
                'total_proxies': 5,
                'healthy_proxies': 4,
                'failed_proxies': 1,
                'health_rate': 0.8,
                'message': '代理池健康'
            }
        """
        if not self.proxy_manager:
            return {
                'status': 'disabled',
                'total_proxies': 0,
                'healthy_proxies': 0,
                'failed_proxies': 0,
                'health_rate': 0,
                'message': '代理池未启用'
            }

        total = len(self.proxy_manager._pool)
        healthy = sum(1 for p in self.proxy_manager._pool if p.failures == 0)
        failed = total - healthy
        health_rate = healthy / total if total > 0 else 0

        # 判断健康状态
        if health_rate >= 0.8:
            status = 'healthy'
            message = '代理池健康'
        elif health_rate >= 0.5:
            status = 'warning'
            message = '代理池部分失效，建议补充'
        else:
            status = 'critical'
            message = '代理池严重失效，需要立即补充'

        return {
            'status': status,
            'total_proxies': total,
            'healthy_proxies': healthy,
            'failed_proxies': failed,
            'health_rate': round(health_rate, 2),
            'message': message
        }

    def get_crawler_status(self) -> Dict[str, Any]:
        """获取爬虫状态"""
        status = {
            'proxy_enabled': self.proxy_enabled,
            'proxy_pool_size': len(self.proxy_manager._pool) if self.proxy_manager else 0,
            'static_proxies': len(self.proxy_manager._static_pool) if self.proxy_manager else 0,
            'consecutive_failures': self.consecutive_failures,
            'config': {
                'batch_size': self.batch_size,
                'worker_count': self.worker_count,
                'request_timeout': self.request_timeout,
                'max_retries': self.max_retries,
                'default_delay': self.default_delay
            },
            'data_source': 'eastmoney'
        }

        # 添加代理池健康状态
        if self.proxy_enabled:
            status['proxy_health'] = self.check_proxy_health()

        return status

    def get_breaking_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取东方财富快讯（实时性较好，延迟5-15分钟）

        Args:
            limit: 获取数量，默认20条

        Returns:
            [
                {
                    'title': '新闻标题',
                    'content': '新闻内容',
                    'publish_time': '2025-11-07 10:30:00',
                    'source': '东方财富',
                    'url': 'https://...',
                    'keywords': ['关键词1', '关键词2']
                },
                ...
            ]
        """
        try:
            # 东方财富快讯API
            url = "https://np-anotice-stock.eastmoney.com/api/content/ann"
            params = {
                'client_source': 'web',
                'page_size': limit,
                'page_index': 1,
                'ann_type': 'SHA,SZA',  # 沪深A股
                'f_node': '0',
                'sort_column': 'notice_date',
                'sort_type': 'desc'
            }

            response = self._http_get(url, params=params, use_proxy=True, timeout=10)

            # 检查响应内容
            if not response or not response.text:
                logger.error("获取东方财富快讯失败: 响应为空")
                return []

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"获取东方财富快讯失败: JSON解析错误 - {e}")
                logger.debug(f"响应内容: {response.text[:200]}")
                return []

            if data.get('code') != 0:
                logger.error(f"获取东方财富快讯失败: {data.get('message')}")
                return []

            news_list = []
            for item in data.get('data', {}).get('list', []):
                news_list.append({
                    'title': item.get('title', ''),
                    'content': item.get('content', ''),
                    'publish_time': item.get('notice_date', ''),
                    'source': '东方财富',
                    'url': f"http://data.eastmoney.com/notices/detail/{item.get('art_code', '')}.html",
                    'keywords': self._extract_keywords(item.get('title', '') + item.get('content', '')),
                    'stock_codes': item.get('stock_codes', [])
                })

            logger.info(f"✅ 获取东方财富快讯成功: {len(news_list)}条")
            return news_list

        except Exception as e:
            logger.error(f"获取东方财富快讯失败: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词

        Args:
            text: 文本内容

        Returns:
            关键词列表
        """
        # 关键词列表
        positive_keywords = [
            "利好", "上涨", "突破", "创新", "增长", "盈利", "业绩",
            "订单", "合作", "中标", "政策", "扶持", "补贴", "降准", "降息"
        ]

        negative_keywords = [
            "利空", "下跌", "暴跌", "亏损", "风险", "调查", "处罚",
            "诉讼", "违规", "裁员", "ST", "退市", "破产"
        ]

        keywords = []
        for kw in positive_keywords + negative_keywords:
            if kw in text:
                keywords.append(kw)

        return keywords[:5]  # 最多返回5个关键词

    def get_sector_performance(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取板块涨跌数据

        Args:
            limit: 返回板块数量，默认50个

        Returns:
            板块数据列表，每个板块包含：
            - sector_code: 板块代码
            - sector_name: 板块名称
            - change_pct: 涨跌幅（%）
            - volume: 成交额（亿）
            - leading_stock: 领涨股
            - leading_stock_change: 领涨股涨跌幅
        """
        try:
            # 东方财富板块行情API
            # http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=50&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14,f2,f3,f6,f104,f105,f106
            url = 'http://push2.eastmoney.com/api/qt/clist/get'
            params = {
                'pn': 1,  # 页码
                'pz': limit,  # 每页数量
                'po': 1,  # 排序方式（1=正序，0=倒序）
                'np': 1,  # 不分页
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': 2,
                'invt': 2,
                'fid': 'f3',  # 按涨跌幅排序
                'fs': 'm:90+t:2',  # 板块类型（90=行业板块，2=概念板块）
                'fields': 'f12,f14,f2,f3,f6,f104,f105,f106'  # 字段：代码、名称、最新价、涨跌幅、成交额、领涨股代码、领涨股名称、领涨股涨跌幅
            }

            response = self._http_get(url, params=params, use_proxy=True, timeout=10)

            if response.status_code != 200:
                logger.error(f"获取板块数据失败: HTTP {response.status_code}")
                return []

            data = response.json()

            if not data or 'data' not in data or 'diff' not in data['data']:
                logger.error("板块数据格式错误")
                return []

            sectors = []
            for item in data['data']['diff']:
                sector = {
                    'sector_code': item.get('f12', ''),
                    'sector_name': item.get('f14', ''),
                    'change_pct': float(item.get('f3', 0)) / 100,  # 涨跌幅（转换为小数）
                    'volume': float(item.get('f6', 0)) / 100000000,  # 成交额（转换为亿）
                    'leading_stock_code': item.get('f104', ''),
                    'leading_stock_name': item.get('f105', ''),
                    'leading_stock_change': float(item.get('f106', 0)) / 100  # 领涨股涨跌幅（转换为小数）
                }
                sectors.append(sector)

            logger.info(f"成功获取{len(sectors)}个板块数据")
            return sectors

        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return []

    def get_market_hotspots(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取市场热点数据

        Args:
            limit: 返回热点数量，默认20个

        Returns:
            热点数据列表，每个热点包含：
            - hotspot_name: 热点名称
            - change_pct: 涨跌幅（%）
            - volume: 成交额（亿）
            - stock_count: 相关股票数量
            - leading_stocks: 领涨股列表（最多3只）
        """
        try:
            # 东方财富热点板块API
            # http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f12,f14,f2,f3,f6,f104,f105,f106,f128
            url = 'http://push2.eastmoney.com/api/qt/clist/get'
            params = {
                'pn': 1,
                'pz': limit,
                'po': 1,
                'np': 1,
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': 2,
                'invt': 2,
                'fid': 'f3',  # 按涨跌幅排序
                'fs': 'm:90+t:3',  # 热点板块
                'fields': 'f12,f14,f2,f3,f6,f104,f105,f106,f128'  # 字段：代码、名称、最新价、涨跌幅、成交额、领涨股代码、领涨股名称、领涨股涨跌幅、相关股票数量
            }

            response = self._http_get(url, params=params, use_proxy=True, timeout=10)

            if response.status_code != 200:
                logger.error(f"获取热点数据失败: HTTP {response.status_code}")
                return []

            data = response.json()

            if not data or 'data' not in data or 'diff' not in data['data']:
                logger.error("热点数据格式错误")
                return []

            hotspots = []
            for item in data['data']['diff']:
                hotspot = {
                    'hotspot_name': item.get('f14', ''),
                    'change_pct': float(item.get('f3', 0)) / 100,
                    'volume': float(item.get('f6', 0)) / 100000000,
                    'stock_count': int(item.get('f128', 0)),
                    'leading_stocks': [
                        {
                            'code': item.get('f104', ''),
                            'name': item.get('f105', ''),
                            'change_pct': float(item.get('f106', 0)) / 100
                        }
                    ] if item.get('f104') else []
                }
                hotspots.append(hotspot)

            logger.info(f"成功获取{len(hotspots)}个热点数据")
            return hotspots

        except Exception as e:
            logger.error(f"获取热点数据失败: {e}")
            return []


# === 便捷函数 ===

def create_eastmoney_crawler(enable_proxy: bool = None) -> EastMoneyCrawler:
    """创建东方财富爬虫实例"""
    return EastMoneyCrawler(enable_proxy=enable_proxy)

def crawl_stock_quote_eastmoney(stock_code: str, save_to_db: bool = True) -> Optional[Dict[str, Any]]:
    """快速爬取单只股票行情"""
    crawler = EastMoneyCrawler()
    result = crawler.crawl_single_stock(stock_code, save_to_db)
    return result.data if result.success else None

def crawl_multiple_quotes_eastmoney(stock_codes: List[str], save_to_db: bool = True) -> List[Dict[str, Any]]:
    """快速批量爬取股票行情"""
    crawler = EastMoneyCrawler()
    results = crawler.crawl_multiple_stocks(stock_codes, save_to_db)
    return [result.data for result in results if result.success]


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("东方财富爬虫工具测试")
    print("=" * 60)

    crawler = EastMoneyCrawler()

    # 显示爬虫状态
    status = crawler.get_crawler_status()
    print(f"爬虫状态: {status}")

    # 测试单只股票爬取
    print("\n【测试1】爬取单只股票数据")
    result = crawler.crawl_single_stock('600000')
    if result.success:
        print(f"股票: {result.data['stock_name']} ({result.data['stock_code']})")
        print(f"价格: {result.data['current_price']}")
        print(f"涨跌幅: {result.data['change_percent']}%")
        print(f"用时: {result.duration:.2f}s")
    else:
        print(f"爬取失败: {result.error}")

    # 测试市场概览
    print("\n【测试2】获取市场概览")
    overview = crawler.get_market_overview()
    if overview:
        print(f"总股票数: {overview['total_stocks']}")
        print(f"上涨: {overview['up_count']} ({overview['up_ratio']}%)")
        print(f"跌停: {overview['limit_down_count']}")
        print(f"涨停: {overview['limit_up_count']}")

    # 测试批量爬取
    print("\n【测试3】批量爬取测试")
    test_codes = ['600000', '000001', '000002']
    results = crawler.crawl_multiple_stocks(test_codes, save_to_db=False)
    success_results = [r for r in results if r.success]
    print(f"成功: {len(success_results)}/{len(results)}")

    print("\n测试完成！")