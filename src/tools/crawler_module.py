"""
股票数据爬取模块
包含两个主要功能：
1. 爬取股票行情数据
2. 爬取逐笔交易数据（待实现）
"""

import os
import json
import time
import sqlite3
import threading
import multiprocessing
import queue
import sys
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from queue import Empty
from typing import Optional, Dict, List, Tuple, Any, Set

import requests

SETTING_KEYS = {
    'REQUEST_TIMEOUT',
    'CRAWLER_MAX_RETRIES',
    'CRAWLER_RETRY_DELAY',
    'CRAWLER_RETRY_BACKOFF',
    'CRAWLER_DELAY_SECONDS',
    'CRAWLER_PROXY_DELAY',
    'CRAWLER_PROXY_POOL_SIZE',
    'CRAWLER_PROXY_EXPIRY_SECONDS',
    'CRAWLER_FAIL_THRESHOLD',
    'CRAWLER_DB_TIMEOUT',
    'CRAWLER_BATCH_SIZE',
    'CRAWLER_WORKERS',
    'CRAWLER_ITEM_RETRIES',
    'CRAWLER_TICK_INSERT_BATCH',
    'CRAWLER_PROCESS_WRITER',
    'CRAWLER_TICK_QUEUE_SIZE',
    'GIANT_IP_API_URL',
    'GIANT_IP_STATIC_PROXIES',
    'GIANT_IP_PROTOCOL',
    'GIANT_IP_CACHE_TTL',
    'GIANT_IP_MAX_FAILURES',
    'GIANT_IP_FETCH_TIMEOUT',
    'CRAWLER_CONFIG_PATH',
    'CRAWLER_USE_PROXY',
}

RECOMMEND_TABLE = 'daily_recommendations'


def _bulk_save_ticks(db_path: str, tick_list: List[Dict[str, Any]], chunk_size: int, use_split_db: bool = False) -> None:
    if not tick_list:
        return

    trade_date = tick_list[0].get('trade_date')
    if not trade_date:
        return

    # 在拆分数据库模式下，使用 tick_data 作为表名
    # 并且 db_path 应该已经指向了正确的 tick_data_YYYYMMDD.db 文件
    if use_split_db:
        table_name = "tick_data"
    else:
        table_name = f"tick_data_{trade_date.replace('-', '')}"
    
    records = [
        (
            tick.get('stock_code'),
            tick.get('trade_date'),
            tick.get('trade_time'),
            tick.get('price'),
            tick.get('volume'),
            tick.get('amount'),
            tick.get('buy_sell_type'),
        )
        for tick in tick_list
    ]

    chunk_size = max(1, int(chunk_size or 1))
    insert_sql = f"""
        INSERT OR REPLACE INTO {table_name} (
            stock_code, trade_date, trade_time, price, volume, amount,
            buy_sell_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """

    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute('PRAGMA busy_timeout = 30000')
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date DATE NOT NULL,
            trade_time TIME NOT NULL,
            price REAL,
            volume INTEGER,
            amount REAL,
            buy_sell_type INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, trade_date, trade_time)
        )
        """)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_code ON {table_name}(stock_code)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_time ON {table_name}(trade_time)")

        for idx in range(0, len(records), chunk_size):
            cursor.executemany(insert_sql, records[idx: idx + chunk_size])

def _tick_writer_process(db_path: str, task_queue: 'queue.JoinableQueue', chunk_size: int, use_split_db: bool = False, tick_db_folder: str = None) -> None:
    batch_count = 0
    record_total = 0
    while True:
        item = task_queue.get()
        if item is None:
            task_queue.task_done()
            break
        try:
            record_count = len(item)
            # 在拆分数据库模式下，根据日期确定数据库路径
            actual_db_path = db_path
            if use_split_db and item:
                trade_date = item[0].get('trade_date')
                if trade_date and tick_db_folder:
                    date_str = trade_date.replace('-', '')
                    actual_db_path = os.path.join(tick_db_folder, f'tick_data_{date_str}.db')
            
            _bulk_save_ticks(actual_db_path, item, chunk_size, use_split_db)
            batch_count += 1
            record_total += record_count
            print(f"[WRITE] 子进程写入 {record_count} 条（批次 {batch_count}，累计 {record_total} 条）")
        except Exception as exc:
            print(f"[WRITE] 子进程写入失败: {exc}")
        finally:
            sys.stdout.flush()
            task_queue.task_done()
    print(f"[WRITE] 子进程写入完成，共 {batch_count} 批 {record_total} 条记录")
    sys.stdout.flush()
@dataclass

class ProxyEntry:
    """Single proxy item with metadata."""
    proxy: Dict[str, str]
    raw: str
    expires_at: float
    failures: int = 0


class GiantIPProxyManager:
    """巨量IP代理池管理器，支持有限池复用和失败替换。"""

    def __init__(
        self,
        api_url: Optional[str],
        protocol: str = 'http',
        cache_ttl: float = 15.0,
        max_failures: int = 2,
        static_proxies: Optional[List[str]] = None,
        fetch_timeout: int = 8,
        max_pool_size: int = 5,
    ) -> None:
        self.api_url = api_url
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
        """转换原始代理格式为 requests 能识别的格式。"""
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
                print(f"[ProxyPool] 从巨量IP获取代理: {raw}（原因: {reason}）")
                added += 1
                break  # 一次只引入一个代理
            if added == 0:
                print(f"[ProxyPool] 巨量IP接口未返回新代理（{reason}）")
            return added
        except Exception as exc:
            print(f"[ProxyPool] 获取巨量IP代理失败：{exc}（{reason}）")
            return 0

    def _ensure_pool_locked(self, reason: str = '') -> None:
        while len(self._pool) < self.max_pool_size:
            added = self._fetch_one_locked(reason)
            if added == 0:
                break

    def _prune_expired_locked(self) -> None:
        now = time.time()
        refreshed = deque()
        removed = False
        while self._pool:
            entry = self._pool.popleft()
            if entry.expires_at and entry.expires_at < now:
                print(f"[ProxyPool] 代理 {entry.raw} 已过期，移除")
                removed = True
                continue
            refreshed.append(entry)
        self._pool = refreshed
        if removed:
            self._ensure_pool_locked('expired replacement')

    def acquire(self) -> Optional[ProxyEntry]:
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
        with self._lock:
            print(f"[ProxyPool] 代理 {entry.raw} 请求失败：{reason}")
            try:
                self._pool.remove(entry)
            except ValueError:
                pass
            self._ensure_pool_locked('failure replacement')

    def report_success(self, entry: ProxyEntry) -> None:
        entry.failures = 0

    @property
    def enabled(self) -> bool:
        return bool(self.api_url or self._static_pool)

class StockDataCrawler:
    """股票数据爬取器"""

    def __init__(
        self,
        db_path: str = 'stocks.db',
        session: Optional[requests.Session] = None,
        enable_proxy: Optional[bool] = None,
        proxy_pool_size: Optional[int] = None,
        use_split_db: bool = None,
    ):
        """
        初始化爬虫实例。

        Args:
            db_path: 数据库文件路径
            session: 可选自定义 requests.Session
            enable_proxy: 是否启用代理，None 表示遵循配置文件/环境变量
            proxy_pool_size: 代理池大小，None 表示使用配置文件中的值
            use_split_db: 是否使用拆分数据库（None=自动检测）
        """
        self.db_path = db_path
        
        # 自动检测是否使用拆分数据库
        if use_split_db is None:
            use_split_db = os.path.exists('stocks') and os.path.isdir('stocks')
        self.use_split_db = use_split_db
        
        if self.use_split_db:
            from database_manager import DatabaseManager
            self.db_manager = DatabaseManager()
            print("爬虫模块使用拆分数据库模式")
        else:
            self.db_manager = None
            print(f"爬虫模块使用单一数据库模式: {db_path}")
        
        self.session = session or requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'http://quote.eastmoney.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        self.base_url = 'http://push2.eastmoney.com/api/qt'
        self.settings = self._load_settings()
        self.request_timeout = float(self.settings.get('REQUEST_TIMEOUT', 10))
        self.max_retries = int(self.settings.get('CRAWLER_MAX_RETRIES', 3))
        self.retry_delay = float(self.settings.get('CRAWLER_RETRY_DELAY', 0.5))
        self.retry_backoff = float(self.settings.get('CRAWLER_RETRY_BACKOFF', 1.5))
        self.default_delay = float(self.settings.get('CRAWLER_DELAY_SECONDS', 0.5))
        self.proxy_delay = float(self.settings.get('CRAWLER_PROXY_DELAY', 0.05))
        self.proxy_pool_size = proxy_pool_size  # 保存代理池大小参数

        config_proxy_flag = self._to_bool(self.settings.get('CRAWLER_USE_PROXY', False), default=False)
        self.proxy_enabled = config_proxy_flag if enable_proxy is None else enable_proxy
        self.proxy_manager = self._build_proxy_manager() if self.proxy_enabled else None
        if self.proxy_enabled and self.proxy_manager is None:
            raise RuntimeError('启用了代理模式，但未加载有效的巨量IP代理配置。请检查 config/crawler_config.json 或环境变量，或使用 --proxy off 临时禁用。')
        self._thread_local = threading.local()

        self.db_timeout = float(self.settings.get('CRAWLER_DB_TIMEOUT', 30))
        self.fail_threshold = int(self.settings.get('CRAWLER_FAIL_THRESHOLD', 2))
        self.batch_size = int(self.settings.get('CRAWLER_BATCH_SIZE', 100))
        self.worker_count = int(self.settings.get('CRAWLER_WORKERS', 5))
        self.item_retry_limit = int(self.settings.get('CRAWLER_ITEM_RETRIES', 3))
        self.tick_insert_batch = int(self.settings.get('CRAWLER_TICK_INSERT_BATCH', 5000))
        self.use_process_writer = self._to_bool(self.settings.get('CRAWLER_PROCESS_WRITER', True), default=True)
        self.tick_writer_queue_size = int(self.settings.get('CRAWLER_TICK_QUEUE_SIZE', 50))
        self.consecutive_failures = 0

        # 初始化数据库表
        self._init_database()

    def _get_connection(self, db_type: str = 'base') -> sqlite3.Connection:
        """
        获取数据库连接
        
        Args:
            db_type: 数据库类型 ('base', 'quotes', 'watchlist', 'recommendations')
        """
        if self.use_split_db:
            db_path = self.db_manager.db_paths.get(db_type, self.db_path)
        else:
            db_path = self.db_path
        
        conn = sqlite3.connect(db_path, timeout=self.db_timeout)
        conn.execute(f'PRAGMA busy_timeout = {int(self.db_timeout * 1000)}')
        return conn
    
    def _get_quotes_connection(self) -> sqlite3.Connection:
        """获取行情数据库连接"""
        return self._get_connection('quotes')
    
    def _get_base_connection(self) -> sqlite3.Connection:
        """获取基础数据库连接"""
        return self._get_connection('base')
    
    def _get_tick_connection(self, trade_date: str) -> sqlite3.Connection:
        """获取逐笔数据库连接"""
        if self.use_split_db:
            date_str = trade_date.replace('-', '')
            tick_db_path = os.path.join(self.db_manager.tick_db_folder, f'tick_data_{date_str}.db')
            conn = sqlite3.connect(tick_db_path, timeout=self.db_timeout)
        else:
            conn = sqlite3.connect(self.db_path, timeout=self.db_timeout)
        
        conn.execute(f'PRAGMA busy_timeout = {int(self.db_timeout * 1000)}')
        return conn

    def _load_settings(self) -> Dict[str, Any]:
        """加载配置文件和环境变量，环境变量优先级更高。"""
        settings: Dict[str, Any] = {}

        default_config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config',
            'crawler_config.json',
        )
        config_path = os.getenv('CRAWLER_CONFIG_PATH', default_config_path)
        self.config_path = config_path

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(key, str):
                            settings[key.upper()] = value
            except Exception as exc:
                print(f"加载配置文件 {config_path} 失败: {exc}")

        for key in SETTING_KEYS:
            env_value = os.getenv(key)
            if env_value is not None:
                settings[key] = env_value

        return settings

    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        """将多种类型的值解析为布尔值。"""
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

    def _build_proxy_manager(self) -> Optional[GiantIPProxyManager]:
        """根据配置创建巨量IP代理管理器。"""
        settings = self.settings

        api_raw = settings.get('GIANT_IP_API_URL')
        api_url = str(api_raw).strip() if api_raw else None

        static_raw = settings.get('GIANT_IP_STATIC_PROXIES')
        static_list: Optional[List[str]] = None
        if isinstance(static_raw, str):
            static_list = [item.strip() for item in static_raw.split(',') if item.strip()]
        elif isinstance(static_raw, (list, tuple, set)):
            static_list = [str(item).strip() for item in static_raw if str(item).strip()]

        if not api_url and not static_list:
            return None

        protocol = str(settings.get('GIANT_IP_PROTOCOL', 'http')).lower() or 'http'
        expire_seconds = float(settings.get('CRAWLER_PROXY_EXPIRY_SECONDS', 170))
        cache_ttl = float(settings.get('GIANT_IP_CACHE_TTL', expire_seconds))
        max_failures = int(settings.get('GIANT_IP_MAX_FAILURES', 2))
        fetch_timeout = int(settings.get('GIANT_IP_FETCH_TIMEOUT', 8))

        # 优先使用传入的proxy_pool_size参数，否则从配置读取
        if self.proxy_pool_size is not None:
            max_pool_size = int(self.proxy_pool_size)
        else:
            max_pool_size = int(settings.get('CRAWLER_PROXY_POOL_SIZE', 5))

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

    def _set_last_proxy_label(self, label: Optional[str]) -> None:
        self._thread_local.last_proxy_label = label

    def _get_last_proxy_label(self) -> Optional[str]:
        return getattr(self._thread_local, 'last_proxy_label', None)

    def _clear_last_proxy_label(self) -> None:
        self._thread_local.last_proxy_label = None

    def _format_proxy_info(self, label: Optional[str]) -> str:
        if not self.proxy_enabled:
            return 'proxy: off'
        if label and label != 'DIRECT':
            return f'proxy: {label}'
        if self.proxy_manager:
            return 'proxy: direct'
        return 'proxy: off'

    def _init_database(self):
        """初始化数据库表结构"""
        # 在 quotes.db 中创建行情数据表
        with self._get_quotes_connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()

            # 创建行情数据表
            cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            trade_date DATE NOT NULL,
            current_price REAL,
            open_price REAL,
            close_price REAL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, trade_date)
        )
        ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_quotes_code ON stock_quotes(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_quotes_date ON stock_quotes(trade_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_quotes_code_date ON stock_quotes(stock_code, trade_date)')

            # 创建逐笔交易数据表
            cursor.execute('''
        CREATE TABLE IF NOT EXISTS tick_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date DATE NOT NULL,
            trade_time TIME NOT NULL,
            price REAL,
            volume INTEGER,
            amount REAL,
            buy_sell_type INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, trade_date, trade_time)
        )
        ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tick_code ON tick_data(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tick_date ON tick_data(trade_date)')

            # 创建历史K线数据表

            cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {RECOMMEND_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            rank INTEGER NOT NULL,
            score REAL,
            change_percent REAL,
            turnover_rate REAL,
            payload TEXT,
            batch_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(strategy, trade_date, stock_code, batch_id)
        )
        ''')
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{RECOMMEND_TABLE}_date "
                f"ON {RECOMMEND_TABLE}(trade_date)"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{RECOMMEND_TABLE}_strategy "
                f"ON {RECOMMEND_TABLE}(strategy)"
            )

    def _http_get(self, url: str, params: Optional[Dict[str, Any]] = None, use_proxy: bool = True, timeout: Optional[float] = None) -> requests.Response:
        """统一的 GET 请求入口，带重试和代理支持。"""
        last_error: Optional[Exception] = None
        require_proxy = use_proxy and self.proxy_enabled
        self._clear_last_proxy_label()

        if require_proxy and not self.proxy_manager:
            raise RuntimeError('启用了代理模式，但代理池未初始化，请检查配置或使用 --proxy off。')

        for attempt in range(1, self.max_retries + 1):
            entry: Optional[ProxyEntry] = None
            proxies: Optional[Dict[str, str]] = None
            proxy_label: Optional[str] = 'DIRECT' if not require_proxy else None

            try:
                if require_proxy:
                    entry = self.proxy_manager.acquire() if self.proxy_manager else None
                    if not entry:
                        raise RuntimeError('启用了代理模式，但无法获取新的代理IP，请检查余额或降低获取频率。')
                    proxies = entry.proxy
                    proxy_label = entry.raw
                elif use_proxy and self.proxy_manager:
                    entry = self.proxy_manager.acquire()
                    if entry:
                        proxies = entry.proxy
                        proxy_label = entry.raw

                response = self.session.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=timeout or self.request_timeout,
                    proxies=proxies,
                )
                response.raise_for_status()
                if entry and self.proxy_manager:
                    self.proxy_manager.report_success(entry)
                self._set_last_proxy_label(proxy_label if proxy_label else ('DIRECT' if not require_proxy else None))
                return response
            except Exception as exc:
                last_error = exc
                reason = str(exc)
                if entry and self.proxy_manager:
                    self.proxy_manager.report_failure(entry, reason)
                self._set_last_proxy_label(proxy_label if proxy_label else ('DIRECT' if not require_proxy else None))

                if attempt < self.max_retries:
                    sleep_seconds = self.retry_delay * (self.retry_backoff ** (attempt - 1))
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                    continue
                break

        if last_error:
            if require_proxy:
                raise RuntimeError(f'代理模式请求失败: {last_error}')
            raise last_error
        raise RuntimeError('HTTP 请求失败的未知异常')

    def _fetch_recommended_stocks(self, trade_date: str) -> List[Tuple[str, str]]:
        """读取推荐表中指定交易日的股票列表"""
        if not trade_date:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT stock_code, COALESCE(stock_name, '')
                FROM {RECOMMEND_TABLE}
                WHERE trade_date = ?
                ORDER BY rank ASC, stock_code ASC
                """,
                (trade_date,),
            )
            rows = cursor.fetchall()

        seen: Set[str] = set()
        result: List[Tuple[str, str]] = []
        for code, name in rows:
            if not code or code in seen:
                continue
            seen.add(code)
            result.append((code, name or ''))
        return result

    def get_stock_quote(self, stock_code: str) -> Optional[Dict]:
        """
        获取单只股票的实时行情数据

        Args:
            stock_code: 股票代码

        Returns:
            股票行情数据字典，失败返回None
        """
        try:
            # 判断市场代码（上海1，深圳0）
            if stock_code.startswith('6') or stock_code.startswith('688'):
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
            if data.get('data') is None:
                print(f"未找到股票 {stock_code} 的数据")
                return None

            stock_data = data['data']

            # 解析数据
            # 字段说明（已验证）：
            # f43=最新价, f44=最高, f45=最低, f46=今开, f47=成交量(手), f48=成交额
            # f50=量比, f60=昨收, f86=交易日期时间戳
            # f116=总市值, f117=流通市值
            # f162=市盈率(动), f167=市净率, f168=换手率, f171=振幅
            # f169=涨跌额, f170=涨跌幅

            # 获取交易日期（从时间戳转换）
            trade_timestamp = stock_data.get('f86')
            if trade_timestamp:
                trade_date = datetime.fromtimestamp(trade_timestamp).strftime('%Y-%m-%d')
            else:
                trade_date = datetime.now().strftime('%Y-%m-%d')

            # 计算涨跌额和涨跌幅（如果API未提供，则手动计算）
            current_price = stock_data.get('f43', 0) / 100 if stock_data.get('f43') else None
            prev_close = stock_data.get('f60', 0) / 100 if stock_data.get('f60') else None

            # 优先使用API提供的值，如果为None则手动计算
            change_amount = stock_data.get('f169', 0) / 100 if stock_data.get('f169') else None
            change_percent = stock_data.get('f170', 0) / 100 if stock_data.get('f170') else None

            # 如果API没有提供涨跌数据，但有价格数据，则手动计算
            if change_amount is None and current_price is not None and prev_close is not None and prev_close != 0:
                change_amount = round(current_price - prev_close, 2)
            if change_percent is None and current_price is not None and prev_close is not None and prev_close != 0:
                change_percent = round((current_price - prev_close) / prev_close * 100, 2)

            quote = {
                'stock_code': stock_code,
                'stock_name': stock_data.get('f58', ''),
                'trade_date': trade_date,
                'current_price': current_price,
                'open_price': stock_data.get('f46', 0) / 100 if stock_data.get('f46') else None,
                'close_price': current_price,  # 实时收盘价用最新价
                'high_price': stock_data.get('f44', 0) / 100 if stock_data.get('f44') else None,
                'low_price': stock_data.get('f45', 0) / 100 if stock_data.get('f45') else None,
                'prev_close': prev_close,
                'change_amount': change_amount,
                'change_percent': change_percent,
                'volume': stock_data.get('f47', 0) if stock_data.get('f47') else None,
                'turnover': stock_data.get('f48', 0) if stock_data.get('f48') else None,
                'amplitude': stock_data.get('f171', 0) / 100 if stock_data.get('f171') else None,  # 振幅（修正：使用f171）
                'turnover_rate': stock_data.get('f168', 0) / 100 if stock_data.get('f168') else None,  # 换手率
                'volume_ratio': stock_data.get('f50', 0) / 100 if stock_data.get('f50') else None,  # 量比
                'pe_ratio': stock_data.get('f162', 0) / 100 if stock_data.get('f162') else None,  # 市盈率
                'pb_ratio': stock_data.get('f167', 0) / 100 if stock_data.get('f167') else None,  # 市净率
                'market_value': stock_data.get('f116', 0) if stock_data.get('f116') else None,
                'circulating_market_value': stock_data.get('f117', 0) if stock_data.get('f117') else None
            }

            return quote

        except Exception as e:
            print(f"获取股票 {stock_code} 行情数据失败: {str(e)}")
            return None

    def save_quote_to_db(self, quote: Dict) -> bool:
        """
        保存行情数据到数据库

        Args:
            quote: 行情数据字典

        Returns:
            成功返回True，失败返回False
        """
        try:
            with self._get_quotes_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
            INSERT OR REPLACE INTO stock_quotes (
                stock_code, stock_name, trade_date, current_price, open_price,
                close_price, high_price, low_price, prev_close, change_amount,
                change_percent, volume, turnover, amplitude, turnover_rate,
                volume_ratio, pe_ratio, pb_ratio, market_value, circulating_market_value,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (
                quote['stock_code'], quote['stock_name'], quote['trade_date'],
                quote['current_price'], quote['open_price'], quote['close_price'],
                quote['high_price'], quote['low_price'], quote['prev_close'],
                quote['change_amount'], quote['change_percent'], quote['volume'],
                quote['turnover'], quote['amplitude'], quote['turnover_rate'],
                quote['volume_ratio'], quote['pe_ratio'], quote['pb_ratio'],
                quote['market_value'], quote['circulating_market_value']
            ))
            return True

        except Exception as e:
            print(f"保存行情数据失败: {str(e)}")
            return False

    def crawl_quote(self, stock_code: str, save_to_db: bool = True) -> Optional[Dict]:
        """
        爬取单只股票行情数据

        Args:
            stock_code: 股票代码
            save_to_db: 是否保存到数据库

        Returns:
            行情数据字典
        """
        quote = self.get_stock_quote(stock_code)

        if quote and save_to_db:
            self.save_quote_to_db(quote)

        return quote



    def crawl_all_quotes(
        self,
        stocks: Optional[List[Tuple[str, str]]] = None,
        save_to_db: bool = True,
        delay: Optional[float] = None,
    ) -> List[Dict]:
        """爬取所有股票的行情数据"""
        if stocks is None:
            with self._get_base_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT code, name FROM stocks')
                stocks = cursor.fetchall()
        else:
            stocks = list(stocks)

        total = len(stocks)
        if total == 0:
            print("未找到股票列表，终止爬取。")
            return []

        print(f"开始爬取 {total} 只股票的行情数据（批大小 {self.batch_size}，并发 {self.worker_count}）...")

        effective_delay = self.default_delay if delay is None else delay
        if delay is None and self.proxy_manager:
            effective_delay = self.proxy_delay
        if effective_delay < 0:
            effective_delay = 0.0

        self.consecutive_failures = 0
        consecutive_failures = 0
        success_count = 0
        fail_count = 0
        processed = 0
        quotes: List[Dict] = []
        halt_error: Optional[str] = None

        result_queue: Optional[Queue] = None
        writer_thread: Optional[threading.Thread] = None
        writer_process: Optional[multiprocessing.Process] = None

        if save_to_db:
            result_queue = Queue()

            def _writer() -> None:
                while True:
                    item = result_queue.get()
                    if item is None:
                        result_queue.task_done()
                        break
                    try:
                        self.save_quote_to_db(item)
                    except Exception as exc:
                        print(f"[WRITE] 保存行情失败: {exc}")
                    finally:
                        result_queue.task_done()

            writer_thread = threading.Thread(target=_writer, daemon=True)
            writer_thread.start()

        def fetch_quote(entry: Tuple[str, str]) -> Tuple[str, str, Optional[Dict], Optional[Exception]]:
            code, name = entry
            try:
                quote = self.crawl_quote(code, save_to_db=False)
                return code, name, quote, None
            except Exception as exc:
                return code, name, None, exc

        for batch_start in range(0, total, self.batch_size):
            if halt_error:
                break

            batch = stocks[batch_start: batch_start + self.batch_size]
            print(f"\nBatch {batch_start // self.batch_size + 1}: processing {len(batch)} stocks")

            with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
                futures = {executor.submit(fetch_quote, item): item for item in batch}

                for future in as_completed(futures):
                    code, name, quote, error = future.result()
                    processed += 1

                    if halt_error:
                        continue

                    if quote:
                        if save_to_db and result_queue is not None:
                            result_queue.put(quote)
                        quotes.append(quote)
                        success_count += 1
                        consecutive_failures = 0
                        print(f"[{processed}/{total}] {code} {name} -> OK")
                    else:
                        fail_count += 1
                        consecutive_failures += 1
                        reason = error or "no data"
                        print(f"[{processed}/{total}] {code} {name} -> FAIL ({reason})")

                        if consecutive_failures >= self.fail_threshold:
                            halt_error = (
                                f"连续失败 {consecutive_failures} 次，停止爬取。最新股票 {code}，原因: {reason}"
                            )

                    if halt_error:
                        continue

                    if effective_delay > 0:
                        time.sleep(effective_delay)

        if save_to_db and result_queue is not None:
            if self.use_process_writer and writer_process is not None:
                result_queue.put(None)
                result_queue.join()
                writer_process.join()
                try:
                    result_queue.close()
                except Exception:
                    pass
                try:
                    result_queue.join_thread()
                except Exception:
                    pass
            else:
                result_queue.join()
                result_queue.put(None)
                if writer_thread:
                    writer_thread.join()

        self.consecutive_failures = consecutive_failures

        if halt_error:
            raise RuntimeError(halt_error)

        print(f"\n爬取完成！成功: {success_count}, 失败: {fail_count}")
        return quotes


    def get_tick_data(self, stock_code: str, trade_date: str = None) -> Optional[List[Dict]]:
            """
            获取逐笔交易数据（包含所有数据：集合竞价 + 连续竞价）

            Args:
                stock_code: 股票代码
                trade_date: 交易日期，默认为今天

            Returns:
                逐笔交易数据列表
            """
            try:
                # 判断市场代码
                if stock_code.startswith('6') or stock_code.startswith('688'):
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

                if data.get('data') is None or 'details' not in data['data']:
                    print(f"未找到股票 {stock_code} 的逐笔数据")
                    return None

                details = data['data']['details']

                # 获取实际交易日期
                if not trade_date:
                    # 从行情API获取实际交易日期（f86字段是交易时间戳）
                    quote_url = f'{self.base_url}/stock/get'
                    quote_params = {
                        'secid': sec_id,
                        'fields': 'f86',  # f86是交易时间戳
                        'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
                    }
                    quote_response = self._http_get(quote_url, params=quote_params)
                    quote_data = quote_response.json()

                    if quote_data.get('data') and quote_data['data'].get('f86'):
                        # f86是Unix时间戳，转换为日期
                        timestamp = quote_data['data']['f86']
                        trade_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    else:
                        # 如果无法获取，使用当前日期
                        trade_date = datetime.now().strftime('%Y-%m-%d')

                # 解析逐笔数据（所有数据）
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
                        from decimal import Decimal
                        amount = float(Decimal(str(price)) * Decimal(str(volume_in_hands * 100)))

                        tick = {
                            'stock_code': stock_code,
                            'trade_date': trade_date,
                            'trade_time': time_str,
                            'price': price,
                            'volume': volume_in_hands,  # 直接保存手数（不再×100）
                            'amount': amount,
                            'buy_sell_type': buy_sell_type  # 0=中性盘, 1=买入, 2=卖出
                        }
                        tick_list.append(tick)

                return tick_list

            except Exception as e:
                print(f"获取股票 {stock_code} 逐笔数据失败: {str(e)}")
                return None
    def _create_daily_tick_table(self, trade_date: str) -> None:
        """创建当天的逐笔数据表。"""
        table_name = f"tick_data_{trade_date.replace('-', '')}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                trade_date DATE NOT NULL,
                trade_time TIME NOT NULL,
                price REAL,
                volume INTEGER,
                amount REAL,
                buy_sell_type INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, trade_date, trade_time)
            )
            """)
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_code ON {table_name}(stock_code)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_time ON {table_name}(trade_time)")

    def save_tick_to_db(self, tick_list: List[Dict]) -> bool:
        """保存逐笔数据到数据库（按天分表）。"""
        try:
            if self.use_split_db and tick_list:
                # 拆分数据库模式：保存到对应日期的 tick 数据库
                trade_date = tick_list[0].get('trade_date')
                if trade_date:
                    tick_conn = self._get_tick_connection(trade_date)
                    tick_db_path = tick_conn.execute("PRAGMA database_list").fetchone()[2]
                    tick_conn.close()
                    _bulk_save_ticks(tick_db_path, tick_list, self.tick_insert_batch, use_split_db=True)
                else:
                    return False
            else:
                # 单一数据库模式
                _bulk_save_ticks(self.db_path, tick_list, self.tick_insert_batch, use_split_db=False)
            return True
        except Exception as e:
            print(f"保存逐笔数据失败: {str(e)}")
            return False

    def crawl_tick(self, stock_code: str, trade_date: str = None, save_to_db: bool = True) -> Optional[List[Dict]]:
            """爬取单只股票逐笔数据。"""
            tick_list = self.get_tick_data(stock_code, trade_date)

            if tick_list and save_to_db:
                self.save_tick_to_db(tick_list)

            return tick_list

    def crawl_all_ticks(
        self,
        trade_date: str,
        stocks: Optional[List[Tuple[str, str]]] = None,
        save_to_db: bool = True,
        delay: Optional[float] = None,
    ) -> Dict[str, Any]:
        """批量并发抓取逐笔数据，与行情抓取保持一致的线程模型。"""
        trade_date = trade_date or datetime.now().strftime('%Y-%m-%d')

        if stocks is None:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT code, name FROM stocks')
                stocks = cursor.fetchall()

        total = len(stocks)
        if total == 0:
            print('未找到股票列表，终止逐笔爬取任务')
            return {
                'processed': 0,
                'success': 0,
                'fail': 0,
                'stats': {},
                'results': {} if not save_to_db else None,
                'duration_seconds': 0.0,
            }

        print(f"开始抓取 {total} 只股票逐笔数据，批次大小 {self.batch_size}，线程 {self.worker_count} …")

        effective_delay = self.default_delay if delay is None else delay
        if delay is None and self.proxy_manager:
            effective_delay = self.proxy_delay
        if effective_delay < 0:
            effective_delay = 0.0

        self.consecutive_failures = 0
        consecutive_failures = 0
        processed = 0
        success_count = 0
        fail_count = 0
        halt_error: Optional[str] = None

        stats: Dict[str, int] = {}
        result_queue: Optional[Any] = None
        writer_thread: Optional[threading.Thread] = None
        writer_process: Optional[multiprocessing.Process] = None
        stored_results: Optional[Dict[str, List[Dict[str, Any]]]] = {} if not save_to_db else None

        if save_to_db:
            if self.use_process_writer:
                ctx = multiprocessing.get_context('spawn')
                queue_size = max(1, int(getattr(self, 'tick_writer_queue_size', 50) or 1))
                result_queue = ctx.JoinableQueue(maxsize=queue_size)
                tick_db_folder = self.db_manager.tick_db_folder if self.use_split_db else None
                writer_process = ctx.Process(
                    target=_tick_writer_process,
                    args=(self.db_path, result_queue, self.tick_insert_batch, self.use_split_db, tick_db_folder),
                    daemon=True,
                )
                writer_process.start()
            else:
                result_queue = Queue()

                def _writer() -> None:
                    while True:
                        item = result_queue.get()
                        if item is None:
                            result_queue.task_done()
                            break
                        try:
                            record_count = len(item)
                            self.save_tick_to_db(item)
                            print(f"[WRITE] 写入线程写入 {record_count} 条")
                        except Exception as exc:
                            print(f"[WRITE] 写入逐笔数据失败: {exc}")
                        finally:
                            sys.stdout.flush()
                            result_queue.task_done()

                writer_thread = threading.Thread(target=_writer, daemon=True)
                writer_thread.start()

        stock_queue: Queue = Queue()
        for entry in stocks:
            stock_queue.put(entry)

        halt_event = threading.Event()
        lock = threading.Lock()
        item_attempts: Dict[str, int] = defaultdict(int)

        start_time = time.time()

        def worker(worker_id: int) -> None:
            nonlocal processed, success_count, fail_count, consecutive_failures, halt_error

            while not halt_event.is_set():
                try:
                    code, name = stock_queue.get_nowait()
                except queue.Empty:
                    break

                self._clear_last_proxy_label()
                tick_list: Optional[List[Dict[str, Any]]] = None
                error: Optional[Exception] = None
                try:
                    tick_list = self.get_tick_data(code, trade_date=trade_date)
                except Exception as exc:
                    error = exc

                proxy_label = self._get_last_proxy_label()
                proxy_info = self._format_proxy_info(proxy_label)
                requeue = False

                with lock:
                    if halt_event.is_set():
                        pass
                    elif tick_list:
                        processed += 1
                        success_count += 1
                        stats[code] = len(tick_list)
                        consecutive_failures = 0
                        item_attempts.pop(code, None)
                        print(f"[{processed}/{total}] {code} {name} -> OK ({len(tick_list)} 条) [{proxy_info}]")

                        if save_to_db and result_queue is not None:
                            result_queue.put(tick_list)
                        elif stored_results is not None:
                            stored_results[code] = tick_list
                    else:
                        reason = error or "no data"
                        if str(reason).lower() == "no data":
                            processed += 1
                            stats[code] = 0
                            consecutive_failures = 0
                            item_attempts.pop(code, None)
                            print(f"[{processed}/{total}] {code} {name} -> SKIP ({reason}) [{proxy_info}]")
                        else:
                            current_attempt = item_attempts[code] + 1
                            if current_attempt < self.item_retry_limit:
                                item_attempts[code] = current_attempt
                                requeue = True
                                print(f"[retry {current_attempt}/{self.item_retry_limit}] {code} {name} -> requeue ({reason}) [{proxy_info}]")
                            else:
                                processed += 1
                                item_attempts.pop(code, None)
                                fail_count += 1
                                consecutive_failures += 1
                                print(f"[{processed}/{total}] {code} {name} -> FAIL ({reason}) [{proxy_info}]")

                                if consecutive_failures >= self.fail_threshold:
                                    halt_error = f"连续失败 {consecutive_failures} 次，停止后续抓取。最近失败股票 {code}，原因: {reason}"
                                    halt_event.set()

                    if halt_event.is_set():
                        while not stock_queue.empty():
                            try:
                                stock_queue.get_nowait()
                                stock_queue.task_done()
                            except queue.Empty:
                                break

                stock_queue.task_done()

                if requeue and not halt_event.is_set():
                    stock_queue.put((code, name))
                elif effective_delay > 0 and not halt_event.is_set():
                    time.sleep(effective_delay)

        threads: List[threading.Thread] = []
        for worker_id in range(self.worker_count):
            thread = threading.Thread(target=worker, args=(worker_id,), daemon=True)
            threads.append(thread)
            thread.start()

        stock_queue.join()
        for thread in threads:
            thread.join()

        if save_to_db and result_queue is not None:
            result_queue.join()
            result_queue.put(None)
            if writer_thread:
                writer_thread.join()

        self.consecutive_failures = consecutive_failures

        if halt_error:
            raise RuntimeError(halt_error)

        duration_seconds = time.time() - start_time
        duration_minutes = duration_seconds / 60
        print(f"\n逐笔抓取完成: 成功 {success_count}, 失败 {fail_count}, 用时 {duration_minutes:.2f} 分钟")

        return {
            'processed': processed,
            'success': success_count,
            'fail': fail_count,
            'stats': stats,
            'results': stored_results,
            'duration_seconds': duration_seconds,
        }

    def query_quotes(self, stock_code: Optional[str] = None, start_date: Optional[str] = None,
                     end_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """查询行情数据。"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = 'SELECT * FROM stock_quotes WHERE 1=1'
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

    def get_history_kline(self, stock_code: str, start_date: str, end_date: str,
                          klt: str = '101', fqt: str = '1') -> Optional[List[Dict]]:
        """
        获取股票历史K线数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式：YYYY-MM-DD 或 YYYYMMDD
            end_date: 结束日期，格式：YYYY-MM-DD 或 YYYYMMDD
            klt: K线类型，101=日K，102=周K，103=月K
            fqt: 复权类型，0=不复权，1=前复权，2=后复权
            
        Returns:
            K线数据列表，失败返回None
        """
        try:
            # 判断市场代码
            if stock_code.startswith('6') or stock_code.startswith('688'):
                sec_id = f'1.{stock_code}'
            else:
                sec_id = f'0.{stock_code}'
            
            # 日期格式转换
            start_date_fmt = start_date.replace('-', '')
            end_date_fmt = end_date.replace('-', '')
            
            url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
            params = {
                'secid': sec_id,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100,f101,f102,f103,f104,f105,f106,f107,f108,f109,f110,f111,f112,f113,f114,f115,f116,f117,f118,f119,f120',
                'klt': klt,
                'fqt': fqt,
                'beg': start_date_fmt,
                'end': end_date_fmt,
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }
            
            response = self._http_get(url, params=params)
            data = response.json()
            
            if data.get('data') is None:
                print(f"未找到股票 {stock_code} 的历史K线数据")
                return None
            
            klines = data['data'].get('klines', [])
            if not klines:
                print(f"股票 {stock_code} 在 {start_date} 至 {end_date} 期间无K线数据")
                return None
            
            stock_name = data['data'].get('name', '')
            
            # 解析K线数据
            result = []
            for kline in klines:
                fields = kline.split(',')
                if len(fields) < 11:
                    continue
                
                # 基础字段解析
                kline_dict = {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'trade_date': fields[0],
                    'open_price': float(fields[1]) if fields[1] else None,
                    'close_price': float(fields[2]) if fields[2] else None,
                    'high_price': float(fields[3]) if fields[3] else None,
                    'low_price': float(fields[4]) if fields[4] else None,
                    'volume': float(fields[5]) if fields[5] else None,  # 成交量（手）
                    'turnover': float(fields[6]) if fields[6] else None,  # 成交额
                    'amplitude': float(fields[7]) if fields[7] else None,  # 振幅%
                    'change_percent': float(fields[8]) if fields[8] else None,  # 涨跌幅%
                    'change_amount': float(fields[9]) if fields[9] else None,  # 涨跌额
                    'turnover_rate': float(fields[10]) if fields[10] else None,  # 换手率%
                    'circulating_shares': None,  # 流通股本（股）
                    'circulating_market_value': None  # 流通市值（元）
                }
                
                # 解析流通股本（字段19）
                if len(fields) > 19 and fields[19]:
                    try:
                        circulating_shares = float(fields[19])
                        kline_dict['circulating_shares'] = circulating_shares
                        
                        # 计算流通市值 = 收盘价 × 流通股本
                        if kline_dict['close_price'] and circulating_shares:
                            kline_dict['circulating_market_value'] = kline_dict['close_price'] * circulating_shares
                    except (ValueError, TypeError):
                        pass
                
                result.append(kline_dict)
            
            return result
        
        except Exception as e:
            print(f"获取股票 {stock_code} 历史K线数据失败: {str(e)}")
            return None
    
    def save_history_kline_to_db(self, klines: List[Dict]) -> bool:
        """
        保存历史K线数据到数据库（保存到 stock_quotes 表）
        
        Args:
            klines: K线数据列表
            
        Returns:
            成功返回True，失败返回False
        """
        if not klines:
            return False
        
        try:
            # 历史K线数据保存到 quotes.db 的 stock_quotes 表
            with self._get_quotes_connection() as conn:
                cursor = conn.cursor()
                
                for kline in klines:
                    # 注意：current_price 使用 close_price，一些字段可能为 NULL
                    cursor.execute('''
                INSERT OR REPLACE INTO stock_quotes (
                    stock_code, stock_name, trade_date, 
                    current_price, open_price, close_price,
                    high_price, low_price, volume, turnover, 
                    amplitude, change_percent, change_amount, 
                    turnover_rate, circulating_market_value, 
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                ''', (
                    kline['stock_code'], kline['stock_name'], kline['trade_date'],
                    kline['close_price'],  # current_price = close_price
                    kline['open_price'], kline['close_price'], kline['high_price'],
                    kline['low_price'], kline['volume'], kline['turnover'],
                    kline['amplitude'], kline['change_percent'], kline['change_amount'],
                    kline['turnover_rate'], kline['circulating_market_value']
                ))
            
            return True
        
        except Exception as e:
            print(f"保存历史K线数据失败: {str(e)}")
            return False
    
    def crawl_history_kline(self, stock_code: str, start_date: str, end_date: str,
                           save_to_db: bool = True, klt: str = '101', fqt: str = '1') -> Optional[List[Dict]]:
        """
        爬取股票历史K线数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            save_to_db: 是否保存到数据库
            klt: K线类型，101=日K，102=周K，103=月K
            fqt: 复权类型，0=不复权，1=前复权，2=后复权
            
        Returns:
            K线数据列表
        """
        klines = self.get_history_kline(stock_code, start_date, end_date, klt, fqt)
        
        if klines and save_to_db:
            self.save_history_kline_to_db(klines)
        
        return klines
    
    def query_history_klines(self, stock_code: Optional[str] = None, start_date: Optional[str] = None,
                            end_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        查询历史K线数据（从 stock_quotes 表查询）
        
        Args:
            stock_code: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回记录数限制
            
        Returns:
            K线数据列表
        """
        # 历史K线数据从 quotes.db 的 stock_quotes 表查询
        with self._get_quotes_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            sql = 'SELECT * FROM stock_quotes WHERE 1=1'
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

# 便捷函数
def crawl_stock_quote(stock_code: str, db_path: str = 'stocks.db') -> Optional[Dict]:
    """快速爬取单只股票行情"""
    crawler = StockDataCrawler(db_path)
    return crawler.crawl_quote(stock_code)


def crawl_all_stock_quotes(db_path: str = 'stocks.db', delay: Optional[float] = None) -> List[Dict]:
    """快速爬取所有股票行情"""
    crawler = StockDataCrawler(db_path)
    return crawler.crawl_all_quotes(delay=delay)


if __name__ == '__main__':
    # 测试代码
    print("=" * 60)
    print("股票数据爬取模块测试")
    print("=" * 60)

    crawler = StockDataCrawler()

    # 测试1：爬取单只股票行情
    print("\n【测试1】爬取单只股票行情数据")
    print("-" * 60)
    quote = crawler.crawl_quote('600000')
    if quote:
        print(f"股票代码: {quote['stock_code']}")
        print(f"股票名称: {quote['stock_name']}")
        print(f"最新价: {quote['current_price']}")
        print(f"涨跌幅: {quote['change_percent']}%")
        print(f"成交量: {quote['volume']}")
        print(f"成交额: {quote['turnover']}")
        print(f"市盈率: {quote['pe_ratio']}")
        print(f"市净率: {quote['pb_ratio']}")

    # 测试2：查询已保存的行情数据
    print("\n【测试2】查询已保存的行情数据")
    print("-" * 60)
    quotes = crawler.query_quotes(stock_code='600000', limit=5)
    if quotes:
        for q in quotes:
            print(f"{q['trade_date']} - {q['stock_name']}: {q['current_price']} ({q['change_percent']}%)")

    print("\n提示：运行 crawler.crawl_all_quotes() 可以爬取所有股票行情数据")
