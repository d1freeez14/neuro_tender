"""
Базовый класс для парсеров с паттерном стратегия
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ParsingResult:
    """Результат парсинга"""
    announcements: Dict[str, Dict[str, str]]
    total_pages: int = 0
    processed_pages: int = 0
    errors: int = 0


@dataclass
class SiteConfig:
    """Конфигурация для конкретного сайта"""
    base_url: str
    search_url: str
    headers: Dict[str, str]
    request_delay: float = 2.0
    max_retries: int = 3
    retry_delay: float = 5.0


class BaseParser(ABC):
    """Абстрактный базовый класс для парсеров"""
    
    def __init__(self, config: SiteConfig):
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Создает сессию с настройками retry"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def request_with_retry(self, url: str) -> Optional[requests.Response]:
        """
        Выполняет HTTP запрос с повторными попытками
        
        Args:
            url: URL для запроса
            
        Returns:
            Response объект или None в случае ошибки
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.debug(f"Запрос к {url} (попытка {attempt}/{self.config.max_retries})")
                response = self.session.get(url, headers=self.config.headers, timeout=30)
                
                if response.status_code == 200:
                    logger.debug(f"Успешный запрос к {url}")
                    return response
                elif response.status_code == 429:
                    logger.warning(f"Получен 429 Too Many Requests. Ожидание 60 секунд...")
                    import time
                    time.sleep(60)
                else:
                    logger.error(f"Ошибка {response.status_code} при запросе {url}")
                    import time
                    time.sleep(self.config.retry_delay)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса (попытка {attempt}): {e}")
                if attempt < self.config.max_retries:
                    import time
                    time.sleep(self.config.retry_delay)
                    
        logger.critical(f"Не удалось получить данные с {url} после {self.config.max_retries} попыток")
        return None
    
    @abstractmethod
    def get_last_page_number(self, soup: BeautifulSoup) -> int:
        """
        Извлекает номер последней страницы из пагинации
        
        Args:
            soup: BeautifulSoup объект страницы
            
        Returns:
            Номер последней страницы или 1 если не найден
        """
        pass
    
    @abstractmethod
    def extract_announcements_from_page(self, soup: BeautifulSoup, page_number: int) -> Dict[str, Dict[str, str]]:
        """
        Извлекает объявления со страницы
        
        Args:
            soup: BeautifulSoup объект страницы
            page_number: Номер страницы для логирования
            
        Returns:
            Словарь с объявлениями со страницы
        """
        pass
    
    @abstractmethod
    def build_page_url(self, base_url: str, page_number: int) -> str:
        """
        Строит URL для конкретной страницы
        
        Args:
            base_url: Базовый URL
            page_number: Номер страницы
            
        Returns:
            URL для страницы
        """
        pass
    
    def parse_site(self, search_url: str) -> ParsingResult:
        """
        Основной метод парсинга сайта
        
        Args:
            search_url: URL для поиска
            
        Returns:
            Результат парсинга
        """
        result = ParsingResult(announcements={})
        
        logger.info(f"Начало парсинга сайта: {self.config.base_url}")
        
        try:
            # Первая страница для определения количества
            first_response = self.request_with_retry(search_url)
            if not first_response:
                logger.critical("Не удалось получить первую страницу. Прерывание.")
                return result

            soup = BeautifulSoup(first_response.text, "html.parser")
            last_page = self.get_last_page_number(soup)
            result.total_pages = last_page
            
            logger.info(f"Обнаружено {last_page} страниц для обработки")

            # Обработка каждой страницы
            for page_number in range(1, last_page + 1):
                try:
                    current_url = self.build_page_url(search_url, page_number)
                    logger.info(f"Обработка страницы {page_number}/{last_page}")
                    
                    # Пауза между запросами
                    import time
                    time.sleep(self.config.request_delay)
                    
                    response = self.request_with_retry(current_url)
                    if not response:
                        logger.error(f"Пропуск страницы {page_number} из-за ошибки запроса")
                        result.errors += 1
                        continue

                    soup = BeautifulSoup(response.text, "html.parser")
                    page_announcements = self.extract_announcements_from_page(soup, page_number)
                    
                    result.announcements.update(page_announcements)
                    result.processed_pages += 1
                    
                    logger.info(f"Страница {page_number}: найдено {len(page_announcements)} объявлений")
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке страницы {page_number}: {e}")
                    result.errors += 1
                    continue

            # Вывод статистики
            logger.info("=" * 50)
            logger.info("СТАТИСТИКА ПАРСИНГА")
            logger.info("=" * 50)
            logger.info(f"Всего страниц: {result.total_pages}")
            logger.info(f"Обработано страниц: {result.processed_pages}")
            logger.info(f"Найдено объявлений: {len(result.announcements)}")
            logger.info(f"Ошибок: {result.errors}")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            logger.error(f"Критическая ошибка в parse_site: {e}")
            return result
