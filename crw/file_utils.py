import base64
import hashlib
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import fitz
from PIL import Image
import pytesseract
import io
import docx
from config import config, configGS

logger = logging.getLogger(__name__)


def save_results_to_json(results: Union[Dict, List], name: str) -> bool:
    """
    Сохраняет результаты в JSON файл
    
    Args:
        results: Данные для сохранения
        name: Имя файла
        
    Returns:
        True если сохранение успешно, False в противном случае
    """
    try:
        # Используем конфигурацию из config
        file_path = config.data_dir / name
        
        # Создаем директорию, если ее нет
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем результаты в json
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump(results, json_file, ensure_ascii=False, indent=2)
        
        count = len(results) if isinstance(results, (dict, list)) else 1
        logger.info(f"Сохранено {count} записей в {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении в {name}: {e}")
        return False


def get_results_from_json(path: str) -> Dict[str, Any]:
    """
    Загружает данные из JSON файла
    
    Args:
        path: Путь к файлу относительно data_dir
        
    Returns:
        Словарь с данными или пустой словарь в случае ошибки
    """
    try:
        file_path = config.data_dir / path
        
        # Проверяем существование файла
        if not file_path.exists():
            logger.warning(f"Файл {file_path} не найден")
            return {}
        
        # Читаем данные из файла
        with open(file_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
            logger.info(f"Загружено {len(data)} записей из {file_path}")
            
            # Преобразуем данные в dict, если это необходимо
            if isinstance(data, list):
                # Если данные — это список, преобразуем его в словарь с announcement_id как ключ
                data_dict = {item.get("announcement_id"): item for item in data if item.get("announcement_id")}
                return data_dict
            return data  # Если данные уже в формате словаря, возвращаем их как есть
            
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON файла {path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {path}: {e}")
        return {}


def remove_negative_announcements(json_path: str) -> bool:
    """
    Удаляет объявления с отрицательными оценками
    
    Args:
        json_path: Путь к JSON файлу
        
    Returns:
        True если операция успешна, False в противном случае
    """
    try:
        file_path = Path(json_path)
        if not file_path.exists():
            logger.warning(f"Файл {json_path} не найден")
            return False
            
        with open(file_path, "r", encoding="utf-8") as f:
            announcements = json.load(f)
        
        if not isinstance(announcements, list):
            logger.error(f"Ожидался список в файле {json_path}")
            return False
        
        filtered = [
            ann for ann in announcements
            if "не" not in ann.get("score", "").lower()
        ]
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Файл {json_path} очищен успешно — осталось {len(filtered)} записей")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге JSON файла {json_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при обработке файла {json_path}: {e}")
        return False


pytesseract.pytesseract.tesseract_cmd = "tesseract"


def is_text_garbage(text: str, threshold: float = 0.4) -> bool:
    """
    Проверяет, является ли текст мусором (мало кириллических символов)
    
    Args:
        text: Текст для проверки
        threshold: Пороговое значение доли кириллических символов
        
    Returns:
        True если текст считается мусором, False в противном случае
    """
    if not text or not text.strip():
        return True
        
    cyrillic_chars = sum(1 for ch in text if 'А' <= ch <= 'я' or ch in 'ёЁіІңҢғҒүҮұҰқҚөӨһҺ')
    ratio = cyrillic_chars / max(1, len(text))
    return ratio < threshold


def extract_text_from_pdf_with_ocr(pdf_path: Union[str, Path]) -> str:
    """
    Извлекает текст из PDF файла с использованием OCR при необходимости
    
    Args:
        pdf_path: Путь к PDF файлу
        
    Returns:
        Извлеченный текст или пустая строка в случае ошибки
    """
    try:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF файл не найден: {pdf_path}")
            return ""
            
        doc = fitz.open(str(pdf_path))
        page_texts = []

        for page_num in range(len(doc)):
            try:
                page = doc.load_page(page_num)
                text = page.get_text().strip()

                if not text or is_text_garbage(text):
                    # Используем OCR для извлечения текста
                    pix = page.get_pixmap(dpi=250)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang='kaz+rus+eng')
                    source = "OCR"
                else:
                    source = "PDF text"

                page_texts.append(f"--- Страница {page_num + 1} ({source}) ---\n{text.strip()}")
                
            except Exception as e:
                logger.warning(f"Ошибка при обработке страницы {page_num + 1} в {pdf_path}: {e}")
                continue

        doc.close()
        return "\n".join(page_texts)

    except Exception as e:
        logger.error(f"Ошибка при обработке PDF файла {pdf_path}: {e}")
        return ""


def get_docx_or_pdf_content_by_announcement_id(announcement_id: str) -> Optional[str]:
    """
    Извлекает содержимое DOCX и PDF файлов для указанного объявления
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        Объединенный текст всех файлов или None в случае ошибки
    """
    try:
        folder_path = config.data_dir / str(announcement_id)
        
        logger.info(f"[ID {announcement_id}] Начата обработка")
        
        if not folder_path.is_dir():
            logger.warning(f"[ID {announcement_id}] Папка не найдена: {folder_path}")
            return None
        
        text_blocks = []
        
        # Обработка DOCX файлов
        docx_files = [f for f in folder_path.iterdir() if f.suffix.lower() == ".docx"]
        for docx_file in docx_files:
            try:
                doc = docx.Document(str(docx_file))
                text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                if text:
                    logger.info(f"[ID {announcement_id}] DOCX: {docx_file.name} обработан")
                    text_blocks.append(f"=== Файл: {docx_file.name} ===\n{text}")
            except Exception as e:
                logger.error(f"[ID {announcement_id}] Ошибка при чтении DOCX файла {docx_file}: {e}")
        
        # Обработка PDF файлов
        pdf_files = [f for f in folder_path.iterdir() if f.suffix.lower() == ".pdf"]
        for pdf_file in pdf_files:
            text = extract_text_from_pdf_with_ocr(pdf_file)
            if text:
                logger.info(f"[ID {announcement_id}] PDF: {pdf_file.name} обработан")
                text_blocks.append(f"=== Файл: {pdf_file.name} ===\n{text}")
        
        if text_blocks:
            return "\n\n".join(text_blocks)
        
        logger.warning(f"[ID {announcement_id}] Не найдено подходящих файлов")
        return None
        
    except Exception as e:
        logger.error(f"[ID {announcement_id}] Ошибка при обработке файлов: {e}")
        return None

def get_file_md5(announcement_id: str) -> Optional[str]:
    """
    Получает MD5 хеш первого найденного файла для указанного объявления
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        MD5 хеш файла или None в случае ошибки
    """
    try:
        folder_path = config.data_dir / str(announcement_id)
        
        logger.info(f"[ID {announcement_id}] Поиск файлов для получения MD5")
        
        if not folder_path.is_dir():
            logger.warning(f"[ID {announcement_id}] Папка не найдена: {folder_path}")
            return None
        
        # Ищем файлы с поддерживаемыми расширениями
        files = [f for f in folder_path.iterdir() 
                if f.is_file() and f.suffix.lower() in config.document.supported_extensions]
        
        if not files:
            logger.warning(f"[ID {announcement_id}] Нет DOCX или PDF файлов в папке {folder_path}")
            return None
        
        # Берем первый найденный файл
        file_path = files[0]
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        md5_hash = hash_md5.hexdigest()
        logger.info(f"[ID {announcement_id}] MD5 хеш получен для файла {file_path.name}: {md5_hash}")
        return md5_hash
        
    except Exception as e:
        logger.error(f"[ID {announcement_id}] Ошибка при получении MD5 файла: {e}")
        return None

def get_file_convert(announcement_id: str) -> Optional[str]:
    """
    Конвертирует первый найденный файл в base64 для указанного объявления
    
    Args:
        announcement_id: ID объявления
        
    Returns:
        Base64 строка файла или None в случае ошибки
    """
    try:
        folder_path = config.data_dir / str(announcement_id)
        
        logger.info(f"[ID {announcement_id}] Поиск файлов для конвертации в base64")
        
        if not folder_path.is_dir():
            logger.warning(f"[ID {announcement_id}] Папка не найдена: {folder_path}")
            return None
        
        # Ищем файлы с поддерживаемыми расширениями
        files = [f for f in folder_path.iterdir() 
                if f.is_file() and f.suffix.lower() in config.document.supported_extensions]
        
        if not files:
            logger.warning(f"[ID {announcement_id}] Нет DOCX или PDF файлов в папке {folder_path}")
            return None
        
        # Берем первый найденный файл
        file_path = files[0]
        
        with open(file_path, 'rb') as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
        
        logger.info(f"[ID {announcement_id}] Файл {file_path.name} успешно закодирован в base64")
        return encoded_string
        
    except Exception as e:
        logger.error(f"[ID {announcement_id}] Ошибка при кодировании файла в base64: {e}")
        return None