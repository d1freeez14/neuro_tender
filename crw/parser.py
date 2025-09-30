import requests
import time
import re
import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import config, configGS, PAGE_URL, HEADERS
from parsers import ParserFactory, ParserType
from parsers.base_parser import SiteConfig

logger = logging.getLogger(__name__)


@dataclass
class ParsingStats:
    """Статистика парсинга"""
    total_pages: int = 0
    processed_pages: int = 0
    total_announcements: int = 0
    errors: int = 0


def get_last_page_number(soup: BeautifulSoup) -> int:
    """
    Извлекает номер последней страницы из пагинации
    
    Args:
        soup: BeautifulSoup объект страницы
        
    Returns:
        Номер последней страницы или 1 если не найден
    """
    try:
        pagination = soup.find('ul', class_='pagination')
        if not pagination:
            logger.warning("Пагинация не найдена на странице")
            return 1
        
        page_links = pagination.find_all('a', href=True)
        last_page_link = None
        
        for link in page_links:
            href = link.get("href", "")
            if href.startswith("https://goszakup.gov.kz/ru/search/announce"):
                match = re.search(r"page=(\d+)", href)
                if match:
                    last_page_link = match.group(1)
        
        if last_page_link:
            page_num = int(last_page_link)
            logger.info(f"Найдено {page_num} страниц для обработки")
            return page_num
        
        logger.warning("Не удалось определить номер последней страницы")
        return 1
        
    except Exception as e:
        logger.error(f"Ошибка при определении количества страниц: {e}")
        return 1


class WebScraper:
    """Класс для веб-скрапинга с retry механизмом"""
    
    def __init__(self):
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Создает сессию с настройками retry"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=config.scraping.max_retries,
            backoff_factor=config.scraping.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def request_with_retry(self, url: str, retries: Optional[int] = None, pause: Optional[float] = None) -> Optional[requests.Response]:
        """
        Выполняет HTTP запрос с повторными попытками
        
        Args:
            url: URL для запроса
            retries: Количество попыток (по умолчанию из конфигурации)
            pause: Пауза между попытками (по умолчанию из конфигурации)
            
        Returns:
            Response объект или None в случае ошибки
        """
        retries = retries or config.scraping.max_retries
        pause = pause or config.scraping.retry_delay
        
        for attempt in range(1, retries + 1):
            try:
                logger.debug(f"Запрос к {url} (попытка {attempt}/{retries})")
                response = self.session.get(url, headers=HEADERS, timeout=30)
                
                if response.status_code == 200:
                    logger.debug(f"Успешный запрос к {url}")
                    return response
                elif response.status_code == 429:
                    logger.warning(f"Получен 429 Too Many Requests. Ожидание 60 секунд...")
                    time.sleep(60)
                else:
                    logger.error(f"Ошибка {response.status_code} при запросе {url}")
                    time.sleep(pause)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса (попытка {attempt}): {e}")
                if attempt < retries:
                    time.sleep(pause)
                    
        logger.critical(f"Не удалось получить данные с {url} после {retries} попыток")
        return None


def request_with_retry(url: str, retries: int = 3, pause: float = 5) -> Optional[requests.Response]:
    """
    Функция-обертка для обратной совместимости
    
    Args:
        url: URL для запроса
        retries: Количество попыток
        pause: Пауза между попытками
        
    Returns:
        Response объект или None в случае ошибки
    """
    scraper = WebScraper()
    return scraper.request_with_retry(url, retries, pause)


def process_page(page_url: str, parser_type: str = "goszakup") -> Dict[str, Dict[str, str]]:
    """
    Обрабатывает все страницы с объявлениями используя указанный парсер
    
    Args:
        page_url: URL первой страницы
        parser_type: Тип парсера для использования
        
    Returns:
        Словарь с данными объявлений
    """
    try:
        # Создание конфигурации сайта
        site_config = SiteConfig(
            name="goszakup.gov.kz",
            base_url="https://goszakup.gov.kz",
            search_url=page_url,
            parser_type=parser_type,
            request_delay=config.scraping.request_delay,
            max_retries=config.scraping.max_retries,
            retry_delay=config.scraping.retry_delay
        )
        
        # Создание парсера через фабрику
        parser = ParserFactory.create_parser(ParserType(parser_type), site_config)
        
        # Парсинг сайта
        result = parser.parse_site(page_url)
        
        return result.announcements
        
    except Exception as e:
        logger.error(f"Критическая ошибка в process_page: {e}")
        return {}


def process_multiple_sites() -> Dict[str, Dict[str, str]]:
    """
    Обрабатывает все включенные сайты
    
    Returns:
        Словарь с данными объявлений со всех сайтов
    """
    all_results = {}
    
    logger.info("Начало обработки множественных сайтов")
    
    for site_config in config.sites:
        if not site_config.enabled:
            logger.info(f"Сайт {site_config.name} отключен, пропускаем")
            continue
            
        logger.info(f"Обработка сайта: {site_config.name}")
        
        try:
            # Создание парсера через фабрику
            parser = ParserFactory.create_parser(ParserType(site_config.parser_type), site_config)
            
            # Парсинг сайта
            result = parser.parse_site(site_config.search_url)
            
            # Добавление префикса к ключам для избежания конфликтов
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


def _extract_announcements_from_page(soup: BeautifulSoup, page_number: int) -> Dict[str, Dict[str, str]]:
    """
    Извлекает объявления со страницы
    
    Args:
        soup: BeautifulSoup объект страницы
        page_number: Номер страницы для логирования
        
    Returns:
        Словарь с объявлениями со страницы
    """
    announcements = {}
    
    try:
        table_tag = soup.find('table', id='search-result')
        if not table_tag:
            logger.warning(f"Таблица с результатами не найдена на странице {page_number}")
            return announcements
        
        tbody = table_tag.find('tbody')
        if not tbody:
            logger.warning(f"Тело таблицы не найдено на странице {page_number}")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.debug(f"Найдено {len(rows)} строк в таблице на странице {page_number}")
        
        for row_num, row in enumerate(rows, 1):
            try:
                # Поиск ID объявления
                strong_tag = row.find("strong")
                if not strong_tag:
                    logger.debug(f"Строка {row_num} на странице {page_number}: не найден ID объявления")
                    continue
                
                announcement_id = strong_tag.text.strip()
                if not announcement_id:
                    logger.debug(f"Строка {row_num} на странице {page_number}: пустой ID объявления")
                    continue
                
                # Поиск названия объявления
                link_tag = row.find("a")
                if not link_tag:
                    logger.debug(f"Строка {row_num} на странице {page_number}: не найдена ссылка с названием")
                    continue
                
                name = link_tag.text.strip()
                if not name:
                    logger.debug(f"Строка {row_num} на странице {page_number}: пустое название")
                    continue
                
                announcements[announcement_id] = {
                    "name": name
                }
                
            except Exception as e:
                logger.warning(f"Ошибка при обработке строки {row_num} на странице {page_number}: {e}")
                continue
        
        logger.debug(f"Извлечено {len(announcements)} объявлений со страницы {page_number}")
        return announcements
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении объявлений со страницы {page_number}: {e}")
        return announcements


