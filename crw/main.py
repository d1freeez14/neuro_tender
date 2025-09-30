import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from file_utils import get_results_from_json, save_results_to_json
from scorer import request_to_model, final_score
from parser import process_page, process_multiple_sites
from config import config, configGS, PAGE_URL
from downloader import process_by_announcement_id
from uploader import executor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Статистика обработки"""
    total_processed: int = 0
    stage1_success: int = 0
    stage2_success: int = 0
    uploads_successful: int = 0
    errors: int = 0


class TenderProcessor:
    """Основной класс для обработки тендеров"""
    
    def __init__(self):
        self.stats = ProcessingStats()
        self.stage1_success = {}
        self.stage2_success = {}
        self.already_processed = {}
    
    def load_processed_data(self) -> None:
        """Загружает уже обработанные данные"""
        self.already_processed = get_results_from_json(configGS['filtered'])
        logger.info(f"Загружено {len(self.already_processed)} уже обработанных записей")
    
    def process_announcement(self, announcement_id: str, entry: Dict[str, Any]) -> None:
        """
        Обрабатывает одно объявление
        
        Args:
            announcement_id: ID объявления
            entry: Данные объявления
        """
        try:
            self.stats.total_processed += 1
            
            # Добавляем в список обработанных
            self.already_processed[announcement_id] = {'name': entry['name']}
            save_results_to_json(self.already_processed, configGS['filtered'])
            
            # Первый этап - проверка названия
            logger.info(f"[{announcement_id}] Начата обработка: {entry['name'][:100]}...")
            result1 = request_to_model(entry['name'])
            entry['result1'] = result1
            logger.info(f"[{announcement_id}] Результат модели 1: {result1}")
            
            if result1 == 'возможно':
                self.stats.stage1_success += 1
                self.stage1_success[announcement_id] = True
                
                # Второй этап - детальный анализ
                logger.info(f"[{announcement_id}] Переход ко второму этапу")
                info = process_by_announcement_id(announcement_id)
                
                if info is None:
                    logger.error(f"[{announcement_id}] Не удалось получить информацию об объявлении")
                    self.stats.errors += 1
                    return
                
                result2 = final_score(announcement_id)
                entry['result2'] = result2['decision']
                logger.info(f"[{announcement_id}] Результат модели 2: {result2['decision']}")
                
                if result2['decision'] == 'да':
                    self.stats.stage2_success += 1
                    info['summary'] = result2['summary']
                    self.stage2_success[announcement_id] = info
                    
                    # Загрузка в систему
                    logger.info(f"[{announcement_id}] Загрузка в систему Documentolog")
                    document_id = executor(info)
                    
                    if document_id:
                        self.stats.uploads_successful += 1
                        logger.info(f"[{announcement_id}] Успешно загружено с ID: {document_id}")
                    else:
                        logger.error(f"[{announcement_id}] Ошибка при загрузке")
                        self.stats.errors += 1
            else:
                logger.info(f"[{announcement_id}] Пропущено на первом этапе")
                
        except Exception as e:
            logger.error(f"[{announcement_id}] Ошибка при обработке: {e}")
            self.stats.errors += 1
    
    def save_results(self) -> None:
        """Сохраняет результаты обработки"""
        try:
            save_results_to_json(self.stage1_success, configGS['stage1s'])
            save_results_to_json(self.stage2_success, configGS['stage2s'])
            save_results_to_json(self.already_processed, configGS['filtered'])
            logger.info("Результаты сохранены успешно")
        except Exception as e:
            logger.error(f"Ошибка при сохранении результатов: {e}")
    
    def print_stats(self, elapsed_time: float) -> None:
        """Выводит статистику обработки"""
        minutes = int(elapsed_time // 60)
        seconds = round(elapsed_time % 60, 2)
        
        logger.info("=" * 50)
        logger.info("СТАТИСТИКА ОБРАБОТКИ")
        logger.info("=" * 50)
        logger.info(f"Время выполнения: {minutes} мин {seconds} сек")
        logger.info(f"Всего обработано: {self.stats.total_processed}")
        logger.info(f"Прошли этап 1: {self.stats.stage1_success}")
        logger.info(f"Прошли этап 2: {self.stats.stage2_success}")
        logger.info(f"Успешно загружено: {self.stats.uploads_successful}")
        logger.info(f"Ошибок: {self.stats.errors}")
        
        if self.stats.total_processed > 0:
            success_rate = (self.stats.uploads_successful / self.stats.total_processed) * 100
            logger.info(f"Процент успешных загрузок: {success_rate:.1f}%")
        logger.info("=" * 50)


def main():
    """Основная функция приложения"""
    start_time = time.time()
    
    logger.info("Запуск системы обработки тендеров")
    logger.info(f"URL для парсинга: {PAGE_URL}")
    
    try:
        # Инициализация процессора
        processor = TenderProcessor()
        processor.load_processed_data()
        
        # Получение данных с сайта(ов)
        logger.info("Начало парсинга страниц")
        
        # Проверяем, есть ли включенные сайты
        enabled_sites = [site for site in config.sites if site.enabled]
        
        if len(enabled_sites) > 1:
            # Обработка множественных сайтов
            logger.info(f"Обработка {len(enabled_sites)} сайтов")
            full_data = process_multiple_sites()
        else:
            # Обработка одного сайта (обратная совместимость)
            logger.info("Обработка одного сайта")
            full_data = process_page(PAGE_URL)
        
        if not full_data:
            logger.error("Не удалось получить данные с сайта(ов)")
            return
        
        logger.info(f"Получено {len(full_data)} объявлений для обработки")
        
        # Обработка каждого объявления
        for announcement_id, entry in full_data.items():
            if announcement_id in processor.already_processed:
                logger.debug(f"[{announcement_id}] Уже обработано, пропускаем")
                continue
            
            # Извлекаем оригинальный ID (убираем префикс сайта если есть)
            original_id = announcement_id
            if '_' in announcement_id:
                original_id = announcement_id.split('_', 1)[1]
            
            processor.process_announcement(original_id, entry)
        
        # Сохранение результатов
        processor.save_results()
        
        # Вывод статистики
        end_time = time.time()
        elapsed_time = end_time - start_time
        processor.print_stats(elapsed_time)
        
    except KeyboardInterrupt:
        logger.info("Обработка прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в main(): {e}")
        raise


if __name__ == "__main__":
    main()
