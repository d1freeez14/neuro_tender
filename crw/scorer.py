from datetime import datetime
from time import sleep
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

import requests
import json
import logging
import re

from file_utils import get_docx_or_pdf_content_by_announcement_id, save_results_to_json
from config import config, configGS

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Ответ от модели"""
    decision: str
    summary: str = ""
    confidence: float = 0.0

class ModelClient:
    """Клиент для работы с моделью"""
    
    def __init__(self):
        self.base_url = config.model.base_url
        self.model_name = config.model.name
        self.timeout = config.model.timeout
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос к модели
        
        Args:
            endpoint: Конечная точка API
            data: Данные для отправки
            
        Returns:
            Ответ от модели или None в случае ошибки
        """
        try:
            url = f"{self.base_url}/{endpoint}"
            headers = {"Content-Type": "application/json"}
            
            logger.debug(f"Запрос к модели: {endpoint}")
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к модели: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при парсинге ответа модели: {e}")
            return None


def request_to_model(description: str, seed: int = 12) -> str:
    """
    Запрашивает у модели оценку описания тендера
    
    Args:
        description: Описание тендера
        seed: Семя для воспроизводимости
        
    Returns:
        Результат оценки: "возможно", "нет" или "неизвестно"
    """
    try:
        logger.info(f"Запрос к модели для оценки: {description[:100]}...")
        
        client = ModelClient()
        
        base_prompt = f"""
        Ты — специалист по тендерам. Оцени описание закупки и ответь строго одним словом:

        - Ответь «возможно», если описание связано с электронным документооборотом (СЭД), информационными системами, программным обеспечением, автоматизацией документооборота, сопровождением АИС, внедрением или поддержкой ИТ-решений — даже если это указано неявно.
        - Ответь «нет», если речь идёт о товарах, строительстве, ремонтах, обучении, канцелярии, топливе, дезинфекции, мебели, принтерах, аренде транспорта, оборудовании, видеонаблюдении, ИБ или кибербезопасности.

        Примеры:

        Описание: Услуги по сопровождению программы  
        Ответ: возможно

        Описание: Услуги по предоставлению доступа к автоматизированной информационной системе  
        Ответ: возможно

        Описание: Documentolog электрондық құжат айналымының ақпараттық жүйесіне қол жеткізу және сервис ұсыну  
        Ответ: возможно

        Описание: Приобретение кубков для награждения  
        Ответ: нет

        Описание: Текущий ремонт помещений здания  
        Ответ: нет

        Описание: Приобретение бумаги для офисной техники  
        Ответ: нет

        Теперь оцени следующее описание:

        Описание: {description}  
        Ответ:
        """.strip()

        data = {
            "model": config.model.name,
            "prompt": base_prompt,
            "temperature": config.model.temperature,
            "seed": seed,
            "stream": False
        }

        response = client._make_request("api/generate", data)
        if not response:
            logger.error("Не удалось получить ответ от модели")
            return "неизвестно"

        raw_output = response.get("response", "").strip().lower()
        logger.debug(f"Ответ модели: {raw_output}")

        if "возможно" in raw_output:
            result = "возможно"
        elif "нет" in raw_output:
            result = "нет"
        else:
            result = "неизвестно"
        
        logger.info(f"Результат оценки модели: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при запросе к модели: {e}")
        return "неизвестно"




def get_summary_from_model(text: str) -> str:
    """
    Получает краткое резюме текста от модели
    
    Args:
        text: Текст для суммирования
        
    Returns:
        Краткое резюме или пустая строка в случае ошибки
    """
    try:
        logger.debug(f"Запрос резюме для текста длиной {len(text)} символов")
        
        client = ModelClient()
        
        data = {
            "model": config.model.name,
            "temperature": 0.7,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — эксперт по аналитике текста. Твоя задача — суммировать текст кратко, чётко и по существу. "
                        "Выделяй только ключевые идеи, избегай лишних деталей, повторов и воды. "
                        "Результат должен быть в виде делового краткого резюме, не более 2–3 предложений."
                    )
                },
                {
                    "role": "user",
                    "content": "Описание: " + text
                }
            ]
        }
        
        response = client._make_request("v1/chat/completions", data)
        if not response:
            logger.error("Не удалось получить резюме от модели")
            return ""
        
        summary = response["choices"][0]["message"]["content"].strip()
        logger.debug(f"Получено резюме длиной {len(summary)} символов")
        return summary
        
    except Exception as e:
        logger.error(f"Ошибка при получении резюме: {e}")
        return ""

def get_translate_of_summary(text):
    url = "http://dgollama:11434/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_name,
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Переведи на русский язык данный текст, можешь сократить"
                )
            },
            {
                "role": "user",
                "content": "Текст: \n" + text
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def final_request_to_model(text):
    url = "http://dgollama:11434/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_name,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты — специалист по тендерам. Твоя задача — определить, может ли описание относиться "
                    "к системе электронного документооборота (СЭД), даже если это не указано явно. "
                    "Если считаешь, что в теории описание может "
                    "разработки программного обеспечения для  обработки документов, документооборота и т.п.,  "
                    "то ответь \"да\" . Если описание явно не связано с ИТ или автоматизацией (например, ремонт техники, "
                    "поставка оборудования, услуги уборки и пр.), то ответь \"нет\"."
                )
            },
            {
                "role": "user",
                "content": "Описание: " + text
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip().lower()

KEYWORDS = [
    "электронный документооборот", "система электронного документооборота", "электронная цифровая подпись",
    "целостность документа", "подлинность документа", "удостоверяющий центр", "регистрационно-контрольная карточка",
    "согласование документа", "регистрация документов", "внутренние документы" , 'эцп' , "сэд"
]

def final_score(announcement_id: str) -> ModelResponse:
    """
    Выполняет финальную оценку объявления на основе содержимого документов
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        ModelResponse с решением и резюме
    """
    logger.info(f"Обработка объявления ID: {announcement_id}")
    
    try:
        # Получение текста документов
        doc_text = get_docx_or_pdf_content_by_announcement_id(announcement_id)
        if not doc_text:
            logger.warning(f"Не удалось получить текст для ID {announcement_id}")
            _save_result(announcement_id, final_score="нет")
            return ModelResponse(decision="нет", summary="")

        # Проверка наличия ключевых слов
        if not _has_enough_keywords(doc_text):
            logger.info(f"[{announcement_id}] Недостаточно ключевых слов")
            _save_result(announcement_id, final_score="нет")
            return ModelResponse(decision="нет", summary="")

        # Обработка текста в зависимости от длины
        if len(doc_text) <= config.document.chunk_size:
            logger.info(f"[{announcement_id}] Текст короткий (<= {config.document.chunk_size}), отправка напрямую")
            summary, decision = _process_short_text(doc_text)
        else:
            logger.info(f"[{announcement_id}] Текст длинный (>{config.document.chunk_size}), разбиение и обработка")
            summary, decision = _process_long_text(doc_text)

        # Сохранение результата
        if decision == "да":
            _save_result(announcement_id, summary=summary)
        else:
            _save_result(announcement_id, final_score="нет")
        
        # Перевод резюме
        translated_summary = get_translate_of_summary(summary)
        
        logger.info(f"[{announcement_id}] Финальная оценка: {decision}")
        return ModelResponse(decision=decision, summary=translated_summary)
        
    except Exception as e:
        logger.error(f"[{announcement_id}] Ошибка при финальной оценке: {e}")
        return ModelResponse(decision="нет", summary="")

def _has_enough_keywords(text: str, threshold: Optional[int] = None) -> bool:
    """
    Проверяет наличие достаточного количества ключевых слов в тексте
    
    Args:
        text: Текст для проверки
        threshold: Пороговое значение (по умолчанию из конфигурации)
        
    Returns:
        True если найдено достаточно ключевых слов
    """
    threshold = threshold or config.document.keyword_threshold
    count = sum(1 for keyword in KEYWORDS if keyword.lower() in text.lower())
    logger.info(f"🔍 Ключевых слов найдено: {count} (порог: {threshold})")
    return count >= threshold


def _process_short_text(text: str) -> tuple[str, str]:
    """
    Обрабатывает короткий текст
    
    Args:
        text: Текст для обработки
        
    Returns:
        Кортеж (резюме, решение)
    """
    summary = get_summary_from_model(text)
    decision = _retry_model_request(lambda: final_request_to_model(text))
    logger.info(f"✅ Ответ модели (короткий текст): {decision}")
    return summary, _normalize_decision(decision)


def _process_long_text(text: str, chunk_size: Optional[int] = None, max_chunks: Optional[int] = None) -> tuple[str, str]:
    """
    Обрабатывает длинный текст, разбивая его на части
    
    Args:
        text: Текст для обработки
        chunk_size: Размер части (по умолчанию из конфигурации)
        max_chunks: Максимальное количество частей (по умолчанию из конфигурации)
        
    Returns:
        Кортеж (резюме, решение)
    """
    chunk_size = chunk_size or config.document.chunk_size
    max_chunks = max_chunks or config.document.max_chunks
    
    summaries = []
    for i, start in enumerate(range(0, len(text), chunk_size)):
        if i >= max_chunks:
            break
        chunk = text[start:start + chunk_size]
        summary = _retry_model_request(lambda: get_summary_from_model(chunk))
        summaries.append(summary)
        logger.info(f"Summary chunk {i + 1}: {len(summary)} символов")

    full_summary = "\n".join(summaries)
    decision_summary = _retry_model_request(lambda: get_summary_from_model(full_summary))
    final_decision = _retry_model_request(lambda: final_request_to_model(decision_summary))
    logger.info(f"✅ Ответ модели (длинный текст): {final_decision}")
    return full_summary, _normalize_decision(final_decision)


def _retry_model_request(func: Callable, max_retry: int = 3, delay: float = 5) -> str:
    """
    Выполняет запрос к модели с повторными попытками
    
    Args:
        func: Функция для выполнения
        max_retry: Максимальное количество попыток
        delay: Задержка между попытками
        
    Returns:
        Результат выполнения функции или "нет" в случае ошибки
    """
    for attempt in range(max_retry):
        try:
            result = func()
            if result:
                return str(result)
        except Exception as e:
            logger.error(f"❗ Ошибка при попытке {attempt + 1}: {e}")
        sleep(delay)
    return "нет"


def _normalize_decision(response: str) -> str:
    """
    Нормализует ответ модели
    
    Args:
        response: Ответ от модели
        
    Returns:
        Нормализованный ответ: "да" или "нет"
    """
    response = response.strip().lower()
    return "да" if response.startswith("да") else "нет"


def _save_result(announcement_id: str, summary: Optional[str] = None, final_score: Optional[str] = None) -> None:
    """
    Сохраняет результат обработки
    
    Args:
        announcement_id: ID объявления
        summary: Резюме (если есть)
        final_score: Финальная оценка (если есть)
    """
    try:
        result = {"announcement_id": announcement_id}
        if summary:
            result["summary"] = summary
        if final_score:
            result["final_score"] = final_score
        
        # Здесь можно добавить логику сохранения результата
        logger.debug(f"[{announcement_id}] Результат сохранен")
        
    except Exception as e:
        logger.error(f"[{announcement_id}] Ошибка при сохранении результата: {e}")

