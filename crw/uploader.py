import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from file_utils import get_file_convert, get_file_md5

logger = logging.getLogger(__name__)


@dataclass
class UploadConfig:
    """Конфигурация для загрузки данных"""
    url: str = "https://portal.documentolog.kz/webservice/json/create_tented"
    username: str = os.getenv("DOCUMENTOLOG_USERNAME", "documentolog")
    password: str = os.getenv("DOCUMENTOLOG_PASSWORD", "")
    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.3


class DocumentUploader:
    """Класс для загрузки документов в систему Documentolog"""
    
    def __init__(self, config: Optional[UploadConfig] = None):
        self.config = config or UploadConfig()
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Создает сессию с настройками retry"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _validate_input_data(self, company_name: str, bin: str, message: str, 
                           file: str, md5sum: str, kratkij_ii_analiz_ts: str) -> None:
        """Валидация входных данных"""
        if not all([company_name, bin, message, file, md5sum]):
            raise ValueError("Все обязательные поля должны быть заполнены")
        
        if not bin.isdigit() or len(bin) != 12:
            raise ValueError("БИН должен содержать 12 цифр")
        
        if not file:
            raise ValueError("Файл не может быть пустым")
        
        if not md5sum or len(md5sum) != 32:
            raise ValueError("MD5 хеш должен содержать 32 символа")
    
    def upload(self, company_name: str, bin: str, message: str, 
               file: str, md5sum: str, kratkij_ii_analiz_ts: str) -> Optional[str]:
        """
        Загружает документ в систему Documentolog
        
        Args:
            company_name: Название компании
            bin: БИН компании
            message: Текст сообщения
            file: Файл в формате base64
            md5sum: MD5 хеш файла
            kratkij_ii_analiz_ts: Краткий анализ ТС
            
        Returns:
            ID документа или None в случае ошибки
        """
        logger.info(f"Начата загрузка документа для компании: {company_name} (БИН: {bin})")
        
        try:
            self._validate_input_data(company_name, bin, message, file, md5sum, kratkij_ii_analiz_ts)
        except ValueError as e:
            logger.error(f"Ошибка валидации данных: {e}")
            return None
        
        data = {
            'bin': bin,
            'nazvanie_kompanii': company_name,
            'tekst_soobsheniya': message,
            'tip_zayavki': {
                '12': 'Тендер'
            },
            'istochnik': {
                '21': 'goszakup.gov.kz'
            },
            'kratkij_ii_analiz_ts': kratkij_ii_analiz_ts,
            'teh_spetsifikatsiya': [
                {
                    'base64': file,
                    "name": "tech_spec.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "size": 0,
                    'md5sum': md5sum,
                }
            ]
        }
        
        headers = {'Content-Type': 'application/json'}
        
        try:
            logger.debug(f"Отправка запроса на {self.config.url}")
            response = self.session.post(
                self.config.url, 
                json=data, 
                headers=headers, 
                auth=(self.config.username, self.config.password), 
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            response_data = response.json()
            document_id = next(iter(response_data['data']['document_id']))
            
            logger.info(f"Документ успешно загружен. ID: {document_id}")
            return document_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при отправке запроса: {e}")
            return None
        except (KeyError, StopIteration) as e:
            logger.error(f"Ошибка при обработке ответа: {e}")
            logger.debug(f"Ответ сервера: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке документа: {e}")
            return None


def upload(company_name: str, bin: str, message: str, 
           file: str, md5sum: str, kratkij_ii_analiz_ts: str) -> Optional[str]:
    """
    Функция-обертка для обратной совместимости
    
    Args:
        company_name: Название компании
        bin: БИН компании
        message: Текст сообщения
        file: Файл в формате base64
        md5sum: MD5 хеш файла
        kratkij_ii_analiz_ts: Краткий анализ ТС
        
    Returns:
        ID документа или None в случае ошибки
    """
    uploader = DocumentUploader()
    return uploader.upload(company_name, bin, message, file, md5sum, kratkij_ii_analiz_ts)


def executor(item: Dict[str, Any]) -> Optional[str]:
    """
    Обрабатывает элемент тендера и загружает его в систему Documentolog
    
    Args:
        item: Словарь с данными о тендере
        
    Returns:
        ID документа или None в случае ошибки
    """
    announcement_id = item.get("announcement_id")
    if not announcement_id:
        logger.error("Отсутствует announcement_id в данных тендера")
        return None
    
    logger.info(f"Обработка тендера с ID: {announcement_id}")
    
    try:
        # Извлечение основных данных
        company_name = item.get("correspondent")
        bin = item.get("correspondent_id")
        
        if not company_name or not bin:
            logger.error(f"Отсутствуют обязательные данные для тендера {announcement_id}: company_name={company_name}, bin={bin}")
            return None
        
        # Форматирование дат
        try:
            started_at = datetime.fromisoformat(item.get("started_at")).strftime("%d.%m.%Y %H:%M")
            finished_at = datetime.fromisoformat(item.get("finished_at")).strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка при форматировании дат для тендера {announcement_id}: {e}")
            started_at = "Не указано"
            finished_at = "Не указано"
        
        kratkij_ii_analiz_ts = item.get("summary", "")
        
        # Формирование сообщения
        message = _format_tender_message(item, started_at, finished_at)
        
        # Получение файла и его MD5
        logger.debug(f"Получение файла для тендера {announcement_id}")
        file = get_file_convert(announcement_id)
        if not file:
            logger.error(f"Не удалось получить файл для тендера {announcement_id}")
            return None
        
        md5sum = get_file_md5(announcement_id)
        if not md5sum:
            logger.error(f"Не удалось получить MD5 хеш для тендера {announcement_id}")
            return None
        
        # Загрузка документа
        document_id = upload(company_name, bin, message, file, md5sum, kratkij_ii_analiz_ts)
        
        if document_id:
            logger.info(f"Тендер {announcement_id} успешно загружен с ID документа: {document_id}")
        else:
            logger.error(f"Не удалось загрузить тендер {announcement_id}")
        
        return document_id
        
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке тендера {announcement_id}: {e}")
        return None


def _format_tender_message(item: Dict[str, Any], started_at: str, finished_at: str) -> str:
    """
    Форматирует сообщение о тендере
    
    Args:
        item: Данные о тендере
        started_at: Дата начала в формате строки
        finished_at: Дата окончания в формате строки
        
    Returns:
        Отформатированное сообщение
    """
    fields = [
        ("Название", item.get("name", "Не указано")),
        ("Сумма закупки", item.get("amount", "Не указано")),
        ("Тип закупки", item.get("type", "Не указано")),
        ("Статус объявления", item.get("status", "Не указано")),
        ("Срок начала приема заявок", started_at),
        ("Срок окончания приема заявок", finished_at),
        ("Номер объявления", item.get("announcement_id", "Не указано")),
        ("Ссылка", item.get("link", "Не указано"))
    ]
    
    message_parts = [f"{field}: {value}" for field, value in fields]
    return "\n".join(message_parts)
