"""
AKShare 适配器 — ZhituAPI 的开源替代实现

当 ZHITU_API_TOKEN 未配置时，ZhituAPI() 会自动返回 AKShareAdapter 实例。
覆盖项目最常用的接口子集，字段格式与 ZhituAPI 一致，调用方无需改动。

AKShare 是 GitHub 上 22k+ star 的中国金融数据库 (MIT 协议)，无需 token：
    pip install akshare

覆盖接口（10 个）：
- get_stock_list / get_stock_basic_info
- get_real_time_broker / get_real_time_public / get_real_time_multi_broker
- get_history_timeframe / get_latest_timeframe
- get_history_macd / get_history_kdj / get_history_ma
- get_limit_up_pool / get_limit_down_pool
- get_five_level_quotes / get_index_realtime
- get_tick_by_tick / get_stock_sectors（开源版返回空，避免阻塞调用方）
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# AKShare 延迟导入（避免无 akshare 时整个项目无法启动）
_ak = None


def _akshare():
    global _ak
    if _ak is None:
        try:
            import akshare
            _ak = akshare
        except ImportError as e:
            raise ImportError("AKShare 未安装。请运行: pip install akshare") from e
    return _ak


def _strip_market_suffix(symbol: str) -> str:
    """000001.SZ → 000001"""
    if not symbol:
        return ""
    if "." in symbol:
        return symbol.split(".")[0]
    return symbol


def _infer_exchange(code: str) -> str:
    if code.startswith(("60", "68", "90")):
        return "sh"
    if code.startswith(("00", "30", "20")):
        return "sz"
    if code.startswith(("43", "83", "87", "88")):
        return "bj"
    return "sz"


def _safe_float(x, default=0.0) -> float:
    try:
        if x is None or x == "" or x == "-":
            return default
        return float(x)
    except (ValueError, TypeError):
        return default


def _safe_int(x, default=0) -> int:
    try:
        if x is None or x == "" or x == "-":
            return default
        return int(float(x))
    except (ValueError, TypeError):
        return default


class AKShareAdapter:
    """AKShare 数据源适配器，对外接口与 ZhituAPI 一致"""

    _TIMEFRAME_MAP = {"d": "daily", "w": "weekly", "m": "monthly"}

    def __init__(self):
        logger.info("✅ AKShareAdapter 初始化（开源数据源，无需 token）")
        # 兼容 ZhituAPI 的若干属性
        self.base_url = "akshare://local"
        self.token = "akshare"
        self.rate_limit_per_minute = 999999
        self.request_times = []
        # 实时行情缓存（3 秒）
        self._spot_cache = None
        self._spot_cache_t = 0

    # ====== 股票列表 / 基础信息 ======

    def get_stock_list(self) -> List[Dict[str, Any]]:
        # 重试 2 次（AKShare 拉全量股票偶发中断）
        last_err = None
        for attempt in range(3):
            try:
                df = _akshare().stock_info_a_code_name()
                result = []
                for _, row in df.iterrows():
                    code = str(row["code"]).zfill(6)
                    result.append({
                        "stock_code": code,
                        "stock_name": str(row["name"]),
                        "exchange": _infer_exchange(code),
                        "dm": code,
                        "mc": str(row["name"]),
                    })
                return result
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        logger.error(f"AKShare get_stock_list 多次失败: {last_err}")
        return []

    def get_stock_basic_info(self, stock_symbol: str) -> Dict[str, Any]:
        code = _strip_market_suffix(stock_symbol)
        try:
            df = _akshare().stock_individual_info_em(symbol=code)
            info = {row["item"]: row["value"] for _, row in df.iterrows()}
            return {
                "ii": code,
                "name": info.get("股票简称", ""),
                "od": str(info.get("上市时间", "")),
                "fv": _safe_float(info.get("流通股")),
                "tv": _safe_float(info.get("总股本")),
                "pk": 0.01,
                "is": 0,
            }
        except Exception as e:
            logger.warning(f"AKShare get_stock_basic_info({code}) 失败: {e}")
            return {}

    # ====== 实时行情 ======

    def _spot_em_cached(self):
        # 3 秒内复用缓存
        if self._spot_cache is not None and time.time() - self._spot_cache_t <= 3:
            return self._spot_cache
        # 拉取 + 重试 2 次（AKShare 抓东财偶发连接中断）
        last_err = None
        for attempt in range(3):
            try:
                self._spot_cache = _akshare().stock_zh_a_spot_em()
                self._spot_cache_t = time.time()
                return self._spot_cache
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        logger.error(f"AKShare spot_em 多次失败: {last_err}")
        # 返回上一次成功的缓存（如果有），否则空 DataFrame
        if self._spot_cache is not None:
            return self._spot_cache
        import pandas as pd
        return pd.DataFrame()

    def _row_to_realtime(self, row) -> Dict[str, Any]:
        return {
            "dm": str(row["代码"]).zfill(6),
            "mc": str(row["名称"]),
            "current_price": _safe_float(row.get("最新价")),
            "change_pct": _safe_float(row.get("涨跌幅")),
            "change_percent": _safe_float(row.get("涨跌幅")),
            "open_price": _safe_float(row.get("今开")),
            "high_price": _safe_float(row.get("最高")),
            "low_price": _safe_float(row.get("最低")),
            "pre_close_price": _safe_float(row.get("昨收")),
            "volume": _safe_int(row.get("成交量")),
            "turnover_amount": _safe_float(row.get("成交额")),
            "turnover_rate": _safe_float(row.get("换手率")),
            "pe_ratio": _safe_float(row.get("市盈率-动态")),
            "float_market_cap": _safe_float(row.get("流通市值")),
            "total_market_cap": _safe_float(row.get("总市值")),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_real_time_broker(self, stock_code: str) -> Dict[str, Any]:
        code = _strip_market_suffix(stock_code)
        try:
            df = self._spot_em_cached()
            match = df[df["代码"] == code]
            if match.empty:
                return {}
            return self._row_to_realtime(match.iloc[0])
        except Exception as e:
            logger.error(f"AKShare get_real_time_broker({code}) 失败: {e}")
            return {}

    def get_real_time_public(self, stock_code: str) -> Dict[str, Any]:
        return self.get_real_time_broker(stock_code)

    def get_real_time_multi_broker(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        if not stock_codes:
            return {}
        try:
            df = self._spot_em_cached()
            codes = [_strip_market_suffix(c) for c in stock_codes]
            result = {}
            for code in codes:
                match = df[df["代码"] == code]
                if not match.empty:
                    result[code] = self._row_to_realtime(match.iloc[0])
            return result
        except Exception as e:
            logger.error(f"AKShare get_real_time_multi_broker 失败: {e}")
            return {}

    # ====== K 线 ======

    def get_history_timeframe(self, stock_symbol: str, timeframe: str = "d",
                              adjust_type: str = "n", start_time: str = None,
                              end_time: str = None) -> List[Dict[str, Any]]:
        code = _strip_market_suffix(stock_symbol)
        period = self._TIMEFRAME_MAP.get(timeframe, "daily")
        adjust = {"n": "", "f": "qfq", "b": "hfq"}.get(adjust_type, "")
        end = (end_time or datetime.now().strftime("%Y%m%d"))[:8]
        if start_time:
            start = start_time[:8]
        else:
            now = datetime.now()
            start = now.replace(year=now.year - 1).strftime("%Y%m%d")

        # 重试 3 次（东方财富偶发切连接）
        last_err = None
        for attempt in range(3):
            try:
                df = _akshare().stock_zh_a_hist(
                    symbol=code, period=period,
                    start_date=start, end_date=end, adjust=adjust,
                )
                return [
                    {
                        "t": str(row["日期"]),
                        "o": _safe_float(row["开盘"]),
                        "h": _safe_float(row["最高"]),
                        "l": _safe_float(row["最低"]),
                        "c": _safe_float(row["收盘"]),
                        "v": _safe_int(row["成交量"]),
                        "e": _safe_float(row["成交额"]),
                        "zf": _safe_float(row.get("涨跌幅")),
                    }
                    for _, row in df.iterrows()
                ]
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        logger.error(f"AKShare get_history_timeframe({code}) 重试 3 次失败: {last_err}")
        return []

    def get_latest_timeframe(self, stock_symbol: str, timeframe: str = "d",
                             adjust_type: str = "n", limit: int = None) -> List[Dict[str, Any]]:
        data = self.get_history_timeframe(stock_symbol, timeframe, adjust_type)
        if limit and len(data) > limit:
            return data[-limit:]
        return data

    # ====== 技术指标（本地计算） ======

    def _load_kline_df(self, stock_symbol: str, timeframe: str, adjust_type: str, latest_count):
        import pandas as pd
        klines = self.get_history_timeframe(stock_symbol, timeframe, adjust_type)
        if not klines:
            return None
        if latest_count:
            klines = klines[-(latest_count + 60):]  # 多取暖机数据
        return pd.DataFrame(klines)

    def get_history_macd(self, stock_symbol: str, timeframe: str = "d",
                         adjust_type: str = "n", start_time: str = None,
                         end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        try:
            df = self._load_kline_df(stock_symbol, timeframe, adjust_type, latest_count)
            if df is None or df.empty:
                return []
            close = df["c"].astype(float)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd = (dif - dea) * 2
            result = [
                {
                    "t": df.iloc[i]["t"],
                    "diff": round(float(dif.iloc[i]), 4),
                    "dea": round(float(dea.iloc[i]), 4),
                    "macd": round(float(macd.iloc[i]), 4),
                    "ema12": round(float(ema12.iloc[i]), 4),
                    "ema26": round(float(ema26.iloc[i]), 4),
                }
                for i in range(len(df))
            ]
            return result[-latest_count:] if latest_count else result
        except Exception as e:
            logger.error(f"AKShare get_history_macd({stock_symbol}) 失败: {e}")
            return []

    def get_history_kdj(self, stock_symbol: str, timeframe: str = "d",
                        adjust_type: str = "n", start_time: str = None,
                        end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        try:
            df = self._load_kline_df(stock_symbol, timeframe, adjust_type, latest_count)
            if df is None or df.empty:
                return []
            high = df["h"].astype(float)
            low = df["l"].astype(float)
            close = df["c"].astype(float)
            low_n = low.rolling(window=9, min_periods=1).min()
            high_n = high.rolling(window=9, min_periods=1).max()
            rng = (high_n - low_n).replace(0, 1)
            rsv = (close - low_n) / rng * 100
            k = rsv.ewm(com=2, adjust=False).mean()
            d = k.ewm(com=2, adjust=False).mean()
            j = 3 * k - 2 * d
            result = [
                {
                    "t": df.iloc[i]["t"],
                    "k": round(float(k.iloc[i]), 4),
                    "d": round(float(d.iloc[i]), 4),
                    "j": round(float(j.iloc[i]), 4),
                }
                for i in range(len(df))
            ]
            return result[-latest_count:] if latest_count else result
        except Exception as e:
            logger.error(f"AKShare get_history_kdj({stock_symbol}) 失败: {e}")
            return []

    def get_history_ma(self, stock_symbol: str, timeframe: str = "d",
                       adjust_type: str = "n", start_time: str = None,
                       end_time: str = None, latest_count: int = None) -> List[Dict[str, Any]]:
        try:
            df = self._load_kline_df(stock_symbol, timeframe, adjust_type, latest_count)
            if df is None or df.empty:
                return []
            close = df["c"].astype(float)
            periods = [5, 10, 20, 30, 60, 120, 200, 250]
            mas = {p: close.rolling(window=p, min_periods=1).mean() for p in periods}
            result = []
            for i in range(len(df)):
                row = {"t": df.iloc[i]["t"]}
                for p in periods:
                    row[f"ma{p}"] = round(float(mas[p].iloc[i]), 4)
                result.append(row)
            return result[-latest_count:] if latest_count else result
        except Exception as e:
            logger.error(f"AKShare get_history_ma({stock_symbol}) 失败: {e}")
            return []

    # ====== 涨停 / 跌停 ======

    def get_limit_up_pool(self, trade_date: str) -> List[Dict[str, Any]]:
        date_str = trade_date.replace("-", "")
        try:
            df = _akshare().stock_zt_pool_em(date=date_str)
            return [
                {
                    "stock_code": str(row["代码"]).zfill(6),
                    "stock_name": str(row["名称"]),
                    "dm": str(row["代码"]).zfill(6),
                    "mc": str(row["名称"]),
                    "price": _safe_float(row.get("最新价")),
                    "change_pct": _safe_float(row.get("涨跌幅")),
                    "turnover_amount": _safe_float(row.get("成交额")),
                    "float_market_cap": _safe_float(row.get("流通市值")),
                    "total_market_cap": _safe_float(row.get("总市值")),
                    "turnover_rate": _safe_float(row.get("换手率")),
                    "consecutive_limit_up": _safe_int(row.get("连板数"), default=1),
                    "first_limit_time": str(row.get("首次封板时间", "")),
                    "last_limit_time": str(row.get("最后封板时间", "")),
                    "limit_up_funds": _safe_float(row.get("封板资金")),
                    "limit_up_stats": str(row.get("涨停统计", "")),
                    "industry": str(row.get("所属行业", "")),
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_limit_up_pool({trade_date}) 失败: {e}")
            return []

    def get_limit_down_pool(self, trade_date: str) -> List[Dict[str, Any]]:
        date_str = trade_date.replace("-", "")
        try:
            df = _akshare().stock_zt_pool_dtgc_em(date=date_str)
            return [
                {
                    "stock_code": str(row["代码"]).zfill(6),
                    "stock_name": str(row["名称"]),
                    "price": _safe_float(row.get("最新价")),
                    "change_pct": _safe_float(row.get("涨跌幅")),
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            logger.error(f"AKShare get_limit_down_pool({trade_date}) 失败: {e}")
            return []

    # ====== 五档盘口 ======

    def get_five_level_quotes(self, stock_code: str) -> Dict[str, Any]:
        code = _strip_market_suffix(stock_code)
        try:
            df = _akshare().stock_bid_ask_em(symbol=code)
            info = {row["item"]: row["value"] for _, row in df.iterrows()}
            return {
                "pb": [_safe_float(info.get(f"buy_{i}")) for i in range(1, 6)],
                "vb": [_safe_int(info.get(f"buy_{i}_vol")) for i in range(1, 6)],
                "ps": [_safe_float(info.get(f"sell_{i}")) for i in range(1, 6)],
                "vs": [_safe_int(info.get(f"sell_{i}_vol")) for i in range(1, 6)],
                "t": datetime.now().strftime("%H:%M:%S"),
            }
        except Exception as e:
            logger.warning(f"AKShare get_five_level_quotes({code}) 失败: {e}")
            return {}

    # ====== 指数 ======

    def get_index_realtime(self, index_code: str) -> Dict[str, Any]:
        try:
            code = _strip_market_suffix(index_code).lower()
            df = _akshare().stock_zh_index_spot_em()
            for prefix in ("sh", "sz", ""):
                target = prefix + code
                match = df[df["代码"].astype(str).str.lower() == target]
                if not match.empty:
                    row = match.iloc[0]
                    return {
                        "current_price": _safe_float(row["最新价"]),
                        "change_pct": _safe_float(row["涨跌幅"]),
                        "name": str(row["名称"]),
                    }
            return {}
        except Exception as e:
            logger.warning(f"AKShare get_index_realtime({index_code}) 失败: {e}")
            return {}

    # ====== 未实现的接口（保持调用方不崩） ======

    def get_tick_by_tick(self, stock_code: str) -> List[Dict[str, Any]]:
        logger.debug("get_tick_by_tick 在开源版未实现（请使用 src/tools/tick_data_fetcher.py 的东方财富接口）")
        return []

    def get_stock_sectors(self, stock_code: str) -> List[Dict[str, Any]]:
        return []

    def get_history_boll(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return []

    def get_fund_flow(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return []

    def get_real_time_all_broker(self) -> List[Dict[str, Any]]:
        try:
            df = self._spot_em_cached()
            return [self._row_to_realtime(row) for _, row in df.iterrows()]
        except Exception as e:
            logger.error(f"AKShare get_real_time_all_broker 失败: {e}")
            return []

    def get_real_time_multi_public(self, stock_codes: List[str]) -> List[Dict[str, Any]]:
        result = self.get_real_time_multi_broker(stock_codes)
        return list(result.values())

    def get_real_time_all_public(self) -> List[Dict[str, Any]]:
        return self.get_real_time_all_broker()
