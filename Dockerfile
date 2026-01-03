FROM python:3.11-slim

# Метаданные
LABEL maintainer="education-platform"
LABEL version="1.0"

# Устанавливаем системные зависимости (совместимые с Debian 12/trixie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    gcc \
    g++ \
    python3-dev \
    # Для OpenCV и графики
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # Для линейной алгебры (вместо atlas)
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости ПОЭТАПНО
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools

# Сначала устанавливаем numpy отдельно (важно для OpenCV)
RUN pip install --no-cache-dir numpy==1.26.4

# Затем устанавливаем остальные зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем необходимые директории
RUN mkdir -p uploads records static data html_dir

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["python", "-u", "bot.py"]