"""
数据库自动备份工具

功能：
1. 每天自动备份数据库
2. 保留最近30天的备份
3. 支持手动备份和恢复
"""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger


class DatabaseBackup:
    """数据库备份管理器"""
    
    def __init__(self, db_path: str = "data/stock_trading.db", backup_dir: str = "data/backups"):
        """
        初始化备份管理器
        
        Args:
            db_path: 数据库文件路径
            backup_dir: 备份目录路径
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, backup_name: str = None) -> str:
        """
        创建数据库备份
        
        Args:
            backup_name: 备份文件名（可选，默认使用时间戳）
        
        Returns:
            备份文件路径
        """
        if not self.db_path.exists():
            logger.error(f"❌ 数据库文件不存在: {self.db_path}")
            return None
        
        # 生成备份文件名
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"stock_trading_{timestamp}.db"
        
        backup_path = self.backup_dir / backup_name
        
        try:
            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            
            # 获取文件大小
            file_size = backup_path.stat().st_size / 1024 / 1024  # MB
            
            logger.success(f"✅ 数据库备份成功: {backup_path} ({file_size:.2f}MB)")
            return str(backup_path)
        
        except Exception as e:
            logger.error(f"❌ 数据库备份失败: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        从备份恢复数据库
        
        Args:
            backup_path: 备份文件路径
        
        Returns:
            是否恢复成功
        """
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            logger.error(f"❌ 备份文件不存在: {backup_path}")
            return False
        
        try:
            # 先备份当前数据库（以防万一）
            if self.db_path.exists():
                current_backup = self.create_backup(f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                logger.info(f"📦 已备份当前数据库: {current_backup}")
            
            # 恢复备份
            shutil.copy2(backup_file, self.db_path)
            
            logger.success(f"✅ 数据库恢复成功: {backup_path} -> {self.db_path}")
            return True
        
        except Exception as e:
            logger.error(f"❌ 数据库恢复失败: {e}")
            return False
    
    def list_backups(self) -> list:
        """
        列出所有备份文件
        
        Returns:
            备份文件列表（按时间倒序）
        """
        backups = []
        
        for backup_file in self.backup_dir.glob("*.db"):
            file_stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size": file_stat.st_size / 1024 / 1024,  # MB
                "created": datetime.fromtimestamp(file_stat.st_ctime),
                "modified": datetime.fromtimestamp(file_stat.st_mtime),
            })
        
        # 按修改时间倒序排序
        backups.sort(key=lambda x: x["modified"], reverse=True)
        
        return backups
    
    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """
        清理旧备份文件
        
        Args:
            keep_days: 保留最近多少天的备份
        
        Returns:
            删除的备份数量
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for backup_file in self.backup_dir.glob("*.db"):
            file_stat = backup_file.stat()
            file_modified = datetime.fromtimestamp(file_stat.st_mtime)
            
            if file_modified < cutoff_date:
                try:
                    backup_file.unlink()
                    logger.info(f"🗑️ 删除旧备份: {backup_file.name} ({file_modified.strftime('%Y-%m-%d')})")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"❌ 删除备份失败: {backup_file.name}, {e}")
        
        if deleted_count > 0:
            logger.success(f"✅ 已清理 {deleted_count} 个旧备份文件")
        else:
            logger.info(f"ℹ️ 没有需要清理的旧备份")
        
        return deleted_count


def main():
    """主函数：演示备份功能"""
    backup_manager = DatabaseBackup()
    
    print(f"\n{'='*80}")
    print(f"📦 数据库备份管理器")
    print(f"{'='*80}\n")
    
    # 创建备份
    print("1️⃣ 创建备份...")
    backup_path = backup_manager.create_backup()
    
    # 列出所有备份
    print(f"\n2️⃣ 备份文件列表:")
    backups = backup_manager.list_backups()
    
    if backups:
        print(f"\n{'序号':<4} {'文件名':<40} {'大小(MB)':<10} {'创建时间':<20}")
        print(f"{'-'*80}")
        for i, backup in enumerate(backups, 1):
            print(f"{i:<4} {backup['name']:<40} {backup['size']:<10.2f} {backup['created'].strftime('%Y-%m-%d %H:%M:%S'):<20}")
    else:
        print("❌ 没有找到备份文件")
    
    # 清理旧备份
    print(f"\n3️⃣ 清理旧备份（保留30天）...")
    deleted_count = backup_manager.cleanup_old_backups(keep_days=30)
    
    print(f"\n{'='*80}")
    print(f"✅ 备份管理完成")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

