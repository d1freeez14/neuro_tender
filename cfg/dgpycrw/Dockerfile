# Используем официальный Python образ
FROM python:3.11-slim

# Метаданные
LABEL maintainer="neuro_tender_team"
LABEL description="Neuro Tender - система анализа тендеров"
LABEL version="2.0"

# Установка переменных окружения
ENV TZ=Asia/Almaty \
    PYTHONPATH=/app/crw \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Создание пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    vim \
    gcc \
    g++ \
    python3-dev \
    libfreetype6-dev \
    libmupdf-dev \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-kaz \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Обновление pip и установка Python зависимостей
RUN pip install --upgrade pip setuptools wheel

# Копирование requirements.txt и установка зависимостей
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Создание необходимых директорий
RUN mkdir -p /app/log /app/cnt /app/data && \
    chown -R appuser:appuser /app

# Копирование скрипта запуска
COPY entry.sh /opt/entry.sh
RUN chmod +x /opt/entry.sh

# Переключение на пользователя appuser
USER appuser

# Рабочая директория
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Точка входа
ENTRYPOINT ["/opt/entry.sh"]
