"""
Парсер для сайта goszakup.gov.kz
"""
import re
import logging
from typing import Dict, Any
from bs4 import BeautifulSoup

from .base_parser import BaseParser, SiteConfig

logger = logging.getLogger(__name__)


class GoszakupParser(BaseParser):
    """Парсер для сайта goszakup.gov.kz"""
    
    def get_last_page_number(self, soup: BeautifulSoup) -> int:
        """
        Извлекает номер последней страницы из пагинации для goszakup.gov.kz
        
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
    
    def extract_announcements_from_page(self, soup: BeautifulSoup, page_number: int) -> Dict[str, Dict[str, str]]:
        """
        Извлекает объявления со страницы goszakup.gov.kz
        
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
    
    def build_page_url(self, base_url: str, page_number: int) -> str:
        """
        Строит URL для конкретной страницы goszakup.gov.kz
        
        Args:
            base_url: Базовый URL
            page_number: Номер страницы
            
        Returns:
            URL для страницы
        """
        return f"{base_url}&page={page_number}"
