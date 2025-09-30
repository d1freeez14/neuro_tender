# downloader.py
import os
import re
import json
import urllib.parse
import requests
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import config, configGS, HEADERS

logger = logging.getLogger(__name__)


@dataclass
class DownloadStats:
    """Статистика загрузки файлов"""
    total_files: int = 0
    downloaded_files: int = 0
    skipped_files: int = 0
    errors: int = 0


class FileDownloader:
    """Класс для загрузки файлов с retry механизмом"""
    
    def __init__(self):
        self.session = self._create_session()
        self.stats = DownloadStats()
    
    def _create_session(self) -> requests.Session:
        """Создает сессию с настройками retry"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=config.scraping.max_retries,
            backoff_factor=config.scraping.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def get_with_retries(self, url: str, max_retries: Optional[int] = None, delay: Optional[float] = None) -> Optional[requests.Response]:
        """
        Выполняет HTTP запрос с повторными попытками
        
        Args:
            url: URL для запроса
            max_retries: Количество попыток (по умолчанию из конфигурации)
            delay: Пауза между попытками (по умолчанию из конфигурации)
            
        Returns:
            Response объект или None в случае ошибки
        """
        max_retries = max_retries or config.scraping.max_retries
        delay = delay or config.scraping.retry_delay
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Запрос к {url} (попытка {attempt + 1}/{max_retries})")
                response = self.session.get(url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                logger.warning(f"Ошибка запроса к {url}, попытка {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"Достигнуто максимальное количество попыток для {url}")
                    self.stats.errors += 1
        
        return None


def get_with_retries(url: str, max_retries: int = 3, delay: float = 2) -> Optional[requests.Response]:
    """
    Функция-обертка для обратной совместимости
    
    Args:
        url: URL для запроса
        max_retries: Количество попыток
        delay: Пауза между попытками
        
    Returns:
        Response объект или None в случае ошибки
    """
    downloader = FileDownloader()
    return downloader.get_with_retries(url, max_retries, delay)


def get_announcement_info(announcement_id: str) -> Optional[Dict[str, Any]]:
    """
    Получает информацию об объявлении
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        Словарь с информацией об объявлении или None в случае ошибки
    """
    try:
        company_url = f"https://goszakup.gov.kz/ru/announce/index/{announcement_id}"
        logger.info(f"[{announcement_id}] Получение информации об объявлении")
        
        downloader = FileDownloader()
        response = downloader.get_with_retries(company_url)
        if not response:
            logger.error(f"[{announcement_id}] Не удалось получить страницу объявления")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Извлечение полей из формы
        fields = {
            "Номер объявления": None,
            "Наименование объявления": None,
            "Статус объявления": None,
            "Срок начала приема заявок": None,
            "Срок окончания приема заявок": None,
        }

        for label in fields:
            label_element = soup.find('label', string=label)
            if label_element:
                input_tag = label_element.find_next('input')
                if input_tag and input_tag.has_attr('value'):
                    fields[label] = input_tag['value']

        # Извлечение полей из таблицы
        table_fields = {
            "Способ проведения закупки": None,
            "Организатор": None,
            "Сумма закупки": None,
        }

        for row in soup.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td and th.get_text(strip=True) in table_fields:
                table_fields[th.get_text(strip=True)] = td.get_text(strip=True)

        # Обработка организатора
        correspondent_text = table_fields["Организатор"] or ""
        correspondent_id = None
        match = re.search(r"\b\d{12}\b", correspondent_text)
        if match:
            correspondent_id = match.group(0)
            correspondent_text = correspondent_text.replace(correspondent_id, "").strip()

        result = {
            "announcement_id": fields["Номер объявления"] or announcement_id,
            "name": fields["Наименование объявления"],
            "amount": table_fields["Сумма закупки"],
            "type": table_fields["Способ проведения закупки"],
            "status": fields["Статус объявления"],
            "correspondent": correspondent_text,
            "correspondent_id": correspondent_id,
            "started_at": fields["Срок начала приема заявок"],
            "finished_at": fields["Срок окончания приема заявок"],
            "techspec_summary": "",
            "link": company_url
        }
        
        logger.info(f"[{announcement_id}] Информация об объявлении получена успешно")
        return result
        
    except Exception as e:
        logger.error(f"[{announcement_id}] Ошибка при получении информации об объявлении: {e}")
        return None


def download_file(announcement_id: str, category_id: str, raw_id: str) -> bool:
    """
    Загружает файлы для указанной категории объявления
    
    Args:
        announcement_id: ID объявления
        category_id: ID категории файлов
        raw_id: ID для создания папки
        
    Returns:
        True если загрузка успешна, False в противном случае
    """
    try:
        download_url = f"https://goszakup.gov.kz/ru/announce/actionAjaxModalShowFiles/{announcement_id}/{category_id}"
        logger.info(f"[{announcement_id}] Загрузка файлов категории {category_id}")
        
        downloader = FileDownloader()
        response = downloader.get_with_retries(download_url)
        if not response:
            logger.error(f"[{announcement_id}] Не удалось получить список файлов")
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        file_links = soup.find_all("a", href=True)
        
        if not file_links:
            logger.warning(f"[{announcement_id}] Файлы не найдены для категории {category_id}")
            return False
        
        # Создание папки для сохранения
        save_folder = config.data_dir / raw_id
        save_folder.mkdir(parents=True, exist_ok=True)
        
        downloaded_count = 0
        
        for link in file_links:
            href = link["href"]
            if "signature" in href:
                continue

            # HEAD-запрос для получения имени файла
            try:
                head_response = downloader.session.head(href, allow_redirects=True, timeout=30)
                head_response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"[{announcement_id}] HEAD-запрос не удался для {href}: {e}")
                continue

            content_disposition = head_response.headers.get('Content-Disposition')
            ext = ".pdf"
            file_name = f"{category_id}{ext}"

            if content_disposition:
                filename_utf8 = re.findall(r"filename\*=UTF-8''(.+)", content_disposition)
                if filename_utf8:
                    file_name = urllib.parse.unquote(filename_utf8[0])
                    _, ext = os.path.splitext(file_name)
                else:
                    fallback = re.findall(r'filename="(.+?)"', content_disposition)
                    if fallback:
                        file_name = fallback[0]
                        _, ext = os.path.splitext(file_name)

            # Генерация уникального имени файла
            file_path = save_folder / f"{category_id}{ext}"
            counter = 1
            while file_path.exists():
                file_path = save_folder / f"{category_id}_{counter}{ext}"
                counter += 1

            if file_path.exists():
                logger.info(f"[{announcement_id}] Файл уже существует, пропускаем: {file_path}")
                downloader.stats.skipped_files += 1
                continue

            # Пауза перед загрузкой
            time.sleep(3)

            try:
                file_response = downloader.session.get(href, stream=True, timeout=60)
                file_response.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"[{announcement_id}] Ошибка при скачивании {href}: {e}")
                downloader.stats.errors += 1
                continue

            try:
                with open(file_path, "wb") as f:
                    for chunk in file_response.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                logger.info(f"[{announcement_id}] Файл сохранён: {file_path}")
                downloaded_count += 1
                downloader.stats.downloaded_files += 1
                
            except Exception as e:
                logger.error(f"[{announcement_id}] Ошибка при сохранении {file_path}: {e}")
                downloader.stats.errors += 1
                continue

        logger.info(f"[{announcement_id}] Загружено {downloaded_count} файлов для категории {category_id}")
        return downloaded_count > 0
        
    except Exception as e:
        logger.error(f"[{announcement_id}] Ошибка при загрузке файлов: {e}")
        return False


def process_by_announcement_id(announcement_id: str) -> Optional[Dict[str, Any]]:
    """
    Обрабатывает объявление: загружает файлы и получает информацию
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        Словарь с информацией об объявлении или None в случае ошибки
    """
    try:
        raw_id = announcement_id  # для директории
        announcement_id = announcement_id[:-2]
        page_url = f"https://goszakup.gov.kz/ru/announce/index/{announcement_id}?tab=documents"
        
        logger.info(f"[{announcement_id}] Обработка объявления")
        
        downloader = FileDownloader()
        response = downloader.get_with_retries(page_url)
        if not response:
            logger.error(f"[{announcement_id}] Не удалось загрузить страницу документов")
            return None

        time.sleep(2)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table.table-bordered tr")

        found = False
        for row in rows:
            columns = row.find_all("td")
            if len(columns) < 3:
                continue
                
            doc_name = columns[0].get_text(strip=True)
            if "Техническая спецификация" in doc_name or "Техническое задание" in doc_name:
                button = columns[2].find("button", onclick=True)
                if button:
                    match = re.search(r"actionModalShowFiles\(\d+,(\d+)\)", button["onclick"])
                    if match:
                        category_id = match.group(1)
                        logger.info(f"[{announcement_id}] Найдена техническая спецификация, категория: {category_id}")
                        
                        if download_file(announcement_id, category_id, raw_id):
                            found = True
                            logger.info(f"[{announcement_id}] Файлы технической спецификации загружены")
                        else:
                            logger.warning(f"[{announcement_id}] Не удалось загрузить файлы технической спецификации")
                        break

        if not found:
            logger.warning(f"[{announcement_id}] Техническая спецификация не найдена")

        # Получение информации об объявлении
        info = get_announcement_info(announcement_id)
        if info:
            logger.info(f"[{announcement_id}] Обработка объявления завершена успешно")
        else:
            logger.error(f"[{announcement_id}] Не удалось получить информацию об объявлении")
            
        return info
        
    except Exception as e:
        logger.error(f"[{announcement_id}] Ошибка при обработке объявления: {e}")
        return None
