"""
Пример использования новой архитектуры парсеров
"""
import logging
from parsers import ParserFactory, ParserType, SiteConfig
from config import config

logger = logging.getLogger(__name__)


def example_single_site_parsing():
    """Пример парсинга одного сайта"""
    logger.info("=== Пример парсинга одного сайта ===")
    
    # Создание конфигурации для goszakup.gov.kz
    site_config = SiteConfig(
        name="goszakup.gov.kz",
        base_url="https://goszakup.gov.kz",
        search_url="https://goszakup.gov.kz/ru/search/announce?filter%5Bname%5D=&filter%5Bcustomer%5D=&filter%5Bnumber%5D=&filter%5Byear%5D=2025&filter%5Bstatus%5D%5B%5D=210&filter%5Bstatus%5D%5B%5D=230&filter%5Bstatus%5D%5B%5D=280&filter%5Bstatus%5D%5B%5D=220&filter%5Bstatus%5D%5B%5D=240&filter%5Bstatus%5D%5B%5D=245&filter%5Bamount_from%5D=100000&filter%5Bamount_to%5D=&filter%5Btrade_type%5D=&filter%5Btype%5D=&filter%5Bstart_date_from%5D=&filter%5Bstart_date_to%5D=&filter%5Bend_date_from%5D=&filter%5Bend_date_to%5D=&filter%5Bitog_date_from%5D=&filter%5Bitog_date_to%5D=&smb=&count_record=2000",
        parser_type="goszakup",
        enabled=True
    )
    
    # Создание парсера
    parser = ParserFactory.create_parser(ParserType.GOSZAKUP, site_config)
    
    # Парсинг сайта
    result = parser.parse_site(site_config.search_url)
    
    logger.info(f"Найдено объявлений: {len(result.announcements)}")
    logger.info(f"Обработано страниц: {result.processed_pages}")
    logger.info(f"Ошибок: {result.errors}")
    
    return result


def example_multiple_sites_parsing():
    """Пример парсинга множественных сайтов"""
    logger.info("=== Пример парсинга множественных сайтов ===")
    
    all_results = {}
    
    for site_config in config.sites:
        if not site_config.enabled:
            logger.info(f"Сайт {site_config.name} отключен, пропускаем")
            continue
            
        logger.info(f"Обработка сайта: {site_config.name}")
        
        try:
            # Создание парсера
            parser = ParserFactory.create_parser(ParserType(site_config.parser_type), site_config)
            
            # Парсинг сайта
            result = parser.parse_site(site_config.search_url)
            
            # Добавление префикса к ключам
            prefixed_results = {}
            for key, value in result.announcements.items():
                prefixed_key = f"{site_config.name}_{key}"
                prefixed_results[prefixed_key] = value
            
            all_results.update(prefixed_results)
            
            logger.info(f"Сайт {site_config.name}: найдено {len(result.announcements)} объявлений")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сайта {site_config.name}: {e}")
            continue
    
    logger.info(f"Всего найдено объявлений: {len(all_results)}")
    return all_results


def example_custom_parser():
    """Пример создания и регистрации кастомного парсера"""
    logger.info("=== Пример кастомного парсера ===")
    
    # Создание нового типа парсера
    from enum import Enum
    
    class CustomParserType(Enum):
        CUSTOM = "custom"
    
    # Создание кастомного парсера
    from parsers.base_parser import BaseParser
    from bs4 import BeautifulSoup
    from typing import Dict
    
    class CustomParser(BaseParser):
        def get_last_page_number(self, soup: BeautifulSoup) -> int:
            # Простая реализация - всегда возвращаем 1
            return 1
        
        def extract_announcements_from_page(self, soup: BeautifulSoup, page_number: int) -> Dict[str, Dict[str, str]]:
            # Простая реализация - возвращаем пустой словарь
            return {}
        
        def build_page_url(self, base_url: str, page_number: int) -> str:
            return f"{base_url}?page={page_number}"
    
    # Регистрация парсера
    ParserFactory.register_parser(CustomParserType.CUSTOM, CustomParser)
    
    # Создание конфигурации
    site_config = SiteConfig(
        name="custom-site.com",
        base_url="https://custom-site.com",
        search_url="https://custom-site.com/search",
        parser_type="custom",
        enabled=True
    )
    
    # Использование кастомного парсера
    parser = ParserFactory.create_parser(CustomParserType.CUSTOM, site_config)
    result = parser.parse_site(site_config.search_url)
    
    logger.info(f"Кастомный парсер: найдено {len(result.announcements)} объявлений")
    
    return result


def main():
    """Основная функция с примерами"""
    logger.info("Запуск примеров использования новой архитектуры")
    
    # Пример 1: Парсинг одного сайта
    # result1 = example_single_site_parsing()
    
    # Пример 2: Парсинг множественных сайтов
    # result2 = example_multiple_sites_parsing()
    
    # Пример 3: Кастомный парсер
    # result3 = example_custom_parser()
    
    logger.info("Примеры завершены")


if __name__ == "__main__":
    main()
