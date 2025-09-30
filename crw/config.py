import logging
import os
import colorlog
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScrapingConfig:
    """Конфигурация для парсинга goszakup.gov.kz"""
    count_record: int = 2000
    financial_year: int = 2025
    amount_from: int = 100000
    request_delay: float = 2.0
    max_retries: int = 3
    retry_delay: float = 5.0


@dataclass
class SiteConfig:
    """Конфигурация для конкретного сайта"""
    name: str
    base_url: str
    search_url: str
    parser_type: str = "goszakup"
    enabled: bool = True
    request_delay: float = 2.0
    max_retries: int = 3
    retry_delay: float = 5.0


@dataclass
class ModelConfig:
    """Конфигурация для работы с моделью"""
    name: str = 'llama3:8b-instruct-q5_K_M'
    base_url: str = "http://dgollama:11434"
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 30


@dataclass
class DocumentConfig:
    """Конфигурация для работы с документами"""
    chunk_size: int = 3000
    max_chunks: int = 5
    keyword_threshold: int = 2
    supported_extensions: tuple = ('.docx', '.pdf')


@dataclass
class AppConfig:
    """Основная конфигурация приложения"""
    scraping: ScrapingConfig = ScrapingConfig()
    model: ModelConfig = ModelConfig()
    document: DocumentConfig = DocumentConfig()
    sites: list[SiteConfig] = None
    
    def __post_init__(self):
        # Создаем директории при инициализации
        self._create_directories()
        self._setup_logging()
        # Инициализируем сайты если не заданы
        if self.sites is None:
            self.sites = self._get_default_sites()
    
    def _create_directories(self):
        """Создает необходимые директории"""
        parent_dir = Path(__file__).parent.parent
        self.base_dir = parent_dir
        self.log_dir = parent_dir / "log"
        self.data_dir = parent_dir / "cnt" / "goszakup.gov.kz"
        
        self.log_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """Настраивает логирование"""
        log_file_path = self.log_dir / "logs.log"
        
        # Формат логов
        log_format = "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s%(reset)s"
        file_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        
        # Настройка корневого логгера
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        
        # Очистка существующих обработчиков
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Файловый обработчик
        file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(file_format))
        file_handler.setLevel(logging.DEBUG)
        
        # Консольный обработчик с цветами
        console_handler = colorlog.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(log_format)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # Добавление обработчиков
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Отключение избыточных логов
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("pytesseract").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
    
    def _get_default_sites(self) -> list[SiteConfig]:
        """Возвращает конфигурацию сайтов по умолчанию"""
        return [
            SiteConfig(
                name="goszakup.gov.kz",
                base_url="https://goszakup.gov.kz",
                search_url=PAGE_URL,
                parser_type="goszakup",
                enabled=True
            ),
            SiteConfig(
                name="site2.example.com",
                base_url="https://site2.example.com",
                search_url="https://site2.example.com/search",
                parser_type="site2",
                enabled=False  # Отключен по умолчанию
            ),
            SiteConfig(
                name="site3.example.com", 
                base_url="https://site3.example.com",
                search_url="https://site3.example.com/search",
                parser_type="site3",
                enabled=False  # Отключен по умолчанию
            )
        ]


# Создание глобального экземпляра конфигурации
config = AppConfig()

# Обратная совместимость - старые переменные
count_record = config.scraping.count_record
financial_year = config.scraping.financial_year
amount_from = config.scraping.amount_from
model_name = config.model.name

# URL для парсинга
PAGE_URL = (
    f"https://goszakup.gov.kz/ru/search/announce?"
    f"filter%5Bname%5D=&filter%5Bcustomer%5D=&filter%5Bnumber%5D=&"
    f"filter%5Byear%5D={financial_year}&"
    f"filter%5Bstatus%5D%5B%5D=210&filter%5Bstatus%5D%5B%5D=230&"
    f"filter%5Bstatus%5D%5B%5D=280&filter%5Bstatus%5D%5B%5D=220&"
    f"filter%5Bstatus%5D%5B%5D=240&filter%5Bstatus%5D%5B%5D=245&"
    f"filter%5Bamount_from%5D={amount_from}&filter%5Bamount_to%5D=&"
    f"filter%5Btrade_type%5D=&filter%5Btype%5D=&"
    f"filter%5Bstart_date_from%5D=&filter%5Bstart_date_to%5D=&"
    f"filter%5Bend_date_from%5D=&filter%5Bend_date_to%5D=&"
    f"filter%5Bitog_date_from%5D=&filter%5Bitog_date_to%5D=&"
    f"smb=&count_record={count_record}"
)

# HTTP заголовки
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Конфигурация файлов (обратная совместимость)
configGS = {
    'stage1s': 'stage1_success.json',
    'stage2s': 'stage2_success.json', 
    'stage3s': '',
    'stage1f': 'stage1_failure.json',
    'stage2f': 'stage2_failure.json',
    'stage3f': '',
    'stage1p': 'stage1_process.json',
    'stage2p': 'stage2_process.json',
    'stage3p': '',
    'dataset': 'dataset.json',
    'filtered': 'filtered.json',
    'processed': 'processed.json'
}

# Логгер для использования в других модулях
logger = logging.getLogger(__name__)
