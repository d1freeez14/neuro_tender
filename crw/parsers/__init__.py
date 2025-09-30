"""
Пакет парсеров с паттерном стратегия
"""
from .base_parser import BaseParser, SiteConfig, ParsingResult
from .goszakup_parser import GoszakupParser
from .site2_parser import Site2Parser
from .site3_parser import Site3Parser
from .parser_factory import ParserFactory, ParserType

__all__ = [
    'BaseParser',
    'SiteConfig', 
    'ParsingResult',
    'GoszakupParser',
    'Site2Parser',
    'Site3Parser',
    'ParserFactory',
    'ParserType'
]
