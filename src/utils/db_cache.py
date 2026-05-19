#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库缓存工具 - 提供快速的本地数据查询

功能：
1. 获取股票流通股本（用于换手率计算）
2. 获取股票概念标签（用于热点题材分析）
3. 批量加载优化

作者: AI Architect
日期: 2025-11-05
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger


class DBCache:
    """数据库缓存管理器"""
    
    def __init__(self):
        """初始化数据库连接"""
        # 尝试多个可能的数据库路径
        possible_paths = [
            Path.cwd() / 'data' / 'stock_trading.db',
            Path(__file__).parent.parent.parent / 'data' / 'stock_trading.db',
            Path(__file__).resolve().parent.parent.parent / 'data' / 'stock_trading.db',
        ]
        
        self.db_path = None
        for path in possible_paths:
            if path.exists():
                self.db_path = path
                break
        
        if not self.db_path:
            logger.warning("⚠️ 未找到stock_trading.db数据库文件")
        
        # 缓存数据
        self._float_shares_cache = None
        self._concepts_cache = None
    
    def get_float_shares(self, stock_code: str) -> Optional[float]:
        """
        获取股票流通股本
        
        Args:
            stock_code: 股票代码（如'000001'）
        
        Returns:
            流通股本（股），如果不存在返回None
        """
        if not self.db_path:
            return None
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT float_shares FROM stock_basic_info WHERE stock_code=?",
                (stock_code,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            return float(result[0]) if result and result[0] else None
            
        except Exception as e:
            logger.warning(f"获取流通股本失败 {stock_code}: {e}")
            return None
    
    def get_all_float_shares(self) -> Dict[str, float]:
        """
        批量获取所有股票的流通股本
        
        Returns:
            {股票代码: 流通股本} 的映射字典
        """
        if self._float_shares_cache is not None:
            return self._float_shares_cache
        
        if not self.db_path:
            return {}
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT stock_code, float_shares FROM stock_basic_info")
            
            self._float_shares_cache = {
                row[0]: float(row[1]) for row in cursor.fetchall() if row[1]
            }
            
            conn.close()
            logger.info(f"✅ 加载了{len(self._float_shares_cache)}只股票的流通股本数据")
            
            return self._float_shares_cache
            
        except Exception as e:
            logger.warning(f"批量加载流通股本失败: {e}")
            return {}
    
    def get_stock_concepts(self, stock_code: str) -> List[str]:
        """
        获取股票的概念标签
        
        Args:
            stock_code: 股票代码（如'000001'）
        
        Returns:
            概念标签列表（如['区块链', '互联金融', 'HS300_']）
        """
        if not self.db_path:
            return []
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT tag FROM stock_concepts WHERE stock_code=? AND category='所属板块'",
                (stock_code,)
            )
            
            concepts = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return concepts
            
        except Exception as e:
            logger.warning(f"获取概念标签失败 {stock_code}: {e}")
            return []
    
    def get_all_stock_concepts(self) -> Dict[str, List[str]]:
        """
        批量获取所有股票的概念标签
        
        Returns:
            {股票代码: [概念标签列表]} 的映射字典
        """
        if self._concepts_cache is not None:
            return self._concepts_cache
        
        if not self.db_path:
            return {}
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT stock_code, tag FROM stock_concepts WHERE category='所属板块'")
            
            self._concepts_cache = {}
            for row in cursor.fetchall():
                stock_code, tag = row
                if stock_code not in self._concepts_cache:
                    self._concepts_cache[stock_code] = []
                self._concepts_cache[stock_code].append(tag)
            
            conn.close()
            logger.info(f"✅ 加载了{len(self._concepts_cache)}只股票的概念标签数据")
            
            return self._concepts_cache
            
        except Exception as e:
            logger.warning(f"批量加载概念标签失败: {e}")
            return {}
    
    def clear_cache(self):
        """清除缓存"""
        self._float_shares_cache = None
        self._concepts_cache = None


# 全局单例
_db_cache_instance = None


def get_db_cache() -> DBCache:
    """获取数据库缓存单例"""
    global _db_cache_instance
    if _db_cache_instance is None:
        _db_cache_instance = DBCache()
    return _db_cache_instance

