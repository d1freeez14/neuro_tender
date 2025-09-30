import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from config import config

logger = logging.getLogger(__name__)


@dataclass
class RemovalStats:
    """Статистика удаления файлов"""
    total_files: int = 0
    removed_files: int = 0
    errors: int = 0


class FileRemover:
    """Класс для безопасного удаления файлов"""
    
    def __init__(self):
        self.stats = RemovalStats()
    
    def remove_old_files(self, days_old: int = 30, extensions: Optional[List[str]] = None) -> bool:
        """
        Удаляет старые файлы из директории данных
        
        Args:
            days_old: Возраст файлов в днях для удаления
            extensions: Список расширений файлов для удаления
            
        Returns:
            True если операция успешна, False в противном случае
        """
        try:
            if extensions is None:
                extensions = ['.tmp', '.log', '.bak']
            
            logger.info(f"Начало удаления файлов старше {days_old} дней")
            
            data_dir = config.data_dir
            if not data_dir.exists():
                logger.warning(f"Директория данных не найдена: {data_dir}")
                return False
            
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            removed_count = 0
            
            for file_path in data_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in extensions:
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            removed_count += 1
                            logger.debug(f"Удален файл: {file_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {file_path}: {e}")
                        self.stats.errors += 1
            
            logger.info(f"Удалено {removed_count} файлов")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении старых файлов: {e}")
            return False
    
    def cleanup_empty_directories(self) -> bool:
        """
        Удаляет пустые директории
        
        Returns:
            True если операция успешна, False в противном случае
        """
        try:
            logger.info("Начало очистки пустых директорий")
            
            data_dir = config.data_dir
            if not data_dir.exists():
                logger.warning(f"Директория данных не найдена: {data_dir}")
                return False
            
            removed_count = 0
            
            # Проходим по всем поддиректориям снизу вверх
            for dir_path in sorted(data_dir.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                if dir_path.is_dir() and dir_path != data_dir:
                    try:
                        if not any(dir_path.iterdir()):  # Директория пуста
                            dir_path.rmdir()
                            removed_count += 1
                            logger.debug(f"Удалена пустая директория: {dir_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении директории {dir_path}: {e}")
                        self.stats.errors += 1
            
            logger.info(f"Удалено {removed_count} пустых директорий")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при очистке пустых директорий: {e}")
            return False
    
    def get_directory_size(self, path: Optional[Path] = None) -> int:
        """
        Получает размер директории в байтах
        
        Args:
            path: Путь к директории (по умолчанию data_dir)
            
        Returns:
            Размер в байтах
        """
        try:
            if path is None:
                path = config.data_dir
            
            if not path.exists():
                return 0
            
            total_size = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            return total_size
            
        except Exception as e:
            logger.error(f"Ошибка при подсчете размера директории {path}: {e}")
            return 0
    
    def format_size(self, size_bytes: int) -> str:
        """
        Форматирует размер в байтах в читаемый вид
        
        Args:
            size_bytes: Размер в байтах
            
        Returns:
            Отформатированная строка с размером
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"


def cleanup_data_directory(days_old: int = 30) -> bool:
    """
    Функция для очистки директории данных
    
    Args:
        days_old: Возраст файлов в днях для удаления
        
    Returns:
        True если операция успешна, False в противном случае
    """
    try:
        remover = FileRemover()
        
        # Получаем размер до очистки
        size_before = remover.get_directory_size()
        logger.info(f"Размер директории до очистки: {remover.format_size(size_before)}")
        
        # Удаляем старые файлы
        if not remover.remove_old_files(days_old):
            logger.error("Ошибка при удалении старых файлов")
            return False
        
        # Удаляем пустые директории
        if not remover.cleanup_empty_directories():
            logger.error("Ошибка при удалении пустых директорий")
            return False
        
        # Получаем размер после очистки
        size_after = remover.get_directory_size()
        logger.info(f"Размер директории после очистки: {remover.format_size(size_after)}")
        logger.info(f"Освобождено места: {remover.format_size(size_before - size_after)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при очистке директории данных: {e}")
        return False


if __name__ == "__main__":
    # Пример использования
    cleanup_data_directory(30)
