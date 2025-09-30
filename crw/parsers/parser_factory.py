"""
Фабрика парсеров для выбора стратегии
"""
import logging
from typing import Dict, Type
from enum import Enum

from .base_parser import BaseParser, SiteConfig
from .goszakup_parser import GoszakupParser
from .site2_parser import Site2Parser
from .site3_parser import Site3Parser

logger = logging.getLogger(__name__)


class ParserType(Enum):
    """Типы парсеров"""
    GOSZAKUP = "goszakup"
    SITE2 = "site2"
    SITE3 = "site3"


class ParserFactory:
    """Фабрика для создания парсеров"""
    
    _parsers: Dict[ParserType, Type[BaseParser]] = {
        ParserType.GOSZAKUP: GoszakupParser,
        ParserType.SITE2: Site2Parser,
        ParserType.SITE3: Site3Parser,
    }
    
    @classmethod
    def create_parser(cls, parser_type: ParserType, config: SiteConfig) -> BaseParser:
        """
        Создает парсер указанного типа
        
        Args:
            parser_type: Тип парсера
            config: Конфигурация сайта
            
        Returns:
            Экземпляр парсера
            
        Raises:
            ValueError: Если тип парсера не поддерживается
        """
        if parser_type not in cls._parsers:
            raise ValueError(f"Неподдерживаемый тип парсера: {parser_type}")
        
        parser_class = cls._parsers[parser_type]
        logger.info(f"Создание парсера типа: {parser_type.value}")
        return parser_class(config)
    
    @classmethod
    def get_available_parsers(cls) -> list[ParserType]:
        """
        Возвращает список доступных парсеров
        
        Returns:
            Список доступных типов парсеров
        """
        return list(cls._parsers.keys())
    
    @classmethod
    def register_parser(cls, parser_type: ParserType, parser_class: Type[BaseParser]) -> None:
        """
        Регистрирует новый парсер
        
        Args:
            parser_type: Тип парсера
            parser_class: Класс парсера
        """
        cls._parsers[parser_type] = parser_class
        logger.info(f"Зарегистрирован новый парсер: {parser_type.value}")
